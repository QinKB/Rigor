import json, os, subprocess, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
GUARD=ROOT/"hooks"/"guard.py"; CTL=ROOT/"scripts"/"rigorctl.py"

class GuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.repo=Path(self.tmp.name)/"repo"; self.repo.mkdir(); (self.repo/".codex").mkdir()
        subprocess.check_call(["git","init","-q",str(self.repo)]); subprocess.check_call(["git","-C",str(self.repo),"config","user.email","t@example.com"]); subprocess.check_call(["git","-C",str(self.repo),"config","user.name","T"])
        (self.repo/"README.md").write_text("x\n"); subprocess.check_call(["git","-C",str(self.repo),"add","README.md"]); subprocess.check_call(["git","-C",str(self.repo),"commit","-qm","init"])
        self.pdata=Path(self.tmp.name)/"pdata"; self.env={**os.environ,"PLUGIN_DATA":str(self.pdata),"PLUGIN_ROOT":str(ROOT)}
        subprocess.check_call([os.sys.executable,str(ROOT/"scripts"/"setup_project.py"),"--root",str(self.repo)],env=self.env,stdout=subprocess.DEVNULL)
        policy_path = (
            self.repo
            / ".codex"
            / "rigor.json"
        )

        policy = json.loads(
            policy_path.read_text()
        )

        policy["project"] = {
            "configured": True,
            "type": "test",
            "entrypoints": {
                "integration": "entry",
                "evaluation": "entry",
            },
            "protected_surfaces": [
                "models/**",
            ],
            "acceptance_profiles": {
                "test-l1": {
                    "required_level": "L1",
                    "levels": {
                        "L1": {
                            "description": "real integration",
                            "observed_patterns": [
                                "python integration.py",
                                "python acceptance.py",
                                "python real.py",
                            ],
                        },
                    },
                },
                "weaker": {
                    "required_level": "L1",
                    "levels": {
                        "L1": {
                            "description": "weak test profile",
                            "observed_patterns": [
                                "python easy.py",
                            ],
                        },
                    },
                },
            },
            "compute": {},
        }

        policy_path.write_text(
            json.dumps(
                policy,
                indent=2,
            )
            + "\n"
        )
    
    def tearDown(self): self.tmp.cleanup()
    def hook(self,event):
        cp=subprocess.run([os.sys.executable,str(GUARD)],input=json.dumps({"cwd":str(self.repo),"session_id":"s1",**event}),text=True,capture_output=True,env=self.env,check=True)
        return json.loads(cp.stdout) if cp.stdout.strip() else {}
    def ctl(self,*args,ok=True):
        cp=subprocess.run([os.sys.executable,str(CTL),"--root",str(self.repo),*args],text=True,capture_output=True,env=self.env)
        if ok and cp.returncode: self.fail(cp.stderr+cp.stdout)
        return cp
    def test_write_without_task_denied(self):
        out=self.hook({"hook_event_name":"PreToolUse","tool_name":"apply_patch","tool_input":{"command":"*** Begin Patch"}})
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"],"deny")
    def test_unconfigured_project_allows_profile_setup_write(self):
        policy_path = self.repo / ".codex" / "rigor.json"
        policy = json.loads(policy_path.read_text())

        policy["project"] = {
            "configured": False,
            "type": "unknown",
            "entrypoints": {},
            "protected_surfaces": [],
            "acceptance_profiles": {},
            "compute": {},
        }

        policy_path.write_text(
            json.dumps(policy, indent=2) + "\n"
        )

        out = self.hook({
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(policy_path),
                "content": "{}",
            },
        })

        self.assertEqual(out, {})
    def test_configured_project_profile_write_requires_task(self):
        policy_path = self.repo / ".codex" / "rigor.json"

        out = self.hook({
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(policy_path),
                "content": "{}",
            },
        })

        self.assertEqual(
            out["hookSpecificOutput"]["permissionDecision"],
            "deny",
        )
    def test_design_write_denied_until_evidence_and_freeze(self):
        self.ctl("task","start","--objective","adapt","--class","reference-adaptation","--acceptance","L1")
        out=self.hook({"hook_event_name":"PreToolUse","tool_name":"apply_patch","tool_input":{"command":"x"}}); self.assertEqual(out["hookSpecificOutput"]["permissionDecision"],"deny")
        self.hook({"hook_event_name":"PostToolUse","tool_name":"Bash","tool_input":{"command":"rg Foo ."},"tool_use_id":"local1","tool_response":{"exit_code":0}})
        self.hook({"hook_event_name":"PostToolUse","tool_name":"mcp__github__search_code","tool_input":{"query":"Foo"},"tool_use_id":"up1","tool_response":{"isError":False,"content":[{"type":"text","text":"code"}]}})
        self.hook({
    "hook_event_name": "PostToolUse",
    "tool_name": "mcp__github__fetch_file",
    "tool_input": {
        "path": "a.py",
        "ref": "sha",
    },
    "tool_use_id": "up2",
    "tool_response": {
        "isError": False,
        "content": [
            {
                "type": "text",
                "text": "exact upstream code",
            }
        ],
    },
})
        self.hook({"hook_event_name":"PostToolUse","tool_name":"mcp__exa__web_search_exa","tool_input":{"query":"x"},"tool_use_id":"u1","tool_response":{"isError":False,"content":[{"type":"text","text":"results"}]}})
        self.hook({"hook_event_name":"PostToolUse","tool_name":"mcp__papermeld__read","tool_input":{"query":"paper section 3"},"tool_use_id":"p1","tool_response":{"isError":False,"content":[{"type":"text","text":"paper"}]}})
        self.ctl("evidence","add","--kind","local-code","--source","repo","--locator","a.py","--summary","path","--observed","rg Foo")
        primary=json.loads(self.ctl("evidence","add","--kind","primary-paper","--source","paper","--locator","s3","--summary","definition","--observed","mcp__papermeld__read").stdout)
        upstream=json.loads(self.ctl("evidence","add","--kind","upstream-code","--source","github","--locator","r@c:f","--summary","impl","--observed", "mcp__github__fetch_file").stdout)
        self.ctl("evidence","add","--kind","external-search","--source","exa","--locator","q","--summary","current","--observed","mcp__exa__web_search_exa")
        self.ctl("design","freeze","--reference","r@c:f","--reference-evidence",primary["id"],"--reference-evidence",upstream["id"],"--target","a.py:Foo","--method","adapt","--integration","entry->Foo","--acceptance","L1")
        self.ctl(
    "verification",
    "select",
    "--profile",
    "test-l1",
)
        out=self.hook({"hook_event_name":"PreToolUse","tool_name":"apply_patch","tool_input":{"command":"x"}}); self.assertEqual(out,{})
    def test_agent_contract_and_subagent_result(self):
        self.ctl("task","start","--objective","mechanical","--class","mechanical","--acceptance","L1")
        self.ctl(
    "verification",
    "select",
    "--profile",
    "test-l1",
)
        cp=self.ctl("assignment","create","--role","worker","--objective","edit","--reference","existing:a.py:Foo","--target","a.py:Foo","--method","bounded change","--integration","entry->Foo","--resources","no long run","--write-scope","a.py","--acceptance","L1","--output","diff and evidence","--stop-condition","reference mismatch")
        token=cp.stdout.splitlines()[0]; aid=token.split(":",1)[1].rstrip("]")
        out=self.hook({"hook_event_name":"PreToolUse","tool_name":"Agent","tool_input":{"agent_type":"worker","message":"do it "+token}}); self.assertEqual(out["hookSpecificOutput"]["permissionDecision"],"allow"); self.assertIn("CODEX RIGOR ASSIGNMENT",out["hookSpecificOutput"]["updatedInput"]["message"])
        out=self.hook({"hook_event_name":"SubagentStart","agent_id":"a1","agent_type":"worker"}); self.assertIn(aid,out["hookSpecificOutput"]["additionalContext"])
        out = self.hook({
            "hook_event_name": "PreToolUse",
            "agent_id": "a1",
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(
                    self.repo / "outside.py"
                ),
                "content": "x",
            },
        })

        self.assertEqual(
            out["hookSpecificOutput"][
                "permissionDecision"
            ],
            "deny",
        )

        self.assertIn(
            "write_scope",
            out["hookSpecificOutput"][
                "permissionDecisionReason"
            ],
        )
        out = self.hook({
            "hook_event_name": "PreToolUse",
            "agent_id": "a1",
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(
                    self.repo / "a.py"
                ),
                "content": "x",
            },
        })

        self.assertEqual(out, {})
        msg="RIGOR_ASSIGNMENT_RESULT\nassignment_id: %s\nstatus: complete\nacceptance: L0\nintegration: entry\nvalidation: unit\nevidence: log\nremaining: none"%aid
        out=self.hook({"hook_event_name":"SubagentStop","agent_id":"a1","agent_type":"worker","last_assistant_message":msg,"stop_hook_active":False}); self.assertEqual(out["decision"],"block")
    def test_bash_repository_write_cannot_bypass_design_gate(self):
        self.ctl("task","start","--objective","adapt","--class","reference-adaptation","--acceptance","L1")
        out=self.hook({"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"sed -i 's/x/y/' model.py"}})
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"],"deny")
        self.assertIn("research gate",out["hookSpecificOutput"]["permissionDecisionReason"])


    def test_mechanical_task_cannot_write_research_sensitive_path(self):
        self.ctl("task","start","--objective","tiny edit","--class","mechanical","--acceptance","L1")
        self.ctl(
    "verification",
    "select",
    "--profile",
    "test-l1",
)
        out=self.hook({"hook_event_name":"PreToolUse","tool_name":"apply_patch","tool_input":{"patch":"*** Begin Patch\n*** Update File: models/predictor.py\n@@\n*** End Patch"}})
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"],"deny")
        self.assertIn("too weak",out["hookSpecificOutput"]["permissionDecisionReason"])


    def test_mechanical_task_cannot_bypass_with_serena_mcp_write(self):
        self.ctl("task","start","--objective","tiny edit","--class","mechanical","--acceptance","L1")
        self.ctl(
    "verification",
    "select",
    "--profile",
    "test-l1",
)
        out=self.hook({"hook_event_name":"PreToolUse","tool_name":"mcp__serena__replace_content","tool_input":{"relative_path":"models/predictor.py","needle":"x","repl":"y"}})
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"],"deny")
        self.assertIn("too weak",out["hookSpecificOutput"]["permissionDecisionReason"])


    def test_continuity_files_can_be_written_before_research_gate(self):
        self.ctl("task","start","--objective","investigate","--class","root-cause-fix","--acceptance","L1")
        out=self.hook({"hook_event_name":"PreToolUse","tool_name":"Write","tool_input":{"file_path":str(self.repo/"HANDOFF.md"),"content":"paused state"}})
        self.assertEqual(out,{})

    def test_stop_blocks_active_incomplete_task(self):
        self.ctl("task","start","--objective","mechanical","--class","mechanical","--acceptance","L1")
        out=self.hook({"hook_event_name":"Stop","last_assistant_message":"done","stop_hook_active":False}); self.assertEqual(out["decision"],"block")
        out=self.hook({"hook_event_name":"Stop","last_assistant_message":"done","stop_hook_active":True}); self.assertEqual(out,{})
    def test_destructive_git_denied(self):
        self.ctl("task","start","--objective","mechanical","--class","mechanical","--acceptance","L1")
        out=self.hook({"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"git reset --hard HEAD~1"}}); self.assertEqual(out["hookSpecificOutput"]["permissionDecision"],"deny")


    def test_followup_task_reuses_bound_agent_contract(self):
        self.ctl("task","start","--objective","mechanical","--class","mechanical","--acceptance","L1")
        self.ctl("verification","select","--profile","test-l1")
        cp=self.ctl("assignment","create","--role","worker","--objective","edit","--reference","existing:a.py:Foo","--target","a.py:Foo","--method","bounded change","--integration","entry->Foo","--resources","no long run","--write-scope","a.py","--acceptance","L1","--output","diff and evidence","--stop-condition","reference mismatch")
        token=cp.stdout.splitlines()[0]; aid=token.split(":",1)[1].rstrip("]")
        self.hook({"hook_event_name":"PreToolUse","tool_name":"Agent","tool_input":{"agent_type":"worker","message":"do it "+token}})
        self.hook({"hook_event_name":"SubagentStart","agent_id":"a1","agent_type":"worker"})
        out=self.hook({"hook_event_name":"PreToolUse","tool_name":"Agent","tool_input":{"action":"followup_task","agent_id":"a1","message":"continue the same bounded work"}})
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"],"allow")
        self.assertIn(aid,out["hookSpecificOutput"]["updatedInput"]["message"])

    def test_fork_turns_all_is_denied(self):
        self.ctl("task","start","--objective","mechanical","--class","mechanical","--acceptance","L1")
        out=self.hook({"hook_event_name":"PreToolUse","tool_name":"Agent","tool_input":{"agent_type":"worker","fork_turns":"all","message":"x"}})
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"],"deny")
        self.assertIn("fork_turns",out["hookSpecificOutput"]["permissionDecisionReason"])

    def test_child_cannot_self_assert_success_without_observed_planned_check(self):
        self.ctl("task","start","--objective","mechanical","--class","mechanical","--acceptance","L1")
        self.ctl("verification","select","--profile","test-l1")
        cp=self.ctl("assignment","create","--role","worker","--objective","edit","--reference","existing:a.py:Foo","--target","a.py:Foo","--method","bounded change","--integration","entry->Foo","--resources","no long run","--write-scope","a.py","--acceptance","L1","--output","diff and evidence","--stop-condition","reference mismatch")
        token=cp.stdout.splitlines()[0]; aid=token.split(":",1)[1].rstrip("]")
        self.hook({"hook_event_name":"PreToolUse","tool_name":"Agent","tool_input":{"agent_type":"worker","message":"do it "+token}})
        self.hook({"hook_event_name":"SubagentStart","agent_id":"a1","agent_type":"worker"})
        msg="RIGOR_ASSIGNMENT_RESULT\nassignment_id: %s\nstatus: complete\nacceptance: L1\nintegration: entry\nvalidation: python integration.py\nevidence: claimed\nremaining: none"%aid
        out=self.hook({"hook_event_name":"SubagentStop","agent_id":"a1","agent_type":"worker","last_assistant_message":msg,"stop_hook_active":False})
        self.assertEqual(out["decision"],"block")
        state_files=list(self.pdata.glob("projects/*/state.json")); self.assertEqual(len(state_files),1)
        state=json.loads(state_files[0].read_text())
        self.assertEqual(state["assignments"][aid]["status"],"running")

    def test_stop_requires_explicit_task_close_even_after_gates(self):
        self.ctl("task","start","--objective","mechanical","--class","mechanical","--acceptance","L1")
        self.ctl("verification","select","--profile","test-l1")
        self.hook({"hook_event_name":"PostToolUse","tool_name":"Bash","tool_input":{"command":"python real.py"},"tool_use_id":"run1","tool_response":{"exit_code":0}})
        self.ctl("integration","record","--entrypoint","entry","--evidence","real path","--observed","python real.py")
        self.ctl("acceptance","record","--level","L1","--evidence","real result","--observed","python real.py")
        (self.repo/"HANDOFF.md").write_text("# HANDOFF\ncomplete\n"); (self.repo/"LOG.md").write_text("# LOG\nreal.py passed\n")
        self.ctl("continuity","sync","--memory-status","no-new-durable-memory","--summary","continuity updated")
        subprocess.check_call(["git","-C",str(self.repo),"add","."]); subprocess.check_call(["git","-C",str(self.repo),"commit","-qm","task"])
        self.ctl("git","record")
        out=self.hook({"hook_event_name":"Stop","last_assistant_message":"done","stop_hook_active":False})
        self.assertEqual(out["decision"],"block")
        self.assertIn("task close",out["reason"])

if __name__=="__main__": unittest.main()
