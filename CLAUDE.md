# frameledger — instructions for Claude Code

## Where this project is

**State:** 4 — Between items.
**In flight:** nothing.

> Keep these two lines true, and no `Next:` line. Why:
> `~/.claude/workflow.md` § 1, *State 5 has no sub-states*.

## How work is done here

- **`~/.claude/workflow.md`** — the states, the gates, and what "done"
  means. Read in place. This project does not have its own copy.
- **`~/.claude/standards/`** — how to write code, tests, commits,
  documents, releases. Also read in place.

Neither is summarised here. A rule restated in two places is two rules
that will disagree.

## This project's own facts

Everything below is specific to this project, which is why it lives here
rather than in a standard.

### Stack

(Decided in design — `docs/design.md`. Until then, undecided.)

### Build and test

(Filled once the stack exists.)

### Roadmap IDs

`FLED-NNNN`, per `roadmap-format.md` § 3.5.1. Commit subjects
are `<ID>: <description>`, per `commits.md`.

### Who decides and who reviews

The owner, 2026-10-24: frameledger serves Vestige, UT Ants and DOOM
Ants, and their sessions decide and review its work.

- **Questions go to the three engine sessions**, not the owner. Go to
  the owner only for something outside the three projects' scope, with
  a recommendation.
- **Rule 14's gate is cancelled for every document in this project.**
  No `review-contract` run. Each document that would have been gated
  goes to the three engine sessions for review instead.

### Overrides

Any place this project deliberately departs from a global standard goes
in `docs/standards/`, with the reason. If that directory is empty, there
are none.
