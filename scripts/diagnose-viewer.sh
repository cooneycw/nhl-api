#!/bin/bash
# NHL Viewer Diagnostic Script
# Systematically checks all potential failure points and generates a report

set -e

PROJECT_DIR="/home/cooneycw/Projects/nhl-api"
REPORT_DIR="/tmp/nhl-viewer-diagnostics"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
REPORT_FILE="${REPORT_DIR}/diagnostic_${TIMESTAMP}.md"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

mkdir -p "$REPORT_DIR"

echo "# NHL Viewer Diagnostic Report" > "$REPORT_FILE"
echo "Generated: $(date)" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

log_section() {
    echo -e "\n${BLUE}=== $1 ===${NC}"
    echo "" >> "$REPORT_FILE"
    echo "## $1" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"
}

log_check() {
    local status=$1
    local message=$2
    if [ "$status" = "PASS" ]; then
        echo -e "${GREEN}✓${NC} $message"
        echo "- ✅ $message" >> "$REPORT_FILE"
    elif [ "$status" = "FAIL" ]; then
        echo -e "${RED}✗${NC} $message"
        echo "- ❌ $message" >> "$REPORT_FILE"
    else
        echo -e "${YELLOW}⚠${NC} $message"
        echo "- ⚠️ $message" >> "$REPORT_FILE"
    fi
}

# ============================================================================
# SECTION 1: Environment Checks
# ============================================================================

log_section "1. Environment Configuration"

# Check .env file exists
if [ -f "$PROJECT_DIR/.env" ]; then
    log_check "PASS" ".env file exists"

    # Check for DB credentials (without revealing values)
    if grep -q "^DB_HOST=" "$PROJECT_DIR/.env" 2>/dev/null; then
        log_check "PASS" "DB_HOST configured (direct credentials mode)"
    elif grep -q "^AWS_ACCESS_KEY_ID=" "$PROJECT_DIR/.env" 2>/dev/null; then
        log_check "PASS" "AWS credentials configured (Secrets Manager mode)"
    else
        log_check "FAIL" "No database credentials found in .env"
    fi
else
    log_check "FAIL" ".env file not found (copy from .env.example)"
fi

# Check Python environment
cd "$PROJECT_DIR"
export PYTHONPATH="$PROJECT_DIR/src:${PYTHONPATH:-}"

if python3 -c "import nhl_api" 2>/dev/null; then
    log_check "PASS" "nhl_api package importable"
else
    log_check "FAIL" "nhl_api package not importable (PYTHONPATH issue?)"
fi

# Check frontend dependencies
if [ -d "$PROJECT_DIR/viewer-frontend/node_modules" ]; then
    log_check "PASS" "Frontend dependencies installed"
else
    log_check "FAIL" "Frontend dependencies not installed (run: cd viewer-frontend && npm install)"
fi

# ============================================================================
# SECTION 2: Process Status
# ============================================================================

log_section "2. Process Status"

# Check if backend is running
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    log_check "PASS" "Backend responding on port 8000"
    BACKEND_RUNNING=true
else
    log_check "FAIL" "Backend not responding on port 8000"
    BACKEND_RUNNING=false

    # Check if process exists but not responding
    if lsof -ti:8000 > /dev/null 2>&1; then
        log_check "WARN" "Process bound to port 8000 but not responding"
    fi
fi

# Check if frontend is running
if curl -s http://localhost:5173 > /dev/null 2>&1; then
    log_check "PASS" "Frontend responding on port 5173"
    FRONTEND_RUNNING=true
else
    log_check "FAIL" "Frontend not responding on port 5173"
    FRONTEND_RUNNING=false
fi

# ============================================================================
# SECTION 3: Backend Health
# ============================================================================

if [ "$BACKEND_RUNNING" = true ]; then
    log_section "3. Backend Health Checks"

    # Test health endpoint
    HEALTH_RESPONSE=$(curl -s http://localhost:8000/health)

    if echo "$HEALTH_RESPONSE" | grep -q '"status":"healthy"'; then
        log_check "PASS" "Health endpoint reports Healthy"
    elif echo "$HEALTH_RESPONSE" | grep -q '"status":"degraded"'; then
        log_check "WARN" "Health endpoint reports Degraded"
    else
        log_check "FAIL" "Health endpoint returned unexpected response"
        echo "\`\`\`json" >> "$REPORT_FILE"
        echo "$HEALTH_RESPONSE" >> "$REPORT_FILE"
        echo "\`\`\`" >> "$REPORT_FILE"
    fi

    # Check database connection
    if echo "$HEALTH_RESPONSE" | grep -q '"connected":true'; then
        log_check "PASS" "Database connection established"
        DB_CONNECTED=true
    else
        log_check "FAIL" "Database connection failed"
        DB_CONNECTED=false

        # Extract error if present
        DB_ERROR=$(echo "$HEALTH_RESPONSE" | grep -o '"error":"[^"]*"' || echo "")
        if [ -n "$DB_ERROR" ]; then
            echo "  Error: $DB_ERROR" >> "$REPORT_FILE"
        fi
    fi

    # Test API endpoints
    log_section "3.1 API Endpoint Tests"

    endpoints=(
        "/api/v1/players"
        "/api/v1/games"
        "/api/v1/teams"
        "/api/v1/monitoring/dashboard"
        "/api/v1/downloads/seasons"
        "/api/v1/downloads/sources"
        "/api/v1/validation/summary?season=20242025"
        "/api/v1/coverage/summary"
    )

    for endpoint in "${endpoints[@]}"; do
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000${endpoint}")
        if [ "$HTTP_CODE" = "200" ]; then
            log_check "PASS" "$endpoint → 200 OK"
        elif [ "$HTTP_CODE" = "500" ]; then
            log_check "FAIL" "$endpoint → 500 Internal Server Error"
        elif [ "$HTTP_CODE" = "000" ]; then
            log_check "FAIL" "$endpoint → Connection refused"
        else
            log_check "WARN" "$endpoint → HTTP $HTTP_CODE"
        fi
    done
else
    log_section "3. Backend Health Checks"
    log_check "FAIL" "Cannot perform health checks - backend not running"

    # Check logs for startup errors
    if [ -f /tmp/nhl-viewer-backend.log ]; then
        echo "" >> "$REPORT_FILE"
        echo "### Backend Log Errors" >> "$REPORT_FILE"
        echo "\`\`\`" >> "$REPORT_FILE"
        tail -50 /tmp/nhl-viewer-backend.log | grep -i "error\|exception\|failed\|unable" >> "$REPORT_FILE" 2>/dev/null || echo "No errors in log" >> "$REPORT_FILE"
        echo "\`\`\`" >> "$REPORT_FILE"
    fi
fi

# ============================================================================
# SECTION 4: Database Checks
# ============================================================================

if [ "$DB_CONNECTED" = true ]; then
    log_section "4. Database Checks"

    # Create a Python helper script to check database
    DB_CHECK_SCRIPT="$REPORT_DIR/db_checks_${TIMESTAMP}.py"

    cat > "$DB_CHECK_SCRIPT" << 'DBCHECK'
import asyncio
import sys
from nhl_api.services.db import DatabaseService

async def check_database():
    db = DatabaseService()
    try:
        await db.connect()
    except Exception as e:
        print(f"CONNECTION_ERROR:{str(e)}")
        return

    try:
        # Check materialized views exist and have data
        views = [
            'mv_player_summary',
            'mv_game_summary',
            'mv_download_batch_stats',
            'mv_source_health',
            'mv_reconciliation_summary',
            'mv_data_coverage'
        ]

        for view in views:
            count_exists = await db.fetchval(
                f"SELECT COUNT(*) FROM information_schema.tables WHERE table_name = '{view}'"
            )
            print(f"VIEW_EXISTS:{view}:{count_exists > 0}")

            # Check if view has data
            if count_exists > 0:
                try:
                    row_count = await db.fetchval(f"SELECT COUNT(*) FROM {view}")
                    print(f"VIEW_ROWS:{view}:{row_count}")
                except Exception as e:
                    print(f"VIEW_ERROR:{view}:{str(e)}")

        # Check core tables have data
        tables = ['players', 'games', 'teams', 'seasons', 'import_batches', 'data_sources']
        for table in tables:
            try:
                count = await db.fetchval(f"SELECT COUNT(*) FROM {table}")
                print(f"TABLE_ROWS:{table}:{count}")
            except Exception as e:
                print(f"TABLE_ERROR:{table}:{str(e)}")

    finally:
        await db.disconnect()

asyncio.run(check_database())
DBCHECK

    # Run database checks
    cd "$PROJECT_DIR"
    export PYTHONPATH="$PROJECT_DIR/src:${PYTHONPATH:-}"
    python3 "$DB_CHECK_SCRIPT" > "$REPORT_DIR/db_output_${TIMESTAMP}.txt" 2>&1

    # Parse results
    while IFS=: read -r key value extra; do
        case "$key" in
            CONNECTION_ERROR)
                log_check "FAIL" "Database connection error: $value"
                ;;
            VIEW_EXISTS)
                if [ "$extra" = "True" ]; then
                    log_check "PASS" "Materialized view exists: $value"
                else
                    log_check "FAIL" "Materialized view missing: $value"
                fi
                ;;
            VIEW_ROWS)
                if [ "$extra" -gt 0 ] 2>/dev/null; then
                    log_check "PASS" "View $value has data: $extra rows"
                else
                    log_check "WARN" "View $value is empty (0 rows)"
                fi
                ;;
            VIEW_ERROR)
                log_check "FAIL" "Error querying view $value: $extra"
                ;;
            TABLE_ROWS)
                if [ "$extra" -gt 0 ] 2>/dev/null; then
                    log_check "PASS" "Table $value has data: $extra rows"
                else
                    log_check "WARN" "Table $value is empty (0 rows)"
                fi
                ;;
            TABLE_ERROR)
                log_check "FAIL" "Error querying table $value: $extra"
                ;;
        esac
    done < "$REPORT_DIR/db_output_${TIMESTAMP}.txt"
else
    log_section "4. Database Checks"
    log_check "FAIL" "Cannot perform database checks - no connection"
fi

# ============================================================================
# SECTION 5: Frontend Checks
# ============================================================================

if [ "$FRONTEND_RUNNING" = true ]; then
    log_section "5. Frontend Checks"

    # Check if frontend can load
    FRONTEND_HTML=$(curl -s http://localhost:5173)

    if echo "$FRONTEND_HTML" | grep -q "root"; then
        log_check "PASS" "Frontend HTML loads correctly"
    else
        log_check "FAIL" "Frontend HTML malformed or missing"
    fi

    log_check "WARN" "Browser console errors require Playwright tests (see Phase 2)"
else
    log_section "5. Frontend Checks"
    log_check "FAIL" "Cannot perform frontend checks - frontend not running"

    if [ -f /tmp/nhl-viewer-frontend.log ]; then
        echo "" >> "$REPORT_FILE"
        echo "### Frontend Log Errors" >> "$REPORT_FILE"
        echo "\`\`\`" >> "$REPORT_FILE"
        tail -50 /tmp/nhl-viewer-frontend.log | grep -i "error\|exception\|failed" >> "$REPORT_FILE" 2>/dev/null || echo "No errors in log" >> "$REPORT_FILE"
        echo "\`\`\`" >> "$REPORT_FILE"
    fi
fi

# ============================================================================
# Summary
# ============================================================================

log_section "Summary"

echo "" >> "$REPORT_FILE"
echo "### Next Steps" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

if [ "$BACKEND_RUNNING" = false ]; then
    echo "1. **Start the backend**: \`./scripts/start-viewer.sh --full\`" >> "$REPORT_FILE"
fi

if [ "$DB_CONNECTED" = false ]; then
    echo "1. **Fix database connection**: Check .env credentials or AWS Secrets Manager" >> "$REPORT_FILE"
fi

echo "" >> "$REPORT_FILE"
echo "**Run Playwright tests for detailed failure analysis:**" >> "$REPORT_FILE"
echo "\`\`\`bash" >> "$REPORT_FILE"
echo "cd viewer-frontend" >> "$REPORT_FILE"
echo "npx playwright test --reporter=html" >> "$REPORT_FILE"
echo "\`\`\`" >> "$REPORT_FILE"

echo ""
echo -e "${GREEN}Diagnostic report generated: $REPORT_FILE${NC}"
echo ""
cat "$REPORT_FILE"
