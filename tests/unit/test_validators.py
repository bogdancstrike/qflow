"""Unit tests for input validation."""

import pytest
from src.api.validators import validate_task_input, _validate_text_security, _validate_file_path


class TestValidateTaskInput:

    def test_valid_text_ner(self):
        errors = validate_task_input({"text": "Hello"}, ["ner_result"])
        assert errors == []

    def test_valid_file_summary(self):
        errors = validate_task_input({"file_path": "/tmp/test.mp4"}, ["summary"])
        assert errors == []

    def test_valid_multi_output(self):
        errors = validate_task_input(
            {"text": "Hello"}, ["ner_result", "sentiment_result", "summary"]
        )
        assert errors == []

    def test_empty_input_data(self):
        errors = validate_task_input({}, ["ner_result"])
        assert len(errors) > 0
        assert "input_data" in errors[0].lower()

    def test_none_input_data(self):
        errors = validate_task_input(None, ["ner_result"])
        assert len(errors) > 0

    def test_empty_outputs(self):
        errors = validate_task_input({"text": "Hello"}, [])
        assert len(errors) > 0
        assert "outputs" in errors[0].lower()

    def test_none_outputs(self):
        errors = validate_task_input({"text": "Hello"}, None)
        assert len(errors) > 0

    def test_unknown_output_type(self):
        errors = validate_task_input({"text": "Hello"}, ["nonexistent"])
        assert len(errors) > 0
        assert "Unknown output" in errors[0]

    def test_template_injection(self):
        errors = validate_task_input({"text": "{{malicious}}"}, ["ner_result"])
        assert len(errors) > 0
        assert "template injection" in errors[0].lower()

    def test_path_traversal(self):
        errors = validate_task_input({"file_path": "../../etc/passwd"}, ["summary"])
        assert len(errors) > 0
        assert "traversal" in errors[0].lower()

    def test_null_byte_in_path(self):
        errors = validate_task_input({"file_path": "/tmp/test\x00.mp4"}, ["summary"])
        assert len(errors) > 0


class TestTextSecurity:

    def test_clean_text(self):
        assert _validate_text_security("Hello world") == []

    def test_jinja_template(self):
        errors = _validate_text_security("{{ config.items() }}")
        assert len(errors) > 0

    def test_jinja_block(self):
        errors = _validate_text_security("{% for x in y %}{{ x }}{% endfor %}")
        assert len(errors) > 0


class TestFilePathValidation:

    def test_clean_path(self):
        assert _validate_file_path("/tmp/uploads/test.mp4") == []

    def test_traversal(self):
        errors = _validate_file_path("../../../etc/passwd")
        assert len(errors) > 0

    def test_null_byte(self):
        errors = _validate_file_path("/tmp/test\x00.mp4")
        assert len(errors) > 0
