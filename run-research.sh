#!/bin/bash
# Deterministic research orchestrator.
# Spawns one claude worker per topic, checks targets, retries shortfalls.
# No LLM judgment in orchestration — every topic gets a worker, every time.

set -euo pipefail
cd "$(dirname "$0")"

# --- Config ---
CLAUDE_BIN="${CLAUDE_BIN:-claude}"
PYTHON="${PYTHON:-python3}"
WORKER_TIMEOUT="${WORKER_TIMEOUT:-900}"   # 15 min per worker
TIMEOUT_BIN="${TIMEOUT_BIN:-timeout}"

# --- Log rotation ---
mkdir -p .logs
LOG_FILE=".logs/research-$(date +%Y-%m-%d).log"
exec >> "$LOG_FILE" 2>&1

# Clean up logs older than 7 days
find .logs -name "research-*.log" -mtime +7 -delete 2>/dev/null || true
find .logs -name "*_round*.log" -mtime +7 -delete 2>/dev/null || true
find .logs -name "*_retry*.log" -mtime +7 -delete 2>/dev/null || true

# --- Guaranteed publish on exit ---
PUBLISHED=0
cleanup_publish() {
    if [ "$PUBLISHED" -eq 0 ]; then
        echo ""
        echo "--- Emergency publish (orchestration did not complete normally) ---"
        $PYTHON feed.py prune --keep 50 || true
        local base_url
        base_url=$($PYTHON -c "
import yaml
with open('config.yaml') as f:
    print(yaml.safe_load(f).get('settings',{}).get('base_url',''))
" 2>/dev/null || true)
        if [ -n "$base_url" ]; then
            bash publish.sh "$base_url" || true
        fi
    fi
}
trap cleanup_publish EXIT

# Parse topics from config.yaml: topic_id|target|model
TOPICS=$($PYTHON -c "
import yaml
with open('config.yaml') as f:
    config = yaml.safe_load(f)
for t in config.get('topics', []):
    model = t.get('model', 'opus')
    print(f\"{t['id']}|{t.get('target',0)}|{model}\")
")

# Init all feed XMLs
$PYTHON feed.py init

# Generate run ID
RUN_ID=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "=== Research cycle: $RUN_ID ==="
echo ""

spawn_workers() {
    local round_name="$1"
    shift
    local topics_to_run=("$@")

    local pids=()
    local topic_ids=()
    for line in "${topics_to_run[@]}"; do
        IFS='|' read -r topic_id target_or_gap model extra_prompt <<< "$line"
        echo "  [$round_name] $topic_id (target: $target_or_gap, model: $model)"

        # Pre-fetch recently covered subjects so the worker sees them in the prompt
        local covered
        covered=$($PYTHON feed.py state "$topic_id" 2>/dev/null | sed -n '/^=== RECENTLY COVERED/,/^===/p' || true)

        local prompt="@research-worker Process topic '$topic_id' with run-id '$RUN_ID'. Your target is $target_or_gap entries."
        if [ -n "$covered" ]; then
            prompt="$prompt

$covered
Do NOT write entries about subjects listed above unless you have genuinely new facts."
        fi
        if [ -n "$extra_prompt" ]; then
            prompt="$prompt $extra_prompt"
        fi

        "$TIMEOUT_BIN" --kill-after=30 "$WORKER_TIMEOUT" \
            "$CLAUDE_BIN" --model "$model" -p "$prompt" \
            --allowedTools "WebSearch,WebFetch,Bash,Read,Grep,Glob" \
            --permission-mode dontAsk \
            > ".logs/${topic_id}_${round_name}.log" 2>&1 &
        pids+=($!)
        topic_ids+=("$topic_id")
    done

    echo "  Waiting for ${#pids[@]} workers (timeout: ${WORKER_TIMEOUT}s)..."
    local failed=()
    local i=0
    for pid in "${pids[@]}"; do
        local exit_code=0
        wait "$pid" || exit_code=$?
        local tid="${topic_ids[$i]}"
        if [ "$exit_code" -eq 124 ] || [ "$exit_code" -eq 137 ]; then
            echo "  TIMEOUT: $tid (killed after ${WORKER_TIMEOUT}s)"
            failed+=("$tid:timeout")
        elif [ "$exit_code" -ne 0 ]; then
            echo "  FAILED: $tid (exit code $exit_code)"
            failed+=("$tid:exit-$exit_code")
        else
            echo "  OK: $tid"
        fi
        i=$((i + 1))
    done
    if [ ${#failed[@]} -gt 0 ]; then
        echo "  [$round_name] Failures: ${failed[*]}"
    fi
    echo "  [$round_name] Done."
    echo ""
}

# === Round 1: All topics ===
echo "--- Round 1: Spawning all workers ---"
round1_topics=()
while IFS= read -r line; do
    round1_topics+=("${line}|")  # empty extra_prompt
done <<< "$TOPICS"

spawn_workers "round1" "${round1_topics[@]}"

# === Check targets ===
echo "--- Checking targets ---"
CHECK_OUTPUT=$($PYTHON feed.py check-targets --run-id "$RUN_ID" 2>&1) || true
echo "$CHECK_OUTPUT"
echo ""

if echo "$CHECK_OUTPUT" | grep -q "__SHORTFALLS_JSON__"; then
    # Parse shortfalls
    SHORTFALLS_JSON=$(echo "$CHECK_OUTPUT" | grep "__SHORTFALLS_JSON__" | sed 's/.*__SHORTFALLS_JSON__://')

    RETRY_LINES=$($PYTHON -c "
import json, yaml, sys
shortfalls = json.loads(sys.argv[1])
with open('config.yaml') as f:
    config = yaml.safe_load(f)
topic_map = {t['id']: t for t in config.get('topics', [])}
for s in shortfalls:
    t = topic_map.get(s['topic_id'], {})
    model = t.get('model', 'opus')
    extra = f\"Previous round produced {s['added']}/{s['target']}. Try to produce {s['gap']} more entries by searching different sub-topics and broadening scope. Do NOT re-cover subjects already in state — check the RECENTLY COVERED list. If you cannot find genuinely new subjects after thorough searching, producing fewer is OK.\"
    print(f\"{s['topic_id']}|{s['gap']}|{model}|{extra}\")
" "$SHORTFALLS_JSON")

    # === Round 2: Retry shortfalls ===
    echo "--- Round 2: Retrying shortfall topics ---"
    retry_topics=()
    while IFS= read -r line; do
        retry_topics+=("$line")
    done <<< "$RETRY_LINES"

    spawn_workers "retry" "${retry_topics[@]}"

    # Final check (informational)
    echo "--- Final target check ---"
    $PYTHON feed.py check-targets --run-id "$RUN_ID" 2>&1 || true
    echo ""
else
    echo "All targets met on first round!"
fi

# === Prune and publish ===
echo "--- Pruning and publishing ---"
$PYTHON feed.py prune --keep 50
BASE_URL=$($PYTHON -c "
import yaml
with open('config.yaml') as f:
    print(yaml.safe_load(f).get('settings',{}).get('base_url',''))
")
bash publish.sh "$BASE_URL"
PUBLISHED=1
echo ""
echo "=== Done ==="
