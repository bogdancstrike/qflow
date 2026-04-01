"""Expression evaluator for SWITCH conditions and DO_WHILE loop conditions.

Evaluates expressions like:
  - Simple value: "{{steps.language_detect.output.language}}" -> "en"
  - Comparison: "{{steps.count.output.value}} < 10" -> True/False
  - Equality check done by SWITCH: expression value matched against decision_cases keys
"""

from src.core.interpolator import interpolate


def evaluate_expression(expression, context):
    """Evaluate an expression in the given context.

    Returns the resolved value (for SWITCH matching) or a boolean (for DO_WHILE conditions).
    """
    result = interpolate(expression, context)

    # If the result is already a boolean, return it
    if isinstance(result, bool):
        return result

    # If string, try to interpret as boolean
    if isinstance(result, str):
        if result.lower() in ("true", "1", "yes"):
            return True
        if result.lower() in ("false", "0", "no", ""):
            return False

    return result


def evaluate_condition(condition, context) -> bool:
    """Evaluate a condition expression, always returning a boolean."""
    result = evaluate_expression(condition, context)
    return bool(result)
