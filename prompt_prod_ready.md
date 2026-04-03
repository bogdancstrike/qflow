# AI Flow Orchestrator — Production Readiness & Dynamic DAG Engine

## Project Context


It currently uses static JSON flow definition files (e.g. `flow_text_to_ner.json`) to describe
which steps to run for a given task. The core execution engine (StepRunner, executors, Kafka
consumer loop) works and should not be restructured — changes are additive.

The stack: Python, Flask, gevent, Kafka (confluent-kafka), PostgreSQL, Redis. The codebase
uses the internal `qf` library (`qf_framework_with_poc_v6` found at `/home/bogdan/workspace/templates/framework_qf/qf/qf_framework_with_poc_v6`) which wraps the Kafka consumer loop,
dispatch, commit logic, tracing, logging and more.

---

## Part 1 — Dynamic DAG Engine (Core Feature)

### 1.1 Problem with Static Flows

Static JSON flow files hardcode the sequence of steps for every input/output combination.
Adding a new AI capability (e.g. emotion detection) requires creating new flow files for every
input type that should support it. This does not scale. Flow files also cannot express
conditional logic (e.g. skip translation if already English) without custom branching steps.

### 1.2 Mental Model

The code is ALWAYS written with extensibility in mind and respecting design principles.
Use qf library whenever possible for every functionalities it supports.

The processing pipeline has two clearly separated phases:

**Phase 1 — Ingest.** Every input type is normalised into `text` before any analysis happens.
This is the only goal of Phase 1. All paths lead to `text`:

- A raw text input is already `text` — Phase 1 is a no-op.
- An audio or video file goes through speech-to-text (STT) to produce `text`.
- A YouTube URL is first downloaded with yt-dlp to produce an audio file, then goes through STT.

**Phase 2 — Analysis.** Once `text` exists, any number of AI analysis nodes can be applied to
it. These nodes are independent of each other and can run in parallel. The full set of
Phase 2 nodes includes: `summarize`, `iptc`, `translate`, `lang_detect`, `ner`, `sentiment`,
`keyword_extract`, and any future additions. New nodes are addable without touching any
existing logic — just register the node in the graph.

The graph looks like this:

```
audio/video file ──▶ stt ──────────────────┐
youtube url ─────▶ ytdlp ──▶ stt ──────────┤
raw text ──────────────────────────────────┴──▶ TEXT ──┬──▶ summarize
                                                        ├──▶ iptc
                                                        ├──▶ lang_detect
                                                        ├──▶ translate
                                                        ├──▶ keyword_extract
                                                        ├──▶ ner          (requires EN)
                                                        └──▶ sentiment    (requires EN)
```

### 1.3 Node Catalogue

Every processing capability is a node. Each node declares:
- what data type it consumes (`input_type`)
- what data type it produces (`output_type`)
- whether it requires the input text to be in English (`requires_en`)

The full catalogue:

| Node ID           | Phase | Consumes        | Produces          | Requires EN |
|-------------------|-------|-----------------|-------------------|-------------|
| `ytdlp_download`  | 1     | `youtube_url`   | `audio_path`      | no          |
| `stt`             | 1     | `audio_path`    | `text`            | no          |
| `lang_detect`     | 2     | `text`          | `lang_meta`       | no          |
| `translate`       | 2     | `text`          | `text_en`         | no          |
| `summarize`       | 2     | `text`          | `summary`         | no          |
| `iptc`            | 2     | `text`          | `iptc_tags`       | no          |
| `keyword_extract` | 2     | `text`          | `keywords`        | no          |
| `ner`             | 2     | `text_en`       | `ner_result`      | **yes**     |
| `sentiment`       | 2     | `text_en`       | `sentiment_result`| **yes**     |

`text_en` is the same payload as `text` but carries the guarantee that its content is English.
It is produced by the `translate` node. Nodes that declare `requires_en = true` consume
`text_en`, not `text` — this distinction is what drives automatic EN preparation injection
at plan time (see 1.5).

### 1.4 Input Type Detection

The planner must detect the input type from the task payload before it can determine the
Phase 1 path. Detection rules:

- If the payload contains a `url` field that matches a YouTube URL pattern
  (`youtube.com/watch?v=` or `youtu.be/`) → `youtube_url`
- If the payload contains a `file_path` field with an audio extension
  (`.mp3`, `.wav`, `.ogg`, `.flac`, `.aac`, `.m4a`) or video extension
  (`.mp4`, `.mkv`, `.avi`, `.webm`, `.mov`, `.ts`) → `audio_path`
- If the payload contains a `text` field → `text`
- Any other combination is an error and must be rejected with a clear message before
  the task enters the execution engine.

### 1.5 Plan Building (Execution Plan)

When a task arrives, the planner computes an `ExecutionPlan` composed of:

1. **Ingest steps** — the ordered Phase 1 nodes needed to get from the detected input type
   to `text`. This list is shared by all output branches (executed once, sequentially).
   If the input is already `text`, this list is empty.

2. **Output branches** — one branch per requested output. Each branch is an ordered list of
   Phase 2 nodes. Branches are independent and must run in parallel (gevent greenlets).

Branch construction rules:

- For each requested output, find the single node that produces that `output_type`.
- If that node has `requires_en = false`: the branch contains only that node.
- If that node has `requires_en = true`: the branch must be prepended with
  `lang_detect → translate`. The `translate` node is marked as **conditional** — at
  runtime it must check the `lang` field in the execution context and skip the service
  call (promoting `text` directly to `text_en`) if the detected language is already `en`.
  This skip must not be hardcoded into the planner — the planner always injects these
  two nodes; the executor of `translate` is responsible for the conditional skip.

### 1.6 Fan-out Parallelism

All output branches in Phase 2 run in parallel as gevent greenlets. The shared execution
context (produced by Phase 1) must be shallow-copied per branch before the branch starts,
so that branches cannot mutate each other's state. The final task result is the merge of
all branch outputs into a single result dict, keyed by `output_type`.

### 1.7 yt-dlp Integration

The `ytdlp_download` node is a `TRANSFORM`-type executor (not HTTP). It shells out to
`yt-dlp` as a subprocess, downloading and extracting audio from the YouTube URL, and writes
the output path into the execution context. It must:
- Use `--extract-audio --audio-format mp3` to produce a consistent audio format for STT
- Capture stderr for error reporting
- Write the output file path into `context["audio_path"]` before returning
- Enforce a subprocess timeout (configurable, default 300s)
- Clean up temp files if the overall task fails

### 1.8 Task Request Shape

The task payload sent to Kafka (or via the REST API) must support:

- `input_data` — an object containing exactly one of: `text`, `file_path`, or `url`
- `outputs` — a list of one or more output type strings (e.g. `["ner_result", "summary"]`)

Single-output requests may also use the legacy `output_type` string field for backwards
compatibility, but internally it must be normalised to a single-element `outputs` list.

### 1.9 Extensibility Contract

Adding a new AI node in the future must require only:
1. Adding one entry to the node catalogue (id, input_type, output_type, executor config,
   requires_en flag)
2. No changes to the planner, runner, or any existing node

This is a hard design constraint — the planner must not contain any node-specific logic.

---

## Part 2 — Known Bug: COMMIT FAIL in qf Library

After every successfully processed task the logs show:

```
🟡 [COMMIT FAIL] err=
```

The error string is empty. This is not a real failure — it is a silent false-positive caused
by the commit being called in a state where there is nothing to commit or a rebalance is in
progress. The bug is in `qf_framework_with_poc_v6`.

Root cause: `commit()` is called unconditionally after task processing, without checking
whether there are assigned partitions or whether a rebalance is in progress. When the
consumer has no assignments (e.g. briefly after a rebalance), the commit either silently
no-ops or raises a Kafka error with code `UNKNOWN_MEMBER_ID`, `REBALANCE_IN_PROGRESS`,
or `_NO_OFFSET` — all of which are expected and should not be logged as failures.

The fix must:
- Check `consumer.assignment()` before attempting commit; skip if empty
- Catch `KafkaException` and inspect the error code; treat rebalance-related codes as
  expected and log them at DEBUG level, not WARNING
- Catch unexpected exceptions separately and log at WARNING
- After fixing, rebuild the wheel and reinstall it into the qflow virtualenv

---

## Part 3 — Security

### 3.1 Input Sanitization

The following must be validated/sanitized at the API boundary before a task is enqueued:

- **File path sanitization** — strip path traversal sequences (`..`, null bytes) from any
  `file_path` value. Use `os.path.basename` as a first pass, then reject any remaining
  suspicious characters.
- **Template injection guard** — reject any `text` input containing `{{...}}` or `{%...%}`
  patterns. These could be interpolated by Jinja2-based components downstream.
- **Output type allowlist** — the `outputs` list must be validated against the known set of
  valid output types before the task reaches the planner. Unknown output types must return
  HTTP 400 with a clear error listing valid options.
- **MIME type validation** — file upload endpoints must validate the Content-Type header and
  reject non-audio/video MIME types before any processing starts.
- **Request size limits** — enforce a maximum body size on Flask:
  - File uploads: configurable via `MAX_UPLOAD_SIZE_MB` env var (default 100MB)
  - JSON payloads: configurable via `MAX_JSON_SIZE_KB` env var (default 1MB)
- **Sensitive header redaction** — strip or mask `Authorization`, `X-API-Key`, `Cookie` and
  similar headers from `task_step_logs` before persisting them to PostgreSQL.

---

## Part 4 — Health Checks

The app must expose three endpoints following Kubernetes probe conventions:

**`GET /api/liveness`** — is the process alive? Must always return 200 as long as the Flask
process is running. No dependency checks. Used as the K8s liveness probe.

**`GET /api/readiness`** — is the app ready to accept traffic? Must check that PostgreSQL
is reachable (execute `SELECT 1`) and that the Kafka consumer has active partition assignments.
Returns 200 only if both pass. Returns 503 otherwise. Used as the K8s readiness probe.

**`GET /api/health`** — full dependency health report. Must check all three:
PostgreSQL (`SELECT 1`), Redis (`PING`), and Kafka (list topics or verify broker connectivity).
Each check must record latency in milliseconds. The overall status must be:
- `healthy` — all checks pass and all latencies are under threshold
- `degraded` — all checks pass but at least one latency exceeds 500ms
- `unhealthy` — at least one check failed

Returns HTTP 200 for `healthy`/`degraded`, HTTP 503 for `unhealthy`.

---

## Part 5 — Resilience

### 5.1 Graceful Shutdown

The app must handle `SIGTERM` and `SIGINT` cleanly:

1. Stop accepting new messages from Kafka immediately upon signal receipt
2. Allow in-flight task greenlets to finish (with a configurable drain timeout, default 30s)
3. Force-cancel any greenlets still running after the timeout
4. Close the Kafka consumer and database connection pool cleanly before exiting
5. Log each shutdown phase clearly so ops can observe progress in logs

---

## Part 6 — API Hardening

### 6.1 Rate Limiting

- Implement sliding-window rate limiting on `POST /api/v1/tasks` using Redis as the counter
  store (so it works across multiple replicas)
- Limit is configurable via `RATE_LIMIT_RPM` env var (default 100 requests/minute)
- Exceeded requests must return HTTP 429 with a `Retry-After` header (seconds until the
  window resets)
- The rate limit key must be per IP (use `X-Forwarded-For` if present, fall back to
  `remote_addr`)

### 6.2 API Versioning

- All task and business logic routes must be prefixed `/api/v1/`
- Health endpoints (`/api/health`, `/api/liveness`, `/api/readiness`) are intentionally
  unversioned — they follow Kubernetes probe conventions
- When breaking changes are introduced in a future `/api/v2/`, the v1 routes must remain
  active for a deprecation window
- v1 endpoints should return `Deprecation: true` and `Sunset: <date>` response headers
  once v2 is live, to signal clients to migrate
- The node catalogue (DAG) is versioned separately from the API — graph changes must be
  additive only (new nodes/edges); removing a node is a breaking change requiring a v2
  migration plan

### 6.3 Pagination on Task List

- `GET /api/v1/tasks` must use **cursor-based pagination** (not offset-based — offsets
  become unreliable and slow on large datasets)
- The cursor is the UUID of the last seen task, encoded opaquely in the response
- Parameters: `cursor` (pagination cursor), `limit` (max items, capped at 200, default 50),
  `sort` (column and direction, e.g. `created_at:desc`), `created_after` and `created_before`
  (ISO date strings for range filtering)
- The response must include `next_cursor` (null if no more pages) and `has_more` (boolean)
- `step_logs` inside a task detail response must be paginated separately — never returned
  inline in bulk

---

## Part 7 — Performance

### 7.1 CPU maxed out

If the process shows 100% CPU when idle (visible in htop), try to find the root problem of if (while True without sleeps, qf library bottlenecks, etc).


---

## Part 8 — Testing Requirements

### 8.1 Unit Tests

The following must have unit test coverage:

- **DAG planner — ingest path resolution**: given each input type (text, audio file, video
  file, YouTube URL), verify the correct Phase 1 node sequence is produced
- **DAG planner — branch construction**: for each output type, verify the correct Phase 2
  node sequence is produced, including that `lang_detect + translate` are injected (and only
  injected) for `requires_en = true` nodes
- **DAG planner — fan-out**: verify that requesting multiple outputs produces the correct
  number of branches with correct steps each
- **DAG planner — error cases**: unknown output type, unsupported file extension, empty input
- **Input detector**: test all valid and invalid inputs for correct type detection
- **Translate conditional skip**: verify that the translate executor promotes `text → text_en`
  without a service call when `context["lang"] == "en"`, and makes the service call otherwise

### 8.2 Full Environment Integration Tests

A `docker-compose.test.yml` is provided that brings up all third-party dependencies
(PostgreSQL, Redis, Kafka/ZooKeeper). The third-parties services may be already running
locally, check before starting the docker-compose.

An end-to-end test script must cover the following scenarios as concrete HTTP calls (curl or
Python requests), with pass/fail assertions on status codes and response body fields:

1. **Text → single output (NER, Japanese input)** — verifies full EN prep chain runs
2. **Text → single output (NER, English input)** — verifies translate step is skipped
3. **Text → fan-out (NER + summary + IPTC)** — verifies all three branches complete and
   all three output keys are present in the result
4. **Audio file → NER + summary** — verifies Phase 1 (STT) runs and Phase 2 fan-out works
5. **YouTube URL → NER + summary** — verifies yt-dlp + STT + fan-out chain
6. **Invalid file type (PDF)** — must return HTTP 400
7. **Unknown output type** — must return HTTP 400
8. **Template injection attempt** — must return HTTP 400
9. **Rate limiting** — send 110 requests in a tight loop, verify at least some return HTTP 429
10. **Pagination** — verify `has_more` and `next_cursor` are present in task list response

A wrapper shell script must: start the compose environment, wait for qflow readiness (poll
`/api/liveness`), run the test script, tear down the environment, and exit with the test
script's exit code so it can be used in CI.

## Part 9 — Documentation

- Always keep README.md up-to-date with the latest changes, explain the architecture, terminology,
and any other relevant information. Add mermaid diagrams for the DAG if possible and any complicated flows and concepts.
- Document main methods of the code so it's easy for a new developer to understand what's going on.