## MasterTrader Scaffold

Minimal, production-style scaffold for a durable LLM trader with hard rails using Temporal, FastAPI, and Postgres.

### Repo layout

```
infra/
  docker-compose.yml
  migrations/
    000_temporal.sql
    001_init.sql
libs/
  schemas/proposal.py
apps/
  executor/
    app.py
    venues/
      binance (in app.py)
      kraken.py
      coinbase.py
    Dockerfile
  agent_brain/
    graph.py
    prompts/proposal.md
  temporal_worker/
    worker.py
    workflows.py
    activities.py
    Dockerfile
  gateway/
    app.py
    Dockerfile
requirements.txt
.env.example
```

### Dependencies

- Python 3.11
- Packages are pinned in `requirements.txt`

### Quickstart

1) Copy environment file and fill testnet keys:

```bash
cp .env.example .env
# Fill BINANCE_API_KEY / BINANCE_API_SECRET (Testnet)
```

2) Bring up services:

```bash
docker compose -f infra/docker-compose.yml up -d --build
```

3) Submit a demo proposal (Temporal workflow):

```bash
python scripts/submit_example.py
```

4) Call the executor status:

```bash
curl -s http://localhost:8001/status
```

5) Submit via HTTP gateway:

```bash
curl -X POST http://localhost:8000/submit-proposal \
  -H 'content-type: application/json' \
  -d '{"proposal":{"action":"open","symbol":"BTCUSDT","side":"buy","size_bps_equity":4.0,"horizon_minutes":120,"thesis":"stub","risk":{"stop_loss_bps":60,"take_profit_bps":120,"max_slippage_bps":3},"evidence":[{"url":"https://example.com","type":"news_headline"}],"confidence":0.7}}'
```

### Features

- Debate Brain (LangGraph): Reader → Proposer → Skeptic → Referee with consensus threshold (`CONSENSUS_MIN`).
- Live RAG (stub): `apps/rag/collector.py` provides normalized docs; Reader injects into state.
- Provenance Lock: `verify_evidence` stores SHA-256 + C2PA status; `reverify_evidence` aborts on change.
- Counterfactual PnL: child `PostmortemWorkflow` computes counterfactual delta after horizon.
- Preflight: `GET /preflight` on Gateway checks Binance server time, ping, and Temporal connectivity.
 - ASLF Rule: Attention-Surprise × Liquidity-Friction gate; `GET /aslf?symbol=BTCUSDT&notional=25` for live debug. Thresholds via env: `ASLF_THETA_BUY`, `ASLF_THETA_FADE`, `ASLF_LAMBDA`, `LMF_ALPHA/BETA/GAMMA`, `FRACTIONAL_KELLY_MAX`.
 - RAG Fetchers (live sources): configure in `.env`:
   - `RAG_RSS_SOURCES=https://www.coindesk.com/arc/outboundfeeds/rss/,https://cointelegraph.com/rss`
   - `RAG_HTTP_SOURCES=https://www.binance.com/en/support/announcement`
   - `RAG_TIMEOUT_S=6`, `RAG_MAX_DOCS=8`


