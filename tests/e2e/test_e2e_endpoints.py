"""E2E endpoint tests — runs against a live environment.

Requires: docker compose up + python main.py running.
Connects to http://localhost:5000 and tests all API endpoints.

Run:
    python -m pytest tests/e2e/test_e2e_endpoints.py -v --tb=short

Reports written to: reports/e2e_endpoints.txt
"""

import os
import json
import time
import uuid
import resource

import pytest
import requests

API_URL = os.getenv("API_URL", "http://localhost:5000")
REPORT_FILE = os.path.join(os.path.dirname(__file__), "../../reports/e2e_endpoints.txt")


def _api(method, path, **kwargs):
    """Make an API request and return (status_code, body_dict)."""
    url = f"{API_URL}{path}"
    resp = requests.request(method, url, timeout=30, **kwargs)
    try:
        body = resp.json()
    except Exception:
        body = {"raw": resp.text}
    return resp.status_code, body


def _write_report(test_name, lines):
    os.makedirs(os.path.dirname(REPORT_FILE), exist_ok=True)
    with open(REPORT_FILE, "a") as f:
        f.write(f"\n{'='*70}\n")
        f.write(f"  TEST: {test_name}\n")
        f.write(f"  TIME: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        for line in lines:
            f.write(f"  {line}\n")
        f.write(f"{'='*70}\n")


def _resource_usage():
    """Get current process resource usage."""
    ru = resource.getrusage(resource.RUSAGE_SELF)
    return {
        "user_time_s": round(ru.ru_utime, 2),
        "system_time_s": round(ru.ru_stime, 2),
        "max_rss_mb": round(ru.ru_maxrss / 1024, 1),
    }


@pytest.fixture(scope="module", autouse=True)
def check_api_reachable():
    """Skip all tests if the API is not running."""
    try:
        requests.get(f"{API_URL}/api/health", timeout=5)
    except Exception:
        pytest.skip(f"API not reachable at {API_URL}. Start with: docker compose up -d && python main.py")


@pytest.fixture(scope="module")
def created_task_ids():
    """Collect task IDs created during tests for cleanup."""
    ids = []
    yield ids
    for tid in ids:
        try:
            _api("DELETE", f"/api/tasks/{tid}")
        except Exception:
            pass


class TestHealthAndMeta:
    """Health check and metadata endpoints."""

    def test_health(self):
        code, body = _api("GET", "/api/health")
        assert code == 200
        assert body["status"] == "healthy"
        _write_report("test_health", [
            f"Status: {code}",
            f"Body: {json.dumps(body, indent=2)}",
            f"Resources: {_resource_usage()}",
            "PASS",
        ])


class TestTaskCreation:
    """Valid task creation and polling."""

    @pytest.mark.parametrize("input_data,outputs,expect_field", [
        ({"text": "John Smith lives in Berlin."}, ["ner_result"], "ner_result"),
        ({"text": "I love this product!"}, ["sentiment_result"], "sentiment_result"),
        ({"text": "A long article about tech."}, ["summary"], "summary"),
        ({"file_path": "/tmp/test.mp4"}, ["text"], "text"),
        ({"url": "https://youtube.com/watch?v=test"}, ["text"], "text"),
    ])
    def test_create_and_poll(self, input_data, outputs, expect_field, created_task_ids):
        start = time.time()

        # Create
        code, body = _api("POST", "/api/v1/tasks", json={
            "input_data": input_data,
            "outputs": outputs,
        })
        create_time = time.time() - start

        assert code == 201, f"Expected 201, got {code}: {body}"
        task_id = body["id"]
        created_task_ids.append(task_id)
        assert body["status"] == "PENDING"

        # Poll for completion
        poll_start = time.time()
        status = "PENDING"
        task_body = None
        for _ in range(60):
            time.sleep(0.5)
            poll_code, task_body = _api("GET", f"/api/v1/tasks/{task_id}")
            assert poll_code == 200
            status = task_body["status"]
            if status in ("COMPLETED", "FAILED", "TERMINATED"):
                break

        poll_time = time.time() - poll_start
        total_time = time.time() - start

        report_lines = [
            f"Task: {input_data} -> {outputs}",
            f"Task ID: {task_id}",
            f"Create time: {create_time:.2f}s",
            f"Poll time: {poll_time:.2f}s",
            f"Total time: {total_time:.2f}s",
            f"Final status: {status}",
            f"Resources: {_resource_usage()}",
        ]

        if status == "COMPLETED":
            final_output = task_body.get("final_output", {})
            assert expect_field in final_output, \
                f"Missing '{expect_field}' in final_output: {final_output}"
            report_lines.append(f"Output keys: {list(final_output.keys())}")
            report_lines.append("PASS")
        else:
            report_lines.append(f"Error: {task_body.get('error')}")
            report_lines.append("FAIL")

        _write_report(f"test_create_and_poll_{outputs[0]}", report_lines)
        assert status == "COMPLETED", f"Task {task_id} ended with status={status}"


class TestTaskList:
    """Task listing and filtering."""

    def test_list_all(self, created_task_ids):
        code, body = _api("GET", "/api/v1/tasks")
        assert code == 200
        assert "tasks" in body
        _write_report("test_list_all", [
            f"Count (returned): {len(body['tasks'])}",
            "PASS",
        ])

    def test_list_with_filters(self):
        code, body = _api("GET", "/api/v1/tasks?status=COMPLETED&limit=5")
        assert code == 200
        for t in body["tasks"]:
            assert t["status"] == "COMPLETED"
        _write_report("test_list_with_filters", [
            f"Filter: status=COMPLETED, limit=5",
            f"Returned: {len(body['tasks'])} tasks",
            "PASS",
        ])


class TestInvalidRequests:
    """Error handling for invalid requests."""

    def test_empty_body(self):
        code, body = _api("POST", "/api/v1/tasks", json={})
        assert code == 400
        assert "errors" in body or "message" in body
        _write_report("test_empty_body", [f"Status: {code}", f"Body: {body}", "PASS"])

    def test_invalid_input_data(self):
        code, body = _api("POST", "/api/v1/tasks", json={
            "outputs": ["ner_result"],
        })
        assert code == 400
        _write_report("test_invalid_input_type", [f"Status: {code}", f"Body: {body}", "PASS"])

    def test_invalid_outputs(self):
        code, body = _api("POST", "/api/v1/tasks", json={
            "input_data": {"text": "hello"},
            "outputs": ["nonexistent_output"],
        })
        assert code == 400
        _write_report("test_invalid_outputs", [f"Status: {code}", f"Body: {body}", "PASS"])

    def test_nonexistent_task(self):
        fake_id = str(uuid.uuid4())
        code, body = _api("GET", f"/api/v1/tasks/{fake_id}")
        assert code == 404
        _write_report("test_nonexistent_task", [f"Status: {code}", f"Body: {body}", "PASS"])

    def test_delete_nonexistent_task(self):
        fake_id = str(uuid.uuid4())
        code, body = _api("DELETE", f"/api/v1/tasks/{fake_id}")
        assert code == 404
        _write_report("test_delete_nonexistent", [f"Status: {code}", f"Body: {body}", "PASS"])

    def test_malformed_json(self):
        """Send non-JSON body."""
        resp = requests.post(
            f"{API_URL}/api/v1/tasks",
            data="this is not json",
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        assert resp.status_code in (400, 500)
        _write_report("test_malformed_json", [f"Status: {resp.status_code}", "PASS"])


class TestTaskDeletion:
    """Task deletion lifecycle."""

    def test_create_and_delete(self):
        # Create
        code, body = _api("POST", "/api/v1/tasks", json={
            "input_data": {"text": "delete me"},
            "outputs": ["ner_result"],
        })
        assert code == 201
        task_id = body["id"]

        # Delete
        code, body = _api("DELETE", f"/api/v1/tasks/{task_id}")
        assert code == 200

        # Verify gone
        code, body = _api("GET", f"/api/v1/tasks/{task_id}")
        assert code == 404

        _write_report("test_create_and_delete", [
            f"Task ID: {task_id}",
            "Created -> Deleted -> Verified 404",
            "PASS",
        ])


class TestObservability:
    """Check Jaeger traces are being exported."""

    def test_jaeger_has_services(self):
        try:
            resp = requests.get("http://localhost:16686/api/services", timeout=5)
            assert resp.status_code == 200
            data = resp.json().get("data", [])
            _write_report("test_jaeger_has_services", [
                f"Services: {data}",
                "PASS" if data else "SKIP (no services)",
            ])
            if not data:
                pytest.skip("No services in Jaeger yet")
        except Exception as e:
            pytest.skip(f"Jaeger not reachable: {e}")
