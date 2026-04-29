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
_PROXY_TOOL_HEADER = os.environ.get("TOPGUN_PROXY_TOOL_HEADER", "")
_PROXY_TOOL_VALUE  = os.environ.get("TOPGUN_PROXY_TOOL_VALUE", "")
_MODEL = "claude-haiku-4-5-20251001"
_console = Console()


class InferenceError(RuntimeError):
    """Raised when the inference API returns a non-2xx response or is unreachable."""

    def __init__(self, status_code: int, url: str, body: str, key_hint: str, base_url: str) -> None:
        self.status_code = status_code
        self.response_body = body
        preview = body[:500].strip() or "(empty)"
        super().__init__(
            f"Inference API returned {status_code} for {url}\n"
            f"Response: {preview}\n"
            f"Key (last 4): {key_hint}  Base URL: {base_url}"
        )


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

    # Use httpx directly rather than the Anthropic SDK. Some proxy configurations
    # require Authorization: Bearer (not x-api-key) and reject x-stainless-*
    # diagnostic headers injected by the SDK. A raw httpx call sidesteps both.
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
            headers = {
                "authorization": f"Bearer {token}",
                "content-type": "application/json",
                "anthropic-version": "2023-06-01",
            }
            if _PROXY_TOOL_HEADER:
                headers[_PROXY_TOOL_HEADER] = _PROXY_TOOL_VALUE
            response = httpx.post(
                url,
                headers=headers,
                content=json.dumps(body).encode(),
                timeout=60,
            )
        except httpx.ConnectError as e:
            raise InferenceError(0, url, str(e), "(n/a)", base_url) from None
    duration_ms = round((time.monotonic() - t0) * 1000)
    if not response.is_success:
        key_hint = f"…{token[-4:]}" if len(token) >= 4 else "(too short)"
        raise InferenceError(response.status_code, url, response.text or "", key_hint, base_url)
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
