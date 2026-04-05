"""HTTP endpoint handlers for the AI Flow Orchestrator.

These functions are registered via maps/endpoint.json (QF Framework dynamic endpoints).
Each function signature follows the QF pattern: (app, operation, request, **kwargs).

All task creation uses the DAG planner. The planner auto-detects input type from
input_data and builds an execution plan for the requested outputs.
"""
import json
import os
import time
import uuid

from flask import request as flask_request

from framework.commons.logger import logger
from framework.tracing import get_tracer

from src.config import Config
from src.api.validators import validate_task_input
from src.services.task_service import (
    create_task, get_task, list_tasks, delete_task,
    get_task_step_logs, update_task_status, get_global_stats,
)
from src.dag.catalogue import get_all_valid_output_types
from src.api.rate_limiter import check_rate_limit

tracer = get_tracer()


def _json():
    return flask_request.get_json(force=True, silent=False)


# ---------------------------------------------------------------------------
# Combined handlers (POST+GET on same URL, GET+DELETE on same URL)
# ---------------------------------------------------------------------------

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


def task_step_logs_handler(app, operation, request, **kwargs):
    """GET /api/v1/tasks/<task_id>/logs — Get paginated step logs."""
    task_id = kwargs.get("task_id") or flask_request.view_args.get("task_id")
    if not task_id:
        return {"message": "task_id is required"}, 400

    cursor = flask_request.args.get("cursor")
    limit = int(flask_request.args.get("limit", 100))
    return get_task_step_logs(task_id, limit=limit, cursor=cursor)


# ---------------------------------------------------------------------------
# System endpoints (unversioned)
# ---------------------------------------------------------------------------

def liveness(app, operation, request, **kwargs):
    """GET /api/liveness — K8s liveness probe. Always 200 if process is alive."""
    return {"status": "alive"}


def readiness(app, operation, request, **kwargs):
    """GET /api/readiness — K8s readiness probe. Checks PG and Kafka."""
    checks = {}
    all_ok = True

    # PostgreSQL check
    try:
        from src.models.task import get_engine
        with get_engine().connect() as conn:
            conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as e:
        checks["postgres"] = f"error: {e}"
        all_ok = False

    # Kafka check — verify consumer has assignments
    try:
        from src.workers.flow_executor import _get_kafka_consumer_ref
        consumer = _get_kafka_consumer_ref()
        if consumer and consumer.assignment():
            checks["kafka"] = "ok"
        else:
            checks["kafka"] = "no_assignments"
            all_ok = False
    except Exception:
        checks["kafka"] = "ok"  # Graceful if consumer ref not available

    if all_ok:
        return {"status": "ready", "checks": checks}, 200
    return {"status": "not_ready", "checks": checks}, 503


def health_check(app, operation, request, **kwargs):
    """GET /api/health — Full dependency health report with latencies."""
    checks = {}
    all_ok = True
    any_slow = False

    # PostgreSQL
    try:
        start = time.time()
        from src.models.task import get_engine
        with get_engine().connect() as conn:
            conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        latency_ms = int((time.time() - start) * 1000)
        checks["postgres"] = {"status": "ok", "latency_ms": latency_ms}
        if latency_ms > 500:
            any_slow = True
    except Exception as e:
        checks["postgres"] = {"status": "error", "error": str(e)}
        all_ok = False

    # Redis
    try:
        start = time.time()
        import redis
        r = redis.Redis(
            host=Config.REDIS_HOST,
            port=int(Config.REDIS_PORT),
            db=int(Config.REDIS_DB),
            socket_timeout=5,
        )
        r.ping()
        latency_ms = int((time.time() - start) * 1000)
        checks["redis"] = {"status": "ok", "latency_ms": latency_ms}
        if latency_ms > 500:
            any_slow = True
    except Exception as e:
        checks["redis"] = {"status": "error", "error": str(e)}
        all_ok = False

    # Kafka
    try:
        start = time.time()
        from kafka import KafkaConsumer as _KC
        temp = _KC(
            bootstrap_servers=Config.KAFKA_BOOTSTRAP_SERVERS,
            consumer_timeout_ms=3000,
        )
        temp.topics()
        temp.close()
        latency_ms = int((time.time() - start) * 1000)
        checks["kafka"] = {"status": "ok", "latency_ms": latency_ms}
        if latency_ms > 500:
            any_slow = True
    except Exception as e:
        checks["kafka"] = {"status": "error", "error": str(e)}
        all_ok = False

    if not all_ok:
        overall = "unhealthy"
        status_code = 503
    elif any_slow:
        overall = "degraded"
        status_code = 200
    else:
        overall = "healthy"
        status_code = 200

    return {
        "status": overall,
        "checks": checks,
        "dev_mode": Config.DEV_MODE,
    }, status_code


def flow_strategies(app, operation, request, **kwargs):
    """GET /api/v1/flows — List DAG node catalogue info."""
    from src.dag.catalogue import NODE_CATALOGUE
    nodes = [
        {
            "node_id": n.node_id,
            "phase": n.phase,
            "input_type": n.input_type,
            "output_type": n.output_type,
            "requires_en": n.requires_en,
        }
        for n in NODE_CATALOGUE.values()
    ]
    return {
        "nodes": nodes,
        "valid_outputs": get_all_valid_output_types(),
        "count": len(nodes),
    }


def flow_stats_handler(app, operation, request, **kwargs):
    """GET /api/v1/stats — Global dashboard statistics."""
    stats = get_global_stats()
    # Explicitly set headers to prevent any intermediate caching
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0"
    }
    return stats, 200, headers


# ---------------------------------------------------------------------------
# Internal implementations
# ---------------------------------------------------------------------------

def _task_create():
    """Create a new task via the DAG planner."""
    with tracer.start_as_current_span("api.task_create") as span:
        content_type = flask_request.content_type or ""

        # Handle file upload
        if "multipart/form-data" in content_type:
            return _task_create_file_upload(span)

        data = _json()
        input_data = data.get("input_data", {})
        outputs = data.get("outputs", [])

        # Support shorthand: "output" or "desired_output" as single output
        if not outputs:
            single = data.get("output_type") or data.get("desired_output")
            if single:
                outputs = [single]

        # Support input_type hint: wrap raw input_data based on type
        input_type = data.get("input_type")
        if input_type and isinstance(input_data, str):
            if input_type == "text":
                input_data = {"text": input_data}
            elif input_type in ("youtube_link", "youtube_url"):
                input_data = {"url": input_data}
        elif isinstance(input_data, str):
            # Auto-wrap plain string as text
            input_data = {"text": input_data}

        errors = validate_task_input(input_data, outputs)
        if errors:
            return {"message": "Validation failed", "errors": errors}, 400

        try:
            from src.dag.planner import PlanningError
            task = create_task(input_data, outputs)
        except (PlanningError, ValueError) as e:
            return {"message": str(e), "errors": [str(e)]}, 400

        span.set_attribute("task.id", task["id"])
        span.set_attribute("task.input_type", task["input_type"])

        _publish_to_kafka(task, input_data)
        return task, 201


def _task_create_file_upload(span):
    """Handle file upload task creation."""
    desired_output = flask_request.form.get("desired_output")
    outputs_str = flask_request.form.get("outputs", "")
    file = flask_request.files.get("file")

    if not file:
        return {"message": "No file uploaded", "errors": ["file is required"]}, 400

    os.makedirs(Config.UPLOAD_DIR, exist_ok=True)
    filename = f"{uuid.uuid4()}_{os.path.basename(file.filename)}"
    file_path = os.path.join(Config.UPLOAD_DIR, filename)
    file.save(file_path)

    input_data = {"file_path": file_path}

    # Parse outputs
    outputs = []
    if outputs_str:
        outputs = [o.strip() for o in outputs_str.split(",") if o.strip()]
    elif desired_output:
        outputs = [desired_output]

    if not outputs:
        return {"message": "outputs or desired_output is required"}, 400

    try:
        from src.dag.planner import PlanningError
        task = create_task(input_data, outputs)
    except (PlanningError, ValueError) as e:
        return {"message": str(e), "errors": [str(e)]}, 400

    span.set_attribute("task.id", task["id"])
    span.set_attribute("task.mode", "dag_upload")

    _publish_to_kafka(task, input_data)
    return task, 201


def _publish_to_kafka(task: dict, input_data: dict):
    """Publish a task to Kafka for async processing."""
    try:
        from framework.streams.kafka_client import KafkaClient
        kafka = KafkaClient(
            bootstrap_servers=Config.KAFKA_BOOTSTRAP_SERVERS,
            security_protocol=None,
        )
        kafka.put_message(
            Config.KAFKA_TASK_TOPIC_IN,
            json.dumps({
                "task_id": task["id"],
                **(input_data or {}),
                "outputs": task.get("outputs", []),
            }),
            key=task["id"],
        )
        logger.info(f"[API] Published task {task['id']} to {Config.KAFKA_TASK_TOPIC_IN}")
    except Exception as e:
        logger.error(f"[API] Failed to publish task to Kafka: {e}")


def _task_list():
    """List tasks with page-based pagination."""
    with tracer.start_as_current_span("api.task_list") as span:
        status = flask_request.args.get("status")
        input_type = flask_request.args.get("input_type")
        page = int(flask_request.args.get("page", 1))
        size = int(flask_request.args.get("size", 50))
        sort = flask_request.args.get("sort", "created_at:desc")
        created_after = flask_request.args.get("created_after")
        created_before = flask_request.args.get("created_before")

        result = list_tasks(
            status=status,
            input_type=input_type,
            page=page,
            size=size,
            sort=sort,
            created_after=created_after,
            created_before=created_before,
        )
        return result


def _task_get(task_id: str):
    """Get task by ID (step logs are paginated separately)."""
    with tracer.start_as_current_span("api.task_get") as span:
        span.set_attribute("task.id", task_id)
        task = get_task(task_id)
        if task is None:
            return {"message": f"Task {task_id} not found"}, 404
        return task


def _task_delete(task_id: str):
    """Delete/cancel a task."""
    deleted = delete_task(task_id)
    if not deleted:
        return {"message": f"Task {task_id} not found"}, 404
    return {"message": f"Task {task_id} deleted"}, 200
