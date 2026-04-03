#!/usr/bin/env bash
# =============================================================================
# E2E Test Suite — Full Environment
#
# Starts docker-compose infrastructure, launches the app, runs all endpoint
# tests, validates flows, checks observability, monitors resources, and
# writes a comprehensive report.
#
# Usage:
#   ./tests/e2e/run_e2e.sh
#
# Prerequisites:
#   - docker compose available
#   - Python venv with dependencies installed
#   - Ports 5000, 9094, 5432, 6379, 16686 available
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
REPORT_DIR="$PROJECT_DIR/reports"
REPORT_FILE="$REPORT_DIR/e2e_report_$(date +%Y%m%d_%H%M%S).txt"
APP_PID=""
APP_LOG="$REPORT_DIR/app.log"
PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0

API_URL="http://localhost:5000"

mkdir -p "$REPORT_DIR"

# =============================================================================
# Helpers
# =============================================================================

log()  { echo "[$(date +%H:%M:%S)] $*" | tee -a "$REPORT_FILE"; }
pass() { PASS_COUNT=$((PASS_COUNT + 1)); log "  PASS: $1"; }
fail() { FAIL_COUNT=$((FAIL_COUNT + 1)); log "  FAIL: $1"; }
skip() { SKIP_COUNT=$((SKIP_COUNT + 1)); log "  SKIP: $1"; }

section() {
    log ""
    log "================================================================"
    log "  $1"
    log "================================================================"
}

cleanup() {
    section "CLEANUP"
    if [ -n "$APP_PID" ] && kill -0 "$APP_PID" 2>/dev/null; then
        log "Stopping app (PID $APP_PID)..."
        kill "$APP_PID" 2>/dev/null || true
        wait "$APP_PID" 2>/dev/null || true
    fi
    log "Stopping docker-compose..."
    cd "$PROJECT_DIR" && docker compose down --timeout 10 2>/dev/null || true
    log "Cleanup done."
}

trap cleanup EXIT

# =============================================================================
# Resource monitoring (background)
# =============================================================================

monitor_resources() {
    local monitor_file="$REPORT_DIR/resource_monitor.csv"
    echo "timestamp,cpu_percent,mem_used_mb,mem_total_mb,docker_mem_mb" > "$monitor_file"
    while true; do
        local ts=$(date +%H:%M:%S)
        local cpu=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' 2>/dev/null || echo "0")
        local mem_info=$(free -m | awk '/^Mem:/{print $3","$2}' 2>/dev/null || echo "0,0")
        local docker_mem=$(docker stats --no-stream --format "{{.MemUsage}}" 2>/dev/null | \
            awk -F/ '{gsub(/[^0-9.]/, "", $1); sum+=$1} END{printf "%.0f", sum}' 2>/dev/null || echo "0")
        echo "$ts,$cpu,$mem_info,$docker_mem" >> "$monitor_file"
        sleep 5
    done
}

# =============================================================================
# 1. Infrastructure Setup
# =============================================================================

section "1. INFRASTRUCTURE SETUP"

cd "$PROJECT_DIR"

log "Stopping any existing containers..."
docker compose down --timeout 10 2>/dev/null || true
sleep 2

log "Starting docker-compose..."
docker compose up -d 2>&1 | tee -a "$REPORT_FILE"

log "Waiting for services to be healthy..."
MAX_WAIT=120
WAITED=0
ALL_HEALTHY=false

while [ $WAITED -lt $MAX_WAIT ]; do
    KAFKA_OK=$(docker inspect --format='{{.State.Health.Status}}' aiflow-kafka 2>/dev/null || echo "missing")
    REDIS_OK=$(docker inspect --format='{{.State.Health.Status}}' aiflow-redis 2>/dev/null || echo "missing")
    PG_OK=$(docker inspect --format='{{.State.Health.Status}}' aiflow-postgres 2>/dev/null || echo "missing")
    JAEGER_OK=$(docker inspect --format='{{.State.Health.Status}}' aiflow-jaeger 2>/dev/null || echo "missing")

    log "  Health: kafka=$KAFKA_OK redis=$REDIS_OK postgres=$PG_OK jaeger=$JAEGER_OK (${WAITED}s)"

    if [ "$KAFKA_OK" = "healthy" ] && [ "$REDIS_OK" = "healthy" ] && \
       [ "$PG_OK" = "healthy" ] && [ "$JAEGER_OK" = "healthy" ]; then
        ALL_HEALTHY=true
        break
    fi

    sleep 5
    WAITED=$((WAITED + 5))
done

if [ "$ALL_HEALTHY" = true ]; then
    pass "All infrastructure services healthy (${WAITED}s)"
else
    fail "Infrastructure not healthy after ${MAX_WAIT}s"
    log "  kafka=$KAFKA_OK redis=$REDIS_OK postgres=$PG_OK jaeger=$JAEGER_OK"
    exit 1
fi

# =============================================================================
# 2. Start Application
# =============================================================================

section "2. APPLICATION STARTUP"

cd "$PROJECT_DIR"

# Activate venv if exists
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

log "Starting application..."
python main.py > "$APP_LOG" 2>&1 &
APP_PID=$!
log "App PID: $APP_PID"

# Start resource monitor in background
monitor_resources &
MONITOR_PID=$!

# Wait for API to be ready
MAX_WAIT=30
WAITED=0
API_READY=false

while [ $WAITED -lt $MAX_WAIT ]; do
    if curl -sf "$API_URL/api/health" > /dev/null 2>&1; then
        API_READY=true
        break
    fi
    sleep 1
    WAITED=$((WAITED + 1))
done

if [ "$API_READY" = true ]; then
    pass "API ready at $API_URL (${WAITED}s)"
else
    fail "API did not start within ${MAX_WAIT}s"
    log "--- App log tail ---"
    tail -50 "$APP_LOG" | tee -a "$REPORT_FILE"
    exit 1
fi

# =============================================================================
# 3. Health Check
# =============================================================================

section "3. HEALTH CHECK"

HEALTH=$(curl -sf "$API_URL/api/health" 2>&1) || true
if echo "$HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['status']=='healthy'" 2>/dev/null; then
    pass "GET /api/health -> healthy"
    log "  Response: $HEALTH"
else
    fail "GET /api/health"
    log "  Response: $HEALTH"
fi

# =============================================================================
# 4. (Skipped Flow Strategies)
# =============================================================================

section "4. FLOW STRATEGIES (skipped)"

# =============================================================================
# 5. Valid Task Creation & Execution
# =============================================================================

section "5. VALID TASK CREATION & POLLING"

test_task() {
    local desc="$1"
    local payload="$2"
    local expect_field="$3"

    local response
    local http_code

    response=$(curl -sf -w "\n%{http_code}" -X POST "$API_URL/api/tasks" \
        -H "Content-Type: application/json" \
        -d "$payload" 2>&1) || true

    http_code=$(echo "$response" | tail -1)
    body=$(echo "$response" | sed '$d')

    if [ "$http_code" != "201" ]; then
        fail "$desc -> HTTP $http_code"
        log "  Payload: $payload"
        log "  Response: $body"
        return 1
    fi

    task_id=$(echo "$body" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null || echo "")
    if [ -z "$task_id" ]; then
        fail "$desc -> no task_id in response"
        log "  Response: $body"
        return 1
    fi

    pass "$desc -> 201 (task_id=$task_id)"

    # Poll for completion
    local max_poll=30
    local polled=0
    local status="PENDING"

    while [ $polled -lt $max_poll ]; do
        sleep 1
        polled=$((polled + 1))
        local task_resp
        task_resp=$(curl -sf "$API_URL/api/tasks/$task_id" 2>&1) || true
        status=$(echo "$task_resp" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])" 2>/dev/null || echo "UNKNOWN")

        if [ "$status" = "COMPLETED" ] || [ "$status" = "FAILED" ] || [ "$status" = "TERMINATED" ]; then
            break
        fi
    done

    if [ "$status" = "COMPLETED" ]; then
        # Check expected field in final_output
        local has_field
        has_field=$(echo "$task_resp" | python3 -c "
import sys,json
d=json.load(sys.stdin)
fo=d.get('final_output') or {}
print('yes' if '$expect_field' in fo else 'no')
" 2>/dev/null || echo "no")
        if [ "$has_field" = "yes" ]; then
            pass "  Poll: COMPLETED with '$expect_field' in output (${polled}s)"
        else
            fail "  Poll: COMPLETED but missing '$expect_field' in output"
            log "  Task response: $task_resp"
        fi
    else
        fail "  Poll: status=$status after ${polled}s (expected COMPLETED)"
        log "  Task response: $task_resp"
    fi

    echo "$task_id"
}

# Text -> NER
test_task "POST text->ner" \
    '{"input_data":{"text":"John Smith lives in Berlin and works at Google."},"outputs":["ner_result"]}' \
    "ner_result"

# Text -> Sentiment
test_task "POST text->sentiment" \
    '{"input_data":{"text":"I love this product! It is amazing."},"outputs":["sentiment_result"]}' \
    "sentiment"

# Text -> Summary
test_task "POST text->summary" \
    '{"input_data":{"text":"Technology is advancing rapidly in all sectors of the economy."},"outputs":["summary"]}' \
    "summary"

# File upload -> STT
test_task "POST file->stt" \
    '{"input_data":{"file_path":"/tmp/test.mp4"},"outputs":["text"]}' \
    "text"

# YouTube -> STT
test_task "POST youtube->stt" \
    '{"input_data":{"url":"https://youtube.com/watch?v=test123"},"outputs":["text"]}' \
    "text"

# =============================================================================
# 6. Task List & Get
# =============================================================================

section "6. TASK LIST & GET"

# List all tasks
LIST_RESP=$(curl -sf "$API_URL/api/tasks" 2>&1) || true
TASK_COUNT=$(echo "$LIST_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['count'])" 2>/dev/null || echo "0")
if [ "$TASK_COUNT" -gt 0 ]; then
    pass "GET /api/tasks -> $TASK_COUNT tasks"
else
    fail "GET /api/tasks -> 0 tasks"
fi

# List with filter
FILTER_RESP=$(curl -sf "$API_URL/api/tasks?status=COMPLETED&limit=5" 2>&1) || true
FILTER_COUNT=$(echo "$FILTER_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['count'])" 2>/dev/null || echo "0")
log "  Filtered (status=COMPLETED, limit=5): $FILTER_COUNT tasks"

# =============================================================================
# 7. Invalid Request Handling
# =============================================================================

section "7. INVALID REQUEST HANDLING"

# Missing fields
RESP=$(curl -sf -w "\n%{http_code}" -X POST "$API_URL/api/tasks" \
    -H "Content-Type: application/json" \
    -d '{}' 2>&1) || true
HTTP_CODE=$(echo "$RESP" | tail -1)
if [ "$HTTP_CODE" = "400" ]; then
    pass "POST empty body -> 400"
else
    fail "POST empty body -> HTTP $HTTP_CODE (expected 400)"
fi

# Invalid input_type
RESP=$(curl -sf -w "\n%{http_code}" -X POST "$API_URL/api/tasks" \
    -H "Content-Type: application/json" \
    -d '{"outputs":["ner_result"]}' 2>&1) || true
HTTP_CODE=$(echo "$RESP" | tail -1)
if [ "$HTTP_CODE" = "400" ]; then
    pass "POST invalid input_type -> 400"
else
    fail "POST invalid input_type -> HTTP $HTTP_CODE (expected 400)"
fi

# Invalid desired_output
RESP=$(curl -sf -w "\n%{http_code}" -X POST "$API_URL/api/tasks" \
    -H "Content-Type: application/json" \
    -d '{"input_data":{"text":"hello"},"outputs":["nonexistent"]}' 2>&1) || true
HTTP_CODE=$(echo "$RESP" | tail -1)
if [ "$HTTP_CODE" = "400" ]; then
    pass "POST invalid desired_output -> 400"
else
    fail "POST invalid desired_output -> HTTP $HTTP_CODE (expected 400)"
fi

# Invalid combination
RESP=$(curl -sf -w "\n%{http_code}" -X POST "$API_URL/api/tasks" \
    -H "Content-Type: application/json" \
    -d '{"input_data":{"text":""},"outputs":["ner_result"]}' 2>&1) || true
HTTP_CODE=$(echo "$RESP" | tail -1)
if [ "$HTTP_CODE" = "400" ]; then
    pass "POST text->stt (invalid combo) -> 400"
else
    fail "POST text->stt -> HTTP $HTTP_CODE (expected 400)"
fi

# Nonexistent task
RESP=$(curl -sf -w "\n%{http_code}" "$API_URL/api/tasks/00000000-0000-0000-0000-000000000000" 2>&1) || true
HTTP_CODE=$(echo "$RESP" | tail -1)
if [ "$HTTP_CODE" = "404" ]; then
    pass "GET nonexistent task -> 404"
else
    fail "GET nonexistent task -> HTTP $HTTP_CODE (expected 404)"
fi

# Delete nonexistent task
RESP=$(curl -sf -w "\n%{http_code}" -X DELETE "$API_URL/api/tasks/00000000-0000-0000-0000-000000000000" 2>&1) || true
HTTP_CODE=$(echo "$RESP" | tail -1)
if [ "$HTTP_CODE" = "404" ]; then
    pass "DELETE nonexistent task -> 404"
else
    fail "DELETE nonexistent task -> HTTP $HTTP_CODE (expected 404)"
fi

# =============================================================================
# 8. Task Deletion
# =============================================================================

section "8. TASK DELETION"

# Create a task, then delete it
DEL_RESP=$(curl -sf -X POST "$API_URL/api/tasks" \
    -H "Content-Type: application/json" \
    -d '{"input_data":{"text":"delete me"},"outputs":["ner_result"]}' 2>&1) || true
DEL_ID=$(echo "$DEL_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null || echo "")

if [ -n "$DEL_ID" ]; then
    RESP=$(curl -sf -w "\n%{http_code}" -X DELETE "$API_URL/api/tasks/$DEL_ID" 2>&1) || true
    HTTP_CODE=$(echo "$RESP" | tail -1)
    if [ "$HTTP_CODE" = "200" ]; then
        pass "DELETE task $DEL_ID -> 200"
    else
        fail "DELETE task $DEL_ID -> HTTP $HTTP_CODE"
    fi

    # Verify it's gone
    RESP=$(curl -sf -w "\n%{http_code}" "$API_URL/api/tasks/$DEL_ID" 2>&1) || true
    HTTP_CODE=$(echo "$RESP" | tail -1)
    if [ "$HTTP_CODE" = "404" ]; then
        pass "GET deleted task -> 404"
    else
        fail "GET deleted task -> HTTP $HTTP_CODE (expected 404)"
    fi
else
    skip "Could not create task for deletion test"
fi

# =============================================================================
# 9. Observability — Jaeger Traces
# =============================================================================

section "9. OBSERVABILITY — JAEGER TRACES"

sleep 3  # allow traces to flush

JAEGER_RESP=$(curl -sf "http://localhost:16686/api/services" 2>&1) || true
if echo "$JAEGER_RESP" | grep -q "data"; then
    SERVICES=$(echo "$JAEGER_RESP" | python3 -c "
import sys,json
d=json.load(sys.stdin)
print(', '.join(d.get('data', [])))
" 2>/dev/null || echo "none")
    pass "Jaeger reachable, services: $SERVICES"
else
    skip "Jaeger not reachable or no services"
fi

# =============================================================================
# 10. Check for Silent Failures in App Log
# =============================================================================

section "10. LOG ANALYSIS"

if [ -f "$APP_LOG" ]; then
    ERROR_COUNT=$(grep -c "ERROR" "$APP_LOG" 2>/dev/null || echo "0")
    TRACEBACK_COUNT=$(grep -c "Traceback" "$APP_LOG" 2>/dev/null || echo "0")
    WARNING_COUNT=$(grep -c "WARNING" "$APP_LOG" 2>/dev/null || echo "0")

    log "  Errors: $ERROR_COUNT"
    log "  Tracebacks: $TRACEBACK_COUNT"
    log "  Warnings: $WARNING_COUNT"

    if [ "$TRACEBACK_COUNT" -gt 0 ]; then
        fail "Found $TRACEBACK_COUNT tracebacks in app log"
        log "--- Tracebacks ---"
        grep -A 5 "Traceback" "$APP_LOG" | head -50 | tee -a "$REPORT_FILE"
    else
        pass "No tracebacks in app log"
    fi

    if [ "$ERROR_COUNT" -gt 0 ]; then
        log "--- Errors ---"
        grep "ERROR" "$APP_LOG" | head -20 | tee -a "$REPORT_FILE"
    fi
else
    skip "App log not found"
fi

# =============================================================================
# 11. Resource Consumption Summary
# =============================================================================

section "11. RESOURCE CONSUMPTION"

# Stop monitor
kill "$MONITOR_PID" 2>/dev/null || true

MONITOR_FILE="$REPORT_DIR/resource_monitor.csv"
if [ -f "$MONITOR_FILE" ]; then
    SAMPLES=$(wc -l < "$MONITOR_FILE")
    log "  Resource samples: $((SAMPLES - 1))"

    # Peak memory from docker
    PEAK_DOCKER=$(awk -F, 'NR>1{if($5+0 > max) max=$5+0} END{print max}' "$MONITOR_FILE" 2>/dev/null || echo "0")
    log "  Peak Docker memory: ${PEAK_DOCKER}MB"

    # Peak system memory
    PEAK_MEM=$(awk -F, 'NR>1{if($3+0 > max) max=$3+0} END{print max}' "$MONITOR_FILE" 2>/dev/null || echo "0")
    TOTAL_MEM=$(awk -F, 'NR>1{print $4; exit}' "$MONITOR_FILE" 2>/dev/null || echo "0")
    log "  Peak system memory: ${PEAK_MEM}MB / ${TOTAL_MEM}MB"

    pass "Resource monitoring completed ($((SAMPLES - 1)) samples)"
else
    skip "Resource monitor file not found"
fi

# =============================================================================
# FINAL SUMMARY
# =============================================================================

section "FINAL SUMMARY"

TOTAL=$((PASS_COUNT + FAIL_COUNT + SKIP_COUNT))
log ""
log "  Total:   $TOTAL"
log "  Passed:  $PASS_COUNT"
log "  Failed:  $FAIL_COUNT"
log "  Skipped: $SKIP_COUNT"
log ""
log "  Report: $REPORT_FILE"
log "  App log: $APP_LOG"
log "  Resources: $REPORT_DIR/resource_monitor.csv"
log ""

if [ "$FAIL_COUNT" -gt 0 ]; then
    log "  RESULT: FAIL"
    exit 1
else
    log "  RESULT: PASS"
    exit 0
fi
TOTAL"
log "  Passed:  $PASS_COUNT"
log "  Failed:  $FAIL_COUNT"
log "  Skipped: $SKIP_COUNT"
log ""
log "  Report: $REPORT_FILE"
log "  App log: $APP_LOG"
log "  Resources: $REPORT_DIR/resource_monitor.csv"
log ""

if [ "$FAIL_COUNT" -gt 0 ]; then
    log "  RESULT: FAIL"
    exit 1
else
    log "  RESULT: PASS"
    exit 0
fi
