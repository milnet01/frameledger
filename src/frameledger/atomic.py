"""Write a file whole or not at all.

The text goes to a temporary file beside the target, which is then put
in the target's place. So a write that fails part way leaves no half
file, and leaves the target as it was. `import` writes its run file
this way, never over an existing file (§ 4.18 of
docs/specs/FLED-0001-run-file-format.md), and `report --html` its page,
which it overwrites (§ 4.21).
"""

from __future__ import annotations

import os
import tempfile

import ledger


class Exists(ledger.LedgerError):
    """`path` holds a file, and the write was not to overwrite one."""

    def __init__(self, path: str):
        super().__init__("the file exists, and it is not to be overwritten", path)


def write(path: str, text: str, overwrite: bool = False) -> None:
    """Write `text` to `path`, replacing a file there only when
    `overwrite`; without it, a file there raises Exists. Raises
    LedgerError naming `path` when it cannot write."""
    folder = os.path.dirname(os.path.abspath(path))
    try:
        handle, temporary = tempfile.mkstemp(dir=folder, prefix=".frameledger-")
    except OSError as error:
        raise ledger.LedgerError(error.strerror or "cannot be written", path) from error
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        os.chmod(temporary, 0o666 & ~_umask())  # mkstemp's 0600, made what open() would give
        if overwrite:
            os.replace(temporary, path)
        else:
            _link(temporary, path)
    except OSError as error:
        raise ledger.LedgerError(error.strerror or "cannot be written", path) from error
    finally:
        if os.path.lexists(temporary):
            os.unlink(temporary)


def _link(temporary: str, path: str) -> None:
    """Put `temporary` at `path`, never over a file there: a link fails
    if `path` appeared meanwhile, where a rename would overwrite it. A
    file system with no hard links falls back to a rename after one more
    look."""
    try:
        os.link(temporary, path)
    except FileExistsError:
        raise Exists(path) from None
    except OSError:
        if os.path.lexists(path):
            raise Exists(path) from None
        os.replace(temporary, path)


def _umask() -> int:
    mask = os.umask(0)
    os.umask(mask)
    return mask
