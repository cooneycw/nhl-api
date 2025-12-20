#!/bin/bash
# NHL API Data Viewer Startup Script
#
# Usage:
#   ./scripts/start-viewer.sh           # Start backend only
#   ./scripts/start-viewer.sh --full    # Start backend + frontend
#   ./scripts/start-viewer.sh --stop    # Stop all viewer processes
#
# The backend runs on port 8000, frontend on port 5173

set -e

PROJECT_DIR="/home/cooneycw/Projects/nhl-api"
BACKEND_PID_FILE="/tmp/nhl-viewer-backend.pid"
FRONTEND_PID_FILE="/tmp/nhl-viewer-frontend.pid"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

stop_viewer() {
    echo -e "${YELLOW}Stopping NHL Data Viewer...${NC}"

    if [ -f "$BACKEND_PID_FILE" ]; then
        PID=$(cat "$BACKEND_PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID"
            echo -e "${GREEN}Backend stopped (PID: $PID)${NC}"
        fi
        rm -f "$BACKEND_PID_FILE"
    fi

    if [ -f "$FRONTEND_PID_FILE" ]; then
        PID=$(cat "$FRONTEND_PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID"
            echo -e "${GREEN}Frontend stopped (PID: $PID)${NC}"
        fi
        rm -f "$FRONTEND_PID_FILE"
    fi

    # Also kill any orphaned processes on the ports
    lsof -ti:8000 2>/dev/null | xargs -r kill 2>/dev/null || true
    lsof -ti:5173 2>/dev/null | xargs -r kill 2>/dev/null || true

    echo -e "${GREEN}Viewer stopped.${NC}"
}

start_backend() {
    echo -e "${YELLOW}Starting NHL Data Viewer Backend...${NC}"

    cd "$PROJECT_DIR"

    # Check if already running
    if [ -f "$BACKEND_PID_FILE" ] && kill -0 "$(cat "$BACKEND_PID_FILE")" 2>/dev/null; then
        echo -e "${GREEN}Backend already running (PID: $(cat "$BACKEND_PID_FILE"))${NC}"
        return 0
    fi

    # Start backend in background
    nohup uvicorn nhl_api.viewer.main:app --host 0.0.0.0 --port 8000 > /tmp/nhl-viewer-backend.log 2>&1 &
    echo $! > "$BACKEND_PID_FILE"

    # Wait for startup
    sleep 3

    # Check if process is still running and responding
    if kill -0 "$(cat "$BACKEND_PID_FILE")" 2>/dev/null; then
        # Give it a moment to fully initialize
        sleep 1
        if curl -s http://localhost:8000/health > /dev/null 2>&1; then
            echo -e "${GREEN}Backend started successfully (PID: $(cat "$BACKEND_PID_FILE"))${NC}"
            echo ""
            echo -e "  ${GREEN}API:${NC}     http://localhost:8000"
            echo -e "  ${GREEN}Swagger:${NC} http://localhost:8000/docs"
            echo -e "  ${GREEN}ReDoc:${NC}   http://localhost:8000/redoc"
            echo -e "  ${GREEN}Health:${NC}  http://localhost:8000/health"
            echo ""
            echo -e "  Logs: tail -f /tmp/nhl-viewer-backend.log"
        else
            echo -e "${RED}Backend failed to start.${NC}"
            echo ""
            # Check for common errors
            if grep -q "Unable to locate credentials" /tmp/nhl-viewer-backend.log 2>/dev/null; then
                echo -e "${YELLOW}Cause: AWS credentials not configured${NC}"
                echo ""
                echo "The viewer needs AWS credentials to access the database."
                echo "Options:"
                echo "  1. Configure AWS CLI: aws configure"
                echo "  2. Set environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY"
                echo "  3. Use AWS SSO: aws sso login"
            else
                echo "Check logs: tail -20 /tmp/nhl-viewer-backend.log"
            fi
            rm -f "$BACKEND_PID_FILE"
            return 1
        fi
    else
        echo -e "${RED}Backend failed to start.${NC}"
        echo ""
        # Check for common errors in log
        if grep -q "Unable to locate credentials" /tmp/nhl-viewer-backend.log 2>/dev/null; then
            echo -e "${YELLOW}Cause: AWS credentials not configured${NC}"
            echo ""
            echo "The viewer needs AWS credentials to access the database."
            echo "Options:"
            echo "  1. Configure AWS CLI: aws configure"
            echo "  2. Set environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY"
            echo "  3. Use AWS SSO: aws sso login"
        elif grep -q "Connection refused" /tmp/nhl-viewer-backend.log 2>/dev/null; then
            echo -e "${YELLOW}Cause: Database connection refused${NC}"
            echo "Check that PostgreSQL is running and accessible."
        else
            echo "Check logs: tail -20 /tmp/nhl-viewer-backend.log"
        fi
        rm -f "$BACKEND_PID_FILE"
        return 1
    fi
}

start_frontend() {
    echo -e "${YELLOW}Starting NHL Data Viewer Frontend...${NC}"

    cd "$PROJECT_DIR/viewer-frontend"

    # Check if already running
    if [ -f "$FRONTEND_PID_FILE" ] && kill -0 "$(cat "$FRONTEND_PID_FILE")" 2>/dev/null; then
        echo -e "${GREEN}Frontend already running (PID: $(cat "$FRONTEND_PID_FILE"))${NC}"
        return 0
    fi

    # Check if node_modules exists
    if [ ! -d "node_modules" ]; then
        echo -e "${YELLOW}Installing frontend dependencies...${NC}"
        npm install
    fi

    # Start frontend in background
    nohup npm run dev > /tmp/nhl-viewer-frontend.log 2>&1 &
    echo $! > "$FRONTEND_PID_FILE"

    # Wait for startup
    sleep 3

    if kill -0 "$(cat "$FRONTEND_PID_FILE")" 2>/dev/null; then
        echo -e "${GREEN}Frontend started successfully (PID: $(cat "$FRONTEND_PID_FILE"))${NC}"
        echo ""
        echo -e "  ${GREEN}UI:${NC} http://localhost:5173"
        echo ""
        echo -e "  Logs: tail -f /tmp/nhl-viewer-frontend.log"
    else
        echo -e "${RED}Frontend failed to start. Check /tmp/nhl-viewer-frontend.log${NC}"
        return 1
    fi
}

show_status() {
    echo -e "${YELLOW}NHL Data Viewer Status${NC}"
    echo ""

    if [ -f "$BACKEND_PID_FILE" ] && kill -0 "$(cat "$BACKEND_PID_FILE")" 2>/dev/null; then
        echo -e "  Backend:  ${GREEN}Running${NC} (PID: $(cat "$BACKEND_PID_FILE"))"
    else
        echo -e "  Backend:  ${RED}Stopped${NC}"
    fi

    if [ -f "$FRONTEND_PID_FILE" ] && kill -0 "$(cat "$FRONTEND_PID_FILE")" 2>/dev/null; then
        echo -e "  Frontend: ${GREEN}Running${NC} (PID: $(cat "$FRONTEND_PID_FILE"))"
    else
        echo -e "  Frontend: ${RED}Stopped${NC}"
    fi
}

# Main
case "${1:-}" in
    --stop)
        stop_viewer
        ;;
    --full)
        start_backend
        echo ""
        start_frontend
        ;;
    --status)
        show_status
        ;;
    --help)
        echo "NHL Data Viewer Startup Script"
        echo ""
        echo "Usage:"
        echo "  ./scripts/start-viewer.sh           Start backend only"
        echo "  ./scripts/start-viewer.sh --full    Start backend + frontend"
        echo "  ./scripts/start-viewer.sh --stop    Stop all viewer processes"
        echo "  ./scripts/start-viewer.sh --status  Show running status"
        echo ""
        echo "URLs:"
        echo "  Backend API:  http://localhost:8000"
        echo "  Swagger UI:   http://localhost:8000/docs"
        echo "  Frontend UI:  http://localhost:5173 (with --full)"
        ;;
    *)
        start_backend
        ;;
esac
