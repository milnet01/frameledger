# frameledger — Discovery

> **Purpose — so that later, anyone can tell whether the thing being
> built is still the thing that was wanted.**

**This document is a gate.** Design does not start until it is agreed —
`~/.claude/workflow.md` § 2.

**Status:** draft, 2026-10-24.

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

## Who it is for

- **The owner of the three engines**, who wants to find where each one
  loses frame time. They are partially sighted, so the answer has to be
  short plain text, not a chart.
- **A Claude Code session working on one engine**, which needs to know
  whether its change made the engine faster, slower, or neither — as a
  verdict and an exit code it can act on.

**When finished:** a tool any engine can use. Someone who has never seen
these three engines writes the file format from its spec alone, and the
analyser reads their runs.

## Signs it is working

- **S1** — In each of the three engines, a bottleneck has been found
  from a frameledger report and then fixed.
- **S2** — One analyser command on one run says which pass costs the
  most, and what share of frames were CPU-bound or GPU-bound.
- **S3** — The report lists the worst frames by segment and frame
  number, and the owner can go to that place in the game and see it.
- **S4** — Comparing a build against itself reports no difference, and
  comparing it against a build with a known slowdown reports that
  slowdown.
- **S5** — The analyser refuses to compare two runs that are not
  comparable (another resolution, another build type, another input),
  and warns on a run it should not trust (a Debug build, a software
  renderer, too few frames).
- **S6** — Each engine moves to a new frameledger release by changing
  one pinned version, and its older run files still analyse.
- **S7** — A writer built from the format spec alone, by a session that
  has not read the analyser's code, produces files the analyser accepts.

## What it deliberately does not do

- **never** — Capture frames inside the engine. Each engine keeps its
  own run and capture code, and writes the shared file.
- **never** — Depend on anything beyond the Python 3 standard library
  for the analyser.
- **never** — Replace a GPU or CPU profiler such as RenderDoc or Tracy.
  frameledger says which pass and which frames to look at; a profiler
  says why.
- **not yet** — Charts or an HTML report. Plain text comes first.
- **not yet** — Publishing outside this machine. It stays local until
  the owner says otherwise.
