"""Locust load test for AI Flow Orchestrator.

Usage:
    # Baseline: 10 concurrent users, 100 tasks
    locust -f tests/load/locustfile.py --headless -u 10 -r 2 -t 60s \
        --csv=reports/load_baseline --html=reports/load_baseline.html

    # Stress: 100 concurrent users, 1000 tasks
    locust -f tests/load/locustfile.py --headless -u 100 -r 10 -t 120s \
        --csv=reports/load_stress --html=reports/load_stress.html

    # Spike: burst 500 tasks in 10 seconds
    locust -f tests/load/locustfile.py --headless -u 500 -r 50 -t 30s \
        --csv=reports/load_spike --html=reports/load_spike.html

Reports are written to reports/ directory.
"""

import os
import json
import time
import random
import resource

from locust import HttpUser, task, between, events, tag


# Write summary report on test stop
@events.quitting.add_listener
def on_quitting(environment, **kwargs):
    stats = environment.runner.stats
    report_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "reports",
        f"load_summary_{int(time.time())}.txt",
    )
    os.makedirs(os.path.dirname(report_path), exist_ok=True)

    with open(report_path, "w") as f:
        f.write("=" * 70 + "\n")
        f.write("  LOAD TEST SUMMARY\n")
        f.write(f"  Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"  Users: {environment.runner.user_count}\n")
        f.write("=" * 70 + "\n\n")

        for entry in stats.entries.values():
            f.write(f"  {entry.method} {entry.name}\n")
            f.write(f"    Requests:   {entry.num_requests}\n")
            f.write(f"    Failures:   {entry.num_failures}\n")
            f.write(f"    Avg (ms):   {entry.avg_response_time:.0f}\n")
            f.write(f"    p50 (ms):   {entry.get_response_time_percentile(0.50) or 0:.0f}\n")
            f.write(f"    p95 (ms):   {entry.get_response_time_percentile(0.95) or 0:.0f}\n")
            f.write(f"    p99 (ms):   {entry.get_response_time_percentile(0.99) or 0:.0f}\n")
            f.write(f"    RPS:        {entry.current_rps:.1f}\n")
            f.write("\n")

        total = stats.total
        f.write("  TOTAL\n")
        f.write(f"    Requests:   {total.num_requests}\n")
        f.write(f"    Failures:   {total.num_failures}\n")
        f.write(f"    Avg (ms):   {total.avg_response_time:.0f}\n")
        f.write(f"    p50 (ms):   {total.get_response_time_percentile(0.50) or 0:.0f}\n")
        f.write(f"    p95 (ms):   {total.get_response_time_percentile(0.95) or 0:.0f}\n")
        f.write(f"    p99 (ms):   {total.get_response_time_percentile(0.99) or 0:.0f}\n")
        f.write(f"    RPS:        {total.current_rps:.1f}\n")
        f.write(f"    Fail ratio: {total.fail_ratio:.2%}\n")

        # Resource usage
        ru = resource.getrusage(resource.RUSAGE_SELF)
        f.write(f"\n  Resource Usage:\n")
        f.write(f"    Max RSS: {ru.ru_maxrss / 1024:.1f} MB\n")
        f.write(f"    User CPU: {ru.ru_utime:.2f}s\n")
        f.write(f"    Sys CPU: {ru.ru_stime:.2f}s\n")

    print(f"\n[LOAD TEST] Summary written to {report_path}")


SAMPLE_TEXTS = [
    "John Smith lives in Berlin and works at Google Inc.",
    "Maria Garcia travelled to Tokyo for the AI conference.",
    "The weather in London is rainy but temperatures are mild.",
    "Apple released a new product at their annual keynote event.",
    "I love this service! The quality is excellent and support is great.",
    "This is terrible. The product broke after two days of use.",
    "Technology is transforming healthcare through AI diagnostics.",
    "The government announced new economic policies for 2026.",
]


class AIFlowUser(HttpUser):
    """Simulates a user creating tasks and polling for results."""

    host = os.getenv("API_URL", "http://localhost:5000")
    wait_time = between(0.5, 2.0)

    @tag("health")
    @task(1)
    def health_check(self):
        self.client.get("/api/health")

    @tag("list")
    @task(2)
    def list_tasks(self):
        self.client.get("/api/tasks?limit=10")

    @tag("flows")
    @task(1)
    def list_flows(self):
        self.client.get("/api/flows")

    @tag("create", "text_ner")
    @task(5)
    def create_text_ner(self):
        text = random.choice(SAMPLE_TEXTS)
        with self.client.post("/api/tasks",
                              json={
                                  "input_type": "text",
                                  "input_data": text,
                                  "desired_output": "sentiment",
                              },
                              catch_response=True) as resp:
            if resp.status_code == 201:
                resp.success()
                task_id = resp.json().get("id")
                if task_id:
                    self._poll_task(task_id)
            else:
                resp.failure(f"Expected 201, got {resp.status_code}")

    @tag("create", "text_sentiment")
    @task(3)
    def create_text_sentiment(self):
        text = random.choice(SAMPLE_TEXTS)
        with self.client.post("/api/tasks",
                              json={
                                  "input_type": "text",
                                  "input_data": text,
                                  "desired_output": "sentiment",
                              },
                              catch_response=True) as resp:
            if resp.status_code == 201:
                resp.success()
                task_id = resp.json().get("id")
                if task_id:
                    self._poll_task(task_id)
            else:
                resp.failure(f"Expected 201, got {resp.status_code}")

    @tag("create", "text_summary")
    @task(2)
    def create_text_summary(self):
        text = random.choice(SAMPLE_TEXTS) * 5
        with self.client.post("/api/tasks",
                              json={
                                  "input_type": "text",
                                  "input_data": text,
                                  "desired_output": "summary",
                              },
                              catch_response=True) as resp:
            if resp.status_code == 201:
                resp.success()
            else:
                resp.failure(f"Expected 201, got {resp.status_code}")

    @tag("create", "file_stt")
    @task(2)
    def create_file_stt(self):
        with self.client.post("/api/tasks",
                              json={
                                  "input_type": "file_upload",
                                  "input_data": {"file_path": "/tmp/test.mp4"},
                                  "desired_output": "stt",
                              },
                              catch_response=True) as resp:
            if resp.status_code == 201:
                resp.success()
            else:
                resp.failure(f"Expected 201, got {resp.status_code}")

    @tag("invalid")
    @task(1)
    def create_invalid_task(self):
        """Verify error handling under load."""
        with self.client.post("/api/tasks",
                              json={
                                  "input_type": "invalid",
                                  "desired_output": "ner",
                                  "input_data": "hello",
                              },
                              catch_response=True) as resp:
            if resp.status_code == 400:
                resp.success()
            else:
                resp.failure(f"Expected 400, got {resp.status_code}")

    def _poll_task(self, task_id, max_polls=10):
        """Poll a task until completion."""
        for _ in range(max_polls):
            time.sleep(1)
            with self.client.get(f"/api/tasks/{task_id}",
                                 name="/api/tasks/[id] (poll)",
                                 catch_response=True) as resp:
                if resp.status_code == 200:
                    status = resp.json().get("status", "")
                    if status in ("COMPLETED", "FAILED", "TERMINATED"):
                        resp.success()
                        return
                    resp.success()
                else:
                    resp.failure(f"Poll got {resp.status_code}")
                    return
