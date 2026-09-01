import json, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
class Structure(unittest.TestCase):
    def test_manifest_and_hooks(self):
        m = json.loads(
            (ROOT / ".codex-plugin" / "plugin.json").read_text()
        )

        self.assertEqual(m["name"], "rigor")
        self.assertEqual(m["version"], "1.1.0")
        self.assertEqual(m["skills"], "./skills/")
        self.assertEqual(m["hooks"], "./hooks/hooks.json")

        market = json.loads(
            (
                ROOT
                / ".agents"
                / "plugins"
                / "marketplace.json"
            ).read_text()
        )

        self.assertNotIn(
            "hooks",
            m,
        )

        self.assertTrue(
            (
                ROOT
                / "hooks"
                / "hooks.json"
            ).is_file()
        )

        h = json.loads(
            (ROOT / "hooks" / "hooks.json").read_text()
        )["hooks"]

        for event in [
            "SessionStart",
            "PreCompact",
            "SubagentStart",
            "SubagentStop",
            "PreToolUse",
            "PostToolUse",
            "Stop",
        ]:
            self.assertIn(event, h)

        self.assertNotIn("SessionEnd", h)

        for groups in h.values():
            for group in groups:
                for handler in group["hooks"]:
                    self.assertIn(
                        "commandWindows",
                        handler,
                    )
    def test_no_placeholders(self):
        bad=[]
        for p in ROOT.rglob("*"):
            if p.is_file() and p.suffix in {".md",".py",".json",".toml",".yaml"}:
                t=p.read_text(encoding="utf-8",errors="ignore")
                if ("TO"+"DO") in t or ("example"+"_asset") in t or ("api"+"_reference.md") in t: bad.append(str(p.relative_to(ROOT)))
        self.assertEqual(bad,[])
if __name__=="__main__": unittest.main()
