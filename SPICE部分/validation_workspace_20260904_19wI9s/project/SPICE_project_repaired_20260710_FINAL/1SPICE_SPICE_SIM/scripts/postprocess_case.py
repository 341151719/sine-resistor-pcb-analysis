#!/usr/bin/env python3
"""Re-run corrected acceptance post-processing on an existing ngspice case."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import run_sweeps as rs  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("case_dir", type=Path)
    ap.add_argument("--write-derived-csv", action="store_true")
    ap.add_argument("--plots", action="store_true")
    args = ap.parse_args()

    case_dir = args.case_dir.resolve()
    configs = list(case_dir.glob("*_config.json"))
    if len(configs) != 1:
        raise SystemExit(f"Expected exactly one *_config.json in {case_dir}, found {len(configs)}")
    cfg_path = configs[0]
    name = cfg_path.name.removesuffix("_config.json")
    payload = json.loads(cfg_path.read_text(encoding="utf-8"))
    spk = rs.SpeakerTS(**payload["speaker"])
    cfg = rs.SimConfig(**payload["config"])
    data_path = case_dir / f"{name}.dat"
    if not data_path.exists():
        raise SystemExit(f"Missing ngspice wrdata output: {data_path}")

    df = rs.add_derived(rs.read_wrdata(data_path), spk, cfg)
    summary = rs.summarize(df, spk, cfg, name, payload.get("model", "full"))
    if args.write_derived_csv:
        df.to_csv(case_dir / f"{name}.csv", index=False)
    dynamic_rows = df.attrs.get("dynamic_phasor_rows", [])
    if dynamic_rows:
        pd.DataFrame(dynamic_rows).to_csv(case_dir / f"{name}_dynamic_phasor.csv", index=False)
    (case_dir / f"{name}_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.plots:
        rs.plot_case(df, name, case_dir / f"{name}.png", cfg=cfg, tail_only=False)
        rs.plot_case(df, name, case_dir / f"{name}_tail.png", cfg=cfg, tail_only=True)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if summary.get("acceptance_status") == "fail":
        raise SystemExit(3)


if __name__ == "__main__":
    main()
