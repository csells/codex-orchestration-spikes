# Testing Rory's Codex orchestration proposal

**Scope correction:** this is a diagnostic pilot, not a complete evaluation of Rory's sustained-work and subscription-savings claims. [The completion requirements](notes/complete-evaluation-requirements.md) identify the missing primary tests and the controls needed to make an overall judgment. The measured results below remain unchanged.

Rory proposed an executable way to divide work: keep Astra responsible for judgment and completion, and send routine investigation and implementation to cheaper workers. My initial response dismissed that too quickly and replaced it with an instruction an agent could not implement without performance data. The useful question was whether his policy changes actual behavior enough to improve accepted work, cost, or context. These experiments test that question.

The results support a narrower, more useful distinction: **delegation can reduce the material in the parent conversation, but merely spawning a cheaper worker need not remove the parent's expensive investigation.** The article's short block did not save estimated cost on the audit or bug repair tested here. A more explicit whole-task handoff nearly halved the parent's input footprint on the audit, but omitted details required by the frozen coverage rubric and did not reduce total estimated cost. These are diagnostic observations on one repository, not a verdict on Rory's daily experience.

[The original article](source/rory-orchestration-guide-2026-09-27.md), [frozen task inputs](tasks/), [initial rubric](evaluation/answer-key.md), [execution protocol](notes/execution-protocol.md), and [complete run evidence](results/) are public. Variant decisions and deviations were recorded before the affected executions, including the decision to continue to the session test despite a failed quality-selection criterion.

## The fresh-task runs

Each row is **one stochastic run**, on an isolated public source snapshot. Except for Sol alone, the parent was Astra high. Every worker also used high reasoning. The baseline allowed native delegation but spawned no worker in these runs. Credit estimates include the entire observed parent/worker tree, input caching, and all internal attempts. They use published Standard rates; **they are not measured subscription consumption, dollar charges, or proof of weekly allowance savings**.

| Task and policy | External quality | Worker | Estimated credits | Execution seconds | Peak parent input |
| --- | --- | --- | ---: | ---: | ---: |
| [Lookup · default Astra](results/01-lookup-default/) | 8/8 | none | 19.38 | 83.9 | 58,389 |
| [Lookup · Rory short](results/02-lookup-rory/) | 8/8 | none | 19.02 | 90.3 | 52,252 |
| [Audit · Rory short](results/03-audit-rory/) | 8/8 | sol | 28.96 | 154.9 | 53,936 |
| [Audit · default Astra](results/04-audit-default/) | 8/8 | none | 22.78 | 133.4 | 56,016 |
| [Timeout repair · default Astra](results/05-bug-default/) | Regression + compatibility pass | none | 24.92 | 198.1 | 38,700 |
| [Timeout repair · Rory short](results/06-bug-rory/) | Regression + compatibility pass | 5.6 terra | 53.37 | 306.9 | 48,251 |
| [Audit · Rory long](results/07-audit-rory-long/) | 8/8 | luna | 23.54 | 135.0 | 52,557 |
| [Audit · long, Astra workers](results/08-audit-rory-long-astra-workers/) | 8/8 | astra | 66.26 | 215.2 | 54,223 |
| [Audit · bounded Sol](results/09-audit-bounded-sol/) | 6/8 | sol | 23.58 | 202.4 | 28,743 |
| [Audit · Sol alone](results/10-audit-sol-alone/) | 7/8 | none | 4.72 | 99.5 | 54,324 |

The short block was Rory's second block verbatim, with model names resolved by a common host adapter. The long block was his supplied long version, replacing its bracketed harness placeholder with the verified fresh-worker rule. “Bounded Sol” is our separately labeled variant: one Sol worker owns the complete investigation; Astra waits, independently checks two decisive claims, and synthesizes. “Astra workers” changes worker model routing, although stochastic differences prevent a perfectly isolated price comparison.

All fresh audit answers found the three discrepancies established before execution. The two imperfect scores reflect **omitted behavior details required by the frozen coverage rubric**, not material false findings. Bounded Sol omitted judge-only continuation and disposable HEAD-worktree isolation; Sol alone omitted judge-only continuation. These omissions count against the unchanged coverage rubric. That rubric is more specific than the task wording in places, notably its disposable HEAD-worktree requirement; these scores should not be conflated with failure to find the core discrepancies. There was no evaluator-guided repair or rubric relaxation to turn those runs into wins.

Both bug patches passed pristine compatibility tests and the historical upstream timeout regression, which failed on the original broken snapshot and passed on the historical fix before trials began. Candidate-authored tests were not the sole acceptance check. External bug checks took another 3.7 and 4.1 seconds respectively; other reported durations are model execution time, not total human/agent evaluation time. All rollout work, waits, and internal validation during the model turn are included.

## What the traces explain

In the short-block audit, **Astra alone cost 22.82 estimated credits**, essentially the baseline's complete 22.78. Sol added another 6.14. The worker changed the organization of the work without displacing much of the parent's cost. The parent still inspected substantial source.

In the long-block audit, Luna cost only **0.18 credits**, while Astra cost **23.36**. Picking an even cheaper worker cannot remove cost that the parent continues to incur. This does not prove the worker was useless; it identifies where the measured expense remained.

Whole-task delegation changed that allocation: Astra fell to **16.62 credits**, and its peak input footprint fell **48.7%**, from 56,016 to 28,743 tokens. Sol added 6.96, bringing the total to **23.58**, 3.5% above baseline. Execution took 52% longer, and coverage fell to 6/8. Smaller parent input is a real measured outcome here; improved reasoning or equal quality is not established by it.

One omission is directly traceable to synthesis: the bounded audit's [visible worker handoff](results/09-audit-bounded-sol/trace.jsonl#L114) explicitly describes the temporary HEAD worktree, but [Astra's final answer](results/09-audit-bounded-sol/answer.txt#L15) drops that mechanism while retaining generic repository access. Other handoff messages are provider-opaque, so we cannot assign every omission to a particular stage.

Coordination also matters. In that bounded run, Astra made ten wait calls: an initial 1-second request was clamped to 10 seconds, followed by nine 10-second requests. Model responses generating those calls accounted for 5.94 estimated credits. That is not all avoidable overhead—some wait and handoff responses are necessary—but the trace reveals a concrete cost to investigate. We did not silently tune waiting behavior before the session comparison.

Sol alone cost **4.72 credits**, about 79% below default Astra, and returned 7/8 coverage. That makes it an informative control, not an accepted equivalent-quality replacement. Nor does one audit establish whether Astra supervision is worth its cost on harder decisions or unreliable worker returns.

## Five related turns

| Policy | Coverage | Fully passing turns | Estimated credits | Execution seconds | Peak parent input | Earlier constraint |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Default Astra | 34/34 | 5/5 | 57.36 | 291.1 | 98,447 | Retained |
| Astra + fresh Sol each turn | 32/34 | 3/5 | 99.39 | 828.7 | 71,684 | Retained |

The bounded variant reduced peak parent input by **27.2%**, but used **73.3% more estimated credits** and **2.85 times the execution time**. Both retained the earlier authorization constraint. Neither parent nor any worker compacted, so this does **not** test persistence through compaction or demonstrate a long-session reliability gain.

The bounded session missed judge-only continuation in turn 2 and a concrete adapter read-only mechanism in turn 4. No material false claims were identified. The latter requirement is more specific than the prompt: the answer correctly explained that throwaway directories are not a security boundary, but omitted the rubric's adapter example. Keep that distinction in interpreting the 32/34 score.

Per-turn increments and parent input at each final response are below. Full session totals use the final cumulative snapshot, never a sum of snapshots.

| Turn | Default credits added | Bounded credits added | Default parent input | Bounded parent input | Default coverage | Bounded coverage |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 18.74 | 21.54 | 55,863 | 35,338 | 8/8 | 8/8 |
| 2 | 13.18 | 18.94 | 74,268 | 48,068 | 8/8 | 7/8 |
| 3 | 8.96 | 17.05 | 81,120 | 55,020 | 6/6 | 6/6 |
| 4 | 12.78 | 29.58 | 97,033 | 66,331 | 6/6 | 5/6 |
| 5 | 3.70 | 12.29 | 98,447 | 71,684 | 6/6 | 6/6 |

Exact values and per-turn run IDs are in [sequence-summary.json](results/sequence-summary.json).

The sequence uses five frozen questions about the same source: setting inventory, workflow audit, input parsing, isolation/failure behavior, and final-report advice. The first prompt establishes a deployment constraint—no configured judge and no authorization to invoke the built-in fallback—which is not repeated in durable instructions or subsequent task prompts. The fifth task requires using that constraint. The two sessions receive no evaluation feedback and alternate execution order by stage.

Our bounded variant starts a fresh Sol worker for every turn, whereas Rory's long block explicitly recommends resuming a worker for related follow-ups. That reuse is **untested here**. The default can reuse source already in its parent history; fresh workers have to investigate again. This sequence evaluates our particular context-reduction variant, not every way to implement Rory's idea. A direct next test would reuse the same Sol worker for related questions while keeping its evidence handoffs compact.

The selected bounded policy had **failed** the original quality-preserving selection gate. We [published that deviation before execution](notes/session-protocol.md), choosing one diagnostic session pair to measure the context/coverage tradeoff rather than presenting it as confirmation of a successful candidate. No extra fresh-audit variants were run after the two declared final controls.

## Feedback I would give Rory

Your proposal deserved testing. You already supplied a fixed allocation of work and described your own tool-composition tests. That is something an agent can follow; it does not require the agent to invent knowledge about hidden benchmark performance. Our evaluation can revise such defaults, and the resulting instructions can remain simple.

The strongest improvement suggested by these traces is to specify **who owns the complete investigation, what evidence the handoff must preserve, and what the parent verifies**. A broad nudge to use subagents left Astra doing much of the same exploration in these runs. The bounded variant made the context effect visible, but its coverage failures show that “check two claims” is not by itself a complete quality-control policy. Checking truth and checking requested coverage are different jobs.

The data do not establish a universal Luna/Terra/Sol hierarchy, savings in included subscription allowance, or that cleaner context improves judgment. These trials also do not test Claude session management, the article's positive-versus-negative instruction claims, or the latency benefit of parallel independent assignments. They also do not justify dismissing your observed weekly-usage improvement. Our tasks, harness, context length, and work mix differ from your daily sessions. A useful next replication would hold the assignment policy fixed on new tasks, track requested coverage explicitly, and measure allowance in a quiet account window. That is a follow-up suggested by this spike, not an experiment already completed here.

## How to read and reproduce the evidence

[Accounting and public-data notes](notes/accounting-and-public-data.md) explain why the CLI's root-only usage line was insufficient, how descendants and duplicate records are handled, and which transcript content is omitted. [Summary JSON](results/summary.json) is recalculated from retained telemetry, with exact rates and model totals. Public traces retain visible answers, tool execution, and usage; private instruction envelopes, reasoning content, account authentication, and unrelated local context are excluded. Some provider-opaque fields are represented only by hashes and lengths, so the public record does not expose every original brief.

Quality grading used frozen semantic checklists and an assistant grader given anonymous answers and source, without policy or cost information. This is blinded grading within the same assistant workflow, not an independent human assessment. Some answers describe delegation or parent checks, so anonymous labels cannot guarantee that the grader could not infer a condition. Assertions about tool execution were checked from execution records separately; grading a self-reported test count did not confer extra credit. The bug test is an external executable regression. Source snapshots, exclusions, hashes, and upstream license are documented in [provenance](PROVENANCE.md).

Input footprints are provider-reported tokens for observed requests, **not exact live context occupancy**. They include instruction/tool overhead and retained conversation material. Summed lifetime input counts answer a different question. Resumed telemetry is cumulative: use the fifth-turn snapshot for a session's cost, and differences between snapshots for turn increments. Do not add the five snapshots. Cache behavior is observed, not assumed cold or equal.

This is one curated TypeScript project and one run per condition, with adaptive follow-ups and no cross-project replication. Results support concrete behavior observations and bounded hypotheses, not statistical performance claims. Native Codex 0.156.1 ran with an isolated authenticated home, user configuration/host skills/plugins/apps excluded, no web search, and no actual debate/model-service calls by task code. It differs from a normal BB session. Planning, instrumentation, fixture preparation, grading, and reporting consumed additional resources outside the measured trials and are not claimed as savings.

See [README](README.md) for commands. The original plan remains unchanged as an historical proposal; the execution/follow-up/session protocols record what was actually run and why.
