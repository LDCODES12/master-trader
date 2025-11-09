# 🚀 Phase 1 Setup - Complete Guide

## Step 1: Add OpenAI API Key (5 minutes)

### Get Your API Key:
1. Go to: https://platform.openai.com/api-keys
2. Click "Create new secret key"
3. Copy the key (starts with `sk-`)

### Add to Render:
1. Go to: https://render.com/dashboard
2. Click your `mastertrader` service
3. Go to "Environment" tab
4. Click "Add Environment Variable"
5. Add:
   - **Key**: `OPENAI_API_KEY`
   - **Value**: (paste your key)
6. Click "Save Changes"
7. Service will auto-redeploy

**Done!** LLM agents are now enabled.

---

## Step 2: Deploy Temporal Worker

### Option A: Run Locally (Easiest for Testing)

```bash
# Start Temporal locally
cd /Users/liam/Downloads/trader
docker compose -f infra/docker-compose.yml up -d temporal db

# Run worker locally (connects to local Temporal)
export DATABASE_URL="postgresql://trader:traderpw@localhost:5432/mastertrader"
export OPENAI_API_KEY="your_key_here"
python3 -m apps.temporal_worker.worker
```

### Option B: Deploy to Render (24/7)

Create a new Background Worker service on Render:

1. **Go to Render Dashboard** → "New +" → "Background Worker"
2. **Connect GitHub** → Select `LDCODES12/master-trader`
3. **Configure**:
   - **Name**: `mastertrader-worker`
   - **Environment**: **Docker**
   - **Dockerfile Path**: `apps/temporal_worker/Dockerfile`
   - **Plan**: **Starter** ($7/month)
   - **Environment Variables**:
     - `DATABASE_URL` = (same as gateway)
     - `OPENAI_API_KEY` = (your key)
     - `EXEC_MODE` = `paper`
     - `TEMPORAL_ADDRESS` = (Temporal server address - see below)

**Note**: For full 24/7 operation, you'll also need Temporal server. For now, Option A (local) is easier for testing.

---

## Step 3: Test the System

Use the test script:

```bash
python3 scripts/test_proposal.py
```

Or submit manually:

```bash
curl -X POST https://master-trader.onrender.com/submit-proposal \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: test-$(date +%s)" \
  -d '{
    "proposal": {
      "action": "open",
      "symbol": "BTCUSDT",
      "side": "buy",
      "size_bps_equity": 4.0,
      "horizon_minutes": 120,
      "thesis": "Testing Phase 1 setup",
      "risk": {
        "stop_loss_bps": 60,
        "take_profit_bps": 120,
        "max_slippage_bps": 3
      },
      "evidence": [{
        "url": "https://www.binance.com/en/support/announcement",
        "type": "exchange_status"
      }],
      "confidence": 0.7
    }
  }'
```

---

## ✅ Phase 1 Checklist

- [ ] OpenAI API key added to Render
- [ ] Temporal worker running (local or Render)
- [ ] Test proposal submitted
- [ ] Check logs for workflow execution
- [ ] Verify paper trade was executed

**Once all checked, Phase 1 is complete!** 🎉

