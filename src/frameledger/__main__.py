"""Run as `python3 -I src/frameledger ...` or `python3 -I frameledger.pyz ...`."""

import sys

import cli

# A Windows console may not encode every character in a path; print a
# stand-in rather than stop with an encoding error.
sys.stdout.reconfigure(errors="backslashreplace")
sys.exit(cli.main(sys.argv[1:]))
