# Contributing to frameledger

**Purpose: so that an outsider can ask for help, report a problem, or
send a change the project can accept.**

Everyone taking part follows the [code of conduct](CODE_OF_CONDUCT.md).

## Ask for help, or report a problem

[Open an issue](https://github.com/milnet01/frameledger/issues/new/choose)
and pick its form: a bug, a feature, or a question.

For a bug, give the output of `frameledger --version` and the command
you ran. Attach the run file if you can share it.

A security hole goes through [`SECURITY.md`](SECURITY.md), never an
issue.

## Send a change

**Open an issue first**, saying what you want to change and why. Wait
for a maintainer to agree on the issue before writing code. A pull
request with no agreed issue may be closed.

### Build and test

On Linux or macOS:

```sh
git clone https://github.com/milnet01/frameledger.git
cd frameledger
./scripts/setup-hooks.sh
./scripts/local-ci.sh
```

`setup-hooks.sh` turns on the project's hooks. They check each
commit's subject and the Markdown it changes. On your machine they do
not run the gate before a push, and say so, so run it yourself.

`scripts/local-ci.sh` is the gate, and GitHub runs the same script on
every pull request. It needs [uv](https://docs.astral.sh/uv/) on your
PATH, which fetches the pinned Python and tools. The writer checks also
need C and C++ compilers: `gcc`, `clang` and the MinGW-w64
cross-compilers on Linux, `clang` on macOS. A missing compiler fails
the gate, which names it. Without one, push anyway and read the pull
request's checks.

`./scripts/local-ci.sh --docs` runs only the document checks.

### What a change needs

- **The analyser stays Python 3.10 or newer, standard library only.**
  [`docs/design.md` § The stack, and what it rules out](docs/design.md#the-stack-and-what-it-rules-out)
  says why.
- **A fix comes with a test that fails without it.**
- **A new feature comes with tests**, and with its documentation in
  `README.md` or [`docs/guide.md`](docs/guide.md).
- **A change a user would notice gets an entry** under
  `## [Unreleased]` in [`CHANGELOG.md`](CHANGELOG.md).
- **A new file under `src/frameledger/` must be `git add`ed** before
  the tests pass: the tests build the analyser from the files git
  tracks.
- **A change that breaks a file format, a command or a JSON result**
  follows [`docs/support-policy.md` § When a breaking change is allowed](docs/support-policy.md#when-a-breaking-change-is-allowed).
- **Each commit subject opens with the id the maintainer gave the
  issue**, as in `FLED-0090: …`. A fix, a documentation change or a
  chore with no id may open `fix: `, `docs: ` or `chore: ` instead.
  The commit hook checks this.

`docs/standards/` holds the few places where this project departs
from its maintainers' general rules.

## Licence

A change you send is licensed under the project's [MIT licence](LICENSE).
