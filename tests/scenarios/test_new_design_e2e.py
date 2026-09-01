import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CTL = ROOT / "scripts" / "rigorctl.py"
GUARD = ROOT / "hooks" / "guard.py"
SETUP = ROOT / "scripts" / "setup_project.py"


class NewDesignEndToEnd(unittest.TestCase):
    def test_evidence_design_worker_l4_git_stop(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            repo = base / "repo"
            repo.mkdir()

            subprocess.check_call([
                "git",
                "init",
                "-q",
                str(repo),
            ])

            subprocess.check_call([
                "git",
                "-C",
                str(repo),
                "config",
                "user.email",
                "rigor@example.com",
            ])

            subprocess.check_call([
                "git",
                "-C",
                str(repo),
                "config",
                "user.name",
                "Rigor Test",
            ])

            (repo / "model.py").write_text(
                "VALUE = 1\n"
            )

            subprocess.check_call([
                "git",
                "-C",
                str(repo),
                "add",
                ".",
            ])

            subprocess.check_call([
                "git",
                "-C",
                str(repo),
                "commit",
                "-qm",
                "initial",
            ])

            env = {
                **os.environ,
                "PLUGIN_ROOT": str(ROOT),
                "PLUGIN_DATA": str(
                    base / "plugin-data"
                ),
            }

            subprocess.check_call(
                [
                    sys.executable,
                    str(SETUP),
                    "--root",
                    str(repo),
                    "--install-agents",
                ],
                env=env,
                stdout=subprocess.DEVNULL,
            )

            policy_path = (
                repo
                / ".codex"
                / "rigor.json"
            )

            policy = json.loads(
                policy_path.read_text()
            )

            policy["project"] = {
                "configured": True,
                "type": "test-research",
                "entrypoints": {
                    "integration": "real_entry",
                    "evaluation": (
                        "python authoritative_eval.py"
                    ),
                },
                "protected_surfaces": [
                    "model.py",
                ],
                "acceptance_profiles": {
                    "model-change": {
                        "required_level": "L4",
                        "levels": {
                            "L1": {
                                "description": (
                                    "real integration"
                                ),
                                "observed_patterns": [
                                    (
                                        "python "
                                        "integration_check.py"
                                    ),
                                ],
                            },
                            "L2": {
                                "description": (
                                    "real operational lifecycle"
                                ),
                                "observed_patterns": [
                                    "python train_cycle.py",
                                ],
                            },
                            "L3": {
                                "description": (
                                    "fresh runtime reload"
                                ),
                                "observed_patterns": [
                                    "python reload_check.py",
                                ],
                            },
                            "L4": {
                                "description": (
                                    "authoritative "
                                    "evaluation"
                                ),
                                "observed_patterns": [
                                    (
                                        "python "
                                        "authoritative_eval.py"
                                    ),
                                ],
                                "authoritative": True,
                            },
                        },
                    },
                    "weaker": {
                        "required_level": "L4",
                        "levels": {
                            "L1": {
                                "description": (
                                    "weak integration"
                                ),
                                "observed_patterns": [
                                    "python easy.py",
                                ],
                            },
                            "L4": {
                                "description": (
                                    "weak final check"
                                ),
                                "observed_patterns": [
                                    "python easy.py",
                                ],
                            },
                        },
                    },
                },
                "compute": {
                    # Portable E2E control-flow test.
                    # Real GPU saturation is covered
                    # separately by resource unit tests.
                    "required_gpu_count": 0,
                },
            }

            policy["overrides"] = {
                "compute": {
                    "enforce_all_eligible_gpus": False,
                },
            }

            policy_path.write_text(
                json.dumps(
                    policy,
                    indent=2,
                )
                + "\n"
            )

            def ctl(*args, ok=True):
                cp = subprocess.run(
                    [
                        sys.executable,
                        str(CTL),
                        "--root",
                        str(repo),
                        *args,
                    ],
                    env=env,
                    text=True,
                    capture_output=True,
                    timeout=15,
                )

                if ok and cp.returncode:
                    self.fail(
                        cp.stderr + cp.stdout
                    )

                return cp

            def hook(event):
                payload = {
                    "cwd": str(repo),
                    "session_id": "s-e2e",
                    **event,
                }

                cp = subprocess.run(
                    [
                        sys.executable,
                        str(GUARD),
                    ],
                    input=json.dumps(payload),
                    env=env,
                    text=True,
                    capture_output=True,
                    check=True,
                    timeout=15,
                )

                if not cp.stdout.strip():
                    return {}

                return json.loads(
                    cp.stdout
                )

            ctl(
                "task",
                "start",
                "--objective",
                (
                    "adapt an evidence-backed "
                    "mechanism into the real model path"
                ),
                "--class",
                "new-design",
                "--acceptance",
                "L4",
            )

            hook({
                "hook_event_name": "PostToolUse",
                "tool_name": "Bash",
                "tool_input": {
                    "command": (
                        "rg ExistingMechanism ."
                    ),
                },
                "tool_use_id": "local-search",
                "tool_response": {
                    "exit_code": 0,
                },
            })

            # Discovery only.
            hook({
                "hook_event_name": "PostToolUse",
                "tool_name": (
                    "mcp__github__search_code"
                ),
                "tool_input": {
                    "query": "ExistingMechanism",
                },
                "tool_use_id": "upstream-search",
                "tool_response": {
                    "isError": False,
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "candidate upstream"
                            ),
                        }
                    ],
                },
            })

            # Exact implementation read.
            hook({
                "hook_event_name": "PostToolUse",
                "tool_name": (
                    "mcp__github__fetch_file"
                ),
                "tool_input": {
                    "repository_full_name": (
                        "org/repo"
                    ),
                    "path": "file.py",
                    "ref": "sha",
                },
                "tool_use_id": "upstream-read",
                "tool_response": {
                    "isError": False,
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "exact implementation"
                            ),
                        }
                    ],
                },
            })

            hook({
                "hook_event_name": "PostToolUse",
                "tool_name": (
                    "mcp__exa__web_search_exa"
                ),
                "tool_input": {
                    "query": (
                        "ExistingMechanism "
                        "failure cases"
                    ),
                },
                "tool_use_id": "external-search",
                "tool_response": {
                    "isError": False,
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "current evidence"
                            ),
                        }
                    ],
                },
            })

            hook({
                "hook_event_name": "PostToolUse",
                "tool_name": (
                    "mcp__papermeld__read"
                ),
                "tool_input": {
                    "query": (
                        "ExistingMechanism "
                        "section 3"
                    ),
                },
                "tool_use_id": "paper-read",
                "tool_response": {
                    "isError": False,
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "primary paper "
                                "mechanism"
                            ),
                        }
                    ],
                },
            })

            ctl(
                "evidence",
                "add",
                "--kind",
                "local-code",
                "--source",
                "repo",
                "--locator",
                "model.py",
                "--summary",
                "real local entry path",
                "--observed",
                "local-search",
            )

            primary = json.loads(
                ctl(
                    "evidence",
                    "add",
                    "--kind",
                    "primary-paper",
                    "--source",
                    "paper",
                    "--locator",
                    "section 3",
                    "--summary",
                    (
                        "authoritative "
                        "mechanism semantics"
                    ),
                    "--observed",
                    "paper-read",
                ).stdout
            )

            upstream = json.loads(
                ctl(
                    "evidence",
                    "add",
                    "--kind",
                    "upstream-code",
                    "--source",
                    "github",
                    "--locator",
                    (
                        "org/repo@sha:"
                        "file.py:Mechanism"
                    ),
                    "--summary",
                    (
                        "known-good exact "
                        "implementation"
                    ),
                    "--observed",
                    "upstream-read",
                ).stdout
            )

            ctl(
                "evidence",
                "add",
                "--kind",
                "external-search",
                "--source",
                "exa",
                "--locator",
                (
                    "ExistingMechanism "
                    "failure cases"
                ),
                "--summary",
                (
                    "current alternatives "
                    "and failure reports"
                ),
                "--observed",
                "external-search",
            )

            ctl(
                "design",
                "freeze",
                "--reference",
                (
                    "org/repo@sha:"
                    "file.py:Mechanism"
                ),
                "--reference-evidence",
                primary["id"],
                "--reference-evidence",
                upstream["id"],
                "--target",
                "model.py:Mechanism",
                "--method",
                (
                    "faithful adaptation "
                    "preserving semantics"
                ),
                "--integration",
                (
                    "real_entry -> Mechanism "
                    "-> downstream_consumer"
                ),
                "--acceptance",
                "L4",
            )

            ctl(
                "verification",
                "select",
                "--profile",
                "model-change",
            )

            inspect_cmd = (
                "python %s"
                % (
                    ROOT
                    / "scripts"
                    / "inspect_resources.py"
                )
            )

            hook({
                "hook_event_name": "PostToolUse",
                "tool_name": "Bash",
                "tool_input": {
                    "command": inspect_cmd,
                },
                "tool_use_id": "resources",
                "tool_response": {
                    "exit_code": 0,
                },
            })

            ctl(
                "resources",
                "plan",
                "--gpus",
                "0",
                "--cpu-workers",
                str(
                    max(
                        1,
                        min(
                            2,
                            os.cpu_count() or 1,
                        ),
                    )
                ),
                "--strategy",
                (
                    "maximize useful headroom "
                    "without oversubscription"
                ),
                "--notes",
                (
                    "portable E2E path; "
                    "GPU saturation is "
                    "unit-tested separately"
                ),
                "--observed",
                "resources",
            )

            assignment = ctl(
                "assignment",
                "create",
                "--role",
                "worker",
                "--objective",
                (
                    "implement the frozen "
                    "mechanism"
                ),
                "--reference",
                (
                    "org/repo@sha:"
                    "file.py:Mechanism"
                ),
                "--target",
                "model.py:Mechanism",
                "--method",
                (
                    "faithful adaptation "
                    "preserving semantics"
                ),
                "--integration",
                (
                    "real_entry -> Mechanism "
                    "-> downstream_consumer"
                ),
                "--resources",
                "follow task resource plan",
                "--write-scope",
                "model.py",
                "--acceptance",
                "L1",
                "--output",
                (
                    "bounded diff plus real "
                    "integration evidence"
                ),
                "--stop-condition",
                (
                    "reference assumptions "
                    "do not fit"
                ),
            )

            token = (
                assignment
                .stdout
                .splitlines()[0]
            )

            aid = (
                token
                .split(":", 1)[1]
                .rstrip("]")
            )

            spawn = hook({
                "hook_event_name": "PreToolUse",
                "tool_name": "Agent",
                "tool_input": {
                    "agent_type": "worker",
                    "message": (
                        "implement " + token
                    ),
                },
                "tool_use_id": "spawn1",
            })

            self.assertEqual(
                spawn["hookSpecificOutput"][
                    "permissionDecision"
                ],
                "allow",
            )

            self.assertIn(
                "task_resource_plan",
                spawn["hookSpecificOutput"][
                    "updatedInput"
                ]["message"],
            )

            child = hook({
                "hook_event_name": "SubagentStart",
                "agent_id": "child1",
                "agent_type": "worker",
            })

            self.assertIn(
                aid,
                child["hookSpecificOutput"][
                    "additionalContext"
                ],
            )

            self.assertIn(
                "Ponytail",
                child["hookSpecificOutput"][
                    "additionalContext"
                ],
            )

            write = hook({
                "hook_event_name": "PreToolUse",
                "tool_name": "apply_patch",
                "tool_input": {
                    "patch": (
                        "*** Begin Patch\n"
                        "*** Update File: model.py\n"
                        "@@\n"
                        "-VALUE = 1\n"
                        "+VALUE = 2\n"
                        "*** End Patch"
                    ),
                },
                "tool_use_id": "write1",
            })

            self.assertEqual(
                write,
                {},
            )

            reselect = ctl(
                "verification",
                "select",
                "--profile",
                "weaker",
                ok=False,
            )

            self.assertNotEqual(
                reselect.returncode,
                0,
            )

            (repo / "model.py").write_text(
                "VALUE = 2\n"
            )

            hook({
                "hook_event_name": "PostToolUse",
                "tool_name": "Bash",
                "tool_input": {
                    "command": (
                        "python "
                        "integration_check.py"
                    ),
                },
                "tool_use_id": (
                    "integration-run"
                ),
                "tool_response": {
                    "exit_code": 0,
                },
            })

            child_result = "\n".join([
                "RIGOR_ASSIGNMENT_RESULT",
                "assignment_id: %s" % aid,
                "status: complete",
                "acceptance: L1",
                (
                    "integration: real_entry "
                    "consumes model.py result"
                ),
                (
                    "validation: "
                    "integration-run"
                ),
                (
                    "evidence: model.py diff "
                    "plus observed "
                    "integration run"
                ),
                "remaining: none",
            ])

            self.assertEqual(
                hook({
                    "hook_event_name": (
                        "SubagentStop"
                    ),
                    "agent_id": "child1",
                    "agent_type": "worker",
                    "last_assistant_message": (
                        child_result
                    ),
                    "stop_hook_active": False,
                }),
                {},
            )

            ctl(
                "integration",
                "record",
                "--entrypoint",
                "real_entry",
                "--evidence",
                "real downstream consumed changed result",
                "--observed",
                "integration-run",
            )

            ctl(
                "acceptance",
                "record",
                "--level",
                "L1",
                "--evidence",
                "real integration succeeded",
                "--observed",
                "integration-run",
            )

            hook({
                "hook_event_name": "PostToolUse",
                "tool_name": "Bash",
                "tool_input": {
                    "command": "python train_cycle.py",
                },
                "tool_use_id": "operational-run",
                "tool_response": {
                    "exit_code": 0,
                },
            })

            ctl(
                "acceptance",
                "record",
                "--level",
                "L2",
                "--evidence",
                "operational lifecycle succeeded",
                "--observed",
                "operational-run",
            )

            hook({
                "hook_event_name": "PostToolUse",
                "tool_name": "Bash",
                "tool_input": {
                    "command": "python reload_check.py",
                },
                "tool_use_id": "reload-run",
                "tool_response": {
                    "exit_code": 0,
                },
            })

            ctl(
                "acceptance",
                "record",
                "--level",
                "L3",
                "--evidence",
                "fresh runtime reload succeeded",
                "--observed",
                "reload-run",
            )

            hook({
                "hook_event_name": "PostToolUse",
                "tool_name": "Bash",
                "tool_input": {
                    "command": "python authoritative_eval.py",
                },
                "tool_use_id": "acceptance-run",
                "tool_response": {
                    "exit_code": 0,
                },
            })

            ctl(
                "acceptance",
                "record",
                "--level",
                "L4",
                "--evidence",
                "authoritative evaluator produced valid task outcome",
                "--observed",
                "acceptance-run",
            )

            (repo / "HANDOFF.md").write_text(
                (
                    "# HANDOFF\n\n"
                    "Task accepted at L4; "
                    "no unfinished work.\n"
                )
            )

            with (
                repo / "LOG.md"
            ).open("a") as fh:
                fh.write(
                    "\nL4 authoritative "
                    "evaluation passed.\n"
                )

            ctl(
                "continuity",
                "sync",
                "--memory-status",
                "no-new-durable-memory",
                "--summary",
                (
                    "handoff and run evidence "
                    "updated; no new durable "
                    "project fact"
                ),
            )

            pre_commit = hook({
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "tool_input": {
                    "command": (
                        "git commit "
                        "-m rigor-task"
                    ),
                },
                "tool_use_id": "commit-pre",
            })

            self.assertEqual(
                pre_commit,
                {},
            )

            subprocess.check_call(
                [
                    "git",
                    "-C",
                    str(repo),
                    "add",
                    ".",
                ],
                timeout=10,
            )

            subprocess.check_call(
                [
                    "git",
                    "-C",
                    str(repo),
                    "commit",
                    "-qm",
                    "rigor task",
                ],
                timeout=10,
            )

            ctl(
                "git",
                "record",
            )

            ctl(
                "task",
                "close",
            )

            self.assertEqual(
                hook({
                    "hook_event_name": "Stop",
                    "last_assistant_message": (
                        "completed"
                    ),
                    "stop_hook_active": False,
                }),
                {},
            )


if __name__ == "__main__":
    unittest.main()