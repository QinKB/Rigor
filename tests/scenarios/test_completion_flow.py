import json, os, subprocess, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; CTL=ROOT/"scripts"/"rigorctl.py"; GUARD=ROOT/"hooks"/"guard.py"
class CompletionFlow(unittest.TestCase):
    def test_mechanical_full_flow(self):
        with tempfile.TemporaryDirectory() as td:
            repo=Path(td)/"repo"; repo.mkdir(); (repo/".codex").mkdir(); env={**os.environ,"PLUGIN_DATA":str(Path(td)/"data")}
            subprocess.check_call(["git","init","-q",str(repo)]); subprocess.check_call(["git","-C",str(repo),"config","user.email","t@example.com"]); subprocess.check_call(["git","-C",str(repo),"config","user.name","T"])
            (repo/"x.txt").write_text("x\n"); subprocess.check_call(["git","-C",str(repo),"add","."]); subprocess.check_call(["git","-C",str(repo),"commit","-qm","init"])
            subprocess.check_call([os.sys.executable,str(ROOT/"scripts"/"setup_project.py"),"--root",str(repo)],env=env,stdout=subprocess.DEVNULL)
            policy_path = repo / ".codex" / "rigor.json"
            policy = json.loads(
                policy_path.read_text()
            )

            policy["project"] = {
                "configured": True,
                "type": "test",
                "entrypoints": {
                    "integration": "real-entry",
                    "evaluation": "real-entry",
                },
                "protected_surfaces": [],
                "acceptance_profiles": {
                    "mechanical-l1": {
                        "required_level": "L1",
                        "levels": {
                            "L1": {
                                "description": "real demo",
                                "observed_patterns": [
                                    "python real_demo.py",
                                ],
                            },
                        },
                    },
                },
                "compute": {},
            }

            policy_path.write_text(
                json.dumps(policy, indent=2)
                + "\n"
            )
            def ctl(*a): return subprocess.run([os.sys.executable,str(CTL),"--root",str(repo),*a],env=env,text=True,capture_output=True)
            self.assertEqual(ctl("task","start","--objective","x","--class","mechanical","--acceptance","L1").returncode,0)
            self.assertEqual(
    ctl(
        "verification",
        "select",
        "--profile",
        "mechanical-l1",
    ).returncode,
    0,
)
            event={"cwd":str(repo),"session_id":"s","hook_event_name":"PostToolUse","tool_name":"Bash","tool_input":{"command":"python real_demo.py"},"tool_use_id":"run1","tool_response":{"exit_code":0}}
            subprocess.run([os.sys.executable,str(GUARD)],input=json.dumps(event),text=True,env={**env,"PLUGIN_ROOT":str(ROOT)},stdout=subprocess.DEVNULL,check=True)
            self.assertEqual(ctl("integration","record","--entrypoint","real-entry","--evidence","real downstream consumed output","--observed","python real_demo.py").returncode,0)
            self.assertEqual(ctl("acceptance","record","--level","L1","--evidence","real entry path passed","--observed","python real_demo.py").returncode,0)
            (repo/"HANDOFF.md").write_text("# HANDOFF\n\nTask complete; next action none.\n")
            with (repo/"LOG.md").open("a") as f: f.write("\nvalidated real_demo.py\n")
            self.assertEqual(ctl("continuity","sync","--memory-status","no-new-durable-memory","--summary","Updated handoff and run log; no new durable memory.").returncode,0)
            # Git gate requires clean state; setup created continuity files after initial commit, so checkpoint them.
            subprocess.check_call(["git","-C",str(repo),"add","."]); subprocess.check_call(["git","-C",str(repo),"commit","-qm","rigor init"])
            self.assertEqual(ctl("git","record").returncode,0)
            close=ctl("task","close"); self.assertEqual(close.returncode,0,close.stderr+close.stdout)
if __name__=="__main__": unittest.main()
