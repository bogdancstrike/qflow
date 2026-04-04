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
