"""Full-environment integration tests — PostgreSQL + flow execution in DEV_MODE.

These tests exercise the complete stack:
  1. Create a task via task_service (writes to PostgreSQL)
  2. Execute the resolved flow (primitives run with mock responses)
  3. Update task status in PostgreSQL
  4. Verify task state in DB matches expected output

Requires: PostgreSQL running (docker compose up -d postgres)
"""

import os
import pytest

os.environ["DEV_MODE"] = "true"
os.environ["DATABASE_URL"] = "postgresql://qf:qf@localhost:5432/ai_flow"

import src.models.task as task_module
from src.config import Config
from src.models.task import init_db, get_session, Task, get_engine
from src.models.task_step_log import TaskStepLog
from src.core.context import ExecutionContext
from src.core.executor import execute_flow
from src.core.resolver import resolve_flow
from src.services.task_service import (
    create_task, get_task, list_tasks, update_task_status, delete_task, get_task_step_logs,
)
from src.templating.registry import init_registry, get_flow


@pytest.fixture(scope="module", autouse=True)
def setup_environment():
    """Initialize DB tables and template registry."""
    # Reset engine singleton to use PostgreSQL (conftest may have set SQLite)
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
    """Clean up tasks created during each test."""
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


def _execute_task_end_to_end(input_type, input_data, desired_output):
    """Full lifecycle: create task in DB -> execute flow -> update DB -> verify.

    Returns (task_dict, result, context).
    """
    # 1. Create task in PostgreSQL
    task = create_task(input_type, input_data, desired_output)
    task_id = task["id"]
    assert task["status"] == "PENDING"
    assert task["resolved_flow"] is not None

    # 2. Simulate what flow_executor does: get flow, execute, update status
    flow_id = task["resolved_flow"]
    flow_def = get_flow(flow_id)
    assert flow_def is not None

    # Update status to RUNNING
    update_task_status(task_id, "RUNNING")
    running_task = get_task(task_id)
    assert running_task["status"] == "RUNNING"

    # 3. Execute the flow
    ctx = ExecutionContext(input_data, _make_env())
    result = execute_flow(flow_def, ctx, task_id)

    # 4. Update task to COMPLETED with results
    update_task_status(
        task_id,
        "COMPLETED",
        step_results=ctx.steps,
        workflow_variables=ctx.variables,
        final_output=result,
    )

    # 5. Verify final state in DB
    completed_task = get_task(task_id)
    assert completed_task["status"] == "COMPLETED"
    assert completed_task["final_output"] is not None

    # 6. Verify step logs were written
    step_logs = get_task_step_logs(task_id)

    # --- Report ---
    total_ms = sum(s.get("duration_ms", 0) for s in ctx.steps.values())
    print(f"\n{'='*70}")
    print(f"  TASK:     {input_type} -> {desired_output}")
    print(f"  FLOW:     {flow_id}")
    print(f"  TASK ID:  {task_id}")
    print(f"  DB STATE: {completed_task['status']}")
    print(f"  STEPS:    {len(ctx.steps)} primitives ({total_ms}ms total)")
    for ref, step_data in ctx.steps.items():
        status = step_data.get("status", "?")
        dur = step_data.get("duration_ms", 0)
        print(f"    {ref}: {status} ({dur}ms)")
    if ctx.variables:
        print(f"  VARS:     {ctx.variables}")
    print(f"  RESULT:   {result}")
    if step_logs:
        print(f"  DB LOGS:  {len(step_logs)} step logs in PostgreSQL")
    print(f"{'='*70}")

    return completed_task, result, ctx


# ============================================================
# Full lifecycle: create in DB -> execute -> verify DB state
# ============================================================

class TestTaskLifecycle:
    """End-to-end: task_service + executor + PostgreSQL."""

    def test_create_and_get_task(self):
        """Verify task creation writes to PostgreSQL correctly."""
        task = create_task("text", {"text": "Hello world"}, "ner")
        assert task["id"] is not None
        assert task["input_type"] == "text"
        assert task["desired_output"] == "ner"
        assert task["resolved_flow"] == "flow_text_to_ner"
        assert task["status"] == "PENDING"

        # Retrieve from DB
        fetched = get_task(task["id"])
        assert fetched is not None
        assert fetched["id"] == task["id"]
        print(f"\n  [OK] Task created in PostgreSQL: {task['id']} (flow={task['resolved_flow']})")

    def test_list_tasks_with_filters(self):
        """Verify task listing with status/output filters."""
        create_task("text", {"text": "Hello"}, "ner")
        create_task("text", {"text": "World"}, "sentiment")
        create_task("file_upload", {"file_path": "/tmp/test.mp4"}, "stt")

        all_result = list_tasks()
        assert len(all_result["tasks"]) == 3

        ner_result = list_tasks(desired_output="ner")
        assert len(ner_result["tasks"]) == 1

        text_result = list_tasks(input_type="text")
        assert len(text_result["tasks"]) == 2
        print(f"\n  [OK] Task filtering: 3 total, 1 ner, 2 text")

    def test_delete_task(self):
        """Verify task deletion from PostgreSQL."""
        task = create_task("text", {"text": "Delete me"}, "ner")
        task_id = task["id"]

        assert delete_task(task_id) is True
        assert get_task(task_id) is None
        assert delete_task(task_id) is False  # already deleted
        print(f"\n  [OK] Task {task_id} deleted from PostgreSQL")


# ============================================================
# File upload tasks — full DB lifecycle
# ============================================================

class TestFileUploadFullEnvironment:
    """file_upload tasks: DB create -> flow execute -> DB verify."""

    def test_file_to_stt_full(self):
        """Task: test.mp4 -> STT (full DB lifecycle)
        Flow: LOG -> HTTP(stt) -> LOG
        """
        task, result, ctx = _execute_task_end_to_end(
            "file_upload", {"file_path": "/tmp/test.mp4"}, "stt"
        )
        assert task["status"] == "COMPLETED"
        assert "text" in result
        assert "stt" in ctx.steps

    def test_file_to_ner_full(self):
        """Task: test.mp4 -> NER (full DB lifecycle)
        Flow: LOG -> HTTP(stt) -> HTTP(lang-detect) -> SWITCH -> HTTP(translate) -> SET_VAR -> HTTP(ner) -> LOG
        """
        task, result, ctx = _execute_task_end_to_end(
            "file_upload", {"file_path": "/tmp/test.mp4"}, "ner"
        )
        assert task["status"] == "COMPLETED"
        assert "entities" in result
        assert len(result["entities"]) > 0
        assert result["language_detected"] == "de"

    def test_file_to_sentiment_full(self):
        """Task: test.mp4 -> Sentiment (full DB lifecycle)"""
        task, result, ctx = _execute_task_end_to_end(
            "file_upload", {"file_path": "/tmp/test.mp4"}, "sentiment"
        )
        assert task["status"] == "COMPLETED"
        assert "sentiment" in result
        assert "score" in result

    def test_file_to_summary_full(self):
        """Task: test.mp4 -> Summary (full DB lifecycle)"""
        task, result, ctx = _execute_task_end_to_end(
            "file_upload", {"file_path": "/tmp/test.mp4"}, "summary"
        )
        assert task["status"] == "COMPLETED"
        assert "summary" in result


# ============================================================
# Text tasks — full DB lifecycle
# ============================================================

class TestTextFullEnvironment:
    """text tasks: DB create -> flow execute -> DB verify."""

    def test_text_to_ner_full(self):
        """Task: text -> NER (full DB lifecycle)
        Flow: LOG -> HTTP(lang-detect) -> SWITCH -> HTTP(translate) -> SET_VAR -> HTTP(ner) -> LOG
        """
        task, result, ctx = _execute_task_end_to_end(
            "text",
            {"text": "東京で開催された会議で田中太郎氏がソニーの新戦略を発表しました。"},
            "ner",
        )
        assert task["status"] == "COMPLETED"
        assert "entities" in result
        assert len(result["entities"]) > 0
        assert result["language_detected"] == "ja"

    def test_text_to_sentiment_full(self):
        """Task: text -> Sentiment (full DB lifecycle)"""
        task, result, ctx = _execute_task_end_to_end(
            "text",
            {"text": "Este serviço é horrível. Nunca mais vou usar."},
            "sentiment",
        )
        assert task["status"] == "COMPLETED"
        assert "sentiment" in result
        assert result["sentiment"] == "negative"

    def test_text_to_summary_full(self):
        """Task: text -> Summary (full DB lifecycle)"""
        task, result, ctx = _execute_task_end_to_end(
            "text",
            {"text": "Il governo italiano ha approvato un nuovo piano economico."},
            "summary",
        )
        assert task["status"] == "COMPLETED"
        assert "summary" in result


# ============================================================
# YouTube tasks — full DB lifecycle
# ============================================================

class TestYouTubeFullEnvironment:
    """youtube_link tasks: DB create -> flow execute -> DB verify."""

    def test_youtube_to_stt_full(self):
        """Task: youtube -> STT (full DB lifecycle)
        Flow: LOG -> HTTP(download) -> HTTP(stt) -> LOG
        """
        task, result, ctx = _execute_task_end_to_end(
            "youtube_link",
            {"youtube_url": "https://youtube.com/watch?v=test123"},
            "stt",
        )
        assert task["status"] == "COMPLETED"
        assert "text" in result

    def test_youtube_to_ner_full(self):
        """Task: youtube -> NER (full DB lifecycle)
        Flow: LOG -> HTTP(download) -> HTTP(stt) -> HTTP(lang-detect) -> SWITCH
              -> HTTP(translate) -> SET_VAR -> HTTP(ner) -> LOG
        """
        task, result, ctx = _execute_task_end_to_end(
            "youtube_link",
            {"youtube_url": "https://youtube.com/watch?v=test123"},
            "ner",
        )
        assert task["status"] == "COMPLETED"
        assert "entities" in result
        assert len(result["entities"]) > 0
