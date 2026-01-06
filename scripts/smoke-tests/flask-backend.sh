#!/bin/bash
# Flask Backend Smoke Tests
# Tests health checks, authentication flow, and API endpoints

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${1:-/tmp/smoke-test}"
FLASK_PORT=${FLASK_PORT:-5000}
BASE_URL="http://localhost:${FLASK_PORT}"

# Source common functions
source "${SCRIPT_DIR}/common.sh"

echo "Flask Backend Smoke Tests"
echo "========================="
echo "Base URL: ${BASE_URL}"
echo ""

# Health checks
echo "--- Health Checks ---"
test_endpoint "healthz" "GET" "${BASE_URL}/healthz" "200"
test_endpoint "readyz" "GET" "${BASE_URL}/readyz" "200"
test_json_field "health status" "${BASE_URL}/healthz" ".status" "healthy"

# Public endpoints
echo ""
echo "--- Public Endpoints ---"
test_endpoint "status" "GET" "${BASE_URL}/api/v1/status" "200"
test_endpoint "hello (public)" "GET" "${BASE_URL}/api/v1/hello" "200"

# Authentication flow
echo ""
echo "--- Authentication Flow ---"

# Generate unique test user
TEST_EMAIL="smoketest-$(date +%s)@test.local"
TEST_PASSWORD="SmokeTest123!"

# Register a test user
echo -n "  Testing registration... "
REGISTER_RESPONSE=$(curl -s -X POST "${BASE_URL}/api/v1/auth/register" \
    -H "Content-Type: application/json" \
    -d "{\"email\": \"${TEST_EMAIL}\", \"password\": \"${TEST_PASSWORD}\", \"full_name\": \"Smoke Test User\"}" 2>/dev/null)

USER_ID=$(echo "$REGISTER_RESPONSE" | jq -r '.user.id' 2>/dev/null)

if [ -n "$USER_ID" ] && [ "$USER_ID" != "null" ]; then
    echo -e "${GREEN}PASS${NC} (user_id: $USER_ID)"
    ((SMOKE_PASSED++)) || true
else
    echo -e "${RED}FAIL${NC}"
    echo "    Response: ${REGISTER_RESPONSE:0:200}"
    ((SMOKE_FAILED++)) || true
fi

# Login
echo -n "  Testing login... "
LOGIN_RESPONSE=$(curl -s -X POST "${BASE_URL}/api/v1/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\": \"${TEST_EMAIL}\", \"password\": \"${TEST_PASSWORD}\"}" 2>/dev/null)

ACCESS_TOKEN=$(echo "$LOGIN_RESPONSE" | jq -r '.access_token' 2>/dev/null)
REFRESH_TOKEN=$(echo "$LOGIN_RESPONSE" | jq -r '.refresh_token' 2>/dev/null)

if [ -n "$ACCESS_TOKEN" ] && [ "$ACCESS_TOKEN" != "null" ]; then
    echo -e "${GREEN}PASS${NC} (token received)"
    ((SMOKE_PASSED++)) || true
else
    echo -e "${RED}FAIL${NC}"
    echo "    Response: ${LOGIN_RESPONSE:0:200}"
    ((SMOKE_FAILED++)) || true
fi

# Authenticated endpoints (only if we have a token)
echo ""
echo "--- Authenticated Endpoints ---"

if [ -n "$ACCESS_TOKEN" ] && [ "$ACCESS_TOKEN" != "null" ]; then
    AUTH_HEADER="Authorization: Bearer ${ACCESS_TOKEN}"

    test_endpoint "auth/me" "GET" "${BASE_URL}/api/v1/auth/me" "200" "" "$AUTH_HEADER"
    test_endpoint "hello/protected" "GET" "${BASE_URL}/api/v1/hello/protected" "200" "" "$AUTH_HEADER"

    # Test token refresh
    echo -n "  Testing token refresh... "
    REFRESH_RESPONSE=$(curl -s -X POST "${BASE_URL}/api/v1/auth/refresh" \
        -H "Content-Type: application/json" \
        -d "{\"refresh_token\": \"${REFRESH_TOKEN}\"}" 2>/dev/null)

    NEW_TOKEN=$(echo "$REFRESH_RESPONSE" | jq -r '.access_token' 2>/dev/null)

    if [ -n "$NEW_TOKEN" ] && [ "$NEW_TOKEN" != "null" ]; then
        echo -e "${GREEN}PASS${NC} (new token received)"
        ((SMOKE_PASSED++)) || true
        ACCESS_TOKEN="$NEW_TOKEN"
        AUTH_HEADER="Authorization: Bearer ${ACCESS_TOKEN}"
    else
        echo -e "${RED}FAIL${NC}"
        echo "    Response: ${REFRESH_RESPONSE:0:200}"
        ((SMOKE_FAILED++)) || true
    fi

    # Test logout
    echo -n "  Testing logout... "
    LOGOUT_RESPONSE=$(curl -s -X POST "${BASE_URL}/api/v1/auth/logout" \
        -H "Authorization: Bearer ${ACCESS_TOKEN}" 2>/dev/null)

    LOGOUT_MSG=$(echo "$LOGOUT_RESPONSE" | jq -r '.message' 2>/dev/null)

    if [ -n "$LOGOUT_MSG" ] && [ "$LOGOUT_MSG" != "null" ]; then
        echo -e "${GREEN}PASS${NC}"
        ((SMOKE_PASSED++)) || true
    else
        echo -e "${RED}FAIL${NC}"
        echo "    Response: ${LOGOUT_RESPONSE:0:200}"
        ((SMOKE_FAILED++)) || true
    fi
else
    echo "  Skipping authenticated tests (no token available)"
    ((SMOKE_FAILED+=4)) || true
fi

# Error handling tests
echo ""
echo "--- Error Handling ---"
test_endpoint "unauthorized (no token)" "GET" "${BASE_URL}/api/v1/hello/protected" "401"
test_endpoint "invalid login (empty body)" "POST" "${BASE_URL}/api/v1/auth/login" "400" '{}' "Content-Type: application/json"
test_endpoint "invalid login (wrong password)" "POST" "${BASE_URL}/api/v1/auth/login" "401" "{\"email\": \"${TEST_EMAIL}\", \"password\": \"wrongpassword\"}" "Content-Type: application/json"

# Print summary
print_summary "Flask Backend"
exit $?
