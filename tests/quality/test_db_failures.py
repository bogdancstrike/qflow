"""Quality tests — database connection failures.

Verifies graceful handling when PostgreSQL is unreachable or returns errors.
"""

import os
import time
from unittest.mock import patch, MagicMock

import pytest
from sqlalchemy.exc import OperationalError

os.environ["DEV_MODE"] = "true"
os.environ["DATABASE_URL"] = "sqlite:///test_db_failures.db"

from src.services.task_service import create_task, get_task, list_tasks, update_task_status, delete_task
from src.models.task import get_session


REPORT_FILE = os.path.join(os.path.dirname(__file__), "../../reports/quality_db_failures.txt")


def _write_report(test_name, lines):
    os.makedirs(os.path.dirname(REPORT_FILE), exist_ok=True)
    with open(REPORT_FILE, "a") as f:
        f.write(f"\n{'='*70}\n")
        f.write(f"  TEST: {test_name}\n")
        f.write(f"  TIME: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        for line in lines:
            f.write(f"  {line}\n")
        f.write(f"{'='*70}\n")


class TestDatabaseConnectionFailures:
    """Verify graceful handling of DB failures."""

    def test_create_task_db_down(self):
        """Simulate DB connection failure during task creation."""
        with patch("src.services.task_service.get_session") as mock_session:
            mock_session.side_effect = OperationalError(
                "connection refused", None, None
            )
            with pytest.raises(OperationalError):
                create_task("text", {"text": "hello"}, "ner")

        _write_report("test_create_task_db_down", [
            "Simulated: DB connection refused during create_task",
            "Result: OperationalError raised (expected)",
            "PASS",
        ])

    def test_get_task_db_down(self):
        """Simulate DB failure during task retrieval."""
        with patch("src.services.task_service.get_session") as mock_session:
            mock_session.side_effect = OperationalError(
                "connection refused", None, None
            )
            with pytest.raises(OperationalError):
                get_task("fake-id")

        _write_report("test_get_task_db_down", [
            "Simulated: DB connection refused during get_task",
            "Result: OperationalError raised (expected)",
            "PASS",
        ])

    def test_list_tasks_db_down(self):
        """Simulate DB failure during task listing."""
        with patch("src.services.task_service.get_session") as mock_session:
            mock_session.side_effect = OperationalError(
                "connection refused", None, None
            )
            with pytest.raises(OperationalError):
                list_tasks()

        _write_report("test_list_tasks_db_down", [
            "Simulated: DB connection refused during list_tasks",
            "Result: OperationalError raised (expected)",
            "PASS",
        ])

    def test_update_status_db_down(self):
        """Simulate DB failure during status update."""
        with patch("src.services.task_service.get_session") as mock_session:
            mock_session.side_effect = OperationalError(
                "connection refused", None, None
            )
            with pytest.raises(OperationalError):
                update_task_status("fake-id", "RUNNING")

        _write_report("test_update_status_db_down", [
            "Simulated: DB connection refused during update_task_status",
            "Result: OperationalError raised (expected)",
            "PASS",
        ])

    def test_delete_task_db_down(self):
        """Simulate DB failure during delete."""
        with patch("src.services.task_service.get_session") as mock_session:
            mock_session.side_effect = OperationalError(
                "connection refused", None, None
            )
            with pytest.raises(OperationalError):
                delete_task("fake-id")

        _write_report("test_delete_task_db_down", [
            "Simulated: DB connection refused during delete_task",
            "Result: OperationalError raised (expected)",
            "PASS",
        ])

    def test_db_commit_failure_rolls_back(self):
        """Simulate commit failure — verify rollback is called."""
        mock_session = MagicMock()
        mock_session.commit.side_effect = OperationalError(
            "disk full", None, None
        )

        with patch("src.services.task_service.get_session", return_value=mock_session):
            with pytest.raises(OperationalError):
                create_task("text", {"text": "hello"}, "ner")

        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()

        _write_report("test_db_commit_failure_rolls_back", [
            "Simulated: commit fails with 'disk full'",
            "Result: rollback() called, session closed",
            "PASS",
        ])
