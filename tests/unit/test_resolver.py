"""Tests for the flow strategy resolver."""

import pytest
from src.core.resolver import (
    resolve_flow, is_valid_combination, get_valid_outputs,
    get_valid_input_types_for_output, register_flow_strategy,
)


def test_resolve_video_to_ner():
    assert resolve_flow("file_upload", "ner") == "flow_video_to_ner"


def test_resolve_text_to_sentiment():
    assert resolve_flow("text", "sentiment") == "flow_text_to_sentiment"


def test_resolve_youtube_to_stt():
    assert resolve_flow("youtube_link", "stt") == "flow_youtube_to_stt"


def test_resolve_invalid_combination():
    with pytest.raises(ValueError, match="No flow strategy"):
        resolve_flow("text", "stt")


def test_is_valid_combination():
    assert is_valid_combination("file_upload", "ner") is True
    assert is_valid_combination("text", "stt") is False


def test_get_valid_outputs():
    outputs = get_valid_outputs()
    assert "ner" in outputs
    assert "sentiment" in outputs
    assert "summary" in outputs
    assert "stt" in outputs


def test_get_valid_input_types_for_output():
    inputs = get_valid_input_types_for_output("ner")
    assert "file_upload" in inputs
    assert "text" in inputs
    assert "youtube_link" in inputs


def test_register_flow_strategy():
    register_flow_strategy("custom_input", "custom_output", "flow_custom")
    assert resolve_flow("custom_input", "custom_output") == "flow_custom"
    assert is_valid_combination("custom_input", "custom_output") is True
