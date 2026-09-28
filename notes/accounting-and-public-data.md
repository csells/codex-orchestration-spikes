# Accounting and public evidence

These measurements use native Codex CLI 0.156.1 rollouts. The [preflight](../results/preflight/) established that the completion usage in `codex exec --json` covered the root only: Astra used 75,071 input and 304 output tokens, while its Luna worker separately used 43,927 input and 167 output tokens. Counting only the CLI completion would have omitted the worker.

## Full-tree collection

[telemetry.py](../scripts/telemetry.py) discovers descendants through `session_meta.source.subagent.thread_spawn.parent_thread_id`. Finished workers remain in the tree. For each actual thread it reads `token_usage_record.usage`, excludes records belonging to a different thread, and deduplicates by response ID. Copied parent history in a fork does not become new worker usage. Compaction usage is included, whether stored separately or inside `compacted.latest_token_usage_record`; the same response is counted once.

Models and reasoning settings come from recorded `turn_context` fields. These are the provider's recorded session settings, not independent inspection of the backend serving a response. Requested worker models come from spawn tool arguments. Matching a spawn to a child uses parent identity, agent path, and the child's creation time within the tool call's time interval. This avoids attaching an earlier spawn to a later worker that reuses the same task name. Missing evidence or unresolved routing ambiguity produces a warning rather than an invented match. Routing uncertainty does not erase attributable per-thread token usage.

The collector can account only for persisted rollouts supplied to it. Successful spawn outputs without matching descendant records are flagged, but this does not establish that every conceivable provider-side operation is visible. Tests cover copied history, duplicate response records, compaction, descendants, missing evidence, and reused task names.

`cached_input_tokens` is a subset of input tokens; reasoning output is a subset of output tokens. Neither is added again to the respective total. Published Standard credit-equivalent estimates are:

```text
((input - cached_input) × input_rate
 + cached_input × cached_rate
 + output × output_rate) / 1,000,000
```

Rates and their source are recorded in [summary.json](../results/summary.json). This is a pricing-based comparison, not a measured subscription deduction or API invoice. Quota observations are account-wide, may be rounded or delayed, and can include overlapping investigation or unrelated work.

## Resumed sessions and context

The five-turn protocol resumes each condition's own root and workspace, using fresh workers when the policy requests them. The collector retains completed workers from earlier turns and deduplicates their responses. Each `telemetry.json` is a cumulative snapshot taken when that stage ends. Use the final snapshot for a session total, or subtract consecutive snapshots for stage usage. Never sum successive cumulative snapshots. By contrast, `elapsed_seconds` is the wall time of that individual runner invocation.

The resume command retains the original session model rather than passing a new `-m` override. Actual recorded model/effort evidence remains available. Resume argument parsing was checked against the installed CLI, and synthetic tests verify accumulation across resumed turns with completed workers and reused names.

Later turns append to the same underlying history. Therefore regenerating an earlier trace must use its original `run.json` `ended_at` cutoff. [export_trace.py](../scripts/export_trace.py) accepts an inclusive, timezone-aware `--until` and excludes later root events and future child sessions. It determines a fork file's own identity before filtering copied history. [refresh_records.py](../scripts/refresh_records.py) applies these cutoffs while preserving the original usage snapshots.

Context figures are observed per-response input-token footprints, including the reported peak and last request. They are not exact live context occupancy or a count of only repository evidence. Compactions are recorded separately. A sequence with no observed compaction cannot establish what happens across compaction.

## Public trace treatment

Raw rollouts remain private. The exporter omits system/developer/user instruction envelopes, world-state envelopes, reasoning records, and compaction replacement history. Public task prompts and experiment policies are published separately. Retained records include tool calls/results, handoffs, assistant commentary/final answers, model settings, per-response accounting, and allowlisted command/file-change execution events. Execution evidence can overlap tool output; it is not an additional token charge.

Some native delegation briefs and messages are stored as opaque encrypted content. The exporter does not decode them. Explicit `encrypted_content` fields and the observed `gAAAA…` ciphertext format become SHA-256 and character-count markers. Plaintext `item_completed` events of type `CommandExecution` and `FileChange` preserve recorded commands, output, exit status, and patches by thread. Neighboring reasoning and user-message events remain excluded. Exported usage carries a shortened response hash for deduplication, including compaction records.

Known private path prefixes are replaced in values and filename dictionary keys. Quota exports retain an allowlist of bucket/window observations, excluding account IDs and reset-credit details. These transformations are not a general guarantee that arbitrary task output is free of sensitive content. The trials use curated public fixtures, and published artifacts still require review. Opaque briefs cannot be inspected, retained outputs may be truncated at their source, and the ciphertext matcher covers the observed format rather than every possible encryption format.

## An observed coordination cost

In [09-audit-bounded-sol](../results/09-audit-bounded-sol/), the Astra root made 16 model responses, including 10 that generated `wait_agent` calls. The first requested 1,000 ms; the tool explicitly clamped it to its 10,000 ms minimum. The remaining nine requested 10,000 ms. Seven waits timed out. Three woke on mailbox activity after approximately 5.264, 5.818, and 2.376 seconds. Thus the observed ten-second polling interval was selected behavior, not evidence of a required ten-second maximum.

The ten wait-generating responses used 183,792 input tokens, of which 179,840 were cached, plus 368 output tokens. At Astra's recorded Standard rates (250/25/1,250 credits per million uncached-input/cached-input/output tokens), these responses represent **5.944 estimated credits**: 35.8% of the root's 16.61855 and 25.2% of the full tree's 23.57801. This measures model iterations associated with waiting, not a separate fee charged by the wait tool.

It does **not** establish that all 5.944 credits could be avoided: an orchestrator still needs some waiting and handoff processing, and this experiment did not run a longer-wait counterfactual. The measured policy was left unchanged for the sequence. Smaller root input footprints and lower coordination cost are distinct outcomes.

## Reproduction

From the repository root, these checks use synthetic fixtures and published data without model calls:

```sh
python3 -m unittest discover -s scripts -p 'test_*.py' -v
python3 scripts/summarize.py
```

With retained private rollouts, set the following task-specific variables to the desired run's root ID, private Codex directory, workspace, and `ended_at` value. Exporting does not invoke a model:

```sh
python3 scripts/export_trace.py "$TRIAL_ROOT_ID" "$TRIAL_CODEX_HOME" \
  --workspace "$TRIAL_WORKSPACE" --until "$TRIAL_ENDED_AT" > trace.jsonl
```

To refresh public traces using their stored cutoffs, choose a prefix for runs whose original private rollouts you possess (omit the filter only when you possess them all):

```sh
python3 scripts/refresh_records.py --prefix "$TRIAL_RUN_PREFIX" \
  --codex-home "$TRIAL_CODEX_HOME" --private-root "$TRIAL_PRIVATE_ROOT"
```

The raw-rollout collector can also be run directly, but it reads the complete history currently present. Do not overwrite an earlier cumulative snapshot after that session has advanced:

```sh
python3 scripts/telemetry.py collect "$TRIAL_ROOT_ID" "$TRIAL_CODEX_HOME/sessions"
```

## Recorded CLI warning

The public CLI event streams contain an `item.completed` item of type `error` warning that `skip_host_skill_discovery` is an under-development feature. This is the same startup warning in each observed invocation; it is not a failed model turn. It is preserved rather than suppressed. The actual exit code, timeout flag, and turn completion events are recorded separately. The experimental feature was used to exclude unrelated host skills consistently in both conditions.

## Final routing correction

A final audit found one metadata timestamp lag: a worker was created during its spawn call, but the outer log-write timestamp appeared 7 ms after the call returned. The collector now prefers the actual creation timestamp in the metadata payload. This removed a false missing-child warning and corrected the fourth worker's label in stages 4/5; all usage, cost, context, and compaction fields were unchanged. [The correction record](../verification/routing-audit.json) preserves the original warning, timestamp evidence, before/after hashes, and exact changed fields. The delayed-write case has a regression test; all 23 accounting/export tests pass.

Captured answer/instruction files retain their original whitespace after path/opaque-content sanitization. Narrow `.gitattributes` exemptions allow trailing spaces in captured answers and final blank lines in captured instructions; authored code and documentation retain normal whitespace checks. This preserves the recorded instructions and their hashes.
