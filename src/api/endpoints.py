"""HTTP endpoint handlers for the AI Flow Orchestrator.

These functions are registered via maps/endpoint.json (QF Framework dynamic endpoints).
Each function signature follows the QF pattern: (app, operation, request, **kwargs).

Because QF creates one Resource per endpoint entry, combined handlers dispatch
by HTTP method when multiple methods share the same URL.
"""
import json
import os
import uuid

from flask import jsonify, request as flask_request

from framework.commons.logger import logger
from framework.tracing import get_tracer

from src.config import Config
from src.api.validators import validate_task_input
from src.services.task_service import (
    create_task, get_task, list_tasks, delete_task, get_task_step_logs,
)
from src.templating.registry import list_primitives, list_flows
from src.core.resolver import get_valid_outputs, FLOW_STRATEGIES

tracer = get_tracer()


def _json():
    return flask_request.get_json(force=True, silent=False)


# ---------------------------------------------------------------------------
# Combined handlers (POST+GET on same URL, GET+DELETE on same URL)
# ---------------------------------------------------------------------------

def tasks_handler(app, operation, request, **kwargs):
    """POST /api/tasks — Create a new task.
    GET  /api/tasks — List tasks with filters.
    """
    if flask_request.method == "POST":
        return _task_create()
    else:
        return _task_list()


def task_detail_handler(app, operation, request, **kwargs):
    """GET    /api/tasks/<task_id> — Get task status and result.
    DELETE /api/tasks/<task_id> — Cancel/delete a task.
    """
    task_id = kwargs.get("task_id") or flask_request.view_args.get("task_id")
    if not task_id:
        return jsonify({"message": "task_id is required"}), 400

    if flask_request.method == "DELETE":
        return _task_delete(task_id)
    else:
        return _task_get(task_id)


# ---------------------------------------------------------------------------
# System endpoints
# ---------------------------------------------------------------------------

def health_check(app, operation, request, **kwargs):
    """GET /api/health — Healthcheck."""
    return jsonify({
        "status": "healthy",
        "dev_mode": Config.DEV_MODE,
        "primitives": len(list_primitives()),
        "flows": len(list_flows()),
        "supported_outputs": get_valid_outputs(),
    })


def flow_strategies(app, operation, request, **kwargs):
    """GET /api/flows — List all registered flow strategies."""
    strategies = [
        {"input_type": it, "desired_output": do, "flow_id": fid}
        for (it, do), fid in sorted(FLOW_STRATEGIES.items())
    ]
    return jsonify({"strategies": strategies, "count": len(strategies)})


# ---------------------------------------------------------------------------
# Internal implementations
# ---------------------------------------------------------------------------

def _task_create():
    """Create a new task."""
    with tracer.start_as_current_span("api.task_create") as span:
        return _task_create_inner(span)


def _task_create_inner(span):
    content_type = flask_request.content_type or ""

    # Handle file upload
    if "multipart/form-data" in content_type:
        input_type = flask_request.form.get("input_type", "file_upload")
        desired_output = flask_request.form.get("desired_output")
        file = flask_request.files.get("file")

        if not file:
            return jsonify({"message": "No file uploaded", "errors": ["file is required"]}), 400

        os.makedirs(Config.UPLOAD_DIR, exist_ok=True)
        filename = f"{uuid.uuid4()}_{file.filename}"
        file_path = os.path.join(Config.UPLOAD_DIR, filename)
        file.save(file_path)

        data = {
            "input_type": input_type,
            "input_data": {"file_path": file_path, "original_filename": file.filename},
            "desired_output": desired_output,
        }
    else:
        data = _json()

    # Validate
    errors = validate_task_input(data)
    if errors:
        return jsonify({"message": "Validation failed", "errors": errors}), 400

    # Normalize input_data
    input_data = data.get("input_data")
    if isinstance(input_data, str):
        if data["input_type"] == "text":
            input_data = {"text": input_data}
        elif data["input_type"] == "youtube_link":
            input_data = {"youtube_url": input_data}

    try:
        task = create_task(data["input_type"], input_data, data["desired_output"])
    except ValueError as e:
        return jsonify({"message": str(e), "errors": [str(e)]}), 400

    span.set_attribute("task.id", task["id"])
    span.set_attribute("task.input_type", data["input_type"])
    span.set_attribute("task.desired_output", data["desired_output"])

    # Publish to Kafka for async processing
    try:
        from framework.streams.kafka_client import KafkaClient
        kafka = KafkaClient(bootstrap_servers=Config.KAFKA_BOOTSTRAP_SERVERS, security_protocol=None)
        kafka.put_message(
            Config.KAFKA_TASK_TOPIC_IN,
            json.dumps({
                "task_id": task["id"],
                **input_data,
                "desired_output": data["desired_output"]
            }),
            key=task["id"],
        )
        logger.info(f"[API] Published task {task['id']} to {Config.KAFKA_TASK_TOPIC_IN}")
    except Exception as e:
        logger.error(f"[API] Failed to publish task to Kafka: {e}")

    return jsonify(task), 201


def _task_list():
    """List tasks with optional filters."""
    with tracer.start_as_current_span("api.task_list") as span:
        status = flask_request.args.get("status")
        input_type = flask_request.args.get("input_type")
        desired_output = flask_request.args.get("desired_output")
        limit = int(flask_request.args.get("limit", 50))
        offset = int(flask_request.args.get("offset", 0))

        tasks = list_tasks(status=status, input_type=input_type,
                           desired_output=desired_output, limit=limit, offset=offset)
        return jsonify({"tasks": tasks, "count": len(tasks), "limit": limit, "offset": offset})


def _task_get(task_id: str):
    """Get task by ID with step logs."""
    with tracer.start_as_current_span("api.task_get") as span:
        span.set_attribute("task.id", task_id)
        task = get_task(task_id)
        if task is None:
            return jsonify({"message": f"Task {task_id} not found"}), 404

        task["step_logs"] = get_task_step_logs(task_id)
        return jsonify(task)


def _task_delete(task_id: str):
    """Delete/cancel a task."""
    deleted = delete_task(task_id)
    if not deleted:
        return jsonify({"message": f"Task {task_id} not found"}), 404

    return jsonify({"message": f"Task {task_id} deleted"}), 200
