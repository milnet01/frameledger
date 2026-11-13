"""A baseline file (S24): the run files it names, as paths.

The rules are docs/specs/FLED-0001-run-file-format.md § 4.17. The engine
keeps the file and its runs; this module reads the file and nothing
else, and never opens a run.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import ledger

SCHEMA = 1
KEYWORD = "# frameledger-baseline"
FEWEST_RUNS = 3  # § 4.10's smallest set; a test holds it equal to compare.py's
WINDOWS_DRIVE = re.compile(r"[A-Za-z]:")


def read(path: str) -> list[str]:
    """The run files `path` lists, in its order, as absolute paths.
    Raises LedgerError naming the line at fault."""
    path = os.path.abspath(path)
    try:
        data = Path(path).read_bytes()
    except OSError as error:
        raise ledger.LedgerError(error.strerror or "cannot be read", path) from error
    texts = _lines(data, path)
    if not texts:
        raise ledger.LedgerError(f"the file is empty; its first line must be '{KEYWORD} {{\"schema\":{SCHEMA}}}'",
                                 path)
    _check_header(texts[0], path)

    listed: dict[object, int] = {}  # a run file's _identity -> the line that names it
    runs = []
    for number, text in enumerate(texts[1:], start=2):
        written = text.strip()
        if not written or written.startswith("#"):
            continue  # a blank line or a comment
        run = _resolve(written, os.path.dirname(path))
        if run is None:
            raise ledger.LedgerError(f"'{ledger.clip(written, ledger.LONG_QUOTE)}' is neither a relative path "
                                     "nor an absolute one on this system", path, number)
        if not os.path.isfile(run):  # a moved run must not read as a regression (Vestige)
            raise ledger.LedgerError(f"this line names {run}, which is not a file", path, number)
        # One file under two names would count twice and narrow the spread
        # (Vestige, UT Ants).
        same = _identity(run)
        if same in listed:
            raise ledger.LedgerError(f"this line names {run}, which is line {listed[same]}'s", path, number)
        listed[same] = number
        runs.append(run)
    if len(runs) < FEWEST_RUNS:
        raise ledger.LedgerError(f"the file names {len(runs)} runs; a baseline needs at least {FEWEST_RUNS}, "
                                 "since two give too many false changes", path)
    return runs


def _identity(run: str) -> object:
    """What two names of one file share: a symbolic link, a hard link, or
    on Windows another letter case. The file's own number where the
    system gives one, else its path with links followed."""
    status = os.stat(run)
    return (status.st_dev, status.st_ino) if status.st_ino else os.path.normcase(os.path.realpath(run))


def _lines(data: bytes, path: str) -> list[str]:
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]  # some Windows editors add a byte-order mark
    lines = data.split(b"\n")
    if lines[-1] == b"":
        lines.pop()  # the final line ending, not an empty line
    texts = []
    for number, raw in enumerate(lines, start=1):
        try:
            texts.append(raw.removesuffix(b"\r").decode("utf-8"))
        except UnicodeDecodeError:
            raise ledger.LedgerError("the line is not UTF-8 text", path, number) from None
    return texts


def _check_header(text: str, path: str) -> None:
    keyword, _, rest = text.partition(" {")
    if keyword != KEYWORD:
        raise ledger.LedgerError(f"the first line must be '{KEYWORD} {{\"schema\":{SCHEMA}}}'", path, 1)
    try:
        header = json.loads("{" + rest)
    except (ValueError, RecursionError):  # a huge integer is a plain ValueError; deep nesting recurses (UT Ants)
        raise ledger.LedgerError("the header is not one JSON object", path, 1) from None
    schema = header.get("schema") if isinstance(header, dict) else None
    if type(schema) is not int or schema != SCHEMA:  # not True, not 1.0
        raise ledger.LedgerError(f"schema must be {SCHEMA}, not {json.dumps(schema)}", path, 1)


def _resolve(written: str, folder: str) -> str | None:
    """A listed path as an absolute one. A relative path starts at the
    baseline file's folder, and may use either slash on any platform, so
    one file serves Linux and Windows; an absolute path is the
    platform's own. None for a path that is neither here: one that opens
    with a slash or a drive letter and is still not absolute, as
    `\\runs\\a.csv` or `C:\\runs\\a.csv` on Linux, or `/runs/a.csv` and
    `C:a.csv` on Windows. Joining one to the folder would name a file
    the line never wrote (Vestige, UT Ants). So would a later part with
    a drive letter, `runs/C:a.csv`: Windows' join starts again at it
    (DOOM Ants)."""
    drive, rest = os.path.splitdrive(written)
    if os.path.isabs(written) and (drive or os.sep == "/"):
        return os.path.normpath(written)
    parts = written.replace("\\", "/").split("/")
    if rest[:1] in ("/", "\\") or any(WINDOWS_DRIVE.match(part) for part in parts):
        return None
    return os.path.normpath(os.path.join(folder, *parts))
