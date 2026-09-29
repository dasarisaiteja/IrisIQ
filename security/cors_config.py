"""
CORS Configuration Security Module.
Provides environment-driven CORS allowlist management, enforcing strict origin checks
and preventing dangerous wildcard credentials configurations.
"""

import os
import json
from typing import List, Tuple

DEFAULT_DEV_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


def get_cors_configuration() -> Tuple[List[str], bool]:
    """
    Computes (allowed_origins, allow_credentials) based on environment variables:
    - CORS_ALLOWED_ORIGINS: Comma-separated list or JSON array of allowed origins.
    - ENVIRONMENT / ENV: "production", "staging", or "development".

    Rules:
    1. If CORS_ALLOWED_ORIGINS is provided, parses and validates each origin.
    2. If ENVIRONMENT is "production", requires explicit origins; no fallback to localhost.
    3. In "development" mode (default when unspecified), permits localhost origins.
    4. If "*" is present in origins, credentials MUST be set to False (W3C standard).
    """
    raw_origins = os.environ.get("CORS_ALLOWED_ORIGINS", "").strip()
    environment = os.environ.get("ENVIRONMENT", os.environ.get("ENV", "development")).lower().strip()

    allowed_origins: List[str] = []

    if raw_origins:
        # Check if JSON array
        if raw_origins.startswith("[") and raw_origins.endswith("]"):
            try:
                parsed = json.loads(raw_origins)
                if isinstance(parsed, list):
                    allowed_origins = [str(o).strip() for o in parsed if str(o).strip()]
            except json.JSONDecodeError:
                pass
        
        if not allowed_origins:
            # Fallback to comma-separated
            allowed_origins = [o.strip() for o in raw_origins.split(",") if o.strip()]

    elif environment == "production":
        # Production with no configured origins: fail-safe to empty list (reject cross-origin)
        allowed_origins = []
    else:
        # Development mode default
        allowed_origins = list(DEFAULT_DEV_ORIGINS)

    # In production mode, strictly prohibit wildcard '*' origins
    if environment == "production":
        allowed_origins = [o for o in allowed_origins if o != "*"]

    # Enforce W3C Credential Safety Rule
    if "*" in allowed_origins:
        allow_credentials = False
    else:
        allow_credentials = True

    return allowed_origins, allow_credentials
