#!/usr/bin/env bash
#
# Run E2E Torch Integration Tests
#
# This script builds the test FAISS index (if needed) and runs the
# complete E2E test suite for Torch integration with real components.
#
# Usage:
#   bash tests/run_e2e_torch.sh [--rebuild-index] [--verify-index] [--coverage]
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Change to project root
cd "$PROJECT_ROOT"

# Parse arguments
REBUILD_INDEX=false
VERIFY_INDEX=false
COVERAGE=false

for arg in "$@"; do
    case $arg in
        --rebuild-index)
            REBUILD_INDEX=true
            shift
            ;;
        --verify-index)
            VERIFY_INDEX=true
            shift
            ;;
        --coverage)
            COVERAGE=true
            shift
            ;;
        --help)
            echo "Usage: $0 [--rebuild-index] [--verify-index] [--coverage]"
            echo ""
            echo "Options:"
            echo "  --rebuild-index    Force rebuild test FAISS index even if it exists"
            echo "  --verify-index     Verify test index after building"
            echo "  --coverage         Generate coverage report for E2E tests only"
            echo ""
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $arg${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  ShopMindAI E2E Torch Integration Test Suite           ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# Step 1: Check Python environment
echo -e "${BLUE}[1/4]${NC} Checking Python environment..."
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${YELLOW}   ⚠️  Warning: No virtual environment detected${NC}"
    echo -e "${YELLOW}   Consider running: source .venv/bin/activate${NC}"
fi

python --version
echo ""

# Step 2: Build test FAISS index
echo -e "${BLUE}[2/4]${NC} Checking test FAISS index..."

TEST_INDEX_DIR="tests/fixtures/test_faiss_index"
INDEX_FILE="$TEST_INDEX_DIR/index.bin"
META_FILE="$TEST_INDEX_DIR/meta.pkl"

if [ "$REBUILD_INDEX" = true ] || [ ! -f "$INDEX_FILE" ] || [ ! -f "$META_FILE" ]; then
    echo -e "${YELLOW}   Building test FAISS index (this may take 1-2 minutes)...${NC}"
    
    BUILD_CMD="python tests/fixtures/build_test_faiss_index.py"
    
    if [ "$REBUILD_INDEX" = true ]; then
        BUILD_CMD="$BUILD_CMD --rebuild"
    fi
    
    if [ "$VERIFY_INDEX" = true ]; then
        BUILD_CMD="$BUILD_CMD --verify"
    fi
    
    if $BUILD_CMD; then
        echo -e "${GREEN}   ✅ Test FAISS index ready${NC}"
    else
        echo -e "${RED}   ❌ Failed to build test FAISS index${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}   ✅ Test FAISS index already exists${NC}"
    
    # Show index info
    if python -c "import pickle; meta = pickle.load(open('$META_FILE', 'rb')); print(f'   📊 Index contains {len(meta)} test documents')" 2>/dev/null; then
        :
    fi
fi

echo ""

# Step 3: Run E2E tests
echo -e "${BLUE}[3/4]${NC} Running E2E Torch integration tests..."
echo ""

# Build pytest command
PYTEST_CMD="pytest -m e2e_torch -v --tb=short --durations=10"

if [ "$COVERAGE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD --cov=app --cov-report=term-missing --cov-report=html:htmlcov/e2e"
fi

# Add color output
PYTEST_CMD="$PYTEST_CMD --color=yes"

echo -e "${YELLOW}   Running: $PYTEST_CMD${NC}"
echo ""

# Run tests
if $PYTEST_CMD; then
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  ✅  All E2E Torch Integration Tests Passed!            ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
    TEST_STATUS=0
else
    echo ""
    echo -e "${RED}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║  ❌  Some E2E Tests Failed                               ║${NC}"
    echo -e "${RED}╚══════════════════════════════════════════════════════════╝${NC}"
    TEST_STATUS=1
fi

echo ""

# Step 4: Summary
echo -e "${BLUE}[4/4]${NC} Test Summary"
echo ""

if [ "$COVERAGE" = true ]; then
    echo -e "${BLUE}   📊 Coverage report generated: htmlcov/e2e/index.html${NC}"
    echo ""
fi

if [ $TEST_STATUS -eq 0 ]; then
    echo -e "${GREEN}   Phase 2 Torch integration is production-ready! 🚀${NC}"
    echo ""
    echo -e "   Next steps:"
    echo -e "   • Run full test suite: ${BLUE}pytest${NC}"
    echo -e "   • Check coverage: ${BLUE}open htmlcov/index.html${NC}"
    echo -e "   • Deploy to staging: ${BLUE}./deploy_staging.sh${NC}"
else
    echo -e "${YELLOW}   Review failed tests and fix issues before deployment${NC}"
    echo ""
    echo -e "   Debug tips:"
    echo -e "   • Run specific test: ${BLUE}pytest tests/e2e/test_real_torch_integration.py::TestClassName::test_name -v${NC}"
    echo -e "   • Show full traceback: ${BLUE}pytest -m e2e_torch --tb=long${NC}"
    echo -e "   • Drop into debugger on failure: ${BLUE}pytest -m e2e_torch --pdb${NC}"
fi

echo ""

exit $TEST_STATUS
