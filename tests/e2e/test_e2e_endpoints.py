"""E2E endpoint tests — runs against a live environment.

Requires: docker compose up + python main.py running.
Connects to http://localhost:5000 and tests all API endpoints.
Tests ALL possible DAG flows: text, file, youtube, multi-output.

Run:
    python -m pytest tests/e2e/test_e2e_endpoints.py -v --tb=short

Reports written to: reports/e2e_endpoints.txt
"""

import os
import json
import time
import uuid
import statistics
import resource

import pytest
import requests

API_URL = os.getenv("API_URL", "http://localhost:5000")
REPORT_FILE = os.path.join(os.path.dirname(__file__), "../../reports/e2e_endpoints.txt")

TASKS_URL = "/api/v1/tasks"
FLOWS_URL = "/api/v1/flows"
HEALTH_URL = "/api/health"
LIVENESS_URL = "/api/liveness"
READINESS_URL = "/api/readiness"


def _api(method, path, **kwargs):
    """Make an API request. Returns (status_code, body_dict, elapsed_ms)."""
    url = f"{API_URL}{path}"
    start = time.time()
    resp = requests.request(method, url, timeout=30, **kwargs)
    elapsed_ms = int((time.time() - start) * 1000)
    try:
        body = resp.json()
    except Exception:
        body = {"raw": resp.text}
    return resp.status_code, body, elapsed_ms


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
    ru = resource.getrusage(resource.RUSAGE_SELF)
    return {
        "user_time_s": round(ru.ru_utime, 2),
        "system_time_s": round(ru.ru_stime, 2),
        "max_rss_mb": round(ru.ru_maxrss / 1024, 1),
    }


def _poll_task(task_id, max_polls=60):
    """Poll a task until it completes. Returns (status, task_body, poll_times_ms)."""
    poll_times = []
    task_body = None
    status = "PENDING"
    for _ in range(max_polls):
        time.sleep(0.5)
        code, task_body, elapsed = _api("GET", f"{TASKS_URL}/{task_id}")
        poll_times.append(elapsed)
        assert code == 200
        status = task_body["status"]
        if status in ("COMPLETED", "FAILED", "TERMINATED"):
            break
    return status, task_body, poll_times


def _create_and_poll(input_data, outputs, test_name):
    """Create a task and poll for completion. Returns (task_body, durations)."""
    create_code, create_body, create_ms = _api("POST", TASKS_URL, json={
        "input_data": input_data,
        "outputs": outputs,
    })
    assert create_code == 201, f"Expected 201, got {create_code}: {create_body}"

    task_id = create_body["id"]
    assert create_body["status"] == "PENDING"

    status, task_body, poll_times = _poll_task(task_id)
    total_ms = create_ms + sum(poll_times)

    report_lines = [
        f"POST {TASKS_URL}",
        f"  Body: input_data={json.dumps(input_data)[:100]}, outputs={outputs}",
        f"  Create: HTTP 201, {create_ms}ms",
        f"  Task ID: {task_id}",
        f"  Input type: {create_body.get('input_type')}",
        f"  Plan: {create_body.get('execution_plan', {}).get('ingest_steps', [])} + "
        f"{len(create_body.get('execution_plan', {}).get('branches', []))} branches",
        f"  Poll count: {len(poll_times)}",
        f"  Poll times: p50={int(statistics.median(poll_times))}ms, "
        f"p95={int(sorted(poll_times)[int(len(poll_times)*0.95)])if poll_times else 0}ms",
        f"  Final status: {status}",
        f"  Total time: {total_ms}ms",
        f"  Resources: {_resource_usage()}",
    ]

    if status == "COMPLETED":
        final_output = task_body.get("final_output", {})
        report_lines.append(f"  Output keys: {list(final_output.keys())}")
        report_lines.append("PASS")
    else:
        report_lines.append(f"  Error: {task_body.get('error')}")
        report_lines.append("FAIL")

    _write_report(test_name, report_lines)
    return task_body, {"create_ms": create_ms, "poll_times": poll_times, "total_ms": total_ms}


@pytest.fixture(scope="module", autouse=True)
def check_api_reachable():
    try:
        requests.get(f"{API_URL}{HEALTH_URL}", timeout=5)
    except Exception:
        pytest.skip(f"API not reachable at {API_URL}. Start with: docker compose up -d && python main.py")


@pytest.fixture(scope="module")
def created_task_ids():
    ids = []
    yield ids
    for tid in ids:
        try:
            _api("DELETE", f"{TASKS_URL}/{tid}")
        except Exception:
            pass


# ============================================================
# System/Health endpoints
# ============================================================

class TestHealthAndMeta:

    def test_health(self):
        code, body, ms = _api("GET", HEALTH_URL)
        assert code == 200
        assert body["status"] in ("healthy", "degraded")
        assert "checks" in body
        _write_report("test_health", [
            f"GET {HEALTH_URL} -> HTTP {code} ({ms}ms)",
            f"Status: {body['status']}",
            f"Checks: {json.dumps(body.get('checks', {}), indent=2)}",
            f"Resources: {_resource_usage()}",
            "PASS",
        ])

    def test_liveness(self):
        code, body, ms = _api("GET", LIVENESS_URL)
        assert code == 200
        assert body["status"] == "alive"
        _write_report("test_liveness", [
            f"GET {LIVENESS_URL} -> HTTP {code} ({ms}ms)",
            f"Body: {body}",
            "PASS",
        ])

    def test_readiness(self):
        code, body, ms = _api("GET", READINESS_URL)
        assert code in (200, 503)
        assert "checks" in body
        _write_report("test_readiness", [
            f"GET {READINESS_URL} -> HTTP {code} ({ms}ms)",
            f"Body: {body}",
            "PASS",
        ])

    def test_flow_catalogue(self):
        code, body, ms = _api("GET", FLOWS_URL)
        assert code == 200
        assert body["count"] > 0
        assert len(body["valid_outputs"]) > 0
        _write_report("test_flow_catalogue", [
            f"GET {FLOWS_URL} -> HTTP {code} ({ms}ms)",
            f"Nodes: {body['count']}",
            f"Valid outputs: {body['valid_outputs']}",
            "PASS",
        ])


# ============================================================
# Text input -> all outputs
# ============================================================

class TestTextFlows:

    def test_text_to_ner(self, created_task_ids):
        task_body, durations = _create_and_poll(
            {"text": "John Smith lives in Berlin and works at Acme Corp."},
            ["ner_result"],
            "test_text_to_ner",
        )
        created_task_ids.append(task_body["id"])
        assert task_body["status"] == "COMPLETED"
        assert "ner_result" in task_body["final_output"]
        assert "entities" in task_body["final_output"]["ner_result"]

    def test_text_to_sentiment(self, created_task_ids):
        task_body, durations = _create_and_poll(
            {"text": "I absolutely love this product! It's amazing quality."},
            ["sentiment_result"],
            "test_text_to_sentiment",
        )
        created_task_ids.append(task_body["id"])
        assert task_body["status"] == "COMPLETED"
        assert "sentiment_result" in task_body["final_output"]

    def test_text_to_summary(self, created_task_ids):
        task_body, durations = _create_and_poll(
            {"text": "Technology is transforming the global economy in unprecedented ways."},
            ["summary"],
            "test_text_to_summary",
        )
        created_task_ids.append(task_body["id"])
        assert task_body["status"] == "COMPLETED"
        assert "summary" in task_body["final_output"]

    def test_text_to_iptc(self, created_task_ids):
        task_body, durations = _create_and_poll(
            {"text": "The government announced new economic policies for 2026."},
            ["iptc_tags"],
            "test_text_to_iptc",
        )
        created_task_ids.append(task_body["id"])
        assert task_body["status"] == "COMPLETED"
        assert "iptc_tags" in task_body["final_output"]

    def test_text_to_keywords(self, created_task_ids):
        task_body, durations = _create_and_poll(
            {"text": "Artificial intelligence is revolutionizing healthcare diagnostics."},
            ["keywords"],
            "test_text_to_keywords",
        )
        created_task_ids.append(task_body["id"])
        assert task_body["status"] == "COMPLETED"
        assert "keywords" in task_body["final_output"]

    def test_text_multi_output(self, created_task_ids):
        """NER + Sentiment + Summary in parallel branches."""
        task_body, durations = _create_and_poll(
            {"text": "Maria Garcia loves AI technology and works at Google."},
            ["ner_result", "sentiment_result", "summary"],
            "test_text_multi_output",
        )
        created_task_ids.append(task_body["id"])
        assert task_body["status"] == "COMPLETED"
        final = task_body["final_output"]
        assert "ner_result" in final
        assert "sentiment_result" in final
        assert "summary" in final

    def test_text_all_outputs(self, created_task_ids):
        """All 5 main outputs simultaneously."""
        task_body, durations = _create_and_poll(
            {"text": "Apple released a new product at their annual keynote event in Cupertino."},
            ["ner_result", "sentiment_result", "summary", "iptc_tags", "keywords"],
            "test_text_all_outputs",
        )
        created_task_ids.append(task_body["id"])
        assert task_body["status"] == "COMPLETED"
        assert len(task_body["final_output"]) == 5


# ============================================================
# File upload -> all outputs
# ============================================================

class TestFileFlows:

    def test_file_to_ner(self, created_task_ids):
        task_body, durations = _create_and_poll(
            {"file_path": "/tmp/test.mp4"},
            ["ner_result"],
            "test_file_to_ner",
        )
        created_task_ids.append(task_body["id"])
        assert task_body["status"] == "COMPLETED"
        assert "ner_result" in task_body["final_output"]

    def test_file_to_sentiment(self, created_task_ids):
        task_body, durations = _create_and_poll(
            {"file_path": "/tmp/test.mp4"},
            ["sentiment_result"],
            "test_file_to_sentiment",
        )
        created_task_ids.append(task_body["id"])
        assert task_body["status"] == "COMPLETED"

    def test_file_to_summary(self, created_task_ids):
        task_body, durations = _create_and_poll(
            {"file_path": "/tmp/audio.wav"},
            ["summary"],
            "test_file_to_summary",
        )
        created_task_ids.append(task_body["id"])
        assert task_body["status"] == "COMPLETED"

    def test_file_multi_output(self, created_task_ids):
        task_body, durations = _create_and_poll(
            {"file_path": "/tmp/test.mp4"},
            ["ner_result", "summary", "iptc_tags"],
            "test_file_multi_output",
        )
        created_task_ids.append(task_body["id"])
        assert task_body["status"] == "COMPLETED"
        assert len(task_body["final_output"]) == 3


# ============================================================
# YouTube -> all outputs
# ============================================================

class TestYouTubeFlows:

    def test_youtube_to_ner(self, created_task_ids):
        task_body, durations = _create_and_poll(
            {"url": "https://youtube.com/watch?v=test123"},
            ["ner_result"],
            "test_youtube_to_ner",
        )
        created_task_ids.append(task_body["id"])
        assert task_body["status"] == "COMPLETED"
        assert "ner_result" in task_body["final_output"]

    def test_youtube_to_sentiment(self, created_task_ids):
        task_body, durations = _create_and_poll(
            {"url": "https://youtu.be/abc456"},
            ["sentiment_result"],
            "test_youtube_to_sentiment",
        )
        created_task_ids.append(task_body["id"])
        assert task_body["status"] == "COMPLETED"

    def test_youtube_to_summary(self, created_task_ids):
        task_body, durations = _create_and_poll(
            {"url": "https://youtube.com/watch?v=test789"},
            ["summary"],
            "test_youtube_to_summary",
        )
        created_task_ids.append(task_body["id"])
        assert task_body["status"] == "COMPLETED"

    def test_youtube_multi_output(self, created_task_ids):
        task_body, durations = _create_and_poll(
            {"url": "https://youtube.com/watch?v=multi"},
            ["ner_result", "sentiment_result", "summary", "keywords"],
            "test_youtube_multi_output",
        )
        created_task_ids.append(task_body["id"])
        assert task_body["status"] == "COMPLETED"
        assert len(task_body["final_output"]) == 4


# ============================================================
# API with input_type hint (optional field)
# ============================================================

class TestInputTypeHint:
    """Verify input_type hint is accepted and correctly routes the request."""

    def test_text_with_type_hint(self, created_task_ids):
        code, body, ms = _api("POST", TASKS_URL, json={
            "input_type": "text",
            "input_data": "Hello world, this is a test.",
            "outputs": ["ner_result"],
        })
        assert code == 201
        created_task_ids.append(body["id"])
        assert body["input_type"] == "text"
        _write_report("test_text_with_type_hint", [
            f"POST with input_type=text, input_data as string",
            f"HTTP {code}, task_id={body['id']}",
            "PASS",
        ])

    def test_youtube_with_type_hint(self, created_task_ids):
        code, body, ms = _api("POST", TASKS_URL, json={
            "input_type": "youtube_link",
            "input_data": "https://youtube.com/watch?v=test",
            "outputs": ["summary"],
        })
        assert code == 201
        created_task_ids.append(body["id"])
        assert body["input_type"] == "youtube_url"
        _write_report("test_youtube_with_type_hint", [
            f"POST with input_type=youtube_link (hint), input_data as string URL",
            f"HTTP {code}, detected input_type={body['input_type']}",
            "PASS",
        ])


# ============================================================
# Task management
# ============================================================

class TestTaskManagement:

    def test_list_all(self):
        code, body, ms = _api("GET", TASKS_URL)
        assert code == 200
        assert "tasks" in body
        assert isinstance(body["tasks"], list)
        _write_report("test_list_all", [
            f"GET {TASKS_URL} -> HTTP {code} ({ms}ms)",
            f"Tasks returned: {len(body['tasks'])}",
            f"has_more: {body.get('has_more')}",
            "PASS",
        ])

    def test_list_with_filters(self):
        code, body, ms = _api("GET", f"{TASKS_URL}?status=COMPLETED&limit=5")
        assert code == 200
        for t in body["tasks"]:
            assert t["status"] == "COMPLETED"
        _write_report("test_list_with_filters", [
            f"GET {TASKS_URL}?status=COMPLETED&limit=5 -> HTTP {code} ({ms}ms)",
            f"Tasks: {len(body['tasks'])}",
            "PASS",
        ])

    def test_create_and_delete(self):
        code, body, ms = _api("POST", TASKS_URL, json={
            "input_data": {"text": "delete me"},
            "outputs": ["ner_result"],
        })
        assert code == 201
        task_id = body["id"]

        del_code, del_body, del_ms = _api("DELETE", f"{TASKS_URL}/{task_id}")
        assert del_code == 200

        get_code, get_body, get_ms = _api("GET", f"{TASKS_URL}/{task_id}")
        assert get_code == 404

        _write_report("test_create_and_delete", [
            f"Created task {task_id}",
            f"DELETE -> HTTP {del_code} ({del_ms}ms)",
            f"GET after delete -> HTTP {get_code} (404 expected)",
            "PASS",
        ])


# ============================================================
# Invalid requests / error handling
# ============================================================

class TestInvalidRequests:

    def test_empty_body(self):
        code, body, ms = _api("POST", TASKS_URL, json={})
        assert code == 400
        _write_report("test_empty_body", [
            f"POST empty body -> HTTP {code} ({ms}ms)",
            f"Response: {body}",
            "PASS",
        ])

    def test_invalid_output_type(self):
        code, body, ms = _api("POST", TASKS_URL, json={
            "input_data": {"text": "hello"},
            "outputs": ["nonexistent_output"],
        })
        assert code == 400
        _write_report("test_invalid_output_type", [
            f"POST invalid output -> HTTP {code} ({ms}ms)",
            f"Response: {body}",
            "PASS",
        ])

    def test_empty_outputs_list(self):
        code, body, ms = _api("POST", TASKS_URL, json={
            "input_data": {"text": "hello"},
            "outputs": [],
        })
        assert code == 400
        _write_report("test_empty_outputs_list", [
            f"POST empty outputs -> HTTP {code} ({ms}ms)",
            "PASS",
        ])

    def test_unclassifiable_input(self):
        """input_data with no recognizable fields."""
        code, body, ms = _api("POST", TASKS_URL, json={
            "input_data": {"unknown_field": "value"},
            "outputs": ["ner_result"],
        })
        assert code == 400
        _write_report("test_unclassifiable_input", [
            f"POST unknown input_data fields -> HTTP {code} ({ms}ms)",
            "PASS",
        ])

    def test_nonexistent_task(self):
        fake_id = str(uuid.uuid4())
        code, body, ms = _api("GET", f"{TASKS_URL}/{fake_id}")
        assert code == 404
        _write_report("test_nonexistent_task", [
            f"GET nonexistent task -> HTTP {code} ({ms}ms)",
            "PASS",
        ])

    def test_delete_nonexistent_task(self):
        fake_id = str(uuid.uuid4())
        code, body, ms = _api("DELETE", f"{TASKS_URL}/{fake_id}")
        assert code == 404
        _write_report("test_delete_nonexistent", [
            f"DELETE nonexistent task -> HTTP {code} ({ms}ms)",
            "PASS",
        ])

    def test_malformed_json(self):
        resp = requests.post(
            f"{API_URL}{TASKS_URL}",
            data="this is not json",
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        assert resp.status_code in (400, 500)
        _write_report("test_malformed_json", [
            f"POST malformed JSON -> HTTP {resp.status_code}",
            "PASS",
        ])

    def test_template_injection(self):
        code, body, ms = _api("POST", TASKS_URL, json={
            "input_data": {"text": "{{config.items()}}"},
            "outputs": ["ner_result"],
        })
        assert code == 400
        _write_report("test_template_injection", [
            f"POST template injection -> HTTP {code} ({ms}ms)",
            "PASS",
        ])


# ============================================================
# Observability
# ============================================================

class TestObservability:

    def test_jaeger_has_services(self):
        try:
            resp = requests.get("http://localhost:16686/api/services", timeout=5)
            assert resp.status_code == 200
            data = resp.json().get("data", [])
            _write_report("test_jaeger_has_services", [
                f"Services: {data}",
                "PASS" if data else "SKIP (no services yet)",
            ])
            if not data:
                pytest.skip("No services in Jaeger yet")
        except Exception as e:
            pytest.skip(f"Jaeger not reachable: {e}")
