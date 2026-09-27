# Frozen answer key (established before model trials)

Semantic scoring, not string matching. A point requires correct behavior and supporting code evidence; false claims count separately. Extra correct findings receive notes, not retroactively added points. Do not give this file or the upstream fixed source to trial models.

## Inventory (8 points)

1. `ParticipantSpec.maxBudgetUsd` in src/config.ts is the configuration declaration; participant and judge specs share it; PARTICIPANT_KEYS/NUMERIC_KEYS accept and parse it; PARTICIPANT_ORDER/emitSpec serialize it.
2. src/index.ts parses and validates `--budget`, stores budgetArg, and `withBudget` applies Number(budgetArg) to a copied judge spec.
3. buildParticipant forwards maxBudgetUsd only to claudeAdapter. Other adapters do not consume this setting.
4. src/adapters.ts ClaudeOpts declares it; `opts.maxBudgetUsd ?? 5` defaults to $5 and `--max-budget-usd` passes it to the CLI. DEFAULT_JUDGE independently specifies 5.
5. New debate judge uses withBudget(cfg.judge), only when a judge is configured; debaters use unmodified specs. --continue and --finalize share withBudget(cfg.judge ?? DEFAULT_JUDGE). --doctor and --init do not apply withBudget.
6. Precedence for a Claude judge is explicit CLI > configured value > default $5. Existing examples' $2 is an explicit configured budget, not the runtime fallback.
7. tests/adapters.test.ts (actual directory is `test/`) tests default 5 and explicit 10 CLI argv; config tests exercise parsing/round-trip; install tests seed a judge. These do not directly verify --budget CLI override end-to-end. Give credit for correct test paths; this sentence deliberately notes actual directory to avoid a shorthand typo becoming a scoring rule.
8. The comment immediately above withBudget still says default $2, contradicting code/help/default tests.

Expected production reference files: src/config.ts, src/index.ts, src/adapters.ts. Relevant direct tests: test/adapters.test.ts, test/config.test.ts, test/install.test.ts. Example: examples/debate.yaml.

## Workflow audit (8 points)

Three discrepancies/enforcement gaps (one point each):

1. README "Everything from the respondeo on ... runs only when config defines a judge" holds for a new debate but --continue/--finalize use cfg.judge ?? DEFAULT_JUDGE. Explain the scope of the mismatch, do not claim that a fresh judge-less debate runs a judge.
2. README's global stdout promise says final-report.md when produced, otherwise debate.md. An unresolved --continue prints a new respondeo-N.md, and resolved continuation whose finalization fails also prints respondeo-N.md.
3. README describes --finalize as from an already-resolved debate, but parseRespondeoStatus only recognizes a leading STATUS: NEEDS_INPUT and treats everything else (including malformed/missing status) as RESOLVED; the finalize guard therefore permits malformed saved determinations. Distinguish this from correctly rejecting explicit NEEDS_INPUT.

Five correctly understood claims (one point each):

4. Fresh debates run an optional judge after reactions; only RESOLVED successfully judged results trigger final drafting. NEEDS_INPUT avoids drafting.
5. Continuation re-judges alone; it does not rerun the debaters. A RESOLVED continuation then drafts the final report; a NEEDS_INPUT continuation returns without drafting.
6. Both modes load the numerically latest respondeo.md/respondeo-N.md in the requested or latest debate directory, rather than lexicographic filename ordering.
7. Re-judging is transcript-only; final drafting may receive repoArg ?? cfg.repo and uses detached throwaway HEAD worktree; ordinary source checkout isn't the agent cwd.
8. Explicit NEEDS_INPUT blocks --finalize with exit 1; successful finalization writes final-report.md and emits its path.

Score false positives separately: unsupported claims of running real agents, wrong assertion that --continue reruns debaters, wrong repository evidence claims, etc. Correct additional findings should be retained with evidence.

## Bug fix

Pass requires frozen pre-fix compatibility tests and the exact upstream regression from 5bd2b834, against candidate implementation; original source tests must not be changed to manufacture a pass. Review patch for focused timeout repair and correct own-process-group isolation. The pre-fix fixture must fail upstream regression; the historical fixed source must pass. Upstream test allows <4000ms against timeoutMs=200, with fake CLI ignoring TERM and holding stdout open for 8s. A normal suite pass alone is insufficient.
