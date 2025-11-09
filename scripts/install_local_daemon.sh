#!/usr/bin/env bash
set -euo pipefail

echo "[install] master-trader local autostart"

REPO_DIR="${REPO_DIR:-$HOME/Downloads/trader}"
PLIST_SRC="${REPO_DIR}/launchd/com.mastertrader.stack.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.mastertrader.stack.plist"

PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

# Ensure Homebrew
if ! command -v brew >/dev/null 2>&1; then
  echo "[install] installing Homebrew..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  eval "$(/opt/homebrew/bin/brew shellenv)" || true
  eval "$(/usr/local/bin/brew shellenv)" || true
fi

# Tools
brew list --versions jq >/dev/null 2>&1 || brew install jq

# Docker Desktop (skip if already installed)
if [ -d "/Applications/Docker.app" ]; then
  echo "[install] Docker.app detected; skipping install."
else
  brew install --cask docker || true
fi

# Start Docker Desktop and wait for engine
open -ga Docker || true
echo "[install] waiting for Docker engine..."
for i in $(seq 1 60); do
  if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    echo "[install] Docker is ready."
    break
  fi
  sleep 2
done

mkdir -p "$(dirname "${PLIST_DST}")"
cp -f "${PLIST_SRC}" "${PLIST_DST}"

# Load/Reload launch agent idempotently
launchctl unload "${PLIST_DST}" >/dev/null 2>&1 || true
launchctl load "${PLIST_DST}"
launchctl start com.mastertrader.stack || true

echo "[install] loaded com.mastertrader.stack"
echo "[install] logs: ${HOME}/Library/Logs/master-trader/daemon.log"
echo "[install] to view live logs: tail -f ${HOME}/Library/Logs/master-trader/daemon.log"


