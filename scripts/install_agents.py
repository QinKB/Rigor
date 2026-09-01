#!/usr/bin/env python3
from __future__ import annotations
import argparse, shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--scope",choices=["user","project"],default="project"); ap.add_argument("--root",default="."); ap.add_argument("--force",action="store_true"); args=ap.parse_args()
    dest=(Path.home()/".codex"/"agents") if args.scope=="user" else (Path(args.root).resolve()/".codex"/"agents")
    dest.mkdir(parents=True,exist_ok=True)
    for src in sorted((ROOT/"templates"/"agents").glob("*.toml")):
        target=dest/src.name
        if target.exists() and not args.force:
            print("skip existing: %s"%target); continue
        shutil.copy2(src,target); print("installed: %s"%target)

if __name__=="__main__": main()
