#!/bin/bash
# Fully automated setup - Cursor handles everything
# This script sets up the entire system for 24/7 operation

set -e

echo "🚀 MasterTrader - Fully Automated Setup"
echo "========================================"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${YELLOW}Starting Docker Desktop...${NC}"
    open -a Docker
    echo "Waiting for Docker to start..."
    sleep 30
fi

# Check if .env exists, create if not
if [ ! -f .env ]; then
    echo -e "${YELLOW}Creating .env file with defaults...${NC}"
    cat > .env << EOF
# Execution Mode - Start with paper trading for safety
EXEC_MODE=paper

# Agent Mode - Use LLM for better signals
AGENT_MODE=llm

# OpenAI API Key (REQUIRED for LLM mode)
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
EOF
    echo -e "${YELLOW}⚠️  Please edit .env and add your OPENAI_API_KEY${NC}"
fi

# Build and start services
echo -e "${GREEN}Building and starting services...${NC}"
docker compose -f infra/docker-compose.yml up -d --build

# Wait for services to be ready
echo -e "${GREEN}Waiting for services to be ready...${NC}"
sleep 10

# Health check
echo -e "${GREEN}Running health checks...${NC}"
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s http://localhost:8000/status > /dev/null 2>&1 && \
       curl -s http://localhost:8001/status > /dev/null 2>&1; then
        echo -e "${GREEN}✅ All services are up!${NC}"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "Waiting for services... ($RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo -e "${RED}❌ Services failed to start${NC}"
    exit 1
fi

# Run database migrations
echo -e "${GREEN}Running database migrations...${NC}"
docker compose -f infra/docker-compose.yml exec -T db psql -U trader -d mastertrader -f /docker-entrypoint-initdb.d/009_positions.sql 2>/dev/null || echo "Migrations may already be applied"

# Start health monitoring system
echo -e "${GREEN}Setting up 24/7 health monitoring...${NC}"
./scripts/start_monitor.sh

# Start continuous learning and optimization
echo -e "${GREEN}Starting continuous learning system...${NC}"
./scripts/start_auto_optimizer.sh

echo -e "${GREEN}"
echo "========================================"
echo "✅ Setup Complete!"
echo "========================================"
echo ""
echo "System is now running 24/7 with:"
echo "  ✅ Automated trading"
echo "  ✅ Continuous learning"
echo "  ✅ Self-healing"
echo "  ✅ Auto-optimization"
echo ""
echo "Monitor logs: make logs"
echo "Check status: make status"
echo "View metrics: curl http://localhost:8000/metrics"
echo -e "${NC}"

