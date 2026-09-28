"""
Authentication API Router.
Exposes endpoints for user login, token issuance, user registration, and self-profile queries.
"""

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

from security.auth import (
    authenticate_user,
    create_access_token,
    create_user,
    get_user_by_username,
    get_current_user,
    require_admin,
    JWT_EXPIRE_MINUTES
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, description="Username")
    password: str = Field(..., min_length=1, description="Password")


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Alphanumeric username")
    password: str = Field(..., min_length=8, description="Strong password (min 8 chars)")
    role: str = Field("Student", description="User role: Student, Counselor, or Admin")
    full_name: Optional[str] = ""
    email: Optional[str] = ""


@router.post("/login")
def login(req: LoginRequest):
    """
    Authenticates a user and returns a signed JWT access token.
    """
    user = authenticate_user(req.username, req.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = create_access_token(
        subject=user["username"],
        role=user["role"],
        extra_claims={
            "full_name": user.get("full_name", ""),
            "email": user.get("email", "")
        }
    )

    return {
        "status": True,
        "access_token": token,
        "token_type": "bearer",
        "username": user["username"],
        "role": user["role"],
        "full_name": user.get("full_name", ""),
        "expires_in": JWT_EXPIRE_MINUTES * 60
    }


@router.post("/register")
def register(
    req: RegisterRequest,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    """
    Registers a new user.
    Note: Admin account creation requires Admin privileges.
    Students and Counselors can be provisioned by authenticated staff.
    """
    if req.role == "Admin":
        if not current_user or current_user.get("role") != "Admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only existing Administrators can provision new Admin accounts"
            )

    try:
        new_user = create_user(
            username=req.username,
            password=req.password,
            role=req.role,
            full_name=req.full_name or "",
            email=req.email or ""
        )
        return {
            "status": True,
            "message": f"User {req.username} registered successfully",
            "user": {
                "username": new_user["username"],
                "role": new_user["role"],
                "full_name": new_user["full_name"],
                "email": new_user["email"]
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/me")
def get_me(current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Returns the currently authenticated user identity and role.
    """
    return {
        "status": True,
        "username": current_user["username"],
        "role": current_user["role"]
    }
