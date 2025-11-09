#!/bin/bash
# Uninstall 24/7 launchd agents

set -e

LAUNCHD_DIR="$HOME/Library/LaunchAgents"

echo "🔧 Uninstalling 24/7 launchd agents..."

# Unload and remove monitor agent
if [ -f "$LAUNCHD_DIR/com.mastertrader.monitor.plist" ]; then
    launchctl unload "$LAUNCHD_DIR/com.mastertrader.monitor.plist" 2>/dev/null || true
    rm -f "$LAUNCHD_DIR/com.mastertrader.monitor.plist"
    echo "✅ Monitor agent uninstalled"
fi

# Unload and remove optimizer agent
if [ -f "$LAUNCHD_DIR/com.mastertrader.optimizer.plist" ]; then
    launchctl unload "$LAUNCHD_DIR/com.mastertrader.optimizer.plist" 2>/dev/null || true
    rm -f "$LAUNCHD_DIR/com.mastertrader.optimizer.plist"
    echo "✅ Optimizer agent uninstalled"
fi

echo "✅ 24/7 agents uninstalled"

