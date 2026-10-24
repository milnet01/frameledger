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
