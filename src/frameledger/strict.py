"""`check --strict`: warnings on what is legal but unwise
(docs/specs/FLED-0001-run-file-format.md § 4.19).

Every value is compared in whole thousandths, as written, so no
threshold depends on floating point. Each warning is a ledger.Notice,
named by the code in § 4.19's table.
"""

from __future__ import annotations

import ledger
import stats

FIXED_LEAST = 10  # walls, or frame/gpu_span rows, before all-equal means a fixed value
CEILING_LEAST = 3  # frames holding the longest wall before it can be a ceiling
PERIODIC_LEAST = 5  # slow frames before their spacing is judged
WHOLE_MS = 1000  # thousandths in a millisecond

MACHINE_STATE = ("load", "gpu_busy_pct", "gpu_clock_mhz", "cpu_governor", "turbo", "power",
                 "cpu_clock_mhz", "cpu_temp_c", "gpu_temp_c", "throttled")


def warnings(run: ledger.Run) -> list[ledger.Notice]:
    """§ 4.19's warnings on a run that meets the format, in the table's
    order. A run with breaches gets none: what is unwise is judged only
    on what is legal."""
    if run.breaches or run.header is None:
        return []
    walls = {frame: rows[("frame", "wall")].thousandths
             for frame, rows in sorted(run.frames.items()) if ("frame", "wall") in rows}
    found: list[ledger.Notice] = []
    for check in (_wall_fixed, _wall_stepped, _wall_ceiling, _wall_periodic):
        found += check(run, walls)
    for check in (_span_over_wall, _gpu_span_flat, _no_gpu_span, _passes_over_span, _depth_gap,
                  _no_segments, _whole_second_start, _no_machine_state, _says_unknown):
        found += check(run)
    return found


def _ms(thousandths: int) -> str:
    """A value in thousandths as § 4.4 writes it: 16.667."""
    whole, part = divmod(abs(thousandths), 1000)
    return f"{'-' if thousandths < 0 else ''}{whole}.{part:03d}"


def _frames(numbers) -> str:
    """`frame 3`, or `frames 3, 9 and 15`, naming at most five."""
    numbers = list(numbers)
    return f"frame{'' if len(numbers) == 1 else 's'} {ledger.listed(map(str, numbers))}"


def _known(run: ledger.Run, field: str, value: bool) -> bool:
    """The header's boolean `field` is `value` and not a stand-in."""
    return run.header.get(field) is value and field not in run.unknown


def _wall_fixed(run: ledger.Run, walls: dict[int, int]) -> list[ledger.Notice]:
    values = set(walls.values())
    if len(walls) < FIXED_LEAST or len(values) != 1:
        return []
    return [ledger.Notice("wall_fixed", f"all {len(walls)} frame/wall values are {_ms(values.pop())} ms: "
                          "a fixed simulation step, not real time")]


def _wall_stepped(run: ledger.Run, walls: dict[int, int]) -> list[ledger.Notice]:
    """Every wall within 0.001 ms of a whole multiple of the shortest, as a
    clock that ticks gives. The margin stays one thousandth however many
    steps a wall spans, so a short smallest wall cannot fit them all."""
    values = list(walls.values())
    if len(values) < FIXED_LEAST or len(set(values)) < 2 or not _known(run, "vsync", False):
        return []
    step = min(values)
    if step < WHOLE_MS or not all(w % step <= 1 or step - w % step <= 1 for w in values):
        return []
    return [ledger.Notice("wall_stepped", f"every frame/wall is within 0.001 ms of a whole multiple of the "
                          f"shortest, {_ms(step)} ms, with vsync off: a clock that ticks")]


def _wall_ceiling(run: ledger.Run, walls: dict[int, int]) -> list[ledger.Notice]:
    """The longest wall shared by several frames, far above the median: a
    clamped clock. A clock counting whole milliseconds is skipped, since
    its missed-vsync frames all land on one value."""
    if not walls or all(w % WHOLE_MS == 0 for w in walls.values()):
        return []
    longest = max(walls.values())
    held = [frame for frame, wall in walls.items() if wall == longest]
    median = stats.median(list(walls.values()))
    if len(held) < CEILING_LEAST or 100 * len(held) < len(walls) or longest < 2 * median:
        return []
    return [ledger.Notice("wall_ceiling", f"{len(held)} frames share the longest frame/wall, {_ms(longest)} ms, "
                          f"at least twice the median {_ms(median)} ms: a clamped clock ({_frames(held)})")]


def _wall_periodic(run: ledger.Run, walls: dict[int, int]) -> list[ledger.Notice]:
    """Slow frames at a steady spacing: the writer's own flush. Frames
    holding an `event/cut`, and each segment's first frame, are left out of
    the slow frames, never out of the median."""
    if not walls:
        return []
    median = stats.median(list(walls.values()))
    skipped = {frame for frame, rows in run.frames.items() if ("event", "cut") in rows}
    firsts: dict[str, int] = {}
    for frame, rows in sorted(run.frames.items()):
        firsts.setdefault(ledger.frame_segment(rows), frame)
    # A segment's first frame is its first ever: a re-entry is a camera
    # jump, which carries an event/cut (§ 4.4), left out above. Frames with
    # no segment are in no segment, so a run without segments keeps its
    # first frame; such a run already warns no_segments.
    skipped |= {frame for segment, frame in firsts.items() if segment}
    # Over 1.5 times the median, in whole thousandths: 2 * wall > 3 * median.
    slow = [frame for frame, wall in walls.items() if 2 * wall > 3 * median and frame not in skipped]
    if len(slow) < PERIODIC_LEAST:
        return []
    gaps = [later - earlier for earlier, later in zip(slow, slow[1:], strict=False)]
    usual = stats.median(gaps)
    near = sum(1 for gap in gaps if abs(gap - usual) <= 1)
    if usual < 3 or 5 * near < 4 * len(gaps):
        return []
    return [ledger.Notice("wall_periodic", f"{len(slow)} slow frames, over 1.5 times the median frame/wall of "
                          f"{_ms(median)} ms, come about every {usual} frames: the writer's own flush? "
                          f"({_frames(slow)})")]


def _over(total: int, limit: int) -> bool:
    """More than 1% over: 100 * (total - limit) > limit."""
    return 100 * (total - limit) > limit


def _span_over_wall(run: ledger.Run) -> list[ledger.Notice]:
    """A span over its wall by more than 1%: the wrong clock or units.
    Per frame only for `cpu_span` in a run known not to pipeline; a
    GPU-bound run's `gpu_span` passes its wall on about half its frames
    whatever the engine does, so it is judged as a total only."""
    found = []
    pairs = {name: [(frame, rows[("frame", name)].thousandths, rows[("frame", "wall")].thousandths)
                    for frame, rows in sorted(run.frames.items())
                    if ("frame", name) in rows and ("frame", "wall") in rows]
             for name in ("cpu_span", "gpu_span")}
    totals = ["gpu_span"]
    if _known(run, "pipelined", False):
        over = [frame for frame, span, wall in pairs["cpu_span"] if _over(span, wall)]
        if over:
            found.append(ledger.Notice("span_over_wall", f"frame/cpu_span is over frame/wall by more than 1% "
                                       f"in a run not pipelined: the wrong clock or units? ({_frames(over)})"))
    else:
        totals.insert(0, "cpu_span")
    for name in totals:
        span = sum(pair[1] for pair in pairs[name])
        wall = sum(pair[2] for pair in pairs[name])
        if pairs[name] and _over(span, wall):
            found.append(ledger.Notice("span_over_wall", f"the frame/{name} total, {_ms(span)} ms, is over the "
                                       f"frame/wall total, {_ms(wall)} ms, by more than 1%, over the "
                                       f"{len(pairs[name])} frames with both: the wrong clock or units?"))
    return found


def _gpu_span_flat(run: ledger.Run) -> list[ledger.Notice]:
    spans = [rows[("frame", "gpu_span")].thousandths for rows in run.frames.values() if ("frame", "gpu_span") in rows]
    if len(spans) < FIXED_LEAST or len(set(spans)) != 1:
        return []
    return [ledger.Notice("gpu_span_flat", f"all {len(spans)} frame/gpu_span values are {_ms(spans[0])} ms: "
                          "a GPU timestamp query never read back?")]


def _no_gpu_span(run: ledger.Run) -> list[ledger.Notice]:
    if any(("frame", "gpu_span") in rows for rows in run.frames.values()):
        return []
    return [ledger.Notice("no_gpu_span", "no frame has a frame/gpu_span row, so no report can say whether "
                          "the run is GPU-bound")]


def _passes_over_span(run: ledger.Run) -> list[ledger.Notice]:
    """Depth-0 rows summing to more than their span. Each row and the span
    are rounded on their own, so N rows may sum to (N + 1) / 2
    thousandths over it in a correct writer."""
    found = []
    for category in ("cpu", "gpu"):
        over = []
        for frame, rows in sorted(run.frames.items()):
            span = rows.get(("frame", f"{category}_span"))
            parts = [row.thousandths for (cat, _), row in rows.items() if cat == category and row.depth == 0]
            if span is not None and parts and 2 * (sum(parts) - span.thousandths) > len(parts) + 1:
                over.append(frame)
        if over:
            found.append(ledger.Notice("passes_over_span", f"the {category} depth-0 rows sum to more than "
                                       f"frame/{category}_span by over (N + 1) / 2 thousandths, N the rows "
                                       f"summed, which is more than rounding allows ({_frames(over)})"))
    return found


def _depth_gap(run: ledger.Run) -> list[ledger.Notice]:
    gaps = []
    for frame, rows in sorted(run.frames.items()):
        depths = {(cat, row.depth) for (cat, _), row in rows.items() if cat in ("cpu", "gpu")}
        if any(depth > 0 and (cat, depth - 1) not in depths for cat, depth in depths):
            gaps.append(frame)
    if not gaps:
        return []
    return [ledger.Notice("depth_gap", f"a cpu or gpu row sits deeper than any row of its category one depth "
                          f"above it ({_frames(gaps)})")]


def _no_segments(run: ledger.Run) -> list[ledger.Notice]:
    if any(row.segment for rows in run.frames.values() for row in rows.values()):
        return []
    return [ledger.Notice("no_segments", "no row has a segment, so no report can tell one view or stretch "
                          "of the run from another")]


def _whole_second_start(run: ledger.Run) -> list[ledger.Notice]:
    started = run.header["started_utc"]
    if "." in started:
        return []
    return [ledger.Notice("whole_second_start", f"started_utc, {started}, has no fraction of a second, so two "
                          "runs started in one second cannot be ordered")]


def _no_machine_state(run: ledger.Run) -> list[ledger.Notice]:
    if any(field in run.header for field in MACHINE_STATE):
        return []
    return [ledger.Notice("no_machine_state", f"the header gives none of {ledger.listed_names(list(MACHINE_STATE))}, "
                          "so a busy, slowed or hot machine cannot be told from a regression")]


def _says_unknown(run: ledger.Run) -> list[ledger.Notice]:
    """A string field reading `unknown`, in any case, that `unknown` does
    not list: it is compared as a real value. Only § 4.18.1's fields may be
    listed, so the message suggests it for those alone. `tool.version` is
    not top-level, so an import without --presentmon-version is not judged."""
    found = []
    for name, value in run.header.items():
        if name not in ledger.HEADER_FIELDS or not isinstance(value, str) or value.lower() != "unknown" \
                or name in run.unknown:
            continue
        remedy = ("; list it in 'unknown' if it holds a stand-in" if name in ledger.UNKNOWABLE
                  else "; 'unknown' cannot list it, so give the real value")
        found.append(ledger.Notice("says_unknown", f"the header's '{name}' is '{value}', so it is compared as "
                                   f"a real value{remedy}"))
    return found
