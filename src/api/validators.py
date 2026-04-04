"""Input validation for API requests.

Validates DAG-based task creation: input_data (dict) + outputs (list of output types).
Includes security sanitization (path traversal, template injection, size limits).
"""

import os
import re

from src.dag.catalogue import get_all_valid_output_types

# Security patterns
_TEMPLATE_INJECTION_RE = re.compile(r"\{\{.*?\}\}|\{%.*?%\}")
_PATH_TRAVERSAL_CHARS = re.compile(r"[;\x00]")

# Sensitive headers to redact from logs
SENSITIVE_HEADERS = frozenset({
    "authorization", "x-api-key", "cookie", "set-cookie",
    "proxy-authorization", "x-csrf-token",
})


def validate_task_input(input_data, outputs: list) -> list:
    """Validate task creation input (input_data + outputs).

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
