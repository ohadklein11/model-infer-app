#!/bin/bash

# API Testing Script for Job API
# Run this script to test all endpoints with both valid and invalid inputs
# This script will automatically start the service, run tests, and clean up

BASE_URL="http://localhost:8080"
MAKE_PID=""
CLEANUP_NEEDED=false

echo "Job API Test Suite"
echo "=================="
echo "Base URL: $BASE_URL"
echo "Service will be started automatically"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test result tracking
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Cleanup function
cleanup() {
    if [ "$CLEANUP_NEEDED" = true ]; then
        echo -e "\n${YELLOW}Stopping services with make down...${NC}"
        CLEANUP_NEEDED=false  # Prevent double cleanup

        # Kill the make process if it's still running
        if [ -n "$MAKE_PID" ]; then
            # First try SIGTERM (graceful)
            kill $MAKE_PID 2>/dev/null

            # Give it 3 seconds to terminate gracefully
            local count=0
            while [ $count -lt 3 ] && kill -0 $MAKE_PID 2>/dev/null; do
                sleep 1
                count=$((count + 1))
            done

            # If still running, force kill with SIGKILL
            if kill -0 $MAKE_PID 2>/dev/null; then
                kill -9 $MAKE_PID 2>/dev/null
            fi

            timeout 5 bash -c "wait $MAKE_PID" 2>/dev/null || true
        fi
        # Run make down in background with timeout to prevent hanging
        timeout 30 make down > /dev/null 2>&1 &
        MAKE_DOWN_PID=$!

        # Wait for make down to complete or timeout
        wait $MAKE_DOWN_PID 2>/dev/null

        echo -e "${GREEN}Services stopped and cleaned up.${NC}"
    fi
}

# Set up trap to ensure cleanup on exit
trap cleanup EXIT INT TERM

# Function to check if service is running
check_service() {
    curl -s "$BASE_URL/health" > /dev/null 2>&1
    return $?
}

# Function to start the service using Docker Compose
start_service() {
    echo -e "${YELLOW}Starting Job API service with Docker Compose...${NC}"

    # Check if we're in the right directory
    if [ ! -f "Makefile" ] || [ ! -f "docker-compose.dev.yml" ]; then
        echo -e "${RED}Error: Cannot find Makefile or docker-compose.dev.yml${NC}"
        echo "Please run this script from the model-infer-app root directory"
        exit 1
    fi

    # Check if make is available
    if ! command -v make &> /dev/null; then
        echo -e "${RED}Error: make command not found${NC}"
        echo "Please install make or use docker compose directly"
        exit 1
    fi

    # Check if docker is available
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}Error: docker command not found${NC}"
        echo "Please install Docker"
        exit 1
    fi

    # Start the service using make up
    echo "Running: make up"
    make up > /tmp/job-api-test.log 2>&1 &
    MAKE_PID=$!
    CLEANUP_NEEDED=true

    echo "Docker Compose started (PID: $MAKE_PID)"
    echo "Waiting for service to be ready..."

    # Wait for service to be ready (max 60 seconds for Docker build/start)
    local max_attempts=60
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if check_service; then
            echo -e "${GREEN}✓ Service is ready!${NC}"
            echo ""
            return 0
        fi

        echo -n "."
        sleep 1
        attempt=$((attempt + 1))
    done

    echo -e "\n${RED}✗ Service failed to start within 60 seconds${NC}"
    echo "Check the log file: /tmp/job-api-test.log"
    echo "Last few lines of the log:"
    tail -20 /tmp/job-api-test.log
    exit 1
}

# Check if service is already running
echo -e "${YELLOW}Checking if service is already running...${NC}"
if check_service; then
    echo -e "${GREEN}✓ Service is already running${NC}"
    echo -e "${YELLOW}Warning: Using existing service instance${NC}"
    echo ""
else
    start_service
fi


# Function to test an endpoint
test_endpoint() {
    local test_name="$1"
    local method="$2"
    local endpoint="$3"
    local data="$4"
    local expected_status="$5"

    # Make the request
    if [ -n "$data" ]; then
        response=$(curl -s -w "\n%{http_code}" -X "$method" "$BASE_URL$endpoint" \
            -H "Content-Type: application/json" \
            -d "$data")
    else
        response=$(curl -s -w "\n%{http_code}" -X "$method" "$BASE_URL$endpoint")
    fi

    # Split response and status code
    status_code=$(echo "$response" | tail -n1)
    response_body=$(echo "$response" | head -n -1)

    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    if [ "$status_code" = "$expected_status" ]; then
        echo -e "${GREEN}✓${NC} $test_name"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo -e "${RED}✗${NC} $test_name"
        echo "  Expected: $expected_status, Got: $status_code"
        echo "  Request: $method $endpoint"
        if [ -n "$data" ]; then
            echo "  Data: $data"
        fi
        if [ -n "$response_body" ] && [ "$response_body" != "" ]; then
            echo "  Response: $response_body"
        fi
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
}

# 1. HEALTH CHECK
echo -e "\n${YELLOW}=== HEALTH CHECK ===${NC}"
test_endpoint "Health check" "GET" "/health" "" "200"

# 2. LIST MODELS
echo -e "\n${YELLOW}=== LIST MODELS ===${NC}"
test_endpoint "List available models" "GET" "/models" "" "200"

# 3. VALID JOB CREATION TESTS
echo -e "\n${YELLOW}=== VALID JOB CREATION ===${NC}"

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
echo -e "\n${YELLOW}Creating job to get ID for later tests...${NC}"
job_response=$(curl -s -X POST "$BASE_URL/jobs" \
    -H "Content-Type: application/json" \
    -d '{"jobName": "test-job", "modelId": "distilbert-base-uncased-finetuned-sst-2-english", "input": {"text": "test"}}')

job_id=$(echo "$job_response" | grep -o '"id":"[^"]*"' | cut -d'"' -f4)
echo "Created job with ID: $job_id"

# 4. VALIDATION ERROR TESTS (422)
echo -e "\n${YELLOW}=== VALIDATION ERRORS (422) ===${NC}"

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
echo -e "\n${YELLOW}=== JOB RETRIEVAL ===${NC}"

if [ -n "$job_id" ]; then
    test_endpoint "Get existing job" "GET" "/jobs/$job_id" "" "200"
else
    echo -e "${RED}Skipping job retrieval test - no job ID available${NC}"
fi

test_endpoint "Get non-existent job (404)" "GET" "/jobs/nonexistent-job-id" "" "404"

test_endpoint "Get job with invalid UUID format" "GET" "/jobs/invalid-uuid" "" "404"

# 6. LIST JOBS TESTS
echo -e "\n${YELLOW}=== LIST JOBS ===${NC}"

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
echo -e "\n${YELLOW}=== RESPONSE VALIDATION ===${NC}"

echo -e "\n${YELLOW}Testing response structure for created job...${NC}"
response=$(curl -s -X POST "$BASE_URL/jobs" \
    -H "Content-Type: application/json" \
    -d '{"jobName": "response-test", "modelId": "distilbert-base-uncased-finetuned-sst-2-english", "input": {"text": "test"}}')

# Check if response contains required fields (response only shown on failures)

# Helper function for structure validation
check_field() {
    local field_name="$1"
    local pattern="$2"
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if echo "$response" | grep -q "$pattern"; then
        echo -e "${GREEN}✓${NC} Has $field_name field"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo -e "${RED}✗${NC} Missing $field_name field"
        echo "  Response: $response"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
}

check_field "id" '"id"'
check_field "jobName" '"jobName"'
check_field "modelId" '"modelId"'
check_field "status" '"status"'
check_field "createdAt" '"createdAt"'
check_field "updatedAt" '"updatedAt"'

TOTAL_TESTS=$((TOTAL_TESTS + 1))
if echo "$response" | grep -q '"status":"queued"'; then
    echo -e "${GREEN}✓${NC} Status is queued"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo -e "${RED}✗${NC} Status is not queued"
    echo "  Response: $response"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

echo -e "\n${YELLOW}=== TESTING COMPLETE ===${NC}"
echo "======================================"
echo -e "Total Tests: $TOTAL_TESTS"
echo -e "Passed: ${GREEN}$PASSED_TESTS${NC}"
echo -e "Failed: ${RED}$FAILED_TESTS${NC}"
echo "======================================"

if [ $FAILED_TESTS -eq 0 ]; then
    echo -e "${GREEN}🎉 ALL TESTS PASSED! 🎉${NC}"
    echo "Your API is working correctly!"
else
    echo -e "${RED}❌ SOME TESTS FAILED ❌${NC}"
    echo "Please review the failed tests above and fix any issues."
fi

# Exit with appropriate code (cleanup will be handled by trap)
if [ $FAILED_TESTS -eq 0 ]; then
    exit 0
else
    exit 1
fi
