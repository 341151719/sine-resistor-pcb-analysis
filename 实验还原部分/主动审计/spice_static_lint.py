#!/usr/bin/env python3
"""Lint SPICE decks for known project-specific modeling blind spots.
Usage: python spice_static_lint.py /path/to/sine-resistor-pcb-analysis
No third-party packages required.
"""
from pathlib import Path
import re, sys
root = Path(sys.argv[1] if len(sys.argv)>1 else '.')
files = list(root.rglob('*.cir')) + list(root.rglob('*.inc')) + list(root.rglob('*.sp'))
checks = {
    'E/S hard-clamped to V-+0.6V': re.compile(r'^\s*V\S*\s+ES\s+(?:VMINUS|PWR_N)\s+0\.6\b', re.I|re.M),
    'stale V8 C27=10p': re.compile(r'^\s*C27\b[^\n]*\b10p\b', re.I|re.M),
    'R10=100k retained': re.compile(r'^\s*R10\b[^\n]*\b100k\b', re.I|re.M),
    'absolute Windows/WSL .include': re.compile(r'^\s*\.include\s+["\']?(?:/mnt/c/|[A-Za-z]:\\)', re.I|re.M),
}
for title, rx in checks.items():
    hits=[]
    for f in files:
        try: t=f.read_text(errors='ignore')
        except Exception: continue
        if rx.search(t): hits.append(f.relative_to(root))
    print(f'\n[{title}] {len(hits)}')
    for p in hits: print(' ', p)

print('\n[OPA548 J1/PDN disconnect signature]')
for f in root.rglob('*.cir'):
    t=f.read_text(errors='ignore')
    if not ('OPA548' in t and 'PWR_P' in t and 'PWR_N' in t):
        continue
    if not re.search(r'^\s*X\S*\s+[^\n]*\bVMINUS\s+VPLUS\s+[^\n]*\bOPA548\b',t,re.I|re.M):
        continue
    lines=[ln for ln in t.splitlines() if re.search(r'\b(VPLUS|VMINUS)\b',ln,re.I) and not ln.lstrip().upper().startswith(('*','X'))]
    bridge=any((('PWR_P' in ln.upper() and 'VPLUS' in ln.upper()) or ('PWR_N' in ln.upper() and 'VMINUS' in ln.upper())) for ln in lines)
    src=any(re.match(r'\s*V\S*\s+(?:VPLUS|VMINUS)\s+',ln,re.I) for ln in lines)
    if not (bridge or src):
        print(' ', f.relative_to(root))
