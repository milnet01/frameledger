# Security policy — frameledger

**Purpose: so that whoever finds a security hole knows how to report it
privately, and what frameledger defends.**

## Reporting a vulnerability

Report it through GitHub's private reporting form:
[Report a vulnerability](https://github.com/milnet01/frameledger/security/advisories/new).
Only the maintainers see the report.

Do not open a public issue for a security hole. An issue is public the
moment it is filed.

The fix ships in the next release, and its `CHANGELOG.md` entry says
what it fixed.

## Supported versions

Only the newest release gets fixes, a security fix included.
[`docs/support-policy.md` § Which release gets fixes](docs/support-policy.md#which-release-gets-fixes)
owns this.

## Trust boundaries

Where data from outside reaches frameledger, and what is checked there.

- **Run, budget and baseline files.** Each is read as UTF-8 and
  checked against its own grammar, in `ledger.py`, `budgeting.py` and
  `baseline.py`. A file is read whole into memory, with no size limit.
- **A baseline's run files.** A baseline names run files by path, and
  an absolute path is read wherever it points (`baseline.py`).
- **A PresentMon capture.** `import presentmon` checks each column and
  number it reads, in `presentmon.py`. It never overwrites an existing
  run file.
- **Text shown back to you.** Text from a file or the command line is
  printed with control, bidirectional and zero-width characters shown
  as escapes (`render.py`), so it cannot drive the terminal. In
  `--markdown` output those characters become spaces, and Markdown's
  own symbols are escaped (`render.py`). In the HTML report the text is
  also HTML-escaped (`picture.py`).
- **The HTML report** loads nothing from the network. `--html`
  replaces only an earlier frameledger page at its path, and refuses
  any other file there.
- **Files frameledger writes.** `import presentmon`, `alternate` and
  `kit` never overwrite an existing file. `alternate` deletes a failed
  run's own file.
- **`alternate`'s commands** are run by the system shell, as typed.
  They are yours, so they are trusted, and their output is passed to
  standard error unchanged. Only the run file path is inserted into
  them. A variant name may hold only lowercase letters, digits and `_`.
  `--out` may hold only ASCII letters, digits and `._-/:`, and on
  Windows `\`, so the shell never changes the path the command gets.
- **The network.** The analyser opens no connection.
- **The writer header.** `include/frameledger.h` trusts its caller for
  pointers and buffer sizes. It refuses a run id or header holding a
  line break or unsafe character, and a row field outside the grammar.
- **The release.** Each release's notes give the SHA256 of its
  archive. The hash catches a damaged download, not a tampered release:
  whoever could change the archive could change the hash beside it.
