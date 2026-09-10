#!/usr/bin/env python3
"""Cross-check V8 pcb_analysis.json against release BOM_SMT/CPL_SMT.
Usage: python release_assembly_crosscheck.py pcb_analysis.json BOM_SMT.csv CPL_SMT.csv
"""
import csv,json,sys
if len(sys.argv)!=4:
    raise SystemExit('usage: release_assembly_crosscheck.py pcb_analysis.json BOM_SMT.csv CPL_SMT.csv')
j,b,c=sys.argv[1:]
d=json.load(open(j,encoding='utf8'))
fps={x['reference']:x for x in d['footprints']}
bom={r['Refs']:r for r in csv.DictReader(open(b,encoding='utf-8-sig'))}
cpl={r['Ref']:r for r in csv.DictReader(open(c,encoding='utf-8-sig'))}
errs=[]
for ref,r in bom.items():
    if ref not in fps: errs.append((ref,'missing PCB')); continue
    if ref not in cpl: errs.append((ref,'missing CPL')); continue
    f,p=fps[ref],cpl[ref]
    if r['Value'].strip()!=f['value'].strip(): errs.append((ref,'value',f['value'],r['Value']))
    pcbfp=f['footprint'].split(':')[-1]; bomfp=r['Footprint'].split(':')[-1]; cplfp=p['Package'].split(':')[-1]
    if pcbfp!=bomfp: errs.append((ref,'BOM footprint',pcbfp,bomfp))
    if pcbfp!=cplfp: errs.append((ref,'CPL footprint',pcbfp,cplfp))
    x,y,rot=float(p['PosX']),float(p['PosY']),float(p['Rot'])
    if abs(x-f['x'])>1e-5 or abs(y+f['y'])>1e-5: errs.append((ref,'XY',(f['x'],f['y']),(x,y)))
    if abs(((rot-f['angle']+180)%360)-180)>1e-5: errs.append((ref,'rotation',f['angle'],rot))
    side=p['Side'].lower(); expected='top' if f['layer']=='F.Cu' else 'bottom'
    if side!=expected: errs.append((ref,'side',expected,side))
print(f'BOM={len(bom)} CPL={len(cpl)} PCB_footprints={len(fps)} errors={len(errs)}')
for e in errs: print(e)
raise SystemExit(1 if errs else 0)
