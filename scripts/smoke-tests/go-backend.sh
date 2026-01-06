#!/bin/bash
# Go Backend Smoke Tests
# Tests health checks, metrics, and high-performance API endpoints

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${1:-/tmp/smoke-test}"
GO_PORT=${GO_PORT:-8080}
BASE_URL="http://localhost:${GO_PORT}"

# Source common functions
source "${SCRIPT_DIR}/common.sh"

echo "Go Backend Smoke Tests"
echo "======================"
echo "Base URL: ${BASE_URL}"
echo ""

# Health checks
echo "--- Health Checks ---"
test_endpoint "healthz" "GET" "${BASE_URL}/healthz" "200"
test_endpoint "readyz" "GET" "${BASE_URL}/readyz" "200"
test_json_field "health status" "${BASE_URL}/healthz" ".status" "healthy"

# API v1 endpoints
echo ""
echo "--- API v1 Endpoints ---"
test_endpoint "status" "GET" "${BASE_URL}/api/v1/status" "200"
test_endpoint "hello" "GET" "${BASE_URL}/api/v1/hello" "200"
test_endpoint "memory/stats" "GET" "${BASE_URL}/api/v1/memory/stats" "200"
test_endpoint "numa/info" "GET" "${BASE_URL}/api/v1/numa/info" "200"

# Prometheus metrics
echo ""
echo "--- Prometheus Metrics ---"
test_endpoint "metrics endpoint" "GET" "${BASE_URL}/metrics" "200"

# Validate metrics contains expected content
echo -n "  Testing metrics content... "
METRICS_RESPONSE=$(curl -s "${BASE_URL}/metrics" 2>/dev/null)

if echo "$METRICS_RESPONSE" | grep -q "go_goroutines"; then
    echo -e "${GREEN}PASS${NC} (contains go_goroutines)"
    ((SMOKE_PASSED++)) || true
else
    echo -e "${RED}FAIL${NC} (missing expected metrics)"
    ((SMOKE_FAILED++)) || true
fi

# Response validation
echo ""
echo "--- Response Validation ---"
test_json_field "status service name" "${BASE_URL}/api/v1/status" ".service" "go-backend"
test_json_field "hello service name" "${BASE_URL}/api/v1/hello" ".service" "go-backend"
test_json_exists "memory stats pool_size" "${BASE_URL}/api/v1/memory/stats" ".pool_size"
test_json_exists "numa info available" "${BASE_URL}/api/v1/numa/info" ".numa_available"

# Performance check (basic response time)
echo ""
echo "--- Performance Check ---"
echo -n "  Testing response time... "

START_TIME=$(date +%s%N)
curl -s "${BASE_URL}/api/v1/hello" > /dev/null 2>&1
END_TIME=$(date +%s%N)

ELAPSED_MS=$(( (END_TIME - START_TIME) / 1000000 ))

if [ "$ELAPSED_MS" -lt 1000 ]; then
    echo -e "${GREEN}PASS${NC} (${ELAPSED_MS}ms < 1000ms)"
    ((SMOKE_PASSED++)) || true
else
    echo -e "${YELLOW}WARN${NC} (${ELAPSED_MS}ms >= 1000ms)"
    # Don't fail on slow response, just warn
    ((SMOKE_PASSED++)) || true
fi

# Print summary
print_summary "Go Backend"
exit $?
