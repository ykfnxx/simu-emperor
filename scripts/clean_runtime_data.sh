#!/bin/bash
# Clean runtime-generated data files and logs (V5 architecture).
# Usage: ./scripts/clean_runtime_data.sh [--dry-run]

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

DRY_RUN=false
if [ "$1" = "--dry-run" ]; then
    DRY_RUN=true
    echo -e "${YELLOW}=== Dry run: showing files that would be deleted ===${NC}\n"
fi

cleanup() {
    local file="$1"
    local desc="$2"
    if [ -e "$file" ]; then
        if [ "$DRY_RUN" = true ]; then
            echo -e "${YELLOW}[dry-run]${NC} would delete: $file ($desc)"
        else
            rm -rf "$file"
            echo -e "${GREEN}✓${NC} deleted: $file ($desc)"
        fi
    fi
}

echo -e "${RED}=== Cleaning V5 runtime data ===${NC}\n"

echo "1. Server database:"
cleanup "data/db" "Server SQLite database (server.db + group_chats.json)"

echo -e "\n2. Agent runtime data:"
cleanup "data/agents" "Agent config & tape data (copied from default_agents on startup)"

echo -e "\n3. Memory dual-write:"
cleanup "data/memory" "JSONL message logs & tape_meta index"

echo -e "\n4. Logs:"
cleanup "data/server.log" "Server log (from start.sh)"
cleanup "data/logs" "Data directory logs"
cleanup "logs" "Root directory logs"

echo -e "\n5. Python caches:"
find . -type d -name "__pycache__" -not -path "./web/*" -not -path "./.venv/*" | while read d; do
    cleanup "$d" "Python bytecode cache"
done
cleanup ".pytest_cache" "Pytest cache"
cleanup ".ruff_cache" "Ruff cache"

echo -e "\n${GREEN}=== Clean complete ===${NC}"

echo -e "\n${YELLOW}=== Preserved ===${NC}"
echo "  data/default_agents/     - Default agent definitions"
echo "  data/agent_templates/    - Agent templates"
echo "  data/initial_state.json  - Initial game state"
echo "  data/event_templates.json - Event templates"
echo "  data/skills/             - Skill definitions"
echo "  .env                     - Configuration"
echo "  packages/                - Source code"
echo "  tests/                   - Tests"
echo "  web/                     - Frontend"
