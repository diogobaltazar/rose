"""
Anthropic API client for topgun inference calls.

Every call is appended to ~/.topgun/logs/inference/anthropic/calls.jsonl
so that all direct API usage is auditable independently of Claude Code sessions.
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console

load_dotenv()

_PROMPTS_DIR = Path(__file__).parent / "prompts"
_LOG_FILE = Path(os.environ.get("TOPGUN_INFERENCE_LOG", str(
    Path.home() / ".topgun" / "logs" / "inference" / "anthropic" / "calls.jsonl"
)))
_CUSTOM_HEADER = "x-build-cli-tool"
_CUSTOM_HEADER_VALUE = "claude"
_MODEL = "claude-haiku-4-5-20251001"
_console = Console()


def _get_token() -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if api_key:
        return api_key
    raise EnvironmentError(
        "ANTHROPIC_API_KEY is not set. Add it to your .env file."
    )


def _append_log(record: dict) -> None:
    _LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _LOG_FILE.open("a") as f:
        f.write(json.dumps(record) + "\n")


def load_prompt(name: str) -> str:
    """Load a system prompt from the prompts/ directory by filename stem."""
    path = _PROMPTS_DIR / f"{name}.md"
    return path.read_text()


def call(prompt: str, system: str, command: str, status_message: str = "thinking…") -> str:
    """
    Make a single-turn inference call to Claude Haiku.

    Args:
        prompt:         The user message (task list + query).
        system:         The system prompt string (load via load_prompt()).
        command:        The topgun command making the call (e.g. "timer").
        status_message: Label shown in the spinner while the call is in flight.

    Returns:
        The raw text content of the model's response.
    """
    import httpx

    token = _get_token()
    base_url = (os.environ.get("ANTHROPIC_BASE_URL", "").strip() or "https://api.anthropic.com").rstrip("/")

    # Use httpx directly rather than the Anthropic SDK. The build-cli proxy
    # requires Authorization: Bearer (not x-api-key) and rejects the SDK's
    # x-stainless-* diagnostic headers. A raw httpx call avoids both issues
    # and works identically against api.anthropic.com.
    body = {
        "model": _MODEL,
        "max_tokens": 1024,
        "system": system,
        "messages": [{"role": "user", "content": prompt}],
    }
    url = f"{base_url}/v1/messages"
    t0 = time.monotonic()
    with _console.status(f"{status_message} [dim]{_MODEL}[/dim]"):
        try:
            response = httpx.post(
                url,
                headers={
                    "authorization": f"Bearer {token}",
                    "content-type": "application/json",
                    "anthropic-version": "2023-06-01",
                    _CUSTOM_HEADER: _CUSTOM_HEADER_VALUE,
                },
                content=json.dumps(body).encode(),
                timeout=60,
            )
        except httpx.ConnectError as e:
            raise RuntimeError(
                f"Could not connect to {url} — check ANTHROPIC_BASE_URL and network access.\n"
                f"Underlying error: {e}"
            ) from None
    duration_ms = round((time.monotonic() - t0) * 1000)
    if not response.is_success:
        raise RuntimeError(
            f"Inference API returned {response.status_code} for {url}\n"
            f"Check your API key / proxy credentials (ANTHROPIC_API_KEY, ANTHROPIC_BASE_URL)."
        )
    data = response.json()

    usage = data.get("usage", {})
    _append_log({
        "ts": datetime.now(timezone.utc).isoformat(),
        "command": command,
        "model": _MODEL,
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "duration_ms": duration_ms,
    })

    return data["content"][0]["text"]
