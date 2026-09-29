"""
Official IRIS Counsellor Dashboard, Student Assignment, Counselling Notes & Follow-Up Management (Phase 6).
Implements:
- GET  /api/counsellor/dashboard: Aggregated real-time metrics for assigned students, reports, and follow-ups
- GET  /api/counsellor/students: Directory of students strictly assigned to the authenticated counsellor
- GET  /api/counsellor/students/{studentId}: Detailed assigned student profile and assessment history
- GET  /api/counsellor/assessments/{assessmentId}: Assigned assessment inspection including dual-scan & analysis state
- GET  /api/counsellor/reports/{assessmentId}: Official structured report retrieval for assigned assessment
- GET  /api/counsellor/follow-ups: Consolidated follow-up consultations assigned to the counsellor
- POST /api/assessments/{assessmentId}/notes: Create counsellor clinical observation note
- GET  /api/assessments/{assessmentId}/notes: Retrieve clinical notes for an assigned assessment
- PATCH /api/notes/{noteId}: Update an existing counselling note
- DELETE /api/notes/{noteId}: Remove an existing counselling note
- POST /api/assessments/{assessmentId}/follow-ups: Schedule a follow-up consultation
- GET  /api/assessments/{assessmentId}/follow-ups: Retrieve scheduled follow-ups for an assessment
- PATCH /api/follow-ups/{followUpId}: Update follow-up status (Pending, Completed, Cancelled, Overdue) or notes
- GET  /api/admin/counsellors: Admin directory of registered counsellors
- GET  /api/admin/assignments: Admin overview of student-counsellor assignments
- POST /api/admin/assignments: Admin assigns a counsellor to an assessment/student
- PATCH /api/admin/assignments/{assignmentId}/revoke: Admin revokes an active assignment

Conforms strictly to:
- IRIS_Backend_Detailed_Requirements.docx
- IRIS_Frontend_Detailed_Requirements.docx
- Strict RBAC: Counsellor isolated strictly to assigned students/assessments (HTTP 403 on unassigned access)
- Audit logging of all assignment, note, follow-up, and review actions (WITHOUT private note content)
- Zero data fabrication and zero alteration of biometric analysis values
"""

import os
import json
import time
import uuid
import sqlite3
from datetime import datetime
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, HTTPException, Depends, status, Query, Body
from pydantic import BaseModel, Field

from database_official import get_connection
from api.students import get_required_user

router = APIRouter(tags=["Official IRIS Counsellor Management"])


# =====================================================================
# PYDANTIC SCHEMAS
# =====================================================================

class CreateNoteRequest(BaseModel):
    note: str = Field(..., min_length=1, max_length=4000, description="Counsellor clinical or advisory note")


class UpdateNoteRequest(BaseModel):
    note: str = Field(..., min_length=1, max_length=4000, description="Updated note text")


class CreateFollowUpRequest(BaseModel):
    follow_up_date: str = Field(..., description="Target date for follow-up (YYYY-MM-DD)")
    notes: Optional[str] = Field(None, max_length=1000, description="Objective or notes for the session")


class UpdateFollowUpRequest(BaseModel):
    status: Optional[str] = Field(None, description="Pending, Completed, Cancelled, or Overdue")
    follow_up_date: Optional[str] = Field(None, description="Updated follow-up date")
    notes: Optional[str] = Field(None, description="Updated session notes")


class AdminAssignCounsellorRequest(BaseModel):
    student_id: str = Field(..., description="Target student identifier")
    assessment_id: str = Field(..., description="Target assessment identifier")
    counsellor_id: str = Field(..., description="Target counsellor username")


# =====================================================================
# AUTHORIZATION & AUDIT HELPERS
# =====================================================================

def _log_audit(
    cursor: sqlite3.Cursor,
    user_id: str,
    role: str,
    action: str,
    assessment_id: Optional[str],
    entity_type: str,
    entity_id: Optional[str] = None,
    status_str: str = "SUCCESS",
    safe_metadata: Optional[Dict[str, Any]] = None
) -> None:
    """Records sanitized audit log entry without secrets, tokens, or private note contents."""
    audit_id = f"AUD-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    meta_json = json.dumps(safe_metadata) if safe_metadata else None
    cursor.execute("""
    INSERT INTO audit_logs (
        audit_id, user_id, role, action, assessment_id,
        entity_type, entity_id, status, safe_metadata_json, timestamp
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        audit_id, user_id, role, action, assessment_id,
        entity_type, entity_id or assessment_id, status_str, meta_json, ts
    ))


def verify_counsellor_role(current_user: Dict[str, Any]) -> str:
    """Ensures user has Counsellor or Admin role."""
    role = current_user.get("role")
    if role not in ("Admin", "Counselor", "Counsellor"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access forbidden: Role '{role}' is not authorized for counsellor operations"
        )
    return current_user.get("username", "")


def verify_active_assignment(cursor: sqlite3.Cursor, current_user: Dict[str, Any], assessment_id: str) -> Dict[str, Any]:
    """
    Strictly verifies active assignment for Counsellors.
    - Admin: permitted unconditionally across all assessments.
    - Counsellor: must have an active row in counsellor_assignments where is_active = 1.
    - Student: rejected with 403.
    Returns dictionary with assessment_id and student_id.
    """
    role = current_user.get("role")
    username = current_user.get("username", "")

    cursor.execute("""
        SELECT assessment_id, student_id, status
        FROM assessments WHERE assessment_id = ?;
    """, (assessment_id,))
    asm_row = cursor.fetchone()
    if not asm_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment '{assessment_id}' was not found"
        )

    t_asm_id, t_stu_id, t_status = asm_row

    if role == "Admin":
        return {"assessment_id": t_asm_id, "student_id": t_stu_id, "status": t_status}

    if role in ("Counselor", "Counsellor"):
        cursor.execute("""
            SELECT COUNT(*) FROM counsellor_assignments
            WHERE (assessment_id = ? OR student_id = ?)
              AND counsellor_id = ?
              AND is_active = 1
              AND status = 'ACTIVE';
        """, (assessment_id, t_stu_id, username))
        is_assigned = cursor.fetchone()[0] > 0
        if not is_assigned:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: Counsellor '{username}' is not assigned to assessment '{assessment_id}'"
            )
        return {"assessment_id": t_asm_id, "student_id": t_stu_id, "status": t_status}

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Insufficient permissions to access assessment"
    )


def verify_active_student_assignment(cursor: sqlite3.Cursor, current_user: Dict[str, Any], student_id: str) -> Dict[str, Any]:
    """
    Strictly verifies that a Counsellor is assigned to the given student_id.
    """
    role = current_user.get("role")
    username = current_user.get("username", "")

    cursor.execute("SELECT student_id, student_name FROM students WHERE student_id = ?;", (student_id,))
    stu_row = cursor.fetchone()
    if not stu_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student '{student_id}' was not found"
        )

    if role == "Admin":
        return {"student_id": stu_row[0], "student_name": stu_row[1]}

    if role in ("Counselor", "Counsellor"):
        cursor.execute("""
            SELECT COUNT(*) FROM counsellor_assignments
            WHERE student_id = ? AND counsellor_id = ? AND is_active = 1 AND status = 'ACTIVE';
        """, (student_id, username))
        if cursor.fetchone()[0] == 0:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: Counsellor '{username}' is not assigned to student '{student_id}'"
            )
        return {"student_id": stu_row[0], "student_name": stu_row[1]}

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Insufficient permissions"
    )


# =====================================================================
# 1. COUNSELLOR DASHBOARD METRICS
# =====================================================================

@router.get(
    "/api/counsellor/dashboard",
    summary="Get aggregated statistics and summary for counsellor dashboard",
    status_code=status.HTTP_200_OK
)
async def get_counsellor_dashboard(
    current_user: Dict[str, Any] = Depends(get_required_user)
):
    """
    GET /api/counsellor/dashboard
    Returns real-time KPI metrics strictly for the authenticated counsellor's assigned students:
    - assigned_students_count
    - reports_ready_count
    - pending_counselling_count
    - active_follow_ups_count
    - recent_activity
    """
    verify_counsellor_role(current_user)
    username = current_user.get("username", "")
    role = current_user.get("role", "")

    conn = get_connection()
    try:
        cur = conn.cursor()

        # Assigned Students Count
        if role == "Admin":
            cur.execute("SELECT COUNT(DISTINCT student_id) FROM counsellor_assignments WHERE is_active = 1;")
        else:
            cur.execute("""
                SELECT COUNT(DISTINCT student_id)
                FROM counsellor_assignments
                WHERE counsellor_id = ? AND is_active = 1 AND status = 'ACTIVE';
            """, (username,))
        assigned_students_count = cur.fetchone()[0]

        # Assigned Assessments
        if role == "Admin":
            cur.execute("""
                SELECT DISTINCT a.assessment_id
                FROM assessments a
                JOIN counsellor_assignments ca ON a.assessment_id = ca.assessment_id
                WHERE ca.is_active = 1;
            """)
        else:
            cur.execute("""
                SELECT DISTINCT a.assessment_id
                FROM assessments a
                JOIN counsellor_assignments ca ON a.assessment_id = ca.assessment_id
                WHERE ca.counsellor_id = ? AND ca.is_active = 1 AND ca.status = 'ACTIVE';
            """, (username,))
        assigned_asm_ids = [r[0] for r in cur.fetchall()]

        reports_ready_count = 0
        pending_counselling_count = 0
        if assigned_asm_ids:
            placeholders = ",".join(["?"] * len(assigned_asm_ids))
            cur.execute(f"""
                SELECT COUNT(*) FROM reports
                WHERE assessment_id IN ({placeholders}) AND status = 'REPORT_READY';
            """, tuple(assigned_asm_ids))
            reports_ready_count = cur.fetchone()[0]

            cur.execute(f"""
                SELECT COUNT(*) FROM reports
                WHERE assessment_id IN ({placeholders}) AND status = 'REPORT_READY' AND reviewed_status = 0;
            """, tuple(assigned_asm_ids))
            pending_counselling_count = cur.fetchone()[0]

        # Active Follow-ups Count
        if role == "Admin":
            cur.execute("SELECT COUNT(*) FROM follow_ups WHERE status = 'Pending';")
        else:
            cur.execute("""
                SELECT COUNT(*) FROM follow_ups
                WHERE counsellor_id = ? AND status = 'Pending';
            """, (username,))
        active_follow_ups_count = cur.fetchone()[0]

        # Recent Activity (Notes & Follow-ups)
        if role == "Admin":
            cur.execute("""
                SELECT 'note' as type, note_id as id, assessment_id, counsellor_id, created_at
                FROM counselling_notes
                ORDER BY id DESC LIMIT 5;
            """)
        else:
            cur.execute("""
                SELECT 'note' as type, note_id as id, assessment_id, counsellor_id, created_at
                FROM counselling_notes
                WHERE counsellor_id = ?
                ORDER BY id DESC LIMIT 5;
            """, (username,))
        recent_notes = [
            {"type": r[0], "id": r[1], "assessment_id": r[2], "counsellor_id": r[3], "timestamp": r[4]}
            for r in cur.fetchall()
        ]

        return {
            "status": "success",
            "counsellor_id": username,
            "role": role,
            "metrics": {
                "assigned_students": assigned_students_count,
                "reports_ready": reports_ready_count,
                "pending_counselling": pending_counselling_count,
                "active_follow_ups": active_follow_ups_count
            },
            "recent_activity": recent_notes
        }
    finally:
        conn.close()


# =====================================================================
# 2. ASSIGNED STUDENTS DIRECTORY
# =====================================================================

@router.get(
    "/api/counsellor/students",
    summary="List students actively assigned to the authenticated counsellor",
    status_code=status.HTTP_200_OK
)
async def list_assigned_students(
    search: Optional[str] = Query(None, description="Filter by student ID or name"),
    current_user: Dict[str, Any] = Depends(get_required_user)
):
    """
    GET /api/counsellor/students
    Strictly isolated: Counsellors only see students assigned to them.
    Admins see all assigned students.
    """
    verify_counsellor_role(current_user)
    username = current_user.get("username", "")
    role = current_user.get("role", "")

    conn = get_connection()
    try:
        cur = conn.cursor()

        query = """
            SELECT 
                s.student_id,
                s.student_name,
                a.assessment_id,
                a.status AS assessment_status,
                a.created_at AS assessment_created_at,
                ca.assigned_at,
                ca.status AS assignment_status,
                ca.counsellor_id,
                r.report_id,
                r.status AS report_status,
                COALESCE(r.reviewed_status, 0) AS reviewed_status,
                (SELECT status FROM eye_scans WHERE assessment_id = a.assessment_id AND eye_side = 'LEFT' AND is_active = 1 LIMIT 1) AS left_scan_status,
                (SELECT status FROM eye_scans WHERE assessment_id = a.assessment_id AND eye_side = 'RIGHT' AND is_active = 1 LIMIT 1) AS right_scan_status,
                (SELECT status FROM follow_ups WHERE assessment_id = a.assessment_id ORDER BY id DESC LIMIT 1) AS follow_up_status
            FROM counsellor_assignments ca
            JOIN students s ON ca.student_id = s.student_id
            JOIN assessments a ON ca.assessment_id = a.assessment_id
            LEFT JOIN reports r ON a.assessment_id = r.assessment_id
            WHERE ca.is_active = 1 AND ca.status = 'ACTIVE'
        """
        params = []
        if role != "Admin":
            query += " AND ca.counsellor_id = ?"
            params.append(username)

        if search:
            s_term = f"%{search.strip()}%"
            query += " AND (s.student_id LIKE ? OR s.student_name LIKE ? OR a.assessment_id LIKE ?)"
            params.extend([s_term, s_term, s_term])

        query += " ORDER BY ca.id DESC;"

        cur.execute(query, tuple(params))
        rows = cur.fetchall()

        students = [
            {
                "student_id": r[0],
                "student_name": r[1],
                "assessment_id": r[2],
                "assessment_status": r[3],
                "assessment_created_at": r[4],
                "assigned_at": r[5],
                "assignment_status": r[6],
                "counsellor_id": r[7],
                "report_id": r[8],
                "report_status": r[9] or "NOT_GENERATED",
                "reviewed_status": bool(r[10]),
                "left_scan_status": r[11] or "Pending",
                "right_scan_status": r[12] or "Pending",
                "follow_up_status": r[13] or "None"
            }
            for r in rows
        ]

        return {
            "status": "success",
            "counsellor_id": username,
            "count": len(students),
            "students": students
        }
    finally:
        conn.close()


# =====================================================================
# 3. SINGLE ASSIGNED STUDENT DETAILS
# =====================================================================

@router.get(
    "/api/counsellor/students/{studentId}",
    summary="Get single assigned student details and assessments",
    status_code=status.HTTP_200_OK
)
async def get_counsellor_student_details(
    studentId: str,
    current_user: Dict[str, Any] = Depends(get_required_user)
):
    """
    GET /api/counsellor/students/{studentId}
    Enforces active assignment: returns 403 if unassigned counsellor attempts lookup.
    """
    verify_counsellor_role(current_user)
    clean_stu_id = studentId.strip()

    conn = get_connection()
    try:
        cur = conn.cursor()
        stu_meta = verify_active_student_assignment(cur, current_user, clean_stu_id)

        # Profile details
        cur.execute("""
            SELECT age, gender, school_college, stream, course, location, photo_path, created_on
            FROM student_profiles WHERE student_id = ?;
        """, (clean_stu_id,))
        prof_row = cur.fetchone()

        profile_data = {
            "age": prof_row[0] if prof_row else None,
            "gender": prof_row[1] if prof_row else None,
            "school_college": prof_row[2] if prof_row else None,
            "stream": prof_row[3] if prof_row else None,
            "course": prof_row[4] if prof_row else None,
            "location": prof_row[5] if prof_row else None,
            "photo_url": f"/api/media/{prof_row[6]}" if prof_row and prof_row[6] else None
        }

        # Assessments for this student
        cur.execute("""
            SELECT a.assessment_id, a.status, a.created_at, a.completed_at,
                   r.report_id, r.status AS report_status, COALESCE(r.reviewed_status, 0)
            FROM assessments a
            LEFT JOIN reports r ON a.assessment_id = r.assessment_id
            WHERE a.student_id = ?
            ORDER BY a.id DESC;
        """, (clean_stu_id,))
        asms = [
            {
                "assessment_id": r[0],
                "status": r[1],
                "created_at": r[2],
                "completed_at": r[3],
                "report_id": r[4],
                "report_status": r[5] or "NOT_GENERATED",
                "reviewed_status": bool(r[6])
            }
            for r in cur.fetchall()
        ]

        return {
            "status": "success",
            "student_id": stu_meta["student_id"],
            "student_name": stu_meta["student_name"],
            "profile": profile_data,
            "assessments": asms
        }
    finally:
        conn.close()


# =====================================================================
# 4. ASSIGNED ASSESSMENT DETAILS
# =====================================================================

@router.get(
    "/api/counsellor/assessments/{assessmentId}",
    summary="Get assigned assessment status, scan details, and report availability",
    status_code=status.HTTP_200_OK
)
async def get_counsellor_assessment_details(
    assessmentId: str,
    current_user: Dict[str, Any] = Depends(get_required_user)
):
    """
    GET /api/counsellor/assessments/{assessmentId}
    Enforces active assignment: returns 403 if unassigned counsellor attempts lookup.
    """
    verify_counsellor_role(current_user)
    clean_asm_id = assessmentId.strip()

    conn = get_connection()
    try:
        cur = conn.cursor()
        asm_info = verify_active_assignment(cur, current_user, clean_asm_id)

        # Scans
        cur.execute("""
            SELECT scan_id, eye_side, status, attempt_number, created_at, completed_at
            FROM eye_scans WHERE assessment_id = ? AND is_active = 1;
        """, (clean_asm_id,))
        scans = {
            r[1]: {
                "scan_id": r[0],
                "status": r[2],
                "attempt_number": r[3],
                "created_at": r[4],
                "completed_at": r[5]
            }
            for r in cur.fetchall()
        }

        # Analysis
        cur.execute("SELECT model_version, created_at FROM analysis_results WHERE assessment_id = ?;", (clean_asm_id,))
        a_row = cur.fetchone()
        analysis_info = {"model_version": a_row[0], "completed_at": a_row[1]} if a_row else None

        # Report
        cur.execute("""
            SELECT report_id, version, status, generated_at, reviewed_status, reviewed_by, reviewed_at
            FROM reports WHERE assessment_id = ? ORDER BY id DESC LIMIT 1;
        """, (clean_asm_id,))
        rep_row = cur.fetchone()
        report_info = {
            "report_id": rep_row[0],
            "version": rep_row[1],
            "status": rep_row[2],
            "generated_at": rep_row[3],
            "reviewed_status": bool(rep_row[4]),
            "reviewed_by": rep_row[5],
            "reviewed_at": rep_row[6]
        } if rep_row else None

        return {
            "status": "success",
            "assessment_id": clean_asm_id,
            "student_id": asm_info["student_id"],
            "assessment_status": asm_info["status"],
            "scans": scans,
            "analysis": analysis_info,
            "report": report_info
        }
    finally:
        conn.close()


# =====================================================================
# 5. ASSIGNED REPORT RETRIEVAL
# =====================================================================

@router.get(
    "/api/counsellor/reports/{assessmentId}",
    summary="Retrieve official 10-section report for assigned assessment",
    status_code=status.HTTP_200_OK
)
async def get_counsellor_report(
    assessmentId: str,
    current_user: Dict[str, Any] = Depends(get_required_user)
):
    """
    GET /api/counsellor/reports/{assessmentId}
    Retrieves the exact 10-section structured report generated in Phase 5B.
    Enforces active assignment: returns 403 if unassigned.
    """
    verify_counsellor_role(current_user)
    clean_asm_id = assessmentId.strip()
    user_id = current_user.get("username", "")
    role = current_user.get("role", "")

    conn = get_connection()
    try:
        cur = conn.cursor()
        verify_active_assignment(cur, current_user, clean_asm_id)

        cur.execute("""
            SELECT report_id, version, status, generated_at, pdf_reference,
                   reviewed_status, reviewed_by, reviewed_at
            FROM reports WHERE assessment_id = ? ORDER BY id DESC LIMIT 1;
        """, (clean_asm_id,))
        rep_row = cur.fetchone()
        if not rep_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Report has not been generated for assessment '{clean_asm_id}'"
            )

        report_id, rep_version, rep_status, gen_at, pdf_ref, rev_stat, rev_by, rev_at = rep_row

        cur.execute("""
            SELECT section_key, title, content_json, order_num
            FROM report_sections WHERE report_id = ? ORDER BY order_num ASC;
        """, (report_id,))
        sections = {r[0]: json.loads(r[2]) for r in cur.fetchall()}

        _log_audit(
            cur, user_id, role, "REPORT_RETRIEVED", clean_asm_id,
            entity_type="report", entity_id=report_id,
            safe_metadata={"action": "counsellor_view", "version": rep_version}
        )
        conn.commit()

        return {
            "status": "success",
            "report_id": report_id,
            "assessment_id": clean_asm_id,
            "version": rep_version,
            "report_status": rep_status,
            "generated_at": gen_at,
            "pdf_reference": pdf_ref,
            "reviewed_status": bool(rev_stat),
            "reviewed_by": rev_by,
            "reviewed_at": rev_at,
            "sections": sections
        }
    finally:
        conn.close()


# =====================================================================
# 6. COUNSELLING NOTES ENDPOINTS
# =====================================================================

@router.post(
    "/api/assessments/{assessmentId}/notes",
    summary="Create counsellor clinical or advisory note",
    status_code=status.HTTP_201_CREATED
)
async def create_counselling_note(
    assessmentId: str,
    payload: CreateNoteRequest,
    current_user: Dict[str, Any] = Depends(get_required_user)
):
    """
    POST /api/assessments/{assessmentId}/notes
    Authorization: Counsellor (assigned) or Admin.
    Student -> 403 Forbidden.
    Unassigned Counsellor -> 403 Forbidden.
    Audit: COUNSELLING_NOTE_CREATED (WITHOUT logging note content).
    """
    verify_counsellor_role(current_user)
    clean_asm_id = assessmentId.strip()
    user_id = current_user.get("username", "")
    role = current_user.get("role", "")
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_connection()
    try:
        cur = conn.cursor()
        asm_info = verify_active_assignment(cur, current_user, clean_asm_id)

        note_id = f"NOT-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        cur.execute("""
            INSERT INTO counselling_notes (note_id, assessment_id, counsellor_id, note, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?);
        """, (note_id, clean_asm_id, user_id, payload.note.strip(), now_str, now_str))

        _log_audit(
            cur, user_id, role, "COUNSELLING_NOTE_CREATED", clean_asm_id,
            entity_type="counselling_note", entity_id=note_id,
            safe_metadata={"note_id": note_id, "assessment_id": clean_asm_id}
        )
        conn.commit()

        return {
            "status": "success",
            "message": "Counselling note created successfully",
            "note_id": note_id,
            "note": {
                "note_id": note_id,
                "assessment_id": clean_asm_id,
                "student_id": asm_info["student_id"],
                "counsellor_id": user_id,
                "note": payload.note.strip(),
                "created_at": now_str,
                "updated_at": now_str
            }
        }
    finally:
        conn.close()


@router.get(
    "/api/assessments/{assessmentId}/notes",
    summary="Retrieve clinical notes for an assigned assessment",
    status_code=status.HTTP_200_OK
)
async def get_counselling_notes(
    assessmentId: str,
    current_user: Dict[str, Any] = Depends(get_required_user)
):
    """
    GET /api/assessments/{assessmentId}/notes
    Authorization: Admin or assigned Counsellor.
    Unassigned Counsellor -> 403 Forbidden.
    """
    clean_asm_id = assessmentId.strip()

    conn = get_connection()
    try:
        cur = conn.cursor()
        verify_active_assignment(cur, current_user, clean_asm_id)

        cur.execute("""
            SELECT note_id, assessment_id, counsellor_id, note, created_at, updated_at
            FROM counselling_notes
            WHERE assessment_id = ?
            ORDER BY created_at ASC;
        """, (clean_asm_id,))
        notes = [
            {
                "note_id": r[0],
                "assessment_id": r[1],
                "counsellor_id": r[2],
                "note": r[3],
                "created_at": r[4],
                "updated_at": r[5]
            }
            for r in cur.fetchall()
        ]

        return {
            "status": "success",
            "assessment_id": clean_asm_id,
            "count": len(notes),
            "notes": notes
        }
    finally:
        conn.close()


@router.patch(
    "/api/notes/{noteId}",
    summary="Update an existing counselling note",
    status_code=status.HTTP_200_OK
)
async def update_counselling_note(
    noteId: str,
    payload: UpdateNoteRequest,
    current_user: Dict[str, Any] = Depends(get_required_user)
):
    """
    PATCH /api/notes/{noteId}
    Only the creating counsellor or Admin can modify the note.
    Audit: COUNSELLING_NOTE_UPDATED (WITHOUT logging note content).
    """
    verify_counsellor_role(current_user)
    clean_note_id = noteId.strip()
    user_id = current_user.get("username", "")
    role = current_user.get("role", "")
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT assessment_id, counsellor_id FROM counselling_notes WHERE note_id = ?;", (clean_note_id,))
        nrow = cur.fetchone()
        if not nrow:
            raise HTTPException(status_code=404, detail=f"Note '{clean_note_id}' was not found")

        asm_id, creator_counsellor = nrow
        if role != "Admin" and creator_counsellor != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You may only edit notes created by your account"
            )

        cur.execute("""
            UPDATE counselling_notes
            SET note = ?, updated_at = ?
            WHERE note_id = ?;
        """, (payload.note.strip(), now_str, clean_note_id))

        _log_audit(
            cur, user_id, role, "COUNSELLING_NOTE_UPDATED", asm_id,
            entity_type="counselling_note", entity_id=clean_note_id,
            safe_metadata={"note_id": clean_note_id}
        )
        conn.commit()

        return {
            "status": "success",
            "message": "Note updated successfully",
            "note_id": clean_note_id,
            "updated_at": now_str
        }
    finally:
        conn.close()


@router.delete(
    "/api/notes/{noteId}",
    summary="Delete a counselling note",
    status_code=status.HTTP_200_OK
)
async def delete_counselling_note(
    noteId: str,
    current_user: Dict[str, Any] = Depends(get_required_user)
):
    """
    DELETE /api/notes/{noteId}
    Only creator or Admin can delete note.
    """
    verify_counsellor_role(current_user)
    clean_note_id = noteId.strip()
    user_id = current_user.get("username", "")
    role = current_user.get("role", "")

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT assessment_id, counsellor_id FROM counselling_notes WHERE note_id = ?;", (clean_note_id,))
        nrow = cur.fetchone()
        if not nrow:
            raise HTTPException(status_code=404, detail=f"Note '{clean_note_id}' was not found")

        asm_id, creator = nrow
        if role != "Admin" and creator != user_id:
            raise HTTPException(status_code=403, detail="Forbidden")

        cur.execute("DELETE FROM counselling_notes WHERE note_id = ?;", (clean_note_id,))
        _log_audit(
            cur, user_id, role, "COUNSELLING_NOTE_DELETED", asm_id,
            entity_type="counselling_note", entity_id=clean_note_id
        )
        conn.commit()

        return {"status": "success", "message": "Note deleted successfully"}
    finally:
        conn.close()


# =====================================================================
# 7. FOLLOW-UPS ENDPOINTS
# =====================================================================

@router.post(
    "/api/assessments/{assessmentId}/follow-ups",
    summary="Schedule a follow-up consultation",
    status_code=status.HTTP_201_CREATED
)
async def create_follow_up(
    assessmentId: str,
    payload: CreateFollowUpRequest,
    current_user: Dict[str, Any] = Depends(get_required_user)
):
    """
    POST /api/assessments/{assessmentId}/follow-ups
    Authorization: Assigned Counsellor or Admin.
    Student -> 403 Forbidden.
    Unassigned Counsellor -> 403 Forbidden.
    Audit: FOLLOW_UP_CREATED.
    """
    verify_counsellor_role(current_user)
    clean_asm_id = assessmentId.strip()
    user_id = current_user.get("username", "")
    role = current_user.get("role", "")
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_connection()
    try:
        cur = conn.cursor()
        asm_info = verify_active_assignment(cur, current_user, clean_asm_id)

        fu_id = f"FOL-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        cur.execute("""
            INSERT INTO follow_ups (follow_up_id, assessment_id, counsellor_id, follow_up_date, status, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'Pending', ?, ?, ?);
        """, (fu_id, clean_asm_id, user_id, payload.follow_up_date.strip(), payload.notes or "", now_str, now_str))

        _log_audit(
            cur, user_id, role, "FOLLOW_UP_CREATED", clean_asm_id,
            entity_type="follow_up", entity_id=fu_id,
            safe_metadata={"follow_up_id": fu_id, "follow_up_date": payload.follow_up_date.strip()}
        )
        conn.commit()

        return {
            "status": "success",
            "message": "Follow-up scheduled successfully",
            "follow_up_id": fu_id,
            "follow_up_status": "Pending",
            "follow_up": {
                "follow_up_id": fu_id,
                "assessment_id": clean_asm_id,
                "student_id": asm_info["student_id"],
                "counsellor_id": user_id,
                "follow_up_date": payload.follow_up_date.strip(),
                "status": "Pending",
                "notes": payload.notes,
                "created_at": now_str
            }
        }
    finally:
        conn.close()


@router.get(
    "/api/assessments/{assessmentId}/follow-ups",
    summary="Retrieve scheduled follow-ups for an assessment",
    status_code=status.HTTP_200_OK
)
async def get_assessment_follow_ups(
    assessmentId: str,
    current_user: Dict[str, Any] = Depends(get_required_user)
):
    """
    GET /api/assessments/{assessmentId}/follow-ups
    Authorization: Admin or assigned Counsellor.
    Unassigned Counsellor -> 403 Forbidden.
    """
    clean_asm_id = assessmentId.strip()

    conn = get_connection()
    try:
        cur = conn.cursor()
        verify_active_assignment(cur, current_user, clean_asm_id)

        cur.execute("""
            SELECT follow_up_id, assessment_id, counsellor_id, follow_up_date, status, notes, created_at, updated_at
            FROM follow_ups
            WHERE assessment_id = ?
            ORDER BY follow_up_date ASC;
        """, (clean_asm_id,))
        follow_ups = [
            {
                "follow_up_id": r[0],
                "assessment_id": r[1],
                "counsellor_id": r[2],
                "follow_up_date": r[3],
                "status": r[4],
                "notes": r[5],
                "created_at": r[6],
                "updated_at": r[7]
            }
            for r in cur.fetchall()
        ]

        return {
            "status": "success",
            "assessment_id": clean_asm_id,
            "count": len(follow_ups),
            "follow_ups": follow_ups
        }
    finally:
        conn.close()


@router.get(
    "/api/counsellor/follow-ups",
    summary="List all follow-ups assigned to the authenticated counsellor",
    status_code=status.HTTP_200_OK
)
async def list_counsellor_follow_ups(
    status_filter: Optional[str] = Query(None, description="Pending, Completed, Cancelled, Overdue"),
    current_user: Dict[str, Any] = Depends(get_required_user)
):
    """
    GET /api/counsellor/follow-ups
    Lists all follow-ups assigned to this counsellor across all their students.
    """
    verify_counsellor_role(current_user)
    username = current_user.get("username", "")
    role = current_user.get("role", "")

    conn = get_connection()
    try:
        cur = conn.cursor()
        query = """
            SELECT 
                f.follow_up_id,
                f.assessment_id,
                a.student_id,
                s.student_name,
                f.counsellor_id,
                f.follow_up_date,
                f.status,
                f.notes,
                f.created_at,
                f.updated_at
            FROM follow_ups f
            JOIN assessments a ON f.assessment_id = a.assessment_id
            JOIN students s ON a.student_id = s.student_id
            WHERE 1=1
        """
        params = []
        if role != "Admin":
            query += " AND f.counsellor_id = ?"
            params.append(username)

        if status_filter:
            query += " AND f.status = ?"
            params.append(status_filter.strip())

        query += " ORDER BY f.follow_up_date ASC;"

        cur.execute(query, tuple(params))
        items = [
            {
                "follow_up_id": r[0],
                "assessment_id": r[1],
                "student_id": r[2],
                "student_name": r[3],
                "counsellor_id": r[4],
                "follow_up_date": r[5],
                "status": r[6],
                "notes": r[7],
                "created_at": r[8],
                "updated_at": r[9]
            }
            for r in cur.fetchall()
        ]

        return {
            "status": "success",
            "counsellor_id": username,
            "count": len(items),
            "follow_ups": items
        }
    finally:
        conn.close()


@router.patch(
    "/api/follow-ups/{followUpId}",
    summary="Update follow-up status, schedule date, or notes",
    status_code=status.HTTP_200_OK
)
async def update_follow_up(
    followUpId: str,
    payload: UpdateFollowUpRequest,
    current_user: Dict[str, Any] = Depends(get_required_user)
):
    """
    PATCH /api/follow-ups/{followUpId}
    Updates status: 'Pending', 'Completed', 'Cancelled', 'Overdue'.
    Audit: FOLLOW_UP_UPDATED.
    """
    verify_counsellor_role(current_user)
    clean_fu_id = followUpId.strip()
    user_id = current_user.get("username", "")
    role = current_user.get("role", "")
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT assessment_id, counsellor_id, status FROM follow_ups WHERE follow_up_id = ?;", (clean_fu_id,))
        fu_row = cur.fetchone()
        if not fu_row:
            raise HTTPException(status_code=404, detail=f"Follow-up '{clean_fu_id}' was not found")

        asm_id, assigned_counsellor, current_status = fu_row
        if role != "Admin" and assigned_counsellor != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You may only modify follow-ups assigned to your account"
            )

        updates = []
        params = []
        if payload.status:
            valid_statuses = ("Pending", "Completed", "Cancelled", "Overdue")
            if payload.status not in valid_statuses:
                raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
            updates.append("status = ?")
            params.append(payload.status)

        if payload.follow_up_date:
            updates.append("follow_up_date = ?")
            params.append(payload.follow_up_date.strip())

        if payload.notes is not None:
            updates.append("notes = ?")
            params.append(payload.notes.strip())

        if not updates:
            return {"status": "success", "message": "No changes requested", "follow_up_id": clean_fu_id}

        updates.append("updated_at = ?")
        params.append(now_str)
        params.append(clean_fu_id)

        cur.execute(f"UPDATE follow_ups SET {', '.join(updates)} WHERE follow_up_id = ?;", tuple(params))

        _log_audit(
            cur, user_id, role, "FOLLOW_UP_UPDATED", asm_id,
            entity_type="follow_up", entity_id=clean_fu_id,
            safe_metadata={"follow_up_id": clean_fu_id, "new_status": payload.status}
        )
        conn.commit()

        return {
            "status": "success",
            "message": "Follow-up updated successfully",
            "follow_up_id": clean_fu_id,
            "status": payload.status or current_status,
            "updated_at": now_str
        }
    finally:
        conn.close()


# =====================================================================
# 8. ADMIN ASSIGNMENT MANAGEMENT
# =====================================================================

@router.get(
    "/api/admin/counsellors",
    summary="Admin directory of registered counsellors",
    status_code=status.HTTP_200_OK
)
async def list_admin_counsellors(
    current_user: Dict[str, Any] = Depends(get_required_user)
):
    """
    GET /api/admin/counsellors
    Admin-only endpoint listing all counsellors.
    """
    if current_user.get("role") != "Admin":
        raise HTTPException(status_code=403, detail="Admin authorization required")

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, username, role, is_active, created_at
            FROM app_users
            WHERE role IN ('Counselor', 'Counsellor') AND is_active = 1
            ORDER BY id ASC;
        """)
        counsellors = [
            {
                "id": r[0],
                "username": r[1],
                "role": r[2],
                "is_active": bool(r[3]),
                "created_at": r[4]
            }
            for r in cur.fetchall()
        ]
        return {"status": "success", "count": len(counsellors), "counsellors": counsellors}
    finally:
        conn.close()


@router.get(
    "/api/admin/assignments",
    summary="Admin list of student-counsellor assignments",
    status_code=status.HTTP_200_OK
)
async def list_admin_assignments(
    student_id: Optional[str] = Query(None),
    counsellor_id: Optional[str] = Query(None),
    assessment_id: Optional[str] = Query(None),
    current_user: Dict[str, Any] = Depends(get_required_user)
):
    """
    GET /api/admin/assignments
    Admin-only list of all assignments.
    """
    if current_user.get("role") != "Admin":
        raise HTTPException(status_code=403, detail="Admin authorization required")

    conn = get_connection()
    try:
        cur = conn.cursor()
        query = """
            SELECT 
                ca.assignment_id,
                ca.assessment_id,
                ca.student_id,
                s.student_name,
                ca.counsellor_id,
                ca.assigned_by,
                ca.assigned_at,
                ca.status,
                ca.is_active
            FROM counsellor_assignments ca
            JOIN students s ON ca.student_id = s.student_id
            WHERE 1=1
        """
        params = []
        if student_id:
            query += " AND ca.student_id = ?"
            params.append(student_id.strip())
        if counsellor_id:
            query += " AND ca.counsellor_id = ?"
            params.append(counsellor_id.strip())
        if assessment_id:
            query += " AND ca.assessment_id = ?"
            params.append(assessment_id.strip())

        query += " ORDER BY ca.id DESC;"
        cur.execute(query, tuple(params))
        items = [
            {
                "assignment_id": r[0],
                "assessment_id": r[1],
                "student_id": r[2],
                "student_name": r[3],
                "counsellor_id": r[4],
                "assigned_by": r[5],
                "assigned_at": r[6],
                "status": r[7],
                "is_active": bool(r[8])
            }
            for r in cur.fetchall()
        ]
        return {"status": "success", "count": len(items), "assignments": items}
    finally:
        conn.close()


@router.post(
    "/api/admin/assignments",
    summary="Admin assigns a counsellor to an assessment and student",
    status_code=status.HTTP_201_CREATED
)
async def create_admin_assignment(
    payload: AdminAssignCounsellorRequest,
    current_user: Dict[str, Any] = Depends(get_required_user)
):
    """
    POST /api/admin/assignments
    Admin-only: Assigns a counsellor to an assessment.
    Deactivates any previous active assignment for that assessment.
    Audit: COUNSELLOR_ASSIGNED.
    """
    role = current_user.get("role")
    admin_user = current_user.get("username", "admin")
    if role != "Admin":
        raise HTTPException(status_code=403, detail="Admin authorization required to create assignments")

    target_stu_id = payload.student_id.strip()
    target_asm_id = payload.assessment_id.strip()
    target_counsellor = payload.counsellor_id.strip()
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_connection()
    try:
        cur = conn.cursor()

        # Validate student
        cur.execute("SELECT student_id FROM students WHERE student_id = ?;", (target_stu_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail=f"Student '{target_stu_id}' was not found")

        # Validate assessment
        cur.execute("SELECT student_id FROM assessments WHERE assessment_id = ?;", (target_asm_id,))
        asm_row = cur.fetchone()
        if not asm_row:
            raise HTTPException(status_code=404, detail=f"Assessment '{target_asm_id}' was not found")
        if asm_row[0] != target_stu_id:
            raise HTTPException(status_code=400, detail="Assessment does not belong to specified student")

        # Validate counsellor
        cur.execute("SELECT username FROM app_users WHERE username = ? AND role IN ('Counselor', 'Counsellor');", (target_counsellor,))
        if not cur.fetchone():
            raise HTTPException(status_code=400, detail=f"User '{target_counsellor}' is not a valid registered counsellor")

        # Deactivate previous active assignments for this assessment
        cur.execute("""
            UPDATE counsellor_assignments
            SET is_active = 0, status = 'COMPLETED'
            WHERE assessment_id = ? AND is_active = 1;
        """, (target_asm_id,))

        assignment_id = f"ASG-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        cur.execute("""
            INSERT INTO counsellor_assignments (
                assignment_id, assessment_id, student_id, counsellor_id,
                assigned_by, assigned_at, status, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE', 1);
        """, (assignment_id, target_asm_id, target_stu_id, target_counsellor, admin_user, now_str))

        _log_audit(
            cur, admin_user, role, "COUNSELLOR_ASSIGNED", target_asm_id,
            entity_type="counsellor_assignment", entity_id=assignment_id,
            safe_metadata={
                "assignment_id": assignment_id,
                "student_id": target_stu_id,
                "counsellor_id": target_counsellor
            }
        )
        conn.commit()

        return {
            "status": "success",
            "message": "Counsellor assigned successfully",
            "assignment_id": assignment_id,
            "assignment_status": "ACTIVE",
            "assignment": {
                "assignment_id": assignment_id,
                "assessment_id": target_asm_id,
                "student_id": target_stu_id,
                "counsellor_id": target_counsellor,
                "assigned_by": admin_user,
                "assigned_at": now_str,
                "status": "ACTIVE",
                "is_active": True
            }
        }
    finally:
        conn.close()


@router.patch(
    "/api/admin/assignments/{assignmentId}/revoke",
    summary="Admin revokes an active counsellor assignment",
    status_code=status.HTTP_200_OK
)
async def revoke_admin_assignment(
    assignmentId: str,
    current_user: Dict[str, Any] = Depends(get_required_user)
):
    """
    PATCH /api/admin/assignments/{assignmentId}/revoke
    Admin-only: Revokes assignment, setting status='REVOKED' and is_active=0.
    The counsellor immediately loses access to the student/assessment.
    Audit: COUNSELLOR_ASSIGNMENT_REVOKED.
    """
    role = current_user.get("role")
    admin_user = current_user.get("username", "admin")
    if role != "Admin":
        raise HTTPException(status_code=403, detail="Admin authorization required to revoke assignments")

    clean_asg_id = assignmentId.strip()

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT assessment_id, student_id, counsellor_id, is_active
            FROM counsellor_assignments WHERE assignment_id = ?;
        """, (clean_asg_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Assignment '{clean_asg_id}' was not found")

        asm_id, stu_id, c_id, was_active = row

        cur.execute("""
            UPDATE counsellor_assignments
            SET status = 'REVOKED', is_active = 0
            WHERE assignment_id = ?;
        """, (clean_asg_id,))

        _log_audit(
            cur, admin_user, role, "COUNSELLOR_ASSIGNMENT_REVOKED", asm_id,
            entity_type="counsellor_assignment", entity_id=clean_asg_id,
            safe_metadata={
                "assignment_id": clean_asg_id,
                "student_id": stu_id,
                "counsellor_id": c_id
            }
        )
        conn.commit()

        return {
            "status": "success",
            "message": "Assignment revoked successfully",
            "assignment_id": clean_asg_id,
            "assignment_status": "REVOKED",
            "is_active": False
        }
    finally:
        conn.close()


@router.delete(
    "/api/admin/assignments/{assignmentId}",
    summary="Admin deletes or revokes an assignment",
    status_code=status.HTTP_200_OK
)
async def delete_admin_assignment(
    assignmentId: str,
    current_user: Dict[str, Any] = Depends(get_required_user)
):
    """Delegates to revoke to preserve historical records."""
    return await revoke_admin_assignment(assignmentId, current_user)
