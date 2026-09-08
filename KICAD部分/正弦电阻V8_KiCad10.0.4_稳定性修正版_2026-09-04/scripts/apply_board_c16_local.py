#!/usr/bin/env python3
"""Move only U4's badly remote ANA_N bypass capacitor C16."""
from pathlib import Path
import pcbnew

ROOT = Path(__file__).resolve().parents[1]
BOARD_PATH = ROOT / "project.kicad_pcb"
board = pcbnew.LoadBoard(str(BOARD_PATH))
c16 = board.FindFootprintByReference("C16")
u4 = board.FindFootprintByReference("U4")
if not c16 or not u4:
    raise RuntimeError("C16 or U4 missing")
old_pads = {tuple(p.GetPosition()) for p in c16.Pads()}
net = c16.FindPadByNumber("1").GetNet()
u4_pin4 = u4.FindPadByNumber("4").GetPosition()

c16.SetPosition(pcbnew.VECTOR2I_MM(116.873, 104.500))
c16.SetOrientationDegrees(-90)
new_pad1 = c16.FindPadByNumber("1").GetPosition()

t = pcbnew.PCB_TRACK(board)
t.SetStart(u4_pin4); t.SetEnd(new_pad1)
t.SetWidth(pcbnew.FromMM(0.5)); t.SetLayer(pcbnew.F_Cu); t.SetNet(net)
board.Add(t)

for item in list(board.GetTracks()):
    if isinstance(item, pcbnew.PCB_TRACK) and (
        tuple(item.GetStart()) in old_pads or tuple(item.GetEnd()) in old_pads
    ):
        board.Remove(item)

pcbnew.ZONE_FILLER(board).Fill(board.Zones())
pcbnew.SaveBoard(str(BOARD_PATH), board)
print(f"updated {BOARD_PATH}")
