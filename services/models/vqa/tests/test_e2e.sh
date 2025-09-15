#!/bin/bash

# VQA Model Component Tests (E2E over HTTP)
# Mirrors the style used by distilbert component tests.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

# Source common test utilities
source "$PROJECT_ROOT/tests/utils/test_utils.sh"

# Configuration
TEST_BASE_URL="${TEST_BASE_URL:-http://localhost:8092}"
COMPONENT_NAME="VQA Model"

echo "$COMPONENT_NAME Test Suite"
echo "===================="
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
# 1x1 transparent PNG (data URI trimmed by backend). Small and self-contained.
BASE64_IMG="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGMAAQAABQABDQottQAAAABJRU5ErkJggg=="
test_endpoint "Predict with imageBase64" "POST" "/predict" '{"imageBase64":"'"$BASE64_IMG"'","question":"What is in the image?"}' "200"

# 3) PREDICT - VALIDATION ERRORS
print_test_section "PREDICT (VALIDATION ERRORS)"
test_endpoint "Empty question (whitespace)" "POST" "/predict" '{"imageBase64":"'"$BASE64_IMG"'","question":"   "}' "422"
test_endpoint "Missing image fields" "POST" "/predict" '{"question":"Is there a cat?"}' "422"

# 4) PREDICT - MAX TOKENS (approximate)
# Use long repeated words to exceed typical max limit. Only execute if MAX_INPUT_TOKENS is set explicitly.
if [ -n "$MAX_INPUT_TOKENS" ]; then
  long_text=""
  for i in $(seq 1 $((MAX_INPUT_TOKENS+10))); do long_text+="word "; done
  payload='{"imageBase64":"'"$BASE64_IMG"'","question":"'"$long_text"'"}'
  test_endpoint "Too long question (> MAX_INPUT_TOKENS)" "POST" "/predict" "$payload" "422"
fi

# Print final results
if print_test_results "$COMPONENT_NAME"; then
  exit 0
else
  exit 1
fi
