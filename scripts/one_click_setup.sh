#!/usr/bin/env bash
set -euo pipefail

info() { printf "[info] %s\n" "$*"; }
warn() { printf "[warn] %s\n" "$*" >&2; }
err()  { printf "[error] %s\n" "$*" >&2; }

require_macos() {
  if [[ "$(uname)" != "Darwin" ]]; then
    err "This bootstrap is designed for macOS. Exiting."
    exit 1
  fi
}

ensure_brew() {
  if ! command -v brew >/dev/null 2>&1; then
    warn "Homebrew not found. Installing..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    eval "$(/opt/homebrew/bin/brew shellenv)" || true
    eval "$(/usr/local/bin/brew shellenv)" || true
  else
    info "Homebrew present."
  fi
}

ensure_gh() {
  if ! command -v gh >/dev/null 2>&1; then
    info "Installing GitHub CLI..."
    brew install gh
  else
    info "GitHub CLI present."
  fi
  if ! gh auth status >/dev/null 2>&1; then
    info "Logging into GitHub CLI..."
    gh auth login
  else
    info "GitHub CLI already authenticated."
  fi
}

ensure_gcloud() {
  if ! command -v gcloud >/dev/null 2>&1; then
    info "Installing Google Cloud SDK..."
    brew install --cask google-cloud-sdk || brew install google-cloud-sdk
  else
    info "Google Cloud SDK present."
  fi
  local acct_count
  acct_count="$(gcloud auth list --format='value(account)' | wc -l | tr -d ' ')"
  if [[ "${acct_count}" == "0" ]]; then
    info "Logging into Google Cloud..."
    gcloud auth login
  else
    info "gcloud already authenticated."
  fi
}

ensure_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    info "Installing Docker Desktop..."
    brew install --cask docker
    warn "Please open Docker.app once to finalize installation."
  else
    info "Docker present."
  fi
}

ensure_repo_remote() {
  if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    info "Git repo detected."
  else
    info "Initializing git repository..."
    git init -b main
    git add .
    git commit -m "Initial commit"
  fi
  if git remote get-url origin >/dev/null 2>&1; then
    info "Git remote 'origin' already set. Skipping repo creation."
  else
    info "Creating GitHub repo and setting remote..."
    local repo_name
    repo_name="$(basename "$(pwd)")"
    gh repo create "${repo_name}" --private --source=. --remote=origin --push -y
  fi
}

prompt_if_empty() {
  local var_name="$1"
  local prompt_msg="$2"
  local secret="${3:-0}"
  if [[ -n "${!var_name:-}" ]]; then
    return 0
  fi
  if [[ "${secret}" == "1" ]]; then
    read -r -s -p "${prompt_msg}: " tmpval
    echo
  else
    read -r -p "${prompt_msg}: " tmpval
  fi
  export "${var_name}"="${tmpval}"
}

setup_gcp_project() {
  prompt_if_empty GCP_PROJECT_ID "Enter GCP Project ID"
  prompt_if_empty GCP_REGION "Enter GCP Region (e.g., us-central1)"
  prompt_if_empty GCP_ZONE "Enter GCP Zone (e.g., us-central1-a)"

  info "Configuring gcloud project/region/zone..."
  gcloud config set project "${GCP_PROJECT_ID}" >/dev/null
  gcloud config set compute/region "${GCP_REGION}" >/dev/null
  gcloud config set compute/zone "${GCP_ZONE}" >/dev/null

  info "Enabling Compute API (idempotent)..."
  gcloud services enable compute.googleapis.com --project "${GCP_PROJECT_ID}"

  local sa_email="trader-deploy@${GCP_PROJECT_ID}.iam.gserviceaccount.com"
  if ! gcloud iam service-accounts list --filter="email=${sa_email}" --format="value(email)" | grep -q "${sa_email}"; then
    info "Creating service account trader-deploy..."
    gcloud iam service-accounts create trader-deploy --display-name="Trader Deploy"
  else
    info "Service account trader-deploy exists."
  fi

  info "Binding roles to service account (idempotent)..."
  gcloud projects add-iam-policy-binding "${GCP_PROJECT_ID}" \
    --member="serviceAccount:${sa_email}" \
    --role="roles/compute.admin" >/dev/null
  gcloud projects add-iam-policy-binding "${GCP_PROJECT_ID}" \
    --member="serviceAccount:${sa_email}" \
    --role="roles/iam.serviceAccountUser" >/dev/null

  mkdir -p deploy
  if [[ ! -s deploy/sa.json ]]; then
    info "Creating service account key at deploy/sa.json..."
    gcloud iam service-accounts keys create deploy/sa.json \
      --iam-account "${sa_email}"
  else
    info "Service account key deploy/sa.json already exists. Skipping."
  fi
}

set_repo_secrets() {
  prompt_if_empty BINANCE_API_KEY "Enter BINANCE_API_KEY" 1
  prompt_if_empty BINANCE_API_SECRET "Enter BINANCE_API_SECRET" 1
  prompt_if_empty OPENAI_API_KEY "Enter OPENAI_API_KEY" 1

  info "Setting GitHub repo secrets (idempotent, will overwrite)..."
  gh secret set GCP_PROJECT_ID --body "${GCP_PROJECT_ID}"
  gh secret set GCP_REGION --body "${GCP_REGION}"
  gh secret set GCP_ZONE --body "${GCP_ZONE}"
  gh secret set GCP_SA_KEY < deploy/sa.json
  gh secret set BINANCE_API_KEY --body "${BINANCE_API_KEY}"
  gh secret set BINANCE_API_SECRET --body "${BINANCE_API_SECRET}"
  gh secret set OPENAI_API_KEY --body "${OPENAI_API_KEY}"
}

trigger_deploy_and_stream() {
  info "Triggering Deploy Trader (GCP) workflow..."
  gh workflow run .github/workflows/deploy-gcp.yml || gh workflow run deploy-gcp.yml
  info "Waiting for workflow to start..."
  sleep 3

  # Wait for the most recent workflow_dispatch run id and stream logs
  local run_id=""
  local attempts=20
  while [[ $attempts -gt 0 ]]; do
    run_id="$(gh run list --workflow deploy-gcp.yml --limit 20 --json databaseId,event \
      -q 'map(select(.event==\"workflow_dispatch\")) | .[0].databaseId' || true)"
    [[ -n "${run_id}" && "${run_id}" != "null" ]] && break
    sleep 5
    attempts=$((attempts-1))
  done
  if [[ -z "${run_id}" || "${run_id}" == "null" ]]; then
    warn "Could not find a workflow_dispatch run id. Showing latest run output instead."
    gh run watch --exit-status || true
  else
    gh run watch "${run_id}" --exit-status || true
  fi

  info "Fetching run logs and extracting PUBLIC_IP..."
  local logs
  logs="$(gh run view ${run_id:-} --log 2>/dev/null || gh run view --log 2>/dev/null || true)"
  local ip
  ip="$(printf "%s" "${logs}" | grep -oE 'PUBLIC_IP=[0-9]+(\\.[0-9]+){3}' | head -n1 | cut -d= -f2 || true)"

  if [[ -n "${ip}" ]]; then
    printf "\nPUBLIC_IP=%s\n" "${ip}"
    printf "SSH tunnel:\n"
    printf "ssh -N -L 8000:localhost:8000 -L 8001:localhost:8001 -L 8080:localhost:8080 ubuntu@%s\n" "${ip}"
    printf "\nOpen:\n  - http://localhost:8000/health\n  - http://localhost:8080\n"
    printf "\nReminder: Add this PUBLIC_IP to your Binance API key allowlist (if enabled).\n"
  else
    warn "Could not parse PUBLIC_IP from logs. You can view logs with: gh run view --log"
  fi
}

main() {
  require_macos
  ensure_brew
  ensure_gh
  ensure_gcloud
  ensure_docker
  ensure_repo_remote
  setup_gcp_project
  set_repo_secrets
  trigger_deploy_and_stream
  info "Bootstrap complete."
}

main "$@"


