#!/bin/bash
# Publish feeds/ to gh-pages branch for GitHub Pages serving.
# Called after each research cycle.

set -e

FEEDS_DIR="$(cd "$(dirname "$0")" && pwd)/feeds"

if [ ! -d "$FEEDS_DIR" ] || [ -z "$(ls -A "$FEEDS_DIR"/*.xml 2>/dev/null)" ]; then
    echo "No feed XML files found in feeds/. Nothing to publish."
    exit 0
fi

# Create a temporary directory for the gh-pages content
TMPDIR=$(mktemp -d)
cp "$FEEDS_DIR"/*.xml "$TMPDIR/"

# Switch to gh-pages branch, update, switch back
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
git stash --include-untracked -q 2>/dev/null || true

# Create gh-pages branch if it doesn't exist
if ! git rev-parse --verify gh-pages >/dev/null 2>&1; then
    git checkout --orphan gh-pages
    git rm -rf . >/dev/null 2>&1 || true
else
    git checkout gh-pages
fi

# Copy feeds and commit
cp "$TMPDIR"/*.xml .
git add *.xml
if git diff --cached --quiet; then
    echo "No changes to publish."
else
    git commit -m "Update feeds $(date +%Y-%m-%d)"
    echo "Published feeds to gh-pages."
fi

# Return to original branch
git checkout "$CURRENT_BRANCH"
git stash pop -q 2>/dev/null || true
rm -rf "$TMPDIR"
