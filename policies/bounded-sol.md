# Bounded whole-task delegation variant

For this experiment, the parent coordinates and verifies. Delegate the complete requested investigation to one fresh gpt-6-sol worker at high reasoning, supplying the user's task, workspace path, and applicable constraints. The worker should inspect the relevant source and run useful local checks, then return its answer with evidence paths/lines, validation results, and uncertainties. The worker does not spawn further workers.

Wait for the handoff. Then independently check two decisive claims against the cited source or local verification. If a check reveals a discrepancy, investigate and repair it; otherwise synthesize the final answer from the checked handoff. The parent owns the final answer's accuracy. Record the two checks in the final answer.
