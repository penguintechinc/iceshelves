#!/bin/bash
# Common functions for smoke tests
# Shared utilities for all per-container smoke test scripts

# Colors for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test counters (to be used by sourcing scripts)
SMOKE_PASSED=0
SMOKE_FAILED=0

# Wait for health endpoint to respond
# Usage: wait_for_health "service-name" "http://url/healthz" timeout_seconds
wait_for_health() {
    local service="$1"
    local url="$2"
    local timeout="${3:-120}"
    local start
    start=$(date +%s)

    echo -n "Waiting for $service to be healthy..."

    while true; do
        if curl -s -f "$url" > /dev/null 2>&1; then
            echo -e " ${GREEN}ready${NC}"
            return 0
        fi

        local elapsed=$(($(date +%s) - start))
        if [ "$elapsed" -ge "$timeout" ]; then
            echo -e " ${RED}timeout after ${timeout}s${NC}"
            return 1
        fi

        echo -n "."
        sleep 2
    done
}

# Test HTTP endpoint
# Usage: test_endpoint "name" "METHOD" "url" expected_status ["data"] ["headers"]
test_endpoint() {
    local name="$1"
    local method="$2"
    local url="$3"
    local expected_status="$4"
    local data="${5:-}"
    local headers="${6:-}"

    echo -n "  Testing $name... "

    local curl_args=(-s -w "\n%{http_code}" -X "$method")

    # Add headers if provided
    if [ -n "$headers" ]; then
        IFS=',' read -ra HEADER_ARRAY <<< "$headers"
        for h in "${HEADER_ARRAY[@]}"; do
            curl_args+=(-H "$h")
        done
    fi

    # Add data if provided
    if [ -n "$data" ]; then
        curl_args+=(-d "$data")
    fi

    local response
    local status
    local body

    response=$(curl "${curl_args[@]}" "$url" 2>/dev/null)
    status=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')

    if [ "$status" = "$expected_status" ]; then
        echo -e "${GREEN}PASS${NC} (HTTP $status)"
        ((SMOKE_PASSED++)) || true
        return 0
    else
        echo -e "${RED}FAIL${NC} (expected $expected_status, got $status)"
        if [ -n "$body" ]; then
            echo "    Response: ${body:0:200}"
        fi
        ((SMOKE_FAILED++)) || true
        return 1
    fi
}

# Test JSON response contains expected field value
# Usage: test_json_field "name" "url" ".field.path" "expected_value" ["headers"]
test_json_field() {
    local name="$1"
    local url="$2"
    local field="$3"
    local expected="$4"
    local headers="${5:-}"

    echo -n "  Testing $name... "

    local curl_args=(-s)
    if [ -n "$headers" ]; then
        IFS=',' read -ra HEADER_ARRAY <<< "$headers"
        for h in "${HEADER_ARRAY[@]}"; do
            curl_args+=(-H "$h")
        done
    fi

    local response
    local value

    response=$(curl "${curl_args[@]}" "$url" 2>/dev/null)
    value=$(echo "$response" | jq -r "$field" 2>/dev/null)

    if [ "$value" = "$expected" ]; then
        echo -e "${GREEN}PASS${NC} ($field = $expected)"
        ((SMOKE_PASSED++)) || true
        return 0
    else
        echo -e "${RED}FAIL${NC} (expected $field = $expected, got $value)"
        ((SMOKE_FAILED++)) || true
        return 1
    fi
}

# Test that JSON response contains a field (not null or empty)
# Usage: test_json_exists "name" "url" ".field.path" ["headers"]
test_json_exists() {
    local name="$1"
    local url="$2"
    local field="$3"
    local headers="${4:-}"

    echo -n "  Testing $name... "

    local curl_args=(-s)
    if [ -n "$headers" ]; then
        IFS=',' read -ra HEADER_ARRAY <<< "$headers"
        for h in "${HEADER_ARRAY[@]}"; do
            curl_args+=(-H "$h")
        done
    fi

    local response
    local value

    response=$(curl "${curl_args[@]}" "$url" 2>/dev/null)
    value=$(echo "$response" | jq -r "$field" 2>/dev/null)

    if [ -n "$value" ] && [ "$value" != "null" ]; then
        echo -e "${GREEN}PASS${NC} ($field exists)"
        ((SMOKE_PASSED++)) || true
        return 0
    else
        echo -e "${RED}FAIL${NC} ($field is null or missing)"
        ((SMOKE_FAILED++)) || true
        return 1
    fi
}

# Print test summary
# Usage: print_summary "Service Name"
print_summary() {
    local service="$1"
    echo ""
    echo "================================"
    echo "$service Summary"
    echo "================================"
    echo -e "Passed: ${GREEN}${SMOKE_PASSED}${NC}"
    echo -e "Failed: ${RED}${SMOKE_FAILED}${NC}"

    if [ "$SMOKE_FAILED" -eq 0 ]; then
        echo -e "${GREEN}All tests passed!${NC}"
        return 0
    else
        echo -e "${RED}Some tests failed!${NC}"
        return 1
    fi
}
