"""Stateless subflow workers — generic task executors via Kafka.

Each sub-step in a flow can be dispatched as a stateless Kafka message.
Instead of executing the full pipeline in a single worker, the orchestrator
publishes individual task definitions to Kafka topics where generic workers
pick them up, execute the appropriate primitive (HTTP, TRANSFORM, etc.),
and publish the result back.

This is approach B (Kafka-chained stateless execution) vs. approach A
(inline execution within the flow_executor worker).

Architecture:
    flow.tasks.in                  — main orchestrator input
    flow.step.request.in           — generic HTTP request primitive worker
    flow.step.request.out          — HTTP request result
    flow.step.transform.in/out     — TRANSFORM primitive worker
    flow.step.execute.in/out       — generic task executor (any primitive)

Message format for step workers:
{
    "task_id": "uuid",               # parent task ID
    "task_def": { ... },             # full task definition (type, input_parameters, etc.)
    "workflow_input": { ... },       # original workflow input
    "env": { ... },                  # environment variables
    "prior_steps": {                 # outputs of prior steps for interpolation
        "step_ref": {"output": {...}, "status": "SUCCESS"},
        ...
    }
}

The worker:
1. Rebuilds an ExecutionContext from the message
2. Dispatches to the correct operator based on task_def.type
3. Returns the result with updated prior_steps
"""

from framework.commons.logger import logger
from framework.decorators import kafka_handler, retry_to_dlq, rate_limit

from src.config import Config
from src.core.context import ExecutionContext
from src.core.executor import execute_single_task


def _build_context_from_message(message: dict) -> ExecutionContext:
    """Rebuild an ExecutionContext from a Kafka message."""
    workflow_input = message.get("workflow_input", {})
    env = message.get("env", {})
    prior_steps = message.get("prior_steps", {})

    ctx = ExecutionContext(workflow_input, env)
    for ref, step_data in prior_steps.items():
        output = step_data.get("output", step_data) if isinstance(step_data, dict) else step_data
        ctx.set_step_output(ref, output)

    # Restore workflow variables if present
    for var_name, var_value in message.get("workflow_variables", {}).items():
        ctx.set_variable(var_name, var_value)

    return ctx


def _build_result(message: dict, task_ref: str, ctx: ExecutionContext) -> dict:
    """Build the result message with updated prior steps and variables."""
    step = ctx.steps.get(task_ref, {})
    return {
        "task_id": message.get("task_id"),
        "task_ref": task_ref,
        "output": step.get("output"),
        "status": step.get("status", "SUCCESS"),
        "duration_ms": step.get("duration_ms", 0),
        "workflow_input": message.get("workflow_input", {}),
        "env": message.get("env", {}),
        "prior_steps": {
            **message.get("prior_steps", {}),
            task_ref: {"output": step.get("output"), "status": step.get("status", "SUCCESS")},
        },
        "workflow_variables": ctx.variables,
    }


# ============================================================
# Generic HTTP Request Worker
# Executes ANY HTTP request primitive — the message contains
# the full task definition with url, body, headers, etc.
# This is the "request" primitive, not an AI-specific worker.
# ============================================================

@kafka_handler(
    name="step_http_request",
    topics_in=["flow.step.request.in"],
    topics_out=["flow.step.request.out"],
    max_workers=20,
    bulk_mode=False,
    metadatas={"worker": "step_http_request", "primitive": "HTTP"},
)
@retry_to_dlq(max_attempts=3, dlq_topic="flow.step.request.dlq", retry_count_field="retry_count")
@rate_limit(rps=100, burst=100)
def step_http_request(message: dict, consumer_name: str, metadatas: dict) -> dict:
    """Generic HTTP request worker.

    Executes any HTTP task definition — STT, NER, translate, or any other API.
    The task_def in the message determines what to call.
    """
    task_def = message.get("task_def", {})
    task_ref = task_def.get("task_ref", "unknown")

    logger.info(f"[STEP_HTTP] Executing HTTP request: {task_ref} (task_id={message.get('task_id')})")

    ctx = _build_context_from_message(message)
    execute_single_task(task_def, ctx)

    return _build_result(message, task_ref, ctx)


# ============================================================
# Generic Task Executor Worker
# Executes ANY primitive type — HTTP, TRANSFORM, SET_VARIABLE,
# LOG, SWITCH, etc. The message contains the full task_def.
# ============================================================

@kafka_handler(
    name="step_execute",
    topics_in=["flow.step.execute.in"],
    topics_out=["flow.step.execute.out"],
    max_workers=20,
    bulk_mode=False,
    metadatas={"worker": "step_execute", "primitive": "ANY"},
)
@retry_to_dlq(max_attempts=3, dlq_topic="flow.step.execute.dlq", retry_count_field="retry_count")
@rate_limit(rps=200, burst=200)
def step_execute(message: dict, consumer_name: str, metadatas: dict) -> dict:
    """Generic task executor — handles any primitive type.

    The task_def.type determines which operator runs (HTTP, TRANSFORM,
    SET_VARIABLE, SWITCH, LOG, TERMINATE, etc.).
    """
    task_def = message.get("task_def", {})
    task_ref = task_def.get("task_ref", "unknown")
    task_type = task_def.get("type", "unknown")

    logger.info(
        f"[STEP_EXECUTE] Executing {task_type} task: {task_ref} "
        f"(task_id={message.get('task_id')})"
    )

    ctx = _build_context_from_message(message)
    execute_single_task(task_def, ctx)

    return _build_result(message, task_ref, ctx)
