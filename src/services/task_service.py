"""Business logic for Task persistence."""

from src.models.task import get_session, Task
from framework.commons.logger import logger

def create_task(input_data: dict, outputs: list) -> dict:
    session = get_session()
    try:
        task = Task(
            input_data=input_data,
            outputs=outputs,
            status="PENDING",
        )
        session.add(task)
        session.commit()
        return task.to_dict()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

def get_task(task_id: str) -> dict:
    session = get_session()
    try:
        task = session.query(Task).filter(Task.id == task_id).first()
        return task.to_dict() if task else None
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

def update_task_status(task_id: str, status: str, step_results: dict = None, workflow_variables: dict = None, final_output: dict = None, error: dict = None):
    session = get_session()
    try:
        task = session.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = status
            if step_results is not None:
                task.step_results = step_results
            if workflow_variables is not None:
                task.workflow_variables = workflow_variables
            if final_output is not None:
                task.final_output = final_output
            if error is not None:
                task.error = error
            session.commit()
            return task.to_dict()
        return None
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

def list_tasks(status: str = None, limit: int = 50, cursor: str = None, sort: str = "created_at:desc", created_after=None, created_before=None):
    session = get_session()
    try:
        q = session.query(Task)
        if status:
            q = q.filter(Task.status == status)

        col_name, direction = (sort.split(":") + ["desc"])[:2]
        
        if cursor:
            pivot = session.query(Task).get(cursor)
            if pivot:
                col = getattr(Task, col_name)
                val = getattr(pivot, col_name)
                if direction == "desc":
                    q = q.filter(col < val)
                else:
                    q = q.filter(col > val)
                    
        if created_after:
            q = q.filter(Task.created_at >= created_after)
        if created_before:
            q = q.filter(Task.created_at <= created_before)

        col = getattr(Task, col_name)
        if direction == "desc":
            q = q.order_by(col.desc())
        else:
            q = q.order_by(col.asc())

        rows = q.limit(limit + 1).all()
        has_more = len(rows) > limit
        rows = rows[:limit]
        next_cursor = str(rows[-1].id) if has_more and rows else None

        return {
            "tasks": [r.to_dict() for r in rows],
            "next_cursor": next_cursor,
            "has_more": has_more
        }
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

def delete_task(task_id: str) -> bool:
    session = get_session()
    try:
        task = session.query(Task).filter(Task.id == task_id).first()
        if task:
            session.delete(task)
            session.commit()
            return True
        return False
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

def get_task_step_logs(task_id: str) -> list:
    return []
