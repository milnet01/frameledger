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

[Fork the repository](https://github.com/milnet01/frameledger/fork) on
GitHub, then, on Linux or macOS:

```sh
git clone https://github.com/<you>/frameledger.git
cd frameledger
./scripts/setup-hooks.sh
./scripts/local-ci.sh
```

`setup-hooks.sh` turns on the project's hooks. They check each commit
subject, and the Markdown a commit changes outside `docs/`. They do
not run the gate before a push. Run `./scripts/local-ci.sh` yourself.

A hook message may cite a `~/.claude/` file. Those are the maintainer's
own rules and are not published; the message itself says what to fix.

`scripts/local-ci.sh` is the gate, and GitHub runs the same script on
every pull request. It needs [uv](https://docs.astral.sh/uv/) on your
PATH. uv fetches the pinned Python and tools.

The writer checks also need C and C++ compilers: `gcc`, `clang` and
the MinGW-w64 cross-compilers on Linux, `clang` on macOS. On Linux they
also need the `de_DE.UTF-8` locale. The gate stops at the first check
that fails, and names any compiler it cannot find.

Without those, two commands still check your change:

```sh
./scripts/local-ci.sh --docs
uvx --python 3.10 --with jsonschema pytest
```

The first runs the document checks, the second the analyser's tests.
Your pull request's checks then run the rest. On a first pull request,
GitHub waits for a maintainer to approve those checks before they run.

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
- **Each commit subject opens `fix: `, `docs: ` or `chore: `**, and
  is at most 72 characters, with no full stop at the end. The commit
  hook checks this. Pick the nearest for a feature: the maintainer
  squash-merges it under the project's own id.

## Licence

A change you send is licensed under the project's [MIT licence](LICENSE).
