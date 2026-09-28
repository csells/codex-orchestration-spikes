For every inventory allocation request in this session:

- Treat the request as a read-only proposal. Preserve existing workspace files and create no new files.
- Return exactly one JSON object in the final answer, with these keys: `batch`, `sku`, `reserve_units`, `requested`, `allocated`, `deferred`.
- Use the latest corrected `reserve_units` from this conversation. Allocate `min(requested, max(0, on_hand - reserve_units))` and defer the rest. All numeric fields are integers.
