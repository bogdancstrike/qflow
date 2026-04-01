"""Tests for the FORK_JOIN operator."""

import pytest
from src.core.operators.fork_join_operator import ForkJoinOperator
from src.core.context import ExecutionContext


@pytest.fixture
def operator():
    return ForkJoinOperator()


@pytest.fixture
def ctx():
    ctx = ExecutionContext(workflow_input={"text": "test"})
    return ctx


def test_fork_join_parallel(operator, ctx):
    task_def = {
        "task_ref": "parallel_test",
        "type": "FORK_JOIN",
        "fork_tasks": [
            [
                {
                    "task_ref": "branch_a",
                    "type": "SET_VARIABLE",
                    "input_parameters": {"a_done": True},
                },
            ],
            [
                {
                    "task_ref": "branch_b",
                    "type": "SET_VARIABLE",
                    "input_parameters": {"b_done": True},
                },
            ],
        ],
        "join_on": ["branch_a", "branch_b"],
    }

    result = operator.execute(task_def, ctx)

    assert "branch_a" in ctx.steps
    assert "branch_b" in ctx.steps
    assert ctx.variables["a_done"] is True
    assert ctx.variables["b_done"] is True


def test_fork_join_missing_join_on(operator, ctx):
    task_def = {
        "task_ref": "parallel_fail",
        "type": "FORK_JOIN",
        "fork_tasks": [
            [
                {
                    "task_ref": "branch_a",
                    "type": "SET_VARIABLE",
                    "input_parameters": {"val": 1},
                },
            ],
        ],
        "join_on": ["branch_a", "nonexistent_branch"],
    }

    with pytest.raises(RuntimeError, match="missing join_on"):
        operator.execute(task_def, ctx)
