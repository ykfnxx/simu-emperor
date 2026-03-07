#!/bin/bash

# 如果用户用 `sh start-web.sh ...` 调用，或当前是 bash POSIX 模式，自动切回 bash 执行。
if [ -z "${BASH_VERSION:-}" ] || (set -o 2>/dev/null | grep -Eq '^posix[[:space:]]+on$'); then
    exec /bin/bash "$0" "$@"
fi

set -euo pipefail

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

LOG_DIR="$SCRIPT_DIR/logs"
BACKEND_LOG_DIR="$LOG_DIR/backend"
FRONTEND_LOG_DIR="$LOG_DIR/frontend"
LAUNCHER_LOG_DIR="$LOG_DIR/launcher"
PID_DIR="$LOG_DIR/pids"

mkdir -p "$BACKEND_LOG_DIR" "$FRONTEND_LOG_DIR" "$LAUNCHER_LOG_DIR" "$PID_DIR"

MODE=${1:-dev}
TS="$(date +%Y%m%d-%H%M%S)"
LAUNCHER_LOG="$LAUNCHER_LOG_DIR/launcher-$TS.log"

log_info() {
    local msg="$1"
    echo -e "${GREEN}[INFO]${NC} $msg"
    echo "[INFO] $msg" >> "$LAUNCHER_LOG"
}

log_warn() {
    local msg="$1"
    echo -e "${YELLOW}[WARN]${NC} $msg"
    echo "[WARN] $msg" >> "$LAUNCHER_LOG"
}

log_error() {
    local msg="$1"
    echo -e "${RED}[ERROR]${NC} $msg"
    echo "[ERROR] $msg" >> "$LAUNCHER_LOG"
}

print_banner() {
    echo -e "${BLUE}======================================${NC}"
    echo -e "${BLUE}   皇帝模拟器 V2 - Web 启动脚本${NC}"
    echo -e "${BLUE}======================================${NC}"
    echo ""
    echo -e "${GREEN}日志根目录:${NC} $LOG_DIR"
    echo -e "${GREEN}分类日志目录:${NC}"
    echo "  - $BACKEND_LOG_DIR"
    echo "  - $FRONTEND_LOG_DIR"
    echo "  - $LAUNCHER_LOG_DIR"
    echo "  - $PID_DIR"
    echo -e "${GREEN}启动日志:${NC} $LAUNCHER_LOG"
    echo ""
}

usage() {
    cat <<USAGE
用法: ./start-web.sh [模式]

模式:
  dev       后台启动前端(dev) + 后端
  backend   仅后台启动后端
  frontend  仅后台启动前端(dev)
  build     构建前端后，仅后台启动后端
  status    查看前后端进程状态
  stop      停止前后端后台进程

说明:
  - 所有服务均以后台方式启动，不占用当前终端。
  - 回显分类输出到 logs 目录：
    backend stdout/stderr -> logs/backend/
    frontend stdout/stderr -> logs/frontend/
    启动脚本日志         -> logs/launcher/
USAGE
}

check_command() {
    local cmd="$1"
    if ! command -v "$cmd" &> /dev/null; then
        log_error "缺少命令: $cmd"
        exit 1
    fi
}

is_pid_running() {
    local pid="$1"
    kill -0 "$pid" 2>/dev/null
}

read_pid() {
    local pid_file="$1"
    if [ -f "$pid_file" ]; then
        cat "$pid_file"
    else
        echo ""
    fi
}

write_pid() {
    local pid_file="$1"
    local pid="$2"
    echo "$pid" > "$pid_file"
}

clear_pid_if_stale() {
    local pid_file="$1"
    local name="$2"
    local pid
    pid=$(read_pid "$pid_file")
    if [ -n "$pid" ] && ! is_pid_running "$pid"; then
        rm -f "$pid_file"
        log_warn "$name PID 文件存在但进程不存在，已清理: $pid_file"
    fi
}

check_frontend_deps() {
    log_info "检查前端依赖..."
    if [ ! -d "web/node_modules" ]; then
        log_warn "未检测到 web/node_modules，执行 npm install"
        (cd web && npm install)
    fi
}

check_backend_deps() {
    log_info "检查后端依赖..."
    if ! uv run python -c "import fastapi" >/dev/null 2>&1; then
        log_warn "后端依赖不完整，执行 uv sync"
        uv sync
    fi
}

check_backend_port() {
    local port=${1:-8000}

    if ! command -v lsof &> /dev/null; then
        log_warn "未检测到 lsof，跳过端口占用检查"
        return
    fi

    local pids
    pids=$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
    if [ -n "$pids" ]; then
        log_error "端口 $port 已被占用，无法启动后端"
        log_error "占用 PID: $pids"
        exit 1
    fi
}

wait_backend_ready() {
    local timeout=${1:-20}
    local url="http://localhost:8000/api/health"

    if ! command -v curl &> /dev/null; then
        log_warn "未检测到 curl，跳过后端就绪等待"
        return 0
    fi

    for ((i=1; i<=timeout; i++)); do
        if curl -fsS "$url" > /dev/null 2>&1; then
            log_info "后端已就绪: $url"
            return 0
        fi
        sleep 1
    done

    log_warn "后端在 ${timeout}s 内未就绪，前端可能出现临时 ECONNREFUSED"
    return 1
}

start_backend_bg() {
    local pid_file="$PID_DIR/backend.pid"
    clear_pid_if_stale "$pid_file" "backend"

    local old_pid
    old_pid=$(read_pid "$pid_file")
    if [ -n "$old_pid" ] && is_pid_running "$old_pid"; then
        log_warn "后端已在运行，PID=$old_pid"
        return
    fi

    local stamp out_log err_log
    stamp="$(date +%Y%m%d-%H%M%S)"
    out_log="$BACKEND_LOG_DIR/backend-$stamp.out.log"
    err_log="$BACKEND_LOG_DIR/backend-$stamp.err.log"

    log_info "后台启动后端..."
    (
        cd "$SCRIPT_DIR"
        nohup uv run simu-emperor web >"$out_log" 2>"$err_log" &
        echo $! > "$pid_file"
    )

    local pid
    pid=$(read_pid "$pid_file")
    log_info "后端已启动，PID=$pid"
    log_info "后端 stdout: $out_log"
    log_info "后端 stderr: $err_log"
}

start_frontend_bg() {
    local pid_file="$PID_DIR/frontend.pid"
    clear_pid_if_stale "$pid_file" "frontend"

    local old_pid
    old_pid=$(read_pid "$pid_file")
    if [ -n "$old_pid" ] && is_pid_running "$old_pid"; then
        log_warn "前端已在运行，PID=$old_pid"
        return
    fi

    local stamp out_log err_log
    stamp="$(date +%Y%m%d-%H%M%S)"
    out_log="$FRONTEND_LOG_DIR/frontend-$stamp.out.log"
    err_log="$FRONTEND_LOG_DIR/frontend-$stamp.err.log"

    log_info "后台启动前端(dev)..."
    (
        cd "$SCRIPT_DIR/web"
        nohup npm run dev >"$out_log" 2>"$err_log" &
        echo $! > "$pid_file"
    )

    local pid
    pid=$(read_pid "$pid_file")
    log_info "前端已启动，PID=$pid"
    log_info "前端 stdout: $out_log"
    log_info "前端 stderr: $err_log"
}

stop_service() {
    local name="$1"
    local pid_file="$2"

    local pid
    pid=$(read_pid "$pid_file")

    if [ -z "$pid" ]; then
        log_warn "$name 未运行（无 PID 文件）"
        return
    fi

    if is_pid_running "$pid"; then
        kill "$pid" || true
        sleep 1
        if is_pid_running "$pid"; then
            kill -9 "$pid" || true
        fi
        log_info "$name 已停止，PID=$pid"
    else
        log_warn "$name PID=$pid 不存在，视为已停止"
    fi

    rm -f "$pid_file"
}

show_status() {
    local backend_pid_file="$PID_DIR/backend.pid"
    local frontend_pid_file="$PID_DIR/frontend.pid"

    clear_pid_if_stale "$backend_pid_file" "backend"
    clear_pid_if_stale "$frontend_pid_file" "frontend"

    local backend_pid frontend_pid
    backend_pid=$(read_pid "$backend_pid_file")
    frontend_pid=$(read_pid "$frontend_pid_file")

    echo ""
    echo "服务状态:"

    if [ -n "$backend_pid" ] && is_pid_running "$backend_pid"; then
        echo "  backend : running (PID=$backend_pid)"
    else
        echo "  backend : stopped"
    fi

    if [ -n "$frontend_pid" ] && is_pid_running "$frontend_pid"; then
        echo "  frontend: running (PID=$frontend_pid)"
    else
        echo "  frontend: stopped"
    fi

    echo ""
    echo "PID 文件目录: $PID_DIR"
    echo "日志目录: $LOG_DIR"
}

main() {
    print_banner

    if [[ "$MODE" == "--help" ]] || [[ "$MODE" == "-h" ]]; then
        usage
        exit 0
    fi

    case "$MODE" in
        dev)
            check_command npm
            check_command uv
            check_frontend_deps
            check_backend_deps
            check_backend_port 8000

            start_backend_bg
            wait_backend_ready 20 || true
            start_frontend_bg

            log_info "开发模式服务已后台启动。"
            show_status
            ;;

        backend)
            check_command uv
            check_backend_deps
            check_backend_port 8000
            start_backend_bg
            wait_backend_ready 20 || true
            show_status
            ;;

        frontend)
            check_command npm
            check_frontend_deps
            start_frontend_bg
            show_status
            ;;

        build)
            check_command npm
            check_command uv
            check_frontend_deps
            check_backend_deps
            check_backend_port 8000

            local build_out build_err
            build_out="$FRONTEND_LOG_DIR/frontend-build-$TS.out.log"
            build_err="$FRONTEND_LOG_DIR/frontend-build-$TS.err.log"
            log_info "构建前端..."
            (
                cd "$SCRIPT_DIR/web"
                npm run build >"$build_out" 2>"$build_err"
            )
            log_info "前端构建完成"
            log_info "构建 stdout: $build_out"
            log_info "构建 stderr: $build_err"

            start_backend_bg
            wait_backend_ready 20 || true
            show_status
            ;;

        stop)
            stop_service "frontend" "$PID_DIR/frontend.pid"
            stop_service "backend" "$PID_DIR/backend.pid"
            show_status
            ;;

        status)
            show_status
            ;;

        *)
            log_error "未知模式: $MODE"
            usage
            exit 1
            ;;
    esac
}

main "$@"
