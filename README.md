# AI Flow Orchestrator

An on-demand AI pipeline orchestrator built on the QF Framework. The system receives tasks (text, audio/video files, or YouTube links), dynamically plans an execution graph (DAG), and dispatches AI microservice calls in parallel to produce one or more analytical outputs.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Quick Start](#quick-start)
3. [API Reference](#api-reference)
4. [How to Model Data](#how-to-model-data)
5. [How Step Output Transforms Work](#how-step-output-transforms-work)
6. [All Supported Flows](#all-supported-flows)
7. [How to Add a New Service](#how-to-add-a-new-service)
8. [Configuration](#configuration)
9. [Testing](#testing)
10. [Docker Deployment](#docker-deployment)

---

## Architecture Overview

```
Client ──POST /api/v1/tasks──► API (Flask-RESTX)
                                    │
                               validate input_data + outputs
                                    │
                              DAG Planner builds ExecutionPlan
                               (ingest steps + branches)
                                    │
                              Store Task in PostgreSQL
                                    │
                          Publish to Kafka (flow.tasks.in)
                                    │
                         ┌──────────▼────────────┐
                         │   Kafka Worker          │
                         │   (flow_executor)       │
                         │                         │
                         │   Phase 1: Sequential   │
                         │   ytdlp_download → stt  │
                         │          ▼              │
                         │   Phase 2: Parallel     │
                         │   ├── ner branch        │
                         │   ├── sentiment branch  │
                         │   └── summary branch    │
                         └──────────┬──────────────┘
                                    │
                         Update Task in PostgreSQL
                              (COMPLETED + final_output)
                                    │
              Client ◄──GET /api/v1/tasks/{id}──── Poll for result
```

### Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| **Node Catalogue** | `src/dag/catalogue.py` | Declarative registry of all processing nodes |
| **DAG Planner** | `src/dag/planner.py` | Builds execution plan from input + outputs |
| **DAG Runner** | `src/dag/runner.py` | Executes plan with gevent parallelism |
| **Node Executor** | `src/dag/executors/node_executor.py` | Dispatches individual HTTP/TRANSFORM nodes |
| **API** | `src/api/endpoints.py` | HTTP endpoints (registered via `maps/endpoint.json`) |
| **Task Service** | `src/services/task_service.py` | Task CRUD operations against PostgreSQL |
| **Kafka Worker** | `src/workers/flow_executor.py` | Consumes tasks and runs the DAG |
| **Task Model** | `src/models/task.py` | SQLAlchemy Task table |

### Execution Flow

1. Client `POST /api/v1/tasks` with `input_data` + `outputs`
2. **Input detection**: classify `input_data` as `text`, `audio_path`, or `youtube_url`
3. **Plan building**: compute sequential ingest steps (Phase 1) + parallel analysis branches (Phase 2)
4. **Task stored** in PostgreSQL as `PENDING` with the full `execution_plan`
5. **Kafka message** published to `flow.tasks.in`
6. **Worker** picks up message, reconstructs plan, executes it
7. **Phase 1** (sequential): `ytdlp_download` → `stt` for YouTube/audio; skipped for text
8. **Phase 2** (parallel, gevent greenlets): one branch per requested output
9. Task updated to `COMPLETED` with `final_output` dict keyed by output type
10. Client polls `GET /api/v1/tasks/{id}` until `status == "COMPLETED"`

---

## Quick Start

### Prerequisites

```bash
# Start infrastructure
docker compose up -d

# Install dependencies
pip install -r requirements.txt

# Start the app
python main.py
```

### Create your first task

```bash
# Text → Named Entity Recognition
curl -X POST http://localhost:5000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "input_data": {"text": "John Smith lives in Berlin and works at Google."},
    "outputs": ["ner_result"]
  }'

# Response:
# {
#   "id": "550e8400-e29b-41d4-a716-446655440000",
#   "input_type": "text",
#   "outputs": ["ner_result"],
#   "status": "PENDING",
#   "execution_plan": { ... }
# }

# Poll for result
curl http://localhost:5000/api/v1/tasks/550e8400-e29b-41d4-a716-446655440000
```

### Multiple outputs in one request

```bash
curl -X POST http://localhost:5000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "input_data": {"text": "Apple released a new product at their annual event."},
    "outputs": ["ner_result", "sentiment_result", "summary", "iptc_tags", "keywords"]
  }'
```

All five outputs are computed **in parallel** in separate gevent branches.

---

## API Reference

### `POST /api/v1/tasks` — Create a task

**Request body:**

```json
{
  "input_data": {
    "text": "string"
  },
  "outputs": ["ner_result", "sentiment_result"]
}
```

The `input_data` field auto-detects the input type based on its keys:

| input_data key | Detected type | Ingest chain |
|----------------|---------------|--------------|
| `{"text": "..."}` | `text` | (none — direct to analysis) |
| `{"file_path": "/tmp/audio.mp3"}` | `audio_path` | `stt` |
| `{"file_path": "/tmp/video.mp4"}` | `audio_path` | `stt` |
| `{"url": "https://youtube.com/..."}` | `youtube_url` | `ytdlp_download` → `stt` |

**Optional `input_type` hint:**

If provided, `input_data` can be a plain string that gets automatically wrapped:

```json
{"input_type": "text",         "input_data": "Hello world",         "outputs": ["ner_result"]}
{"input_type": "youtube_link", "input_data": "https://youtu.be/...", "outputs": ["summary"]}
```

**Valid output types** (query `GET /api/v1/flows` for the live list):

| Output type | Description | Requires English |
|-------------|-------------|-----------------|
| `ner_result` | Named entity recognition | Yes (auto-translated) |
| `sentiment_result` | Sentiment classification | Yes (auto-translated) |
| `summary` | Text summarization | No |
| `iptc_tags` | IPTC taxonomy classification | No |
| `keywords` | Keyword extraction | No |
| `lang_meta` | Language detection result | No |
| `text_en` | English translation | No |

**Response (201 Created):**

```json
{
  "id": "550e8400-...",
  "input_type": "text",
  "input_data": {"text": "..."},
  "outputs": ["ner_result"],
  "execution_plan": {
    "input_type": "text",
    "ingest_steps": [],
    "branches": [
      {"output_type": "ner_result", "steps": ["lang_detect", "translate", "ner"]}
    ]
  },
  "status": "PENDING",
  "created_at": "2026-04-04T12:00:00Z"
}
```

---

### `GET /api/v1/tasks` — List tasks

Query parameters:

| Param | Default | Description |
|-------|---------|-------------|
| `status` | — | Filter: `PENDING`, `RUNNING`, `COMPLETED`, `FAILED` |
| `input_type` | — | Filter: `text`, `audio_path`, `youtube_url` |
| `limit` | 50 | Max results (max 200) |
| `cursor` | — | Pagination cursor from previous response |
| `sort` | `created_at:desc` | Sort order |
| `created_after` | — | ISO 8601 start date |
| `created_before` | — | ISO 8601 end date |

**Response:**

```json
{
  "tasks": [...],
  "next_cursor": "task-id-for-next-page",
  "has_more": true
}
```

---

### `GET /api/v1/tasks/{task_id}` — Get task status

```json
{
  "id": "...",
  "status": "COMPLETED",
  "final_output": {
    "ner_result": {
      "entities": [
        {"text": "John Smith", "type": "PERSON", "start": 0, "end": 10},
        {"text": "Berlin", "type": "LOCATION", "start": 20, "end": 26}
      ]
    }
  },
  "error": null
}
```

**Task statuses:**

| Status | Meaning |
|--------|---------|
| `PENDING` | Task created, waiting for Kafka consumer |
| `RUNNING` | DAG execution in progress |
| `COMPLETED` | All branches finished successfully |
| `FAILED` | One or more branches failed |

---

### Other endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/tasks/{id}` | `DELETE` | Cancel/delete a task |
| `/api/v1/tasks/{id}/logs` | `GET` | Paginated per-step execution logs |
| `/api/v1/flows` | `GET` | List node catalogue and valid output types |
| `/api/health` | `GET` | Health check with dependency latencies |
| `/api/liveness` | `GET` | K8s liveness probe (always 200) |
| `/api/readiness` | `GET` | K8s readiness probe (checks PG + Kafka) |

---

## How to Model Data

### Input data format

`input_data` is always a JSON object with **one recognized key**:

```python
# Text analysis — go directly to analysis nodes
{"text": "Your text here"}

# Audio/video file — STT runs first, then analysis
{"file_path": "/path/to/audio.mp3"}   # .wav, .mp4, .mkv, .avi, .webm, .mov, .ts, .flac, .aac, .m4a

# YouTube URL — download + STT, then analysis
{"url": "https://youtube.com/watch?v=VIDEO_ID"}
{"url": "https://youtu.be/VIDEO_ID"}
```

Detection priority: `url` (YouTube pattern) > `file_path` (extension check) > `text`.

### Output data structure

Final output is a dict keyed by output type:

```python
# ner_result
{
  "ner_result": {
    "entities": [
      {"text": "John Smith", "type": "PERSON",       "start": 0,  "end": 10},
      {"text": "Berlin",     "type": "LOCATION",     "start": 20, "end": 26},
      {"text": "Acme Corp",  "type": "ORGANIZATION", "start": 40, "end": 49}
    ]
  }
}

# sentiment_result
{"sentiment_result": {"sentiment": "positive", "score": 0.87}}

# summary
{"summary": {"summary": "A brief summary of the text."}}

# iptc_tags
{"iptc_tags": {"tags": ["economy", "business", "technology"]}}

# keywords
{"keywords": {"keywords": ["AI", "conference", "strategy"]}}

# lang_meta
{"lang_meta": {"language": "ja", "text": "東京で開催..."}}

# text_en
{"text_en": "At a conference held in Tokyo..."}
```

Multi-output tasks return all outputs in a single dict:

```python
{
  "ner_result":      {...},
  "sentiment_result": {...},
  "summary":         {...}
}
```

---

## How Step Output Transforms Work

The DAG runner uses a **shared context dict** to pass data between steps. Each node reads from `context[node.input_type]` and writes to `context[node.output_type]`.

### Context keys by node

| Node | Reads | Writes |
|------|-------|--------|
| `ytdlp_download` | `context["youtube_url"]` | `context["audio_path"]` |
| `stt` | `context["audio_path"]` | `context["text"]` |
| `lang_detect` | `context["text"]` | `context["lang_meta"]` |
| `translate` | `context["text"]`, `context["lang_meta"]` | `context["text_en"]` |
| `ner` | `context["text_en"]` | `context["ner_result"]` |
| `sentiment` | `context["text_en"]` | `context["sentiment_result"]` |
| `summarize` | `context["text"]` | `context["summary"]` |
| `iptc` | `context["text"]` | `context["iptc_tags"]` |
| `keyword_extract` | `context["text"]` | `context["keywords"]` |

### HTTP body template substitution

Each node's `executor_config` has a `body_template`. Placeholders like `{text}` are resolved from the context at execution time:

```python
# Node config:
executor_config={
    "body_template": {"text": "{text}", "source_language": "{lang}", "target_language": "en"}
}

# Context at execution time:
context = {"text": "Hallo Welt", "lang_meta": {"language": "de"}}

# After resolution → HTTP request body:
{"text": "Hallo Welt", "source_language": None, "target_language": "en"}
```

The `{key}` resolver (in `node_executor._build_body`):
1. Looks up `key` in context
2. If value is a `dict`, tries `value[key]` (same-named field), else passes the dict
3. If value is `None`/missing, uses `None`

### Conditional skip: translate node

The `translate` node has a built-in conditional skip: if the detected language is `"en"`, the translation API is skipped and `context["text"]` is promoted directly to `context["text_en"]`:

```python
# In node_executor.py:
if conditional_skip == "lang_is_en":
    lang = context.get("lang_meta", {}).get("language")
    if lang == "en":
        return context.get("text")  # Passthrough — no API call
```

### Branch isolation (no cross-branch contamination)

Each Phase 2 branch gets a **shallow copy** of the shared context at the start of Phase 2:

```python
# In runner.py:
for branch in plan.branches:
    branch_ctx = copy(context)   # Shallow copy
    gevent.spawn(_run_branch, branch.output_type, branch.steps, branch_ctx, task_id)
```

This means:
- All branches share Phase 1 outputs (`text`, `audio_path`)
- Each branch computes its own `text_en` independently (if needed)
- No branch can overwrite another's intermediate state

---

## All Supported Flows

### Text input

```
input: {"text": "..."}

Plan: ingest=[] + branches:
  ner_result       → [lang_detect → translate → ner]
  sentiment_result → [lang_detect → translate → sentiment]
  summary          → [summarize]
  iptc_tags        → [iptc]
  keywords         → [keyword_extract]
  lang_meta        → [lang_detect]
  text_en          → [lang_detect → translate]
```

### Audio/Video file

```
input: {"file_path": "/path/to/file.mp4"}

Plan: ingest=[stt] + branches (same as text above)
      file_path → audio_path ─(stt)→ text
```

Supported: `.mp3`, `.wav`, `.ogg`, `.flac`, `.aac`, `.m4a`, `.mp4`, `.mkv`, `.avi`, `.webm`, `.mov`, `.ts`

### YouTube URL

```
input: {"url": "https://youtube.com/watch?v=..."}

Plan: ingest=[ytdlp_download, stt] + branches (same as text above)
      youtube_url ─(ytdlp_download)→ audio_path ─(stt)→ text
```

### Multi-output (parallel execution)

All branches execute simultaneously as gevent greenlets. Total time ≈ slowest branch, not sum of all:

```json
{
  "input_data": {"text": "..."},
  "outputs": ["ner_result", "sentiment_result", "summary", "iptc_tags", "keywords"]
}
```

---

## How to Add a New Service

This example adds an **OCR** node that reads text from images.

### Step 1: Add the node to the catalogue

In `src/dag/catalogue.py`, append to `_NODES`:

```python
# Phase 2 analysis node (reads text, writes structured output)
NodeDef(
    node_id="ocr",
    phase=2,
    input_type="text",
    output_type="ocr_result",
    requires_en=False,
    executor_type="HTTP",
    executor_config={
        "method": "POST",
        "url_env": "AI_OCR_URL",    # env var holding the service URL
        "path": "/ocr",
        "body_template": {"text": "{text}"},
        "output_field": "text",     # field to extract from the JSON response
        "timeout_seconds": 60,
    },
    mock_response={"text": "Extracted OCR text from image"},
),
```

For a **Phase 1 ingest node** (e.g. image → text):

```python
NodeDef(
    node_id="image_to_text",
    phase=1,
    input_type="image_path",   # new input type
    output_type="text",        # must produce "text" for Phase 2 to work
    executor_type="HTTP",
    executor_config={
        "method": "POST",
        "url_env": "AI_OCR_URL",
        "path": "/extract",
        "body_template": {"file_path": "{image_path}"},
        "output_field": "text",
        "timeout_seconds": 30,
    },
    mock_response={"text": "Text extracted from image"},
),
```

### Step 2: Register the service URL

In `src/config.py`:

```python
AI_OCR_URL = os.getenv("AI_OCR_URL", "http://localhost:8010")
```

In your `.env` or `docker-compose.yml`:

```bash
AI_OCR_URL=http://ocr-service:8010
```

### Step 3: (Phase 1 only) Update input detection

If introducing `image_path` as a new input type, add extension detection in `src/dag/input_detector.py`:

```python
IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".tiff", ".bmp", ".webp"})

# In detect_input_type():
if file_path:
    ext = os.path.splitext(file_path)[1].lower()
    if ext in MEDIA_EXTENSIONS:
        return "audio_path"
    if ext in IMAGE_EXTENSIONS:      # ← add this
        return "image_path"
    raise InputDetectionError(...)
```

### Step 4: Use it immediately

```bash
# Phase 2 node (input_data is text):
curl -X POST http://localhost:5000/api/v1/tasks \
  -d '{"input_data": {"text": "Sample text"}, "outputs": ["ocr_result"]}'

# Phase 1 node (input_data is image path):
curl -X POST http://localhost:5000/api/v1/tasks \
  -d '{"input_data": {"file_path": "/tmp/scan.png"}, "outputs": ["ner_result"]}'
```

No planner or runner changes are needed. The planner auto-discovers your node via the catalogue.

### Step 5: Add tests

In `tests/unit/test_catalogue.py`:

```python
def test_ocr_node_registered(self):
    assert get_node("ocr") is not None
    assert "ocr_result" in get_all_valid_output_types()
```

In `tests/unit/test_planner.py`:

```python
def test_text_to_ocr(self):
    plan = build_plan({"text": "Hello"}, ["ocr_result"])
    step_ids = [s.node_id for s in plan.branches[0].steps]
    assert "ocr" in step_ids
```

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DEV_MODE` | `true` | Mock all AI service calls |
| `DATABASE_URL` | `postgresql://qf:qf@localhost:5432/ai_flow` | PostgreSQL DSN |
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9094` | Kafka broker |
| `KAFKA_TASK_TOPIC_IN` | `flow.tasks.in` | Input topic |
| `KAFKA_TASK_TOPIC_OUT` | `flow.tasks.out` | Output topic |
| `KAFKA_DLQ_TOPIC` | `flow.tasks.dlq` | Dead-letter queue |
| `REDIS_HOST` | `localhost` | Redis host (rate limiting) |
| `API_PORT` | `5000` | HTTP listen port |
| `ENABLE_TRACING` | `false` | OpenTelemetry export |
| `QSINT_OTLP_ENDPOINT` | `http://localhost:4317` | OTLP gRPC endpoint |
| `UPLOAD_DIR` | `/tmp/uploads` | File upload directory |
| `AI_SERVICE_URL` | `http://localhost:8000` | Lang detect, translate, keywords |
| `AI_STT_URL` | `http://localhost:8001` | Speech-to-text |
| `AI_NER_URL` | `http://localhost:8002` | Named entity recognition |
| `AI_SENTIMENT_URL` | `http://localhost:8005` | Sentiment analysis |
| `AI_SUMMARY_URL` | `http://localhost:8006` | Summarization |
| `AI_TAXONOMY_URL` | `http://localhost:8007` | IPTC taxonomy |

---

## Testing

```bash
make test-unit          # Unit tests — no infra required
make test-integration   # Integration — DEV_MODE + PostgreSQL
make test-quality       # Quality/resilience — PostgreSQL
make test-chaos         # Chaos — PostgreSQL
make test-e2e           # E2E — live API (docker compose + main.py)
make test-all           # unit + integration + quality
```

Reports written to `reports/` after each run.

---

## Docker Deployment

```bash
docker compose up -d        # Start all infrastructure
python main.py              # Start the application
```

### Infrastructure services

| Service | Port | Purpose |
|---------|------|---------|
| PostgreSQL | 5432 | Task storage |
| Kafka | 9094 | Task messaging |
| Redis | 6379 | Rate limiting |
| Kafka UI | 8080 | Broker management |
| Jaeger | 16686 | Distributed tracing |

### Kafka topics

| Topic | Purpose |
|-------|---------|
| `flow.tasks.in` | API → Worker (task execution requests) |
| `flow.tasks.out` | Worker → downstream (results) |
| `flow.tasks.dlq` | Failed tasks after 3 retries |
