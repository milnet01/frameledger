"""`schema COMMAND`: the JSON Schema of one command's `--json` result
(docs/specs/FLED-0041-json-result-schemas.md).

The schemas are plain data in `schemas/` beside this module, one
COMMAND.schema.json per command that prints a result. They are written
by hand and read with pkgutil.get_data, which reads the source tree and
frameledger.pyz alike, and are printed as the bytes they are.
"""

from __future__ import annotations

import pkgutil

import ledger

# A folder inside the .pyz cannot be listed through its loader, so the
# commands are named here; tests/test_schemas.py checks this against
# schemas/. These are the values a result's `command` key takes.
COMMANDS = ("check", "kit", "report", "floor", "compare", "alternate", "bisect", "budget", "survey", "import",
            "selftest")


def data(command: str | None) -> bytes:
    """The schema file of `command`. The name only picks from COMMANDS:
    it is user input, and never becomes part of a path (INV-10)."""
    if command not in COMMANDS:
        asked = "name the command whose schema to print" if command is None else f"no command is called '{command}'"
        raise ledger.LedgerError(f"{asked}; the schemas are {', '.join(COMMANDS)}")
    try:
        found = pkgutil.get_data(__name__, f"schemas/{command}.schema.json")
    except OSError:
        found = None
    if found is None:
        raise ledger.LedgerError(f"the schema of {command} is missing from this copy of frameledger")
    return found
