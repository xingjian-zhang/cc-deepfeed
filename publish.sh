#!/bin/bash
# Publish feeds/ to gh-pages branch for GitHub Pages serving.
# Uses a throwaway clone — never touches the main working tree.
# Usage: bash publish.sh [base-url]

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
FEEDS_DIR="$PROJECT_DIR/feeds"
PYTHON="${PYTHON:-python3}"

# --- Phase 1: Early exit if nothing to publish ---
shopt -s nullglob
xml_files=("$FEEDS_DIR"/*.xml)
shopt -u nullglob

if [ ${#xml_files[@]} -eq 0 ]; then
    echo "No feed XML files found in feeds/. Nothing to publish."
    exit 0
fi

# --- Phase 2: Generate index files if base URL provided ---
BASE_URL="${1:-}"
if [ -n "$BASE_URL" ]; then
    "$PYTHON" "$PROJECT_DIR/feed.py" index-html --base-url "$BASE_URL"
    "$PYTHON" "$PROJECT_DIR/feed.py" opml --base-url "$BASE_URL"
fi

# --- Phase 3: Acquire lock (portable mkdir-based) ---
LOCKDIR="$PROJECT_DIR/.publish.lock"
if ! mkdir "$LOCKDIR" 2>/dev/null; then
    echo "Another publish.sh is already running. Skipping."
    exit 0
fi

# --- Phase 4: Setup cleanup trap and create throwaway clone ---
WORK_DIR=$(mktemp -d)

cleanup() {
    rm -rf "${WORK_DIR:-}" "${LOCKDIR:-}"
}
trap cleanup EXIT

REMOTE_URL=$(git -C "$PROJECT_DIR" remote get-url origin)
CLONE_DIR="$WORK_DIR/repo"

if git ls-remote --exit-code --heads "$REMOTE_URL" gh-pages >/dev/null 2>&1; then
    git clone --depth 1 --single-branch --branch gh-pages "$REMOTE_URL" "$CLONE_DIR"
else
    echo "gh-pages branch not found on remote. Creating it."
    git init "$CLONE_DIR"
    git -C "$CLONE_DIR" remote add origin "$REMOTE_URL"
    git -C "$CLONE_DIR" checkout --orphan gh-pages
fi

# --- Phase 5: Wipe clone and sync feeds content ---
find "$CLONE_DIR" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +

cp "${xml_files[@]}" "$CLONE_DIR/"

shopt -s nullglob
png_files=("$FEEDS_DIR"/*.png)
shopt -u nullglob
if [ ${#png_files[@]} -gt 0 ]; then
    cp "${png_files[@]}" "$CLONE_DIR/"
fi

[ -f "$FEEDS_DIR/index.html" ] && cp "$FEEDS_DIR/index.html" "$CLONE_DIR/"
[ -f "$FEEDS_DIR/index.opml" ] && cp "$FEEDS_DIR/index.opml" "$CLONE_DIR/"

# --- Phase 6: Commit and push ---
git -C "$CLONE_DIR" add -A

if git -C "$CLONE_DIR" diff --cached --quiet; then
    echo "No changes to publish."
else
    git -C "$CLONE_DIR" commit -m "Update feeds $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    git -C "$CLONE_DIR" push origin gh-pages
    echo "Published feeds to gh-pages."
fi

# --- Phase 7: Ping WebSub hub if configured ---
WEBSUB_HUB=$("$PYTHON" -c "
import yaml
with open('$PROJECT_DIR/config.yaml') as f:
    print(yaml.safe_load(f).get('settings',{}).get('websub_hub',''))
" 2>/dev/null) || true

if [ -n "${WEBSUB_HUB:-}" ] && [ -n "${BASE_URL:-}" ]; then
    for xml in "${xml_files[@]}"; do
        filename=$(basename "$xml")
        FEED_URL="${BASE_URL%/}/${filename}"
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$WEBSUB_HUB" \
            -d "hub.mode=publish&hub.url=${FEED_URL}") || true
        if [ "${HTTP_CODE:-0}" -ge 200 ] && [ "${HTTP_CODE:-0}" -lt 300 ]; then
            echo "Pinged WebSub hub for ${filename} (${HTTP_CODE})."
        else
            echo "WARNING: WebSub ping failed for ${filename} (HTTP ${HTTP_CODE:-unknown})." >&2
        fi
    done
fi
