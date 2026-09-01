import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from rigor.policy import DEFAULT_POLICY
from rigor.runtime import (
    is_governed_mcp_write,
    is_repository_write_command,
    is_sensitive_repository_target,
    task_class_allows_sensitive_write,
    tool_write_targets,
)
from rigor.state import RigorState


def configure_profile(
    policy,
    name,
    required_level,
    levels,
):
    project = policy.setdefault(
        "project",
        {},
    )

    project["configured"] = True
    project["type"] = "test"

    project.setdefault(
        "entrypoints",
        {
            "integration": "entry",
            "evaluation": "entry",
        },
    )

    project.setdefault(
        "protected_surfaces",
        [],
    )

    project.setdefault(
        "acceptance_profiles",
        {},
    )

    project.setdefault(
        "compute",
        {},
    )

    project["acceptance_profiles"][name] = {
        "required_level": required_level,
        "levels": {
            level: {
                "description": "test " + level,
                "observed_patterns": patterns,
            }
            for level, patterns in levels.items()
        },
    }


class HardeningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

        self.root = Path(self.tmp.name) / "repo"
        self.root.mkdir()
        (self.root / ".codex").mkdir()

        os.environ["PLUGIN_DATA"] = str(
            Path(self.tmp.name) / "data"
        )

        self.policy = json.loads(
            json.dumps(DEFAULT_POLICY)
        )
        self.policy["enabled"] = True
        self.policy["git"]["require_clean_checkpoint"] = False

        self.s = RigorState(
            self.root,
            self.policy,
        )

    def tearDown(self):
        self.s.close()
        os.environ.pop(
            "PLUGIN_DATA",
            None,
        )
        self.tmp.cleanup()

    def test_fake_acceptance_rejected_without_observed_execution(self):
        self.s.start_task(
            "x",
            "mechanical",
            "L1",
        )

        with self.assertRaises(ValueError):
            self.s.record_acceptance(
                "L1",
                "claimed",
                "python never_ran.py",
            )

    def test_fake_integration_rejected_without_observed_execution(self):
        self.s.start_task(
            "x",
            "mechanical",
            "L1",
        )

        with self.assertRaises(ValueError):
            self.s.record_integration(
                "entry",
                "claimed",
                "python never_ran.py",
            )

    def test_continuity_requires_task_period_update(self):
        for name in [
            "HANDOFF.md",
            "MEMORY.md",
            "LOG.md",
        ]:
            (self.root / name).write_text(
                "# " + name + "\nold\n"
            )

        import time
        time.sleep(1.05)

        self.s.start_task(
            "x",
            "mechanical",
            "L1",
        )

        with self.assertRaises(ValueError):
            self.s.sync_memory(
                "no-new-durable-memory",
                "no changes",
            )

        (self.root / "HANDOFF.md").write_text(
            "# HANDOFF\nupdated\n"
        )
        (self.root / "LOG.md").write_text(
            "# LOG\nupdated\n"
        )

        out = self.s.sync_memory(
            "no-new-durable-memory",
            "handoff/log updated",
        )

        self.assertEqual(
            out["memory_status"],
            "no-new-durable-memory",
        )

    def test_stale_observation_from_previous_task_cannot_back_new_task(self):
        self.s.record_observed_tool({
            "tool_name": "Bash",
            "provider": "shell",
            "kind": "execution",
            "query": "python stale.py",
            "tool_use_id": "old",
            "success": True,
        })

        import time
        time.sleep(0.01)

        self.s.start_task(
            "x",
            "mechanical",
            "L1",
        )

        configure_profile(
            self.policy,
            "stale-check",
            "L1",
            {
                "L1": [
                    "python stale.py",
                ],
            },
        )

        self.s.select_verification_profile(
            "stale-check"
        )

        with self.assertRaises(ValueError):
            self.s.record_integration(
                "entry",
                "stale evidence",
                "old",
            )

    def test_repository_mutation_invalidates_prior_validation_and_memory(self):
        self.s.start_task(
            "x",
            "mechanical",
            "L1",
        )

        configure_profile(
            self.policy,
            "check",
            "L1",
            {
                "L1": [
                    "python check.py",
                ],
            },
        )

        self.s.select_verification_profile(
            "check"
        )

        self.s.record_observed_tool({
            "tool_name": "Bash",
            "provider": "shell",
            "kind": "execution",
            "query": "python check.py",
            "tool_use_id": "old-check",
            "success": True,
        })

        self.s.record_integration(
            "entry",
            "old integration",
            "old-check",
        )

        self.s.record_acceptance(
            "L1",
            "old acceptance",
            "old-check",
        )

        for name, body in [
            (
                "HANDOFF.md",
                "# HANDOFF\nupdated\n",
            ),
            (
                "MEMORY.md",
                "# MEMORY\nstable\n",
            ),
            (
                "LOG.md",
                "# LOG\nupdated\n",
            ),
        ]:
            (self.root / name).write_text(body)

        self.s.sync_memory(
            "no-new-durable-memory",
            "updated before mutation",
        )

        self.assertTrue(
            self.s.active_task()["gates"]["acceptance"]["passed"]
        )

        self.s.mark_implementation_started(
            "apply_patch",
            "write-after-validation",
        )

        task = self.s.active_task()

        self.assertFalse(
            task["gates"]["integration"]["passed"]
        )
        self.assertFalse(
            task["gates"]["acceptance"]["passed"]
        )
        self.assertFalse(
            task["gates"]["memory"]["passed"]
        )
        self.assertIsNone(
            task["acceptance"]["highest"]
        )

        with self.assertRaises(ValueError):
            self.s.record_integration(
                "entry",
                "replayed old run",
                "old-check",
            )

        self.s.record_observed_tool({
            "tool_name": "Bash",
            "provider": "shell",
            "kind": "execution",
            "query": "python check.py",
            "tool_use_id": "fresh-check",
            "success": True,
        })

        self.s.record_integration(
            "entry",
            "fresh integration",
            "fresh-check",
        )

        self.s.record_acceptance(
            "L1",
            "fresh acceptance",
            "fresh-check",
        )

        self.assertTrue(
            self.s.active_task()["gates"]["acceptance"]["passed"]
        )

    def test_pause_requires_continuity_sync(self):
        self.s.start_task(
            "x",
            "mechanical",
            "L1",
        )

        with self.assertRaises(ValueError):
            self.s.pause_task(
                "need to stop"
            )

        (self.root / "HANDOFF.md").write_text(
            "# HANDOFF\npaused at exact next step\n"
        )
        (self.root / "MEMORY.md").write_text(
            "# MEMORY\nno new durable fact\n"
        )
        (self.root / "LOG.md").write_text(
            "# LOG\npause reason recorded\n"
        )

        self.s.sync_memory(
            "no-new-durable-memory",
            "pause state persisted",
        )

        task = self.s.pause_task(
            "need to stop"
        )

        self.assertEqual(
            task["status"],
            "paused",
        )

    def test_verification_profile_cannot_change_after_implementation_starts(self):
        self.s.start_task(
            "x",
            "mechanical",
            "L1",
        )

        configure_profile(
            self.policy,
            "real",
            "L1",
            {
                "L1": [
                    "python integration.py",
                ],
            },
        )

        configure_profile(
            self.policy,
            "weaker",
            "L1",
            {
                "L1": [
                    "python easy.py",
                ],
            },
        )

        self.s.select_verification_profile(
            "real"
        )

        self.s.mark_implementation_started(
            "apply_patch",
            "write1",
        )

        with self.assertRaises(ValueError):
            self.s.select_verification_profile(
                "weaker"
            )

    def test_resource_plan_requires_observation_and_project_gpu_minimum(self):
        self.policy.setdefault(
            "project",
            {},
        )
        self.policy["project"].setdefault(
            "compute",
            {},
        )
        self.policy["project"]["compute"][
            "required_gpu_count"
        ] = 2

        self.s.policy = self.policy

        self.s.start_task(
            "x",
            "mechanical",
            "L1",
        )

        with self.assertRaises(ValueError):
            self.s.plan_resources(
                2,
                2,
                "use headroom",
                "",
                "never observed",
            )

        self.s.record_observed_tool({
            "tool_name": "Bash",
            "provider": "shell",
            "kind": "resource-inspection",
            "query": "python inspect_resources.py",
            "tool_use_id": "res1",
            "success": True,
        })

        snap = {
            "cpu": {
                "count": 16,
                "loadavg": [0, 0, 0],
            },
            "memory": {},
            "disk": None,
            "gpus": [
                {
                    "index": 0,
                    "eligible": True,
                },
                {
                    "index": 1,
                    "eligible": True,
                },
            ],
            "visible_gpu_count": 2,
            "eligible_gpu_count": 2,
        }

        with mock.patch(
            "rigor.state.inspect_resources",
            return_value=snap,
        ):
            with self.assertRaises(ValueError):
                self.s.plan_resources(
                    1,
                    2,
                    "use headroom",
                    "",
                    "res1",
                )

            plan = self.s.plan_resources(
                2,
                2,
                "use headroom",
                "",
                "res1",
            )

        self.assertEqual(
            plan["gpus"],
            2,
        )

    def test_auto_resource_plan_requires_all_eligible_gpus(self):
        self.s.start_task(
            "x",
            "mechanical",
            "L1",
        )

        self.s.record_observed_tool({
            "tool_name": "Bash",
            "provider": "shell",
            "kind": "resource-inspection",
            "query": "python inspect_resources.py",
            "tool_use_id": "res-auto",
            "success": True,
        })

        snap = {
            "cpu": {
                "count": 16,
                "loadavg": [0, 0, 0],
            },
            "memory": {},
            "disk": None,
            "gpus": [
                {
                    "index": 0,
                    "eligible": True,
                },
                {
                    "index": 1,
                    "eligible": True,
                },
            ],
            "visible_gpu_count": 2,
            "eligible_gpu_count": 2,
        }

        with mock.patch(
            "rigor.state.inspect_resources",
            return_value=snap,
        ):
            with self.assertRaises(ValueError):
                self.s.plan_resources(
                    1,
                    8,
                    "maximize measured headroom",
                    "",
                    "res-auto",
                )

            plan = self.s.plan_resources(
                2,
                8,
                "maximize measured headroom",
                "",
                "res-auto",
            )

        self.assertEqual(
            plan["live_snapshot"]["eligible_gpu_count"],
            2,
        )

    def test_assignment_role_must_match_spawn_profile(self):
        self.s.start_task(
            "x",
            "mechanical",
            "L1",
        )

        fields = {
            "objective": "map code",
            "reference": "current repo",
            "target": "src",
            "method": "read only mapping",
            "integration": "read-only evidence to Lead",
            "resources": "read-only/no compute",
            "write_scope": "read-only",
            "acceptance": "L0",
            "output": "map",
            "stop_conditions": [
                "scope ambiguity",
            ],
        }

        asg = self.s.create_assignment(
            "researcher",
            fields,
        )

        with self.assertRaises(ValueError):
            self.s.queue_assignment(
                asg["id"],
                "worker",
            )

        self.s.queue_assignment(
            asg["id"],
            "researcher",
        )

        self.assertEqual(
            self.s.bind_agent(
                "a1",
                "researcher",
            )["id"],
            asg["id"],
        )

    def test_runner_requires_resource_plan(self):
        self.s.start_task(
            "x",
            "mechanical",
            "L1",
        )

        configure_profile(
            self.policy,
            "runner-l1",
            "L1",
            {
                "L1": [
                    "python integration.py",
                ],
            },
        )

        self.s.select_verification_profile(
            "runner-l1"
        )

        fields = {
            "objective": "run eval",
            "reference": "current repo",
            "target": "evaluation",
            "method": "run selected profile",
            "integration": "real evaluator",
            "resources": "task resource plan",
            "write_scope": "outputs only",
            "acceptance": "L1",
            "output": "metrics",
            "stop_conditions": [
                "resource mismatch",
            ],
        }

        with self.assertRaises(ValueError):
            self.s.create_assignment(
                "runner",
                fields,
            )


class ShellWriteClassifierTests(unittest.TestCase):
    def test_common_repo_writes_detected_but_tmp_setup_allowed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            policy = json.loads(
                json.dumps(DEFAULT_POLICY)
            )

            self.assertTrue(
                is_repository_write_command(
                    "sed -i 's/a/b/' model.py",
                    policy,
                    root,
                )
            )

            self.assertTrue(
                is_repository_write_command(
                    "echo x > model.py",
                    policy,
                    root,
                )
            )

            self.assertTrue(
                is_repository_write_command(
                    "cp /tmp/ref.py model.py",
                    policy,
                    root,
                )
            )

            self.assertFalse(
                is_repository_write_command(
                    "mkdir /tmp/rigor-reference",
                    policy,
                    root,
                )
            )

            self.assertFalse(
                is_repository_write_command(
                    "rg Foo . 2>/dev/null",
                    policy,
                    root,
                )
            )

    def test_sensitive_paths_are_classified_generically(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            policy = json.loads(
                json.dumps(DEFAULT_POLICY)
            )
            policy["project"] = {
                "protected_surfaces": [
                    "src/coop/**",
                ],
            }
            self.assertTrue(
                is_sensitive_repository_target(
                    "src/coop/fusion.py",
                    policy,
                    root,
                )
            )

            self.assertFalse(
                task_class_allows_sensitive_write(
                    {"class": "mechanical"},
                    policy,
                    ["src/coop/fusion.py"],
                    root,
                )
            )

            self.assertTrue(
                is_sensitive_repository_target(
                    "src/models/predictor.py",
                    policy,
                    root,
                )
            )

            self.assertTrue(
                is_sensitive_repository_target(
                    "train_model.py",
                    policy,
                    root,
                )
            )

            self.assertFalse(
                is_sensitive_repository_target(
                    "README.md",
                    policy,
                    root,
                )
            )

            self.assertFalse(
                task_class_allows_sensitive_write(
                    {"class": "root-cause-fix"},
                    policy,
                    ["src/models/predictor.py"],
                    root,
                )
            )

            self.assertTrue(
                task_class_allows_sensitive_write(
                    {"class": "new-design"},
                    policy,
                    ["src/models/predictor.py"],
                    root,
                )
            )

            self.assertTrue(
                task_class_allows_sensitive_write(
                    {"class": "root-cause-fix"},
                    policy,
                    ["src/train_model.py"],
                    root,
                )
            )

            self.assertIn(
                "src/models/predictor.py",
                tool_write_targets(
                    "apply_patch",
                    {
                        "patch": (
                            "*** Update File: "
                            "src/models/predictor.py\n@@"
                        )
                    },
                    root,
                ),
            )

            self.assertIn(
                "src/models/predictor.py",
                tool_write_targets(
                    "Bash",
                    {
                        "command": (
                            "sed -i 's/a/b/' "
                            "src/models/predictor.py"
                        )
                    },
                    root,
                ),
            )

            self.assertIn(
                "src/models/predictor.py",
                tool_write_targets(
                    "Bash",
                    {
                        "command": (
                            "python3 -c "
                            "\"from pathlib import Path; "
                            "Path('src/models/predictor.py')"
                            ".write_text('x')\""
                        )
                    },
                    root,
                ),
            )

            self.assertTrue(
                is_governed_mcp_write(
                    "mcp__serena__replace_content",
                    {
                        "relative_path": (
                            "src/models/predictor.py"
                        )
                    },
                    policy,
                    root,
                )
            )

            self.assertFalse(
                is_governed_mcp_write(
                    "mcp__serena__find_symbol",
                    {
                        "relative_path": (
                            "src/models/predictor.py"
                        )
                    },
                    policy,
                    root,
                )
            )


class PassiveRepoHookTests(unittest.TestCase):
    def test_uninitialized_repo_is_not_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            env = {
                **os.environ,
                "PLUGIN_DATA": str(
                    Path(td) / "data"
                ),
                "PLUGIN_ROOT": str(ROOT),
            }

            event = {
                "cwd": td,
                "session_id": "s",
                "hook_event_name": "PreToolUse",
                "tool_name": "apply_patch",
                "tool_input": {
                    "command": "x",
                },
            }

            cp = subprocess.run(
                [
                    sys.executable,
                    str(
                        ROOT
                        / "hooks"
                        / "guard.py"
                    ),
                ],
                input=json.dumps(event),
                text=True,
                capture_output=True,
                env=env,
                check=True,
            )

            self.assertEqual(
                cp.stdout.strip(),
                "",
            )


class ObservedExecutionStatusTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

        self.root = Path(self.tmp.name) / "repo"
        self.root.mkdir()
        (self.root / ".codex").mkdir()

        os.environ["PLUGIN_DATA"] = str(
            Path(self.tmp.name) / "data"
        )

        self.policy = json.loads(
            json.dumps(DEFAULT_POLICY)
        )
        self.policy["enabled"] = True
        self.policy["git"]["require_clean_checkpoint"] = False

        configure_profile(
            self.policy,
            "execution-l1",
            "L1",
            {
                "L1": [
                    "python integration.py",
                    "python acceptance.py",
                    "python check.py",
                ],
            },
        )

        self.s = RigorState(
            self.root,
            self.policy,
        )

        self.s.start_task(
            "x",
            "mechanical",
            "L1",
        )

        self.s.select_verification_profile(
            "execution-l1"
        )

    def tearDown(self):
        os.environ.pop(
            "PLUGIN_DATA",
            None,
        )
        self.tmp.cleanup()

    def test_assignment_completion_requires_fresh_post_assignment_execution(self):
        self.s.record_observed_tool({
            "tool_name": "Bash",
            "provider": "shell",
            "kind": "execution",
            "query": "python integration.py",
            "tool_use_id": "before-assignment",
            "success": True,
        })

        fields = {
            "objective": "edit",
            "reference": "existing:a.py:Foo",
            "target": "a.py:Foo",
            "method": "bounded change",
            "integration": "entry->Foo",
            "resources": "no long run",
            "write_scope": "a.py",
            "acceptance": "L1",
            "output": "diff and evidence",
            "stop_conditions": [
                "reference mismatch",
            ],
        }

        asg = self.s.create_assignment(
            "worker",
            fields,
        )

        result = {
            "acceptance": "L1",
            "validation": "before-assignment",
        }

        with self.assertRaises(ValueError):
            self.s.validate_assignment_result_evidence(
                asg,
                result,
            )

    def test_failed_execution_cannot_back_acceptance(self):
        self.s.record_observed_tool({
            "tool_name": "Bash",
            "provider": "shell",
            "kind": "execution",
            "query": "python check.py",
            "tool_use_id": "bad",
            "success": False,
        })

        with self.assertRaises(ValueError):
            self.s.record_acceptance(
                "L1",
                "claimed",
                "bad",
            )

    def test_ambiguous_execution_cannot_back_integration(self):
        self.s.record_observed_tool({
            "tool_name": "Bash",
            "provider": "shell",
            "kind": "execution",
            "query": "python check.py",
            "tool_use_id": "unknown",
            "success": None,
        })

        with self.assertRaises(ValueError):
            self.s.record_integration(
                "entry",
                "claimed",
                "unknown",
            )

    def test_successful_execution_can_back_gates(self):
        self.s.record_observed_tool({
            "tool_name": "Bash",
            "provider": "shell",
            "kind": "execution",
            "query": "python check.py",
            "tool_use_id": "ok",
            "success": True,
        })

        self.s.record_integration(
            "entry",
            "observed integration",
            "ok",
        )

        self.s.record_acceptance(
            "L1",
            "observed acceptance",
            "ok",
        )

        task = self.s.active_task()

        self.assertTrue(
            task["gates"]["integration"]["passed"]
        )

        self.assertTrue(
            task["gates"]["acceptance"]["passed"]
        )


if __name__ == "__main__":
    unittest.main()