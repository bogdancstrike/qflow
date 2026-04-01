"""Tests for the HTTP client retry logic."""

import pytest
from unittest.mock import patch, MagicMock
from src.core.http_client import make_request, HttpClientError


def test_successful_request():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"result": "ok"}
    mock_response.headers = {"Content-Type": "application/json"}

    with patch("src.core.http_client.requests.request", return_value=mock_response):
        result = make_request("POST", "http://example.com/api", body={"text": "test"})

    assert result["status_code"] == 200
    assert result["body"]["result"] == "ok"


def test_non_retryable_error():
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.json.return_value = {"error": "not found"}
    mock_response.headers = {"Content-Type": "application/json"}

    with patch("src.core.http_client.requests.request", return_value=mock_response):
        with pytest.raises(HttpClientError, match="404"):
            make_request("GET", "http://example.com/missing")


def test_connection_error():
    with patch("src.core.http_client.requests.request") as mock_req:
        import requests
        mock_req.side_effect = requests.exceptions.ConnectionError("refused")
        with pytest.raises(HttpClientError, match="Connection error"):
            make_request("POST", "http://nonexistent:9999/fail")
