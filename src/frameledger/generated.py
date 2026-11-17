"""Generated frames (FLED-0075): frames a driver or an SDK made between two
rendered ones, each marked `event/generated`.

The rules are docs/specs/FLED-0001-run-file-format.md § 4.20. By default
every command that judges or reports frame times reads the application's
frames: `read` leaves the generated ones out and adds each one's wall to
the application frame before it. Under --all-frames it reads every frame
as written. `check` never comes here: it judges the file.

Who finds a hole in the frame numbers: `application_frames` before the
first application frame, which no kept frame can show, and wherever a
hole leaves an application frame's wall unknown; run_report.timeline
everywhere else, stepping over the frames left out.
"""

from __future__ import annotations

import dataclasses

import ledger

MARK = ("event", "generated")
WALL = ("frame", "wall")


def read(path: str, all_frames: bool) -> ledger.Run:
    """The run at `path`: as written under --all-frames (`all_frames`), and
    otherwise its application frames alone. Raises LedgerError when the
    file cannot be read, or when every frame was generated."""
    run = ledger.read(path)
    return run if all_frames else application_frames(run)


def application_frames(run: ledger.Run) -> ledger.Run:
    """`run` without its generated frames. An application frame's wall runs
    to the next application frame's start: its own plus each generated
    frame's after it. It has none if any of those walls is missing, or a
    frame number is missing among them, since the missing frame may have
    been generated: nothing is guessed.

    A run breaking the format is returned as read, for the command to
    refuse with its breach. A run whose every frame was generated has
    nothing to judge, so it raises LedgerError."""
    if run.breaches or not any(MARK in rows for rows in run.frames.values()):
        return run
    order = sorted(run.frames)
    left_out = frozenset(number for number in order if MARK in run.frames[number])
    if len(left_out) == len(order):
        raise ledger.LedgerError(f"every one of its {len(order)} frames was generated, so there is no "
                                 "application frame to judge; --all-frames counts them", run.path)
    first = next(number for number in order if number not in left_out)
    start_us, start_unknown = _before_first(run, [number for number in order if number < first], first)
    kept: dict[int, dict] = {}
    owner, previous = first, None  # owner: the application frame the generated frames since belong to
    for number in order[order.index(first):]:
        if previous is not None and number != previous + 1:
            kept[owner].pop(WALL, None)
        previous = number
        if number in left_out:
            _add_wall(kept[owner], run.frames[number].get(WALL))
        else:
            kept[number], owner = dict(run.frames[number]), number
    return dataclasses.replace(run, frames=kept, left_out=left_out, start_us=start_us,
                               start_unknown=start_unknown)


def _before_first(run: ledger.Run, leading: list[int], first: int) -> tuple[int, str | None]:
    """The generated frames `leading` the first application frame, `first`,
    belong to none, but their walls move the timeline (§ 4.20): the time
    they take, and what stops it being known, a missing frame or wall, or
    None."""
    start_us, previous = 0, None
    for number in [*leading, first]:
        if previous is not None and number != previous + 1:
            return start_us, f"frame {previous + 1} is missing"
        if number == first:
            return start_us, None
        wall = run.frames[number].get(WALL)
        if wall is None:
            return start_us, f"frame {number} has no frame/wall row"
        start_us += wall.thousandths
        previous = number
    return start_us, None  # not reached: the loop ends at `first`


def _add_wall(rows: dict, wall: ledger.Row | None) -> None:
    """Add a generated frame's wall to its application frame's `rows`,
    which keep none once either is missing."""
    own = rows.get(WALL)
    if own is None:
        return
    if wall is None:
        del rows[WALL]
    else:
        rows[WALL] = dataclasses.replace(own, thousandths=own.thousandths + wall.thousandths)


def count(run: ledger.Run) -> int:
    """How many of the run's frames were generated: those `read` left out,
    or under --all-frames, where it leaves none out, those marked."""
    return len(run.left_out) or sum(MARK in rows for rows in run.frames.values())


def sentence(run: ledger.Run, all_frames: bool, name: str = "") -> str | None:
    """§ 4.20's opening sentence for a run holding generated frames, or
    None; `name` is the run's where the command names runs."""
    generated = count(run)
    if not generated:
        return None
    total = len(run.frames) + len(run.left_out)
    opening = f"{name}: " if name else ""
    was, are = ("was", "is") if generated == 1 else ("were", "are")
    ending = f"{are} counted, as --all-frames asks" if all_frames else f"{are} left out; --all-frames counts them"
    return (f"{opening}{generated} of {total} frames {was} generated, not rendered by the application, "
            f"and {ending}.")
