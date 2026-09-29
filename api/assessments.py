"""
Official IRIS Assessment Lifecycle & State Machine APIs (Phase 2).
Implements:
- POST /api/assessments: Create assessment linked to student with duplicate protection
- GET /api/assessments/{assessmentId}: Get assessment details & metadata
- GET /api/assessments/{assessmentId}/status: Get assessment workflow state & scan flags

Conforms strictly to IRIS_Backend_Detailed_Requirements.docx & IRIS_Frontend_Detailed_Requirements.docx.
"""

import os
import re
import uuid
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field

from database_official import (
    get_connection,
    OFFICIAL_ASSESSMENT_STATES,
)
from security.auth import (
    require_admin,
    require_authenticated,
)
from api.students import get_required_user, verify_student_read_access

router = APIRouter(prefix="/api/assessments", tags=["Official Assessment Lifecycle"])


# =====================================================================
# SCHEMAS
# =====================================================================

class AssessmentCreateRequest(BaseModel):
    student_id: str = Field(..., description="Target student identifier", min_length=2, max_length=64)

    class Config:
        json_schema_extra = {
            "example": {
                "student_id": "STU-1001"
            }
        }


# =====================================================================
# 1. CREATE ASSESSMENT
# =====================================================================

@router.post("", status_code=status.HTTP_201_CREATED)
def create_assessment(
    body: AssessmentCreateRequest,
    current_user: Dict[str, Any] = Depends(get_required_user)
):
    """
    Creates a new assessment record for an approved student.
    - Accepts student_id
    - Verifies student exists in database
    - Generates unique assessment_id
    - Initializes status as REGISTERED
    - Prevents accidental duplicates from rapid double-clicks
    - Restricts role access: Admin can create for any student; Student only for themselves
    """
    clean_id = body.student_id.strip()
    role = current_user.get("role")
    username = current_user.get("username", "")
    token_student_id = current_user.get("claims", {}).get("student_id") or username

    if role == "Student":
        if clean_id.lower() != token_student_id.lower() and clean_id.lower() != username.lower():
            conn_check = get_connection()
            cur_check = conn_check.cursor()
            cur_check.execute("SELECT created_by FROM students WHERE student_id = ?;", (clean_id,))
            created_row = cur_check.fetchone()
            conn_check.close()
            if not (created_row and created_row[0] and created_row[0].lower() == username.lower()):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Students are permitted to create assessments only for their own account"
                )
    elif role in ("Counselor", "Counsellor"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Counsellors are not authorized to create new assessments"
        )

    conn = get_connection()
    cursor = conn.cursor()

    # 1. Verify student exists in students (or student_profiles)
    cursor.execute("SELECT student_id, student_name FROM students WHERE student_id = ?;", (clean_id,))
    stu_row = cursor.fetchone()
    if not stu_row:
        cursor.execute("SELECT student_id, full_name FROM student_profiles WHERE student_id = ?;", (clean_id,))
        stu_row = cursor.fetchone()
        if not stu_row:
            conn.close()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cannot create assessment: Student '{clean_id}' does not exist"
            )

    # 2. Check for duplicate pending assessment (prevents rapid double-click duplication)
    cursor.execute("""
    SELECT assessment_id, status, created_at
    FROM assessments
    WHERE student_id = ? AND status IN ('REGISTERED', 'SCAN_PENDING')
    ORDER BY created_at DESC LIMIT 1;
    """, (clean_id,))
    recent_unstarted = cursor.fetchone()

    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    # If student has an untouched assessment created recently (< 10 minutes), reuse it safely
    if recent_unstarted:
        conn.close()
        return {
            "status": True,
            "message": "Existing active assessment returned (duplicate creation prevented)",
            "assessment": {
                "assessment_id": recent_unstarted[0],
                "student_id": clean_id,
                "status": recent_unstarted[1],
                "created_at": recent_unstarted[2],
                "is_reused": True
            }
        }

    # 3. Generate unique assessment ID
    date_tag = datetime.utcnow().strftime("%Y%m%d")
    unique_suffix = uuid.uuid4().hex[:6].upper()
    assessment_id = f"ASM-{date_tag}-{unique_suffix}"

    try:
        cursor.execute("""
        INSERT INTO assessments (assessment_id, student_id, status, created_by, created_at)
        VALUES (?, ?, 'REGISTERED', ?, ?);
        """, (assessment_id, clean_id, username, now_str))

        # Audit log
        audit_id = f"AUD-{uuid.uuid4().hex[:8].upper()}"
        cursor.execute("""
        INSERT INTO audit_logs (audit_id, user_id, role, action, assessment_id, entity_type, entity_id, status, timestamp)
        VALUES (?, ?, ?, 'ASSESSMENT_CREATED', ?, 'ASSESSMENT', ?, 'SUCCESS', ?);
        """, (audit_id, username, role, assessment_id, assessment_id, now_str))

        conn.commit()
    except HTTPException:
        raise
    except sqlite3.IntegrityError:
        try:
            conn.rollback()
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Assessment creation conflict: ID '{assessment_id}' already exists"
        )
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal database error: {str(e)}"
        )
    finally:
        try:
            conn.close()
        except Exception:
            pass

    return {
        "status": True,
        "message": "Assessment created successfully",
        "assessment": {
            "assessment_id": assessment_id,
            "student_id": clean_id,
            "status": "REGISTERED",
            "created_at": now_str,
            "created_by": username,
            "is_reused": False
        }
    }


# =====================================================================
# 2. GET ASSESSMENT DETAILS
# =====================================================================

@router.get("/{assessment_id}")
def get_assessment_by_id(
    assessment_id: str,
    current_user: Dict[str, Any] = Depends(get_required_user)
):
    """
    Returns full assessment metadata, associated student record, and scan statuses.
    Protected by RBAC (Admin, authorized Student, or assigned Counsellor).
    """
    clean_asm_id = assessment_id.strip()
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT a.assessment_id, a.student_id, a.status, a.created_by, a.created_at, a.completed_at,
           s.student_name
    FROM assessments a
    LEFT JOIN students s ON s.student_id = a.student_id
    WHERE a.assessment_id = ?;
    """, (clean_asm_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment '{clean_asm_id}' not found"
        )

    target_student_id = row[1]
    # Enforce access authorization
    verify_student_read_access(current_user, target_student_id)

    # Check scans for this assessment
    cursor.execute("""
    SELECT eye_side, status, file_reference, created_at, completed_at
    FROM eye_scans
    WHERE assessment_id = ? AND is_active = 1;
    """, (clean_asm_id,))
    scans_rows = cursor.fetchall()
    conn.close()

    scans_dict = {"LEFT": None, "RIGHT": None}
    for s in scans_rows:
        scans_dict[s[0]] = {
            "status": s[1],
            "file_reference": s[2],
            "created_at": s[3],
            "completed_at": s[4]
        }

    return {
        "status": True,
        "assessment": {
            "assessment_id": row[0],
            "student_id": row[1],
            "student_name": row[6] or "Unknown",
            "status": row[2],
            "created_by": row[3],
            "created_at": row[4],
            "completed_at": row[5],
            "scans": scans_dict
        }
    }


# =====================================================================
# 3. GET ASSESSMENT STATUS
# =====================================================================

@router.get("/{assessment_id}/status")
def get_assessment_status(
    assessment_id: str,
    current_user: Dict[str, Any] = Depends(get_required_user)
):
    """
    Returns concise workflow state machine status and dual eye scan flags for UI polling.
    Protected by RBAC.
    """
    clean_asm_id = assessment_id.strip()
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT assessment_id, student_id, status, created_at, completed_at
    FROM assessments
    WHERE assessment_id = ?;
    """, (clean_asm_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment '{clean_asm_id}' not found"
        )

    verify_student_read_access(current_user, row[1])

    # Fetch eye scans status
    cursor.execute("""
    SELECT eye_side, status FROM eye_scans WHERE assessment_id = ? AND is_active = 1;
    """, (clean_asm_id,))
    scans = dict(cursor.fetchall())
    conn.close()

    left_status = scans.get("LEFT", "Pending")
    right_status = scans.get("RIGHT", "Pending")
    both_completed = (left_status == "Completed" and right_status == "Completed")

    return {
        "status": True,
        "assessment_id": row[0],
        "student_id": row[1],
        "workflow_status": row[2],
        "scans": {
            "left": left_status,
            "right": right_status,
            "both_completed": both_completed
        },
        "created_at": row[3],
        "completed_at": row[4]
    }
