#!/usr/bin/env python3
"""Audit the SPICE control path for forbidden instantaneous V/I feedback."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def audit(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    probe_idx = next((i for i, line in enumerate(lines) if "* Probes" in line), len(lines))
    control_lines = lines[:probe_idx]
    probe_lines = lines[probe_idx:]

    forbidden = []
    div_patterns = [
        re.compile(r"V\([^)]*\)\s*/\s*V\([^)]*\)", re.I),
        re.compile(r"\b(?:voltage|vmeas|v_sense|vspk)\w*\s*/\s*(?:current|imeas|i_sense|iport)\w*", re.I),
        re.compile(r"\b(?:impedance|reff|rest|zest)\w*\s*=.*?/", re.I),
    ]
    for n, line in enumerate(control_lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("*"):
            continue
        if any(p.search(stripped) for p in div_patterns):
            forbidden.append({"line": n, "text": stripped})

    required_evidence = {
        "dac_target_generator": any("XU_DAC" in l for l in control_lines),
        "current_sense": any("XU_INA" in l for l in control_lines),
        "analog_multiplier": any("XU_MULT" in l and "AD633" in l for l in control_lines),
        "multiplier_control_comment": any("VCMD = 20*MUL = Rx_cmd*ip" in l for l in control_lines),
        "pointwise_vi_only_in_probe_section": any("B_REFF" in l for l in probe_lines) and not any("B_REFF" in l for l in control_lines),
    }
    passed = not forbidden and all(required_evidence.values())
    return {
        "file": str(path),
        "status": "pass" if passed else "fail",
        "forbidden_instantaneous_vi_control_hits": forbidden,
        "required_evidence": required_evidence,
        "conclusion": (
            "MCU/DAC generates the target trajectory; the analog path multiplies target impedance by measured current. "
            "Instantaneous V/I exists only as a diagnostic probe."
            if passed else
            "The SPICE control path does not satisfy the no-instantaneous-V/I contract."
        ),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", default=str(Path(__file__).resolve().parents[1] / "spice" / "circuits" / "full_component_template.cir"))
    ap.add_argument("--json-out")
    args = ap.parse_args()
    result = audit(Path(args.path))
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    print(payload)
    if args.json_out:
        Path(args.json_out).write_text(payload + "\n", encoding="utf-8")
    raise SystemExit(0 if result["status"] == "pass" else 2)


if __name__ == "__main__":
    main()
