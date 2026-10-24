# frameledger

> Finds what slows a game engine's frames: one run-file format and one
> analyser, shared by the Vestige, UT Ants and DOOM Ants engines.

## Status

In development; nothing is released yet. The run-file format is
agreed ([spec](docs/specs/FLED-0001-run-file-format.md)). Two commands
are built: `check`, which says whether a run file meets it, and
`report`, which says where one run's frame time went. The
[roadmap](ROADMAP.md) lists what comes next.

## Install

(Once there is something to install.)

## Usage

(Once there is something to use.)

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
