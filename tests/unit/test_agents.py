import sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
class AgentTemplates(unittest.TestCase):
    def test_toml_templates_parse(self):
        try:
            import tomllib
        except ImportError:
            self.skipTest('tomllib unavailable')
        expected={'scout':'read-only','researcher':'read-only','reviewer':'read-only','worker':'workspace-write','runner':'workspace-write'}
        for name,sandbox in expected.items():
            data=tomllib.loads((ROOT/'templates'/'agents'/(name+'.toml')).read_text())
            self.assertEqual(data['name'],name); self.assertEqual(data['sandbox_mode'],sandbox)
            self.assertTrue(data['developer_instructions'].strip())
if __name__=='__main__': unittest.main()
