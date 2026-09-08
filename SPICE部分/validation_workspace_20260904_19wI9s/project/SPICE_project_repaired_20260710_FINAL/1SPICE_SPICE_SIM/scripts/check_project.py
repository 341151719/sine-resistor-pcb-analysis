#!/usr/bin/env python3
"""Structural project check; no simulation is run."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    ROOT / "scripts" / "run_sweeps.py",
    ROOT / "scripts" / "validation_metrics.py",
    ROOT / "scripts" / "audit_control_path.py",
    ROOT / "scripts" / "audit_firmware.py",
    ROOT / "spice" / "circuits" / "full_component_template.cir",
    ROOT / "spice" / "models" / "official_pure_rawps_wrapped_models.lib",
]


def main() -> None:
    problems = []
    for path in REQUIRED:
        if not path.exists():
            problems.append(f"missing: {path.relative_to(ROOT)}")

    for module in ["numpy", "pandas", "matplotlib"]:
        if importlib.util.find_spec(module) is None:
            problems.append(f"python module unavailable: {module}")

    control_report = ROOT / "control_path_audit.json"
    cp = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "audit_control_path.py"), "--json-out", str(control_report)],
        capture_output=True,
        text=True,
    )
    if cp.returncode:
        problems.append("SPICE control-path audit failed")

    model_text = (ROOT / "spice" / "models" / "official_pure_rawps_wrapped_models.lib").read_text(encoding="utf-8", errors="replace") if (ROOT / "spice" / "models" / "official_pure_rawps_wrapped_models.lib").exists() else ""
    for token in ["AD633_NG_SURR", "OPA548_NG_SURR", "OPA1656_NG_SURR", "INA149_NG_SURR"]:
        if token not in model_text:
            problems.append(f"model wrapper missing subcircuit: {token}")

    result = {"status": "pass" if not problems else "fail", "problems": problems}
    (ROOT / "project_check.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if not problems else 2)


if __name__ == "__main__":
    main()
