from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path


def _capture(args, timeout=3):
    try:
        return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL, timeout=timeout).strip()
    except Exception:
        return ""


def _memory_bytes():
    values = {}
    try:
        for line in Path('/proc/meminfo').read_text(encoding='utf-8').splitlines():
            if ':' not in line:
                continue
            key, rest = line.split(':', 1)
            if key in {'MemTotal', 'MemAvailable'}:
                parts = rest.strip().split()
                values[key] = int(parts[0]) * 1024
    except Exception:
        pass
    return values


def _gpus(policy=None):
    policy = policy or {}
    free_ratio_threshold = float(policy.get('eligible_gpu_free_ratio', 0.70))
    max_util = int(policy.get('eligible_gpu_max_utilization', 50))
    raw = _capture([
        'nvidia-smi',
        '--query-gpu=index,name,memory.total,memory.used,memory.free,utilization.gpu',
        '--format=csv,noheader,nounits',
    ])
    out = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = [p.strip() for p in line.split(',')]
        if len(parts) != 6:
            continue
        try:
            idx = int(parts[0]); total = int(parts[2]); used = int(parts[3]); free = int(parts[4]); util = int(parts[5])
        except ValueError:
            continue
        ratio = (float(free) / float(total)) if total else 0.0
        out.append({
            'index': idx,
            'name': parts[1],
            'memory_total_mb': total,
            'memory_used_mb': used,
            'memory_free_mb': free,
            'memory_free_ratio': round(ratio, 4),
            'utilization_percent': util,
            'eligible': ratio >= free_ratio_threshold and util <= max_util,
        })
    return out


def inspect_resources(cwd=None, compute_policy=None):
    cwd = Path(cwd or os.getcwd()).resolve()
    count = os.cpu_count() or 1
    load = list(os.getloadavg()) if hasattr(os, 'getloadavg') else None
    mem = _memory_bytes()
    gpus = _gpus(compute_policy or {})
    try:
        disk = shutil.disk_usage(str(cwd))
        disk_info = {'total_bytes': disk.total, 'used_bytes': disk.used, 'free_bytes': disk.free}
    except Exception:
        disk_info = None
    return {
        'cpu': {'count': count, 'loadavg': load},
        'memory': {
            'total_bytes': mem.get('MemTotal'),
            'available_bytes': mem.get('MemAvailable'),
        },
        'disk': disk_info,
        'gpus': gpus,
        'visible_gpu_count': len(gpus),
        'eligible_gpu_count': sum(1 for g in gpus if g.get('eligible')),
    }


def dumps_snapshot(snapshot):
    return json.dumps(snapshot, indent=2, ensure_ascii=False, sort_keys=True)
