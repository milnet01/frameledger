"""Run as `python3 -I src/frameledger ...`, `python3 -I frameledger.pyz ...`,
or, installed by pip, `frameledger ...` or `python3 -m frameledger ...`."""

import os
import sys

# The modules import each other by bare name (docs/design.md § The parts).
# The first two forms already have this folder on the import path; the
# installed forms do not, so put it first, ahead of any other module of the
# same name (FLED-0043).
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import cli  # noqa: E402 - needs the path above

# A Windows console may not encode every character in a path; print a
# stand-in rather than stop with an encoding error.
# Standard output may be closed (None) when it runs headless (S20).
if sys.stdout is not None:
    sys.stdout.reconfigure(errors="backslashreplace")
sys.exit(cli.main(sys.argv[1:]))
