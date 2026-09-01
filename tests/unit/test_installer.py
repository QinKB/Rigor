import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INSTALLER = ROOT / "scripts" / "install_local_plugin.py"


class LocalInstallerTests(unittest.TestCase):
    def test_personal_install_and_marketplace_merge(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td) / "home"
            marketplace = home / ".agents" / "plugins" / "marketplace.json"
            marketplace.parent.mkdir(parents=True)
            marketplace.write_text(json.dumps({
                "name": "mine",
                "interface": {"displayName": "Mine"},
                "plugins": [{
                    "name": "existing",
                    "source": {"source": "local", "path": "./plugins/existing"},
                    "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                    "category": "Productivity",
                }],
            }))
            cp = subprocess.run([sys.executable, str(INSTALLER), "--home", str(home)], text=True, capture_output=True)
            self.assertEqual(cp.returncode, 0, cp.stderr + cp.stdout)
            dest = home / ".codex" / "plugins" / "rigor"
            self.assertTrue((dest / ".codex-plugin" / "plugin.json").exists())
            data = json.loads(marketplace.read_text())
            names = [x["name"] for x in data["plugins"]]
            self.assertEqual(names.count("rigor"), 1)
            self.assertIn("existing", names)
            rigor = next(x for x in data["plugins"] if x["name"] == "rigor")
            self.assertEqual(rigor["source"]["path"], "./.codex/plugins/rigor")

    def test_refuses_existing_without_force(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td) / "home"
            dest = home / ".codex" / "plugins" / "rigor"
            dest.mkdir(parents=True)
            (dest / "sentinel").write_text("keep")
            cp = subprocess.run([sys.executable, str(INSTALLER), "--home", str(home)], text=True, capture_output=True)
            self.assertNotEqual(cp.returncode, 0)
            self.assertEqual((dest / "sentinel").read_text(), "keep")


if __name__ == "__main__":
    unittest.main()
