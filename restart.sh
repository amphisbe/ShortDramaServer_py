#!/bin/bash
# ============================================
# Short Drama Server — 重启脚本
# ============================================

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=========================================="
echo "  Short Drama Server — 重启"
echo "=========================================="

echo ""
echo "[1/2] 关闭现有服务..."
bash "$PROJECT_DIR/stop.sh"

echo ""
echo "[2/2] 启动服务..."
bash "$PROJECT_DIR/start.sh"
