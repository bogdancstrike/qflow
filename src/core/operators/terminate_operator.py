"""TERMINATE operator — immediately halts flow execution."""

from framework.commons.logger import logger

from src.core.operators.base import BaseOperator, TerminateFlowException
from src.core.interpolator import interpolate


class TerminateOperator(BaseOperator):
    def execute(self, task_def: dict, context, task_id: str = None) -> dict:
        task_ref = task_def.get("task_ref", "unknown")
        status = task_def.get("termination_status", "FAILED")
        reason = task_def.get("termination_reason", "Flow terminated")
        output = task_def.get("output", {})

        resolved_output = interpolate(output, context)
        resolved_reason = interpolate(reason, context) if isinstance(reason, str) else reason

        logger.warning(f"[TERMINATE] {task_ref}: status={status}, reason={resolved_reason}")

        raise TerminateFlowException(
            status=status,
            reason=str(resolved_reason),
            output=resolved_output,
        )
