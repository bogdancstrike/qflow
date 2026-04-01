"""Tests for the DO_WHILE operator."""

import pytest
from src.core.operators.do_while_operator import DoWhileOperator
from src.core.context import ExecutionContext


@pytest.fixture
def operator():
    return DoWhileOperator()


@pytest.fixture
def ctx():
    return ExecutionContext(workflow_input={})


def test_do_while_runs_once_when_false(operator, ctx):
    task_def = {
        "task_ref": "loop_test",
        "type": "DO_WHILE",
        "loop_condition": "false",
        "loop_over": [
            {
                "task_ref": "loop_body",
                "type": "SET_VARIABLE",
                "input_parameters": {"ran": True},
            },
        ],
    }

    result = operator.execute(task_def, ctx)
    assert result["iterations"] == 1  # DO_WHILE runs at least once
    assert ctx.variables["ran"] is True


def test_do_while_max_iterations(operator, ctx):
    task_def = {
        "task_ref": "loop_test",
        "type": "DO_WHILE",
        "loop_condition": "true",  # Always true
        "max_iterations": 3,
        "loop_over": [
            {
                "task_ref": "loop_body",
                "type": "LOG",
                "input_parameters": {"message": "iterating"},
            },
        ],
    }

    result = operator.execute(task_def, ctx)
    assert result["iterations"] == 3
