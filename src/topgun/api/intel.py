"""
Intel document registry — Google Drive JSONL backend.

Each intel document is a pointer to a GitHub issue or Obsidian vault file.
Stored as lines in Google Drive /topgun/intel.jsonl.
Tags and content live at the source — never stored here.
"""

import hashlib
import json
import os
import re
import uuid
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from deps import require_auth, get_storage

router = APIRouter(prefix="/intel", tags=["intel"])

INTEL_FILE = "registry.jsonl"
STATS_FILE = "registry_stats_cache.json"
STATS_TTL_S = 120
VAULT_PREFIX = "vault/"

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")


def _vault_uid(path: str) -> str:
    """Stable UID derived from vault file path."""
    return hashlib.sha1(path.encode()).hexdigest()[:12]


def _is_topgun_format(content: str) -> bool:
    """Check if an .md file has topgun frontmatter (date + status fields)."""
    return bool(re.match(r"^---\n", content)) and "status:" in content[:500]


def _vault_docs(client) -> list[dict[str, Any]]:
    """List all topgun-format .md files in topgun/vault/ on Google Drive."""
    try:
        folder_id = client._folder()
        svc = client._svc

        # Find vault subfolder
        results = svc.files().list(
            q=f"name='vault' and '{folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
            spaces="drive", fields="files(id)",
        ).execute()
        vault_files = results.get("files", [])
        if not vault_files:
            return []
        vault_id = vault_files[0]["id"]

        # List .md files recursively in vault
        md_files = svc.files().list(
            q=f"'{vault_id}' in parents and name contains '.md' and trashed=false",
            spaces="drive", fields="files(id, name)",
        ).execute().get("files", [])

        docs = []
        for f in md_files:
            content = client.read_text(f["name"])
            if _is_topgun_format(content):
                path = f"{VAULT_PREFIX}{f['name']}"
                docs.append({
                    "uid": _vault_uid(path),
                    "source": "obsidian",
                    "source_url": path,
                    "title": _extract_title(content),
                    "auto_discovered": True,
                })
        return docs
    except Exception:
        return []


def _extract_title(content: str) -> str:
    m = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    return m.group(1).strip() if m else ""


class IntelCreate(BaseModel):
    source: str  # "github" | "obsidian"
    source_url: str


class IntelUpdate(BaseModel):
    source: str | None = None
    source_url: str | None = None


# ── CRUD ──────────────────────────────────────────────────────────────────────

@router.get("")
def list_intel(auth: dict | None = Depends(require_auth)) -> list[dict[str, Any]]:
    client = get_storage(auth)
    registered = client.read_jsonl(INTEL_FILE)
    registered_urls = {d.get("source_url") for d in registered}
    discovered = [d for d in _vault_docs(client) if d["source_url"] not in registered_urls]
    return registered + discovered


@router.get("/stats")
async def intel_stats(auth: dict | None = Depends(require_auth)) -> dict[str, Any]:
    from datetime import datetime, timezone
    client = get_storage(auth)

    # Try cache
    cache = client.read_json(STATS_FILE)
    if cache:
        cached_at = cache.get("_cached_at", 0)
        now = datetime.now(timezone.utc).timestamp()
        if now - cached_at < STATS_TTL_S:
            cache.pop("_cached_at", None)
            return cache

    stats = await _compute_stats(client)
    cache_entry = {**stats, "_cached_at": datetime.now(timezone.utc).timestamp()}
    client.write_json(STATS_FILE, cache_entry)
    return stats


@router.post("/stats/refresh")
async def refresh_stats(auth: dict | None = Depends(require_auth)) -> dict[str, Any]:
    from datetime import datetime, timezone
    client = get_storage(auth)
    stats = await _compute_stats(client)
    cache_entry = {**stats, "_cached_at": datetime.now(timezone.utc).timestamp()}
    client.write_json(STATS_FILE, cache_entry)
    return stats


@router.get("/search")
async def search_intel(q: str, auth: dict | None = Depends(require_auth)) -> list[dict[str, Any]]:
    client = get_storage(auth)
    docs = client.read_jsonl(INTEL_FILE)
    if not docs:
        return []
    return await _search_docs(docs, q)


@router.get("/{uid}")
def get_intel(uid: str, auth: dict | None = Depends(require_auth)) -> dict[str, Any]:
    client = get_storage(auth)
    docs = client.read_jsonl(INTEL_FILE)
    doc = next((d for d in docs if d.get("uid") == uid), None)
    if not doc:
        raise HTTPException(status_code=404, detail="Intel document not found")
    return doc


@router.post("", status_code=201)
def create_intel(
    body: IntelCreate | None = None,
    auth: dict | None = Depends(require_auth),
) -> dict[str, Any]:
    client = get_storage(auth)
    uid = uuid.uuid4().hex[:12]
    entry: dict[str, Any] = {"uid": uid}
    if body:
        entry["source"] = body.source
        entry["source_url"] = body.source_url
    else:
        entry["source"] = ""
        entry["source_url"] = ""
    client.append_jsonl(INTEL_FILE, entry)
    client.write_json(STATS_FILE, {})  # invalidate stats cache
    return entry


@router.patch("/{uid}")
def update_intel(
    uid: str,
    body: IntelUpdate,
    auth: dict | None = Depends(require_auth),
) -> dict[str, Any]:
    client = get_storage(auth)
    docs = client.read_jsonl(INTEL_FILE)
    idx = next((i for i, d in enumerate(docs) if d.get("uid") == uid), None)
    if idx is None:
        raise HTTPException(status_code=404, detail="Intel document not found")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    docs[idx].update(updates)
    client.rewrite_jsonl(INTEL_FILE, docs)
    client.write_json(STATS_FILE, {})
    return docs[idx]


@router.delete("/{uid}", status_code=204)
def delete_intel(uid: str, auth: dict | None = Depends(require_auth)) -> None:
    client = get_storage(auth)
    docs = client.read_jsonl(INTEL_FILE)
    remaining = [d for d in docs if d.get("uid") != uid]
    if len(remaining) == len(docs):
        raise HTTPException(status_code=404, detail="Intel document not found")
    client.rewrite_jsonl(INTEL_FILE, remaining)

    # Also clean up timer entries for this uid
    timers = client.read_jsonl("timers.jsonl")
    remaining_timers = [t for t in timers if t.get("uid") != uid]
    client.rewrite_jsonl("timers.jsonl", remaining_timers)
    client.write_json(STATS_FILE, {})


# ── Stats + Search helpers ────────────────────────────────────────────────────

async def _compute_stats(client) -> dict[str, Any]:
    docs = client.read_jsonl(INTEL_FILE)
    total = len(docs)
    by_source = {"github": 0, "obsidian": 0}
    for doc in docs:
        src = doc.get("source", "")
        if src in by_source:
            by_source[src] += 1

    tags = await _fetch_all_tags(docs)
    missions = sum(1 for t in tags.values() if "topgun-mission" in t)
    drafts = sum(1 for t in tags.values() if "topgun-mission-draft" in t)
    ready = sum(1 for t in tags.values() if "topgun-mission-ready" in t)

    return {
        "total": total,
        "by_source": by_source,
        "missions": missions,
        "drafts": drafts,
        "ready": ready,
    }


async def _fetch_all_tags(docs: list[dict]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for doc in docs:
        if doc.get("source") == "github":
            result[doc["uid"]] = await _github_issue_tags(doc.get("source_url", ""))
        elif doc.get("source") == "obsidian":
            result[doc["uid"]] = _obsidian_file_tags(doc.get("source_url", ""))
    return result


async def _github_issue_tags(url: str) -> list[str]:
    m = re.match(r"https://github\.com/([^/]+/[^/]+)/issues/(\d+)", url)
    if not m:
        return []
    repo, number = m.group(1), m.group(2)
    headers: dict[str, str] = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"https://api.github.com/repos/{repo}/issues/{number}", headers=headers
            )
            r.raise_for_status()
            return [label["name"] for label in r.json().get("labels", [])]
    except Exception:
        return []


def _obsidian_file_tags(path: str) -> list[str]:
    from pathlib import Path
    file_path = Path(path) if Path(path).is_absolute() else Path.home() / path.lstrip("/")
    if not file_path.exists():
        return []
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    fm = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not fm:
        return []
    tags_match = re.search(r"tags:\s*\[([^\]]*)\]", fm.group(1))
    if tags_match:
        return [t.strip().strip('"').strip("'") for t in tags_match.group(1).split(",") if t.strip()]
    return []


async def _search_docs(docs: list[dict], query: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    q_lower = query.lower()
    for doc in docs:
        if doc.get("source") == "github":
            match = await _search_github_issue(doc, q_lower)
        else:
            match = _search_obsidian_file(doc, q_lower)
        if match:
            results.append(match)
    return results


async def _search_github_issue(doc: dict, query: str) -> dict[str, Any] | None:
    url = doc.get("source_url", "")
    m = re.match(r"https://github\.com/([^/]+/[^/]+)/issues/(\d+)", url)
    if not m:
        return None
    repo, number = m.group(1), m.group(2)
    headers: dict[str, str] = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"https://api.github.com/repos/{repo}/issues/{number}", headers=headers
            )
            r.raise_for_status()
            issue = r.json()
            if query in (issue.get("title") or "").lower() or query in (issue.get("body") or "").lower():
                return {"uid": doc["uid"], "source": "github", "source_url": url, "title": issue.get("title", "")}
    except Exception:
        pass
    return None


def _search_obsidian_file(doc: dict, query: str) -> dict[str, Any] | None:
    from pathlib import Path
    path = doc.get("source_url", "")
    file_path = Path(path) if Path(path).is_absolute() else Path.home() / path.lstrip("/")
    if not file_path.exists():
        return None
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if query not in text.lower():
        return None
    title_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    title = title_match.group(1) if title_match else file_path.stem.replace("-", " ").title()
    return {"uid": doc["uid"], "source": "obsidian", "source_url": path, "title": title}
