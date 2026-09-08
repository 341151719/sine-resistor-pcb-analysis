#!/usr/bin/env python3
"""Apply deterministic V8 PCB corrections; run under KiCad 10 AppRun Python."""
from pathlib import Path
import pcbnew

ROOT = Path(__file__).resolve().parents[1]
BOARD_PATH = ROOT / "project.kicad_pcb"
LIB_DIR = ROOT / "easyedapro.pretty"

board = pcbnew.LoadBoard(str(BOARD_PATH))

def set_value(ref, value):
    fp = board.FindFootprintByReference(ref)
    if fp is None:
        raise RuntimeError(f"missing footprint {ref}")
    fp.SetValue(value)
    return fp

# Explicit OPA548 robustness corrections.
set_value("C27", "10nF")
set_value("R10", "6.8kR")

# Replace the erroneous converted 0805 R12 with exact production geometry.
old = board.FindFootprintByReference("R12")
if old is None:
    raise RuntimeError("missing footprint R12")
net_by_pad = {pad.GetNumber(): pad.GetNet() for pad in old.Pads()}
board.Remove(old)
# Make reruns idempotent by removing the prior short fanout, if present.
target_a = pcbnew.VECTOR2I_MM(151.287712, 89.740)
target_b = pcbnew.VECTOR2I_MM(154.907, 89.359)
for item in list(board.GetTracks()):
    if not isinstance(item, pcbnew.PCB_TRACK):
        continue
    ends = {tuple(item.GetStart()), tuple(item.GetEnd())}
    if ends == {tuple(target_a), tuple(target_b)}:
        board.Remove(item)
new = pcbnew.FootprintLoad(str(LIB_DIR), "AAI_R_2512_Production_4R7_2W")
if new is None:
    raise RuntimeError("unable to load R12 production footprint")
new.SetReference("R12")
new.SetValue("4.7R 2W")
new.SetPosition(pcbnew.VECTOR2I_MM(154.354, 89.740))
new.SetOrientationDegrees(180)
for pad in new.Pads():
    pad.SetNet(net_by_pad[pad.GetNumber()])
board.Add(new)

# Preserve the converted route and add only the short production-pad fanout.
# Pad 1 lies on the existing wide DRV trace. Pad 2 needs a short link to the
# existing SNUB_MID vertical route at (154.907, 89.359).
pad2 = new.FindPadByNumber("2")
link = pcbnew.PCB_TRACK(board)
link.SetStart(pad2.GetPosition())
link.SetEnd(pcbnew.VECTOR2I_MM(154.907, 89.359))
link.SetWidth(pcbnew.FromMM(1.016))
link.SetLayer(pcbnew.F_Cu)
link.SetNet(net_by_pad["2"])
board.Add(link)

# Refill all copper zones so their clearances reflect the recovered footprint.
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
pcbnew.SaveBoard(str(BOARD_PATH), board)
print(f"updated {BOARD_PATH}")
