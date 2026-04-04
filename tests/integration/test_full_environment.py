"""Full-environment integration tests — PostgreSQL + DAG execution in DEV_MODE.

These tests exercise the complete stack:
  1. Create a task via task_service (writes to PostgreSQL)
  2. Build and execute the DAG plan
  3. Update task status in PostgreSQL
  4. Verify task state in DB matches expected output

Requires: PostgreSQL running (docker compose up -d postgres)
"""

import os
import time
import pytest

os.environ["DEV_MODE"] = "true"
os.environ["DATABASE_URL"] = "postgresql://qf:qf@localhost:5432/ai_flow"

import src.models.task as task_module
from src.models.task import init_db, get_session, Task
from src.models.task_step_log import TaskStepLog
from src.dag.planner import build_plan
from src.dag.runner import run_plan
from src.services.task_service import (
    create_task, get_task, list_tasks, update_task_status, delete_task, get_task_step_logs,
)


REPORT_FILE = os.path.join(os.path.dirname(__file__), "../../reports/integration_full_env.txt")


def _write_report(test_name, lines):
    os.makedirs(os.path.dirname(REPORT_FILE), exist_ok=True)
    with open(REPORT_FILE, "a") as f:
        f.write(f"\n{'='*70}\n")
        f.write(f"  TEST: {test_name}\n")
        f.write(f"  TIME: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        for line in lines:
            f.write(f"  {line}\n")
        f.write(f"{'='*70}\n")


@pytest.fixture(scope="module", autouse=True)
def setup_environment():
    """Initialize DB tables."""
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


def _execute_task_end_to_end(input_data, outputs):
    """Full lifecycle: create task in DB -> execute DAG -> update DB -> verify.

    Returns (task_dict, result, plan).
    """
    # 1. Create task in PostgreSQL
    task = create_task(input_data, outputs)
    task_id = task["id"]
    assert task["status"] == "PENDING"
    assert task["execution_plan"] is not None

    # 2. Update status to RUNNING
    update_task_status(task_id, "RUNNING")
    running_task = get_task(task_id)
    assert running_task["status"] == "RUNNING"

    # 3. Reconstruct plan and execute
    plan = build_plan(input_data, outputs)
    context = dict(input_data)
    if plan.input_type == "youtube_url" and "url" in input_data:
        context["youtube_url"] = input_data["url"]
    elif plan.input_type == "audio_path" and "file_path" in input_data:
        context["audio_path"] = input_data["file_path"]

    start = time.time()
    result = run_plan(plan, context, task_id)
    elapsed_ms = int((time.time() - start) * 1000)

    # 4. Update task to COMPLETED with results
    update_task_status(task_id, "COMPLETED", final_output=result)

    # 5. Verify final state in DB
    completed_task = get_task(task_id)
    assert completed_task["status"] == "COMPLETED"
    assert completed_task["final_output"] is not None

    # 6. Verify step logs
    step_logs = get_task_step_logs(task_id)

    # --- Report ---
    print(f"\n{'='*70}")
    print(f"  INPUT:    {plan.input_type}")
    print(f"  OUTPUTS:  {outputs}")
    print(f"  TASK ID:  {task_id}")
    print(f"  DB STATE: {completed_task['status']}")
    print(f"  DURATION: {elapsed_ms}ms")
    print(f"  INGEST:   {[n.node_id for n in plan.ingest_steps]}")
    for b in plan.branches:
        print(f"  BRANCH:   {b.output_type} -> {[n.node_id for n in b.steps]}")
    if step_logs["logs"]:
        print(f"  DB LOGS:  {len(step_logs['logs'])} step logs in PostgreSQL")
    print(f"  RESULT:   {list(result.keys())}")
    print(f"{'='*70}")

    return completed_task, result, plan


# ============================================================
# Task CRUD lifecycle
# ============================================================

class TestTaskLifecycle:

    def test_create_and_get_task(self):
        task = create_task({"text": "Hello world"}, ["ner_result"])
        assert task["id"] is not None
        assert task["input_type"] == "text"
        assert task["outputs"] == ["ner_result"]
        assert task["status"] == "PENDING"

        fetched = get_task(task["id"])
        assert fetched is not None
        assert fetched["id"] == task["id"]

        _write_report("test_create_and_get_task", [
            f"Task created: {task['id']}",
            f"Plan: {task['execution_plan']}",
            "PASS",
        ])

    def test_list_tasks_with_filters(self):
        create_task({"text": "Hello"}, ["ner_result"])
        create_task({"text": "World"}, ["sentiment_result"])
        create_task({"file_path": "/tmp/test.mp4"}, ["summary"])

        all_result = list_tasks()
        assert len(all_result["tasks"]) == 3

        text_result = list_tasks(input_type="text")
        assert len(text_result["tasks"]) == 2

        _write_report("test_list_tasks_with_filters", [
            "3 total, 2 text, 1 audio_path",
            "PASS",
        ])

    def test_delete_task(self):
        task = create_task({"text": "Delete me"}, ["ner_result"])
        task_id = task["id"]
        assert delete_task(task_id) is True
        assert get_task(task_id) is None
        assert delete_task(task_id) is False

        _write_report("test_delete_task", [
            f"Task {task_id} deleted",
            "PASS",
        ])


# ============================================================
# Text tasks — full DB lifecycle
# ============================================================

class TestTextFullEnvironment:

    def test_text_to_ner_full(self):
        task, result, plan = _execute_task_end_to_end(
            {"text": "東京で開催された会議で田中太郎氏がソニーの新戦略を発表しました。"},
            ["ner_result"],
        )
        assert task["status"] == "COMPLETED"
        assert "ner_result" in result
        assert "entities" in result["ner_result"]

    def test_text_to_sentiment_full(self):
        task, result, plan = _execute_task_end_to_end(
            {"text": "Este serviço é horrível. Nunca mais vou usar."},
            ["sentiment_result"],
        )
        assert task["status"] == "COMPLETED"
        assert "sentiment_result" in result

    def test_text_to_summary_full(self):
        task, result, plan = _execute_task_end_to_end(
            {"text": "Il governo italiano ha approvato un nuovo piano economico."},
            ["summary"],
        )
        assert task["status"] == "COMPLETED"
        assert "summary" in result

    def test_text_multi_output_full(self):
        task, result, plan = _execute_task_end_to_end(
            {"text": "AI technology is transforming the world economy."},
            ["ner_result", "sentiment_result", "summary", "iptc_tags", "keywords"],
        )
        assert task["status"] == "COMPLETED"
        assert len(result) == 5


# ============================================================
# File upload tasks — full DB lifecycle
# ============================================================

class TestFileUploadFullEnvironment:

    def test_file_to_ner_full(self):
        task, result, plan = _execute_task_end_to_end(
            {"file_path": "/tmp/test.mp4"},
            ["ner_result"],
        )
        assert task["status"] == "COMPLETED"
        assert "ner_result" in result

    def test_file_to_sentiment_full(self):
        task, result, plan = _execute_task_end_to_end(
            {"file_path": "/tmp/test.mp4"},
            ["sentiment_result"],
        )
        assert task["status"] == "COMPLETED"

    def test_file_to_summary_full(self):
        task, result, plan = _execute_task_end_to_end(
            {"file_path": "/tmp/test.mp4"},
            ["summary"],
        )
        assert task["status"] == "COMPLETED"

    def test_file_multi_output_full(self):
        task, result, plan = _execute_task_end_to_end(
            {"file_path": "/tmp/audio.wav"},
            ["ner_result", "summary", "keywords"],
        )
        assert task["status"] == "COMPLETED"
        assert len(result) == 3


# ============================================================
# YouTube tasks — full DB lifecycle
# ============================================================

class TestYouTubeFullEnvironment:

    def test_youtube_to_ner_full(self):
        task, result, plan = _execute_task_end_to_end(
            {"url": "https://youtube.com/watch?v=test123"},
            ["ner_result"],
        )
        assert task["status"] == "COMPLETED"
        assert "ner_result" in result

    def test_youtube_to_sentiment_full(self):
        task, result, plan = _execute_task_end_to_end(
            {"url": "https://youtube.com/watch?v=test456"},
            ["sentiment_result"],
        )
        assert task["status"] == "COMPLETED"

    def test_youtube_to_summary_full(self):
        task, result, plan = _execute_task_end_to_end(
            {"url": "https://youtube.com/watch?v=test789"},
            ["summary"],
        )
        assert task["status"] == "COMPLETED"

    def test_youtube_multi_output_full(self):
        task, result, plan = _execute_task_end_to_end(
            {"url": "https://youtube.com/watch?v=multi"},
            ["ner_result", "sentiment_result", "summary", "iptc_tags"],
        )
        assert task["status"] == "COMPLETED"
        assert len(result) == 4
