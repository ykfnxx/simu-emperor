#!/usr/bin/env bash
set -e

SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
PROJECT_ROOT="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
COMPOSE_FILE="$PROJECT_ROOT/docker-compose.yml"

cd "$PROJECT_ROOT"

LOG_DIR="$PROJECT_ROOT/logs"
PID_DIR="$LOG_DIR/pids"
mkdir -p "$LOG_DIR" "$PID_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

docker_compose() {
    docker compose -f "$COMPOSE_FILE" "$@"
}

wait_for_db() {
    log_info "Waiting for database to be ready..."
    log_info "Note: SeekDB takes ~60s to initialize on first run"
    local max_attempts=40
    local attempt=0
    while [ $attempt -lt $max_attempts ]; do
        if docker_compose exec -T seekdb mysql -h127.0.0.1 -P2881 -uroot -proot -e "SELECT 1" 2>/dev/null; then
            log_info "Database is ready!"
            return 0
        fi
        attempt=$((attempt + 1))
        if [ $((attempt % 10)) -eq 0 ]; then
            log_warn "Database not ready yet (attempt $attempt/$max_attempts)..."
        fi
        sleep 3
    done
    log_error "Database failed to start within timeout"
    log_info "Check logs: ./start_v5.sh db-logs"
    return 1
}

start_db() {
    log_info "Starting SeekDB container..."
    log_info "Project root: $PROJECT_ROOT"
    log_info "Compose file: $COMPOSE_FILE"
    
    if docker_compose ps -q seekdb 2>/dev/null | grep -q .; then
        log_info "Database container already running"
        return 0
    fi
    docker_compose up -d seekdb
    wait_for_db
}

stop_db() {
    log_info "Stopping SeekDB container..."
    docker_compose down
}

start_orchestrator() {
    log_info "Starting V5 Orchestrator..."
    
    if [ -f "$PID_DIR/orchestrator.pid" ]; then
        pid=$(cat "$PID_DIR/orchestrator.pid")
        if kill -0 "$pid" 2>/dev/null; then
            log_warn "Orchestrator already running (PID: $pid)"
            return 0
        fi
    fi
    
    nohup uv run simu-emperor --mode orchestrator > "$LOG_DIR/orchestrator.log" 2>&1 &
    echo $! > "$PID_DIR/orchestrator.pid"
    
    sleep 2
    pid=$(cat "$PID_DIR/orchestrator.pid")
    if kill -0 "$pid" 2>/dev/null; then
        log_info "Orchestrator started (PID: $pid)"
        log_info "Logs: $LOG_DIR/orchestrator.log"
        log_info "API: http://localhost:8000"
    else
        log_error "Orchestrator failed to start. Check logs: $LOG_DIR/orchestrator.log"
        return 1
    fi
}

stop_orchestrator() {
    log_info "Stopping Orchestrator..."
    if [ -f "$PID_DIR/orchestrator.pid" ]; then
        pid=$(cat "$PID_DIR/orchestrator.pid")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
        fi
        rm -f "$PID_DIR/orchestrator.pid"
    fi
    log_info "Orchestrator stopped"
}

show_status() {
    echo ""
    echo "=== V5 Service Status ==="
    echo ""
    
    echo "Docker containers:"
    docker_compose ps 2>/dev/null || echo "  No containers running"
    echo ""
    
    echo "Orchestrator:"
    if [ -f "$PID_DIR/orchestrator.pid" ]; then
        pid=$(cat "$PID_DIR/orchestrator.pid")
        if kill -0 "$pid" 2>/dev/null; then
            echo "  ✓ Running (PID: $pid)"
        else
            echo "  ✗ Stopped (stale PID file)"
        fi
    else
        echo "  - Not started"
    fi
    echo ""
    
    echo "Recent logs:"
    if [ -f "$LOG_DIR/orchestrator.log" ]; then
        tail -15 "$LOG_DIR/orchestrator.log"
    else
        echo "  No logs available"
    fi
}

show_logs() {
    if [ -f "$LOG_DIR/orchestrator.log" ]; then
        tail -f "$LOG_DIR/orchestrator.log"
    else
        log_error "No log file found at $LOG_DIR/orchestrator.log"
    fi
}

usage() {
    cat << 'EOF'
V5 Emperor Simulator - Startup Script

Usage: ./start_v5.sh <command>

Commands:
    start       Start database and orchestrator (default)
    stop        Stop all services
    restart     Restart all services
    status      Show service status
    logs        Follow orchestrator logs
    db-start    Start only the database
    db-stop     Stop only the database
    db-logs     Follow database logs
    help        Show this help message

Examples:
    ./start_v5.sh start        # Start everything
    ./start_v5.sh status       # Check status
    ./start_v5.sh logs         # Follow logs
EOF
}

case "${1:-start}" in
    start)
        start_db && start_orchestrator
        ;;
    stop)
        stop_orchestrator
        stop_db
        ;;
    restart)
        stop_orchestrator
        stop_db
        sleep 2
        start_db && start_orchestrator
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    db-start)
        start_db
        ;;
    db-stop)
        stop_db
        ;;
    db-logs)
        docker_compose logs -f seekdb
        ;;
    help|*)
        usage
        ;;
esac
