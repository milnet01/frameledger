# frameledger — Design

> **Purpose — so the shape is decided once, and anyone can tell where a
> new piece of work belongs and what it is allowed to touch.**

**This document is a gate.** Work is not broken into items until it is
agreed — `~/.claude/workflow.md` § 4. The owner delegated this gate to
the Vestige, UT Ants and DOOM Ants sessions on 2026-10-24.

**Status:** draft, 2026-10-24. Built from
[discovery](discovery.md) and the engines'
[requirements](reviews/2026-10-24-discovery-customer-answers.md).

## The parts

Four parts. The format spec is the only thing the other three share.

- **The format** — what a run file is: its header, static line, rows
  and their rules. One document, `docs/specs/`, written with
  `write-spec`. Every other part, and every engine's own writer, is
  built to it and to nothing else.
- **The analyser** — reads run files and reports. A Python package in
  `src/frameledger/`, run as `python3 -I <path>/src/frameledger` or as
  a single bundled `frameledger.pyz`. Its files:
  - `ledger.py` — reads one run file into a `Run`, and says how it
    breaks the format. The `check` command (S18) is this file's
    verdict.
  - `stats.py` — percentiles, lows, spreads, one-second windows,
    frame-to-frame variation. Numbers in, numbers out.
  - `trust.py` — whether a run can be trusted and whether two runs may
    be compared, with overrides (S5).
  - `run_report.py` — one run: cost ranking, bound-by, worst frames,
    floor check, pass budgets, pacing (S2, S3, S8, S12, S13, S14).
  - `compare.py` — labelled sets of runs, survey against survey, and
    the bisect verdict (S4, S15, S16, S17).
  - `survey.py` — many runs ranked (S9).
  - `render.py` — turns a result into plain text or JSON. Plain
    sentences come first.
  - `cli.py` and `__main__.py` — commands, flags and exit codes.
  - `selftest.py` — `--selftest`: the analyser's own checks on built-in
    sample files, no GPU, no network.
- **The writer** — `include/frameledger.h`, one optional header in the
  common subset of C99 and C++17. It formats what the engine hands it,
  buffers in memory, and writes outside the frame loop. It times
  nothing (N1).
- **The tests** — `tests/`: analyser tests, sample run files in
  `tests/fixtures/`, and a writer test that compiles the header as C
  and as C++ and runs its output through `check`.

## What may depend on what

- **Every part depends on the format spec, and on nothing in another
  part.** The writer and the analyser never share code. So a writer
  built from the spec alone (S7) meets the same contract as ours.
- **Inside the analyser, imports run one way:** `cli.py` →
  `run_report.py`, `compare.py`, `survey.py` → `trust.py`, `stats.py`,
  `ledger.py`. `render.py` is called only by `cli.py`.
- **`ledger.py` and `stats.py` import nothing from the package.**
- **Nothing imports `cli.py`.** The reports return results; they never
  print and never exit.
- **Only the Python standard library** (N3), and only what Python 3.10
  has.
- **Tests may import any analyser file.** No analyser file imports from
  `tests/`.

## What every part does the same way

- **Results are data first.** Every report builds one result object.
  `render.py` turns it into text or JSON, so the two can never
  disagree.
- **Plain sentences lead.** Every text report opens with sentences a
  non-programmer can act on. Then tables no wider than 100 columns. No
  meaning is carried by colour alone.
- **Errors.** A file or argument problem raises one exception type,
  `LedgerError`, carrying what was wrong and where (file, line). Only
  `cli.py` turns it into a message and an exit code.
- **Exit codes**, one ladder for every command: 0 pass, 1 regression or
  failed check, 2 inconclusive (worth re-running), 3 file or
  configuration error (not worth re-running). The bisect mode uses
  `git bisect run`'s own codes instead: 0 good, 1 bad, 125 skip.
- **Warnings are part of the result**, never only on standard error, so
  they reach the JSON and the plain sentences.
- **No state.** The analyser reads files and writes standard output, or
  a file named on the command line. It keeps nothing between runs.
- **Locale never matters.** Numbers are read and written with `.` as
  the decimal point, whatever the machine's language.
- **Files are read in one pass**, row by row, so a survey of about a
  million rows stays under a minute (S19).

## The stack, and what it rules out

- **Analyser: Python 3.10 or newer, standard library only.** All three
  engines asked for it: no build step, already in their CI, runs on
  Windows. Runner-up: C or C++, which would make every customer build
  the analyser for a report. [ADR-0001](decisions/ADR-0001-analyser-language.md).
  Rules out: plotting libraries, data-frame libraries, embedding the
  analyser in an engine.
- **Writer: one header, C99 and C++17 common subset.** DOOM Ants is C;
  Vestige is C++17; UT Ants is C++23. Runner-up: a C++ header, which
  DOOM's C engine cannot include. [ADR-0002](decisions/ADR-0002-writer-language.md).
  Rules out: designated initialisers, variable-length arrays,
  `restrict`, and anything else one of the two languages rejects.
- **Release: a git tag plus one archive attached to the release, with
  its SHA256 in the notes.** The archive holds `frameledger.pyz` and
  `include/frameledger.h`, so one pinned hash covers both. Engines pin
  the archive and its hash (S6). GitHub's own tag archives are not used for the pin; their
  hash is not promised to stay the same.
- **Our tests: pytest**, a test-time tool only. The analyser and its
  `--selftest` need nothing installed.
- **No CMake ships.** An engine fetches the archive itself.

## Close calls

- [ADR-0001 — the analyser is Python, not C or C++](decisions/ADR-0001-analyser-language.md)
- [ADR-0002 — the writer is one C header usable from C++](decisions/ADR-0002-writer-language.md)

## Cold-eyes loop log

| Loop | Date | Lanes | Q1 | Q2 | Q3 | Q4 | Outcome |
|------|------|-------|----|----|----|----|---------|
