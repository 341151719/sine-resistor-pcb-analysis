#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Static checks for v3 project files before running ngspice."""
from pathlib import Path
import hashlib
import math
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
required = [
    "spice/models/ngspice_compatible_macros.lib",
    "spice/circuits/full_component_template.cir",
    "spice/circuits/ideal_reference_template.cir",
    "spice/circuits/behavioral_chain_template.cir",
    "spice/circuits/macro_smoke_tests.cir",
    "spice/models/vendor_fetch_manifest.json",
    "scripts/run_sweeps.py",
    "scripts/replot_existing_results.py",
    "docs/PLOT_FIX_NOTES_V3_1.md",
    "docs/PLOT_AXIS_PLAN_V3_2.md",
    "docs/ACOUSTIC_STRESS_LIMIT_V3_3.md",
]
missing = [p for p in required if not (ROOT / p).exists()]
if missing:
    raise SystemExit("Missing files: " + ", ".join(missing))

mac = (ROOT / "spice/models/ngspice_compatible_macros.lib").read_text(encoding="utf-8")
for subckt in ["OPA548_NG_SURR", "AD633_NG_SURR", "INA149_NG_SURR", "OPA1656_NG_SURR", "DAC_STM32G431_SURR"]:
    if f".SUBCKT {subckt}" not in mac:
        raise SystemExit(f"Missing subckt {subckt}")

# Macro polarity regression checks: in ngspice, BOUT OUT 0 I=positive sinks current from OUT to 0.
# Stable voltage-output surrogates must therefore use V(OUT)-target, not target-V(OUT).
for bad in [
    "clip(V(NDOM), V(VNEG)+VHEAD, V(VPOS)-VHEAD)-V(OUT)",
    "clip(V(NLP), V(VNEG)+VHEAD, V(VPOS)-VHEAD)-V(OUT)",
    "clip(V(NLP), V(VNEG)+VHEAD, V(VPOS)-VHEAD)-V(W)",
]:
    if bad in mac:
        raise SystemExit("Legacy wrong-polarity BOUT pattern found: " + bad)
for good in [
    "V(OUT)-clip(V(NDOM), V(VNEG)+VHEAD, V(VPOS)-VHEAD)",
    "V(OUT)-clip(V(NLP), V(VNEG)+VHEAD, V(VPOS)-VHEAD)",
    "V(W)-clip(V(NLP), V(VNEG)+VHEAD, V(VPOS)-VHEAD)",
]:
    if good not in mac:
        raise SystemExit("Expected repaired BOUT polarity pattern missing: " + good)

for template_name in ["full_component_template.cir", "ideal_reference_template.cir", "behavioral_chain_template.cir"]:
    txt = (ROOT / "spice/circuits" / template_name).read_text(encoding="utf-8")
    for token in ["TSTART", "TRAMP", "soft(time)", "ItestAmp", "ItestFreq", "B_EINJ", "SYNERR", "RXNODE", "RTARGET", "RDES"]:
        if token not in txt:
            raise SystemExit(f"{template_name}: missing v3 token {token}")
    if "V(SPK)" not in txt or "V(RXNODE)*V(IPORT)" not in txt or "SYNERR" not in txt:
        raise SystemExit(f"{template_name}: missing voltage-domain synthesis error probe")
    if "__" in re.sub(r"__\w+__", "", txt):
        raise SystemExit(f"{template_name}: suspicious template marker remains")

run = (ROOT / "scripts/run_sweeps.py").read_text(encoding="utf-8")
for token in ["synerr_rms_tail_v", "reff_fit_tail_ohm", "iport_threshold_for_reff", "full_einj_fixed_r", "--case-filter", "tail_only", "robust_ylim", "STRESS_PRESSURES_PA = [1, 5]"]:
    if token not in run:
        raise SystemExit(f"run_sweeps.py missing v3 metric/case token: {token}")

replot = (ROOT / "scripts/replot_existing_results.py").read_text(encoding="utf-8")
for token in ["Regenerate readable PNG", "plot_case", "_tail.png"]:
    if token not in replot:
        raise SystemExit(f"replot_existing_results.py missing token: {token}")


# v3.3 policy check: stress pressures are centralized and limited to <=5 Pa.
import ast
try:
    stress_line = next(line for line in run.splitlines() if line.strip().startswith("STRESS_PRESSURES_PA"))
    stress_values = ast.literal_eval(stress_line.split("=", 1)[1].strip())
except Exception as exc:
    raise SystemExit("Cannot parse STRESS_PRESSURES_PA from run_sweeps.py") from exc
if any(float(v) > 5 for v in stress_values):
    raise SystemExit("Acoustic stress pressure above 5 Pa remains in STRESS_PRESSURES_PA")

# Theory checks.
Re = 7.2
Bl = 4.6
Mms = 5.7e-3
fs = 90
Qms = 2.29
w0 = 2 * math.pi * fs
Cms = 1 / (Mms * w0 * w0)
Rms = w0 * Mms / Qms
assert abs(Cms - 5.486e-4) / 5.486e-4 < 2e-3
assert abs(Rms - 1.408) / 1.408 < 2e-3
for rt in [1, 7.2, 100]:
    rx = rt - Re
    rem = Bl * Bl / rt
    q = w0 * Mms / (Rms + rem)
    print(f"Rtarget={rt:g} ohm -> Rx={rx:.6g} ohm, Rem={rem:.6g} N*s/m, Qeff={q:.6g}")
print("SHA256 models:", hashlib.sha256(mac.encode()).hexdigest())
print("Project static check OK:", ROOT)
