### GCP one-click deploy (Always-Free e2-micro)

This sets up a tiny Ubuntu 22.04 VM, installs Docker, writes `.env` from repo secrets, clones this repo, and brings the stack up with `docker compose`. Temporal Web and Gateway are exposed via SSH tunnel (no public ports).

#### 1) Add GitHub Actions secrets

- GCP_PROJECT_ID
- GCP_REGION (e.g., us-central1)
- GCP_ZONE (e.g., us-central1-a)
- GCP_SA_KEY (JSON for a service account with Compute Admin)
- BINANCE_API_KEY
- BINANCE_API_SECRET
- OPENAI_API_KEY

Optional tuning (leave empty to use defaults in cloud-init):

- ALLOWED_SYMBOLS
- CONSENSUS_MIN
- ASLF_THETA_BUY
- PROBE_SIZE_BPS
- FRACTIONAL_KELLY_MAX
- EXECUTOR_MODE
- AGENT_MODE
- BINANCE_BASE
- BINANCE_FRICTION_BASE

#### 2) Deploy

In GitHub → Actions → “Deploy Trader (GCP)” → Run workflow.

The action prints:

- PUBLIC_IP=<ip>
- SSH tunnel command:

```
ssh -N -L 8000:localhost:8000 -L 8001:localhost:8001 -L 8080:localhost:8080 ubuntu@<ip>
```

Then open:

- http://localhost:8000/health
- http://localhost:8080 (Temporal Web)

#### 3) Binance allowlist

Add the VM’s PUBLIC_IP to your Binance API key IP allowlist (if enabled).

#### 4) Teardown

GitHub → Actions → “Teardown Trader (GCP)” → provide `vm_name` (from deploy output, default is `trader-<run_id>`).

#### Defaults used by cloud-init

```
BINANCE_BASE=https://testnet.binance.vision
BINANCE_FRICTION_BASE=https://api.binance.us
AGENT_MODE=llm
EXECUTOR_MODE=live
ALLOWED_SYMBOLS=BTCUSDT,ETHUSDT
CONSENSUS_MIN=0.55
ASLF_THETA_BUY=0.8
PROBE_SIZE_BPS=3
FRACTIONAL_KELLY_MAX=0.08
```


