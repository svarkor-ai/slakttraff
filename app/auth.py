"""Site-password authentication for Släktträff 2026.

A single shared site password (env SITE_PASSWORD, default "sibbamala") gates
every API call. Successful verification returns an opaque session token kept
in-memory server-side; the frontend sends it as a Bearer token. Wrong-password
attempts are rate-limited per IP with a sliding-window counter that cannot be
parallelized away.
"""
import hmac
import os
import secrets
import threading
import time
from typing import Dict, List

from fastapi import Header, HTTPException, status

# Default is the owner-approved site password; override with SITE_PASSWORD.
SITE_PASSWORD = os.environ.get("SITE_PASSWORD", "sibbamala")
# Admin password: owner-approved default; override with ADMIN_PASSWORD.
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "grisfest")
FAILED_ATTEMPTS_ALLOWED = 5
FAILED_ATTEMPT_WINDOW_SECONDS = 60.0

# token -> expiry (monotonic time). Sessions last 12 hours.
_TOKEN_TTL_SECONDS = 12 * 3600
_tokens: Dict[str, float] = {}
_admin_tokens: Dict[str, float] = {}
_failed_attempts: Dict[str, List[float]] = {}
_lock = threading.Lock()


def _throttle_ip(ip: str) -> bool:
    """Count a failed attempt; return True when the IP is over the limit.

    The counter is advanced atomically under the lock, so N parallel requests
    all count against the same window — the limit cannot be bypassed by
    opening more connections.
    """
    now = time.monotonic()
    with _lock:
        window_start = now - FAILED_ATTEMPT_WINDOW_SECONDS
        recent = [t for t in _failed_attempts.get(ip, []) if t > window_start]
        recent.append(now)
        _failed_attempts[ip] = recent
        return len(recent) > FAILED_ATTEMPTS_ALLOWED


def verify_password(candidate: str, ip: str = "-") -> tuple[bool, bool]:
    """Constant-time password check; rate-limits the IP on failure.

    Returns (password_ok, throttled). throttled is True when this failure
    tripped the per-IP limit (the caller answers 429 instead of 403).
    """
    # compare_digest only accepts ASCII str; encode both sides so any bytes
    # the client sends are compared safely instead of raising TypeError.
    ok = hmac.compare_digest(
        candidate.encode("utf-8"), SITE_PASSWORD.encode("utf-8")
    )
    if ok:
        return True, False
    return False, _throttle_ip(ip)


def issue_token() -> str:
    """Create a new opaque session token."""
    token = secrets.token_hex(32)
    with _lock:
        _tokens[token] = time.monotonic() + _TOKEN_TTL_SECONDS
        # Opportunistic cleanup of expired tokens.
        expired = [t for t, exp in _tokens.items() if exp <= time.monotonic()]
        for t in expired:
            del _tokens[t]
    return token


def is_valid_token(token: str) -> bool:
    with _lock:
        expiry = _tokens.get(token)
    return expiry is not None and expiry > time.monotonic()


def verify_admin_password(candidate: str, ip: str = "-") -> bool:
    """Constant-time admin password check; rate-limits the IP on failure."""
    ok = hmac.compare_digest(
        candidate.encode("utf-8"), ADMIN_PASSWORD.encode("utf-8")
    )
    if ok:
        return True
    _throttle_ip(ip)
    return False


def issue_admin_token() -> str:
    """Create a new admin session token (separate store from site tokens)."""
    token = secrets.token_hex(32)
    with _lock:
        _admin_tokens[token] = time.monotonic() + _TOKEN_TTL_SECONDS
    return token


def is_valid_admin_token(token: str) -> bool:
    with _lock:
        expiry = _admin_tokens.get(token)
    return expiry is not None and expiry > time.monotonic()


def require_token(authorization: str = Header(default="")) -> None:
    """FastAPI dependency: 401 unless a valid site OR admin Bearer token is
    presented (an admin token can do everything a site token can)."""
    if authorization.startswith("Bearer "):
        token = authorization[len("Bearer "):]
        if is_valid_token(token) or is_valid_admin_token(token):
            return
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing session token",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_admin_token(authorization: str = Header(default="")) -> None:
    """FastAPI dependency for admin-only endpoints.

    401 without a valid admin Bearer token.
    """
    if authorization.startswith("Bearer "):
        token = authorization[len("Bearer "):]
        if is_valid_admin_token(token):
            return
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing admin token",
        headers={"WWW-Authenticate": "Bearer"},
    )
