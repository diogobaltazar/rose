"""Shared dependencies for API routers."""

import os
import time

import httpx
import redis
from jose import jwt as jose_jwt, JWTError

from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")

AUTH0_DOMAIN = os.environ.get("AUTH0_DOMAIN", "")
AUTH0_CLIENT_ID = os.environ.get("AUTH0_CLIENT_ID", "")
AUTH0_AUDIENCE = os.environ.get("AUTH0_AUDIENCE", "")

_jwks_cache: dict | None = None
_jwks_cache_time: float = 0.0
_JWKS_TTL = 3600

_security = HTTPBearer(auto_error=False)


def get_redis() -> redis.Redis:
    return redis.from_url(REDIS_URL, decode_responses=True)


def get_storage(auth: dict | None) -> "DriveClient":
    from storage import get_storage as _get
    return _get(auth)


async def _get_jwks() -> dict:
    global _jwks_cache, _jwks_cache_time
    now = time.time()
    if _jwks_cache and (now - _jwks_cache_time) < _JWKS_TTL:
        return _jwks_cache
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"https://{AUTH0_DOMAIN}/.well-known/jwks.json")
        r.raise_for_status()
        _jwks_cache = r.json()
        _jwks_cache_time = now
        return _jwks_cache


async def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Security(_security),
) -> dict | None:
    if not AUTH0_DOMAIN:
        return None
    if not credentials:
        raise HTTPException(status_code=401, detail="Authorization required")
    token = credentials.credentials
    try:
        header = jose_jwt.get_unverified_header(token)
        jwks = await _get_jwks()
        key = next((k for k in jwks.get("keys", []) if k.get("kid") == header.get("kid")), None)
        if not key:
            raise HTTPException(status_code=401, detail="Unknown signing key")
        options = {}
        if not AUTH0_AUDIENCE:
            options["verify_aud"] = False
        payload = jose_jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=AUTH0_AUDIENCE or None,
            issuer=f"https://{AUTH0_DOMAIN}/",
            options=options or None,
        )
        return payload
    except JWTError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}") from exc
