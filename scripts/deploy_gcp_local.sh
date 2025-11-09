#!/usr/bin/env bash
set -euo pipefail

# Simple local GCP deploy (bypasses GitHub Actions)
# Requirements: gcloud, envsubst (gettext), jq (optional)
#
# Usage:
#   bash scripts/deploy_gcp_local.sh --project <PROJECT_ID> --region us-central1 --zone us-central1-a --vm trader-llm
#
# It will:
# - Enable Compute API
# - Render deploy/cloud-init.yaml with your .env values
# - Create an e2-micro Ubuntu 22.04 VM
# - Print PUBLIC_IP and SSH tunnel command

PROJECT=""
REGION="us-central1"
ZONE="us-central1-a"
VM="trader-$(date +%s)"
GITHUB_REPOSITORY_DEFAULT="LDCODES12/master-trader"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project) PROJECT="$2"; shift 2;;
    --region) REGION="$2"; shift 2;;
    --zone) ZONE="$2"; shift 2;;
    --vm) VM="$2"; shift 2;;
    *) echo "Unknown arg: $1"; exit 1;;
  esac
done

if ! command -v gcloud >/dev/null 2>&1; then
  echo "[error] gcloud not found. Install Google Cloud SDK." >&2
  exit 1
fi
if ! command -v envsubst >/dev/null 2>&1; then
  echo "[error] envsubst not found. Install gettext (brew install gettext; brew link --force gettext)." >&2
  exit 1
fi

cd "$(dirname "$0")/.."

# Resolve project from flag or current config
if [[ -z "${PROJECT}" ]]; then
  PROJECT="$(gcloud config get-value project 2>/dev/null || true)"
fi
if [[ -z "${PROJECT}" || "${PROJECT}" == "(unset)" ]]; then
  echo "[error] No GCP project set. Pass --project <PROJECT_ID> or run: gcloud config set project <PROJECT_ID>" >&2
  exit 1
fi

echo "[info] Using project=${PROJECT} region=${REGION} zone=${ZONE} vm=${VM}"
gcloud config set project "${PROJECT}" >/dev/null
gcloud config set compute/region "${REGION}" >/dev/null
gcloud config set compute/zone "${ZONE}" >/dev/null

echo "[info] Enabling Compute API (idempotent)..."
gcloud services enable compute.googleapis.com --project "${PROJECT}" >/dev/null

# Export env for cloud-init rendering (pull from .env if present)
if [[ -f .env ]]; then
  # shellcheck disable=SC2046
  export $(grep -E '^(BINANCE_API_KEY|BINANCE_API_SECRET|OPENAI_API_KEY|BINANCE_BASE|BINANCE_FRICTION_BASE|AGENT_MODE|EXECUTOR_MODE|ALLOWED_SYMBOLS|CONSENSUS_MIN|ASLF_THETA_BUY|PROBE_SIZE_BPS|FRACTIONAL_KELLY_MAX)=' .env | xargs -I{} bash -lc 'echo {}')
fi
export GITHUB_REPOSITORY="${GITHUB_REPOSITORY:-$GITHUB_REPOSITORY_DEFAULT}"

OUT="/tmp/cloud-init.${VM}.yaml"
echo "[info] Rendering cloud-init to ${OUT} (GITHUB_REPOSITORY=${GITHUB_REPOSITORY})"
envsubst < deploy/cloud-init.yaml > "${OUT}"
head -n 12 "${OUT}" || true

# If VM exists, reuse IP; else create
if gcloud compute instances describe "${VM}" >/dev/null 2>&1; then
  echo "[info] VM ${VM} already exists; reusing."
else
  echo "[info] Creating VM ${VM} (e2-micro, Ubuntu 22.04)..."
  gcloud compute instances create "${VM}" \
    --machine-type=e2-micro \
    --image-family=ubuntu-2204-lts \
    --image-project=ubuntu-os-cloud \
    --metadata-from-file=user-data="${OUT}" \
    --quiet
fi

IP="$(gcloud compute instances describe "${VM}" --format='get(networkInterfaces[0].accessConfigs[0].natIP)')"
if [[ -z "${IP}" ]]; then
  echo "[error] Could not retrieve PUBLIC_IP for ${VM}" >&2
  exit 1
fi
echo "PUBLIC_IP=${IP}"
echo "ssh -N -L 8000:localhost:8000 -L 8001:localhost:8001 -L 8080:localhost:8080 ubuntu@${IP}"

echo "[info] Next:"
echo "  - Add ${IP} to your Binance API key allowlist (if enabled)"
echo "  - Then run the SSH tunnel above and open http://localhost:8000/health and http://localhost:8080"


