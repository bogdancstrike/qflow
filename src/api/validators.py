"""Input validation for API requests.

Covers both legacy (input_type + desired_output) and DAG (input_data + outputs) modes,
plus security sanitization (path traversal, template injection, size limits).
"""

import os
import re

from src.dag.catalogue import get_all_valid_output_types

# Legacy validation
from src.core.resolver import is_valid_combination, get_valid_outputs, get_valid_input_types_for_output

VALID_INPUT_TYPES = {"file_upload", "text", "youtube_link"}

# Security patterns
_TEMPLATE_INJECTION_RE = re.compile(r"\{\{.*?\}\}|\{%.*?%\}")
_PATH_TRAVERSAL_CHARS = re.compile(r"[;\x00]")

# Sensitive headers to redact from logs
SENSITIVE_HEADERS = frozenset({
    "authorization", "x-api-key", "cookie", "set-cookie",
    "proxy-authorization", "x-csrf-token",
})


def validate_task_input(data: dict) -> list:
    """Validate legacy task creation input (input_type + desired_output).

    Returns list of error messages (empty if valid).
    """
    errors = []

    input_type = data.get("input_type")
    if not input_type:
        errors.append("'input_type' is required")
    elif input_type not in VALID_INPUT_TYPES:
        errors.append(f"Invalid input_type '{input_type}'. Valid: {sorted(VALID_INPUT_TYPES)}")

    desired_output = data.get("desired_output")
    if not desired_output:
        errors.append("'desired_output' is required")
    elif desired_output not in get_valid_outputs():
        errors.append(
            f"Invalid desired_output '{desired_output}'. "
            f"Valid: {get_valid_outputs()}"
        )

    if input_type and desired_output and not errors:
        if not is_valid_combination(input_type, desired_output):
            valid_inputs = get_valid_input_types_for_output(desired_output)
            errors.append(
                f"Input type '{input_type}' is not supported for desired_output "
                f"'{desired_output}'. Valid input types: {valid_inputs}"
            )

    # Validate input_data based on input_type
    if not errors:
        input_data = data.get("input_data")
        if input_type == "text":
            if not input_data or not isinstance(input_data, (str, dict)):
                errors.append("'input_data' must be a non-empty string or JSON object for text input")
            else:
                errors.extend(_validate_text_security(input_data))
        elif input_type == "youtube_link":
            if not input_data or not isinstance(input_data, str):
                errors.append("'input_data' must be a YouTube URL string")
        elif input_type == "file_upload":
            pass  # File uploads handled separately via multipart form

    return errors


def validate_dag_task_input(input_data: dict, outputs: list) -> list:
    """Validate DAG-based task creation input (input_data + outputs).

    Returns list of error messages (empty if valid).
    """
    errors = []

    # Validate input_data
    if not input_data or not isinstance(input_data, dict):
        errors.append("'input_data' must be a non-empty JSON object")
        return errors

    # Validate outputs
    if not outputs or not isinstance(outputs, list):
        errors.append("'outputs' must be a non-empty list of output types")
        return errors

    valid_outputs = get_all_valid_output_types()
    unknown = [o for o in outputs if o not in valid_outputs]
    if unknown:
        errors.append(
            f"Unknown output type(s): {unknown}. Valid: {valid_outputs}"
        )

    # Security: text content
    text = input_data.get("text")
    if text and isinstance(text, str):
        errors.extend(_validate_text_security(text))

    # Security: file path sanitization
    file_path = input_data.get("file_path")
    if file_path and isinstance(file_path, str):
        errors.extend(_validate_file_path(file_path))

    return errors


def _validate_text_security(text_input) -> list:
    """Check text input for template injection patterns."""
    errors = []
    text = text_input if isinstance(text_input, str) else str(text_input)

    if _TEMPLATE_INJECTION_RE.search(text):
        errors.append(
            "Text input contains template injection patterns ({{...}} or {%...%}). "
            "This is not allowed for security reasons."
        )

    return errors


def _validate_file_path(file_path: str) -> list:
    """Sanitize and validate file paths against traversal attacks."""
    errors = []

    if ".." in file_path:
        errors.append("File path contains path traversal sequence '..'")

    if "\x00" in file_path:
        errors.append("File path contains null bytes")

    if _PATH_TRAVERSAL_CHARS.search(file_path):
        errors.append("File path contains suspicious characters")

    return errors


def sanitize_file_path(file_path: str) -> str:
    """Sanitize a file path by extracting just the basename and removing dangerous chars."""
    basename = os.path.basename(file_path)
    basename = basename.replace("\x00", "").replace("..", "")
    return basename


def redact_headers(headers: dict) -> dict:
    """Redact sensitive headers from a dict before storing in logs."""
    if not headers:
        return headers
    redacted = {}
    for key, value in headers.items():
        if key.lower() in SENSITIVE_HEADERS:
            redacted[key] = "***REDACTED***"
        else:
            redacted[key] = value
    return redacted


def validate_mime_type(content_type: str) -> list:
    """Validate that a Content-Type header is for audio/video."""
    errors = []
    if not content_type:
        return errors

    allowed_prefixes = ("audio/", "video/", "application/octet-stream", "multipart/form-data")
    if not any(content_type.startswith(p) for p in allowed_prefixes):
        errors.append(
            f"Unsupported Content-Type '{content_type}'. "
            "Only audio/*, video/*, or multipart/form-data is accepted for file uploads."
        )
    return errors
