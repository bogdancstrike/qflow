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
from src.core.context import ExecutionContext
from src.core.executor import execute_flow
from src.services.task_service import create_task, get_task, update_task_status
from src.templating.registry import init_registry, get_flow


REPORT_FILE = os.path.join(os.path.dirname(__file__), "../../reports/quality_concurrent.txt")


@pytest.fixture(scope="module", autouse=True)
def setup_environment():
    task_module._engine = None
    task_module._SessionFactory = None
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    init_registry(base_dir)
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


def _make_env():
    return {
        "AI_SERVICE_URL": "http://ai-service:8000",
        "AI_STT_URL": "http://stt-service:8001",
        "AI_STT_TOKEN": "dev-token",
        "AI_NER_URL": "http://ner-service:8002",
        "AI_TRANSLATE_URL": "http://translate-service:8003",
        "AI_LANGDETECT_URL": "http://langdetect-service:8004",
        "AI_SENTIMENT_URL": "http://sentiment-service:8005",
        "AI_SUMMARY_URL": "http://summary-service:8006",
        "AI_TAXONOMY_URL": "http://taxonomy-service:8007",
    }


def _execute_task(input_type, input_data, desired_output, results, index):
    """Execute a task and store result in results list."""
    try:
        task = create_task(input_type, input_data, desired_output)
        task_id = task["id"]
        flow_def = get_flow(task["resolved_flow"])
        update_task_status(task_id, "RUNNING")

        ctx = ExecutionContext(input_data, _make_env())
        result = execute_flow(flow_def, ctx, task_id)

        update_task_status(
            task_id, "COMPLETED",
            step_results=ctx.steps,
            workflow_variables=ctx.variables,
            final_output=result,
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
                args=("text", {"text": f"Task {i}: John Smith lives in Berlin."}, "ner", results, i),
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
            assert "entities" in r["result"]

    def test_mixed_parallel_tasks(self):
        """Run different task types concurrently."""
        task_specs = [
            ("text", {"text": "Hello world"}, "ner"),
            ("text", {"text": "Great product!"}, "sentiment"),
            ("text", {"text": "Long text about technology..."}, "summary"),
            ("file_upload", {"file_path": "/tmp/test.mp4"}, "stt"),
            ("file_upload", {"file_path": "/tmp/test.mp4"}, "ner"),
        ]
        results = [None] * len(task_specs)
        threads = []

        start = time.time()
        for i, (it, data, do) in enumerate(task_specs):
            t = threading.Thread(target=_execute_task, args=(it, data, do, results, i))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=60)

        elapsed = time.time() - start
        successes = sum(1 for r in results if r and r["status"] == "ok")
        failures = sum(1 for r in results if r and r["status"] == "error")

        report = [
            f"Mixed parallel tasks: {len(task_specs)}",
            f"Types: {[(it, do) for it, _, do in task_specs]}",
            f"Successes: {successes}",
            f"Failures: {failures}",
            f"Elapsed: {elapsed:.2f}s",
        ]
        _write_report("test_mixed_parallel_tasks", report)

        assert successes == len(task_specs), f"{failures} tasks failed"
