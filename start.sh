#!/bin/bash

# 一键启动 simu-emperor 前后端

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 清理函数
cleanup() {
    echo ""
    echo "正在停止服务..."
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null || true
    fi
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null || true
    fi
    exit 0
}

trap cleanup SIGINT SIGTERM

echo "=========================================="
echo "  Simu Emperor - 一键启动"
echo "=========================================="

# 清除运行时临时文件
echo "[0/2] 清除运行时临时文件..."
rm -rf data/log/* data/saves/* 2>/dev/null || true

# 提示清理前端缓存
echo "提示: 如需清除前端缓存，请在浏览器中清除 localStorage（开发者工具 > Application > Local Storage）"

# 启动后端
echo "[1/2] 启动后端服务 (端口 8000)..."
uv run simu-emperor &
BACKEND_PID=$!

# 等待后端启动
sleep 2

# 启动前端
echo "[2/2] 启动前端服务 (端口 5173)..."
cd frontend && npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "=========================================="
echo "  服务已启动!"
echo "  后端: http://localhost:8000"
echo "  前端: http://localhost:5173"
echo "  按 Ctrl+C 停止所有服务"
echo "=========================================="

# 等待任一进程退出
wait
