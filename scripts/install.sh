#!/bin/bash
# Eathy 自动化服务安装脚本
# 安装 MCP 服务 + 调度器到 macOS launchd

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LAUNCHD_DIR="$PROJECT_DIR/launchd"
LOG_DIR="$PROJECT_DIR/data/logs"
PLIST_TARGET="$HOME/Library/LaunchAgents"

echo "═══════════════════════════════════════════"
echo "  Eathy 自动化服务安装"
echo "═══════════════════════════════════════════"
echo ""
echo "项目目录: $PROJECT_DIR"
echo ""

# 创建日志目录
mkdir -p "$LOG_DIR"

# 创建 LaunchAgents 目录（如果不存在）
mkdir -p "$PLIST_TARGET"

# 停止已有服务（忽略错误）
echo "→ 停止已有服务..."
launchctl unload "$PLIST_TARGET/com.eathy.mcp.plist" 2>/dev/null || true
launchctl unload "$PLIST_TARGET/com.eathy.scheduler.plist" 2>/dev/null || true

# 复制 plist 文件
echo "→ 安装 launchd 配置..."
cp "$LAUNCHD_DIR/com.eathy.mcp.plist" "$PLIST_TARGET/"
cp "$LAUNCHD_DIR/com.eathy.scheduler.plist" "$PLIST_TARGET/"

# 加载服务
echo "→ 启动 MCP 服务..."
launchctl load "$PLIST_TARGET/com.eathy.mcp.plist"

echo "→ 等待 MCP 服务就绪..."
sleep 3

echo "→ 启动调度器..."
launchctl load "$PLIST_TARGET/com.eathy.scheduler.plist"

echo ""
echo "═══════════════════════════════════════════"
echo "  ✅ 安装完成！"
echo ""
echo "  MCP 服务:  launchctl list | grep eathy.mcp"
echo "  调度器:    launchctl list | grep eathy.scheduler"
echo "  日志目录:  $LOG_DIR"
echo ""
echo "  查看调度日志:"
echo "    tail -f $LOG_DIR/scheduler.log"
echo ""
echo "  卸载服务:"
echo "    bash $SCRIPT_DIR/uninstall.sh"
echo "═══════════════════════════════════════════"
