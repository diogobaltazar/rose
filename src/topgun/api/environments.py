"""
Gitpod / Ona environment management.

Environments are scoped per user — each user's Gitpod token and config
lives in their Redis-encrypted connection. All Gitpod API calls are made
directly via httpx with Bearer auth; no CLI required on the server.

Terminal access is proxied over a WebSocket using asyncssh so the browser
gets a live PTY connected to the running Ona environment.
"""

import asyncio
import json
import logging
from typing import AsyncIterator

import asyncssh
import httpx
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from connect import get_gitpod_config
from deps import require_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/environments", tags=["environments"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _gitpod_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


async def _gitpod_get(host: str, token: str, path: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{host}/api/v1{path}",
            headers=_gitpod_headers(token),
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()


async def _gitpod_post(host: str, token: str, path: str, body: dict) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{host}/api/v1{path}",
            headers=_gitpod_headers(token),
            content=json.dumps(body).encode(),
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()


def _normalise_phase(raw: str) -> str:
    """ENVIRONMENT_PHASE_RUNNING → running."""
    return raw.lower().replace("environment_phase_", "")


def _extract_ssh_host(env: dict, host: str) -> str | None:
    """
    Derive the SSH hostname for an environment.
    Gitpod exposes SSH at <env-id>.ssh.<host-domain>.
    Falls back to checking the environment status object.
    """
    env_id = env.get("id", "")
    # Check if API returns SSH details directly
    status = env.get("status", {})
    ssh_info = status.get("ssh", {}) or status.get("environmentUrl", {})
    if isinstance(ssh_info, dict):
        ssh_host = ssh_info.get("host") or ssh_info.get("sshHost")
        if ssh_host:
            return ssh_host

    # Derive from environment ID and host domain
    domain = host.replace("https://", "").replace("http://", "")
    return f"{env_id}.ssh.{domain}" if env_id else None


# ── Endpoints ─────────────────────────────────────────────────────────────────

class CreateEnvironmentBody(BaseModel):
    repo_url: str   # e.g. https://github.com/diogobaltazar/topgun


@router.post("", status_code=201)
async def create_environment(
    body: CreateEnvironmentBody,
    auth: dict | None = Depends(require_auth),
) -> dict:
    """Create a new Gitpod environment from the user's connected config."""
    if not auth:
        raise HTTPException(status_code=401, detail="Authentication required")
    cfg = get_gitpod_config(auth["sub"])
    if not cfg:
        raise HTTPException(status_code=409, detail="No Gitpod connection configured")

    host, token, class_id = cfg["host"], cfg["token"], cfg["class_id"]

    # Parse stored devcontainer JSON — sent as inline override if API supports it
    try:
        devcontainer = json.loads(cfg.get("devcontainer", "{}"))
    except json.JSONDecodeError:
        devcontainer = {}

    payload: dict = {
        "spec": {
            "machine": {"class": class_id},
            "content": {
                "initializer": {
                    "specs": [{
                        "git": {"remoteUri": body.repo_url, "cloneTarget": "main", "targetMode": "CLONE_TARGET_MODE_REMOTE_BRANCH"}
                    }]
                }
            },
        }
    }
    if devcontainer:
        payload["spec"]["devcontainer"] = {"devcontainerFile": json.dumps(devcontainer)}

    try:
        result = await _gitpod_post(host, token, "/environments", payload)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Gitpod API error: {e.response.text}")
    except httpx.ConnectError as e:
        raise HTTPException(status_code=502, detail=f"Cannot reach Gitpod: {e}")

    env = result.get("environment", result)
    phase = _normalise_phase(env.get("status", {}).get("phase", "unknown"))
    return {"id": env.get("id"), "phase": phase, "raw": env}


@router.get("")
async def list_environments(
    auth: dict | None = Depends(require_auth),
) -> dict:
    """List all Gitpod environments for the authenticated user."""
    if not auth:
        raise HTTPException(status_code=401, detail="Authentication required")
    cfg = get_gitpod_config(auth["sub"])
    if not cfg:
        raise HTTPException(status_code=409, detail="No Gitpod connection configured")

    try:
        result = await _gitpod_get(cfg["host"], cfg["token"], "/environments")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Gitpod API error: {e.response.text}")

    envs = result if isinstance(result, list) else result.get("environments", [])
    return {
        "environments": [
            {
                "id": e.get("id"),
                "phase": _normalise_phase(e.get("status", {}).get("phase", "unknown")),
                "name": e.get("name") or e.get("id", "")[:8],
                "repo": (e.get("spec", {}).get("content", {}).get("initializer", {})
                          .get("specs", [{}])[0].get("git", {}).get("remoteUri", "")),
            }
            for e in envs
        ]
    }


@router.get("/{env_id}")
async def get_environment(
    env_id: str,
    auth: dict | None = Depends(require_auth),
) -> dict:
    """Get status of a specific Gitpod environment."""
    if not auth:
        raise HTTPException(status_code=401, detail="Authentication required")
    cfg = get_gitpod_config(auth["sub"])
    if not cfg:
        raise HTTPException(status_code=409, detail="No Gitpod connection configured")

    try:
        result = await _gitpod_get(cfg["host"], cfg["token"], f"/environments/{env_id}")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise HTTPException(status_code=404, detail="Environment not found")
        raise HTTPException(status_code=502, detail=f"Gitpod API error: {e.response.text}")

    env = result.get("environment", result)
    phase = _normalise_phase(env.get("status", {}).get("phase", "unknown"))
    return {
        "id": env.get("id"),
        "phase": phase,
        "ssh_host": _extract_ssh_host(env, cfg["host"]),
    }


# ── WebSocket terminal ────────────────────────────────────────────────────────

@router.websocket("/{env_id}/terminal")
async def environment_terminal(
    env_id: str,
    ws: WebSocket,
    auth: dict | None = Depends(require_auth),
) -> None:
    """
    WebSocket PTY bridge to a running Gitpod environment via SSH.
    The browser connects with xterm.js; we proxy stdin/stdout over asyncssh.
    Auth: Gitpod PAT is used as the SSH password (token-based SSH auth).
    """
    if not auth:
        await ws.close(code=4001)
        return

    cfg = get_gitpod_config(auth["sub"])
    if not cfg:
        await ws.close(code=4009)
        return

    host, token = cfg["host"], cfg["token"]

    # Fetch environment to resolve SSH host
    try:
        result = await _gitpod_get(host, token, f"/environments/{env_id}")
    except Exception as e:
        logger.error("Failed to fetch environment %s: %s", env_id, e)
        await ws.close(code=4002)
        return

    env = result.get("environment", result)
    phase = _normalise_phase(env.get("status", {}).get("phase", "unknown"))
    if phase != "running":
        await ws.close(code=4003)
        return

    ssh_host = _extract_ssh_host(env, host)
    if not ssh_host:
        logger.error("Cannot resolve SSH host for environment %s", env_id)
        await ws.close(code=4004)
        return

    await ws.accept()

    try:
        async with asyncssh.connect(
            ssh_host,
            port=22,
            username="user",
            password=token,
            known_hosts=None,
            connect_timeout=30,
        ) as conn:
            async with conn.create_process(
                term_type="xterm-256color",
                term_size=(220, 50),
                request_pty=True,
            ) as process:
                await _bridge(ws, process)
    except asyncssh.DisconnectError as e:
        logger.info("SSH disconnect for env %s: %s", env_id, e)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("Terminal error for env %s: %s", env_id, e)
    finally:
        try:
            await ws.close()
        except Exception:
            pass


async def _bridge(ws: WebSocket, process: asyncssh.SSHClientProcess) -> None:
    """Bidirectional bridge: WebSocket ↔ SSH process stdin/stdout."""

    async def ws_to_ssh() -> None:
        try:
            while True:
                data = await ws.receive_bytes()
                process.stdin.write(data.decode("utf-8", errors="replace"))
        except (WebSocketDisconnect, Exception):
            process.stdin.write_eof()

    async def ssh_to_ws() -> None:
        try:
            async for chunk in _read_stream(process.stdout):
                await ws.send_bytes(chunk.encode("utf-8"))
        except Exception:
            pass

    await asyncio.gather(ws_to_ssh(), ssh_to_ws(), return_exceptions=True)


async def _read_stream(reader: asyncssh.SSHReader) -> AsyncIterator[str]:
    while True:
        chunk = await reader.read(4096)
        if not chunk:
            break
        yield chunk
