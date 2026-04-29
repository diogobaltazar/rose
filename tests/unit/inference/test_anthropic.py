"""
Unit tests for topgun.inference.anthropic.

Covers the InferenceError class and the call() function's error-handling path.
These tests ensure that when the inference API returns a non-2xx response the
error raised is (a) the right type, (b) a subclass of RuntimeError for
backwards compatibility, and (c) contains the response body so the caller can
diagnose what went wrong without inspecting raw HTTP traffic.
"""

import sys
from types import ModuleType
from unittest.mock import MagicMock

import pytest

# httpx is a runtime dependency that may not be present in the test environment.
# We inject a lightweight stub so the module under test can be imported and its
# internals exercised without a real network client.
if "httpx" not in sys.modules:
    _stub = ModuleType("httpx")
    _stub.ConnectError = type("ConnectError", (OSError,), {})
    _stub.post = MagicMock()
    sys.modules["httpx"] = _stub

from topgun.inference.anthropic import InferenceError, call  # noqa: E402


# ── InferenceError class ──────────────────────────────────────────────────────


def test_inference_error_is_runtime_error():
    """InferenceError must be a RuntimeError subclass for backwards-compatible catches.

    Existing callers that rescue RuntimeError must not break silently when the
    more specific class is introduced.
    """
    err = InferenceError(401, "https://example.com/v1/messages", '{"error":"bad"}', "…abcd", "https://example.com")
    assert isinstance(err, RuntimeError)


def test_inference_error_message_contains_status_code():
    """The error message must include the HTTP status code.

    Without the status code a user cannot distinguish a 401 (auth) from a 429
    (rate limit) or 500 (server error).
    """
    err = InferenceError(401, "https://example.com/v1/messages", "body text", "…abcd", "https://example.com")
    assert "401" in str(err)


def test_inference_error_message_contains_body():
    """The error message must include the response body.

    This is the primary diagnostic improvement: proxy and API errors embed
    machine-readable explanations in the body that were previously discarded.
    """
    body = '{"error":{"type":"authentication_error","message":"invalid api key"}}'
    err = InferenceError(401, "https://example.com/v1/messages", body, "…abcd", "https://example.com")
    assert "authentication_error" in str(err)


def test_inference_error_body_attribute():
    """InferenceError must expose response_body as an attribute for programmatic access."""
    body = '{"error":"bad token"}'
    err = InferenceError(401, "https://example.com/v1/messages", body, "…abcd", "https://example.com")
    assert err.response_body == body


def test_inference_error_truncates_long_body():
    """Bodies longer than 500 chars must be truncated in the message.

    A runaway response body should not flood the terminal.
    """
    body = "x" * 1000
    err = InferenceError(401, "https://example.com/v1/messages", body, "…abcd", "https://example.com")
    # The preview in the message is capped; the full body is on the attribute.
    assert err.response_body == body
    assert body not in str(err)  # message is truncated
    assert "x" * 500 in str(err)  # exactly 500 chars appear


# ── call() error path ─────────────────────────────────────────────────────────


def _mock_response(status_code: int, text: str) -> MagicMock:
    r = MagicMock()
    r.is_success = status_code < 400
    r.status_code = status_code
    r.text = text
    return r


def test_call_raises_inference_error_on_401(monkeypatch):
    """call() must raise InferenceError (not bare RuntimeError) on a 401 response.

    Having a typed exception lets callers handle known API failures without
    accidentally swallowing unrelated RuntimeErrors.
    """
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-1234567890")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://api.example.com")

    body = '{"error":{"type":"authentication_error"}}'
    sys.modules["httpx"].post.return_value = _mock_response(401, body)
    with pytest.raises(InferenceError) as exc_info:
        call(prompt="hello", system="you are helpful", command="test")

    assert exc_info.value.status_code == 401
    assert "authentication_error" in str(exc_info.value)


def test_call_raises_inference_error_on_500(monkeypatch):
    """call() must raise InferenceError for 5xx server errors too.

    Server errors carry diagnostic body content just like 4xx responses.
    """
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-1234567890")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://api.example.com")

    body = '{"error":{"type":"overloaded_error","message":"service overloaded"}}'
    sys.modules["httpx"].post.return_value = _mock_response(529, body)
    with pytest.raises(InferenceError) as exc_info:
        call(prompt="hello", system="you are helpful", command="test")

    assert exc_info.value.status_code == 529
    assert "overloaded_error" in str(exc_info.value)


def test_call_raises_inference_error_on_connect_error(monkeypatch):
    """call() must raise InferenceError when the host is unreachable.

    Unreachable hosts and misconfigured ANTHROPIC_BASE_URL are inference
    failures just like a 401 — they should be catchable by the same handler.
    """
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-1234567890")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://unreachable.invalid")

    sys.modules["httpx"].post.side_effect = sys.modules["httpx"].ConnectError("Connection refused")
    try:
        with pytest.raises(InferenceError) as exc_info:
            call(prompt="hello", system="you are helpful", command="test")
        assert exc_info.value.status_code == 0
    finally:
        sys.modules["httpx"].post.side_effect = None
