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

@pytest.fixture
def context():
    """Basic execution context for testing."""
    workflow_input = {
        "text": "Hello world, this is a test.",
        "file_path": "/tmp/test.mp4",
        "youtube_url": "https://youtube.com/watch?v=test123",
    }
    return dict(workflow_input)

@pytest.fixture
def context_with_steps(context):
    """Context pre-populated with step outputs for testing downstream steps."""
    context["text"] = "This is a transcribed text about artificial intelligence."
    context["lang"] = "en"
    context["lang_meta"] = {
        "language": "en",
        "confidence": 0.98,
    }
    context["text_en"] = "This is a translated text about artificial intelligence."
    return context
