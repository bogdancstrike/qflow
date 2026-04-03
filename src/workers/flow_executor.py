"""Kafka worker — consumes flow.tasks.in and executes the resolved pipeline."""

import os
from framework.commons.logger import logger
from framework.tracing import get_tracer
from framework.decorators import (
    kafka_handler,
    retry_to_dlq,
    rate_limit,
)

from src.config import Config
from src.services.task_service import update_task_status, get_task
from src.dag.planner import build_execution_plan
from src.dag.runner import run_plan

tracer = get_tracer()

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
    """Execute a DAG plan for a task.

    Message format:
    {
        "task_id": "uuid",
        "input_data": {"text": "..."} | {"file_path": "..."} | {"url": "..."},
        "outputs": ["ner_result", "summary"]
    }
    """
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

        update_task_status(task_id, "RUNNING")

        try:
            plan = build_execution_plan(message)
            context = dict(message.get("input_data", {}))
            
            result = run_plan(plan, context)

            span.set_attribute("task.status", "COMPLETED")
            update_task_status(
                task_id,
                "COMPLETED",
                final_output=result.get("outputs", {})
            )

            logger.info(f"[FLOW_EXECUTOR] Task {task_id} completed successfully")
            return {"task_id": task_id, "status": "COMPLETED", "result": result}

        except Exception as e:
            logger.error(f"[FLOW_EXECUTOR] Task {task_id} failed: {e}")
            span.set_attribute("task.status", "FAILED")
            span.set_attribute("task.error", str(e))
            update_task_status(
                task_id,
                "FAILED",
                error={"message": str(e)}
            )
            raise
