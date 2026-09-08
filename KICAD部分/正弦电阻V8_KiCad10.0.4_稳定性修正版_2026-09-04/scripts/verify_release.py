#!/usr/bin/env python3
"""Machine-readable V8 release gate."""
from pathlib import Path
import csv, json
import pcbnew

ROOT = Path(__file__).resolve().parents[1]
REL = ROOT / "release" / "V8_2026-09-04"
board = pcbnew.LoadBoard(str(ROOT / "project.kicad_pcb"))
checks = {}

def mm(v): return round(pcbnew.ToMM(v), 6)
def fp(ref):
    found = board.FindFootprintByReference(ref)
    if not found: raise RuntimeError(f"missing {ref}")
    return found

r12 = fp("R12")
checks["r12"] = {
    "value": r12.GetValue(),
    "position_mm": [mm(r12.GetPosition().x), mm(r12.GetPosition().y)],
    "orientation_deg": r12.GetOrientationDegrees(),
    "pads": {
        p.GetNumber(): {
            "net": p.GetNetname(),
            "position_mm": [mm(p.GetPosition().x), mm(p.GetPosition().y)],
            "size_mm": [mm(p.GetSize().x), mm(p.GetSize().y)],
        } for p in r12.Pads()
    },
}
checks["values"] = {ref: fp(ref).GetValue() for ref in ("C27", "R10", "C16")}
checks["c16_position_mm"] = [mm(fp("C16").GetPosition().x), mm(fp("C16").GetPosition().y)]
checks["testpoints_pth"] = all(
    fp(f"TP{i}").FindPadByNumber("1").GetAttribute() == pcbnew.PAD_ATTRIB_PTH
    and mm(fp(f"TP{i}").FindPadByNumber("1").GetDrillSize().x) == 0.7
    for i in range(1, 21)
)
checks["j7_pth"] = all(p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH and mm(p.GetDrillSize().x) == 0.65 for p in fp("J7").Pads())
checks["fiducials"] = sorted(f.GetReference() for f in board.GetFootprints() if f.GetReference().startswith("FID"))

def rows(name):
    with (REL / "assembly" / name).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))
bom, cpl = rows("BOM_SMT.csv"), rows("CPL_SMT.csv")
checks["assembly"] = {
    "bom_count": len(bom), "cpl_count": len(cpl),
    "refs_equal": {r["Refs"] for r in bom} == {r["Ref"] for r in cpl},
}
drc = json.load((REL / "reports" / "drc.json").open(encoding="utf-8"))
checks["drc"] = {
    "unconnected": len(drc["unconnected_items"]),
    "non_graphical": [v["type"] for v in drc["violations"] if v["type"] not in {"silk_over_copper", "silk_overlap", "courtyards_overlap"}],
    "graphical_warning_count": len(drc["violations"]),
}
def erc_signature(path):
    data = json.load(path.open(encoding="utf-8"))
    violations = [v for sheet in data["sheets"] for v in sheet.get("violations", [])]
    counts = {}
    for v in violations:
        counts[v["type"]] = counts.get(v["type"], 0) + 1
    return {"total": len(violations), "by_type": counts}
checks["erc"] = erc_signature(REL / "reports" / "erc.json")
checks["erc"]["unchanged_from_conversion_baseline"] = (
    {k: v for k, v in checks["erc"].items() if k != "unchanged_from_conversion_baseline"}
    == erc_signature(ROOT / "verification" / "baseline" / "erc.json")
)

expected = (
    checks["r12"]["value"] == "4.7R 2W"
    and checks["r12"]["position_mm"] == [154.354, 89.74]
    and checks["r12"]["pads"]["1"]["net"] == "DRV"
    and checks["r12"]["pads"]["2"]["net"] == "SNUB_MID"
    and checks["values"]["C27"] == "10nF"
    and checks["values"]["R10"] == "6.8kR"
    and checks["testpoints_pth"] and checks["j7_pth"]
    and checks["fiducials"] == ["FID1", "FID2", "FID3", "FID4", "FID5", "FID6"]
    and checks["assembly"] == {"bom_count": 73, "cpl_count": 73, "refs_equal": True}
    and checks["drc"]["unconnected"] == 0 and not checks["drc"]["non_graphical"]
    and checks["erc"]["unchanged_from_conversion_baseline"]
)
result = {"pass": expected, "checks": checks}
(REL / "reports" / "release_gate.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
raise SystemExit(0 if expected else 1)
