# frameledger — Design

> **Purpose — so the shape is decided once, and anyone can tell where a
> new piece of work belongs and what it is allowed to touch.**

**This document is a gate.** Work is not broken into items until it is
agreed — `~/.claude/workflow.md` § 4. The owner delegated this gate to
the Vestige, UT Ants and DOOM Ants sessions on 2026-10-24.

**Status:** agreed (2026-10-24) by Vestige, UT Ants and DOOM Ants, on the
owner's delegation. Built from
[discovery](discovery.md) and the engines'
[requirements](reviews/2026-10-24-discovery-customer-answers.md).

## The parts

Four parts. The format spec is the only thing the other three share.

- **The format** — what a run file is: its header, static line, rows
  and their rules. One document, `docs/specs/`, written with
  `write-spec`. It also fixes what engines' scripts call on the
  analyser: its commands and flags, the budget file (S12) and the JSON
  result. Every other part, and every engine's own writer, is
  built to it and to nothing else.
- **The analyser** — reads run files and reports. A directory of
  modules, `src/frameledger/`, run as `python3 -I <path>/src/frameledger`
  or as a single bundled `frameledger.pyz`. On Windows the command is
  usually `python -I` or `py -I`. Both forms put
  `src/frameledger` itself on the import path, so modules import each
  other by bare name (`import ledger`), never relatively or as
  `frameledger.ledger`. So no module may share a name with a standard
  library module, or it hides that module from the whole analyser; a
  test fails when one does (`sys.stdlib_module_names`). Its files:
  - `ledger.py` — reads one run file into a `Run`, and lists every way
    it breaks the format. It reads every older schema version (S6's
    older files) and Windows files, with CRLF endings and Windows paths
    (S11). The `check` command (S18) reports that list.
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
  common subset of C99 and C++17. It formats what the engine hands it
  and times nothing (N1). It never allocates: the engine hands it a
  buffer when it opens a run. The header states the most bytes one row
  can take, so an engine can size the buffer once for a known run
  length. Rows go into that buffer, and the engine
  writes the buffer out at a moment it chooses, outside the measured
  part of the frame (S10). When the buffer is full, a row is dropped
  and counted, never lost silently. The count goes into the file when
  the run closes. A run with any dropped rows cannot pass S8's checks,
  nor a compare that uses them: they return inconclusive, and the
  opening sentence says how many rows were dropped.
- **The tests** — `tests/`: analyser tests, sample run files in
  `tests/fixtures/`, and a writer test that compiles the header as C
  (GCC, Clang and mingw-w64 GCC) and as C++17 (G++, Clang++ and
  mingw-w64 G++), each at `-Wall -Wextra -Wpedantic -Werror`, and runs
  its output through `check`. MSVC cannot run here; Vestige and
  UT Ants compile the header with it (ADR-0002). They put
  `src/frameledger` on `sys.path`, as the run forms do.

S1, a bottleneck found and fixed in each engine, is met by the whole
tool, not by any one part.

## What may depend on what

- **The writer and the analyser depend on the format spec, and on
  nothing in each other.** They never share code. So a writer
  built from the spec alone (S7) meets the same contract as ours.
- **Inside the analyser, imports run one way:** `cli.py` →
  `run_report.py`, `compare.py`, `survey.py` → `trust.py`, `stats.py`,
  `ledger.py`. `compare.py` and `survey.py` may import
  `run_report.py`; it imports neither. `cli.py` imports `selftest.py`,
  which may import any file but `cli.py`. `render.py` is
  called only by `cli.py`.
- **`ledger.py` and `stats.py` import no other analyser file.**
- **Only `__main__.py` and the tests import `cli.py`.** The reports
  return results; they never print and never exit.
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
  `cli.py` turns it into a message and an exit code. Under `check`, a
  file that breaks the format is a failed check, not an error; every
  other command raises `LedgerError` on it.
- **Exit codes**, one ladder for every command: 0 pass, 1 regression or
  failed check, 2 inconclusive (worth re-running), 3 file or
  configuration error, or a comparison refused under S5 (not worth
  re-running). The bisect mode uses `git bisect run`'s own codes
  instead: 0 good, 1 bad, and 125 (skip this commit) where the ladder
  gives 2 or where the commit's own run file is missing or breaks the
  format. A configuration error or a broken reference file gives 128,
  which stops the bisect: `git bisect run` aborts on any code from 128
  to 255.
- **Warnings are part of the result**, never only on standard error, so
  they reach the JSON and the plain sentences.
- **No state.** The analyser reads files and writes standard output, or
  a file named on the command line. It keeps nothing between runs.
- **Locale never matters**, in the analyser or the writer. Numbers are
  read and written with `.` as the decimal point, whatever the
  machine's language. The writer formats numbers itself, never with
  locale-dependent `printf`.
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
  its SHA256 in the notes.** The archive holds `frameledger.pyz`,
  `include/frameledger.h` and `LICENSE`, so one pinned hash covers both
  parts. Engines pin the archive and its hash (S6). GitHub's own tag
  archives are not used for the pin; their hash is not promised to stay
  the same. `scripts/build_release.py` builds the archive reproducibly.
  `.github/workflows/release.yml` publishes it only when its builds on
  Linux and Windows give the hash in the notes.
- **Our tests: pytest**, a test-time tool only. The analyser and its
  `--selftest` need nothing installed.
- **No CMake ships.** An engine fetches the archive itself.

## Close calls

- [ADR-0001 — the analyser is Python, not C or C++](decisions/ADR-0001-analyser-language.md)
- [ADR-0002 — the writer is one C header usable from C++](decisions/ADR-0002-writer-language.md)

## Cold-eyes loop log

| Loop | Date | Lanes | Q1 | Q2 | Q3 | Q4 | Outcome |
|------|------|-------|----|----|----|----|---------|
| 1 | 2026-10-24 | 2 | 0 | 3 | 5 | 0 | 8 findings (both lanes held every question; 3 found by both), 8 verified / 0 dismissed, 8 fixed. 0 landed on text an earlier loop of this run added. Run stopped after this loop on the coordinator's word that the owner moved all future reviews to the three engine sessions (2026-10-24); this loop's fixes were read by no lane. Not converged. |
