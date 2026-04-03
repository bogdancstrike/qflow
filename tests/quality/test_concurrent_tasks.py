"""Quality tests — concurrent task execution.

Verifies the system handles multiple tasks executing in parallel without
data corruption or race conditions.
"""

import os
import threading
import time

import pytest

os.environ["DEV_MODE"] = "true"
os.environ["DATABASE_URL"] = "postgresql://qf:qf@localhost:5432/ai_flow"

import src.models.task as task_module
from src.models.task import init_db, get_session, Task
from src.models.task_step_log import TaskStepLog
from src.dag.planner import build_execution_plan
from src.dag.runner import run_plan
from src.services.task_service import create_task, get_task, update_task_status

REPORT_FILE = os.path.join(os.path.dirname(__file__), "../../reports/quality_concurrent.txt")

@pytest.fixture(scope="module", autouse=True)
def setup_environment():
    task_module._engine = None
    task_module._SessionFactory = None
    try:
        init_db()
    except Exception as e:
        pytest.skip(f"PostgreSQL not available: {e}")

@pytest.fixture(autouse=True)
def cleanup_tasks():
    yield
    session = get_session()
    try:
        session.query(TaskStepLog).delete()
        session.query(Task).delete()
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()

def _execute_task(input_data, outputs, results, index):
    """Execute a task and store result in results list."""
    try:
        task = create_task(input_data, outputs)
        task_id = task["id"]
        
        request_msg = {
            "input_data": input_data,
            "outputs": outputs
        }
        
        plan = build_execution_plan(request_msg)
        update_task_status(task_id, "RUNNING")

        context = dict(input_data)
        result = run_plan(plan, context)

        update_task_status(
            task_id, "COMPLETED",
            final_output=result.get("outputs", {}),
        )
        completed = get_task(task_id)
        results[index] = {"status": "ok", "task": completed, "result": result}
    except Exception as e:
        results[index] = {"status": "error", "error": str(e)}

def _write_report(test_name, lines):
    os.makedirs(os.path.dirname(REPORT_FILE), exist_ok=True)
    with open(REPORT_FILE, "a") as f:
        f.write(f"\n{'='*70}\n")
        f.write(f"  TEST: {test_name}\n")
        f.write(f"  TIME: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        for line in lines:
            f.write(f"  {line}\n")
        f.write(f"{'='*70}\n")

class TestConcurrentTasks:
    """Verify multiple tasks can execute in parallel without corruption."""

    def test_10_parallel_text_ner_tasks(self):
        """Run 10 text->NER tasks concurrently."""
        num_tasks = 10
        results = [None] * num_tasks
        threads = []

        start = time.time()
        for i in range(num_tasks):
            t = threading.Thread(
                target=_execute_task,
                args=({"text": f"Task {i}: John Smith lives in Berlin."}, ["ner_result"], results, i),
            )
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=60)

        elapsed = time.time() - start

        successes = sum(1 for r in results if r and r["status"] == "ok")
        failures = sum(1 for r in results if r and r["status"] == "error")

        report = [
            f"Parallel tasks: {num_tasks}",
            f"Successes: {successes}",
            f"Failures: {failures}",
            f"Elapsed: {elapsed:.2f}s",
        ]
        if failures:
            for i, r in enumerate(results):
                if r and r["status"] == "error":
                    report.append(f"  Task {i} error: {r['error']}")

        _write_report("test_10_parallel_text_ner_tasks", report)

        assert successes == num_tasks, f"{failures} tasks failed out of {num_tasks}"

        # Verify each task got its own result (no data corruption)
        task_ids = set()
        for r in results:
            task = r["task"]
            assert task["status"] == "COMPLETED"
            assert task["id"] not in task_ids, f"Duplicate task ID: {task['id']}"
            task_ids.add(task["id"])
            assert "ner_result" in r["result"]["outputs"]

    def test_mixed_parallel_tasks(self):
        """Run different task types concurrently."""
        task_specs = [
            ({"text": "Hello world"}, ["ner_result"]),
            ({"text": "Great product!"}, ["sentiment_result"]),
            ({"text": "Long text about technology..."}, ["summary"]),
            ({"file_path": "/tmp/test.mp4"}, ["text"]),
            ({"file_path": "/tmp/test.mp4"}, ["ner_result"]),
        ]
        results = [None] * len(task_specs)
        threads = []

        start = time.time()
        for i, (data, outs) in enumerate(task_specs):
            t = threading.Thread(target=_execute_task, args=(data, outs, results, i))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=60)

        elapsed = time.time() - start
        successes = sum(1 for r in results if r and r["status"] == "ok")
        failures = sum(1 for r in results if r and r["status"] == "error")

        report = [
            f"Mixed parallel tasks: {len(task_specs)}",
            f"Types: {[outs for _, outs in task_specs]}",
            f"Successes: {successes}",
            f"Failures: {failures}",
            f"Elapsed: {elapsed:.2f}s",
        ]
        _write_report("test_mixed_parallel_tasks", report)

        assert successes == len(task_specs), f"{failures} tasks failed"
