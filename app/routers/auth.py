"""Password-gate endpoint: exchange the site password for a session token."""
from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.auth import issue_token, verify_password

router = APIRouter(prefix="/api", tags=["auth"])


class AuthRequest(BaseModel):
    password: str = Field(..., min_length=1, max_length=200)


@router.post("/auth")
def authenticate(payload: AuthRequest, request: Request):
    client_ip = request.client.host if request.client else "-"
    if not verify_password(payload.password, client_ip):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "Fel lösenord"},
        )
    return {"token": issue_token()}
