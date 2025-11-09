# 🔑 Add OpenAI API Key - Quick Guide

## Step 1: Get Your API Key

1. **Go to:** https://platform.openai.com/api-keys
2. **Sign in** (or create account)
3. **Click:** "Create new secret key"
4. **Name it:** "MasterTrader" (optional)
5. **Copy the key** (starts with `sk-`)
   - ⚠️ **Save it now** - you won't see it again!

## Step 2: Add to Render

1. **Go to:** https://render.com/dashboard
2. **Click:** Your `mastertrader` service
3. **Click:** "Environment" tab (left sidebar)
4. **Click:** "Add Environment Variable" button
5. **Add:**
   - **Key**: `OPENAI_API_KEY`
   - **Value**: (paste your key from Step 1)
6. **Click:** "Save Changes"
7. **Wait:** Service will auto-redeploy (~2 minutes)

## Step 3: Verify

After redeploy, check logs:
- Should see LLM agents initializing
- No errors about missing API key

**Done!** Your LLM agents are now enabled. 🎉

---

## 💰 Cost Estimate

OpenAI API costs:
- **GPT-4**: ~$0.03 per proposal (Reader + Proposer + Skeptic + Referee)
- **GPT-3.5**: ~$0.001 per proposal (much cheaper)
- **Estimated**: $5-20/month for active trading

**Tip**: Start with GPT-3.5, upgrade to GPT-4 if profitable.

