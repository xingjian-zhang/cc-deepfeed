#!/bin/bash
# Deterministic research orchestrator.
# Spawns one claude worker per topic, checks targets, retries shortfalls.
# No LLM judgment in orchestration — every topic gets a worker, every time.

set -euo pipefail
cd "$(dirname "$0")"

CLAUDE_BIN="${CLAUDE_BIN:-claude}"

# Parse topics from config.yaml: topic_id|target|model
TOPICS=$(python3 -c "
import yaml
with open('config.yaml') as f:
    config = yaml.safe_load(f)
for t in config.get('topics', []):
    model = t.get('model', 'opus')
    print(f\"{t['id']}|{t.get('target',0)}|{model}\")
")

# Init all feed XMLs
python3 feed.py init

# Generate run ID
RUN_ID=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "=== Research cycle: $RUN_ID ==="
echo ""

# Ensure log dirs exist
mkdir -p .logs

spawn_workers() {
    local round_name="$1"
    shift
    local topics_to_run=("$@")

    local pids=()
    for line in "${topics_to_run[@]}"; do
        IFS='|' read -r topic_id target_or_gap model extra_prompt <<< "$line"
        echo "  [$round_name] $topic_id (target: $target_or_gap, model: $model)"

        local prompt="@research-worker Process topic '$topic_id' with run-id '$RUN_ID'. Your target is $target_or_gap entries."
        if [ -n "$extra_prompt" ]; then
            prompt="$prompt $extra_prompt"
        fi

        "$CLAUDE_BIN" --model "$model" -p "$prompt" \
            --allowedTools "WebSearch,WebFetch,Bash,Read,Grep,Glob" \
            > ".logs/${topic_id}_${round_name}.log" 2>&1 &
        pids+=($!)
    done

    echo "  Waiting for ${#pids[@]} workers..."
    for pid in "${pids[@]}"; do
        wait "$pid" || true
    done
    echo "  [$round_name] All workers complete."
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
CHECK_OUTPUT=$(python3 feed.py check-targets --run-id "$RUN_ID" 2>&1) || true
echo "$CHECK_OUTPUT"
echo ""

if echo "$CHECK_OUTPUT" | grep -q "__SHORTFALLS_JSON__"; then
    # Parse shortfalls
    SHORTFALLS_JSON=$(echo "$CHECK_OUTPUT" | grep "__SHORTFALLS_JSON__" | sed 's/.*__SHORTFALLS_JSON__://')

    RETRY_LINES=$(python3 -c "
import json, yaml, sys
shortfalls = json.loads(sys.argv[1])
with open('config.yaml') as f:
    config = yaml.safe_load(f)
topic_map = {t['id']: t for t in config.get('topics', [])}
for s in shortfalls:
    t = topic_map.get(s['topic_id'], {})
    model = t.get('model', 'opus')
    extra = f\"Previous round only got {s['added']}/{s['target']}. You MUST produce at least {s['gap']} more entries. Search HARDER — different angles, broader sub-topics, go back 2 weeks, evergreen content.\"
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
    python3 feed.py check-targets --run-id "$RUN_ID" 2>&1 || true
    echo ""
else
    echo "All targets met on first round!"
fi

# === Prune and publish ===
echo "--- Pruning and publishing ---"
python3 feed.py prune --keep 50
bash publish.sh "https://xingjianz.com/rss-research"
echo ""
echo "=== Done ==="
