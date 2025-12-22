#!/bin/bash
# Comprehensive Playwright Test Runner with Categorized Results

set -e

PROJECT_DIR="/home/cooneycw/Projects/nhl-api"
FRONTEND_DIR="$PROJECT_DIR/viewer-frontend"
RESULTS_DIR="/tmp/nhl-viewer-test-results"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

mkdir -p "$RESULTS_DIR"

cd "$FRONTEND_DIR"

# Ensure backend and frontend are running
echo -e "${BLUE}Checking viewer status...${NC}"

if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${RED}ERROR: Backend not running on port 8000${NC}"
    echo "Start with: ./scripts/start-viewer.sh --full"
    exit 1
fi

if ! curl -s http://localhost:5173 > /dev/null 2>&1; then
    echo -e "${RED}ERROR: Frontend not running on port 5173${NC}"
    echo "Start with: ./scripts/start-viewer.sh --full"
    exit 1
fi

echo -e "${GREEN}✓ Backend and frontend are running${NC}"
echo ""

# Run all tests with HTML reporter
echo -e "${YELLOW}Running comprehensive Playwright tests...${NC}"
echo ""

# Create summary report
REPORT_FILE="$RESULTS_DIR/test-summary-${TIMESTAMP}.md"

echo "# Playwright Test Results Summary" > "$REPORT_FILE"
echo "" >> "$REPORT_FILE"
echo "Generated: $(date)" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

echo "## Test Execution Overview" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

# Run each test suite individually to get detailed results
test_specs=(
    "dashboard.spec.ts"
    "data-viewer.spec.ts"
    "downloads.spec.ts"
    "validation.spec.ts"
    "game-reconciliation.spec.ts"
)

TOTAL_PASSED=0
TOTAL_FAILED=0
TOTAL_SKIPPED=0

for spec in "${test_specs[@]}"; do
    echo -e "${BLUE}Testing: $spec${NC}"

    echo "### $spec" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"

    # Run spec and capture output
    SPEC_OUTPUT="$RESULTS_DIR/${spec%.spec.ts}-output-${TIMESTAMP}.txt"

    if npx playwright test "tests/$spec" --reporter=list > "$SPEC_OUTPUT" 2>&1; then
        echo -e "${GREEN}✓ All tests passed${NC}"
        STATUS="✅ PASSED"
    else
        echo -e "${YELLOW}⚠ Some tests failed${NC}"
        STATUS="❌ FAILED"
    fi

    # Count results (simplified parsing)
    PASSED=$(grep -c "✓" "$SPEC_OUTPUT" 2>/dev/null || echo "0")
    FAILED=$(grep -c "✘" "$SPEC_OUTPUT" 2>/dev/null || echo "0")

    TOTAL_PASSED=$((TOTAL_PASSED + PASSED))
    TOTAL_FAILED=$((TOTAL_FAILED + FAILED))

    echo "**Status**: $STATUS" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"
    echo "- ✅ Passed: $PASSED" >> "$REPORT_FILE"
    echo "- ❌ Failed: $FAILED" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"

    # If failures, extract failure details
    if [ "$FAILED" -gt 0 ]; then
        echo "**Failures:**" >> "$REPORT_FILE"
        echo "\`\`\`" >> "$REPORT_FILE"
        grep "✘" "$SPEC_OUTPUT" | head -20 >> "$REPORT_FILE" 2>/dev/null || echo "See full output for details" >> "$REPORT_FILE"
        echo "\`\`\`" >> "$REPORT_FILE"
        echo "" >> "$REPORT_FILE"

        # Also capture error details
        echo "**Error Details:**" >> "$REPORT_FILE"
        echo "\`\`\`" >> "$REPORT_FILE"
        grep -A 3 "Error:" "$SPEC_OUTPUT" | head -30 >> "$REPORT_FILE" 2>/dev/null || echo "No detailed error messages captured" >> "$REPORT_FILE"
        echo "\`\`\`" >> "$REPORT_FILE"
        echo "" >> "$REPORT_FILE"
    fi

    echo ""
done

# Run full test suite with HTML reporter for detailed analysis
echo -e "${BLUE}Generating HTML report...${NC}"
npx playwright test --reporter=html --quiet > /dev/null 2>&1 || true

# Add summary to report
echo "## Overall Summary" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"
echo "- **Total Passed**: $TOTAL_PASSED" >> "$REPORT_FILE"
echo "- **Total Failed**: $TOTAL_FAILED" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

if [ "$TOTAL_FAILED" -eq 0 ]; then
    echo "🎉 **All tests passed!**" >> "$REPORT_FILE"
else
    echo "⚠️ **$TOTAL_FAILED tests failed - investigation needed**" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"
    echo "### Recommended Next Steps" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"
    echo "1. Review HTML report for screenshots and traces" >> "$REPORT_FILE"
    echo "2. Check backend logs: \`tail -100 /tmp/nhl-viewer-backend.log\`" >> "$REPORT_FILE"
    echo "3. Verify database connection and data availability" >> "$REPORT_FILE"
    echo "4. Create GitHub issues for each distinct failure type" >> "$REPORT_FILE"
fi

echo "" >> "$REPORT_FILE"
echo "---" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"
echo "**Reports:**" >> "$REPORT_FILE"
echo "- Summary: $REPORT_FILE" >> "$REPORT_FILE"
echo "- HTML: $FRONTEND_DIR/playwright-report/index.html" >> "$REPORT_FILE"
echo "- Individual outputs: $RESULTS_DIR/*-output-${TIMESTAMP}.txt" >> "$REPORT_FILE"

# Display summary
echo ""
echo -e "${GREEN}Test execution complete!${NC}"
echo ""
echo -e "Results:"
echo -e "  ${GREEN}Passed:${NC} $TOTAL_PASSED"
echo -e "  ${RED}Failed:${NC} $TOTAL_FAILED"
echo ""
echo -e "Reports:"
echo -e "  Summary: $REPORT_FILE"
echo -e "  HTML:    ${FRONTEND_DIR}/playwright-report/index.html"
echo ""
echo -e "To view HTML report:"
echo -e "  ${BLUE}npx playwright show-report${NC}"
echo ""

# Display summary report
cat "$REPORT_FILE"
