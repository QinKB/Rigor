#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rigor.policy import load_policy
from rigor.resources import inspect_resources, dumps_snapshot
from rigor.util import project_root


def main():
    ap = argparse.ArgumentParser(description='Inspect resources for a Codex Rigor resource plan.')
    ap.add_argument('--root', default='.')
    ap.add_argument('--require-gpus', type=int, default=None)
    args = ap.parse_args()
    root = project_root(args.root)
    policy, _ = load_policy(root)
    snap = inspect_resources(root, policy.get('compute', {}))
    print(dumps_snapshot(snap))
    if args.require_gpus is not None and snap.get('eligible_gpu_count', 0) < args.require_gpus:
        raise SystemExit('eligible GPUs %d < required %d' % (snap.get('eligible_gpu_count', 0), args.require_gpus))


if __name__ == '__main__':
    main()
