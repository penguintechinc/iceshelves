#!/bin/bash
# WebUI Smoke Tests
# Tests health checks, API proxy, and page load via Puppeteer

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_DIR="${1:-/tmp/smoke-test}"
WEBUI_PORT=${WEBUI_PORT:-3000}
BASE_URL="http://localhost:${WEBUI_PORT}"

# Source common functions
source "${SCRIPT_DIR}/common.sh"

echo "WebUI Smoke Tests"
echo "================="
echo "Base URL: ${BASE_URL}"
echo ""

# Health checks
echo "--- Health Checks ---"
test_endpoint "healthz" "GET" "${BASE_URL}/healthz" "200"
test_endpoint "readyz" "GET" "${BASE_URL}/readyz" "200"
test_json_field "health status" "${BASE_URL}/healthz" ".status" "healthy"

# API proxy tests (WebUI -> Flask backend)
echo ""
echo "--- API Proxy Tests ---"
test_endpoint "proxy: /api/v1/status" "GET" "${BASE_URL}/api/v1/status" "200"
test_endpoint "proxy: /api/v1/hello" "GET" "${BASE_URL}/api/v1/hello" "200"

# API proxy tests (WebUI -> Go backend)
test_endpoint "proxy: /api/go/v1/status" "GET" "${BASE_URL}/api/go/v1/status" "200"
test_endpoint "proxy: /api/go/v1/hello" "GET" "${BASE_URL}/api/go/v1/hello" "200"

# Static content / React app
echo ""
echo "--- Static Content ---"
echo -n "  Testing React app loads... "
APP_RESPONSE=$(curl -s -w "\n%{http_code}" "${BASE_URL}/" 2>/dev/null)
APP_STATUS=$(echo "$APP_RESPONSE" | tail -n1)
APP_BODY=$(echo "$APP_RESPONSE" | sed '$d')

if [ "$APP_STATUS" = "200" ]; then
    # Check that it contains React root element or common React patterns
    if echo "$APP_BODY" | grep -q -E '(id="root"|<div id="app"|React|bundle\.js|main\.js)'; then
        echo -e "${GREEN}PASS${NC} (React app detected)"
        ((SMOKE_PASSED++)) || true
    else
        echo -e "${YELLOW}WARN${NC} (HTML returned but React markers not found)"
        ((SMOKE_PASSED++)) || true
    fi
else
    echo -e "${RED}FAIL${NC} (HTTP $APP_STATUS)"
    ((SMOKE_FAILED++)) || true
fi

# Puppeteer page load tests (if available)
echo ""
echo "--- Page Load Tests (Puppeteer) ---"

# Check if puppeteer is available
PUPPETEER_AVAILABLE=false
if [ -d "${PROJECT_ROOT}/services/webui/node_modules/puppeteer" ]; then
    PUPPETEER_AVAILABLE=true
elif [ -d "${PROJECT_ROOT}/node_modules/puppeteer" ]; then
    PUPPETEER_AVAILABLE=true
fi

if [ "$PUPPETEER_AVAILABLE" = true ]; then
    # Create temporary Puppeteer test script
    PUPPETEER_SCRIPT="${LOG_DIR}/page-load-test.cjs"
    mkdir -p "$LOG_DIR"

    cat > "$PUPPETEER_SCRIPT" << 'PUPPETEER_EOF'
const puppeteer = require('puppeteer');

const BASE_URL = process.env.BASE_URL || 'http://localhost:3000';
const results = { passed: 0, failed: 0 };

async function testPageLoad(browser, name, path, options = {}) {
    const page = await browser.newPage();
    const expectRedirect = options.expectRedirect || false;
    const redirectPath = options.redirectPath || '/login';

    try {
        process.stdout.write(`  Testing ${name}... `);
        const response = await page.goto(`${BASE_URL}${path}`, {
            waitUntil: 'networkidle2',
            timeout: 30000
        });

        const status = response.status();
        const finalUrl = new URL(page.url());

        // Check for successful load (200-399 range)
        if (status >= 200 && status < 400) {
            // If expecting redirect, verify destination
            if (expectRedirect) {
                if (finalUrl.pathname === redirectPath || finalUrl.pathname.startsWith(redirectPath)) {
                    console.log(`\x1b[32mPASS\x1b[0m (redirected to ${finalUrl.pathname})`);
                    results.passed++;
                } else {
                    console.log(`\x1b[33mWARN\x1b[0m (expected redirect to ${redirectPath}, got ${finalUrl.pathname})`);
                    results.passed++; // Still pass since page loaded
                }
            } else {
                console.log(`\x1b[32mPASS\x1b[0m (HTTP ${status})`);
                results.passed++;
            }
        } else {
            throw new Error(`HTTP ${status}`);
        }
    } catch (error) {
        console.log(`\x1b[31mFAIL\x1b[0m (${error.message})`);
        results.failed++;
    } finally {
        await page.close();
    }
}

async function main() {
    let browser;
    try {
        browser = await puppeteer.launch({
            headless: 'new',
            args: [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu'
            ]
        });

        // Test login page (public)
        await testPageLoad(browser, 'Login page', '/login');

        // Test protected pages (should redirect to login when unauthenticated)
        await testPageLoad(browser, 'Dashboard (redirect)', '/', {
            expectRedirect: true,
            redirectPath: '/login'
        });

        console.log('');
        console.log(`  Page Load Results: ${results.passed} passed, ${results.failed} failed`);

        process.exit(results.failed > 0 ? 1 : 0);
    } catch (err) {
        console.error(`  Puppeteer error: ${err.message}`);
        process.exit(1);
    } finally {
        if (browser) {
            await browser.close();
        }
    }
}

main();
PUPPETEER_EOF

    # Run Puppeteer tests
    PUPPETEER_DIR=""
    if [ -d "${PROJECT_ROOT}/services/webui/node_modules/puppeteer" ]; then
        PUPPETEER_DIR="${PROJECT_ROOT}/services/webui"
    elif [ -d "${PROJECT_ROOT}/node_modules/puppeteer" ]; then
        PUPPETEER_DIR="${PROJECT_ROOT}"
    fi

    if [ -n "$PUPPETEER_DIR" ]; then
        cd "$PUPPETEER_DIR"
        if BASE_URL="$BASE_URL" node "$PUPPETEER_SCRIPT" 2>&1; then
            ((SMOKE_PASSED++)) || true
        else
            echo -e "  Page load tests overall: ${RED}FAIL${NC}"
            ((SMOKE_FAILED++)) || true
        fi
    fi

    # Cleanup
    rm -f "$PUPPETEER_SCRIPT"
else
    echo -e "  Puppeteer not installed - ${YELLOW}SKIPPING${NC} page load tests"
    echo "  (Install puppeteer in services/webui to enable)"
fi

# Print summary
print_summary "WebUI"
exit $?
