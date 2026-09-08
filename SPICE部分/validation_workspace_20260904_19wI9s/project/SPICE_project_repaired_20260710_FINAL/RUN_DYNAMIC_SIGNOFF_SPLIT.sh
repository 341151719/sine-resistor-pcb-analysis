#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
PROJ="$ROOT/1SPICE_SPICE_SIM"
cd "$PROJ"
rm -rf split_dynamic_fm* results_dynamic_signoff_combined
for fm in 10 30 100 300 1000; do
  echo "=== dynamic split: fm=${fm}Hz ==="
  python scripts/run_sweeps.py \
    --clean \
    --results-dir "split_dynamic_fm${fm}" \
    --suite dynamic-signoff \
    --case-filter "signoff_dynamic_fm${fm}_" \
    --model-lib official-pure \
    --allow-acceptance-fail \
    --no-plots \
    --no-case-csv
done
python scripts/aggregate_split_results.py \
  split_dynamic_fm10 split_dynamic_fm30 split_dynamic_fm100 split_dynamic_fm300 split_dynamic_fm1000 \
  --out results_dynamic_signoff_combined
