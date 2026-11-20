<!-- ants-spec-format: 1 -->
# FLED-0040 — Promise the run file's format stable

**Status:** accepted (2026-11-20).
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
- `resolution` is the image handed on for display (§ 11; raised by UT
  Ants, and each engine writes or will write it so).
- `check --strict` may gain a code that fails a file it passed, and
  the release note names each new code (§ 4.3).
- `FLED_SCHEMA` is the lowest schema the writer header's own lines are
  valid under, and an engine writes it as its `schema` (§ 4.5; asked
  by Vestige).

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
- line 1 is the file's keyword from § 4.1, whose last character is
  one space, then one JSON object on that line. The line ends in LF or
  CRLF;
- that object holds `schema` at its top level: a whole number, 1 or
  more, written in digits alone. `1.0`, `1e0` and `"1"` are not it
  (ExperiRays);
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

- **Without a breach** — `check FILE`, without `--strict`, exits 0 for
  a run file; a budget or baseline file is not refused with exit 3 for
  its own contents. `check --strict` is outside the promise: it fails
  on any warning (FLED-0001 § 4.19), and § 4.4's additions make an
  older release warn (DOOM Ants). It may gain a code in any release.
- **The same values**, types included — for a run file, the header,
  static and close objects, and each row's segment, frame, category,
  name, depth and value. A row's `run_id` is the header's, so it adds
  nothing. For a budget file, its `match` and each budget's fields. For
  a baseline file, each path as written, before it is resolved. § 4.8
  gives the stored form. The tests read them through the readers'
  types, such as `ledger.Run`; those types are not a surface
  (`versioning-overrides.md` § Not surfaces) and may change shape.
- **Not covered here** — what is computed from those values. A
  percentile, a warning or a verdict changes only as
  `versioning-overrides.md` § Breaking surfaces allows. A new warning
  on an old file is an addition, not a break.

So after 0.8.0 no rule of a released schema is tightened. A check that
would newly refuse a file that passed, as INV-102 of FLED-0001 did, is
a new schema or a warning, never a new breach in schema 1.

**Rules a file is judged by elsewhere are frozen with it** (Vestige).
A budget file's `match` names compare-blocking fields, so for schema 1
that list does not shrink (`compare.BLOCKING`). A baseline file needs
a fewest number of runs, so for schema 1 that number does not rise
(`baseline.FEWEST_RUNS`).

**A file that already breaches is promised nothing.** A later release
may read it, or report the breach in other words.

**A reader fault is fixed, not kept**, and FLED-0001 decides what a
fault is.

- Where the reader passes a file that FLED-0001 forbids, the fix lands
  as a warning in schema 1. It becomes a breach only in a later schema.
- Where the reader parses a value differently from what FLED-0001
  says, the fix lands and the value changes. The release note names it
  (UT Ants). "The same values" means the values FLED-0001 gives. This
  is the one case in which a frozen file's stored values change
  (§ 4.8).

### 4.4 What may be added to a released schema

Only what every earlier release already reads correctly. For the run
file's schema 1:

| Addition | What a release from before it does with the file |
|---|---|
| an optional header field | warns `unknown_field`, reads the rest |
| an optional key in the close line | ignores it |
| an `event`, `cpu`, `gpu`, `mem` or `ext.<engine>` name | reads the row; FLED-0001 § 4.4 limits a name's characters and length and lists no names for these categories |
| a segment kind | reads the row; any kind within the length limit is allowed, and `view`, `move`, `leg` and `spot` are examples |
| a `frame` name | warns `unknown_frame_name`, reads the rest |
| a key in the static line, at any depth | prints it; the shape is the engine's. No JSON number may appear anywhere in the line: a number is written as a string of its digits, and a bare one is a breach (FLED-0001 § 4.3). Strings, true, false and null are allowed |
| a key inside a header field that is an object, such as `tool`, `load` or an `inputs` entry | ignores it, with no warning; `unknown_field` judges top-level fields only (Vestige) |

For the baseline file's schema 1: a key in line 1, which FLED-0001
§ 4.17 already says is ignored. For the budget file's schema 1: a key
in line 1 that changes nothing judged, such as a note; an earlier
release ignores it. § 4.5 has the other kind.

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
definition, and then gets its warning. The close line is not such a
home: a key an engine adds there is read today and may be defined
later.

### 4.5 What needs a new schema number

Everything else, because an earlier release would refuse the file or
read it wrongly:

- a new required field, line or column;
- a new category, or a new line beginning `#`;
- a change to what an existing field, row or unit means, or to the
  rounding rule of FLED-0001 § 4.4;
- a rule that refuses what the schema allowed;
- a rule that allows what the schema refused (Vestige): a new value in
  a closed set, such as `display`, a hash prefix or a budget's
  `statistic`; a longer name, kind or number; a new character in a
  name. Every earlier release refuses the file;
- for the budget file, a new column, or a key in line 1 that changes
  what is judged. An earlier release reads only `schema` and `match`
  from line 1 (`budgeting.py`), so it would ignore the key and judge
  by the older rule.

**A writer is never made to move.** A schema N file stays valid for
ever (§ 4.6). A writer changes the number it writes only when it uses
something a later schema defines.

Two things are called a header. Here **the writer** is the C file
`include/frameledger.h`, and **line 1** is the JSON the engine puts on
the file's first line.

**`FLED_SCHEMA` in the writer is the schema whose rules the rows and
close line it writes follow.** `fled_open` copies the engine's line 1
JSON as given, so the engine writes `schema` itself, and writes
`FLED_SCHEMA` there, as Vestige does. The number rises only in a
release whose writer puts out a row or close line that the earlier
schema does not allow, and that release's note says so. A writer that
only gains what § 4.4 allows keeps its number. So taking a newer
writer relabels no file unless the writer's own output changed, and
keeping the older writer is always allowed.

The engine composes line 1 itself, so `FLED_SCHEMA` cannot know what
is in it. A file follows one schema throughout. An engine whose line 1
uses something only a later schema defines writes that schema's
number, and needs a writer whose `FLED_SCHEMA` is that number too (UT
Ants). A field of the engine's own does not
touch `schema`: the number says which schema's rules the file
follows, and § 4.4 already allows such a field (DOOM Ants). A writer
that does not use `frameledger.h` writes the number of the schema it
follows, as a literal.

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

A `schema` that § 4.2 does not allow, such as `0`, `1.5` or `true`, is
no schema at all. In a run file it is a breach of line 1 in every
release; a budget or baseline file holding it is exit 3.

### 4.8 Frozen files

```
tests/fixtures/frozen/
  run-schema-1.csv           every field, line and limit schema 1 defines at 0.8.0
  run-schema-1-awkward.csv   what schema 1 allows and a careful writer seldom writes
  run-schema-1-b.csv         two small runs, so the baseline names three
  run-schema-1-c.csv
  run-schema-1-vestige.csv   the opening frames of a run Vestige's writer wrote
  budget-schema-1.csv
  baseline-schema-1.txt      names three of the run files by relative path
  <each file above>.json     its stored values
  SHA256SUMS                 one line per file above
scripts/freeze.py            freezes a new file
tests/test_frozen.py
```

**Names.** A schema's first frozen file is `<file>-schema-<N>` with
its extension, `<file>` being `run`, `budget` or `baseline`. A further
file of the same schema adds one word: `run-schema-1-awkward.csv`.

**The stored values** are one JSON object per file, in the form
`scripts/freeze.py` writes:

| File | Its `.json` holds |
|---|---|
| run | `header`, `static` and `close` as the file's JSON gives them, `close` null when the file has none; and `rows`, in file order, each `[segment, frame, category, name, depth, thousandths]` |
| budget | `match`; and `budgets`, in file order, each `[category, name, kind, depth, statistic, limit]`, the limit in thousandths of a millisecond, an empty kind or depth null |
| baseline | `runs`: each path, relative to the baseline file's folder |

A later schema whose lines differ defines its own stored form in the
spec that defines the schema.

**Freezing a file.** Put it in the folder under its name and run
`python3 -I scripts/freeze.py`. The script writes the `.json` with the
reader of the commit it runs in, and adds the new files' lines to
`SHA256SUMS`. It refuses, writing nothing, when a file already listed
has changed or is gone. Read the new `.json` before committing it.

**Never edited.** Once a release has shipped a frozen file, the file,
its `.json` and its `SHA256SUMS` line do not change, and none is
removed. `SHA256SUMS` itself only gains lines. Until a file's first
release it may still change. A later addition to a schema (§ 4.4)
gets a new frozen file beside the old ones. The one exception is
§ 4.3's reader fault in a parsed value: the commit that fixes the
reader rewrites that `.json` and its line, and the release note names
it. The run, budget or baseline file itself still does not change.

**What the files hold.**

- `.gitattributes` marks `tests/fixtures/frozen/**` as `-text`, so no
  checkout changes a line ending or a trailing space (DOOM Ants).
- `run-schema-1.csv`: every required and optional header field, the
  static line, every category, a quoted field, a negative value, and
  line 1 padded with 2048 spaces after its closing brace (FLED-0001
  § 4.1), the most Vestige's writer leaves. A row at each limit of
  FLED-0001 § 4.2 and § 4.4: the longest name, segment kind, segment
  id and category, the most digits in a frame number and a depth, the
  largest value, and the most fraction digits in `started_utc` (UT
  Ants).
- `run-schema-1-awkward.csv` (UT Ants): no close line, as a killed run
  leaves; CRLF on every line and no final line ending; `display`
  `offscreen`; empty `inputs`, `sanitizers` and `unknown`; `power`
  `battery`; a `render_scale` of 0, a `load` above 1, negative clock
  and temperature figures, a whole number past 64 bits; a leap-day
  `started_utc` before 1970; text outside ASCII in a header string and
  a segment; a doubled quote in a quoted field; a segment id holding
  `:`; `.` and `-` in a name and an `ext.` category; `-0.000`, a
  negative `mem` value, leading zeros in a frame, a depth and a value;
  a missing frame number; true, false and null in the static line.
- `run-schema-1-c.csv` has `rows_dropped` above 0.
- `budget-schema-1.csv`: CRLF on some lines, a comment, a blank line,
  each statistic, an empty kind and depth, a depth of two digits, and
  limits with no, one and three decimal places.
- `baseline-schema-1.txt`: a key in line 1, a comment, a blank line, a
  CRLF line and a path beginning `./`.

## 5. Invariants

- **INV-1** — Every frozen run file passes `check` with exit 0 and no
  breach, and reads to exactly the values in the `.json` beside it,
  types included.
  *Test:* `tests/test_frozen.py::test_run_file_reads_the_same`.
  *Breaks when:* a reader change refuses or re-reads something schema 1
  allowed: a limit lowered, `offscreen` dropped from `display`, a file
  with no close line refused, a value read as a float, false read as
  0. The fixture isolates the reader: the test compares parsed values,
  so no change to statistics or wording can fail it.

- **INV-2** — Every frozen budget and baseline file is accepted, and
  its reader gives the values in the `.json` beside it. The `budget`
  command does not exit 3 on the frozen budget and run files.
  *Test:* `tests/test_frozen.py::test_budget_and_baseline_read_the_same`
  and `tests/test_frozen.py::test_budget_command_takes_the_frozen_budget`.
  *Breaks when:* `budgeting.py` or `baseline.py` refuses a column value
  or a line 1 key that schema 1 allowed, needs three decimal places in
  a limit, or keeps a line's CR.

- **INV-3** — Each frozen file's SHA-256 is its line in `SHA256SUMS`,
  and every file in the folder has a line.
  *Test:* `tests/test_frozen.py::test_frozen_files_unchanged`.
  *Breaks when:* a commit edits a frozen file so that INV-1 or INV-2
  passes again. It does not break when the same commit also rewrites
  `SHA256SUMS`, or removes a file with its line; § 10 says so.

- **INV-4** — For each of the three files, every number from 1 to the
  analyser's `SCHEMA` constant has a frozen file of exactly the name
  § 4.8 gives, and every frozen file has its `.json`.
  *Test:* `tests/test_frozen.py::test_every_schema_is_frozen` and
  `tests/test_frozen.py::test_frozen_files_are_found`.
  *Breaks when:* a commit raises a `SCHEMA` constant and adds no frozen
  file for the new number, deletes an old schema's first frozen file,
  or adds a frozen file without freezing it.

- **INV-5** — A run file whose line 1 holds `schema` 99, and whose
  other header fields and later lines break schema 1, is exit 3 with a
  message naming schema 99 and the reader's own schema, and no file is
  judged.
  *Test:* `tests/test_frozen.py::test_newer_schema_is_judged_from_line_1`,
  on a file built in the test.
  *Breaks when:* a newer schema stops ending the read: the reader
  notes it and goes on, so `check` lists breaches and exits 1 for a
  file that is not its schema. `tests/fixtures/schema-99.csv` cannot
  show this: every other line of it is valid schema 1.

- **INV-6** — `run-schema-1.csv` still exits 0 from `check`, with its
  other parsed values as stored, when given any of: one more header
  field; one more close-line key; one more key inside the `tool`
  object; a segment of a new kind; a row under a new `event` name; a
  row under a new `frame` name; rows under new `cpu`, `gpu`, `mem` and
  `ext.` names. Each is tried alone, then all together.
  *Test:* `tests/test_frozen.py::test_additions_do_not_break_the_reader`.
  *Breaks when:* the reader turns any of them into a breach: an
  unknown header field, close-line key, inner key or `frame` name
  refused, or segment kinds or `mem` names held to a list. Each would
  make an addition of § 4.4 a break for a pinned older release.

- **INV-7** — A `schema` of `0`, `1.5`, `true`, `1.0`, `1e0` or `"1"`
  in `run-schema-1.csv` fails `check` with exit 1 and one breach, on
  line 1. The same values, and `99`, in the frozen budget or baseline
  file are an error naming `schema`.
  *Test:* `tests/test_frozen.py::test_a_schema_that_is_no_schema` and
  `tests/test_frozen.py::test_budget_and_baseline_refuse_another_schema`.
  *Breaks when:* a reader takes `true`, `1.0` or `1.5` as schema 1,
  treats `0` as an older schema, or reads a budget file of a schema it
  does not know.

- **INV-8** — A UTF-8 byte-order mark before the first byte of the
  frozen run, budget or baseline file changes none of its values, and
  the run file still passes `check`.
  *Test:* `tests/test_frozen.py::test_byte_order_mark_is_skipped`.
  *Breaks when:* a reader stops skipping the mark, so line 1 no longer
  begins with the keyword and a file a release read is refused.

- **INV-9** — Every field `compare.BLOCKING` held at the freeze is
  still in it, and `baseline.FEWEST_RUNS` is no more than it was.
  *Test:* `tests/test_frozen.py::test_rules_frozen_with_schema_1`.
  *Breaks when:* a field leaves the blocking list, so a schema 1
  budget file's `match` naming it is refused; or a baseline needs more
  runs than a schema 1 file had to name.

- **INV-10** — `scripts/freeze.py` changes nothing in the folder as
  committed, writes each committed `.json` again byte for byte, and
  refuses, writing nothing, when a listed file was edited or removed.
  *Test:* `tests/test_frozen.py::test_freeze_adds_nothing_to_a_frozen_folder`,
  `tests/test_frozen.py::test_freeze_writes_the_stored_values_again`
  and `tests/test_frozen.py::test_freeze_refuses_a_changed_frozen_file`.
  *Breaks when:* the script re-freezes over an edited file, which
  would make an edit pass INV-3; or its stored form drifts from the
  committed files, so the next frozen file is held to another form.

## 6. Failure modes

- **A frozen file must change**, because it was built wrong and never
  held what § 4.8 lists. Add a corrected file beside it. The wrong one
  stays: it is still a file a release read.
- **A reader fault changed a stored value.** § 4.8's exception: the
  fix rewrites that `.json` and its `SHA256SUMS` line by hand, since
  `scripts/freeze.py` refuses a changed file.
- **A needed fix would refuse files schema 1 allowed.** It lands as a
  warning (§ 4.3). If a warning is not enough, it waits for schema 2.
- **An addition turns out to need a meaning change.** The field keeps
  its meaning; the new meaning takes a new field name.
- **The promise itself is found wrong.** Changing § 4.2 to § 4.6 is a
  breaking change to a surface, with a MAJOR release and the three
  engines' agreement.

## 7. Tests

`tests/test_frozen.py` holds INV-1 to INV-10, under the test names § 5
gives. `scripts/freeze.py` gives it the stored form, so the tests and
the script cannot disagree on it.

The reader already behaved as the promise says, so no test was seen
red on the tree. Each was seen to fail on a copy of the tree, with the
reader changed in a way the promise forbids: a limit lowered, a value
read as a float, false read as 0, a file with no close line refused,
`offscreen` dropped, an unknown field made a breach, the schema checks
loosened, the byte-order mark kept, a blocking field removed.

Three changes tried that way passed every test, and each changes
nothing a file can show: keeping the CR on line 1, which JSON reads as
space; keeping the CR in a baseline file, whose reader strips each
line; and lowering `baseline.FEWEST_RUNS`, which the promise allows.

What the tests do not show:

- that the frozen files use every rule of schema 1. A rule no frozen
  file exercises can be tightened unseen (§ 10);
- INV-6 to INV-8 for a schema other than 1. They build their cases by
  editing schema 1's bytes; a later schema needs its own;
- a baseline file through a command. INV-2 reads it with
  `baseline.read`; `compare --baseline` would also need the frozen
  runs to be comparable with each other, which they are not.

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
| INV-2 | Partial: `tests/test_frozen.py::test_budget_and_baseline_read_the_same` and `::test_budget_command_takes_the_frozen_budget`; a baseline file through `compare --baseline` has **nothing** |
| INV-3 | Partial: `tests/test_frozen.py::test_frozen_files_unchanged` catches an edited file; a commit that edits a file and `SHA256SUMS` together, or removes a further file such as `run-schema-1-vestige.csv` with its line, is caught only by the engines' code review |
| INV-4 | `tests/test_frozen.py::test_every_schema_is_frozen` and `::test_frozen_files_are_found` |
| INV-5 | `tests/test_frozen.py::test_newer_schema_is_judged_from_line_1` |
| INV-6 | `tests/test_frozen.py::test_additions_do_not_break_the_reader` |
| INV-7 | `tests/test_frozen.py::test_a_schema_that_is_no_schema` and `::test_budget_and_baseline_refuse_another_schema` |
| INV-8 | `tests/test_frozen.py::test_byte_order_mark_is_skipped` |
| INV-9 | `tests/test_frozen.py::test_rules_frozen_with_schema_1` |
| INV-10 | `tests/test_frozen.py::test_freeze_adds_nothing_to_a_frozen_folder`, `::test_freeze_writes_the_stored_values_again` and `::test_freeze_refuses_a_changed_frozen_file` |
| § 4.2 no mark from a writer | Partial: `include/frameledger.h` writes none, and an engine's own writer is judged by the kit (FLED-0001 § 4.19) only if the kit gains a case for it; today **nothing** |
| § 4.2 | Partial: INV-5 holds the reader to line 1; **nothing** stops a later spec from moving `schema` off line 1 but its review |
| § 4.3 no tightening | Partial: INV-1, INV-2 and INV-9, for the rules the frozen files exercise; a rule they do not exercise has **nothing** |
| § 4.4 and § 4.5 | **nothing** — whether a change is an addition or a new schema, and whether a newly defined name brings only a warning, is judged when its spec amendment is reviewed by the engines |
| § 4.6 | Partial: INV-4 stops a frozen file being dropped; **nothing** stops a release note from ending support but the engines' review |

## 11. Cross-doc impact

- `docs/standards/versioning-overrides.md` § Breaking surfaces — the
  run-file bullet keeps the surface and points here for the rule.
- `docs/specs/FLED-0001-run-file-format.md` — § 4.2's `schema` row and
  § 4.6's `FLED_SCHEMA` line point here for when the number moves;
  § 4.12 and § 4.17 likewise. Three sentences are added before 0.8.0,
  while nothing is frozen:
  - § 4.2: `resolution` is the size of the image the engine hands on
    for display, after any upscaling of its own; a window that
    stretches that image does not count, and a run with no display
    writes the size it would hand on. `render_scale` times each side,
    rounded to whole pixels as the engine chooses, is the size drawn.
    Both are as at the run's start. No reader computes the drawn size.
  - § 4.1 and § 4.12: a reader skips a UTF-8 byte-order mark at the
    start of the file, and a writer never writes one. `ledger.py` and
    `budgeting.py` already skip it.
- `docs/design.md` § The parts — `ledger.py`'s "reads every older
  schema version" cites this spec.
- `README.md` — one line under its format section naming the promise.
- `CHANGELOG.md` — 0.8.0 names the freeze.

## 12. Cold-eyes loop log

Rows live in `../reviews/FLED-0040-format-stability-promise-loop-log.md`.

## 13. Open questions

None.
