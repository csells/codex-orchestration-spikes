# Codex orchestration spikes

Reproducible, bounded experiments testing Rory's proposal to use Astra as an orchestrator with cheaper workers.

**Completed:** ten fresh-task trials, two independent five-turn sessions, and a routing/accounting preflight. [Read the report and feedback for Rory](REPORT.md).

The experiments demonstrate that a whole-task handoff can reduce parent input. They did not establish an equivalent-quality cost saving for the tested delegation policies. Across five turns, our bounded variant used 27% less peak parent input but 73% more estimated credits, with 32/34 coverage versus 34/34. Both sessions retained the earlier constraint; neither compacted. The original short block, long block, and our variant are distinguished in the report. These estimates do not measure subscription savings.

The question is practical: does an executable delegation policy produce more accepted work for the cost, and does it keep the main session's context smaller? A cheaper incomplete answer is not an equivalent-quality saving. More total tokens can still cost less when the work moves to cheaper models.

- [Rory's original article, as supplied](source/rory-orchestration-guide-2026-09-27.md)
- [Initial proposed experiment](specs/plans/0001-subagent-orchestration-spikes.md)
- [Frozen initial protocol](notes/execution-protocol.md), [follow-up decisions](notes/follow-up-protocol.md), and [five-turn protocol and disclosed selection deviation](notes/session-protocol.md)
- [Source provenance and exclusions](PROVENANCE.md), [fixture hashes](fixture-manifest.json), and [quality rubrics](evaluation/)
- [Machine-readable results](results/summary.json) and [measurement/public-data details](notes/accounting-and-public-data.md)

## Inspect the published results

The public data do not require account access. Recompute Standard credit-equivalent estimates and run accounting/export regression checks with Python3:

```sh
python3 scripts/summarize.py
python3 scripts/summarize_sequence.py
python3 scripts/check_records.py
python3 -m unittest discover -s scripts -p 'test_*.py' -v
```

Each completed run retains its exact task, project instructions, answer, patch, elapsed execution time, per-model full-tree telemetry, visible execution evidence, and external validation. Resumed-session telemetry is **cumulative**: never add successive snapshots. Account-meter observations are rounded/account-wide and cannot attribute subscription savings to these runs.

Local source checks use a Node version supporting native TypeScript execution. Recorded environment: Node v26.8.2, Codex CLI 0.156.1. No production model service is required for the fixture checks:

```sh
node evaluation/verify_audit.mjs fixtures/current
python3 evaluation/evaluate_bug.py /absolute/path/to/candidate-workspace
```

The bug evaluator uses pristine tests plus the historical upstream timeout regression, not just a candidate's own tests. The default current-source suite has an optional bundled-build test that skips without esbuild. See [verification](verification/) for the before-trial evidence.

## Repeat model trials

These commands consume model allowance and require the model IDs recorded in [common instructions](policies/common.md). Authenticate the Codex CLI in a **private** CODEX_HOME outside this repository. Never commit its authentication or raw session files. Reproduction may need adaptation as native CLI interfaces and model availability change.

From this repository's root, replace the example paths with absolute private paths and choose new run IDs:

```sh
python3 scripts/run_trial.py --task audit --policy default \
  --run-id replication-audit-default \
  --private-root /absolute/private/runs \
  --codex-home /absolute/private/codex-home

python3 scripts/run_trial.py --task audit --policy rory \
  --run-id replication-audit-rory \
  --private-root /absolute/private/runs \
  --codex-home /absolute/private/codex-home

python3 scripts/run_sequence.py --prefix replication-sequence \
  --private-root /absolute/private/runs \
  --codex-home /absolute/private/codex-home
```

The sequence runner alternates condition order by stage and resumes each condition's own source workspace and conversation. It preserves completed attempts and stops on incomplete/failed attempts instead of silently overwriting them. The execution cap is 900 seconds per turn. The initial/follow-up protocols specify the actual original run order and deliberate harness adaptations.

Before sharing new data, export task-visible traces and review all outputs for sensitive content:

```sh
python3 scripts/refresh_records.py --prefix replication- \
  --private-root /absolute/private/runs \
  --codex-home /absolute/private/codex-home
python3 scripts/summarize.py
```

`refresh_records.py` uses each run's end timestamp so later resumed turns cannot leak into an earlier snapshot. It omits instruction envelopes and reasoning, replaces observed opaque provider strings with hash/length markers, and sanitizes local paths. This is an exporter for the observed provider format, not a universal secret detector. Do not publish raw CODEX_HOME files. External scoring is separate from model execution; use the frozen rubric without showing the grader policies or cost.

## Attribution

Rory authored the supplied article. Reproducing it here does not relicense his writing or assert that these experiments are his work. The Apache-2.0 source fixtures retain their upstream license. Experiment design, policies labeled as our variants, and conclusions are separate.

This investigation began after an assistant gave Chris a dismissive critique and proposed an unusable alternative. That response was not evidence. The purpose of this repository is considered, inspectable feedback.
