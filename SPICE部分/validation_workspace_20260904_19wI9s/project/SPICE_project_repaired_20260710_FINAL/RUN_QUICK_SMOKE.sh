#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
PROJ="$ROOT/1SPICE_SPICE_SIM"
cd "$PROJ"
python scripts/check_project.py
python tests/test_validation_metrics.py
python scripts/audit_firmware.py . --allow-missing --json-out firmware_audit.json
python scripts/run_sweeps.py \
  --clean \
  --results-dir results_quick_smoke \
  --case-filter full_einj_fixed_r7p2_f1000 \
  --model-lib official-pure \
  --no-plots \
  --no-case-csv
printf '\nQUICK SMOKE PASSED\n'
