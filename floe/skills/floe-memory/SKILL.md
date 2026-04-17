---
name: floe-memory
description: >
  Use first on any substantial task. Retrieve relevant project memory, validate
  it against current artifacts, repair stale or superseded memory, then save
  only durable truth. Supports recall, context building, updating existing
  memories, registering documents, and linking related records for continuity
  across agent sessions.
license: MIT
compatibility: Requires Bun (https://bun.sh). Works with Codex, Copilot, and Claude.
---

# Floe Memory Skill

## Objective

Keep project memory trustworthy enough that a future agent can rely on it
without inheriting stale process, outdated decisions, or contradictory context.

Memory is not an archive of everything that was said.
Memory is a working knowledge layer that should stay:

- accurate enough to trust
- small enough to retrieve
- explicit about what changed and why
- connected enough to navigate

Success means a recalled memory helps the current task immediately and does not
quietly conflict with the current user, the current repo artifacts, or the
current operating model.

## When to use this skill

Use this skill before any substantial work and before finishing any substantial
work.

Use it again during the task whenever:

- recalled memory appears stale, vague, duplicated, or contradictory
- the user changes a process, preference, owner, timeline, or direction
- current files disagree with remembered process or project state
- you create or identify a canonical note that replaces older memory

Skip it only for trivial work where no project context could matter.

## Source Of Truth Order

When memory conflicts with other evidence, resolve it in this order:

1. current user instruction in this thread
2. current canonical repo artifacts and notes
3. recent validated memory
4. older or weakly supported memory

Treat memory as a hypothesis layer, not the final authority.

## Operating Loop

For the current objective, run this loop:

1. retrieve the smallest relevant memory context
2. validate anything process-shaped, current-state, owner-shaped, or time-bound before relying on it
3. use validated memory to do the work
4. repair memory when it is wrong, stale, duplicated, or superseded
5. save only the durable delta worth carrying forward

Do not optimize for memory volume.
Optimize for memory trustworthiness.

## How to invoke

Run the canonical Floe Memory runtime, not the duplicated skill directory.

Project install path:

```bash
bun run .floe/memory/scripts/memory.ts <command> [args]
```

Global install path:

```bash
bun run ~/.floe/memory/scripts/memory.ts <command> [args]
```

Run these from the active project root so the runtime resolves the correct
workspace and database path.

If you cannot run the runtime from `.floe/memory` or `~/.floe/memory`, stop and
ask the user.

## Retrieval

Start with fast retrieval:

```bash
bun run .floe/memory/scripts/memory.ts recall "your task description"
```

Use richer discovery only when onboarding, when recall is thin, or when the
task spans multiple note areas:

```bash
bun run .floe/memory/scripts/memory.ts context "your objective"
```

To pull in linked neighbors:

```bash
bun run .floe/memory/scripts/memory.ts recall "your task description" --expand-links
```

### Retrieval rules

- Retrieve narrowly around the active objective, not the whole project.
- If the recalled memory is about process, current state, file roles, owners, dates, or operating model, validate it against the current repo before using it.
- Prefer just-in-time validation over broad audits.
- On the first substantial session for an objective after visible project drift, spend a few minutes on targeted memory hygiene before answering normally.
- Do not perform a full memory cleanup at the start of every day unless the user asked for an audit.

## Maintenance Rules

The default behavior should be maintain-or-repair first, add second.

### Update an existing memory

Update in place when the concept is the same and the existing record should stay
canonical, but its content needs correction, tightening, or fresh detail.

Use the memory ID returned by `recall` and update it directly:

```bash
bun run .floe/memory/scripts/memory.ts save "Updated memory text" --record-id mem_123 --type pattern --tags memory,process
```

Update instead of adding when:

- the same process still exists but the wording or details changed
- the same decision is still current but now needs clearer reasoning
- a current-state memory needs refresh rather than replacement

### Supersede an older memory

Supersede instead of overwriting when a decision, process, or operating model
has been replaced and preserving the historical record matters.

1. save the new canonical memory
2. link the new memory to the old one with `supersedes`

```bash
bun run .floe/memory/scripts/memory.ts save "New operating model..." --type decision --tags workflow
bun run .floe/memory/scripts/memory.ts link memory <new-id> supersedes memory <old-id>
```

Use `supersedes` when:

- the user explicitly says "stop doing this, do this instead"
- a prior process memory is no longer valid
- a canonical file structure or workflow has changed
- a current strategic frame replaces an older one

### Add a new memory

Create a new memory only when the knowledge is genuinely net-new and deserves
its own recall surface.

Good candidates:

- a new decision
- a new durable constraint
- a new pattern or convention
- a new gotcha or recurring risk

Bad candidates:

- temporary task chatter
- duplicate restatements of existing memory
- raw meeting fragments that have not been distilled

### Remove links, not records

Relationship cleanup is supported:

```bash
bun run .floe/memory/scripts/memory.ts unlink <relationship_id>
```

Use this when a relationship is wrong or no longer useful.

Do not claim that a memory or document record was deleted unless the runtime
adds a real delete command. Today, record cleanup means updating, superseding,
or leaving the record alone.

### Leave memory alone

Do not save or update memory just to mirror a temporary status if the durable
note already captures it and the information is unlikely to matter later.

## Just-In-Time Validation

Whenever retrieval returns something operationally important, verify it before
you act on it.

Validate against:

- the current user message
- the canonical notes or files for that project
- the most recent durable artifact you can inspect directly

When a recalled memory looks wrong:

- say so briefly if it materially affects the work
- name the conflict concretely
- repair the memory before finishing the task

Example:

`I found an older memory that says the project uses X, but the current START.md says Y. I'm treating X as stale and updating memory accordingly.`

If the repo resolves the conflict, fix the memory directly.
If the conflict changes intent and the repo does not settle it, ask the user a
short clarifying question before repairing memory.

## Conversation Behavior

Use memory naturally in the conversation.

- Mention prior memory when it helps the user understand continuity or a change in direction.
- If the user reverses a prior preference or process, acknowledge the change in plain language and update or supersede the old memory.
- Do not dump recall output into the conversation unless the user asked for it.
- Do not pretend memory is certain when it has not been validated.

## Write-Back Standards

Before finishing substantial work, write back only the durable delta:

- what is true now
- why it matters
- what changed
- any scope or date boundary needed to avoid future drift
- where the canonical artifact lives, when relevant

Good memory records explain the decision, reasoning, and constraints.
Bad memory records merely say that work happened.

Prefer these memory types:

- `decision` for chosen direction or replaced direction
- `learning` for verified understanding of how something works
- `pattern` for repeatable conventions or operating models
- `issue` for bugs, gotchas, or failure modes
- `preference` for user or team ways of working
- `constraint` for limitations that shape choices

For process-shaped memories, include the canonical artifact when possible, for
example `START.md`, `AGENTS.md`, or another durable note.

## Commands

From the project root:

| Command | What it does |
|---------|--------------|
| `bun run .floe/memory/scripts/memory.ts recall "<query>"` | Search memory for relevant context |
| `bun run .floe/memory/scripts/memory.ts context "<objective>"` | Build a richer context bundle |
| `bun run .floe/memory/scripts/memory.ts save "<text>" --type <type> --tags <tags>` | Save a new memory |
| `bun run .floe/memory/scripts/memory.ts save "<text>" --record-id <memory-id> ...` | Update an existing memory in place |
| `bun run .floe/memory/scripts/memory.ts remember <file> [file...]` | Register and index file(s) |
| `bun run .floe/memory/scripts/memory.ts status` | Show memory overview |
| `bun run .floe/memory/scripts/memory.ts link <src_type> <src_id> <relation> <dst_type> <dst_id>` | Create or update a relationship |
| `bun run .floe/memory/scripts/memory.ts links <type> <id> [--direction out|in|both]` | Query relationships |
| `bun run .floe/memory/scripts/memory.ts unlink <relationship_id>` | Remove a relationship |

### Retrieval flags

- `recall` and `context` support `--expand-links`
- filter link expansion with `--link-relations <csv>`
- cap linked neighbors with `--link-limit <n>`

### Relationship flags

- `link` supports `--weight <n>`
- `link` supports `--meta <json>`
- `links` supports `--relation <name>`
- `links` supports `--limit <n>`

## Relationship Types

Use these relation names when linking:

| Relation | Use when |
|----------|----------|
| `derived_from` | A memory was extracted from a document or artifact |
| `continues` | New work extends prior work |
| `depends_on` | The result needs the linked source to make sense |
| `blocks` | The result is blocked by or blocks the source |
| `describes` | The result documents the source |
| `belongs_to` | The result is part of a larger whole |
| `supersedes` | A new memory replaces an older one |
| `relates_to` | General association |
| `mentions` | Weak reference only |

## Completion Standard

You are not done with a substantial task until memory is in a trustworthy state
for the knowledge you touched.

Before you finish:

- repair any recalled memory that you proved stale or misleading
- save the durable delta from the work
- register any canonical file that should be retrievable later
- link new and old memories when replacement history matters

If you relied on memory and discovered it was wrong, fixing that is part of the
task, not optional cleanup.
