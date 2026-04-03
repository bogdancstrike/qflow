"""Quality tests — malformed JSON payloads and invalid input.

Verifies the API properly validates and rejects bad input without crashing.
"""

import os
import json
import time

import pytest
from flask import Flask

os.environ["DEV_MODE"] = "true"
os.environ["DATABASE_URL"] = "sqlite:///test_malformed.db"

# Set up simple flask app to route to our endpoint logic
app = Flask(__name__)
@app.route("/api/tasks", methods=["POST"])
def fake_tasks():
    from src.api.endpoints import _task_create
    # Because _task_create tries to publish to Kafka, we mock KafkaClient
    from unittest.mock import patch
    with patch("framework.streams.kafka_client.KafkaClient"):
        # and DB create_task
        with patch("src.api.endpoints.create_task", return_value={"id": "test-id", "status": "PENDING"}):
            return _task_create()

client = app.test_client()


REPORT_FILE = os.path.join(os.path.dirname(__file__), "../../reports/quality_malformed_input.txt")


def _write_report(test_name, lines):
    os.makedirs(os.path.dirname(REPORT_FILE), exist_ok=True)
    with open(REPORT_FILE, "a") as f:
        f.write(f"\n{'='*70}\n")
        f.write(f"  TEST: {test_name}\n")
        f.write(f"  TIME: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        for line in lines:
            f.write(f"  {line}\n")
        f.write(f"{'='*70}\n")


class TestMalformedJsonPayloads:
    """Verify validation catches all forms of bad input."""

    def test_empty_payload(self):
        resp = client.post("/api/tasks", json={})
        assert resp.status_code == 400
        _write_report("test_empty_payload", [f"Status: {resp.status_code}", "PASS"])

    def test_missing_input_data(self):
        resp = client.post("/api/tasks", json={"outputs": ["ner"]})
        # Wait, the endpoint uses data.get("input_data", {}) which defaults to {}
        # Then detect_input_type throws ValueError
        assert resp.status_code == 400
        _write_report("test_missing_input_data", [f"Status: {resp.status_code}", "PASS"])

    def test_missing_outputs(self):
        resp = client.post("/api/tasks", json={"input_data": {"text": "hello"}})
        assert resp.status_code == 400
        _write_report("test_missing_outputs", [f"Status: {resp.status_code}", "PASS"])

    def test_invalid_outputs_format(self):
        resp = client.post("/api/tasks", json={
            "input_data": {"text": "hello"},
            "outputs": "ner"  # Should be a list
        })
        # Currently, if outputs is not a list, validate_outputs or create_task might fail
        assert resp.status_code == 400
        _write_report("test_invalid_outputs_format", [f"Status: {resp.status_code}", "PASS"])

    def test_invalid_desired_output(self):
        resp = client.post("/api/tasks", json={
            "input_data": {"text": "hello"},
            "outputs": ["nonexistent_output"]
        })
        assert resp.status_code == 400
        _write_report("test_invalid_desired_output", [f"Status: {resp.status_code}", "PASS"])

    def test_empty_input_data_text(self):
        resp = client.post("/api/tasks", json={
            "input_data": {"text": ""},
            "outputs": ["ner"]
        })
        # Empty text raises error in detect_input_type
        assert resp.status_code == 400
        _write_report("test_empty_input_data_text", [f"Status: {resp.status_code}", "PASS"])

    def test_null_input_data(self):
        resp = client.post("/api/tasks", json={
            "input_data": None,
            "outputs": ["ner"]
        })
        # Causes AttributeError in data.get or detect_input_type
        assert resp.status_code == 400
        _write_report("test_null_input_data", [f"Status: {resp.status_code}", "PASS"])

    def test_numeric_input_data(self):
        resp = client.post("/api/tasks", json={
            "input_data": {"text": 12345},
            "outputs": ["ner"]
        })
        # Fails in sanitize_text_input or detect_input_type
        assert resp.status_code == 400
        _write_report("test_numeric_input_data", [f"Status: {resp.status_code}", "PASS"])

    def test_extremely_long_input(self):
        """Verify handling of very large text input."""
        large_text = "A" * (10 * 1024 * 1024)  # 10MB string
        resp = client.post("/api/tasks", json={
            "input_data": {"text": large_text},
            "outputs": ["ner"]
        })
        # Should accept or reject gracefully, not crash
        assert resp.status_code in (201, 413, 400)
        _write_report("test_extremely_long_input", [
            f"Input size: {len(large_text)} bytes",
            f"Status: {resp.status_code}",
            "PASS (no crash)",
        ])

    def test_nested_json_bomb(self):
        """Deeply nested JSON should not crash."""
        nested = {"a": "value"}
        for _ in range(100):
            nested = {"nested": nested}
        resp = client.post("/api/tasks", json={
            "input_data": nested,
            "outputs": ["ner"]
        })
        assert resp.status_code == 400
        _write_report("test_nested_json_bomb", [
            "Depth: 100 levels",
            f"Status: {resp.status_code}",
            "PASS (no crash)",
        ])

    def test_special_characters_in_input(self):
        """Unicode, null bytes, etc."""
        special_inputs = [
            "Hello\x00World",       # null byte
            "Hello\nWorld\tTab",    # control chars
            "\ud800",               # lone surrogate
            "' OR 1=1; --",         # SQL injection attempt
            "<script>alert(1)</script>",  # XSS attempt
            "{{ payload }}",        # Template injection
        ]
        for text in special_inputs:
            resp = client.post("/api/tasks", json={
                "input_data": {"text": text},
                "outputs": ["ner"]
            })
            assert resp.status_code in (201, 400)
        _write_report("test_special_characters_in_input", [
            f"Tested {len(special_inputs)} special inputs",
            "PASS (no crash)",
        ])
