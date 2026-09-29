"""
Official IRIS Bilateral Analysis Processing & Structured Analysis Results (Phase 4).
Implements:
- POST /api/assessments/{assessmentId}/process: Executes bilateral analysis processing
- GET  /api/assessments/{assessmentId}/process/status: Polling endpoint for analysis job/workflow status
- GET  /api/assessments/{assessmentId}/analysis: Retrieves persisted structured analysis results

Strictly conforms to:
- IRIS_Backend_Detailed_Requirements.docx
- IRIS_Frontend_Detailed_Requirements.docx
- State transitions: SCAN_COMPLETED -> PROCESSING -> ANALYSIS_COMPLETED (or FAILED)
- Both-eyes completion requirement (LEFT=Completed AND RIGHT=Completed)
- Real biometric CV/ML pipeline reuse (NO fabricated psychological or personality claims)
- Provenance tagging (iris-derived, ml-derived, rule-based)
"""

import os
import json
import time
import uuid
import sqlite3
from datetime import datetime
from typing import Optional, Dict, Any

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException, Depends, status

from database_official import get_connection
from api.students import get_required_user, verify_student_read_access

# Existing ML and CV Utilities (Reused without modification)
from utils.pupil_detection import detect_pupil
from utils.iris_segmentation import segment_iris
from utils.iris_quality_analyzer import analyze_iris_quality
from utils.feature_extractor import extract_features
from utils.color_analysis import analyze_color
from utils.iris_normalization import normalize_iris
from utils.lbp_extractor import calculate_lbp
from utils.similarity import cosine_similarity

router = APIRouter(prefix="/api/assessments", tags=["Official IRIS Analysis Processing"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")


def _sanitize_for_json(obj: Any) -> Any:
    """Recursively converts NumPy scalar types and arrays to standard Python types for JSON serialization."""
    if isinstance(obj, (np.integer, np.int64, np.int32, np.int16, np.int8, np.uint8, np.uint16, np.uint32, np.uint64)):
        return int(obj)
    if isinstance(obj, (np.floating, np.float32, np.float64)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    return obj


def _log_audit_action(
    cursor: sqlite3.Cursor,
    user_id: str,
    role: str,
    action: str,
    assessment_id: str,
    status_str: str = "SUCCESS",
    metadata: Optional[Dict[str, Any]] = None
) -> None:
    """Inserts a secure sanitized audit log entry."""
    audit_id = f"AUD-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    safe_meta = json.dumps(_sanitize_for_json(metadata)) if metadata else None
    cursor.execute("""
    INSERT INTO audit_logs (
        audit_id, user_id, role, action, assessment_id,
        entity_type, entity_id, status, safe_metadata_json, timestamp
    ) VALUES (?, ?, ?, ?, ?, 'assessment', ?, ?, ?, ?);
    """, (
        audit_id, user_id, role, action, assessment_id,
        assessment_id, status_str, safe_meta, ts
    ))


@router.post("/{assessmentId}/process", summary="Execute official bilateral iris analysis")
async def process_assessment_analysis(
    assessmentId: str,
    current_user: Dict[str, Any] = Depends(get_required_user)
):
    """
    POST /api/assessments/{assessmentId}/process

    Requirements:
    1. Authenticated user (Admin, owning Student, or assigned Counsellor).
    2. Assessment must exist.
    3. BOTH LEFT and RIGHT active eye scans must have status == 'Completed'.
    4. Rejects processing with HTTP 409 if either eye scan is incomplete or missing.
    5. Transitions assessment: SCAN_COMPLETED (or FAILED) -> PROCESSING -> ANALYSIS_COMPLETED.
    6. Idempotent: repeated requests on completed analysis return existing results safely.
    7. Executes real bilateral feature extraction, quality analysis, color analysis, and symmetry comparison.
    8. Persists structured results into analysis_results table with explicit provenance tags.
    9. Records processing_logs and audit_logs.
    """
    clean_asm_id = assessmentId.strip()
    username = current_user.get("username", "unknown")
    user_role = current_user.get("role", "unknown")

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # 1. Fetch assessment
        cursor.execute("""
        SELECT assessment_id, student_id, status, created_by, completed_at
        FROM assessments
        WHERE assessment_id = ?;
        """, (clean_asm_id,))
        asm_row = cursor.fetchone()

        if not asm_row:
            conn.close()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Assessment '{clean_asm_id}' not found."
            )

        target_student_id = asm_row[1]
        current_asm_status = asm_row[2]

        # 2. RBAC check (Admin, Student owner, or assigned Counsellor)
        verify_student_read_access(current_user, target_student_id)

        # 3. Idempotency Check: Already completed?
        if current_asm_status == "ANALYSIS_COMPLETED":
            cursor.execute("""
            SELECT results_json, model_version, created_at, updated_at
            FROM analysis_results
            WHERE assessment_id = ?;
            """, (clean_asm_id,))
            res_row = cursor.fetchone()

            if res_row:
                parsed_res = json.loads(res_row[0])
                conn.close()
                return {
                    "status": True,
                    "already_completed": True,
                    "message": "Analysis is already completed for this assessment.",
                    "assessment_id": clean_asm_id,
                    "workflow_status": "ANALYSIS_COMPLETED",
                    "model_version": res_row[1],
                    "completed_at": res_row[2],
                    "analysis": parsed_res
                }

        # In-flight processing?
        if current_asm_status == "PROCESSING":
            conn.close()
            return {
                "status": True,
                "is_processing": True,
                "message": "Analysis is currently processing for this assessment.",
                "assessment_id": clean_asm_id,
                "workflow_status": "PROCESSING"
            }

        # Check for disallowed advanced states
        if current_asm_status in ("REPORT_GENERATING", "REPORT_READY"):
            conn.close()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Assessment '{clean_asm_id}' has already reached stage '{current_asm_status}'."
            )

        # 4. Mandatory Both-Eyes Verification
        cursor.execute("""
        SELECT scan_id, eye_side, file_reference, status, attempt_number
        FROM eye_scans
        WHERE assessment_id = ? AND is_active = 1;
        """, (clean_asm_id,))
        scan_rows = cursor.fetchall()

        scans_by_eye = {}
        for row in scan_rows:
            scans_by_eye[row[1]] = {
                "scan_id": row[0],
                "eye_side": row[1],
                "file_reference": row[2],
                "status": row[3],
                "attempt_number": row[4]
            }

        left_scan = scans_by_eye.get("LEFT")
        right_scan = scans_by_eye.get("RIGHT")

        left_complete = (left_scan is not None and left_scan["status"] == "Completed")
        right_complete = (right_scan is not None and right_scan["status"] == "Completed")

        # Explicit Both-Eyes Gating: Both must be Completed
        if not left_complete or not right_complete:
            conn.close()
            left_status = left_scan["status"] if left_scan else "Missing"
            right_status = right_scan["status"] if right_scan else "Missing"
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Bilateral analysis requires both eyes to be completed. "
                    f"Current status: LEFT={left_status}, RIGHT={right_status}. "
                    f"Complete dual-eye scanning before requesting analysis."
                )
            )

        # 5. Transition Assessment State to PROCESSING
        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
        UPDATE assessments
        SET status = 'PROCESSING', updated_at = ?
        WHERE assessment_id = ?;
        """, (now_str, clean_asm_id))

        # 6. Initialize Processing Job Log
        processing_id = f"PRC-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        cursor.execute("""
        INSERT INTO processing_logs (
            processing_id, assessment_id, operation, status,
            started_at, model_version
        ) VALUES (?, ?, 'ANALYSIS_PROCESSING', 'STARTED', ?, 'iris-analysis-v1.0');
        """, (processing_id, clean_asm_id, now_str))

        _log_audit_action(
            cursor, username, user_role, "ANALYSIS_STARTED", clean_asm_id,
            "SUCCESS", {"processing_id": processing_id}
        )

        conn.commit()

        # 7. Execute Bilateral CV/ML Analysis Pipeline
        start_ts = time.time()

        # Resolve image file paths
        left_file_path = os.path.join(UPLOADS_DIR, left_scan["file_reference"])
        right_file_path = os.path.join(UPLOADS_DIR, right_scan["file_reference"])

        if not os.path.exists(left_file_path):
            raise FileNotFoundError(f"LEFT scan file reference '{left_scan['file_reference']}' not found on storage.")
        if not os.path.exists(right_file_path):
            raise FileNotFoundError(f"RIGHT scan file reference '{right_scan['file_reference']}' not found on storage.")

        left_img = cv2.imread(left_file_path)
        right_img = cv2.imread(right_file_path)

        if left_img is None or left_img.size == 0:
            raise ValueError("LEFT eye image bitmap could not be decoded.")
        if right_img is None or right_img.size == 0:
            raise ValueError("RIGHT eye image bitmap could not be decoded.")

        # --- LEFT Eye Processing ---
        _, left_pupil = detect_pupil(left_img)
        _, left_iris = segment_iris(left_img)
        left_quality = analyze_iris_quality(left_img, pupil=left_pupil, iris=left_iris)
        left_features = extract_features(left_pupil, left_iris, left_img) or {}
        left_color = analyze_color(left_img) or {}
        left_norm = normalize_iris(left_img, left_iris)
        left_lbp_stats = {}
        if left_norm is not None and left_norm.size > 0:
            lbp_left = calculate_lbp(left_norm)
            left_lbp_stats = {
                "lbp_mean": round(float(np.mean(lbp_left)), 2),
                "lbp_std": round(float(np.std(lbp_left)), 2)
            }

        # --- RIGHT Eye Processing ---
        _, right_pupil = detect_pupil(right_img)
        _, right_iris = segment_iris(right_img)
        right_quality = analyze_iris_quality(right_img, pupil=right_pupil, iris=right_iris)
        right_features = extract_features(right_pupil, right_iris, right_img) or {}
        right_color = analyze_color(right_img) or {}
        right_norm = normalize_iris(right_img, right_iris)
        right_lbp_stats = {}
        if right_norm is not None and right_norm.size > 0:
            lbp_right = calculate_lbp(right_norm)
            right_lbp_stats = {
                "lbp_mean": round(float(np.mean(lbp_right)), 2),
                "lbp_std": round(float(np.std(lbp_right)), 2)
            }

        # --- Bilateral Metrics & Symmetry Analysis ---
        pupil_radius_delta = None
        if "pupil_radius" in left_features and "pupil_radius" in right_features:
            pupil_radius_delta = round(abs(float(left_features["pupil_radius"]) - float(right_features["pupil_radius"])), 2)

        pupil_iris_ratio_delta = None
        if "pupil_iris_ratio" in left_features and "pupil_iris_ratio" in right_features:
            pupil_iris_ratio_delta = round(abs(float(left_features["pupil_iris_ratio"]) - float(right_features["pupil_iris_ratio"])), 4)

        avg_quality_score = round(
            (float(left_quality.get("capture_quality_score", 0.0)) + float(right_quality.get("capture_quality_score", 0.0))) / 2.0,
            2
        )

        color_match = (
            left_color.get("eye_color") == right_color.get("eye_color")
            if (left_color.get("eye_color") and right_color.get("eye_color"))
            else False
        )

        # Biometric geometric similarity between eyes using genuine cosine similarity
        vec_left = [
            float(left_features.get("pupil_iris_ratio", 0.0)),
            float(left_features.get("center_distance", 0.0)),
            float(left_features.get("mean_intensity", 0.0)) / 255.0,
            float(left_features.get("std_intensity", 0.0)) / 128.0,
            float(left_quality.get("capture_quality_score", 0.0)) / 100.0,
        ]
        vec_right = [
            float(right_features.get("pupil_iris_ratio", 0.0)),
            float(right_features.get("center_distance", 0.0)),
            float(right_features.get("mean_intensity", 0.0)) / 255.0,
            float(right_features.get("std_intensity", 0.0)) / 128.0,
            float(right_quality.get("capture_quality_score", 0.0)) / 100.0,
        ]
        bilateral_similarity = round(cosine_similarity(vec_left, vec_right), 4)

        end_ts = time.time()
        end_time_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        duration_ms = int((end_ts - start_ts) * 1000)

        # 8. Construct Structured Analysis Results with Explicit Provenance
        structured_results = {
            "assessment_id": clean_asm_id,
            "student_id": target_student_id,
            "processing_id": processing_id,
            "workflow_status": "ANALYSIS_COMPLETED",
            "model_metadata": {
                "service": "IRIS-Official-Analysis-Engine",
                "pipeline_version": "iris-analysis-v1.0",
                "model_name": "iris-geometry-cv",
                "opencv_version": cv2.__version__,
                "mode": "bilateral-dual-eye"
            },
            "provenance": {
                "pupil_iris_geometry": "iris-derived",
                "quality_metrics": "rule-based",
                "color_measurements": "iris-derived",
                "texture_descriptors": "ml-derived",
                "bilateral_symmetry": "iris-derived",
                "geometric_similarity": "ml-derived"
            },
            "timing": {
                "started_at": now_str,
                "completed_at": end_time_str,
                "duration_ms": duration_ms
            },
            "left_eye": {
                "scan_id": left_scan["scan_id"],
                "file_reference": left_scan["file_reference"],
                "pupil_circle": left_pupil,
                "iris_circle": left_iris,
                "quality": left_quality,
                "features": left_features,
                "color": left_color,
                "texture_descriptors": left_lbp_stats
            },
            "right_eye": {
                "scan_id": right_scan["scan_id"],
                "file_reference": right_scan["file_reference"],
                "pupil_circle": right_pupil,
                "iris_circle": right_iris,
                "quality": right_quality,
                "features": right_features,
                "color": right_color,
                "texture_descriptors": right_lbp_stats
            },
            "bilateral_analysis": {
                "pupil_radius_delta": pupil_radius_delta,
                "pupil_iris_ratio_delta": pupil_iris_ratio_delta,
                "average_quality_score": avg_quality_score,
                "color_match": color_match,
                "detected_left_color": left_color.get("eye_color"),
                "detected_right_color": right_color.get("eye_color"),
                "bilateral_geometric_similarity": bilateral_similarity
            }
        }

        # Sanitize for JSON storage (NumPy scalars -> Python natives)
        sanitized_results = _sanitize_for_json(structured_results)
        results_json_str = json.dumps(sanitized_results)

        # 9. Persist into analysis_results (Upsert on assessment_id)
        cursor.execute("""
        INSERT INTO analysis_results (
            assessment_id, results_json, model_version, created_at, updated_at
        ) VALUES (?, ?, 'iris-analysis-v1.0', ?, ?)
        ON CONFLICT(assessment_id) DO UPDATE SET
            results_json = excluded.results_json,
            model_version = excluded.model_version,
            updated_at = excluded.updated_at;
        """, (clean_asm_id, results_json_str, now_str, end_time_str))

        # 10. Transition Assessment Status to ANALYSIS_COMPLETED
        cursor.execute("""
        UPDATE assessments
        SET status = 'ANALYSIS_COMPLETED',
            completed_at = COALESCE(completed_at, ?),
            updated_at = ?
        WHERE assessment_id = ?;
        """, (end_time_str, end_time_str, clean_asm_id))

        # 11. Update processing_logs to COMPLETED
        cursor.execute("""
        UPDATE processing_logs
        SET status = 'COMPLETED',
            completed_at = ?,
            duration_ms = ?
        WHERE processing_id = ?;
        """, (end_time_str, duration_ms, processing_id))

        # 12. Record Audit Log for Completion
        _log_audit_action(
            cursor, username, user_role, "ANALYSIS_COMPLETED", clean_asm_id,
            "SUCCESS", {
                "processing_id": processing_id,
                "duration_ms": duration_ms,
                "avg_quality": avg_quality_score
            }
        )

        conn.commit()
        conn.close()

        return {
            "status": True,
            "message": "Analysis processing completed successfully.",
            "assessment_id": clean_asm_id,
            "processing_id": processing_id,
            "workflow_status": "ANALYSIS_COMPLETED",
            "duration_ms": duration_ms,
            "analysis": sanitized_results
        }

    except HTTPException:
        # Re-raise explicit HTTP exceptions as is
        conn.close()
        raise

    except Exception as exc:
        # Failure handling: transition assessment to FAILED and log safely
        fail_time_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        safe_msg = str(exc)

        try:
            cursor.execute("""
            UPDATE assessments
            SET status = 'FAILED', updated_at = ?
            WHERE assessment_id = ?;
            """, (fail_time_str, clean_asm_id))

            if 'processing_id' in locals():
                cursor.execute("""
                UPDATE processing_logs
                SET status = 'FAILED',
                    safe_error_code = 'PROCESSING_FAILURE',
                    safe_error_message = ?,
                    completed_at = ?
                WHERE processing_id = ?;
                """, (safe_msg, fail_time_str, processing_id))

            _log_audit_action(
                cursor, username, user_role, "ANALYSIS_FAILED", clean_asm_id,
                "FAILED", {"error": safe_msg}
            )
            conn.commit()
        except Exception:
            pass

        conn.close()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis processing failed: {safe_msg}"
        )


@router.get("/{assessmentId}/process/status", summary="Poll analysis processing and workflow status")
async def get_process_status(
    assessmentId: str,
    current_user: Dict[str, Any] = Depends(get_required_user)
):
    """
    GET /api/assessments/{assessmentId}/process/status

    Requirements:
    1. Authenticated user.
    2. RBAC check (Admin, owning Student, or assigned Counsellor).
    3. Returns assessment_id, workflow_status, processing_status, job/processing reference, and safe error details.
    """
    clean_asm_id = assessmentId.strip()

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT assessment_id, student_id, status, updated_at, completed_at
    FROM assessments
    WHERE assessment_id = ?;
    """, (clean_asm_id,))
    asm_row = cursor.fetchone()

    if not asm_row:
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment '{clean_asm_id}' not found."
        )

    target_student_id = asm_row[1]
    workflow_status = asm_row[2]
    updated_at = asm_row[3]
    completed_at = asm_row[4]

    # RBAC check
    verify_student_read_access(current_user, target_student_id)

    # Fetch latest processing log for this assessment
    cursor.execute("""
    SELECT processing_id, operation, status, safe_error_code, safe_error_message, duration_ms, started_at, completed_at
    FROM processing_logs
    WHERE assessment_id = ?
    ORDER BY id DESC
    LIMIT 1;
    """, (clean_asm_id,))
    log_row = cursor.fetchone()

    conn.close()

    if log_row:
        proc_id = log_row[0]
        proc_status = log_row[2]
        err_code = log_row[3]
        err_msg = log_row[4]
        duration_ms = log_row[5]
        started_at = log_row[6]
        proc_completed = log_row[7]
    else:
        proc_id = None
        proc_status = "NOT_STARTED"
        err_code = None
        err_msg = None
        duration_ms = None
        started_at = None
        proc_completed = None

    return {
        "status": True,
        "assessment_id": clean_asm_id,
        "workflow_status": workflow_status,
        "processing_status": proc_status,
        "processing_id": proc_id,
        "started_at": started_at,
        "completed_at": proc_completed or completed_at,
        "duration_ms": duration_ms,
        "safe_error_code": err_code,
        "safe_error_message": err_msg,
        "updated_at": updated_at
    }


@router.get("/{assessmentId}/analysis", summary="Retrieve persisted structured analysis results")
async def get_assessment_analysis(
    assessmentId: str,
    current_user: Dict[str, Any] = Depends(get_required_user)
):
    """
    GET /api/assessments/{assessmentId}/analysis

    Requirements:
    1. Authenticated user.
    2. RBAC check: Student ownership, assigned Counsellor, or Admin.
    3. Returns only persisted structured analysis results from analysis_results table.
    4. Never calculates fake results on the fly.
    """
    clean_asm_id = assessmentId.strip()
    username = current_user.get("username", "unknown")
    user_role = current_user.get("role", "unknown")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT assessment_id, student_id, status
    FROM assessments
    WHERE assessment_id = ?;
    """, (clean_asm_id,))
    asm_row = cursor.fetchone()

    if not asm_row:
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment '{clean_asm_id}' not found."
        )

    target_student_id = asm_row[1]
    workflow_status = asm_row[2]

    # Enforce RBAC
    verify_student_read_access(current_user, target_student_id)

    # Fetch persisted analysis results
    cursor.execute("""
    SELECT results_json, model_version, created_at, updated_at
    FROM analysis_results
    WHERE assessment_id = ?;
    """, (clean_asm_id,))
    res_row = cursor.fetchone()

    if not res_row:
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No analysis results found for assessment '{clean_asm_id}'. Current workflow status: '{workflow_status}'."
        )

    parsed_analysis = json.loads(res_row[0])
    model_version = res_row[1]
    created_at = res_row[2]
    updated_at = res_row[3]

    # Log audit event for retrieval
    _log_audit_action(
        cursor, username, user_role, "ANALYSIS_RETRIEVED", clean_asm_id,
        "SUCCESS", {"model_version": model_version}
    )
    conn.commit()
    conn.close()

    return {
        "status": True,
        "assessment_id": clean_asm_id,
        "workflow_status": workflow_status,
        "model_version": model_version,
        "created_at": created_at,
        "updated_at": updated_at,
        "analysis": parsed_analysis
    }
