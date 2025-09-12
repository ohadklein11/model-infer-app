#!/bin/bash

# Job API Component Tests
# This script contains only the actual tests for the Job API component.
# Service orchestration is handled by the main test runner.

set -e

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Source common test utilities
source "$PROJECT_ROOT/tests/utils/test_utils.sh"

# Configuration
TEST_BASE_URL="${TEST_BASE_URL:-http://localhost:8080}"
COMPONENT_NAME="Job API"

echo "$COMPONENT_NAME Test Suite"
echo "=========================="
echo "Base URL: $TEST_BASE_URL"
echo ""

# Validate test environment
if ! validate_test_environment "$TEST_BASE_URL"; then
    exit 1
fi

# Wait for service to be ready (only if not skipping service management)
if [ "$TEST_SKIP_SERVICE_MANAGEMENT" != "true" ]; then
    if ! wait_for_service "$TEST_BASE_URL/health" 30 "$COMPONENT_NAME"; then
        exit 1
    fi
fi

# 1. HEALTH CHECK
print_test_section "HEALTH CHECK"
test_endpoint "Health check" "GET" "/health" "" "200"

# 2. LIST MODELS
print_test_section "LIST MODELS"
test_endpoint "List available models" "GET" "/models" "" "200"

# 3. VALID JOB CREATION TESTS
print_test_section "VALID JOB CREATION"

test_endpoint "Create valid job with username" "POST" "/jobs" \
    '{"jobName": "sentiment-analysis", "username": "alice", "modelId": "distilbert-base-uncased-finetuned-sst-2-english", "input": {"text": "I love this!"}}' \
    "200"

test_endpoint "Create valid job without username" "POST" "/jobs" \
    '{"jobName": "text-classification", "modelId": "distilbert-base-uncased-finetuned-sst-2-english", "input": {"text": "This is great!"}}' \
    "200"

test_endpoint "Create job with non-dict input" "POST" "/jobs" \
    '{"jobName": "simple-test", "modelId": "distilbert-base-uncased-finetuned-sst-2-english", "input": "simple text input"}' \
    "200"

# Store a job ID for later tests
print_test_section "SETUP FOR RETRIEVAL TESTS"
echo "Creating job to get ID for later tests..."
job_response=$(make_request "POST" "/jobs" \
    '{"jobName": "test-job", "modelId": "distilbert-base-uncased-finetuned-sst-2-english", "input": {"text": "test"}}')

job_id=$(extract_json_field "$job_response" "id")
echo "Created job with ID: $job_id"

# 4. VALIDATION ERROR TESTS (422)
print_test_section "VALIDATION ERRORS (422)"

test_endpoint "Missing required field (jobName)" "POST" "/jobs" \
    '{"username": "alice", "modelId": "distilbert-base-uncased-finetuned-sst-2-english", "input": {"text": "hello"}}' \
    "422"

test_endpoint "Missing required field (modelId)" "POST" "/jobs" \
    '{"jobName": "test", "input": {"text": "hello"}}' \
    "422"

test_endpoint "Missing required field (input)" "POST" "/jobs" \
    '{"jobName": "test", "modelId": "distilbert-base-uncased-finetuned-sst-2-english"}' \
    "422"

test_endpoint "Invalid model ID" "POST" "/jobs" \
    '{"jobName": "test", "modelId": "invalid-model", "input": {"text": "hello"}}' \
    "422"

test_endpoint "Empty input" "POST" "/jobs" \
    '{"jobName": "test", "modelId": "distilbert-base-uncased-finetuned-sst-2-english", "input": null}' \
    "422"

test_endpoint "Empty jobName (whitespace)" "POST" "/jobs" \
    '{"jobName": "   ", "modelId": "distilbert-base-uncased-finetuned-sst-2-english", "input": {"text": "hello"}}' \
    "422"

test_endpoint "Empty username (whitespace)" "POST" "/jobs" \
    '{"jobName": "test", "username": "   ", "modelId": "distilbert-base-uncased-finetuned-sst-2-english", "input": {"text": "hello"}}' \
    "422"

test_endpoint "JobName too long" "POST" "/jobs" \
    '{"jobName": "this-is-a-very-long-job-name-that-exceeds-the-maximum-allowed-length-of-100-characters-and-should-fail", "modelId": "distilbert-base-uncased-finetuned-sst-2-english", "input": {"text": "hello"}}' \
    "422"

test_endpoint "Wrong data type for jobName" "POST" "/jobs" \
    '{"jobName": 123, "modelId": "distilbert-base-uncased-finetuned-sst-2-english", "input": {"text": "hello"}}' \
    "422"

# 5. JOB RETRIEVAL TESTS
print_test_section "JOB RETRIEVAL"

if [ -n "$job_id" ]; then
    test_endpoint "Get existing job" "GET" "/jobs/$job_id" "" "200"
else
    echo -e "${RED}Skipping job retrieval test - no job ID available${NC}"
fi

test_endpoint "Get non-existent job (404)" "GET" "/jobs/nonexistent-job-id" "" "404"

test_endpoint "Get job with invalid UUID format" "GET" "/jobs/invalid-uuid" "" "404"

# 6. LIST JOBS TESTS
print_test_section "LIST JOBS"

test_endpoint "List all jobs" "GET" "/jobs" "" "200"

test_endpoint "List jobs with username filter" "GET" "/jobs?username=alice" "" "200"

test_endpoint "List jobs with jobName filter" "GET" "/jobs?jobName=sentiment-analysis" "" "200"

test_endpoint "List jobs with status filter" "GET" "/jobs?status=queued" "" "200"

test_endpoint "List jobs with text search" "GET" "/jobs?q=test" "" "200"

test_endpoint "List jobs with pagination" "GET" "/jobs?page=1&pageSize=10" "" "200"

test_endpoint "List jobs with invalid status enum" "GET" "/jobs?status=invalid-status" "" "422"

test_endpoint "List jobs with invalid page (0)" "GET" "/jobs?page=0" "" "422"

test_endpoint "List jobs with invalid pageSize (0)" "GET" "/jobs?pageSize=0" "" "422"

test_endpoint "List jobs with pageSize too large" "GET" "/jobs?pageSize=101" "" "422"

# 7. RESPONSE VALIDATION TESTS
print_test_section "RESPONSE VALIDATION"

echo "Testing response structure for created job..."
response=$(make_request "POST" "/jobs" \
    '{"jobName": "response-test", "modelId": "distilbert-base-uncased-finetuned-sst-2-english", "input": {"text": "test"}}')

# Check if response contains required fields
check_field "$response" "id" '"id"'
check_field "$response" "jobName" '"jobName"'
check_field "$response" "modelId" '"modelId"'
check_field "$response" "status" '"status"'
check_field "$response" "createdAt" '"createdAt"'
check_field "$response" "updatedAt" '"updatedAt"'

# Check status value
TOTAL_TESTS=$((TOTAL_TESTS + 1))
if echo "$response" | grep -q '"status":"queued"'; then
    echo -e "${GREEN}✓${NC} Status is queued"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo -e "${RED}✗${NC} Status is not queued"
    echo "  Response: $response"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

# Print final results and exit with appropriate code
if print_test_results "$COMPONENT_NAME"; then
    exit 0
else
    exit 1
fi
