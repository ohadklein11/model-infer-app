#!/bin/bash

# Common Test Utilities
# Shared functions and utilities for component tests

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test result tracking (to be used by individual test scripts)
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Function to test an endpoint
test_endpoint() {
    local test_name="$1"
    local method="$2"
    local endpoint="$3"
    local data="$4"
    local expected_status="$5"
    local base_url="${6:-$TEST_BASE_URL}"

    # Make the request
    local response
    if [ -n "$data" ]; then
        response=$(curl -s -w "\n%{http_code}" -X "$method" "$base_url$endpoint" \
            -H "Content-Type: application/json" \
            -d "$data")
    else
        response=$(curl -s -w "\n%{http_code}" -X "$method" "$base_url$endpoint")
    fi

    # Split response and status code
    local status_code=$(echo "$response" | tail -n1)
    local response_body=$(echo "$response" | head -n -1)

    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    if [ "$status_code" = "$expected_status" ]; then
        echo -e "${GREEN}✓${NC} $test_name"
        PASSED_TESTS=$((PASSED_TESTS + 1))
        return 0
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
        return 1
    fi
}

# Function to check if a field exists in JSON response
check_field() {
    local response="$1"
    local field_name="$2"
    local pattern="$3"

    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if echo "$response" | grep -q "$pattern"; then
        echo -e "${GREEN}✓${NC} Has $field_name field"
        PASSED_TESTS=$((PASSED_TESTS + 1))
        return 0
    else
        echo -e "${RED}✗${NC} Missing $field_name field"
        echo "  Response: $response"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        return 1
    fi
}

# Function to print test section header
print_test_section() {
    local section_name="$1"
    echo -e "\n${YELLOW}=== $section_name ===${NC}"
}

# Function to print test results summary
print_test_results() {
    local component_name="${1:-Component}"

    echo -e "\n${YELLOW}=== $component_name TESTING COMPLETE ===${NC}"
    echo "======================================"
    echo -e "Total Tests: $TOTAL_TESTS"
    echo -e "Passed: ${GREEN}$PASSED_TESTS${NC}"
    echo -e "Failed: ${RED}$FAILED_TESTS${NC}"
    echo "======================================"

    if [ $FAILED_TESTS -eq 0 ]; then
        echo -e "${GREEN}🎉 ALL TESTS PASSED! 🎉${NC}"
        echo "Your $component_name is working correctly!"
        return 0
    else
        echo -e "${RED}❌ SOME TESTS FAILED ❌${NC}"
        echo "Please review the failed tests above and fix any issues."
        return 1
    fi
}

# Function to wait for a service to be ready
wait_for_service() {
    local service_url="$1"
    local max_attempts="${2:-30}"
    local service_name="${3:-Service}"

    echo "Waiting for $service_name to be ready at $service_url..."

    local attempt=1
    while [ $attempt -le $max_attempts ]; do
        if curl -s "$service_url" > /dev/null 2>&1; then
            echo -e "${GREEN}✓ $service_name is ready!${NC}"
            return 0
        fi

        echo -n "."
        sleep 1
        attempt=$((attempt + 1))
    done

    echo -e "\n${RED}✗ $service_name failed to start within $max_attempts seconds${NC}"
    return 1
}

# Function to make a simple HTTP request and return just the response body
make_request() {
    local method="$1"
    local endpoint="$2"
    local data="$3"
    local base_url="${4:-$TEST_BASE_URL}"

    if [ -n "$data" ]; then
        curl -s -X "$method" "$base_url$endpoint" \
            -H "Content-Type: application/json" \
            -d "$data"
    else
        curl -s -X "$method" "$base_url$endpoint"
    fi
}

# Function to extract field from JSON response
extract_json_field() {
    local json="$1"
    local field="$2"
    echo "$json" | grep -o "\"$field\":\"[^\"]*\"" | cut -d'"' -f4
}

# Function to validate test environment
validate_test_environment() {
    local base_url="${1:-$TEST_BASE_URL}"

    if [ -z "$base_url" ]; then
        echo -e "${RED}❌ Error: TEST_BASE_URL not set${NC}"
        return 1
    fi

    # Check required tools
    for tool in curl grep; do
        if ! command -v $tool &> /dev/null; then
            echo -e "${RED}❌ Error: $tool command not found${NC}"
            return 1
        fi
    done

    return 0
}

# Function to reset test counters (useful for multiple test runs)
reset_test_counters() {
    TOTAL_TESTS=0
    PASSED_TESTS=0
    FAILED_TESTS=0
}
