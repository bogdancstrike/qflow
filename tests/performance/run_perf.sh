#!/bin/bash

# Configuration
TOTAL_TASKS=10000
BATCH_SIZE=200
API_URL="http://localhost:3001/api/v1/tasks"

echo "Starting performance test: Submitting $TOTAL_TASKS tasks in batches of $BATCH_SIZE..."

# Function to submit a single task with randomized combinations
submit_task() {
    local i=$1
    local mod=$((i % 3))
    local payload=""

    case $mod in
        0)
            # Text input
            payload="{\"input_data\":{\"text\":\"Performance test task number $i\"},\"outputs\":[\"ner_result\",\"summary\"]}"
            ;;
        1)
            # YouTube URL
            payload="{\"input_data\":{\"url\":\"https://www.youtube.com/watch?v=perf_$i\"},\"outputs\":[\"sentiment_result\",\"keywords\"]}"
            ;;
        2)
            # Audio path
            payload="{\"input_data\":{\"file_path\":\"/tmp/perf_test_$i.mp3\"},\"outputs\":[\"lang_meta\",\"text_en\",\"iptc_tags\"]}"
            ;;
    esac

    curl -s -X POST "$API_URL" \
        -H "Content-Type: application/json" \
        -d "$payload" > /dev/null
}

export -f submit_task
export API_URL

# Using GNU Parallel to submit tasks in parallel batches
seq 1 $TOTAL_TASKS | parallel -j $BATCH_SIZE submit_task

echo "Done! Submitted $TOTAL_TASKS tasks."
