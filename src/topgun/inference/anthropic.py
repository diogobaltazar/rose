"""
Anthropic SDK client for topgun inference calls.

Every call is appended to ~/.topgun/logs/inference/anthropic/calls.jsonl
so that all direct API usage is auditable independently of Claude Code sessions.
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_PROMPTS_DIR = Path(__file__).parent / "prompts"
_LOG_FILE = Path(os.environ.get("TOPGUN_INFERENCE_LOG", str(
    Path.home() / ".topgun" / "logs" / "inference" / "anthropic" / "calls.jsonl"
)))
_CUSTOM_HEADER = "x-build-cli-tool"
_CUSTOM_HEADER_VALUE = "claude"
_MODEL = "claude-haiku-4-5-20251001"


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


def call(prompt: str, system: str, command: str) -> str:
    """
    Make a single-turn inference call to Claude Haiku.

    Args:
        prompt:  The user message (task list + query).
        system:  The system prompt string (load via load_prompt()).
        command: The topgun command making the call (e.g. "timer").

    Returns:
        The raw text content of the model's response.
    """
    import anthropic

    base_url = os.environ.get("ANTHROPIC_BASE_URL", "").strip() or None
    client = anthropic.Anthropic(
        api_key=_get_token(),
        base_url=base_url,
        default_headers={_CUSTOM_HEADER: _CUSTOM_HEADER_VALUE},
    )

    t0 = time.monotonic()
    response = client.messages.create(
        model=_MODEL,
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    duration_ms = round((time.monotonic() - t0) * 1000)

    usage = response.usage
    _append_log({
        "ts": datetime.now(timezone.utc).isoformat(),
        "command": command,
        "model": _MODEL,
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "duration_ms": duration_ms,
    })

    return response.content[0].text
