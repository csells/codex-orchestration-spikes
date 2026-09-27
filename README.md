# Codex orchestration spikes

Small, reproducible experiments testing Rory's proposal to use Astra as an orchestrator with cheaper workers.

**Status:** experiments being prepared. No comparative results yet. This repository will preserve failures, adaptations, and measurement limits alongside successful runs.

The question is practical: does a simple delegation policy produce more correct, useful work for the cost, and does it keep the main session's context smaller? A cheaper failed answer is not a saving; a higher aggregate token count is not necessarily a higher cost.

## Starting material

- [Rory's original article, as supplied](source/rory-orchestration-guide-2026-09-27.md)
- [Proposed staged experiment](specs/plans/0001-subagent-orchestration-spikes.md)
- [Preparation evidence and boundaries](notes/preparation.md)

The initial plan is preserved as written. Execution changes and their reasons will be recorded separately. We will first test the article's second, short instruction block, rather than replace it with an imagined optimal router.

## Experiment sequence

1. Verify model routing, worker context, and usage accounting.
2. Run a paired pilot: a small lookup, a documentation/code audit, and a historical bug repair.
3. Run targeted follow-ups justified by the pilot.
4. Compare a short sequence of related tasks when the earlier results justify a session-level trial.

Each run will retain its prompt, settings, source revision, answer or patch, validation outcome, elapsed time, and publishable execution/usage records. Private account credentials and unrelated local context are excluded from public records. Sanitization will be documented.

## Attribution

Rory authored the supplied article. Reproducing it here does not relicense his writing or assert that these experiments are his work. The experiment design and conclusions are separate, and any criticism must be grounded in the measured results and their limits.

This investigation began after an assistant gave Chris a dismissive critique and proposed an unusable alternative. That response was not evidence. The purpose of this work is to produce considered, reproducible feedback.
