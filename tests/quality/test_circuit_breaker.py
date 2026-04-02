"""Quality tests — circuit breaker state transitions.

Verifies the HTTP client circuit breaker opens after failures
and rejects calls while open.
"""

import os
import time
from unittest.mock import patch, MagicMock

import pytest
import pybreaker
import requests

os.environ["DEV_MODE"] = "true"

from src.core.http_client import make_request, HttpClientError, _http_breaker


REPORT_FILE = os.path.join(os.path.dirname(__file__), "../../reports/quality_circuit_breaker.txt")


def _write_report(test_name, lines):
    os.makedirs(os.path.dirname(REPORT_FILE), exist_ok=True)
    with open(REPORT_FILE, "a") as f:
        f.write(f"\n{'='*70}\n")
        f.write(f"  TEST: {test_name}\n")
        f.write(f"  TIME: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        for line in lines:
            f.write(f"  {line}\n")
        f.write(f"{'='*70}\n")


@pytest.fixture(autouse=True)
def reset_breaker():
    """Reset circuit breaker state before each test."""
    _http_breaker.close()
    yield
    _http_breaker.close()


class TestCircuitBreakerTransitions:
    """Verify circuit breaker opens/closes correctly."""

    def test_breaker_starts_closed(self):
        assert _http_breaker.current_state == "closed"
        _write_report("test_breaker_starts_closed", [
            f"State: {_http_breaker.current_state}",
            "PASS",
        ])

    def test_breaker_opens_after_fail_max(self):
        """After 10 consecutive failures, breaker should open."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"error": "server error"}
        mock_response.headers = {}

        failures = 0
        with patch("src.core.http_client.requests.request", return_value=mock_response):
            for i in range(_http_breaker.fail_max + 5):
                try:
                    make_request("GET", "http://fake-service/api")
                except (HttpClientError, pybreaker.CircuitBreakerError):
                    failures += 1

        assert _http_breaker.current_state == "open"

        _write_report("test_breaker_opens_after_fail_max", [
            f"fail_max: {_http_breaker.fail_max}",
            f"Total failures triggered: {failures}",
            f"State after: {_http_breaker.current_state}",
            "PASS",
        ])

    def test_breaker_rejects_when_open(self):
        """Once open, new requests should be rejected immediately."""
        # Force breaker open
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"error": "fail"}
        mock_response.headers = {}

        with patch("src.core.http_client.requests.request", return_value=mock_response):
            for _ in range(_http_breaker.fail_max):
                try:
                    make_request("GET", "http://fake-service/api")
                except (HttpClientError, pybreaker.CircuitBreakerError):
                    pass

        assert _http_breaker.current_state == "open"

        # Now requests should be rejected without hitting the actual endpoint
        with patch("src.core.http_client.requests.request") as mock_req:
            with pytest.raises(pybreaker.CircuitBreakerError):
                _http_breaker.call(lambda: None)
            mock_req.assert_not_called()

        _write_report("test_breaker_rejects_when_open", [
            "Breaker state: open",
            "Attempted call -> CircuitBreakerError raised",
            "Underlying request NOT called",
            "PASS",
        ])

    def test_breaker_half_open_after_timeout(self):
        """After reset_timeout, breaker should transition to half-open."""
        # Create a short-timeout breaker for testing
        test_breaker = pybreaker.CircuitBreaker(
            fail_max=2, reset_timeout=1, name="test-short-breaker"
        )

        # Trip it
        for _ in range(test_breaker.fail_max):
            try:
                test_breaker.call(lambda: (_ for _ in ()).throw(Exception("fail")))
            except Exception:
                pass

        assert test_breaker.current_state == "open"

        # Wait for reset
        time.sleep(1.5)

        # Next call should attempt (half-open)
        success_called = False

        def success_func():
            nonlocal success_called
            success_called = True
            return "ok"

        result = test_breaker.call(success_func)
        assert result == "ok"
        assert success_called
        assert test_breaker.current_state == "closed"

        _write_report("test_breaker_half_open_after_timeout", [
            f"fail_max: {test_breaker.fail_max}, reset_timeout: {test_breaker.reset_timeout}s",
            "Tripped breaker -> open",
            "Waited 1.5s -> half-open",
            "Successful call -> closed",
            "PASS",
        ])

    def test_breaker_reopens_on_half_open_failure(self):
        """If a call fails during half-open, breaker should reopen."""
        test_breaker = pybreaker.CircuitBreaker(
            fail_max=2, reset_timeout=1, name="test-reopen-breaker"
        )

        # Trip it
        for _ in range(test_breaker.fail_max):
            try:
                test_breaker.call(lambda: (_ for _ in ()).throw(Exception("fail")))
            except Exception:
                pass

        assert test_breaker.current_state == "open"
        time.sleep(1.5)

        # Fail during half-open
        try:
            test_breaker.call(lambda: (_ for _ in ()).throw(Exception("still failing")))
        except Exception:
            pass

        assert test_breaker.current_state == "open"

        _write_report("test_breaker_reopens_on_half_open_failure", [
            "Tripped -> open -> waited -> half-open",
            "Failed again during half-open -> re-opened",
            f"State: {test_breaker.current_state}",
            "PASS",
        ])

    def test_successful_requests_dont_trip_breaker(self):
        """Normal 200 responses should not affect the breaker."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "ok"}
        mock_response.headers = {}

        with patch("src.core.http_client.requests.request", return_value=mock_response):
            for _ in range(20):
                result = make_request("GET", "http://fake-service/api")
                assert result["status_code"] == 200

        assert _http_breaker.current_state == "closed"

        _write_report("test_successful_requests_dont_trip_breaker", [
            "20 successful requests",
            f"Breaker state: {_http_breaker.current_state}",
            "PASS",
        ])
