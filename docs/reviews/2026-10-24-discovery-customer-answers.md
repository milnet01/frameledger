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

Awaiting reply.
