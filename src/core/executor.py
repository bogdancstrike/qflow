"""Flow executor — main loop engine that dispatches tasks to operators.

Processes the task list from a flow definition, handling each task type
through the appropriate operator.
"""

import time
from datetime import datetime, timezone

from framework.commons.logger import logger
from framework.tracing import get_tracer

from src.core.context import ExecutionContext

tracer = get_tracer()
from src.core.interpolator import interpolate
from src.core.operators.base import TerminateFlowException
from src.core.operators.http_operator import HttpOperator
from src.core.operators.switch_operator import SwitchOperator
from src.core.operators.fork_join_operator import ForkJoinOperator
from src.core.operators.do_while_operator import DoWhileOperator
from src.core.operators.set_variable_operator import SetVariableOperator
from src.core.operators.transform_operator import TransformOperator
from src.core.operators.sub_workflow_operator import SubWorkflowOperator
from src.core.operators.terminate_operator import TerminateOperator
from src.core.operators.wait_operator import WaitOperator
from src.core.operators.log_operator import LogOperator

# Operator dispatch registry
OPERATORS = {
    "HTTP": HttpOperator(),
    "SWITCH": SwitchOperator(),
    "FORK_JOIN": ForkJoinOperator(),
    "DO_WHILE": DoWhileOperator(),
    "SET_VARIABLE": SetVariableOperator(),
    "TRANSFORM": TransformOperator(),
    "SUB_WORKFLOW": SubWorkflowOperator(),
    "TERMINATE": TerminateOperator(),
    "WAIT": WaitOperator(),
    "LOG": LogOperator(),
}


def execute_flow(flow_def: dict, context: ExecutionContext, task_id: str = None) -> dict:
    """Execute a complete flow definition.

    Returns the final output (resolved output_parameters or last step output).
    """
    flow_id = flow_def.get("flow_id", "unknown")
    tasks = flow_def.get("tasks", [])
    output_parameters = flow_def.get("output_parameters")

    with tracer.start_as_current_span("execute_flow") as span:
        span.set_attribute("flow.id", flow_id)
        span.set_attribute("flow.tasks_count", len(tasks))

        try:
            execute_task_list(tasks, context, task_id)
        except TerminateFlowException as e:
            logger.warning(f"Flow terminated: status={e.status}, reason={e.reason}")
            span.set_attribute("flow.terminated", True)
            return {"_terminated": True, "status": e.status, "reason": e.reason, "output": e.output}

        # Resolve output_parameters if defined
        if output_parameters:
            return interpolate(output_parameters, context)

        # Return last step output if no output_parameters
        if tasks:
            last_ref = tasks[-1].get("task_ref")
            if last_ref and last_ref in context.steps:
                return context.steps[last_ref].get("output", {})

        return {}


def execute_task_list(tasks: list, context: ExecutionContext, task_id: str = None):
    """Execute a list of tasks sequentially, updating context after each step."""
    for task_def in tasks:
        execute_single_task(task_def, context, task_id)


def execute_single_task(task_def: dict, context: ExecutionContext, task_id: str = None):
    """Execute a single task, dispatching to the correct operator."""
    task_ref = task_def.get("task_ref", "unknown")
    task_type = task_def.get("type", "HTTP")
    optional = task_def.get("optional", False)

    operator = OPERATORS.get(task_type)
    if operator is None:
        raise ValueError(f"Unknown task type: {task_type} (task_ref: {task_ref})")

    logger.info(f"[EXECUTOR] Starting task: {task_ref} (type={task_type})")

    with tracer.start_as_current_span(f"execute_step.{task_ref}") as span:
        span.set_attribute("step.ref", task_ref)
        span.set_attribute("step.type", task_type)

        start_time = time.time()
        try:
            output = operator.execute(task_def, context, task_id)
            duration_ms = int((time.time() - start_time) * 1000)

            context.set_step_output(task_ref, output, status="SUCCESS", duration_ms=duration_ms)
            span.set_attribute("step.status", "SUCCESS")
            span.set_attribute("step.duration_ms", duration_ms)

            # Log step to DB if we have a task_id
            if task_id:
                _log_step(task_id, task_ref, task_type, "SUCCESS", output, duration_ms)

            logger.info(f"[EXECUTOR] Completed task: {task_ref} ({duration_ms}ms)")

        except TerminateFlowException:
            duration_ms = int((time.time() - start_time) * 1000)
            span.set_attribute("step.status", "TERMINATED")
            if task_id:
                _log_step(task_id, task_ref, task_type, "TERMINATED", None, duration_ms)
            raise

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"[EXECUTOR] Failed task: {task_ref} ({duration_ms}ms) — {e}")
            span.set_attribute("step.status", "FAILED")
            span.set_attribute("step.error", str(e))

            if task_id:
                _log_step(task_id, task_ref, task_type, "FAILED", None, duration_ms, error=str(e))

            if optional:
                logger.warning(f"[EXECUTOR] Task {task_ref} is optional, continuing flow")
                context.set_step_output(task_ref, {"error": str(e)}, status="FAILED", duration_ms=duration_ms)
            else:
                raise


def _log_step(task_id, task_ref, task_type, status, output, duration_ms, error=None):
    """Write step execution to task_step_logs table."""
    try:
        from src.models.task import get_session
        from src.models.task_step_log import TaskStepLog

        session = get_session()
        log = TaskStepLog(
            task_id=task_id,
            task_ref=task_ref,
            task_type=task_type,
            status=status,
            response_payload=output if isinstance(output, dict) else {"result": output},
            error_message=error,
            duration_ms=duration_ms,
        )
        session.add(log)
        session.commit()
        session.close()
    except Exception as e:
        logger.warning(f"[EXECUTOR] Failed to log step {task_ref}: {e}")
