"""
Topgun Python SDK — HTTP client for the topgun API.

All task operations go through the FastAPI backend, making the API
the single source of truth for both the CLI and the webapp.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx

from topgun.sdk.types import Task, TimerStatus, TimerStopResult, IntelDocument, IntelTimerStatus

DEFAULT_BASE_URL = os.environ.get("TOPGUN_API") or "http://localhost:5101"
def _auth_file() -> Path:
    cfg = os.environ.get("TOPGUN_CONFIG", str(Path.home() / ".config" / "topgun" / "config.json"))
    return Path(cfg).parent / "auth.json"


def _load_token() -> str | None:
    try:
        data = json.loads(_auth_file().read_text())
        return data.get("access_token")
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return None


class TopgunClient:
    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
        token: str | None = None,
    ):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._token = token or _load_token()

    def _url(self, path: str) -> str:
        return f"{self._base_url}{path}"

    def _headers(self) -> dict[str, str]:
        if self._token:
            return {"Authorization": f"Bearer {self._token}"}
        return {}

    def _get(self, path: str, params: dict | None = None) -> httpx.Response:
        return httpx.get(self._url(path), params=params, headers=self._headers(), timeout=self._timeout)

    def _post(self, path: str, json: dict | None = None) -> httpx.Response:
        return httpx.post(self._url(path), json=json, headers=self._headers(), timeout=self._timeout)

    def _patch(self, path: str, json: dict | None = None) -> httpx.Response:
        return httpx.patch(self._url(path), json=json, headers=self._headers(), timeout=self._timeout)

    def _delete(self, path: str) -> httpx.Response:
        return httpx.delete(self._url(path), headers=self._headers(), timeout=self._timeout)

    def is_available(self) -> bool:
        try:
            r = self._get("/backlog", params={"status": "open"})
            return r.is_success
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    def list_tasks(
        self,
        *,
        search: str | None = None,
        sort: str | None = None,
        order: str | None = None,
        status: str | None = None,
    ) -> list[Task]:
        params: dict[str, str] = {}
        if search:
            params["search"] = search
        if sort:
            params["sort"] = sort
        if order:
            params["order"] = order
        if status:
            params["status"] = status
        r = self._get("/backlog", params=params or None)
        r.raise_for_status()
        return r.json()

    def refresh_backlog(self) -> None:
        r = self._post("/backlog/refresh")
        r.raise_for_status()

    def close_task(self, task_id: str) -> bool:
        r = self._post(f"/tasks/{task_id}/close")
        if r.is_success:
            data = r.json()
            return data.get("status") == "closed"
        return False

    def timer_status(self) -> TimerStatus | None:
        r = self._get("/timer/status")
        r.raise_for_status()
        data = r.json()
        if data.get("running") is False and "task_id" not in data:
            return None
        return data

    def timer_start(self, task_id: str, task_title: str = "") -> dict:
        r = self._post("/timer/start", json={"task_id": task_id, "task_title": task_title})
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            raise ValueError(data["error"])
        return data

    def timer_stop(self) -> TimerStopResult:
        r = self._post("/timer/stop")
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            raise ValueError(data["error"])
        return data

    # ── Intel ─────────────────────────────────────────────────────────────

    def list_intel(self) -> list[IntelDocument]:
        r = self._get("/intel")
        r.raise_for_status()
        return r.json()

    def get_intel(self, uid: str) -> IntelDocument:
        r = self._get(f"/intel/{uid}")
        r.raise_for_status()
        return r.json()

    def create_intel(self, source: str = "", source_url: str = "") -> IntelDocument:
        body = {}
        if source and source_url:
            body = {"source": source, "source_url": source_url}
        r = self._post("/intel", json=body or None)
        r.raise_for_status()
        return r.json()

    def update_intel(self, uid: str, **fields: str) -> IntelDocument:
        r = self._patch(f"/intel/{uid}", json=fields)
        r.raise_for_status()
        return r.json()

    def delete_intel(self, uid: str) -> None:
        r = self._delete(f"/intel/{uid}")
        r.raise_for_status()

    def search_intel(self, query: str) -> list[IntelDocument]:
        r = self._get("/intel/search", params={"q": query})
        r.raise_for_status()
        return r.json()

    def intel_stats(self) -> dict:
        r = self._get("/intel/stats")
        r.raise_for_status()
        return r.json()

    def refresh_intel_stats(self) -> dict:
        r = self._post("/intel/stats/refresh")
        r.raise_for_status()
        return r.json()

    # ── Intel Timer ───────────────────────────────────────────────────────

    def intel_timer_status(self, uid: str) -> IntelTimerStatus:
        r = self._get(f"/timer/{uid}")
        r.raise_for_status()
        return r.json()

    def intel_timer_start(self, uid: str) -> dict:
        r = self._post(f"/timer/{uid}/start")
        r.raise_for_status()
        return r.json()

    def intel_timer_stop(self, uid: str) -> dict:
        r = self._post(f"/timer/{uid}/stop")
        r.raise_for_status()
        return r.json()
