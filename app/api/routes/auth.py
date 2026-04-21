import logging
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.core.auth.kotak_neo import kotak_auth
from app.core.security import check_rate_limit

logger = logging.getLogger("tradeos.auth")
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
async def trigger_login(request: Request):
    ip = request.client.host if request.client else "unknown"
    check_rate_limit(ip)
    try:
        await kotak_auth.get_session()
        logger.info("Kotak auth success from %s", ip)
        return {"message": "Authentication successful", "auth_date": str(kotak_auth._auth_date)}
    except RuntimeError as e:
        logger.error("Kotak auth failed from %s: %s", ip, e)
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error("Kotak auth error from %s: %s", ip, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/logout")
async def logout(request: Request):
    ip = request.client.host if request.client else "unknown"
    logger.info("Kotak logout from %s", ip)
    await kotak_auth.close()
    return {"message": "Logged out"}
