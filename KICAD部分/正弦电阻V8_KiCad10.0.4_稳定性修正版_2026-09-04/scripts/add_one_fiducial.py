#!/usr/bin/env python3
"""Add one fiducial per process to avoid KiCad 10.0.4 SWIG invalidation."""
from pathlib import Path
import sys
import pcbnew

if len(sys.argv) != 5:
    raise SystemExit("usage: add_one_fiducial.py REF front|back X_MM Y_MM")
ref, side, xs, ys = sys.argv[1:]
ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "project.kicad_pcb"
board = pcbnew.LoadBoard(str(path))
if board.FindFootprintByReference(ref):
    print(f"{ref} already exists")
    raise SystemExit(0)
footprint_name = "AAI_Fiducial_1mm_Mask2mm_Bottom" if side == "back" else "AAI_Fiducial_1mm_Mask2mm"
fp = pcbnew.FootprintLoad(str(ROOT / "easyedapro.pretty"), footprint_name)
fp.SetReference(ref)
pos = pcbnew.VECTOR2I_MM(float(xs), float(ys))
fp.SetPosition(pos)
if side not in ("front", "back"):
    raise SystemExit(f"invalid side {side}")
board.Add(fp)
pcbnew.SaveBoard(str(path), board)
print(f"added {ref} on {side}")
