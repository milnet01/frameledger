"""Many runs ranked by their slowest frames, and those floor would fail
flagged (S9, S19).

Builds the `survey` command's sentences and result, in the shape of
docs/specs/FLED-0001-run-file-format.md § 4.13. The flag is
run_report.frame_check, floor's own single-frame check, so survey and
floor cannot disagree on one file (INV-69). The rank is a separate
question: a run can rank first and pass, or be flagged by one frame.
"""

from __future__ import annotations

from collections import defaultdict

import ledger
import run_report
import stats

FEWEST_FRAMES = 100  # a kind ranks from this many judged frames, as compare's fewest (§ 4.10)
VERDICTS = {"fail": "flagged", "pass": "clean", "inconclusive": "inconclusive"}


def survey(paths: list[str], budget_us: int, warmup_us: int, allowed: int) -> dict:
    """{"verdict", "summary", "warnings", "result"} for the runs at
    `paths`, each read and judged on its own: a file that cannot be
    judged is listed, and the others go on."""
    entries = [_entry(path, budget_us, warmup_us, allowed) for path in paths]
    # Slowest first; ties by median, then the order given.
    ranked = [e for _key, e in sorted(((-e["p99_ms"], -e["median_ms"], i), e)
                                      for i, e in enumerate(entries) if e["p99_ms"] is not None)]
    for rank, entry in enumerate(ranked, 1):
        entry["rank"] = rank
    runs = ranked + [e for e in entries if e["p99_ms"] is None]

    warmup = f"{warmup_us / run_report.SECOND:g} s warm-up"
    summary = [_flag_sentence(e, warmup, budget_us, allowed) for e in runs if e["verdict"] == "flagged"]
    summary += [_unjudged_sentence(e, warmup) for e in runs if e["verdict"] in ("inconclusive", "unjudged")]
    warnings = [w for e in runs for w in e["warnings"]]
    summary += [f"Warning: {w['message']}." for w in warnings]
    flagged = sum(e["verdict"] == "flagged" for e in runs)
    unsure = sum(e["verdict"] in ("inconclusive", "unjudged") for e in runs)
    if flagged:
        verdict = "fail"
        summary.append(f"The survey fails: {flagged} of {run_report.counted(len(runs), 'run')} "
                       f"{'is' if flagged == 1 else 'are'} flagged by floor's single-frame check.")
    elif unsure:
        verdict = "inconclusive"
        summary.append(f"The survey is inconclusive: no run is flagged, but {unsure} of "
                       f"{run_report.counted(len(runs), 'run')} could not be fully judged.")
    else:
        verdict = "pass"
        summary.append(f"The survey passes: none of the {run_report.counted(len(runs), 'run')} is "
                       "flagged by floor's single-frame check; its per-second check was not run.")
    result = {"runs": runs, "budget_ms": budget_us / 1000, "warmup_s": warmup_us / run_report.SECOND,
              "allowed": allowed}
    return {"verdict": verdict, "summary": summary, "warnings": warnings, "result": result}


def _entry(path: str, budget_us: int, warmup_us: int, allowed: int) -> dict:
    """One run's line of the result."""
    entry = {"path": path, "run_id": None, "verdict": "unjudged", "reason": None, "rank": None,
             "worst_kind": None, "worst_segment": None, "median_ms": None, "p99_ms": None,
             "frames_over_budget": None, "slowest_over": None, "kinds": [], "warnings": []}
    try:
        run = ledger.read(path)
        check = run_report.frame_check(run, warmup_us, budget_us, allowed)
    except ledger.LedgerError as error:
        entry["reason"] = error.reason if error.line is None else f"{error.reason} (line {error.line})"
        return entry
    entry["run_id"] = run.header.get("run_id")
    entry["verdict"] = VERDICTS[check.state]
    if check.state == "inconclusive":
        entry["reason"] = " ".join(check.reasons) or None
    entry["frames_over_budget"] = len(check.slow)
    if check.slow:
        entry["slowest_over"] = run_report.slow_frame(min(check.slow, key=lambda t: (-t[3], t[0])))
    entry["kinds"], worst = _kinds(check.judged)
    if worst:
        entry.update(worst)
    notices = run_report.judged_notices(run, check.judged)
    entry["warnings"] = [{"code": n.code, "message": f"{path}: {n.message}"}
                         for n in notices if n.code not in run_report.FLOOR_REASONS]
    return entry


def _kinds(judged: list[tuple]) -> tuple[list[dict], dict | None]:
    """Each segment kind's frame/wall figures over the judged frames, and
    the worst kind of FEWEST_FRAMES or more with its worst segment (UT
    Ants), or None when no kind has that many."""
    by_kind: dict[str | None, list[int]] = defaultdict(list)
    by_segment: dict[str, list[int]] = defaultdict(list)
    for _frame, rows, _end, wall in judged:
        segment = ledger.frame_segment(rows)
        by_kind[run_report.segment_kind(segment)].append(wall)
        by_segment[segment].append(wall)
    kinds = []
    for kind in sorted(by_kind, key=run_report.kind_order):
        median, p99 = stats.percentiles(by_kind[kind], 50, 99)
        kinds.append({"segment_kind": kind, "median_ms": median / 1000, "p99_ms": p99 / 1000,
                      "frames": len(by_kind[kind]), "ranked": len(by_kind[kind]) >= FEWEST_FRAMES})
    eligible = [k for k in kinds if k["ranked"]]
    if not eligible:
        return kinds, None
    worst = min(eligible, key=lambda k: (-k["p99_ms"], -k["median_ms"], run_report.kind_order(k["segment_kind"])))
    segments = []
    for segment, walls in by_segment.items():
        if run_report.segment_kind(segment) == worst["segment_kind"]:
            median, p99 = stats.percentiles(walls, 50, 99)
            segments.append((-p99, -median, segment))
    return kinds, {"worst_kind": worst["segment_kind"], "worst_segment": min(segments)[2] or None,
                   "median_ms": worst["median_ms"], "p99_ms": worst["p99_ms"]}


def _flag_sentence(entry: dict, warmup: str, budget_us: int, allowed: int) -> str:
    over = entry["frames_over_budget"]
    slowest = entry["slowest_over"]
    tolerated = f" ({allowed} allowed)" if allowed else ""
    return (f"{entry['path']} is flagged: {run_report.counted(over, 'frame')} after the {warmup} "
            f"{'is' if over == 1 else 'are'} over the {budget_us / 1000:.3f} ms budget{tolerated}, the "
            f"slowest frame {slowest['frame']} in {slowest['segment'] or 'no segment'} at "
            f"{slowest['wall_ms']:.3f} ms (top pass {slowest['top_pass'] or 'none'}); floor's "
            "per-second check was not run.")


def _unjudged_sentence(entry: dict, warmup: str) -> str:
    if entry["verdict"] == "unjudged":
        return f"{entry['path']} is unjudged: {entry['reason']}."
    reason = entry["reason"] or f"No frame ends after the {warmup}."
    return f"{entry['path']} is inconclusive: {reason}"
