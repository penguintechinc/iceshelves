#!/bin/bash
# Marketplace API Smoke Tests
# Tests marketplace endpoints including repositories, apps, inventory, manifests, and notifications

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${1:-/tmp/smoke-test}"
FLASK_PORT=${FLASK_PORT:-5000}
BASE_URL="http://localhost:${FLASK_PORT}"

# Source common functions
source "${SCRIPT_DIR}/common.sh"

echo "Marketplace API Smoke Tests"
echo "============================"
echo "Base URL: ${BASE_URL}"
echo ""

# Authentication flow
echo "--- Authentication ---"

# Login as admin (default credentials from docker-compose.yml)
echo -n "  Testing admin login... "
LOGIN_RESPONSE=$(curl -s -X POST "${BASE_URL}/api/v1/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"email": "admin@example.com", "password": "admin123"}' 2>/dev/null)

ACCESS_TOKEN=$(echo "$LOGIN_RESPONSE" | jq -r '.access_token' 2>/dev/null)

if [ -n "$ACCESS_TOKEN" ] && [ "$ACCESS_TOKEN" != "null" ]; then
    echo -e "${GREEN}PASS${NC} (token received)"
    ((SMOKE_PASSED++)) || true
else
    echo -e "${RED}FAIL${NC}"
    echo "    Response: ${LOGIN_RESPONSE:0:200}"
    ((SMOKE_FAILED++)) || true
    print_summary "Marketplace API"
    exit 1
fi

AUTH_HEADER="Authorization: Bearer ${ACCESS_TOKEN}"

# Repository Management (routes are at /api/v1/marketplace/helm)
echo ""
echo "--- Repository Management ---"
test_endpoint "GET /api/v1/marketplace/helm" "GET" "${BASE_URL}/api/v1/marketplace/helm" "200" "" "$AUTH_HEADER"

echo -n "  Testing POST /api/v1/marketplace/helm... "
REPO_DATA='{"name": "test-repo", "url": "https://example.com/helm", "description": "Test repository"}'
REPO_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${BASE_URL}/api/v1/marketplace/helm" \
    -H "Content-Type: application/json" \
    -H "$AUTH_HEADER" \
    -d "$REPO_DATA" 2>/dev/null)

REPO_STATUS=$(echo "$REPO_RESPONSE" | tail -n1)
REPO_BODY=$(echo "$REPO_RESPONSE" | sed '$d')

if [ "$REPO_STATUS" = "201" ] || [ "$REPO_STATUS" = "200" ]; then
    echo -e "${GREEN}PASS${NC} (HTTP $REPO_STATUS)"
    ((SMOKE_PASSED++)) || true
else
    echo -e "${RED}FAIL${NC} (expected 201/200, got $REPO_STATUS)"
    if [ -n "$REPO_BODY" ]; then
        echo "    Response: ${REPO_BODY:0:200}"
    fi
    ((SMOKE_FAILED++)) || true
fi

# Cluster Management (routes at /api/v1/marketplace/clusters)
echo ""
echo "--- Cluster Management ---"
test_endpoint "GET /api/v1/marketplace/clusters" "GET" "${BASE_URL}/api/v1/marketplace/clusters" "200" "" "$AUTH_HEADER"

# App Catalog (routes at /api/v1/marketplace/apps)
echo ""
echo "--- App Catalog ---"
test_endpoint "GET /api/v1/marketplace/apps" "GET" "${BASE_URL}/api/v1/marketplace/apps" "200" "" "$AUTH_HEADER"
test_endpoint "GET /api/v1/marketplace/apps/search?q=nginx" "GET" "${BASE_URL}/api/v1/marketplace/apps/search?q=nginx" "200" "" "$AUTH_HEADER"
test_endpoint "GET /api/v1/marketplace/apps/categories" "GET" "${BASE_URL}/api/v1/marketplace/apps/categories" "200" "" "$AUTH_HEADER"

# Inventory (routes at /api/v1/marketplace/inventory)
echo ""
echo "--- Inventory ---"
test_endpoint "GET /api/v1/marketplace/inventory" "GET" "${BASE_URL}/api/v1/marketplace/inventory" "200" "" "$AUTH_HEADER"
test_endpoint "GET /api/v1/marketplace/inventory/summary" "GET" "${BASE_URL}/api/v1/marketplace/inventory/summary" "200" "" "$AUTH_HEADER"

# Manifest Upload
echo ""
echo "--- Manifest Upload ---"
VALID_MANIFEST='{"manifest":"apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: test-config\ndata:\n  key: value"}'

echo -n "  Testing POST /api/v1/marketplace/manifests/validate (valid YAML)... "
MANIFEST_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${BASE_URL}/api/v1/marketplace/manifests/validate" \
    -H "Content-Type: application/json" \
    -H "$AUTH_HEADER" \
    -d "$VALID_MANIFEST" 2>/dev/null)

MANIFEST_STATUS=$(echo "$MANIFEST_RESPONSE" | tail -n1)
MANIFEST_BODY=$(echo "$MANIFEST_RESPONSE" | sed '$d')

if [ "$MANIFEST_STATUS" = "200" ]; then
    echo -e "${GREEN}PASS${NC} (HTTP $MANIFEST_STATUS)"
    ((SMOKE_PASSED++)) || true
else
    echo -e "${RED}FAIL${NC} (expected 200, got $MANIFEST_STATUS)"
    if [ -n "$MANIFEST_BODY" ]; then
        echo "    Response: ${MANIFEST_BODY:0:200}"
    fi
    ((SMOKE_FAILED++)) || true
fi

# Version Tracking (routes at /api/v1/marketplace/versions)
echo ""
echo "--- Version Tracking ---"
test_endpoint "GET /api/v1/marketplace/versions" "GET" "${BASE_URL}/api/v1/marketplace/versions" "200" "" "$AUTH_HEADER"
test_endpoint "GET /api/v1/marketplace/versions/updates" "GET" "${BASE_URL}/api/v1/marketplace/versions/updates" "200" "" "$AUTH_HEADER"

# Cloud Detection
echo ""
echo "--- Cloud Detection ---"
test_endpoint "GET /api/v1/marketplace/cloud/detect" "GET" "${BASE_URL}/api/v1/marketplace/cloud/detect" "200" "" "$AUTH_HEADER"
test_endpoint "GET /api/v1/marketplace/cloud/ingress-options" "GET" "${BASE_URL}/api/v1/marketplace/cloud/ingress-options" "200" "" "$AUTH_HEADER"

# Notifications
echo ""
echo "--- Notifications ---"
test_endpoint "GET /api/v1/marketplace/notifications/preferences" "GET" "${BASE_URL}/api/v1/marketplace/notifications/preferences" "200" "" "$AUTH_HEADER"
test_endpoint "GET /api/v1/marketplace/notifications/webhooks" "GET" "${BASE_URL}/api/v1/marketplace/notifications/webhooks" "200" "" "$AUTH_HEADER"

# Error Handling
echo ""
echo "--- Error Handling ---"

echo -n "  Testing POST /api/v1/marketplace/helm (missing name)... "
BAD_REPO_DATA='{"url": "https://example.com/helm"}'
BAD_REPO_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${BASE_URL}/api/v1/marketplace/helm" \
    -H "Content-Type: application/json" \
    -H "$AUTH_HEADER" \
    -d "$BAD_REPO_DATA" 2>/dev/null)

BAD_REPO_STATUS=$(echo "$BAD_REPO_RESPONSE" | tail -n1)
BAD_REPO_BODY=$(echo "$BAD_REPO_RESPONSE" | sed '$d')

if [ "$BAD_REPO_STATUS" = "400" ]; then
    echo -e "${GREEN}PASS${NC} (HTTP $BAD_REPO_STATUS)"
    ((SMOKE_PASSED++)) || true
else
    echo -e "${RED}FAIL${NC} (expected 400, got $BAD_REPO_STATUS)"
    if [ -n "$BAD_REPO_BODY" ]; then
        echo "    Response: ${BAD_REPO_BODY:0:200}"
    fi
    ((SMOKE_FAILED++)) || true
fi

echo -n "  Testing POST /api/v1/marketplace/manifests/validate (invalid YAML)... "
INVALID_MANIFEST='{"manifest":"invalid: yaml: [structure"}'
INVALID_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${BASE_URL}/api/v1/marketplace/manifests/validate" \
    -H "Content-Type: application/json" \
    -H "$AUTH_HEADER" \
    -d "$INVALID_MANIFEST" 2>/dev/null)

INVALID_STATUS=$(echo "$INVALID_RESPONSE" | tail -n1)
INVALID_BODY=$(echo "$INVALID_RESPONSE" | sed '$d')

# Note: API returns 200 with is_valid=false, which is correct behavior
if [ "$INVALID_STATUS" = "200" ]; then
    IS_VALID=$(echo "$INVALID_BODY" | jq -r '.is_valid' 2>/dev/null)
    if [ "$IS_VALID" = "false" ]; then
        echo -e "${GREEN}PASS${NC} (HTTP $INVALID_STATUS, is_valid=false)"
        ((SMOKE_PASSED++)) || true
    else
        echo -e "${RED}FAIL${NC} (expected is_valid=false)"
        ((SMOKE_FAILED++)) || true
    fi
else
    echo -e "${RED}FAIL${NC} (expected 200, got $INVALID_STATUS)"
    if [ -n "$INVALID_BODY" ]; then
        echo "    Response: ${INVALID_BODY:0:200}"
    fi
    ((SMOKE_FAILED++)) || true
fi

# Print summary
print_summary "Marketplace API"
exit $?
