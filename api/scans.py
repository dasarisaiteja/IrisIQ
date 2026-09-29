"""
Official IRIS Dual-Eye Scanning & Upload APIs (Phase 3).
Implements:
- POST /api/assessments/{assessmentId}/scan/left: Upload and process LEFT eye scan
- POST /api/assessments/{assessmentId}/scan/right: Upload and process RIGHT eye scan
- GET /api/assessments/{assessmentId}/scan/status: Polling endpoint for dual-eye scan states
- GET /api/assessments/{assessmentId}/scan/{eye}: Retrieve active scan details for specified eye
- POST /api/assessments/{assessmentId}/scan/{eye}/retry: Safely retry/rescan a failed or replacement eye scan

Conforms strictly to IRIS_Backend_Detailed_Requirements.docx & IRIS_Frontend_Detailed_Requirements.docx.
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
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, status

from database_official import get_connection, OFFICIAL_ASSESSMENT_STATES, OFFICIAL_EYE_SIDES
from security.upload_validator import validate_uploaded_image
from api.students import get_required_user, verify_student_read_access

# Existing ML and CV Utilities (Reused without modification)
from utils.pupil_detection import detect_pupil
from utils.iris_segmentation import segment_iris
from utils.iris_quality_analyzer import analyze_iris_quality
from utils.feature_extractor import extract_features

router = APIRouter(prefix="/api/assessments", tags=["Official Dual-Eye Scanning"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCANS_DIR = os.path.join(BASE_DIR, "uploads", "scans")
os.makedirs(SCANS_DIR, exist_ok=True)


def _sanitize_for_json(obj):
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


def _validate_eye_parameter(eye: str) -> str:
    """Strictly validates eye parameter to be explicitly LEFT or RIGHT."""
    normalized = eye.strip().upper()
    if normalized not in ("LEFT", "RIGHT"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid eye side '{eye}'. Eye must be explicitly 'LEFT' or 'RIGHT'."
        )
    return normalized


async def _execute_scan_pipeline(
    assessment_id: str,
    eye_side: str,
    file: UploadFile,
    current_user: Dict[str, Any],
    is_retry: bool = False
) -> Dict[str, Any]:
    """
    Core validation and processing pipeline for an eye scan:
    1. Validates assessment existence and state.
    2. Validates user RBAC permissions for the student.
    3. Enforces single active scan per eye side per assessment (prevents duplicate active records).
    4. Validates uploaded image format, size, magic bytes, and integrity.
    5. Saves to secure filesystem abstraction (no raw path exposed).
    6. Executes existing CV pipeline (pupil detection, iris segmentation, quality metrics).
    7. Updates eye_scans, assessments state machine, processing_logs, and audit_logs.
    """
    clean_asm_id = assessment_id.strip()
    eye_norm = _validate_eye_parameter(eye_side)
    username = current_user.get("username", "unknown")
    user_role = current_user.get("role", "unknown")

    conn = get_connection()
    cursor = conn.cursor()

    # 1. Fetch assessment details
    cursor.execute("""
    SELECT assessment_id, student_id, status, created_by
    FROM assessments
    WHERE assessment_id = ?;
    """, (clean_asm_id,))
    asm_row = cursor.fetchone()

    if not asm_row:
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment '{clean_asm_id}' not found"
        )

    target_student_id = asm_row[1]
    current_asm_status = asm_row[2]

    # 2. RBAC check (Admin, owning student, or assigned counsellor)
    verify_student_read_access(current_user, target_student_id)

    # 3. Assessment state machine verification
    if current_asm_status == "SCAN_COMPLETED" and not is_retry:
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Assessment '{clean_asm_id}' has already completed dual-eye scanning. Use the retry endpoint if rescan is required."
        )

    if current_asm_status in ("PROCESSING", "ANALYSIS_COMPLETED", "REPORT_GENERATING", "REPORT_READY"):
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Assessment '{clean_asm_id}' is in advanced state '{current_asm_status}' and cannot accept scan uploads."
        )

    # 4. Check for active scan on this eye side
    cursor.execute("""
    SELECT id, scan_id, status, attempt_number
    FROM eye_scans
    WHERE assessment_id = ? AND eye_side = ? AND is_active = 1;
    """, (clean_asm_id, eye_norm))
    existing_active = cursor.fetchone()

    if existing_active and existing_active[2] == "Completed" and not is_retry:
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An active completed scan already exists for {eye_norm} eye on assessment '{clean_asm_id}'. Use the retry endpoint to submit a replacement scan."
        )

    # 5. Validate file upload using security validator
    contents, safe_filename = await validate_uploaded_image(file)

    # 6. Save image to secure path abstraction
    date_tag = datetime.utcnow().strftime("%Y%m%d")
    scan_uuid = uuid.uuid4().hex[:8].upper()
    scan_id = f"SCN-{date_tag}-{eye_norm}-{scan_uuid}"
    
    _, ext = os.path.splitext(safe_filename.lower())
    if ext not in (".jpg", ".jpeg", ".png", ".bmp"):
        ext = ".jpg"
    
    stored_filename = f"{clean_asm_id}_{eye_norm.lower()}_{scan_uuid}{ext}"
    stored_path = os.path.join(SCANS_DIR, stored_filename)
    file_reference = f"scans/{stored_filename}"

    with open(stored_path, "wb") as f:
        f.write(contents)

    start_time_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    start_ts = time.time()

    # Determine attempt number and deactivate prior active scan if retrying
    if existing_active:
        attempt_number = (existing_active[3] or 1) + 1
        cursor.execute("UPDATE eye_scans SET is_active = 0 WHERE id = ?;", (existing_active[0],))
    else:
        attempt_number = 1

    # 7. Run Existing CV/ML Validation Pipeline
    pipeline_status = "SUCCESS"
    error_code = None
    error_message = None
    quality_score = 0.0
    scan_status = "Pending"
    result_ref = None

    try:
        # Decode image using OpenCV
        img_bgr = cv2.imdecode(np.frombuffer(contents, np.uint8), cv2.IMREAD_COLOR)
        if img_bgr is None or img_bgr.size == 0:
            scan_status = "Failed"
            error_code = "DECODE_ERROR"
            error_message = "Uploaded image could not be decoded as a valid bitmap."
        else:
            # Pupil detection
            _, pupil_circle = detect_pupil(img_bgr)

            # Iris segmentation
            _, iris_circle = segment_iris(img_bgr)

            # Iris quality analysis
            quality_info = analyze_iris_quality(img_bgr, pupil=pupil_circle, iris=iris_circle)
            quality_score = float(quality_info.get("capture_quality_score", 0.0))

            # Feature extraction
            features = extract_features(pupil_circle, iris_circle, img_bgr)

            # Assess validity: require real detected iris and sufficient quality threshold
            is_valid_iris = (
                iris_circle is not None and 
                quality_score >= 40.0 and 
                quality_info.get("image_quality") not in ("Poor", "Unusable")
            )

            if not is_valid_iris:
                scan_status = "Failed"
                error_code = "POOR_QUALITY"
                error_message = f"Insufficient image quality (score: {quality_score:.1f}%) or iris boundaries not detected."
            else:
                scan_status = "Completed"
                result_ref = json.dumps(_sanitize_for_json({
                    "quality_score": quality_score,
                    "blur_score": quality_info.get("blur_score", 0.0),
                    "brightness": quality_info.get("brightness", 0.0),
                    "contrast": quality_info.get("contrast", 0.0),
                    "pupil": pupil_circle,
                    "iris": iris_circle,
                    "features": features
                }))
    except Exception as e:
        scan_status = "Failed"
        error_code = "PROCESSING_EXCEPTION"
        error_message = f"Error during iris validation: {str(e)}"

    end_ts = time.time()
    end_time_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    duration_ms = int((end_ts - start_ts) * 1000)

    # 8. Record new eye scan in eye_scans table
    cursor.execute("""
    INSERT INTO eye_scans (
        scan_id, assessment_id, eye_side, file_reference, status,
        result_reference, error_code, error_message, attempt_number,
        is_active, created_at, completed_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?);
    """, (
        scan_id, clean_asm_id, eye_norm, file_reference, scan_status,
        result_ref, error_code, error_message, attempt_number,
        start_time_str, end_time_str if scan_status == "Completed" else None
    ))

    # 9. Recompute and Update Assessment State Machine
    cursor.execute("""
    SELECT eye_side, status FROM eye_scans WHERE assessment_id = ? AND is_active = 1;
    """, (clean_asm_id,))
    active_scans = dict(cursor.fetchall())

    left_completed = (active_scans.get("LEFT") == "Completed")
    right_completed = (active_scans.get("RIGHT") == "Completed")

    if left_completed and right_completed:
        new_asm_status = "SCAN_COMPLETED"
    elif left_completed:
        new_asm_status = "LEFT_SCAN_COMPLETED"
    elif right_completed:
        new_asm_status = "RIGHT_SCAN_COMPLETED"
    else:
        new_asm_status = "SCAN_PENDING"

    cursor.execute("""
    UPDATE assessments SET status = ? WHERE assessment_id = ?;
    """, (new_asm_status, clean_asm_id))

    # 10. Write Processing Log
    proc_id = f"PRC-{uuid.uuid4().hex[:8].upper()}"
    cursor.execute("""
    INSERT INTO processing_logs (
        processing_id, assessment_id, operation, status,
        safe_error_code, safe_error_message, started_at, completed_at,
        duration_ms, model_version
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'iris-cv-v1.0');
    """, (
        proc_id, clean_asm_id, f"IRIS_SCAN_{eye_norm}", scan_status,
        error_code, error_message, start_time_str, end_time_str, duration_ms
    ))

    # 11. Write Audit Log
    audit_id = f"AUD-{uuid.uuid4().hex[:8].upper()}"
    action_type = f"SCAN_{eye_norm}_RETRY" if is_retry else f"SCAN_{eye_norm}_SUBMISSION"
    cursor.execute("""
    INSERT INTO audit_logs (
        audit_id, user_id, role, action, assessment_id,
        entity_type, entity_id, status, timestamp
    ) VALUES (?, ?, ?, ?, ?, 'EYE_SCAN', ?, ?, ?);
    """, (
        audit_id, username, user_role, action_type, clean_asm_id,
        scan_id, "SUCCESS" if scan_status == "Completed" else "FAILED", start_time_str
    ))

    conn.commit()
    conn.close()

    is_success = (scan_status == "Completed")
    return {
        "status": is_success,
        "message": f"{eye_norm} eye scan processed successfully" if is_success else f"{eye_norm} eye scan failed: {error_message}",
        "scan": {
            "scan_id": scan_id,
            "assessment_id": clean_asm_id,
            "eye_side": eye_norm,
            "status": scan_status,
            "attempt_number": attempt_number,
            "quality_score": quality_score if is_success else 0.0,
            "error_message": error_message,
            "created_at": start_time_str,
            "completed_at": end_time_str if is_success else None
        },
        "assessment": {
            "assessment_id": clean_asm_id,
            "workflow_status": new_asm_status,
            "both_completed": (left_completed and right_completed)
        }
    }


# =====================================================================
# 1. SCAN SUBMISSION APIS
# =====================================================================

@router.post("/{assessment_id}/scan/left", status_code=status.HTTP_200_OK)
async def upload_left_eye_scan(
    assessment_id: str,
    file: UploadFile = File(...),
    current_user: Dict[str, Any] = Depends(get_required_user)
):
    """
    Official LEFT Eye Scan Upload & Verification Endpoint.
    Validates payload, executes iris CV pipeline, updates assessment state.
    """
    return await _execute_scan_pipeline(
        assessment_id=assessment_id,
        eye_side="LEFT",
        file=file,
        current_user=current_user,
        is_retry=False
    )


@router.post("/{assessment_id}/scan/right", status_code=status.HTTP_200_OK)
async def upload_right_eye_scan(
    assessment_id: str,
    file: UploadFile = File(...),
    current_user: Dict[str, Any] = Depends(get_required_user)
):
    """
    Official RIGHT Eye Scan Upload & Verification Endpoint.
    Validates payload, executes iris CV pipeline, updates assessment state.
    """
    return await _execute_scan_pipeline(
        assessment_id=assessment_id,
        eye_side="RIGHT",
        file=file,
        current_user=current_user,
        is_retry=False
    )


@router.post("/{assessment_id}/scan/{eye}", status_code=status.HTTP_200_OK)
async def upload_eye_scan_generic(
    assessment_id: str,
    eye: str,
    file: UploadFile = File(...),
    current_user: Dict[str, Any] = Depends(get_required_user)
):
    """
    Eye scan upload endpoint validating {eye} parameter (LEFT or RIGHT).
    Rejects any non-standard eye identifier with HTTP 400 Bad Request.
    """
    eye_norm = _validate_eye_parameter(eye)
    return await _execute_scan_pipeline(
        assessment_id=assessment_id,
        eye_side=eye_norm,
        file=file,
        current_user=current_user,
        is_retry=False
    )


# =====================================================================
# 2. SCAN STATUS & DETAIL RETRIEVAL APIS
# =====================================================================

@router.get("/{assessment_id}/scan/status", status_code=status.HTTP_200_OK)
def get_dual_scan_status(
    assessment_id: str,
    current_user: Dict[str, Any] = Depends(get_required_user)
):
    """
    Retrieves comprehensive workflow state and scan statuses for both eyes.
    Provides data required for UI progress bars, status badges, and transition gating.
    """
    clean_asm_id = assessment_id.strip()
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT a.assessment_id, a.student_id, a.status, s.student_name
    FROM assessments a
    LEFT JOIN students s ON s.student_id = a.student_id
    WHERE a.assessment_id = ?;
    """, (clean_asm_id,))
    asm_row = cursor.fetchone()

    if not asm_row:
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment '{clean_asm_id}' not found"
        )

    verify_student_read_access(current_user, asm_row[1])

    cursor.execute("""
    SELECT scan_id, eye_side, status, result_reference, error_message, attempt_number, created_at, completed_at
    FROM eye_scans
    WHERE assessment_id = ? AND is_active = 1;
    """, (clean_asm_id,))
    scan_rows = cursor.fetchall()
    conn.close()

    scans_map = {"LEFT": None, "RIGHT": None}
    for r in scan_rows:
        eye = r[1]
        quality = 0.0
        if r[3]:
            try:
                parsed = json.loads(r[3])
                quality = parsed.get("quality_score", 0.0)
            except Exception:
                pass

        scans_map[eye] = {
            "scan_id": r[0],
            "status": r[2],
            "quality_score": quality,
            "error_message": r[4],
            "attempt_number": r[5],
            "created_at": r[6],
            "completed_at": r[7]
        }

    left_info = scans_map["LEFT"] or {"status": "Pending", "quality_score": 0.0, "attempt_number": 0}
    right_info = scans_map["RIGHT"] or {"status": "Pending", "quality_score": 0.0, "attempt_number": 0}
    both_completed = (left_info["status"] == "Completed" and right_info["status"] == "Completed")

    return {
        "status": True,
        "assessment_id": clean_asm_id,
        "student_id": asm_row[1],
        "student_name": asm_row[3] or "Unknown",
        "workflow_status": asm_row[2],
        "both_completed": both_completed,
        "scans": {
            "left": left_info,
            "right": right_info,
            "both_completed": both_completed
        }
    }


@router.get("/{assessment_id}/scan/{eye}", status_code=status.HTTP_200_OK)
def get_single_eye_scan(
    assessment_id: str,
    eye: str,
    current_user: Dict[str, Any] = Depends(get_required_user)
):
    """
    Retrieves active scan metadata for a specific eye (LEFT or RIGHT).
    Strictly validates eye parameter and hides sensitive filesystem paths.
    """
    clean_asm_id = assessment_id.strip()
    eye_norm = _validate_eye_parameter(eye)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT assessment_id, student_id, status FROM assessments WHERE assessment_id = ?;", (clean_asm_id,))
    asm_row = cursor.fetchone()
    if not asm_row:
        conn.close()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Assessment '{clean_asm_id}' not found")

    verify_student_read_access(current_user, asm_row[1])

    cursor.execute("""
    SELECT scan_id, assessment_id, eye_side, file_reference, status, result_reference, error_message, attempt_number, created_at, completed_at
    FROM eye_scans
    WHERE assessment_id = ? AND eye_side = ? AND is_active = 1;
    """, (clean_asm_id, eye_norm))
    scan_row = cursor.fetchone()
    conn.close()

    if not scan_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active scan record found for {eye_norm} eye on assessment '{clean_asm_id}'"
        )

    quality_score = 0.0
    if scan_row[5]:
        try:
            parsed = json.loads(scan_row[5])
            quality_score = parsed.get("quality_score", 0.0)
        except Exception:
            pass

    return {
        "status": True,
        "scan": {
            "scan_id": scan_row[0],
            "assessment_id": scan_row[1],
            "eye_side": scan_row[2],
            "file_reference": scan_row[3],  # Safe reference, NOT local filesystem path
            "status": scan_row[4],
            "quality_score": quality_score,
            "error_message": scan_row[6],
            "attempt_number": scan_row[7],
            "created_at": scan_row[8],
            "completed_at": scan_row[9]
        }
    }


# =====================================================================
# 3. SCAN RETRY API
# =====================================================================

@router.post("/{assessment_id}/scan/{eye}/retry", status_code=status.HTTP_200_OK)
async def retry_eye_scan(
    assessment_id: str,
    eye: str,
    file: UploadFile = File(...),
    current_user: Dict[str, Any] = Depends(get_required_user)
):
    """
    Safely retries an eye scan for a specific eye (LEFT or RIGHT).
    Deactivates prior active scan (preserves audit history), increments attempt number,
    and updates assessment state machine accordingly.
    """
    eye_norm = _validate_eye_parameter(eye)
    return await _execute_scan_pipeline(
        assessment_id=assessment_id,
        eye_side=eye_norm,
        file=file,
        current_user=current_user,
        is_retry=True
    )
