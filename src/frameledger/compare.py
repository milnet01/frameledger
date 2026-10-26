"""Compare labelled sets of runs (S4, S5's refusal half, S16).

The rules are docs/specs/FLED-0001-run-file-format.md § 4.10. Each run
gives one value per measure; a measure is judged by its own spread and a
floor, so a pass that moved is found even when the frame total is too
noisy to judge. Runs are named by set and order (old-1, new-2), never by
path, in every sentence and warning.
"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction
from typing import NamedTuple

import ledger
import run_report
import stats
import trust

# § 4.2: two runs differing in any of these are not comparable without an override.
BLOCKING = ("resolution", "render_scale", "tier", "ray_tracing", "build_type", "inputs", "display",
            "api", "device", "vsync", "scene")
FEWEST_RUNS = 3  # a set of two gives too many false changes (§ 4.10's table)
# The frame measures judged, in § 4.8's frame_times order; the waits are not
# judged, since a wait moves when the work around it moves.
FRAME_MEASURES = (("cpu_span", "median"), ("gpu_span", "median"), ("wall", "median"), ("wall", "p99"))
CATEGORY_ORDER = {"frame": 0, "cpu": 1, "gpu": 2}
ABSENT = object()  # a run's header field that is absent: it matches only another absent one
# The opening sentences say these themselves, per run.
INCOMPLETE = ("rows_dropped", "unfinished")


class Named(NamedTuple):
    name: str  # old-1, new-2, ...
    set: str  # "old" or "new"
    path: str
    run: ledger.Run


class Measure(NamedTuple):
    kind: str | None
    category: str
    name: str
    depth: int
    statistic: str  # "median" or "p99"


def compare(old: list[ledger.Run], new: list[ledger.Run], overrides: dict[str, str],
            min_ms: Decimal, min_pct: Decimal) -> dict:
    """{"verdict", "summary", "warnings", "overrides", "result"} for two sets
    of runs that meet the format. cli.py checks the run counts and the
    override fields; a Run with a breach raises LedgerError, as under
    `report`."""
    runs = [Named(f"{label}-{i}", label, run.path, run)
            for label, group in (("old", old), ("new", new)) for i, run in enumerate(group, 1)]
    for named in runs:
        run_report.refuse_breaches(named.run)
    override_list = [{"field": f, "reason": r} for f, r in overrides.items()]
    summary = [_overrides_sentence(override_list)] if override_list else []
    refused, unused = _refusals(runs, overrides)
    notices = [ledger.Notice("override_unused", f"--override {field} was given, but every run has the "
                             "same value") for field in unused]
    run_list = [_run_entry(r) for r in runs]
    if refused:
        summary.append(_refusal_sentence(refused))
        return {"verdict": "error", "summary": summary, "warnings": _warnings(notices),
                "overrides": override_list, "result": {"runs": run_list, "refused": refused}}

    incomplete = _incomplete_sentences(runs)
    notices += _run_notices(runs) + _set_notices(runs)
    shown = [n for n in notices if n.code not in INCOMPLETE]
    summary += incomplete + run_report.warning_sentences(shown)

    measures, unmatched = _judge_all(runs, min_ms, min_pct)
    short = _short_kinds(runs)
    verdict, sentence = _verdict(incomplete, measures, short)
    summary.append(sentence)
    summary += _wall_sentences(measures)
    if short:
        kinds = ", ".join(run_report.kind_name(k) for k in short)
        summary.append(f"Some run has fewer than {trust.FEWEST_FRAMES} frames with a frame/wall in "
                       f"{kinds} segments, so a noisy frame time there cannot make the compare "
                       "inconclusive.")
    result = {
        "runs": run_list,
        "min_ms": float(min_ms),
        "min_pct": float(min_pct),
        "measures": measures,
        "unmatched": unmatched,
        "static_diff": _static_diff(runs),
        "refused": [],
    }
    return {"verdict": verdict, "summary": summary, "warnings": _warnings(notices),
            "overrides": override_list, "result": result}


def _run_entry(named: Named) -> dict:
    header, close = named.run.header, named.run.close
    return {"name": named.name, "set": named.set, "path": named.path, "run_id": header["run_id"],
            "commit": header["commit"], "dirty": header["dirty"], "started_utc": header["started_utc"],
            "rows_dropped": close["rows_dropped"] if close else None, "finished": close is not None}


def _overrides_sentence(overrides: list[dict]) -> str:
    """S5: every override and its reason, in the first sentence (DOOM Ants)."""
    listed = "; ".join(f"{o['field']} may differ (\"{o['reason']}\")" for o in overrides)
    return f"Overrides given: {listed}."


def _refusals(runs: list[Named], overrides: dict[str, str]) -> tuple[list[dict], list[str]]:
    """The compare-blocking fields that refuse the compare, each with every
    run's value; and the overridden fields that did not differ."""
    refused, unused = [], []
    for field in BLOCKING:
        keys = {_match_key(field, r.run.header.get(field, ABSENT)) for r in runs}
        # Two empty input lists are unknown, not equal (§ 4.2).
        blocked = len(keys) > 1 or (field == "inputs" and None in keys)
        if field in overrides:
            if not blocked:
                unused.append(field)
        elif blocked:
            refused.append({"field": field, "values": {
                r.name: r.run.header.get(field) for r in runs}})
    return refused, unused


def _match_key(field: str, value) -> str | None:
    """What two runs must share in `field`. `inputs` match on their name and
    hash pairs in any order; an empty list gives None, which matches
    nothing."""
    if value is ABSENT:
        return "absent"
    if field == "inputs":
        if not value:
            return None
        value = sorted([i["name"], i["hash"]] for i in value)
    return json.dumps(value, sort_keys=True)


def _refusal_sentence(refused: list[dict]) -> str:
    parts = []
    for entry in refused:
        by_value: dict[str, list[str]] = {}
        for name, value in entry["values"].items():
            by_value.setdefault("absent" if value is None else json.dumps(value), []).append(name)
        if entry["field"] == "inputs" and "[]" in by_value:
            what = f"inputs is empty in {', '.join(by_value['[]'])}, so the inputs are unknown"
        else:
            what = f"{entry['field']} differs: " + "; ".join(
                f"{value} in {', '.join(names)}" for value, names in by_value.items())
        parts.append(f"{what} (--override {entry['field']}=REASON compares anyway)")
    return f"The runs cannot be compared: {'; '.join(parts)}."


def _incomplete_sentences(runs: list[Named]) -> list[str]:
    """A run with dropped rows or no close line cannot pass or fail a compare
    (docs/design.md, the writer)."""
    sentences = []
    for r in runs:
        if r.run.close is None:
            sentences.append(f"{r.name} has no close line, so the run did not finish and the "
                             "compare cannot pass or fail.")
        elif r.run.close["rows_dropped"]:
            sentences.append(f"In {r.name} the writer dropped "
                             f"{run_report.counted(r.run.close['rows_dropped'], 'row')}, so the compare "
                             "cannot pass or fail.")
    return sentences


def _run_notices(runs: list[Named]) -> list[ledger.Notice]:
    """Each run's own notices and § 4.9 warnings, opening with its name."""
    found = []
    for r in runs:
        measured = sum(("frame", "wall") in rows for rows in r.run.frames.values())
        for notice in r.run.notices + trust.warnings(r.run, measured):
            found.append(ledger.Notice(notice.code, f"{r.name}: {notice.message}"))
    return found


def _set_notices(runs: list[Named]) -> list[ledger.Notice]:
    found = []
    starts = {label: [_started(r.run.header["started_utc"]) for r in runs if r.set == label]
              for label in ("old", "new")}
    if max(starts["old"]) < min(starts["new"]) or max(starts["new"]) < min(starts["old"]):
        found.append(ledger.Notice("not_interleaved", "every run of one set started before every run "
                                   "of the other, so a drift over time reads as a change"))
    for label in ("old", "new"):
        builds = {(r.run.header["commit"], r.run.header["dirty"]) for r in runs if r.set == label}
        if len(builds) > 1:
            found.append(ledger.Notice("mixed_build", f"the {label} runs differ in commit or dirty, so "
                                       "they may not be one build"))
    return found


def _started(utc: str) -> tuple[datetime, Fraction]:
    """started_utc as a sortable value; ledger.py has checked its shape. Any
    number of fraction digits, which Python 3.10's fromisoformat refuses."""
    whole, _, fraction = utc.rstrip("Z").partition(".")
    return datetime.strptime(whole, "%Y-%m-%dT%H:%M:%S"), Fraction(f"0.{fraction or 0}")


def _values(run: ledger.Run) -> dict[Measure, int]:
    """One value per measure for one run, in thousandths: the medians and
    the wall's 99th percentile, as `report` gives them."""
    costs = run_report.Costs(run)
    values = {}
    for (kind, name), times in costs.frame_values.items():
        for wanted, statistic in FRAME_MEASURES:
            if name == wanted:
                values[Measure(kind, "frame", name, 0, statistic)] = (
                    stats.median(times) if statistic == "median" else stats.percentile(times, 99))
    for (kind, category, name, depth), times in costs.pass_values.items():
        values[Measure(kind, category, name, depth, "median")] = stats.median(times)
    return values


def _judge_all(runs: list[Named], min_ms: Decimal, min_pct: Decimal) -> tuple[list[dict], list[dict]]:
    """Every measure all runs share, judged; and those only some runs have."""
    per_run = [_values(r.run) for r in runs]
    tick = _largest_tick(runs)
    measures, unmatched = [], []
    for measure in sorted(set().union(*per_run), key=_unranked_order):
        present = [r.name for r, values in zip(runs, per_run, strict=True) if measure in values]
        if len(present) < len(runs):
            unmatched.append({**_measure_fields(measure), "present_in": present})
            continue
        old = [values[measure] for r, values in zip(runs, per_run, strict=True) if r.set == "old"]
        new = [values[measure] for r, values in zip(runs, per_run, strict=True) if r.set == "new"]
        measures.append(_judge(measure, old, new, min_ms, min_pct, tick))
    measures.sort(key=lambda m: (run_report.kind_order(m["segment_kind"]),
                                 CATEGORY_ORDER[m["category"]], _frame_rank(m), -m["old_centre_ms"],
                                 m["name"], m["depth"], m["statistic"]))
    return measures, unmatched


def _judge(measure: Measure, old: list[int], new: list[int], min_ms: Decimal, min_pct: Decimal,
           tick: Fraction) -> dict:
    """§ 4.10's table, in exact fractions of a thousandth."""
    old_centre, new_centre = _centre(old), _centre(new)
    spread = max(max(old) - min(old), max(new) - min(new))
    change = new_centre - old_centre
    floor = max(Fraction(min_ms) * 1000, Fraction(min_pct) / 100 * old_centre)
    if measure.category == "gpu" or (measure.category, measure.name) == ("frame", "gpu_span"):
        floor = max(floor, tick)
    if change > spread and change >= floor:
        verdict = "slower"
    elif -change > spread and -change >= floor:
        verdict = "faster"
    elif spread >= floor:
        verdict = "noisy"
    else:
        verdict = "unchanged"
    return {
        **_measure_fields(measure),
        "old_ms": [v / 1000 for v in old],
        "new_ms": [v / 1000 for v in new],
        "old_centre_ms": _ms4(old_centre),
        "new_centre_ms": _ms4(new_centre),
        "change_ms": _ms4(change),
        "change_pct": None if old_centre == 0 else _round(change / old_centre * 100, "0.01"),
        "spread_ms": _ms4(spread),
        "floor_ms": _ms4(floor),
        "verdict": verdict,
    }


def _centre(values: list[int]) -> Fraction:
    """The median: the middle value, or the mean of the two middle ones.
    Not stats.median's nearest rank, which for two values is the lower."""
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return Fraction(ordered[middle])
    return Fraction(ordered[middle - 1] + ordered[middle], 2)


def _largest_tick(runs: list[Named]) -> Fraction:
    """The largest gpu_tick_ns among the runs, in thousandths of a ms (ns
    / 1000); 0 when no run states one."""
    ticks = [Fraction(str(r.run.header["gpu_tick_ns"])) / 1000 for r in runs
             if "gpu_tick_ns" in r.run.header]
    return max(ticks, default=Fraction(0))


def _measure_fields(measure: Measure) -> dict:
    return {"segment_kind": measure.kind, "category": measure.category, "name": measure.name,
            "depth": measure.depth, "statistic": measure.statistic}


def _unranked_order(measure: Measure) -> tuple:
    return (run_report.kind_order(measure.kind), CATEGORY_ORDER[measure.category], measure.name,
            measure.depth, measure.statistic)


def _frame_rank(entry: dict) -> int:
    """Frame measures keep FRAME_MEASURES' order; passes rank by old centre."""
    key = (entry["name"], entry["statistic"])
    return FRAME_MEASURES.index(key) if entry["category"] == "frame" else 0


def _short_kinds(runs: list[Named]) -> list[str | None]:
    """Segment kinds where some run has fewer than trust.FEWEST_FRAMES frames
    with a wall: their frame time is noisy almost every time (Vestige)."""
    counts: dict[str | None, list[int]] = {}
    for r in runs:
        per_kind: dict[str | None, int] = {}
        for rows in r.run.frames.values():
            if ("frame", "wall") in rows:
                kind = run_report.segment_kind(ledger.frame_segment(rows))
                per_kind[kind] = per_kind.get(kind, 0) + 1
        for kind in per_kind.keys() | counts.keys():
            counts.setdefault(kind, []).append(per_kind.get(kind, 0))
    return sorted((k for k, c in counts.items() if min(c) < trust.FEWEST_FRAMES),
                  key=run_report.kind_order)


def _verdict(incomplete: list[str], measures: list[dict], short: list) -> tuple[str, str]:
    """§ 4.10's verdict, first match wins, and the sentence saying it."""
    slower = [m for m in measures if m["verdict"] == "slower"]
    faster = [m for m in measures if m["verdict"] == "faster"]
    noisy_walls = [m for m in measures if (m["category"], m["name"], m["statistic"]) ==
                   ("frame", "wall", "median") and m["verdict"] == "noisy"
                   and m["segment_kind"] not in short]
    if incomplete:
        return "inconclusive", ("The compare is inconclusive: a run is incomplete, so a change could "
                                "be a missing frame.")
    if slower:
        worst = max(slower, key=lambda m: (m["change_ms"], m["change_pct"] or 0))
        return "fail", (f"The new runs are slower: {run_report.counted(len(slower), 'measure')} got "
                        f"slower; the largest is {_label(worst)}, up {worst['change_ms']:.3f} ms"
                        f"{_pct(worst)}, beyond the runs' spread of {worst['spread_ms']:.3f} ms.")
    if noisy_walls:
        wall = noisy_walls[0]
        return "inconclusive", (f"The compare is inconclusive: {_label(wall)} moved "
                                f"{wall['change_ms']:+.3f} ms, within the runs' spread of "
                                f"{wall['spread_ms']:.3f} ms; re-run with more runs a set.")
    sentence = "No measure got slower between the old and new runs"
    if faster:
        sentence += f"; {run_report.counted(len(faster), 'measure')} got faster"
    return "pass", sentence + "."


def _wall_sentences(measures: list[dict]) -> list[str]:
    return [f"In {run_report.kind_name(m['segment_kind'])} segments the median frame/wall went from "
            f"{m['old_centre_ms']:.3f} ms to {m['new_centre_ms']:.3f} ms ({m['verdict']})."
            for m in measures if (m["category"], m["name"], m["statistic"]) == ("frame", "wall", "median")]


def _label(measure: dict) -> str:
    statistic = " p99" if measure["statistic"] == "p99" else " median"
    return (f"{measure['category']}/{measure['name']}{statistic} in "
            f"{run_report.kind_name(measure['segment_kind'])} segments")


def _pct(measure: dict) -> str:
    return "" if measure["change_pct"] is None else f" ({measure['change_pct']:+.1f}%)"


def _static_diff(runs: list[Named]) -> list[dict]:
    """Each dotted key of the static lines whose value is not the same in
    every run, with every run's value as written; absent is None."""
    flat = [_flatten(r.run.static or {}) for r in runs]
    keys = list(dict.fromkeys(key for facts in flat for key in facts))
    diff = []
    for key in keys:
        values = {r.name: facts.get(key) for r, facts in zip(runs, flat, strict=True)}
        if len({json.dumps(v, sort_keys=True) for v in values.values()}) > 1:
            diff.append({"key": key, "values": values})
    return diff


def _flatten(value: dict, prefix: str = "") -> dict:
    """Objects become dotted keys; anything else, an array included, is one
    value."""
    facts = {}
    for key, item in value.items():
        dotted = f"{prefix}.{key}" if prefix else key
        if isinstance(item, dict):
            facts.update(_flatten(item, dotted))
        else:
            facts[dotted] = item
    return facts


def _warnings(notices: list[ledger.Notice]) -> list[dict]:
    return [{"code": n.code, "message": n.message} for n in notices]


def _ms4(thousandths: Fraction | int) -> float:
    """Milliseconds to four places, half away from zero (§ 4.10)."""
    return _round(Fraction(thousandths) / 1000, "0.0001")


def _round(value: Fraction, places: str) -> float:
    exact = Decimal(value.numerator) / Decimal(value.denominator)
    return float(exact.quantize(Decimal(places), rounding=ROUND_HALF_UP))
