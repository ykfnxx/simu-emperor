#!/bin/bash
# Start the simu-emperor backend server and (optionally) the frontend dev server.
#
# Usage:
#   ./scripts/start.sh              # backend only
#   ./scripts/start.sh --with-web   # backend + frontend

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

# Ensure .env exists
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        echo "No .env found — copying from .env.example"
        cp .env.example .env
    else
        echo "Warning: no .env file found. Using defaults."
    fi
fi

# Ensure data directories exist
mkdir -p data/db data/agents data/agent_templates

# Sync dependencies
echo "Syncing dependencies..."
uv sync --quiet

# Ensure data/memory directory exists for dual-write
mkdir -p data/memory

# Start backend
echo "Starting backend server..."
if [ "$1" = "--with-web" ]; then
    # Start backend in background with logs piped to a file AND terminal
    LOGFILE="data/server.log"
    uv run simu-emperor 2>&1 | tee "$LOGFILE" &
    BACKEND_PID=$!
    echo "Backend PID: $BACKEND_PID (logs: $LOGFILE)"

    # Wait briefly for backend to start
    sleep 2

    # Start frontend
    echo "Starting frontend dev server..."
    cd web
    npm install --silent
    npm run dev

    # Clean up backend when frontend exits
    kill $BACKEND_PID 2>/dev/null
else
    uv run simu-emperor
fi
