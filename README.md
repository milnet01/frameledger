# frameledger

<img src="assets/frameledger-icon.svg" width="96" height="96" alt="">

> Finds what slows a game engine's frames: one run-file format and one
> analyser, shared by the Vestige, UT Ants and DOOM Ants engines.

## Status

0.2.0 compares two builds. The run-file format is agreed
([spec](docs/specs/FLED-0001-run-file-format.md)). Six commands are
built:

- `check` says whether a run file meets the format.
- `report` says where one run's frame time went, and how evenly its
  frames were paced.
- `floor` says whether a run held a set frame rate.
- `compare` says whether a new build's runs got slower than an old
  build's, measure by measure, memory included.
- `bisect` gives `git bisect run` a good, bad or skip verdict for one
  commit's runs.
- `budget` says whether any pass went over its time budget.

The [roadmap](ROADMAP.md) lists what comes next.

## Install

Download `frameledger-v<version>.zip` from the
[releases page](https://github.com/milnet01/frameledger/releases), and
check its SHA256 against the one in that release's notes. It holds:

- `frameledger.pyz` — the analyser. It needs Python 3.10 or newer and
  nothing else.
- `frameledger` and `frameledger.cmd` — launchers that run it by name,
  on Linux and on Windows.
- `include/frameledger.h` — the optional writer, one header for C and
  C++.
- `LICENSE`.

`frameledger.zip` on the latest release is the same bytes under a name
that does not change.

To unpack it without `unzip`, which minimal Linux images leave out,
use Python itself:

```sh
python3 -m zipfile -e frameledger-v<version>.zip frameledger
```

### Run it by name

Put the launcher on your PATH, and `frameledger report run.csv` works
from any folder.

On Linux, make the launcher runnable, then link it into a folder on
your PATH. Python's unpacker does not keep the runnable mark, so the
first line is needed after it:

```sh
chmod +x frameledger/frameledger
ln -s "$PWD/frameledger/frameledger" ~/.local/bin/frameledger
```

If `echo $PATH` does not list `~/.local/bin`, link into a folder it
does list.

On Windows, add the unpacked folder to your account's PATH from
PowerShell, then open a new terminal:

```powershell
$dir = "C:\tools\frameledger"   # the folder you unpacked into
[Environment]::SetEnvironmentVariable("Path", [Environment]::GetEnvironmentVariable("Path", "User") + ";$dir", "User")
```

The Windows launcher uses the `py` launcher when it is installed, and
`python` otherwise.

`frameledger --version` checks it worked. A script can also call the
launcher by its path, such as `tools/frameledger/frameledger`, with
nothing on PATH.

## Usage

The analyser and its launchers come in the release zip (see Install).
An engine that vendors only the header must still fetch them.

```sh
frameledger check run.csv
frameledger report run.csv
frameledger floor run.csv --fps 60
frameledger compare --old a1.csv a2.csv a3.csv --new b1.csv b2.csv b3.csv
frameledger alternate --old './old/engine --frame-log={run}' --new './new/engine --frame-log={run}' --out ab
frameledger bisect --tested run.csv --measure gpu/opaque --kind view --bad-above 12
frameledger budget run.csv --budgets budgets.csv
frameledger --selftest
```

Without the launcher, `python3 -I frameledger.pyz` runs the same
commands; on Windows, `py -I frameledger.pyz` or `python -I
frameledger.pyz`. Every command takes `--json`,
and `--markdown` for results to paste into a pull request or a note.
The spec lists the flags and exit codes:
[check, report and floor](docs/specs/FLED-0001-run-file-format.md#47-the-010-commands),
[compare](docs/specs/FLED-0001-run-file-format.md#410-comparing-labelled-sets-of-runs),
[alternate](docs/specs/FLED-0001-run-file-format.md#415-alternating-runs),
[bisect](docs/specs/FLED-0001-run-file-format.md#411-bisect-verdicts) and
[budget](docs/specs/FLED-0001-run-file-format.md#412-pass-budgets).

### An A/B with compare

Each build needs at least three runs. Alternate them in one sitting:
old, new, new, old, old, new. Three of one build then three of the
other lets drift over time read as a change, and compare warns
`not_interleaved`. `alternate` runs both builds' commands in that
order, five runs a side by default, then compares what they wrote.
Each command must hold `{run}` where its run file's path goes.
A run whose header records other programs loading the CPU or GPU
while it ran makes the compare inconclusive; `--max-load` and
`--max-gpu-busy` set how much is allowed.
`--measure gpu/opaque`, given once per measure, judges only the
measures named, and adds a table of each run's value of each.
Compare reads each run's start time from its file's `started_utc`
header, so list each build's files together on the command line.

For each measure, compare takes each build's median across its runs,
and judges the change against the spread. The spread is the larger of
the two builds' ranges, highest run minus lowest. Here the new build's
opaque pass got slower:

```text
$ frameledger compare --old a1.csv a2.csv a3.csv --new b1.csv b2.csv b3.csv
The new runs are slower: 4 measures got slower; the largest is gpu/opaque median in view segments, up 0.890 ms (+22.1%), beyond the runs' spread of 0.090 ms.
In view segments the median frame/wall went from 16.020 ms to 16.910 ms (slower).

Runs:
  old-1     a1.csv
  old-2     a2.csv
  old-3     a3.csv
  new-1     b1.csv
  new-2     b2.csv
  new-3     b3.csv

Measures that moved or are too noisy to judge, old and new as the runs' median:
  measure                                       old ms      new ms      change      spread  verdict
  view: frame/gpu_span                          12.020      12.910      +0.890       0.090  slower
  view: frame/wall                              16.020      16.910      +0.890       0.090  slower
  view: frame/wall p99                          16.020      16.910      +0.890       0.090  slower
  view: gpu/opaque                               4.020       4.910      +0.890       0.090  slower
4 of 8 measures unchanged.
```

`view` is the segment kind these runs wrote: the part before the colon
in a row's `segment`, such as `view:3`. Your engine names its own
kinds, and compare judges each kind apart.

It judges frame times, `cpu` and `gpu` passes, and `mem`. It does not
judge `event` or `ext.<engine>` rows.

The first line names the measure with the largest change in ms. Here
all four moved 0.890 ms, so the tie goes to the largest percentage.

It exits 1 here, because a measure got slower. It exits 0 when nothing
got slower or larger, 2 when the runs are too noisy to judge, and 3 on
an error. Unchanged measures are counted, not listed; `--json` lists
every measure with its verdict.

## Working on it

After cloning, run `./scripts/setup-hooks.sh` once. It turns on the
commit and push checks, which git does not copy with a clone.

## Documentation

| | |
|---|---|
| [ROADMAP.md](ROADMAP.md) | What is planned, in progress and shipped |
| [CHANGELOG.md](CHANGELOG.md) | What shipped, when |
| [docs/discovery.md](docs/discovery.md) | What this is for, and how we would know it works |
| [docs/design.md](docs/design.md) | The shape — the parts, and what may touch what |
| [docs/decisions/](docs/decisions/) | Why a close call went the way it did |
| [docs/specs/](docs/specs/) | The contract for one feature, where one was needed |

Paths starting `~/.claude/` point at the author's own workflow standards.
They live on the author's machine and are not published; you can skip them.

## License

[MIT](LICENSE).
