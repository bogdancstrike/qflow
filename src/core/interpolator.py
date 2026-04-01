"""Variable interpolation engine for {{...}} expressions.

Supported patterns:
  {{workflow.input.<field>}}       — Workflow-level input
  {{steps.<task_ref>.output.<field>}} — Output of a previous step
  {{env.<VAR>}}                    — Environment variable
  {{workflow.variables.<var>}}     — Variables set via SET_VARIABLE
  {{now()}}                        — Current ISO timestamp
  {{len(expr)}}                    — Length of string/array
"""

import os
import re
from datetime import datetime, timezone
from copy import deepcopy

_PATTERN = re.compile(r"\{\{(.+?)\}\}")
_LEN_PATTERN = re.compile(r"^len\((.+)\)$")


def interpolate(template, context):
    """Recursively interpolate all {{...}} expressions in a template.

    `template` can be a string, dict, list, or primitive.
    `context` is an ExecutionContext instance.
    """
    if isinstance(template, str):
        return _interpolate_string(template, context)
    elif isinstance(template, dict):
        return {k: interpolate(v, context) for k, v in template.items()}
    elif isinstance(template, list):
        return [interpolate(item, context) for item in template]
    else:
        return template


def _interpolate_string(text: str, context):
    """Interpolate a single string. If the entire string is one expression, return the raw value."""
    # If the entire string is a single expression, return the resolved value directly
    # (preserves type — not stringified)
    match = re.fullmatch(r"\{\{(.+?)\}\}", text.strip())
    if match:
        return _resolve_expression(match.group(1).strip(), context)

    # Otherwise, substitute all {{...}} within the string
    def replacer(m):
        val = _resolve_expression(m.group(1).strip(), context)
        if val is None:
            return ""
        return str(val)

    return _PATTERN.sub(replacer, text)


def _resolve_expression(expr: str, context):
    """Resolve a single expression."""
    # now()
    if expr == "now()":
        return datetime.now(timezone.utc).isoformat()

    # len(...)
    len_match = _LEN_PATTERN.match(expr)
    if len_match:
        inner = _resolve_expression(len_match.group(1).strip(), context)
        if inner is not None and hasattr(inner, "__len__"):
            return len(inner)
        return 0

    # Check for comparison operators BEFORE prefix-based matching
    # so that "steps.x.output.y != 'en'" is handled as a comparison
    for op in (" != ", " == ", " >= ", " <= ", " > ", " < "):
        if op in expr:
            return _eval_comparison(expr, context)

    # env.<VAR>
    if expr.startswith("env."):
        var_name = expr[4:]
        if hasattr(context, "env") and var_name in context.env:
            return context.env[var_name]
        return os.getenv(var_name, "")

    # workflow.input.<field>
    if expr.startswith("workflow.input."):
        path = expr[len("workflow.input."):]
        return _deep_get(context.workflow_input, path)

    # workflow.variables.<var>
    if expr.startswith("workflow.variables."):
        path = expr[len("workflow.variables."):]
        return _deep_get(context.variables, path)

    # steps.<task_ref>.output.<field>
    if expr.startswith("steps."):
        parts = expr.split(".", 3)  # steps, task_ref, output, field_path
        if len(parts) >= 3:
            task_ref = parts[1]
            step = context.steps.get(task_ref)
            if step is None:
                return None
            if parts[2] == "output":
                if len(parts) > 3:
                    return _deep_get(step.get("output"), parts[3])
                return step.get("output")
            return _deep_get(step, ".".join(parts[2:]))

    return expr


def _deep_get(data, path: str):
    """Navigate nested dicts/lists using dot notation."""
    if data is None or not path:
        return data
    parts = path.split(".")
    current = data
    for part in parts:
        if current is None:
            return None
        # Handle list index
        if isinstance(current, list):
            try:
                current = current[int(part)]
                continue
            except (ValueError, IndexError):
                return None
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _eval_comparison(expr: str, context):
    """Evaluate simple comparison expressions."""
    for op, py_op in [(" != ", "!="), (" == ", "=="), (" >= ", ">="), (" <= ", "<="), (" > ", ">"), (" < ", "<")]:
        if op in expr:
            left_str, right_str = expr.split(op, 1)
            left = _resolve_value(left_str.strip(), context)
            right = _resolve_value(right_str.strip(), context)
            # Type-coerce for numeric comparison
            left, right = _coerce_types(left, right)
            if py_op == "!=":
                return left != right
            elif py_op == "==":
                return left == right
            elif py_op == ">=":
                return left >= right
            elif py_op == "<=":
                return left <= right
            elif py_op == ">":
                return left > right
            elif py_op == "<":
                return left < right
    return expr


def _resolve_value(val_str: str, context):
    """Resolve a value that might be a literal or a reference."""
    # String literal
    if (val_str.startswith("'") and val_str.endswith("'")) or \
       (val_str.startswith('"') and val_str.endswith('"')):
        return val_str[1:-1]
    # Boolean
    if val_str.lower() == "true":
        return True
    if val_str.lower() == "false":
        return False
    # Number
    try:
        if "." in val_str:
            return float(val_str)
        return int(val_str)
    except ValueError:
        pass
    # Reference
    return _resolve_expression(val_str, context)


def _coerce_types(left, right):
    """Attempt to coerce both sides to comparable types."""
    if isinstance(left, str) and isinstance(right, (int, float)):
        try:
            left = type(right)(left)
        except (ValueError, TypeError):
            pass
    elif isinstance(right, str) and isinstance(left, (int, float)):
        try:
            right = type(left)(right)
        except (ValueError, TypeError):
            pass
    return left, right
