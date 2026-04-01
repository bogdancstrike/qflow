# Production Readiness — Task List

Make the AI Flow Orchestrator production-ready. The app is currently in POC/MVP state — core orchestration logic works, but infrastructure, security, observability, and operational concerns need hardening.

---

## 1. Security


### 1.1 Input Sanitization & Hardening
- Validate file upload content-type (reject non-audio/video MIME types)
- Sanitize original filenames to prevent path traversal (strip `..`, `/`, null bytes)
- Add max request body size limit on Flask (e.g. 100MB for file uploads, 1MB for JSON, configurable in .env)
- Sanitize user-provided text before interpolation — prevent template injection via `{{...}}` patterns in input_data
- Strip or redact sensitive headers (Authorization, tokens) from task_step_logs before persisting to DB

---

## 2. Database

### 2.1 Query Performance
- Add database indexes on frequently filtered columns:
  - `tasks.status` (filtered in list_tasks)
  - `tasks.desired_output` (filtered in list_tasks)
  - `tasks.input_type` (filtered in list_tasks)
  - `tasks.created_at` (ordered by in list_tasks)
  - Composite index: `(status, created_at DESC)` for the most common query pattern
- Add `EXPLAIN ANALYZE` logging for slow queries (>200ms)

### 2.2 Connection Management
- Configure idle connection timeout (`pool_recycle=3600`)
- Add `pool_pre_ping=True` (already exists, verify it's working)
- Add connection pool monitoring (log pool size, overflow, checkouts)
- Set `pool_timeout=30` to fail fast when pool is exhausted

### 2.3 Data Lifecycle
- Add task retention policy: auto-delete COMPLETED tasks older than N days (configurable in .env, default 30)
- Add a periodic cleanup job (cron or Kafka-based) that purges old tasks and step logs
- Clean up uploaded files when task is deleted or expired

---

## 3. Observability

### 3.1 Prometheus Metrics
- Add `prometheus_flask_instrumentator` or `prometheus_client` for HTTP metrics:
  - `http_request_duration_seconds` (histogram by endpoint, method, status)
  - `http_requests_total` (counter by endpoint, method, status)
- Add custom business metrics:
  - `flow_execution_duration_seconds` (histogram by flow_id)
  - `flow_steps_total` (counter by step_type, status)
  - `tasks_created_total` (counter by input_type, desired_output)
  - `tasks_completed_total` / `tasks_failed_total`
  - `kafka_consumer_lag` (gauge)
  - `dlq_messages_total` (counter)
  - `circuit_breaker_state` (gauge: 0=closed, 1=open, 2=half-open)
- Expose `/metrics` endpoint for Prometheus scraping

### 3.2 Health Check Depth
- Enhance `GET /api/health` to check all dependencies:
  - PostgreSQL: execute `SELECT 1`
  - Redis: execute `PING`
  - Kafka: verify broker connectivity
  - Return `degraded` if any dependency is slow, `unhealthy` if any is down
- Add separate `/api/readiness` endpoint (readiness probe — is the app ready to accept traffic?)
- Add `/api/liveness` endpoint (liveness probe — is the process alive?)

### 3.3 Dashboards & Alerting

- Deploy Prometheus and Grafana (or use existing)
- Configure Grafana to scrape Prometheus metrics
- Create Grafana dashboard templates for:
  - Task throughput and latency (p50, p95, p99)
  - Flow execution breakdown by step
  - Error rates by flow_id and step_type
  - Kafka consumer lag
  - PostgreSQL connection pool utilization
- Define alert rules:
  - Error rate > 5% over 5 minutes
  - Task processing latency p95 > 30s
  - DLQ message count > 0
  - Circuit breaker open for > 5 minutes
  - Kafka consumer lag > 1000 messages

---

## 4. Resilience & Reliability

### 4.1 Graceful Shutdown
- Add SIGTERM/SIGINT signal handlers in `main.py`:
  - Stop accepting new Kafka messages
  - Wait for in-flight tasks to complete (with timeout)
  - Close DB connections cleanly

### 4.2 Task Timeout & Heartbeat
- Add configurable per-flow timeout (e.g. `"timeout_seconds": 300` in flow definition)
- Implement a task heartbeat: flow_executor periodically updates `updated_at` while running
- Add a watchdog job that marks RUNNING tasks as FAILED if `updated_at` is older than timeout
- Prevent duplicate execution: check task status is still PENDING before starting

### 4.3 Backpressure & Rate Limiting
- Add API rate limiting on `POST /api/tasks` (e.g. 100 req/min using Redis)

### 4.4 Retry & Circuit Breaker Improvements
- Replace fixed 1s retry wait with exponential backoff (1s, 2s, 4s) in `http_client.py`
- Add per-service circuit breakers (not one global breaker)
- Log circuit breaker state changes as WARNING
- Add circuit breaker metrics (open/closed/half-open state, trip count)

---

## 5. API Hardening

### 5.1 Rate Limiting & Throttling
- Add Redis-based rate limiting on `POST /api/tasks` (100 req/min configurable in .env)
- Return `429 Too Many Requests` with `Retry-After` header

### 5.2 API Versioning
- Prefix all routes with `/api/v1/`
- Plan for `/api/v2/` with breaking changes
- Document versioning strategy in README

### 5.3 OpenAPI Documentation
- Enable Flask-RESTX Swagger UI at `/api/docs`
- Document all endpoints with request/response schemas
- Add example requests and responses

### 5.4 Pagination & Filtering
- Add cursor-based pagination on `GET /api/tasks` (replace offset-based for large datasets)
- Add date range filtering (`created_after`, `created_before`)
- Add sorting parameter (`sort=created_at:desc`)
- Limit `step_logs` in task detail response (paginate separately)

---

## 7. Testing

### 7.1 Quality
- Add missing test scenarios:
  - Concurrent task execution (multiple tasks in parallel)
  - Large file uploads (>100MB)
  - Malformed JSON payloads
  - Database connection failures
  - Kafka broker unavailability
  - Circuit breaker state transitions

### 7.2 Load & Performance Testing
- Add k6 or locust load test scripts:
  - Baseline: 10 concurrent users, 100 tasks
  - Stress: 100 concurrent users, 1000 tasks
  - Spike: burst of 500 tasks in 10 seconds
- Establish performance baselines (p50, p95, p99 latency per flow)
- Add performance regression tests in CI

### 7.3 Chaos Testing
- Add tests for:
  - Kill PostgreSQL mid-flow (verify task status recovery)
  - Kill Kafka mid-flow (verify message replay)
  - Simulate slow AI service (verify timeout handling)
  - Simulate circuit breaker trip (verify fallback behavior)

### 7.4 Full Environment Testing
- Start full environment using docker-compose:
  - docker compose down
  - docker compose up -d
- Verify all services are healthy (app, Kafka, DB, etc.)
- Test all endpoints using curl:
  - Send valid requests → verify expected responses
  - Send invalid requests → verify proper error handling
- Validate full flow
- Validate observability:
  - Traces (Jaeger)
  - Logs (no silent failures)
- If any bug is found:
  - Identify root cause
  - Fix immediately
  - Re-run full test suite
  - Add regression test for the issue
- Automate:
  - Create E2E test script

---

## 8. Configuration & Operations

### 8.1 Startup Validation
- Validate all required environment variables at startup (fail fast with clear error messages)
- Check database connectivity before starting Kafka consumers
- Check Kafka broker connectivity before accepting API requests
- Log full configuration (redacted secrets) on startup for debugging

### 8.3 Operational Runbooks
- Document common operations:
  - How to add a new flow to production
  - How to retry failed tasks
  - How to drain and restart workers
  - How to investigate DLQ messages
  - How to roll back a bad deployment
  - How to scale workers horizontally

## 9. Known Bugs

### 9.1 POST /api/tasks

```code
curl -X POST http://localhost:5000/api/tasks   -H "Content-Type: application/json"   -d '{
    "input_type": "text",
    "input_data": "This is a sample input",
    "desired_output": "ner"
  }'
{"message": "Internal Server Error"}
```

```code
2026-04-01 21:59:19,353 - DEBUG - 🔵 Kafka consumer connected | topics=['flow.step.execute.in', 'flow.step.request.in', 'flow.tasks.in'] auto_commit=False - [no-traceparent]
2026-04-01 21:59:19,354 - DEBUG - 🔵 Kafka producer connected | acks=1 linger_ms=5 batch_size=65536 - [no-traceparent]
2026-04-01 21:59:19,355 - DEBUG - 🔵 [ai-flow-orchestrator] ETL start | topics=['flow.step.execute.in', 'flow.step.request.in', 'flow.tasks.in'] - [no-traceparent]
2026-04-01 21:59:33,230 - INFO - [RESOLVER] (text, ner) -> flow_text_to_ner - [traceparent=00-ce2d96a2689e6d1ab2fed88a8251be3e-9fe409342e64c3e2-01]
2026-04-01 21:59:52,840 - DEBUG - 🔵 [IN] tp=flow.tasks.in[0] off=0 id=de268633-871a-4289-b14d-65e6d6711c98 - [no-traceparent]
2026-04-01 21:59:52,840 - DEBUG - 🔵 [IN] tp=flow.tasks.in[0] off=1 id=098c94dd-ba14-4b81-a1d2-5848fdf38b27 - [no-traceparent]
2026-04-01 21:59:52,840 - DEBUG - 🔵 [IN] tp=flow.tasks.in[0] off=0 id=de268633-871a-4289-b14d-65e6d6711c98 (pending) - [no-traceparent]
2026-04-01 21:59:52,840 - DEBUG - 🟣 [DISPATCH] worker=flow_executor kind=single tp=flow.tasks.in[0] off=0 id=de268633-871a-4289-b14d-65e6d6711c98 - [no-traceparent]
2026-04-01 21:59:52,840 - DEBUG - Message sent to flow.tasks.in: {"task_id": "ca1d477f-b53d-42b4-92ef-5c4a5fc79f40", "text": "This is a sample input", "desired_output": "ner"} with key ca1d477f-b53d-42b4-92ef-5c4a5fc79f40. Duration time: 7.953882217407227 ms - [traceparent=00-ce2d96a2689e6d1ab2fed88a8251be3e-9fe409342e64c3e2-01]
2026-04-01 21:59:52,840 - INFO - [API] Published task ca1d477f-b53d-42b4-92ef-5c4a5fc79f40 to flow.tasks.in - [traceparent=00-ce2d96a2689e6d1ab2fed88a8251be3e-9fe409342e64c3e2-01]
2026-04-01 21:59:52,841 - INFO - [FLOW_EXECUTOR] Processing task 9ac4d897-4791-48b2-a88d-a5b7763cc46d - [traceparent=00-95cce312c7e19ef672fb9bd7959be5f8-a0e6790aa8286b58-01]
2026-04-01 21:59:52,841 - DEBUG - 🔵 [IN] tp=flow.tasks.in[0] off=1 id=098c94dd-ba14-4b81-a1d2-5848fdf38b27 (pending) - [no-traceparent]
2026-04-01 21:59:52,841 - DEBUG - 🟣 [DISPATCH] worker=flow_executor kind=single tp=flow.tasks.in[0] off=1 id=098c94dd-ba14-4b81-a1d2-5848fdf38b27 - [no-traceparent]
2026-04-01 21:59:52,841 - INFO - [FLOW_EXECUTOR] Processing task 9ac4d897-4791-48b2-a88d-a5b7763cc46d - [traceparent=00-9cab0d03136c10631c58ff2293fc50b9-cd491a6b3900d169-01]
2026-04-01 21:59:52,843 - DEBUG - 🔵 [IN] tp=flow.tasks.in[0] off=2 id=b4299f9b-70b7-4252-ac1f-2bc8ca084e0f - [no-traceparent]
2026-04-01 21:59:52,843 - DEBUG - 🔵 [IN] tp=flow.tasks.in[0] off=2 id=b4299f9b-70b7-4252-ac1f-2bc8ca084e0f (pending) - [no-traceparent]
2026-04-01 21:59:52,843 - DEBUG - 🟣 [DISPATCH] worker=flow_executor kind=single tp=flow.tasks.in[0] off=2 id=b4299f9b-70b7-4252-ac1f-2bc8ca084e0f - [no-traceparent]
2026-04-01 21:59:52,843 - ERROR - [FLOW_EXECUTOR] Task 9ac4d897-4791-48b2-a88d-a5b7763cc46d has no resolved flow definition - [traceparent=00-95cce312c7e19ef672fb9bd7959be5f8-a0e6790aa8286b58-01]
2026-04-01 21:59:52,843 - INFO - [FLOW_EXECUTOR] Processing task ca1d477f-b53d-42b4-92ef-5c4a5fc79f40 - [traceparent=00-b92c837c33386013047174f6649369cb-781a689801453fdf-01]
2026-04-01 21:59:53,346 - ERROR - [FLOW_EXECUTOR] Task 9ac4d897-4791-48b2-a88d-a5b7763cc46d has no resolved flow definition - [traceparent=00-9cab0d03136c10631c58ff2293fc50b9-cd491a6b3900d169-01]
2026-04-01 21:59:53,346 - ERROR - [FLOW_EXECUTOR] Task ca1d477f-b53d-42b4-92ef-5c4a5fc79f40 has no resolved flow definition - [traceparent=00-b92c837c33386013047174f6649369cb-781a689801453fdf-01]
[2026-04-01 21:59:52,840] ERROR in logger: Exception on /api/tasks [POST]
Traceback (most recent call last):
  File "/home/bogdan/workspace/dev/qflow/ai-flow-orchestrator/venv/lib/python3.12/site-packages/flask/app.py", line 917, in full_dispatch_request
    rv = self.dispatch_request()
         ^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/bogdan/workspace/dev/qflow/ai-flow-orchestrator/venv/lib/python3.12/site-packages/flask/app.py", line 902, in dispatch_request
    return self.ensure_sync(self.view_functions[rule.endpoint])(**view_args)  # type: ignore[no-any-return]
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/bogdan/workspace/dev/qflow/ai-flow-orchestrator/venv/lib/python3.12/site-packages/flask_restx/api.py", line 408, in wrapper
    return self.make_response(data, code, headers=headers)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/bogdan/workspace/dev/qflow/ai-flow-orchestrator/venv/lib/python3.12/site-packages/flask_restx/api.py", line 432, in make_response
    resp = self.representations[mediatype](data, *args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/bogdan/workspace/dev/qflow/ai-flow-orchestrator/venv/lib/python3.12/site-packages/flask_restx/representations.py", line 22, in output_json
    dumped = dumps(data, **settings) + "\n"
             ^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/json/__init__.py", line 231, in dumps
    return _default_encoder.encode(obj)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/json/encoder.py", line 200, in encode
    chunks = self.iterencode(o, _one_shot=True)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/json/encoder.py", line 258, in iterencode
    return _iterencode(o, 0)
           ^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/json/encoder.py", line 180, in default
    raise TypeError(f'Object of type {o.__class__.__name__} '
TypeError: Object of type Response is not JSON serializable
127.0.0.1 - - [01/Apr/2026 21:59:54] "POST /api/tasks HTTP/1.1" 500 -
2026-04-01 21:59:54,919 - DEBUG - 🟢 [OUT] worker=flow_executor topic=flow.tasks.out id=None - [no-traceparent]
2026-04-01 21:59:54,919 - DEBUG - 🟡 [COMMIT FAIL] err=OffsetAndMetadata.__new__() missing 1 required positional argument: 'leader_epoch' - [no-traceparent]
2026-04-01 21:59:54,919 - DEBUG - 🟢 [OUT] worker=flow_executor topic=flow.tasks.out id=None - [no-traceparent]
2026-04-01 21:59:54,919 - DEBUG - 🟡 [COMMIT FAIL] err=OffsetAndMetadata.__new__() missing 1 required positional argument: 'leader_epoch' - [no-traceparent]
2026-04-01 21:59:54,919 - DEBUG - 🟢 [OUT] worker=flow_executor topic=flow.tasks.out id=None - [no-traceparent]
2026-04-01 21:59:54,919 - DEBUG - 🟡 [COMMIT FAIL] err=OffsetAndMetadata.__new__() missing 1 required positional argument: 'leader_epoch' - [no-traceparent]
2026-04-01 21:59:54,920 - DEBUG - 🟡 [COMMIT FAIL] err=OffsetAndMetadata.__new__() missing 1 required positional argument: 'leader_epoch' - [no-traceparent]
2026-04-01 21:59:54,921 - DEBUG - 🟡 [COMMIT FAIL] err=OffsetAndMetadata.__new__() missing 1 required positional argument: 'leader_epoch' - [no-traceparent]
2026-04-01 21:59:54,922 - DEBUG - 🟡 [COMMIT FAIL] err=OffsetAndMetadata.__new__() missing 1 required positional argument: 'leader_epoch' - [no-traceparent]
```