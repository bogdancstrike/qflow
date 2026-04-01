"""Tests for the flow executor with mocked operators."""

import pytest
from src.core.context import ExecutionContext
from src.core.executor import execute_flow, execute_single_task
from src.core.operators.base import TerminateFlowException


@pytest.fixture
def ctx():
    return ExecutionContext(
        workflow_input={"text": "test input"},
        env={"DEV_MODE": "true"},
    )


def test_execute_simple_transform(ctx):
    task_def = {
        "task_ref": "transform_1",
        "type": "TRANSFORM",
        "input_parameters": {"text": "{{workflow.input.text}}"},
        "expression": "$.text",
    }
    execute_single_task(task_def, ctx)
    assert ctx.steps["transform_1"]["output"] == "test input"
    assert ctx.steps["transform_1"]["status"] == "SUCCESS"


def test_execute_set_variable(ctx):
    task_def = {
        "task_ref": "set_var_1",
        "type": "SET_VARIABLE",
        "input_parameters": {"my_var": "my_value"},
    }
    execute_single_task(task_def, ctx)
    assert ctx.variables["my_var"] == "my_value"


def test_execute_log(ctx):
    task_def = {
        "task_ref": "log_1",
        "type": "LOG",
        "input_parameters": {"message": "Test log", "text": "{{workflow.input.text}}"},
    }
    execute_single_task(task_def, ctx)
    assert ctx.steps["log_1"]["status"] == "SUCCESS"
    assert ctx.steps["log_1"]["output"]["message"] == "Test log"


def test_execute_terminate(ctx):
    task_def = {
        "task_ref": "terminate_1",
        "type": "TERMINATE",
        "termination_status": "FAILED",
        "termination_reason": "Test abort",
        "output": {"error": "test"},
    }
    with pytest.raises(TerminateFlowException) as exc_info:
        execute_single_task(task_def, ctx)
    assert exc_info.value.status == "FAILED"
    assert exc_info.value.reason == "Test abort"


def test_execute_flow_with_terminate(ctx):
    flow_def = {
        "flow_id": "test_flow",
        "tasks": [
            {
                "task_ref": "step1",
                "type": "TRANSFORM",
                "input_parameters": {"val": "hello"},
                "expression": "$.val",
            },
            {
                "task_ref": "abort",
                "type": "TERMINATE",
                "termination_status": "FAILED",
                "termination_reason": "Aborting",
                "output": {"stopped_at": "step2"},
            },
            {
                "task_ref": "step3",
                "type": "LOG",
                "input_parameters": {"message": "Should not run"},
            },
        ],
    }
    result = execute_flow(flow_def, ctx)
    assert result["_terminated"] is True
    assert result["status"] == "FAILED"
    # step3 should not have executed
    assert "step3" not in ctx.steps


def test_execute_flow_output_parameters(ctx):
    flow_def = {
        "flow_id": "test_flow",
        "output_parameters": {"result": "{{steps.step1.output}}"},
        "tasks": [
            {
                "task_ref": "step1",
                "type": "TRANSFORM",
                "input_parameters": {"val": "output_value"},
                "expression": "$.val",
            },
        ],
    }
    result = execute_flow(flow_def, ctx)
    assert result["result"] == "output_value"


def test_optional_task_failure(ctx):
    task_def = {
        "task_ref": "optional_step",
        "type": "HTTP",
        "optional": True,
        "input_parameters": {
            "http_request": {
                "method": "POST",
                "url": "http://nonexistent:9999/fail",
            },
        },
    }
    # Should not raise even though HTTP will fail
    execute_single_task(task_def, ctx)
    assert ctx.steps["optional_step"]["status"] == "FAILED"
