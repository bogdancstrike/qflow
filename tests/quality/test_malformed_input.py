"""Quality tests — malformed JSON payloads and invalid input.

Verifies the API properly validates and rejects bad input without crashing.
"""

import os
import json
import time

import pytest

os.environ["DEV_MODE"] = "true"
os.environ["DATABASE_URL"] = "sqlite:///test_malformed.db"

from src.api.validators import validate_task_input
from src.core.resolver import is_valid_combination


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
        errors = validate_task_input({})
        assert len(errors) >= 2  # missing input_type and desired_output
        _write_report("test_empty_payload", [f"Errors: {errors}", "PASS"])

    def test_missing_input_type(self):
        errors = validate_task_input({"desired_output": "ner", "input_data": "hello"})
        assert any("input_type" in e for e in errors)
        _write_report("test_missing_input_type", [f"Errors: {errors}", "PASS"])

    def test_missing_desired_output(self):
        errors = validate_task_input({"input_type": "text", "input_data": "hello"})
        assert any("desired_output" in e for e in errors)
        _write_report("test_missing_desired_output", [f"Errors: {errors}", "PASS"])

    def test_invalid_input_type(self):
        errors = validate_task_input({
            "input_type": "invalid_type",
            "desired_output": "ner",
            "input_data": "hello",
        })
        assert any("Invalid input_type" in e for e in errors)
        _write_report("test_invalid_input_type", [f"Errors: {errors}", "PASS"])

    def test_invalid_desired_output(self):
        errors = validate_task_input({
            "input_type": "text",
            "desired_output": "nonexistent_output",
            "input_data": "hello",
        })
        assert any("Invalid desired_output" in e for e in errors)
        _write_report("test_invalid_desired_output", [f"Errors: {errors}", "PASS"])

    def test_invalid_combination(self):
        """Some input_type + desired_output combos may not be supported."""
        assert not is_valid_combination("text", "stt")  # text can't be STT'd
        errors = validate_task_input({
            "input_type": "text",
            "desired_output": "stt",
            "input_data": "hello",
        })
        assert len(errors) > 0
        _write_report("test_invalid_combination", [f"Errors: {errors}", "PASS"])

    def test_empty_input_data_text(self):
        errors = validate_task_input({
            "input_type": "text",
            "desired_output": "ner",
            "input_data": "",
        })
        assert len(errors) > 0
        _write_report("test_empty_input_data_text", [f"Errors: {errors}", "PASS"])

    def test_null_input_data(self):
        errors = validate_task_input({
            "input_type": "text",
            "desired_output": "ner",
            "input_data": None,
        })
        assert len(errors) > 0
        _write_report("test_null_input_data", [f"Errors: {errors}", "PASS"])

    def test_numeric_input_data(self):
        errors = validate_task_input({
            "input_type": "text",
            "desired_output": "ner",
            "input_data": 12345,
        })
        assert len(errors) > 0
        _write_report("test_numeric_input_data", [f"Errors: {errors}", "PASS"])

    def test_youtube_with_non_string_input(self):
        errors = validate_task_input({
            "input_type": "youtube_link",
            "desired_output": "stt",
            "input_data": {"url": "https://youtube.com"},
        })
        assert len(errors) > 0
        _write_report("test_youtube_with_non_string_input", [f"Errors: {errors}", "PASS"])

    def test_extremely_long_input(self):
        """Verify handling of very large text input."""
        large_text = "A" * (10 * 1024 * 1024)  # 10MB string
        errors = validate_task_input({
            "input_type": "text",
            "desired_output": "ner",
            "input_data": large_text,
        })
        # Should either accept or reject gracefully, not crash
        _write_report("test_extremely_long_input", [
            f"Input size: {len(large_text)} bytes",
            f"Errors: {errors}",
            "PASS (no crash)",
        ])

    def test_nested_json_bomb(self):
        """Deeply nested JSON should not crash."""
        nested = {"a": "value"}
        for _ in range(100):
            nested = {"nested": nested}
        errors = validate_task_input({
            "input_type": "text",
            "desired_output": "ner",
            "input_data": nested,
        })
        _write_report("test_nested_json_bomb", [
            "Depth: 100 levels",
            f"Errors: {errors}",
            "PASS (no crash)",
        ])

    def test_special_characters_in_input(self):
        """Unicode, null bytes, etc."""
        special_inputs = [
            "Hello\x00World",       # null byte
            "Hello\nWorld\tTab",    # control chars
            "\ud800",               # lone surrogate (if encoding allows)
            "' OR 1=1; --",         # SQL injection attempt
            "<script>alert(1)</script>",  # XSS attempt
        ]
        for text in special_inputs:
            try:
                errors = validate_task_input({
                    "input_type": "text",
                    "desired_output": "ner",
                    "input_data": text,
                })
            except Exception as e:
                # Acceptable to raise, not acceptable to crash silently
                pass
        _write_report("test_special_characters_in_input", [
            f"Tested {len(special_inputs)} special inputs",
            "PASS (no crash)",
        ])
