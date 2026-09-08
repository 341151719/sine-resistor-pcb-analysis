from pathlib import Path
import re, subprocess, pandas as pd, numpy as np, json, os, sys

ROOT=Path(__file__).resolve().parent
TEMPLATE=(ROOT/'es_dynamic_loop_fast.cir').read_text()
OUT=ROOT/'results_h12_sweep'
OUT.mkdir(exist_ok=True)

cases=[]
def add(name, **kw): cases.append((name,kw))

# Core board revisions / source impedance
for r10 in ['100k','6.8k']:
    for lsrc in ['0.2u','1u','3u','10u']:
        add(f'r10_{r10}_lsrc_{lsrc}', R10VAL=r10, LSRC=lsrc, IESVAL='70u', ENHIGH='0')
# E/S source current uncertainty at V7 R10
for ies in ['6u','20u','40u','70u']:
    add(f'r10_100k_ies_{ies}', R10VAL='100k', IESVAL=ies, LSRC='1u', ENHIGH='0')
# State timing sensitivity
for ton,toff in [('1u','1u'),('3u','1u'),('5u','2u'),('10u','3u')]:
    add(f'timing_on_{ton}_off_{toff}', R10VAL='100k', IESVAL='70u', TON=ton, TOFF=toff, LSRC='1u', ENHIGH='0')
# Single optocoupler enable window; not periodic
for r10 in ['100k','6.8k']:
    for lsrc in ['1u','3u']:
        add(f'enpulse_r10_{r10}_lsrc_{lsrc}', R10VAL=r10, IESVAL='70u', LSRC=lsrc, ENHIGH='3.3', EN_DELAY='100u', EN_WIDTH='100u')
# Ground bridge stress test
for gl in ['2n','10n','50n']:
    add(f'gndL_{gl}', R10VAL='100k', IESVAL='70u', LSRC='3u', GND_L=gl, ENHIGH='0')

# de-duplicate names
seen=set(); uniq=[]
for x in cases:
    if x[0] not in seen: uniq.append(x); seen.add(x[0])
cases=uniq

def patch_param(text,key,val):
    pat=rf'(?<![A-Za-z0-9_]){re.escape(key)}=[^\s]+'
    new,n=re.subn(pat,f'{key}={val}',text,count=1)
    if not n:
        raise RuntimeError(f'parameter {key} not found')
    return new

def analyze(path):
    df=pd.read_csv(path,sep=r'\s+')
    t=df['time'].to_numpy()
    y=df['v(TP8)'].to_numpy()
    es=df['v(OPA_ES)'].to_numpy()-df['v(PWR_N)'].to_numpy()
    st=df['v(ES_STATE)'].to_numpy()
    # late window excludes startup/one-shot command
    m=t>=0.4e-3
    tl=t[m]; yl=y[m]
    pp=float(np.ptp(yl)); rms=float(np.sqrt(np.mean((yl-np.mean(yl))**2)))
    # interpolate to uniform 50 ns for spectral fingerprint
    dt=50e-9
    tu=np.arange(tl[0],tl[-1],dt)
    yu=np.interp(tu,tl,yl)
    yu=yu-yu.mean()
    if len(yu)>16:
        win=np.hanning(len(yu)); sp=np.abs(np.fft.rfft(yu*win)); f=np.fft.rfftfreq(len(yu),dt)
        band=(f>=10e3)&(f<=1e6)
        if np.any(band):
            ib=np.where(band)[0]
            j=ib[np.argmax(sp[band])]
            fdom=float(f[j]); amp=float(sp[j])
        else: fdom=0.; amp=0.
    else: fdom=0.; amp=0.
    # state transitions/crossings around mid-level
    b=st>0.5
    crossings=int(np.count_nonzero(b[1:]!=b[:-1]))
    return dict(tp8_pp=pp,tp8_rms=rms,f_dom_hz=fdom,es_min=float(es.min()),es_max=float(es.max()),state_min=float(st.min()),state_max=float(st.max()),state_crossings=crossings)

rows=[]
for i,(name,params) in enumerate(cases,1):
    text=TEMPLATE
    for k,v in params.items(): text=patch_param(text,k,v)
    outdat=OUT/f'{name}.dat'
    text=re.sub(r'results_h12_fast/tran\.dat',outdat.as_posix(),text)
    cir=OUT/f'{name}.cir'; log=OUT/f'{name}.log'
    cir.write_text(text)
    print(f'[{i}/{len(cases)}] {name}',flush=True)
    proc=subprocess.run(['ngspice','-b',str(cir)],cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    log.write_text(proc.stdout)
    row={'case':name,'returncode':proc.returncode,**params}
    if proc.returncode==0 and outdat.exists():
        try: row.update(analyze(outdat))
        except Exception as e: row['analysis_error']=repr(e)
    rows.append(row)

pd.DataFrame(rows).to_csv(OUT/'summary.csv',index=False)
print(pd.DataFrame(rows)[['case','returncode','tp8_pp','f_dom_hz','es_min','es_max','state_min','state_max','state_crossings']].to_string(index=False))
