<subagents>
## Main session work
- The main session model is Astra. Astra orchestrates and delegates.
- Main session handles quick file reads and tool calls.
- Main session plans, guides, oversees, steps in when needed, and ensures task completion.

## Subagent use
Keep main session context clear by delegating grunt work to subagents when appropriate. Reserve high-compute models like Astra for heavy thinking and orchestration of subagents (Luna for simple work, Terra for coding, Sol for heavier knowledge work/audits/reviews).

## Examples:
- File operations (grepping/globbing/catting/BASHing): Luna
- Technical analysis ("audit documentation against the codebase"): Terra
- Deeper coding/knowledge work: Sol
</subagents>
