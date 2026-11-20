<!-- ants-spec-format: 1 -->
# FLED-0041 — Publish a schema for every JSON result

**Status:** spec draft (2026-11-20).
**Kind:** feature.
**Source:** ROADMAP FLED-0041 (engine-answers-2026-11-10).
**Blocker for:** FLED-0015.
**Pairs with:** FLED-0001, whose commands print the results; FLED-0040,
which makes the same kind of promise for the files.

**Layman:** Programs that read frameledger's results get a fixed
description of them, shipped with each release, and a test stops a
later release from quietly breaking it.

## 1. Goal

After this ships, a script's author can read, for each command, one
file that says which keys its `--json` result holds, each key's type,
whether it is always there and whether it may be null. The file comes
with the release they pinned. The tests hold every result the analyser
prints to that file, and hold later releases to the files earlier
releases shipped.

## 2. Problem

1. **A result's shape is written as key names in prose.** FLED-0001
   § 4.8 and § 4.10 to § 4.18 list each `result`'s keys with no types.
   Whether a key may be null or absent is in sentences, or nowhere.
2. **No test checks a whole result.** The tests assert picked keys.
   `tests/test_render.py::test_text_matches_json` holds `summary`
   (FLED-0001 INV-13), and nothing holds a result's key set or types.
   A key can be dropped, or change type, with every test passing.
3. **The promise has no machine behind it.**
   `docs/standards/versioning-overrides.md` § Breaking surfaces makes a
   result's "keys and meanings" a breaking surface, and says adding a
   key is not breaking. Only a reviewer notices a breach.
4. **Two results differ where a reader expects one shape.** In
   `bisect`'s `runs` an entry has no `started_utc`, which `compare`'s
   has, and an unreadable run's entry has no `under_load` key
   (`src/frameledger/bisecting.py`).
5. **Nothing stops a number JSON cannot hold.** `render.to_json` calls
   `json.dumps` with its default `allow_nan`, which would print `NaN`
   or `Infinity`. No result holds one today.

## 3. Scope decisions (agreed with the user)

The owner handed this project's decisions to the three engine sessions
(`CLAUDE.md` § Who decides and who reviews). Vestige and UT Ants each
agreed the choices below on 2026-11-20. DOOM Ants' answer is owed
(§ 13).

- JSON Schema draft 2020-12, one file per command (§ 4.1).
- The files ship in the release archive and inside `frameledger.pyz`,
  which prints them (§ 4.2). Vestige and UT Ants each pin the `.pyz`
  alone and would read them from it.
- The published files allow keys they do not name; the tests refuse
  them (§ 4.3, § 4.6).
- Each release's files are frozen, and later output is held to them
  (§ 4.7).
- A result carries no schema number. Its `frameledger` key picks the
  release whose files describe it (§ 4.3; Vestige). So every result
  carries that key, on an error exit too (INV-8; UT Ants).
- The tests use the `jsonschema` package; the analyser stays standard
  library only (§ 4.8).
- `bisect`'s run entries gain `started_utc` and always carry
  `under_load` (§ 4.5).
- `floor`'s `fps` keeps its name, and its description says it is a
  count (§ 4.5).
- On an unreadable file `result` stays as it is, and each schema
  states that shape, so a script need not read prose (§ 4.4; Vestige,
  UT Ants).

Mine, not yet put to the engines, for their review of this spec: the
files are printed by a flag, `--schema`, not a command (§ 4.2, § 8);
which value sets are closed (§ 4.3); and no `$id` (§ 4.3).

## 4. Design

### 4.1 The files

```
src/frameledger/schemas/
  <command>.schema.json    one per command
```

`<command>` is each value the result's `command` key takes: `check`,
`kit`, `report`, `floor`, `compare`, `alternate`, `bisect`, `budget`,
`survey`, `import` and `selftest`. Each file describes the whole
object the command prints under `--json`, from `frameledger` to
`result` (FLED-0001 § 4.8).

Each file is UTF-8 with LF line ends, and is written by hand. It is
not generated from the code, since a file made from the code cannot
disagree with it.

### 4.2 Where a reader gets them

- **The archive.** `frameledger-TAG.zip` holds each file as
  `schemas/<command>.schema.json`.
- **The `.pyz`.** `frameledger.pyz` holds the same files, and
  `frameledger --schema COMMAND` prints one to standard output, byte
  for byte, and exits 0. `--json` and `--markdown` change nothing, as
  with `--version`.
- A `COMMAND` that is not one of § 4.1's names is exit 3: standard
  output holds nothing, and standard error names the ones there are.
  The name is looked up in a fixed list and is never used as a path.
- Under `bisect`, `--schema` is refused as `--version` is (FLED-0001
  § 4.11).

`scripts/build_release.py::tracked_files` takes `schemas/` as it takes
`kit/`: tracked data files one level down, read with
`pkgutil.get_data`.

### 4.3 What a file says

- **Dialect.** `"$schema"` is
  `https://json-schema.org/draft/2020-12/schema`. There is no `$id`:
  two releases' files differ, and an `$id` would name both the same.
  The result's `frameledger` key says which release's file applies.
- **Self-contained.** A `$ref` points inside its own file. What the
  files share, such as a warning or the envelope's keys, is repeated
  under `$defs` in each, under the same name and with the same content
  (INV-5), so a printed file is usable alone.
- **Every key the analyser writes is named**, with its type and a
  `description`. A key always written is in `required`. A key that may
  be null says so in its type.
- **Open to additions.** No object is closed with
  `additionalProperties: false` or `unevaluatedProperties: false`, so
  a result with a key the file does not name still validates. That is
  `versioning-overrides.md` § Breaking surfaces, *Adding is not
  breaking*.
- **A map whose keys are data** states its values' schema with
  `additionalProperties` and names no key: a run name in
  `static_diff[].values` and `refused[].values`, a side name in
  `alternate`'s `commands`, a frame type in `import`'s `generated`.
- **Engine-supplied values are any JSON.** `report`'s `static`, the
  values in `static_diff` and `refused`, and `expected` and `found` in
  `check --expect`'s differences.
- **Closed sets** are an `enum`, and a later value is a breaking
  change: `command`; the top-level `verdict`, per command; each
  entry's own `verdict` (a measure's, a scene's, a variant's, a
  surveyed run's); `set`; `unit`; and `skip_reason`.
- **Open sets** are a string whose `description` lists today's values:
  warning codes, breach rules, `category`, `statistic`, segment kinds
  and every name an engine chose.
- **`exit_code`** is an `enum` of the codes the command's result can
  carry.

### 4.4 The shapes a file must tell apart

A command's `result` has more than one shape. Each file tells them
apart with `if`/`then` on keys of the result itself, so a validator
needs nothing but the result.

| Command | Shapes |
|---|---|
| `check` | files judged; with `--expect`, also `expect`; an unreadable file, which is left out of `files` |
| `report`, `floor`, `budget` | judged; a file error, where `result` is `{}` |
| `compare` | plain; `--by-scene`; `--base` with `--variant`; refused over blocking fields; an absent `--measure` name; a file error, `{}` |
| `alternate` | `compare`'s plain or variants shape with `commands`, `out`, `warmup` and `stopped`; stopped, with those four and `baseline` only |
| `bisect` | judged; skipped or stopped, where `value` is null |
| `survey` | judged; a run it could not judge, its figures null |
| `import`, `kit`, `selftest` | one |

The top-level `verdict` decides which keys of `result` are required:
with `"error"`, none but the ones the error shape above names. Each
file states that rule as `if`/`then` on `verdict`.

A setup or argument error prints no result (FLED-0001 § 4.11, *A bad
argument*), so no file describes one.

### 4.5 What changes in the output

- `bisect`'s `runs` entries gain `started_utc`, as `compare`'s have,
  and always carry `under_load`. For a run that could not be read both
  are null, as that entry's `commit` is.
- `render.to_json` passes `allow_nan=False`. A NaN or an infinity
  reaching it is an error inside the analyser: exit 3, or 128 under
  `bisect`, and nothing on standard output.
- Nothing else. Key order, indentation and the escaping of non-ASCII
  characters stay as `render.to_json` writes them, and are no part of
  the promise: a script parses the JSON.

### 4.6 The samples, and the stricter test

```
tests/schema_samples.py      the sample runs
tests/test_schemas.py
```

- **A sample** is a command line, the files it needs, and the shape of
  § 4.4 it shows. The samples cover every shape in § 4.4's table, and
  between them write every key the files name (INV-3).
- **The strict form** of a file is made by the test: every object that
  has `properties` and no `additionalProperties` gains
  `unevaluatedProperties: false`. Each sample's output must validate
  against its file's strict form (INV-1). So a key cannot reach a
  result without being described, while the published file stays open.

### 4.7 Frozen sets

```
tests/fixtures/schemas/
  <version>/<command>.schema.json   the files a release shipped
  SHA256SUMS                        one line per file above
scripts/freeze_schemas.py           copies the tree's files to <version>/
```

- **From 0.8.0, every release freezes its files.** `<version>` is
  `cli.VERSION`. `scripts/freeze_schemas.py` copies
  `src/frameledger/schemas/` to that folder and adds the lines to
  `SHA256SUMS`. It refuses to write over a folder that exists.
- **The release cannot forget.** With `cli.VERSION` at 0.8.0 or later,
  the tests fail when `tests/fixtures/schemas/<VERSION>/` is absent,
  and `scripts/check-release.sh` fails when it differs from the
  tree's files.
- **Later output is held to every frozen set.** Each sample's output
  must validate against its command's file in every frozen folder, in
  the open form (INV-6). A removed key, a changed type or a new value
  in a closed set fails it.
- **A deliberate break** is listed in `tests/test_schemas.py` as the
  frozen version, the command and the `CHANGELOG.md` entry that names
  it. Only a listed pair is let off. When a break is allowed is
  FLED-0042's.
- **Never edited.** A frozen file does not change. A wrong one stays,
  and the next release's file is right.

### 4.8 The validator

`scripts/local-ci.sh` pins `jsonschema` beside pytest and ruff and
passes it the same way. The version is chosen when this is built, per
`~/.claude/standards/dependencies.md`. `tests/test_schemas.py` imports
it plainly, so bare `pytest` without it fails with the import error
and skips nothing. Nothing under `src/frameledger/` imports it.

## 5. Invariants

- **INV-1** — Every sample's output validates against the strict form
  of its command's file in `src/frameledger/schemas/`.
  *Test:* `tests/test_schemas.py::test_output_matches_its_schema`.
  The fixture isolates § 4.6's strict form: a key added to a result
  and not to its file fails here and passes INV-6.
  *Breaks when:* a result gains a key its file does not name; a key
  the file requires is absent; a value has another type, or is null
  where the file does not allow it.

- **INV-2** — Each file is a valid draft 2020-12 schema, names that
  dialect, has no `$id`, closes no object, and holds no `$ref` that
  leaves the file.
  *Test:* `tests/test_schemas.py::test_each_file_is_a_schema`.
  *Breaks when:* a file has a keyword the dialect's own schema
  refuses; `additionalProperties: false`; a `$ref` to another file.

- **INV-3** — The samples show every shape in § 4.4's table, and every
  key a file names is written by at least one sample.
  *Test:* `tests/test_schemas.py::test_samples_cover_the_schemas`.
  *Breaks when:* a file names a key no sample writes; a shape in the
  table has no sample.

- **INV-4** — `--schema COMMAND` prints the file byte for byte and
  exits 0, from the tree and from `frameledger.pyz`, and the archive
  holds the same bytes under `schemas/`. A name not in § 4.1, a path
  among them, is exit 3 with nothing on standard output.
  *Test:* `tests/test_schemas.py::test_schema_flag_prints_the_file`
  and `::test_archive_holds_the_schemas`.
  *Breaks when:* the build leaves `schemas/` out of the `.pyz`; the
  flag prints a re-serialised copy; `--schema ../cli.py` prints a file.

- **INV-5** — A definition under `$defs` with the same name is the
  same in every file that has it.
  *Test:* `tests/test_schemas.py::test_shared_definitions_agree`.
  *Breaks when:* a warning's shape is corrected in one file only.

- **INV-6** — Every sample's output validates against its command's
  file in every folder under `tests/fixtures/schemas/`, but for the
  pairs listed as deliberate breaks.
  *Test:* `tests/test_schemas.py::test_output_matches_every_frozen_set`.
  Before 0.8.0 there is no folder, so the test builds one from the
  tree's files in a temporary directory and changes a sample's output.
  *Breaks when:* a release removes or renames a key a frozen file
  requires, changes its type, or writes a new value in a closed set.

- **INV-7** — Each frozen file's SHA-256 is its line in `SHA256SUMS`,
  which lists every frozen file; with `cli.VERSION` at 0.8.0 or later
  the folder for that version exists; and `scripts/freeze_schemas.py`
  refuses a folder that exists.
  *Test:* `tests/test_schemas.py::test_frozen_sets_unchanged`,
  `::test_this_version_is_frozen` and
  `::test_freeze_refuses_an_existing_folder`.
  *Breaks when:* a frozen file is edited; a release is cut without
  freezing; the script is run twice for one version.

- **INV-8** — Every sample's result carries all eight top-level keys,
  on an error exit too, and its `frameledger` is `cli.VERSION`.
  *Test:* `tests/test_schemas.py::test_every_result_names_its_release`.
  *Breaks when:* an error path builds its result without
  `cli._result`.

- **INV-9** — `render.to_json` raises on a NaN or an infinity, at any
  depth, and prints neither.
  *Test:* `tests/test_schemas.py::test_json_holds_no_nan`.
  *Breaks when:* `allow_nan=False` is dropped.

- **INV-10** — The name given to `--schema` is user input. It selects
  from § 4.1's list and never reaches the file system as a path.
  *Test:* `tests/test_schemas.py::test_schema_flag_prints_the_file`,
  its cases `../cli.py`, an absolute path and `check.schema.json`.
  *Breaks when:* the name is joined to the folder and opened.

## 6. Failure modes

- **A file and the code disagree.** INV-1 fails, naming the sample and
  the key. The fix is to whichever is wrong against FLED-0001.
- **A shape no sample shows.** Its keys are unchecked. INV-3 catches a
  key the file names; a key the code writes only in a shape with no
  sample is caught by nothing (§ 10).
- **A release is cut without freezing.** INV-7 fails as soon as
  `cli.VERSION` is bumped.
- **A frozen file was wrong when it shipped.** It stays. If the code
  was right and the file wrong, later output fails INV-6 for that
  pair, and the pair is listed with the changelog entry that says so.
- **`jsonschema` is not installed.** `tests/test_schemas.py` fails at
  import. The gate installs it, so only bare `pytest` meets this.
- **A NaN reaches `to_json`.** Exit 3 and a message on standard error,
  where today the output would be text no JSON parser reads.

## 7. Tests

`tests/test_schemas.py` holds every invariant. Each is seen to fail first: INV-1 against a file with a key
removed, INV-4 against a build without `schemas/`, INV-9 against
today's `to_json`, and the `bisect` change of § 4.5 against today's
`bisecting.py` through INV-1.

What they do not show: that a file's `description` is true, and that a
key's meaning is unchanged. A schema holds shape, not meaning.

## 8. Alternatives considered (and rejected)

- **Generate the files from the code.** A generated file agrees with
  the code by construction, so it cannot catch the code changing.
- **Closed published files.** A script validating a later release's
  output against its pinned file would fail on every added key, which
  `versioning-overrides.md` says is not a break.
- **A `schema` command instead of a flag.** Every command takes
  `--json` and prints the result object (FLED-0001 § 4.7). A command
  whose output is not that object would be the one exception, and
  would need a schema of its own. `--version` and `--selftest` are
  flags already.
- **A hand-written checker in the tests.** No new pin, but it would
  prove the files to our reading of the dialect, not to the tool an
  engine would use.
- **A schema number in the result.** One more value to keep true,
  beside a version the result already carries.
- **Rename `floor`'s `fps`.** It breaks whoever reads it, for a name.

## 9. Out of scope

- When a breaking change is allowed and how it is announced — tracked
  by FLED-0042.
- A schema for the run file, the budget file and the baseline file —
  FLED-0040 § 4.8 freezes files instead; deferred; not yet queued.
- The text and Markdown output — not a surface
  (`versioning-overrides.md` § Not surfaces).

## 10. What checks this

| Rule | What catches a breach |
|------|----------------------|
| INV-1 | Partial: `tests/test_schemas.py::test_output_matches_its_schema`, for the shapes the samples show; a key written only in a shape with no sample has **nothing** |
| INV-2 | `tests/test_schemas.py::test_each_file_is_a_schema` |
| INV-3 | Partial: `tests/test_schemas.py::test_samples_cover_the_schemas` catches a named key no sample writes; that § 4.4's table lists every shape the code has is caught only by the engines' review |
| INV-4 | `tests/test_schemas.py::test_schema_flag_prints_the_file` and `::test_archive_holds_the_schemas` |
| INV-5 | `tests/test_schemas.py::test_shared_definitions_agree` |
| INV-6 | Partial: `tests/test_schemas.py::test_output_matches_every_frozen_set`; a pair wrongly listed as a deliberate break is caught only by the engines' code review |
| INV-7 | Partial: `tests/test_schemas.py::test_frozen_sets_unchanged`, `::test_this_version_is_frozen` and `::test_freeze_refuses_an_existing_folder`; a commit that edits a frozen file and `SHA256SUMS` together is caught only by the engines' code review |
| INV-8 | `tests/test_schemas.py::test_every_result_names_its_release` |
| INV-9 | `tests/test_schemas.py::test_json_holds_no_nan` |
| INV-10 | `tests/test_schemas.py::test_schema_flag_prints_the_file` |
| § 4.3 a `description` is true | **nothing** — read by the engines when a file changes |
| § 4.3 which sets are closed | **nothing** — a set closed or opened wrongly is judged in review |
| § 4.7 the frozen folder equals the tree's files at release | `scripts/check-release.sh` |

## 11. Cross-doc impact

- `docs/specs/FLED-0001-run-file-format.md` — § 4.7 gains `--schema`;
  § 4.8 points here for each result's types; § 4.11's result block
  gains `started_utc` and `under_load`, with the rule for an unreadable
  run, and its refused flags gain `--schema`.
- `docs/standards/versioning-overrides.md` § Breaking surfaces — the
  commands bullet points here for what holds the JSON result.
- `README.md` — where a script's author finds the schemas.
- `CHANGELOG.md` — the files, `--schema`, and `bisect`'s two keys.
- `CLAUDE.md` § Build and test — bare `pytest` needs `jsonschema`.
- `docs/design.md` § The stack, and what it rules out — the
  test-only dependency.

## 12. Cold-eyes loop log

Rows live in `../reviews/FLED-0041-json-result-schemas-loop-log.md`.

## 13. Open questions

1. DOOM Ants' answer to § 3's choices is owed.
2. Vestige asks that `floor`'s windows also gain a correctly named
   key, `frames`, with `fps`'s value, `fps` being described as the
   older name. UT Ants would leave `fps` alone. DOOM Ants decides.
3. § 4.3's closed sets are narrower than the engines were asked about:
   `category` and `statistic` are open here, since a new feature may
   add one. For the engines' review.
4. `bisect` leaves `started_utc` out on purpose
   (`bisecting.py::_entry`, since the FLED-0009 code review). § 4.5
   puts it back; say if the reason then still stands.
5. `--schema` as a flag (§ 4.2, § 8) where the engines were asked
   about a `schema` command. For the engines' review.
