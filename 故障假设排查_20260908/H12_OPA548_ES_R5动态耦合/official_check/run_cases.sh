#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p ../results_h12_official
for deck in v7_100k.cir v7_ideal_j1.cir v7_r5_1Meg.cir v7_ies20u.cir v8_6k8.cir v7_c39_220p.cir opa548_standalone_on.cir; do
  stem="${deck%.cir}"
  echo "== $stem =="
  ngspice -b -o "${stem}.rerun.log" "$deck"
done
