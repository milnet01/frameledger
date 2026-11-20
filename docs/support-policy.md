# Support and deprecation policy — frameledger

**Purpose: so that whoever pins a release knows which release gets
fixes, what it runs on, and how much warning comes before something
they use stops working.**

This file owns four things: which release gets fixes, what frameledger
runs on, when a breaking change is allowed, and how a thing is retired.
What counts as breaking is
[`versioning-overrides.md` § Breaking surfaces](standards/versioning-overrides.md#breaking-surfaces).

## Which release gets fixes

- **Only the newest release.** A fix ships in the next release. No
  older release is patched.
- **An older release stays published.** Its archive and SHA256 stay on
  the releases page, so a pin keeps resolving.

## What it runs on

- **Python.** The floor is Python 3.10
  ([ADR-0001](decisions/ADR-0001-analyser-language.md)). The gate runs
  on the floor only, the version `scripts/local-ci.sh` pins as
  `PYTHON_VERSION`. A failure on a newer Python is a bug, and its fix
  ships in the next release.
- **Systems.** Linux, Windows and macOS. `.github/workflows/ci.yml`
  runs the gate on Linux and macOS. `.github/workflows/release.yml`
  builds each release and runs its `--selftest` on Linux and Windows.
  No version of a system is promised beyond the ones those runners
  give.
- **The writer.** `include/frameledger.h` compiles as C and as C++17
  under the flags `tests/writer/test_compile.sh` uses.

**For how long.** No end date is set for any of these. Dropping one is
a breaking change, so it follows the two sections below.

## When a breaking change is allowed

**The release it may ship in.** Before 1.0.0, the next milestone's
MINOR, never a PATCH
([`versioning-overrides.md` § One MINOR per milestone](standards/versioning-overrides.md#one-minor-per-milestone)).
From 1.0.0, a MAJOR only (`~/.claude/standards/versioning.md` § 2).

**What it needs first.** All three:

1. **A warning.** An earlier release deprecated the thing, as § How a
   thing is retired says. A PATCH of the breaking release's own MINOR
   is not earlier.
2. **A way across.** The deprecating release already holds the
   replacement, or its `CHANGELOG.md` entry says there is none.
3. **The three engines' agreement**: Vestige, UT Ants and DOOM Ants.

Nothing checks these three. The release's reviewers do.

**One exception.** A security hole that cannot be closed without a
break skips the warning. It keeps the release level and the
`CHANGELOG.md` entry.

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
  the verdict and the exit code do not change. Its `--help` text says
  it is deprecated.
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

## Deprecated now

| What | Since | Use | May go in |
|---|---|---|---|
| `fps` in each of `floor --json`'s `windows` | 0.8.0 | `frames`, which holds the same count | 2.0.0 or later |
