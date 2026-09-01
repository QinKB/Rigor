#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

PLUGIN_NAME = "rigor"
ROOT = Path(__file__).resolve().parents[1]


def load_marketplace(path: Path):
    if not path.exists():
        return {
            "name": "personal-plugins",
            "interface": {"displayName": "Personal Plugins"},
            "plugins": [],
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit("Cannot parse existing marketplace %s: %s" % (path, exc))
    if not isinstance(data, dict) or not isinstance(data.get("plugins", []), list):
        raise SystemExit("Existing marketplace has an unsupported shape: %s" % path)
    data.setdefault("name", "personal-plugins")
    data.setdefault("interface", {"displayName": "Personal Plugins"})
    data.setdefault("plugins", [])
    return data


def copy_plugin(source: Path, destination: Path, force: bool):
    source = source.resolve()
    destination = destination.resolve()
    if source == destination:
        return None
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not force:
        raise SystemExit("Plugin already exists at %s. Re-run with --force to replace it safely." % destination)

    backup = None
    stage = Path(tempfile.mkdtemp(prefix=".%s-install-" % PLUGIN_NAME, dir=str(destination.parent))) / PLUGIN_NAME
    try:
        shutil.copytree(
            source,
            stage,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git", ".pytest_cache"),
        )
        if destination.exists():
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup = destination.with_name(destination.name + ".bak-" + stamp)
            destination.rename(backup)
        stage.rename(destination)
    except Exception:
        if backup and backup.exists() and not destination.exists():
            backup.rename(destination)
        raise
    finally:
        parent = stage.parent
        if parent.exists():
            shutil.rmtree(parent, ignore_errors=True)
    return backup


def update_marketplace(home: Path, marketplace_path: Path):
    data = load_marketplace(marketplace_path)
    entry = {
        "name": PLUGIN_NAME,
        "source": {"source": "local", "path": "./.codex/plugins/%s" % PLUGIN_NAME},
        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
        "category": "Developer Tools",
    }
    plugins = [p for p in data.get("plugins", []) if not (isinstance(p, dict) and p.get("name") == PLUGIN_NAME)]
    plugins.append(entry)
    data["plugins"] = plugins
    marketplace_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = marketplace_path.with_suffix(marketplace_path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(marketplace_path)
    return entry


def main():
    parser = argparse.ArgumentParser(description="Install Codex Rigor into the personal Codex plugin marketplace.")
    parser.add_argument("--home", type=Path, default=Path.home(), help="Home directory override, mainly for testing.")
    parser.add_argument("--source", type=Path, default=ROOT, help="Plugin source directory.")
    parser.add_argument("--force", action="store_true", help="Replace an existing local copy after creating a backup.")
    args = parser.parse_args()

    home = args.home.expanduser().resolve()
    source = args.source.expanduser().resolve()
    manifest = source / ".codex-plugin" / "plugin.json"
    if not manifest.exists():
        raise SystemExit("Not a Codex plugin directory: missing %s" % manifest)
    parsed = json.loads(manifest.read_text(encoding="utf-8"))
    if parsed.get("name") != PLUGIN_NAME:
        raise SystemExit("Unexpected plugin name in manifest: %r" % parsed.get("name"))

    destination = home / ".codex" / "plugins" / PLUGIN_NAME
    marketplace = home / ".agents" / "plugins" / "marketplace.json"
    backup = copy_plugin(source, destination, args.force)
    update_marketplace(home, marketplace)

    print("installed_plugin=%s" % destination)
    print("marketplace=%s" % marketplace)
    if backup:
        print("backup=%s" % backup)
    print("next=restart ChatGPT desktop/Codex, install Codex Rigor from Personal Plugins, then review and trust /hooks")


if __name__ == "__main__":
    main()
