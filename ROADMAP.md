<!-- ants-roadmap-format: 1 -->
<!-- Generated from the Ants Terminal roadmap store. Edit it with roadmap_log; hand edits are discarded by the next write. -->
<!-- ants-roadmap-id-high-water: FLED=74 -->
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
  the CHANGELOG section, cut-release 0.1.0, same bytes. Release note
  (release): no CHANGELOG entry — this item is the release itself.
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

- ✅ [FLED-0008] **Compare labelled sets of runs.**
  compare.py: interleaved labelled sets (old-1, new-1, old-2, new-2),
  each pass judged by its own spread, a verdict on the exit ladder;
  trust.py's comparability refusals with per-field overrides named,
  with their reasons, in the opening sentence; static-line diff beside
  the pass comparison. Claims S4, S16 and S5's refusal half.
  2026-10-26: amends docs/specs/FLED-0001-run-file-format.md with § 4.10
  and INV-30 onward, for the three engines' review before anything is
  built.
  2026-10-26: built at 87fad7d, engines' code review folded in at
  9a3b5fb and 1b271ec; Vestige, UT Ants and DOOM Ants agreed 1b271ec.
  Spec FLED-0001 § 4.10, INV-30 to INV-38. Unreleased: ships in 0.2.0.
  Vestige will send its run-to-run frame/wall spread from its first
  interleaved sets, to test whether three runs a set is enough.
  **Layman:** Says whether a change made the engine faster, slower or neither, pass by pass.
  Kind: implement.
  Source: design-2026-10-24.
  Blocked-by: FLED-0003, FLED-0005.

- ✅ [FLED-0009] **Bisect verdict mode.**
  One measure against a threshold or two reference runs; 0 good, 1 bad,
  125 skip, 128 stop; a dry run printing the verdict for a value.
  Claims S17. Overlaps the compare item in compare.py.
  Open question (Vestige, 2026-10-26, FLED-0008 review): judge `mem`
  rows, as Vestige's tools/perf_gate.py gates mem,gpu_mb with a 1.0 MB
  minimum. FLED-0008's compare judges no mem rows. Vestige, 2026-10-26: bisect's
  mem judging does not retire perf_gate.py, a baseline gate; that needs
  compare to judge mem (FLED-0018).
  2026-10-26: spec amendment in docs/specs/FLED-0001-run-file-format.md
  § 4.11 and INV-39 to INV-46, sent to the three engines for review.
  It proposes mem judging for bisect (mem medians, --min-mb default
  1.000); whether compare judges mem too is asked of the engines.
  2026-10-26: the three engines' review folded in; § 4.11 and INV-39
  to INV-50 sent back for confirmation. Open: DOOM Ants asks that tested
  runs straddling the verdict line skip (125); UT Ants and Vestige do not.
  2026-10-26: built at 8fd7b83; the three engines' code review folded
  in: an empty tested file crashed to 128 (all three); a closed pipe
  exited 120, read as bad (UT Ants); tested runs now follow --tested;
  bisect moved to bisecting.py. 61 hand mutants, all killed. Sent back to
  the three for review.
  2026-10-26: shipped; the three engines confirmed 32b87ac for
  correctness and readability, and the --tested interface. Each re-ran
  the failure cases by hand. Unreleased, for 0.2.0. UT Ants' depth point
  filed as FLED-0020.
  **Layman:** Lets git bisect find the change that made a pass slower.
  Kind: implement.
  Source: design-2026-10-24.
  Blocked-by: FLED-0008.

- ✅ [FLED-0010] **Pass budgets.**
  A budget file naming passes, each with a statistic (median or p99)
  and a limit; names each pass over budget and exits non-zero. Claims
  S12.
  Spec: docs/specs/FLED-0001-run-file-format.md § 4.12, INV-54 to INV-60
  (amend-0010, 2026-10-29); with the three engines for review.
  Spec confirmed by the three engines at f766388 (2026-10-29). Built in
  src/frameledger/budgeting.py; with the engines for code review.
  Shipped 2026-10-29 at eb47707: the three engines confirmed the code
  review fold (Vestige, UT Ants; DOOM Ants' last case is the test).
  **Layman:** Gives each drawing step a time budget and names the one that goes over.
  Kind: implement.
  Source: design-2026-10-24.
  Blocked-by: FLED-0003.

- ✅ [FLED-0011] **Frame pacing figure.**
  A frame-to-frame variation figure beside the 1% low. Claims S14.
  2026-11-04: design asked of the three engines before amending
  docs/specs/FLED-0001-run-file-format.md: |wall(n) - wall(n-1)| over
  consecutive frames with a wall, not across a hole, segment change or
  cut; median, p99 and pairs per segment kind in report (JSON "pacing",
  text row "wall change"); a figure, no verdict; floor unchanged.
  2026-11-04: all three engines agreed the design (a, b, c; not in
  floor; no warm-up skip). Spec amendment in
  docs/specs/FLED-0001-run-file-format.md § 4.8 and INV-68, sent for
  review before building.
  Shipped 2026-11-04 at 35b6f20 and the rename commit after it; the
  three engines agreed the code. DOOM Ants ran report on a real traced
  run (399 frames): wall change median 1.859 ms, p99 33.421 ms over 398
  pairs, which matched the run. Vestige and UT Ants have no run files
  yet (3D_E-0786, UTA-0437). Tests: tests/test_pacing.py.
  **Layman:** Shows judder even when the frame rate passes.
  Kind: implement.
  Source: design-2026-10-24.
  Blocked-by: FLED-0003.

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

- ✅ [FLED-0018] **Compare judges mem measures.**
  Amend spec FLED-0001 § 4.10 so compare judges each mem row's median
  per segment kind, with a --min-mb floor (default 1.000) in place of
  --min-ms, as FLED-0009's § 4.11 does for bisect. Vestige retires
  tools/perf_gate.py (gates frame,total, gpu,total, cpu,total and
  mem,gpu_mb against a committed baseline, min_abs_mb 1.0) once this
  lands (Vestige, 2026-10-26, FLED-0009 review).
  Spec amendment in docs/specs/FLED-0001-run-file-format.md § 4.10 and
  INV-65 to INV-67, at the engines' review. Vestige's perf_gate.py fails
  memory at 25 percent, so compare's default 3 percent is stricter and
  no separate memory percent is proposed. Read 2026-10-31.
  Vestige, UT Ants and DOOM Ants confirmed 0ebcf7d, 2026-10-31. Vestige
  keeps tools/perf_gate.py for now: its mem/gpu_mb reads the whole card,
  which Vestige fixes on its own roadmap, and it waits for a compare
  release to pin.
  **Layman:** Lets the comparison catch a build that uses more memory, so Vestige can retire its own gate script.
  Kind: implement.
  Source: vestige-review-2026-10-26.
  Blocked-by: FLED-0009.

- ✅ [FLED-0019] **The analyser runs headless.**
  The owner, 2026-10-26: the app must run headless. Claims S20. The
  analyser imports the standard library only and opens no display, so it
  already did; tests/test_cli.py::test_headless locks it: --selftest,
  report and a bisect dry run, with only PATH (and SYSTEMROOT on
  Windows) in the environment, stdin closed and no controlling terminal.
  Seen failing on a copy whose entry point reads DISPLAY.
  2026-10-26, DOOM Ants' review: the test now runs every command (check,
  report, floor, compare, bisect on real run files, --json) through the
  frameledger.pyz the release builds, and requires the same output and
  exit code as in-process; test_headless_results_are_whole checks a
  sentence, a parsed JSON result and an error message. Seen failing on a
  clone whose archive leaves out render.py. The two "FILE…" messages are
  now ASCII.
  **Layman:** Makes sure the tool works on a machine with no screen, such as a build server.
  Kind: test.
  Source: user-request-2026-10-26.

- ✅ [FLED-0020] **A tested run at another depth skips rather than stops.**
  UT Ants, 2026-10-26, FLED-0009 review of 32b87ac: without --depth, a
  tested run whose pass sits at another depth from the references, or
  tested runs at mixed depths, stop the bisect (128) in bisecting.py
  _one_depth, while a tested run lacking the measure skips (125). A
  commit that re-nests a pass then ends the bisect instead of skipping
  that commit, and a bisect range can cross such a restructure
  (UTA-0437). The references' own depth mismatch would still stop. Spec
  § 4.11 and INV-46 change; needs the three engines' agreement, since
  Vestige and DOOM Ants asked for the one-depth rule.
  2026-11-04: asked the three engines A (keep the stop) or B (a tested
  run at another depth, or mixed tested depths, skips 125 naming both
  depths; the references' mismatch still stops 128); recommended B. UT
  Ants: B, and the skip message names the measure and says --depth pins
  it, since a mid-range restructure skips every later commit. Vestige
  and DOOM Ants not yet answered.
  2026-11-04, Vestige: B, if every depth skip says why ("gpu/blur at
  depth 1, references at depth 0") and depth skips are counted apart
  from missing-measure skips. bisect judges one commit per run, so it
  cannot count across a range; the proposal back is a distinct skip
  reason in the JSON, so a caller can count each kind. DOOM Ants not yet
  answered.
  2026-11-04: DOOM Ants: B, the 125 sentence names both depths and says
  --depth judges such commits. All three chose B. Spec amendment in
  docs/specs/FLED-0001-run-file-format.md § 4.11 and INV-46, with
  skip_reason in place of a cross-commit count, sent for review.
  Shipped 2026-11-04 at d2ff396 and the review fold-in after it; the
  three engines agreed the amendment (139c66c) and the code. A tested
  commit at another depth skips (125) with skip_reason depth and a
  --depth hint; references at two depths still stop (128). Tests:
  tests/test_bisect.py::test_depth, test_one_depth_across_runs.
  **Layman:** Lets a bisect step over a commit that reorganised a drawing step, instead of halting the whole search.
  Kind: enhancement.
  Source: ut-ants-review-2026-10-26.

- ✅ [FLED-0021] **Analyser review fixes from PR #1.**
  PR #1 (branch claude/exciting-cray-d4fxmf). Its commits are labelled
  FLED-0009, which had already shipped; they land under this item.
  Fixes: --allow-frames / --depth take only ASCII digits; the null
  device's descriptor is closed after dup2. Engines review before merge.
  Landed f89be63..4737180 (PR #1, relabelled from FLED-0009) and b3acb89
  (the engines' review). Vestige, UT Ants and DOOM Ants confirmed
  b3acb89, 2026-10-29.
  **Layman:** A cloud session's review of the analyser: two small bug fixes, faster statistics, and shared helpers in place of repeated code. No output changes.
  Kind: review-fix.
  Source: github-pr-1-2026-10-28.

- ✅ [FLED-0022] **A huge frame or depth number crashes the reader.**
  ledger._row_problem accepts any length of digits for `frame` and
  `depth` (COUNT_RE), then _Reader converts them with int(). Past
  Python's 4300-digit limit that raises ValueError: `check` on a row
  whose depth has 5000 digits ends in a traceback (run 2026-10-29),
  not a breach. Exit 1 then reads as "fail" to a gate. A breach naming
  the line is the fix. Found beside Vestige's FLED-0010 code review,
  which hit the same limit in the budget file (fixed there).
  The value's whole part crashed the same way, in _thousandths, and with
  leading zeros too; all three now stop at 20 digits (INV-64). Run
  2026-10-31.
  Correction to f5e476b's commit body, which says 21 of 22 new cases
  were red on the old reader. There are 23 new cases. 19 failed on the
  old reader for the intended reason. The first red run showed 22
  failing, but 3 of those were a fault in the test (a duplicate
  cpu/scene row), since fixed. The 4 acceptance cases are expected to
  pass on both readers; after that test fix they were run on the new
  reader only.
  Vestige, UT Ants and DOOM Ants confirmed 0c5b57d, 2026-10-31.
  **Layman:** A run file with an absurdly long number makes frameledger crash instead of saying the file is broken.
  Kind: fix.
  Source: vestige-review-2026-10-29.

- ✅ [FLED-0023] **A huge --warmup-s crashes floor.**
  floor --warmup-s 1e400, or a 5000-digit whole number, ends in a
  traceback at run_report.floor's warmup_us / SECOND (OverflowError),
  exit 1, which a gate reads as "fail" (run 2026-10-31). _non_negative has
  no upper limit, unlike _value and _floor_ms, which stop at BUDGET_LIMIT.
  Exit 3 with a sentence is the fix. budget --warmup-s shares the parser;
  not yet tried with a valid budget file. Found beside FLED-0022.
  2026-11-04: budget --warmup-s 1e400 with a valid budget file crashed
  the same way (OverflowError, exit 1). Both now refuse 1000000000 s or
  more, exit 3, in docs/specs/FLED-0001-run-file-format.md §§ 4.7 and
  4.12. With the engines for review.
  Shipped 2026-11-04 at bd6f033, 8cef832 and 17d5d8c; the three engines
  confirmed. Vestige's review found compare and bisect --min-pct crashed
  the same way; both are bounded too. Tests: test_huge_warmup_is_exit_3
  (test_floor.py, test_budget.py), test_huge_min_pct_is_exit_3
  (test_compare.py), test_huge_min_pct_stops (test_bisect.py).
  **Layman:** An absurdly long warm-up time makes frameledger crash instead of saying the setting is wrong.
  Kind: fix.
  Source: fled-0022-probe-2026-10-31.

## 0.3.0 — many runs surveyed

Many runs at once: one per map, ranked, and one build's survey against

another's.

- ✅ [FLED-0012] **Survey ranking.**
  survey.py: many runs ranked by worst-segment median and p99, those
  over budget flagged with their costliest pass, per-effect ext rows
  as a ranked table. A survey of about a million rows in under a
  minute. Claims S9 and S19.
  Measured 2026-10-24 (FLED-0002): `check` on a one-million-row file
  took 8 s and peaked at about 640 MB, because ledger.Run holds every
  row. A survey of many such files needs a reader that keeps less.
  Refute: time `python3 -I src/frameledger check` on a generated
  million-row file.
  2026-11-04: design asked of the three engines before amending
  docs/specs/FLED-0001-run-file-format.md: survey FILE... (--fps N |
  --budget-ms B); rank by the worst segment kind's frame/wall p99; flag
  over floor's budget, naming the costliest depth-0 pass; unreadable
  runs listed, not stopping; exit 1 flagged, 2 unjudged, 0, 3 bad flags;
  ext rows left for later; a one-pass reader for S19.
  2026-11-04, UT Ants and Vestige: agree, with changes. --warmup-s,
  default 2, judging floor's frames (cut frames kept, as floor judges
  them). Name the worst segment within the worst kind (UT Ants). A kind
  under 100 frames is listed but not ranked or flagged (Vestige). The
  flag sentence says p99 over the frame budget, not floor's verdict
  (Vestige); a floor column is optional, proposed as a later item. No
  --kind; ext rows later. DOOM Ants not yet answered.
  2026-11-04, DOOM Ants: agree, and a flag must mean exactly that floor
  would fail the run on frame time. Proposed back to all three: the flag
  is floor's single-frame check with --allow-frames, saying the window
  check is not run; the worst eligible kind's p99 ranks. Awaiting their
  confirmation.
  2026-11-04: UT Ants and Vestige confirmed the flag as floor's
  single-frame check; DOOM Ants proposed it. Spec amendment
  docs/specs/FLED-0001-run-file-format.md § 4.13 and INV-69 to INV-72
  sent for review.
  2026-11-04: built at 3e7006b (survey.py, run_report.frame_check shared
  with floor, tests/test_survey.py). UT Ants and DOOM Ants agreed the
  code with no defect; DOOM Ants' 60+ real runs matched floor's counts.
  Their notes folded in after. Waiting on Vestige's code review (asked
  2026-11-04); on agreement, flip to shipped and add a confirm-impl-0012
  loop-log row.
  2026-11-04: Vestige agreed the code at 3e7006b with no defect, so all
  three engines have agreed. Its two optional readability notes were not
  taken: the sort stays as written, and the inconclusive sentence's
  capital matches frame_check's reasons, which are whole sentences.
  Shipped.
  **Layman:** Ranks every map's run and flags the slow ones.
  Kind: implement.
  Source: design-2026-10-24.
  Blocked-by: FLED-0003.

- ✅ [FLED-0013] **Survey against survey.**
  Two builds' surveys, per run and per pass; flags each pass that got
  slower by more than its run-to-run spread. Claims S15. Overlaps the
  compare item in compare.py.
  2026-11-04: design asked of the three engines before amending
  docs/specs/FLED-0001-run-file-format.md: `compare --by-scene --old
  FILE... --new FILE...`, each scene judged as compare judges a pair of
  sets; a scene under 3 runs a side, one-sided, refused or unreadable
  listed as unjudged and the rest going on; exit 1 slower or larger, 2
  inconclusive or unjudged, 0, 3 bad flags; scenes ranked by their
  largest slower change in ms. Asked: flag or new command, 3 runs a side,
  unjudged or exit 3, anything missing.
  Waiting-on: Vestige, UT Ants and DOOM Ants (FLED-0013 design, 2026-11-04).
  2026-11-04, UT Ants and DOOM Ants: agree 1 to 5, the flag, 3 runs a
  side kept as the minimum, run on a chosen subset of scenes. DOOM Ants:
  `scene` named as the key, a file without one unjudged; a one-sided
  scene names the side it lacks; say plainly when no scene could be
  judged. UT Ants: exit 3 when no scene could be judged; compare's
  `not_interleaved` per scene; the failing sentence names the segment
  (view:N) where the slower measure changed most. To reconcile with
  Vestige's answer, which is still awaited.
  2026-11-04, Vestige: agrees 1 to 5, the flag, 3 runs a side. Adds:
  `scene` matched exactly, a run without one unjudged; say plainly when
  no scene could be judged; § 4.10 states that many scenes multiply the
  false-fail rate, and the result counts scenes and measures judged.
  Merged design sent back to all three, every addition taken. Proposed
  for the one split: no scene judged gives exit 3 (UT Ants), opening
  "No scene could be judged: ..." (DOOM Ants, Vestige). Objections
  asked for; otherwise the spec amendment follows.
  2026-11-04: no objection to the merged design. Spec amendment
  docs/specs/FLED-0001-run-file-format.md § 4.14 and INV-73 to INV-77,
  with § 4.10's flag and many-scene rate, at ee0dd83, sent to the three
  engines for review.
  Waiting-on: Vestige, UT Ants and DOOM Ants (review of ee0dd83, 2026-11-04).
  2026-11-04: Vestige and UT Ants agree ee0dd83 with no change,
  including the three details settled in drafting.
  Waiting-on: DOOM Ants (review of ee0dd83, 2026-11-04).
  2026-11-04: DOOM Ants agrees ee0dd83 with no change, so all three
  have. Building.
  2026-11-04: build not started; no code or tests written. Plan: tests
  first in tests/test_compare_scenes.py (the five names § 10 cites),
  seen red, then the code. compare.compare() takes the runs of one
  scene unchanged; the by-scene layer groups, ranks and counts. Where it
  lives is open: docs/design.md puts survey against survey in compare.py,
  but a new module may read better; if one is added, update design.md's
  module list and git add it before the tests run. Segment-level values
  for the named segment are new: compare._values works per kind only.
  2026-11-04: built at 3d9ed37, in a new module scenes.py; the five
  tests seen red, then the gate green. Sent to the three engines for
  code review, readability included, with five calls the spec left to
  the build.
  Waiting-on: Vestige, UT Ants and DOOM Ants (code review of 3d9ed37, 2026-11-04).
  2026-11-04: all three engines asked for changes to 3d9ed37: per-scene
  warning sentences, a weak rank test, an always-true assertion, the
  changed-between-reads reason, and the separator in "No scene could be
  judged:". Fixed in 1bf50e4, and sent back for re-review.
  2026-11-04: re-review of 1bf50e4. DOOM Ants agreed. Vestige and
  UT Ants asked for one fix: a file broken between the two reads
  crashed the scene re-check. Fixed in 6da8f79, with three readability
  nits, and sent back. Waiting-on: Vestige and UT Ants (re-review of
  6da8f79).
  2026-11-04: Vestige, UT Ants and DOOM Ants all agreed 6da8f79.
  Shipped.
  **Layman:** Catches a map that got slower between two builds.
  Kind: implement.
  Source: design-2026-10-24.
  Blocked-by: FLED-0008, FLED-0012.

- ✅ [FLED-0026] **The README shows what compare prints for an A/B of a few runs a side.**
  DOOM Ants (FLED-0014 feedback) A/B-tested two features, 3 runs
  a side, with a private script taking per-pass medians. They did
  not try compare: nothing at the point of use said it does that.
  It does: run on 3 vs 3, it prints each moved measure's old and
  new median, the change, the spread and a verdict.
  The README's Usage section shows the compare command but not its
  output. Add one short example output under it, and say that
  unchanged measures are counted, not listed, and that --json
  carries them all.
  2026-11-09: text in 2888307, sent to the three engines for review.
  Also says the .pyz comes in the release zip (DOOM Ants' inbox
  finding).
  2026-11-09: review fixes 849f316 (DOOM Ants), 6aa87a1 (Vestige),
  06b61af (UT Ants), pushed. UT Ants agreed 06b61af; DOOM Ants agreed
  849f316. Waiting on Vestige and DOOM Ants to agree 06b61af.
  Shipped 2026-11-10. Agreed by UT Ants (final text), Vestige and DOOM
  Ants (06b61af, 2026-11-09). 0fc13c1 adds DOOM Ants' requested clause
  on run order (started_utc) and Vestige's "median" wording.
  Release note (2026-11-11): no CHANGELOG entry. A README-only change;
  its last commit, 0fc13c1, is in v0.3.0.
  **Layman:** Show an example of the comparison report, so engines use it instead of writing their own scripts.
  Kind: doc.
  Source: doom-ants-feedback-2026-11-05.

## 0.4.0 — A/B runs you can trust

All three engines' first ask (2026-11-10): run old and new builds in

turn, know when the machine was busy, and paste the result. Inputs:

the engines' answers to the 0.4–1.0 draft, 2026-11-10.

- ✅ [FLED-0028] **Discovery and design cover the 0.4–1.0 scope.**
  Add signs of success for the run helper, load evidence, variants,
  baselines, imports, the picture report and the stability promises;
  move charts from "not yet" to optional; place each new module in
  design.md's import order. Agreed by the three engines, as discovery
  and design were. Every later item here claims one of the new signs.
  2026-11-10: discovery S21–S27, S11's macOS and the picture-report
  line, and design's new modules, drafted and sent to the three engines
  for agreement.
  2026-11-10: agreed by DOOM Ants, UT Ants and Vestige at 64f0687, with
  Vestige's optional S22 wording added after. Release note (docs only):
  no CHANGELOG entry.
  **Layman:** Write down what the new features are for and how we will know they work, before building them.
  Kind: doc.
  Source: engine-answers-2026-11-10.

- ✅ [FLED-0029] **A run helper alternates old and new builds, then compares.**
  Given the command that runs each build, it runs them in turn (old,
  new, old, new), at least three a side, and compares the files they
  wrote. It times nothing and writes no run file: the engine still
  does both. Asked first by all three engines: DOOM Ants writes the
  order by hand in each A/B script; UT Ants saw one binary's median
  move from 32.6 to 24.9 ms between back-to-back runs (UTA-0435);
  Vestige would retire perf_gate.py with it and a baseline.
  Needs a spec amendment to FLED-0001, reviewed by the engines.
  2026-11-10, FLED-0028 reviews: the helper fills a placeholder in each
  command with that run's own file name, so runs never overwrite each
  other (DOOM Ants' c-<tag>/l.csv, Vestige's --frame-log=PATH). The
  placeholder's spelling is fixed in this item's spec amendment, which
  DOOM Ants and Vestige review. S23's variants use the same helper, base
  and each variant in turn (UT Ants).
  2026-11-10: spec amendment drafted as docs/specs/FLED-0001-run-file-format.md
  § 4.15 (`alternate`, placeholder `{run}`) with INV-78 to INV-81; sent
  to the three engines for review before building.
  2026-11-10: spec confirmed by all three engines at 2168982 (paired
  order, --warmup default 0, failed run's file deleted). Built in
  51e1cd3 (src/frameledger/alternate.py, tests/test_alternate.py); gate
  green. Code sent to the three engines for review.
  Shipped 2026-11-11 at 5318296: all three engines agreed the code after
  three review rounds.
  **Layman:** One command runs the old and new versions of a game in turn and says which is faster.
  Kind: feature.
  Source: engine-answers-2026-11-10.
  Blocked-by: FLED-0028.

- ✅ [FLED-0030] **compare acts on a busy machine.**
  The header already has optional load, gpu_busy_pct and
  gpu_clock_mhz, read at start and end only (spec § 4.2), and a
  warning never changes a verdict (§ 4.9). Vestige's A/Bs failed
  when other programs loaded the GPU mid-run, which a start sample
  misses. Add an optional peak taken during the run; compare names
  each run taken under load and gives inconclusive rather than a
  verdict; it warns when the two sides' load or GPU clock differ.
  Asked by Vestige (3D_E-0704, 0658, 0795) and UT Ants (UTA-0435).
  Needs a spec amendment, reviewed by the engines.
  2026-11-10, FLED-0028 reviews: a run is under load when either peak
  (CPU load as a share of the machine, GPU busy share) passes its limit;
  the spec sets both limits and a flag changes them; a loaded compare
  exits 2. DOOM Ants needs the flag: its machine is shared with other
  sessions, so defaults could mark many runs inconclusive. UT Ants and
  Vestige review the numbers in this item's spec amendment.
  2026-11-10: spec amendment drafted in
  docs/specs/FLED-0001-run-file-format.md (§ 4.2 `peak`, § 4.10 under
  load and the three differ warnings) with INV-82 to INV-84; sent to the
  three engines for review before building. A peak counts other programs
  only: a game keeps the GPU busy, so a peak counting the run would mark
  every run.
  2026-11-10: the three engines' reviews folded in at 51e1cd3 (own work
  may include helper processes; samples clamped; partial visibility; end
  clock before GPU release); defaults kept at 0.25 and 20. Sent back for
  confirmation before building.
  Shipped 2026-11-11: code 32eea63, review fold 320f093 and 27fddc2;
  Vestige, UT Ants and DOOM Ants agreed.
  **Layman:** The comparison notices when something else was using the computer during a test and says the result cannot be trusted.
  Kind: feature.
  Source: engine-answers-2026-11-10.
  Blocked-by: FLED-0028.

- ✅ [FLED-0031] **compare can name its measures and show one row per run.**
  A --measure filter keeps only the named passes, and a per-run
  table gives each run's median of each kept measure on one row.
  DOOM Ants' private ledp.py does exactly this; DOOM says compare
  would replace it with both. compare already judges each pass by its
  own spread (S16).
  2026-11-11: amended docs/specs/FLED-0001-run-file-format.md § 4.10
  (and § 4.14, § 4.15): --measure CATEGORY/NAME and the per-run table,
  INV-85 and INV-86. Sent to the three engines for review before
  building.
  2026-11-11: all three engines agreed the spec at b7c2c55. Built:
  --measure on compare, --by-scene and alternate; the per-run tables;
  tests/test_compare_measure.py for INV-85 and INV-86. Sent to the
  engines for code review.
  2026-11-11: shipped, all three engines agreeing the code at d042ed6
  after three code-review folds (f753a1f, 7f34c72, d042ed6). DOOM Ants
  checked it on its own runs. FLED-0064 queues alternate's missing
  tables, found in review.
  **Layman:** Lets you ask about just the parts of a frame you care about, with one line per test run.
  Kind: feature.
  Source: engine-answers-2026-11-10.

- ✅ [FLED-0032] **Every command can print Markdown.**
  A --markdown output, made from the same result as text and JSON,
  ready to paste into a commit body, a roadmap note or a pull
  request. Asked by DOOM Ants and Vestige, who copy numbers by hand.
  2026-11-11: amended docs/specs/FLED-0001-run-file-format.md § 4.7
  and § 4.8: --markdown, INV-87 and INV-88. Sent to the three engines
  for review before building.
  2026-11-11: shipped at 9d72f75, all three engines agreeing. --markdown
  on every command; § 4.8, INV-87 and INV-88 in tests/test_markdown.py.
  **Layman:** Results come out ready to paste into notes and messages.
  Kind: feature.
  Source: engine-answers-2026-11-10.

- ✅ [FLED-0033] **frameledger runs by name.**
  The release ships a small launcher for Linux and Windows, and the
  README says how to put it on PATH, so `frameledger report run.csv`
  works. DOOM Ants keeps a private script partly because the command
  is not on PATH.
  Built 2026-11-11: launcher/frameledger and launcher/frameledger.cmd
  ship in the release zip; README § Run it by name. Out to the three
  engines for review.
  Shipped 2026-11-11, all three engines agreeing. The launchers also run
  a source checkout (DOOM Ants), and a copied launcher says it cannot
  find the analyser (UT Ants).
  **Layman:** You can type frameledger as a command instead of a long path.
  Kind: ux.
  Source: engine-answers-2026-11-10.

- 🚫 [FLED-0052] **The run helper can discard warm-up runs and run a prepare command.**
  `alternate --warmup-runs N` runs and discards N runs a side first;
  `--prepare CMD` runs before each run, e.g. to clear a shader cache.
  The first run after a build pays for cold disk and shader caches,
  which reads as a slowdown of whichever build ran first. General
  benchmark runners offer both (hyperfine --warmup and --prepare):
  https://github.com/sharkdp/hyperfine
  Asked of the engines as question 6 of FLED-0029's review; folds into
  FLED-0029 if they want it, otherwise moves after 1.0.
  2026-11-10, engines: warm-up yes (UT Ants, Vestige), no (DOOM Ants);
  prepare command no from all three. Warm-up folded into FLED-0029 as
  `--warmup`, default 0.
  Dropped as its own item: its warm-up half is in FLED-0029; its prepare
  half no engine needs.
  **Layman:** Before timing, the helper can throw away a first run and clear caches, so a cold start is not mistaken for a slowdown.
  Kind: feature.
  Source: competitor-research-2026-11-10.

- ✅ [FLED-0064] **alternate prints compare's tables.**
  § 4.15 says alternate gives § 4.10's text, but render.py's
  _BODIES has no alternate entry, so alternate prints only the
  opening sentences: none of compare's tables, the runs list, the
  static diff, or FLED-0031's per-run table. Found by UT Ants' code
  review of FLED-0031, 2026-11-11; it predates that item.
  **Layman:** After running both builds, alternate shows the same tables of results that compare shows.
  Kind: fix.
  Source: engine-review-2026-11-11.

## 0.5.0 — variants and baselines

The engines' second asks: more than two builds at once, a saved set

to compare against, and the small fixes they filed.

- ✅ [FLED-0034] **compare judges named variants against one base.**
  More than two sets at once: the full frame against each effect
  switched off, each variant judged against the base as compare
  judges new against old. UT Ants' UTA-0436, the cost of each effect
  per map. compare --by-scene groups by scene, not variant, so it
  does not cover this.
  2026-11-11: spec amendment drafted as docs/specs/FLED-0001-run-file-format.md
  § 4.16 (compare --base/--variant, alternate --base/--variant) with
  INV-89 to INV-94; sent to the three engines for review before building.
  2026-11-12: built at a9b3c35 (variants.py; compare and alternate
  --base/--variant; tests/test_compare_variants.py). Gate green. Sent to
  the three engines for code review, correctness and readability.
  2026-11-12: all three engines reviewed a9b3c35; no blocker. UT Ants' and
  DOOM Ants' findings folded at 171668f, Vestige's at 79ca5d6. Sent back
  to the three for a yes or no on the folds; ships on their yes.
  2026-11-12: Vestige: yes to the fold, on its description; it did not
  re-read 79ca5d6. No scenes.py item wanted. UT Ants and DOOM Ants awaited.
  2026-11-12: UT Ants: yes to the fold, to its list and not to 4bab2e7's
  diff. DOOM Ants awaited.
  2026-11-12: DOOM Ants: yes to the fold, on its description and the
  named tests. All three engines agreed; none re-read the fold's diff.
  Shipped.
  **Layman:** Compare many versions at once, such as the game with each effect turned off in turn.
  Kind: feature.
  Source: engine-answers-2026-11-10.

- ✅ [FLED-0035] **A saved baseline to compare against.**
  A file naming a set of runs taken as the reference, which compare
  and the run helper take in place of --old. The analyser keeps no
  state: the engine keeps the file. Vestige needs it, with the run
  helper, to retire perf_gate.py.
  2026-11-12, engines: all three agreed the design. The file lists run
  paths, relative to its own folder; `--baseline FILE` stands in for
  `--old` or `--base` on compare and alternate, not on bisect; runs stay
  old-N; no thresholds, measure list or hash in the file; no converter
  from perf_gate.py's JSON (Vestige). Added from their answers: a listed
  path that is not a file is exit 3 naming its line (Vestige); the
  not-interleaved warning names the baseline's commit, date and age (all
  three); a warning when driver or os differs (UT Ants).
  Spec: docs/specs/FLED-0001-run-file-format.md § 4.17.
  2026-11-12: built at e5f2758. The three engines' code reviews found
  no blocker and agreed where the build departed from the design; their
  points on comments, duplicate files, paths that are not absolute, the
  warning's wording and cli.py's readability are folded. FLED-0069 and
  FLED-0070 queue two older crashes the reviews found.
  **Layman:** Keep a known-good set of test runs and check every new version against it.
  Kind: feature.
  Source: engine-answers-2026-11-10.

- ✅ [FLED-0024] **A long warm-up is shown rounded, in exponent form.**
  album-builder, 2026-11-04: floor --warmup-s 999999999 on
  tests/fixtures/passing-run.csv says "follows the 1e+09 s warm-up",
  which is the refused limit. run_report.floor and budgeting format the
  warm-up with :g, six significant digits, so any warm-up of 1000000 s
  or more prints rounded. No real run's warm-up is that long; showing
  the value as given would fix it.
  2026-11-10: planned for 0.5.0, a small fix kept out of 0.4.0's A/B
  work.
  2026-11-12: fixed. run_report.seconds gives a warm-up in full for
  floor, budget and survey; a test in each command's file.
  **Layman:** A warm-up of millions of seconds is printed as a rounded number like 1e+09 instead of as typed.
  Kind: fix.
  Source: album-builder-fact-check-2026-11-04.

- 💭 [FLED-0054] **A noisy compare says how many more runs would settle it.**
  On exit 2 for a noisy `frame/wall`, estimate the runs a side that
  would settle it; the run helper could keep alternating up to a cap.
  Chromium's bisect returned "need more data" and grew its sample:
  https://codereview.chromium.org/1702013004
  Needs FLED-0029, the engines' agreement and a spec amendment.
  2026-11-10, engines: yes (DOOM Ants), later (UT Ants, Vestige).
  **Layman:** Instead of just 'can't tell', frameledger suggests how many more test runs to do.
  Kind: feature.
  Source: competitor-research-2026-11-10.

- 💭 [FLED-0056] **report gives a 0.1% low and lows as the mean of the slowest frames.**
  Today report gives p99 and a 1% low from p99. Add a 0.1% low, and
  the x% low as the mean of the slowest x% of frames, a common
  industry definition. A 0.1% figure needs at least 1000 frames, so it
  needs a too-few-frames warning like § 4.9's. Rare hitches such as
  shader compiles hide below p99. Seen in MangoHud's summary:
  https://github.com/flightlessmango/MangoHud
  Needs the engines' agreement and a spec amendment.
  2026-11-10, engines: later from all three.
  **Layman:** Shows how bad the rarest stutters are, not only the usual slow frames.
  Kind: feature.
  Source: competitor-research-2026-11-10.

- 💭 [FLED-0057] **Time-weighted figures: the share of time spent in slow frames.**
  The share of the run's time spent in frames over budget, and a
  percentile weighted by time rather than by frame count. A count-based
  p99 understates long frames, since a slow frame fills more of the
  player's time. Seen in CapFrameX's metrics:
  https://www.capframex.com/blog/post/Explanation%20of%20different%20performance%20metrics
  Sits beside floor and budget. Needs the engines' agreement.
  2026-11-10, engines: later from all three.
  **Layman:** Measures how much of the playing time felt slow, which counts long stutters fairly.
  Kind: feature.
  Source: competitor-research-2026-11-10.

- 💭 [FLED-0058] **report counts hitches against the local median.**
  Count frames longer than k times the rolling median of nearby frames,
  per segment kind. One number for judder that pacing (S14) and the
  worst-10 list do not give. A common practice; no authoritative
  source for the multiplier was found, so k is the engines' call.
  2026-11-10, engines: yes (Vestige, for 3D_E-0795's frame-time gate),
  later (DOOM Ants, UT Ants).
  **Layman:** Counts sudden stutters: frames much slower than the frames around them.
  Kind: feature.
  Source: competitor-research-2026-11-10.

- ✅ [FLED-0063] **alternate stops a Windows command's whole process tree.**
  On Linux and macOS, alternate runs each command in its own process
  group and passes Ctrl-C and SIGTERM on to all of it (FLED-0029,
  spec § 4.15). On Windows it does not yet: the console's Ctrl-C reaches
  the command, and SIGTERM kills only cmd.exe, so an engine behind a
  wrapper can outlive it. Vestige's review suggested
  CREATE_NEW_PROCESS_GROUP with CTRL_BREAK_EVENT, then taskkill /T /F.
  Nothing here runs Windows, so it waits for a Windows engine to test
  it: Vestige's 3D_E-0820, its Windows writer.
  Moved from 0.4.0 to 0.5.0 on 2026-11-11: Vestige, UT Ants and DOOM
  Ants all chose to cut 0.4.0 without it. Leads for a Windows test: UT
  Ants' MSVC build machine, and the user's own Windows box (Vestige is
  asking the user). Using either is the user's call.
  2026-11-11, user decision relayed by Vestige: Windows tests may run on
  the Windows 10 test box Vestige reaches over SSH. Vestige runs them:
  message vestige with the commit and the exact commands; Vestige copies
  the release zip there and sends back the output. No longer blocked.
  2026-11-11: built at 299499a (CREATE_NEW_PROCESS_GROUP, CTRL_BREAK_EVENT,
  taskkill /T /F; SIGBREAK stops alternate); § 4.15 amended, INV-95.
  Gate green here; the Windows test skips on Linux. Sent to Vestige to
  run on its Windows 10 test box, green at 299499a and red with the old
  alternate.py.
  2026-11-11: UT Ants' code review folded at d942254 (KILL no longer
  aliases SIGTERM; no-console Ctrl-Break caught). Vestige's Windows runs
  folded at 4533b7b and 759dfcb. Vestige's Windows 10 box at 759dfcb:
  23 passed, 8 skipped, 0 failed; red with 26a6b84's alternate.py
  (analyser died 0xC000013A). Awaiting DOOM Ants' code review to ship.
  2026-11-12: DOOM Ants' code review folded at 2b23c4c (the Windows test
  times Ctrl-Break to exit; tasklist polled; INV-95's Breaks-when
  narrowed; "did not end after being killed"). Sent to Vestige for a
  Windows re-run: green at 2b23c4c, and red with only
  _signal_windows_tree reverted. Ships when that comes back.
  2026-11-12: Vestige's Windows run at 2b23c4c: green as it stands; with
  the tree signalling emptied [wait] went red but [stubborn] stayed
  green, so the test was tightened at 4621891 and 27bb14e. Vestige asked
  to re-run at 27bb14e.
  2026-11-12: Vestige's Windows 10 box with 27bb14e's test: as committed,
  2 passed ([wait] 2.14 s, [stubborn] 11.37 s). With `return` first in
  _signal_windows_tree, both modes red on the timing asserts alone
  (59.5 s each). DOOM Ants agreed both readings. Shipped.
  **Layman:** On Windows, stopping a test run also stops every program the game's start-up script launched.
  Kind: feature.
  Source: engine-review-2026-11-10.

- ✅ [FLED-0065] **Record how frameledger numbers its 0.x releases.**
  versioning.md § 4 says that inside 0.x only a breaking change bumps
  the MINOR; new features bump the PATCH. frameledger instead cuts one
  MINOR per roadmap milestone (0.3.0 and 0.4.0 carried only Added
  entries). § 4 also asks for a one-line exit condition for 1.0. Write
  both in docs/standards/versioning-overrides.md, with the reason, and
  send it to the three engine sessions for review.
  2026-11-11: written at 06cea97 as docs/standards/versioning-overrides.md;
  sent to the three engines for review.
  2026-11-12: all three reviews folded at dd5d103; UT Ants, Vestige and
  DOOM Ants agreed. Shipped.
  **Layman:** Write down why each roadmap milestone gets its own 0.x number, and what would make frameledger 1.0.
  Kind: doc.
  Source: cut-release-0.4.0-2026-11-11.

- 💭 [FLED-0066] **On Windows, alternate ends processes a command left detached.**
  FLED-0063's taskkill /T finds only processes whose parent still
  runs, so cmd's `start`, or a launcher that spawns and exits, leaves
  processes behind (§ 4.15 says so). UT Ants' review of 299499a: a
  Job Object with JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE catches every
  descendant that does not break away, and would also let Windows check
  for leftovers after a command exits, as Linux does. Not needed by any
  engine yet; considered until one is.
  **Layman:** On Windows, stopping a test run also stops programs the game's script started and walked away from.
  Kind: feature.
  Source: engine-review-2026-11-11.

- ✅ [FLED-0067] **The writer header says which release it came from.**
  include/frameledger.h has no version macro, so a vendored copy is
  pinned only by the engine's own notes: DOOM Ants' copy at v0.2.0,
  Vestige's under external/frameledger/. DOOM Ants' review of FLED-0065:
  an FLED_VERSION macro would let a copied header say its version.
  Needs a § 4.6 amendment, reviewed by the engines, and a release step
  that keeps the macro equal to the release's version.
  2026-11-12: § 4.6 of docs/specs/FLED-0001-run-file-format.md amended
  (FLED_VERSION, INV-96) and built with it: the macro, a bump.json entry
  and tests/test_release.py::test_header_names_the_release. Sent to the
  three engines for review, string-only or with numeric parts asked.
  2026-11-12: Vestige: yes at a6625de, string only. UT Ants and DOOM Ants
  awaited.
  2026-11-12: UT Ants: no objection, string only; it does not vendor the
  header yet, so no MSVC build to report. Its point folded: the test
  also asserts bump.json's exact pattern is in the header. DOOM Ants
  awaited.
  2026-11-12: DOOM Ants: correct and readable, string only. Its caution
  folded: § 4.6 says to vendor the header from a release tag. All three
  engines agreed. Shipped.
  **Layman:** A copied writer file says which frameledger version it is, so an engine knows what it has.
  Kind: feature.
  Source: engine-review-2026-11-11.

- ✅ [FLED-0068] **A header line may be padded with spaces and rewritten in place.**
  `end` and `peak` are header fields known only after the last frame,
  and a streaming writer has already written line 1. Vestige (3D_E-0968)
  chose to pad the header with spaces after its closing brace and
  rewrite the line in place at close. The reader already ignores such
  spaces; docs/specs/FLED-0001-run-file-format.md § 4.1 did not promise
  it. This item adds the promise and its test.
  2026-11-12: built at f89d7ac (§ 4.1, INV-97,
  tests/test_check.py::test_header_may_be_padded; no reader change).
  Vestige: yes; it will report when a real padded run file has gone
  through `check`. UT Ants and DOOM Ants awaited.
  2026-11-12: UT Ants: no objection. Its point folded: § 4.1 says only
  spaces, not tabs, and that the length kept counts the line ending;
  the test also runs with CRLF. DOOM Ants awaited.
  2026-11-12: DOOM Ants: no objection; its writer pads `end` inside the
  JSON and is unaffected. All three engines agreed. Shipped.
  **Layman:** A game can fill in end-of-run figures on the file's first line after the run, without rewriting the whole file.
  Kind: feature.
  Source: engine-request-2026-11-12.

- ✅ [FLED-0069] **A header nested too deep ends in a traceback.**
  UT Ants, reviewing FLED-0035 at e5f2758: json.loads raises
  RecursionError on a header of very many nested brackets, and the
  readers catch only ValueError. baseline.py was fixed with FLED-0035.
  Seen 2026-11-12 on a run file whose `# frameledger` line holds 200,000
  `[`: `check` ends in a traceback with exit 1. budgeting.py's `_header`
  has the same `except ValueError`. Catch RecursionError wherever a
  header's JSON is read, so each gives its own sentence and code.
  2026-11-13: built at 329e62f. ledger.py's JSON reader and budgeting.py's
  header reader catch RecursionError; check reports a breach, budget
  gives exit 3. Code sent to the three engines for review.
  2026-11-13: the three engines' code reviews found no defect.
  **Layman:** A run file whose first line is damaged in one rare way makes frameledger crash instead of saying what is wrong.
  Kind: fix.
  Source: ut-ants-review-2026-11-12.

- ✅ [FLED-0070] **A started_utc that is no real date crashes compare.**
  DOOM Ants, reviewing FLED-0035 at c962eaa: ledger.UTC_RE checks only
  the digits' shape, so `2026-13-01T12:00:00Z` passes `check`, and
  compare._started then raises ValueError from strptime. Seen
  2026-11-12: `check` says the file meets the format; `compare` with
  that run ends in a traceback with exit 1, the code for a regression.
  Older than FLED-0035 (compare._started), but a hand-kept baseline run
  is where a bad date is likeliest. Make an impossible date a `check`
  breach, so every other command gives exit 3 on it. A format rule:
  needs the spec's § 4.2 to say so, and the engines' agreement.
  2026-11-13, engines: all three agreed the rule before it was built. A real
  date and time, year 0001 to 9999, second 60 refused, no schema bump;
  each writer formats gmtime fields and cannot break it.
  Spec: docs/specs/FLED-0001-run-file-format.md § 4.2, INV-102.
  2026-11-13: built; code sent to the three engines for review.
  2026-11-13: the three engines' code reviews found no blocker. Folded: at
  most 20 fraction digits, stated in § 4.2 (DOOM Ants: a longer one was
  refused by Python's own digit limit); `ledger.start_time` and its
  comments.
  **Layman:** A run file with an impossible date, such as month 13, passes the format check and then makes a comparison crash with the code that means "got slower".
  Kind: fix.
  Source: doom-ants-review-2026-11-12.

## 0.6.0 — other people's data

The first steps beyond the three engines: an engine with no writer

can still use the analyser, and a stranger's writer can prove itself.

- 📋 [FLED-0036] **Import a PresentMon capture.**
  Turn a PresentMon CSV into a run that report, floor and survey
  accept, so an engine with no writer gets frame times and pacing.
  It has no passes, so pass reports say so. None of the three
  engines need it; it serves engines beyond them.
  **Layman:** Use frameledger with a free, widely used frame-timing tool, without changing your game.
  Kind: feature.
  Source: engine-answers-2026-11-10.

- 📋 [FLED-0037] **A kit proves a stranger's writer.**
  Sample engine output and the files it must produce, and a strict
  check that also flags what is legal but unwise, so someone writing
  the format from the spec alone can show their writer is right (S7).
  **Layman:** A set of tests anyone can run to prove their game writes the file correctly.
  Kind: test.
  Source: engine-answers-2026-11-10.

- 📋 [FLED-0038] **Runs and is tested on macOS.**
  The analyser and the writer header are built and tested on macOS in
  CI, alongside Linux and Windows (S11).
  **Layman:** Works on Apple computers too.
  Kind: package.
  Source: engine-answers-2026-11-10.

- 🚫 [FLED-0059] **The PresentMon import keeps display and busy-time columns.**
  Widens FLED-0036: bring over displayed time, frames never shown,
  the CPU-busy and GPU-busy split, and animation error, which PresentMon
  writes:
  https://github.com/GameTechDev/PresentMon/blob/main/README-ConsoleApplication.md
  What reached the screen is what judders; busy times give bound-by
  (S2) without passes.
  2026-11-10, engines: no from all three (Linux; none uses PresentMon).
  **Layman:** When reading another tool's capture, keep what was actually shown on screen, not only when frames were sent.
  Kind: feature.
  Source: competitor-research-2026-11-10.

- 🚫 [FLED-0060] **Import a MangoHud frame-time log.**
  MangoHud logs frame times to CSV:
  https://github.com/flightlessmango/MangoHud
  The exact columns are unverified; read a real log before specifying.
  Beside FLED-0036. Needs a discovery sign of success and the engines'
  agreement.
  2026-11-10, engines: no from all three.
  **Layman:** Lets frameledger read logs from a popular Linux performance overlay, so games without frameledger's writer can use it.
  Kind: feature.
  Source: competitor-research-2026-11-10.

- ✅ [FLED-0016] **Warn on a sanitizer build.**
  An optional header field `sanitizers` (an array of strings, such as
  "address") and a `sanitizer_build` trust warning when it is not empty.
  debug_build (FLED-0005) misses a Release build with ASan, which Vestige
  never counts as a reading. Asked by Vestige in its FLED-0005 review.
  2026-11-10: planned for 0.5.0. Vestige still wants it; DOOM Ants says
  it can wait.
  2026-11-13: moved to 0.6.0. The three engines agreed to cut 0.5.0
  without it.
  2026-11-13: first 0.6.0 item. Vestige and UT Ants agreed the order
  0016, 0055, 0053, 0025, then 0036 to 0038; DOOM Ants had not answered.
  Amends docs/specs/FLED-0001-run-file-format.md §§ 4.2 and 4.9.
  2026-11-13: built at 8e9a970 and reviewed by the three engines. Folded:
  an empty or blank name is refused, a long name is cut short. FLED-0071
  queued from DOOM Ants' review.
  **Layman:** Warns when a run came from a build with memory checking switched on, which makes it slow.
  Kind: enhancement.
  Source: vestige-review-2026-10-26.

- ✅ [FLED-0025] **Survey's table drops the paths' shared directory.**
  DOOM Ants, reviewing 3e7006b on 60+ real runs: with every file under
  one long directory, the left-cut file column spends its width on the
  shared prefix ("…OM_Ants/scratch/fled/g-12.csv"). Name the common
  directory once above the table and show each path after it. Not
  needed for 0.3.0.
  2026-11-10: planned for 0.5.0. DOOM Ants, who asked, says it can wait.
  2026-11-13: moved to 0.6.0. The three engines agreed to cut 0.5.0
  without it.
  2026-11-13: built ahead of FLED-0053, whose design answers were
  still out. The heading names a directory two or more files share; one
  file keeps its path. Amends docs/specs/FLED-0001-run-file-format.md
  § 4.13, INV-108.
  2026-11-13: shipped. Vestige, UT Ants and DOOM Ants reviewed it; DOOM
  Ants' finding (a bare ./ names nothing) is folded at 5d8b2c7, the
  other two found nothing.
  **Layman:** When every file sits in one folder, the survey table would show each file's own name instead of the folder again and again.
  Kind: ux.
  Source: doom-ants-review-2026-11-04.

- ✅ [FLED-0053] **compare names an outlier run.**
  compare's spread is the full range, so one bad run makes a measure
  `noisy`. Flag the run outside quartile fences, and warn when one run's
  own frame-to-frame scatter is high. A warning only; verdicts do not
  change. Seen in hyperfine's outlier warning, criterion.rs's outlier
  classes and pyperf check:
  https://bheisler.github.io/criterion.rs/book/analysis.html
  https://pyperf.readthedocs.io/en/latest/cli.html
  Needs the engines' agreement and a spec amendment.
  2026-11-10, engines: yes (DOOM Ants, Vestige), later (UT Ants).
  2026-11-13: moved to 0.6.0. The three engines agreed to cut 0.5.0
  without it.
  2026-11-13: the three engines agreed the design. Built now:
  `outlier_run`, on the frame/wall median only and only where it is
  noisy; a set's highest or lowest run is named when the set's range is
  at least the floor and dropping the run cuts it by more than half.
  Held: `noisy_run`, until the engines' real runs give its limit
  (Vestige owes three captures under 3D_E-0970). Amends
  docs/specs/FLED-0001-run-file-format.md § 4.10, INV-109.
  2026-11-13: shipped at 39dbfc9. Vestige, UT Ants and DOOM Ants
  reviewed it and their findings are folded: a set under three names
  none, each named run has its own sentence, and a base run is named
  once. `noisy_run` is now FLED-0072.
  **Layman:** When one test run went oddly, frameledger says which one, so only that run needs redoing.
  Kind: feature.
  Source: competitor-research-2026-11-10.

- ✅ [FLED-0055] **The header records machine state, and compare warns when it differs.**
  Optional header fields: CPU governor, turbo on or off, on battery or
  mains, CPU clock, CPU and GPU temperature or throttling. compare warns
  when the two sides differ, as FLED-0030 does for load. A governor or
  thermal change mimics a regression. pyperf records and checks these:
  https://pyperf.readthedocs.io/en/latest/system.html
  Same shape as FLED-0016. Needs the engines' agreement and a spec
  amendment.
  2026-11-10, engines: yes from all three. DOOM Ants asks for the load
  average; Vestige for governor and temperature; UT Ants for a warning
  when sides differ (FLED-0030 adds load and clock ones).
  2026-11-13: moved to 0.6.0. The three engines agreed to cut 0.5.0
  without it; DOOM Ants would use it most.
  2026-11-13, engines (FLED-0016 review): the differs-warning also
  covers `sanitizers`. DOOM Ants: compare passes three clean runs
  against three ["address"] runs with warnings only.
  2026-11-13: design agreed by the three engines before it was built.
  Fields: cpu_governor (free text), turbo, power, cpu_clock_mhz,
  cpu_temp_c, gpu_temp_c, throttled. Per run: on_battery, throttled.
  compare: governor, turbo, power and sanitizers differ; CPU clock by
  5%; temperatures by 10 degrees, on peak when every run has one.
  Amends docs/specs/FLED-0001-run-file-format.md §§ 4.2, 4.9 and 4.10.
  2026-11-13: built at 4a67c02 and reviewed by the three engines.
  Folded: setting values compared whole, a list's order ignored, a huge
  header number a breach and not a traceback, a clock below zero.
  **Layman:** Each run notes things like CPU power mode and temperature, and frameledger warns when the two builds were tested under different conditions.
  Kind: feature.
  Source: competitor-research-2026-11-10.

- ✅ [FLED-0071] **A header value cannot forge or flood a warning line.**
  DOOM Ants, reviewing 8e9a970 (FLED-0016): plain-text output quotes a
  header string as written, so a `sanitizers` name of "addr\nWarning: fake"
  prints a forged second Warning line; ESC and NUL pass too. `renderer`
  has the same hole in `software_renderer`, and `build_type` in
  `debug_build`. Markdown output is already cleaned by `render._escape`.
  A list of 5,000 names also gives one very long line, since
  `ledger.clip` cuts each name and not the count. Not checked here:
  which other quoted header fields share it. Decide with the engines
  whether `check` refuses control characters in header strings or the
  text output cleans them.
  2026-11-13, DOOM Ants (FLED-0025 review): survey's table heading now
  carries a directory from the paths given, so a control character in a
  directory name reaches plain-text output there too.
  2026-11-13: the three engines agreed the design. Plain text is cleaned
  where it is written and `check` is unchanged. A control character
  shows as an escape (\n, \x1b, \x00): Unicode's controls, the line and
  paragraph separators and the text-direction marks. A backslash is
  doubled only inside a quoted header value; a path keeps single ones. A
  list quoted in a warning shows five entries, then "and N more"; a long
  value is cut. `--json` is exact. Checked while building: `debug_build`
  cannot carry one, since it fires only when `build_type` is "debug" in
  some case. Amends docs/specs/FLED-0001-run-file-format.md § 4.8,
  INV-110.
  2026-11-13: built at 26583ea; the three engines' code reviews folded at
  44c1a1b. They found callers that quoted file text uncut and a baseline
  file's line reaching standard error raw. Now cut: an undefined header
  key, a refusal's values, the baseline warning's commit, a scene's name
  in a sentence, a budget file's fields. Standard error is cleaned and
  cut. INV-110's test feeds a hostile value to every free-string header
  field. Markdown is its own item.
  **Layman:** A run file cannot make frameledger print a fake warning or a huge line.
  Kind: fix.
  Source: doom-ants-review-2026-11-13.

- 📋 [FLED-0073] **Markdown output cannot reorder or split a line.**
  Split from FLED-0071. `render._escape` makes U+0000 to U+001F and U+007F
  a space, but passes the text-direction marks, U+2028, U+2029 and the
  C1 controls, which `render.visible` shows as escapes in plain text. So
  Markdown has a second, shorter list (`render._CONTROL`). Vestige and
  DOOM Ants, reviewing 26583ea: a rendered pull-request comment is where
  U+202E reorders a verdict, so do it soon. To decide with the engines:
  a space, as now, or a visible escape. Amends FLED-0001 § 4.8.
  **Layman:** A run file cannot make a report pasted into a pull request read in a different order than it was written.
  Kind: fix.
  Source: engine-reviews-FLED-0071-2026-11-13.

## 0.7.0 — seen, not only read

An optional picture of a run. The text report stays the default and

the source of truth; all three engines set that condition, 2026-11-10.

- 📋 [FLED-0039] **An optional picture report.**
  report --html writes one self-contained page with a frame-time
  graph and the worst frames marked, drawn as SVG with the standard
  library alone. Large text; no meaning carried by colour alone; the
  plain sentences come first, as in text. Text stays the default.
  Agreed by all three engines on those conditions.
  **Layman:** A page you open in a browser that shows a run as a graph, easy to read with poor eyesight.
  Kind: feature.
  Source: engine-answers-2026-11-10.

- 💭 [FLED-0061] **The picture report can show two sets' frame-time curves.**
  Percentile curves of old and new runs on one graph. Shows whether a
  regression is a shifted median or a fatter tail. Log viewers for
  MangoHud and Tracy's comparison mode do this. S26 covers one run
  only, so the engines must agree to widen S26 first; otherwise after
  1.0. Builds on FLED-0039.
  2026-11-10, engines: later from all three.
  **Layman:** A picture of old against new frame times, showing whether a build got slower overall or only in its worst moments.
  Kind: feature.
  Source: competitor-research-2026-11-10.

- 📋 [FLED-0072] **compare warns on a run whose own frame times scatter.**
  FLED-0053's held half. Proposed 2026-11-13: `noisy_run`, per run, when
  (75th - 25th percentile) / median of frame/wall is above a limit, over
  segment kinds with at least 100 frames. The three engines agreed the
  measure and held the number until real runs give it; 0.25 was a guess.
  DOOM Ants warns that quartiles of one run's frames miss a burst.
  Waiting on: Vestige's three quiet-machine captures under 3D_E-0970;
  UT Ants has no ledgers yet. Needs a spec amendment to FLED-0001 § 4.9
  or § 4.10.
  2026-11-13, Vestige's figures (message 1974; commit 0508b49, Release,
  RX 6600, 1920x1080, meadow-flythrough, no vsync, about 2490 frames a
  run, warm-up included). Five quiet runs: (p75 - p25) / median of
  frame/wall is 0.105 to 0.115; their medians span 1.06%. One run under
  load, taken right after a build: 0.2194, p99 81.663 ms against about
  14.5. So for this scene a limit between 0.12 and 0.21 separates them;
  one loaded sample, so the upper end is soft. Vestige's caution: the
  camera moves, so much of the 0.11 is the path, not noise, and a still
  scene would read lower. Still waiting on: UT Ants and DOOM Ants runs.
  **Layman:** When one test run was jumpy from frame to frame, frameledger says which one.
  Kind: feature.
  Source: split-from-FLED-0053-2026-11-13.

- 💭 [FLED-0074] **Read a gzip-compressed run file.**
  Vestige, 2026-11-13: `check run.csv.gz` reads the gzip bytes as a run
  with no close line ("unfinished") rather than refusing it as not a run
  file. Five of its runs are 29 MB, 2.2 MB gzipped, so a baseline's runs
  are too big to commit. Two parts: say plainly that a .gz is not a run
  file, and perhaps read one. Low priority by Vestige's word. Not
  checked here: the message `check` gives.
  **Layman:** Keep run files compressed, so a set of reference runs is small enough to store beside the code.
  Kind: feature.
  Source: vestige-2026-11-13.

## 0.8.0 — stable promises (beta)

What a stranger can rely on not to change under them: the file

format, the JSON output and the commands.

- 📋 [FLED-0040] **The run-file format is promised stable.**
  Format spec 1.0: what may change in a later schema version and
  what never will, and how long older versions keep analysing (S6).
  **Layman:** A promise that files written today will still be read by future versions.
  Kind: doc.
  Source: engine-answers-2026-11-10.

- 📋 [FLED-0041] **A published schema for every --json result.**
  A JSON Schema per command, shipped in the release and checked by
  the tests against every command's output, so scripts can rely on it.
  **Layman:** Programs that read frameledger's results get a fixed description of them.
  Kind: feature.
  Source: engine-answers-2026-11-10.

- 📋 [FLED-0042] **A support and deprecation policy.**
  How a flag or field is retired (warned for a release first), which
  Python versions and systems are supported, and for how long.
  **Layman:** Says how long features and systems are supported and how changes are announced.
  Kind: doc.
  Source: engine-answers-2026-11-10.

## 0.9.0 — ready for strangers (release candidate)

Someone who has never seen the three engines can install

frameledger, wire it into their engine and get help.

- 📋 [FLED-0043] **Install with pip or pipx.**
  A frameledger package on PyPI with a `frameledger` command,
  still standard library only. The release zip stays for engines that
  pin a hash.
  **Layman:** Install it with one standard command.
  Kind: package.
  Source: engine-answers-2026-11-10.

- 📋 [FLED-0044] **A user guide and a quick start.**
  From nothing to a first report: write the file (by hand, with the
  header, or by import), run each command, read its answer. Worked
  examples for C and C++. Checked by running every step
  (verify-instructions).
  **Layman:** A guide that takes a newcomer from nothing to their first report.
  Kind: doc.
  Source: engine-answers-2026-11-10.

- 📋 [FLED-0045] **Contributing and support files.**
  CONTRIBUTING, issue and pull request templates, a code of conduct,
  and where to ask for help.
  **Layman:** Tells outsiders how to report problems and help out.
  Kind: doc.
  Source: engine-answers-2026-11-10.

## 1.0.0 — fully working

Every sign in docs/discovery.md met, measured and reviewed.

- 📋 [FLED-0046] **A million-row survey finishes in under a minute.**
  Measure S19 on the owner's machine and keep a benchmark in the
  gate so it stays true.
  **Layman:** Checking a very large batch of test runs takes less than a minute.
  Kind: perf.
  Source: engine-answers-2026-11-10.

- 📋 [FLED-0047] **The reader is fuzzed with broken files.**
  Random and mangled run files, generated with the standard library,
  never crash the reader: each gives a format breach or LedgerError.
  **Layman:** Feed the tool thousands of broken files to make sure none of them crash it.
  Kind: test.
  Source: engine-answers-2026-11-10.

- 📋 [FLED-0048] **Full code, test, security and README reviews before 1.0.**
  review-code, review-tests, review-readability and review-readme
  over the whole project, with every finding closed or recorded.
  **Layman:** A full independent check of the whole tool before calling it finished.
  Kind: audit-fix.
  Source: engine-answers-2026-11-10.

- 📋 [FLED-0014] **Each engine finds and fixes a bottleneck with it.**
  Vestige (3D_E-0786), UT Ants (UTA-0437) and DOOM Ants each write run
  files, and each finds a bottleneck from a report and fixes it. UT
  Ants' c80d41d/d9009b1 pair is a ready known-slowdown case. At least
  one engine writes from the spec alone. Claims S1, and S7 in use.
  Status 2026-11-05. DOOM Ants: writer is DOOM-0502 (shipped
  2026-10-30, header pinned at v0.2.0); consumer is DOOM-0431 (bench
  harness, parked). Used for per-pass A/Bs of two features, but read
  with a private script, not compare (see FLED-0026). No bottleneck
  found and fixed from a report yet. UT Ants: UTA-0437 not started;
  the c80d41d/d9009b1 pair not yet run.
  Vestige 2026-11-05: 3D_E-0786 shipped 2026-10-31 (--frame-log,
  header v0.1.0). check and report used on a real run; no bottleneck
  found and fixed yet; GPU contention has blocked interleaved run
  sets. Its writer leaves `inputs` empty, so compare would refuse its
  runs; Vestige is filing that on its own roadmap. No frameledger
  finding.
  2026-11-10: moved from 0.3.0 to 1.0.0. It waits on the engines' use,
  not on code, so it gates 1.0 rather than 0.3.0. Engines' status:
  nothing in frameledger blocks any of them. Vestige is blocked by
  other GPU users (FLED-0030); UT Ants' writer UTA-0437 sits in its
  own 1.0.0; DOOM Ants uses it with a private script (FLED-0031).
  **Layman:** The real test: each game finds something slow with this tool and fixes it.
  Kind: investigate.
  Source: design-2026-10-24.
  Blocked-by: FLED-0007.

- 📋 [FLED-0015] **A version anyone can use.**
  Offer frameledger to engines other than the three it serves. Not
  started before the three engines' requirements are met. What "anyone
  can use" needs (install, documentation, a stable format promise,
  support) is to be decided then.
  2026-11-10: planned for 1.0. The engines' answers and the owner's request
  split it into the 0.6.0 to 0.9.0 items; it is met when they ship
  and a stranger's engine is analysed (S7).
  **Layman:** A version of frameledger that any game developer can pick up and use, not only our three engines.
  Kind: feature.
  Source: user-request-2026-10-24.
  Blocked-by: FLED-0014, FLED-0036, FLED-0037, FLED-0038, FLED-0040, FLED-0041, FLED-0042, FLED-0043, FLED-0044, FLED-0045.

## After 1.0 — plugins and more

After frameledger does what Vestige, UT Ants and DOOM Ants need (the owner, 2026-10-24: build it for our own requirements first).

- 💭 [FLED-0049] **Plugins for importers and report sections.**
  Let an engine add its own importer or report section without
  changing frameledger. Decided after 1.0, from what users ask for.
  **Layman:** Others can add their own features without changing frameledger itself.
  Kind: feature.
  Source: engine-answers-2026-11-10.

- 💭 [FLED-0050] **Writers for more languages.**
  Rust, C# and others, each built from the spec and proved with the
  writer kit. Decided after 1.0, from who asks.
  **Layman:** Ready-made writers for games built in other programming languages.
  Kind: feature.
  Source: engine-answers-2026-11-10.

- 💭 [FLED-0051] **Trends across many commits.**
  Show how a measure moved across a range of commits, from runs the
  engine keeps. The analyser stays stateless.
  **Layman:** See how a game's speed changed over many versions.
  Kind: feature.
  Source: engine-answers-2026-11-10.

- 💭 [FLED-0027] **compare can judge an ext row's frame-to-frame jump at p99.**
  DOOM Ants logs ext.doom/view_lag per frame (camera time minus
  clock, in tics). It needs the p99 of its frame-to-frame change, not
  its median, so it wrote a private script. compare judges no ext rows
  (spec § 4.10). Considered until a second engine asks or DOOM Ants
  says it blocks real work.
  2026-11-10: moved after 1.0. DOOM Ants says it does not block it; UT
  Ants writes no ext rows; still considered.
  **Layman:** Let the comparison check how much an engine's own measurement jumps between frames, not only its typical value.
  Kind: feature.
  Source: doom-ants-feedback-2026-11-09.

- 💭 [FLED-0062] **compare shows a rank-based effect size beside its verdict.**
  A rank-based effect size such as Cliff's delta, which Mozilla's
  PerfCompare shows:
  https://firefox-source-docs.mozilla.org/testing/perfdocs/perfcompare.html
  Shown only, never deciding: at three runs a side, the smallest
  two-sided Mann-Whitney p is 0.1. The spread-and-floor rule (§ 4.10)
  stays the verdict.
  2026-11-10, engines: later from all three, after 1.0 as planned.
  **Layman:** Adds a figure for how strongly the new build differs, alongside the existing verdict.
  Kind: feature.
  Source: competitor-research-2026-11-10.
