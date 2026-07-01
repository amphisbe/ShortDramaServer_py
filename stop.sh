#!/bin/bash
# ============================================
# Short Drama Server — 关闭脚本
# 优雅终止 (SIGTERM)，超时后强制 kill (SIGKILL)
# ============================================

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$PROJECT_DIR/runtime/server.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "[INFO] 未找到 PID 文件，尝试通过端口查找..."
    PID=$(lsof -ti:9011 2>/dev/null || true)
    if [ -z "$PID" ]; then
        echo "[INFO] 未发现运行中的服务器"
        exit 0
    fi
else
    PID=$(cat "$PID_FILE")
fi

if ! kill -0 "$PID" 2>/dev/null; then
    echo "[INFO] 进程 $PID 已不存在，清理 PID 文件"
    rm -f "$PID_FILE"
    exit 0
fi

echo "[INFO] 正在关闭服务器 (PID: $PID)..."
kill "$PID"

# 等待最多 10 秒
for i in $(seq 1 10); do
    if ! kill -0 "$PID" 2>/dev/null; then
        echo "[OK] 服务器已关闭"
        rm -f "$PID_FILE"
        exit 0
    fi
    sleep 1
done

echo "[WARN] 正常关闭超时，强制终止..."
kill -9 "$PID" 2>/dev/null || true
rm -f "$PID_FILE"
echo "[OK] 服务器已强制关闭"
