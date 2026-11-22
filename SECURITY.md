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

- **Run, budget and baseline files.** Each line is read as UTF-8 and
  checked against the run file's grammar, in `ledger.py`,
  `budgeting.py` and `baseline.py`. A file is read whole into memory,
  with no size limit.
- **A PresentMon capture.** `import presentmon` checks each column and
  number it reads, in `presentmon.py`. It never overwrites an existing
  run file.
- **Text shown back to you.** Text from a file or the command line is
  printed with control, bidirectional and zero-width characters shown
  as escapes (`render.py`), so it cannot drive the terminal. In the
  HTML report it is also HTML-escaped (`picture.py`).
- **The HTML report** loads nothing from the network. `--html`
  replaces a file already at its path.
- **`alternate`'s commands** are run by the system shell, as typed.
  They are yours, so they are trusted. Only the run file path is
  inserted into them. `--out` may hold only ASCII letters, digits and
  `._-/\:`, and a variant name only lowercase letters, digits and `_`,
  so the path needs no quoting.
- **The network.** The analyser opens no connection.
- **The writer header.** `include/frameledger.h` trusts its caller for
  pointers and buffer sizes. It refuses a run id or header holding a
  line break or unsafe character, and a row field outside the grammar.
- **The release.** Each release's notes give the SHA256 of its
  archive. The hash shows a damaged download. It is published beside the
  archive, so it cannot show a tampered releases page.
