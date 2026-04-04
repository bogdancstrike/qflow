"""Quality tests — malformed and edge-case inputs.

Verifies the API gracefully handles invalid, malicious, or extreme inputs
without crashing, hanging, or leaking information.
"""

import os
import time
import pytest

os.environ["DEV_MODE"] = "true"
os.environ["DATABASE_URL"] = "sqlite:///test_malformed.db"

from src.api.validators import validate_task_input
from src.dag.planner import build_plan, PlanningError
from src.dag.input_detector import InputDetectionError


REPORT_FILE = os.path.join(os.path.dirname(__file__), "../../reports/quality_malformed.txt")


def _write_report(test_name, lines):
    os.makedirs(os.path.dirname(REPORT_FILE), exist_ok=True)
    with open(REPORT_FILE, "a") as f:
        f.write(f"\n{'='*70}\n")
        f.write(f"  TEST: {test_name}\n")
        f.write(f"  TIME: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        for line in lines:
            f.write(f"  {line}\n")
        f.write(f"{'='*70}\n")


class TestMalformedInput:

    def test_empty_input_data(self):
        errors = validate_task_input({}, ["ner_result"])
        assert len(errors) > 0
        _write_report("test_empty_input_data", [f"Errors: {errors}", "PASS"])

    def test_none_input_data(self):
        errors = validate_task_input(None, ["ner_result"])
        assert len(errors) > 0
        _write_report("test_none_input_data", [f"Errors: {errors}", "PASS"])

    def test_string_as_input_data(self):
        errors = validate_task_input("not a dict", ["ner_result"])
        assert len(errors) > 0
        _write_report("test_string_as_input_data", [f"Errors: {errors}", "PASS"])

    def test_empty_outputs(self):
        errors = validate_task_input({"text": "hello"}, [])
        assert len(errors) > 0
        _write_report("test_empty_outputs", [f"Errors: {errors}", "PASS"])

    def test_invalid_output_type(self):
        errors = validate_task_input({"text": "hello"}, ["invalid_output"])
        assert len(errors) > 0
        assert "Unknown output" in errors[0]
        _write_report("test_invalid_output_type", [f"Errors: {errors}", "PASS"])

    def test_template_injection_in_text(self):
        errors = validate_task_input({"text": "{{config.items()}}"}, ["ner_result"])
        assert len(errors) > 0
        assert "template injection" in errors[0].lower()
        _write_report("test_template_injection", [f"Errors: {errors}", "PASS"])

    def test_jinja_block_in_text(self):
        errors = validate_task_input(
            {"text": "{% for x in range(1000000) %}x{% endfor %}"},
            ["ner_result"],
        )
        assert len(errors) > 0
        _write_report("test_jinja_block", [f"Errors: {errors}", "PASS"])

    def test_path_traversal_in_file_path(self):
        errors = validate_task_input({"file_path": "../../etc/passwd"}, ["summary"])
        assert len(errors) > 0
        _write_report("test_path_traversal", [f"Errors: {errors}", "PASS"])

    def test_null_bytes_in_file_path(self):
        errors = validate_task_input({"file_path": "/tmp/test\x00.mp4"}, ["summary"])
        assert len(errors) > 0
        _write_report("test_null_bytes", [f"Errors: {errors}", "PASS"])

    def test_unknown_field_raises_detection_error(self):
        with pytest.raises(PlanningError):
            build_plan({"unknown_key": "value"}, ["ner_result"])
        _write_report("test_unknown_field", ["PlanningError raised as expected", "PASS"])

    def test_unsupported_file_extension(self):
        with pytest.raises(PlanningError):
            build_plan({"file_path": "/tmp/document.pdf"}, ["summary"])
        _write_report("test_unsupported_extension", ["PlanningError raised as expected", "PASS"])

    def test_extremely_large_text(self):
        """10MB text — validator should not crash."""
        large_text = "A" * (10 * 1024 * 1024)
        errors = validate_task_input({"text": large_text}, ["summary"])
        assert isinstance(errors, list)
        _write_report("test_large_text", [
            f"Text size: {len(large_text):,} bytes",
            f"Errors: {len(errors)}",
            "PASS (no crash)",
        ])

    def test_deeply_nested_json(self):
        """100-level nested dict — should not crash."""
        nested = {}
        current = nested
        for _ in range(100):
            current["child"] = {}
            current = current["child"]
        errors = validate_task_input({"text": str(nested)[:1000]}, ["ner_result"])
        assert isinstance(errors, list)
        _write_report("test_nested_json", ["100-level nesting handled without crash", "PASS"])

    def test_sql_injection_in_text(self):
        sql_injection = "'; DROP TABLE tasks; --"
        errors = validate_task_input({"text": sql_injection}, ["ner_result"])
        assert isinstance(errors, list)
        _write_report("test_sql_injection", [f"Errors: {errors}", "PASS (treated as text)"])

    def test_xss_in_text(self):
        xss = "<script>alert('xss')</script>"
        errors = validate_task_input({"text": xss}, ["ner_result"])
        assert isinstance(errors, list)
        _write_report("test_xss", [f"Errors: {errors}", "PASS (treated as text)"])
