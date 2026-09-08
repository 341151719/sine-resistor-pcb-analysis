#!/usr/bin/env python3
"""Add three front and three back assembly fiducials."""
from pathlib import Path
import pcbnew

ROOT = Path(__file__).resolve().parents[1]
BOARD_PATH = ROOT / "project.kicad_pcb"
LIB_DIR = ROOT / "easyedapro.pretty"
points = [(195.0, 55.0), (93.0, 70.0), (93.0, 135.0)]
for side, offset in (("front", 0), ("back", 3)):
    for index, (x, y) in enumerate(points, 1):
        # Reload for every addition. KiCad 10.0.4's Python bindings can
        # invalidate footprint wrappers after repeated board mutations.
        board = pcbnew.LoadBoard(str(BOARD_PATH))
        ref = f"FID{index + offset}"
        if board.FindFootprintByReference(ref):
            continue
        fp = pcbnew.FootprintLoad(str(LIB_DIR), "AAI_Fiducial_1mm_Mask2mm")
        fp.SetReference(ref)
        pos = pcbnew.VECTOR2I_MM(x, y)
        fp.SetPosition(pos)
        if side == "back":
            fp.Flip(pos, False)
        board.Add(fp)
        pcbnew.SaveBoard(str(BOARD_PATH), board)

board = pcbnew.LoadBoard(str(BOARD_PATH))
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
pcbnew.SaveBoard(str(BOARD_PATH), board)
print(f"updated {BOARD_PATH}")
