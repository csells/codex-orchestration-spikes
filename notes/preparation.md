# Preparation record — 2026-09-27

These observations preceded model trials and are not experimental results.

- Local Codex version: 0.156.1.
- Local catalog includes GPT-6 Astra, Sol, Luna, and GPT-5.6 Terra. Successful execution and actual selected models still need to be verified.
- The BB collaboration interface says full-history workers inherit the parent model. Native CLI behavior will be checked separately; behavior in one harness is not assumed to establish another's behavior.
- BB exposes recorded parent context occupancy. Cumulative input-token counts are not the same measurement.
- Standard credit rates published at [OpenAI's pricing page](https://learn.chatgpt.com/docs/pricing), checked 2026-09-27, have Astra:Sol:Luna ratios of 100:20:1 for matching token categories. Published credits do not establish consumption of included subscription allowance.
- [Official subagent documentation](https://learn.chatgpt.com/docs/agent-configuration/subagents) describes context separation and configurable worker models.
- [Agents API accounting guidance](https://developers.openai.com/api/docs/guides/agents-api/observability) identifies the categories needed for full accounting. Local CLI telemetry must be inspected independently.

No benchmark results existed when the repository was created. One independent agent helped review the experiment design; that planning activity is not counted as a comparative trial.

The planned tests will use public source snapshots and checks fixed before the tested models return their answers. The investigation's own planning, fixture construction, and reporting cost is separate from measured task execution and is not claimed as a saving.
