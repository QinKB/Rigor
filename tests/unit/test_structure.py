import json, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
class Structure(unittest.TestCase):
    def test_manifest_and_hooks(self):
        m=json.loads((ROOT/".codex-plugin"/"plugin.json").read_text()); self.assertEqual(m["name"],"rigor"); self.assertEqual(m["skills"],"./skills/"); self.assertEqual(m["hooks"],"./hooks/hooks.json")
        h=json.loads((ROOT/"hooks"/"hooks.json").read_text())["hooks"]
        for event in ["SessionStart","SubagentStart","SubagentStop","PreToolUse","PostToolUse","Stop","SessionEnd"]: self.assertIn(event,h)
    def test_no_placeholders(self):
        bad=[]
        for p in ROOT.rglob("*"):
            if p.is_file() and p.suffix in {".md",".py",".json",".toml",".yaml"}:
                t=p.read_text(encoding="utf-8",errors="ignore")
                if ("TO"+"DO") in t or ("example"+"_asset") in t or ("api"+"_reference.md") in t: bad.append(str(p.relative_to(ROOT)))
        self.assertEqual(bad,[])
if __name__=="__main__": unittest.main()
