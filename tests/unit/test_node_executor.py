"""Unit tests for DAG node executor."""

import os
import pytest
from unittest.mock import patch, MagicMock

os.environ["DEV_MODE"] = "true"

from src.dag.catalogue import get_node
from src.dag.executors.node_executor import execute_node, _build_body


class TestNodeExecutorMockMode:
    """All nodes return mock responses in DEV_MODE."""

    def test_stt_mock(self):
        node = get_node("stt")
        result = execute_node(node, {"audio_path": "/tmp/test.mp3"})
        assert "text" in result

    def test_lang_detect_mock(self):
        node = get_node("lang_detect")
        result = execute_node(node, {"text": "Hello world"})
        assert "language" in result

    def test_translate_mock(self):
        node = get_node("translate")
        ctx = {"text": "Hallo Welt", "lang_meta": {"language": "de"}}
        result = execute_node(node, ctx)
        assert "text" in result

    def test_translate_skip_when_english(self):
        """Translate node should skip when language is already English."""
        node = get_node("translate")
        ctx = {"text": "Hello world", "lang_meta": {"language": "en"}}
        result = execute_node(node, ctx)
        assert result == "Hello world"  # Passthrough, not translated

    def test_ner_mock(self):
        node = get_node("ner")
        result = execute_node(node, {"text_en": "John lives in Berlin"})
        assert "entities" in result

    def test_sentiment_mock(self):
        node = get_node("sentiment")
        result = execute_node(node, {"text_en": "I love this!"})
        assert "sentiment" in result

    def test_summarize_mock(self):
        node = get_node("summarize")
        result = execute_node(node, {"text": "Long article..."})
        assert "summary" in result

    def test_iptc_mock(self):
        node = get_node("iptc")
        result = execute_node(node, {"text": "News article about economy"})
        assert "tags" in result

    def test_keyword_extract_mock(self):
        node = get_node("keyword_extract")
        result = execute_node(node, {"text": "Tech article about AI"})
        assert "keywords" in result

    def test_ytdlp_mock(self):
        node = get_node("ytdlp_download")
        result = execute_node(node, {"youtube_url": "https://youtube.com/watch?v=abc"})
        assert "audio_path" in result


class TestBuildBody:
    """Test HTTP body template substitution."""

    def test_simple_substitution(self):
        template = {"text": "{text}", "language": "{lang}"}
        ctx = {"text": "Hello", "lang": "en"}
        body = _build_body(template, ctx)
        assert body == {"text": "Hello", "language": "en"}

    def test_missing_field_is_none(self):
        template = {"text": "{text}"}
        ctx = {}
        body = _build_body(template, ctx)
        assert body == {"text": None}

    def test_static_value_preserved(self):
        template = {"text": "{text}", "target_language": "en"}
        ctx = {"text": "Hallo"}
        body = _build_body(template, ctx)
        assert body == {"text": "Hallo", "target_language": "en"}
