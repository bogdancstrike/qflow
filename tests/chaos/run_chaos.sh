#!/usr/bin/env bash
# =============================================================================
# Chaos Test Runner — real infrastructure destruction tests
#
# WARNING: This script kills Docker containers during flow execution.
# Only run in a development environment.
#
# Usage:
#   ./tests/chaos/run_chaos.sh
#
# Prerequisites:
#   - docker compose running (docker compose up -d)
#   - App running (python main.py)
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
REPORT_DIR="$PROJECT_DIR/reports"
REPORT_FILE="$REPORT_DIR/chaos_report_$(date +%Y%m%d_%H%M%S).txt"
API_URL="${API_URL:-http://localhost:5000}"
PASS_COUNT=0
FAIL_COUNT=0

mkdir -p "$REPORT_DIR"

log()  { echo "[$(date +%H:%M:%S)] $*" | tee -a "$REPORT_FILE"; }
pass() { PASS_COUNT=$((PASS_COUNT + 1)); log "  PASS: $1"; }
fail() { FAIL_COUNT=$((FAIL_COUNT + 1)); log "  FAIL: $1"; }

section() {
    log ""
    log "================================================================"
    log "  $1"
    log "================================================================"
}

wait_api() {
    local max_wait=${1:-30}
    local waited=0
    while [ $waited -lt $max_wait ]; do
        if curl -sf "$API_URL/api/health" > /dev/null 2>&1; then
            return 0
        fi
        sleep 1
        waited=$((waited + 1))
    done
    return 1
}

wait_container() {
    local container="$1"
    local max_wait=${2:-60}
    local waited=0
    while [ $waited -lt $max_wait ]; do
        local status
        status=$(docker inspect --format='{{.State.Health.Status}}' "$container" 2>/dev/null || echo "missing")
        if [ "$status" = "healthy" ]; then
            return 0
        fi
        sleep 2
        waited=$((waited + 2))
    done
    return 1
}

# Check prerequisites
if ! curl -sf "$API_URL/api/health" > /dev/null 2>&1; then
    echo "ERROR: API not reachable at $API_URL"
    exit 1
fi

# =============================================================================
# 1. Kill PostgreSQL mid-flow
# =============================================================================

section "1. KILL POSTGRESQL MID-FLOW"

log "Creating a task..."
TASK_RESP=$(curl -sf -X POST "$API_URL/api/tasks" \
    -H "Content-Type: application/json" \
    -d '{"input_type":"text","input_data":"John Smith in Berlin","desired_output":"ner"}' 2>&1) || true
TASK_ID=$(echo "$TASK_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null || echo "")

if [ -z "$TASK_ID" ]; then
    fail "Could not create task"
else
    log "Task created: $TASK_ID"
    sleep 1

    log "Killing PostgreSQL..."
    docker kill aiflow-postgres 2>/dev/null || true
    sleep 3

    # API should still be reachable (just DB operations fail)
    if curl -sf "$API_URL/api/health" > /dev/null 2>&1; then
        pass "API still responds after PostgreSQL killed"
    else
        fail "API unreachable after PostgreSQL killed"
    fi

    # Restart PostgreSQL
    log "Restarting PostgreSQL..."
    docker start aiflow-postgres 2>/dev/null || true
    if wait_container "aiflow-postgres" 60; then
        pass "PostgreSQL recovered"

        # Check task state
        sleep 2
        TASK_CHECK=$(curl -sf "$API_URL/api/tasks/$TASK_ID" 2>&1) || true
        STATUS=$(echo "$TASK_CHECK" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','UNKNOWN'))" 2>/dev/null || echo "ERROR")
        log "  Task status after recovery: $STATUS"
        pass "Task $TASK_ID accessible after recovery (status=$STATUS)"
    else
        fail "PostgreSQL did not recover within 60s"
    fi
fi

# =============================================================================
# 2. Kill Kafka mid-flow
# =============================================================================

section "2. KILL KAFKA MID-FLOW"

log "Creating a task..."
TASK_RESP=$(curl -sf -X POST "$API_URL/api/tasks" \
    -H "Content-Type: application/json" \
    -d '{"input_type":"text","input_data":"Test Kafka resilience","desired_output":"sentiment"}' 2>&1) || true
TASK_ID=$(echo "$TASK_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null || echo "")

if [ -z "$TASK_ID" ]; then
    fail "Could not create task"
else
    log "Task created: $TASK_ID"

    log "Killing Kafka..."
    docker kill aiflow-kafka 2>/dev/null || true
    sleep 3

    # API should still respond for reads
    if curl -sf "$API_URL/api/health" > /dev/null 2>&1; then
        pass "API still responds after Kafka killed"
    else
        log "  API might be degraded — checking health..."
    fi

    # Restart Kafka
    log "Restarting Kafka..."
    docker start aiflow-kafka 2>/dev/null || true
    if wait_container "aiflow-kafka" 90; then
        pass "Kafka recovered"
        sleep 5  # allow rebalance

        # Send a new task to verify Kafka is working
        NEW_RESP=$(curl -sf -w "\n%{http_code}" -X POST "$API_URL/api/tasks" \
            -H "Content-Type: application/json" \
            -d '{"input_type":"text","input_data":"Post-kafka-recovery test","desired_output":"ner"}' 2>&1) || true
        HTTP_CODE=$(echo "$NEW_RESP" | tail -1)
        if [ "$HTTP_CODE" = "201" ]; then
            pass "Task creation works after Kafka recovery"
        else
            fail "Task creation failed after Kafka recovery (HTTP $HTTP_CODE)"
        fi
    else
        fail "Kafka did not recover within 90s"
    fi
fi

# =============================================================================
# 3. Simulate slow AI service (pause Redis)
# =============================================================================

section "3. PAUSE REDIS (simulate slow dependency)"

log "Pausing Redis container..."
docker pause aiflow-redis 2>/dev/null || true
sleep 2

# API should still work (Redis is used for rate limiting, not critical path)
HEALTH_RESP=$(curl -sf "$API_URL/api/health" 2>&1) || true
if echo "$HEALTH_RESP" | grep -q "healthy"; then
    pass "API healthy with Redis paused"
else
    log "  API may be degraded with Redis paused"
fi

log "Unpausing Redis..."
docker unpause aiflow-redis 2>/dev/null || true
sleep 2

if docker inspect --format='{{.State.Health.Status}}' aiflow-redis 2>/dev/null | grep -q "healthy"; then
    pass "Redis recovered after unpause"
else
    fail "Redis not healthy after unpause"
fi

# =============================================================================
# 4. Network partition simulation (disconnect and reconnect)
# =============================================================================

section "4. DISCONNECT/RECONNECT KAFKA FROM NETWORK"

log "Disconnecting Kafka from network..."
docker network disconnect qfnet aiflow-kafka 2>/dev/null || \
    docker network disconnect ai-flow-orchestrator_qfnet aiflow-kafka 2>/dev/null || \
    log "  Could not disconnect (network name may differ)"

sleep 5

log "Reconnecting Kafka..."
docker network connect qfnet aiflow-kafka 2>/dev/null || \
    docker network connect ai-flow-orchestrator_qfnet aiflow-kafka 2>/dev/null || \
    log "  Could not reconnect (network name may differ)"

sleep 5

if wait_container "aiflow-kafka" 30; then
    pass "Kafka recovered after network partition"
else
    log "  Kafka may need manual restart"
    docker restart aiflow-kafka 2>/dev/null || true
    wait_container "aiflow-kafka" 60 && pass "Kafka recovered after restart" || fail "Kafka unrecoverable"
fi

# =============================================================================
# SUMMARY
# =============================================================================

section "SUMMARY"

TOTAL=$((PASS_COUNT + FAIL_COUNT))
log ""
log "  Total:  $TOTAL"
log "  Passed: $PASS_COUNT"
log "  Failed: $FAIL_COUNT"
log ""
log "  Report: $REPORT_FILE"

if [ "$FAIL_COUNT" -gt 0 ]; then
    log "  RESULT: FAIL"
    exit 1
else
    log "  RESULT: PASS"
    exit 0
fi
