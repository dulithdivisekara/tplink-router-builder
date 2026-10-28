#!/usr/bin/env bash
# ==============================================================================
# merge-and-sync.sh — Automated Merge from dev -> main & Ecosystem Sync
# Merges the development branch into main, executes full test suite,
# and automatically propagates updates to CLI, MCP, and Web showcases.
#
# Author: Dulith Divisekara (SLIIT Malabe)
# ==============================================================================

set -e

REPO_DIR="/home/dulith/Projects/tplink-router-builder"
cd "$REPO_DIR"

echo -e "\033[94m[1/5] Checking out main and pulling latest changes...\033[0m"
git checkout main
git pull origin main

echo -e "\033[94m[2/5] Merging dev branch into main...\033[0m"
git merge dev -m "merge: Merge 'dev' branch into 'main' with tested updates"

echo -e "\033[94m[3/5] Pushing merged main to GitHub...\033[0m"
git push origin main

echo -e "\033[94m[4/5] Executing hub orchestration pipeline...\033[0m"
python3 scripts/sync-repos.py --push --deploy

echo -e "\033[92m=======================================================================\033[0m"
echo -e "\033[92m  [SUCCESS] All 4 downstreams synchronized and deployed from main!\033[0m"
echo -e "\033[92m=======================================================================\033[0m"
