#!/usr/bin/env python3
"""Aggregate independently-run result directories without hiding failures."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import pandas as pd


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+", type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--allow-acceptance-fail", action="store_true")
    args = ap.parse_args()

    frames = []
    missing = []
    for root in args.inputs:
        p = root / "all_summary.csv"
        if not p.exists():
            missing.append(str(p))
            continue
        df = pd.read_csv(p)
        df.insert(0, "source_results_dir", str(root))
        frames.append(df)
    if missing:
        raise SystemExit("Missing split summaries:\n" + "\n".join(missing))
    if not frames:
        raise SystemExit("No input summaries")

    out = args.out
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    df = pd.concat(frames, ignore_index=True, sort=False)
    df.to_csv(out / "all_summary.csv", index=False)
    sim_fail = df[df.get("simulation_status", pd.Series(index=df.index, dtype=str)).fillna("") != "completed"]
    acc_fail = df[df.get("acceptance_status", pd.Series(index=df.index, dtype=str)).fillna("") == "fail"]
    sim_fail.to_csv(out / "simulation_failures.csv", index=False)
    acc_fail.to_csv(out / "acceptance_failures.csv", index=False)
    status = {
        "cases": len(df),
        "simulation_failures": len(sim_fail),
        "acceptance_failures": len(acc_fail),
        "simulation_status_counts": df.get("simulation_status", pd.Series(dtype=str)).value_counts(dropna=False).to_dict(),
        "acceptance_status_counts": df.get("acceptance_status", pd.Series(dtype=str)).value_counts(dropna=False).to_dict(),
    }
    (out / "aggregate_status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(json.dumps(status, indent=2))
    if len(sim_fail):
        raise SystemExit(2)
    if len(acc_fail) and not args.allow_acceptance_fail:
        raise SystemExit(3)


if __name__ == "__main__":
    main()
