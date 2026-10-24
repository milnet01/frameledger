# Design — customer sessions' answers, 2026-10-24

A dated record. Each engine session was sent the design draft
(`docs/design.md`, ADR-0001, ADR-0002) to agree or correct, with
questions on the Python floor, how it will pin a release, and how the
writer is compiled with its toolchain.

## UT Ants (ut-ants-aa)

Agrees, assuming the cold review changes none of the parts.

- Corrected its discovery answer D: its build sets no warnings-as-
  errors flags. The header requirement stands; UT Ants turns the strict
  flags on for the header's own translation unit.
- Python 3.13 on its Windows test machine and on this machine.
- Pins a release-asset URL plus SHA256. Prefers the `.pyz`, run as
  `python3 -I <path>/frameledger.pyz`. Asks that the header ship in
  the same archive, under one hash.
- Its push gate builds with MSVC on every push. It will compile a test
  translation unit including the header as C++23 at `/W4 /WX` (MSVC)
  and `-Wall -Wextra -Werror` (GCC, Clang) for each release it pins,
  report a failure, and stay on the previous pin.

## DOOM Ants (doom-ants-97)

Agrees, with four corrections. Checked against DOOM's `Makefile`,
`packaging/ci-local.sh`, `packaging/ci-deps.txt` and
`.github/workflows/build.yml`.

- Python: its pre-push mirror runs in a bare Ubuntu 24.04 image with no
  Python today. DOOM will add `python3` to `ci-deps.txt` (3.12). Linux
  only; DOOM does not run the analyser on Windows.
- Pinning: archive URL plus SHA256, no submodules. Prefers the `.pyz`.
  Asks for the `.pyz` and the header in one archive. Will probably
  vendor the header; its build must not need the network.
- **a.** ADR-0002: the engine is C built as `-std=gnu11 -Wall`; the
  back-end is C++ built as `-std=c++23 -Wall`. The decision stands.
- **b.** DOOM's Windows build uses mingw-w64 GCC and G++ 13, not MSVC.
  Add them, as C and as C++, to the writer's compile tests. This
  machine can run them.
- **c.** The writer formats numbers too. The `.`-decimal rule must bind
  the writer: integer times, or decimals formatted without
  locale-dependent `printf`.
- **d.** Say who owns the writer's buffer (handed in by the caller, or
  allocated once at open) and what happens when it fills (flush outside
  the frame, or drop rows and count the drops). Silent loss is not
  acceptable. Estimates a few hundred thousand rows per run.

Repeated, for the format spec: microsecond resolution; a per-frame
sim-tic flag; a warm-up or camera-cut marker with a trust warning;
render scale, tier and ray tracing on/off block a compare; display kind
in the header.

## Vestige (vestige-5e)

Agrees; every Vestige MUST is covered.

- Python: Linux CI 3.12, local CI 3.13.16. The Windows CI runner's
  default version is unverified; Vestige will pin 3.12 there with
  `actions/setup-python`.
- Pins a release-asset URL plus SHA256 through FetchContent. Prefers
  the `.pyz`; the package directory is not needed.
- MSVC: its Windows CI builds with MSVC on every push. It will add a
  ctest entry compiling the header in one C++17 file at `/W4 /WX`, and
  report a failure. Asked to be named beside UT Ants in ADR-0002.
- **a.** On Windows the command is usually `python` or `py`; say so.
- **b.** Add `-Wpedantic` to the writer's C++ compile test.

## Applied

All corrections above went into `docs/design.md`, ADR-0001 and
ADR-0002 on 2026-10-24. The writer takes a buffer from the engine and
never allocates; a full buffer drops and counts rows.

## Second round — the changes since agreement

Each session read the diff from 56287aa (the cold review's eight fixes
and the corrections above) and answered six choices: `check` exits 1
for a nonconforming file; a refused compare exits 3; bisect exit codes;
the format spec also fixes the commands, budget file and JSON; the
writer's buffer; bare-name imports.

- **Vestige** — agreed 1–4 and 6. Changed 5: a run with dropped rows
  makes S8's checks, and compares using them, inconclusive, said in the
  opening sentence. Asked that the S1 placement sentence be plain.
- **UT Ants** — agreed 1, 2, 4 and 5. Changed 3: a missing or broken
  run file of the commit under test skips (125); configuration errors
  and a broken reference file stop the bisect (128). Changed 6: a test
  fails when a module's name matches a standard-library module.
- **DOOM Ants** — agreed all six. Asked that the header state the most
  bytes one row can take, so the buffer is sized once.

All four changes went into `docs/design.md`.

Confirmed: UT Ants and DOOM Ants agreed the result. DOOM Ants, for the
format spec: a run file with no close record (the engine crashed or was
killed) has no drop count, so the analyser treats it as inconclusive at
least, never a pass.
