"""
Official IRIS Structured Report Generation & Server-Side PDF (Phase 5B).
Implements:
- POST /api/assessments/{assessmentId}/report/generate: Compiles and persists official 10-section report & PDF
- GET  /api/assessments/{assessmentId}/report: Retrieves structured 10-section report
- GET  /api/assessments/{assessmentId}/report/pdf: Securely downloads server-side generated PDF
- GET  /api/reports: Admin directory of generated reports
- GET  /api/reports/{reportId}: Single report detail view by report ID
- PATCH /api/assessments/{assessmentId}/report/review: Counsellor / Admin sign-off and review notes

Conforms strictly to:
- IRIS_Backend_Detailed_Requirements.docx
- IRIS_Frontend_Detailed_Requirements.docx
- scratch/phase5_report_field_mapping.md
- scratch/phase5_report_gap_analysis.md
- EXACT 10 LOGICAL SECTIONS with zero invented psychological, behavioral, or IQ claims
- Idempotent generation & controlled versioning
"""

import os
import json
import time
import uuid
import sqlite3
from datetime import datetime
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, HTTPException, Depends, status, Query, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from database_official import get_connection
from api.students import get_required_user, verify_student_read_access
from services.official_pdf_generator import build_official_pdf_report

router = APIRouter(tags=["Official IRIS Report Generation"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
REPORTS_DIR = os.path.join(UPLOADS_DIR, "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)


# =====================================================================
# PYDANTIC SCHEMAS
# =====================================================================

class ReviewReportRequest(BaseModel):
    review_notes: Optional[str] = Field(None, description="Clinical or guidance notes from counsellor")
    follow_up_date: Optional[str] = Field(None, description="Scheduled follow-up date (YYYY-MM-DD)")
    follow_up_notes: Optional[str] = Field(None, description="Objectives for the follow-up session")


# =====================================================================
# HELPER FUNCTIONS
# =====================================================================

def _log_audit_action(
    cursor: sqlite3.Cursor,
    user_id: str,
    role: str,
    action: str,
    assessment_id: Optional[str],
    entity_id: Optional[str] = None,
    status_str: str = "SUCCESS",
    metadata: Optional[Dict[str, Any]] = None
) -> None:
    """Inserts a secure sanitized audit log entry without secrets or raw images."""
    audit_id = f"AUD-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    safe_meta = json.dumps(metadata) if metadata else None
    cursor.execute("""
    INSERT INTO audit_logs (
        audit_id, user_id, role, action, assessment_id,
        entity_type, entity_id, status, safe_metadata_json, timestamp
    ) VALUES (?, ?, ?, ?, ?, 'report', ?, ?, ?, ?);
    """, (
        audit_id, user_id, role, action, assessment_id,
        entity_id or assessment_id, status_str, safe_meta, ts
    ))


def _record_processing_log(
    cursor: sqlite3.Cursor,
    assessment_id: str,
    operation: str,
    status_str: str,
    started_at: str,
    completed_at: Optional[str] = None,
    duration_ms: Optional[int] = None,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
    model_version: str = "iris-analysis-v1.0"
) -> str:
    """Records a processing log entry for asynchronous tracking and diagnostics."""
    processing_id = f"PRC-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
    cursor.execute("""
    INSERT INTO processing_logs (
        processing_id, assessment_id, operation, status,
        safe_error_code, safe_error_message, started_at, completed_at,
        duration_ms, model_version
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        processing_id, assessment_id, operation, status_str,
        error_code, error_message, started_at, completed_at,
        duration_ms, model_version
    ))
    return processing_id


def _compute_next_version(existing_versions: List[str]) -> str:
    """Computes semantic version string (e.g., 'v1.0' -> 'v1.1' -> 'v1.2')."""
    if not existing_versions:
        return "v1.0"
    max_minor = 0
    for v in existing_versions:
        try:
            if v.startswith("v") and "." in v:
                parts = v[1:].split(".")
                major = int(parts[0])
                minor = int(parts[1])
                if major == 1 and minor > max_minor:
                    max_minor = minor
        except Exception:
            continue
    return f"v1.{max_minor + 1}"


# =====================================================================
# REPORT GENERATION ENDPOINT
# =====================================================================

@router.post(
    "/api/assessments/{assessmentId}/report/generate",
    summary="Generate official 10-section report & server-side PDF",
    status_code=status.HTTP_200_OK
)
async def generate_official_report(
    assessmentId: str,
    regenerate: bool = Query(False, description="Force generation of a new semantic report version"),
    current_user: Dict[str, Any] = Depends(get_required_user)
):
    """
    POST /api/assessments/{assessmentId}/report/generate

    Workflow:
    ANALYSIS_COMPLETED -> REPORT_GENERATING -> REPORT_READY (or FAILED on error).

    Guarantees:
    - Enforces Student ownership, assigned Counsellor, or Admin authorization.
    - Assessment must exist (404).
    - Analysis must be complete (409 if before ANALYSIS_COMPLETED).
    - Idempotent: repeated calls return existing report without duplicate records unless regenerate=True.
    - Compiles exact 10 logical sections with zero fabricated claims.
    - Generates server-side vector PDF using ReportLab.
    - Persists sections to `report_sections` and master record to `reports`.
    - Updates assessment workflow status to REPORT_READY.
    - Comprehensive audit and processing logging.
    """
    start_ts = time.time()
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    user_id = current_user.get("username", "anonymous")
    user_role = current_user.get("role", "Student")
    clean_asm_id = assessmentId.strip()

    conn = get_connection()
    try:
        cur = conn.cursor()

        # 1. Lookup Assessment
        cur.execute("""
            SELECT id, assessment_id, student_id, status, created_at, completed_at
            FROM assessments WHERE assessment_id = ?;
        """, (clean_asm_id,))
        asm_row = cur.fetchone()
        if not asm_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Assessment '{clean_asm_id}' was not found"
            )

        asm_id_db, target_asm_id, target_student_id, current_asm_status, asm_created_at, asm_completed_at = asm_row

        # 2. RBAC Enforcement
        verify_student_read_access(current_user, target_student_id)

        # 3. Check Existing Report (Idempotency Check)
        cur.execute("""
            SELECT report_id, version, status, generated_at, pdf_reference,
                   reviewed_status, reviewed_by, reviewed_at
            FROM reports
            WHERE assessment_id = ?
            ORDER BY id DESC;
        """, (clean_asm_id,))
        existing_report_rows = cur.fetchall()

        if existing_report_rows and not regenerate:
            latest_rep = existing_report_rows[0]
            rep_id, rep_ver, rep_stat, rep_gen_at, rep_pdf_ref, rep_rev_stat, rep_rev_by, rep_rev_at = latest_rep
            if rep_stat == "REPORT_READY":
                # Check if sections exist
                cur.execute("""
                    SELECT section_key, title, content_json, order_num
                    FROM report_sections
                    WHERE report_id = ?
                    ORDER BY order_num ASC;
                """, (rep_id,))
                sec_rows = cur.fetchall()
                if len(sec_rows) == 10:
                    sections_dict = {r[0]: json.loads(r[2]) for r in sec_rows}
                    _log_audit_action(
                        cur, user_id, user_role, "REPORT_RETRIEVED",
                        clean_asm_id, entity_id=rep_id, status_str="SUCCESS",
                        metadata={"action": "idempotent_generate_return", "version": rep_ver}
                    )
                    conn.commit()
                    return {
                        "status": "success",
                        "message": "Report is ready",
                        "report_id": rep_id,
                        "assessment_id": clean_asm_id,
                        "version": rep_ver,
                        "report_status": rep_stat,
                        "generated_at": rep_gen_at,
                        "pdf_reference": rep_pdf_ref,
                        "sections": sections_dict
                    }

        # 4. Workflow State Gate: Must be ANALYSIS_COMPLETED (or REPORT_READY/FAILED for regeneration)
        valid_states = ("ANALYSIS_COMPLETED", "REPORT_GENERATING", "REPORT_READY")
        if current_asm_status == "FAILED" and regenerate:
            pass  # Allow controlled retry from FAILED
        elif current_asm_status not in valid_states:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot generate report for assessment '{clean_asm_id}' in state '{current_asm_status}'. Assessment analysis must be completed (ANALYSIS_COMPLETED) first."
            )

        # 5. Determine Report Version and Identifiers
        existing_versions = [r[1] for r in existing_report_rows]
        if regenerate and existing_report_rows:
            report_version = _compute_next_version(existing_versions)
        elif existing_report_rows and existing_report_rows[0][2] == "FAILED":
            report_version = existing_report_rows[0][1]
        else:
            report_version = "v1.0"

        report_id = f"REP-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

        # 6. Transition to REPORT_GENERATING
        cur.execute("""
            UPDATE assessments
            SET status = 'REPORT_GENERATING', updated_at = ?
            WHERE assessment_id = ?;
        """, (now_str, clean_asm_id))

        _log_audit_action(
            cur, user_id, user_role, "REPORT_GENERATION_STARTED",
            clean_asm_id, entity_id=report_id, status_str="SUCCESS",
            metadata={"version": report_version, "regenerate": regenerate}
        )

        proc_id = _record_processing_log(
            cur, clean_asm_id, "report_generation", "STARTED",
            started_at=now_str, model_version="iris-analysis-v1.0"
        )
        conn.commit()

        # 7. Collect Persisted Source Data for Exactly 10 Sections

        # --- Section 1: Student Details ---
        cur.execute("""
            SELECT student_id, student_name FROM students WHERE student_id = ?;
        """, (target_student_id,))
        student_master = cur.fetchone()
        student_name = student_master[1] if student_master else "Unknown Student"

        # Optional profile attributes
        cur.execute("""
            SELECT age, gender, school_college, stream, course, location, photo_path
            FROM student_profiles WHERE student_id = ?;
        """, (target_student_id,))
        prof_row = cur.fetchone()
        prof_age = prof_row[0] if prof_row else None
        prof_gender = prof_row[1] if prof_row else None
        prof_school = prof_row[2] if prof_row else None
        prof_stream = prof_row[3] if prof_row else None
        prof_course = prof_row[4] if prof_row else None
        prof_loc = prof_row[5] if prof_row else None
        prof_photo = prof_row[6] if prof_row else None

        section_student = {
            "student_id": target_student_id,
            "student_name": student_name,
            "age": prof_age,
            "gender": prof_gender,
            "school_college": prof_school,
            "stream": prof_stream,
            "course": prof_course,
            "location": prof_loc,
            "photo_url": f"/api/media/{prof_photo}" if prof_photo else None
        }

        # --- Section 2: Assessment Details ---
        section_assessment = {
            "assessment_id": clean_asm_id,
            "assessment_date": asm_created_at,
            "workflow_status": "REPORT_READY",
            "completed_at": asm_completed_at or now_str
        }

        # --- Section 3: Bilateral Eye Scans ---
        cur.execute("""
            SELECT results_json, model_version
            FROM analysis_results
            WHERE assessment_id = ?;
        """, (clean_asm_id,))
        analysis_row = cur.fetchone()
        if not analysis_row:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Analysis results for assessment '{clean_asm_id}' were not found. Please run analysis processing first."
            )

        analysis_json = json.loads(analysis_row[0])
        left_eye_data = analysis_json.get("left_eye", {})
        right_eye_data = analysis_json.get("right_eye", {})
        bilateral_data = analysis_json.get("bilateral_analysis", {})

        cur.execute("""
            SELECT scan_id, eye_side, status, file_reference
            FROM eye_scans
            WHERE assessment_id = ? AND is_active = 1;
        """, (clean_asm_id,))
        active_scans = {row[1]: {"scan_id": row[0], "status": row[2], "file_ref": row[3]} for row in cur.fetchall()}

        left_scan_meta = active_scans.get("LEFT", {})
        right_scan_meta = active_scans.get("RIGHT", {})

        section_eye_scan = {
            "left_scan": {
                "scan_id": left_scan_meta.get("scan_id") or left_eye_data.get("scan_id"),
                "status": left_scan_meta.get("status", "Completed"),
                "quality_score": left_eye_data.get("quality", {}).get("capture_quality_score"),
                "blur_score": left_eye_data.get("quality", {}).get("blur_score"),
                "detected_color": left_eye_data.get("color", {}).get("eye_color"),
                "pupil_radius": left_eye_data.get("features", {}).get("pupil_radius") or (left_eye_data.get("pupil_circle") or {}).get("radius"),
                "iris_radius": left_eye_data.get("features", {}).get("iris_radius") or (left_eye_data.get("iris_circle") or {}).get("radius"),
                "pupil_iris_ratio": left_eye_data.get("features", {}).get("pupil_iris_ratio"),
                "image_ref": left_scan_meta.get("file_ref") or left_eye_data.get("file_reference")
            },
            "right_scan": {
                "scan_id": right_scan_meta.get("scan_id") or right_eye_data.get("scan_id"),
                "status": right_scan_meta.get("status", "Completed"),
                "quality_score": right_eye_data.get("quality", {}).get("capture_quality_score"),
                "blur_score": right_eye_data.get("quality", {}).get("blur_score"),
                "detected_color": right_eye_data.get("color", {}).get("eye_color"),
                "pupil_radius": right_eye_data.get("features", {}).get("pupil_radius") or (right_eye_data.get("pupil_circle") or {}).get("radius"),
                "iris_radius": right_eye_data.get("features", {}).get("iris_radius") or (right_eye_data.get("iris_circle") or {}).get("radius"),
                "pupil_iris_ratio": right_eye_data.get("features", {}).get("pupil_iris_ratio"),
                "image_ref": right_scan_meta.get("file_ref") or right_eye_data.get("file_reference")
            }
        }

        # --- Section 4: Overall Biometric Result ---
        avg_q = bilateral_data.get("average_quality_score")
        p_delta = bilateral_data.get("pupil_radius_delta")
        r_delta = bilateral_data.get("pupil_iris_ratio_delta")
        sim = bilateral_data.get("bilateral_geometric_similarity")
        c_match = bilateral_data.get("color_match")

        factual_summary = (
            f"Bilateral iris scans completed with combined quality score of {avg_q}%. "
            f"Geometric similarity index between left and right iris structures is {sim}. "
            f"Pupil diameter delta is {p_delta}px with {'consistent' if c_match else 'divergent'} bilateral pigmentation."
        )

        section_overall = {
            "combined_capture_quality": avg_q,
            "bilateral_symmetry_delta": p_delta,
            "pupil_iris_ratio_delta": r_delta,
            "bilateral_similarity": sim,
            "color_consistency": c_match,
            "biometric_summary": factual_summary
        }

        # --- Sections 5, 6, 7, 8: Explicit Pending Sections (Anti-Fabrication) ---
        section_behaviour = {
            "status": "PENDING_ASSESSMENT_INPUT",
            "message": "Questionnaire assessment pending",
            "data": None
        }

        section_personality = {
            "status": "PENDING_ASSESSMENT_INPUT",
            "message": "Questionnaire assessment pending",
            "data": None
        }

        section_subjects = {
            "status": "PROFILE_DATA_PENDING",
            "message": "Academic records pending",
            "data": None
        }

        section_recommendations = {
            "status": "PENDING_ASSESSMENT_INPUT",
            "message": "Assessment recommendations pending",
            "data": None
        }

        # --- Section 9: Counselling & Follow-up ---
        cur.execute("""
            SELECT counsellor_id, assigned_at
            FROM counsellor_assignments
            WHERE assessment_id = ? AND is_active = 1
            LIMIT 1;
        """, (clean_asm_id,))
        counsellor_row = cur.fetchone()
        assigned_counsellor_id = counsellor_row[0] if counsellor_row else None
        assigned_at = counsellor_row[1] if counsellor_row else None

        cur.execute("""
            SELECT note_id, counsellor_id, note, created_at
            FROM counselling_notes
            WHERE assessment_id = ?
            ORDER BY created_at ASC;
        """, (clean_asm_id,))
        notes_rows = [
            {"note_id": r[0], "counsellor_id": r[1], "note": r[2], "created_at": r[3]}
            for r in cur.fetchall()
        ]

        cur.execute("""
            SELECT follow_up_id, counsellor_id, follow_up_date, status, notes
            FROM follow_ups
            WHERE assessment_id = ?
            ORDER BY follow_up_date ASC;
        """, (clean_asm_id,))
        followup_rows = [
            {"follow_up_id": r[0], "counsellor_id": r[1], "follow_up_date": r[2], "status": r[3], "notes": r[4]}
            for r in cur.fetchall()
        ]

        section_counselling = {
            "assigned_counsellor_id": assigned_counsellor_id,
            "assigned_at": assigned_at,
            "reviewed_status": 0,
            "reviewed_by": None,
            "reviewed_at": None,
            "counselling_notes": notes_rows,
            "follow_ups": followup_rows
        }

        # --- Section 10: Report Metadata ---
        relative_pdf_ref = f"reports/{report_id}.pdf"
        pipeline_version = analysis_json.get("model_metadata", {}).get("pipeline_version", "iris-analysis-v1.0")

        section_meta = {
            "report_id": report_id,
            "version": report_version,
            "status": "REPORT_READY",
            "generated_date": now_str,
            "pdf_reference": relative_pdf_ref,
            "pipeline_version": pipeline_version
        }

        # Assemble Exact 10 Logical Sections
        all_sections = {
            "student": section_student,
            "assessment": section_assessment,
            "eye_scan": section_eye_scan,
            "overall_result": section_overall,
            "behaviour": section_behaviour,
            "personality": section_personality,
            "subjects_interest": section_subjects,
            "recommendations": section_recommendations,
            "counselling": section_counselling,
            "report_meta": section_meta
        }

        # 8. Server-Side PDF Generation
        pdf_absolute_path = os.path.join(REPORTS_DIR, f"{report_id}.pdf")
        report_payload_for_pdf = {
            "report_id": report_id,
            "version": report_version,
            "status": "REPORT_READY",
            "sections": all_sections
        }

        try:
            build_official_pdf_report(report_payload_for_pdf, pdf_absolute_path, uploads_dir=UPLOADS_DIR)
            _log_audit_action(
                cur, user_id, user_role, "PDF_GENERATED",
                clean_asm_id, entity_id=report_id, status_str="SUCCESS",
                metadata={"pdf_reference": relative_pdf_ref}
            )
        except Exception as pdf_err:
            raise RuntimeError(f"Server-side PDF generation failed: {str(pdf_err)}")

        # 9. Persist Report Master and Sections
        cur.execute("""
            INSERT OR REPLACE INTO reports (
                report_id, assessment_id, version, status,
                generated_at, pdf_reference, reviewed_status,
                reviewed_by, reviewed_at, created_at, updated_at
            ) VALUES (?, ?, ?, 'REPORT_READY', ?, ?, 0, NULL, NULL, ?, ?);
        """, (
            report_id, clean_asm_id, report_version,
            now_str, relative_pdf_ref, now_str, now_str
        ))

        section_titles = {
            "student": "Student Profile Details",
            "assessment": "Assessment Overview & Timeline",
            "eye_scan": "Bilateral Dual-Eye Iris Scans",
            "overall_result": "Overall Biometric Synthesis & Bilateral Symmetry",
            "behaviour": "Behavioral Evaluation",
            "personality": "Big Five Personality Dimensions",
            "subjects_interest": "Academic Records & Subject Interests",
            "recommendations": "Educational & Career Guidance",
            "counselling": "Counsellor Guidance & Review Notes",
            "report_meta": "Report Metadata & Regulatory Disclaimer"
        }

        for order_idx, (sec_key, sec_content) in enumerate(all_sections.items(), start=1):
            cur.execute("""
                INSERT INTO report_sections (
                    report_id, section_key, title, content_json, order_num, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(report_id, section_key) DO UPDATE SET
                    title = excluded.title,
                    content_json = excluded.content_json,
                    order_num = excluded.order_num,
                    created_at = excluded.created_at;
            """, (
                report_id, sec_key, section_titles.get(sec_key, sec_key),
                json.dumps(sec_content), order_idx, now_str
            ))

        # 10. Update Assessment Workflow Status to REPORT_READY
        cur.execute("""
            UPDATE assessments
            SET status = 'REPORT_READY', updated_at = ?
            WHERE assessment_id = ?;
        """, (now_str, clean_asm_id))

        end_ts = time.time()
        duration_ms = int((end_ts - start_ts) * 1000)

        # Update processing log
        cur.execute("""
            UPDATE processing_logs
            SET status = 'COMPLETED', completed_at = ?, duration_ms = ?
            WHERE processing_id = ?;
        """, (now_str, duration_ms, proc_id))

        _log_audit_action(
            cur, user_id, user_role, "REPORT_GENERATION_COMPLETED",
            clean_asm_id, entity_id=report_id, status_str="SUCCESS",
            metadata={"duration_ms": duration_ms, "version": report_version}
        )

        conn.commit()

        return {
            "status": "success",
            "message": "Report generated successfully",
            "report_id": report_id,
            "assessment_id": clean_asm_id,
            "version": report_version,
            "report_status": "REPORT_READY",
            "generated_at": now_str,
            "pdf_reference": relative_pdf_ref,
            "sections": all_sections
        }

    except HTTPException:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        # Record failure state safely
        fail_conn = get_connection()
        try:
            fcur = fail_conn.cursor()
            fcur.execute("""
                UPDATE assessments
                SET status = 'FAILED', updated_at = datetime('now')
                WHERE assessment_id = ?;
            """, (clean_asm_id,))
            _log_audit_action(
                fcur, user_id, user_role, "REPORT_GENERATION_FAILED",
                clean_asm_id, status_str="FAILED",
                metadata={"error": "Processing exception occurred during report compilation"}
            )
            fail_conn.commit()
        finally:
            fail_conn.close()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while compiling the official report. Workflow state has been safely set to FAILED."
        )
    finally:
        conn.close()


# =====================================================================
# REPORT RETRIEVAL ENDPOINT
# =====================================================================

@router.get(
    "/api/assessments/{assessmentId}/report",
    summary="Retrieve structured 10-section report",
    status_code=status.HTTP_200_OK
)
async def get_assessment_report(
    assessmentId: str,
    version: Optional[str] = Query(None, description="Optional specific report version (e.g. 'v1.0')"),
    current_user: Dict[str, Any] = Depends(get_required_user)
):
    """
    GET /api/assessments/{assessmentId}/report

    Requirements:
    - Enforces Student ownership, assigned Counsellor, or Admin authorization.
    - Assessment must exist (404).
    - If report does not exist -> 404.
    - Returns structured 10-section JSON payload.
    - Logs REPORT_RETRIEVED audit action.
    """
    clean_asm_id = assessmentId.strip()
    user_id = current_user.get("username", "anonymous")
    user_role = current_user.get("role", "Student")

    conn = get_connection()
    try:
        cur = conn.cursor()

        # 1. Lookup Assessment
        cur.execute("SELECT student_id, status FROM assessments WHERE assessment_id = ?;", (clean_asm_id,))
        asm_row = cur.fetchone()
        if not asm_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Assessment '{clean_asm_id}' was not found"
            )

        target_student_id, asm_status = asm_row
        verify_student_read_access(current_user, target_student_id)

        # 2. Query Report
        if version:
            cur.execute("""
                SELECT report_id, version, status, generated_at, pdf_reference,
                       reviewed_status, reviewed_by, reviewed_at
                FROM reports
                WHERE assessment_id = ? AND version = ?;
            """, (clean_asm_id, version.strip()))
        else:
            cur.execute("""
                SELECT report_id, version, status, generated_at, pdf_reference,
                       reviewed_status, reviewed_by, reviewed_at
                FROM reports
                WHERE assessment_id = ?
                ORDER BY id DESC LIMIT 1;
            """, (clean_asm_id,))

        rep_row = cur.fetchone()
        if not rep_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No report has been generated for assessment '{clean_asm_id}'"
            )

        report_id, rep_version, rep_status, gen_at, pdf_ref, rev_stat, rev_by, rev_at = rep_row

        # 3. Fetch 10 Sections
        cur.execute("""
            SELECT section_key, title, content_json, order_num
            FROM report_sections
            WHERE report_id = ?
            ORDER BY order_num ASC;
        """, (report_id,))
        sections_rows = cur.fetchall()

        sections_dict = {}
        for r in sections_rows:
            sections_dict[r[0]] = json.loads(r[2])

        _log_audit_action(
            cur, user_id, user_role, "REPORT_RETRIEVED",
            clean_asm_id, entity_id=report_id, status_str="SUCCESS",
            metadata={"version": rep_version}
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
            "reviewed_status": rev_stat,
            "reviewed_by": rev_by,
            "reviewed_at": rev_at,
            "sections": sections_dict
        }
    finally:
        conn.close()


# =====================================================================
# SERVER-SIDE PDF RETRIEVAL ENDPOINT
# =====================================================================

@router.get(
    "/api/assessments/{assessmentId}/report/pdf",
    summary="Securely download server-side generated PDF report"
)
async def download_report_pdf(
    assessmentId: str,
    version: Optional[str] = Query(None, description="Optional specific report version"),
    current_user: Dict[str, Any] = Depends(get_required_user)
):
    """
    GET /api/assessments/{assessmentId}/report/pdf

    Security & Access Control:
    - Enforces Student ownership, assigned Counsellor, or Admin authorization.
    - Path traversal protection: prevents arbitrary filesystem access.
    - Zero filesystem path leakage in headers or error messages.
    - Logs PDF_RETRIEVED audit action.
    """
    clean_asm_id = assessmentId.strip()
    user_id = current_user.get("username", "anonymous")
    user_role = current_user.get("role", "Student")

    conn = get_connection()
    try:
        cur = conn.cursor()

        # 1. Lookup Assessment
        cur.execute("SELECT student_id, status FROM assessments WHERE assessment_id = ?;", (clean_asm_id,))
        asm_row = cur.fetchone()
        if not asm_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Assessment '{clean_asm_id}' was not found"
            )

        target_student_id, asm_status = asm_row
        verify_student_read_access(current_user, target_student_id)

        # 2. Query Report Record
        if version:
            cur.execute("""
                SELECT report_id, version, status, pdf_reference
                FROM reports
                WHERE assessment_id = ? AND version = ? AND status = 'REPORT_READY';
            """, (clean_asm_id, version.strip()))
        else:
            cur.execute("""
                SELECT report_id, version, status, pdf_reference
                FROM reports
                WHERE assessment_id = ? AND status = 'REPORT_READY'
                ORDER BY id DESC LIMIT 1;
            """, (clean_asm_id,))

        rep_row = cur.fetchone()
        if not rep_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Official PDF report is not ready or has not been generated for assessment '{clean_asm_id}'"
            )

        report_id, rep_version, rep_status, pdf_ref = rep_row

        # 3. Path Traversal Hardening
        if not pdf_ref:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="PDF reference missing for this report"
            )

        # Resolve relative to UPLOADS_DIR
        safe_full_path = os.path.normpath(os.path.join(UPLOADS_DIR, pdf_ref))
        expected_root = os.path.abspath(UPLOADS_DIR)

        if not safe_full_path.startswith(expected_root):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid report file reference"
            )

        # If file on disk does not exist, re-render it from database sections
        if not os.path.exists(safe_full_path):
            cur.execute("""
                SELECT section_key, title, content_json, order_num
                FROM report_sections
                WHERE report_id = ?
                ORDER BY order_num ASC;
            """, (report_id,))
            sec_rows = cur.fetchall()
            if not sec_rows:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Report data unavailable for PDF generation"
                )
            sections_dict = {r[0]: json.loads(r[2]) for r in sec_rows}
            rebuild_payload = {
                "report_id": report_id,
                "version": rep_version,
                "status": rep_status,
                "sections": sections_dict
            }
            build_official_pdf_report(rebuild_payload, safe_full_path, uploads_dir=UPLOADS_DIR)

        _log_audit_action(
            cur, user_id, user_role, "PDF_RETRIEVED",
            clean_asm_id, entity_id=report_id, status_str="SUCCESS",
            metadata={"version": rep_version}
        )
        conn.commit()

        safe_filename = f"IRIS_Report_{clean_asm_id}_{report_id}.pdf"
        return FileResponse(
            path=safe_full_path,
            media_type="application/pdf",
            filename=safe_filename,
            headers={"Content-Disposition": f'inline; filename="{safe_filename}"'}
        )
    finally:
        conn.close()


# =====================================================================
# ADMIN GLOBAL REPORT LISTING ENDPOINT
# =====================================================================

@router.get(
    "/api/reports",
    summary="Admin directory of generated assessment reports",
    status_code=status.HTTP_200_OK
)
async def list_official_reports(
    page: int = Query(1, ge=1, description="Page index"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search by student ID, assessment ID, or report ID"),
    current_user: Dict[str, Any] = Depends(get_required_user)
):
    """
    GET /api/reports
    Admin-only directory listing of all generated reports.
    """
    role = current_user.get("role")
    if role != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required to access report directory"
        )

    conn = get_connection()
    try:
        cur = conn.cursor()
        query = """
            SELECT r.report_id, r.assessment_id, r.version, r.status,
                   r.generated_at, r.pdf_reference, r.reviewed_status,
                   a.student_id, s.student_name
            FROM reports r
            JOIN assessments a ON r.assessment_id = a.assessment_id
            JOIN students s ON a.student_id = s.student_id
        """
        params = []
        if search:
            s_term = f"%{search.strip()}%"
            query += " WHERE (r.report_id LIKE ? OR r.assessment_id LIKE ? OR a.student_id LIKE ? OR s.student_name LIKE ?)"
            params.extend([s_term, s_term, s_term, s_term])

        query += " ORDER BY r.id DESC LIMIT ? OFFSET ?;"
        params.extend([limit, (page - 1) * limit])

        cur.execute(query, tuple(params))
        rows = cur.fetchall()

        items = [
            {
                "report_id": r[0],
                "assessment_id": r[1],
                "version": r[2],
                "status": r[3],
                "generated_at": r[4],
                "pdf_reference": r[5],
                "reviewed_status": r[6],
                "student_id": r[7],
                "student_name": r[8]
            }
            for r in rows
        ]

        return {
            "status": "success",
            "page": page,
            "limit": limit,
            "count": len(items),
            "reports": items
        }
    finally:
        conn.close()


# =====================================================================
# REPORT DETAIL BY REPORT ID
# =====================================================================

@router.get(
    "/api/reports/{reportId}",
    summary="Get single report details by unique report ID",
    status_code=status.HTTP_200_OK
)
async def get_report_by_id(
    reportId: str,
    current_user: Dict[str, Any] = Depends(get_required_user)
):
    """
    GET /api/reports/{reportId}
    Retrieves full 10-section report by unique report_id.
    """
    clean_rep_id = reportId.strip()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT r.report_id, r.assessment_id, r.version, r.status,
                   r.generated_at, r.pdf_reference, r.reviewed_status,
                   r.reviewed_by, r.reviewed_at, a.student_id
            FROM reports r
            JOIN assessments a ON r.assessment_id = a.assessment_id
            WHERE r.report_id = ?;
        """, (clean_rep_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Report '{clean_rep_id}' was not found"
            )

        rep_id, asm_id, ver, stat, gen_at, pdf_ref, rev_stat, rev_by, rev_at, stu_id = row
        verify_student_read_access(current_user, stu_id)

        cur.execute("""
            SELECT section_key, title, content_json, order_num
            FROM report_sections
            WHERE report_id = ?
            ORDER BY order_num ASC;
        """, (clean_rep_id,))
        sec_rows = cur.fetchall()
        sections_dict = {r[0]: json.loads(r[2]) for r in sec_rows}

        return {
            "status": "success",
            "report_id": rep_id,
            "assessment_id": asm_id,
            "version": ver,
            "report_status": stat,
            "generated_at": gen_at,
            "pdf_reference": pdf_ref,
            "reviewed_status": rev_stat,
            "reviewed_by": rev_by,
            "reviewed_at": rev_at,
            "sections": sections_dict
        }
    finally:
        conn.close()


# =====================================================================
# COUNSELLOR REPORT REVIEW & NOTES ENDPOINT
# =====================================================================

@router.patch(
    "/api/assessments/{assessmentId}/report/review",
    summary="Counsellor or Admin review sign-off and clinical notes",
    status_code=status.HTTP_200_OK
)
async def review_assessment_report(
    assessmentId: str,
    payload: ReviewReportRequest,
    current_user: Dict[str, Any] = Depends(get_required_user)
):
    """
    PATCH /api/assessments/{assessmentId}/report/review

    Enables assigned Counsellor or Admin to:
    - Mark report as reviewed (reviewed_status = 1).
    - Add counselling notes.
    - Schedule follow-up consultations.
    - Updates section 9 in report_sections and regenerates PDF.
    """
    role = current_user.get("role")
    user_id = current_user.get("username", "anonymous")
    clean_asm_id = assessmentId.strip()
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    if role not in ("Admin", "Counselor", "Counsellor"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only assigned counsellors or administrators may submit report reviews"
        )

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT student_id FROM assessments WHERE assessment_id = ?;", (clean_asm_id,))
        asm_row = cur.fetchone()
        if not asm_row:
            raise HTTPException(status_code=404, detail="Assessment not found")

        student_id = asm_row[0]
        verify_student_read_access(current_user, student_id)

        # Fetch active report
        cur.execute("""
            SELECT report_id, version, pdf_reference
            FROM reports WHERE assessment_id = ? AND status = 'REPORT_READY'
            ORDER BY id DESC LIMIT 1;
        """, (clean_asm_id,))
        rep_row = cur.fetchone()
        if not rep_row:
            raise HTTPException(status_code=404, detail="Report not ready for review")

        report_id, rep_version, pdf_ref = rep_row

        # Update review status in reports
        cur.execute("""
            UPDATE reports
            SET reviewed_status = 1, reviewed_by = ?, reviewed_at = ?, updated_at = ?
            WHERE report_id = ?;
        """, (user_id, now_str, now_str, report_id))

        # Add optional counselling note
        if payload.review_notes:
            note_id = f"NOT-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
            cur.execute("""
                INSERT INTO counselling_notes (note_id, assessment_id, counsellor_id, note, created_at)
                VALUES (?, ?, ?, ?, ?);
            """, (note_id, clean_asm_id, user_id, payload.review_notes.strip(), now_str))

        # Add optional follow-up
        if payload.follow_up_date:
            fu_id = f"FOL-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
            cur.execute("""
                INSERT INTO follow_ups (follow_up_id, assessment_id, counsellor_id, follow_up_date, status, notes, created_at)
                VALUES (?, ?, ?, ?, 'Pending', ?, ?);
            """, (fu_id, clean_asm_id, user_id, payload.follow_up_date.strip(), payload.follow_up_notes or "", now_str))

        # Refresh Section 9 (counselling)
        cur.execute("""
            SELECT note_id, counsellor_id, note, created_at
            FROM counselling_notes WHERE assessment_id = ? ORDER BY created_at ASC;
        """, (clean_asm_id,))
        all_notes = [{"note_id": r[0], "counsellor_id": r[1], "note": r[2], "created_at": r[3]} for r in cur.fetchall()]

        cur.execute("""
            SELECT follow_up_id, counsellor_id, follow_up_date, status, notes
            FROM follow_ups WHERE assessment_id = ? ORDER BY follow_up_date ASC;
        """, (clean_asm_id,))
        all_fu = [{"follow_up_id": r[0], "counsellor_id": r[1], "follow_up_date": r[2], "status": r[3], "notes": r[4]} for r in cur.fetchall()]

        cur.execute("""
            SELECT counsellor_id, assigned_at
            FROM counsellor_assignments WHERE assessment_id = ? AND is_active = 1 LIMIT 1;
        """, (clean_asm_id,))
        c_row = cur.fetchone()

        updated_counselling_sec = {
            "assigned_counsellor_id": c_row[0] if c_row else user_id,
            "assigned_at": c_row[1] if c_row else now_str,
            "reviewed_status": 1,
            "reviewed_by": user_id,
            "reviewed_at": now_str,
            "counselling_notes": all_notes,
            "follow_ups": all_fu
        }

        cur.execute("""
            UPDATE report_sections
            SET content_json = ?, created_at = ?
            WHERE report_id = ? AND section_key = 'counselling';
        """, (json.dumps(updated_counselling_sec), now_str, report_id))

        # Re-render updated PDF
        cur.execute("""
            SELECT section_key, title, content_json, order_num
            FROM report_sections WHERE report_id = ? ORDER BY order_num ASC;
        """, (report_id,))
        all_sec_rows = cur.fetchall()
        full_sections = {r[0]: json.loads(r[2]) for r in all_sec_rows}

        pdf_path = os.path.join(REPORTS_DIR, f"{report_id}.pdf")
        build_official_pdf_report(
            {"report_id": report_id, "version": rep_version, "status": "REPORT_READY", "sections": full_sections},
            pdf_path,
            uploads_dir=UPLOADS_DIR
        )

        _log_audit_action(
            cur, user_id, role, "REPORT_REVIEWED",
            clean_asm_id, entity_id=report_id, status_str="SUCCESS",
            metadata={"reviewer": user_id, "timestamp": now_str}
        )

        conn.commit()

        return {
            "status": "success",
            "message": "Report marked as reviewed and counselling records updated",
            "reviewed_status": 1,
            "reviewed_by": user_id,
            "reviewed_at": now_str,
            "counselling": updated_counselling_sec
        }
    finally:
        conn.close()
