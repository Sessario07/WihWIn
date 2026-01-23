#!/bin/bash
# =============================================================================
# k6 Load Testing Runner Script
# =============================================================================
# Usage:
#   ./run-k6-tests.sh [test_type]
#   
# Test types: load, stress, spike, soak, all
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

TEST_TYPE="${1:-load}"

echo -e "${BLUE}"
echo "============================================================"
echo "          WihWIn k6 Load Testing Suite"
echo "============================================================"
echo -e "${NC}"

# Batch Processing Calculations
echo -e "${YELLOW}BATCH PROCESSING CALCULATIONS:${NC}"
echo "============================================================"
case $TEST_TYPE in
    load)
        echo "Test Type:          Load Test (Gradual Ramp-Up)"
        echo "Duration:           90 seconds"
        echo "Target RPS:         100 requests/second"
        echo "Flush interval:     120 seconds"
        echo "Requests per batch: 100 × 120 = 12,000"
        echo "Flush cycles:       90 ÷ 120 = 0.75 (partial)"
        echo "Total requests:     ~9,000"
        ;;
    stress)
        echo "Test Type:          Stress Test (Beyond Capacity)"
        echo "Duration:           90 seconds"
        echo "Target RPS:         500 requests/second (peak)"
        echo "Flush interval:     120 seconds"
        echo "Requests per batch: 500 × 120 = 60,000"
        echo "Flush cycles:       90 ÷ 120 = 0.75 (partial)"
        echo "Total requests:     ~27,000"
        ;;
    spike)
        echo "Test Type:          Spike Test (Immediate Spike)"
        echo "Duration:           90 seconds"
        echo "Target RPS:         1000 requests/second (spike)"
        echo "Flush interval:     120 seconds"
        echo "Requests per batch: 1000 × 120 = 120,000"
        echo "Flush cycles:       90 ÷ 120 = 0.75 (partial)"
        echo "Total requests:     ~63,000"
        ;;
    soak)
        echo "Test Type:          Soak Test (Sustained Load)"
        echo "Duration:           300 seconds (5 minutes)"
        echo "Target RPS:         50 requests/second"
        echo "Flush interval:     120 seconds"
        echo "Requests per batch: 50 × 120 = 6,000"
        echo "Flush cycles:       300 ÷ 120 = 2.5"
        echo "Total requests:     ~15,000"
        ;;
    all)
        echo "Running ALL test types sequentially"
        echo "Total Duration:     ~10 minutes"
        ;;
    *)
        echo -e "${RED}Invalid test type: $TEST_TYPE${NC}"
        echo "Valid options: load, stress, spike, soak, all"
        exit 1
        ;;
esac
echo "============================================================"
echo ""

# Check if containers are running
echo -e "${BLUE}Checking infrastructure status...${NC}"
if ! docker compose ps | grep -q "nginx_proxy.*running"; then
    echo -e "${YELLOW}Starting infrastructure...${NC}"
    docker compose up -d
    echo "Waiting for services to be ready..."
    sleep 30
fi

# Start k6 container if not running
echo -e "${BLUE}Starting k6 container...${NC}"
docker compose --profile testing up -d k6

# Verify connectivity
echo -e "${BLUE}Verifying k6 can reach nginx...${NC}"
if docker compose exec -T k6 wget -q -O- http://nginx:80/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ k6 can reach nginx successfully${NC}"
else
    echo -e "${YELLOW}⚠ Waiting for nginx to be ready...${NC}"
    sleep 10
fi

echo ""
echo -e "${GREEN}Starting $TEST_TYPE test...${NC}"
echo "============================================================"

run_test() {
    local script=$1
    local name=$2
    echo -e "${BLUE}Running $name...${NC}"
    docker compose exec -T k6 k6 run /scripts/$script
    echo ""
}

case $TEST_TYPE in
    load)
        run_test "load-test.js" "Load Test"
        ;;
    stress)
        run_test "stress-test.js" "Stress Test"
        ;;
    spike)
        run_test "spike-test.js" "Spike Test"
        ;;
    soak)
        run_test "soak-test.js" "Soak Test"
        ;;
    all)
        run_test "load-test.js" "Load Test"
        sleep 5
        run_test "stress-test.js" "Stress Test"
        sleep 5
        run_test "spike-test.js" "Spike Test"
        sleep 5
        run_test "soak-test.js" "Soak Test"
        ;;
esac

echo -e "${GREEN}"
echo "============================================================"
echo "                    TEST COMPLETE"
echo "============================================================"
echo -e "${NC}"
