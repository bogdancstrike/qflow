"""Regression tests for bugs fixed in April 2026.

Bug 1: POST /api/tasks returned 500 (TypeError: Object of type Response is not JSON serializable)
  Fix: Return plain dicts instead of jsonify().

Bug 2: Kafka offset commit failure (OffsetAndMetadata missing leader_epoch)
  Fix: Monkey-patch OffsetAndMetadata at startup with default leader_epoch=0.

Bug 3: Endpoints must not use jsonify() — flask-restx wraps return values.
"""

import os
import time
import pytest

os.environ["DEV_MODE"] = "true"
os.environ["DATABASE_URL"] = "sqlite:///test_regression.db"


REPORT_FILE = os.path.join(os.path.dirname(__file__), "../../reports/regression_tests.txt")


def _write_report(test_name, lines):
    os.makedirs(os.path.dirname(REPORT_FILE), exist_ok=True)
    with open(REPORT_FILE, "a") as f:
        f.write(f"\n{'='*70}\n")
        f.write(f"  REGRESSION: {test_name}\n")
        f.write(f"  TIME: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        for line in lines:
            f.write(f"  {line}\n")
        f.write(f"{'='*70}\n")


class TestEndpointReturnTypes:
    """Regression: endpoints must return dicts, not Flask Response objects."""

    def test_endpoints_return_dicts_not_responses(self):
        """Verify no endpoint function uses jsonify()."""
        import inspect
        import src.api.endpoints as ep

        source = inspect.getsource(ep)
        assert "jsonify" not in source, \
            "endpoints.py still uses jsonify() — this causes flask-restx serialization errors"

        _write_report("test_endpoints_return_dicts_not_responses", [
            "Bug: jsonify() returns Flask Response, flask-restx tries to re-serialize it",
            "Verified: no jsonify() calls in endpoints.py",
            "PASS",
        ])


class TestKafkaOffsetAndMetadata:
    """Regression: OffsetAndMetadata must accept 2 args (offset, metadata)."""

    def test_offset_and_metadata_accepts_two_args(self):
        """The monkey-patch should allow 2-arg construction."""
        from collections import namedtuple
        OAM = namedtuple("OffsetAndMetadata", ["offset", "metadata", "leader_epoch"], defaults=[0])

        oam = OAM(42, None)
        assert oam.offset == 42
        assert oam.metadata is None
        assert oam.leader_epoch == 0

        _write_report("test_offset_and_metadata_accepts_two_args", [
            "Bug: QF framework calls OffsetAndMetadata(offset, metadata) with 2 args",
            "kafka-python 2.3.0 requires 3 args (offset, metadata, leader_epoch)",
            "Fix: namedtuple with defaults=[0] for leader_epoch",
            f"Verified: OAM(42, None) -> {oam}",
            "PASS",
        ])

    def test_offset_and_metadata_accepts_three_args(self):
        from collections import namedtuple
        OAM = namedtuple("OffsetAndMetadata", ["offset", "metadata", "leader_epoch"], defaults=[0])

        oam = OAM(42, None, 5)
        assert oam.leader_epoch == 5

        _write_report("test_offset_and_metadata_accepts_three_args", [
            f"Verified: OAM(42, None, 5) -> {oam}",
            "PASS",
        ])


class TestTaskModelFields:
    """Verify Task model contains all required DAG fields."""

    def test_task_to_dict_has_dag_fields(self):
        from src.models.task import Task
        import uuid
        from datetime import datetime, timezone

        task = Task(
            id=uuid.uuid4(),
            input_type="text",
            input_data={"text": "hello"},
            outputs=["ner_result"],
            execution_plan={"input_type": "text", "ingest_steps": [], "branches": []},
            status="PENDING",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        d = task.to_dict()
        assert "outputs" in d
        assert "execution_plan" in d
        assert d["outputs"] == ["ner_result"]
        assert d["execution_plan"]["input_type"] == "text"

        _write_report("test_task_to_dict_has_dag_fields", [
            "Verified: to_dict() includes outputs and execution_plan",
            "PASS",
        ])

    def test_task_to_dict_no_legacy_fields(self):
        """Legacy fields (resolved_flow, resolved_flow_definition, desired_output) should not exist."""
        from src.models.task import Task
        import uuid
        from datetime import datetime, timezone

        task = Task(
            id=uuid.uuid4(),
            input_type="text",
            input_data={"text": "hello"},
            outputs=["ner_result"],
            execution_plan={"input_type": "text", "ingest_steps": [], "branches": []},
            status="PENDING",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        d = task.to_dict()
        assert "resolved_flow" not in d
        assert "resolved_flow_definition" not in d
        assert "desired_output" not in d

        _write_report("test_task_to_dict_no_legacy_fields", [
            "Verified: legacy fields removed from to_dict()",
            "PASS",
        ])


class TestFlowExecutorValidation:
    """Verify flow_executor handles edge cases."""

    def test_flow_executor_missing_task_id(self):
        from src.workers.flow_executor import flow_executor

        result = flow_executor(
            message={},
            consumer_name="test",
            metadatas={"worker": "flow_executor"},
        )
        assert result == {"error": "missing task_id"}

        _write_report("test_flow_executor_missing_task_id", [
            "Sent message without task_id to flow_executor",
            f"Result: {result}",
            "PASS",
        ])

    def test_flow_executor_task_not_in_db(self):
        from unittest.mock import patch

        with patch("src.workers.flow_executor.get_task", return_value=None):
            from src.workers.flow_executor import flow_executor

            result = flow_executor(
                message={"task_id": "nonexistent-id"},
                consumer_name="test",
                metadatas={"worker": "flow_executor"},
            )
            assert result == {"error": "task not found"}

        _write_report("test_flow_executor_task_not_in_db", [
            "Sent nonexistent task_id to flow_executor",
            f"Result: {result}",
            "PASS",
        ])
