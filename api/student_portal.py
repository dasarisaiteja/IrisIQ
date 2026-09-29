"""
Official IRIS Student Portal APIs (Phase 7).
Implements:
- GET /api/student/profile (and /api/student/me): Authenticated student profile
- GET /api/student/assessments: List student's own assessments
- GET /api/student/assessments/{assessmentId} (and /api/student/assessment): Detailed assessment view
- GET /api/student/assessments/{assessmentId}/status (and /api/student/assessment/status): Fast status polling
- GET /api/student/assessments/{assessmentId}/report (and /api/student/report): Official 10-section report
- GET /api/student/assessments/{assessmentId}/report/pdf (and /api/student/report/pdf): Secure server-side PDF download

Strictly conforms to:
- IRIS_Backend_Detailed_Requirements.docx
- IRIS_Frontend_Detailed_Requirements.docx
- Anti-IDOR enforcement: Students can ONLY access their own records.
- Cross-student access is strictly rejected with HTTP 403 Forbidden.
- Audit logging for profile, assessment, report, and PDF retrieval.
"""

import os
import json
import uuid
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, Depends, Query, status
from fastapi.responses import FileResponse

from database_official import get_connection
from api.students import get_required_user, verify_student_read_access
from api.official_report import get_assessment_report, download_report_pdf

router = APIRouter(prefix="/api/student", tags=["Official Student Portal"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
REPORTS_DIR = os.path.join(UPLOADS_DIR, "reports")


# =====================================================================
# SECURITY & OWNERSHIP HELPERS
# =====================================================================

def verify_student_role(current_user: Dict[str, Any]):
    """
    Ensures that the caller has Student (or Admin) authorization.
    Counsellors or non-student roles are denied with HTTP 403 Forbidden.
    """
    role = current_user.get("role")
    if role not in ("Student", "Admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access forbidden: Role '{role}' is not authorized for the Student Portal. Requires Student credentials."
        )


def resolve_authenticated_student_id(current_user: Dict[str, Any], cursor: sqlite3.Cursor) -> str:
    """
    Securely resolves the student_id belonging to the authenticated token.
    Never trusts client-supplied query/body params.
    """
    claims = current_user.get("claims", {})
    username = current_user.get("username", "")

    # 1. Direct claim in token
    token_sid = claims.get("student_id")
    if token_sid:
        cursor.execute("SELECT student_id FROM students WHERE student_id = ?;", (str(token_sid).strip(),))
        row = cursor.fetchone()
        if row:
            return row[0]

    # 2. Check if username matches student_id directly in students table
    cursor.execute("SELECT student_id FROM students WHERE student_id = ?;", (username,))
    row = cursor.fetchone()
    if row:
        return row[0]

    # 3. Check if username matches created_by in students table (latest record)
    cursor.execute("SELECT student_id FROM students WHERE created_by = ? ORDER BY id DESC LIMIT 1;", (username,))
    row = cursor.fetchone()
    if row:
        return row[0]

    # 4. Check student_profiles table
    cursor.execute("SELECT student_id FROM student_profiles WHERE student_id = ? OR full_name = ?;", (username, username))
    row = cursor.fetchone()
    if row:
        return row[0]

    # 5. If role is Student, default to username
    if current_user.get("role") == "Student":
        return username

    # If Admin without a mapped student, check claim or default to username
    return token_sid or username


def verify_student_assessment_ownership(
    cursor: sqlite3.Cursor,
    current_user: Dict[str, Any],
    clean_asm_id: str
) -> Dict[str, Any]:
    """
    Verifies that the requested assessment exists and belongs to the authenticated student.
    Returns the assessment record dict. Raises 403 if IDOR violation occurs.
    """
    role = current_user.get("role")
    student_id = resolve_authenticated_student_id(current_user, cursor)

    cursor.execute("""
        SELECT assessment_id, student_id, status, created_at, updated_at, completed_at
        FROM assessments WHERE assessment_id = ?;
    """, (clean_asm_id,))
    asm_row = cursor.fetchone()
    if not asm_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment '{clean_asm_id}' was not found"
        )

    asm_student_id = asm_row[1]

    # IDOR Check: Student can ONLY access their own assessment
    if role != "Admin" and asm_student_id.lower() != student_id.lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access forbidden: Assessment '{clean_asm_id}' belongs to another student"
        )

    return {
        "assessment_id": asm_row[0],
        "student_id": asm_student_id,
        "status": asm_row[2],
        "created_at": asm_row[3],
        "updated_at": asm_row[4],
        "completed_at": asm_row[5]
    }


def _log_student_audit(
    cursor: sqlite3.Cursor,
    user_id: str,
    role: str,
    action: str,
    assessment_id: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    safe_metadata: Optional[Dict[str, Any]] = None
):
    """Securely records audit logs without sensitive biometric or personal text."""
    audit_id = f"AUD-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO audit_logs (
            audit_id, user_id, role, action, assessment_id, entity_type, entity_id, safe_metadata_json, timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        audit_id,
        user_id,
        role,
        action,
        assessment_id,
        entity_type,
        entity_id,
        json.dumps(safe_metadata or {}),
        now_str
    ))


# =====================================================================
# 1. STUDENT PROFILE ENDPOINTS
# =====================================================================

@router.get(
    "/profile",
    summary="Retrieve authenticated student profile and active assessment info",
    status_code=status.HTTP_200_OK
)
@router.get(
    "/me",
    summary="Alias for /api/student/profile",
    status_code=status.HTTP_200_OK
)
async def get_student_profile(
    current_user: Dict[str, Any] = Depends(get_required_user)
):
    """
    GET /api/student/profile (and /api/student/me)
    Returns:
    - Student ID, Name, registration date
    - Demographic details if available
    - Active / most recent assessment summary
    Enforces that students only ever see their own profile.
    """
    verify_student_role(current_user)
    user_id = current_user.get("username", "")
    role = current_user.get("role", "")

    conn = get_connection()
    try:
        cur = conn.cursor()
        student_id = resolve_authenticated_student_id(current_user, cur)

        cur.execute("""
            SELECT student_id, student_name, created_by, created_at, updated_at
            FROM students WHERE student_id = ?;
        """, (student_id,))
        stu_row = cur.fetchone()

        if not stu_row:
            # Fallback check by name or created_by
            cur.execute("""
                SELECT student_id, student_name, created_by, created_at, updated_at
                FROM students WHERE created_by = ? OR student_name = ? ORDER BY id DESC LIMIT 1;
            """, (user_id, user_id))
            stu_row = cur.fetchone()

        if not stu_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No student record registered for user '{user_id}'"
            )

        actual_student_id = stu_row[0]
        student_name = stu_row[1]
        created_at = stu_row[3]

        # Optional demographics from student_profiles
        cur.execute("""
            SELECT age, gender, school_college, stream, course, location, created_on
            FROM student_profiles WHERE student_id = ?;
        """, (actual_student_id,))
        prof_row = cur.fetchone()
        demographics = None
        if prof_row:
            demographics = {
                "age": prof_row[0],
                "gender": prof_row[1],
                "school_college": prof_row[2],
                "stream": prof_row[3],
                "course": prof_row[4],
                "location": prof_row[5],
                "profile_created_on": prof_row[6]
            }

        # Active / latest assessment
        cur.execute("""
            SELECT assessment_id, status, created_at, completed_at
            FROM assessments WHERE student_id = ? ORDER BY id DESC LIMIT 1;
        """, (actual_student_id,))
        asm_row = cur.fetchone()
        active_assessment = None
        if asm_row:
            active_assessment = {
                "assessment_id": asm_row[0],
                "workflow_status": asm_row[1],
                "created_at": asm_row[2],
                "completed_at": asm_row[3]
            }

        _log_student_audit(
            cur, user_id, role, "STUDENT_PROFILE_RETRIEVED",
            assessment_id=active_assessment["assessment_id"] if active_assessment else None,
            entity_type="student", entity_id=actual_student_id,
            safe_metadata={"student_id": actual_student_id}
        )
        conn.commit()

        return {
            "status": "success",
            "student": {
                "student_id": actual_student_id,
                "student_name": student_name,
                "created_at": created_at,
                "demographics": demographics,
                "active_assessment": active_assessment
            }
        }
    finally:
        conn.close()


# =====================================================================
# 2. ASSESSMENT LIST & HISTORY
# =====================================================================

@router.get(
    "/assessments",
    summary="Retrieve all assessments belonging to the authenticated student",
    status_code=status.HTTP_200_OK
)
async def list_student_assessments(
    current_user: Dict[str, Any] = Depends(get_required_user)
):
    """
    GET /api/student/assessments
    Returns historical assessments belonging strictly to the authenticated student.
    Enriches each record with Left/Right scan statuses, analysis status, and report status.
    """
    verify_student_role(current_user)
    user_id = current_user.get("username", "")
    role = current_user.get("role", "")

    conn = get_connection()
    try:
        cur = conn.cursor()
        student_id = resolve_authenticated_student_id(current_user, cur)

        cur.execute("""
            SELECT assessment_id, status, created_at, updated_at, completed_at
            FROM assessments WHERE student_id = ? ORDER BY id DESC;
        """, (student_id,))
        asm_rows = cur.fetchall()

        assessments = []
        for r in asm_rows:
            aid = r[0]
            asm_status = r[1]
            created_at = r[2]
            updated_at = r[3]
            completed_at = r[4]

            # Scans
            cur.execute("""
                SELECT eye_side, status FROM eye_scans WHERE assessment_id = ? AND is_active = 1;
            """, (aid,))
            scans_dict = {sr[0]: sr[1] for sr in cur.fetchall()}
            left_status = str(scans_dict.get("LEFT", "PENDING")).upper()
            right_status = str(scans_dict.get("RIGHT", "PENDING")).upper()
            both_completed = (left_status in ("COMPLETED", "COMPLETE") and right_status in ("COMPLETED", "COMPLETE"))

            # Analysis
            cur.execute("SELECT id FROM analysis_results WHERE assessment_id = ?;", (aid,))
            analysis_completed = cur.fetchone() is not None

            # Report
            cur.execute("""
                SELECT report_id, version, status, reviewed_status FROM reports
                WHERE assessment_id = ? ORDER BY id DESC LIMIT 1;
            """, (aid,))
            rep_row = cur.fetchone()
            report_status = rep_row[2] if rep_row else "NOT_GENERATED"
            report_id = rep_row[0] if rep_row else None
            report_version = rep_row[1] if rep_row else None
            reviewed_status = bool(rep_row[3]) if rep_row else False

            # Contextual Next Action
            next_action = "CONTINUE_SCAN"
            if both_completed:
                if asm_status in ("PROCESSING", "ANALYZING"):
                    next_action = "ANALYSIS_IN_PROGRESS"
                elif report_status == "REPORT_READY":
                    next_action = "VIEW_REPORT"
                elif asm_status == "ANALYSIS_COMPLETED":
                    next_action = "REPORT_PENDING"
                else:
                    next_action = "START_ANALYSIS"

            assessments.append({
                "assessment_id": aid,
                "date": created_at,
                "workflow_status": asm_status,
                "left_scan_status": left_status,
                "right_scan_status": right_status,
                "analysis_status": "COMPLETED" if analysis_completed else ("PROCESSING" if asm_status == "PROCESSING" else "PENDING"),
                "report_status": report_status,
                "report_id": report_id,
                "report_version": report_version,
                "reviewed_status": reviewed_status,
                "next_action": next_action
            })

        _log_student_audit(
            cur, user_id, role, "STUDENT_ASSESSMENT_LIST_RETRIEVED",
            entity_type="student", entity_id=student_id,
            safe_metadata={"student_id": student_id, "count": len(assessments)}
        )
        conn.commit()

        return {
            "status": "success",
            "student_id": student_id,
            "count": len(assessments),
            "assessments": assessments
        }
    finally:
        conn.close()


# =====================================================================
# 3. DETAILED ASSESSMENT VIEW
# =====================================================================

@router.get(
    "/assessments/{assessmentId}",
    summary="Retrieve detailed assessment view for an assessment owned by student",
    status_code=status.HTTP_200_OK
)
@router.get(
    "/assessment",
    summary="Alias for the authenticated student's active assessment",
    status_code=status.HTTP_200_OK
)
async def get_student_assessment(
    assessmentId: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_required_user)
):
    """
    GET /api/student/assessments/{assessmentId} (or /api/student/assessment)
    Enforces student ownership. Returns HTTP 403 Forbidden if unowned.
    """
    verify_student_role(current_user)
    user_id = current_user.get("username", "")
    role = current_user.get("role", "")

    conn = get_connection()
    try:
        cur = conn.cursor()
        student_id = resolve_authenticated_student_id(current_user, cur)

        target_asm_id = assessmentId
        if not target_asm_id:
            # Query latest assessment for student
            cur.execute("""
                SELECT assessment_id FROM assessments WHERE student_id = ? ORDER BY id DESC LIMIT 1;
            """, (student_id,))
            latest = cur.fetchone()
            if not latest:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No assessment found for student '{student_id}'"
                )
            target_asm_id = latest[0]

        clean_asm_id = target_asm_id.strip()
        asm = verify_student_assessment_ownership(cur, current_user, clean_asm_id)

        # Scans details
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

        # Analysis status
        cur.execute("SELECT model_version, created_at FROM analysis_results WHERE assessment_id = ?;", (clean_asm_id,))
        a_row = cur.fetchone()
        analysis = {"model_version": a_row[0], "completed_at": a_row[1]} if a_row else None

        # Report status
        cur.execute("""
            SELECT report_id, version, status, generated_at, pdf_reference, reviewed_status
            FROM reports WHERE assessment_id = ? ORDER BY id DESC LIMIT 1;
        """, (clean_asm_id,))
        rep_row = cur.fetchone()
        report = {
            "report_id": rep_row[0],
            "version": rep_row[1],
            "status": rep_row[2],
            "generated_at": rep_row[3],
            "has_pdf": bool(rep_row[4]),
            "reviewed_status": bool(rep_row[5])
        } if rep_row else None

        _log_student_audit(
            cur, user_id, role, "STUDENT_ASSESSMENT_RETRIEVED",
            assessment_id=clean_asm_id, entity_type="assessment", entity_id=clean_asm_id,
            safe_metadata={"assessment_id": clean_asm_id}
        )
        conn.commit()

        return {
            "status": "success",
            "assessment_id": clean_asm_id,
            "student_id": asm["student_id"],
            "workflow_status": asm["status"],
            "created_at": asm["created_at"],
            "completed_at": asm["completed_at"],
            "scans": scans,
            "analysis": analysis,
            "report": report
        }
    finally:
        conn.close()


# =====================================================================
# 4. FAST STATUS POLLING
# =====================================================================

@router.get(
    "/assessments/{assessmentId}/status",
    summary="Fast status polling for an assessment owned by student",
    status_code=status.HTTP_200_OK
)
@router.get(
    "/assessment/status",
    summary="Alias for latest assessment status",
    status_code=status.HTTP_200_OK
)
async def get_student_assessment_status(
    assessmentId: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_required_user)
):
    """
    GET /api/student/assessments/{assessmentId}/status
    Lightweight endpoint for polling scanning and analysis progression.
    Enforces student ownership. Returns HTTP 403 Forbidden if unowned.
    """
    verify_student_role(current_user)

    conn = get_connection()
    try:
        cur = conn.cursor()
        student_id = resolve_authenticated_student_id(current_user, cur)

        target_asm_id = assessmentId
        if not target_asm_id:
            cur.execute("SELECT assessment_id FROM assessments WHERE student_id = ? ORDER BY id DESC LIMIT 1;", (student_id,))
            latest = cur.fetchone()
            if not latest:
                raise HTTPException(status_code=404, detail="No active assessment found.")
            target_asm_id = latest[0]

        clean_asm_id = target_asm_id.strip()
        asm = verify_student_assessment_ownership(cur, current_user, clean_asm_id)

        # Scans
        cur.execute("SELECT eye_side, status FROM eye_scans WHERE assessment_id = ? AND is_active = 1;", (clean_asm_id,))
        scans_dict = {r[0]: r[1] for r in cur.fetchall()}
        left_status = str(scans_dict.get("LEFT", "PENDING")).upper()
        right_status = str(scans_dict.get("RIGHT", "PENDING")).upper()
        both_completed = (left_status in ("COMPLETED", "COMPLETE") and right_status in ("COMPLETED", "COMPLETE"))

        # Report
        cur.execute("SELECT status, report_id FROM reports WHERE assessment_id = ? ORDER BY id DESC LIMIT 1;", (clean_asm_id,))
        rep_row = cur.fetchone()
        report_status = rep_row[0] if rep_row else "NOT_GENERATED"
        report_id = rep_row[1] if rep_row else None

        # Contextual next action
        next_action = "CONTINUE_SCAN"
        if both_completed:
            if asm["status"] in ("PROCESSING", "ANALYZING"):
                next_action = "ANALYSIS_IN_PROGRESS"
            elif report_status == "REPORT_READY":
                next_action = "VIEW_REPORT"
            elif asm["status"] == "ANALYSIS_COMPLETED":
                next_action = "REPORT_PENDING"
            else:
                next_action = "START_ANALYSIS"

        return {
            "status": True,
            "assessment_id": clean_asm_id,
            "workflow_status": asm["status"],
            "left_scan_status": left_status,
            "right_scan_status": right_status,
            "both_completed": both_completed,
            "report_status": report_status,
            "report_id": report_id,
            "next_action": next_action
        }
    finally:
        conn.close()


# =====================================================================
# 5. STUDENT REPORT RETRIEVAL
# =====================================================================

@router.get(
    "/assessments/{assessmentId}/report",
    summary="Retrieve structured 10-section report for student's own assessment",
    status_code=status.HTTP_200_OK
)
@router.get(
    "/report",
    summary="Alias for latest report retrieval",
    status_code=status.HTTP_200_OK
)
async def get_student_report(
    assessmentId: Optional[str] = None,
    version: Optional[str] = Query(None, description="Specific report semantic version (e.g. v1.0)"),
    current_user: Dict[str, Any] = Depends(get_required_user)
):
    """
    GET /api/student/assessments/{assessmentId}/report (and /api/student/report)
    Enforces student ownership. Returns HTTP 403 Forbidden if unowned.
    Reuses the Phase 5B 10-section structured report contract.
    """
    verify_student_role(current_user)
    user_id = current_user.get("username", "")
    role = current_user.get("role", "")

    conn = get_connection()
    try:
        cur = conn.cursor()
        student_id = resolve_authenticated_student_id(current_user, cur)

        target_asm_id = assessmentId
        if not target_asm_id:
            cur.execute("SELECT assessment_id FROM assessments WHERE student_id = ? ORDER BY id DESC LIMIT 1;", (student_id,))
            latest = cur.fetchone()
            if not latest:
                raise HTTPException(status_code=404, detail="No active assessment found.")
            target_asm_id = latest[0]

        clean_asm_id = target_asm_id.strip()
        verify_student_assessment_ownership(cur, current_user, clean_asm_id)

        _log_student_audit(
            cur, user_id, role, "STUDENT_REPORT_RETRIEVED",
            assessment_id=clean_asm_id, entity_type="report", entity_id=clean_asm_id,
            safe_metadata={"assessment_id": clean_asm_id}
        )
        conn.commit()
    finally:
        conn.close()

    # Delegate to the Phase 5B official report endpoint
    return await get_assessment_report(clean_asm_id, version=version, current_user=current_user)


# =====================================================================
# 6. STUDENT PDF DOWNLOAD
# =====================================================================

@router.get(
    "/assessments/{assessmentId}/report/pdf",
    summary="Securely download official server-side PDF for student's own assessment",
    status_code=status.HTTP_200_OK
)
@router.get(
    "/report/pdf",
    summary="Alias for latest PDF download",
    status_code=status.HTTP_200_OK
)
async def download_student_report_pdf(
    assessmentId: Optional[str] = None,
    version: Optional[str] = Query(None, description="Specific report semantic version (e.g. v1.0)"),
    current_user: Dict[str, Any] = Depends(get_required_user)
):
    """
    GET /api/student/assessments/{assessmentId}/report/pdf (and /api/student/report/pdf)
    Enforces student ownership. Returns HTTP 403 Forbidden if unowned.
    Reuses the Phase 5B server-side PDF generator and retrieval security.
    """
    verify_student_role(current_user)
    user_id = current_user.get("username", "")
    role = current_user.get("role", "")

    conn = get_connection()
    try:
        cur = conn.cursor()
        student_id = resolve_authenticated_student_id(current_user, cur)

        target_asm_id = assessmentId
        if not target_asm_id:
            cur.execute("SELECT assessment_id FROM assessments WHERE student_id = ? ORDER BY id DESC LIMIT 1;", (student_id,))
            latest = cur.fetchone()
            if not latest:
                raise HTTPException(status_code=404, detail="No active assessment found.")
            target_asm_id = latest[0]

        clean_asm_id = target_asm_id.strip()
        verify_student_assessment_ownership(cur, current_user, clean_asm_id)

        _log_student_audit(
            cur, user_id, role, "STUDENT_PDF_RETRIEVED",
            assessment_id=clean_asm_id, entity_type="pdf", entity_id=clean_asm_id,
            safe_metadata={"assessment_id": clean_asm_id}
        )
        conn.commit()
    finally:
        conn.close()

    # Delegate to the Phase 5B secure PDF download endpoint
    return await download_report_pdf(clean_asm_id, version=version, current_user=current_user)
