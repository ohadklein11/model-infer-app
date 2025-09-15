#!/bin/bash

set -e

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "🧪 Running unit/integration tests (pytest)"
echo "======================================="
(cd "$BASE_DIR/services/job-api" && uv run pytest -q)
echo
(cd "$BASE_DIR/services/models/distilbert" && uv run pytest -q)
(cd "$BASE_DIR/services/models/vqa" && uv run pytest -q)

echo
echo "🧪 Running end-to-end component tests (bash)"
echo "=========================================="
bash "$BASE_DIR/tests/run_e2e_tests.sh"
