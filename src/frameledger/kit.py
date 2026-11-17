"""`kit DIR`: write the kit that proves a stranger's writer
(docs/specs/FLED-0001-run-file-format.md § 4.19).

The kit is plain data in `kit/` beside this module: README.txt, and for
each case NAME.json, what an engine measured, and NAME.csv, the run file
a correct writer makes from it. scripts/make_kit.py makes each NAME.csv
with the shipped writer. The files are read with pkgutil.get_data, which
reads the source tree and frameledger.pyz alike, and are written as the
bytes they are.
"""

from __future__ import annotations

import pkgutil
from pathlib import Path

import ledger

# A folder inside the .pyz cannot be listed through its loader, so the
# cases are named here; tests/test_kit.py checks this against kit/.
CASES = (
    "basic",
    "dropped",
    "events",
    "frame-hole",
    "frame-numbers-large",
    "gpu-after-last",
    "gpu-after-last-dropped",
    "gpu-late",
    "gpu-late-segments",
    "gpu-over-wall-not-pipelined",
    "header-every-field",
    "header-required-only",
    "hitch",
    "longest-fields",
    "negative",
    "pipelined-gpu-over-wall",
    "quoting",
    "round-largest",
    "round-ties",
    "static-no-summary",
    "static-summary",
    "unfinished",
)


def names() -> list[str]:
    """Every file the kit holds, README.txt first."""
    return ["README.txt", *(f"{case}.{kind}" for case in CASES for kind in ("json", "csv"))]


def write(directory: str) -> list[str]:
    """Write the kit into `directory`, made when missing, and return the
    names written. Raises LedgerError, writing nothing, when `directory`
    holds anything."""
    target = Path(directory)
    if target.exists() and not target.is_dir():
        raise ledger.LedgerError("is not a directory", directory)
    if target.is_dir() and any(target.iterdir()):
        raise ledger.LedgerError("already holds files; the kit is written only into an empty or missing "
                                 "directory", directory)
    contents = {name: _data(name) for name in names()}  # all read first, so a missing one writes nothing
    try:
        target.mkdir(parents=True, exist_ok=True)
        for name, data in contents.items():
            with open(target / name, "xb") as stream:
                stream.write(data)
    except OSError as error:
        raise ledger.LedgerError(error.strerror or "cannot be written", str(error.filename or directory)) from error
    return list(contents)


def _data(name: str) -> bytes:
    try:
        data = pkgutil.get_data(__name__, f"kit/{name}")
    except OSError:
        data = None
    if data is None:
        raise ledger.LedgerError(f"the kit's {name} is missing from this copy of frameledger")
    return data
