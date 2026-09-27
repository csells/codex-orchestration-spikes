# Proposed spikes: does Rory's orchestration policy buy more useful work?

Status: proposed, 2026-09-27. Preparation only; no comparative model trials have been run. One independent agent reviewed this experimental design. Its work is not a performance measurement.

The decision is whether a simple delegation policy lets Chris complete materially more acceptable work with his existing Codex allowance. We do not need an optimal router or a universal ranking of models to make that decision.

## Starting hypothesis

Rory's second instruction block is an executable prior: it gives the main agent a default allocation of work. Test it before rewriting it. Separate four possible effects:

1. Moving work to models with lower rates reduces total cost.
2. Returning worker summaries reduces material retained in the parent context.
3. Keeping the parent context smaller improves subsequent work or delays compaction.
4. Independent workers reduce elapsed time.

An experiment can support one without supporting the others. A shorter parent transcript is not itself a cost saving or a quality improvement. More aggregate tokens need not mean greater cost.

The relevant unit is a completed, checked task, including parent briefing, worker exploration, retries, review, integration, and repairs. The important distinction may be work that is cheap to verify, not work that sounds simple. A lengthy extraction with an exact checker could be a better candidate than a short judgment call that requires Astra to repeat the investigation.

## Evidence checked during preparation

- Installed CLI: `codex-cli 0.156.1`. Its help exposes model selection, noninteractive execution, and JSONL events. This does not establish that the JSONL stream includes complete, separately attributable child usage.
- `bb thread context --self --json` returns recorded context occupancy; in this session it reported `estimated: false`. Occupancy is separate from cumulative token consumption.
- The local provider catalog lists GPT-6 Astra, Sol, Luna, and GPT-5.6 Terra. Catalog visibility is not proof a worker request will execute successfully.
- The collaboration tools in this environment document that full-history forks inherit the parent model. Explicit model overrides require a fresh or partial context. Verify the selected worker model in runtime records, not the worker's self-description.
- Current host instructions encourage proactive delegation. A default workflow may already delegate. Record that behavior; do not call it a single-agent baseline unless it actually is one. Experimental policy must not conflict with higher-priority host instructions.
- [Official subagent guidance](https://learn.chatgpt.com/docs/agent-configuration/subagents) describes separate worker contexts, summarized returns, and model-specific configurations. It supports the mechanism's plausibility, not a measured benefit on Chris's tasks.
- [Published Codex pricing](https://learn.chatgpt.com/docs/pricing) gives Standard credit rates whose ratios are Astra:Sol:Luna = 100:20:1 for corresponding token categories. It explicitly says credit prices alone do not determine included subscription usage. Use actual quota observations for quota claims.
- [Agents API usage guidance](https://developers.openai.com/api/docs/guides/agents-api/observability) identifies input, cached input, output, and reasoning usage, and the need to account for children and retries. That API documentation does not prove the local CLI exposes every field.

## Spike 1: verify the mechanism and measurement

Fold this check into the first treatment run below where possible. Otherwise use one bounded, read-only repository inventory with an independently checkable answer. Avoid a model comparison matrix.

Observe:

- Did the main agent actually delegate under Rory's policy?
- Which model and reasoning setting executed each worker? Was its context fresh, partial, or fully inherited?
- What task-related history and global instructions did the worker actually receive?
- Can we attribute usage to the parent and every child without double counting provider totals?
- Did Astra consume the worker's handoff, selectively verify it, or redo the investigation?
- Can the account meter resolve the run's change, with timestamps and reset boundaries recorded?

Missing telemetry is unknown, not zero. If full child usage is unavailable, establish what can be measured before claiming total cost. If the account meter is too coarse, continue testing quality and context but leave included-budget savings unresolved. If model routing fails, diagnose that failure before interpreting the policy's economics.

Keep the preflight bounded: one task and its instrumentation. No continuing rounds of increasingly elaborate probes without a specific missing measurement to resolve.

## Spike 2: small paired pilot of the actual policy

Three task shapes, two conditions: six initial runs.

| Task | Concrete shape | Independent acceptance |
| --- | --- | --- |
| Small lookup | Find all declarations and consumers of one named setting in a fixed repository snapshot. | An answer key or deterministic inventory of expected references, distinguishing declarations from incidental mentions. |
| Broad investigation | Audit one documented workflow against its implementation and identify discrepancies with evidence. | Predetermined discrepancy checklist and verification of each reported claim; record missed discrepancies and false positives. |
| Routine implementation | Repair a previously fixed bug using the pre-fix source snapshot and original issue description. | Regression test that fails on the starting snapshot, passes on the historical fix, and checks behavior rather than the historical patch's shape; relevant existing tests also pass. |

Select tasks before seeing experimental outputs. Prefer tasks from Chris's actual work with existing checks. Freeze the repository revision, prompt, acceptance criteria, and external fixtures. Keep the historical answer/fix outside worker-accessible material. Do not let the model write a test and then use only that test as its own success criterion.

Conditions:

- **Default:** Astra with the current workflow, without Rory's block. Keep existing applicable instructions consistent across conditions and record any spontaneous delegation.
- **Rory:** The same setup with his second block in the experiment's durable project instructions. Resolve family names once to exact model IDs: `gpt-6-luna`, `gpt-5.6-terra`, `gpt-6-sol`; main `gpt-6-astra`. Disclose the Terra generation. Add only the host-specific adapter necessary to execute explicit model selection, such as fresh-context spawning. Preserve the original task-allocation wording.

Fix each model's reasoning setting and service/speed setting before running. Use the same root setting in both conditions. Do not silently upgrade a model or change effort halfway through a comparison. Ordinary recovery is allowed and counted; record all substitutions.

Use separate clean copies and fresh parent sessions, identical task prompts and tool access. Counterbalance run order across tasks; a fresh session does not guarantee a cold provider cache. Save observed cached-token usage. For account-meter attribution, run experimental conditions sequentially and exclude intervals with other account activity or resets. Do not stop unrelated work without authorization; postpone or mark account-meter observations contaminated instead.

For each run, record:

| Measure | Interpretation |
| --- | --- |
| Acceptance result and specific defects | First-attempt result and final result after counted repairs; failures remain visible. |
| Parent and worker token categories by actual model | Input, cached input, output, reasoning when exposed. Reasoning is a subset of output when the provider reports it that way. |
| Estimated credit charge | Apply the applicable rate to each category. This is a credit-equivalent estimate, not included-quota consumption. |
| Actual account usage change | Timestamped meter before/after; note rounding, delayed updates, other activity, and resets. |
| Parent context occupancy | Start, peak, end, and compaction events; do not substitute cumulative input-token totals. |
| Time to acceptable completion | Includes waits, validation, repair, and integration. |
| Delegation behavior | Spawned agents, models, task briefs, retries, returned evidence, and parent duplication. |

Use the same acceptance-and-repair protocol for both conditions. Record first-pass failures even if subsequently fixed. Set a maximum of one externally reported repair round for this screening pilot; an unresolved task is a failure, not a cheap completion. Count all work before the cap. This cap is a proposed experiment boundary, not a recommended production behavior.

Early decision: the six runs screen for a useful signal, not statistical proof. A practical candidate is a repeated saving large enough to matter, for example roughly 25% or more, with comparable acceptance and tolerable latency. The 25% is a proposed decision threshold, not a scientific constant. Repeat a promising task class on two new comparable tasks before treating it as a rule. A cheaper failed run does not qualify. A context-only benefit proceeds to Spike 4 even if immediate cost is flat. If there is no benefit, inspect the trace before spending more.

## Spike 3: find the cause of a promising result or specific failure

Run only the branch that the pilot justifies.

- **If cheap delegation wins:** On the promising task class, compare fresh Astra workers with fresh cheaper workers under the same stated assignment and handoff requirements. This estimates how much model routing contributes beyond the delegation arrangement. Different model behavior prevents a perfect causal isolation, which must be acknowledged.
- **If the task seems to need little supervision:** Try Sol alone on that task with the same acceptance checks. A win over the default Astra workflow does not establish that Astra coordination was necessary. Reserve this control for the task class where that question actually arose.
- **If Luna causes expensive rescue:** Repeat that specific assignment with Sol. Measure total completion cost, particularly how much Astra had to do after the handoff. Do not infer the winner from retry counts alone.
- **If startup dominates:** Compare separate small assignments with one coherent batch of related questions.
- **If summaries omit needed facts:** Repeat with evidence paths, relevant exceptions, and a narrowly specified deliverable. Track whether this actually reduces parent re-reading.

Make one change at a time and label these variants separately from Rory's original policy. Keep trials bounded to the task class that produced the observation; no all-model, all-task grid.

## Spike 4: test the benefit that a fresh-task benchmark misses

Compare default and the promising policy on the same short sequence of related tasks in two independent parent sessions. Start with five realistic tasks; preserve each session's history between tasks. Use a frozen prompt sequence and independently checked outcomes so one run's discoveries do not coach the other.

Include a later task that needs an earlier constraint or exception, with a deterministic acceptance check where possible. This tests whether useful context survives alongside the reductions in noise.

Compare cumulative accepted tasks, full-tree cost, account usage where attributable, time, parent occupancy, and constraint failures. A smaller main context may yield savings only on later turns; a thin handoff may create costs only when an earlier detail is needed again.

Record natural compactions. If neither session reaches one, report that the experiment did not test compaction persistence. A forced compaction can separately test whether a policy and important constraint survive; it cannot establish how much longer a natural session lasts. Do not pad the context with junk merely to force an impressive-looking rollover result.

## How results become usable instructions

The experiment produces fixed defaults a future agent can follow. It does not instruct that agent to infer nonexistent performance history.

Examples of possible measured rules: use Luna for a specified inventory task; use Sol for a specified audit class; keep tiny lookups local; return evidence and exceptions; escalate after a failed acceptance check. Adopt a rule only as broadly as the observed tasks justify. Revisit it after meaningful model or harness changes, rather than continuously benchmarking every request.

## Recommended starting investment

Do the routing/accounting preflight and six-run pilot first. Reuse existing regression checks and a small results file; avoid building an evaluation product. Task/repository selection and the account-meter capture method remain to be fixed before execution. No global agent instructions or production code were changed during this preparation.
