#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
PROJ="$ROOT/1SPICE_SPICE_SIM"
cd "$PROJ"
rm -rf split_fixed_r* results_fixed_signoff_combined
for tag in r1 r5 r7p2 r20 r100; do
  echo "=== fixed split: $tag ==="
  python scripts/run_sweeps.py \
    --clean \
    --results-dir "split_fixed_${tag}" \
    --suite fixed-signoff \
    --case-filter "signoff_fixed_${tag}_" \
    --model-lib official-pure \
    --allow-acceptance-fail \
    --no-plots \
    --no-case-csv
done
python scripts/aggregate_split_results.py \
  split_fixed_r1 split_fixed_r5 split_fixed_r7p2 split_fixed_r20 split_fixed_r100 \
  --out results_fixed_signoff_combined
