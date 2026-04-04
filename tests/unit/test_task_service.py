"""Unit tests for task_service (DAG mode only, using SQLite)."""

import os
import pytest

os.environ["DEV_MODE"] = "true"
os.environ["DATABASE_URL"] = "sqlite:///test_task_service.db"

import src.models.task as task_module
from src.models.task import init_db, get_session, Task
from src.models.task_step_log import TaskStepLog
from src.services.task_service import (
    create_task, get_task, list_tasks, update_task_status, delete_task,
)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    task_module._engine = None
    task_module._SessionFactory = None
    init_db()


@pytest.fixture(autouse=True)
def cleanup():
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


class TestCreateTask:

    def test_create_text_ner(self):
        task = create_task({"text": "John in Berlin"}, ["ner_result"])
        assert task["id"] is not None
        assert task["input_type"] == "text"
        assert task["outputs"] == ["ner_result"]
        assert task["execution_plan"] is not None
        assert task["status"] == "PENDING"

    def test_create_file_stt(self):
        task = create_task({"file_path": "/tmp/test.mp4"}, ["summary"])
        assert task["input_type"] == "audio_path"
        assert task["outputs"] == ["summary"]
        assert "stt" in task["execution_plan"]["ingest_steps"]

    def test_create_youtube_ner(self):
        task = create_task({"url": "https://youtube.com/watch?v=abc"}, ["ner_result"])
        assert task["input_type"] == "youtube_url"
        ingest = task["execution_plan"]["ingest_steps"]
        assert "ytdlp_download" in ingest
        assert "stt" in ingest

    def test_create_multi_output(self):
        task = create_task({"text": "hello"}, ["ner_result", "sentiment_result", "summary"])
        assert len(task["outputs"]) == 3
        assert len(task["execution_plan"]["branches"]) == 3

    def test_create_invalid_output_raises(self):
        with pytest.raises(Exception):
            create_task({"text": "hello"}, ["nonexistent"])


class TestGetTask:

    def test_get_existing(self):
        task = create_task({"text": "hello"}, ["ner_result"])
        fetched = get_task(task["id"])
        assert fetched is not None
        assert fetched["id"] == task["id"]

    def test_get_nonexistent(self):
        assert get_task("00000000-0000-0000-0000-000000000000") is None


class TestListTasks:

    def test_list_empty(self):
        result = list_tasks()
        assert result["tasks"] == []
        assert result["has_more"] is False

    def test_list_with_tasks(self):
        create_task({"text": "hello"}, ["ner_result"])
        create_task({"text": "world"}, ["summary"])
        result = list_tasks()
        assert len(result["tasks"]) == 2

    def test_list_filter_by_status(self):
        task = create_task({"text": "hello"}, ["ner_result"])
        update_task_status(task["id"], "COMPLETED")
        create_task({"text": "world"}, ["summary"])

        result = list_tasks(status="COMPLETED")
        assert len(result["tasks"]) == 1
        assert result["tasks"][0]["status"] == "COMPLETED"

    def test_list_filter_by_input_type(self):
        create_task({"text": "hello"}, ["ner_result"])
        create_task({"file_path": "/tmp/test.mp4"}, ["summary"])

        result = list_tasks(input_type="text")
        assert len(result["tasks"]) == 1
        assert result["tasks"][0]["input_type"] == "text"

    def test_list_pagination(self):
        for i in range(5):
            create_task({"text": f"task {i}"}, ["ner_result"])

        result = list_tasks(limit=2)
        assert len(result["tasks"]) == 2
        assert result["has_more"] is True
        assert result["next_cursor"] is not None


class TestUpdateTaskStatus:

    def test_update_to_running(self):
        task = create_task({"text": "hello"}, ["ner_result"])
        update_task_status(task["id"], "RUNNING")
        fetched = get_task(task["id"])
        assert fetched["status"] == "RUNNING"

    def test_update_to_completed_with_output(self):
        task = create_task({"text": "hello"}, ["ner_result"])
        update_task_status(task["id"], "COMPLETED", final_output={"entities": []})
        fetched = get_task(task["id"])
        assert fetched["status"] == "COMPLETED"
        assert fetched["final_output"] == {"entities": []}

    def test_update_nonexistent_no_error(self):
        update_task_status("00000000-0000-0000-0000-000000000000", "RUNNING")


class TestDeleteTask:

    def test_delete_existing(self):
        task = create_task({"text": "hello"}, ["ner_result"])
        assert delete_task(task["id"]) is True
        assert get_task(task["id"]) is None

    def test_delete_nonexistent(self):
        assert delete_task("00000000-0000-0000-0000-000000000000") is False
