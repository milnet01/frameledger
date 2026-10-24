"""One run: cost ranking, bound-by share and worst frames (S2, S3, S13),
and the floor check (S8).

Builds the `report` and `floor` commands' opening sentences, warnings and
results, in the shape of docs/specs/FLED-0001-run-file-format.md § 4.7
and § 4.8. Nothing here names the file or a line number: INV-3 and INV-4
need the same rows to give byte-identical JSON whatever the path, line
endings or row order. So warnings name the frame instead.
"""

from __future__ import annotations

from bisect import bisect_left
from collections import defaultdict
from decimal import Decimal

import ledger
import stats

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
    warnings = [{"code": n.code, "message": n.message} for n in run.notices]
    summary = _warning_sentences(run.notices)
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
NO_WINDOW = ("The floor check is inconclusive: no full one-second window follows the warm-up, "
             "so the window check could not run.")


def floor(run: ledger.Run, fps: Decimal, warmup_us: int, budget: int, windows: bool = True,
          frames: bool = True, allowed: int = 0) -> dict:
    """{"verdict", "summary", "warnings", "result"} for S8's two checks.
    `budget` is in thousandths of a millisecond. Dropped rows, an
    unfinished run or a gap in the timeline make the check inconclusive
    whatever the frames show (INV-7): a missing frame moves every later
    frame into the wrong window."""
    _refuse_breaches(run)
    timed, cuts, gap = _timeline(run)
    end = timed[-1][2] if timed else 0
    judged = [t for t in timed if t[2] >= warmup_us]
    full, skipped = _windows([t[2] for t in timed], cuts, warmup_us, end) if windows else ([], 0)
    slow = [t for t in judged if t[3] > budget] if frames else []
    dropped = run.close["rows_dropped"] if run.close else None

    doubts = []
    if dropped:
        doubts.append(f"The check is inconclusive: the writer dropped {_count(dropped, 'row')}, "
                      "so frames may be missing from the timeline.")
    if run.close is None:
        doubts.append("The check is inconclusive: the file has no close line, so the run did not finish.")
    if gap is not None:
        doubts.append(f"The check is inconclusive: frame {gap} has no frame/wall row, so the "
                      "timeline stops there.")
    failed_windows = [w for w in full if w[1] < fps]
    failures = []
    if failed_windows:
        failures.append(f"{_count(len(failed_windows), 'one-second window')} fell below {_num(fps)} FPS")
    if len(slow) > allowed:
        failures.append(f"{_count(len(slow), 'frame')} took longer than {_ms(budget):.3f} ms "
                        f"({allowed} allowed)")
    if doubts:
        verdict = "inconclusive"
        if failures:
            doubts.append(f"Judged on the rows present, it would fail: {' and '.join(failures)}.")
    elif failures:
        verdict = "fail"
        doubts.append(f"The run fails the {_num(fps)} FPS floor: {' and '.join(failures)}.")
    elif windows and not full:
        verdict = "inconclusive"
        doubts.append(NO_WINDOW)
    else:
        verdict = "pass"
        doubts.append(f"The run passes the {_num(fps)} FPS floor.")

    shown = [n for n in run.notices if n.code not in ("rows_dropped", "unfinished", "wall_missing")]
    summary = _warning_sentences(shown) + doubts
    warmup = f"{warmup_us / SECOND:g} s warm-up"
    if not windows:
        summary.append("The window check is off (--no-windows).")
    elif full:
        slowest = min(full, key=lambda w: (w[1], w[0]))
        summary.append(f"Windows: {len(full) - len(failed_windows)} of {len(full)} one-second windows "
                       f"after the {warmup} reached {_num(fps)} FPS; the slowest, at "
                       f"{slowest[0] / SECOND:.3f} s, had {slowest[1]} frames.")
    elif verdict != "inconclusive" or doubts[-1] != NO_WINDOW:  # not said already
        summary.append(f"No full one-second window follows the {warmup}.")
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
    else:
        summary.append(f"Frames: none of the {len(judged)} after the warm-up took longer than the "
                       f"{_ms(budget):.3f} ms budget.")

    result = {
        "windows": [{"start_s": start / SECOND, "fps": count, "pass": count >= fps} for start, count in full],
        "windows_skipped": skipped,
        "slow_frames": [{"frame": frame, "segment": _segment(rows), "wall_ms": _ms(wall),
                         "top_pass": _top_pass(rows)} for frame, rows, _, wall in slow],
        "frames_over_budget": len(slow),
        "allowed": allowed,
        "rows_dropped": dropped,
        "finished": run.close is not None,
    }
    return {"verdict": verdict, "summary": summary,
            "warnings": [{"code": n.code, "message": n.message} for n in run.notices], "result": result}


def _timeline(run: ledger.Run) -> tuple[list[tuple], list[int], int | None]:
    """Each frame with a known end, as (frame, rows, end, wall) in frame
    order, summed from the first frame in integer microseconds; the start
    of every frame carrying event/cut; and the frame where the timeline
    stops early, a frame other than the last with no wall, or None."""
    order = sorted(run.frames)
    timed, cuts, now = [], [], 0
    for frame in order:
        rows = run.frames[frame]
        if ("event", "cut") in rows:
            cuts.append(now)
        wall = rows.get(("frame", "wall"))
        if wall is None:
            return timed, cuts, None if frame == order[-1] else frame
        now += wall.thousandths
        timed.append((frame, rows, now, wall.thousandths))
    return timed, cuts, None


def _windows(ends: list[int], cuts: list[int], warmup_us: int, end: int) -> tuple[list[tuple], int]:
    """The full one-second windows as (start, frames ending in it), and how
    many shorter ones were skipped. Windows are half-open, so a frame
    ending on a window's end belongs to the next (INV-8). The first starts
    when the warm-up ends, a new one after each full second and at every
    cut (INV-18)."""
    cuts = sorted(c for c in set(cuts) if c > warmup_us)
    full, skipped, start, i = [], 0, warmup_us, 0
    while start < end:
        while i < len(cuts) and cuts[i] <= start:
            i += 1
        stop = start + SECOND
        if i < len(cuts) and cuts[i] < stop:
            skipped, start = skipped + 1, cuts[i]
        elif stop > end:
            skipped += 1
            break
        else:
            full.append((start, bisect_left(ends, stop) - bisect_left(ends, start)))
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
            kind = _kind(_segment(rows))
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
    return [{"frame": frame, "segment": _segment(rows), "wall_ms": _ms(wall), "top_pass": _top_pass(rows)}
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
    kinds = sorted({_kind(_segment(rows)) for rows in run.frames.values()}, key=_kind_key)
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


def _segment(rows: dict) -> str:
    """A frame's segment: its cpu_span row's, or else its first row's."""
    row = rows.get(("frame", "cpu_span")) or min(rows.values(), key=lambda r: r.line)
    return row.segment


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
