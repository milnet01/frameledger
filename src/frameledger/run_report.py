"""One run: cost ranking, bound-by share and worst frames (S2, S3, S13).

Builds the `report` command's opening sentences, warnings and result,
in the shape of docs/specs/FLED-0001-run-file-format.md § 4.8. Nothing
here names the file or a line number: INV-3 and INV-4 need the same rows
to give byte-identical JSON whatever the path, line endings or row order.
So warnings name the frame instead.
"""

from __future__ import annotations

from collections import defaultdict

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
    if run.breaches:
        first = run.breaches[0]
        raise ledger.LedgerError(f"{first.message}; the file breaks the run-file format, so it "
                                 "cannot be reported on (`check` lists every breach)", run.path, first.line)
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


def _frames(n: int) -> str:
    return "1 frame has" if n == 1 else f"{n} frames have"
