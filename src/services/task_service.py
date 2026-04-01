"""Business logic for task management — create, query, cancel."""

import json
import uuid
from datetime import datetime, timezone

from framework.commons.logger import logger

from src.config import Config
from src.core.resolver import resolve_flow, is_valid_combination
from src.templating.registry import get_flow
from src.models.task import Task, get_session
from src.models.task_step_log import TaskStepLog


def create_task(input_type: str, input_data: dict, desired_output: str) -> dict:
    """Create a new task record and return its dict representation.

    Does NOT publish to Kafka — that's done by the API layer after this.
    """
    # Resolve the flow
    flow_id = resolve_flow(input_type, desired_output)
    flow_def = get_flow(flow_id)

    if flow_def is None:
        raise ValueError(f"Flow definition '{flow_id}' not found in registry")

    task_id = uuid.uuid4()
    session = get_session()
    try:
        task = Task(
            id=task_id,
            input_type=input_type,
            input_data=input_data,
            desired_output=desired_output,
            resolved_flow=flow_id,
            resolved_flow_definition=flow_def,
            status="PENDING",
            step_results={},
            workflow_variables={},
            retry_count=0,
        )
        session.add(task)
        session.commit()
        result = task.to_dict()
        return result
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_task(task_id: str) -> dict:
    """Get a task by ID."""
    session = get_session()
    try:
        task = session.query(Task).filter(Task.id == task_id).first()
        if task is None:
            return None
        return task.to_dict()
    finally:
        session.close()


def list_tasks(status: str = None, input_type: str = None,
               desired_output: str = None, limit: int = 50, offset: int = 0) -> list:
    """List tasks with optional filters."""
    session = get_session()
    try:
        query = session.query(Task)
        if status:
            query = query.filter(Task.status == status)
        if input_type:
            query = query.filter(Task.input_type == input_type)
        if desired_output:
            query = query.filter(Task.desired_output == desired_output)
        query = query.order_by(Task.created_at.desc()).offset(offset).limit(limit)
        return [t.to_dict() for t in query.all()]
    finally:
        session.close()


def update_task_status(task_id: str, status: str, current_step: str = None,
                       step_results: dict = None, workflow_variables: dict = None,
                       final_output: dict = None, error: dict = None,
                       retry_count: int = None):
    """Update task status and related fields."""
    session = get_session()
    try:
        task = session.query(Task).filter(Task.id == task_id).first()
        if task is None:
            logger.warning(f"[TASK_SERVICE] Task {task_id} not found for update")
            return

        task.status = status
        task.updated_at = datetime.now(timezone.utc)

        if current_step is not None:
            task.current_step = current_step
        if step_results is not None:
            task.step_results = step_results
        if workflow_variables is not None:
            task.workflow_variables = workflow_variables
        if final_output is not None:
            task.final_output = final_output
        if error is not None:
            task.error = error
        if retry_count is not None:
            task.retry_count = retry_count

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def delete_task(task_id: str) -> bool:
    """Delete (cancel) a task."""
    session = get_session()
    try:
        task = session.query(Task).filter(Task.id == task_id).first()
        if task is None:
            return False

        # Delete step logs first
        session.query(TaskStepLog).filter(TaskStepLog.task_id == task_id).delete()
        session.delete(task)
        session.commit()
        return True
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_task_step_logs(task_id: str) -> list:
    """Get step logs for a task."""
    session = get_session()
    try:
        logs = (
            session.query(TaskStepLog)
            .filter(TaskStepLog.task_id == task_id)
            .order_by(TaskStepLog.created_at.asc())
            .all()
        )
        return [log.to_dict() for log in logs]
    finally:
        session.close()
