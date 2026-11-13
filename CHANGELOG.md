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

- **The header records the machine's state, and `compare` warns when the two sides differ** (FLED-0055)
  Seven optional header fields: `cpu_governor` (text, the writer's own words), `turbo` (true or false), `power` (`mains` or `battery`), `cpu_clock_mhz` (`start` and `end`), `cpu_temp_c` and `gpu_temp_c` (`start`, `end` and an optional `peak`, in degrees Celsius) and `throttled` (true or false). A run on battery warns `on_battery`, and a throttled one `throttled`. `compare` warns `governor_differs`, `turbo_differs`, `power_differs` or `sanitizers_differs` when the two sides' values differ; `cpu_clock_differs` when the median clocks differ by more than 5%; and `cpu_temp_differs` or `gpu_temp_differs` when the median temperatures differ by more than 10 degrees, judged on `peak` when every run has one and on `end` otherwise. Each needs the field in every run. A warning changes no verdict and no exit code. No schema change.

- **`compare` names the run that stands apart** (FLED-0053)
  When the frame time is too noisy to judge, `compare` warns `outlier_run` for a run far from the rest of its set, as in "new-3 stands apart from the other new runs: its frame/wall median in view segments is 20.000 ms and theirs lie from 16.000 to 16.100 ms; re-run it". A set's highest or lowest run is named when dropping it cuts the set's range by more than half. So one run can be taken again instead of the whole set. Each named run has its own sentence. The warning changes no verdict and no exit code.

- **A run from a sanitizer build carries a warning** (FLED-0016)
  The header takes an optional `sanitizers` field: a list of the sanitizers the build was compiled with, such as `["address"]`, and `[]` for none. Where the list names any, every command that gives trust warnings adds `sanitizer_build`, quoting the names. A warning changes no verdict and no exit code. `check` refuses a `sanitizers` that is not a list of strings, or that holds an empty or blank one. No schema change: a file without the field reads as before.

### Changed

- **`survey`'s table names a shared folder once** (FLED-0025)
  When two or more surveyed files are all in one directory, the table's heading names it, as in "Runs, slowest first, each file in runs/:", and each row shows the path after it. Before, a long shared directory filled the file column and hid the names. The sentences above the table and `--json` still give whole paths.

### Fixed

- **Text from a run file or a path cannot forge or flood a line** (FLED-0071)
  A header value holding a line break could print a second line reading "Warning: …", and an escape character reached the terminal. Plain text now shows such a character as an escape, `\n` or `\x1b`: the control characters, the line separators and the marks that set text direction. A quoted header string also shows a backslash doubled; a path keeps single backslashes, so a Windows path can still be copied. A `sanitizers` list names its first five entries, then "and N more", and a long `renderer`, `device`, `driver` or `os` is cut to 60 characters. `--json` is unchanged and exact.

- **A huge whole number in the header is refused in a sentence** (FLED-0055)
  A header number such as a `gpu_clock_mhz.end` of 1 followed by 400 zeros ended `check` in a traceback. It is now a `header` breach, as any other bad value.

## [0.5.0] - 2026-11-13

**Theme:** Variants and baselines.

### Added

- The release archive, `frameledger-v0.5.0.zip`: `frameledger.pyz`, its
  launchers `frameledger` and `frameledger.cmd`, `include/frameledger.h`
  and `LICENSE`. SHA256
  `0dbe624c4b26bb5d986461973a6df040b3d539412ffcdbb8ec02efa864b09ae3`.
  `python3 -I scripts/build_release.py OUTDIR v0.5.0`, run on the tag,
  rebuilds it; the release workflow does so under Python 3.10.22.

- **`compare` and `alternate` take a saved baseline** (FLED-0035)
  `--baseline FILE` names kept runs in a file and takes the place of `--old`, or of `--base` with `--variant`. The file is a first line `# frameledger-baseline {"schema":1}` and then one run file's path per line; a relative path starts at the file's own folder. The kept runs are judged as any old runs, so the same refusals and warnings apply. `alternate --baseline` runs only the new build's command. Since nothing alternates with a baseline, the warning `baseline_not_interleaved` names its commit, the day it was taken and its age; `baseline_driver_differs` and `baseline_os_differs` warn when the driver or the system has changed since. Every `compare` and `alternate` JSON result gains a `baseline` key, null without the flag. A listed run file that is missing is exit 3, naming its line.

- **`compare` and `alternate` judge named variants against one base** (FLED-0034)
  `compare --base FILE… --variant NAME FILE…`, with `--variant` given once per variant, judges each variant's runs against the base runs exactly as `compare` judges new against old. Runs are named `base-1`, `no_bloom-1` and so on. The variants are ranked by the change in one measure, the largest saving first: the first `--measure` name, or `frame/wall`. A variant that cannot be compared with the base is unjudged and the others go on. Exit 1 when any variant fails, 2 when any is inconclusive or unjudged, 3 when none could be judged. `alternate --base CMD --variant NAME CMD` runs every side in rounds that reverse, base, a, b, b, a, base, …, then compares the files that way.

- **On Windows, stopping `alternate` stops the command's whole process tree** (FLED-0063)
  Each command runs in its own console process group. Ctrl-C, Ctrl-Break or a terminate signal is passed on as Ctrl-Break, and a command still running 10 seconds later is ended with `taskkill /T /F`, so an engine started through `cmd.exe` or a script no longer outlives the run. A process whose parent has already exited is not found.

- **The writer header says which release it came from** (FLED-0067)
  `include/frameledger.h` defines `FLED_VERSION`, a string such as `"0.5.0"`: the release the header shipped in. A copy vendored into an engine names its own version.

- **A header line may be padded with spaces** (FLED-0068)
  Spaces after the closing brace of a `# frameledger` line are ignored, and the format now promises it. A writer that learns the header's `end` and `peak` only after the last frame can pad line 1 and rewrite it in place at close.

### Changed

- A process group that outlives its kill is reported as "did not end after being killed", where it said "after SIGKILL": on Windows the kill is `taskkill` (FLED-0063).

### Fixed

- **A long warm-up is shown as given** (FLED-0024)
  `floor`, `budget` and `survey` named a `--warmup-s` of a million seconds or more in rounded exponent form, such as "the 1e+09 s warm-up". Their sentences now give the warm-up in full, "the 999999999 s warm-up". A warm-up with more than six significant digits, such as 12345.678, was rounded the same way, and one under 0.0001 s was in exponent form; both are now given in full too.

- **A `started_utc` that is no real date is a format breach** (FLED-0070)
  `check` tested only the digits' shape, so `2026-13-01T12:00:00Z` passed, and `compare` with that run then ended in a traceback with exit 1, the code for a regression. `check` now reports a header breach for a month, day, hour, minute or second that does not exist, 29 February outside a leap year, second 60 and year 0000. A fraction of a second may have at most 20 digits, the limit the row fields already have. Every command that judges the file gives exit 3. The format says so in its header section.

- **A run or budget file nested too deep is refused in a sentence** (FLED-0069)
  A `# frameledger` or `# frameledger-budget` line holding very many nested brackets, such as 200,000 `[`, ended `check`, `budget` and every command that reads a run file in a traceback with exit 1. `check` now reports a breach on that line, "not valid JSON: it is nested too deep to read", and `budget` gives exit 3 with "the header is not one JSON object".

## [0.4.0] - 2026-11-11

**Theme:** A/B runs you can trust.

### Added

- The release archive, `frameledger-v0.4.0.zip`: `frameledger.pyz`, its
  launchers `frameledger` and `frameledger.cmd`, `include/frameledger.h`
  and `LICENSE`. SHA256
  `fad27de1049d288d700a0c6b9d6028f0938b3a154a5de4ef946385d3ae3deb0c`.
  `python3 -I scripts/build_release.py OUTDIR v0.4.0`, run on the tag,
  rebuilds it; the release workflow does so under Python 3.10.22.

- **`alternate` runs the old and new builds in turn, then compares them** (FLED-0029)
  `alternate --old CMD --new CMD --out DIR` runs each build's command five times by default (`--runs N`, 3 to 100), filling `{run}` in each command with that run's own file, `DIR/old-1.csv` and so on. Runs go in pairs, old-1, new-1, new-2, old-2, …, so a machine that drifts over the batch does not read as a change. `--warmup W` runs untimed runs first. A run that fails or is interrupted stops the rest, exit 3, and its file is deleted. Otherwise the files are compared exactly as `compare` would, and the text shows `compare`'s tables (FLED-0064).
- **A compare names a run taken on a busy machine, and gives no verdict** (FLED-0030)
  The header's `load` and `gpu_busy_pct` may carry a `peak`: the highest share other programs used while the run ran, the run's own work left out. A run whose `load.peak` is above `--max-load` (default 0.25) or whose `gpu_busy_pct.peak` is above `--max-gpu-busy` (default 20) was taken under load: the compare names it and is inconclusive, exit 2. New warnings, `load_differs`, `gpu_busy_differs` and `gpu_clock_differs`, say when the old and new runs started under different load or ended at different GPU clocks. `compare --by-scene` and `alternate` take the same flags.
- **A compare can judge only the measures you name, and show each run's value** (FLED-0031)
  `--measure CATEGORY/NAME`, such as `--measure gpu/trace`, given once per measure, keeps only those measures: the verdict, the tables and the counts use nothing else. A name matches exactly, case included, and one that no run has stops the compare, exit 3, so a misspelt name never passes. If every named measure is missing from some runs, nothing is judged and the compare is inconclusive, exit 2. With `--measure`, `compare`'s text adds a table with one row per run and one column per named measure. `compare --by-scene` and `alternate` take the same flag; `--by-scene` gives no table.
- **Every command can print Markdown** (FLED-0032)
  `--markdown` prints the text as GitHub-flavoured Markdown, to paste into a pull request, a commit or a note. The opening sentences are a list and each table is a Markdown table, lined up so it also reads unrendered. Nothing is cut to fit 100 columns, so long names and paths stay whole. Characters Markdown would read as formatting are escaped, so a path or a static value cannot break a table. `--markdown` with `--json` is refused, exit 3.
- **frameledger runs by name** (FLED-0033)
  The release zip holds two launchers beside `frameledger.pyz`: `frameledger` for Linux and `frameledger.cmd` for Windows. With one on PATH, `frameledger report run.csv` runs from any folder; the README's Install section says how. Each passes its arguments through unchanged and exits with the analyser's code. The Linux launcher follows a symlink to find the analyser. In a source checkout, `launcher/` holds the same launchers, and they run `src/frameledger`. A launcher copied away from the analyser, rather than linked, says so and exits 127 (9009 on Windows). The Windows launcher uses the `py` launcher where it is installed, and `python` otherwise.

## [0.3.0] - 2026-11-10

**Theme:** Many runs surveyed.

### Added

- The release archive, `frameledger-v0.3.0.zip`: `frameledger.pyz`,
  `include/frameledger.h` and `LICENSE`. SHA256
  `36f65f6380028f1c1855631497db50e7ba90c23443171ca64b4dfcbf1ff1697e`.
  `python3 -I scripts/build_release.py OUTDIR v0.3.0`, run on the tag,
  rebuilds it; the release workflow does so under Python 3.10.22.

- **`survey` ranks many runs and flags the ones `floor` would fail** (FLED-0012)
  `survey FILE… --fps N` (or `--budget-ms B`) judges each run with `floor`'s single-frame check, after `floor`'s 2 s warm-up, and flags a run with more frames over the budget than `--allow-frames`. A flagged run names its slowest frame and that frame's top pass. Runs rank by their worst segment kind's 99th-percentile frame time, naming the worst segment; a kind needs 100 frames to rank. A file that cannot be read is listed, not fatal. Exit 1 when a run is flagged, 2 when one could not be judged, 0 otherwise.
- **`compare --by-scene` compares two builds map by map** (FLED-0013)
  Files are grouped by their header's `scene`, and each scene's old runs are compared with its new as `compare` would compare them alone. A failing scene names the measure that got slower and the segment where it changed most; failing scenes rank by that change. A scene with fewer than three runs a side, or one that cannot be compared, is listed as unjudged and the rest go on. Exit 1 when a scene fails, 2 when one is inconclusive or unjudged, 3 when no scene could be judged.

## [0.2.0] - 2026-11-04

**Theme:** Two builds compared.

### Added

- The release archive, `frameledger-v0.2.0.zip`: `frameledger.pyz`,
  `include/frameledger.h` and `LICENSE`. SHA256
  `cfb692516c48e45534657b1ce5dc903f1e91156716b7265063b579d6b930b01c`.
  `python3 -I scripts/build_release.py OUTDIR v0.2.0`, run on the tag,
  rebuilds it; the release workflow does so under Python 3.10.22.

- **`report` shows frame pacing** (FLED-0011)
  A run can hold its frame rate and still judder. Per segment kind, `report` now gives the median and 99th-percentile change in frame time between neighbouring frames, never across a load, a missing frame or a segment change. The JSON's `pacing` list carries it; the text gives a `wall change (pairs)` row under `wall`.

- **`compare` judges memory too** (FLED-0018)
  Each `mem` measure is judged in MB, with `--min-mb` (default 1.000). A measure that grew reads `larger` and fails the compare; one that shrank reads `smaller`. In the JSON, each measure gains `unit` and its values lose the `_ms` suffix: `old`, `new`, `old_centre`, `new_centre`, `change`, `spread`, `floor`.

- `compare --old FILE… --new FILE…` says whether the new runs got
  slower than the old, measure by measure: frame time, CPU and GPU
  spans, and every pass, each judged by its own run-to-run spread and a
  smallest change (`--min-ms`, `--min-pct`). At least three runs a set.
  Runs differing in a compare-blocking header field are refused, unless
  `--override FIELD=REASON` allows it; every override and its reason
  open the report. Exit 0 pass, 1 slower, 2 inconclusive, 3 error or
  refused. A static-line diff sits beside the measures. The format
  gains `vsync` and `scene` as compare-blocking fields (FLED-0008).
- `--selftest` checks the compare too (FLED-0008).
- `bisect --tested FILE… --measure CATEGORY/NAME` gives `git bisect run` one
  commit's verdict on one measure: exit 0 good, 1 bad, 125 skip, 128
  stop. It judges against `--bad-above X`, or the midpoint of at least
  three `--good` and three `--bad` reference runs, which must separate
  and not straddle their own midpoint. `--kind`, `--segment` or
  `--unsegmented` picks the frames; `mem` rows can be judged, with
  `--min-mb`. A broken or incomplete tested run skips, and so does one
  without the measure or with it at another depth from the references
  (FLED-0020); the result's `skip_reason` says which. Any other
  problem, `--help` and `--version` included, stops. `--dry-run VALUE`
  shows the verdict a value would get. Tested runs on both sides of the
  line warn, and skip with `--skip-straddle` (FLED-0009).
- `--selftest` checks the bisect too (FLED-0009).
- `budget FILE --budgets BUDGETS` names every pass over its time
  budget. The budget file is CSV, with comments: each line gives a pass,
  a segment kind or `*` for each kind apart, a depth, `median` or `p99`,
  and a limit in ms. A budget is judged on `report`'s own figure for
  the pass, never a single frame. `match` in the file's header names
  the settings it was written for, and a run without them is refused.
  `--warmup-s` leaves out the first seconds, as `floor` does (default
  0). A budget that matches nothing, dropped rows or an unfinished run
  are inconclusive. Exit 0 every budget holds, 1 over, 2 inconclusive,
  3 error (FLED-0010).
- `--selftest` checks the budget too (FLED-0010).
- A test locks that the analyser runs headless: no display, no
  terminal, no input and no locale (FLED-0019).
- A write to standard output that fails, such as a pipe closed early,
  exits 3, or 128 under `bisect`, never Python's 120 (FLED-0009,
  FLED-0019).
- An app icon, `assets/frameledger-icon.svg`, shown in the README; the
  projects website's logo, `assets/frameledger-logo-stacked.svg`; and a
  one-line logo, `assets/frameledger-logo.svg` (FLED-0017).

### Fixed

- **`--allow-frames` and `bisect --depth` take only ASCII digits** (FLED-0021)
  Another script's digits were read as a number, and a superscript got a generic error. Both now get the flag's own message.

- **A run file with a very long number is a breach, not a crash** (FLED-0022)
  A `frame`, a `depth` or a value's whole part past 20 digits now breaks the format and is named by line. Past 4300 digits it used to end in a traceback.

- **A huge `floor --warmup-s` is exit 3, not a crash** (FLED-0023)
  A warm-up of 1000000000 s or more is refused with a sentence. A value like `1e400` used to end in a traceback, exit 1, which a gate reads as a fail.

## [0.1.0] - 2026-10-26

**Theme:** One run, read and checked.

### Added

- The release archive, `frameledger-v0.1.0.zip`: `frameledger.pyz`,
  `include/frameledger.h` and `LICENSE`. SHA256
  `84a9254101421b223ca1429f889310ef92d1d4e4da433f19ce0d4225c89b9f5a`.
  A release candidate's archive, `frameledger-v0.1.0-rc.N.zip`, is the
  same bytes under another name. `python3 -I scripts/build_release.py
  OUTDIR v0.1.0`, run on the tag, rebuilds it; the release workflow
  does so under Python 3.10.22.
- The run-file format, schema 1: a header line, an optional static
  line, a column line, CSV rows, and a close line ending a finished
  run, as
  `docs/specs/FLED-0001-run-file-format.md` § 4 defines them. This is
  the first schema. Every later change to it will be named here
  (FLED-0001).
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
