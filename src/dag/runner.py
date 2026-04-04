"""DAG runner — executes an ExecutionPlan using gevent for parallel branches.

Phase 1 (ingest) steps run sequentially in the main greenlet.
Phase 2 (analysis) branches run in parallel as gevent greenlets, each with
a shallow-copied execution context to prevent cross-branch mutation.
Results from all branches are merged into a single output dict keyed by output_type.
"""

import time
from copy import copy

import gevent

from framework.commons.logger import logger
from framework.tracing import get_tracer

from src.dag.catalogue import NodeDef
from src.dag.planner import ExecutionPlan
from src.dag.executors.node_executor import execute_node
from src.services.task_service import update_task_status

tracer = get_tracer()


class DAGExecutionError(RuntimeError):
    """Raised when the DAG runner encounters an unrecoverable error."""
    pass


def run_plan(plan: ExecutionPlan, context: dict, task_id: str = None) -> dict:
    """Execute a complete ExecutionPlan.

    Args:
        plan: The ExecutionPlan built by the planner.
        context: A mutable dict holding all intermediate data
                 (populated from input_data initially).
        task_id: Optional task ID for logging/DB updates.

    Returns:
        Merged result dict keyed by output_type.
    """
    with tracer.start_as_current_span("dag.run_plan") as span:
        span.set_attribute("dag.input_type", plan.input_type)
        span.set_attribute("dag.branches", len(plan.branches))
        span.set_attribute("dag.ingest_steps", len(plan.ingest_steps))

        # Phase 1 — Ingest (sequential)
        if plan.ingest_steps:
            logger.info(f"[DAG] Phase 1: {len(plan.ingest_steps)} ingest step(s)")
            for node in plan.ingest_steps:
                _execute_step(node, context, task_id)

        # Phase 2 — Analysis branches (parallel via gevent)
        logger.info(f"[DAG] Phase 2: {len(plan.branches)} branch(es) in parallel")

        if len(plan.branches) == 1:
            # Single branch — no need for greenlet overhead
            branch = plan.branches[0]
            branch_ctx = copy(context)
            branch_result = _run_branch(branch.output_type, branch.steps, branch_ctx, task_id)
            _merge_context(context, branch_ctx)
            return branch_result

        # Multiple branches — fan out with gevent
        greenlets = []
        branch_contexts = []
        for branch in plan.branches:
            branch_ctx = copy(context)
            branch_contexts.append(branch_ctx)
            g = gevent.spawn(
                _run_branch, branch.output_type, branch.steps, branch_ctx, task_id
            )
            greenlets.append(g)

        gevent.joinall(greenlets, raise_error=False)

        # Collect results and check for errors
        merged_result = {}
        errors = []
        for i, g in enumerate(greenlets):
            branch = plan.branches[i]
            if g.exception is not None:
                errors.append(f"{branch.output_type}: {g.exception}")
                logger.error(f"[DAG] Branch '{branch.output_type}' failed: {g.exception}")
            else:
                merged_result.update(g.value)
                _merge_context(context, branch_contexts[i])

        if errors:
            raise DAGExecutionError(
                f"{len(errors)} branch(es) failed: {'; '.join(errors)}"
            )

        return merged_result


def _run_branch(output_type: str, steps: list, context: dict, task_id: str = None) -> dict:
    """Execute a single analysis branch and return its result."""
    with tracer.start_as_current_span(f"dag.branch.{output_type}") as span:
        span.set_attribute("branch.output_type", output_type)
        span.set_attribute("branch.steps", len(steps))

        logger.info(f"[DAG] Branch '{output_type}': {[s.node_id for s in steps]}")

        result = None
        for node in steps:
            result = _execute_step(node, context, task_id)

        return {output_type: result}


def _execute_step(node: NodeDef, context: dict, task_id: str = None):
    """Execute a single node, updating the context with its output."""
    with tracer.start_as_current_span(f"dag.step.{node.node_id}") as span:
        span.set_attribute("node.id", node.node_id)
        span.set_attribute("node.phase", node.phase)

        start_time = time.time()
        logger.info(f"[DAG] Executing node '{node.node_id}'")

        try:
            result = execute_node(node, context)
            duration_ms = int((time.time() - start_time) * 1000)

            # Store result in context under the node's output_type
            context[node.output_type] = result

            span.set_attribute("node.status", "SUCCESS")
            span.set_attribute("node.duration_ms", duration_ms)
            logger.info(f"[DAG] Node '{node.node_id}' completed ({duration_ms}ms)")

            # Log step to DB
            if task_id:
                _log_step(task_id, node.node_id, "SUCCESS", result, duration_ms)

            return result

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            span.set_attribute("node.status", "FAILED")
            span.set_attribute("node.error", str(e))
            logger.error(f"[DAG] Node '{node.node_id}' failed ({duration_ms}ms): {e}")

            if task_id:
                _log_step(task_id, node.node_id, "FAILED", None, duration_ms, error=str(e))

            raise


def _merge_context(target: dict, source: dict):
    """Merge branch context back into the main context (new keys only)."""
    for key, value in source.items():
        if key not in target:
            target[key] = value


def _log_step(task_id, node_id, status, output, duration_ms, error=None):
    """Write step execution to task_step_logs table."""
    try:
        from src.models.task import get_session
        from src.models.task_step_log import TaskStepLog

        session = get_session()
        log = TaskStepLog(
            task_id=task_id,
            task_ref=node_id,
            task_type="DAG_NODE",
            status=status,
            response_payload=output if isinstance(output, dict) else {"result": output},
            error_message=error,
            duration_ms=duration_ms,
        )
        session.add(log)
        session.commit()
        session.close()
    except Exception as e:
        logger.warning(f"[DAG] Failed to log step {node_id}: {e}")
