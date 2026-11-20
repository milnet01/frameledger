<!-- ants-spec-format: 1 -->
# FLED-0040 — Promise the run file's format stable

**Status:** spec draft (2026-11-20).
**Kind:** doc.
**Source:** ROADMAP FLED-0040 (engine-answers-2026-11-10; discovery S6 and S27).
**Blocker for:** FLED-0015.
**Pairs with:** FLED-0001, whose files this promise is about.

**Layman:** A promise that files written today will still be read by
future versions, and a rule for what may be added to them without
breaking that.

## 1. Goal

After this ships, an engine knows three things from one page: which
parts of its files can never change, what a later release may add to
them, and that a file frameledger reads at 0.8.0 is read by every later
release with the same values. A test holds the last of these.

## 2. Problem

1. **The promise exists as one sentence.**
   `docs/standards/versioning-overrides.md` § Breaking surfaces says a
   run file one release reads must still be read by the next. It does
   not say for how long, or what "read" covers.
2. **Nothing says when `schema` goes up.** FLED-0001 § 4.2 gives
   `schema` as `1 for this spec`, and § 4.6 says `FLED_SCHEMA` "moves
   only when the run-file format breaks". Neither defines a break. A
   writer's author cannot tell whether a later release will make them
   change their writer.
3. **Schema 1 has been tightened in place.** FLED-0070 made a
   `started_utc` that is not a real date a breach (FLED-0001 INV-102),
   so a file an earlier release passed now fails `check`. Inside `0.x`
   that was allowed. Nothing yet says it stops.
4. **No test holds an old file fixed.** `tests/test_check.py::test_schema_versions`
   reads `tests/fixtures/schema-1.csv`, a small file any commit may
   edit. A reader change that altered how an old file parses would
   pass if the fixture were changed with it.

## 3. Scope decisions (agreed with the user)

The owner handed this project's decisions to the three engine
sessions (`CLAUDE.md` § Who decides and who reviews), so the agreement
recorded here is theirs. Vestige, UT Ants and DOOM Ants each agreed
the choices below on 2026-11-20, as sessions using the format.

- The promise covers three files, not the run file alone (§ 4.1).
- An older schema is read for ever, with no deprecation window (§ 4.6).
- Only the version line is fixed across schemas (§ 4.2).
- "Read" means the reader's side: no new breach and the same parsed
  values. Statistics and verdicts stay under
  `versioning-overrides.md` § Breaking surfaces, *Verdicts* (§ 4.3).
- Schema 1 is frozen as FLED-0001 stands at the 0.8.0 release (§ 4.3).
- A writer is never made to move to a later schema (§ 4.5). UT Ants
  and DOOM Ants each named this as the part they rely on.
- A writer never writes a byte-order mark (§ 4.2; UT Ants).
- Segment kinds are an open set (§ 4.4; UT Ants).
- The frozen run file has a space-padded line 1 (§ 4.8; Vestige, which
  rewrites its header in place at close).

## 4. Design

### 4.1 The files it covers

| File | Line 1 keyword | Defined in FLED-0001 | The analyser's number |
|---|---|---|---|
| run file | `# frameledger ` | § 4.1 to § 4.5 | `ledger.SCHEMA` |
| budget file | `# frameledger-budget ` | § 4.12 | `budgeting.SCHEMA` |
| baseline file | `# frameledger-baseline ` | § 4.17 | `baseline.SCHEMA` |

Each file has its own `schema` number. One going up does not move the
others. "A file" below means any of the three.

### 4.2 What never changes

In every schema, present and future:

- the file is UTF-8 text;
- line 1 is the file's keyword from § 4.1, then one JSON object on that
  line;
- that object holds `schema` at its top level, a whole number, 1 or
  more;
- a writer puts no byte-order mark before the keyword. A reader skips
  one, as `ledger.read_bytes` does today, since an editor on Windows
  may add it.

So any release can tell which schema a file is before reading anything
else. Nothing else is fixed across schemas: schema 2 may change the
column line, the rows or the close line.

### 4.3 A released schema is fixed

**A file that 0.8.0 or any later release reads without a breach is
read without a breach by every release after it, and parses to the
same values.** A file only an earlier release passed is promised
nothing.

- **Without a breach** — `check FILE` exits 0 for a run file; a budget
  or baseline file is not refused with exit 3 for its own contents.
- **The same values** — for a run file, the `ledger.Run`'s `header`,
  `static`, `close` and rows: each row's segment, frame, category,
  name, depth and value in thousandths. For a budget or baseline file,
  the lines it holds, as the reader hands them to the command.
- **Not covered here** — what is computed from those values. A
  percentile, a warning or a verdict changes only as
  `versioning-overrides.md` § Breaking surfaces allows. A new warning
  on an old file is an addition, not a break.

So after 0.8.0 no rule of a released schema is tightened. A check that
would newly refuse a file that passed, as INV-102 of FLED-0001 did, is
a new schema or a warning, never a new breach in schema 1.

**A file that already breaches is promised nothing.** A later release
may read it, or report the breach in other words.

**A reader fault is fixed, not kept**, and FLED-0001 decides what a
fault is.

- Where the reader passes a file that FLED-0001 forbids, the fix lands
  as a warning in schema 1. It becomes a breach only in a later schema.
- Where the reader parses a value differently from what FLED-0001
  says, the fix lands and the value changes. The release note names it
  (UT Ants). "The same values" means the values FLED-0001 gives.

### 4.4 What may be added to a released schema

Only what every earlier release already reads correctly. For the run
file's schema 1:

| Addition | What a release from before it does with the file |
|---|---|
| an optional header field | warns `unknown_field`, reads the rest |
| an optional key in the close line | ignores it |
| an `event`, `cpu`, `gpu`, `mem` or `ext.<engine>` name | reads the row; these sets are open (FLED-0001 § 4.4) |
| a segment kind | reads the row; any kind within the length limit is allowed, and `view`, `move`, `leg` and `spot` are examples |
| a `frame` name | warns `unknown_frame_name`, reads the rest |
| anything in the static line | prints it; its shape is the engine's (FLED-0001 § 4.3) |

For the baseline file's schema 1: a key in line 1, which FLED-0001
§ 4.17 already says is ignored.

An addition is optional for ever. Its absence means unknown, as
FLED-0001 § 4.2 says of every optional field. A field once defined
keeps its meaning, type and unit.

**A name defined after a schema's release brings warnings only in that
schema, never a breach** (UT Ants). A file may already use the name
for something else: a header field of its own, a `frame` name, an
`event` name. FLED-0001 § 4.4 made any `event/generated` value but
`1.000` a breach; after 0.8.0 such a rule is a warning in schema 1.

**An engine's own names have homes no later release defines into**:
the header's `extra` object (FLED-0001 § 4.2), the static line, and
rows under `ext.<engine>`. A name written elsewhere may meet a later
definition, and then gets its warning.

### 4.5 What needs a new schema number

Everything else, because an earlier release would refuse the file or
read it wrongly:

- a new required field, line or column;
- a new category, or a new line beginning `#`;
- a change to what an existing field, row or unit means, or to the
  rounding rule of FLED-0001 § 4.4;
- a rule that refuses what the schema allowed;
- for the budget file, a new key in line 1 or a new column.

**A writer is never made to move.** A schema N file stays valid for
ever (§ 4.6). A writer changes the number it writes only when it uses
something a later schema defines.

`FLED_SCHEMA` in `include/frameledger.h` is the schema that header's
functions write. An engine vendors the header from a release (FLED-0001
§ 4.6), so its files change schema only when it takes a newer header
whose `FLED_SCHEMA` is higher. The release note of the first such
header says so. Keeping the older header is always allowed.

### 4.6 How long an older schema is read

For ever. Every release reads every schema that any release defined.
There is no end date and no deprecation window.

Ending support for a schema is a breaking change to a surface. It
needs a MAJOR release and the three engines' agreement, and it is not
planned.

### 4.7 A file newer than the analyser

Unchanged from FLED-0001 INV-2: a run file whose `schema` is above the
analyser's is exit 3, naming both versions. The reader decides this
from line 1 alone (§ 4.2), before judging any other header field or
line, since under a newer schema those may be laid out differently. A
budget or baseline file whose `schema` the release does not read is
exit 3, naming the schema it holds and the one read.

### 4.8 Frozen files

```
tests/fixtures/frozen/
  run-schema-1.csv         a run file using every field and line schema 1 defines at 0.8.0
  run-schema-1.json        its parsed values (§ 4.3)
  budget-schema-1.csv
  baseline-schema-1.txt
  SHA256SUMS               one line per file above
tests/test_frozen.py
```

- A frozen file is never edited once a release has shipped it. A later
  addition to a schema (§ 4.4) gets a new frozen file beside it; the
  old one stays. So does a run file an engine's own writer wrote, when
  an engine gives one.
- `run-schema-1.csv` holds every required and optional header field,
  the static line, every category, a quoted field, a negative value,
  line 1 padded with spaces after its closing brace (FLED-0001 § 4.1)
  and CRLF on at least one line.
- It also holds a row at each limit of FLED-0001 § 4.2 and § 4.4: the
  longest name, segment kind, segment id and category, the most digits
  in a frame number and a depth, the largest value, and the most
  fraction digits in `started_utc`. A limit lowered later then fails
  INV-1 (UT Ants).
- `tests/test_frozen.py` reads each frozen file and compares; checks
  each file against `SHA256SUMS`; and checks that every number from 1
  to each of the three `SCHEMA` constants has its frozen files.

## 5. Invariants

- **INV-1** — `run-schema-1.csv` passes `check` with exit 0 and no
  breach, and `ledger.read` gives exactly the values in
  `run-schema-1.json`.
  *Test:* `tests/test_frozen.py::test_run_file_reads_the_same`.
  *Breaks when:* a reader change refuses or re-reads something schema 1
  allowed: a tightened `started_utc` rule, a changed rounding, a
  stripped space. The fixture isolates the reader: the test compares
  parsed values, so no change to statistics or wording can fail it.

- **INV-2** — The frozen budget file and baseline file are accepted,
  and hold the lines stored for them.
  *Test:* `tests/test_frozen.py::test_budget_and_baseline_read_the_same`.
  *Breaks when:* `budgeting.py` or `baseline.py` refuses a column value
  or a line 1 key that schema 1 allowed.

- **INV-3** — Each frozen file's SHA-256 is its line in `SHA256SUMS`.
  *Test:* `tests/test_frozen.py::test_frozen_files_unchanged`.
  *Breaks when:* a commit edits a frozen file so that INV-1 or INV-2
  passes again. It does not break when the same commit also rewrites
  `SHA256SUMS`; § 10 says so.

- **INV-4** — For each of the three files, every number from 1 to the
  analyser's `SCHEMA` constant has a frozen file.
  *Test:* `tests/test_frozen.py::test_every_schema_is_frozen`.
  *Breaks when:* a commit raises a `SCHEMA` constant and adds no frozen
  file for the new number, or deletes an old schema's frozen file.

- **INV-5** — A run file whose line 1 holds `schema` 99, and whose
  other header fields and later lines break schema 1, is exit 3 with a
  message naming schema 99 and schema 1, and reports no breach.
  *Test:* `tests/test_frozen.py::test_newer_schema_is_judged_from_line_1`,
  on a file built in the test.
  *Breaks when:* the reader judges a header field or a later line
  before `schema`, and so reports a schema 1 breach in a file that is
  not schema 1. `tests/fixtures/schema-99.csv` cannot show this: every
  other line of it is valid schema 1.

- **INV-6** — `run-schema-1.csv` with one more header field, one more
  close-line key, a row under a new `event` name, a row under a new
  `frame` name and a row in a segment of a new kind still exits 0 from
  `check`, and its other parsed values equal `run-schema-1.json`. Each
  addition is also tried alone.
  *Test:* `tests/test_frozen.py::test_additions_do_not_break_the_reader`.
  *Breaks when:* the reader turns any of the five into a breach: an
  unknown header field, close-line key or `frame` name refused, or
  segment kinds held to a list. Each would make an addition of § 4.4 a
  break for a pinned older release.

## 6. Failure modes

- **A frozen file must change**, because it was built wrong and never
  held what § 4.8 lists. Add a corrected file beside it. The wrong one
  stays: it is still a file a release read.
- **A needed fix would refuse files schema 1 allowed.** It lands as a
  warning (§ 4.3). If a warning is not enough, it waits for schema 2.
- **An addition turns out to need a meaning change.** The field keeps
  its meaning; the new meaning takes a new field name.
- **The promise itself is found wrong.** Changing § 4.2 to § 4.6 is a
  breaking change to a surface, with a MAJOR release and the three
  engines' agreement.

## 7. Tests

`tests/test_frozen.py` holds INV-1 to INV-6, one test each, named in
§ 5. It is new, with `tests/fixtures/frozen/`.

Each test is seen to fail before it is trusted: INV-1 by a reader
patched to round a value differently, INV-2 by a narrowed budget
column, INV-3 by one changed byte, INV-4 by a `SCHEMA` constant set to
2, INV-5 by moving the schema check after the header's field checks,
INV-6 by making `unknown_field` a breach and by holding segment kinds
to `view`, `move`, `leg` and `spot`.

What the tests do not show: that `run-schema-1.csv` uses every rule of
schema 1. A rule the file does not exercise can be tightened unseen
(§ 10). INV-6 does not try the static line or the open `cpu`, `gpu`,
`mem` and `ext.<engine>` names of § 4.4: the frozen file already holds
them, so INV-1 does.

## 8. Alternatives considered (and rejected)

- **Read an older schema for a stated number of releases.** Rejected:
  S6 says older run files still analyse, without a limit, and
  `docs/design.md` § The parts already says `ledger.py` reads every
  older schema version. A baseline kept beside an engine's code may be
  years old.
- **Raise `schema` for every addition.** Rejected: an optional header
  field would then make a pinned older analyser refuse the file with
  exit 3, where today it warns and reads it. Each release since 0.1.0
  that added a header field would have been a new schema.
- **Promise the same `report --json`, not the same parsed values.**
  Rejected: a result gains keys in most releases, and
  `versioning-overrides.md` already rules its verdicts. Two rules for
  one output would disagree.
- **Amend FLED-0001 in place of a new spec.** Rejected: FLED-0001
  defines schema 1; this rules every schema, and stays in force when a
  later spec defines schema 2.
- **Keep the rule in `versioning-overrides.md`.** Rejected: that file
  says which surfaces break. This needs invariants and tests, which a
  standard's delta file does not carry.

## 9. Out of scope

- A schema for each command's JSON result — tracked by FLED-0041.
- How a flag or field is retired, and which Python versions and
  systems are supported — tracked by FLED-0042.
- Defining schema 2. Nothing asks for one.
- Which schema the analyser's own writers write once two exist:
  `presentmon.py`, and a saved baseline — deferred; not yet queued.
- Fuzzing the reader with broken files — tracked by FLED-0047.

## 10. What checks this

| Rule | What catches a breach |
|------|----------------------|
| INV-1 | `tests/test_frozen.py::test_run_file_reads_the_same` |
| INV-2 | `tests/test_frozen.py::test_budget_and_baseline_read_the_same` |
| INV-3 | Partial: `tests/test_frozen.py::test_frozen_files_unchanged` catches an edited file; a commit that edits the file and `SHA256SUMS` together is caught only by the engines' code review |
| INV-4 | `tests/test_frozen.py::test_every_schema_is_frozen` |
| INV-5 | `tests/test_frozen.py::test_newer_schema_is_judged_from_line_1` |
| INV-6 | `tests/test_frozen.py::test_additions_do_not_break_the_reader` |
| § 4.2 | Partial: INV-5 holds the reader to line 1; **nothing** stops a later spec from moving `schema` off line 1 but its review |
| § 4.3 no tightening | Partial: INV-1 and INV-2, for the rules the frozen files exercise; a rule they do not exercise has **nothing** |
| § 4.4 and § 4.5 | **nothing** — whether a change is an addition or a new schema, and whether a newly defined name brings only a warning, is judged when its spec amendment is reviewed by the engines |
| § 4.6 | Partial: INV-4 stops a frozen file being dropped; **nothing** stops a release note from ending support but the engines' review |

## 11. Cross-doc impact

- `docs/standards/versioning-overrides.md` § Breaking surfaces — the
  run-file bullet keeps the surface and points here for the rule.
- `docs/specs/FLED-0001-run-file-format.md` — § 4.2's `schema` row and
  § 4.6's `FLED_SCHEMA` line point here for when the number moves;
  § 4.12 and § 4.17 likewise. No clause of it changes meaning.
- `docs/design.md` § The parts — `ledger.py`'s "reads every older
  schema version" cites this spec.
- `README.md` — one line under its format section naming the promise.
- `CHANGELOG.md` — 0.8.0 names the freeze.

## 12. Cold-eyes loop log

Rows live in `../reviews/FLED-0040-format-stability-promise-loop-log.md`.

## 13. Open questions

1. **What `resolution` means when `render_scale` is not 1** (UT Ants,
   2026-11-20). FLED-0001 § 4.2 says `[width, height]` in pixels and
   not which pixels. Both fields block a compare, so two engines
   reading it differently would write files that compare and should
   not. Proposed, for FLED-0001 § 4.2 before the freeze: `resolution`
   is the size presented, and `render_scale` times each side is the
   size drawn, rounded as the engine chooses. No reader computes the
   drawn size: a printed 0.6667 times 3840 is not the 2560 drawn (UT
   Ants). Needs each engine to say what it writes today.
2. **A byte-order mark in a run file.** `ledger.read_bytes` skips one.
   FLED-0001 says so for the baseline file (§ 4.17) and not for the
   run file (§ 4.1). Proposed: § 4.1 gains the sentence, with a test.
3. **May `kit --strict` (FLED-0001 § 4.19) gain a code that fails a
   file it passed?** Proposed: yes. It judges a writer, and § 4.3 is
   about `check` without `--strict`. The release note names each new
   code (UT Ants).
