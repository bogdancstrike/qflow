#!/usr/bin/env bash
# =============================================================================
# Load Test Runner — runs baseline, stress, and spike scenarios
#
# Usage:
#   ./tests/load/run_load_tests.sh
#
# Prerequisites:
#   - pip install locust
#   - API running at localhost:5000
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
REPORT_DIR="$PROJECT_DIR/reports"
LOCUST_FILE="$SCRIPT_DIR/locustfile.py"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$REPORT_DIR"

API_URL="${API_URL:-http://localhost:5000}"

# Check API is reachable
if ! curl -sf "$API_URL/api/health" > /dev/null 2>&1; then
    echo "ERROR: API not reachable at $API_URL"
    echo "Start with: docker compose up -d && python main.py"
    exit 1
fi

echo "API reachable at $API_URL"

# Check locust is installed
if ! command -v locust &> /dev/null; then
    echo "ERROR: locust not installed. Run: pip install locust"
    exit 1
fi

run_scenario() {
    local name="$1"
    local users="$2"
    local spawn_rate="$3"
    local duration="$4"

    echo ""
    echo "================================================================"
    echo "  SCENARIO: $name"
    echo "  Users: $users, Spawn rate: $spawn_rate/s, Duration: $duration"
    echo "================================================================"

    locust -f "$LOCUST_FILE" \
        --headless \
        --host "$API_URL" \
        -u "$users" \
        -r "$spawn_rate" \
        -t "$duration" \
        --csv="$REPORT_DIR/load_${name}_${TIMESTAMP}" \
        --html="$REPORT_DIR/load_${name}_${TIMESTAMP}.html" \
        --logfile="$REPORT_DIR/load_${name}_${TIMESTAMP}.log" \
        2>&1 | tee "$REPORT_DIR/load_${name}_${TIMESTAMP}_console.txt"

    echo "  Reports: $REPORT_DIR/load_${name}_${TIMESTAMP}*"
}

# Baseline: 10 users, ramp 2/s, 60s
run_scenario "baseline" 10 2 "60s"

# Stress: 100 users, ramp 10/s, 120s
run_scenario "stress" 100 10 "120s"

# Spike: 500 users, ramp 50/s, 30s (burst)
run_scenario "spike" 500 50 "30s"

echo ""
echo "================================================================"
echo "  ALL LOAD TESTS COMPLETE"
echo "  Reports in: $REPORT_DIR/load_*"
echo "================================================================"
