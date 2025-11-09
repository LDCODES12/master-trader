# MasterTrader - Automated Trading System

Automated cryptocurrency trading system with LLM-powered decision making, built on Temporal, FastAPI, and PostgreSQL.

## 🚀 Quick Start

### Local Development

```bash
# One command to start everything
./start.sh

# Or use Make
make start
```

This automatically:
- ✅ Checks and starts Docker
- ✅ Creates `.env` with defaults
- ✅ Builds and starts all services
- ✅ Runs database migrations
- ✅ Starts health monitoring
- ✅ Starts auto-optimization

### Cloud Deployment (24/7)

Deploy to Render.com for true 24/7 operation:

1. **Create PostgreSQL database** on Render (Starter plan)
2. **Create Web Service**:
   - Connect GitHub repo
   - Environment: **Docker**
   - Dockerfile Path: `Dockerfile.production`
   - Plan: **Starter** ($7/month)
   - Environment Variables:
     - `DATABASE_URL` = (Internal Database URL from PostgreSQL)
     - `EXEC_MODE` = `paper`
     - `AGENT_MODE` = `llm`
     - `PORT` = `8000`

See `render.yaml` for configuration.

## 📁 Project Structure

```
apps/
  agent_brain/     # LLM debate system (LangGraph)
  analytics/        # Equity tracking, positions, PnL
  attention/        # ASLF scoring mechanism
  executor/         # Trade execution (paper/live)
  gateway/          # FastAPI HTTP API
  monitor/          # Health checks, auto-optimization
  temporal_worker/  # Temporal workflows
infra/
  docker-compose.yml  # Local development
  migrations/         # Database schema
config/
  profit_maximization.py  # Aggressive profit settings
scripts/
  auto_setup.sh           # Automated setup
  start_monitor.sh        # Health monitoring
  start_auto_optimizer.sh # Continuous learning
```

## ⚙️ Configuration

Edit `.env` (created automatically):

```bash
# Execution mode
EXEC_MODE=paper  # Start with paper trading!

# LLM agents
AGENT_MODE=llm
OPENAI_API_KEY=your_key_here

# Profit maximization (aggressive defaults)
MAX_POSITION_SIZE_PCT=20.0
MAX_PORTFOLIO_EXPOSURE_PCT=300.0
ASLF_THETA_BUY=0.8
FRACTIONAL_KELLY_MAX=0.5

# Risk management
MAX_DRAWDOWN_PCT=25.0
MAX_DAILY_LOSS_PCT=10.0
```

## 🎯 Key Features

- **LLM-Powered Trading**: Multi-agent debate system (Reader, Proposer, Skeptic, Referee)
- **Position Tracking**: Real-time PnL, portfolio exposure, risk metrics
- **Paper Trading**: Safe testing mode before going live
- **Smart Execution**: TWAP/VWAP algorithms, smart order routing
- **Auto-Optimization**: Continuous learning and parameter tuning
- **Health Monitoring**: Auto-restart failed services
- **24/7 Operation**: Runs continuously, survives reboots

## 📊 Monitoring

```bash
make status      # Check system health
make logs-all    # View all logs
curl http://localhost:8000/metrics  # Performance metrics
```

## 🧪 Testing

```bash
# Submit a test trade proposal
python scripts/submit_example.py

# Check executor status
curl http://localhost:8001/status

# Submit via HTTP
curl -X POST http://localhost:8000/submit-proposal \
  -H 'content-type: application/json' \
  -d '{"proposal":{"action":"open","symbol":"BTCUSDT","side":"buy","size_bps_equity":4.0,"horizon_minutes":120,"thesis":"test","risk":{"stop_loss_bps":60,"take_profit_bps":120,"max_slippage_bps":3},"evidence":[{"url":"https://example.com","type":"news_headline"}],"confidence":0.7}}'
```

## 🔧 Make Commands

```bash
make start          # Start everything
make status         # Check health
make logs-all       # View logs
make stop           # Stop monitoring
make full-restart   # Restart everything
```

## 📝 Requirements

- Python 3.11+
- Docker & Docker Compose
- PostgreSQL (via Docker or cloud)
- OpenAI API key (for LLM mode)

## ⚠️ Important Notes

- **Start with paper trading** (`EXEC_MODE=paper`) for safety
- **Starter plan required** on Render for true 24/7 operation (Free tier spins down)
- **Database migrations** run automatically on startup
- **Health monitoring** auto-restarts failed services

## 📄 License

See LICENSE file for details.
