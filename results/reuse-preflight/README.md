# Native worker reuse preflight

Passed on Codex 0.156.1 using one persistent app-server process, an Astra/high
root, and a Luna/high worker created with `fork_turns=none`.

The first root user turn asked a worker to read a synthetic fact and return only
`READY`. The deterministic controller then deleted the fact file. In the second
root user turn, the root used `followup_task` on that same worker. The worker
returned `cerulean-lantern-7139` with no new tool call, and the root returned it.
The controller supplied neither the value nor the worker's conversation to the
second root turn. Both native child turns have the same thread ID; hashed IDs,
native activity events, and the single successful command are in `proof.json`.

Evidence in `trace.jsonl` (one-based rows): spawn at 4; follow-up at 15; successful
worker read at 29; worker's first final at 31; remembered value at 35. The root's
final answers are at 11 and 22. The two telemetry files are cumulative snapshots:
**use telemetry-2 for the total, not the sum of both files.** There are two native
threads, one spawn, one follow-up, no accounting warnings, and no compactions.

The driver did not override context limits or auto-compaction settings. Native
telemetry reported a 258,400-token model context window. This small capability
test does not establish performance, savings, or instruction persistence through
compaction.

`exec-probe.json` preserves the earlier infrastructure-failed CLI probe: its
worker was successfully followed up after `codex exec resume`, but an enclosing
sandbox prevented the original file read. Its first `READY` was insufficient
evidence of a successful read. The persistent probe ran outside that enclosing
sandbox; native Codex itself used workspace-write with approvals disabled.

Raw protocol envelopes and credentials remain private. Public traces omit known
instruction and reasoning envelopes and replace observed provider ciphertext
with hash/length markers. This is not a claim to detect arbitrary secrets.

To repeat, use `scripts/persistent_session.py` with a fresh private workspace and
isolated authenticated Codex home. Create `fact.txt` from `fact-fixture.txt`, start
one `PersistentSession`, call `start_thread()`, and call `run_turn()` with prompt 1.
Delete `fact.txt` in the deterministic controller, then call `run_turn()` with
prompt 2 on the same instance. Check actual native thread IDs, successful read,
and absence of second-turn commands; checking the final answer alone is not
enough. Finally close the transport. Launch outside an enclosing shell sandbox
when native Codex needs to establish its own sandbox.

The infrastructure-failed attempt also has its [full-tree usage](exec-probe-telemetry.json) and [sanitized trace](exec-probe-trace.jsonl) retained. Its cost is included in the follow-up accounting ledger.
