"""FORK_JOIN operator — parallel execution of multiple branches."""

from concurrent.futures import ThreadPoolExecutor, as_completed

from framework.commons.logger import logger
from framework.tracing import get_tracer

from src.core.operators.base import BaseOperator
from src.core.context import ExecutionContext
from src.config import Config

tracer = get_tracer()


class ForkJoinOperator(BaseOperator):
    def execute(self, task_def: dict, context, task_id: str = None) -> dict:
        task_ref = task_def.get("task_ref", "unknown")
        fork_tasks = task_def.get("fork_tasks", [])
        join_on = task_def.get("join_on", [])

        logger.info(f"[FORK_JOIN] {task_ref}: forking {len(fork_tasks)} branches, join_on={join_on}")

        from src.core.executor import execute_task_list

        results = {}
        errors = {}

        def run_branch(branch_index, branch_tasks):
            """Execute a branch in its own thread, sharing the parent context."""
            try:
                execute_task_list(branch_tasks, context, task_id)
                # Collect outputs from branch tasks
                branch_outputs = {}
                for t in branch_tasks:
                    ref = t.get("task_ref")
                    if ref and ref in context.steps:
                        branch_outputs[ref] = context.steps[ref].get("output")
                return branch_index, branch_outputs
            except Exception as e:
                return branch_index, {"error": str(e)}

        max_workers = min(Config.FORK_JOIN_MAX_WORKERS, len(fork_tasks))

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(run_branch, i, branch): i
                for i, branch in enumerate(fork_tasks)
            }

            for future in as_completed(futures):
                branch_idx, branch_result = future.result()
                if isinstance(branch_result, dict) and "error" in branch_result:
                    errors[branch_idx] = branch_result["error"]
                else:
                    results.update(branch_result)

        if errors:
            logger.warning(f"[FORK_JOIN] {task_ref}: {len(errors)} branch(es) failed: {errors}")

        # Check join_on requirements
        if join_on:
            missing = [ref for ref in join_on if ref not in context.steps]
            if missing:
                raise RuntimeError(f"FORK_JOIN {task_ref}: missing join_on tasks: {missing}")

        logger.info(f"[FORK_JOIN] {task_ref}: all branches completed")
        return {"branches_completed": len(results), "branch_results": results}
