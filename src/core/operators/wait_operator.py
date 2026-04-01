"""WAIT operator — pauses execution for a timeout or external signal."""

import time

from framework.commons.logger import logger

from src.core.operators.base import BaseOperator


class WaitOperator(BaseOperator):
    def execute(self, task_def: dict, context, task_id: str = None) -> dict:
        task_ref = task_def.get("task_ref", "unknown")
        wait_type = task_def.get("wait_type", "timeout")
        timeout_seconds = task_def.get("timeout_seconds", 60)
        on_timeout = task_def.get("on_timeout", "CONTINUE")

        if wait_type == "timeout":
            logger.info(f"[WAIT] {task_ref}: waiting {timeout_seconds}s (on_timeout={on_timeout})")
            time.sleep(timeout_seconds)
            return {"waited_seconds": timeout_seconds, "result": on_timeout}

        elif wait_type == "signal":
            logger.info(f"[WAIT] {task_ref}: waiting for signal (timeout={timeout_seconds}s)")
            # In a real implementation, this would poll a DB flag or callback endpoint
            # For the PoC, we just wait the timeout
            time.sleep(min(timeout_seconds, 5))  # Cap at 5s for PoC
            return {"waited_seconds": min(timeout_seconds, 5), "result": on_timeout}

        return {"waited_seconds": 0, "result": "UNKNOWN_WAIT_TYPE"}
