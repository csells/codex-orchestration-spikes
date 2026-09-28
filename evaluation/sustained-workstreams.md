# Sustained coding workstreams

These are two **new functional feature sequences**, using the public Apache-2.0 Disputatio source snapshot `706995b0934ba3ad28684c6b68e965b1b0d9995c`. They do not reuse the earlier timeout repair, budget inventory, or workflow-audit tasks. The original snapshot is unchanged and contains neither requested feature module.

Each condition starts from a fresh copy of `fixtures/current`, then receives eight related coding requests in one continuing session. The same eight prompts are used across policies. Future prompts, metadata, this document, external tests, and reference implementations must not be copied into candidate workspaces. The tested agent may write its own implementation/tests and reuse workers. Root orchestration owns policy selection, model execution, accounting, caps, and any standard repair opportunity.

The sequences are deliberately compact. They offer opportunities to retain decisions, reuse workers, and respond to corrections; they do not guarantee or force compaction. Do not insert token padding or claim a long-context benefit merely because eight turns occurred.

## Workstream A: named configuration bundles

A user adds reusable profile bundles around the existing YAML configuration format, then a rendering CLI that emits YAML usable by ordinary Disputatio `--config`. The initial no-writes/fresh-returned-objects invariant persists through inheritance, overrides, correction, path validation, and CLI work.

| Turn | New behavior tested |
|---|---|
| 1 | JSON envelope, relative YAML loading, errors, independently owned results, unchanged inputs |
| 2 | Single-parent inheritance and initially requested merge-by-adapter participant policy |
| 3 | Inline overrides, explicit judge removal, validation, overrides-only profiles |
| 4 | Actual requirement correction: supplied participant lists replace inherited lists completely |
| 5 | Default profile selection, explicit precedence, cycles and missing parents |
| 6 | Relative and realpath confinement to the bundle's real directory |
| 7 | YAML rendering CLI and meaningful error exits |
| 8 | Sorted profile discovery and JSON rendering with incompatible-flag checks |

## Workstream B: saved-debate catalog and artifact access

A user adds cataloging and exact artifact extraction for existing saved debates. The initial read-only/no-child-symlink-following invariant persists across metadata, queries, pagination correction, and CLI work. Catalog status interpretation is an explicitly specified new strict classifier; the existing engine parser stays unchanged.

| Turn | New behavior tested |
|---|---|
| 1 | Immediate debate-directory discovery, file-presence metadata, read-only/symlink behavior |
| 2 | Highest numeric determination and strict status metadata |
| 3 | Newest-first pagination and query validation |
| 4 | Initially requested page-window filtering |
| 5 | Exact artifact reads with path/absence/error behavior |
| 6 | Actual requirement correction: filter matching records before pagination |
| 7 | JSON catalog CLI, option parsing, and errors |
| 8 | Exact artifact CLI output, absence exit 2, conflicting modes, safe paths |

The corrections replace earlier requirements; the evaluator changes the relevant assertion at the correction stage rather than requiring contradictory old and new behavior. Other prior requirements remain cumulative.

## Executable acceptance

Run:

```
python3 evaluation/evaluate_sustained.py WORKSPACE --workstream a --stage 4
python3 evaluation/evaluate_sustained.py WORKSPACE --workstream b --stage 8 --json-output result.json
```

The evaluator copies candidate files to a temporary checkout, replaces candidate tests with the pristine original `fixtures/current/test` suite, and runs that suite directly with Node. It then runs `sustained_cases.mjs` against the candidate implementation using generated temporary input files and fake local data. It does not invoke model services. Success requires both original compatibility and all current cumulative functional assertions. The optional original bundled-build check may skip when esbuild is absent, matching the fixture baseline.

The source-level API and CLI signatures, data shapes, relevant ordering, error codes, correction semantics, and exercised edge cases are all in the corresponding user prompts. These are behavior checks, not prose coverage grades. No score depends on whether the final explanation quotes a particular term, supplies a particular file citation, names a tool, or is verbose. Equivalent implementations are accepted.

`repair_feedback` is a concise top-level report containing current failing checks and bounded failure details, so a driver can provide corrective feedback without repeating all passing-test logs. The complete report retains original-test evidence separately. Reports do not contain future test source or future prompt contents. First-attempt and repaired outcomes must be distinguished if the driver allows repair.

Checks include independent mutation of returned data, input-tree snapshots around representative loader/catalog/CLI calls, hand-constructed inheritance/query cases, paths and symlinks to generated external test data, exact output bytes, exit codes, and original compatibility. These assertions demonstrate the checked cases; they do not prove complete filesystem confinement, eliminate all time-of-check/time-of-use races, or cover every possible malformed input.

The evaluator has bounded execution (90 seconds original compatibility; 45 seconds functional checks). A timeout is an incomplete result, not evidence of semantic wrongness by itself; report it distinctly. Model/turn hard caps are driver concerns. No artificial context growth is included.

## Validation before model execution

The untouched source must fail because requested modules do not exist while its original suite passes. Private hand-written reference implementations exercise all stages, including the differing pre/post-correction semantics, to validate the acceptance harness. Those reference implementations are preparation tools, not experimental model outputs and not candidate-visible. Their check summaries are recorded in `sustained-verification.json`.

This is a small fixed coding pilot on one TypeScript project. It tests end-to-end functional completion and coordination under evolving requirements, not universal model rankings. Freeze/hash prompts and evaluator before model runs; do not adjust expectations after observing policy results.
