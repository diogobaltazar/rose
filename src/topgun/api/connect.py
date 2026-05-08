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
import re
import secrets
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
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

def _llm_key(sub: str) -> str:
    return f"user:llm:{sub}"

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


# ── GitHub stats helpers ──────────────────────────────────────────────────────

def _gh_count(pat: str, url: str) -> int | None:
    try:
        resp = httpx.get(url, headers={"Authorization": f"Bearer {pat}", "Accept": "application/vnd.github+json"}, params={"state": "open", "per_page": 1}, timeout=8)
        if not resp.is_success:
            return None
        link = resp.headers.get("link", "")
        m = re.search(r'page=(\d+)>; rel="last"', link)
        return int(m.group(1)) if m else len(resp.json())
    except Exception:
        return None


def _gh_stats(pat: str, repo: str) -> dict:
    base = f"https://api.github.com/repos/{repo}"
    return {"open_issues": _gh_count(pat, f"{base}/issues"), "open_prs": _gh_count(pat, f"{base}/pulls")}


# ── LLM provider ─────────────────────────────────────────────────────────────

class LlmConfigBody(BaseModel):
    api_key: str
    base_url: str = ""
    proxy_header: str = ""
    proxy_value: str = ""


@router.get("/llm")
async def get_llm_config(auth: dict | None = Depends(require_auth)) -> dict:
    if not auth:
        raise HTTPException(status_code=401, detail="Authentication required")
    encrypted = get_redis().get(_llm_key(auth["sub"]))
    if not encrypted:
        raise HTTPException(status_code=404, detail="No LLM config found")
    return json.loads(decrypt_token(encrypted, auth["sub"]))


@router.post("/llm/verify")
async def verify_llm(body: LlmConfigBody, auth: dict | None = Depends(require_auth)) -> dict[str, str]:
    """Test LLM credentials without saving."""
    if not auth:
        raise HTTPException(status_code=401, detail="Authentication required")
    base_url = (body.base_url.strip() or "https://api.anthropic.com").rstrip("/")
    headers: dict[str, str] = {
        "authorization": f"Bearer {body.api_key}",
        "content-type": "application/json",
        "anthropic-version": "2023-06-01",
    }
    if body.proxy_header and body.proxy_value:
        headers[body.proxy_header] = body.proxy_value
    req_body = {"model": "claude-haiku-4-5-20251001", "max_tokens": 8, "messages": [{"role": "user", "content": "Hi"}]}
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{base_url}/v1/messages", headers=headers, content=json.dumps(req_body).encode(), timeout=60)
        resp.raise_for_status()
    except httpx.ConnectError as e:
        raise HTTPException(status_code=502, detail=f"Connection failed: {e}")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=e.response.text)
    return {"status": "ok"}


_LLM_CHECK_TTL = 600  # 10 minutes


async def _check_llm_key(sub: str, r) -> bool:
    """Probe the stored LLM key; result cached in Redis for 10 min."""
    cache_key = f"user:llm:{sub}:check"
    cached = r.get(cache_key)
    if cached is not None:
        return cached == "1"
    try:
        encrypted = r.get(_llm_key(sub))
        if not encrypted:
            return False
        config = json.loads(decrypt_token(encrypted, sub))
        api_key = config.get("api_key", "")
        base_url = (config.get("base_url", "") or "https://api.anthropic.com").rstrip("/")
        proxy_header = config.get("proxy_header", "")
        proxy_value = config.get("proxy_value", "")
        headers: dict[str, str] = {
            "authorization": f"Bearer {api_key}",
            "content-type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        if proxy_header and proxy_value:
            headers[proxy_header] = proxy_value
        req_body = {"model": "claude-haiku-4-5-20251001", "max_tokens": 8,
                    "messages": [{"role": "user", "content": "Hi"}]}
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{base_url}/v1/messages",
                headers=headers,
                content=json.dumps(req_body).encode(),
                timeout=8,
            )
        working = resp.is_success
    except Exception:
        working = False
    r.setex(cache_key, _LLM_CHECK_TTL, "1" if working else "0")
    return working


@router.post("/llm")
async def connect_llm(body: LlmConfigBody, auth: dict | None = Depends(require_auth)) -> dict[str, str]:
    if not auth:
        raise HTTPException(status_code=401, detail="Authentication required")
    sub = auth["sub"]
    config = {"api_key": body.api_key, "base_url": body.base_url, "proxy_header": body.proxy_header, "proxy_value": body.proxy_value}
    r = get_redis()
    r.set(_llm_key(sub), encrypt_token(json.dumps(config), sub))
    r.delete(f"user:llm:{sub}:check")  # force re-probe on next load
    return {"status": "connected"}


# ── GitHub OAuth ──────────────────────────────────────────────────────────────

# ── Google Drive backend OAuth ────────────────────────────────────────────────

@router.get("/backend/init")
async def connect_backend_init(
    client_id: str = Query(..., description="GCP OAuth2 client ID"),
    client_secret: str = Query(..., description="GCP OAuth2 client secret"),
    auth: dict | None = Depends(require_auth),
) -> dict[str, str]:
    """Return Google OAuth2 URL. Redirect URI derived from FRONTEND_URL."""
    if not auth:
        raise HTTPException(status_code=401, detail="Authentication required")
    redirect_uri = FRONTEND_URL.rstrip("/") + "/api/connect/backend/callback"
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


class GithubRepoBody(BaseModel):
    name: str
    repo: str   # "owner/repo"
    pat: str


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


# ── GitHub repo connections ───────────────────────────────────────────────────

def _github_repo_key(sub: str, name: str) -> str:
    return f"creds:{sub}:github_repo:{name}"


@router.post("/github/repo", status_code=201)
async def add_github_repo(
    body: GithubRepoBody,
    auth: dict | None = Depends(require_auth),
) -> dict[str, str]:
    """Store an encrypted GitHub PAT and register the repo in config.json."""
    if not auth:
        raise HTTPException(status_code=401, detail="Authentication required")
    sub = auth["sub"]
    r = get_redis()
    r.set(_github_repo_key(sub, body.name), encrypt_token(body.pat, sub))
    storage = get_storage(auth)
    config = storage.read_json("config.json")
    config.setdefault("github_repos", {})[body.name] = {"repo": body.repo}
    storage.write_json("config.json", config)
    # Invalidate the Drive stats cache so INTEL reflects the new repo immediately.
    try:
        storage.write_json("registry_stats_cache.json", {})
    except Exception:
        pass
    return {"status": "connected", "name": body.name, "repo": body.repo}


@router.delete("/github/repo/{name}", status_code=204)
async def remove_github_repo(
    name: str,
    auth: dict | None = Depends(require_auth),
) -> None:
    """Remove a GitHub repo connection."""
    if not auth:
        raise HTTPException(status_code=401, detail="Authentication required")
    sub = auth["sub"]
    r = get_redis()
    r.delete(_github_repo_key(sub, name))
    try:
        storage = get_storage(auth)
        config = storage.read_json("config.json")
        config.get("github_repos", {}).pop(name, None)
        storage.write_json("config.json", config)
    except Exception:
        pass


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
    llm_connected = bool(r.get(_llm_key(sub)))
    llm_working = await _check_llm_key(sub, r) if llm_connected else False

    services = []
    github_repos = []
    file_count: int | None = None
    if backend_connected:
        try:
            storage = get_storage(auth)
            config = storage.read_json("config.json")
            for name, conn in config.get("connections", {}).items():
                services.append({
                    "name": name,
                    "provider": conn.get("provider", ""),
                    "account": conn.get("account", ""),
                    "authenticated": bool(_get_token(sub, name)),
                })
            for name, repo_config in config.get("github_repos", {}).items():
                repo = repo_config.get("repo", "")
                pat_enc = r.get(_github_repo_key(sub, name))
                pat = decrypt_token(pat_enc, sub) if pat_enc else None
                stats = _gh_stats(pat, repo) if pat else {"open_issues": None, "open_prs": None}
                github_repos.append({"name": name, "repo": repo, "authenticated": bool(pat_enc), **stats})
            try:
                file_count = storage.file_count()
            except Exception:
                pass
        except Exception:
            pass

    return {
        "backend": {"provider": "gdrive", "connected": backend_connected, "file_count": file_count},
        "llm": {"connected": llm_connected, "working": llm_working},
        "services": services,
        "github_repos": github_repos,
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
    if name == "llm":
        r.delete(_llm_key(sub))
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
