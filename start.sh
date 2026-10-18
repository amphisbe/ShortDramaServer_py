#!/bin/bash
# ============================================
# Short Drama Server — 启动脚本
# 以后台方式启动 uvicorn，PID 写入 runtime/server.pid
# ============================================

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$PROJECT_DIR/runtime/server.pid"
LOG_DIR="$PROJECT_DIR/logs"

cd "$PROJECT_DIR"

# 检查是否已运行
if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "[WARN] 服务器似乎已在运行 (PID: $(cat "$PID_FILE"))"
    echo "       如需重启请执行 ./restart.sh"
    exit 1
fi

# 创建必要目录
mkdir -p "$LOG_DIR" runtime

# 激活虚拟环境并启动
source venv/bin/activate

echo "[INFO] 启动 Short Drama Server..."
nohup uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 9011 \
    --log-level info \
    > "$LOG_DIR/server.log" 2>&1 &

PID=$!
echo $PID > "$PID_FILE"

sleep 1
if kill -0 "$PID" 2>/dev/null; then
    echo "[OK] 服务器已启动 (PID: $PID, 端口: 9011)"
else
    echo "[ERROR] 服务器启动失败，请查看日志: $LOG_DIR/server.log"
    rm -f "$PID_FILE"
    exit 1
fi
