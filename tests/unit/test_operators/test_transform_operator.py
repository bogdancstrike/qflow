"""Tests for the TRANSFORM operator."""

import pytest
from src.core.operators.transform_operator import TransformOperator
from src.core.context import ExecutionContext


@pytest.fixture
def operator():
    return TransformOperator()


@pytest.fixture
def ctx():
    ctx = ExecutionContext(workflow_input={"text": "hello"})
    ctx.set_step_output("ner", {"entities": [{"text": "John", "type": "PERSON"}]})
    ctx.set_step_output("sentiment", {"score": 0.8, "label": "positive"})
    return ctx


def test_transform_passthrough(operator, ctx):
    task_def = {
        "task_ref": "passthrough",
        "type": "TRANSFORM",
        "input_parameters": {"text": "{{workflow.input.text}}"},
    }
    result = operator.execute(task_def, ctx)
    assert result == {"text": "hello"}


def test_transform_string_expression(operator, ctx):
    task_def = {
        "task_ref": "extract",
        "type": "TRANSFORM",
        "input_parameters": {"text": "{{workflow.input.text}}"},
        "expression": "$.text",
    }
    result = operator.execute(task_def, ctx)
    assert result == "hello"


def test_transform_dict_expression(operator, ctx):
    task_def = {
        "task_ref": "merge",
        "type": "TRANSFORM",
        "input_parameters": {
            "entities": "{{steps.ner.output.entities}}",
            "score": "{{steps.sentiment.output.score}}",
        },
        "expression": {
            "combined": {
                "entities": "$.entities",
                "sentiment": "$.score",
            },
        },
    }
    result = operator.execute(task_def, ctx)
    assert result["combined"]["entities"] == [{"text": "John", "type": "PERSON"}]
    assert result["combined"]["sentiment"] == 0.8
