#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, shutil, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from rigor.policy import DEFAULT_POLICY
from rigor.util import project_root

MEMORY_TEMPLATES={
"HANDOFF.md":"# HANDOFF\n\n## Active outcome\n\nNone yet.\n\n## Current state\n\nInitialized by Codex Rigor.\n\n## Next action\n\nStart the next task with `$rigor-task`.\n",
"MEMORY.md":"# MEMORY\n\nVerified, non-obvious, durable project knowledge only.\n",
"LOG.md":"# LOG\n\nOperational chronology, experiments, failures, and run evidence.\n",
}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--root",default="."); ap.add_argument("--force",action="store_true"); ap.add_argument("--install-agents",action="store_true"); args=ap.parse_args()
    root=project_root(args.root); codex=root/".codex"; codex.mkdir(parents=True,exist_ok=True); policy_path=codex/"rigor.json"
    if policy_path.exists() and not args.force:
        print("policy exists: %s"%policy_path)
    else:
        policy=json.loads(json.dumps(DEFAULT_POLICY)); policy["enabled"]=True
        policy_path.write_text(json.dumps(policy,indent=2)+"\n",encoding="utf-8"); print("created: %s"%policy_path)
    for name,body in MEMORY_TEMPLATES.items():
        p=root/name
        if not p.exists(): p.write_text(body,encoding="utf-8"); print("created: %s"%p)
    if args.install_agents:
        from subprocess import check_call
        check_call([sys.executable,str(ROOT/"scripts"/"install_agents.py"),"--scope","project","--root",str(root)])
    print("Codex Rigor initialized for %s"%root)

if __name__=="__main__": main()
