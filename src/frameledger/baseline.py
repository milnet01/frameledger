"""A baseline file (S24): the run files it names, as paths.

The rules are docs/specs/FLED-0001-run-file-format.md § 4.17. The engine
keeps the file and its runs; this module reads the file and nothing
else, and never opens a run.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import ledger

SCHEMA = 1
KEYWORD = "# frameledger-baseline"
FEWEST_RUNS = 3  # § 4.10's smallest set


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

    listed: dict[str, int] = {}  # run file -> the line that names it
    for number, text in enumerate(texts[1:], start=2):
        if not text.strip() or text.startswith("#"):
            continue  # a blank line or a comment
        run = _resolve(text.strip(), os.path.dirname(path))
        if run in listed:
            raise ledger.LedgerError(f"this line names {run}, which is line {listed[run]}'s", path, number)
        if not os.path.isfile(run):  # a moved run must not read as a regression (Vestige)
            raise ledger.LedgerError(f"this line names {run}, which is not a file", path, number)
        listed[run] = number
    if len(listed) < FEWEST_RUNS:
        raise ledger.LedgerError(f"the file names {len(listed)} runs; a baseline needs at least {FEWEST_RUNS}, "
                                 "since two give too many false changes", path)
    return list(listed)


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
    except ValueError:  # not just JSONDecodeError: a huge integer raises plain ValueError
        raise ledger.LedgerError("the header is not one JSON object", path, 1) from None
    schema = header.get("schema") if isinstance(header, dict) else None
    if type(schema) is not int or schema != SCHEMA:  # not True, not 1.0
        raise ledger.LedgerError(f"schema must be {SCHEMA}, not {json.dumps(schema)}", path, 1)


def _resolve(written: str, folder: str) -> str:
    """A listed path as an absolute one. A relative path starts at the
    baseline file's folder, and may use either slash on any platform, so
    one file serves Linux and Windows; an absolute path is the
    platform's own."""
    if os.path.isabs(written):
        return os.path.normpath(written)
    return os.path.normpath(os.path.join(folder, *written.replace("\\", "/").split("/")))
