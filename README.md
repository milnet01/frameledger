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

## Usage

`frameledger.pyz` comes in the release zip (see Install). An engine
that vendors only the header must still fetch it.

```sh
python3 -I frameledger.pyz check run.csv
python3 -I frameledger.pyz report run.csv
python3 -I frameledger.pyz floor run.csv --fps 60
python3 -I frameledger.pyz compare --old a1.csv a2.csv a3.csv --new b1.csv b2.csv b3.csv
python3 -I frameledger.pyz alternate --old './old/engine --frame-log={run}' --new './new/engine --frame-log={run}' --out ab
python3 -I frameledger.pyz bisect --tested run.csv --measure gpu/opaque --kind view --bad-above 12
python3 -I frameledger.pyz budget run.csv --budgets budgets.csv
python3 -I frameledger.pyz --selftest
```

On Windows, use `py -I` or `python -I`. Every command takes `--json`.
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
Compare reads each run's start time from its file's `started_utc`
header, so list each build's files together on the command line.

For each measure, compare takes each build's median across its runs,
and judges the change against the spread. The spread is the larger of
the two builds' ranges, highest run minus lowest. Here the new build's
opaque pass got slower:

```text
$ python3 -I frameledger.pyz compare --old a1.csv a2.csv a3.csv --new b1.csv b2.csv b3.csv
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
