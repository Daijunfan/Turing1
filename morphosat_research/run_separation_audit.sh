#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")" && pwd)
cd "$ROOT"
./scripts/bootstrap_baselines.sh
mkdir -p proofs
./run_checks.sh 2>&1 | tee proofs/v01_regression_checks.log
"$ROOT/.venv-audit/bin/python" experiments/separation_audit.py \
  --profile "${AUDIT_PROFILE:-full}" \
  --timeout "${AUDIT_TIMEOUT_SECONDS:-10}" \
  --memory-mb "${AUDIT_MEMORY_MB:-4096}"
shasum -a 256 -c AUDIT_MANIFEST.sha256
