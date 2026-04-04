"""Node executor — dispatches a NodeDef to the appropriate execution handler.

Handles HTTP calls to AI microservices and TRANSFORM-type local processing.
The translate node has a conditional skip: if context["lang"] is already "en",
it promotes text directly to text_en without calling the translation service.
"""

import time
import random

from framework.commons.logger import logger
from framework.tracing import get_tracer

from src.config import Config
from src.dag.catalogue import NodeDef

tracer = get_tracer()


def execute_node(node: NodeDef, context: dict):
    """Execute a single node against the current context.

    Args:
        node: The NodeDef from the catalogue.
        context: Mutable dict with all intermediate data.

    Returns:
        The node's output value (stored in context[node.output_type] by the runner).
    """
    if node.executor_type == "TRANSFORM":
        return _execute_transform(node, context)
    elif node.executor_type == "HTTP":
        return _execute_http(node, context)
    else:
        raise ValueError(f"Unknown executor_type '{node.executor_type}' for node '{node.node_id}'")


def _execute_transform(node: NodeDef, context: dict):
    """Execute a TRANSFORM node (local processing, no HTTP call)."""
    handler = node.executor_config.get("handler")
    if handler == "ytdlp":
        from src.dag.executors.ytdlp_executor import execute_ytdlp
        return execute_ytdlp(node, context)

    # Generic passthrough transform
    logger.info(f"[NODE] Transform '{node.node_id}': passthrough")
    return context.get(node.input_type)


def _execute_http(node: NodeDef, context: dict):
    """Execute an HTTP node — calls an AI microservice.

    In DEV_MODE, returns the mock response instead.
    """
    config = node.executor_config

    # Conditional skip for translate: if language is already English
    conditional_skip = config.get("conditional_skip_on")
    if conditional_skip == "lang_is_en":
        lang_meta = context.get("lang_meta")
        lang = None
        if isinstance(lang_meta, dict):
            lang = lang_meta.get("language")
        elif isinstance(lang_meta, str):
            lang = lang_meta

        if lang == "en":
            logger.info(f"[NODE] '{node.node_id}': skipping — language is already 'en'")
            # Promote text directly to text_en
            return context.get("text")

    # DEV_MODE: return mock response
    if Config.DEV_MODE and node.mock_response is not None:
        delay = random.uniform(0.3, 1.5)
        logger.info(f"[NODE-MOCK] '{node.node_id}': returning mock (delay={delay:.1f}s)")
        time.sleep(delay)
        return node.mock_response

    # Real HTTP call
    from src.core.http_client import make_request

    url_env = config.get("url_env", "AI_SERVICE_URL")
    base_url = getattr(Config, url_env, Config.AI_SERVICE_URL)
    path = config.get("path", "")
    url = f"{base_url}{path}"

    body = _build_body(config.get("body_template", {}), context)
    method = config.get("method", "POST")
    timeout = config.get("timeout_seconds", 120)

    logger.info(f"[NODE] '{node.node_id}': {method} {url}")

    result = make_request(
        method=method,
        url=url,
        headers={},
        body=body,
        timeout_seconds=timeout,
    )

    # Extract the relevant output field from the response
    response_body = result.get("body", result)
    output_field = config.get("output_field")
    if output_field and isinstance(response_body, dict):
        return response_body.get(output_field, response_body)

    return response_body


def _build_body(template: dict, context: dict) -> dict:
    """Build an HTTP request body by substituting {field} placeholders from context.

    Supports simple {key} replacement where key is looked up in context.
    """
    body = {}
    for key, value in template.items():
        if isinstance(value, str) and value.startswith("{") and value.endswith("}"):
            ref = value[1:-1]
            resolved = context.get(ref)
            # For nested dict values, extract the relevant field
            if isinstance(resolved, dict):
                # Try common fields: text, language, etc.
                body[key] = resolved.get(key, resolved)
            else:
                body[key] = resolved
        else:
            body[key] = value
    return body
