"""The installed form (FLED-0043): pip puts this folder in site-packages as
the package `frameledger`, and its `frameledger` command calls main().

The modules import each other by bare name, as they do when this folder or
frameledger.pyz is run directly (docs/design.md § The parts), so importing
the package puts this folder first on the import path. frameledger is a
command, not a library: a program that imports it gets that path too.

The other two run forms never import this file.
"""

import os
import runpy
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)


def main() -> None:
    """Run the analyser as `python3 -I src/frameledger` does; exits with its code."""
    runpy.run_path(os.path.join(_HERE, "__main__.py"), run_name="__main__")
