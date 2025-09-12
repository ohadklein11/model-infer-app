# Testing Framework

This document describes the testing framework for the model-infer-app project.

## Overview

The testing framework is designed to be modular and scalable, with clear separation between test orchestration and individual component tests. Each component has its own test script, and a main test runner handles service lifecycle management and result aggregation.

## Architecture

```
model-infer-app/
├── tests/
│   ├── run_tests.sh              # Main test runner (orchestration)
│   ├── utils/
│   │   └── test_utils.sh         # Common test utilities
│   └── README.md                 # This documentation
├── services/
│   └── job-api/
│       ├── main.py               # Service code
│       ├── test_job_api.sh       # Job API component tests (co-located)
│       └── ...                   # Other service files
└── .pre-commit-config.yaml       # Updated to use new test structure
```

## Components

### 1. Main Test Runner (`run_tests.sh`)

The main test runner is responsible for:
- Service lifecycle management (start/stop Docker services)
- Running component tests in sequence
- Aggregating results from all components
- Providing a unified interface for running tests

**Usage:**
```bash
# Run all component tests
tests/run_tests.sh

# Run specific components
tests/run_tests.sh job-api

# Show help
tests/run_tests.sh --help
```

**Features:**
- Automatic service startup and cleanup
- Parallel test execution support (future)
- Detailed logging and error reporting
- Color-coded output for easy reading
- Test result aggregation across components

### 2. Test Utilities (`test_utils.sh`)

Common utilities shared across all component tests:
- HTTP endpoint testing functions
- JSON field validation
- Test result tracking and reporting
- Service health checking
- Environment validation

**Key Functions:**
- `test_endpoint()` - Test HTTP endpoints with expected status codes
- `check_field()` - Validate JSON response fields
- `print_test_results()` - Display test summary
- `wait_for_service()` - Wait for service to be ready
- `validate_test_environment()` - Check test prerequisites

### 3. Component Tests

Individual test scripts for each component (e.g., `services/job-api/test_job_api.sh`):
- Focus only on testing the component's functionality
- Use common utilities from `test_utils.sh`
- No service management logic
- Standardized output format for result aggregation

## Adding New Component Tests

To add tests for a new component:

1. **Create the test script:**
   ```bash
   # Create the test file co-located with the service
   touch services/new-component/test_new_component.sh
   chmod +x services/new-component/test_new_component.sh
   ```

2. **Structure the test script:**
   ```bash
   #!/bin/bash

   set -e

   # Get paths
   SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
   PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

   # Source utilities
   source "$PROJECT_ROOT/tests/utils/test_utils.sh"

   # Configuration
   TEST_BASE_URL="${TEST_BASE_URL:-http://localhost:8080}"
   COMPONENT_NAME="New Component"

   # Validate environment
   if ! validate_test_environment "$TEST_BASE_URL"; then
       exit 1
   fi

   # Your tests here...
   print_test_section "BASIC TESTS"
   test_endpoint "Health check" "GET" "/health" "" "200"

   # Print results and exit
   if print_test_results "$COMPONENT_NAME"; then
       exit 0
   else
       exit 1
   fi
   ```

3. **Register the component in the main runner:**
   Edit `tests/run_tests.sh` and add your component to the `COMPONENT_TESTS` array:
   ```bash
   declare -A COMPONENT_TESTS=(
       ["job-api"]="services/job-api/test_job_api.sh"
       ["new-component"]="services/new-component/test_new_component.sh"
   )
   ```

4. **Update pre-commit configuration (if needed):**
   The current configuration should automatically include new services, but verify the file patterns in `.pre-commit-config.yaml`.

## Environment Variables

The test framework uses these environment variables:

- `TEST_BASE_URL` - Base URL for API testing (default: http://localhost:8080)
- `TEST_SKIP_SERVICE_MANAGEMENT` - Set to "true" to skip service startup (used by main runner)

## Integration with Pre-commit

The test suite is integrated with pre-commit hooks:
```yaml
- id: test-suite
  name: Run Test Suite
  entry: tests/run_tests.sh
  language: script
  files: ^(services/.*\.(py|toml|yml|yaml|Dockerfile)|docker-compose\..*\.yml|Makefile)$
  pass_filenames: false
  verbose: true
```

Tests run automatically when files matching the pattern are changed.

## Best Practices

### Test Organization
- Keep component tests focused on their specific functionality
- Use descriptive test names that explain what is being tested
- Group related tests in sections using `print_test_section()`

### Error Handling
- Always validate the test environment before running tests
- Use appropriate exit codes (0 for success, 1 for failure)
- Provide clear error messages for debugging

### Service Dependencies
- Let the main runner handle service lifecycle
- Use `TEST_SKIP_SERVICE_MANAGEMENT` to detect when running under the main runner
- Include service readiness checks when running standalone

### Output Format
- Use standardized output format for result aggregation
- Include test counts in the expected format:
  ```
  Total Tests: X
  Passed: Y
  Failed: Z
  ```

## Troubleshooting

### Common Issues

1. **Tests fail to connect to service:**
   - Check if services are running: `docker compose -f docker-compose.dev.yml ps`
   - Verify the base URL is correct
   - Check firewall/network settings

2. **Permission denied errors:**
   - Ensure test scripts are executable: `chmod +x path/to/test_script.sh`
   - Check Docker permissions

3. **Tests hang during service startup:**
   - Check Docker logs: `docker compose -f docker-compose.dev.yml logs`
   - Increase timeout values if needed
   - Verify system resources

### Debug Mode

For detailed debugging, check the log file created by the main runner:
```bash
tail -f /tmp/test-suite.log
```

## Future Enhancements

- Parallel test execution across components
- Test coverage reporting
- Integration with CI/CD pipelines
- Performance benchmarking
- Database state management for integration tests
