"""Tests for primitive/flow loading and validation."""

import pytest
import os

from src.templating.loader import load_primitives, load_flows
from src.templating.validator import validate_task_template, validate_flow_definition, TemplateValidationError


BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_load_primitives():
    primitives = load_primitives(os.path.join(BASE_DIR, "src", "templating", "templates"))
    assert len(primitives) >= 10
    assert "HTTP" in primitives
    assert "SWITCH" in primitives
    assert "FORK_JOIN" in primitives
    assert "TRANSFORM" in primitives
    assert "LOG" in primitives


def test_primitive_has_schema_and_examples():
    primitives = load_primitives(os.path.join(BASE_DIR, "src", "templating", "templates"))
    http = primitives["HTTP"]
    assert "schema" in http
    assert "examples" in http
    assert http["name"] == "HTTP Request"


def test_load_flows():
    flows = load_flows(os.path.join(BASE_DIR, "src", "templating", "flows"))
    assert len(flows) >= 9
    assert "flow_video_to_ner" in flows
    assert "flow_text_to_ner" in flows
    assert "flow_youtube_to_stt" in flows


def test_validate_valid_http_task():
    template = {
        "task_ref": "test_http",
        "type": "HTTP",
        "input_parameters": {
            "http_request": {
                "method": "POST",
                "url": "http://example.com/api",
            },
        },
    }
    validate_task_template(template)


def test_validate_missing_task_ref():
    with pytest.raises(TemplateValidationError, match="task_ref"):
        validate_task_template({"type": "HTTP"})


def test_validate_missing_type():
    with pytest.raises(TemplateValidationError, match="type"):
        validate_task_template({"task_ref": "test"})


def test_validate_invalid_type():
    with pytest.raises(TemplateValidationError, match="invalid type"):
        validate_task_template({"task_ref": "test", "type": "INVALID"})


def test_validate_switch_missing_expression():
    with pytest.raises(TemplateValidationError, match="expression"):
        validate_task_template({"task_ref": "test", "type": "SWITCH"})


def test_validate_fork_join_missing_fork_tasks():
    with pytest.raises(TemplateValidationError, match="fork_tasks"):
        validate_task_template({"task_ref": "test", "type": "FORK_JOIN"})


def test_validate_flow_duplicate_task_refs():
    flow = {
        "flow_id": "test_flow",
        "tasks": [
            {"task_ref": "step1", "type": "LOG", "input_parameters": {}},
            {"task_ref": "step1", "type": "LOG", "input_parameters": {}},
        ],
    }
    with pytest.raises(TemplateValidationError, match="duplicate"):
        validate_flow_definition(flow)


def test_validate_flow_valid():
    flow = {
        "flow_id": "test_flow",
        "tasks": [
            {"task_ref": "step1", "type": "LOG", "input_parameters": {}},
            {"task_ref": "step2", "type": "TRANSFORM", "input_parameters": {"x": "1"}},
        ],
    }
    validate_flow_definition(flow)
