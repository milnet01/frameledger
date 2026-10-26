# frameledger

> Finds what slows a game engine's frames: one run-file format and one
> analyser, shared by the Vestige, UT Ants and DOOM Ants engines.

## Status

0.1.0 is the first release. The run-file format is
agreed ([spec](docs/specs/FLED-0001-run-file-format.md)). Three commands
are built: `check`, which says whether a run file meets it; `report`,
which says where one run's frame time went; and `floor`, which says
whether a run held a set frame rate. The
[roadmap](ROADMAP.md) lists what comes next.

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
python3 -I frameledger.pyz --selftest
```

On Windows, use `py -I` or `python -I`. Every command takes `--json`.
The [spec](docs/specs/FLED-0001-run-file-format.md#47-the-010-commands)
lists the flags and exit codes.

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
