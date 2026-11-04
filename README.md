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

## Usage

```sh
python3 -I frameledger.pyz check run.csv
python3 -I frameledger.pyz report run.csv
python3 -I frameledger.pyz floor run.csv --fps 60
python3 -I frameledger.pyz compare --old a1.csv a2.csv a3.csv --new b1.csv b2.csv b3.csv
python3 -I frameledger.pyz bisect --tested run.csv --measure gpu/opaque --kind view --bad-above 12
python3 -I frameledger.pyz budget run.csv --budgets budgets.csv
python3 -I frameledger.pyz --selftest
```

On Windows, use `py -I` or `python -I`. Every command takes `--json`.
The spec lists the flags and exit codes:
[check, report and floor](docs/specs/FLED-0001-run-file-format.md#47-the-010-commands),
[compare](docs/specs/FLED-0001-run-file-format.md#410-comparing-labelled-sets-of-runs),
[bisect](docs/specs/FLED-0001-run-file-format.md#411-bisect-verdicts) and
[budget](docs/specs/FLED-0001-run-file-format.md#412-pass-budgets).

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
