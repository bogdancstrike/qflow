"""Business logic for task management — create, query, cancel.

All task creation uses the DAG planner: input_data + outputs -> execution plan.
"""

import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from sqlalchemy import func, text
from framework.commons.logger import logger

from src.config import Config
from src.models.task import Task, get_session
from src.models.task_step_log import TaskStepLog


def create_task(input_data: dict, outputs: List[str]) -> dict:
    """Create a task using the DAG planner."""
    from src.dag.planner import build_plan

    plan = build_plan(input_data, outputs)

    task_id = str(uuid.uuid4())
    session = get_session()
    try:
        task = Task(
            id=task_id,
            input_type=plan.input_type,
            input_data=input_data,
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
               page: int = 1, size: int = 50,
               sort: str = "created_at:desc",
               created_after: str = None, created_before: str = None) -> dict:
    """List tasks with page-based pagination."""
    session = get_session()
    try:
        query = session.query(Task)

        # Filters
        if status:
            query = query.filter(Task.status == status)
        if input_type:
            query = query.filter(Task.input_type == input_type)
        if created_after:
            try:
                dt = datetime.fromisoformat(created_after.replace('Z', ''))
                query = query.filter(Task.created_at >= dt)
            except ValueError:
                pass
        if created_before:
            try:
                dt = datetime.fromisoformat(created_before.replace('Z', ''))
                query = query.filter(Task.created_at <= dt)
            except ValueError:
                pass

        # Total count before pagination
        total_count = query.count()

        # Sort
        sort_col, sort_dir = _parse_sort(sort)
        if sort_dir == "asc":
            order_expr = sort_col.asc()
        else:
            order_expr = sort_col.desc()
        query = query.order_by(order_expr)

        # Page-based pagination
        offset = (max(1, page) - 1) * size
        tasks = query.offset(offset).limit(size).all()
        
        task_dicts = [t.to_dict() for t in tasks]
        has_more = total_count > (page * size)

        return {
            "tasks": task_dicts,
            "total_count": total_count,
            "page": page,
            "size": size,
            "has_more": has_more,
        }
    finally:
        session.close()


def get_global_stats() -> dict:
    """Fetch global statistics directly from the database."""
    session = get_session()
    try:
        # Diagnostic: Log real count
        total_in_db = session.query(func.count(Task.id)).scalar() or 0
        logger.info(f"[STATS] Database total task count: {total_in_db}")

        # 1. Total by status
        status_counts = session.query(Task.status, func.count(Task.id)).group_by(Task.status).all()
        by_status = {s: count for s, count in status_counts}
        for s in ["PENDING", "RUNNING", "COMPLETED", "FAILED"]:
            if s not in by_status:
                by_status[s] = 0

        total = sum(by_status.values())

        # 2. Total by input type
        type_counts = session.query(Task.input_type, func.count(Task.id)).group_by(Task.input_type).all()
        by_input_type = {t: count for t, count in type_counts}

        # 2a. Output Type Distribution (Unnesting JSON array)
        by_output_requested = {}
        # Try standard JSON first as it's defined in the model (SQLAlchemy JSON -> PG json)
        try:
            output_counts = session.execute(text(
                "SELECT output_val, count(*) FROM tasks, json_array_elements_text(outputs::json) AS output_val GROUP BY output_val"
            )).all()
            by_output_requested = {row[0]: int(row[1]) for row in output_counts}
        except Exception:
            session.rollback()
            # Try JSONB as fallback
            try:
                output_counts = session.execute(text(
                    "SELECT output_val, count(*) FROM tasks, jsonb_array_elements_text(outputs::jsonb) AS output_val GROUP BY output_val"
                )).all()
                by_output_requested = {row[0]: int(row[1]) for row in output_counts}
            except Exception:
                session.rollback()
                # If both fail (e.g. no data yet or wrong version), we stay silent and return empty
                pass

        # 3. Success rate (overall)
        completed = by_status.get("COMPLETED", 0)
        failed = by_status.get("FAILED", 0)
        finished = completed + failed
        success_rate = round((completed / finished * 100), 1) if finished > 0 else 0

        # 4. Latency stats (completed only)
        # End-to-end latency: updated_at - created_at
        e2e_latency_raw = session.query(
            func.avg(func.extract('epoch', Task.updated_at) - func.extract('epoch', Task.created_at))
        ).filter(Task.status == 'COMPLETED').scalar()
        e2e_latency = float(e2e_latency_raw) if e2e_latency_raw is not None else 0.0

        # Processing Speed (per task): updated_at - started_at
        proc_latency_raw = session.query(
            func.avg(func.extract('epoch', Task.updated_at) - func.extract('epoch', Task.started_at))
        ).filter(Task.status == 'COMPLETED', Task.started_at.isnot(None)).scalar()
        proc_latency = float(proc_latency_raw) if proc_latency_raw is not None else 0.0

        # Queue Latency: started_at - created_at
        queue_latency_raw = session.query(
            func.avg(func.extract('epoch', Task.started_at) - func.extract('epoch', Task.created_at))
        ).filter(Task.started_at.isnot(None)).scalar()
        queue_latency = float(queue_latency_raw) if queue_latency_raw is not None else 0.0
        
        # 5. Success rate by input type
        success_by_type = session.query(
            Task.input_type,
            func.count(Task.id).label('total'),
            func.sum(text("CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END")).label('success')
        ).filter(Task.status.in_(['COMPLETED', 'FAILED'])).group_by(Task.input_type).all()
        
        input_success_rate = []
        for t, tot, s in success_by_type:
            s_val = float(s) if s is not None else 0.0
            input_success_rate.append({
                "type": t, 
                "rate": round((s_val / tot * 100), 1) if tot > 0 else 0
            })

        # 6. Latency by input type
        latency_by_type = session.query(
            Task.input_type,
            func.avg(func.extract('epoch', Task.updated_at) - func.extract('epoch', Task.created_at))
        ).filter(Task.status == 'COMPLETED').group_by(Task.input_type).all()
        
        duration_by_input_type = []
        for t, avg in latency_by_type:
            avg_val = float(avg) if avg is not None else 0.0
            duration_by_input_type.append({
                "type": t, 
                "avgMs": int(avg_val * 1000)
            })

        now = datetime.now(timezone.utc)

        # 7. Volume Stats (Hourly/Daily/Weekly)
        # 7a. Last 60 minutes throughput (Minutely)
        start_1h = now - timedelta(hours=1)
        minutely_stats = session.query(
            func.to_char(Task.created_at, 'HH24:MI').label('minute'),
            Task.status,
            func.count(Task.id)
        ).filter(Task.created_at >= start_1h).group_by('minute', Task.status).all()
        
        minutely_volume_1h = []
        for min_val, status, count in minutely_stats:
            minutely_volume_1h.append({"time": min_val, "status": status, "count": int(count)})

        # 7b. Last 24 hours throughput (Hourly)
        start_24h = now - timedelta(hours=24)
        hourly_stats = session.query(
            func.to_char(Task.created_at, 'YYYY-MM-DD HH24:00').label('hour'),
            Task.status,
            func.count(Task.id)
        ).filter(Task.created_at >= start_24h).group_by('hour', Task.status).all()
        
        hourly_volume_24h = []
        for hr, status, count in hourly_stats:
            hourly_volume_24h.append({"time": hr, "status": status, "count": int(count)})

        # 7c. Queue Latency Trend (Hourly for last 24h)
        queue_latency_trend = session.query(
            func.to_char(Task.created_at, 'YYYY-MM-DD HH24:00').label('hour'),
            func.avg(func.extract('epoch', Task.started_at) - func.extract('epoch', Task.created_at))
        ).filter(Task.created_at >= start_24h, Task.started_at.isnot(None)).group_by('hour').all()

        queue_latency_24h = []
        for hr, avg in queue_latency_trend:
            queue_latency_24h.append({"time": hr, "avgMs": int(float(avg) * 1000) if avg else 0})

        # 8. Last 30 days throughput (Daily)
        start_30d = (now - timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0)
        daily_stats = session.query(
            func.to_char(Task.created_at, 'YYYY-MM-DD').label('day'),
            Task.status,
            func.count(Task.id)
        ).filter(Task.created_at >= start_30d).group_by('day', Task.status).all()
        
        daily_volume_30d = []
        for day, status, count in daily_stats:
            daily_volume_30d.append({"time": day, "status": status, "count": int(count)})

        # 9. Last 12 weeks throughput (Weekly)
        start_12w = (now - timedelta(weeks=12)).replace(hour=0, minute=0, second=0, microsecond=0)
        weekly_stats = session.query(
            func.to_char(Task.created_at, 'IYYY-"W"IW').label('week'),
            Task.status,
            func.count(Task.id)
        ).filter(Task.created_at >= start_12w).group_by('week', Task.status).all()
        
        weekly_volume_12w = []
        for week, status, count in weekly_stats:
            weekly_volume_12w.append({"time": week, "status": status, "count": int(count)})

        # 10. Concurrency (active in last 24h & last 1h)
        concurrency_24h = []
        active_per_hour = {}
        for hr, status, count in hourly_stats:
            if status in ["PENDING", "RUNNING"]:
                active_per_hour[hr] = active_per_hour.get(hr, 0) + int(count)
        for hr in sorted(active_per_hour.keys()):
            concurrency_24h.append({"time": hr, "count": active_per_hour[hr]})

        concurrency_1h = []
        active_per_min = {}
        for min_val, status, count in minutely_stats:
            if status in ["PENDING", "RUNNING"]:
                active_per_min[min_val] = active_per_min.get(min_val, 0) + int(count)
        for min_val in sorted(active_per_min.keys()):
            concurrency_1h.append({"time": min_val, "count": active_per_min[min_val]})

        # 11. TPM (Tasks Per Minute) - Relatable Metrics
        tpm_current_raw = session.query(func.count(Task.id)).filter(Task.created_at >= now - timedelta(minutes=1)).scalar() or 0
        tpm_15m_avg_raw = session.query(func.count(Task.id)).filter(Task.created_at >= now - timedelta(minutes=15)).scalar() or 0
        
        # 12. Node Latency Analysis (Heatmap data)
        node_stats = session.query(
            TaskStepLog.task_ref,
            func.avg(TaskStepLog.duration_ms),
            func.count(TaskStepLog.id),
            func.sum(text("CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END"))
        ).filter(TaskStepLog.created_at >= now - timedelta(hours=24)).group_by(TaskStepLog.task_ref).all()
        
        node_latency_stats = []
        for ref, avg, count, fails in node_stats:
            node_latency_stats.append({
                "node": ref,
                "avgMs": int(float(avg)) if avg else 0,
                "count": int(count),
                "failureRate": round((float(fails) / count * 100), 1) if count > 0 else 0
            })

        return {
            "total": int(total),
            "byStatus": by_status,
            "byInputType": by_input_type,
            "byOutputRequested": by_output_requested,
            "successRate": success_rate,
            "avgDurationMs": int(e2e_latency * 1000),
            "avgProcessingMs": int(proc_latency * 1000),
            "avgQueueMs": int(queue_latency * 1000),
            "inputSuccessRate": input_success_rate,
            "durationByInputType": duration_by_input_type,
            "minutely_volume_1h": minutely_volume_1h,
            "hourly_volume_24h": hourly_volume_24h,
            "daily_volume_30d": daily_volume_30d,
            "weekly_volume_12w": weekly_volume_12w,
            "queue_latency_24h": queue_latency_24h,
            "concurrency_24h": concurrency_24h,
            "concurrency_1h": concurrency_1h,
            "tpm_current": int(tpm_current_raw),
            "tpm_avg_15m": round(float(tpm_15m_avg_raw) / 15.0, 1),
            "node_latency_stats": node_latency_stats,
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
        "input_type": Task.input_type,
        "retry_count": Task.retry_count,
    }
    col = col_map.get(col_name, Task.created_at)
    return col, direction


def update_task_status(task_id: str, status: str, current_step: str = None,
                       step_results: dict = None, workflow_variables: dict = None,
                       final_output: dict = None, error: dict = None,
                       retry_count: int = None):
    """Update task status and related fields with row-level locking."""
    session = get_session()
    try:
        # Use with_for_update to prevent race conditions during high load
        task = session.query(Task).filter(Task.id == task_id).with_for_update().first()
        if task is None:
            logger.warning(f"[TASK_SERVICE] Task {task_id} not found for update")
            return

        # If transitioning to RUNNING, set started_at
        if status == "RUNNING" and task.status == "PENDING" and task.started_at is None:
            task.started_at = datetime.now(timezone.utc)

        task.status = status
        # updated_at will be auto-updated by SQLAlchemy Column onupdate

        if current_step is not None:
            task.current_step = current_step
        if step_results is not None:
            task.step_results = dict(step_results) # Ensure new object reference
        if workflow_variables is not None:
            task.workflow_variables = dict(workflow_variables)
        if final_output is not None:
            task.final_output = dict(final_output)
        if error is not None:
            task.error = dict(error)
        if retry_count is not None:
            task.retry_count = retry_count

        session.commit()
    except Exception as e:
        logger.error(f"[TASK_SERVICE] Update failed for {task_id}: {e}")
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
