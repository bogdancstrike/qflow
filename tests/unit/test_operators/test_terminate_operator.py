"""Tests for the TERMINATE operator."""

import pytest
from src.core.operators.terminate_operator import TerminateOperator
from src.core.operators.base import TerminateFlowException
from src.core.context import ExecutionContext


@pytest.fixture
def operator():
    return TerminateOperator()


def test_terminate_raises_exception(operator):
    ctx = ExecutionContext(workflow_input={})
    task_def = {
        "task_ref": "abort",
        "type": "TERMINATE",
        "termination_status": "FAILED",
        "termination_reason": "Empty input",
        "output": {"error": "no_data"},
    }

    with pytest.raises(TerminateFlowException) as exc_info:
        operator.execute(task_def, ctx)

    assert exc_info.value.status == "FAILED"
    assert exc_info.value.reason == "Empty input"
    assert exc_info.value.output == {"error": "no_data"}


def test_terminate_with_interpolation(operator):
    ctx = ExecutionContext(workflow_input={"reason": "bad input"})
    task_def = {
        "task_ref": "abort",
        "type": "TERMINATE",
        "termination_status": "FAILED",
        "termination_reason": "{{workflow.input.reason}}",
        "output": {},
    }

    with pytest.raises(TerminateFlowException) as exc_info:
        operator.execute(task_def, ctx)

    assert exc_info.value.reason == "bad input"
