---
name: rigor-verify
description: Determine what a repository change actually proves and record integration or acceptance evidence before completion, task close, Git checkpoint, or final claims. Use after implementation, during end-to-end validation, or whenever low-level checks risk being mistaken for feature completion.
---

# Rigor Verify

Read references/acceptance.md and validate against the repository's
selected acceptance profile.

1. Do not count additional low-level checks as a substitute for a missing higher-level gate.
2. Use the real commands/tools defined by the selected repository acceptance
profile. Successful execution must be observed by PostToolUse.
3. After the real downstream path consumes the change, record integration with `scripts/rigorctl.py integration record --entrypoint <...> --evidence <...> --observed <planned-command/tool/tool_use_id>`.
4. Record the achieved level with `rigorctl acceptance record --level L0|L1|L2|L3|L4 --evidence <...> --observed <planned-command/tool/tool_use_id>`. L1-L4 require a successful matching observation from the frozen acceptance plan.
5. For learned/stateful systems, include the applicable real update/persistence/reload/runtime/evaluator lifecycle required by the task. For other systems, map the levels to their real user/system path.
6. Use fresh artifacts/checkpoints when the accepted outcome depends on generated state. Do not validate new code only against an old artifact unless old-artifact compatibility is the explicit task.
7. If the required level cannot be reached, pause with the exact blocker instead of calling the task complete.

The Hook blocks unsupported Stop and Git checkpoint attempts while required gates are missing.
