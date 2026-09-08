#!/usr/bin/env python3
from pathlib import Path
import pcbnew
root = Path(__file__).resolve().parents[1]
path = root / "project.kicad_pcb"
board = pcbnew.LoadBoard(str(path))
for fp in board.GetFootprints():
    if fp.GetReference().startswith("FID"):
        fp.FindPadByNumber("1").SetLocalClearance(pcbnew.FromMM(0.6))
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
pcbnew.SaveBoard(str(path), board)
print("zones refilled")
