"""Kafka worker — consumes flow.tasks.in and executes the resolved pipeline.

This is the main worker that bridges Kafka dispatch with the flow executor engine.
"""

import os

from framework.commons.logger import logger
from framework.tracing import get_tracer
from framework.decorators import (
    kafka_handler,
    retry_to_dlq,
    rate_limit,
)

from src.config import Config
from src.core.context import ExecutionContext
from src.core.executor import execute_flow
from src.core.operators.base import TerminateFlowException
from src.services.task_service import update_task_status, get_task

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
    """Execute a flow pipeline for a task.

    Message format:
    {
        "task_id": "uuid",
        "text": "...",           # for text input
        "file_path": "...",      # for file_upload input
        "youtube_url": "...",    # for youtube_link input
        "desired_output": "ner"
    }
    """
    task_id = message.get("task_id")
    if not task_id:
        logger.error("[FLOW_EXECUTOR] Message missing task_id, skipping")
        return {"error": "missing task_id"}

    with tracer.start_as_current_span("flow_executor") as span:
        span.set_attribute("task.id", task_id)
        span.set_attribute("task.desired_output", message.get("desired_output", ""))

        logger.info(f"[FLOW_EXECUTOR] Processing task {task_id}")

        # Get the task from DB to retrieve the flow definition
        task = get_task(task_id)
        if task is None:
            logger.error(f"[FLOW_EXECUTOR] Task {task_id} not found in DB")
            span.set_attribute("task.error", "task not found")
            return {"error": "task not found"}

        flow_def = task.get("resolved_flow_definition")
        if not flow_def:
            logger.error(f"[FLOW_EXECUTOR] Task {task_id} has no resolved flow definition")
            update_task_status(task_id, "FAILED", error={"message": "No flow definition"})
            span.set_attribute("task.error", "no flow definition")
            return {"error": "no flow definition"}

        flow_id = flow_def.get("flow_id", "unknown")
        span.set_attribute("flow.id", flow_id)

        # Build workflow input from the message
        workflow_input = {k: v for k, v in message.items() if k not in ("task_id", "retry_count")}

        # Build env context from Config
        env = {
            "AI_SERVICE_URL": Config.AI_SERVICE_URL,
            "AI_STT_URL": Config.AI_STT_URL,
            "AI_STT_TOKEN": Config.AI_STT_TOKEN,
            "AI_NER_URL": Config.AI_NER_URL,
            "AI_TRANSLATE_URL": Config.AI_TRANSLATE_URL,
            "AI_LANGDETECT_URL": Config.AI_LANGDETECT_URL,
            "AI_SENTIMENT_URL": Config.AI_SENTIMENT_URL,
            "AI_SUMMARY_URL": Config.AI_SUMMARY_URL,
            "AI_TAXONOMY_URL": Config.AI_TAXONOMY_URL,
            "DEV_MODE": str(Config.DEV_MODE),
        }

        context = ExecutionContext(workflow_input, env)

        # Update status to RUNNING
        update_task_status(task_id, "RUNNING")

        try:
            result = execute_flow(flow_def, context, task_id)

            # Check for termination
            if isinstance(result, dict) and result.get("_terminated"):
                status = result.get("status", "TERMINATED")
                span.set_attribute("task.status", status)
                update_task_status(
                    task_id,
                    status,
                    step_results=context.steps,
                    workflow_variables=context.variables,
                    final_output=result.get("output"),
                    error={"reason": result.get("reason")},
                )
            else:
                span.set_attribute("task.status", "COMPLETED")
                span.set_attribute("task.steps_count", len(context.steps))
                update_task_status(
                    task_id,
                    "COMPLETED",
                    step_results=context.steps,
                    workflow_variables=context.variables,
                    final_output=result,
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
                step_results=context.steps,
                workflow_variables=context.variables,
                error={"message": str(e), "current_step": task.get("current_step")},
            )
            raise
