"""Tests for the LOG operator."""

import pytest
from src.core.operators.log_operator import LogOperator
from src.core.context import ExecutionContext


@pytest.fixture
def operator():
    return LogOperator()


def test_log_basic(operator):
    ctx = ExecutionContext(workflow_input={"text": "hello"})
    task_def = {
        "task_ref": "log_test",
        "type": "LOG",
        "input_parameters": {
            "message": "Processing started",
            "input_text": "{{workflow.input.text}}",
        },
    }

    result = operator.execute(task_def, ctx)
    assert result["message"] == "Processing started"
    assert result["input_text"] == "hello"
