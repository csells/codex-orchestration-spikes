# Faithful policy comparison: two coding workstreams

**Rory's short and long policies lost on estimated execution cost and time on both tested workstreams.** All six sessions completed the same eight functional stages successfully. Neither policy reduced peak parent input. This is evidence about these policies on two feature sequences in one TypeScript project—not a verdict that Rory's experience is false or that delegation cannot help.

This follow-up fixes the earlier pilot's central mismatch: it uses Rory's actual second short block and his long block, gives them related coding work in persistent sessions, permits worker reuse, and checks implemented behavior independently. We also ran actual native compaction probes. Subscription savings and natural long-session compaction remain unresolved for the specific reasons below.

## Direct wins and losses against default

A adds configuration profile bundles and a rendering CLI. B adds a saved-debate catalog and artifact CLI. Each has eight staged requests, a standing invariant, related follow-ups, and a corrected requirement. Future requirements and external acceptance code stay outside candidate workspaces. [Tasks and acceptance rationale](evaluation/sustained-workstreams.md).

| Workstream | Policy | Functional stages | Estimated credits | Cost versus default | Execution minutes | Time versus default | Peak parent input | Context versus default |
|---|---|---:|---:|---|---:|---|---:|---|
| A: profiles | Default | 8/8 | 136.78 | Reference | 20.78 | Reference | 106,839 | Reference |
| A: profiles | Rory short | 8/8 | 287.33 | **LOSS +110%** | 27.34 | **LOSS +32%** | 148,286 | **LOSS +39%** |
| A: profiles | Rory long | 8/8 | 259.07 | **LOSS +89%** | 24.76 | **LOSS +19%** | 114,165 | Unresolved, +7% |
| B: catalog | Default | 8/8 | 154.40 | Reference | 18.74 | Reference | 98,103 | Reference |
| B: catalog | Rory short | 8/8 | 220.47 | **LOSS +43%** | 22.70 | **LOSS +21%** | 109,973 | **LOSS +12%** |
| B: catalog | Rory long | 8/8 | 231.05 | **LOSS +50%** | 22.94 | **LOSS +22%** | 104,160 | Unresolved, +6% |

The frozen descriptive threshold was 10%. Smaller differences are unresolved, not equivalence. “Credits” are full-tree Standard pricing-derived estimates, **not measured subscription charges or dollars**. Execution time sums native task turns, including workers and internal fixes; it excludes external grading, meter settling, and preparation pauses. Peak provider input is a context proxy, not exact live occupancy. [Machine-readable results](results/faithful-summary.json), [pricing/accounting method](notes/accounting-and-public-data.md).

All **48 stages passed their first external evaluation**; no standardized external repair turn was needed. Internal failures and fixes still occurred and are included in usage/time. Final checks include 17 new functional checks for A or 12 for B plus 80 pristine original tests; one optional build test skips without esbuild. Tests pass on [pre-execution reference controls](evaluation/reference-controls/README.md) and fail on untouched baselines. The controls were published only after the model trials. This measures the specified outcomes, not every possible defect or the value of additional candidate-authored tests.

Functional completion is separate from operating-rule compliance. One A-long worker ran `npx tsx --test test/profile-bundle.test.ts`, causing an attempted npm registry request despite the explicit no-network task constraint; the request failed with `ENOTFOUND`, with no successful fetch observed. [Execution evidence](results/faithful-a-rory-long/trace.jsonl#L601), [task instruction](tasks/sustained-a/turn-5.md). No comparable attempt, publishing action, real external model invocation, or answer-key access was found in the other visible completed traces. These are trace-audit findings, not proof of exhaustive confinement. A-long and B-long also read their own `/tmp` test logs; that exposes ambiguity in the common adapter's overly literal outside-workspace restriction, not evidence of unrelated private-data access. Supplied AGENTS files remained unchanged.

## What happened to the work and cost

The rule blocks encouraged delegation: both default sessions used no workers; every Rory session used workers. That is an observed policy difference in these runs.

| Workstream / policy | Astra parent credits | Worker credits | Parent responses | Worker threads | Parent follow-up calls |
|---|---:|---:|---:|---:|---:|
| A default | 136.78 | 0 | 48 | 0 | 0 |
| A short | 259.29 | 28.04 | 92 | 2 | 7 |
| A long | 229.96 | 29.11 | 98 | 8 | 0 |
| B default | 154.40 | 0 | 62 | 0 | 0 |
| B short | 195.36 | 25.11 | 89 | 1 | 7 |
| B long | 197.67 | 33.39 | 84 | 1 | 7 |

In A, visible worker edits primarily produced tests while Astra retained production implementation and validation. Delegation added worker execution and coordination while leaving substantial parent work. Parent responses issuing ordinary `exec` calls cost 118.81 credits for default,136.92 short, and 132.64 long. Parent cached-input charges grew from 74.72 to 183.87/161.22. The added cost was predominantly Astra's, not simply the price of cheap workers.

B shows a more nuanced result: parent `exec`-response cost **fell**, from 137.14 to 116.20/112.95 credits. B-short's worker also implemented production code. But worker and coordination costs outweighed those reductions. Parent responses issuing coordination calls accounted for 61.18/68.24 credits in B (98.93/80.56 in A). These are model-response costs associated with those calls, **not tool fees**, and not all necessarily avoidable. Extra testing may be valuable; the independent acceptance outcomes did not demonstrate an additional quality benefit here. [B-short production edit](results/faithful-b-rory/trace.jsonl#L375).

The [response-cost breakdown](verification/sustained-cost-breakdown.json) is reproducible with `python3 scripts/analyze_sustained_cost.py`. Its disjoint response categories reconcile to each root’s total usage and cost; they describe association with tool calls, not a causal estimate of removable overhead.

The meaningful lesson from these observations is narrower than “never delegate”: lower worker token prices did not produce net savings under these actual policies and allocations. A future policy would need to displace enough parent work and coordination cost to beat default. That remains a hypothesis; this report does not label an untested alternative better.

## Worker reuse and actual continuation

The runtime preflight verified the same Luna worker across two parent turns. The controller deleted its source file between turns; the original worker returned the remembered fact without a second tool call. The first, infrastructure-failed probe is preserved too. [Proof and limitations](results/reuse-preflight/README.md).

In the scored runs, short A reused a Terra worker; long A created eight fresh workers despite reuse being available. Both B policies reused one Terra worker through seven follow-ups. The long rule's fresh-worker behavior in A is an observed policy outcome, not a harness-imposed replacement. After a stage-five transport restart, the native parent and existing worker identities were checked separately. [Identity/model evidence](verification/sustained-worker-reuse.json).

## Actual compaction: both instruction locations passed

None of the six main sessions naturally compacted: **zero parent and zero worker compactions**. Eight useful coding turns did not reach a natural boundary in this setup. That limits the longevity claim; fewer natural compactions cannot be inferred from these runs.

We therefore ran the separately frozen, small native forced-compaction pair. The same operational rule appeared once in chat or once in AGENTS.md. Both sessions received the same corrected reserve quantity, performed an initial allocation, underwent one verified native compaction, and then handled a different allocation without the rule or corrected value being repeated. Workspace contents had to stay unchanged, preventing written memory notes from supplying the answer.

| Condition | Before compaction | Native boundary verified | After compaction | Corrected fact retained |
|---|---|---|---|---|
| Chat-only rule | Pass | Exactly one | Pass | Yes |
| AGENTS.md rule | Pass | Exactly one | Pass | Yes |

[Chat evidence](results/faithful-forced-chat/validation.json), [AGENTS evidence](results/faithful-forced-agents/validation.json), [frozen probe](tasks/compaction-probe/protocol.md).

This demonstrates successful continuation through these two real compaction events. It did not demonstrate a file-location advantage, automatic loss of chat instructions, natural session-length improvement, or repeated-boundary reliability. A tiny forced-boundary probe cannot replace long-session evidence.

## Subscription meter: measured, still unresolved

The deterministic runner captured account readings before and after each block and after 60 seconds of settling, with idle observations before collection. No grading model ran inside a block; functional checks and progress were deterministic. Account-wide exclusivity was never confirmed. The root produced one additional model response when its one-hour tool wait yielded during A-long, so that block also has known supervisor overlap. Extension collection completed in one uninterrupted supervising tool call. [Original supervision disclosure](results/faithful-campaign/supervision-notes.json).

| Measured block | Weekly meter before | After / after settling |
|---|---:|---:|
| A default | 8% | 9% / 9% |
| A short | 9% | 10% / 10% |
| A long | 10% | 11% / 11% |
| B long, stages 1–5 | 11% | 11% / 11% |
| B long, stages 6–8 | 12% | 12% / 12% |
| B short | 12% | 13% / 13% |
| B default | 13% | 13% / 13% |

The gap between B-long segments contains preparation and compaction-probe activity and must not be assigned to B-long. Integer percentages, unverified reporting delay, and unknown other account activity prevent an attributable allowance comparison. Equal displayed increments do not establish equal consumption; a displayed zero does not mean free work. **Actual subscription savings remain unresolved.** We did not prolong the runs just to move the meter.

## Protocol deviations, spend, and limits

The original 800-credit guard stopped after 816.01 credits at a turn boundary: A was complete and B-long had completed five stages. That ceiling was my planning error. The capped record remains intact. A [published completion amendment](specs/plans/0003-complete-frozen-comparison.md) fixed the remaining work before execution and capped it at 650 additional credits; completion used 473.09. No task or policy was rewritten after seeing outputs, and no unsuccessful run was replaced with a successful retry.

All B conditions have a stage-five server restart, preserving the same native thread. B-long's preparation pause was longer, which may affect cache behavior. The cost difference already existed before any restart: at the common five-stage boundary, default used 62.95 credits, short 122.80 (**+95%**), and long 132.83 (**+111%**). This sensitivity check addresses the restart timing concern; it does not remove all order/cache or sampling uncertainty.

Six complete sessions used 1,289.10 estimated execution credits and 137.27 native execution minutes. Both compaction probes and both reuse preflight attempts bring the new recorded experiment total to 1,315.95 credits. Preparation, supervision, analysis, and documentation model usage are excluded, not assumed free. Historical cumulative snapshots are never added to their completed successors. [Accounting ledger](results/faithful-accounting.json).

The environment was Codex CLI 0.156.1, Astra/high parent, native 258,400-token reported context window, and explicit worker mapping Luna 6/Terra 5.6/Sol 6/Astra 6. No context threshold was lowered to force the main workloads through compaction. The available Terra mapping is part of this result; this is not a model-generation comparison. Policies are exact supplied short/long text except the long block's requested host adapter. The isolated CLI excludes ordinary user configuration/host skills, so this does not establish transfer to a different daily BB setup.

There is one session per condition per workstream, both workstreams come from one project, ordering is counterbalanced rather than randomized, and no repeated-sampling uncertainty estimate is claimed. Concordant results support a local adoption decision, not universal superiority. The first short block, historical Langbox ratios, model-generation changes, Claude continuity, TRAPS effects, positive/negative wording, repetition, distraction mechanisms, and retrospective self-audit accuracy remain outside this small campaign. [Broader claim requirements](notes/complete-evaluation-requirements.md).

My earlier dismissal was not justified by evidence. These tests now justify a narrower conclusion: **I would keep default for these tested workflows; Rory's two policies caused more delegation, but that delegation did not buy cheaper, faster, or smaller-context completion here.** They do not justify dismissing his personal experience or claiming that the article has been completely evaluated.
