"""
Path and Identifier Security Validation Module.
Prevents directory traversal, illegal path component injection, and null-byte injection.
"""

import os
import re
from fastapi import HTTPException

# Whitelist: alphanumeric characters, underscores, and hyphens
SAFE_IDENTIFIER_REGEX = re.compile(r"^[a-zA-Z0-9_\-]+$")


def validate_identifier(code: str, field_name: str = "identifier") -> str:
    """
    Validates that an identifier (e.g. employee_code, student_id, report_id)
    contains only safe alphanumeric, underscore, or hyphen characters.
    Rejects directory traversal sequences, slashes, backslashes, and null bytes.
    """
    if not code or not isinstance(code, str):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {field_name}: must be a non-empty string"
        )

    # Check for null bytes
    if "\x00" in code:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {field_name}: null bytes are strictly forbidden"
        )

    # Check for traversal patterns or slashes
    if "/" in code or "\\" in code or ".." in code:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {field_name}: path traversal sequences are strictly forbidden"
        )

    if not SAFE_IDENTIFIER_REGEX.match(code):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {field_name}: only alphanumeric characters, underscores, and hyphens are permitted"
        )

    return code


def safe_path_join(base_directory: str, untrusted_filename: str) -> str:
    """
    Safely joins a base directory with an untrusted filename, ensuring that
    the resolved absolute path remains strictly contained within the base directory.
    """
    if not untrusted_filename or not isinstance(untrusted_filename, str):
        raise HTTPException(status_code=400, detail="Filename cannot be empty")

    if "\x00" in untrusted_filename:
        raise HTTPException(status_code=400, detail="Null bytes are forbidden in paths")

    # Extract only the basename to strip any directory path prefixes
    clean_name = os.path.basename(untrusted_filename)
    if not clean_name or clean_name in (".", ".."):
        raise HTTPException(status_code=400, detail="Invalid filename")

    base_abs = os.path.abspath(base_directory)
    target_abs = os.path.abspath(os.path.join(base_abs, clean_name))

    # Strict containment check
    if not target_abs.startswith(base_abs + os.sep) and target_abs != base_abs:
        raise HTTPException(
            status_code=403,
            detail="Access forbidden: path traversal detected"
        )

    return target_abs
