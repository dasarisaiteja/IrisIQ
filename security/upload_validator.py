"""
Centralized File Upload and Image Validation Security Module.
Enforces file size limits, magic-byte inspection, PIL image integrity verification,
and safe filename extraction to defend against DoS, polyglot files, and malformed payloads.
"""

import io
import os
from typing import Tuple
from fastapi import UploadFile, HTTPException
from PIL import Image

# 10 Megabytes maximum payload limit
MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024

# Allowed image extensions
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp"}

# Magic byte signatures
MAGIC_SIGNATURES = {
    "jpeg": (b"\xff\xd8\xff",),
    "png": (b"\x89PNG\r\n\x1a\n",),
    "bmp": (b"BM",),
}


def _verify_magic_bytes(header: bytes) -> str:
    """Verifies file header matches known image magic bytes."""
    if header.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if header.startswith(b"BM"):
        return "bmp"
    return ""


async def validate_uploaded_image(
    file: UploadFile,
    max_size: int = MAX_UPLOAD_SIZE_BYTES
) -> Tuple[bytes, str]:
    """
    Validates an uploaded image file:
    1. Ensures safe filename and allowed extension.
    2. Enforces maximum byte size.
    3. Verifies magic bytes match image standards (JPEG, PNG, BMP).
    4. Performs PIL integrity verification to reject truncated/malformed images.
    5. Resets file buffer pointer and returns (contents, safe_filename).
    """
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    # 1. Safe filename extraction
    raw_filename = file.filename
    if "\x00" in raw_filename or "/" in raw_filename or "\\" in raw_filename or ".." in raw_filename:
        # Reject traversal in filename
        raise HTTPException(
            status_code=400,
            detail="Filename contains invalid characters or path traversal components"
        )

    safe_filename = os.path.basename(raw_filename)
    _, ext = os.path.splitext(safe_filename.lower())
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file extension '{ext}'. Allowed extensions: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    # 2. Read bytes with size cap
    contents = await file.read()
    if not contents or len(contents) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    if len(contents) > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum allowed size of {max_size // (1024 * 1024)}MB"
        )

    # 3. Magic-byte inspection
    detected_format = _verify_magic_bytes(contents[:16])
    if not detected_format:
        raise HTTPException(
            status_code=400,
            detail="Invalid file format: file header does not match valid image magic bytes"
        )

    # Cross-check extension with detected format
    if detected_format == "jpeg" and ext not in (".jpg", ".jpeg"):
        raise HTTPException(status_code=400, detail="Mismatched file extension and image format")
    if detected_format == "png" and ext != ".png":
        raise HTTPException(status_code=400, detail="Mismatched file extension and image format")
    if detected_format == "bmp" and ext != ".bmp":
        raise HTTPException(status_code=400, detail="Mismatched file extension and image format")

    # 4. PIL Integrity verification
    try:
        with Image.open(io.BytesIO(contents)) as img:
            img.verify()
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Corrupted or invalid image stream: {str(e)}"
        )

    # Reset file pointer for any subsequent reads
    await file.seek(0)
    return contents, safe_filename
