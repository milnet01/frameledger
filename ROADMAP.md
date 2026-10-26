<!-- ants-roadmap-format: 1 -->
<!-- Generated from the Ants Terminal roadmap store. Edit it with roadmap_log; hand edits are discarded by the next write. -->
<!-- ants-roadmap-id-high-water: FLED=17 -->
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

- ✅ [FLED-0002] **Read and check a run file.**
  ledger.py reads one file into a Run and lists every breach; the
  check command reports them with exit codes; cli.py's exit ladder;
  selftest.py's first sample files. Reads older schema versions and
  Windows files (CRLF, Windows paths). Claims S18, S11's file half and
  S6's reading half. Overlaps every later item in cli.py.
  Shipped 2026-10-24: ledger.py, cli.py, render.py, selftest.py,
  __main__.py; tests in tests/test_check.py, test_ledger.py,
  test_cli.py and test_layout.py; the gate runs pytest and --selftest.
  INV-1 and INV-21 cover check only, and INV-3 and INV-4 compare the
  parsed run; their report halves are FLED-0003's.
  **Layman:** The tool can open a run file and say whether it is valid.
  Kind: implement.
  Source: design-2026-10-24.
  Blocked-by: FLED-0001.

- ✅ [FLED-0003] **Single-run report.**
  stats.py and run_report.py: cost ranking per pass and per segment
  kind, bound-by share (or "does not apply" when not pipelined), GPU
  rows joined to their submitting frame, worst frames with their top
  pass. render.py: plain sentences first, tables within 100 columns,
  JSON. Claims S2, S3 and S13. Overlaps the floor check, pass budgets
  and pacing in run_report.py.
  From FLED-0002 (2026-10-24): add the report halves of the spec's
  tests: INV-1 (report exits 3), INV-21 (report names the negative), and
  INV-3 and INV-4 comparing `report --json` output, beside the
  parsed-run comparison already there. render.py exists with check's and
  selftest's text bodies.
  Shipped 2026-10-24: stats.py, run_report.py, render.py's report
  body, cli.py's `report FILE`; two --selftest checks. Tests in
  tests/test_report.py and test_render.py, and the report halves of
  INV-1, 3, 4 and 21 beside their check halves. The § 4.8 report shape
  was amended with the engines' review: frame_times, static, depth and
  frames per pass, remainders as passes, ranking by time spent
  (Vestige), and a capped static block with an optional "summary"
  object (UT Ants). DOOM Ants had not answered at commit (silence =
  keep). check's own breach and warning lines can pass 100 columns,
  since they carry the file's path; not changed here.
  **Layman:** One command says where a run's frame time went and which frames were worst.
  Kind: implement.
  Source: design-2026-10-24.
  Blocked-by: FLED-0002.

- ✅ [FLED-0004] **Floor check.**
  S8: one-second windows (frames completed over the window's length)
  and single frames against a per-run budget, each switchable and
  reported apart; warm-up; inconclusive when rows were dropped or the
  run has no close record. Claims S8.
  Built 2026-10-24 (3553b55): run_report.py's floor, cli.py's
  `floor FILE`, render.py's floor body, one --selftest check, tests in
  tests/test_floor.py. The three engines' code review changed both
  choices the spec left open: a frame over the budget fails even with
  rows dropped, and a cut's window starts at the end of the cut frame.
  Their findings are being fixed; the window pass rule awaits the
  engines' answer.
  Review fixes landed in 45138a2. Left, in order: (1) the window
  pass rule. Proposed to the engines 2026-10-24, silence = build it: a
  window passes when the mean frame/wall of the frames ending in it is
  <= round(1000/N, 3), independent of --budget-ms, so a steady 16.667 ms
  run passes at 60 (DOOM's finding 1). (2) Amend spec § 4.4 (frames
  numbered without holes; a hole is a frame_missing warning), § 4.7 (cut
  windows start at the cut frame's end; a frame failure stands under
  drops; a missing wall or frame, or nothing judged, is inconclusive;
  both checks off, or a budget outside 0.001 ms to 1e9 ms, is exit 3)
  and INV-7, 8, 18 to match. (3) Second engine review, readability
  included. (4) Flip shipped.
  Steps 1 and 2 done in 8caf07f: the mean-wall window rule (no
  engine objected) and the spec amendment. Step 3, the second engine
  review with readability, was requested 2026-10-24. Left: fold in its
  findings, then flip shipped.
  Second review folded in at da9644f: 1000/N rounded up (144 Hz
  and 59.94 Hz runs pass), a cut frame also closes the window open when
  it starts, windows report mean_ms, the --fps exemption under
  --budget-ms --no-windows; spec § 4.7, § 4.8, INV-8, INV-18 amended.
  UT Ants agreed 8caf07f; confirmation of da9644f asked of all three
  2026-10-24. Left: their confirmation, then flip shipped.
  Shipped 2026-10-24 at da9644f: Vestige, UT Ants and DOOM Ants all
  agreed the code and the spec amendment. UT Ants' optional note, that
  _timeline's first return type is still list[tuple], is dismissed:
  UT Ants judged it not worth a commit, and nothing reads it wrongly.
  **Layman:** Pass or fail: did the run hold 60 FPS every second, and did any single frame take too long?
  Kind: implement.
  Source: design-2026-10-24.
  Blocked-by: FLED-0003.

- ✅ [FLED-0005] **Trust warnings.**
  trust.py's run half of S5: Debug builds, software renderers, too few
  frames, high CPU or GPU load, settling below the header's need, a
  camera cut inside a measured stretch, dropped rows, missing timings
  counted as missing. Claims S5's warning half.
  2026-10-26: spec amendment drafted in
  docs/specs/FLED-0001-run-file-format.md § 4.9, INV-23 to INV-27;
  sent to the three engines for review before the build.
  2026-10-26: shipped at acc1e99. Spec § 4.9 agreed by Vestige, UT Ants
  and DOOM Ants at a3eea64; code agreed at 2e8e0cd, DOOM's gap fix at
  cad32de, Vestige's pinning test at acc1e99. UT Ants' optional notes
  (negative settling counts; a doubled sentence when floor judges
  nothing) left as they are.
  **Layman:** Warns when a run's numbers should not be trusted.
  Kind: implement.
  Source: design-2026-10-24.
  Blocked-by: FLED-0002.

- ✅ [FLED-0006] **Optional C writer header.**
  include/frameledger.h: C99 and C++17 common subset, no allocation,
  engine-owned buffer, rows dropped and counted when full, the largest
  row size stated, locale-free number formatting. Compile tests as C
  and C++ under GCC, Clang and mingw-w64 at -Wall -Wextra -Wpedantic
  -Werror, output run through check. Vestige and UT Ants compile it
  with MSVC. Claims S10.
  2026-10-26: include/frameledger.h and tests/writer/ built; gate
  green with GCC, Clang and mingw-w64. Sent to the three engines for
  code review, readability included. MSVC is theirs.
  2026-10-26: shipped at f963e9f. The three engines agreed f6fef40 and
  f963e9f after their review found the failed-open read and the DEL
  mismatch. Vestige compiled the header clean under MSVC cl 19.51 as C11
  and C++17; UT Ants' MSVC leg runs when it adopts the header
  (UTA-0437).
  **Layman:** A small file engines can include to write run files without writing their own.
  Kind: implement.
  Source: design-2026-10-24.
  Blocked-by: FLED-0001.

- ✅ [FLED-0007] **First release archive.**
  frameledger.pyz and include/frameledger.h in one archive attached to a
  tagged release, its SHA256 in the notes; CHANGELOG naming every
  format change. Windows runs of --selftest by Vestige and UT Ants.
  Claims S6's pin half and S11's Windows half.
  2026-10-26: v0.1.0-rc.1 published as a pre-release at d3ded0b, archive
  SHA256
  84a9254101421b223ca1429f889310ef92d1d4e4da433f19ce0d4225c89b9f5a.
  Release run 40250446302: Linux and windows-latest builds gave that
  hash and passed --selftest under Python 3.10.22. All three engines
  reviewed the tooling. Waiting on the Windows --selftest runs by
  Vestige and UT Ants; both machines are switched off. Then v0.1.0: date
  the CHANGELOG section, cut-release 0.1.0, same bytes. No CHANGELOG
  entry: this item is the release itself.
  2026-10-26: Vestige's Windows run passed. Windows 10 22H2, Python
  3.13.15 via py: archive SHA256 matched (certutil); `py -I
  frameledger.pyz --version` printed "frameledger 0.1.0", exit 0;
  `--selftest` printed 11 of 11 passed, exit 0; a `--bogus` control
  exited 3. The Python 3.10 floor on Windows is covered by release run
  40250446302's windows-latest job. UT Ants' run is still owed.
  2026-10-26: UT Ants' Windows run passed. Windows 10 Home 10.0.19045, a
  real PC; Python 3.13.15, run as `python -I`. The archive was
  downloaded with curl.exe; Get-FileHash gave
  84a9254101421b223ca1429f889310ef92d1d4e4da433f19ce0d4225c89b9f5a.
  `--version` printed "frameledger 0.1.0", exit 0; `--selftest` passed
  11 of 11, exit 0. Both Windows runs are in.
  2026-10-26: v0.1.0 published as the latest release at 022214e (release
  run 40250873697, all jobs green). Assets: frameledger-v0.1.0.zip, plus
  frameledger.zip, the same bytes; SHA256
  84a9254101421b223ca1429f889310ef92d1d4e4da433f19ce0d4225c89b9f5a,
  re-downloaded and matched, and the same bytes as rc.1's. The release
  notes are the CHANGELOG section verbatim.
  **Layman:** A downloadable, pinned version the three engines can use.
  Kind: release.
  Source: design-2026-10-24.
  Blocked-by: FLED-0003, FLED-0004, FLED-0005, FLED-0006.

## 0.2.0 — two builds compared

Compare, bisect, pass budgets and pacing: whether a change made an

engine faster, and which pass it changed.

- 🚧 [FLED-0008] **Compare labelled sets of runs.**
  compare.py: interleaved labelled sets (old-1, new-1, old-2, new-2),
  each pass judged by its own spread, a verdict on the exit ladder;
  trust.py's comparability refusals with per-field overrides named,
  with their reasons, in the opening sentence; static-line diff beside
  the pass comparison. Claims S4, S16 and S5's refusal half.
  2026-10-26: amends docs/specs/FLED-0001-run-file-format.md with § 4.10
  and INV-30 onward, for the three engines' review before anything is
  built.
  **Layman:** Says whether a change made the engine faster, slower or neither, pass by pass.
  Kind: implement.
  Source: design-2026-10-24.
  Blocked-by: FLED-0003, FLED-0005.

- 📋 [FLED-0009] **Bisect verdict mode.**
  One measure against a threshold or two reference runs; 0 good, 1 bad,
  125 skip, 128 stop; a dry run printing the verdict for a value.
  Claims S17. Overlaps the compare item in compare.py.
  Open question (Vestige, 2026-10-26, FLED-0008 review): judge `mem`
  rows, as Vestige's tools/perf_gate.py gates mem,gpu_mb with a 1.0 MB
  minimum. FLED-0008's compare judges no mem rows. Vestige retires
  perf_gate.py after this item lands, if mem judging is in by then.
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

- 💭 [FLED-0016] **Warn on a sanitizer build.**
  An optional header field `sanitizers` (an array of strings, such as
  "address") and a `sanitizer_build` trust warning when it is not empty.
  debug_build (FLED-0005) misses a Release build with ASan, which Vestige
  never counts as a reading. Asked by Vestige in its FLED-0005 review.
  **Layman:** Warns when a run came from a build with memory checking switched on, which makes it slow.
  Kind: enhancement.
  Source: vestige-review-2026-10-26.

- ✅ [FLED-0017] **An app icon and a site logo.**
  The owner, relayed by the ants-projects-hub-website session
  (message 849): a square app icon kept in this repository, and a
  wordmark logo for the site, per that repository's
  src/assets/img/logos/README.md: SVG with text as outlines, about
  3:1 to 2:1, transparent, readable on a dark teal (#5eead4) panel,
  strong contrast. Send the path back by session_message. Keep the
  release zip named frameledger.zip, which the site's Download link
  uses.
  2026-10-26: assets/frameledger-icon.svg (README shows it),
  assets/frameledger-logo-stacked.svg sent to the website session for
  logos/frameledger.svg (message 851), and the one-line
  assets/frameledger-logo.svg. 8fffb85, 764f4f6.
  **Layman:** Gives frameledger a picture of its own for the repository and the projects website.
  Kind: marketing.
  Source: ants-projects-hub-website-2026-10-26.

## 0.3.0 — many runs surveyed

Many runs at once: one per map, ranked, and one build's survey against

another's.

- 📋 [FLED-0012] **Survey ranking.**
  survey.py: many runs ranked by worst-segment median and p99, those
  over budget flagged with their costliest pass, per-effect ext rows
  as a ranked table. A survey of about a million rows in under a
  minute. Claims S9 and S19.
  Measured 2026-10-24 (FLED-0002): `check` on a one-million-row file
  took 8 s and peaked at about 640 MB, because ledger.Run holds every
  row. A survey of many such files needs a reader that keeps less.
  Refute: time `python3 -I src/frameledger check` on a generated
  million-row file.
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

## Later — for anyone

After frameledger does what Vestige, UT Ants and DOOM Ants need (the owner, 2026-10-24: build it for our own requirements first).

- 💭 [FLED-0015] **A version anyone can use.**
  Offer frameledger to engines other than the three it serves. Not
  started before the three engines' requirements are met. What "anyone
  can use" needs (install, documentation, a stable format promise,
  support) is to be decided then.
  **Layman:** A version of frameledger that any game developer can pick up and use, not only our three engines.
  Kind: feature.
  Source: user-request-2026-10-24.
  Blocked-by: FLED-0014.
