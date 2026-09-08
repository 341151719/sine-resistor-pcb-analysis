#!/usr/bin/env python3
"""Make all named test points and the SWD header genuinely through-hole."""
from pathlib import Path
import pcbnew

ROOT = Path(__file__).resolve().parents[1]
BOARD_PATH = ROOT / "project.kicad_pcb"
board = pcbnew.LoadBoard(str(BOARD_PATH))

# Reuse a known-good through-hole layer set from the existing J13 connector.
j13 = board.FindFootprintByReference("J13")
if not j13:
    raise RuntimeError("reference PTH footprint J13 missing")
pth_layers = next(iter(j13.Pads())).GetLayerSet()

def make_pth(pad, diameter, drill):
    pad.SetAttribute(pcbnew.PAD_ATTRIB_PTH)
    pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
    pad.SetSize(pcbnew.VECTOR2I_MM(diameter, diameter))
    pad.SetDrillSize(pcbnew.VECTOR2I_MM(drill, drill))
    pad.SetLayerSet(pth_layers)

for index in range(1, 21):
    fp = board.FindFootprintByReference(f"TP{index}")
    if not fp:
        raise RuntimeError(f"TP{index} missing")
    make_pth(fp.FindPadByNumber("1"), 1.6, 0.7)

j7 = board.FindFootprintByReference("J7")
if not j7:
    raise RuntimeError("J7 missing")
for pad in j7.Pads():
    # 1.05 mm preserves 0.22 mm copper spacing at 1.27 mm pitch.
    make_pth(pad, 1.05, 0.65)

# TP11's original 1 mm SMD location was only 0.508 mm from MUL_RAW.
# Move the enlarged PTH pad onto the preceding ANA_P route endpoint and
# remove the obsolete terminal stub to preserve clearance.
tp11 = board.FindFootprintByReference("TP11")
tp11.SetPosition(pcbnew.VECTOR2I_MM(97.331, 111.192))
stub_ends = {
    tuple(pcbnew.VECTOR2I_MM(97.331, 112.346)),
    tuple(pcbnew.VECTOR2I_MM(97.331, 111.192)),
}
for item in list(board.GetTracks()):
    if isinstance(item, pcbnew.PCB_TRACK) and {
        tuple(item.GetStart()), tuple(item.GetEnd())
    } == stub_ends:
        board.Remove(item)

pcbnew.ZONE_FILLER(board).Fill(board.Zones())
pcbnew.SaveBoard(str(BOARD_PATH), board)
print(f"updated {BOARD_PATH}")
