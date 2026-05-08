"""Mission creation — GitHub issues + Drive vault files from the KB chat."""

import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from deps import require_auth, get_storage, get_redis
from gdrive import decrypt_token

router = APIRouter(prefix="/missions", tags=["missions"])
logger = logging.getLogger(__name__)


class MissionPlanBody(BaseModel):
    title: str
    body: str
    source_urls: list[str] = []


@router.post("/plan", status_code=201)
async def create_mission_plan(
    body: MissionPlanBody,
    auth: dict | None = Depends(require_auth),
) -> dict[str, Any]:
    """Create GitHub issues and a Drive vault file for a mission."""
    if not auth:
        raise HTTPException(status_code=401, detail="Authentication required")

    sub = auth["sub"]
    storage = get_storage(auth)
    r = get_redis()

    try:
        config = storage.read_json("config.json")
    except Exception as exc:
        logger.warning("missions: failed to read config.json: %s", exc)
        raise HTTPException(status_code=503, detail="Could not read configuration")

    repos = config.get("github_repos", {})
    if not repos:
        raise HTTPException(
            status_code=400,
            detail="No GitHub repositories connected. Add one in Settings → Intel Knowledge Base Sources.",
        )

    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    slug = re.sub(r"[^a-z0-9]+", "-", body.title.lower().strip()).strip("-")[:50]

    created_issues: list[dict[str, Any]] = []

    for name, repo_config in repos.items():
        repo = repo_config.get("repo", "")
        encrypted_pat = r.get(f"creds:{sub}:github_repo:{name}")
        if not repo or not encrypted_pat:
            logger.warning("missions: no token for repo %r — skipping", name)
            continue
        try:
            pat = decrypt_token(encrypted_pat, sub)
            headers = {
                "Authorization": f"Bearer {pat}",
                "Accept": "application/vnd.github+json",
            }
            # Ensure topgun-mission label exists
            label_resp = httpx.get(
                f"https://api.github.com/repos/{repo}/labels/topgun-mission",
                headers=headers, timeout=10,
            )
            if label_resp.status_code == 404:
                httpx.post(
                    f"https://api.github.com/repos/{repo}/labels",
                    json={"name": "topgun-mission", "color": "FFB800", "description": "TopGun autonomous mission"},
                    headers=headers, timeout=10,
                )

            issue_parts = [body.body.strip(), "", "---", "", "*Created by TopGun Intel Knowledge Base*"]
            if body.source_urls:
                issue_parts += ["", "**Intel sources:**"] + [f"- {u}" for u in body.source_urls]

            issue_resp = httpx.post(
                f"https://api.github.com/repos/{repo}/issues",
                json={"title": body.title, "body": "\n".join(issue_parts), "labels": ["topgun-mission"]},
                headers=headers, timeout=10,
            )
            issue_resp.raise_for_status()
            issue_data = issue_resp.json()
            created_issues.append({
                "repo": repo,
                "url": issue_data["html_url"],
                "number": issue_data["number"],
            })
        except Exception as exc:
            logger.warning("missions: failed to create issue in %r: %s", repo, exc)
            continue

    if not created_issues:
        raise HTTPException(
            status_code=502,
            detail="Could not create GitHub issues — check repository credentials in Settings.",
        )

    # Build and store the vault file in Drive root (named mission-*.md so it's
    # discoverable if vault indexing is later extended to include root .md files).
    vault_filename = f"mission-{date_str}-{slug}.md"
    vault_content = _build_vault_file(body.title, body.body, created_issues, body.source_urls, date_str)
    try:
        storage.write_text(vault_filename, vault_content)
    except Exception as exc:
        logger.warning("missions: could not write vault file to Drive: %s", exc)

    # Invalidate stats cache so INTEL refreshes immediately.
    try:
        storage.write_json("registry_stats_cache.json", {})
    except Exception:
        pass

    return {
        "vault_file": vault_filename,
        "github_issues": created_issues,
    }


def _build_vault_file(
    title: str,
    body: str,
    issues: list[dict[str, Any]],
    source_urls: list[str],
    date: str,
) -> str:
    lines = [
        "---",
        f"date: {date}",
        "tags: [topgun-mission]",
        "status: planning",
        "---",
        "",
        f"# {title}",
        "",
        "## Mission Plan",
        "",
        body.strip(),
        "",
        "## GitHub Issues",
        "",
        "Complete in the following order:",
        "",
    ]
    for i, issue in enumerate(issues, 1):
        lines.append(f"{i}. [{issue['repo']}#{issue['number']}]({issue['url']})")
    lines.append("")

    if source_urls:
        lines += ["## Intel Sources", ""]
        for url in source_urls:
            lines.append(f"- {url}")
        lines.append("")

    return "\n".join(lines)
