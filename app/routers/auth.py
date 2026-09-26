"""Password-gate endpoints: exchange a password for a session token."""
from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.auth import (
    issue_admin_token,
    issue_token,
    verify_admin_password,
    verify_password,
)

router = APIRouter(prefix="/api", tags=["auth"])


class AuthRequest(BaseModel):
    password: str = Field(..., min_length=1, max_length=200)


@router.post("/auth")
def authenticate(payload: AuthRequest, request: Request):
    client_ip = request.client.host if request.client else "-"
    ok, throttled = verify_password(payload.password, client_ip)
    if ok:
        return {"token": issue_token()}
    if throttled:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": "För många försök — vänta en minut och försök igen."},
        )
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"detail": "Fel lösenord"},
    )


@router.post("/admin/auth")
def admin_authenticate(payload: AuthRequest, request: Request):
    """Exchange the admin password for an admin session token.

    """
    from app.auth import ADMIN_PASSWORD

    client_ip = request.client.host if request.client else "-"
    if not verify_admin_password(payload.password, client_ip):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "Fel lösenord"},
        )
    return {"token": issue_admin_token()}
