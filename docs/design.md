# frameledger — Design

> **Purpose — so the shape is decided once, and anyone can tell where a
> new piece of work belongs and what it is allowed to touch.**

**This document is a gate.** Work is not broken into items until it is
agreed — `~/.claude/workflow.md` § 4. The owner delegated this gate to
the Vestige, UT Ants and DOOM Ants sessions on 2026-10-24.

**Status:** agreed by Vestige, UT Ants and DOOM Ants, on the owner's
delegation. Built from [discovery](discovery.md) and
the engines' [requirements](reviews/2026-10-24-discovery-customer-answers.md).
How it grew: [history](history/design.md).

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
    older files; `docs/specs/FLED-0040-format-stability-promise.md`) and Windows files, with CRLF endings and Windows paths
    (S11). The `check` command (S18) reports that list.
  - `stats.py` — percentiles, lows, spreads, one-second windows,
    frame-to-frame variation. Numbers in, numbers out.
  - `trust.py` — whether a run can be trusted and whether two runs may
    be compared, with overrides (S5).
  - `run_report.py` — one run: cost ranking, bound-by, worst frames,
    floor check, pacing (S2, S3, S8, S13, S14).
  - `budgeting.py` — pass budgets: reads a budget file and judges one
    run's passes and frame spans on `run_report.py`'s figures (S12). It takes the
    compare-blocking fields from `compare.py`, which `run_report.py`
    may not import.
  - `compare.py` — labelled sets of runs (S4, S16).
  - `bisecting.py` — the bisect verdict, from `compare.py`'s judging of a
    measure (S17). Not `bisect.py`, which would shadow the standard
    library's module.
  - `survey.py` — many runs ranked (S9).
  - `scenes.py` — survey against survey, `compare --by-scene`: each
    scene one `compare.py` compare, then ranked and counted (S15).
  - `alternate.py` — the run helper (S21): starts each build's command
    in turn, in pairs that alternate which side goes first; `cli.py`
    then compares the files they wrote. It times nothing.
  - `variants.py` — named variants against one base (S23): each
    variant one `compare.py` compare against the base, then ranked.
  - `baseline.py` — reads a baseline file into the run paths it names
    (S24).
  - `presentmon.py` — turns a PresentMon capture into a run file (S25).
  - `atomic.py` — writes a file whole or not at all: an import's run
    file, and the report page.
  - `generated.py` — reads a run as its application rendered it: frames
    marked `event/generated` left out, unless `--all-frames` keeps them
    (FLED-0001 § 4.20).
  - `strict.py` — `check --strict`: the warnings on what is legal but
    unwise (S7).
  - `expect.py` — `check --expect`: one run file against an expected
    one, by content, not layout (S7).
    It compares a JSON boolean only with a boolean, since Python's
    `True == 1`.
  - `kit.py` — `kit DIR`: writes the kit that proves a stranger's
    writer (S7). Its cases are files in `kit/` beside it, a `NAME.json`
    and a `NAME.csv` each, with `README.txt`. `kit/` is plain data: no
    `.py` and no `__init__.py`, so `import kit` still loads `kit.py`.
    `kit.py` reads each with `pkgutil.get_data(__name__, "kit/NAME")`,
    which reads the tree and `frameledger.pyz` alike, as bytes, and
    writes them as bytes. It names each case itself, since a folder
    inside the `.pyz` cannot be listed through the loader; a test
    checks the names against `kit/`. `.gitattributes` pins `kit/` to LF,
    so a Windows checkout writes the same bytes as the `.pyz`.
  - `schemas.py` — `schema COMMAND`: prints the JSON Schema of one
    command's `--json` result
    ([FLED-0041](specs/FLED-0041-json-result-schemas.md)). The
    schemas are files in `schemas/` beside it, plain data read and
    named as `kit.py` reads and names its cases, and pinned to LF the
    same way.
  - `render.py` — turns a result into plain text, JSON or Markdown.
    Plain sentences come first.
  - `picture.py` — turns one run and its result into the optional
    report page, its graph drawn as SVG from the run's timeline (S26).
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
  its output through `check`. A second writer test,
  `tests/writer/test_kit.sh`, runs `scripts/make_kit.py` into a
  scratch folder under each toolchain that runs its programs, then
  checks each file it wrote with `check --expect` against the case's
  `NAME.csv`. Both scripts read one toolchain table,
  `tests/writer/toolchains.sh`, and a toolchain not installed fails
  the run, naming the checks that did not run. mingw-w64 is build-only
  here, so it runs no case. On macOS the table has Apple's Clang alone.
  The local gate and CI run both scripts.
  `tests/test_kit.py` checks the kit itself: each `NAME.csv` gives under
  `check --strict` exactly the codes its `warns` lists, and `kit` run
  from the release `.pyz` writes the same bytes as from the tree.
  `tests/test_strict.py` checks the strict codes. CI runs the whole gate on Linux and on
  macOS, where the writer test uses Apple's Clang alone (S11). MSVC
  cannot run here; Vestige and
  UT Ants compile the header with it (ADR-0002). They put
  `src/frameledger` on `sys.path`, as the run forms do.

**The kit's expected files are made by the shipped writer, never by
hand.** `scripts/make_kit.py` is the one piece of code that turns a
case into writer calls. For each case it writes a C driver, builds it
with the header and runs it, keeping what it prints, as bytes, as the
case's `NAME.csv`. The driver:

- calls `fled_open` with the case's `header` and `static` as JSON text,
  and the header's `run_id` as its own argument;
- calls `fled_row` for each row, ordered by `arrives`, then as listed;
- sizes the buffer to hold the opening lines, the close line and one
  row. Before each kept row it hands on the pending bytes but keeps
  the opening lines' length of them pending, and before a dropped row
  hands on nothing. So the
  kept row before a dropped one still fills the buffer, and `fled_row`
  returns `FLED_DROPPED`. Handing on every byte would free the opening
  lines' room too, and one row could not fill it. A dropped row must
  therefore follow a kept one;
- calls `fled_close` with `close.frames`, unless `close` is null.

So a writer change that alters a kit file fails `test_kit.sh` until the
kit is made again and the change shows in its diff.

S1, a bottleneck found and fixed in each engine, is met by the whole
tool, not by any one part.

## What may depend on what

- **The writer and the analyser depend on the format spec, and on
  nothing in each other.** They never share code. So a writer
  built from the spec alone (S7) meets the same contract as ours.
- **Inside the analyser, imports run one way:** `cli.py` →
  `bisecting.py`, `budgeting.py`, `scenes.py`, `alternate.py`,
  `variants.py` → `run_report.py`, `compare.py`,
  `survey.py` → `trust.py`, `stats.py`, `ledger.py`. `compare.py` and
  `survey.py` may import `run_report.py`; it imports neither. `bisecting.py` may import
  `compare.py` and `run_report.py`, and so may `budgeting.py`,
  `scenes.py`, `alternate.py` and `variants.py`.
  `cli.py` imports `selftest.py`,
  which may import any file but `cli.py`. `render.py` and `picture.py`
  are called only by `cli.py`. `render.py` imports no other analyser
  file; `picture.py` imports `render.py`, for the text's sentences and
  tables, and `run_report.py`, `stats.py` and `ledger.py`.
- **`ledger.py` and `stats.py` import no other analyser file.**
  `baseline.py`, `atomic.py`, `expect.py` and `kit.py` import only
  `ledger.py`, and `presentmon.py` only `ledger.py` and `atomic.py`; `strict.py` imports `ledger.py` and `stats.py`, whose
  `median` is § 4.19's lower middle. Only `cli.py` calls them, and
  `selftest.py` may, as it may import any file but `cli.py`.
- **`generated.py` imports only `ledger.py`.** `compare.py`,
  `survey.py`, `scenes.py`, `variants.py` and `cli.py` import it, so
  every command reads a run the same way.
- **Only `__main__.py` and the tests import `cli.py`.** The reports
  return results; they never print and never exit.
- **Only the Python standard library** (N3), and only what Python 3.10
  has.
- **Tests may import any analyser file.** No analyser file imports from
  `tests/`.

## What every part does the same way

- **Results are data first.** Every report builds one result object.
  `render.py` turns it into text, JSON or Markdown, and `picture.py`
  into the report page, so no two forms can disagree.
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
  a file named on the command line. It keeps nothing between runs. The
  run helper (S21) also starts the commands it is given and waits for
  each; a baseline (S24) is a file the engine keeps.
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
  its SHA256 in the notes.** The archive holds `frameledger.pyz`, its
  launchers for Linux and Windows, `include/frameledger.h` and
  `LICENSE`, so one pinned hash covers both parts. The kit is inside
  `frameledger.pyz`: `scripts/build_release.py` packs the tracked
  `kit/` files under `kit/` with the modules, and the result schemas
  under `schemas/` the same way. Those are the two folders
  its flatness check allows, and only for files that are not `.py`.
  The archive also holds each schema under `schemas/`, for an engine
  that pins the archive and not the `.pyz`. Engines pin the archive and its hash (S6). GitHub's own tag
  archives are not used for the pin; their hash is not promised to stay
  the same. `scripts/build_release.py` builds the archive reproducibly.
  `.github/workflows/release.yml` publishes it only when its builds on
  Linux and Windows give the hash in the notes, and its Windows
  launcher runs by name. A PyPI package with a `frameledger` command
  (FLED-0043), still standard library only, sits beside the archive
  and does not replace it.
- **Our tests: pytest, and `jsonschema`** to hold each JSON result to
  its schema with the validator a script's author would use
  (FLED-0041 § 4.8). Both are test-time tools only, pinned in
  `scripts/local-ci.sh`. The analyser and its `--selftest` need
  nothing installed.
- **No CMake ships.** An engine fetches the archive itself.

## Close calls

- [ADR-0001 — the analyser is Python, not C or C++](decisions/ADR-0001-analyser-language.md)
- [ADR-0002 — the writer is one C header usable from C++](decisions/ADR-0002-writer-language.md)

## Cold-eyes loop log

In [its own file](reviews/design-loop-log.md).
