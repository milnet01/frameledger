<!-- ants-roadmap-format: 1 -->
<!-- Generated from the Ants Terminal roadmap store. Edit it with roadmap_log; hand edits are discarded by the next write. -->
<!-- ants-roadmap-id-high-water: FLED=14 -->
# frameledger — Roadmap

> What is planned, in progress and shipped. [CHANGELOG.md](CHANGELOG.md)
> is the user-facing record of what shipped; released items stay here and
> flip to ✅.
>
> **Format:** `~/.claude/standards/roadmap-format.md`. Theme emojis
> (§ 3.4), priority bands (§ 3.5.2) and the full bullet field set (§ 3.5)
> are defined there and deliberately not restated here.

**Legend**

- ✅ Done · 🚧 In progress · 📋 Planned · 💭 Considered
- 🚫 Dropped (closed, not done)

## 0.1.0 — one run, read and checked

The first release Vestige needs (its goal order, 2026-10-24): the
format, the check command, the single-run report and the floor check.
Engines can write files and pin a release.

- ✅ [FLED-0001] **Format and command spec.**
  The contract every writer and the analyser are built to: run header,
  static line, rows, close record, segment kinds, the analyser's
  commands and flags, the budget file and the JSON result. Written with
  write-spec; reviewed by the three engine sessions. Claims S7 (a
  writer from the spec alone) and S6's schema version. Inputs:
  docs/reviews/2026-10-24-discovery-customer-answers.md and
  docs/reviews/2026-10-24-design-customer-answers.md.
  Accepted 2026-10-24: docs/specs/FLED-0001-run-file-format.md, agreed
  by all three engine sessions at 23a8605.
  **Layman:** Writes down exactly what a run file looks like, so every engine writes the same thing.
  Kind: doc.
  Source: design-2026-10-24.

- 📋 [FLED-0002] **Read and check a run file.**
  ledger.py reads one file into a Run and lists every breach; the
  check command reports them with exit codes; cli.py's exit ladder;
  selftest.py's first sample files. Reads older schema versions and
  Windows files (CRLF, Windows paths). Claims S18, S11's file half and
  S6's reading half. Overlaps every later item in cli.py.
  **Layman:** The tool can open a run file and say whether it is valid.
  Kind: implement.
  Source: design-2026-10-24.
  Blocked-by: FLED-0001.

- 📋 [FLED-0003] **Single-run report.**
  stats.py and run_report.py: cost ranking per pass and per segment
  kind, bound-by share (or "does not apply" when not pipelined), GPU
  rows joined to their submitting frame, worst frames with their top
  pass. render.py: plain sentences first, tables within 100 columns,
  JSON. Claims S2, S3 and S13. Overlaps the floor check, pass budgets
  and pacing in run_report.py.
  **Layman:** One command says where a run's frame time went and which frames were worst.
  Kind: implement.
  Source: design-2026-10-24.
  Blocked-by: FLED-0002.

- 📋 [FLED-0004] **Floor check.**
  S8: one-second windows (frames completed over the window's length)
  and single frames against a per-run budget, each switchable and
  reported apart; warm-up; inconclusive when rows were dropped or the
  run has no close record. Claims S8.
  **Layman:** Pass or fail: did the run hold 60 FPS every second, and did any single frame take too long?
  Kind: implement.
  Source: design-2026-10-24.
  Blocked-by: FLED-0003.

- 📋 [FLED-0005] **Trust warnings.**
  trust.py's run half of S5: Debug builds, software renderers, too few
  frames, high CPU or GPU load, settling below the header's need, a
  camera cut inside a measured stretch, dropped rows, missing timings
  counted as missing. Claims S5's warning half.
  **Layman:** Warns when a run's numbers should not be trusted.
  Kind: implement.
  Source: design-2026-10-24.
  Blocked-by: FLED-0002.

- 📋 [FLED-0006] **Optional C writer header.**
  include/frameledger.h: C99 and C++17 common subset, no allocation,
  engine-owned buffer, rows dropped and counted when full, the largest
  row size stated, locale-free number formatting. Compile tests as C
  and C++ under GCC, Clang and mingw-w64 at -Wall -Wextra -Wpedantic
  -Werror, output run through check. Vestige and UT Ants compile it
  with MSVC. Claims S10.
  **Layman:** A small file engines can include to write run files without writing their own.
  Kind: implement.
  Source: design-2026-10-24.
  Blocked-by: FLED-0001.

- 📋 [FLED-0007] **First release archive.**
  frameledger.pyz and include/frameledger.h in one archive attached to a
  tagged release, its SHA256 in the notes; CHANGELOG naming every
  format change. Windows runs of --selftest by Vestige and UT Ants.
  Claims S6's pin half and S11's Windows half.
  **Layman:** A downloadable, pinned version the three engines can use.
  Kind: release.
  Source: design-2026-10-24.
  Blocked-by: FLED-0003, FLED-0004, FLED-0005, FLED-0006.

## 0.2.0 — two builds compared

Compare, bisect, pass budgets and pacing: whether a change made an

engine faster, and which pass it changed.

- 📋 [FLED-0008] **Compare labelled sets of runs.**
  compare.py: interleaved labelled sets (old-1, new-1, old-2, new-2),
  each pass judged by its own spread, a verdict on the exit ladder;
  trust.py's comparability refusals with per-field overrides named,
  with their reasons, in the opening sentence; static-line diff beside
  the pass comparison. Claims S4, S16 and S5's refusal half.
  **Layman:** Says whether a change made the engine faster, slower or neither, pass by pass.
  Kind: implement.
  Source: design-2026-10-24.
  Blocked-by: FLED-0003, FLED-0005.

- 📋 [FLED-0009] **Bisect verdict mode.**
  One measure against a threshold or two reference runs; 0 good, 1 bad,
  125 skip, 128 stop; a dry run printing the verdict for a value.
  Claims S17. Overlaps the compare item in compare.py.
  **Layman:** Lets git bisect find the change that made a pass slower.
  Kind: implement.
  Source: design-2026-10-24.
  Blocked-by: FLED-0008.

- 📋 [FLED-0010] **Pass budgets.**
  A budget file naming passes, each with a statistic (median or p99)
  and a limit; names each pass over budget and exits non-zero. Claims
  S12.
  **Layman:** Gives each drawing step a time budget and names the one that goes over.
  Kind: implement.
  Source: design-2026-10-24.
  Blocked-by: FLED-0003.

- 📋 [FLED-0011] **Frame pacing figure.**
  A frame-to-frame variation figure beside the 1% low. Claims S14.
  **Layman:** Shows judder even when the frame rate passes.
  Kind: implement.
  Source: design-2026-10-24.
  Blocked-by: FLED-0003.

## 0.3.0 — many runs surveyed

Many runs at once: one per map, ranked, and one build's survey against

another's.

- 📋 [FLED-0012] **Survey ranking.**
  survey.py: many runs ranked by worst-segment median and p99, those
  over budget flagged with their costliest pass, per-effect ext rows
  as a ranked table. A survey of about a million rows in under a
  minute. Claims S9 and S19.
  **Layman:** Ranks every map's run and flags the slow ones.
  Kind: implement.
  Source: design-2026-10-24.
  Blocked-by: FLED-0003.

- 📋 [FLED-0013] **Survey against survey.**
  Two builds' surveys, per run and per pass; flags each pass that got
  slower by more than its run-to-run spread. Claims S15. Overlaps the
  compare item in compare.py.
  **Layman:** Catches a map that got slower between two builds.
  Kind: implement.
  Source: design-2026-10-24.
  Blocked-by: FLED-0008, FLED-0012.

- 📋 [FLED-0014] **Each engine finds and fixes a bottleneck with it.**
  Vestige (3D_E-0786), UT Ants (UTA-0437) and DOOM Ants each write run
  files, and each finds a bottleneck from a report and fixes it. UT
  Ants' c80d41d/d9009b1 pair is a ready known-slowdown case. At least
  one engine writes from the spec alone. Claims S1, and S7 in use.
  **Layman:** The real test: each game finds something slow with this tool and fixes it.
  Kind: investigate.
  Source: design-2026-10-24.
  Blocked-by: FLED-0007.
