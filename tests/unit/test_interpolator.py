"""Tests for the variable interpolation engine."""

import pytest
from src.core.interpolator import interpolate
from src.core.context import ExecutionContext


@pytest.fixture
def ctx():
    ctx = ExecutionContext(
        workflow_input={"text": "hello", "file_path": "/tmp/test.mp4"},
        env={"AI_STT_URL": "http://stt:8001", "TOKEN": "secret"},
    )
    ctx.set_step_output("stt", {"text": "transcribed", "language": "en"})
    ctx.set_variable("needs_translation", False)
    return ctx


def test_workflow_input(ctx):
    result = interpolate("{{workflow.input.text}}", ctx)
    assert result == "hello"


def test_workflow_input_nested(ctx):
    result = interpolate("{{workflow.input.file_path}}", ctx)
    assert result == "/tmp/test.mp4"


def test_env_variable(ctx):
    result = interpolate("{{env.AI_STT_URL}}", ctx)
    assert result == "http://stt:8001"


def test_step_output(ctx):
    result = interpolate("{{steps.stt.output.text}}", ctx)
    assert result == "transcribed"


def test_step_output_nested(ctx):
    result = interpolate("{{steps.stt.output.language}}", ctx)
    assert result == "en"


def test_workflow_variables(ctx):
    result = interpolate("{{workflow.variables.needs_translation}}", ctx)
    assert result is False


def test_now_function(ctx):
    result = interpolate("{{now()}}", ctx)
    assert isinstance(result, str)
    assert "T" in result  # ISO format


def test_len_function(ctx):
    result = interpolate("{{len(steps.stt.output.text)}}", ctx)
    assert result == len("transcribed")


def test_string_interpolation(ctx):
    result = interpolate("URL is {{env.AI_STT_URL}}/transcribe", ctx)
    assert result == "URL is http://stt:8001/transcribe"


def test_dict_interpolation(ctx):
    template = {
        "url": "{{env.AI_STT_URL}}/transcribe",
        "body": {"text": "{{steps.stt.output.text}}"},
    }
    result = interpolate(template, ctx)
    assert result["url"] == "http://stt:8001/transcribe"
    assert result["body"]["text"] == "transcribed"


def test_list_interpolation(ctx):
    template = ["{{workflow.input.text}}", "{{steps.stt.output.language}}"]
    result = interpolate(template, ctx)
    assert result == ["hello", "en"]


def test_full_expression_preserves_type(ctx):
    # A single expression should preserve its type (not stringify)
    result = interpolate("{{workflow.variables.needs_translation}}", ctx)
    assert result is False
    assert isinstance(result, bool)


def test_missing_step_returns_none(ctx):
    result = interpolate("{{steps.nonexistent.output.field}}", ctx)
    assert result is None


def test_comparison_expression(ctx):
    result = interpolate("{{steps.stt.output.language != 'en'}}", ctx)
    assert result is False


def test_equality_expression(ctx):
    result = interpolate("{{steps.stt.output.language == 'en'}}", ctx)
    assert result is True
