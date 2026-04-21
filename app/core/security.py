import time
import logging
from collections import defaultdict
from fastapi import HTTPException, status

logger = logging.getLogger("tradeos.security")

_login_attempts: dict[str, list[float]] = defaultdict(list)
_RATE_WINDOW = 60  # seconds
_RATE_MAX = 5      # attempts per window


def check_rate_limit(ip: str) -> None:
    now = time.time()
    cutoff = now - _RATE_WINDOW
    _login_attempts[ip] = [t for t in _login_attempts[ip] if t > cutoff]
    if len(_login_attempts[ip]) >= _RATE_MAX:
        logger.warning("Rate limit exceeded for %s", ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please wait before retrying.",
            headers={"Retry-After": str(_RATE_WINDOW)},
        )
    _login_attempts[ip].append(now)
