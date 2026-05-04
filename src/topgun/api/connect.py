"""
Connections — Google Drive backend OAuth + per-user service credentials.

Storage backend: Google Drive. User authenticates via Google OAuth2.
Refresh token stored encrypted in Redis: user:gdrive:{sub} → hex.

Service credentials (GitHub tokens, CalDAV): also stored encrypted in Redis,
keyed by creds:{sub}:{connection_name}.

encryption_key = HMAC(BACKEND_SECRET, auth0_sub)
"""

import json
import os
import secrets
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

import httpx

from deps import require_auth, get_redis, get_storage
from gdrive import encrypt_token, decrypt_token, get_auth_url, exchange_code

router = APIRouter(prefix="/connect", tags=["connect"])

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5100")
GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")
GITHUB_REDIRECT_URI = os.environ.get(
    "GITHUB_REDIRECT_URI", "http://localhost:5101/connect/github/callback"
)


# ── Redis key helpers ─────────────────────────────────────────────────────────

def _gdrive_key(sub: str) -> str:
    return f"user:gdrive:{sub}"

def _cred_key(sub: str, name: str) -> str:
    return f"creds:{sub}:{name}"

def _state_key(state: str) -> str:
    return f"oauth:state:{state}"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _store_token(sub: str, name: str, token: str) -> None:
    r = get_redis()
    encrypted = encrypt_token(token, sub)
    r.set(_cred_key(sub, name), encrypted)


def _get_token(sub: str, name: str) -> str | None:
    r = get_redis()
    encrypted = r.get(_cred_key(sub, name))
    if not encrypted:
        return None
    return decrypt_token(encrypted, sub)


# ── GitHub OAuth ──────────────────────────────────────────────────────────────

# ── Google Drive backend OAuth ────────────────────────────────────────────────

@router.get("/backend/init")
async def connect_backend_init(
    request: Request,
    client_id: str = Query(..., description="GCP OAuth2 client ID"),
    client_secret: str = Query(..., description="GCP OAuth2 client secret"),
    auth: dict | None = Depends(require_auth),
) -> dict[str, str]:
    """Return Google OAuth2 URL. Redirect URI derived from the incoming request."""
    if not auth:
        raise HTTPException(status_code=401, detail="Authentication required")
    redirect_uri = str(request.base_url).rstrip("/") + "/connect/backend/callback"
    state = secrets.token_urlsafe(32)
    auth_url, code_verifier = get_auth_url(state, client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri)
    r = get_redis()
    r.setex(_state_key(state), 600, json.dumps({
        "sub": auth["sub"],
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier,
    }))
    return {"auth_url": auth_url}


@router.get("/backend/callback")
async def connect_backend_callback(
    code: str = Query(...),
    state: str = Query(...),
) -> RedirectResponse:
    """Google OAuth2 callback — exchange code, store encrypted token in Redis."""
    r = get_redis()
    raw = r.get(_state_key(state))
    if not raw:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")
    r.delete(_state_key(state))
    payload = json.loads(raw)
    sub = payload["sub"]
    client_id = payload["client_id"]
    client_secret = payload["client_secret"]
    redirect_uri = payload["redirect_uri"]
    code_verifier = payload.get("code_verifier")
    token_data = exchange_code(code, client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri, code_verifier=code_verifier)
    r.set(_gdrive_key(sub), encrypt_token(json.dumps(token_data), sub))
    return RedirectResponse(url=f"{FRONTEND_URL}/deck/connections?connected=gdrive")


# ── Service credentials ───────────────────────────────────────────────────────

class ServiceTokenBody(BaseModel):
    name: str
    provider: str
    token: str


@router.post("/service")
async def store_service_token(
    body: ServiceTokenBody,
    auth: dict | None = Depends(require_auth),
) -> dict[str, str]:
    """Store an encrypted service token (called by CLI after OAuth)."""
    if not auth:
        raise HTTPException(status_code=401, detail="Authentication required")
    sub = auth["sub"]
    _store_token(sub, body.name, body.token)
    return {"status": "stored", "name": body.name}


@router.get("/github/init")
async def github_oauth_init(
    name: str = Query(..., description="Connection name"),
    auth: dict | None = Depends(require_auth),
) -> dict[str, str]:
    """Return GitHub OAuth URL for the given connection name."""
    if not GITHUB_CLIENT_ID:
        raise HTTPException(status_code=503, detail="GitHub OAuth not configured")
    if not auth:
        raise HTTPException(status_code=401, detail="Authentication required")

    state = secrets.token_urlsafe(32)
    r = get_redis()
    r.setex(_state_key(state), 600, json.dumps({"sub": auth["sub"], "name": name}))

    params = {
        "client_id": GITHUB_CLIENT_ID,
        "redirect_uri": GITHUB_REDIRECT_URI,
        "scope": "repo",
        "state": state,
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return {"auth_url": f"https://github.com/login/oauth/authorize?{query}"}


@router.get("/github/callback")
async def github_oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
) -> RedirectResponse:
    """GitHub OAuth callback — exchange code for token, store encrypted."""
    r = get_redis()
    raw = r.get(_state_key(state))
    if not raw:
        raise HTTPException(status_code=400, detail="Invalid or expired state")
    r.delete(_state_key(state))
    payload = json.loads(raw)
    sub, name = payload["sub"], payload["name"]

    try:
        resp = httpx.post(
            "https://github.com/login/oauth/access_token",
            data={"client_id": GITHUB_CLIENT_ID, "client_secret": GITHUB_CLIENT_SECRET, "code": code},
            headers={"Accept": "application/json"},
            timeout=10,
        )
        resp.raise_for_status()
        token = resp.json().get("access_token", "")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"GitHub token exchange failed: {e}")

    _store_token(sub, name, token)
    return RedirectResponse(url=f"{FRONTEND_URL}/deck/connections?connected={name}")


# ── List / remove ─────────────────────────────────────────────────────────────

@router.get("")
async def list_connections(
    auth: dict | None = Depends(require_auth),
) -> dict[str, Any]:
    """List declared connections with auth status."""
    if not auth:
        raise HTTPException(status_code=401, detail="Authentication required")
    sub = auth["sub"]
    r = get_redis()
    backend_connected = bool(r.get(_gdrive_key(sub)))

    services = []
    if backend_connected:
        try:
            config = get_storage(auth).read_json("config.json")
            for name, conn in config.get("connections", {}).items():
                services.append({
                    "name": name,
                    "provider": conn.get("provider", ""),
                    "account": conn.get("account", ""),
                    "authenticated": bool(_get_token(sub, name)),
                })
        except Exception:
            pass

    return {
        "backend": {"provider": "gdrive", "connected": backend_connected},
        "services": services,
    }


@router.delete("/{name}", status_code=204)
async def remove_connection(
    name: str,
    auth: dict | None = Depends(require_auth),
) -> None:
    """Remove a service connection (or 'backend' to disconnect Google Drive)."""
    if not auth:
        raise HTTPException(status_code=401, detail="Authentication required")
    sub = auth["sub"]
    r = get_redis()
    if name == "backend":
        r.delete(_gdrive_key(sub))
        return
    r.delete(_cred_key(sub, name))
    try:
        storage = get_storage(auth)
        config = storage.read_json("config.json")
        connections = config.get("connections", {})
        if name in connections:
            del connections[name]
            config["connections"] = connections
            storage.write_json("config.json", config)
    except Exception:
        pass
