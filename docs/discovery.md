# frameledger — Discovery

> **Purpose — so that later, anyone can tell whether the thing being
> built is still the thing that was wanted.**

**This document is a gate.** Design does not start until it is agreed —
`~/.claude/workflow.md` § 2. The owner delegated this gate to the three
engine sessions on 2026-10-24: each agrees it, and each *never* line,
for its own engine.

**Status:** draft, 2026-10-24. The engines' answers it is built from:
[2026-10-24 customer answers](reviews/2026-10-24-discovery-customer-answers.md).

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
  sighted, so every report opens with one plain sentence before any
  table.
- **A Claude Code session working on one engine**, which needs to know
  whether its change made the engine faster, slower, or neither — as a
  verdict and an exit code it can act on, locally and in CI.

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
  as missing, never as zero.
- **S6** — Each engine moves to a new frameledger release by changing
  one pinned version, and its older run files still analyse.
- **S7** — A writer built from the format spec alone, by a session that
  has not read the analyser's code, produces files the analyser accepts.
- **S8** — A floor check with a set frame rate and warm-up exits
  non-zero when any one-second window after the warm-up falls below it.
- **S9** — One command ranks many runs, such as one per map, by their
  slowest frames and flags those over budget.
- **S10** — An engine using the optional C writer header shows the same
  frame times with the writer on as with it off, to within the run's
  own spread.
- **S11** — The analyser runs on Linux and Windows, and a run file
  written on Windows analyses the same as one written on Linux.

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
- **not yet** — Charts or an HTML report. Plain text comes first.
