#!/bin/bash
# Install 24/7 launchd agents so system survives reboots
# This makes the system truly 24/7 - runs even after reboot

set -e

REPO_DIR="${REPO_DIR:-$HOME/Downloads/trader}"
LAUNCHD_DIR="$HOME/Library/LaunchAgents"

echo "🔧 Installing 24/7 launchd agents..."

# Create LaunchAgents directory if it doesn't exist
mkdir -p "$LAUNCHD_DIR"

# Install monitor agent
if [ -f "$REPO_DIR/launchd/com.mastertrader.monitor.plist" ]; then
    cp "$REPO_DIR/launchd/com.mastertrader.monitor.plist" "$LAUNCHD_DIR/"
    # Replace ${HOME} with actual home directory
    sed -i '' "s|\${HOME}|$HOME|g" "$LAUNCHD_DIR/com.mastertrader.monitor.plist" 2>/dev/null || \
    sed -i "s|\${HOME}|$HOME|g" "$LAUNCHD_DIR/com.mastertrader.monitor.plist" 2>/dev/null || true
    
    launchctl unload "$LAUNCHD_DIR/com.mastertrader.monitor.plist" 2>/dev/null || true
    launchctl load "$LAUNCHD_DIR/com.mastertrader.monitor.plist"
    echo "✅ Monitor agent installed (survives reboots)"
fi

# Install optimizer agent
if [ -f "$REPO_DIR/launchd/com.mastertrader.optimizer.plist" ]; then
    cp "$REPO_DIR/launchd/com.mastertrader.optimizer.plist" "$LAUNCHD_DIR/"
    # Replace ${HOME} with actual home directory
    sed -i '' "s|\${HOME}|$HOME|g" "$LAUNCHD_DIR/com.mastertrader.optimizer.plist" 2>/dev/null || \
    sed -i "s|\${HOME}|$HOME|g" "$LAUNCHD_DIR/com.mastertrader.optimizer.plist" 2>/dev/null || true
    
    launchctl unload "$LAUNCHD_DIR/com.mastertrader.optimizer.plist" 2>/dev/null || true
    launchctl load "$LAUNCHD_DIR/com.mastertrader.optimizer.plist"
    echo "✅ Optimizer agent installed (survives reboots)"
fi

echo ""
echo "✅ 24/7 agents installed!"
echo "   System will now run even after reboots"
echo ""
echo "Check status: launchctl list | grep mastertrader"
echo "Uninstall: bash scripts/uninstall_24_7.sh"

