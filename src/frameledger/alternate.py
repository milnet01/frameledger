"""`alternate`: run the old and new builds' commands in turn, each into its
own run file (docs/specs/FLED-0001-run-file-format.md § 4.15).

This module only plans and runs the commands. It times nothing and reads
no run file: cli.py compares the files once every run has finished.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from typing import NamedTuple

import ledger

PLACEHOLDER = "{run}"
FEWEST_RUNS, MOST_RUNS = 3, 100
MOST_WARMUPS = 10
# The filled path needs no quoting in /bin/sh or cmd.exe.
SAFE_DIR = re.compile(r"[A-Za-z0-9._\-/\\:]+")


class Run(NamedTuple):
    name: str     # old-1, new-warmup-1, ...
    side: str     # old or new
    number: int   # 1 for old-1 and old-warmup-1
    timed: bool   # False for a warm-up, which is never compared
    path: str     # the run's own file, absolute


def plan(out: str, runs: int, warmup: int) -> list[Run]:
    """Warm-ups first, old then new; then pairs, old first in odd pairs and
    new first in even ones, so a steady drift cancels over every two pairs."""
    planned = []
    for number in range(1, warmup + 1):
        planned += [_run(out, side, number, False) for side in ("old", "new")]
    for number in range(1, runs + 1):
        sides = ("old", "new") if number % 2 else ("new", "old")
        planned += [_run(out, side, number, True) for side in sides]
    return planned


def _run(out: str, side: str, number: int, timed: bool) -> Run:
    name = f"{side}-{number}" if timed else f"{side}-warmup-{number}"
    return Run(name, side, number, timed, os.path.join(out, f"{name}.csv"))


def check_setup(commands: dict[str, str], out: str, planned: list[Run]) -> None:
    """Every setup error, found before any command starts."""
    for side, command in commands.items():
        if PLACEHOLDER not in command:
            raise ledger.LedgerError(f"--{side} must hold {PLACEHOLDER}, where its run file's path goes")
    if not os.path.isdir(out):
        raise ledger.LedgerError(f"--out {out} is not an existing folder")
    if not SAFE_DIR.fullmatch(out):
        raise ledger.LedgerError(f"--out {out} may hold only ASCII letters, digits and . _ - / \\ :, "
                                 "so its path needs no quoting; pick a folder without spaces")
    for run in planned:
        if os.path.lexists(run.path):
            raise ledger.LedgerError(f"{run.path} already exists, and no run file is overwritten; "
                                     "give a new --out, or remove its run files")


def run_all(commands: dict[str, str], planned: list[Run]) -> dict | None:
    """Run each command in turn. None when every run finished; otherwise
    § 4.15's `stopped`, after deleting the failed run's file."""
    for index, run in enumerate(planned, 1):
        command = commands[run.side].replace(PLACEHOLDER, run.path)
        print(f"alternate: running {run.name} ({index} of {len(planned)})", file=sys.stderr, flush=True)
        exit_code, reason = _run_one(command, run.path)
        if reason:
            if os.path.lexists(run.path):
                os.remove(run.path)
            return {"run": run.name, "command": command, "reason": reason, "exit_code": exit_code,
                    "finished": [done.name for done in planned[:index - 1]]}
    return None


def _run_one(command: str, path: str) -> tuple[int | None, str | None]:
    """(exit code, why the run failed), the reason None when it did not.
    The engine's output goes to standard error, so --json output is never
    mixed with it."""
    process = subprocess.Popen(command, shell=True, stdout=sys.stderr.fileno())
    try:
        code = process.wait()
    except KeyboardInterrupt:
        # The terminal sent the interrupt to the command too; wait for it to
        # end before its file is deleted. A second interrupt kills it.
        try:
            process.wait()
        except KeyboardInterrupt:
            process.kill()
            process.wait()
        return None, "alternate was interrupted while it ran"
    if code != 0:
        return code, f"the command exited with code {code}"
    if not os.path.exists(path):
        return None, f"the command wrote no file at {path}"
    return code, None


def stopped_sentences(stopped: dict) -> list[str]:
    return [f"{stopped['run']} failed: {stopped['reason']}.", f"Its command was: {stopped['command']}"]
