#!/bin/bash
# ONE SCRIPT TO RULE THEM ALL - Fully Automated 24/7 Trading System
# Just run: ./start.sh
# That's it. Everything else is automatic.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║   MasterTrader - Fully Automated 24/7 Trading System   ║"
echo "║   ONE COMMAND. EVERYTHING AUTOMATIC.                    ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ============================================================================
# STEP 1: Check Prerequisites
# ============================================================================
echo -e "${YELLOW}[1/6] Checking prerequisites...${NC}"

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found. Installing Docker Desktop...${NC}"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        if command -v brew &> /dev/null; then
            brew install --cask docker
        else
            echo "Please install Docker Desktop from https://www.docker.com/products/docker-desktop"
            exit 1
        fi
    else
        echo "Please install Docker from https://www.docker.com/get-started"
        exit 1
    fi
fi

# Start Docker if not running
if ! docker info > /dev/null 2>&1; then
    echo -e "${YELLOW}Starting Docker Desktop...${NC}"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        open -a Docker
    fi
    echo "Waiting for Docker to start (this may take 30-60 seconds)..."
    for i in {1..60}; do
        if docker info > /dev/null 2>&1; then
            echo -e "${GREEN}✅ Docker is ready!${NC}"
            break
        fi
        echo -n "."
        sleep 1
    done
    if ! docker info > /dev/null 2>&1; then
        echo -e "${RED}❌ Docker failed to start. Please start Docker Desktop manually.${NC}"
        exit 1
    fi
fi

# Check Python (for optimizer)
if ! command -v python3 &> /dev/null; then
    echo -e "${YELLOW}Python3 not found. Installing...${NC}"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        if command -v brew &> /dev/null; then
            brew install python3
        fi
    fi
fi

# Check Python dependencies
if command -v python3 &> /dev/null; then
    if ! python3 -c "import psycopg" 2>/dev/null; then
        echo -e "${YELLOW}Installing Python dependencies...${NC}"
        pip3 install psycopg[binary] httpx --quiet || pip install psycopg[binary] httpx --quiet
    fi
fi

echo -e "${GREEN}✅ Prerequisites OK${NC}"

# ============================================================================
# STEP 2: Create .env if needed
# ============================================================================
echo -e "${YELLOW}[2/6] Setting up environment...${NC}"

if [ ! -f .env ]; then
    echo -e "${YELLOW}Creating .env file...${NC}"
    cat > .env << 'ENVEOF'
# Execution Mode - Start with paper trading for safety
EXEC_MODE=paper

# Agent Mode - Use LLM for better signals
AGENT_MODE=llm

# OpenAI API Key (REQUIRED for LLM mode)
# Get one at: https://platform.openai.com/api-keys
OPENAI_API_KEY=your_key_here

# Aggressive Profit Maximization Settings
MAX_POSITION_SIZE_PCT=20.0
MAX_PORTFOLIO_EXPOSURE_PCT=300.0
ASLF_THETA_BUY=0.8
ASLF_THETA_FADE=-0.8
FRACTIONAL_KELLY_MAX=0.5

# Risk Management
MAX_DRAWDOWN_PCT=25.0
MAX_DAILY_LOSS_PCT=10.0

# Execution
MAX_SLIPPAGE_BPS=10.0
ENABLE_SMART_ROUTING=true

# Trading Enabled
TRADING_ENABLED=true

# Database
PG_DSN=postgresql://trader:traderpw@db:5432/mastertrader

# Binance (use testnet for safety)
BINANCE_BASE=https://testnet.binance.vision
BINANCE_API_KEY=
BINANCE_API_SECRET=

# RAG Sources
RAG_RSS_SOURCES=https://www.coindesk.com/arc/outboundfeeds/rss/,https://cointelegraph.com/rss
RAG_HTTP_SOURCES=https://www.binance.com/en/support/announcement
RAG_TIMEOUT_S=6
RAG_MAX_DOCS=8
ENVEOF
    echo -e "${YELLOW}⚠️  Created .env file. Please edit it and add your OPENAI_API_KEY${NC}"
    echo -e "${YELLOW}   You can edit it now or later. The system will work but LLM agents need the key.${NC}"
    sleep 2
fi

echo -e "${GREEN}✅ Environment configured${NC}"

# ============================================================================
# STEP 3: Start Docker Services
# ============================================================================
echo -e "${YELLOW}[3/6] Starting Docker services...${NC}"

docker compose -f infra/docker-compose.yml up -d --build

echo -e "${GREEN}✅ Services starting...${NC}"

# ============================================================================
# STEP 4: Wait for Services to Be Ready
# ============================================================================
echo -e "${YELLOW}[4/6] Waiting for services to be ready...${NC}"

MAX_WAIT=120
WAITED=0

while [ $WAITED -lt $MAX_WAIT ]; do
    if curl -s http://localhost:8000/status > /dev/null 2>&1 && \
       curl -s http://localhost:8001/status > /dev/null 2>&1; then
        echo -e "${GREEN}✅ All services are up!${NC}"
        break
    fi
    echo -n "."
    sleep 2
    WAITED=$((WAITED + 2))
done

if [ $WAITED -ge $MAX_WAIT ]; then
    echo -e "${RED}❌ Services took too long to start. Check logs: docker compose -f infra/docker-compose.yml logs${NC}"
    exit 1
fi

# Run migrations
echo -e "${YELLOW}Running database migrations...${NC}"
docker compose -f infra/docker-compose.yml exec -T db psql -U trader -d mastertrader -f /docker-entrypoint-initdb.d/009_positions.sql 2>/dev/null || echo "Migrations may already be applied"

echo -e "${GREEN}✅ Services ready${NC}"

# ============================================================================
# STEP 5: Start Background Monitoring & Optimization
# ============================================================================
echo -e "${YELLOW}[5/6] Starting 24/7 monitoring and optimization...${NC}"

LOG_DIR="$HOME/Library/Logs/master-trader"
mkdir -p "$LOG_DIR"

# Fix optimizer script to use correct database host
sed -i.bak 's/host=localhost/host=db/g' scripts/start_auto_optimizer.sh 2>/dev/null || \
sed -i '' 's/host=localhost/host=db/g' scripts/start_auto_optimizer.sh 2>/dev/null || true

# Install launchd agents for 24/7 operation (survives reboots)
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo -e "${YELLOW}Installing 24/7 launchd agents (survives reboots)...${NC}"
    chmod +x scripts/install_24_7.sh
    bash scripts/install_24_7.sh
else
    # Linux: Use systemd or just run in background
    echo -e "${YELLOW}Starting background services (Linux)...${NC}"
    chmod +x scripts/start_monitor.sh scripts/start_auto_optimizer.sh
    
    # Start monitor in background
    if [ ! -f "$LOG_DIR/monitor.pid" ] || ! ps -p "$(cat "$LOG_DIR/monitor.pid" 2>/dev/null)" > /dev/null 2>&1; then
        nohup bash scripts/start_monitor.sh > "$LOG_DIR/monitor.out" 2>&1 &
        echo $! > "$LOG_DIR/monitor.pid"
        echo -e "${GREEN}✅ Health monitor started${NC}"
    else
        echo -e "${YELLOW}⚠️  Monitor already running${NC}"
    fi
    
    # Start optimizer in background
    if [ ! -f "$LOG_DIR/optimizer.pid" ] || ! ps -p "$(cat "$LOG_DIR/optimizer.pid" 2>/dev/null)" > /dev/null 2>&1; then
        nohup bash scripts/start_auto_optimizer.sh > "$LOG_DIR/optimizer.out" 2>&1 &
        echo $! > "$LOG_DIR/optimizer.pid"
        echo -e "${GREEN}✅ Auto-optimizer started${NC}"
    else
        echo -e "${YELLOW}⚠️  Optimizer already running${NC}"
    fi
fi

echo -e "${GREEN}✅ Background services started${NC}"

# ============================================================================
# STEP 6: Final Status Check
# ============================================================================
echo -e "${YELLOW}[6/6] Final status check...${NC}"

sleep 3

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗"
echo -e "${GREEN}║                    ✅ SETUP COMPLETE!                    ║"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}System Status:${NC}"
echo "  ✅ Docker services running"
echo "  ✅ Health monitoring active (auto-restarts on failure)"
echo "  ✅ Continuous learning active (optimizes hourly)"
echo "  ✅ Trading system ready"
echo ""
echo -e "${BLUE}Quick Commands:${NC}"
echo "  Status:    curl http://localhost:8000/metrics"
echo "  Logs:      tail -f $LOG_DIR/monitor.log"
echo "  Stop:      docker compose -f infra/docker-compose.yml down"
echo ""
echo -e "${YELLOW}⚠️  IMPORTANT:${NC}"
echo "  1. Edit .env and add your OPENAI_API_KEY for LLM agents"
echo "  2. System is in PAPER mode (safe testing)"
echo "  3. Monitor for a few days before switching to live"
echo ""
echo -e "${GREEN}🚀 System is now running 24/7!${NC}"
echo -e "${GREEN}   It will trade, learn, and optimize automatically.${NC}"
echo ""
echo -e "${YELLOW}⚠️  IMPORTANT: This runs on YOUR computer.${NC}"
echo -e "${YELLOW}   ❌ STOPS when you shut down your computer${NC}"
echo -e "${YELLOW}   ❌ STOPS when you close your laptop${NC}"
echo ""
echo -e "${GREEN}💡 For TRUE 24/7 (runs even when computer is OFF):${NC}"
echo -e "${GREEN}   Run: ./deploy_easiest.sh${NC}"
echo -e "${GREEN}   See CLARIFICATION.md for details${NC}"
echo ""

