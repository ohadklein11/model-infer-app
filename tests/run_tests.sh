#!/bin/bash

# Main Test Suite Runner
# This script orchestrates all component tests, handles service lifecycle,
# and aggregates test results from all components.

set -e

# Configuration
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="docker-compose.dev.yml"
BASE_URL="http://localhost:8080"
MAKE_PID=""
CLEANUP_NEEDED=false
LOG_FILE="/tmp/test-suite.log"

# Test tracking
TOTAL_COMPONENTS=0
PASSED_COMPONENTS=0
FAILED_COMPONENTS=0
TOTAL_TESTS=0
TOTAL_PASSED=0
TOTAL_FAILED=0

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Component test configurations
declare -A COMPONENT_TESTS=(
    ["job-api"]="services/job-api/test_job_api.sh"
)

# Required services for each component
declare -A COMPONENT_SERVICES=(
    ["job-api"]="up"
)

echo "🧪 Test Suite Runner"
echo "==================="
echo "Base Directory: $BASE_DIR"
echo "Log File: $LOG_FILE"
echo ""

# Cleanup function
cleanup() {
    if [ "$CLEANUP_NEEDED" = true ]; then
        echo -e "\n${YELLOW}🧹 Stopping services and cleaning up...${NC}"
        CLEANUP_NEEDED=false  # Prevent double cleanup

        # Kill the make process if it's still running
        if [ -n "$MAKE_PID" ]; then
            # First try SIGTERM (graceful)
            kill $MAKE_PID 2>/dev/null || true

            # Give it 3 seconds to terminate gracefully
            local count=0
            while [ $count -lt 3 ] && kill -0 $MAKE_PID 2>/dev/null; do
                sleep 1
                count=$((count + 1))
            done

            # If still running, force kill with SIGKILL
            if kill -0 $MAKE_PID 2>/dev/null; then
                kill -9 $MAKE_PID 2>/dev/null || true
            fi

            timeout 5 bash -c "wait $MAKE_PID" 2>/dev/null || true
        fi

        # Run make down in background with timeout to prevent hanging
        echo "Running: make down"
        timeout 30 make down > /dev/null 2>&1 &
        MAKE_DOWN_PID=$!

        # Wait for make down to complete or timeout
        wait $MAKE_DOWN_PID 2>/dev/null || true

        echo -e "${GREEN}✅ Services stopped and cleaned up.${NC}"
    fi
}

# Set up trap to ensure cleanup on exit
trap cleanup EXIT INT TERM

# Function to check if service is running
check_service() {
    curl -s "$BASE_URL/health" > /dev/null 2>&1
    return $?
}

# Function to start services
start_services() {
    local service_cmd="$1"

    echo -e "${YELLOW}🚀 Starting services with Docker Compose...${NC}"

    # Check if we're in the right directory
    if [ ! -f "Makefile" ] || [ ! -f "$COMPOSE_FILE" ]; then
        echo -e "${RED}❌ Error: Cannot find Makefile or $COMPOSE_FILE${NC}"
        echo "Please run this script from the project root directory"
        exit 1
    fi

    # Check dependencies
    for cmd in make docker; do
        if ! command -v $cmd &> /dev/null; then
            echo -e "${RED}❌ Error: $cmd command not found${NC}"
            echo "Please install $cmd"
            exit 1
        fi
    done

    # Start the services using make
    echo "Running: make $service_cmd"
    make $service_cmd > "$LOG_FILE" 2>&1 &
    MAKE_PID=$!
    CLEANUP_NEEDED=true

    echo "Docker Compose started (PID: $MAKE_PID)"
    echo "Waiting for services to be ready..."

    # Wait for services to be ready (max 60 seconds)
    local max_attempts=60
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if check_service; then
            echo -e "${GREEN}✅ Services are ready!${NC}"
            echo ""
            return 0
        fi

        echo -n "."
        sleep 1
        attempt=$((attempt + 1))
    done

    echo -e "\n${RED}❌ Services failed to start within 60 seconds${NC}"
    echo "Check the log file: $LOG_FILE"
    echo "Last few lines of the log:"
    tail -20 "$LOG_FILE"
    exit 1
}

# Function to run a component test
run_component_test() {
    local component="$1"
    local test_script="$2"
    local full_test_path="$BASE_DIR/$test_script"

    TOTAL_COMPONENTS=$((TOTAL_COMPONENTS + 1))

    echo -e "${BLUE}📋 Testing component: $component${NC}"
    echo "Test script: $test_script"

    # Check if test script exists and is executable
    if [ ! -f "$full_test_path" ]; then
        echo -e "${RED}❌ Test script not found: $full_test_path${NC}"
        FAILED_COMPONENTS=$((FAILED_COMPONENTS + 1))
        return 1
    fi

    if [ ! -x "$full_test_path" ]; then
        echo -e "${YELLOW}⚠️  Making test script executable: $full_test_path${NC}"
        chmod +x "$full_test_path"
    fi

    # Run the test script and capture its output and exit code
    echo -e "${YELLOW}Running tests for $component...${NC}"
    local test_output
    local test_exit_code

    # Set environment variables for the test script
    export TEST_BASE_URL="$BASE_URL"
    export TEST_SKIP_SERVICE_MANAGEMENT="true"

    if test_output=$("$full_test_path" 2>&1); then
        test_exit_code=0
    else
        test_exit_code=$?
    fi

    # Parse test results from output (looking for our standard format)
    local component_total=$(echo "$test_output" | grep "Total Tests:" | grep -o '[0-9]\+' | head -1)
    local component_passed=$(echo "$test_output" | grep "Passed:" | grep -o '[0-9]\+' | head -1)
    local component_failed=$(echo "$test_output" | grep "Failed:" | grep -o '[0-9]\+' | head -1)

    # Default values if parsing fails
    component_total=${component_total:-0}
    component_passed=${component_passed:-0}
    component_failed=${component_failed:-0}

    # Update totals
    TOTAL_TESTS=$((TOTAL_TESTS + component_total))
    TOTAL_PASSED=$((TOTAL_PASSED + component_passed))
    TOTAL_FAILED=$((TOTAL_FAILED + component_failed))

    if [ $test_exit_code -eq 0 ] && [ "$component_failed" -eq 0 ]; then
        echo -e "${GREEN}✅ $component tests PASSED${NC}"
        echo "   Tests: $component_total, Passed: $component_passed, Failed: $component_failed"
        PASSED_COMPONENTS=$((PASSED_COMPONENTS + 1))
    else
        echo -e "${RED}❌ $component tests FAILED${NC}"
        echo "   Tests: $component_total, Passed: $component_passed, Failed: $component_failed"
        echo "   Exit code: $test_exit_code"
        FAILED_COMPONENTS=$((FAILED_COMPONENTS + 1))

        # Show test output for failed components
        echo -e "${YELLOW}Test output:${NC}"
        echo "$test_output" | sed 's/^/  /'
    fi

    echo ""
    return $test_exit_code
}

# Main execution
main() {
    local components_to_test=()
    local services_needed="up"

    # Parse command line arguments
    if [ $# -eq 0 ]; then
        # Run all components
        components_to_test=($(printf '%s\n' "${!COMPONENT_TESTS[@]}" | sort))
    else
        # Run specific components
        for component in "$@"; do
            if [[ -n "${COMPONENT_TESTS[$component]}" ]]; then
                components_to_test+=("$component")
            else
                echo -e "${RED}❌ Unknown component: $component${NC}"
                echo "Available components: ${!COMPONENT_TESTS[*]}"
                exit 1
            fi
        done
    fi

    echo "Components to test: ${components_to_test[*]}"
    echo ""

    # Check if services are already running
    echo -e "${YELLOW}🔍 Checking if services are already running...${NC}"
    if check_service; then
        echo -e "${GREEN}✅ Services are already running${NC}"
        echo -e "${YELLOW}⚠️  Using existing service instance${NC}"
        echo ""
    else
        start_services "$services_needed"
    fi

    # Run tests for each component
    local failed_components=()
    for component in "${components_to_test[@]}"; do
        if ! run_component_test "$component" "${COMPONENT_TESTS[$component]}"; then
            failed_components+=("$component")
        fi
    done

    # Print final results
    echo -e "${BLUE}📊 TEST SUITE SUMMARY${NC}"
    echo "========================================"
    echo -e "Components tested: $TOTAL_COMPONENTS"
    echo -e "Components passed: ${GREEN}$PASSED_COMPONENTS${NC}"
    echo -e "Components failed: ${RED}$FAILED_COMPONENTS${NC}"
    echo ""
    echo -e "Total tests: $TOTAL_TESTS"
    echo -e "Total passed: ${GREEN}$TOTAL_PASSED${NC}"
    echo -e "Total failed: ${RED}$TOTAL_FAILED${NC}"
    echo "========================================"

    if [ ${#failed_components[@]} -eq 0 ]; then
        echo -e "${GREEN}🎉 ALL COMPONENTS PASSED! 🎉${NC}"
        echo "Your test suite is working correctly!"
    else
        echo -e "${RED}❌ FAILED COMPONENTS: ${failed_components[*]} ❌${NC}"
        echo "Please review the failed tests above and fix any issues."
    fi

    # Exit with appropriate code
    if [ $FAILED_COMPONENTS -eq 0 ]; then
        exit 0
    else
        exit 1
    fi
}

# Show usage information
show_usage() {
    echo "Usage: $0 [component1] [component2] ..."
    echo ""
    echo "Available components:"
    for component in $(printf '%s\n' "${!COMPONENT_TESTS[@]}" | sort); do
        echo "  $component - ${COMPONENT_TESTS[$component]}"
    done
    echo ""
    echo "If no components are specified, all components will be tested."
    echo ""
    echo "Examples:"
    echo "  $0                    # Run all tests"
    echo "  $0 job-api           # Run only job-api tests"
    echo ""
}

# Handle help flag
if [[ "$1" == "-h" || "$1" == "--help" ]]; then
    show_usage
    exit 0
fi

# Run main function
main "$@"
