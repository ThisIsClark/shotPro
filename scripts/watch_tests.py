#!/usr/bin/env python3
"""Opt-in local watcher: debounce source changes, run one isolated suite at a time."""
import argparse
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]

def snapshot(root=ROOT):
    paths=[]
    for folder in ('app','static','templates','tests','scripts','.github'):
        paths.extend((root/folder).rglob('*'))
    paths.extend(root.glob('test_*.py'))
    paths.extend(root/p for p in ('requirements.txt','AGENTS.md'))
    return {str(p.relative_to(root)):(p.stat().st_mtime_ns,p.stat().st_size) for p in paths
            if p.is_file() and '__pycache__' not in p.parts and p.suffix in ('.py','.js','.cjs','.html','.css','.yml','.yaml','.txt','.md')}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--full',action='store_true',help='Run full suite on save; default quick suite')
    args=parser.parse_args()
    command=[sys.executable,str(ROOT/'scripts/verify_site.py')]+([] if args.full else ['--quick'])
    state=None
    print('Watching source files. Ctrl+C stops. Reports: artifacts/verification/index.html',flush=True)
    try:
        while True:
            current=snapshot()
            if current!=state:
                time.sleep(1)
                if snapshot()!=current:continue
                state=current
                subprocess.run(command,cwd=ROOT)
            time.sleep(1)
    except KeyboardInterrupt:
        print('\nWatcher stopped.')

if __name__=='__main__':main()
