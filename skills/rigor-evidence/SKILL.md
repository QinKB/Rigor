---
name: rigor-evidence
description: Gather and select evidence before choosing, changing, reproducing, or replacing a non-trivial technical mechanism, architecture, algorithm, protocol, data transformation, evaluator, or unfamiliar failure fix. Use when the active Rigor task has a research/design gate or current external evidence could materially change the approach.
---

# Rigor Evidence

Use evidence to constrain design; do not search merely to decorate a decision already made.

1. Read [references/evidence-standard.md](references/evidence-standard.md).
2. Trace the current repository first: real entry point, owning symbols, data/control path, and nearby implementations. Use an observable local-code search such as `rg`, Serena, or repository inspection.
3. Search configured local references/literature when relevant, then open the primary definition and actual upstream implementation/issues when they exist.
4. Perform current external discovery when prior art, known failures, version behavior, or community implementation experience can change the decision. Prefer Exa for broad discovery when available, then open primary sources.
5. Register only selected evidence. Evidence used for the research gate must be backed by a successful Hook-observed read/search from the current task; earlier-task observations do not count. Pass `--observed <command/tool/tool_use_id>` for local code, local/primary literature, official sources, upstream code/issues, and external search. Do not self-assert that a paper, implementation, issue, or search was inspected.
6. When required evidence is complete, freeze the design and bind it to the selected evidence IDs emitted by `evidence add`: `rigorctl design freeze --reference ... --reference-evidence ev_... --reference-evidence ev_... --target ... --method ... --integration ... --acceptance ...`. Reference-adaptation/new-design requires the bound set to include a primary definition and an upstream implementation by default.
7. Search results are discovery evidence. A design reference must be registered as verified evidence after opening the decisive primary content or exact upstream implementation.

For reference adaptation/new design, the default chain is current local path -> primary definition -> actual upstream implementation -> current external/failure evidence. If a required evidence class genuinely does not exist, pause and report that constraint rather than inventing a source or substitute.

Never replace the selected mechanism with an easier shape/interface-compatible approximation without returning incompatibility evidence to the Lead. Domain-specific historical mistakes belong in regression scenarios, not this general policy.

