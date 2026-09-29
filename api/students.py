"""
Official IRIS Student Management & Registration APIs (Phase 2).
Implements:
- POST /api/students: Create student & initialize assessment
- GET /api/students/{studentId}: Retrieve student profile & active assessment
- GET /api/students: Admin student directory list / search
- GET /api/students/{studentId}/assessments: Assessment history for student

Conforms strictly to IRIS_Backend_Detailed_Requirements.docx & IRIS_Frontend_Detailed_Requirements.docx.
"""

import os
import re
import uuid
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, Depends, Query, status
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from database_official import get_connection
from security.auth import (
    bearer_scheme,
    decode_access_token,
    require_admin,
    require_authenticated,
)

router = APIRouter(prefix="/api/students", tags=["Official Student Management"])


# =====================================================================
# SCHEMAS
# =====================================================================

class StudentRegisterRequest(BaseModel):
    student_id: str = Field(..., description="Unique alphanumeric student identifier", min_length=2, max_length=64)
    student_name: str = Field(..., description="Full student name", min_length=2, max_length=128)

    class Config:
        json_schema_extra = {
            "example": {
                "student_id": "STU-1001",
                "student_name": "Aarav Patel"
            }
        }


# =====================================================================
# AUTHORIZATION HELPERS
# =====================================================================

def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)
) -> Optional[Dict[str, Any]]:
    """Extracts user claims if a bearer token is present; otherwise returns None."""
    if not credentials or not credentials.credentials:
        return None
    try:
        payload = decode_access_token(credentials.credentials)
        username = payload.get("sub")
        role = payload.get("role")
        if username and role:
            return {"username": username, "role": role, "claims": payload}
    except Exception:
        pass
    return None


def get_required_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)
) -> Dict[str, Any]:
    """Strictly enforces authentication for protected endpoints."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided",
            headers={"WWW-Authenticate": "Bearer"}
        )
    payload = decode_access_token(credentials.credentials)
    username = payload.get("sub")
    role = payload.get("role")
    if not username or not role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload is missing essential claims",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return {"username": username, "role": role, "claims": payload}


def verify_student_read_access(current_user: Dict[str, Any], target_student_id: str):
    """
    RBAC & Object-Level Access Enforcement:
    - Admin: Permitted across all students.
    - Student: Permitted only for their own student_id.
    - Counsellor: Permitted ONLY if an active row exists in counsellor_assignments.
    """
    role = current_user.get("role")
    username = current_user.get("username", "")
    token_student_id = current_user.get("claims", {}).get("student_id") or username

    if role == "Admin":
        return True

    if role == "Student":
        if username.lower() == target_student_id.lower() or token_student_id.lower() == target_student_id.lower():
            return True
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT created_by FROM students WHERE student_id = ?;", (target_student_id,))
        row = cur.fetchone()
        conn.close()
        if row and row[0] and row[0].lower() == username.lower():
            return True
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access forbidden: User '{username}' with role '{role}' is not authorized to access records for student '{target_student_id}'"
        )

    if role in ("Counselor", "Counsellor"):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM counsellor_assignments
            WHERE student_id = ? AND counsellor_id = ? AND is_active = 1 AND status = 'ACTIVE';
        """, (target_student_id, username))
        assigned = cur.fetchone()[0] > 0
        conn.close()
        if assigned:
            return True
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access forbidden: Counsellor '{username}' is not assigned to student '{target_student_id}'"
        )

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")


# =====================================================================
# 1. STUDENT REGISTRATION
# =====================================================================

@router.post("", status_code=status.HTTP_201_CREATED)
def register_student(
    body: StudentRegisterRequest,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_current_user)
):
    """
    Official Student Registration API:
    - Minimum required fields: student_id, student_name.
    - Enforces uniqueness at database level (returns 409 Conflict if duplicate).
    - Prevents duplicate registration on retry/double-click.
    - Atomically creates the student entity and initial Assessment ID.
    - Stores created_by and created_at.
    """
    clean_id = body.student_id.strip()
    clean_name = body.student_name.strip()

    if not clean_id or not clean_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student ID and Student Name cannot be empty"
        )

    # Basic regex validation for clean identifiers
    if not re.fullmatch(r"^[A-Za-z0-9_-]+$", clean_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student ID must contain only alphanumeric characters, underscores, or hyphens"
        )

    # Determine actor identity
    if current_user:
        role = current_user.get("role")
        username = current_user.get("username", "")
        token_student_id = current_user.get("claims", {}).get("student_id") or username

        if role == "Student":
            # Student can only register themselves
            if clean_id.lower() != token_student_id.lower() and clean_id.lower() != username.lower():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Students are not authorized to register other student accounts"
                )
            created_by = username
        elif role in ("Counselor", "Counsellor"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Counsellors are not authorized to register new students"
            )
        else:
            created_by = username
    else:
        created_by = "self-registered"

    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # 1. Check for duplicate student_id
        cursor.execute("SELECT id, student_name, created_at FROM students WHERE student_id = ?;", (clean_id,))
        existing = cursor.fetchone()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Student ID '{clean_id}' is already registered in the system."
            )

        # 2. Insert into official students table
        cursor.execute("""
        INSERT INTO students (student_id, student_name, created_by, created_at, status)
        VALUES (?, ?, ?, ?, 'ACTIVE');
        """, (clean_id, clean_name, created_by, now_str))

        # 3. Non-destructive sync to student_profiles for legacy compatibility
        cursor.execute("""
        INSERT OR IGNORE INTO student_profiles (student_id, full_name, created_by, created_on)
        VALUES (?, ?, ?, ?);
        """, (clean_id, clean_name, created_by, now_str))

        # 4. Generate initial Assessment ID
        date_tag = datetime.utcnow().strftime("%Y%m%d")
        unique_suffix = uuid.uuid4().hex[:6].upper()
        assessment_id = f"ASM-{date_tag}-{unique_suffix}"

        cursor.execute("""
        INSERT INTO assessments (assessment_id, student_id, status, created_by, created_at)
        VALUES (?, ?, 'REGISTERED', ?, ?);
        """, (assessment_id, clean_id, created_by, now_str))

        # 5. Record initial audit log entry
        audit_id = f"AUD-{uuid.uuid4().hex[:8].upper()}"
        cursor.execute("""
        INSERT INTO audit_logs (audit_id, user_id, role, action, assessment_id, entity_type, entity_id, status, timestamp)
        VALUES (?, ?, ?, 'STUDENT_REGISTERED', ?, 'STUDENT', ?, 'SUCCESS', ?);
        """, (audit_id, created_by, current_user.get("role", "Public") if current_user else "Public", assessment_id, clean_id, now_str))

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
            detail=f"Registration conflict: Student ID '{clean_id}' already exists."
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
        "message": "Student registered successfully",
        "student": {
            "student_id": clean_id,
            "student_name": clean_name,
            "created_by": created_by,
            "created_at": now_str
        },
        "assessment": {
            "assessment_id": assessment_id,
            "status": "REGISTERED",
            "created_at": now_str
        }
    }


# =====================================================================
# 2. GET STUDENT BY ID
# =====================================================================

@router.get("/{student_id}")
def get_student_by_id(
    student_id: str,
    current_user: Dict[str, Any] = Depends(get_required_user)
):
    """
    Retrieves approved student profile information and current assessment status.
    Protected by RBAC (Admin, authorized Student, or assigned Counsellor).
    """
    clean_id = student_id.strip()
    verify_student_read_access(current_user, clean_id)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT student_id, student_name, created_by, created_at, status
    FROM students
    WHERE student_id = ?;
    """, (clean_id,))
    row = cursor.fetchone()

    if not row:
        # Fallback to student_profiles if created historically
        cursor.execute("""
        SELECT student_id, full_name, created_by, created_on
        FROM student_profiles
        WHERE student_id = ?;
        """, (clean_id,))
        legacy_row = cursor.fetchone()
        if not legacy_row:
            conn.close()
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Student '{clean_id}' not found")
        student_data = {
            "student_id": legacy_row[0],
            "student_name": legacy_row[1],
            "created_by": legacy_row[2] or "legacy",
            "created_at": legacy_row[3],
            "status": "ACTIVE"
        }
    else:
        student_data = {
            "student_id": row[0],
            "student_name": row[1],
            "created_by": row[2],
            "created_at": row[3],
            "status": row[4]
        }

    # Fetch latest assessment
    cursor.execute("""
    SELECT assessment_id, status, created_at, completed_at
    FROM assessments
    WHERE student_id = ?
    ORDER BY created_at DESC LIMIT 1;
    """, (clean_id,))
    asm_row = cursor.fetchone()

    conn.close()

    latest_assessment = None
    if asm_row:
        latest_assessment = {
            "assessment_id": asm_row[0],
            "status": asm_row[1],
            "created_at": asm_row[2],
            "completed_at": asm_row[3]
        }

    return {
        "status": True,
        "student": student_data,
        "latest_assessment": latest_assessment
    }


# =====================================================================
# 3. GET STUDENTS DIRECTORY (ADMIN ONLY)
# =====================================================================

@router.get("", dependencies=[Depends(require_admin)])
def list_students(
    search: Optional[str] = Query(None, description="Search by name or ID"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    """
    Admin Student Directory Listing with search, pagination, and latest assessment state.
    """
    conn = get_connection()
    cursor = conn.cursor()

    query = """
    SELECT 
        s.student_id,
        s.student_name,
        s.created_by,
        s.created_at,
        s.status,
        a.assessment_id,
        a.status as assessment_status
    FROM students s
    LEFT JOIN assessments a ON a.id = (
        SELECT id FROM assessments WHERE student_id = s.student_id ORDER BY created_at DESC LIMIT 1
    )
    """
    params = []
    if search:
        query += " WHERE s.student_id LIKE ? OR s.student_name LIKE ?"
        params.extend([f"%{search.strip()}%", f"%{search.strip()}%"])

    query += " ORDER BY s.created_at DESC LIMIT ? OFFSET ?;"
    params.extend([limit, offset])

    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) FROM students;")
    total_count = cursor.fetchone()[0]
    conn.close()

    students_list = []
    for r in rows:
        students_list.append({
            "student_id": r[0],
            "student_name": r[1],
            "created_by": r[2],
            "created_at": r[3],
            "status": r[4],
            "latest_assessment_id": r[5],
            "assessment_status": r[6] or "UNASSESSED"
        })

    return {
        "status": True,
        "total": total_count,
        "limit": limit,
        "offset": offset,
        "students": students_list
    }


# =====================================================================
# 4. GET STUDENT ASSESSMENTS HISTORY
# =====================================================================

@router.get("/{student_id}/assessments")
def get_student_assessments_history(
    student_id: str,
    current_user: Dict[str, Any] = Depends(get_required_user)
):
    """
    Returns chronological history of all assessment runs for a specific student.
    Protected by RBAC.
    """
    clean_id = student_id.strip()
    verify_student_read_access(current_user, clean_id)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT assessment_id, student_id, status, created_by, created_at, completed_at
    FROM assessments
    WHERE student_id = ?
    ORDER BY created_at DESC;
    """, (clean_id,))
    rows = cursor.fetchall()
    conn.close()

    history = []
    for r in rows:
        history.append({
            "assessment_id": r[0],
            "student_id": r[1],
            "status": r[2],
            "created_by": r[3],
            "created_at": r[4],
            "completed_at": r[5]
        })

    return {
        "status": True,
        "student_id": clean_id,
        "total_assessments": len(history),
        "assessments": history
    }
