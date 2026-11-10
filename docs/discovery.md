# frameledger — Discovery

> **Purpose — so that later, anyone can tell whether the thing being
> built is still the thing that was wanted.**

**This document is a gate.** Design does not start until it is agreed —
`~/.claude/workflow.md` § 2. The owner delegated this gate to the three
engine sessions on 2026-10-24: each agrees it, and each *never* line,
for its own engine.

**Status:** agreed (2026-10-24) by Vestige, UT Ants and DOOM Ants, on
the owner's delegation. The engines' answers it is built from:
[2026-10-24 customer answers](reviews/2026-10-24-discovery-customer-answers.md).
S21 to S27, S11's macOS and the picture report's line were added on
2026-11-10 (FLED-0028), from the engines' answers that day, which
`ROADMAP.md`'s 0.4.0 to 1.0.0 items record. Those additions await the
three engines' agreement.

## The problem

Three game engines on this machine — Vestige, UT Ants and DOOM Ants —
each measure their own frame times in their own way. None of them can
say, from one run, which part of a frame costs the most, or whether the
frame waited on the CPU or the GPU.

- Vestige logs a rolling average about once a second, so a single slow
  frame disappears into it.
- UT Ants writes one set of medians per run.
- DOOM Ants prints profile lines to the terminal about once a second.

So a bottleneck has to be hunted by hand, in each engine separately, and
a change cannot be shown to be faster or slower by a number all three
agree on.

**The goal behind it** (the owner, 2026-10-24): each engine holds at
least 60 frames per second. frameledger exists to find what stops a
frame fitting in 16.67 ms, and to show when a change has fixed it.

## Who it is for

- **The owner of the three engines**, who wants to find where each one
  loses frame time. They are not a programmer and are partially
  sighted, so every report opens with plain sentences before any
  table, and no meaning is carried by colour alone.
- **A Claude Code session working on one engine**, which needs to know
  whether its change made the engine faster, slower, or neither — as a
  verdict and an exit code it can act on, locally and in CI, and as
  machine-readable output for its scripts.

**When finished:** a tool any engine can use. Someone who has never seen
these three engines writes the file format from its spec alone, and the
analyser reads their runs.

## Signs it is working

- **S1** — In each of the three engines, a bottleneck has been found
  from a frameledger report and then fixed.
- **S2** — One analyser command on one run opens with one plain
  sentence, then says which pass costs the most, per segment kind, and
  what share of frames were CPU-bound or GPU-bound. Where the run does
  not overlap CPU and GPU work, it says the share does not apply rather
  than printing one.
- **S3** — The report lists the worst frames by segment and frame
  number, and the owner can go to that place in the game and see it.
- **S4** — Comparing two labelled sets of interleaved runs of one build
  reports no difference, and comparing a build against one with a known
  slowdown reports that slowdown.
- **S5** — The analyser refuses to compare two runs that are not
  comparable, such as another resolution, render scale, build type,
  input or display kind. It warns on a run it should not trust, such as
  a Debug build, a software renderer, too few frames, or a camera cut
  inside a measured stretch. Frames with a missing timing are counted
  as missing, never as zero. A refusal can be overridden one field at a
  time, with a stated reason. The report names every override, and its
  reason, in its opening sentence.
- **S6** — Each engine moves to a new frameledger release by changing
  one pinned version, and its older run files still analyse.
- **S7** — A writer built from the format spec alone, by a session that
  has not read the analyser's code, produces files the analyser accepts.
- **S8** — A floor check with a set frame rate and warm-up exits
  non-zero, after the warm-up, on either of two failures, each reported
  separately:
  - a one-second window whose frame rate falls below the set rate. A
    window's frame rate is the frames completed in it divided by its
    length, never a mean of per-frame rates;
  - a single frame longer than a budget set per run. The default budget
    is the set rate's frame time, 16.67 ms at 60 FPS; a smaller one
    leaves headroom for gameplay.
- **S9** — One command ranks many runs, such as one per map, by their
  slowest frames, flags those over budget, and names each flagged run's
  costliest pass.
- **S10** — An engine using the optional C writer header shows the same
  frame times with the writer on as with it off, to within the run's
  own spread.
- **S11** — The analyser runs on Linux, Windows and macOS, and a run
  file written on any of them analyses the same as one written on
  Linux.
- **S12** — Given a budget per pass, a check names each pass over its
  budget and exits non-zero on any breach.
- **S13** — In a run with more than one frame in flight, each GPU
  timing counts against the frame that submitted the work, and the
  report still gives the CPU-bound and GPU-bound share.
- **S14** — The report gives a frame-to-frame variation figure beside
  the 1% low, so a run that passes S8 but judders shows it.
- **S15** — Given two surveys from two builds, the report flags each
  run whose pass got slower by more than that pass's run-to-run spread.
- **S16** — A comparison judges each pass by its own spread, so a pass
  that changed is found even when the frame total is too noisy to give
  a verdict.
- **S17** — A bisect mode turns one measure into an exit code `git
  bisect run` understands (good, bad or skip), and a dry run prints the
  verdict a given value would get.
- **S18** — A check command tells whether a run file meets the format
  spec and exits non-zero when it does not, with nothing installed, on
  Linux and Windows.
- **S19** — A survey of about a million rows is analysed in under a
  minute on the owner's machine.
- **S20** — The analyser runs headless: with no display, no terminal,
  no input and no locale set, every command gives its normal output and
  exit code, so it runs under CI and `git bisect run` (the owner,
  2026-10-26). Its output may go to a file, a pipe that closes early, or
  nowhere; a write that fails gives exit 3, or 128 under `bisect`, never
  a code that means a verdict (UT Ants, Vestige).
- **S21** — Given the command that runs each build, one command runs
  the old and new builds in turn (old, new, old, new), at least three
  runs a side, then compares the files they wrote as S4 does. It fills
  a placeholder in each command with that run's own file name, so no
  run overwrites another (DOOM Ants, Vestige). It times nothing and
  writes no run file; each engine still does both.
- **S22** — A run can record its peak CPU load and its peak GPU busy
  share during the run, not only at its start and end. A run is taken
  under load when either peak passes its limit. CPU load is a share of
  the whole machine, so one limit fits any CPU count. The format spec
  sets both limits, and a flag can change them (UT Ants). A compare
  that uses a run taken under load names that run and is inconclusive
  (exit 2, worth re-running) rather than giving a verdict. It warns
  when the two sides' CPU load, GPU busy share or GPU clock differ by
  more than a limit the format spec sets.
- **S23** — One command judges several named variants against one
  base, such as the full frame against each effect switched off in
  turn. Each variant is judged against the base as S16 judges new
  against old. The run helper (S21) runs them in turn, base and each
  variant, several runs each, so machine drift is not read as an
  effect's cost (UT Ants).
- **S24** — A baseline file, which the engine keeps, names a set of
  reference runs. A compare or the run helper (S21) takes it in place
  of the old runs. Those runs keep their headers, so S5's refusals and
  warnings apply to them: a baseline taken on one GPU or graphics API
  is refused against runs from another (Vestige). The analyser itself
  still keeps nothing between runs.
- **S25** — A PresentMon capture becomes a run that the report, the
  floor check and the survey accept. Where a report needs passes, it
  says the run has none rather than failing.
- **S26** — An optional report page shows one run's frame times as a
  graph, with the worst frames marked. It is one self-contained file,
  drawn with the standard library alone, in large text, with no
  meaning carried by colour alone. Its plain sentences come first.
- **S27** — Three promises are written down: what may change in a
  later format version, what never will, and how long older versions
  keep analysing; a schema for every command's JSON result, which the
  tests check each command's output against; and how a flag or field
  is retired, and which Python versions and systems are supported.

## What it deliberately does not do

- **never** — Time or capture anything inside an engine. Each engine
  keeps its own timing and run code. The optional writer only formats
  what the engine hands it.
- **never** — Require the writer. An engine may write the file from the
  spec alone.
- **never** — Depend on anything beyond the Python 3 standard library
  for the analyser.
- **never** — Replace a GPU or CPU profiler such as RenderDoc or Tracy.
  frameledger says which pass and which frames to look at; a profiler
  says why.
- **never** — Make charts the default. The picture report (S26) is
  optional; plain text comes first.
