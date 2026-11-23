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

- The tests break the sample run files thousands of ways and check that
  each broken file gives a list of format breaches, or an error saying it
  cannot be read, and never a crash (FLED-0047).

### Changed

- CI runs the whole gate on Windows as well as Linux and macOS, so the
  test suite, the writer's tests and the kit are checked there on every
  push. On Windows the writer and kit build with mingw-w64's GCC and run
  (FLED-0087).

## [0.9.0] - 2026-11-23

**Theme:** Ready for strangers.

### Added

- The release archive, `frameledger-v0.9.0.zip`: `frameledger.pyz`, its
  launchers `frameledger` and `frameledger.cmd`, `include/frameledger.h`,
  `LICENSE`, and the result schemas under `schemas/`. SHA256
  `e3fde3fa1f356b049534afbc08e53189049e07ee9769c2b267345468f72beee4`.
  `python3 -I scripts/build_release.py OUTDIR v0.9.0`, run on the tag,
  rebuilds it; the release workflow does so under Python 3.10.22.
  `include/frameledger.h` is 0.8.0's, with only `FLED_VERSION`
  changed, and the result schemas are 0.8.0's.

- frameledger is on PyPI: `pipx install frameledger`, or
  `python3 -m pip install frameledger` in a virtual environment, gives
  a `frameledger` command, and `python3 -m frameledger` runs too
  (FLED-0043). Still standard library only. The wheel holds the
  `.pyz`'s files and `__init__.py`, its entry point, and
  `scripts/build_release.py` builds it reproducibly beside the
  archive. release.yml uploads it after the GitHub release, for a
  final release only. The release zip holds the same files as before,
  and stays the thing to pin. `scripts/build_release.py` now refuses a
  tag with a hyphen that does not end `-rc.N`, since release.yml makes
  every such tag a pre-release.
- A user guide, `docs/guide.md` (FLED-0044): a quick start from
  install to a first report, what a run file holds, worked examples in
  C and C++ with the header and how to wire it into an engine, a
  PresentMon import, how to read each command's answer and exit code,
  comparing builds, and checking every build. The README's compare
  walkthroughs moved into it. `tests/test_guide.py` builds and runs
  the guide's examples on every gate run, and fails when an output
  differs from the guide's.

- Where to ask for help, report a bug or send a change (FLED-0045):
  `CONTRIBUTING.md`, issue forms for a bug, a feature and a question,
  and a pull request template. `SECURITY.md` says how to report a
  security hole privately, through GitHub, and lists what frameledger
  checks where outside data reaches it. `CODE_OF_CONDUCT.md` is the
  Contributor Covenant 2.1.

### Changed

- The gate also runs the tests and `--selftest` on the newest released
  Python, 3.15.1, as well as the 3.10 floor (FLED-0082). A
  `DeprecationWarning` now fails the tests and `--selftest`.
  `docs/support-policy.md` § What it runs on says so.

- Text output says "in frames with no segment" where it said "in
  unsegmented segments": in `report`, `compare` (`noisy_run`,
  `outlier_run`, the frame/wall sentences) and `budget` (FLED-0083).
  `report`'s opening sentence says "none of them in a segment" when no
  frame has one, and "some in no segment and the rest in view
  segments" when some do. `budget`'s unmatched-line sentence says "in
  no judged frame outside a segment". `compare`'s short-run sentence counts
  "frame/wall values", not "frames with a frame/wall". JSON is unchanged:
  `segment_kind` stays null, and labels such as `unsegmented: gpu/a`
  keep the kind's name.

### Fixed

- `report --html PAGE` replaces only an earlier frameledger page, and
  refuses anything else at PAGE before reading the run, so a mistyped
  PAGE such as `--html old-1.csv` can no longer destroy a recording
  (FLED-0086). A FIFO or device at PAGE, such as `/dev/stdout`, is
  refused at once.
- `alternate` refuses a `--out` holding a backslash on Linux and
  macOS, where the shell read it as an escape and the engine wrote its
  run file somewhere else (FLED-0085). Windows still allows one, and
  now allows `~` too, which short folder names such as `NAME~1` hold.
- `survey` no longer calls `os.path.commonprefix`, which Python 3.15
  deprecates, to find the directory its runs share (FLED-0082).

## [0.8.0] - 2026-11-21

**Theme:** Stable promises.

### Added

- The release archive, `frameledger-v0.8.0.zip`: `frameledger.pyz`, its
  launchers `frameledger` and `frameledger.cmd`, `include/frameledger.h`,
  `LICENSE`, and the result schemas under `schemas/`. SHA256
  `3b7a03a350604cfef5e0d1339b00e88ed8fac72eac601237d005a8f264336228`.
  `python3 -I scripts/build_release.py OUTDIR v0.8.0`, run on the tag,
  rebuilds it; the release workflow does so under Python 3.10.22.
  `include/frameledger.h` is 0.7.0's, with only `FLED_VERSION` changed.

- The format stability promise,
  `docs/specs/FLED-0040-format-stability-promise.md`: a run, budget or
  baseline file that 0.8.0 or a later release reads without a breach
  is read the same by every release after it, for ever. Schema 1 is
  frozen as FLED-0001 stands at 0.8.0. A later release adds to a
  schema only what an older analyser already reads, and anything else
  takes a new `schema` number; no writer is made to move. Frozen files
  under `tests/fixtures/frozen/` hold it, two of them from a run
  Vestige's writer wrote, and `scripts/freeze.py` freezes a new one
  (FLED-0040).

- A JSON Schema for every command's `--json` result,
  `docs/specs/FLED-0041-json-result-schemas.md`: each key, its type,
  whether it is always there and whether it may be null.
  `frameledger schema COMMAND` prints one, and the release archive
  holds them under `schemas/`. A schema allows keys it does not name,
  so a script that checks a result against the schema it pinned
  survives a later release. From 0.8.0 each release's schemas are
  frozen under `tests/fixtures/schemas/`, and the tests hold every
  later release's output to them (FLED-0041).
- `floor --json`: each window has `frames`, the count of frames ending
  in it (FLED-0041).
- `bisect --json`: each run has `started_utc` and `under_load`, as
  `compare`'s runs have. Both are null for a run that could not be
  read or that breaks the format (FLED-0041).
- A support and deprecation policy, `docs/support-policy.md`: only the
  newest release gets fixes; a breaking change needs a warning in an
  earlier release, a replacement and the three engines' agreement; and
  the Python floor stays 3.10 until 2.0.0 at the earliest (FLED-0042).
- `compare` warns `noisy_run` for a run whose own frame times scatter:
  in a segment kind of at least 1000 frames, more than 2 percent of
  its `frame/wall` values are over twice the kind's median. Something
  else, such as the desktop holding the GPU, likely slowed that run,
  so the message says to re-run it. Each run in `--json` gains
  `noise`, one entry per segment kind with the share, the median, the
  quartile spread and `warns`; a shorter kind is listed with `judged`
  false. A script reads `warns`, since the share is rounded.
  The warning changes no verdict and no exit code (FLED-0072).

### Changed

- A result that would hold a NaN or an infinity is not printed: the
  command ends with a message, exit 3, or 128 under `bisect`. JSON
  holds neither, and no result holds one today (FLED-0041).
- The format spec says what `resolution` means: the size of the image
  the engine hands on for display, after any upscaling of its own.
  `render_scale` times each side is the size drawn. It also says a
  reader skips a byte-order mark at the start of a run or budget file
  and a writer puts none. No command behaves differently (FLED-0040).

### Deprecated

- `floor --json`: `fps` in each window. Read `frames`, which holds the
  same count. `fps` keeps working, and its schema entry is marked
  `"deprecated": true`. The earliest release that may remove it is
  2.0.0. `docs/support-policy.md` says how a thing is retired
  (FLED-0042).

## [0.7.0] - 2026-11-19

**Theme:** Seen, not only read.

### Added

- The release archive, `frameledger-v0.7.0.zip`: `frameledger.pyz`, its
  launchers `frameledger` and `frameledger.cmd`, `include/frameledger.h`
  and `LICENSE`. SHA256
  `e03ce95e1bf6fe81dbee7e0787c5c370edde98fb8acfe638c0d15c01f89ef1a2`.
  `python3 -I scripts/build_release.py OUTDIR v0.7.0`, run on the tag,
  rebuilds it; the release workflow does so under Python 3.10.22.
  `include/frameledger.h` differs from 0.6.0's only in `FLED_VERSION`.
  Since 0.2.0 it has gained `FLED_VERSION` and one corrected comment, and
  no code has changed, so a writer built with 0.2.0's header writes the
  same file.

- **`report` can also write a web page showing the run as a graph** (FLED-0039)
  `report FILE --html PAGE` writes one page beside its usual output, which does not change: the opening sentences, then frame time against time, then the tables. Segments are patterned bands, the worst frames are numbered markers, and `--fps N` adds a dashed budget line at 1000/N ms. A run of more than 1200 frames is drawn as 1200 columns, each from its fastest frame to its slowest, so one slow frame stays as tall as it was. The bands are also listed under the graph by segment, with their start and end, so a screen reader reaches the names; the list holds the first 100 and says how many more there are, and a run of more than 1200 bands draws none and says so (FLED-0080, FLED-0081). The page runs nothing and fetches nothing, so it opens from disk. Its text is the browser's own size; a "Larger text and lines" switch, first on the page, gives larger text and stronger contrast, as does a system set to prefer more contrast. PAGE is written whole or not at all, and is refused when it names the run file.

## [0.6.0] - 2026-11-17

**Theme:** Other people's data.

### Added

- The release archive, `frameledger-v0.6.0.zip`: `frameledger.pyz`, its
  launchers `frameledger` and `frameledger.cmd`, `include/frameledger.h`
  and `LICENSE`. SHA256
  `4406f1701c9ef565b70bf270c067aa41197c75ccedd252151b5454e91eabe67a`.
  `python3 -I scripts/build_release.py OUTDIR v0.6.0`, run on the tag,
  rebuilds it; the release workflow does so under Python 3.10.22.

- **A budget can limit a frame's whole CPU or GPU time** (FLED-0077)
  A budget file line may name `frame,cpu_span` or `frame,gpu_span`, with `median` or `p99`, as a pass line does: `frame,gpu_span,*,,p99,16.667` says whether the GPU alone fits a 60 FPS frame. Its value is `report`'s figure over the frames holding the span, and every pass rule holds: `*` and named kinds, `--warmup-s`, `budget_few_frames`, and a line no frame matches making the verdict inconclusive. `frame,wall` is refused, naming `floor`, which judges frame time; so is any other frame name and a depth on a frame line.

- **`compare` and `bisect` judge the 99th percentile of any frame measure or pass** (FLED-0076)
  `--measure CATEGORY/NAME:p99` judges a measure's 99th percentile, and `:median` its median alone; a bare name judges what it did before, so no verdict changes unless asked. The percentile is over the frames the measure appears in, and that count is shown beside the entry, in each run's values (`12.345 (4210)`) and in JSON as `old_frames` and `new_frames`, now given for every measure. Where any run holds it in fewer than 1000 frames of a segment kind, the entry is `too_few`, shown and named: a longer run cures it. The compare is inconclusive, exit 2, only when no entry of a `:p99` measure is judged. `:p99` on a `mem` measure, any other suffix, and one statistic asked for twice are exit 3. `bisect --statistic p99` now takes any measure but `mem`; a tested run holding it in fewer than 1000 chosen frames skips (125, `skip_reason` `short`), and such a reference stops (128).

- **Frames a driver generated are marked, and left out by default** (FLED-0075)
  `import presentmon` reads PresentMon's `FrameType` column (`--track_frame_type`): a frame that is not `Application` gets the new row `event/generated`, and the summary and `import.generated` count them by type. `report`, `floor`, `budget`, `survey`, `compare` and `alternate` (by scene and by variant too) and `bisect` then judge the frames the application rendered: a generated frame's rows are left out and its wall is added to the application frame before it. Each says how many frames were generated, and JSON gives `generated_frames` and `all_frames`. `--all-frames` counts every frame. A run whose every frame was generated is refused, naming `--all-frames`. `check` refuses an `event/generated` other than `1.000`. No schema change.

- **A kit proves a writer written from the spec alone, and `check` gains `--strict` and `--expect`** (FLED-0037)
  `kit DIR` writes the writer kit into an empty or missing directory: a `README.txt`, and for each case a `NAME.json`, what an engine measured, and a `NAME.csv`, the run file a correct writer makes from it, made by `include/frameledger.h` itself. Each case catches one mistake: rounding ties, the largest value, quoting, every length at its limit, 19-digit frame numbers, a hole, negative values, a GPU span over its wall whether the run is pipelined or not, CPU and GPU hitches, late GPU rows, across a segment change too, event rows, dropped rows, an unfinished run, a static line with a summary and a long one without, and every header field or none. `check --expect EXPECTED FILE` compares one run file with an expected one by content, not layout: key order, spacing, row order and line endings are free, `1` equals `1.0` but never `true`, and each row is compared as text. The summary names the first difference; `--json` lists up to 20. `check --strict` adds warnings on what is legal but unwise, such as a fixed or ticking `frame/wall`, a clamped clock, a span over its wall, a GPU time never read back, or no segments, and exits 1 on any warning, the format's own included. No schema change.

- **`import presentmon` turns a PresentMon capture into a run file** (FLED-0036)
  `import presentmon CAPTURE -o RUN` reads a PresentMon 2 CSV capture of one process and one swap chain, and writes a run that every command reads: `frame/cpu_span` from `MsCPUBusy`, `frame/gpu_span` from `MsGPUBusy`, `frame/wall` from the next present's `MsBetweenPresents`, and `event/not_displayed` on a frame never shown. Values are rounded from their decimal text. A PresentMon 1 capture, a capture of several processes or swap chains, or a run file that already exists is refused, with nothing written. Flags give the facts a capture cannot know, such as `--commit` and `--resolution`; any left out is written as a stand-in and listed in the new header field `unknown`. `report` says an imported run has no passes.

- **A header may list the facts it does not know** (FLED-0036)
  The optional header field `unknown` names the required fields that hold a stand-in. Every command then warns `facts_unknown`, and none compares, matches or shows a listed value: a listed compare-blocking field refuses a compare until overridden, a listed `build_type` is not judged a debug build, a budget naming a listed field does not match, and a listed `pipelined` gives no CPU-bound share. No schema change.

- **The header records the machine's state, and `compare` warns when the two sides differ** (FLED-0055)
  Seven optional header fields: `cpu_governor` (text, the writer's own words), `turbo` (true or false), `power` (`mains` or `battery`), `cpu_clock_mhz` (`start` and `end`), `cpu_temp_c` and `gpu_temp_c` (`start`, `end` and an optional `peak`, in degrees Celsius) and `throttled` (true or false). A run on battery warns `on_battery`, and a throttled one `throttled`. `compare` warns `governor_differs`, `turbo_differs`, `power_differs` or `sanitizers_differs` when the two sides' values differ; `cpu_clock_differs` when the median clocks differ by more than 5%; and `cpu_temp_differs` or `gpu_temp_differs` when the median temperatures differ by more than 10 degrees, judged on `peak` when every run has one and on `end` otherwise. Each needs the field in every run. A warning changes no verdict and no exit code. No schema change.

- **`compare` names the run that stands apart** (FLED-0053)
  When the frame time is too noisy to judge, `compare` warns `outlier_run` for a run far from the rest of its set, as in "new-3 stands apart from the other new runs: its frame/wall median in view segments is 20.000 ms and theirs lie from 16.000 to 16.100 ms; re-run it". A set's highest or lowest run is named when dropping it cuts the set's range by more than half. So one run can be taken again instead of the whole set. Each named run has its own sentence. The warning changes no verdict and no exit code.

- **A run from a sanitizer build carries a warning** (FLED-0016)
  The header takes an optional `sanitizers` field: a list of the sanitizers the build was compiled with, such as `["address"]`, and `[]` for none. Where the list names any, every command that gives trust warnings adds `sanitizer_build`, quoting the names. A warning changes no verdict and no exit code. `check` refuses a `sanitizers` that is not a list of strings, or that holds an empty or blank one. No schema change: a file without the field reads as before.

### Changed

- **A compare that judged nothing is inconclusive, `--measure` or not** (FLED-0076)
  When every measure is in only some runs, as with an empty run on one side, `compare` exits 2 saying nothing was judged, instead of passing.

- **`bisect --statistic p99` needs 1000 frames** (FLED-0076)
  A tested run holding the measure in fewer than 1000 of the chosen frames skips, and a reference stops, `frame/wall` included: below that, the 99th percentile is one of a run's ten slowest frames. `compare`'s 99th percentile of a bare `frame/wall` keeps no minimum.

- **Every change is tested on macOS** (FLED-0038)
  The analyser's tests, its self-test and the writer header's tests now run on macOS as well as Linux before a change is accepted. On macOS the header is built and run with Apple's Clang, as C99 and as C++17.

- **`survey`'s table names a shared folder once** (FLED-0025)
  When two or more surveyed files are all in one directory, the table's heading names it, as in "Runs, slowest first, each file in runs/:", and each row shows the path after it. Before, a long shared directory filled the file column and hid the names. The sentences above the table and `--json` still give whole paths.

### Fixed

- **A run with no frames no longer crashes `floor`, `survey` or `budget`** (FLED-0075)
  A file holding a header and a close line alone is judged as nothing, as a short run is, instead of ending in a traceback and exit 1.

- **Stopping `alternate` on macOS gives its report** (FLED-0038)
  On macOS a stop sent to `alternate` could end it with exit code 3 and no output: the system refused a signal to the command's process group once its processes had ended, and `alternate` took that for a failure. It now waits for such a group as one still ending; a group that refuses through the whole wait is reported as one that did not end. Found by the first run of the tests on macOS.

- **Text from a run file or a path cannot forge or flood a line** (FLED-0071)
  A header value holding a line break could print a second line reading "Warning: …", and an escape character reached the terminal. Plain text now shows such a character as an escape, `\n` or `\x1b`: the control characters, the line separators and the marks that set text direction. A quoted header string also shows a backslash doubled; a path keeps single backslashes, so a Windows path can still be copied. A quoted list names its first five entries, then "and N more". A long quoted value is cut, keeping both its ends: a `renderer`, `device`, `driver`, `os` or `commit` to 60 characters, as are the values in a refusal to compare and a scene's name in a `--by-scene` sentence. A setup error on standard error is cleaned the same way and cut to 500 characters, since it can quote a line of a baseline file. Two or more `sanitizers` now read "'address' and 'undefined'". `--json` is exact, but for a warning's `message`, which is cut the same way. Markdown turns the same characters into a space (FLED-0073), so a text-direction mark cannot reorder a sentence in a rendered pull-request comment.

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
