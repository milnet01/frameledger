# Changelog

All notable changes to frameledger are documented in this file.

The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html). The format
contract is `~/.claude/standards/changelog-format.md` § 4.

The `[Unreleased]` block stays at the top, always, even when empty.

## [Unreleased]

### Added

- `check FILE…` says whether each run file meets the format, with exit
  codes 0, 1 and 3 and a `--json` result (FLED-0002).
- `--selftest` and `--version` (FLED-0002).
- `report FILE` says where one run's frame time went: passes ranked by
  time spent per segment kind, CPU-bound and GPU-bound share (or that
  it does not apply), the worst frames with their costliest pass, and
  the static line. Frames with no GPU result are counted, never taken
  as zero (FLED-0003).
- `floor FILE --fps N` says whether a run held a frame rate in every
  one-second window after the warm-up, and whether any single frame took
  longer than a budget. Exit 0 pass, 1 fail, 2 inconclusive (dropped
  rows, an unfinished run, a gap in the timeline, or no full window),
  3 error (FLED-0004).
- `report` and `floor` warn when a run's numbers should not be trusted:
  a Debug build, a software renderer, a busy CPU or GPU before the run,
  segments timed before they settled, fewer than 100 measured frames,
  or a camera cut in the middle of a segment. A warning never changes
  the verdict or the exit code. New optional header field
  `settled_frames` (FLED-0005).
- `include/frameledger.h`, an optional writer an engine can include
  instead of writing run files itself. One header, usable from C and
  C++. It never allocates and writes no files: the engine hands it a
  buffer and writes the bytes out when it chooses. A full buffer drops
  rows and counts them in the file. Numbers come out the same whatever
  the machine's language (FLED-0006).
