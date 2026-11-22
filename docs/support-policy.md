# Support and deprecation policy — frameledger

**Purpose: so that whoever pins a release knows which release gets
fixes, what it runs on, and how much warning comes before something
they use stops working.**

This file owns four things: which release gets fixes, what frameledger
runs on, when a breaking change is allowed, and how a thing is retired.
What counts as breaking is
[`versioning-overrides.md` § Breaking surfaces](standards/versioning-overrides.md#breaking-surfaces).

## Which release gets fixes

- **Only the newest release**, before 1.0.0 as after. A fix ships in
  the next release. No older release is patched.
- **So a fix can bring a removal with it.** Once a MAJOR is released,
  the one before it gets no fix, a security fix included. Whoever
  wants the fix takes that MAJOR's removals too.
- **An older release is never unpublished.** Its archive and its
  notes, which hold the SHA256, stay on the releases page, so a pin
  keeps resolving.
- **`CHANGELOG.md` is where every deprecation, removal and security
  fix is announced, and the only place.** No notice is sent.
  `scripts/release_notes.py` prints a release's section as its notes.
- **Where to report a bug or a security hole**: a bug in an issue, as
  [`CONTRIBUTING.md`](../CONTRIBUTING.md) says, and a security hole as
  [`SECURITY.md`](../SECURITY.md) says.

## What it runs on

- **Python.** The floor is Python 3.10
  ([ADR-0001](decisions/ADR-0001-analyser-language.md)). The gate runs
  on the floor, the version `scripts/local-ci.sh` pins as
  `PYTHON_VERSION`. Its tests and `--selftest` also run on the newest
  released Python, pinned there as `PYTHON_NEWEST_VERSION`. Versions
  between the two are not tested. A failure on any version from the
  floor up is a bug, fixed once it is reported, and the fix ships in
  the next release.
- **Systems.** Linux, Windows and macOS. `.github/workflows/ci.yml`
  runs the gate on Linux and macOS. `.github/workflows/release.yml`
  builds each release and runs its `--selftest` on Linux and Windows.
  Both name their runners `-latest`, which GitHub moves, so no
  version of a system is promised.
- **The writer.** `include/frameledger.h` compiles as C99 and as
  C++17, under the compilers and flags
  `tests/writer/test_compile.sh` names.

**For how long.** The Python floor stays 3.10 until 2.0.0 at the
earliest. No end date is set for a system or for the writer's
languages. Dropping any of these is a breaking change, so it follows
the two sections below.

## When a breaking change is allowed

**The release it may ship in.** Before 1.0.0, the next milestone's
MINOR, never a PATCH
([`versioning-overrides.md` § One MINOR per milestone](standards/versioning-overrides.md#one-minor-per-milestone)).
From 1.0.0, a MAJOR only (`~/.claude/standards/versioning.md` § 2).

**What it needs first.** All three:

1. **A warning.** An earlier MINOR or MAJOR deprecated the thing, as
   § How a thing is retired says. Its `CHANGELOG.md` entry named the
   earliest release that may remove it, and that binds: no release
   before it removes the thing.
2. **A way across.** The deprecating release already holds the
   replacement, or its `CHANGELOG.md` entry says there is none.
3. **The three engines' agreement**: Vestige, UT Ants and DOOM Ants.
   No other user's agreement is asked. The break's `ROADMAP.md` item
   records each engine's answer.
   Silence is not agreement. Where an engine does not answer, the
   owner decides.

Nothing checks these three. The release's reviewers do.

**One exception.** A security hole that cannot be closed without a
break skips the warning. It keeps the release level and the
`CHANGELOG.md` entry, and it does not reach the two things below.

**What no release breaks.**

- A run, budget or baseline file an earlier release read
  ([FLED-0040 § 4.6](specs/FLED-0040-format-stability-promise.md#46-how-long-an-older-schema-is-read)).
- A frozen schema set, which is never edited
  ([FLED-0041 § 4.7](specs/FLED-0041-json-result-schemas.md#47-frozen-sets)).

## How a thing is retired

**The deprecating release** is a MINOR
(`~/.claude/standards/versioning.md` § 2). It does all of these that
apply, and the thing keeps working unchanged:

- **`CHANGELOG.md`** gains a `### Deprecated` entry. It names the
  thing, its replacement, and the earliest release that may remove it.
- **A flag or a command** prints one line on standard error when used,
  opening `frameledger:` and naming the replacement. Standard output,
  the verdict and the exit code do not change. A script that merges
  standard error into standard output will read the line as part of
  the result. Its `--help` text says it is deprecated.
- **A key in a JSON result** has `"deprecated": true` in its schema,
  and its `description` names the replacement.
- **A header field, or a file's field,** is marked in the spec that
  defines it. The reader adds no warning for it.
- **A function, type or limit of the writer** is marked in a comment
  in `include/frameledger.h`. It is never marked with an attribute
  that makes a compiler warn: an engine building with warnings as
  errors would break on it.
- **A Python version or a system** is named in the entry alone.

**The removing release** names the removal under `### Removed`. A
removed JSON key or closed-set value is also listed as a deliberate
break in `tests/test_schemas.py`
([FLED-0041 § 4.7](specs/FLED-0041-json-result-schemas.md#47-frozen-sets)),
which fails on a removal that is not listed.

Nothing checks the standard-error line or the `--help` text until a
flag is first deprecated. That change brings its test.
`tests/test_schemas.py::test_the_policy_lists_every_deprecated_key`
holds a JSON key's schema mark and the table below to each other.

## Deprecated now

| What | Since | Use | May go in |
|---|---|---|---|
| `fps` in each of `floor --json`'s `windows` | 0.8.0 | `frames`, which holds the same count | 2.0.0 or later |
