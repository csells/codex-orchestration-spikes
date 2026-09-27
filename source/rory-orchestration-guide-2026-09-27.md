# Rory's totally made up guide to subagent orchestration with Codex + Astra

## Ahem

Codex and Perplexity both told me that Astra doesn't spawn subagents the way lesser models do, and I could see that in the way Astra consumed usage.

I assume OpenAI has a good reason for this choice. All the same, it hurts to watch Astra set tokens on fire doing gruntwork when I *could* have Luna/Terra/Sol handle the small stuff. Ergo, experimentation.

OpenAI's Astra workflow with its fancy session management might make this fretting over subagents moot. They haven't solved the context window problem, but the quality of session management is making for a great workaround.

For now, I trust Codex + Astra to run endless sessions. For now, I absolutely *don't* trust Claude Code. I manage Code's session continuity myself and never use compaction.

Codex's weak point is the "Astra doesn't use enough subagents" thing.

My goal with this work is to mitigate *that*. It bothers me OCD-wise to know the most powerful LLM available to the common person blows compute on reading markdown and walking folder hierarchies. The cherry on top is all the tool calls and mistakes and file reads/edits/writes and git history checks that linger and rot in context. It costs attention, meaning distraction, and it costs in reasoning tokens because the model has to decide what to consider relevant (`I'm solving math. The whole thing. Do I really need the Wikipedia entry for "hot dogs" in here? It's distracting! DISTRACTING!`)

**The Luna Question:** GPT-5.6 Luna was fine for the simplest tasks. When I tested its ability to compose tool calls with Langbox (MCP *and* CLI), it had the highest token churn because _Luna fucks up_, so Luna has to try and try again. I haven't run the tests against GPT-6 Luna yet, so I'm keeping it on the roster for now. I'm going to run my Langbox composition tests against GPT-6 Luna/Terra/Sol to see if **GPT-5.6 -> GPT-6** is really a generational difference for non-Astra models. If GPT-6 Luna still has to fail repeatedly to succeed, I'll fire it.

**Those tests against GPT-5.6 models left me with choices to make:**
- Luna regularly burned 10k tokens to complete a task that took Sol 1k. But Luna's fast and cheap, so you don't *feel* the subagent banging its head against the wall. You only see it in token use, transcripts, and audits. If it can get the job done cheaper, then does the head banging matter? I think it does. Correcting mistakes keeps mistakes in context, and LLMs sure do like to pattern match...
- Terra burned about half as many tokens as Luna to complete the same tasks. It got a lot of compositions right the first attempt, but occasionally hit the "try again!" wall. Terra's more expensive per token, but it used far fewer tokens overall in each test task than Luna.
- Sol burned about a third the tokens Luna did for the same tasks. It got compositions right the first time, most of the time. Fewer mistakes means fewer retries and fewer tokens. If it's few enough, it can translate to *cheaper*.

**How do you decide which to use, then?** I think, except for basic file parsing, Luna can be a liability in terms of both accuracy and cost. Where Luna can get it right the first time, Luna's a great choice. But the savings disappear as task complexity increases. At some threshold, Terra (which is obvously more expensive) becomes *cheaper* than Luna thanks to token efficiency. Here's my most basic take on model appropriate work:
- Luna:     `Get a summary of the README`
- Terra:    `Implement section 5 of the plan`
- Sol:      `Audit this entire codebase`
- Astra:    `Make an ASCII version of Doom without peeking at the code for the ASCII version of Doom first`

**We also have to consider how we use Claude Code vs. Codex.** My tests tell me context management is more important for Claude. We tend to run longer sessions in Claude Code, and we tend to use 1m token window models rather than their 200k counterparts. The larger the context window, the more damage context bloat does. An error 700k tokens in the past might look like a solution to Opus/Fable 1m because they're well outside the LLM Smart Zone. `Now I'll delete all these bulky files in /bin...`

Working with Codex + Astra and the 250k token context window makes mistakes more ephemeral. Good compaction would keep what matters, what direction we're going, what approaches worked, etc. Leave behind the noise left over from sidequests and whoopsies (I keep a `TRAPS.md` for Codex/Code sessions to store anything that takes a model by surprise, and I have that file ingested every time I either continue in a fresh session or use autocompact + clear, and then continue - it helps the robots avoid making the same mistake twice (or, more importantly, 500 times)).

**Let us begin by describing a simple interactive Claude Code session.** We'll look at Codex after.

## The Claude Code Way
1. Prompt to encourage use of subagents (a simple nudge is all it takes with Fable). It shouldn't be necessary, but ever since Opus 4.7, Anthropic has fiddled with subagent spawning. Some releases discourage agent spawning while others encourage it. So we nudge to encourage. **The nudge does best when it lives in your CLAUDE.md.** Especially if you like to work outside the Smart Zone. When you're 500k tokens in, you can't rely on a prompt from 400k tokens ago to still work.
2. Do the work and enjoy life as the context window fills *slowly*. The subagents are keeping the window clean. Yay!
3. Somewhere around 250k-500k (or 1m if you like to do that sort of thing):
    1. Prep for handoff (DIY - unlike Codex, Claude Code doesn't do so well on its own when handing off).
    2. Clear session context.
    3. Go back to work.

I find Anthropic's compaction janky. I haven't experimented enough with customizing it. For now, and for me, I think the `work -> prep for handoff -> reset` treadmill works best. No compaction. Just diligence and a consistent DIY handoff system.

**Then we get to Codex...**

## The Codex Way
I've read a lot of complaints about Codex "forgetting" instructions a few turns in. I don't think Codex "forgets" in-chat prompts: I think it fully ditches them as part of the treadmill. Hard rules belong in AGENTS.md. `Use subagents good!` isn't gonna survive compaction.

**I think Codex and Astra are meant to chew through sessions (with "forgetting" being a benefit):**
- The little 250k token window keeps us in the Smart Zone (there's supposedly a flag that can force Codex to use an ~800k token window for Astra, but it's also reported that Astra chokes long before 800k).
- That little window means having to roll over again and again. Every time, session context is reset, so we cut the baggage of context-rotting mistakes and tool calls and file contents etc.
- Most of the work is spent on reasoning and tool calls. Because all the work is done in the main session, the billion tiny file reads/writes, folder searches, full document ingestion, and extraneous content bloats and rots context. It also distracts because Astra has to make decisions about coding while also holding nineteen READMEs picked up here and there. All irrelevant. All costing attention and requiring extra reasoning.
- Compaction, even when it's good, is still compaction. **If you want an instruction to survive a long session, you have to ensure it survives the treadmill.** Again, that means AGENTS.md for any customization you want to last more than a few turns.

**Rather than manage session context the way we would with Claude Code, we trust the treadmill.**

**The Codex + Astra Treadmill:**
1. Session start.
2. Do some work.
3. Before you know it, that little 250k token window is nearly filled.
4. Codex prepares for a handoff and then autocompacts. Low fidelity history is kept; handoff and continuation docs are kepts; specific instructions from chat are lost.
5. Codex clears session context.
6. GOTO 1 (until session is done)

So, if you drop the orchestration/subagent instructions as a session chat prompt, you risk losing it on step #5 (autocompaction). Another reminder we can't rely on Codex to "remember" instructions across long sessions.

The treadmill hauls. You might only get two or three turns before context is full.

I treat in-session (chat) instructions as ephemeral. I trust Codex with long session management. Anything more needs, at the least, some decent AGENT.md instructions.

**And that brings us to the Codex + Astra Treadmill blocks.** Three versions to play with.

### 1: Compact - I used this as the initial "let's see what happens" instruction:
```
<subagents>
Astra runs the main session: it plans, delegates, does the hard thinking, and steps in when a subagent stalls. It does quick reads and tool calls itself. Everything else goes to a subagent so main context stays clear.

- Luna: file operations (grep, glob, cat, shell) and other simple work.
- Terra: routine coding and technical analysis, such as auditing docs against the codebase.
- Sol: deeper coding, heavier knowledge work, reviews.
</subagents>
```

I got more out of each treadmill loop. I also probably burned more tokens than I would've if I'd left Astra to do it all, but those extra tokens I burned were *cheap* tokens (Luna/Terra/Sol). Offloading the gruntwork also does the "keep main session context clean" job, and that's *always* good.

Astra delegates. Astra reviews. Astra course corrects when necessary. And Astra does so unburdened by all that distracting file manipulation and web fetching and gitting cruft.

### 2: Second and slightly refined short version (uses light repetition to reinforce):
```
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
```

### Long version (rewritten with Fable 5.1's help):
```
## Subagents

The main agent frames the task, coordinates, does the hard reasoning, and writes the final answer. Delegate the evidence-gathering so the main conversation stays lean.

### Routing

- Luna: bounded exploration, searches, inventories, extraction, mechanical edits, focused web research.
- Terra: routine implementation, debugging, refactoring, tests.
- Sol: hard research, synthesis, review, verification.
- Astra: architecture, planning, orchestration, judgment calls.

Move up a tier when a cheaper one failed or the stakes are high. Pick the newest model the environment exposes for that family and name it explicitly. If you had to substitute, say so in the answer. [If inheriting context forces the parent's model, state that here as a fact and what to do about it.]

### When to delegate

Delegate work that takes several tool calls and can be stated as a bounded assignment. Do trivial lookups yourself. Keep exploration in the main agent when it feeds an immediate design decision. While an agent works, do something else or wait. When it returns, build on its handoff and spot-check the claims that matter.

### The brief

Give each agent the deliverable and its completion criteria, the paths and constraints that apply, the response format, and instructions to flag uncertainty and stop at the edge of its scope. Start from a fresh context and write the brief from scratch.

Batch related questions into one assignment. Resume an agent for follow-ups on what it already saw. Use a fresh agent for unrelated work and for any review, so the reviewer forms its own view. Give parallel agents disjoint files.

### Handoffs

Lead with the answer, then the evidence. For web research, each material claim carries the source title, publisher, URL, a supporting excerpt, the date when it matters, and whether the page was opened or only its snippet seen. Prefer primary sources and mark inference as inference. Keep stable URLs. For repository work, cite path and line, list what was inspected or changed, what validation ran, and what is unresolved. Write large findings to a file in the workspace and return the path.

The main agent carries citations and qualifications into the final answer and owns its accuracy.
```

## Which is best?
I've been testing with the second version (the short block with *reinforcement through repetition*). It helps, though I'm finding the weaknesses that make the final longer version more compelling.

The downside of the longer version is that it might be too prescriptive. I *trust* Fable and Astra to know better than I do how they should work. Where I would've given Claude 4.x the precise steps to take, I give Fable/Astra the broad strokes and trust them to make the right decisions.

Bad instructions lead to reasoning churn. I had to rewrite Fable's edit of the long version to remove distractions, overreach, and to flip negative instructions to positive. You don't have to reason through positive instructions the way you do negative. Astra and Fable both tell me it doesn't really matter. But it matters:
- Positive instructions with qualifications: `My instructions tell me to use concise language, so I'll keep paragraphs short, use lists instead prose when I can [etc.]`
- Negative instructions require disambiguation: `My instructions tell me not to use too many words. What does "too many words" mean? Does the user want me to omit specific tool calls? Do they want me to use lists instead of prose? Do I have access to a style tool or skill? No. I don't. I'll just keep thinking about it all day. I'll write a first draft of the output and then iterate until it's as compact as it can be while retaining the full meaning and information of the first draft. When I present it, I'll add a TODO item to ask the user if the output is too concise at the end of this turn. I'll start with draft #1 now. I don't have access to the tokenizer, so I'll treat words as roughly 2-3 tokens each to be on the safe side. I don't have a way to count the number of words I'm using, so I'll write a throwaway Python script to do the counting. Now I'll create a PLAN that captures all these decisions, and [etc.]`

Grossly imperfect as it is, that short middle block took me from "Where the fuck did all my usage go?" to "Oh. Hey. I can use Astra more than once a week!"

**Running meaningful model comparison tests is expensive, so rely on three indicators (from least useful to most useful):**
1. The shock of still having gas in the tank before my weekly reset. The results are in the usage bar.
2. Around ~200k, I ask Astra if it's been following the orchestration and subagent instructions in my AGENT.md. Then I ask for a report on what went right (when a spawned agent+model combo did its job) and what went wrong (greatest offender being stuff like `I parsed every README.md in the project, so they've been in context this whole time`). **There will inevitably be** `I should have dispatched a Luna subagent for that task, but I handled it in the main session` reports, but also `I used Terra to [do some task] and Sol for [some harder task]. I checked their work and continued. I recommend keeping those model/task assignments.`
3. My most expensive Astra use *by far* has been test suites I created to compare Luna/Terra/Sol performance on tool use - to be able to categorize what each model could/should handle as a subagent. Astra had to write, execute, and participate in the tests. To get meaningful results, I had to:
    1. Create a set of tasks, each designed to present a different problem.
    2. Run the tests against Astra for a baseline of what perfection looks like in September 2026.
    3. For each task: Run each test multiple times to account for that wacky AI stochasticity (same input -> different output).

In the case of #3 (expensive testing), Astra *has* to be the orchestrator, and it has to be put to the test, and it had to generate the tests in the first place.

The way I have to run the tests, then, is similar to the way a typical (insufficient subagent spawning) Codex session goes. Astra's reading all the files and walking folder trees and loading and executing tests... It takes me right back to the "I used a week's worth in three hours?" days.

It brings us full circle. Expensive Astra Codex to reasonable Astra Codex to expensive Astra Codex again.

Okay. I'll stop talking now.