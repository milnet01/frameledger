# frameledger

<img src="assets/frameledger-icon.svg" width="96" height="96" alt="">

> Finds what slows a game engine's frames: one run-file format and one
> analyser, shared by the Vestige, UT Ants and DOOM Ants engines.

## Status

The run-file format is agreed
([spec](docs/specs/FLED-0001-run-file-format.md)). From 0.8.0 a file
that a release reads is read the same by every later release
([the promise](docs/specs/FLED-0040-format-stability-promise.md)).
These commands are built:

- `check` says whether a run file meets the format.
- `report` says where one run's frame time went, and how evenly its
  frames were paced. `--html PAGE` also writes one web page showing the
  run as a graph, with its slowest frames marked.
- `floor` says whether a run held a set frame rate.
- `compare` says whether a new build's runs got slower than an old
  build's, measure by measure, memory included.
- `bisect` gives `git bisect run` a good, bad or skip verdict for one
  commit's runs.
- `budget` says whether any pass, or a frame's whole CPU or GPU span, went
  over its time budget.
- `alternate` runs an old and a new build in turn, then compares them.
- `survey` ranks many runs by their slowest frames, and flags those
  with a frame over budget.

Built since the last release, and in the next:

- `import presentmon` turns a PresentMon capture into a run file.
- `kit` writes the files that prove a writer made from the spec alone,
  checked with `check --expect` and `check --strict`.

The [roadmap](ROADMAP.md) lists what comes next.

## Install

From 0.9.0, the analyser is also on PyPI. With Python 3.10 or newer,
this gives you a `frameledger` command:

```sh
pipx install frameledger
```

Inside a virtual environment, `python3 -m pip install frameledger` does
the same. Many Linux systems refuse a pip install outside one.

PyPI has final releases only; candidates are in the release zip. The
package holds the analyser only. The writer header, and an archive
with one hash to pin, are in the release zip below.

### The release zip

Download `frameledger-v<version>.zip` from the
[releases page](https://github.com/milnet01/frameledger/releases), and
check its SHA256 against the one in that release's notes. It holds:

- `frameledger.pyz` — the analyser. It needs Python 3.10 or newer and
  nothing else.
- `frameledger` and `frameledger.cmd` — launchers that run it by name,
  on Linux and macOS and on Windows.
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

#### Run it by name

Put the launcher on your PATH, and `frameledger report run.csv` works
from any folder.

On Linux or macOS, make the launcher runnable, then link it into a folder on
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
`python` otherwise. Exit 9009 means it found no real Python, or no
analyser beside it; the message says which. Ctrl+C stops the analyser,
then `cmd` asks "Terminate batch job (Y/N)?"; either answer is fine.
`cmd` may split an argument holding `&`, `|`, `<`, `>` or `^`, so keep
those characters out of run file names.

Link the launcher rather than copying it: a copy cannot find the
analyser, and says so.

`frameledger --version` checks it worked. A script can also call the
launcher by its path, such as `tools/frameledger/frameledger`, with
nothing on PATH.

A source checkout has the same launcher in `launcher/`. With no
`frameledger.pyz` beside it, it runs `src/frameledger`, so linking
`launcher/frameledger` from a checkout, or putting `launcher` on the
Windows PATH, runs the code in that checkout.

## Usage

Install the analyser from PyPI (from 0.9.0) or from the release zip,
which also holds its launchers (see Install). An engine that vendors
only the header must still install it one of those ways.

```sh
frameledger check run.csv
frameledger report run.csv
frameledger report run.csv --html run.html --fps 60
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
`frameledger schema COMMAND` prints the JSON Schema of that command's
`--json` result, for a script that reads it; the release archive holds
the same files under `schemas/`. Releases up to 0.7.0 have none.
The spec lists the flags and exit codes:
[check, report and floor](docs/specs/FLED-0001-run-file-format.md#47-the-010-commands),
[compare](docs/specs/FLED-0001-run-file-format.md#410-comparing-labelled-sets-of-runs),
[alternate](docs/specs/FLED-0001-run-file-format.md#415-alternating-runs),
[variants against one base](docs/specs/FLED-0001-run-file-format.md#416-variants-against-one-base),
[a saved baseline](docs/specs/FLED-0001-run-file-format.md#417-a-saved-baseline),
[bisect](docs/specs/FLED-0001-run-file-format.md#411-bisect-verdicts) and
[budget](docs/specs/FLED-0001-run-file-format.md#412-pass-budgets).

The [guide](docs/guide.md) shows how to read each result, and how to
compare two builds, variants of one build, or a saved baseline.

## Working on it

After cloning, run `./scripts/setup-hooks.sh` once. It turns on the
commit and push checks, which git does not copy with a clone.

To ask for help, report a bug or send a change, see
[CONTRIBUTING.md](CONTRIBUTING.md). Report a security hole as
[SECURITY.md](SECURITY.md) says, never in a public issue.

## Documentation

| | |
|---|---|
| [docs/guide.md](docs/guide.md) | From nothing to a first report, and how to read each result |
| [ROADMAP.md](ROADMAP.md) | What is planned, in progress and shipped |
| [CHANGELOG.md](CHANGELOG.md) | What shipped, when |
| [docs/support-policy.md](docs/support-policy.md) | Which release gets fixes, what it runs on, and how a thing is retired |
| [docs/discovery.md](docs/discovery.md) | What this is for, and how we would know it works |
| [docs/design.md](docs/design.md) | The shape — the parts, and what may touch what |
| [docs/decisions/](docs/decisions/) | Why a close call went the way it did |
| [docs/specs/](docs/specs/) | The contract for one feature, where one was needed |

Paths starting `~/.claude/` point at the author's own workflow standards.
They live on the author's machine and are not published; you can skip them.

## License

[MIT](LICENSE).
