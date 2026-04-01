"""SET_VARIABLE operator — sets/mutates workflow variables."""

from framework.commons.logger import logger

from src.core.operators.base import BaseOperator
from src.core.interpolator import interpolate


class SetVariableOperator(BaseOperator):
    def execute(self, task_def: dict, context, task_id: str = None) -> dict:
        task_ref = task_def.get("task_ref", "unknown")
        input_params = task_def.get("input_parameters", {})

        resolved = interpolate(input_params, context)

        for key, value in resolved.items():
            context.set_variable(key, value)
            logger.debug(f"[SET_VARIABLE] {task_ref}: {key} = {value}")

        logger.info(f"[SET_VARIABLE] {task_ref}: set {len(resolved)} variable(s)")
        return resolved
