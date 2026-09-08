#!/usr/bin/env python3
"""Resolve remaining non-graphical DRC findings."""
from pathlib import Path
import pcbnew

ROOT = Path(__file__).resolve().parents[1]
BOARD_PATH = ROOT / "project.kicad_pcb"
board = pcbnew.LoadBoard(str(BOARD_PATH))

j1 = board.FindFootprintByReference("J1")
if not j1:
    raise RuntimeError("J1 missing")
j1.FindPadByNumber("1").SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)

via_xy = tuple(pcbnew.VECTOR2I_MM(159.0985, 126.1075))
stub_ends = {
    tuple(pcbnew.VECTOR2I_MM(119.9735, 145.6565)),
    tuple(pcbnew.VECTOR2I_MM(120.9165, 146.5995)),
}
for item in list(board.GetTracks()):
    if isinstance(item, pcbnew.PCB_VIA) and tuple(item.GetPosition()) == via_xy and item.GetNetname() == "GPIO_SPARE8":
        board.Remove(item)
    elif isinstance(item, pcbnew.PCB_TRACK) and not isinstance(item, pcbnew.PCB_VIA):
        if item.GetNetname() == "SERVO_INT_N" and {tuple(item.GetStart()), tuple(item.GetEnd())} == stub_ends:
            board.Remove(item)

pcbnew.ZONE_FILLER(board).Fill(board.Zones())
pcbnew.SaveBoard(str(BOARD_PATH), board)
print(f"updated {BOARD_PATH}")
