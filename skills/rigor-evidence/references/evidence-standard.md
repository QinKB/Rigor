# Evidence Standard

Evidence classes are generic and provenance-driven.

- `local-code`: current target repository or verified local reference path. By default it must be backed by a successful observed local search/inspection (`rg`, Serena, or repository tooling).
- `local-paper`: local literature used for discovery/context; it must be backed by an observed literature-library read/search.
- `primary-paper`: authoritative mechanism definition; it must be backed by an observed paper/source read, not just a remembered citation or search snippet.
- `official-spec`, `official-doc`: authoritative platform/protocol definition; they must be backed by an observed authoritative-source read.
- `upstream-code`: actual known-good implementation, ideally pinned to version/commit and exact file/symbol. By default it must be backed by a successful observed GitHub/git inspection.
- `external-search`: current discovery used to find alternatives, failures, issues, or newer work. It must be backed by the same successful observed provider (prefer Exa when available for broad discovery).
- `issue`: upstream/community failure report with enough context to affect a decision; it must be backed by an observed upstream/web source.
- `benchmark`: executed comparative evidence.

A title, abstract, search snippet, comment, memory note, or generated summary is not enough when exact mechanics determine the decision. A tool call that failed or whose success cannot be established is not accepted as observed evidence.

For reference adaptation/new design, prefer a chain covering: current local path -> primary definition -> actual implementation -> current external/failure evidence. If one genuinely does not exist, record the search gap and stop for Lead judgment rather than inventing a substitute.
