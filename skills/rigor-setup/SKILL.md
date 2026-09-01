---
name: rigor-setup
description: Initialize or repair Codex Rigor for a repository. Use when enabling the plugin in a project, creating its policy and continuity files, installing project/user subagent profiles, or checking whether Rigor is correctly configured before governed work begins.
---

# Rigor Setup

Set up the repository once, then leave enforcement to Hooks and the other Rigor skills.

1. Resolve this Skill directory before running bundled scripts; do not assume the repository cwd contains them.
2. Run `scripts/setup_project.py --root <repo> --install-agents` for normal project setup.
3. Inspect `<repo>/.codex/rigor.json`. Keep enforcement enabled unless the user explicitly wants advisory mode.
4. Preserve existing `HANDOFF.md`, `MEMORY.md`, `LOG.md`, `.codex/agents/*.toml`, and policy files unless explicit replacement is requested. The setup script is non-destructive by default.
5. Verify the five agent profiles exist under `<repo>/.codex/agents/`: scout, researcher, runner, worker, reviewer.
6. Start a new Codex thread or review/trust the plugin Hooks through `/hooks` after installation or Hook changes.
7. Inspect the repository and populate project.entrypoints, project.protected_surfaces, project.acceptance_profiles, and project.compute.

Do not set project.configured=true until the real entry points and authoritative acceptance path have been inspected.

Do not encode project-specific algorithms in the global plugin. Put repository-specific acceptance, compute, or safety overrides in `.codex/rigor.json`.
