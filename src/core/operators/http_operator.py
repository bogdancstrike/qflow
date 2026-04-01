"""HTTP operator — calls external services (AI microservices, webhooks, REST APIs)."""

import time
import random

from framework.commons.logger import logger
from framework.tracing import get_tracer

from src.core.operators.base import BaseOperator
from src.core.interpolator import interpolate
from src.core.http_client import make_request, HttpClientError
from src.utils.jsonpath import extract
from src.config import Config

tracer = get_tracer()


class HttpOperator(BaseOperator):
    def execute(self, task_def: dict, context, task_id: str = None) -> dict:
        task_ref = task_def.get("task_ref", "unknown")
        input_params = interpolate(task_def.get("input_parameters", {}), context)
        http_request = input_params.get("http_request", input_params)

        # DEV_MODE: return mock response
        if Config.DEV_MODE and "mock_response" in task_def:
            with tracer.start_as_current_span(f"http_mock.{task_ref}") as span:
                span.set_attribute("http.mock", True)
                span.set_attribute("step.ref", task_ref)
                delay = random.uniform(0.5, 2.0)
                logger.info(f"[MOCK] {task_ref}: returning mock response (delay={delay:.1f}s)")
                time.sleep(delay)
                mock = task_def["mock_response"]
                if isinstance(mock, str):
                    mock = interpolate(mock, context)
                return mock

        method = http_request.get("method", "POST")
        url = http_request.get("url", "")
        headers = http_request.get("headers", {})
        body = http_request.get("body", {})
        timeout = http_request.get("timeout_seconds", 120)

        # Get retry config from task def
        retry_cfg = task_def.get("retry", {})
        retryable_codes = retry_cfg.get("retryable_status_codes", [500, 502, 503, 429])

        with tracer.start_as_current_span(f"http_request.{task_ref}") as span:
            span.set_attribute("http.method", method)
            span.set_attribute("http.url", url)
            span.set_attribute("step.ref", task_ref)

            logger.info(f"[HTTP] {task_ref}: {method} {url}")

            result = make_request(
                method=method,
                url=url,
                headers=headers,
                body=body,
                timeout_seconds=timeout,
                retryable_status_codes=retryable_codes,
            )

            span.set_attribute("http.status_code", result.get("status_code", 0))

            # Apply output_mapping if specified
            output_mapping = task_def.get("output_mapping")
            if output_mapping:
                mapped = {}
                for key, path in output_mapping.items():
                    mapped[key] = extract({"response": result}, path)
                return mapped

            return result.get("body", result)
