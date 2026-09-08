#!/usr/bin/env python3
"""Rollback the rejected C15/C16 placement trial exactly."""
from pathlib import Path
import pcbnew

ROOT = Path(__file__).resolve().parents[1]
BOARD_PATH = ROOT / "project.kicad_pcb"
board = pcbnew.LoadBoard(str(BOARD_PATH))
c15 = board.FindFootprintByReference("C15")
c16 = board.FindFootprintByReference("C16")
if not c15 or not c16:
    raise RuntimeError("C15 or C16 missing")

trial_points = {tuple(p.GetPosition()) for f in (c15, c16) for p in f.Pads()}
c15_net1, c15_net2 = c15.FindPadByNumber("1").GetNet(), c15.FindPadByNumber("2").GetNet()
c16_net1, c16_net2 = c16.FindPadByNumber("1").GetNet(), c16.FindPadByNumber("2").GetNet()

# Return footprints before track removal invalidates SWIG wrappers.
c15.SetPosition(pcbnew.VECTOR2I_MM(121.842, 105.361))
c15.SetOrientationDegrees(180)
c16.SetPosition(pcbnew.VECTOR2I_MM(123.924, 121.1735))
c16.SetOrientationDegrees(0)

for item in list(board.GetTracks()):
    if isinstance(item, pcbnew.PCB_TRACK) and (
        tuple(item.GetStart()) in trial_points or tuple(item.GetEnd()) in trial_points
    ):
        board.Remove(item)

def add(net, a, b, width):
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(pcbnew.VECTOR2I_MM(*a)); t.SetEnd(pcbnew.VECTOR2I_MM(*b))
    t.SetWidth(pcbnew.FromMM(width)); t.SetLayer(pcbnew.F_Cu); t.SetNet(net); board.Add(t)

add(c15_net1, (122.842, 102.932), (122.842, 105.361), 0.635)
add(c15_net1, (122.842, 105.361), (122.858, 105.377), 0.635)
add(c15_net2, (120.842, 105.361), (114.8825, 105.361), 1.016)
add(c16_net2, (124.924, 121.1735), (130.097, 116.0005), 1.016)
add(c16_net1, (122.904, 121.1535), (122.924, 121.1735), 0.635)

pcbnew.ZONE_FILLER(board).Fill(board.Zones())
pcbnew.SaveBoard(str(BOARD_PATH), board)
print(f"rolled back rejected decoupling placement in {BOARD_PATH}")
