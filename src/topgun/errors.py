"""
topgun error hierarchy.

Raise subclasses of TopgunError from library code; catch TopgunError at CLI
boundaries and display a clean message before exiting.
"""


class TopgunError(Exception):
    """Base class for all topgun errors."""
    exit_code: int = 1


class InferenceError(TopgunError):
    """An LLM inference call failed."""


class AuthError(InferenceError):
    """No valid API key could be found or the key has expired."""


class InferenceAPIError(InferenceError):
    """The inference API returned a non-2xx response."""

    def __init__(self, status_code: int, url: str, body: str, key_hint: str, base_url: str) -> None:
        self.status_code = status_code
        self.response_body = body
        preview = body[:500].strip() or "(empty)"
        super().__init__(
            f"inference API returned {status_code} for {url}\n"
            f"response: {preview}\n"
            f"key (last 4): {key_hint}  base url: {base_url}"
        )


class SourceError(TopgunError):
    """A task source (GitHub or Obsidian) could not be queried."""


class TaskNotFoundError(TopgunError):
    """No task matched the given reference."""
