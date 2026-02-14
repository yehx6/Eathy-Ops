#!/bin/bash
# Eathy 自动化服务卸载脚本

set -e

PLIST_TARGET="$HOME/Library/LaunchAgents"

echo "═══════════════════════════════════════════"
echo "  Eathy 自动化服务卸载"
echo "═══════════════════════════════════════════"
echo ""

echo "→ 停止调度器..."
launchctl unload "$PLIST_TARGET/com.eathy.scheduler.plist" 2>/dev/null || true

echo "→ 停止 MCP 服务..."
launchctl unload "$PLIST_TARGET/com.eathy.mcp.plist" 2>/dev/null || true

echo "→ 删除 plist 文件..."
rm -f "$PLIST_TARGET/com.eathy.mcp.plist"
rm -f "$PLIST_TARGET/com.eathy.scheduler.plist"

echo ""
echo "✅ 卸载完成！服务已停止并移除。"
echo "   日志文件保留在 data/logs/ 目录中。"
