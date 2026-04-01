"""Tests for the HTTP operator."""

import os
import pytest
from unittest.mock import patch

from src.core.operators.http_operator import HttpOperator
from src.core.context import ExecutionContext


@pytest.fixture
def operator():
    return HttpOperator()


@pytest.fixture
def ctx():
    return ExecutionContext(
        workflow_input={"file_path": "/tmp/test.mp4"},
        env={"AI_STT_URL": "http://stt:8001"},
    )


def test_mock_response(operator, ctx):
    """In DEV_MODE, HTTP operator should return mock_response."""
    task_def = {
        "task_ref": "stt_test",
        "type": "HTTP",
        "input_parameters": {
            "http_request": {
                "method": "POST",
                "url": "{{env.AI_STT_URL}}/transcribe",
                "body": {"file_path": "{{workflow.input.file_path}}"},
            },
        },
        "mock_response": {
            "text": "Mocked transcription",
            "language": "en",
        },
    }

    with patch("src.core.operators.http_operator.Config") as mock_config:
        mock_config.DEV_MODE = True
        with patch("src.core.operators.http_operator.time.sleep"):
            result = operator.execute(task_def, ctx)

    assert result["text"] == "Mocked transcription"
    assert result["language"] == "en"


def test_output_mapping(operator, ctx):
    """Output mapping should extract fields via JSONPath."""
    task_def = {
        "task_ref": "test_mapping",
        "type": "HTTP",
        "input_parameters": {
            "http_request": {
                "method": "POST",
                "url": "http://example.com/api",
                "body": {},
            },
        },
        "output_mapping": {
            "text": "$.response.body.result.transcription",
        },
    }

    mock_response = {
        "status_code": 200,
        "body": {"result": {"transcription": "hello world"}},
        "headers": {},
    }

    with patch("src.core.operators.http_operator.Config") as mock_config:
        mock_config.DEV_MODE = False
        with patch("src.core.operators.http_operator.make_request", return_value=mock_response):
            result = operator.execute(task_def, ctx)

    assert result["text"] == "hello world"
