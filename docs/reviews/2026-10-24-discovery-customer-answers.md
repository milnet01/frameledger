# Discovery — customer sessions' answers, 2026-10-24

A dated record. The user asked that each discovery "never" and the
signs of success be checked with the three engine sessions before the
discovery is agreed. Each was sent the same four questions:

1. Should frameledger ship a capture or writer library, or never
   capture inside an engine?
2. Analyser language: Python 3 standard library, or C/C++?
3. Is "points at the pass and frames; a profiler explains why" enough?
4. What in the problem, audience or signs is wrong or missing?

## Vestige (vestige-6f)

1. Keep "never captures". Timing is API-specific (GL timer queries in
   Vestige, Vulkan timestamps in UT Ants and DOOM Ants). Wants an
   optional writer: format only, no timing, one C-compatible header
   usable from C, C++17 and C++23. Must stay optional, because S7
   requires spec-only writers to be accepted.
2. Python 3 standard library. Needs a command-line report, an exit
   code for gates, and a `--selftest` that runs in CI with no GPU. Its
   CI already runs Python tools through ctest. No embedding. Estimates
   a 60 s flythrough at a few hundred thousand rows. Must run on
   Windows.
3. Enough.
4. Missing:
   - An absolute floor gate: every one-second window after a warm-up
     at or above a set FPS, non-zero exit on any failing window.
   - GPU rows arrive frames late. The format must not require rows
     grouped or ordered by frame; join on `(run_id, frame)`.
   - A frame with no GPU result must be expressible, and counted as
     missing, never as 0 ms.
   - The default report opens with one plain sentence before the
     tables.

## UT Ants (ut-ants-aa)

1. Keep capture in the engine: urender stamps every step with Vulkan
   timestamps, and ut-bench owns the repeatable run. Wants an optional
   header-only C++ writer (run header, row formatting, escaping, schema
   constant), no timing, fetched at a pinned tag. Without it, UT Ants
   writes its own from the spec.
2. Python 3 standard library, run as `python3 -I`. Needs a
   command-line report and A/B verdicts on this machine. No embedding,
   no GitHub CI (no GPU there). Estimates one run at 5–10k rows and a
   127-map survey at about 1M rows in total.
3. Enough. Asks that `ext.<engine>` rows and the static line carry
   per-pipeline register and wave counts, and later per-effect costs
   (UTA-0436). The analyser prints them beside the ranking without
   interpreting them.
4. Missing:
   - Many runs at once: rank N runs (one per map) by floor in one
     command, flagging those over budget.
   - Compare takes labelled sets of interleaved files (old-1, new-1,
     old-2, new-2), not one baseline. Medians drift about 2 ms between
     runs.
   - Input identity is content: several named inputs, each with a
     hash (camera file and baked map).
   - Report per segment kind, never pooled only. Still views and moves
     behave differently.
   - Bound-by needs a "not applicable" verdict when `pipelined` is
     false, instead of a misleading share.
   - A ready S1/S4 case: commit c80d41d (UTA-0387) made
     DM-ArchNemesis's opaque pass about 3 ms slower; d9009b1 fixes it.
     Usable once ut-bench writes the file (UTA-0437).
   - Accept files from Windows: CRLF line endings and Windows paths.

## DOOM Ants (doom-ants-26)

Adopting frameledger, and parking or reshaping DOOM-0431, are the
user's decisions. The session recommends adoption.

1. An optional single-header C writer helps, usable from the C engine
   and the C++ Vulkan back-end. Conditions: no dependencies; no
   allocation or file I/O per frame (buffer in memory, write at the end
   or on a background flush); timestamps passed in by the engine. GPU
   timing stays in the engine.
2. Python 3 standard library. Needs a command-line report and a gate
   for its local pre-push pipeline (in a container) and CI. No
   embedding. Estimates a few hundred thousand rows per run.
3. Enough. RenderDoc and AMD's Radeon GPU Profiler explain why.
4. Missing:
   - Microsecond resolution: frames run at hundreds of FPS.
   - The game ticks at 35 Hz. A per-frame "sim tic ran" flag or row,
     so spikes line up with tic frames.
   - A warm-up or "after camera cut" marker, and a trust warning when
     one falls inside a run. Ray-traced frames cost more after a cut
     or a level load.
   - Render scale, tier and ray tracing on/off block a compare.
   - The header records the display kind (private headless display or
     on-screen), and runs of different kinds are never compared.
   - DOOM-0431 is parked: spec and plan written, nothing built. The
     session suggests replacing it with a frameledger writer. The
     user's call.

## Agreement round

Each session was sent the revised discovery and asked to agree S1–S11
and confirm each *never* line on its own.

- **Vestige** — agreed S1–S11 and confirmed N1–N4 one by one. Asked
  that S8 define a window's frame rate; that went into S8. Confirmed the
  merged S8.
- **UT Ants** — agreed S1–S7 and S9–S11 and confirmed N1–N4 one by
  one. Asked that S8 judge single frames, not a window mean alone, and
  that the budget be set per run; both went into S8. Accepted one C
  header if it compiles warning-free as C++ under GCC 14, Clang 19 and
  MSVC with warnings as errors, and needs no build step. Confirmed the
  merged S8.
- **DOOM Ants** — agreed S1–S11 and the merged S8, and confirmed N1–N4
  one by one. Its user decided on 2026-10-24 that DOOM Ants adopts
  frameledger and DOOM-0431 stays parked. Corrected the goal addendum:
  the ray-traced view runs at 30–50 FPS on the RX 6600 at 50% render
  scale (DOOM-0279), so 60 is its target, not only a floor. Asked for
  three new signs, which became S12–S14:
  - a per-pass budget check that names the pass over budget and exits
    non-zero (DOOM-0279);
  - with frames in flight (DOOM-0190), GPU rows attributed to the
    submitting frame and the bound-by share still given;
  - a frame-to-frame variation figure beside the 1% low (DOOM-0359,
    DOOM-0277).
  Confirmed S12–S14 as worded.

## UT Ants' full requirements (ut-ants-aa)

Sent at UT Ants' user's request, 2026-10-24. Goal: every map holds
60 FPS at 4K High on an RX 6600 with headroom for gameplay, and no
change silently costs frame time. Placed as follows.

- Survey ranking naming each flagged map's costliest pass — S9.
- Survey-against-survey regression report — S15. Motivating case: a
  3 ms opaque-pass regression on DM-ArchNemesis, live from 2026-10-21
  (c80d41d), unflagged for three days.
- Compare per pass, each by its own spread — S16. Motivating case: one
  binary's frame median swung between 32.6 and 24.9 ms across two reps
  while its opaque pass held between 18.2 and 18.7 ms.
- Interleaved A/B over labelled file sets — S4.
- Input-identity refusal overridable per field with a printed reason —
  S5.
- Bisect verdict mode with a dry run — S17. Motivating case: a
  hand-written bisect script's inverted verdict marked five slow
  commits good.
- Per-run budget — S8. Segment kinds apart — S2.
- Plain sentences first, no meaning by colour alone, machine-readable
  output — Who it is for, S2.
- Validator command with exit codes — S18.
- About a million rows analysed in under a minute — S19.
- Old files keep analysing — S6, with release notes naming every
  format change.
- A permissive licence — met: the repository is MIT.

## Vestige's full requirements (vestige-6f)

Sent at the owner's request, 2026-10-24, for the design and the spec.
MUST means Vestige cannot adopt without it.

- **Goal order** (owner, 2026-10-24): hold 60 FPS per one-second
  window on the meadow flythrough first, then remove single frames over
  16.67 ms. The first release Vestige needs is S2, S3 and S8; S4 and
  S12 can follow. Vestige's gate turns on S8's per-frame failure once
  its window floor holds (3D_E-0795).
- **Integration, MUST:** tagged releases, each with a downloadable
  archive and a stable SHA256, pinned through CMake FetchContent; a
  CHANGELOG flagging breaking changes, plus a schema version in the
  header; an MIT-compatible licence; a `--selftest` with no GPU and no
  network that runs in seconds as a ctest entry; exit codes 0 pass,
  1 regression or floor failure, 2 inconclusive, 3 config or file
  error; works with CMake 3.21 if any CMake ships. Prefers a plain
  Python script and a header, so no CMake ships.
- **Integration, SHOULD:** a migration path or converter from
  `perf_gate.py` baseline JSON.
- **Writer, MUST:** compiles as C++17 under GCC and Clang with
  `-Wall -Wextra -Wpedantic`, and under MSVC, with no warnings; no
  designated initialisers, VLAs or `restrict`; no allocation or file
  write per row in the frame loop; escapes names with commas, quotes or
  non-ASCII; writes ms with 3 decimals whatever the process locale.
- **Writer, SHOULD:** say which thread may call it.
- **Format, MUST:** late and out-of-order GPU rows; missing GPU
  results; segment kind `leg:N`; `frame/wall` is real elapsed time, not
  a fixed simulation step.
- **Format, SHOULD:** `ext.vestige` per-frame rows and static facts
  printed beside the ranking; GPU busy % at start and end in the
  header, with a warning when high; the device string carries
  `GL_RENDERER`, so a software renderer is recognised.
- **Report, MUST:** plain opening sentence; no meaning by colour alone;
  tables no wider than about 100 columns; no dense ASCII art; JSON
  output alongside the text.
- **Report, SHOULD:** each worst frame names its top-cost pass.
- **Process, MUST:** the format spec before anything is built to it;
  release notes for each version.
- **Vestige's side:** 3D_E-0786 replaces `profile_log.cpp`'s averaged
  CSV with per-frame rows. `fps_floor.py` then gives way to the S8
  check, and `perf_gate.py` to the compare.

## Final round

Each session was asked to agree the audience change, S5's per-field
override, S9's costliest pass and S15–S19.

- **DOOM Ants** — agreed each, on condition that every override and its
  reason appear in the report's opening sentence. That went into S5,
  and DOOM Ants accepted the wording.
- **Vestige** — agreed each, including DOOM Ants' S5 ending.
- **UT Ants** — agreed each, including DOOM Ants' S5 ending.

Discovery was marked agreed on 2026-10-24.

## Held for the format and analyser spec

Raised in these answers and placed in the spec rather than discovery.

- Rows need not be grouped or ordered by frame; the analyser joins on
  `(run_id, frame)` (Vestige).
- A frame with no GPU result is expressible and counted as missing
  (Vestige).
- S8's two failures are each switchable per run, both on by default
  (Vestige, UT Ants).
- S8's per-frame failure takes an allowance — a count or a percentile,
  default zero (Vestige).
- Per-run budget flag, default 16.67 ms (UT Ants).
- Several named inputs, each with a content hash (UT Ants).
- `ext.<engine>` rows and static-line register and wave counts printed
  beside the ranking, uninterpreted (UT Ants).
- Windows paths and CRLF in files (UT Ants).
- Writer: one C header, no dependencies, no per-frame allocation or
  file I/O, timestamps passed in, warning-free under GCC 14, Clang 19
  and MSVC as C++ (DOOM Ants, UT Ants, Vestige).
- Microsecond resolution (DOOM Ants).
- Static-line diff printed beside the pass comparison (UT Ants).
- Per-effect `ext` rows as a ranked table per map, uninterpreted
  (UT Ants, UTA-0436).
- Trust warnings for load above a threshold and settling frames below
  the header's stated need (UT Ants).
- Header fields shown: map identity, bake format and baker revision,
  pinned light time, GPU tick (UT Ants).
- A `--json` output (UT Ants).
- Where several overrides would make the opening sentence long, a
  short list straight after it (Vestige). S5 says "in its opening
  sentence", so this needs DOOM Ants' agreement in the spec review.
- Shader statistics in the static line are carried as exact numeric
  text, never as floating point: a 64-bit driver pipeline hash rounds
  as a double (UT Ants, measured on RADV 2026-10-24).
- S12's breach is judged on a per-pass statistic over the run (median
  or p99, chosen in the budget file), never on a single frame (DOOM
  Ants, DOOM-0502).
- A per-frame sim-tic flag (DOOM Ants).
- A camera-cut or warm-up marker, with a trust warning inside a
  measured stretch (DOOM Ants).
- Render scale, tier, ray tracing on/off and display kind block a
  compare (DOOM Ants).
