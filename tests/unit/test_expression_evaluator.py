"""Tests for the expression evaluator."""

import pytest
from src.core.expression_evaluator import evaluate_expression, evaluate_condition
from src.core.context import ExecutionContext


@pytest.fixture
def ctx():
    ctx = ExecutionContext(workflow_input={"text": "test"})
    ctx.set_step_output("lang", {"language": "en"})
    ctx.set_step_output("counter", {"value": 5})
    return ctx


def test_evaluate_simple_value(ctx):
    result = evaluate_expression("{{steps.lang.output.language}}", ctx)
    assert result == "en"


def test_evaluate_condition_true(ctx):
    assert evaluate_condition("{{steps.counter.output.value < 10}}", ctx) is True


def test_evaluate_condition_false(ctx):
    assert evaluate_condition("{{steps.counter.output.value > 10}}", ctx) is False


def test_evaluate_equality(ctx):
    result = evaluate_expression("{{steps.lang.output.language == 'en'}}", ctx)
    assert result is True


def test_evaluate_inequality(ctx):
    result = evaluate_expression("{{steps.lang.output.language != 'en'}}", ctx)
    assert result is False


def test_evaluate_boolean_string():
    ctx = ExecutionContext(workflow_input={})
    result = evaluate_condition("true", ctx)
    assert result is True

    result = evaluate_condition("false", ctx)
    assert result is False
