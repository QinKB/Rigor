import json, os, tempfile, unittest
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
from rigor.policy import DEFAULT_POLICY
from rigor.state import RigorState

class StateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)/"repo"; self.root.mkdir(); (self.root/".codex").mkdir()
        self.data=Path(self.tmp.name)/"pdata"; os.environ["PLUGIN_DATA"]=str(self.data)
        self.policy["project"] = {
            "configured": True,
            "type": "test",
            "entrypoints": {
                "integration": "entry",
                "evaluation": "entry",
            },
            "protected_surfaces": [],
            "acceptance_profiles": {
                "test-l2": {
                    "required_level": "L2",
                    "levels": {
                        "L1": {
                            "description": "real integration",
                            "observed_patterns": [
                                "python integration_demo.py",
                            ],
                        },
                        "L2": {
                            "description": "real update lifecycle",
                            "observed_patterns": [
                                "python integration_demo.py",
                            ],
                        },
                    },
                },
            },
            "compute": {},
        }

        self.s = RigorState(
            self.root,
            self.policy,
        )
    def tearDown(self): self.tmp.cleanup(); os.environ.pop("PLUGIN_DATA",None)
    def test_research_design_acceptance(self):
        t=self.s.start_task("adapt mechanism","reference-adaptation","L2")
        self.s.record_observed_tool({"provider":"rg","kind":"local-code-search","tool_name":"Bash","query":"rg Foo .","tool_use_id":"local","success":True})
        self.s.record_observed_tool({
    "provider": "github",
    "kind": "upstream-code-read",
    "tool_name": "mcp__github__fetch_file",
    "query": "repo@sha:a.py:Foo",
    "tool_use_id": "upstream",
    "success": True,
})
        self.s.record_observed_tool({"provider":"exa","kind":"external-search","tool_name":"mcp__exa__search","query":"prior art","tool_use_id":"exa","success":True})
        self.s.record_observed_tool({
    "provider": "local-literature",
    "kind": "literature-read",
    "tool_name": "mcp__papermeld__read",
    "query": "paper sec 3",
    "tool_use_id": "paper",
    "success": True,
})
        self.s.add_evidence("local-code","repo","a.py:Foo","current path","rg Foo")
        primary=self.s.add_evidence("primary-paper","paper","sec 3","mechanism","mcp__papermeld__read")
        upstream = self.s.add_evidence(
    "upstream-code",
    "github",
    "repo@sha:a.py:Foo",
    "implementation",
    "mcp__github__fetch_file",
)
        self.s.add_evidence("external-search","exa","query:x","current alternatives","mcp__exa__search")
        self.assertTrue(self.s.active_task()["gates"]["research"]["passed"])
        with self.assertRaises(ValueError):
            self.s.freeze_design("repo@sha:Foo","target.py:Bar","adapt Foo","entry->Bar","L2",[upstream["id"]])
        self.s.freeze_design("repo@sha:Foo","target.py:Bar","adapt Foo","entry->Bar","L2",[primary["id"],upstream["id"]])
        self.s.select_verification_profile(
    "test-l2"
)
        bad_worker={
            "objective":"implement","reference":"different-reference","target":"target.py:Bar","method":"adapt",
            "integration":"entry->Bar","resources":"bounded","write_scope":"target.py","acceptance":"L1",
            "output":"diff","stop_conditions":["reference mismatch"],
        }
        with self.assertRaises(ValueError):
            self.s.create_assignment("worker",bad_worker)
        self.assertTrue(self.s.active_task()["gates"]["design"]["passed"])
        self.s.record_observed_tool({"provider":"shell","kind":"execution","tool_name":"Bash","query":"python integration_demo.py","tool_use_id":"run1","success":True})
        self.s.record_integration("entry","real sample consumed new output","python integration_demo.py")
        self.s.record_acceptance("L1","real entrypoint","python integration_demo.py")
        self.assertFalse(self.s.active_task()["gates"]["acceptance"]["passed"])
        self.s.record_acceptance("L2","real update lifecycle","python integration_demo.py")
        self.assertTrue(self.s.active_task()["gates"]["acceptance"]["passed"])
    def test_external_search_must_be_observed(self):
        self.s.start_task("design","new-design","L1")
        with self.assertRaises(ValueError): self.s.add_evidence("external-search","exa","q","x")
    def test_primary_paper_must_be_observed(self):
        self.s.start_task("design","new-design","L1")
        with self.assertRaises(ValueError):
            self.s.add_evidence("primary-paper","paper","sec 3","mechanism")

    def test_root_cause_requires_external_search(self):
        self.s.start_task("bug","root-cause-fix","L1")
        self.s.record_observed_tool({"provider":"rg","kind":"local-code-search","tool_name":"Bash","query":"rg bug .","tool_use_id":"local","success":True})
        self.s.add_evidence("local-code","repo","bug.py","root path","rg bug")
        self.assertFalse(self.s.active_task()["gates"]["research"]["passed"])
        self.s.record_observed_tool({"provider":"exa","kind":"external-search","tool_name":"mcp__exa__web_search_exa","query":"bug failure","tool_use_id":"exa2","success":True})
        self.s.add_evidence("external-search","exa","bug failure","current failure reports","mcp__exa__web_search_exa")
        self.assertTrue(self.s.active_task()["gates"]["research"]["passed"])

    def test_assignment_requires_contract(self):
        self.s.start_task("mechanical","mechanical","L1")
        with self.assertRaises(ValueError): self.s.create_assignment("worker",{"objective":"x"})
    def test_upstream_search_is_discovery_only(self):
        self.s.start_task(
            "design",
            "new-design",
            "L1",
        )

        self.s.record_observed_tool({
            "provider": "github",
            "kind": "upstream-search",
            "tool_name": "mcp__github__search_code",
            "query": "Foo",
            "tool_use_id": "search1",
            "success": True,
        })

        with self.assertRaises(ValueError):
            self.s.add_evidence(
                "upstream-code",
                "github",
                "repo:a.py:Foo",
                "implementation",
                "search1",
                stage="verified",
            )

        ev = self.s.add_evidence(
            "upstream-code",
            "github",
            "repo:a.py:Foo",
            "candidate implementation",
            "search1",
            stage="discovered",
        )

        self.assertEqual(
            ev["stage"],
            "discovered",
        )

if __name__=="__main__": unittest.main()
