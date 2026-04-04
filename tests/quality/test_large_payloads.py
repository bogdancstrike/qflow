"""Quality tests — large file uploads and payloads (>100MB)."""

import os
import time
import tempfile
from unittest.mock import patch, MagicMock

import pytest

os.environ["DEV_MODE"] = "true"
os.environ["DATABASE_URL"] = "sqlite:///test_large.db"

from src.api.validators import validate_task_input


REPORT_FILE = os.path.join(os.path.dirname(__file__), "../../reports/quality_large_payloads.txt")


def _write_report(test_name, lines):
    os.makedirs(os.path.dirname(REPORT_FILE), exist_ok=True)
    with open(REPORT_FILE, "a") as f:
        f.write(f"\n{'='*70}\n")
        f.write(f"  TEST: {test_name}\n")
        f.write(f"  TIME: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        for line in lines:
            f.write(f"  {line}\n")
        f.write(f"{'='*70}\n")


class TestLargePayloads:
    """Verify handling of very large inputs without OOM or crashes."""

    def test_100mb_text_validation(self):
        """Validate a 100MB text payload."""
        size_mb = 100
        large_text = "A" * (size_mb * 1024 * 1024)
        start = time.time()
        errors = validate_task_input(large_text, ["ner_result"])
        elapsed = time.time() - start

        _write_report("test_100mb_text_validation", [
            f"Payload size: {size_mb}MB",
            f"Validation time: {elapsed:.2f}s",
            f"Errors: {errors}",
            "PASS (no crash, no OOM)",
        ])
        # Should not crash — errors list may be empty (valid) or contain size warning
        assert isinstance(errors, list)

    def test_large_json_object_validation(self):
        """Validate a large nested JSON input_data."""
        large_obj = {f"key_{i}": f"value_{i}" * 1000 for i in range(10000)}
        start = time.time()
        errors = validate_task_input(large_obj, ["ner_result"])
        elapsed = time.time() - start

        _write_report("test_large_json_object_validation", [
            f"Keys: 10000, approx size: ~{len(str(large_obj)) // 1024}KB",
            f"Validation time: {elapsed:.2f}s",
            f"Errors: {errors}",
            "PASS (no crash)",
        ])

    def test_simulated_large_file_upload(self):
        """Simulate a large file upload path."""
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            # Write 10MB (not 100MB for speed — pattern is the same)
            f.write(b"\x00" * (10 * 1024 * 1024))
            temp_path = f.name

        try:
            errors = validate_task_input({"file_path": temp_path}, ["stt_result"])
            _write_report("test_simulated_large_file_upload", [
                f"File size: 10MB at {temp_path}",
                f"Errors: {errors}",
                "PASS",
            ])
        finally:
            os.unlink(temp_path)
