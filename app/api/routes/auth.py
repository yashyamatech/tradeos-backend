from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.auth.kotak_neo import kotak_auth

router = APIRouter()


class AuthStatusResponse(BaseModel):
    authenticated: bool
    auth_date: str | None


@router.get("/status", response_model=AuthStatusResponse)
async def auth_status():
    return AuthStatusResponse(
        authenticated=kotak_auth.is_authenticated,
        auth_date=str(kotak_auth._auth_date) if kotak_auth.is_authenticated else None,
    )


@router.post("/login")
async def trigger_login():
    """Manually trigger Kotak Neo v2 authentication."""
    try:
        await kotak_auth.get_client()
        return {
            "message": "Authentication successful",
            "auth_date": str(kotak_auth._auth_date),
        }
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/logout")
async def logout():
    await kotak_auth.close()
    return {"message": "Logged out"}
