"""`alternate`: run the old and new builds' commands in turn, each into its
own run file (docs/specs/FLED-0001-run-file-format.md § 4.15).

This module only plans and runs the commands. It times nothing and reads
no run file: cli.py compares the files once every run has finished.
"""

from __future__ import annotations

import os
import re
import signal
import subprocess
import sys
import time
from typing import NamedTuple

import ledger

PLACEHOLDER = "{run}"
FEWEST_RUNS, MOST_RUNS = 3, 100
MOST_WARMUPS = 10
# The filled path needs no quoting in /bin/sh or cmd.exe.
SAFE_DIR = re.compile(r"[A-Za-z0-9._\-/\\:]+")
POSIX = os.name == "posix"
STOP_SIGNALS = (signal.SIGINT, signal.SIGTERM)
KILL = getattr(signal, "SIGKILL", signal.SIGTERM)  # Windows has no SIGKILL; _signal_group kills there
GRACE_S = 10  # how long a stopped command has to end before it is killed
POLL_S = 0.05  # how often a wait checks for a stop
SETTLE_S = 2  # how long a finished command's leftover processes have to end


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
    § 4.15's `stopped`, after ending the failed command's processes and
    deleting its file.

    While the commands run, Ctrl-C and SIGTERM are only recorded, never
    raised, so a stop cannot land between two steps; each wait checks
    for one (POLL_S)."""
    stops: list[int] = []
    previous = {signum: signal.signal(signum, lambda signum, _frame: stops.append(signum))
                for signum in STOP_SIGNALS}
    try:
        for index, run in enumerate(planned, 1):
            command = commands[run.side].replace(PLACEHOLDER, run.path)
            if stops:  # it came between two runs
                exit_code, reason = None, _stopped_reason(stops[0])
            else:
                print(f"alternate: running {run.name} ({index} of {len(planned)})", file=sys.stderr,
                      flush=True)
                exit_code, reason = _run_one(command, run.path, stops)
            if reason:
                if os.path.isfile(run.path):  # a directory there is not this run's to remove
                    os.remove(run.path)
                return {"run": run.name, "command": command, "reason": reason, "exit_code": exit_code,
                        "finished": [done.name for done in planned[:index - 1]]}
        return None
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def _run_one(command: str, path: str, stops: list[int]) -> tuple[int | None, str | None]:
    """(exit code, why the run failed), the reason None when it did not.
    The engine's output goes to standard error, so --json output is never
    mixed with it. On POSIX the command gets its own process group, so a
    stop reaches every process it started, a wrapper's engine included;
    the terminal's Ctrl-C then reaches only this process, which passes it
    on."""
    process = subprocess.Popen(command, shell=True, stdout=sys.stderr.fileno(), start_new_session=POSIX)
    code = _wait(process, stops)
    if code is None:
        return None, _stopped_reason(stops[0]) + _end_group(process, stops[0], stops)
    if code == 0 and POSIX and not _waited(process, lambda: bool(stops), SETTLE_S):
        # Left running, it would overlap the next run (UT Ants). SETTLE_S
        # lets a headless display finish tearing down first (DOOM Ants).
        if stops:
            return None, _stopped_reason(stops[0]) + _end_group(process, stops[0], stops)
        return None, "the command left processes running" + _end_group(process, signal.SIGTERM, stops)
    if code != 0:
        stuck = _end_group(process, signal.SIGTERM, stops)  # nothing left may write the file later
        return (None if code < 0 else code), _exit_reason(code) + stuck
    if not os.path.exists(path):
        return None, f"the command wrote no file at {path}"
    return code, None


def _wait(process: subprocess.Popen, stops: list[int]) -> int | None:
    """The command's exit code, or None once a stop is recorded."""
    while (code := process.poll()) is None:
        if stops:
            return None
        time.sleep(POLL_S)
    return code


def _end_group(process: subprocess.Popen, signum: int, stops: list[int]) -> str:
    """Send `signum` to the command's processes, give them GRACE_S seconds
    to end, then kill them, and give that GRACE_S too. A further stop
    kills them at once. Returns "" once none is left, or a clause naming
    the group that would not die, as a process stuck in a GPU driver can
    (UT Ants)."""
    seen = len(stops)
    _signal_group(process, signum)
    if not _waited(process, lambda: len(stops) > seen):
        _signal_group(process, KILL)
        if not _waited(process, lambda: False):
            return f"; process group {process.pid} did not end after SIGKILL"
    return ""


def _waited(process: subprocess.Popen, give_up, seconds: float = GRACE_S) -> bool:
    """True once the command's processes have all ended; False after
    `seconds`, or as soon as give_up() is true."""
    deadline = time.monotonic() + seconds
    while _group_alive(process):
        if give_up() or time.monotonic() >= deadline:
            return False
        time.sleep(POLL_S)
    return True


def _signal_group(process: subprocess.Popen, signum: int) -> None:
    if not POSIX:  # Windows: the console's Ctrl-C reached the command itself
        if signum != signal.SIGINT and process.poll() is None:
            process.kill()
        return
    try:
        os.killpg(process.pid, signum)
    except ProcessLookupError:
        pass


def _group_alive(process: subprocess.Popen) -> bool:
    if process.poll() is None:  # poll also reaps the shell once it has ended
        return True
    if not POSIX:
        return False
    try:
        os.killpg(process.pid, 0)
    except ProcessLookupError:
        return False
    return True


def _exit_reason(code: int) -> str:
    if code < 0:
        return f"the command was killed by signal {-code} ({_signal_name(-code)})"
    reason = f"the command exited with code {code}"
    if POSIX and 128 < code < 128 + signal.NSIG:  # how /bin/sh reports a killed command
        reason += f", as the shell reports a command killed by signal {code - 128} ({_signal_name(code - 128)})"
    return reason


def _stopped_reason(signum: int) -> str:
    return f"alternate was stopped by {_signal_name(signum)} while it ran"


def _signal_name(signum: int) -> str:
    try:
        return signal.Signals(signum).name
    except ValueError:
        return f"signal {signum}"


def stopped_sentences(stopped: dict) -> list[str]:
    return [f"{stopped['run']} failed: {stopped['reason']}.", f"Its command was: {stopped['command']}"]
