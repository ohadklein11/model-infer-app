#!/bin/bash

# DistilBERT Model Component Tests (E2E over HTTP)
# Mirrors the style used by job-api component tests.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

# Source common test utilities
source "$PROJECT_ROOT/tests/utils/test_utils.sh"

# Configuration
TEST_BASE_URL="${TEST_BASE_URL:-http://localhost:8091}"
COMPONENT_NAME="DistilBERT Model"

echo "$COMPONENT_NAME Test Suite"
echo "=========================="
echo "Base URL: $TEST_BASE_URL"
echo ""

# Validate environment
if ! validate_test_environment "$TEST_BASE_URL"; then
    exit 1
fi

# Wait for service unless orchestrated by outer runner
if [ "$TEST_SKIP_SERVICE_MANAGEMENT" != "true" ]; then
    if ! wait_for_service "$TEST_BASE_URL/health" 60 "$COMPONENT_NAME"; then
        exit 1
    fi
fi

# 1) HEALTH CHECK
print_test_section "HEALTH CHECK"
test_endpoint "Health check" "GET" "/health" "" "200"

# 2) PREDICT - VALID
print_test_section "PREDICT (VALID)"
test_endpoint "Predict positive text" "POST" "/predict" '{"text":"I love this product"}' "200"

# 3) PREDICT - VALIDATION ERRORS
print_test_section "PREDICT (VALIDATION ERRORS)"
test_endpoint "Empty text (whitespace)" "POST" "/predict" '{"text":"   "}' "422"

# 4) PREDICT - MAX TOKENS (approximate)
# Use long repeated words to exceed typical max limit (defaults to 512). We can't
# know runtime limit here, so only execute if MAX_INPUT_TOKENS is set explicitly.
if [ -n "$MAX_INPUT_TOKENS" ]; then
  long_text=""
  for i in $(seq 1 $((MAX_INPUT_TOKENS+10))); do long_text+="word "; done
  test_endpoint "Too long text (> MAX_INPUT_TOKENS)" "POST" "/predict" "{\"text\":\"$long_text\"}" "422"
fi

# Print final results
if print_test_results "$COMPONENT_NAME"; then
  exit 0
else
  exit 1
fi
