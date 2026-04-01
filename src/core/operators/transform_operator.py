"""TRANSFORM operator — inline data transformation without external calls."""

from framework.commons.logger import logger

from src.core.operators.base import BaseOperator
from src.core.interpolator import interpolate


class TransformOperator(BaseOperator):
    def execute(self, task_def: dict, context, task_id: str = None) -> dict:
        task_ref = task_def.get("task_ref", "unknown")
        input_params = task_def.get("input_parameters", {})
        expression = task_def.get("expression")

        # Resolve input parameters
        resolved_inputs = interpolate(input_params, context)

        if expression is None:
            # If no expression, the resolved inputs are the output
            logger.info(f"[TRANSFORM] {task_ref}: passthrough resolved inputs")
            return resolved_inputs

        if isinstance(expression, str):
            # Simple JSONPath-style expression — extract from resolved inputs
            from src.utils.jsonpath import extract
            result = extract(resolved_inputs, expression)
            logger.info(f"[TRANSFORM] {task_ref}: extracted via '{expression}'")
            return result

        if isinstance(expression, dict):
            # Template-based expression — interpolate using resolved inputs as additional context
            # Replace $.field references with values from resolved_inputs
            result = _resolve_expression_dict(expression, resolved_inputs)
            logger.info(f"[TRANSFORM] {task_ref}: resolved expression dict")
            return result

        return resolved_inputs


def _resolve_expression_dict(expr, inputs):
    """Resolve a dict expression where $.field references point to the inputs."""
    if isinstance(expr, dict):
        return {k: _resolve_expression_dict(v, inputs) for k, v in expr.items()}
    elif isinstance(expr, list):
        return [_resolve_expression_dict(item, inputs) for item in expr]
    elif isinstance(expr, str) and expr.startswith("$."):
        from src.utils.jsonpath import extract
        return extract(inputs, expr)
    else:
        return expr
