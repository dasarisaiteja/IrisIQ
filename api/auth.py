"""
Authentication API Router.
Exposes endpoints for user login, token issuance, user registration, and self-profile queries.
"""

import time
from fastapi import APIRouter, HTTPException, Depends, status, Request
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

from security.auth import (
    authenticate_user,
    create_access_token,
    create_user,
    get_user_by_username,
    get_current_user,
    require_admin,
    bearer_scheme,
    decode_access_token,
    revoke_token,
    JWT_EXPIRE_MINUTES
)
from security.rate_limiter import (
    check_login_rate_limit,
    record_login_failure,
    record_login_success
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
def login(req: LoginRequest, request: Request):
    """
    Authenticates a user and returns a signed JWT access token.
    Enforces reverse-proxy-aware brute-force rate limiting.
    """
    check_login_rate_limit(request)

    user = authenticate_user(req.username, req.password)
    if not user:
        record_login_failure(request)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"}
        )

    record_login_success(request)

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


@router.post("/logout")
def logout(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)
):
    """
    Logs out the current user session and revokes the JWT access token server-side.
    """
    if credentials and credentials.credentials:
        token = credentials.credentials
        try:
            payload = decode_access_token(token)
            exp = payload.get("exp", int(time.time()) + 3600)
            revoke_token(token, exp)
        except HTTPException:
            # Token was already invalid, expired, or revoked
            pass

    return {
        "status": True,
        "message": "Logged out successfully"
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
