"""Business logic for task management — create, query, cancel.

Supports both legacy (input_type + desired_output -> static flow) and
new DAG-based (input_data + outputs -> dynamic execution plan) task creation.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from framework.commons.logger import logger

from src.config import Config
from src.models.task import Task, get_session
from src.models.task_step_log import TaskStepLog


def create_task_dag(input_data: dict, outputs: List[str]) -> dict:
    """Create a task using the dynamic DAG planner.

    Builds an execution plan from input_data + outputs, stores it in the task,
    and returns the task dict. Does NOT publish to Kafka — the API layer does that.
    """
    from src.dag.planner import build_plan, PlanningError
    from src.dag.input_detector import detect_input_type

    plan = build_plan(input_data, outputs)

    task_id = uuid.uuid4()
    session = get_session()
    try:
        task = Task(
            id=task_id,
            input_type=plan.input_type,
            input_data=input_data,
            desired_output=outputs[0] if len(outputs) == 1 else None,
            outputs=outputs,
            execution_plan=plan.to_dict(),
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


def create_task(input_type: str, input_data: dict, desired_output: str) -> dict:
    """Create a task using the legacy static flow resolver.

    Kept for backwards compatibility. New code should use create_task_dag().
    """
    from src.core.resolver import resolve_flow
    from src.templating.registry import get_flow

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
            outputs=[desired_output],
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


def get_task(task_id: str) -> Optional[dict]:
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
               desired_output: str = None, limit: int = 50, offset: int = 0,
               cursor: str = None, sort: str = "created_at:desc",
               created_after: str = None, created_before: str = None) -> dict:
    """List tasks with cursor-based pagination.

    Returns a dict with keys: tasks, next_cursor, has_more.
    """
    session = get_session()
    try:
        query = session.query(Task)

        # Filters
        if status:
            query = query.filter(Task.status == status)
        if input_type:
            query = query.filter(Task.input_type == input_type)
        if desired_output:
            query = query.filter(Task.desired_output == desired_output)
        if created_after:
            try:
                dt = datetime.fromisoformat(created_after)
                query = query.filter(Task.created_at >= dt)
            except ValueError:
                pass
        if created_before:
            try:
                dt = datetime.fromisoformat(created_before)
                query = query.filter(Task.created_at <= dt)
            except ValueError:
                pass

        # Sort
        sort_col, sort_dir = _parse_sort(sort)
        if sort_dir == "asc":
            order_expr = sort_col.asc()
        else:
            order_expr = sort_col.desc()
        query = query.order_by(order_expr)

        # Cursor-based pagination
        if cursor:
            cursor_task = session.query(Task).filter(Task.id == cursor).first()
            if cursor_task:
                if sort_dir == "desc":
                    query = query.filter(Task.created_at < cursor_task.created_at)
                else:
                    query = query.filter(Task.created_at > cursor_task.created_at)

        # Cap limit
        limit = min(limit, 200)

        # Fetch one extra to determine has_more
        tasks = query.limit(limit + 1).all()
        has_more = len(tasks) > limit
        tasks = tasks[:limit]

        task_dicts = [t.to_dict() for t in tasks]
        next_cursor = task_dicts[-1]["id"] if has_more and task_dicts else None

        return {
            "tasks": task_dicts,
            "next_cursor": next_cursor,
            "has_more": has_more,
        }
    finally:
        session.close()


def _parse_sort(sort_str: str):
    """Parse 'column:direction' into (Column, direction)."""
    parts = sort_str.split(":")
    col_name = parts[0] if parts else "created_at"
    direction = parts[1] if len(parts) > 1 else "desc"

    col_map = {
        "created_at": Task.created_at,
        "updated_at": Task.updated_at,
        "status": Task.status,
    }
    col = col_map.get(col_name, Task.created_at)
    return col, direction


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

        session.query(TaskStepLog).filter(TaskStepLog.task_id == task_id).delete()
        session.delete(task)
        session.commit()
        return True
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_task_step_logs(task_id: str, limit: int = 100, cursor: str = None) -> dict:
    """Get step logs for a task with cursor pagination."""
    session = get_session()
    try:
        query = (
            session.query(TaskStepLog)
            .filter(TaskStepLog.task_id == task_id)
            .order_by(TaskStepLog.created_at.asc())
        )

        if cursor:
            cursor_log = session.query(TaskStepLog).filter(TaskStepLog.id == cursor).first()
            if cursor_log:
                query = query.filter(TaskStepLog.created_at > cursor_log.created_at)

        limit = min(limit, 200)
        logs = query.limit(limit + 1).all()
        has_more = len(logs) > limit
        logs = logs[:limit]

        log_dicts = [log.to_dict() for log in logs]
        next_cursor = log_dicts[-1]["id"] if has_more and log_dicts else None

        return {
            "logs": log_dicts,
            "next_cursor": next_cursor,
            "has_more": has_more,
        }
    finally:
        session.close()
