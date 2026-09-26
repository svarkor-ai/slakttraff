"""Site-password authentication for Släktträff 2026.

A single shared site password (env SITE_PASSWORD, default "sibbamala") gates
every API call. Successful verification returns an opaque session token kept
in-memory server-side; the frontend sends it as a Bearer token. Wrong-password
attempts get a small per-IP delay to blunt brute force.
"""
import hmac
import os
import secrets
import threading
import time
from typing import Dict

from fastapi import Header, HTTPException, status

# Default is the owner-approved site password; override with SITE_PASSWORD.
SITE_PASSWORD = os.environ.get("SITE_PASSWORD", "sibbamala")
WRONG_PASSWORD_DELAY_SECONDS = 0.5

# token -> expiry (monotonic time). Sessions last 12 hours.
_TOKEN_TTL_SECONDS = 12 * 3600
_tokens: Dict[str, float] = {}
_last_failed_attempt: Dict[str, float] = {}
_lock = threading.Lock()


def _throttle_ip(ip: str) -> None:
    """Sleep briefly if this IP recently failed a password attempt."""
    with _lock:
        last = _last_failed_attempt.get(ip, 0.0)
    elapsed = time.monotonic() - last
    if elapsed < WRONG_PASSWORD_DELAY_SECONDS:
        time.sleep(WRONG_PASSWORD_DELAY_SECONDS - elapsed)


def _record_failed_attempt(ip: str) -> None:
    with _lock:
        _last_failed_attempt[ip] = time.monotonic()


def verify_password(candidate: str, ip: str = "-") -> bool:
    """Constant-time password check; throttles the IP on failure."""
    ok = hmac.compare_digest(candidate, SITE_PASSWORD)
    if ok:
        return True
    _throttle_ip(ip)
    _record_failed_attempt(ip)
    return False


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


def require_token(authorization: str = Header(default="")) -> None:
    """FastAPI dependency: 401 unless a valid Bearer token is presented."""
    if authorization.startswith("Bearer "):
        token = authorization[len("Bearer "):]
        if is_valid_token(token):
            return
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing session token",
        headers={"WWW-Authenticate": "Bearer"},
    )
