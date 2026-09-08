#!/usr/bin/env python3
"""Static firmware audit for accidental instantaneous V/I impedance feedback.

This scanner is intentionally conservative. It does not prove runtime behavior;
it identifies code that requires manual review and verifies the intended command
pattern where source is available.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

SOURCE_EXTS = {".c", ".h", ".cc", ".cpp", ".hpp", ".ino", ".s", ".asm", ".rs"}
SKIP_DIRS = {".git", "build", "cmake-build-debug", "cmake-build-release", "Debug", "Release", "Middlewares", "Drivers"}

RISK_PATTERNS = [
    ("voltage_divided_by_current", re.compile(r"\b(?:v(?:oltage)?|vmeas|vspk|v_sense)\w*\s*/\s*(?:i(?:current)?|imeas|iport|i_sense)\w*", re.I)),
    ("impedance_assignment_with_division", re.compile(r"\b(?:z|r|impedance|reff|rest|zest)\w*\s*=\s*[^;\n]*/[^;\n]+", re.I)),
    ("reciprocal_current", re.compile(r"\b1(?:\.0+)?\s*/\s*(?:i|imeas|iport|current)\w*", re.I)),
]
ALLOWED_PATTERNS = [
    re.compile(r"(?:vcmd|v_cmd|dac_cmd|command)\w*\s*=\s*[^;\n]*(?:rtarget|r_target|rx|r_synth)\w*\s*\*\s*(?:i|imeas|iport|current)\w*", re.I),
    re.compile(r"(?:rtarget|r_target|rx|r_synth)\w*\s*\*\s*(?:i|imeas|iport|current)\w*", re.I),
]


def collect(root: Path) -> list[Path]:
    if root.is_file():
        return [root] if root.suffix.lower() in SOURCE_EXTS else []
    files = []
    for p in root.rglob("*"):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.is_file() and p.suffix.lower() in SOURCE_EXTS:
            files.append(p)
    return sorted(files)


def audit(root: Path) -> dict:
    files = collect(root)
    if not files:
        return {
            "root": str(root),
            "status": "not_auditable",
            "source_file_count": 0,
            "risk_hits": [],
            "allowed_multiply_hits": [],
            "conclusion": "No MCU firmware source files are present in the supplied project. Runtime firmware behavior cannot be signed off.",
        }
    risk_hits = []
    allowed_hits = []
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), 1):
            code = line.split("//", 1)[0]
            for name, pat in RISK_PATTERNS:
                if pat.search(code):
                    risk_hits.append({"file": str(path), "line": lineno, "rule": name, "text": line.strip()})
            if any(p.search(code) for p in ALLOWED_PATTERNS):
                allowed_hits.append({"file": str(path), "line": lineno, "text": line.strip()})
    status = "review_required" if risk_hits else "pass_static_scan"
    return {
        "root": str(root),
        "status": status,
        "source_file_count": len(files),
        "risk_hits": risk_hits,
        "allowed_multiply_hits": allowed_hits,
        "conclusion": (
            "Potential instantaneous V/I logic was found and requires manual control-flow review."
            if risk_hits else
            "No obvious instantaneous V/I feedback expression was found. Static scanning alone does not prove runtime behavior."
        ),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=str(Path(__file__).resolve().parents[1]))
    ap.add_argument("--json-out")
    ap.add_argument("--allow-missing", action="store_true", help="Return zero when no firmware source is supplied, while retaining not_auditable status")
    args = ap.parse_args()
    result = audit(Path(args.root))
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    print(payload)
    if args.json_out:
        Path(args.json_out).write_text(payload + "\n", encoding="utf-8")
    if result["status"] == "review_required":
        raise SystemExit(2)
    if result["status"] == "not_auditable" and not args.allow_missing:
        raise SystemExit(4)


if __name__ == "__main__":
    main()
