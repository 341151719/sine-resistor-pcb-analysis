#!/usr/bin/env python3
"""Move U4's existing 100 nF bypass capacitors to the supply pins."""
from pathlib import Path
import pcbnew

ROOT = Path(__file__).resolve().parents[1]
BOARD_PATH = ROOT / "project.kicad_pcb"
board = pcbnew.LoadBoard(str(BOARD_PATH))

def remove_tracks_touching(points):
    keys = {tuple(p) for p in points}
    for item in list(board.GetTracks()):
        if isinstance(item, pcbnew.PCB_TRACK) and (
            tuple(item.GetStart()) in keys or tuple(item.GetEnd()) in keys
        ):
            board.Remove(item)

def add_track(net, start, end, width=0.5):
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(start)
    track.SetEnd(end)
    track.SetWidth(pcbnew.FromMM(width))
    track.SetLayer(pcbnew.F_Cu)
    track.SetNet(net)
    board.Add(track)

c15 = board.FindFootprintByReference("C15")
c16 = board.FindFootprintByReference("C16")
u4 = board.FindFootprintByReference("U4")
if not all((c15, c16, u4)):
    raise RuntimeError("C15, C16, or U4 missing")
c15_old_pads = [pad.GetPosition() for pad in c15.Pads()]
c16_old_pads = [pad.GetPosition() for pad in c16.Pads()]

# C15: ANA_P pad 1 sits on the existing U4-pin-8/FB1 rail segment.
c15.SetPosition(pcbnew.VECTOR2I_MM(130.500, 96.360))
c15.SetOrientationDegrees(90)
add_track(c15.FindPadByNumber("1").GetNet(), u4.FindPadByNumber("8").GetPosition(), c15.FindPadByNumber("1").GetPosition(), 0.5)

# C16: ANA_N pad 1 sits directly on the existing pin-4 rail segment.
c16.SetPosition(pcbnew.VECTOR2I_MM(116.873, 104.500))
c16.SetOrientationDegrees(-90)
add_track(c16.FindPadByNumber("1").GetNet(), u4.FindPadByNumber("4").GetPosition(), c16.FindPadByNumber("1").GetPosition(), 0.5)

# Remove only the old pad-entry segments after all footprint operations;
# Remove() invalidates unrelated SWIG wrappers in this KiCad build.
remove_tracks_touching(c15_old_pads)
remove_tracks_touching(c16_old_pads)

pcbnew.ZONE_FILLER(board).Fill(board.Zones())
pcbnew.SaveBoard(str(BOARD_PATH), board)
print(f"updated {BOARD_PATH}")
