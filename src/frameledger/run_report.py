"""One run: cost ranking, bound-by share and worst frames (S2, S3, S13),
and the floor check (S8).

Builds the `report` and `floor` commands' opening sentences, warnings and
results, in the shape of docs/specs/FLED-0001-run-file-format.md § 4.7
and § 4.8. Nothing here names the file or a line number: INV-3 and INV-4
need the same rows to give byte-identical JSON whatever the path, line
endings or row order. So warnings name the frame instead.
"""

from __future__ import annotations

import math
from bisect import bisect_left, bisect_right
from collections import defaultdict
from decimal import ROUND_CEILING, Decimal
from typing import NamedTuple

import ledger
import stats
import trust

WORST_FRAMES = 10
SPAN = {"cpu": "cpu_span", "gpu": "gpu_span"}  # the span each category's passes are shares of
REMAINDER = {"cpu": "cpu_remainder", "gpu": "gpu_remainder"}
FRAME_ORDER = ["cpu_span", "gpu_span", "wall", "fence_wait", "present_wait"]
# § 4.8: dropped rows and an unfinished run open the sentences, before other warnings.
FIRST_WARNINGS = ("rows_dropped", "unfinished")


def report(run: ledger.Run) -> dict:
    """{"summary", "warnings", "result"} for one Run. A Run that breaks the
    format raises LedgerError naming its first breach: § 6, never skip a row."""
    _refuse_breaches(run)
    costs = _Costs(run)
    result = {
        "passes": costs.passes(),
        "frame_times": costs.frame_times(),
        "bound_by": _bound_by(run),
        "worst_frames": _worst_frames(run),
        "missing_gpu_frames": costs.missing_gpu,
        "static": run.static,
    }
    measured = sum(("frame", "wall") in rows for rows in run.frames.values())
    notices = run.notices + trust.warnings(run, measured)
    warnings = [{"code": n.code, "message": n.message} for n in notices]
    summary = _warning_sentences(notices)
    if costs.missing_gpu:
        message = (f"{_frames(costs.missing_gpu)} no GPU result; they are left out of the GPU "
                   "figures, not counted as zero")
        warnings.append({"code": "gpu_missing", "message": message})
        summary.append(f"{message[0].upper()}{message[1:]}.")
    summary += _headline(run, result, costs)
    return {"summary": summary, "warnings": warnings, "result": result}


def _refuse_breaches(run: ledger.Run) -> None:
    if run.breaches:
        first = run.breaches[0]
        raise ledger.LedgerError(f"{first.message}; the file breaks the run-file format, so it "
                                 "cannot be judged (`check` lists every breach)", run.path, first.line)


SECOND = 1_000_000  # microseconds; a ms row's thousandths are microseconds
# The floor's opening sentences say these themselves, as reasons.
FLOOR_REASONS = ("rows_dropped", "unfinished", "wall_missing", "frame_missing")


def floor(run: ledger.Run, fps: Decimal, warmup_us: int, budget: int, windows: bool = True,
          frames: bool = True, allowed: int = 0) -> dict:
    """{"verdict", "summary", "warnings", "result"} for S8's two checks,
    each judged apart; `budget` is in microseconds. With the window check
    off, `fps` only names the floor, so it need not give a frame time in
    range (cli.py checks that).

    Dropped rows, an unfinished run or a hole in the timeline make the
    window check inconclusive (INV-7): a missing frame moves every later
    frame into the wrong window. A frame over the budget still fails,
    since its own wall row is real and missing rows only shorten the
    timeline, so a frame placed after the warm-up truly ended after it
    (the three engines' review)."""
    _refuse_breaches(run)
    timed, cuts, stop, end = _timeline(run)
    judged = [t for t in timed if t[2] >= warmup_us]
    full, skipped = (_windows([t[2] for t in timed], [t[3] for t in timed], cuts, warmup_us, end)
                     if windows else ([], 0))
    limit = frame_time_us(fps) if windows else None
    slow = [t for t in judged if t[3] > budget] if frames else []
    dropped = run.close["rows_dropped"] if run.close else None

    reasons = []
    if dropped:
        reasons.append(f"The writer dropped {_count(dropped, 'row')}, so frames may be missing "
                       "from the timeline.")
    if run.close is None:
        reasons.append("The file has no close line, so the run did not finish.")
    if stop:
        reasons.append(f"{stop[0].upper()}{stop[1:]}, so the timeline stops there.")
    failed = [w for w in full if not _window_passes(w, limit)]

    window_state = (None if not windows else "inconclusive" if reasons or not full
                    else "fail" if failed else "pass")
    frame_state = (None if not frames else "fail" if len(slow) > allowed
                   else "inconclusive" if reasons or not judged else "pass")
    states = {window_state, frame_state}
    warmup = f"{warmup_us / SECOND:g} s warm-up"
    no_window = f"no full one-second window follows the {warmup}"
    no_frame = f"no frame ends after the {warmup}"
    said = set()  # inconclusive checks the verdict sentence already explains
    if "fail" in states:
        verdict = "fail"
        failures = []
        if window_state == "fail":
            failures.append(f"{_count(len(failed), 'one-second window')} fell below {_num(fps)} FPS")
        if frame_state == "fail":
            failures.append(f"{_count(len(slow), 'frame')} took longer than {_ms(budget):.3f} ms "
                            f"({allowed} allowed)")
        opening = f"The run fails the {_num(fps)} FPS floor: {' and '.join(failures)}."
    elif "inconclusive" in states:
        verdict = "inconclusive"
        whys = []
        if reasons:
            whys.append("the run is incomplete, so it cannot pass")
        else:
            if window_state == "inconclusive":
                whys.append(f"{no_window}, so the window check could not run")
                said.add("windows")
            if frame_state == "inconclusive":
                whys.append(f"{no_frame}, so the single-frame check could not run")
                said.add("frames")
        opening = f"The floor check is inconclusive: {' and '.join(whys)}."
    else:
        verdict = "pass"
        opening = f"The run passes the {_num(fps)} FPS floor."

    notices = run.notices + trust.warnings(run, len(judged), {t[0] for t in judged})
    shown = [n for n in notices if n.code not in FLOOR_REASONS]
    summary = reasons + _warning_sentences(shown) + [opening]
    if not windows:
        summary.append("The window check is off (--no-windows).")
    elif full:
        slowest = min(full, key=lambda w: (-_window_mean(w), w.start))
        held = (f"had {slowest.frames} frames averaging {_window_mean(slowest):.3f} ms" if slowest.frames
                else "had no frame end in it")
        summary.append(f"Windows: {len(full) - len(failed)} of {len(full)} one-second windows after "
                       f"the {warmup} held {_num(fps)} FPS; the slowest, at {slowest.start / SECOND:.3f} s, "
                       f"{held}.")
        if reasons and failed:
            summary.append(f"With frames missing, the {_count(len(failed), 'window')} below "
                           f"{_num(fps)} FPS may be an artefact, so the window check is inconclusive.")
    elif "windows" not in said:
        summary.append(f"{no_window[0].upper()}{no_window[1:]}.")
    if skipped:
        summary.append(f"{_count(skipped, 'window')} shorter than one second, cut short by an "
                       f"event/cut or the end of the run, {'was' if skipped == 1 else 'were'} skipped.")
    if not frames:
        summary.append("The single-frame check is off (--no-frames).")
    elif slow:
        longest = min(slow, key=lambda t: (-t[3], t[0]))
        summary.append(f"Frames: {len(slow)} of {len(judged)} after the warm-up took longer than "
                       f"the {_ms(budget):.3f} ms budget; the longest was frame {longest[0]}, "
                       f"{_ms(longest[3]):.3f} ms.")
    elif judged:
        summary.append(f"Frames: none of the {len(judged)} after the warm-up took longer than the "
                       f"{_ms(budget):.3f} ms budget.")
    elif "frames" not in said:
        summary.append(f"{no_frame[0].upper()}{no_frame[1:]}.")

    result = {
        "windows": [{"start_s": w.start / SECOND, "fps": w.frames,
                     "mean_ms": round(_window_mean(w), 3) if w.frames else None,
                     "pass": _window_passes(w, limit)} for w in full],
        "windows_skipped": skipped,
        "slow_frames": [{"frame": frame, "segment": ledger.frame_segment(rows), "wall_ms": _ms(wall),
                         "top_pass": _top_pass(rows)} for frame, rows, _, wall in slow],
        "frames_over_budget": len(slow),
        "allowed": allowed,
        "rows_dropped": dropped,
        "finished": run.close is not None,
    }
    return {"verdict": verdict, "summary": summary,
            "warnings": [{"code": n.code, "message": n.message} for n in notices], "result": result}


def frame_time_us(fps: Decimal) -> int:
    """1000/N ms in whole microseconds, rounded up: 16_667 at 60, 6_945 at
    144, 16_684 at 59.94. The window check's limit and the default budget
    (§ 4.7). Up, because a display locked to N records walls either side
    of 1000/N; rounded to the nearest, 144 Hz's 6.944 would fail them."""
    return int((SECOND / fps).to_integral_value(ROUND_CEILING))


class Window(NamedTuple):
    """One full one-second window, as `_windows` builds it."""
    start: int  # microseconds into the run
    frames: int  # frames ending in it
    wall_us: int  # their frame/walls' sum


def _window_passes(window: Window, limit_us: int) -> bool:
    """A window holds the rate when the mean frame/wall of the frames
    ending in it is at most `limit_us`, from frame_time_us (§ 4.7). Not a
    count of them: a steady 16.667 ms run holds 60 FPS, though some
    windows end only 59 frames. A window no frame ends in fails."""
    return window.frames > 0 and window.wall_us <= window.frames * limit_us


def _window_mean(window: Window) -> float:
    """The mean frame/wall of the frames ending in a window, in ms;
    infinite when none does, so it sorts as the slowest."""
    return _ms(window.wall_us) / window.frames if window.frames else math.inf


def _timeline(run: ledger.Run) -> tuple[list[tuple], list[tuple[int, int]], str | None, int]:
    """Each frame with a wall, as (frame, rows, end, wall) in frame order,
    its end summed from the first frame in integer microseconds; the
    (start, end) of every frame carrying event/cut; what stops the timeline early, a
    missing frame number or a frame other than the last with no wall, or
    None; and the time it stops. Past a stop the ends are too early by the
    missing time: they still place a frame after the warm-up, never
    before."""
    order = sorted(run.frames)
    timed, cuts, now, stop, stopped_at = [], [], 0, None, None
    for previous, frame in zip([None, *order[:-1]], order, strict=True):
        rows = run.frames[frame]
        if stop is None and previous is not None and frame != previous + 1:
            stop, stopped_at = f"frame {previous + 1} is missing", now
        wall = rows.get(("frame", "wall"))
        if wall is None:
            if stop is None and frame != order[-1]:
                stop, stopped_at = f"frame {frame} has no frame/wall row", now
            continue
        if ("event", "cut") in rows:
            cuts.append((now, now + wall.thousandths))
        now += wall.thousandths
        timed.append((frame, rows, now, wall.thousandths))
    return timed, cuts, stop, now if stopped_at is None else stopped_at


def _windows(ends: list[int], walls: list[int], cuts: list[tuple[int, int]], warmup_us: int,
             end: int) -> tuple[list[Window], int]:
    """The full one-second windows, and how many shorter ones were
    skipped. Windows are half-open, so a frame ending on a window's end
    belongs to the next (INV-8). The first starts when the warm-up ends,
    a new one after each full second and at the end of every cut frame
    (INV-18). A cut frame, often a level load, closes the window open when
    it starts, so no window overlaps it, and it is judged by the budget
    alone."""
    cuts = sorted(c for c in cuts if c[1] >= warmup_us)
    cut_ends = {cut_end for _, cut_end in cuts}
    full, skipped, start, i = [], 0, warmup_us, 0
    while start <= end:  # the frame ending at `end` opens a last, short window
        while i < len(cuts) and cuts[i][1] <= start:
            i += 1
        stop = start + SECOND
        if i < len(cuts) and cuts[i][0] < stop:
            if cuts[i][0] > start:  # some of the window comes before the cut frame
                skipped += 1
            start = cuts[i][1]
        elif stop > end:
            skipped += 1
            break
        else:
            # A frame ending exactly at a window opened by a cut is the cut
            # frame itself, so that window takes the frames after it.
            first = (bisect_right if start in cut_ends else bisect_left)(ends, start)
            last = bisect_left(ends, stop)
            full.append(Window(start, last - first, sum(walls[first:last])))
            start = stop
    return full, skipped


class _Costs:
    """Every frame's rows sorted into per-pass and per-frame-measure lists,
    keyed by segment kind. A cpu or gpu row counts only in a frame that has
    that category's span (INV-5): a frame whose GPU result never arrived is
    left out, never counted as 0 ms."""

    def __init__(self, run: ledger.Run):
        self.pass_values: dict[tuple, list[int]] = defaultdict(list)  # (kind, category, name, depth)
        self.span_totals: dict[tuple, int] = defaultdict(int)  # (kind, category)
        self.frame_values: dict[tuple, list[int]] = defaultdict(list)  # (kind, name)
        self.missing_gpu = 0
        for rows in run.frames.values():
            kind = _kind(ledger.frame_segment(rows))
            self.missing_gpu += ("frame", "gpu_span") not in rows
            for (category, name), row in rows.items():
                if category == "frame":
                    self.frame_values[(kind, name)].append(row.thousandths)
                elif category in SPAN and ("frame", SPAN[category]) in rows:
                    self.pass_values[(kind, category, name, row.depth)].append(row.thousandths)
            for category, span_name in SPAN.items():
                span = rows.get(("frame", span_name))
                if span is None:
                    continue
                self.span_totals[(kind, category)] += span.thousandths
                self.pass_values[(kind, category, REMAINDER[category], 0)].append(
                    span.thousandths - _top_level_sum(rows, category))

    def passes(self) -> list[dict]:
        """Ranked by the time the run spent on each pass, so a pass in every
        frame outranks a dearer one that ran once (Vestige's review)."""
        entries = []
        for (kind, category, name, depth), values in self.pass_values.items():
            span_total = self.span_totals[(kind, category)]
            entries.append({
                "category": category, "name": name, "segment_kind": kind, "depth": depth,
                "median_ms": _ms(stats.median(values)), "p99_ms": _ms(stats.percentile(values, 99)),
                "share": round(sum(values) / span_total, 4) if span_total > 0 else None,
                "frames": len(values),
            })
        entries.sort(key=lambda e: (_kind_key(e["segment_kind"]), e["category"], -self.total(e),
                                    -e["median_ms"], e["name"], e["depth"]))
        return entries

    def total(self, entry: dict) -> int:
        """A pass entry's total time over the run, in thousandths."""
        key = (entry["segment_kind"], entry["category"], entry["name"], entry["depth"])
        return sum(self.pass_values[key])

    def frame_times(self) -> list[dict]:
        entries = [{"name": name, "segment_kind": kind, "median_ms": _ms(stats.median(values)),
                    "p99_ms": _ms(stats.percentile(values, 99)), "frames": len(values)}
                   for (kind, name), values in self.frame_values.items()]
        order = {name: i for i, name in enumerate(FRAME_ORDER)}
        entries.sort(key=lambda e: (_kind_key(e["segment_kind"]),
                                    order.get(e["name"], len(order)), e["name"]))
        return entries


def _bound_by(run: ledger.Run) -> dict:
    """Over frames with both spans: GPU-bound when gpu_span > cpu_span,
    otherwise CPU-bound. Without pipelining the two never overlap, so a
    share would mislead (INV-10)."""
    if not run.header.get("pipelined"):
        return {"cpu": None, "gpu": None, "applies": False}
    both = [(rows[("frame", "cpu_span")].thousandths, rows[("frame", "gpu_span")].thousandths)
            for rows in run.frames.values()
            if ("frame", "cpu_span") in rows and ("frame", "gpu_span") in rows]
    if not both:
        return {"cpu": None, "gpu": None, "applies": True}
    gpu = sum(g > c for c, g in both)
    return {"cpu": round((len(both) - gpu) / len(both), 4), "gpu": round(gpu / len(both), 4),
            "applies": True}


def _worst_frames(run: ledger.Run) -> list[dict]:
    timed = [(rows[("frame", "wall")].thousandths, frame, rows)
             for frame, rows in run.frames.items() if ("frame", "wall") in rows]
    timed.sort(key=lambda t: (-t[0], t[1]))
    return [{"frame": frame, "segment": ledger.frame_segment(rows), "wall_ms": _ms(wall), "top_pass": _top_pass(rows)}
            for wall, frame, rows in timed[:WORST_FRAMES]]


def _top_pass(rows: dict) -> str | None:
    """The frame's largest depth-0 cpu or gpu cost, remainders included, so
    a frame lost to unattributed time does not blame a named pass."""
    costs = [(row.thousandths, f"{category}/{name}") for (category, name), row in rows.items()
             if category in SPAN and row.depth == 0]
    for category, span_name in SPAN.items():
        if ("frame", span_name) in rows:
            remainder = rows[("frame", span_name)].thousandths - _top_level_sum(rows, category)
            costs.append((remainder, f"{category}/{REMAINDER[category]}"))
    if not costs:
        return None
    return min(costs, key=lambda c: (-c[0], c[1]))[1]


def _warning_sentences(notices: list[ledger.Notice]) -> list[str]:
    """One sentence per kind of warning, as `check` gives, without the path
    or line; dropped rows and an unfinished run first."""
    by_code: dict[str, list[ledger.Notice]] = {}
    for notice in sorted(notices, key=lambda n: n.code not in FIRST_WARNINGS):
        by_code.setdefault(notice.code, []).append(notice)
    sentences = []
    for group in by_code.values():
        more = f" ({len(group) - 1} more like it)" if len(group) > 1 else ""
        sentences.append(f"Warning: {group[0].message}{more}.")
    return sentences


def _headline(run: ledger.Run, result: dict, costs: _Costs) -> list[str]:
    kinds = sorted({_kind(ledger.frame_segment(rows)) for rows in run.frames.values()}, key=_kind_key)
    sentences = [f"The run has {_count(len(run.frames), 'frame')}, in "
                 f"{', '.join(_kind_name(k) for k in kinds) or 'no'} segments."]
    for kind in kinds:
        top = [e for e in result["passes"] if e["segment_kind"] == kind and e["depth"] == 0]
        if not top:
            continue
        # The ranking is per category; across CPU and GPU, total time decides.
        best = min(top, key=lambda e: (-costs.total(e), -e["median_ms"], e["category"], e["name"]))
        share = "" if best["share"] is None else \
            f", {best['share'] * 100:.1f}% of {best['category'].upper()} time"
        sentences.append(f"In {_kind_name(kind)} segments the costliest pass is "
                         f"{best['category']}/{best['name']}: median {best['median_ms']:.3f} ms{share}.")
    bound = result["bound_by"]
    if not bound["applies"]:
        sentences.append("The run does not overlap CPU and GPU work (pipelined is false), so the "
                         "CPU-bound and GPU-bound share does not apply.")
    elif bound["gpu"] is None:
        sentences.append("No frame has both a CPU and a GPU span, so no CPU-bound or GPU-bound "
                         "share can be given.")
    else:
        sentences.append(f"{bound['gpu'] * 100:.1f}% of frames were GPU-bound and "
                         f"{bound['cpu'] * 100:.1f}% CPU-bound.")
    return sentences


def _top_level_sum(rows: dict, category: str) -> int:
    return sum(row.thousandths for (cat, _), row in rows.items() if cat == category and row.depth == 0)


def _kind(segment: str) -> str | None:
    return segment.partition(":")[0] or None


def _kind_key(kind: str | None) -> tuple:
    return (kind is not None, kind or "")


def _kind_name(kind: str | None) -> str:
    return kind or "unsegmented"


def _ms(thousandths: int) -> float:
    return thousandths / 1000


def _count(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


def _num(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _frames(n: int) -> str:
    return "1 frame has" if n == 1 else f"{n} frames have"
