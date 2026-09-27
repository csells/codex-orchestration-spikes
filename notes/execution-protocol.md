# Frozen execution protocol — initial pilot

This records the implementation of the original plan before the six pilot runs.

## Scope and deliberate adaptations

- Use the native Codex CLI 0.156.1, not BB threads, for repeatable execution and access to persisted per-response accounting. Findings apply to this harness configuration.
- The same isolated, private CODEX_HOME supplies subscription authentication and telemetry. User configuration, plugins, apps, and host skill discovery are excluded from both conditions. This reduces unrelated activity and prevents publishing private global instructions. It is not a claim to reproduce Chris's entire daily BB environment.
- Source tasks use a curated subset of the public csells/disputatio repository, with provenance, license, and hashes preserved. Omitted upstream AGENTS/history/graphs/research are documented in PROVENANCE.md; common experiment instructions replace them in both conditions.
- Root model: gpt-6-astra, high reasoning. Workers explicitly request high reasoning and fresh context. Models: GPT-6 Luna/Sol and GPT-5.6 Terra. No Fast override. Native multi_agent and multi_agent_v2 enabled; web search disabled.
- Common instructions permit native delegation but do not require it. Rory treatment additionally contains the article's second block verbatim. Native defaults remain part of the control; observe whether it delegates.
- At most two active workers, no grandchildren. Use fake CLI tests only; no real debate/init/doctor calls.
- First pass capped at 900 seconds per task. Timeout is a failed/inconclusive run, never a success. One repair turn may follow failed external validation; preserve and count both attempts.
- Run order: lookup/default, lookup/rory; audit/rory, audit/default; bug/default, bug/rory. Root sessions are fresh and source copies isolated. Record cached tokens rather than assume cold caches.
- The lookup is a focused setting trace including precedence and tests, not a single grep. The tiny preflight separately exposes routing overhead but is not a paired performance comparison.
- Evaluation answer keys and the historical fixed implementation stay outside model workspaces. Frozen prompts restrict reading outside workspace and network access. This is procedural isolation, not a claim that the entire host filesystem is unreadable.

## Accounting and public records

Preflight proved that `codex exec --json` turn usage reports root usage only in this configuration. The collector instead deduplicates per-response `token_usage_record` entries across the root and descendants and checks actual model IDs in `turn_context`. Fork-copied historical usage is excluded.

The preflight's three reference locations were correct. Its actual root was Astra high and its fresh worker Luna high. Its telemetry is preserved separately from task comparisons.

Context figures in native rollout telemetry are labeled as per-response input footprints; they are not claimed to be exact live BB context occupancy. Compaction events are counted separately. Output reasoning is a subset of output tokens, not an additional charge.

Public CLI event streams retain tool execution and returned answers with local path prefixes replaced. Public telemetry includes numeric per-model usage, response counts, model/effort, and anonymous parent/child labels; full raw rollouts remain private because their instruction envelopes can contain unrelated host context. Credential files are never copied into publication. The private original records remain available locally for further checking.

Account quota snapshots are account-wide and may be rounded or delayed. Planning/reporting activity and unrelated account use can overlap trials. Therefore quota changes are published as observations but cannot establish attributable per-task subscription savings in this run. Credit-equivalent estimates remain explicitly distinct.

## Before-trial verification

The frozen current-source compatibility suite passed (80 passed, one optional build skipped). All four audit probes passed. The historical bug's compatibility suite passed on the broken revision, while its actual upstream timeout regression failed at 8256 ms. The historical fixed implementation passed both compatibility and that regression at 2243 ms. These observations establish that the acceptance check distinguishes the known defect.
