#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")" && pwd)
cd "$ROOT"

./morphosat_research/scripts/bootstrap_baselines.sh
(cd morphosat_research && ./run_checks.sh) 2>&1 | tee results/v01_v02_regression.log
morphosat_research/.venv-audit/bin/python experiments/run_clone_ascent_v03.py
morphosat_research/.venv-audit/bin/python -m unittest discover -s tests -v 2>&1 | tee results/test_output_v03.log
morphosat_research/.venv-audit/bin/python experiments/finalize_clone_ascent_v03.py
shasum -a 256 -c AUDIT_MANIFEST_V03.sha256

