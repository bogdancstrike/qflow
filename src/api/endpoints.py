"""HTTP endpoint handlers for the AI Flow Orchestrator."""

import json
import os
import uuid

from flask import request as flask_request

from framework.commons.logger import logger
from framework.tracing import get_tracer

from src.config import Config
from src.services.task_service import (
    create_task, get_task, list_tasks, delete_task, get_task_step_logs,
)
from src.security.sanitize import (
    sanitize_text_input, sanitize_filename, validate_outputs
)
from src.api.rate_limit import rate_limit

tracer = get_tracer()

def _json():
    return flask_request.get_json(force=True, silent=False)

def tasks_handler(app, operation, request, **kwargs):
    """POST /api/v1/tasks — Create a new task.
    GET  /api/v1/tasks — List tasks with filters.
    """
    if flask_request.method == "POST":
        return _task_create()
    else:
        return _task_list()

def task_detail_handler(app, operation, request, **kwargs):
    """GET    /api/v1/tasks/<task_id> — Get task status and result.
    DELETE /api/v1/tasks/<task_id> — Cancel/delete a task.
    """
    task_id = kwargs.get("task_id") or flask_request.view_args.get("task_id")
    if not task_id:
        return {"message": "task_id is required"}, 400

    if flask_request.method == "DELETE":
        return _task_delete(task_id)
    else:
        return _task_get(task_id)


@rate_limit
def _task_create():
    """Create a new task."""
    with tracer.start_as_current_span("api.task_create") as span:
        return _task_create_inner(span)


def _task_create_inner(span):
    content_type = flask_request.content_type or ""

    # Parse and sanitize input
    input_data = {}
    outputs = []
    
    try:
        if "multipart/form-data" in content_type:
            outputs_str = flask_request.form.get("outputs")
            if not outputs_str:
                # Fallback to legacy desired_output
                outputs_str = flask_request.form.get("desired_output")
            
            if outputs_str:
                if outputs_str.startswith("["):
                    outputs = json.loads(outputs_str)
                else:
                    outputs = [outputs_str]
                    
            file = flask_request.files.get("file")
            if not file:
                return {"message": "No file uploaded", "errors": ["file is required"]}, 400

            os.makedirs(Config.UPLOAD_DIR, exist_ok=True)
            safe_filename = sanitize_filename(file.filename)
            filename = f"{uuid.uuid4()}_{safe_filename}"
            file_path = os.path.join(Config.UPLOAD_DIR, filename)
            file.save(file_path)

            input_data = {"file_path": file_path, "original_filename": safe_filename}
        else:
            data = _json()
            input_data = data.get("input_data", {})
            outputs = data.get("outputs", [])
            if not outputs and "desired_output" in data:
                outputs = [data["desired_output"]]
            
            # If text, sanitize it
            if "text" in input_data:
                input_data["text"] = sanitize_text_input(input_data["text"])
                
        # Validate outputs
        validate_outputs(outputs)
        
    except ValueError as e:
        return {"message": "Validation failed", "errors": [str(e)]}, 400
    except Exception as e:
        return {"message": "Error parsing request", "errors": [str(e)]}, 400

    try:
        task = create_task(input_data, outputs)
    except ValueError as e:
        return {"message": str(e), "errors": [str(e)]}, 400

    span.set_attribute("task.id", task["id"])

    # Publish to Kafka
    try:
        from framework.streams.kafka_client import KafkaClient
        kafka = KafkaClient(bootstrap_servers=Config.KAFKA_BOOTSTRAP_SERVERS, security_protocol=None)
        kafka.put_message(
            Config.KAFKA_TASK_TOPIC_IN,
            json.dumps({
                "task_id": task["id"],
                "input_data": input_data,
                "outputs": outputs
            }),
            key=task["id"],
        )
        logger.info(f"[API] Published task {task['id']} to {Config.KAFKA_TASK_TOPIC_IN}")
    except Exception as e:
        logger.error(f"[API] Failed to publish task to Kafka: {e}")

    return task, 201


def _task_list():
    """List tasks with optional filters."""
    with tracer.start_as_current_span("api.task_list") as span:
        status = flask_request.args.get("status")
        limit = int(flask_request.args.get("limit", 50))
        cursor = flask_request.args.get("cursor")
        sort = flask_request.args.get("sort", "created_at:desc")
        created_after = flask_request.args.get("created_after")
        created_before = flask_request.args.get("created_before")

        res = list_tasks(status=status, limit=limit, cursor=cursor, sort=sort,
                           created_after=created_after, created_before=created_before)
        return res


def _task_get(task_id: str):
    """Get task by ID with step logs."""
    with tracer.start_as_current_span("api.task_get") as span:
        span.set_attribute("task.id", task_id)
        task = get_task(task_id)
        if task is None:
            return {"message": f"Task {task_id} not found"}, 404

        task["step_logs"] = get_task_step_logs(task_id)
        return task


def _task_delete(task_id: str):
    """Delete/cancel a task."""
    deleted = delete_task(task_id)
    if not deleted:
        return {"message": f"Task {task_id} not found"}, 404

    return {"message": f"Task {task_id} deleted"}, 200
