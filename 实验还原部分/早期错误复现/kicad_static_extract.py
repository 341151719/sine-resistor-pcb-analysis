#!/usr/bin/env python3
from pathlib import Path
import re, sys

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('.')

def balanced_block(text, start):
    depth=0; in_str=False; esc=False
    for i in range(start, len(text)):
        c=text[i]
        if in_str:
            if esc: esc=False
            elif c=='\\': esc=True
            elif c=='"': in_str=False
            continue
        if c=='"': in_str=True
        elif c=='(': depth += 1
        elif c==')':
            depth -= 1
            if depth==0: return text[start:i+1]
    return text[start:]

def footprint_for_ref(text, ref):
    needle=f'(property "Reference" "{ref}"'
    pos=text.find(needle)
    if pos<0: return None
    start=text.rfind('(footprint',0,pos)
    return balanced_block(text,start)

def pad_map(block):
    out={}
    for m in re.finditer(r'\(pad\s+"([^"]+)"',block):
        b=balanced_block(block,m.start())
        net=re.search(r'\(net\s+(?:\d+\s+)?"([^"]+)"\)',b)
        out[m.group(1)] = net.group(1) if net else None
    return out

def value(block):
    m=re.search(r'\(property\s+"Value"\s+"([^"]+)"',block)
    return m.group(1) if m else None

pcbs=list(root.rglob('project.kicad_pcb'))
for tag in ('V7','V8'):
    cand=[p for p in pcbs if tag in str(p)]
    if not cand: continue
    p=cand[0]
    text=p.read_text(errors='ignore')
    print(f'[{tag}] {p}')
    for ref in ('R10','R5','U1','U4','U7'):
        b=footprint_for_ref(text,ref)
        if b:
            print(f'  {ref}: value={value(b)} pads={pad_map(b)}')
