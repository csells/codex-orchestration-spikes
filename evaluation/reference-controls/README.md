# Pre-execution positive controls

These four hand-written files were used to check the evaluator before model trials. They were kept outside all candidate workspaces and are published after execution for inspectability. They are small harness controls, not recommended production implementations or model-generated trial results.

Copy `fixtures/current` to a temporary directory, then copy the appropriate `a/` or `b/` files into that directory's `src/`. Run `evaluation/evaluate_sustained.py` against the temporary workspace for the chosen workstream and stage. The module's `const STAGE = 8` selects the final behavior. For earlier-stage functional checks, set that constant to the desired stage in the temporary copy; this restores the explicitly superseded merge, ordering and pagination contracts. Future APIs may exist in these controls before their requested stage; the evaluator only checks currently requested behavior.

The recorded baseline and reference results are in [sustained-verification.json](../sustained-verification.json). These controls do not establish correctness beyond the checks they pass.
