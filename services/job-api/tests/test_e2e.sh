#!/bin/bash

# Job API Component Tests
# This script contains only the actual tests for the Job API component.
# Service orchestration is handled by the main test runner.

set -e

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Source common test utilities
source "$PROJECT_ROOT/tests/utils/test_utils.sh"

# Configuration
TEST_BASE_URL="${TEST_BASE_URL:-http://localhost:8080}"
COMPONENT_NAME="Job API"

echo "$COMPONENT_NAME Test Suite"
echo "=========================="
echo "Base URL: $TEST_BASE_URL"
echo ""

# Helper: create job, assert 200, store id in provided var; updates counters
create_job_and_store_id() {
    local -n __out_id_var=$1
    local test_name="$2"
    local payload="$3"
    local response=$(curl -s -w "\n%{http_code}" -X POST "${TEST_BASE_URL}/jobs" \
        -H "Content-Type: application/json" \
        -d "$payload" || true)

    local status_code=$(echo "$response" | tail -n1)
    local response_body=$(echo "$response" | head -n -1)

    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if [ "$status_code" = "200" ]; then
        echo -e "${GREEN}✓${NC} ${test_name}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo -e "${RED}✗${NC} ${test_name}"
        echo "  Expected: 200, Got: $status_code"
        echo "  Request: POST /jobs"
        echo "  Data: $payload"
        if [ -n "$response_body" ] && [ "$response_body" != "" ]; then
            echo "  Response: $response_body"
        fi
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi

    __out_id_var=$(extract_json_field "$response_body" "id")
}

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

first_job_id=""
second_job_id=""
third_job_id=""

create_job_and_store_id first_job_id \
    "Create valid job with username" \
    '{"jobName": "sentiment-analysis", "username": "alice", "modelId": "distilbert-base-uncased-finetuned-sst-2-english", "input": {"text": "I love this!"}}'

create_job_and_store_id second_job_id \
    "Create valid job without username" \
    '{"jobName": "text-classification", "modelId": "distilbert-base-uncased-finetuned-sst-2-english", "input": {"text": "This is great!"}}'

create_job_and_store_id third_job_id \
    "Create job with non-dict input" \
    '{"jobName": "simple-test", "modelId": "distilbert-base-uncased-finetuned-sst-2-english", "input": "simple text input"}'

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

# Clean up the job created for retrieval tests
cleanup_test_jobs "$job_id"

# 6. LIST JOBS TESTS
print_test_section "LIST JOBS"

test_endpoint "List all jobs" "GET" "/jobs" "" "200"

test_endpoint "List jobs with username filter" "GET" "/jobs?username=alice" "" "200"

test_endpoint "List jobs with jobName filter" "GET" "/jobs?jobName=sentiment-analysis" "" "200"

test_endpoint "List jobs with status filter" "GET" "/jobs?status=queued" "" "200"

# Removed: free-text 'q' search was deprecated for predictability and index usage
# test_endpoint "List jobs with text search" "GET" "/jobs?q=test" "" "200"

test_endpoint "List jobs with pagination" "GET" "/jobs?page=1&pageSize=10" "" "200"

test_endpoint "List jobs with invalid status enum" "GET" "/jobs?status=invalid-status" "" "422"

test_endpoint "List jobs with invalid page (0)" "GET" "/jobs?page=0" "" "422"

test_endpoint "List jobs with invalid pageSize (0)" "GET" "/jobs?pageSize=0" "" "422"

test_endpoint "List jobs with pageSize too large" "GET" "/jobs?pageSize=101" "" "422"

# 6.5. COMPREHENSIVE PAGINATION & FILTERING TESTS
print_test_section "PAGINATION & FILTERING COMPREHENSIVE TESTS"

# Create unique test jobs for this test run
TEST_RUN_ID=$(date +%s%N | cut -c1-13)  # Unique timestamp

job1_response=$(make_request "POST" "/jobs" \
    '{"jobName": "test-demo-1-'$TEST_RUN_ID'", "username": "test-alice-'$TEST_RUN_ID'", "modelId": "distilbert-base-uncased-finetuned-sst-2-english", "input": {"text": "alice job 1"}}')
job1_id=$(extract_json_field "$job1_response" "id")

job2_response=$(make_request "POST" "/jobs" \
    '{"jobName": "test-demo-2-'$TEST_RUN_ID'", "username": "test-bob-'$TEST_RUN_ID'", "modelId": "distilbert-base-uncased-finetuned-sst-2-english", "input": {"text": "bob job 2"}}')
job2_id=$(extract_json_field "$job2_response" "id")

job3_response=$(make_request "POST" "/jobs" \
    '{"jobName": "test-analysis-'$TEST_RUN_ID'", "username": "test-alice-'$TEST_RUN_ID'", "modelId": "distilbert-base-uncased-finetuned-sst-2-english", "input": {"text": "alice analysis"}}')
job3_id=$(extract_json_field "$job3_response" "id")

job4_response=$(make_request "POST" "/jobs" \
    '{"jobName": "test-demo-3-'$TEST_RUN_ID'", "username": "test-charlie-'$TEST_RUN_ID'", "modelId": "distilbert-base-uncased-finetuned-sst-2-english", "input": {"text": "charlie job"}}')
job4_id=$(extract_json_field "$job4_response" "id")

job5_response=$(make_request "POST" "/jobs" \
    '{"jobName": "test-special-'$TEST_RUN_ID'", "username": "test-alice-'$TEST_RUN_ID'", "modelId": "distilbert-base-uncased-finetuned-sst-2-english", "input": {"text": "alice special"}}')
job5_id=$(extract_json_field "$job5_response" "id")

# Test default pagination behavior
all_jobs_response=$(make_request "GET" "/jobs" "")
total_jobs=$(extract_json_field "$all_jobs_response" "total")
default_limit=$(extract_json_field "$all_jobs_response" "limit")
default_offset=$(extract_json_field "$all_jobs_response" "offset")
default_hasMore=$(extract_json_field "$all_jobs_response" "hasMore")
default_jobs_count=$(echo "$all_jobs_response" | grep -o '"jobs":\[.*\]' | grep -o '"id":' | wc -l)

# Validate default pagination
TOTAL_TESTS=$((TOTAL_TESTS + 4))
if [ "$default_limit" -eq 20 ]; then
    echo -e "${GREEN}✓${NC} Default pagination limit=20"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo -e "${RED}✗${NC} Default pagination limit should be 20, got $default_limit"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

if [ "$default_offset" -eq 0 ]; then
    echo -e "${GREEN}✓${NC} Default pagination offset=0"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo -e "${RED}✗${NC} Default pagination offset should be 0, got $default_offset"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

if [ "$total_jobs" -gt 20 ]; then
    if [ "$default_jobs_count" -eq 20 ] && [ "$default_hasMore" = "true" ]; then
        echo -e "${GREEN}✓${NC} Default pagination limits to 20 jobs when total > 20"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo -e "${RED}✗${NC} Default pagination should return 20 jobs and hasMore=true when total > 20, got count=$default_jobs_count hasMore=$default_hasMore"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
else
    if [ "$default_jobs_count" -eq "$total_jobs" ] && [ "$default_hasMore" = "false" ]; then
        echo -e "${GREEN}✓${NC} Default pagination returns all jobs when total <= 20"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo -e "${RED}✗${NC} Default pagination should return all $total_jobs jobs and hasMore=false, got count=$default_jobs_count hasMore=$default_hasMore"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
fi

if [ "$total_jobs" -ge 5 ]; then
    echo -e "${GREEN}✓${NC} Test data created successfully ($total_jobs total jobs)"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo -e "${RED}✗${NC} Expected at least 5 jobs for testing, found $total_jobs"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

# Test explicit pagination
test_endpoint "Pagination with page/pageSize" "GET" "/jobs?page=1&pageSize=3" "" "200"
test_endpoint "Pagination with limit/offset" "GET" "/jobs?limit=3&offset=0" "" "200"

# Test filtering (validate counts)
alice_response=$(make_request "GET" "/jobs?username=test-alice-$TEST_RUN_ID" "")
alice_total=$(extract_json_field "$alice_response" "total")
alice_jobs_count=$(echo "$alice_response" | grep -o '"jobs":\[.*\]' | grep -o '"id":' | wc -l)

TOTAL_TESTS=$((TOTAL_TESTS + 1))
if [ "$alice_total" -eq 3 ] && [ "$alice_jobs_count" -eq 3 ]; then
    echo -e "${GREEN}✓${NC} Username filter returns 3 alice jobs"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo -e "${RED}✗${NC} Username filter should return 3 alice jobs, got total=$alice_total count=$alice_jobs_count"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

# Test filtering with pagination
alice_limited_response=$(make_request "GET" "/jobs?username=test-alice-$TEST_RUN_ID&limit=2&offset=0" "")
alice_limited_total=$(extract_json_field "$alice_limited_response" "total")
alice_limited_count=$(echo "$alice_limited_response" | grep -o '"jobs":\[.*\]' | grep -o '"id":' | wc -l)
alice_limited_hasMore=$(extract_json_field "$alice_limited_response" "hasMore")

TOTAL_TESTS=$((TOTAL_TESTS + 1))
if [ "$alice_limited_total" -eq 3 ] && [ "$alice_limited_count" -eq 2 ] && [ "$alice_limited_hasMore" = "true" ]; then
    echo -e "${GREEN}✓${NC} Filtering with pagination (alice limit=2)"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo -e "${RED}✗${NC} Filtering with pagination should show total=3, count=2, hasMore=true, got total=$alice_limited_total count=$alice_limited_count hasMore=$alice_limited_hasMore"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

# Test search functionality
# Removed: q-based search and pagination validations (deprecated)

# Test unlimited results (limit=-1)
unlimited_response=$(make_request "GET" "/jobs?limit=-1&offset=0" "")
unlimited_total=$(extract_json_field "$unlimited_response" "total")
unlimited_count=$(echo "$unlimited_response" | grep -o '"jobs":\[.*\]' | grep -o '"id":' | wc -l)
unlimited_hasMore=$(extract_json_field "$unlimited_response" "hasMore")

TOTAL_TESTS=$((TOTAL_TESTS + 1))
if [ "$unlimited_count" -eq "$unlimited_total" ] && [ "$unlimited_hasMore" = "false" ]; then
    echo -e "${GREEN}✓${NC} Unlimited results (limit=-1)"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo -e "${RED}✗${NC} Unlimited should return all jobs with hasMore=false, got count=$unlimited_count total=$unlimited_total hasMore=$unlimited_hasMore"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

# Test unlimited with filtering
alice_unlimited_response=$(make_request "GET" "/jobs?username=test-alice-$TEST_RUN_ID&limit=-1&offset=0" "")
alice_unlimited_total=$(extract_json_field "$alice_unlimited_response" "total")
alice_unlimited_count=$(echo "$alice_unlimited_response" | grep -o '"jobs":\[.*\]' | grep -o '"id":' | wc -l)

TOTAL_TESTS=$((TOTAL_TESTS + 1))
if [ "$alice_unlimited_total" -eq 3 ] && [ "$alice_unlimited_count" -eq 3 ]; then
    echo -e "${GREEN}✓${NC} Unlimited with filtering (alice)"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo -e "${RED}✗${NC} Unlimited alice filter should return 3 jobs, got total=$alice_unlimited_total count=$alice_unlimited_count"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

# Test unlimited with offset
test_endpoint "Unlimited with offset" "GET" "/jobs?limit=-1&offset=2" "" "200"

# Test edge cases
beyond_response=$(make_request "GET" "/jobs?limit=5&offset=1000" "")
beyond_count=$(echo "$beyond_response" | grep -o '"jobs":\[.*\]' | grep -o '"id":' | wc -l)
beyond_hasMore=$(extract_json_field "$beyond_response" "hasMore")

TOTAL_TESTS=$((TOTAL_TESTS + 1))
if [ "$beyond_count" -eq 0 ] && [ "$beyond_hasMore" = "false" ]; then
    echo -e "${GREEN}✓${NC} Pagination beyond available data"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo -e "${RED}✗${NC} Pagination beyond data should return 0 jobs and hasMore=false, got count=$beyond_count hasMore=$beyond_hasMore"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

test_endpoint "Mixed pagination approaches (should fail)" "GET" "/jobs?page=1&limit=5" "" "422"

# Clean up test jobs created for pagination tests
cleanup_test_jobs "$job1_id" "$job2_id" "$job3_id" "$job4_id" "$job5_id"

# 7. RESPONSE VALIDATION TESTS
print_test_section "RESPONSE VALIDATION"

echo "Testing response structure for created job..."
response=$(make_request "POST" "/jobs" \
    '{"jobName": "response-test", "modelId": "distilbert-base-uncased-finetuned-sst-2-english", "input": {"text": "test"}}')
response_test_job_id=$(extract_json_field "$response" "id")

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

# Clean up response validation test job
cleanup_test_jobs "$response_test_job_id"

# Cleanup any jobs created in the VALID JOB CREATION section
cleanup_test_jobs "$first_job_id" "$second_job_id" "$third_job_id"

# Print final results and exit with appropriate code
if print_test_results "$COMPONENT_NAME"; then
    exit 0
else
    exit 1
fi
