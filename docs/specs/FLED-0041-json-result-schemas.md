<!-- ants-spec-format: 1 -->
# FLED-0041 — Publish a schema for every JSON result

**Status:** accepted (2026-11-20).
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
   § 4.8 and § 4.10 to § 4.20 list each `result`'s keys with no types.
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
   has. The entry of a run that could not be read, or that breaks the
   format, has no `under_load` key either (`bisecting._entry`).
5. **Nothing stops a number JSON cannot hold.** `render.to_json` calls
   `json.dumps` with its default `allow_nan`, which would print `NaN`
   or `Infinity`. No result holds one today.

## 3. Scope decisions (agreed with the user)

The owner handed this project's decisions to the three engine sessions
(`CLAUDE.md` § Who decides and who reviews). Vestige, UT Ants and DOOM
Ants each agreed the choices below on 2026-11-20.

- JSON Schema draft 2020-12, one file per command (§ 4.1).
- The files ship in the release archive and inside `frameledger.pyz`,
  which prints them (§ 4.2). Vestige and UT Ants each pin the `.pyz`
  alone; DOOM Ants pins the archive.
- The published files allow keys they do not name; the tests refuse
  them (§ 4.3, § 4.6).
- Each release's files are frozen, and later output is held to them
  (§ 4.7).
- A result carries no schema number. Its `frameledger` key picks the
  release whose files describe it (§ 4.3; Vestige). So every result
  carries that key, with an `"error"` verdict too (§ 4.4, INV-8; UT
  Ants).
- The tests use the `jsonschema` package; the analyser stays standard
  library only (§ 4.8).
- On an unreadable file `result` stays as it is, and each schema
  states that shape, so a script need not read prose (§ 4.4).

Decided in their review of this spec, the same day:

- The files are printed by a `schema` command. A `--schema` flag
  cannot be routed (§ 8; Vestige).
- `bisect`'s run entries gain `started_utc` and always carry
  `under_load` (§ 4.5; all three).
- `floor`'s windows gain `frames` beside `fps` (§ 4.5; Vestige and
  DOOM Ants. UT Ants would have left `fps` alone).
- Which value sets are closed (§ 4.3; all three).

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
  `frameledger schema COMMAND` prints one to standard output and
  exits 0. It writes the file's bytes, not text, so the output is the
  same on every system: Python's text output would turn each line end
  into CR LF on Windows.
- **`schema` prints no result.** It is the one command whose output
  is not the result object of FLED-0001 § 4.8, so `command` never
  holds `schema` and no file describes it. `--json` and `--markdown`
  are accepted and change nothing.
- A `COMMAND` that is missing, or is not one of § 4.1's names, is
  exit 3: standard output holds nothing, and standard error names the
  ones there are. The name is looked up in a fixed list and is never
  used as a path.
- **Which file describes a result.** A file names no release. Print
  it from the same `frameledger.pyz`, or take it from the same
  archive, as the copy that printed the result. 0.7.0 and earlier
  have no files.

`scripts/build_release.py::tracked_files` takes `schemas/` as it takes
`kit/`: tracked data files one level down, read with
`pkgutil.get_data`.

### 4.3 What a file says

- **Dialect.** `"$schema"` is
  `https://json-schema.org/draft/2020-12/schema`. There is no `$id`:
  two releases' files differ, and an `$id` would name both the same.
- **Self-contained.** A `$ref` points inside its own file. What the
  files share, such as a warning or the envelope's keys, is repeated
  under `$defs` in each, under the same name and with the same content
  (INV-5), so a printed file is usable alone. A `$ref` to an object
  stands alone, with no `properties` beside it (a `type` may narrow
  one that is null in some places), and never sits
  directly under `if`, `then`, `else`, `allOf`, `anyOf`, `oneOf` or
  `not`: the strict form closes its target (§ 4.6).
- **Every key the analyser writes is named**, with its type. A key
  that may be null says so in its type. INV-1 holds this for the
  shapes the samples show.
- **Absent and null are different.** A key a shape always writes is in
  that shape's `required`, and null is then a value it may hold. A key
  a shape never writes is not named for that shape. A key a shape
  writes only sometimes is named, not required, and its `description`
  says when.
- **`frameledger`** is a string, the release's version. It is not a
  constant, so a later release's result still validates against an
  earlier file (§ 4.7).
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
- **Closed sets** are an `enum`, each under its own name in `$defs`,
  a command's own as `<command>_verdict` and `<command>_exit_code`,
  and a later value is a breaking change: the top-level
  `verdict`, per command (§ 4.4); each entry's own `verdict` (a
  measure's, a scene's, a variant's, a surveyed run's); `set`;
  `statistic`; `skip_reason`; and `exit_code`, per command, the codes
  its result can carry. `command` is a `const`, the file's own.
- **Open sets** are a string: warning codes, breach rules, `category`,
  `unit`, segment kinds and every name an engine chose. A script must
  ignore a value it does not know. `unit` is open because it follows
  from `category` (`compare.unit_of`).
- **A `description` is documentation.** Every named key has one, and
  an open set's lists today's values. No test holds a description
  true, and it is no part of the promise.

### 4.4 The shapes a file must tell apart

**What standard output holds.** Either one result object or nothing.
A command that reaches a verdict prints the object, and `"error"` is a
verdict: a file that cannot be read is exit 3 with the whole object. A
bad argument or a setup error prints nothing on standard output, and
is also exit 3, or 128 under `bisect` (FLED-0001 § 4.11, *A bad
argument*). No file describes
that case. A script tells the two apart by whether standard output is
empty.

**The top-level `verdict`, per command:**

| Command | `verdict` |
|---|---|
| `check` | `pass`, `fail`, `error` |
| `floor`, `budget`, `compare`, `alternate` | `pass`, `fail`, `inconclusive`, `error` |
| `survey` | `pass`, `fail`, `inconclusive` |
| `report` | `none`, `error` |
| `kit`, `import` | `none` |
| `bisect` | `good`, `bad`, `skip`, `stop` |
| `selftest` | `pass`, `fail` |

**The shapes of `result`.** Each file tells them apart with `if`/`then`
on `verdict` and on which keys `result` holds, so a validator needs
nothing but the result. Each `then` lists the keys that shape always
writes as `required`.

| Command | Shape | Told apart by |
|---|---|---|
| `check` | judged | `verdict` is not `error`; `files` |
| `check` | with `--expect` | `expect` is there |
| `check` | a file unread | `verdict` is `error`; `files` leaves the unread file out, and `expect` is absent |
| `report`, `floor`, `budget` | judged | `verdict` is not `error` |
| `report`, `floor`, `budget` | a file unread | `verdict` is `error`; `result` is `{}`, and its file requires no key of it |
| `compare` | plain | `measures` |
| `compare` | `--by-scene` | `scenes` |
| `compare` | `--base` with `--variant` | `variants` |
| `compare` | refused over blocking fields | `refused` with no `measures`; holds `runs`, `refused`, `all_frames` |
| `compare` | a `--measure` name no run has | `named_measures` with none of `measures`, `scenes`, `variants`; plain compare also holds `runs` |
| `compare` | a file unread | `result` is `{}` |
| `alternate` | each of `compare`'s shapes | as `compare`, with `commands`, `out`, `warmup` and a null `stopped` added; so a file unread holds those and `baseline`, never `{}` |
| `alternate` | stopped | `stopped` is not null; holds `commands`, `out`, `warmup`, `stopped`, `baseline` |
| `bisect` | judged | `verdict` is `good` or `bad` |
| `bisect` | skipped or stopped | `verdict` is `skip` or `stop`; `value` is null |
| `survey` | one | a run it could not judge has its figures null |
| `import`, `kit`, `selftest` | one | |

Every `compare` and `alternate` result but `{}` also holds `baseline`
(`cli._name_baseline`). `compare`'s refused, absent-name and
unread rows have the verdict `error`, and so has a `--by-scene` or
variants result in which nothing was judged; so `verdict` alone does
not pick the shape, and the keys in the last column do.

Those keys belong to their shapes. A release that adds one of them to
another shape makes a breaking change, since a pinned file would then
read the result as the wrong shape. A new shape with keys of its own is
an addition: no file ties a verdict to the absence of keys.

### 4.5 What changes in the output

- **`bisect`'s `runs` entries** gain `started_utc`, as `compare`'s
  have, and always carry `under_load`: a list of the names of the
  peaks over their limits, empty when there are none, as in `compare`.
  `bisect` writes a short entry for a run that could not be read, and
  for one that breaks the format. In a short entry both keys are null,
  as its `commit` is. So in `bisect`'s file the type of `under_load`
  is a list of strings or null, and in `compare`'s a list of strings.
- **`floor`'s `windows` entries** gain `frames`, holding the value
  `fps` holds: the count of frames in the window. `fps` stays, and its
  description calls it the older name.
- **`render.to_json` passes `allow_nan=False`.** A NaN or an infinity
  reaching it ends the command as a setup error does: a message on
  standard error, nothing on standard output, exit 3, or 128 under
  `bisect`. `json.dumps` raises `ValueError` for one, which
  `cli.main` does not catch today, so this needs its own handler.
- Nothing else. Key order, indentation and the escaping of non-ASCII
  characters stay as `render.to_json` writes them, and are no part of
  the promise: a script parses the JSON.

### 4.6 The samples, and the stricter test

```
tests/schema_samples.py      the shapes and the sample runs
tests/test_schemas.py
```

- **`SHAPES`** in `tests/schema_samples.py` lists every row of
  § 4.4's shapes table as a command and a shape name. The tests
  iterate it.
- **A sample** is a command line, the files it needs, and the entry
  of `SHAPES` it shows. Every entry has a sample, and between them the
  samples write every key the files name (INV-3). A key of a shared
  `$defs` entry is one key whichever file names it, so any command's
  sample may write it: `kit` has no warning to show.
- **A file never caps what a result may hold.** An unread file's
  `{}` is described by requiring nothing, not by forbidding keys, so
  a key added to it later still validates.
- **The strict form** of a file is made by the test. It closes each
  object once: a schema with `properties` gains
  `unevaluatedProperties: false` when it is the root, or is reached
  through `properties`, `additionalProperties`, `items`,
  `prefixItems` or a `$defs` entry. A schema under `if`, `then`,
  `else`, `allOf`, `anyOf`, `oneOf` or `not` is left open: the
  enclosing object's `unevaluatedProperties` already counts the keys a
  `then` names, and a closed `if` would never match a whole result.
- Each sample's output must validate against its file's strict form
  (INV-1), and the strict form must refuse a key added to any object
  of any sample's output (INV-11). So a key cannot reach a result
  without being described, while the published file stays open.

### 4.7 Frozen sets

```
tests/fixtures/schemas/
  <version>/<command>.schema.json   the files a release shipped
  <version>/keys.json               the keys each sample wrote
  SHA256SUMS                        one line per file above
scripts/freeze_schemas.py           writes <version>/
```

- **From 0.8.0, every release freezes its files.** `<version>` is
  `cli.VERSION`. `scripts/freeze_schemas.py` copies
  `src/frameledger/schemas/` to that folder, writes `keys.json`, and
  adds the lines to `SHA256SUMS`. It refuses to write over a folder
  that exists.
- **Freeze last.** The script is the last change before the tag, when
  the schemas and the samples are final.
- **`keys.json`** holds, for each sample by name, its command and every
  key path its output held when frozen, such as
  `result.runs[].started_utc`. A path counts as lost only where the
  object that held it is still there: a list now empty, or an object
  now null, is the run's data. A
  schema's open form cannot see a key go missing unless the key is
  `required`, and removing any key is breaking; this record can. A
  path stops at a map whose keys are data and at an engine-supplied
  value (§ 4.3), since what is inside follows the sample's input
  files.
- **The release cannot forget.** With `cli.VERSION` at 0.8.0 or later,
  the tests fail when `tests/fixtures/schemas/<VERSION>/` is absent,
  and `scripts/check-release.sh` fails when its schema files differ
  from the tree's. Neither asks it of an earlier version.
- **Later output is held to every frozen set** (INV-6), three ways.
  Each sample's output validates against its command's frozen file, in
  the open form: a changed type fails. Each sample a frozen
  `keys.json` names still exists and still writes every key path
  recorded for it: a removed or renamed key fails. Each closed set's
  `enum` in the tree's file holds no value the frozen file's `enum` of
  the same `$defs` name lacks, and is still an `enum` under that name:
  a new value fails, whether or not a sample writes it.
- **A deliberate break** is listed in `tests/test_schemas.py` as the
  frozen version, the command, where it is, and a sentence of the
  `CHANGELOG.md` entry that names it. Where is a key path, a `$defs`
  name with the new value, or a sample's name. A missing required key
  is reported at the key, not at the object that lacks it, so one
  listing covers it and nothing else. Only a listed failure is let
  off; another failure in the same command still fails. When a break
  is allowed is FLED-0042's.
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
  dialect, has no `$id`, closes no object, uses only the keywords the
  tests' walkers know, names no key under a conditional keyword that
  the plain `properties` beside it does not, and holds no `$ref` that
  leaves the file, has `properties` beside it, or sits directly under
  `if`, `then`, `else`, `allOf`, `anyOf`, `oneOf` or `not`.
  *Test:* `tests/test_schemas.py::test_each_file_is_a_schema` and
  `::test_a_conditional_names_no_key_of_its_own`.
  *Breaks when:* a file has a keyword the dialect's own schema
  refuses; `additionalProperties: false`; a `$ref` to another file.

- **INV-3** — Every entry of `SHAPES` has a sample, every sample's
  output has the shape it is listed under, and every key a
  file names is written by at least one sample, a shared definition's
  key by a sample of any command.
  *Test:* `tests/test_schemas.py::test_every_shape_has_a_sample`,
  `::test_each_sample_shows_its_shape` and
  `::test_samples_cover_the_schemas`.
  *Breaks when:* a file names a key no sample writes; an entry of
  `SHAPES` has no sample.

- **INV-4** — `schema COMMAND` prints the file's bytes and exits 0,
  from the tree and from `frameledger.pyz`, and the archive holds the
  same bytes under `schemas/`. A missing name, or one § 4.1 does not
  list, is exit 3 with nothing on standard output.
  *Test:* `tests/test_schemas.py::test_schema_command_prints_the_file`,
  `::test_schema_command_takes_a_name_not_a_path` and
  `::test_archive_holds_the_schemas`.
  *Breaks when:* the build leaves `schemas/` out of the `.pyz`; the
  command prints a re-serialised copy; `schema ../cli.py` prints a
  file.

- **INV-5** — A definition under `$defs` with the same name is the
  same in every file that has it.
  *Test:* `tests/test_schemas.py::test_shared_definitions_agree`.
  *Breaks when:* a warning's shape is corrected in one file only.

- **INV-6** — Against every folder under `tests/fixtures/schemas/`:
  every sample's output validates against its command's file; every
  sample `keys.json` names exists and writes every key path recorded
  for it; and no closed set in the tree's file holds a value the
  frozen one lacks. Only a failure listed as a deliberate break is let
  off.
  *Test:* `tests/test_schemas.py::test_output_matches_every_frozen_set`.
  Before 0.8.0 there is no folder, so the test freezes the tree's
  files to a temporary directory and then breaks them four ways: a
  key's type changed, an optional key removed from a sample's output,
  a value added to a closed set, and a second failure beside a listed
  one.
  *Breaks when:* a release removes or renames a key, changes its type,
  adds a value to a closed set, opens or renames one, or drops a
  sample.

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
  and its `frameledger` is `cli.VERSION`. The samples include each
  shape whose verdict is `error`. A bad argument prints nothing on
  standard output.
  *Test:* `tests/test_schemas.py::test_every_result_names_its_release`
  and `::test_a_bad_argument_prints_no_result`.
  *Breaks when:* an error path builds its result without
  `cli._result`; a setup error prints a partial object.

- **INV-9** — A result holding a NaN or an infinity, at any depth,
  ends the command with exit 3, or 128 under `bisect`, and nothing on
  standard output.
  *Test:* `tests/test_schemas.py::test_json_holds_no_nan`, which runs
  `cli.main` with a result patched to hold each.
  *Breaks when:* `allow_nan=False` is dropped; the `ValueError` is
  left to become a traceback, which is exit 1.

- **INV-10** — The name given to `schema` is user input. It selects
  from § 4.1's list and never reaches the file system as a path.
  *Test:* `tests/test_schemas.py::test_schema_command_takes_a_name_not_a_path`,
  its cases `../cli.py`, an absolute path and `check.schema.json`.
  *Breaks when:* the name is joined to the folder and opened.

- **INV-11** — The strict form refuses a key added to any object of
  any sample's output that its file describes, which the published
  form accepts; and, where two shapes differ in the keys they
  require, it refuses a sample's output given the other shape's
  `verdict`.
  *Test:* `tests/test_schemas.py::test_strict_form_refuses_an_unknown_key`
  and `::test_strict_form_refuses_another_shapes_verdict`.
  The fixture isolates the closing rule of § 4.6: a strict form that
  closed a `then`, or left a nested object open, passes INV-1 on a
  correct sample or fails it for every sample, and only this test
  tells a strict form that checks nothing from one that works.
  *Breaks when:* the strict pass skips an object; an `if` no longer
  matches, so its `then` never applies.

## 6. Failure modes

- **A file and the code disagree.** INV-1 fails, naming the sample and
  the key. The fix is to whichever is wrong against FLED-0001.
- **A shape no sample shows.** Its keys are unchecked. INV-3 catches a
  key the file names; a key the code writes only in a shape with no
  sample is caught by nothing (§ 10).
- **A release is cut without freezing.** INV-7 fails as soon as
  `cli.VERSION` is bumped.
- **A frozen file was wrong when it shipped.** It stays. If the code
  was right and the file wrong, later output fails INV-6 at that key,
  and the failure is listed with the changelog entry that says so.
- **`jsonschema` is not installed.** `tests/test_schemas.py` fails at
  import. The gate installs it, so only bare `pytest` meets this.
- **A NaN reaches `to_json`.** Exit 3 and a message on standard error,
  where today the output would be text no JSON parser reads.

## 7. Tests

`tests/test_schemas.py` holds every invariant. Each is seen to fail
first: INV-1 against a file with a key removed, INV-4 against a build
without `schemas/`, INV-9 against today's `cli.main`, and the `bisect`
and `floor` changes of § 4.5 against today's code through INV-1.

What they do not show: that a file's `description` is true, and that a
key's meaning is unchanged. A schema holds shape, not meaning.

## 8. Alternatives considered (and rejected)

- **Generate the files from the code.** A generated file agrees with
  the code by construction, so it cannot catch the code changing.
- **Closed published files.** A script validating a later release's
  output against its pinned file would fail on every added key, which
  `versioning-overrides.md` says is not a break.
- **A `--schema COMMAND` flag.** The options before the command take
  no value, so the first argument without a dash is the command
  (FLED-0001 § 4.11, `cli._command`). `--schema bisect` would run
  `bisect`.
- **A hand-written checker in the tests.** No new pin, but it would
  prove the files to our reading of the dialect, not to the tool an
  engine would use.
- **A schema number in the result.** One more value to keep true,
  beside a version the result already carries.
- **Rename `floor`'s `fps`.** It breaks whoever reads it, for a name.
  `frames` is added beside it instead.
- **List a deliberate break by command alone.** One listed break
  would let every later break to that command through.

## 9. Out of scope

- When a breaking change is allowed and how it is announced, and when
  `floor`'s `fps` may go — tracked by FLED-0042.
- A schema for the run file, the budget file and the baseline file —
  FLED-0040 § 4.8 freezes files instead; deferred; not yet queued.
- The text and Markdown output — not a surface
  (`versioning-overrides.md` § Not surfaces).

## 10. What checks this

| Rule | What catches a breach |
|------|----------------------|
| INV-1 | Partial: `tests/test_schemas.py::test_output_matches_its_schema`, for the shapes the samples show; a key written only in a shape with no sample has **nothing** |
| INV-2 | `tests/test_schemas.py::test_each_file_is_a_schema` and `::test_a_conditional_names_no_key_of_its_own` |
| INV-3 | Partial: `tests/test_schemas.py::test_every_shape_has_a_sample`, `::test_each_sample_shows_its_shape`, and `::test_samples_cover_the_schemas` catches a named key no sample writes; that `SHAPES` and § 4.4's table list every shape the code has is caught only by the engines' review |
| INV-4 | Partial: `tests/test_schemas.py::test_schema_command_prints_the_file`, `::test_schema_command_takes_a_name_not_a_path` and `::test_archive_holds_the_schemas`; `.github/workflows/ci.yml` runs the tests on Linux and macOS, so a changed line end on Windows has **nothing** |
| INV-5 | `tests/test_schemas.py::test_shared_definitions_agree` |
| INV-6 | Partial: `tests/test_schemas.py::test_output_matches_every_frozen_set`; a key pointed at another, wider closed set is caught only where a sample writes the new value; an object that loses its only key leaves no sibling to show it was there, so that loss is caught only where the frozen file requires the key; a failure wrongly listed as a deliberate break is caught only by the engines' code review |
| INV-7 | Partial: `tests/test_schemas.py::test_frozen_sets_unchanged`, `::test_this_version_is_frozen` and `::test_freeze_refuses_an_existing_folder`; a commit that edits a frozen file and `SHA256SUMS` together is caught only by the engines' code review |
| INV-8 | `tests/test_schemas.py::test_every_result_names_its_release` and `::test_a_bad_argument_prints_no_result` |
| INV-9 | `tests/test_schemas.py::test_json_holds_no_nan` |
| INV-10 | `tests/test_schemas.py::test_schema_command_takes_a_name_not_a_path` |
| INV-11 | Partial: `tests/test_schemas.py::test_strict_form_refuses_an_unknown_key` and `::test_strict_form_refuses_another_shapes_verdict`; `check`'s two shapes hold the same keys, a whole result under the verdict `error` passes `report`'s, `floor`'s and `budget`'s files, and a `--by-scene` or variants result may carry any verdict, so those have **nothing** |
| § 4.4 each shape's required keys | `tests/test_schemas.py::test_each_shape_requires_its_keys` |
| § 4.7 a deliberate break names its changelog entry | `tests/test_schemas.py::test_each_deliberate_break_names_its_changelog_entry` |
| § 4.3 a `description` is true | **nothing** — read by the engines when a file changes |
| § 4.3 which sets are closed | **nothing** — a set closed or opened wrongly is judged in review |
| § 4.7 the frozen folder equals the tree's files at release | `scripts/check-release.sh` |

## 11. Cross-doc impact

- `docs/specs/FLED-0001-run-file-format.md` — § 4.7 gains the `schema`
  command; § 4.8 points here for each result's types, and its `floor`
  block gains `frames`; § 4.11's result block gains `started_utc` and
  `under_load`, with the rule for a short entry.
- `docs/standards/versioning-overrides.md` § Breaking surfaces — the
  commands bullet covers every command, `import` and `kit` among
  them, and points here for what holds the JSON result. *Adding is not
  breaking* gains the other half: a new value in a closed set is
  breaking, and § 4.3 here names the closed sets.
- `README.md` — where a script's author finds the schemas, and that
  0.7.0 and earlier have none.
- `CHANGELOG.md` — the files, the `schema` command, `bisect`'s two
  keys and `floor`'s `frames`.
- `CLAUDE.md` § Build and test — bare `pytest` needs `jsonschema`.
- `docs/design.md` § The stack, and what it rules out — the
  test-only dependency.

## 12. Cold-eyes loop log

Rows live in `../reviews/FLED-0041-json-result-schemas-loop-log.md`.

## 13. Open questions

None.
