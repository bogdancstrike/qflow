"""Kafka worker — consumes flow.tasks.in and executes DAG execution plans.

Each task has an execution_plan (built by the DAG planner at creation time).
The worker reconstructs the plan, runs it via the DAG runner, and updates
the task status in PostgreSQL.
"""

from framework.commons.logger import logger
from framework.tracing import get_tracer
from framework.decorators import (
    kafka_handler,
    retry_to_dlq,
    rate_limit,
)

from src.config import Config
from src.services.task_service import update_task_status, get_task

tracer = get_tracer()

# Reference to Kafka consumer for readiness checks (set by ETL framework)
_kafka_consumer = None


def _get_kafka_consumer_ref():
    """Get the Kafka consumer reference for health checks."""
    return _kafka_consumer


@kafka_handler(
    name="flow_executor",
    topics_in=[Config.KAFKA_TASK_TOPIC_IN],
    topics_out=[Config.KAFKA_TASK_TOPIC_OUT],
    max_workers=10,
    bulk_mode=False,
    metadatas={"worker": "flow_executor"},
)
@retry_to_dlq(
    max_attempts=3,
    dlq_topic=Config.KAFKA_DLQ_TOPIC,
    retry_count_field="retry_count",
)
@rate_limit(rps=100, burst=100)
def flow_executor(message: dict, consumer_name: str, metadatas: dict) -> dict:
    """Execute a DAG execution plan for a task."""
    task_id = message.get("task_id")
    if not task_id:
        logger.error("[FLOW_EXECUTOR] Message missing task_id, skipping")
        return {"error": "missing task_id"}

    with tracer.start_as_current_span("flow_executor") as span:
        span.set_attribute("task.id", task_id)

        logger.info(f"[FLOW_EXECUTOR] Processing task {task_id}")

        task = get_task(task_id)
        if task is None:
            logger.error(f"[FLOW_EXECUTOR] Task {task_id} not found in DB")
            span.set_attribute("task.error", "task not found")
            return {"error": "task not found"}

        if not task.get("execution_plan"):
            logger.error(f"[FLOW_EXECUTOR] Task {task_id} has no execution plan")
            update_task_status(task_id, "FAILED", error={"message": "No execution plan"})
            return {"error": "no execution plan"}

        return _execute_dag(task, message, span)


def _execute_dag(task: dict, message: dict, span):
    """Execute a task using the DAG runner."""
    task_id = task["id"]

    from src.dag.planner import ExecutionPlan, ExecutionBranch, PlanningError
    from src.dag.catalogue import get_node
    from src.dag.runner import run_plan, DAGExecutionError

    update_task_status(task_id, "RUNNING")

    try:
        # Reconstruct the ExecutionPlan from the stored dict
        plan_dict = task["execution_plan"]
        plan = _reconstruct_plan(plan_dict)

        # Build initial context from input_data
        input_data = task.get("input_data", {})
        context = dict(input_data)

        # Add the detected input type's value to context
        if plan.input_type == "youtube_url" and "url" in input_data:
            context["youtube_url"] = input_data["url"]
        elif plan.input_type == "audio_path" and "file_path" in input_data:
            context["audio_path"] = input_data["file_path"]

        result = run_plan(plan, context, task_id)

        span.set_attribute("task.status", "COMPLETED")
        update_task_status(
            task_id,
            "COMPLETED",
            final_output=result,
        )

        logger.info(f"[FLOW_EXECUTOR] Task {task_id} completed")
        return {"task_id": task_id, "status": "COMPLETED", "result": result}

    except (DAGExecutionError, PlanningError, Exception) as e:
        logger.error(f"[FLOW_EXECUTOR] Task {task_id} failed: {e}")
        span.set_attribute("task.status", "FAILED")
        span.set_attribute("task.error", str(e))
        update_task_status(
            task_id,
            "FAILED",
            error={"message": str(e)},
        )
        raise


def _reconstruct_plan(plan_dict: dict):
    """Reconstruct an ExecutionPlan from its serialised dict."""
    from src.dag.planner import ExecutionPlan, ExecutionBranch
    from src.dag.catalogue import get_node

    ingest_steps = []
    for node_id in plan_dict.get("ingest_steps", []):
        node = get_node(node_id)
        if node is None:
            raise ValueError(f"Unknown node '{node_id}' in stored execution plan")
        ingest_steps.append(node)

    branches = []
    for b in plan_dict.get("branches", []):
        steps = []
        for node_id in b.get("steps", []):
            node = get_node(node_id)
            if node is None:
                raise ValueError(f"Unknown node '{node_id}' in stored execution plan")
            steps.append(node)
        branches.append(ExecutionBranch(output_type=b["output_type"], steps=steps))

    return ExecutionPlan(
        input_type=plan_dict.get("input_type", "text"),
        ingest_steps=ingest_steps,
        branches=branches,
    )
