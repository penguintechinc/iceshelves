#!/bin/bash
# Smoke Test Orchestrator
# Full container lifecycle testing: build, run, health, API, cleanup
#
# Usage: ./scripts/smoke-test.sh [options]
#
# Options:
#   --skip-build        Skip docker compose build step
#   --keep-containers   Don't cleanup containers after tests
#   --service NAME      Run tests for specific service only (flask-backend, go-backend, webui)
#
# Environment Variables:
#   FLASK_PORT          Flask backend port (default: 5000)
#   GO_PORT             Go backend port (default: 8080)
#   WEBUI_PORT          WebUI port (default: 3000)
#   HEALTH_TIMEOUT      Seconds to wait for health checks (default: 120)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_NAME=$(basename "$PROJECT_ROOT")
EPOCH=$(date +%s)
LOG_DIR="/tmp/smoke-test-${PROJECT_NAME}-${EPOCH}"

# Configuration
FLASK_PORT=${FLASK_PORT:-5000}
GO_PORT=${GO_PORT:-8080}
WEBUI_PORT=${WEBUI_PORT:-3000}
HEALTH_TIMEOUT=${HEALTH_TIMEOUT:-120}
SKIP_BUILD=false
KEEP_CONTAINERS=false
SINGLE_SERVICE=""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-build)
            SKIP_BUILD=true
            shift
            ;;
        --keep-containers)
            KEEP_CONTAINERS=true
            shift
            ;;
        --service)
            SINGLE_SERVICE="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --skip-build        Skip docker compose build step"
            echo "  --keep-containers   Don't cleanup containers after tests"
            echo "  --service NAME      Run tests for specific service only"
            echo ""
            echo "Environment Variables:"
            echo "  FLASK_PORT          Flask backend port (default: 5000)"
            echo "  GO_PORT             Go backend port (default: 8080)"
            echo "  WEBUI_PORT          WebUI port (default: 3000)"
            echo "  HEALTH_TIMEOUT      Health check timeout (default: 120)"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Create log directory
mkdir -p "$LOG_DIR"

# Export for child scripts
export FLASK_PORT GO_PORT WEBUI_PORT LOG_DIR

# Initialize summary
SUMMARY_LOG="${LOG_DIR}/summary.log"
{
    echo "Smoke Test Summary - $(date)"
    echo "Project: ${PROJECT_NAME}"
    echo "Log Directory: ${LOG_DIR}"
    echo "======================================"
} > "$SUMMARY_LOG"

# Source common functions for wait_for_health
source "${SCRIPT_DIR}/smoke-tests/common.sh"

# Counters
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

log_section() {
    echo ""
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}============================================${NC}"
    echo "" >> "$SUMMARY_LOG"
    echo "=== $1 ===" >> "$SUMMARY_LOG"
}

cleanup() {
    if [ "$KEEP_CONTAINERS" = false ]; then
        log_section "Cleanup"
        echo "Stopping and removing containers..."
        cd "$PROJECT_ROOT"
        docker compose down -v --remove-orphans 2>&1 | tee -a "${LOG_DIR}/cleanup.log" || true
        echo -e "${GREEN}Cleanup complete${NC}"
    else
        echo ""
        echo -e "${YELLOW}Keeping containers running (--keep-containers)${NC}"
        echo "To stop: docker compose down -v"
    fi
}

# Trap for cleanup on exit
trap cleanup EXIT

run_service_test() {
    local service="$1"
    local script="${SCRIPT_DIR}/smoke-tests/${service}.sh"

    if [ ! -x "$script" ]; then
        echo -e "${YELLOW}SKIP${NC} - script not found: $script"
        return 0
    fi

    if bash "$script" "$LOG_DIR" 2>&1 | tee "${LOG_DIR}/${service}.log"; then
        echo -e "${GREEN}${service} tests passed${NC}"
        echo "[PASS] ${service} smoke tests" >> "$SUMMARY_LOG"
        ((PASSED_TESTS++)) || true
    else
        echo -e "${RED}${service} tests failed${NC}"
        echo "[FAIL] ${service} smoke tests" >> "$SUMMARY_LOG"
        ((FAILED_TESTS++)) || true
    fi
    ((TOTAL_TESTS++)) || true
}

main() {
    cd "$PROJECT_ROOT"

    echo ""
    echo "============================================"
    echo "Smoke Test Orchestrator"
    echo "============================================"
    echo "Project: ${PROJECT_NAME}"
    echo "Log Directory: ${LOG_DIR}"
    echo "============================================"

    # Step 1: Build containers
    if [ "$SKIP_BUILD" = false ]; then
        log_section "Step 1: Building Containers"
        echo "Building all containers..."
        if docker compose build 2>&1 | tee "${LOG_DIR}/build.log"; then
            echo -e "${GREEN}Build successful${NC}"
            echo "[PASS] Container build" >> "$SUMMARY_LOG"
        else
            echo -e "${RED}Build failed${NC}"
            echo "[FAIL] Container build" >> "$SUMMARY_LOG"
            echo ""
            echo "Build logs: ${LOG_DIR}/build.log"
            exit 1
        fi
    else
        echo ""
        echo -e "${YELLOW}Skipping build (--skip-build)${NC}"
    fi

    # Step 2: Start containers
    log_section "Step 2: Starting Containers"
    echo "Starting containers..."

    # Stop any existing containers first
    docker compose down -v --remove-orphans 2>/dev/null || true

    # Start fresh
    docker compose up -d postgres redis 2>&1 | tee "${LOG_DIR}/startup.log"
    echo "Waiting for databases to initialize..."
    sleep 5

    docker compose up -d flask-backend go-backend webui 2>&1 | tee -a "${LOG_DIR}/startup.log"
    echo -e "${GREEN}Containers started${NC}"

    # Step 3: Wait for health checks
    log_section "Step 3: Waiting for Health Checks"

    HEALTH_FAILED=false

    if ! wait_for_health "flask-backend" "http://localhost:${FLASK_PORT}/healthz" "$HEALTH_TIMEOUT"; then
        echo "[FAIL] flask-backend health check" >> "$SUMMARY_LOG"
        HEALTH_FAILED=true
    else
        echo "[PASS] flask-backend health check" >> "$SUMMARY_LOG"
    fi

    if ! wait_for_health "go-backend" "http://localhost:${GO_PORT}/healthz" "$HEALTH_TIMEOUT"; then
        echo "[FAIL] go-backend health check" >> "$SUMMARY_LOG"
        HEALTH_FAILED=true
    else
        echo "[PASS] go-backend health check" >> "$SUMMARY_LOG"
    fi

    if ! wait_for_health "webui" "http://localhost:${WEBUI_PORT}/healthz" "$HEALTH_TIMEOUT"; then
        echo "[FAIL] webui health check" >> "$SUMMARY_LOG"
        HEALTH_FAILED=true
    else
        echo "[PASS] webui health check" >> "$SUMMARY_LOG"
    fi

    if [ "$HEALTH_FAILED" = true ]; then
        echo ""
        echo -e "${RED}Some services failed health checks${NC}"
        echo "Container logs:"
        docker compose logs --tail=50 2>&1 | tee "${LOG_DIR}/container-logs.log"
        exit 1
    fi

    echo ""
    echo -e "${GREEN}All services healthy${NC}"

    # Step 4-6: Run per-container smoke tests
    if [ -n "$SINGLE_SERVICE" ]; then
        log_section "Step 4: ${SINGLE_SERVICE} Smoke Tests"
        run_service_test "$SINGLE_SERVICE"
    else
        log_section "Step 4: Flask Backend Smoke Tests"
        run_service_test "flask-backend"

        log_section "Step 5: Go Backend Smoke Tests"
        run_service_test "go-backend"

        log_section "Step 6: WebUI Smoke Tests"
        run_service_test "webui"

        log_section "Step 7: Marketplace Smoke Tests"
        run_service_test "marketplace"
    fi

    # Final summary
    log_section "Final Results"
    echo "Total: $TOTAL_TESTS | Passed: $PASSED_TESTS | Failed: $FAILED_TESTS"
    echo "" >> "$SUMMARY_LOG"
    echo "======================================" >> "$SUMMARY_LOG"
    echo "Total: $TOTAL_TESTS | Passed: $PASSED_TESTS | Failed: $FAILED_TESTS" >> "$SUMMARY_LOG"

    if [ "$FAILED_TESTS" -eq 0 ]; then
        echo -e "${GREEN}All smoke tests passed!${NC}"
        echo "Status: PASS" >> "$SUMMARY_LOG"
        echo ""
        echo "Logs: ${LOG_DIR}/"
        return 0
    else
        echo -e "${RED}Some smoke tests failed!${NC}"
        echo "Status: FAIL" >> "$SUMMARY_LOG"
        echo ""
        echo "Logs: ${LOG_DIR}/"
        return 1
    fi
}

main "$@"
