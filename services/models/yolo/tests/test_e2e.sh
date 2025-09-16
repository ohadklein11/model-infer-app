#!/bin/bash

# YOLO Model Component Tests (E2E over HTTP)
# Mirrors the style used by distilbert and vqa component tests.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

# Source common test utilities
source "$PROJECT_ROOT/tests/utils/test_utils.sh"

# Configuration
TEST_BASE_URL="${TEST_BASE_URL:-http://localhost:8093}"
COMPONENT_NAME="YOLO Model"

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

# 2) PREDICT - VALID (imageBase64)
print_test_section "PREDICT (VALID)"
# 1x1 transparent PNG
BASE64_IMG="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGMAAQAABQABDQottQAAAABJRU5ErkJggg=="
test_endpoint "Predict with imageBase64" "POST" "/predict" '{"imageBase64":"'"$BASE64_IMG"'"}' "200"

# 3) PREDICT - VALIDATION ERRORS
print_test_section "PREDICT (VALIDATION ERRORS)"
test_endpoint "Missing image fields" "POST" "/predict" '{}' "422"

# 4) PREDICT - RENDERED OUTPUT
print_test_section "PREDICT (RENDER)"
test_endpoint "Predict with render=true" "POST" "/predict?render=true" '{"imageBase64":"'"$BASE64_IMG"'"}' "200"

# Print final results
if print_test_results "$COMPONENT_NAME"; then
  exit 0
else
  exit 1
fi
