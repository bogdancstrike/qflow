"""Tests for the SET_VARIABLE operator."""

import pytest
from src.core.operators.set_variable_operator import SetVariableOperator
from src.core.context import ExecutionContext


@pytest.fixture
def operator():
    return SetVariableOperator()


def test_set_variable(operator):
    ctx = ExecutionContext(workflow_input={})
    task_def = {
        "task_ref": "set_vars",
        "type": "SET_VARIABLE",
        "input_parameters": {
            "flag": True,
            "name": "test",
        },
    }
    result = operator.execute(task_def, ctx)
    assert ctx.variables["flag"] is True
    assert ctx.variables["name"] == "test"


def test_set_variable_with_interpolation(operator):
    ctx = ExecutionContext(workflow_input={"lang": "en"})
    task_def = {
        "task_ref": "set_vars",
        "type": "SET_VARIABLE",
        "input_parameters": {
            "detected_lang": "{{workflow.input.lang}}",
        },
    }
    operator.execute(task_def, ctx)
    assert ctx.variables["detected_lang"] == "en"
