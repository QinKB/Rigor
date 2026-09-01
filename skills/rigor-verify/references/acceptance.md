# Acceptance Levels

- **L0 - Preflight:** syntax, imports, static checks, shapes/interfaces, mocks, isolated unit tests, narrow CPU checks. Proves only the local property tested.
- **L1 - Integrated:** the change executes through the real target entry point and its intended downstream consumer uses the result.
- **L2 - Operational:** the required real state-changing lifecycle succeeds. For learned systems this usually includes forward/objective/backward/update; use the project-equivalent lifecycle elsewhere.
- **L3 - Reproducible runtime:** current code/config produces any required fresh artifact/state and that artifact survives the intended reload/runtime/inference path with identifiable provenance.
- **L4 - Outcome accepted:** the authoritative evaluator/protocol or closest practical user/scientific outcome produces valid, reasonable, interpretable evidence.

The task declares its required level before implementation. A Git commit is not an acceptance level. A component file existing in the tree is not L1 unless the real path consumes it.
