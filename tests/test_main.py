from unittest.mock import patch, MagicMock
import pytest
import requests
from karakeep_tts.main import ping_healthcheck


def test_ping_healthcheck_no_url_is_noop():
    # Should not raise, should not call requests
    with patch("karakeep_tts.main.requests.get") as mock_get:
        ping_healthcheck("")
        mock_get.assert_not_called()


def test_ping_healthcheck_success_url():
    with patch("karakeep_tts.main.requests.get") as mock_get:
        ping_healthcheck("https://hc.example.com/abc")
        mock_get.assert_called_once_with("https://hc.example.com/abc", timeout=10)


def test_ping_healthcheck_failure_appends_fail():
    with patch("karakeep_tts.main.requests.get") as mock_get:
        ping_healthcheck("https://hc.example.com/abc/", failure=True)
        mock_get.assert_called_once_with("https://hc.example.com/abc/fail", timeout=10)


def test_ping_healthcheck_swallows_request_errors():
    with patch("karakeep_tts.main.requests.get", side_effect=requests.RequestException("net err")):
        # must not raise
        ping_healthcheck("https://hc.example.com/abc")
