#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
ngspice_bin="${NGSPICE:-ngspice}"
mkdir -p results

decks=(
  01_r10_es_sweep.cir
  01b_j1_sweep_r10_100k.cir
  02_opa_on_105k_amp1V.cir
  02_opa_on_105k_amp2V.cir
  02_opa_on_105k_amp3V.cir
  02_opa_on_105k_amp4V.cir
  03_scope_ground_short.cir
  04_healthy_baseline.cir
)

for deck in "${decks[@]}"; do
  name="${deck%.cir}"
  "$ngspice_bin" -b -o "results/${name}.log" "$deck"
done

printf 'Completed %d decks. Generated files are in %s/results/.\n' \
  "${#decks[@]}" "$PWD"
