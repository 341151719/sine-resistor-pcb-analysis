#!/usr/bin/env bash
set -euo pipefail

audit_dir="$(cd "$(dirname "$0")" && pwd)"
repo_root="$(cd "$audit_dir/../.." && pwd)"
ngspice_bin="${NGSPICE:-ngspice}"
result_dir="$audit_dir/results"
v8_root="$repo_root/KICAD部分/正弦电阻V8_KiCad10.0.4_稳定性修正版_2026-09-04"

mkdir -p "$result_dir"

python3 "$audit_dir/spice_static_lint.py" "$repo_root" \
  > "$result_dir/spice_static_lint_output.txt"

python3 "$audit_dir/release_assembly_crosscheck.py" \
  "$v8_root/release/V8_2026-09-04/reports/pcb_analysis.json" \
  "$v8_root/release/V8_2026-09-04/assembly/BOM_SMT.csv" \
  "$v8_root/release/V8_2026-09-04/assembly/CPL_SMT.csv" \
  > "$result_dir/release_assembly_crosscheck_output.txt"

status=0
(
  cd "$audit_dir/corrected_decks"
  mkdir -p results
  "$ngspice_bin" -b -o results/H07_U4rail_corrected.log H07_U4rail_corrected.cir
  "$ngspice_bin" -b -o results/H08_decoupling_corrected.log H08_decoupling_corrected.cir
)

if grep -Eq 'tran simulation\(s\) aborted|measure .* failed|timestep too small' \
  "$audit_dir/corrected_decks/results/H07_U4rail_corrected.log"; then
  printf 'H07: INCOMPLETE (strong-fault points did not converge).\n' >&2
  status=2
else
  printf 'H07: completed without the known failure signatures.\n'
fi

if grep -Eq 'tran simulation\(s\) aborted|measure .* failed|timestep too small' \
  "$audit_dir/corrected_decks/results/H08_decoupling_corrected.log"; then
  printf 'H08: INCOMPLETE (see generated log).\n' >&2
  status=2
else
  printf 'H08: completed without the known failure signatures.\n'
fi

printf 'Audit outputs written to %s and corrected_decks/results/.\n' "$result_dir"
exit "$status"
