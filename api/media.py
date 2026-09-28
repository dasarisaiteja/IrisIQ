"""
Protected Media Retrieval API Router.
Replaces insecure static directory mounting with authenticated, role-verified,
and traversal-resistant media streaming.
"""

import os
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import FileResponse

from security.auth import get_current_user
from security.path_validator import validate_identifier

router = APIRouter(prefix="/api/media", tags=["Protected Media"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MEDIA_DIRECTORIES = {
    "uploads": os.path.join(BASE_DIR, "uploads"),
    "outputs": os.path.join(BASE_DIR, "outputs"),
    "photos": os.path.join(BASE_DIR, "static", "photos"),
}


@router.get("/{category}/{filename:path}")
def get_protected_media(
    category: str,
    filename: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Securely serves media files (biometric scans, output masks, student photos)
    to authenticated users with role verification and strict path-containment defense.
    """
    if category not in MEDIA_DIRECTORIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid media category. Allowed: {list(MEDIA_DIRECTORIES.keys())}"
        )

    # Path traversal detection
    if not filename or "\x00" in filename or ".." in filename or filename.startswith("/") or "\\" in filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path traversal sequences or null bytes are strictly forbidden"
        )

    base_dir = MEDIA_DIRECTORIES[category]
    base_abs = os.path.abspath(base_dir)
    target_abs = os.path.abspath(os.path.join(base_abs, filename))

    # Containment check
    if not target_abs.startswith(base_abs + os.sep) and target_abs != base_abs:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: path traversal detected"
        )

    # Role-Based Permissions Check (enforced before existence check to prevent file enumeration)
    user_role = current_user.get("role")
    username = current_user.get("username")

    if user_role not in ("Admin", "Counselor"):
        # Students may only access photos or reports specifically tied to their user ID
        if category == "photos" and username and username in filename:
            pass
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Students are not authorized to view raw biometric media"
            )

    if not os.path.exists(target_abs) or not os.path.isfile(target_abs):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media file not found"
        )

    return FileResponse(target_abs)
