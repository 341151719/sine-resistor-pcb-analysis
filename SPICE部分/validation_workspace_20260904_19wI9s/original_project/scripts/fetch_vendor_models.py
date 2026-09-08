#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fetch official vendor model files after you confirm each vendor license.
This script intentionally requires --accept-licenses.
"""
from pathlib import Path
import argparse, json, urllib.request, zipfile, shutil
ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT/'spice/models/vendor_fetch_manifest.json'
OUT = ROOT/'spice/models/vendor_downloads'

def print_links(manifest):
    for m in manifest['models']:
        print('\n',m['part'], '-', m['vendor'])
        print(' page:', m['official_page'])
        for u in m['model_candidates']:
            print(' candidate:', u)
        print(' status:', m.get('status',''))

def download(url, outdir):
    fn = outdir / url.rstrip('/').split('/')[-1]
    if '.' not in fn.name:
        fn = fn.with_suffix('.download')
    req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    fn.write_bytes(data)
    print('saved', fn, len(data), 'bytes')
    if zipfile.is_zipfile(fn):
        ex = outdir / (fn.stem + '_unzipped')
        ex.mkdir(exist_ok=True)
        with zipfile.ZipFile(fn) as z:
            z.extractall(ex)
        print('unzipped to', ex)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--print-links', action='store_true')
    ap.add_argument('--accept-licenses', action='store_true', help='You confirm vendor license terms for downloaded models.')
    ap.add_argument('--parts', nargs='*', default=[])
    args=ap.parse_args()
    manifest=json.loads(MANIFEST.read_text(encoding='utf-8'))
    if args.print_links or not args.accept_licenses:
        print_links(manifest)
    if not args.accept_licenses:
        print('\nNo files downloaded. Re-run with --accept-licenses after reviewing vendor terms.')
        return
    OUT.mkdir(parents=True, exist_ok=True)
    wanted=set(p.upper() for p in args.parts)
    for m in manifest['models']:
        if wanted and m['part'].upper() not in wanted: continue
        # Conservative: download direct candidate URLs only; product pages are printed for manual access.
        for u in m['model_candidates']:
            if '#design' in u or 'product/' in u:
                print('manual page:', u); continue
            try: download(u, OUT)
            except Exception as e: print('download failed:', u, repr(e))
if __name__=='__main__': main()
