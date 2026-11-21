"""The installed form (FLED-0043): pip puts this folder in site-packages as
the package `frameledger`, and its `frameledger` command calls main().

Importing the package does nothing else. __main__.py puts this folder on
the import path when frameledger runs, since its modules import each other
by bare name (docs/design.md § The parts). frameledger is a command, not a
library: main() runs it in this process, path change included, so a
host program's own `cli` or `stats` module may meet frameledger's. Offered
as a library, it would need package imports (`from frameledger import
ledger`) instead.

scripts/build_release.py leaves this file out of the .pyz, and the source
form never imports it.
"""

import os
import runpy
from typing import NoReturn


def main() -> NoReturn:
    """Run the analyser as `python3 -I src/frameledger` does; exits with its code.

    It runs __main__.py, never cli.main itself, so __main__'s path and
    output setup apply. `python -m frameledger` runs __main__.py directly.
    """
    runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "__main__.py"), run_name="__main__")
