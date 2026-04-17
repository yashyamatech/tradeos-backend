from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.auth.kotak_neo import kotak_auth

router = APIRouter()


class AuthStatusResponse(BaseModel):
    authenticated: bool
    auth_date: str | None


@router.get("/status", response_model=AuthStatusResponse)
async def auth_status():
    """Returns current Kotak Neo session status."""
    is_auth = kotak_auth._auth_date is not None
    return AuthStatusResponse(
        authenticated=is_auth,
        auth_date=str(kotak_auth._auth_date) if is_auth else None,
    )


@router.post("/login")
async def trigger_login():
    """Manually trigger Kotak Neo authentication (useful for dev/test)."""
    try:
        await kotak_auth.get_client()
        return {"message": "Authentication successful", "auth_date": str(kotak_auth._auth_date)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
