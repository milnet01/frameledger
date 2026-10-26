# frameledger — instructions for Claude Code

## Where this project is

**State:** 5 — On an item.
**In flight:** FLED-0009, bisect verdict mode.

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

The analyser is Python 3.10 or newer, standard library only; the writer
is one C header. `docs/design.md` § The stack, and what it rules out.

### Build and test

- `./scripts/local-ci.sh` — the gate, and all GitHub CI runs: document
  links and cited tests, ruff, pytest, then `--selftest`, each under the
  uv, Python and tool versions the script pins. `--docs` runs only the
  document checks; the pre-push hook picks it for a documentation-only
  push.
- `pytest` — the tests alone. `pyproject.toml` puts `src/frameledger`
  on the import path.
- `python3 -I src/frameledger check FILE…` — run the analyser from the
  tree.

### Roadmap IDs

`FLED-NNNN`, per `roadmap-format.md` § 3.5.1. Commit subjects
are `<ID>: <description>`, per `commits.md`.

`ROADMAP.md` is generated from the Ants roadmap store, as its header
says: change it with `roadmap_log`, never by hand.

### Who decides and who reviews

The owner, 2026-10-24: frameledger serves Vestige, UT Ants and DOOM
Ants, and their sessions decide and review its work.

- **Questions go to the three engine sessions**, not the owner. Go to
  the owner only for something outside the three projects' scope, with
  a recommendation.
- **Rule 14's gate is cancelled for every document in this project.**
  No `review-contract` run. Each document that would have been gated
  goes to the three engine sessions for review instead.
- **Code goes to them for review too, and the request asks for
  readability as well as correctness** (the owner, 2026-10-24).

### Overrides

Any place this project deliberately departs from a global standard goes
in `docs/standards/`, with the reason. If that directory is empty, there
are none.
