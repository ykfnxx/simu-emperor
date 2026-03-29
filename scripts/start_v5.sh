#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

usage() {
    cat << 'EOF'
V5 Emperor Simulator - Startup Script

Usage: ./scripts/start_v5.sh [MODE] [OPTIONS]

Modes:
    orchestrator   Start all services via Python orchestrator (default)
    gateway        Start only the gateway process
    engine         Start only the engine process
    worker         Start only the worker process (requires --agent-id)
    status         Check service status
    stop           Stop all running services
    test           Run the V5 e2e integration tests
    help           Show this help message

Options:
    --agent-id ID       Agent ID for worker mode (required for worker mode)
    --port PORT         Gateway port (default: 8000)
    --tick INTERVAL     Tick interval in seconds (default: 5.0)
    --log-level LEVEL   Log level: DEBUG, INFO, WARNING (default: INFO)
    --detach, -d        Run in background

Examples:
    ./scripts/start_v5.sh orchestrator
    ./scripts/start_v5.sh worker --agent-id governor_zhili
    ./scripts/start_v5.sh status
    ./scripts/start_v5.sh stop
EOF
}

LOG_DIR="$PROJECT_ROOT/logs"
PID_DIR="$LOG_DIR/pids"
mkdir -p "$LOG_DIR" "$PID_DIR"

GATEWAY_PORT=8000
TICK_INTERVAL=5.0
LOG_LEVEL="INFO"
DETACH=false
MODE="orchestrator"
AGENT_ID=""

while [[ $# -gt 0 ]]; do
    case $1 in
        orchestrator|gateway|engine|worker|status|stop|test|help)
            MODE="$1"
            shift
            ;;
        --agent-id)
            AGENT_ID="$2"
            shift 2
            ;;
        --port)
            GATEWAY_PORT="$2"
            shift 2
            ;;
        --tick)
            TICK_INTERVAL="$2"
            shift 2
            ;;
        --log-level)
            LOG_LEVEL="$2"
            shift 2
            ;;
        --detach|-d)
            DETACH=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

if [[ "$MODE" == "help" ]]; then
    usage
    exit 0
fi

if [[ "$MODE" == "worker" ]] && [[ -z "$AGENT_ID" ]]; then
    echo "Error: --agent-id is required for worker mode"
    usage
    exit 1
fi

run_orchestrator() {
    echo "Starting V5 Emperor Simulator (orchestrator mode)..."
    
    if [[ "$DETACH" == "true" ]]; then
        nohup uv run simu-emperor --mode orchestrator --port "$GATEWAY_PORT" --tick-interval "$TICK_INTERVAL" > "$LOG_DIR/orchestrator.log" 2>&1 &
        echo $! > "$PID_DIR/orchestrator.pid"
        echo "Started in background. PID: $(cat $PID_DIR/orchestrator.pid)"
        echo "Logs: $LOG_DIR/orchestrator.log"
    else
        uv run simu-emperor --mode orchestrator --port "$GATEWAY_PORT" --tick-interval "$TICK_INTERVAL"
    fi
}

run_gateway() {
    echo "Starting Gateway process..."
    
    if [[ "$DETACH" == "true" ]]; then
        nohup uv run simu-emperor --mode gateway --port "$GATEWAY_PORT" > "$LOG_DIR/gateway.log" 2>&1 &
        echo $! > "$PID_DIR/gateway.pid"
        echo "Started in background. PID: $(cat $PID_DIR/gateway.pid)"
    else
        uv run simu-emperor --mode gateway --port "$GATEWAY_PORT"
    fi
}

run_engine() {
    echo "Starting Engine process..."
    
    if [[ "$DETACH" == "true" ]]; then
        nohup uv run simu-emperor --mode engine --tick-interval "$TICK_INTERVAL" > "$LOG_DIR/engine.log" 2>&1 &
        echo $! > "$PID_DIR/engine.pid"
        echo "Started in background. PID: $(cat $PID_DIR/engine.pid)"
    else
        uv run simu-emperor --mode engine --tick-interval "$TICK_INTERVAL"
    fi
}

run_worker() {
    echo "Starting Worker process for agent: $AGENT_ID..."
    
    if [[ "$DETACH" == "true" ]]; then
        nohup uv run simu-emperor --mode worker --agent-id "$AGENT_ID" > "$LOG_DIR/worker-$AGENT_ID.log" 2>&1 &
        echo $! > "$PID_DIR/worker-$AGENT_ID.pid"
        echo "Started in background. PID: $(cat $PID_DIR/worker-$AGENT_ID.pid)"
    else
        uv run simu-emperor --mode worker --agent-id "$AGENT_ID"
    fi
}

check_status() {
    echo "Checking V5 service status..."
    
    if [[ -f "$PID_DIR/orchestrator.pid" ]]; then
        pid=$(cat "$PID_DIR/orchestrator.pid")
        if kill -0 "$pid" 2>/dev/null; then
            echo "✓ Orchestrator running (PID: $pid)"
        else
            echo "✗ Orchestrator not running"
        fi
    else
        echo "- Orchestrator not started"
    fi
    
    if [[ -f "$PID_DIR/gateway.pid" ]]; then
        pid=$(cat "$PID_DIR/gateway.pid")
        if kill -0 "$pid" 2>/dev/null; then
            echo "✓ Gateway running (PID: $pid)"
        else
            echo "✗ Gateway not running"
        fi
    else
        echo "- Gateway not started"
    fi
    
    if [[ -f "$PID_DIR/engine.pid" ]]; then
        pid=$(cat "$PID_DIR/engine.pid")
        if kill -0 "$pid" 2>/dev/null; then
            echo "✓ Engine running (PID: $pid)"
        else
            echo "✗ Engine not running"
        fi
    else
        echo "- Engine not started"
    fi
}

stop_services() {
    echo "Stopping V5 services..."
    
    for pidfile in "$PID_DIR"/*.pid; do
        if [[ -f "$pidfile" ]]; then
            pid=$(cat "$pidfile")
            if kill -0 "$pid" 2>/dev/null; then
                kill "$pid"
                echo "Stopped PID $pid"
            fi
            rm -f "$pidfile"
        fi
    done
    
    echo "All services stopped"
}

run_tests() {
    echo "Running V5 integration tests..."
    uv run pytest tests/integration/test_v5_e2e.py -v
}

case "$MODE" in
    orchestrator)
        run_orchestrator
        ;;
    gateway)
        run_gateway
        ;;
    engine)
        run_engine
        ;;
    worker)
        run_worker
        ;;
    status)
        check_status
        ;;
    stop)
        stop_services
        ;;
    test)
        run_tests
        ;;
    *)
        echo "Unknown mode: $MODE"
        usage
        exit 1
        ;;
esac
