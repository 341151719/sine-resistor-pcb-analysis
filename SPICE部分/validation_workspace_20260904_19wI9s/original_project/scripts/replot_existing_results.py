#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regenerate readable PNG figures from existing per-case CSV files.

This helper is optional. It does NOT rerun ngspice. The main rerun path is:

    python scripts/run_sweeps.py --clean

By default this script does not rewrite existing CSV files. It recomputes derived
columns in memory, refreshes PNGs, and optionally refreshes summary JSON/CSV.
Use --update-derived-csv only when you explicitly want the CSV files normalized
with the current derived diagnostic columns.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from run_sweeps import (
    CASES,
    RESULTS,
    SpeakerTS,
    SimConfig,
    add_derived,
    plot_case,
    summarize,
)


def load_config(case_dir: Path) -> tuple[str, str, SpeakerTS, SimConfig]:
    cfg_path = case_dir / f"{case_dir.name}_config.json"
    if not cfg_path.exists():
        raise FileNotFoundError(f"Missing config JSON for {case_dir.name}: {cfg_path}")
    obj = json.loads(cfg_path.read_text(encoding="utf-8"))
    spk_raw = obj.get("speaker", {})
    cfg_raw = obj.get("config", {})
    spk_fields = {k: spk_raw[k] for k in SpeakerTS.__dataclass_fields__ if k in spk_raw}
    cfg_fields = {k: cfg_raw[k] for k in SimConfig.__dataclass_fields__ if k in cfg_raw}
    return obj.get("case", case_dir.name), obj.get("model", "unknown"), SpeakerTS(**spk_fields), SimConfig(**cfg_fields)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case-filter", default="", help="Substring filter for case names")
    ap.add_argument("--no-summary", action="store_true", help="Only regenerate PNGs; do not refresh summary JSON/CSV")
    ap.add_argument("--update-derived-csv", action="store_true", help="Rewrite case CSVs with current derived diagnostic columns")
    args = ap.parse_args()

    if not CASES.exists():
        raise SystemExit(f"No case directory found: {CASES}")

    rows = []
    count = 0
    for case_dir in sorted(p for p in CASES.iterdir() if p.is_dir()):
        if args.case_filter and args.case_filter not in case_dir.name:
            continue
        csv_path = case_dir / f"{case_dir.name}.csv"
        if not csv_path.exists():
            continue
        name, model, spk, cfg = load_config(case_dir)
        df = pd.read_csv(csv_path)
        df = add_derived(df, spk, cfg)

        if args.update_derived_csv:
            df.to_csv(csv_path, index=False)

        plot_case(df, name, case_dir / f"{name}.png", cfg=cfg, tail_only=False)
        plot_case(df, name, case_dir / f"{name}_tail.png", cfg=cfg, tail_only=True)

        if not args.no_summary:
            summary = summarize(df, spk, cfg, name, model)
            (case_dir / f"{name}_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
            rows.append(summary)
        count += 1
        print(f"REPLOT {name}")

    if rows and not args.no_summary:
        RESULTS.mkdir(exist_ok=True)
        pd.DataFrame(rows).to_csv(RESULTS / "all_summary.csv", index=False)
    print(f"Done. Replotted {count} case(s).")


if __name__ == "__main__":
    main()
