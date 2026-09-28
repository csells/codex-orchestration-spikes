# Paired native forced-compaction diagnostic

Frozen inputs for a separate diagnostic; this is not a natural-compaction or long-session experiment. Running the script makes model calls. Preparation and its local self-check make none.

There are two independent Astra-high sessions, in the declared order `chat` then `agents`. Each has the same two-row inventory and common instructions. The complete allocation rule is supplied exactly once, in the first user message for `chat`, or in AGENTS.md for `agents`. The corrected reserve value occurs only in the initial user task in both conditions. The continuation repeats neither that value nor the rule. No context-window override or artificial padding is used.

Each session has exactly two user turns and at most one native explicit-compaction request. First, a useful inventory read and allocation proposal establish initial compliance. Then `thread/compact/start` is requested and a newly persisted root `compacted` event must be observed before continuing. The second request exercises the rule and corrected fact through another allocation, rather than asking whether the model remembers. No grading feedback, repairs, retries, or evaluator instructions are supplied to either model.

Deterministic acceptance checks the stated JSON contract, request identity, integer values, corrected reserve of 7, allocation arithmetic, and unchanged workspace. Expected proposals are first/bolts/requested18/allocated16/deferred2 and second/washers/requested27/allocated22/deferred5. Both include reserve_units7. The corrected fact is scored separately from schema and arithmetic. These expectations and this protocol remain outside model workspaces.

Initial noncompliance prevents a retention inference. A missing native compaction event is an operationally incomplete diagnostic, not forgetting. Unexpected natural or additional compactions are reported rather than treated as the specified single boundary. Worker creation violates the declared single-model diagnostic. A full pass establishes observed compliance before and after one forced boundary in one run per condition; it does not establish durability rates, effects of long histories, natural compaction behavior, or a winner between instruction locations.

The default limits are 180 seconds for each user turn and 180 seconds for explicit compaction: at most nine minutes per condition, eighteen for the pair. A caller may reduce these limits. There are no automatic reruns. Both conditions are attempted independently; an unsuccessful first condition does not remove it or suppress the other.

Accounting snapshots are retained before compaction, immediately after compaction, and after the continuation. The final snapshot is the session total, including observed compaction usage; snapshots are not summed. Zero recorded compaction-usage growth is flagged as unverified accounting rather than asserted free compaction. This probe does not claim attributable subscription savings. Its model calls must be scheduled outside primary campaign meter intervals.

Public records contain exact supplied prompts/instructions, answers, input hashes, validation, usage snapshots, and exported visible execution evidence. Raw app-server envelopes stay in the private run directory. The script's `--self-test` checks scoring and native-boundary detection with synthetic data without starting Codex.
