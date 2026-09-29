"""
Official IRIS Admin Portal & Administrative Workflow APIs (Phase 8).
Conforms strictly to IRIS_Backend_Detailed_Requirements.docx & IRIS_Frontend_Detailed_Requirements.docx.

Provides full administrative oversight across:
1. Dashboard Summary: API-driven metrics, recent students/assessments, and quick actions
2. Students Management: Search, filter, listing, and detail inspection
3. Assessments Management: Institutional case oversight, status filtering, and deep case details
4. Eye Scans Overview: Inspection of bilateral scan quality scores, attempt numbers, and safe statuses
5. Reports Management: Directory of all generated reports, review states, 10-section report views, and server-side PDF access
6. Counsellors & Assignments: Listing counsellors, assigning counsellors to assessments, and revoking assignments
7. Users & Roles Management: Institutional user administration, role assignment, active/disabled toggling, and role capability discovery
8. Institutional Audit Trail: Querying security and action audit logs without exposing sensitive credentials or PII
"""

import os
import uuid
import json
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, Depends, Query, Path, status
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from database_official import get_connection, BASE_DIR
from security.auth import (
    require_admin,
    hash_password,
    verify_password
)
from api.students import get_required_user, verify_student_read_access
from api.counsellor import (
    AdminAssignCounsellorRequest,
    create_admin_assignment as _create_counsellor_assignment,
    revoke_admin_assignment as _revoke_counsellor_assignment
)
from api.official_report import download_report_pdf, get_report_by_id

router = APIRouter(tags=["Official Admin Portal"])


# =====================================================================
# SCHEMAS
# =====================================================================

class CreateUserPayload(BaseModel):
    username: str = Field(..., min_length=3, max_length=64, description="Unique username")
    password: str = Field(..., min_length=6, max_length=128, description="Initial password")
    role: str = Field(..., description="Role: Admin, Student, or Counselor")
    full_name: Optional[str] = Field(None, max_length=128)
    email: Optional[str] = Field(None, max_length=128)


class UpdateUserPayload(BaseModel):
    role: Optional[str] = Field(None, description="Updated role")
    full_name: Optional[str] = Field(None, max_length=128)
    email: Optional[str] = Field(None, max_length=128)
    is_active: Optional[bool] = Field(None, description="Active status toggle")


class AssignCounsellorSimplePayload(BaseModel):
    counsellor_id: str = Field(..., min_length=2, description="Target counsellor username")


# =====================================================================
# AUDIT HELPER
# =====================================================================

def _log_admin_audit(
    cursor: sqlite3.Cursor,
    user_id: str,
    role: str,
    action: str,
    assessment_id: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    status_str: str = "SUCCESS",
    safe_metadata: Optional[Dict[str, Any]] = None
):
    audit_id = f"AUD-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
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


# =====================================================================
# 1. ADMIN DASHBOARD SUMMARY
# =====================================================================

@router.get(
    "/api/admin/dashboard/summary",
    summary="Admin Dashboard Summary Metrics & Recent Activity",
    status_code=status.HTTP_200_OK
)
async def get_admin_dashboard_summary(
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """
    GET /api/admin/dashboard/summary
    Returns 100% API-driven statistics across students, assessments, scans,
    reports, and counsellors, along with recent activity feeds and supported quick actions.
    """
    user_id = current_user.get("username", "admin")
    role = current_user.get("role", "Admin")

    conn = get_connection()
    try:
        cur = conn.cursor()

        # 1. Overall counts
        cur.execute("SELECT COUNT(*) FROM students;")
        total_students = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM assessments;")
        total_assessments = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*) FROM assessments
            WHERE status IN ('REGISTERED', 'SCAN_PENDING');
        """)
        pending_scans = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*) FROM assessments
            WHERE status IN ('PROCESSING', 'ANALYSIS_COMPLETED', 'REPORT_GENERATING');
        """)
        processing = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM assessments WHERE status = 'REPORT_READY';")
        reports_ready = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM assessments WHERE status = 'FAILED';")
        failed = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*) FROM app_users
            WHERE role IN ('Counselor', 'Counsellor') AND is_active = 1;
        """)
        counsellors_count = cur.fetchone()[0]

        # 2. Recent Students (latest 5)
        cur.execute("""
            SELECT s.student_id, s.student_name, s.created_at,
                   (SELECT a.status FROM assessments a WHERE a.student_id = s.student_id ORDER BY a.id DESC LIMIT 1) as latest_status,
                   (SELECT a.assessment_id FROM assessments a WHERE a.student_id = s.student_id ORDER BY a.id DESC LIMIT 1) as latest_assessment_id
            FROM students s
            ORDER BY s.id DESC
            LIMIT 5;
        """)
        recent_students = [
            {
                "student_id": r[0],
                "student_name": r[1],
                "created_at": r[2],
                "latest_status": r[3] or "REGISTERED",
                "latest_assessment_id": r[4]
            }
            for r in cur.fetchall()
        ]

        # 3. Recent Assessments (latest 5)
        cur.execute("""
            SELECT a.assessment_id, a.student_id, COALESCE(s.student_name, 'Unknown'),
                   a.status, a.created_at,
                   (SELECT r.status FROM reports r WHERE r.assessment_id = a.assessment_id ORDER BY r.id DESC LIMIT 1) as report_status
            FROM assessments a
            LEFT JOIN students s ON a.student_id = s.student_id
            ORDER BY a.id DESC
            LIMIT 5;
        """)
        recent_assessments = [
            {
                "assessment_id": r[0],
                "student_id": r[1],
                "student_name": r[2],
                "workflow_status": r[3],
                "created_at": r[4],
                "report_status": r[5] or "NOT_GENERATED"
            }
            for r in cur.fetchall()
        ]

        quick_actions = [
            {"id": "register_student", "label": "Register Student", "url": "/static/register.html", "icon": "fa-user-plus"},
            {"id": "view_students", "label": "Student Directory", "url": "/static/dashboard.html#students", "icon": "fa-graduation-cap"},
            {"id": "view_assessments", "label": "All Assessments", "url": "/static/dashboard.html#assessments", "icon": "fa-list-check"},
            {"id": "view_reports", "label": "Report Directory", "url": "/static/dashboard.html#reports", "icon": "fa-file-invoice"},
            {"id": "counsellor_management", "label": "Counsellor Management", "url": "/static/dashboard.html#counsellors", "icon": "fa-user-tie"}
        ]

        _log_admin_audit(
            cur, user_id, role, "ADMIN_DASHBOARD_VIEWED",
            entity_type="dashboard", entity_id="summary",
            safe_metadata={"total_students": total_students, "total_assessments": total_assessments}
        )
        conn.commit()

        return {
            "status": "success",
            "counts": {
                "total_students": total_students,
                "total_assessments": total_assessments,
                "pending_scans": pending_scans,
                "processing": processing,
                "reports_ready": reports_ready,
                "failed": failed,
                "counsellors": counsellors_count
            },
            "recent_students": recent_students,
            "recent_assessments": recent_assessments,
            "quick_actions": quick_actions
        }
    finally:
        conn.close()


# =====================================================================
# 2. STUDENTS MANAGEMENT
# =====================================================================

@router.get(
    "/api/admin/students",
    summary="Admin Student Directory with enriched assessment & scan statuses",
    status_code=status.HTTP_200_OK
)
async def list_admin_students(
    search: Optional[str] = Query(None, description="Search by Student ID or Name"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by workflow status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """
    GET /api/admin/students
    Lists students with active assessment status, bilateral scan status,
    report status, and assigned counsellor according to Section 7 of Frontend Requirements.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()

        base_query = """
            FROM students s
            LEFT JOIN assessments a ON a.student_id = s.student_id AND a.id = (
                SELECT MAX(id) FROM assessments WHERE student_id = s.student_id
            )
            WHERE 1=1
        """
        params = []
        if search:
            st = f"%{search.strip()}%"
            base_query += " AND (s.student_id LIKE ? OR s.student_name LIKE ?)"
            params.extend([st, st])
        if status_filter:
            base_query += " AND a.status = ?"
            params.append(status_filter.strip())

        cur.execute(f"SELECT COUNT(*) {base_query}", tuple(params))
        total_count = cur.fetchone()[0]

        select_query = f"""
            SELECT 
                s.student_id, 
                s.student_name, 
                s.created_at,
                COALESCE(a.status, 'REGISTERED') as assessment_status,
                a.assessment_id,
                (SELECT status FROM eye_scans WHERE assessment_id = a.assessment_id AND eye_side = 'LEFT' AND is_active = 1) as left_eye,
                (SELECT status FROM eye_scans WHERE assessment_id = a.assessment_id AND eye_side = 'RIGHT' AND is_active = 1) as right_eye,
                (SELECT status FROM reports WHERE assessment_id = a.assessment_id ORDER BY id DESC LIMIT 1) as report_status,
                (SELECT counsellor_id FROM counsellor_assignments WHERE assessment_id = a.assessment_id AND is_active = 1 LIMIT 1) as counsellor
            {base_query}
            ORDER BY s.id DESC
            LIMIT ? OFFSET ?;
        """
        cur.execute(select_query, tuple(params + [limit, offset]))
        rows = cur.fetchall()

        students = []
        for r in rows:
            left_st = str(r[5]).upper() if r[5] else "PENDING"
            right_st = str(r[6]).upper() if r[6] else "PENDING"
            rep_st = r[7] if r[7] else "NOT_READY"

            students.append({
                "student_id": r[0],
                "student_name": r[1],
                "date": r[2],
                "assessment_status": r[3],
                "assessment_id": r[4],
                "left_eye": "Completed" if left_st in ("COMPLETED", "COMPLETE") else "Pending",
                "right_eye": "Completed" if right_st in ("COMPLETED", "COMPLETE") else "Pending",
                "report": "Ready" if rep_st == "REPORT_READY" else "Not Ready",
                "counsellor": r[8] or "Unassigned"
            })

        return {
            "status": "success",
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "students": students
        }
    finally:
        conn.close()


@router.get(
    "/api/admin/students/{student_id}",
    summary="Admin Student Deep Detail Inspection",
    status_code=status.HTTP_200_OK
)
async def get_admin_student_detail(
    student_id: str,
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """
    GET /api/admin/students/{student_id}
    Retrieves full profile demographics and complete assessment history.
    """
    clean_id = student_id.strip()
    conn = get_connection()
    try:
        cur = conn.cursor()

        cur.execute("SELECT student_id, student_name, created_by, created_at, status FROM students WHERE student_id = ?;", (clean_id,))
        s_row = cur.fetchone()
        if not s_row:
            cur.execute("SELECT student_id, full_name, created_by, created_on FROM student_profiles WHERE student_id = ?;", (clean_id,))
            s_row = cur.fetchone()
            if not s_row:
                raise HTTPException(status_code=404, detail=f"Student '{clean_id}' was not found")
            student_meta = {"student_id": s_row[0], "student_name": s_row[1], "created_by": s_row[2], "created_at": s_row[3], "status": "ACTIVE"}
        else:
            student_meta = {"student_id": s_row[0], "student_name": s_row[1], "created_by": s_row[2], "created_at": s_row[3], "status": s_row[4]}

        cur.execute("""
            SELECT age, gender, school_college, stream, course, location, created_on
            FROM student_profiles WHERE student_id = ?;
        """, (clean_id,))
        p_row = cur.fetchone()
        demographics = {
            "age": p_row[0], "gender": p_row[1], "school_college": p_row[2],
            "stream": p_row[3], "course": p_row[4], "location": p_row[5], "created_on": p_row[6]
        } if p_row else None

        cur.execute("""
            SELECT assessment_id, status, created_at, completed_at
            FROM assessments WHERE student_id = ? ORDER BY id DESC;
        """, (clean_id,))
        assessments = [
            {
                "assessment_id": r[0],
                "workflow_status": r[1],
                "created_at": r[2],
                "completed_at": r[3]
            }
            for r in cur.fetchall()
        ]

        return {
            "status": "success",
            "student": student_meta,
            "demographics": demographics,
            "assessments_count": len(assessments),
            "assessments": assessments
        }
    finally:
        conn.close()


# =====================================================================
# 3. ASSESSMENTS MANAGEMENT
# =====================================================================

@router.get(
    "/api/admin/assessments",
    summary="Admin Directory of All Institutional Assessments",
    status_code=status.HTTP_200_OK
)
async def list_admin_assessments(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by workflow status"),
    search: Optional[str] = Query(None, description="Search by Assessment ID, Student ID, or Name"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """
    GET /api/admin/assessments
    Institutional list of all assessments with bilateral scan states and counsellor assignments.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()

        base_query = """
            FROM assessments a
            LEFT JOIN students s ON a.student_id = s.student_id
            WHERE 1=1
        """
        params = []
        if status_filter:
            base_query += " AND a.status = ?"
            params.append(status_filter.strip())
        if search:
            st = f"%{search.strip()}%"
            base_query += " AND (a.assessment_id LIKE ? OR a.student_id LIKE ? OR s.student_name LIKE ?)"
            params.extend([st, st, st])

        cur.execute(f"SELECT COUNT(*) {base_query}", tuple(params))
        total_count = cur.fetchone()[0]

        select_query = f"""
            SELECT 
                a.assessment_id,
                a.student_id,
                COALESCE(s.student_name, 'Unknown') as student_name,
                a.status as workflow_status,
                a.created_at,
                a.completed_at,
                (SELECT status FROM eye_scans WHERE assessment_id = a.assessment_id AND eye_side = 'LEFT' AND is_active = 1) as left_scan,
                (SELECT status FROM eye_scans WHERE assessment_id = a.assessment_id AND eye_side = 'RIGHT' AND is_active = 1) as right_scan,
                (SELECT status FROM reports WHERE assessment_id = a.assessment_id ORDER BY id DESC LIMIT 1) as report_status,
                (SELECT report_id FROM reports WHERE assessment_id = a.assessment_id ORDER BY id DESC LIMIT 1) as report_id,
                (SELECT counsellor_id FROM counsellor_assignments WHERE assessment_id = a.assessment_id AND is_active = 1 LIMIT 1) as counsellor_id
            {base_query}
            ORDER BY a.id DESC
            LIMIT ? OFFSET ?;
        """
        cur.execute(select_query, tuple(params + [limit, offset]))
        rows = cur.fetchall()

        assessments = [
            {
                "assessment_id": r[0],
                "student_id": r[1],
                "student_name": r[2],
                "workflow_status": r[3],
                "created_at": r[4],
                "completed_at": r[5],
                "left_scan_status": r[6] or "PENDING",
                "right_scan_status": r[7] or "PENDING",
                "report_status": r[8] or "NOT_GENERATED",
                "report_id": r[9],
                "counsellor_id": r[10] or "Unassigned"
            }
            for r in rows
        ]

        return {
            "status": "success",
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "assessments": assessments
        }
    finally:
        conn.close()


@router.get(
    "/api/admin/assessments/{assessment_id}",
    summary="Admin Deep Assessment Case Inspection",
    status_code=status.HTTP_200_OK
)
async def get_admin_assessment_detail(
    assessment_id: str,
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """
    GET /api/admin/assessments/{assessment_id}
    Deep case inspection: scans, analysis metadata, report info, counsellor assignment, notes & follow-ups.
    """
    clean_id = assessment_id.strip()
    conn = get_connection()
    try:
        cur = conn.cursor()

        cur.execute("""
            SELECT a.assessment_id, a.student_id, COALESCE(s.student_name, 'Unknown'),
                   a.status, a.created_by, a.created_at, a.completed_at
            FROM assessments a
            LEFT JOIN students s ON a.student_id = s.student_id
            WHERE a.assessment_id = ?;
        """, (clean_id,))
        asm_row = cur.fetchone()
        if not asm_row:
            raise HTTPException(status_code=404, detail=f"Assessment '{clean_id}' was not found")

        asm_info = {
            "assessment_id": asm_row[0],
            "student_id": asm_row[1],
            "student_name": asm_row[2],
            "workflow_status": asm_row[3],
            "created_by": asm_row[4],
            "created_at": asm_row[5],
            "completed_at": asm_row[6]
        }

        # Bilateral Scans
        cur.execute("""
            SELECT scan_id, eye_side, status, result_reference, attempt_number, created_at, completed_at
            FROM eye_scans WHERE assessment_id = ? AND is_active = 1;
        """, (clean_id,))
        scans = {}
        for r in cur.fetchall():
            q_score = 0.0
            if r[3]:
                try:
                    q_score = json.loads(r[3]).get("quality_score", 0.0)
                except Exception:
                    pass
            scans[r[1]] = {
                "scan_id": r[0], "status": r[2], "quality_score": q_score,
                "attempt_number": r[4], "created_at": r[5], "completed_at": r[6]
            }

        # Analysis Meta
        cur.execute("""
            SELECT model_version, results_json, created_at
            FROM analysis_results WHERE assessment_id = ?;
        """, (clean_id,))
        an_row = cur.fetchone()
        analysis = None
        if an_row:
            results_dict = {}
            if an_row[1]:
                try:
                    results_dict = json.loads(an_row[1])
                except Exception:
                    pass
            analysis = {"model_version": an_row[0], "results": results_dict, "created_at": an_row[2]}

        # Report Meta
        cur.execute("""
            SELECT report_id, version, status, generated_at, pdf_reference, reviewed_status, reviewed_by, reviewed_at
            FROM reports WHERE assessment_id = ? ORDER BY id DESC LIMIT 1;
        """, (clean_id,))
        rep_row = cur.fetchone()
        report = {
            "report_id": rep_row[0], "version": rep_row[1], "status": rep_row[2],
            "generated_at": rep_row[3], "has_pdf": bool(rep_row[4]),
            "reviewed_status": bool(rep_row[5]), "reviewed_by": rep_row[6], "reviewed_at": rep_row[7]
        } if rep_row else None

        # Active Counsellor Assignment
        cur.execute("""
            SELECT assignment_id, counsellor_id, assigned_by, assigned_at, status
            FROM counsellor_assignments WHERE assessment_id = ? AND is_active = 1;
        """, (clean_id,))
        asg_row = cur.fetchone()
        assignment = {
            "assignment_id": asg_row[0], "counsellor_id": asg_row[1],
            "assigned_by": asg_row[2], "assigned_at": asg_row[3], "status": asg_row[4]
        } if asg_row else None

        # Counselling Notes
        cur.execute("""
            SELECT note_id, counsellor_id, note, created_at
            FROM counselling_notes WHERE assessment_id = ? ORDER BY id ASC;
        """, (clean_id,))
        notes = [{"note_id": r[0], "counsellor_id": r[1], "note": r[2], "created_at": r[3]} for r in cur.fetchall()]

        # Follow-ups
        cur.execute("""
            SELECT follow_up_id, counsellor_id, follow_up_date, status, notes, created_at
            FROM follow_ups WHERE assessment_id = ? ORDER BY id ASC;
        """, (clean_id,))
        follow_ups = [{"follow_up_id": r[0], "counsellor_id": r[1], "follow_up_date": r[2], "status": r[3], "notes": r[4], "created_at": r[5]} for r in cur.fetchall()]

        return {
            "status": "success",
            "assessment": asm_info,
            "scans": scans,
            "analysis": analysis,
            "report": report,
            "assignment": assignment,
            "counselling_notes": notes,
            "follow_ups": follow_ups
        }
    finally:
        conn.close()


# =====================================================================
# 4. EYE SCANS OVERVIEW
# =====================================================================

@router.get(
    "/api/admin/scans",
    summary="Admin Eye Scans Overview with quality metrics",
    status_code=status.HTTP_200_OK
)
async def list_admin_scans(
    eye: Optional[str] = Query(None, description="Filter by eye side (LEFT or RIGHT)"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by scan status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """
    GET /api/admin/scans
    Inspection of active eye scans across assessments.
    Safe path handling: Never exposes internal filesystem directories.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()

        base_query = """
            FROM eye_scans e
            JOIN assessments a ON e.assessment_id = a.assessment_id
            LEFT JOIN students s ON a.student_id = s.student_id
            WHERE e.is_active = 1
        """
        params = []
        if eye:
            base_query += " AND e.eye_side = ?"
            params.append(eye.strip().upper())
        if status_filter:
            base_query += " AND e.status = ?"
            params.append(status_filter.strip())

        cur.execute(f"SELECT COUNT(*) {base_query}", tuple(params))
        total_count = cur.fetchone()[0]

        select_query = f"""
            SELECT 
                e.scan_id,
                e.assessment_id,
                a.student_id,
                COALESCE(s.student_name, 'Unknown') as student_name,
                e.eye_side,
                e.status,
                e.result_reference,
                e.attempt_number,
                e.created_at,
                e.completed_at
            {base_query}
            ORDER BY e.id DESC
            LIMIT ? OFFSET ?;
        """
        cur.execute(select_query, tuple(params + [limit, offset]))
        rows = cur.fetchall()

        scans = []
        for r in rows:
            q_score = 0.0
            if r[6]:
                try:
                    q_score = json.loads(r[6]).get("quality_score", 0.0)
                except Exception:
                    pass
            scans.append({
                "scan_id": r[0],
                "assessment_id": r[1],
                "student_id": r[2],
                "student_name": r[3],
                "eye_side": r[4],
                "status": r[5],
                "quality_score": q_score,
                "attempt_number": r[7],
                "created_at": r[8],
                "completed_at": r[9]
            })

        return {
            "status": "success",
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "scans": scans
        }
    finally:
        conn.close()


# =====================================================================
# 5. REPORTS MANAGEMENT
# =====================================================================

@router.get(
    "/api/admin/reports",
    summary="Admin Directory of Generated Assessment Reports",
    status_code=status.HTTP_200_OK
)
async def list_admin_reports(
    search: Optional[str] = Query(None, description="Search by student ID, assessment ID, or report ID"),
    reviewed_only: Optional[bool] = Query(None, description="Filter by reviewed status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """
    GET /api/admin/reports
    Institutional directory of all generated reports with review sign-off flags.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()

        base_query = """
            FROM reports r
            JOIN assessments a ON r.assessment_id = a.assessment_id
            LEFT JOIN students s ON a.student_id = s.student_id
            WHERE 1=1
        """
        params = []
        if search:
            st = f"%{search.strip()}%"
            base_query += " AND (r.report_id LIKE ? OR r.assessment_id LIKE ? OR a.student_id LIKE ? OR s.student_name LIKE ?)"
            params.extend([st, st, st, st])
        if reviewed_only is not None:
            base_query += " AND r.reviewed_status = ?"
            params.append(1 if reviewed_only else 0)

        cur.execute(f"SELECT COUNT(*) {base_query}", tuple(params))
        total_count = cur.fetchone()[0]

        select_query = f"""
            SELECT 
                r.report_id,
                r.assessment_id,
                a.student_id,
                COALESCE(s.student_name, 'Unknown') as student_name,
                r.version,
                r.status as report_status,
                r.reviewed_status,
                r.reviewed_by,
                r.reviewed_at,
                r.generated_at,
                r.pdf_reference
            {base_query}
            ORDER BY r.id DESC
            LIMIT ? OFFSET ?;
        """
        cur.execute(select_query, tuple(params + [limit, offset]))
        rows = cur.fetchall()

        reports = [
            {
                "report_id": r[0],
                "assessment_id": r[1],
                "student_id": r[2],
                "student_name": r[3],
                "version": r[4],
                "report_status": r[5],
                "reviewed_status": bool(r[6]),
                "reviewed_by": r[7],
                "reviewed_at": r[8],
                "generated_at": r[9],
                "has_pdf": bool(r[10])
            }
            for r in rows
        ]

        return {
            "status": "success",
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "reports": reports
        }
    finally:
        conn.close()


@router.get(
    "/api/admin/reports/{report_id}",
    summary="Admin Official Report Inspection",
    status_code=status.HTTP_200_OK
)
async def get_admin_report_detail(
    report_id: str,
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """
    GET /api/admin/reports/{report_id}
    Retrieves the authoritative 10-section report contract for admin review.
    """
    return await get_report_by_id(report_id, current_user)


@router.get(
    "/api/admin/assessments/{assessment_id}/report/pdf",
    summary="Admin Server-Side Report PDF Download",
    status_code=status.HTTP_200_OK
)
async def download_admin_report_pdf(
    assessment_id: str,
    version: Optional[str] = Query(None),
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """
    GET /api/admin/assessments/{assessment_id}/report/pdf
    Authoritative server-side streaming of generated PDF report.
    """
    return await download_report_pdf(assessment_id, version, current_user)


# =====================================================================
# 6. COUNSELLORS & ASSIGNMENT MANAGEMENT
# =====================================================================

@router.get(
    "/api/counsellors",
    summary="Global Counsellors Listing",
    status_code=status.HTTP_200_OK
)
async def list_counsellors_public(
    current_user: Dict[str, Any] = Depends(get_required_user)
):
    """
    GET /api/counsellors
    Public/Authenticated list of registered academic counsellors.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, username, role, full_name, email, is_active, created_at
            FROM app_users
            WHERE role IN ('Counselor', 'Counsellor') AND is_active = 1
            ORDER BY id ASC;
        """)
        counsellors = [
            {
                "id": r[0],
                "username": r[1],
                "role": r[2],
                "full_name": r[3] or r[1],
                "email": r[4] or "",
                "is_active": bool(r[5]),
                "created_at": r[6]
            }
            for r in cur.fetchall()
        ]
        return {"status": "success", "count": len(counsellors), "counsellors": counsellors}
    finally:
        conn.close()


@router.post(
    "/api/assessments/{assessment_id}/assign-counsellor",
    summary="Assign Counsellor to Assessment by Assessment ID",
    status_code=status.HTTP_201_CREATED
)
async def assign_counsellor_to_assessment(
    assessment_id: str,
    payload: AssignCounsellorSimplePayload,
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """
    POST /api/assessments/{assessment_id}/assign-counsellor
    Admin-only assignment endpoint resolving student_id directly from assessment.
    """
    clean_asm_id = assessment_id.strip()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT student_id FROM assessments WHERE assessment_id = ?;", (clean_asm_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Assessment '{clean_asm_id}' was not found")
        student_id = row[0]
    finally:
        conn.close()

    req = AdminAssignCounsellorRequest(
        assessment_id=clean_asm_id,
        student_id=student_id,
        counsellor_id=payload.counsellor_id.strip()
    )
    return await _create_counsellor_assignment(req, current_user)


# =====================================================================
# 7. USERS & ROLES ADMINISTRATION
# =====================================================================

@router.get(
    "/api/admin/users",
    summary="Admin System Users Directory",
    status_code=status.HTTP_200_OK
)
@router.get(
    "/api/users",
    summary="Alias for System Users Directory",
    status_code=status.HTTP_200_OK
)
async def list_admin_users(
    role_filter: Optional[str] = Query(None, alias="role"),
    is_active: Optional[bool] = Query(None),
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """
    GET /api/admin/users (and /api/users)
    Institutional list of all system users.
    Zero-exposure: NEVER leaks password_hash.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        query = "SELECT id, username, role, full_name, email, is_active, created_at FROM app_users WHERE 1=1"
        params = []
        if role_filter:
            query += " AND role = ?"
            params.append(role_filter.strip())
        if is_active is not None:
            query += " AND is_active = ?"
            params.append(1 if is_active else 0)

        query += " ORDER BY id ASC;"
        cur.execute(query, tuple(params))
        rows = cur.fetchall()

        users = [
            {
                "id": r[0],
                "username": r[1],
                "role": r[2],
                "full_name": r[3] or "",
                "email": r[4] or "",
                "is_active": bool(r[5]),
                "created_at": r[6]
            }
            for r in rows
        ]
        return {"status": "success", "count": len(users), "users": users}
    finally:
        conn.close()


@router.post(
    "/api/admin/users",
    summary="Admin Provisions New System User",
    status_code=status.HTTP_201_CREATED
)
@router.post(
    "/api/users",
    summary="Alias for Provisioning System User",
    status_code=status.HTTP_201_CREATED
)
async def create_admin_user(
    payload: CreateUserPayload,
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """
    POST /api/admin/users (and /api/users)
    Creates a new user in app_users with securely hashed password.
    Audit: USER_CREATED.
    """
    clean_username = payload.username.strip()
    valid_roles = {"Admin": "Admin", "Student": "Student", "Counselor": "Counselor", "Counsellor": "Counselor"}
    if payload.role not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role '{payload.role}'. Must be one of: Admin, Student, Counselor"
        )
    canonical_role = valid_roles[payload.role]

    admin_username = current_user.get("username", "admin")
    admin_role = current_user.get("role", "Admin")

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM app_users WHERE username = ?;", (clean_username,))
        if cur.fetchone():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Username '{clean_username}' is already registered"
            )

        hashed = hash_password(payload.password)
        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        cur.execute("""
            INSERT INTO app_users (username, password_hash, role, full_name, email, created_at, is_active)
            VALUES (?, ?, ?, ?, ?, ?, 1);
        """, (clean_username, hashed, canonical_role, payload.full_name or "", payload.email or "", now_str))
        user_id = cur.lastrowid

        _log_admin_audit(
            cur, admin_username, admin_role, "USER_CREATED",
            entity_type="user", entity_id=clean_username,
            safe_metadata={"user_id": user_id, "username": clean_username, "role": canonical_role}
        )
        conn.commit()

        return {
            "status": "success",
            "message": "User created successfully",
            "user": {
                "id": user_id,
                "username": clean_username,
                "role": canonical_role,
                "full_name": payload.full_name or "",
                "email": payload.email or "",
                "is_active": True,
                "created_at": now_str
            }
        }
    finally:
        conn.close()


@router.patch(
    "/api/admin/users/{user_id}",
    summary="Admin Updates User Role or Active Status",
    status_code=status.HTTP_200_OK
)
@router.patch(
    "/api/users/{user_id}",
    summary="Alias for Updating User Role or Active Status",
    status_code=status.HTTP_200_OK
)
async def update_admin_user(
    user_id: str,
    payload: UpdateUserPayload,
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """
    PATCH /api/admin/users/{user_id} (and /api/users/{user_id})
    Updates user details or active status.
    Safety Guard: Admin cannot deactivate their own active account.
    """
    admin_username = current_user.get("username", "admin")
    admin_role = current_user.get("role", "Admin")

    conn = get_connection()
    try:
        cur = conn.cursor()

        # Lookup by id if int, or username if string
        if user_id.isdigit():
            cur.execute("SELECT id, username, role, is_active FROM app_users WHERE id = ?;", (int(user_id),))
        else:
            cur.execute("SELECT id, username, role, is_active FROM app_users WHERE username = ?;", (user_id.strip(),))
        target_row = cur.fetchone()
        if not target_row:
            raise HTTPException(status_code=404, detail=f"User '{user_id}' was not found")

        t_id, t_username, t_role, t_active = target_row

        # Safety Check: Prevent admin suicide
        if payload.is_active is False and t_username.lower() == admin_username.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Safety check: You cannot deactivate your own active admin account"
            )

        updates = []
        params = []
        if payload.role:
            valid_roles = {"Admin": "Admin", "Student": "Student", "Counselor": "Counselor", "Counsellor": "Counselor"}
            if payload.role not in valid_roles:
                raise HTTPException(status_code=400, detail=f"Invalid role '{payload.role}'")
            updates.append("role = ?")
            params.append(valid_roles[payload.role])
        if payload.full_name is not None:
            updates.append("full_name = ?")
            params.append(payload.full_name.strip())
        if payload.email is not None:
            updates.append("email = ?")
            params.append(payload.email.strip())
        if payload.is_active is not None:
            updates.append("is_active = ?")
            params.append(1 if payload.is_active else 0)

        if updates:
            params.append(t_id)
            cur.execute(f"UPDATE app_users SET {', '.join(updates)} WHERE id = ?;", tuple(params))

            _log_admin_audit(
                cur, admin_username, admin_role, "USER_UPDATED",
                entity_type="user", entity_id=t_username,
                safe_metadata={
                    "user_id": t_id,
                    "username": t_username,
                    "updated_role": payload.role,
                    "is_active": payload.is_active
                }
            )
            conn.commit()

        # Fetch updated record
        cur.execute("SELECT id, username, role, full_name, email, is_active, created_at FROM app_users WHERE id = ?;", (t_id,))
        updated = cur.fetchone()

        return {
            "status": "success",
            "message": "User updated successfully",
            "user": {
                "id": updated[0],
                "username": updated[1],
                "role": updated[2],
                "full_name": updated[3],
                "email": updated[4],
                "is_active": bool(updated[5]),
                "created_at": updated[6]
            }
        }
    finally:
        conn.close()


@router.get(
    "/api/admin/roles",
    summary="Admin Canonical Roles & Capability Directory",
    status_code=status.HTTP_200_OK
)
@router.get(
    "/api/roles",
    summary="Alias for Canonical Roles & Capability Directory",
    status_code=status.HTTP_200_OK
)
async def list_admin_roles(
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """
    GET /api/admin/roles (and /api/roles)
    Returns canonical system roles and operational privilege matrices.
    """
    roles = [
        {
            "role": "Admin",
            "name": "System Administrator",
            "description": "Full institutional control over system settings, users, assessments, students, and audit logs.",
            "capabilities": [
                "manage_students",
                "manage_assessments",
                "view_scans",
                "view_reports",
                "manage_counsellors",
                "assign_counsellors",
                "manage_users",
                "view_audit_logs"
            ]
        },
        {
            "role": "Counselor",
            "name": "Academic & Career Counselor",
            "description": "Clinical and educational guidance for assigned students; report review and follow-up consultation scheduling.",
            "capabilities": [
                "view_assigned_students",
                "review_reports",
                "add_counselling_notes",
                "manage_follow_ups"
            ]
        },
        {
            "role": "Student",
            "name": "Student Candidate",
            "description": "Student user taking eye scan assessments and viewing personal structured cognitive reports.",
            "capabilities": [
                "view_own_profile",
                "view_own_assessments",
                "perform_eye_scans",
                "trigger_analysis",
                "view_own_report",
                "download_own_pdf"
            ]
        }
    ]
    return {"status": "success", "count": len(roles), "roles": roles}


# =====================================================================
# 8. INSTITUTIONAL AUDIT LOGS
# =====================================================================

@router.get(
    "/api/admin/audit-logs",
    summary="Query Institutional Security and Action Audit Logs",
    status_code=status.HTTP_200_OK
)
async def list_admin_audit_logs(
    action: Optional[str] = Query(None, description="Filter by action keyword"),
    user_id: Optional[str] = Query(None, description="Filter by executing user"),
    assessment_id: Optional[str] = Query(None, description="Filter by assessment ID"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """
    GET /api/admin/audit-logs
    Security audit trail query endpoint.
    Zero-exposure: Never leaks passwords, JWT tokens, hashes, or biometric raw files.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()

        base_query = "FROM audit_logs WHERE 1=1"
        params = []
        if action:
            base_query += " AND action LIKE ?"
            params.append(f"%{action.strip()}%")
        if user_id:
            base_query += " AND user_id = ?"
            params.append(user_id.strip())
        if assessment_id:
            base_query += " AND assessment_id = ?"
            params.append(assessment_id.strip())

        cur.execute(f"SELECT COUNT(*) {base_query}", tuple(params))
        total_count = cur.fetchone()[0]

        select_query = f"""
            SELECT id, audit_id, user_id, role, action, assessment_id,
                   entity_type, entity_id, status, safe_metadata_json, timestamp
            {base_query}
            ORDER BY id DESC
            LIMIT ? OFFSET ?;
        """
        cur.execute(select_query, tuple(params + [limit, offset]))
        rows = cur.fetchall()

        logs = []
        for r in rows:
            meta = {}
            if r[9]:
                try:
                    meta = json.loads(r[9])
                except Exception:
                    pass
            logs.append({
                "id": r[0],
                "audit_id": r[1],
                "user_id": r[2],
                "role": r[3],
                "action": r[4],
                "assessment_id": r[5],
                "entity_type": r[6],
                "entity_id": r[7],
                "status": r[8],
                "metadata": meta,
                "timestamp": r[10]
            })

        return {
            "status": "success",
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "audit_logs": logs
        }
    finally:
        conn.close()
