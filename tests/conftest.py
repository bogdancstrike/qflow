"""Shared test fixtures."""

import os
import sys
from pathlib import Path

# Ensure src/ is on the path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "src"))
sys.path.insert(0, str(BASE_DIR))

# Set test environment
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("DATABASE_URL", "sqlite:///test.db")
os.environ.setdefault("KAFKA_BOOTSTRAP_SERVERS", "localhost:9094")
os.environ.setdefault("LOG_LEVEL", "WARNING")

import pytest
from src.core.context import ExecutionContext


@pytest.fixture
def context():
    """Basic execution context for testing."""
    workflow_input = {
        "text": "Hello world, this is a test.",
        "file_path": "/tmp/test.mp4",
        "youtube_url": "https://youtube.com/watch?v=test123",
    }
    env = {
        "AI_STT_URL": "http://stt-service:8001",
        "AI_STT_TOKEN": "test-token",
        "AI_NER_URL": "http://ner-service:8002",
        "AI_TRANSLATE_URL": "http://translate-service:8003",
        "AI_LANGDETECT_URL": "http://langdetect-service:8004",
        "AI_SENTIMENT_URL": "http://sentiment-service:8005",
        "AI_SUMMARY_URL": "http://summary-service:8006",
        "AI_TAXONOMY_URL": "http://taxonomy-service:8007",
        "DEV_MODE": "true",
    }
    return ExecutionContext(workflow_input, env)


@pytest.fixture
def context_with_steps(context):
    """Context pre-populated with step outputs for testing downstream steps."""
    context.set_step_output("stt", {
        "text": "This is a transcribed text about artificial intelligence.",
        "language": "en",
    })
    context.set_step_output("language_detect", {
        "text": "This is a transcribed text about artificial intelligence.",
        "language": "en",
        "confidence": 0.98,
    })
    context.set_step_output("translate_to_en", {
        "text": "This is a translated text about artificial intelligence.",
        "source_lang": "ro",
        "target_lang": "en",
    })
    return context
