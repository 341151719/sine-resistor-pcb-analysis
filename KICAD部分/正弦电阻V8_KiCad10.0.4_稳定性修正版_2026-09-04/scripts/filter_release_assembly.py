#!/usr/bin/env python3
"""Create mutually consistent SMT BOM/CPL files from KiCad exports."""
from pathlib import Path
import csv

ROOT = Path(__file__).resolve().parents[1]
ASSEMBLY = ROOT / "release" / "V8_2026-09-04" / "assembly"

def read(name):
    with (ASSEMBLY / name).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def write(name, rows, fields):
    with (ASSEMBLY / name).open("w", encoding="utf-8-sig", newline="") as f:
        out = csv.DictWriter(f, fieldnames=fields, quoting=csv.QUOTE_MINIMAL)
        out.writeheader(); out.writerows(rows)

bom_all = read("BOM_all.csv")
cpl_all = read("CPL_all.csv")
bom_smt = [row for row in bom_all if row["Assembly Status"].strip().upper() == "SMT"]
smt_refs = {row["Refs"] for row in bom_smt}
cpl_by_ref = {row["Ref"]: row for row in cpl_all}

missing = sorted(smt_refs - cpl_by_ref.keys())
extra = sorted(cpl_by_ref.keys() - smt_refs)
if missing:
    raise SystemExit(f"SMT BOM references missing from CPL: {missing}")

cpl_smt = [cpl_by_ref[ref] for ref in sorted(smt_refs)]
write("BOM_SMT.csv", bom_smt, list(bom_all[0]))
write("CPL_SMT.csv", cpl_smt, list(cpl_all[0]))

report = ASSEMBLY / "assembly_crosscheck.txt"
report.write_text(
    f"BOM SMT refs: {len(smt_refs)}\n"
    f"CPL SMT refs: {len(cpl_smt)}\n"
    f"Missing from CPL: {missing}\n"
    f"Non-SMT/export-only refs excluded: {extra}\n",
    encoding="utf-8",
)
print(report.read_text(encoding="utf-8"), end="")
