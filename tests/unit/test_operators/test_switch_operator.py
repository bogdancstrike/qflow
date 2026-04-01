"""Tests for the SWITCH operator."""

import pytest
from src.core.operators.switch_operator import SwitchOperator
from src.core.context import ExecutionContext


@pytest.fixture
def operator():
    return SwitchOperator()


@pytest.fixture
def ctx():
    ctx = ExecutionContext(workflow_input={"text": "test"})
    ctx.set_step_output("language_detect", {"language": "en", "text": "test"})
    return ctx


def test_switch_matching_case(operator, ctx):
    task_def = {
        "task_ref": "check_lang",
        "type": "SWITCH",
        "expression": "{{steps.language_detect.output.language}}",
        "decision_cases": {
            "en": [
                {
                    "task_ref": "en_branch",
                    "type": "SET_VARIABLE",
                    "input_parameters": {"processed_text": "english text"},
                },
            ],
            "ro": [
                {
                    "task_ref": "ro_branch",
                    "type": "SET_VARIABLE",
                    "input_parameters": {"processed_text": "romanian text"},
                },
            ],
        },
        "default_case": [
            {
                "task_ref": "default_branch",
                "type": "SET_VARIABLE",
                "input_parameters": {"processed_text": "default text"},
            },
        ],
    }

    result = operator.execute(task_def, ctx)
    assert result["branch_taken"] == "en"
    assert ctx.variables["processed_text"] == "english text"
    assert "en_branch" in ctx.steps


def test_switch_default_case(operator, ctx):
    ctx.set_step_output("language_detect", {"language": "fr", "text": "test"})

    task_def = {
        "task_ref": "check_lang",
        "type": "SWITCH",
        "expression": "{{steps.language_detect.output.language}}",
        "decision_cases": {
            "en": [
                {
                    "task_ref": "en_branch",
                    "type": "SET_VARIABLE",
                    "input_parameters": {"processed_text": "english"},
                },
            ],
        },
        "default_case": [
            {
                "task_ref": "default_branch",
                "type": "SET_VARIABLE",
                "input_parameters": {"processed_text": "default"},
            },
        ],
    }

    result = operator.execute(task_def, ctx)
    assert result["branch_taken"] == "default"
    assert ctx.variables["processed_text"] == "default"
