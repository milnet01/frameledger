"""Generated frames (FLED-0075): frames a driver or an SDK made between two
rendered ones, each marked `event/generated`.

The rules are docs/specs/FLED-0001-run-file-format.md § 4.20. By default
every command that judges or reports frame times reads the application's
frames: `read` leaves the generated ones out and adds each one's wall to
the application frame before it. Under --all-frames it reads every frame
as written. `check` never comes here: it judges the file.
"""

from __future__ import annotations

import dataclasses

import ledger

MARK = ("event", "generated")
WALL = ("frame", "wall")


def read(path: str, all_frames: bool) -> ledger.Run:
    """The run at `path`, as the command reads it."""
    run = ledger.read(path)
    return run if all_frames else application_frames(run)


def application_frames(run: ledger.Run) -> ledger.Run:
    """`run` without its generated frames. An application frame's wall runs
    to the next application frame's start: its own plus each generated
    frame's after it, or none if any of those is missing, since nothing is
    guessed. Generated frames before the first application frame belong
    to none, but their walls still move the timeline (`lead_us`).

    A run breaking the format is returned as read, for the command to
    refuse with its breach. A run whose every frame was generated has
    nothing to judge, so it raises LedgerError."""
    if run.breaches or not any(MARK in rows for rows in run.frames.values()):
        return run
    kept: dict[int, dict] = {}
    left_out: set[int] = set()
    owner = None  # the application frame the generated frames since then belong to
    lead_us, lead_stop, previous = 0, None, None
    for number in sorted(run.frames):
        rows = run.frames[number]
        if owner is None and lead_stop is None and previous is not None and number != previous + 1:
            lead_stop = f"frame {previous + 1} is missing"  # a hole the kept frames cannot show
        previous = number
        if MARK not in rows:
            kept[number], owner = dict(rows), number
            continue
        left_out.add(number)
        wall = rows.get(WALL)
        if owner is None:
            if wall is None:
                lead_stop = lead_stop or f"frame {number} has no frame/wall row"
            else:
                lead_us += wall.thousandths
            continue
        own = kept[owner].get(WALL)
        if own is not None and wall is None:
            del kept[owner][WALL]
        elif own is not None:
            kept[owner][WALL] = dataclasses.replace(own, thousandths=own.thousandths + wall.thousandths)
    if not kept:
        raise ledger.LedgerError(f"every one of its {len(left_out)} frames was generated, so there is no "
                                 "application frame to judge; --all-frames counts them", run.path)
    return dataclasses.replace(run, frames=kept, generated=frozenset(left_out), lead_us=lead_us,
                               lead_stop=lead_stop)


def count(run: ledger.Run) -> int:
    """How many of the run's frames were generated, left out or not."""
    return len(run.generated) or sum(MARK in rows for rows in run.frames.values())


def sentence(run: ledger.Run, all_frames: bool, name: str = "") -> str | None:
    """§ 4.20's opening sentence for a run holding generated frames, or
    None; `name` is the run's where the command names runs."""
    generated = count(run)
    if not generated:
        return None
    total = len(run.frames) + len(run.generated)
    opening = f"{name}: " if name else ""
    was, are = ("was", "is") if generated == 1 else ("were", "are")
    ending = f"{are} counted, as --all-frames asks" if all_frames else f"{are} left out; --all-frames counts them"
    return (f"{opening}{generated} of {total} frames {was} generated, not rendered by the application, "
            f"and {ending}.")
