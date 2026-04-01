"""LOG operator — structured logging / audit point."""

from framework.commons.logger import logger

from src.core.operators.base import BaseOperator
from src.core.interpolator import interpolate


class LogOperator(BaseOperator):
    def execute(self, task_def: dict, context, task_id: str = None) -> dict:
        task_ref = task_def.get("task_ref", "unknown")
        input_params = task_def.get("input_parameters", {})

        resolved = interpolate(input_params, context)

        log_message = resolved.pop("message", f"LOG step: {task_ref}")
        logger.info(f"[LOG] {task_ref}: {log_message} | {resolved}")

        return {"message": log_message, **resolved}
