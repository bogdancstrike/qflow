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

## 7. Performance Optimization
- Watch htop and see cpu usage. If 100% CPU, then find and solve the usage of it.