"""SWITCH operator — conditional branching based on expression evaluation."""

from framework.commons.logger import logger
from framework.tracing import get_tracer

from src.core.operators.base import BaseOperator
from src.core.expression_evaluator import evaluate_expression
from src.core.interpolator import interpolate

tracer = get_tracer()


class SwitchOperator(BaseOperator):
    def execute(self, task_def: dict, context, task_id: str = None) -> dict:
        task_ref = task_def.get("task_ref", "unknown")
        expression = task_def.get("expression", "")

        with tracer.start_as_current_span(f"switch.{task_ref}") as span:
            # Resolve the expression value
            value = evaluate_expression(expression, context)
            value_str = str(value) if value is not None else ""

            decision_cases = task_def.get("decision_cases", {})
            default_case = task_def.get("default_case", [])

            # Find matching branch
            branch_tasks = decision_cases.get(value_str)
            branch_taken = value_str

            if branch_tasks is None:
                branch_tasks = default_case
                branch_taken = "default"

            span.set_attribute("switch.expression_value", value_str)
            span.set_attribute("switch.branch_taken", branch_taken)
            logger.info(f"[SWITCH] {task_ref}: expression='{value_str}', branch='{branch_taken}'")

            # Execute the branch tasks using the executor (lazy import to avoid circular)
            from src.core.executor import execute_task_list

            if branch_tasks:
                execute_task_list(branch_tasks, context, task_id)

            return {"branch_taken": branch_taken, "expression_value": value_str}
