"""
Topgun Python SDK — HTTP client for the topgun API.

All task operations go through the FastAPI backend, making the API
the single source of truth for both the CLI and the webapp.
"""

from __future__ import annotations

import httpx

from topgun.sdk.types import Task, TimerStatus, TimerStopResult

DEFAULT_BASE_URL = "http://localhost:5101"


class TopgunClient:
    def __init__(self, base_url: str = DEFAULT_BASE_URL, timeout: float = 30.0):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def _url(self, path: str) -> str:
        return f"{self._base_url}{path}"

    def _get(self, path: str, params: dict | None = None) -> httpx.Response:
        return httpx.get(self._url(path), params=params, timeout=self._timeout)

    def _post(self, path: str, json: dict | None = None) -> httpx.Response:
        return httpx.post(self._url(path), json=json, timeout=self._timeout)

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
