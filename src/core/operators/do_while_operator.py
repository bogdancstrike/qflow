"""DO_WHILE operator — looping execution while condition is true."""
import time

from framework.commons.logger import logger

from src.core.operators.base import BaseOperator
from src.core.expression_evaluator import evaluate_condition
from src.config import Config


class DoWhileOperator(BaseOperator):
    def execute(self, task_def: dict, context, task_id: str = None) -> dict:
        task_ref = task_def.get("task_ref", "unknown")
        loop_condition = task_def.get("loop_condition", "false")
        loop_over = task_def.get("loop_over", [])
        max_iterations = task_def.get("max_iterations", Config.MAX_LOOP_ITERATIONS)

        from src.core.executor import execute_task_list

        iteration = 0
        all_results = []

        while True:
            time.sleep(0.05)
            iteration += 1

            # Store iteration counter in context for use by loop tasks
            context.set_step_output(task_ref, {"iteration": iteration, "total_pages": max_iterations})

            logger.info(f"[DO_WHILE] {task_ref}: iteration {iteration}")

            execute_task_list(loop_over, context, task_id)

            # Collect iteration results
            iter_results = {}
            for t in loop_over:
                ref = t.get("task_ref")
                if ref and ref in context.steps:
                    iter_results[ref] = context.steps[ref].get("output")
            all_results.append(iter_results)

            # Check max iterations
            if iteration >= max_iterations:
                logger.warning(f"[DO_WHILE] {task_ref}: max iterations ({max_iterations}) reached, stopping")
                break

            # Evaluate loop condition
            if not evaluate_condition(loop_condition, context):
                logger.info(f"[DO_WHILE] {task_ref}: condition false, exiting loop")
                break

        return {"iterations": iteration, "results": all_results}
