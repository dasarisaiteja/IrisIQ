"""
Login Rate Limiting & Brute-Force Defense Module.
Provides reverse-proxy-aware client IP extraction and threshold-based failed login lockout.
"""

import os
import time
import threading
from typing import Dict, List, Optional
from fastapi import Request, HTTPException, status

_lock = threading.Lock()
_failed_attempts: Dict[str, List[float]] = {}
_lockouts: Dict[str, float] = {}


def get_client_ip(request: Request) -> str:
    """
    Extracts the true client IP address, supporting reverse proxies
    via RFC 7239 Forwarded, X-Forwarded-For, and X-Real-IP headers.
    """
    # 1. Standard Forwarded header (RFC 7239)
    forwarded = request.headers.get("forwarded")
    if forwarded:
        for part in forwarded.split(";"):
            part_str = part.strip()
            if part_str.lower().startswith("for="):
                val = part_str[4:].strip('"[]')
                if val:
                    return val

    # 2. X-Forwarded-For (de-facto proxy standard: client, proxy1, proxy2)
    xff = request.headers.get("x-forwarded-for")
    if xff:
        client_ip = xff.split(",")[0].strip()
        if client_ip:
            return client_ip

    # 3. X-Real-IP (common in Nginx setups)
    x_real_ip = request.headers.get("x-real-ip")
    if x_real_ip:
        return x_real_ip.strip()

    # 4. Direct socket connection fallback
    if request.client and request.client.host:
        return request.client.host

    return "127.0.0.1"


def get_rate_limit_config():
    """
    Retrieves rate limit settings from environment with secure defaults.
    """
    enabled = os.environ.get("RATE_LIMIT_ENABLED", "true").lower() not in ("false", "0", "no")
    max_failures = int(os.environ.get("LOGIN_RATE_LIMIT_MAX_FAILURES", "5"))
    window_seconds = int(os.environ.get("LOGIN_RATE_LIMIT_WINDOW", "60"))
    lockout_seconds = int(os.environ.get("LOGIN_RATE_LIMIT_LOCKOUT", "60"))
    return enabled, max_failures, window_seconds, lockout_seconds


def check_login_rate_limit(request: Request):
    """
    Checks if the requesting client IP is currently locked out due to excessive failed attempts.
    Raises HTTPException(429) if locked out.
    """
    enabled, max_failures, window_seconds, lockout_seconds = get_rate_limit_config()
    if not enabled:
        return

    client_ip = get_client_ip(request)
    now = time.time()

    with _lock:
        # Check active lockout
        lockout_until = _lockouts.get(client_ip, 0)
        if now < lockout_until:
            remaining = int(lockout_until - now) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many failed login attempts. Please try again in {remaining} seconds.",
                headers={"Retry-After": str(max(1, remaining))}
            )
        elif client_ip in _lockouts:
            # Lockout expired; clear it
            del _lockouts[client_ip]


def record_login_failure(request: Request):
    """
    Records a failed authentication attempt for the client IP.
    Enforces lockout if failure threshold is reached within the time window.
    """
    enabled, max_failures, window_seconds, lockout_seconds = get_rate_limit_config()
    if not enabled:
        return

    client_ip = get_client_ip(request)
    now = time.time()

    with _lock:
        attempts = _failed_attempts.get(client_ip, [])
        # Prune attempts outside the sliding window
        attempts = [t for t in attempts if (now - t) <= window_seconds]
        attempts.append(now)
        _failed_attempts[client_ip] = attempts

        if len(attempts) >= max_failures:
            _lockouts[client_ip] = now + lockout_seconds


def record_login_success(request: Request):
    """
    Clears failed attempts upon successful authentication.
    """
    enabled, _, _, _ = get_rate_limit_config()
    if not enabled:
        return

    client_ip = get_client_ip(request)
    with _lock:
        if client_ip in _failed_attempts:
            del _failed_attempts[client_ip]
        if client_ip in _lockouts:
            del _lockouts[client_ip]


def reset_rate_limiter():
    """
    Resets all in-memory rate limiting state (useful for tests).
    """
    with _lock:
        _failed_attempts.clear()
        _lockouts.clear()
