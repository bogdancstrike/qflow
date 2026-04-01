"""HTTP client for external service calls.

Implements retry and circuit breaker using tenacity and pybreaker directly,
since the installed QF wheel only ships Kafka-runtime policy decorators.
"""

import requests
import tenacity
import pybreaker

from framework.commons.logger import logger


class HttpClientError(Exception):
    def __init__(self, message, status_code=None, response_body=None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


# Circuit breaker instance for HTTP service calls
_http_breaker = pybreaker.CircuitBreaker(
    fail_max=10,
    reset_timeout=30,
    name="http-service-breaker",
)


@tenacity.retry(
    stop=tenacity.stop_after_attempt(3),
    wait=tenacity.wait_fixed(1.0),
    retry=tenacity.retry_if_exception_type(HttpClientError),
    reraise=True,
)
def make_request(method: str, url: str, headers: dict = None, body=None,
                 timeout_seconds: int = 120, retryable_status_codes=None) -> dict:
    """Make an HTTP request with retry and circuit breaker.

    Returns a dict with:
      - status_code: int
      - body: parsed JSON or raw text
      - headers: response headers
    """
    if retryable_status_codes is None:
        retryable_status_codes = [500, 502, 503, 429]

    return _http_breaker.call(
        _do_request, method, url, headers, body, timeout_seconds, retryable_status_codes
    )


def _do_request(method, url, headers, body, timeout_seconds, retryable_status_codes):
    try:
        response = requests.request(
            method=method.upper(),
            url=url,
            headers=headers,
            json=body if method.upper() in ("POST", "PUT", "PATCH") else None,
            params=body if method.upper() == "GET" else None,
            timeout=timeout_seconds,
        )

        try:
            response_body = response.json()
        except (ValueError, requests.exceptions.JSONDecodeError):
            response_body = response.text

        result = {
            "status_code": response.status_code,
            "body": response_body,
            "headers": dict(response.headers),
        }

        if response.status_code in retryable_status_codes:
            raise HttpClientError(
                f"HTTP {response.status_code} from {url}",
                status_code=response.status_code,
                response_body=response_body,
            )

        if response.status_code >= 400:
            raise HttpClientError(
                f"HTTP {response.status_code} from {url} (non-retryable)",
                status_code=response.status_code,
                response_body=response_body,
            )

        return result

    except requests.exceptions.Timeout:
        raise HttpClientError(f"Timeout after {timeout_seconds}s calling {url}")
    except requests.exceptions.ConnectionError as e:
        raise HttpClientError(f"Connection error calling {url}: {e}")
