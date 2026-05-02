"""Unit tests for the Python SDK client."""

import json
from unittest.mock import MagicMock

import pytest

from topgun.sdk.client import TopgunClient


def _mock_response(status_code: int, json_data):
    resp = MagicMock()
    resp.status_code = status_code
    resp.is_success = 200 <= status_code < 300
    resp.json.return_value = json_data
    return resp


def _client(get_responses=None, post_responses=None) -> TopgunClient:
    """Build a TopgunClient with mocked HTTP methods."""
    c = TopgunClient(base_url="http://test:5101")
    if get_responses:
        c._get = MagicMock(return_value=_mock_response(*get_responses))
    if post_responses:
        c._post = MagicMock(return_value=_mock_response(*post_responses))
    return c


def test_list_tasks_returns_items():
    """list_tasks must return the JSON array from the API."""
    items = [{"id": "gh:owner/repo#1", "title": "Task 1", "state": "open"}]
    c = _client(get_responses=(200, items))
    result = c.list_tasks()
    assert len(result) == 1
    assert result[0]["title"] == "Task 1"


def test_list_tasks_with_search():
    """list_tasks with search must pass the search query param."""
    items = [{"id": "gh:owner/repo#1", "title": "Found", "state": "open"}]
    c = _client(get_responses=(200, items))
    result = c.list_tasks(search="keyword")
    assert len(result) == 1
    c._get.assert_called_once()
    call_args = c._get.call_args
    assert call_args[1]["params"]["search"] == "keyword"


def test_close_task_success():
    """close_task must return True on successful close."""
    c = _client(post_responses=(200, {"status": "closed", "task_id": "gh:owner/repo#1"}))
    assert c.close_task("gh:owner/repo#1") is True


def test_timer_status_idle():
    """timer_status must return None when no timer is running."""
    c = _client(get_responses=(200, {"running": False}))
    assert c.timer_status() is None


def test_timer_start_error():
    """timer_start must raise ValueError when server returns error."""
    c = _client(post_responses=(200, {"error": "already running"}))
    with pytest.raises(ValueError, match="already running"):
        c.timer_start("gh:owner/repo#1")
