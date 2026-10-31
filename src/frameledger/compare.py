"""Compare labelled sets of runs (S4, S5's refusal half, S16), and give
one commit's bisect verdict (S17).

The rules are docs/specs/FLED-0001-run-file-format.md § 4.10 and, for
the bisect, § 4.11. Each run gives one value per measure; a measure is
judged by its own spread and a floor, so a pass that moved is found even
when the frame total is too noisy to judge. Runs are named by set and
order (old-1, new-2, tested-1), never by path, in every sentence and
warning.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from decimal import Decimal
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
CATEGORY_ORDER = {"frame": 0, "cpu": 1, "gpu": 2, "mem": 3}
MEM_VERDICTS = {"slower": "larger", "faster": "smaller"}  # memory has no speed
ABSENT = object()  # a run's header field that is absent: it matches only another absent one
# Notice codes the opening sentences say themselves, per run.
INCOMPLETE_CODES = ("rows_dropped", "unfinished")


class Floors(NamedTuple):
    """The smallest change that counts: --min-ms, --min-mb and --min-pct."""
    min_ms: Decimal
    min_mb: Decimal
    min_pct: Decimal

    def minimum(self, category: str) -> Decimal:
        """The absolute floor, in the unit of a measure of `category`."""
        return self.min_mb if category == "mem" else self.min_ms


def unit_of(category: str) -> str:
    return "MB" if category == "mem" else "ms"


class Named(NamedTuple):
    name: str  # old-1, new-2, ...
    set: str  # "old" or "new"; bisecting.py adds "tested", "good" and "bad"
    path: str
    run: ledger.Run


class Measure(NamedTuple):
    kind: str | None
    category: str
    name: str
    depth: int
    statistic: str  # "median" or "p99"


def compare(old: list[ledger.Run], new: list[ledger.Run], overrides: dict[str, str], floors: Floors) -> dict:
    """{"verdict", "summary", "warnings", "overrides", "result"} for two sets
    of runs that meet the format. cli.py checks the run counts and the
    override fields; a Run with a breach raises LedgerError, as under
    `report`.

    The opening sentences follow § 4.10's order: the overrides; a refusal,
    which ends the compare; each incomplete run; one per kind of warning;
    the verdict; the short kinds; the frame time per segment kind."""
    runs = [Named(f"{label}-{i}", label, run.path, run)
            for label, group in (("old", old), ("new", new)) for i, run in enumerate(group, 1)]
    for named in runs:
        run_report.refuse_breaches(named.run)
    override_list = [{"field": f, "reason": r} for f, r in overrides.items()]
    summary = overrides_sentences(override_list)
    refused, unused = refusals(runs, overrides)
    notices = unused_override_notices(unused)
    run_list = [run_entry(r) for r in runs]
    if refused:
        summary += [refusal_sentence(refused), *run_report.warning_sentences(notices)]
        return {"verdict": "error", "summary": summary, "warnings": run_report.warning_entries(notices),
                "overrides": override_list, "result": {"runs": run_list, "refused": refused}}

    incomplete = _incomplete_sentences(runs)
    notices += run_notices(runs) + _set_notices(runs)
    shown = [n for n in notices if n.code not in INCOMPLETE_CODES]
    summary += incomplete + run_report.warning_sentences(shown)

    measures, unmatched = _judge_all(runs, floors)
    short = _short_kinds(runs)
    verdict, sentences = _verdict(incomplete, measures, short)
    summary += sentences
    if short:  # straight after the verdict, which it explains (Vestige)
        kinds = ", ".join(run_report.kind_name(k) for k in short)
        summary.append(f"Some run has fewer than {trust.FEWEST_FRAMES} frames with a frame/wall in "
                       f"{kinds} segments, so a noisy frame time there cannot make the compare "
                       "inconclusive.")
    summary += _wall_sentences(measures)
    result = {
        "runs": run_list,
        "min_ms": float(floors.min_ms),
        "min_mb": float(floors.min_mb),
        "min_pct": float(floors.min_pct),
        "measures": measures,
        "unmatched": unmatched,
        "static_diff": _static_diff(runs),
        "refused": [],
    }
    return {"verdict": verdict, "summary": summary, "warnings": run_report.warning_entries(notices),
            "overrides": override_list, "result": result}


def run_entry(named: Named) -> dict:
    header, close = named.run.header, named.run.close
    return {"name": named.name, "set": named.set, "path": named.path, "run_id": header["run_id"],
            "commit": header["commit"], "dirty": header["dirty"], "started_utc": header["started_utc"],
            "rows_dropped": close["rows_dropped"] if close else None, "finished": close is not None}


def overrides_sentences(overrides: list[dict]) -> list[str]:
    """S5: every override and its reason, in the first sentence, whatever
    else the compare says (DOOM Ants); none when there are none."""
    if not overrides:
        return []
    listed = "; ".join(f"{o['field']} may differ (\"{o['reason']}\")" for o in overrides)
    return [f"Overrides given: {listed}."]


def refusals(runs: list[Named], overrides: dict[str, str]) -> tuple[list[dict], list[str]]:
    """The compare-blocking fields that refuse the compare, each with every
    run's value; and the overridden fields that did not differ."""
    refused, unused = [], []
    for field in BLOCKING:
        keys = {match_key(field, r.run.header.get(field, ABSENT)) for r in runs}
        # Two empty input lists are unknown, not equal (§ 4.2).
        blocked = len(keys) > 1 or (field == "inputs" and None in keys)
        if field in overrides:
            if not blocked:
                unused.append(field)
        elif blocked:
            refused.append({"field": field, "values": {
                r.name: r.run.header.get(field) for r in runs}})
    return refused, unused


def match_key(field: str, value) -> str | None:
    """What two runs must share in `field`, as a string. `inputs` match on
    their name and hash pairs in any order, and numbers by value, so
    render_scale 1 matches 1.0 (Vestige).

    Three stand-ins for "missing": ABSENT is a field the header leaves out,
    and its key "absent" matches only another absent field; None is an
    empty inputs list, which refusals treats as matching nothing; and in a
    refusal's values a None is an absent field, since a null one is a
    breach."""
    if value is ABSENT:
        return "absent"
    if field == "inputs":
        if not value:
            return None
        value = sorted([i["name"], i["hash"]] for i in value)
    return json.dumps(_by_value(value), sort_keys=True)


def _by_value(value):
    """`value` with every number as the exact text of its value, so JSON's
    1 and 1.0 give one key. Booleans stay booleans."""
    if isinstance(value, bool) or not isinstance(value, (int, float, list, dict)):
        return value
    if isinstance(value, list):
        return [_by_value(v) for v in value]
    if isinstance(value, dict):
        return {k: _by_value(v) for k, v in value.items()}
    return str(Fraction(str(value)))


def refusal_sentence(refused: list[dict]) -> str:
    parts = []
    for entry in refused:
        by_value: dict[str, list[str]] = {}
        for name, value in entry["values"].items():
            # A blocking field holding null breaks the format, so None is absent.
            by_value.setdefault("absent" if value is None else json.dumps(value), []).append(name)
        if entry["field"] == "inputs" and list(by_value) == ["[]"]:
            what = "inputs is empty in every run, so the inputs are unknown"
        else:
            # Two empty input lists are unknown, not equal (§ 4.2), so say so.
            what = f"{entry['field']} differs: " + "; ".join(
                f"{'[] (unknown)' if value == '[]' else value} in {', '.join(names)}"
                for value, names in by_value.items())
        parts.append(f"{what} (--override {entry['field']}=REASON compares anyway)")
    return f"The runs cannot be compared: {'; '.join(parts)}."


def unused_override_notices(unused: list[str]) -> list[ledger.Notice]:
    """An override_unused warning for each overridden field that did not differ."""
    return [ledger.Notice("override_unused", f"--override {field} was given, but every run has the "
                          "same value") for field in unused]


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


def run_notices(runs: list[Named]) -> list[ledger.Notice]:
    """Each run's own notices and § 4.9 warnings, opening with its name."""
    found = []
    for r in runs:
        for notice in r.run.notices + trust.warnings(r.run, run_report.walled_frames(r.run)):
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
    the wall's 99th percentile, as `report` gives them. A mem measure's
    value is in MB, the others' in ms."""
    costs = run_report.Costs(run)
    values = {}
    for (kind, name), times in costs.frame_values.items():
        statistics = [statistic for wanted, statistic in FRAME_MEASURES if wanted == name]
        if not statistics:  # a frame row FRAME_MEASURES does not judge
            continue
        ranks = [stats.RANKS[statistic] for statistic in statistics]
        for statistic, value in zip(statistics, stats.percentiles(times, *ranks), strict=True):
            values[Measure(kind, "frame", name, 0, statistic)] = value
    for (kind, category, name, depth), times in (*costs.pass_values.items(), *costs.mem_values.items()):
        values[Measure(kind, category, name, depth, "median")] = stats.median(times)
    return values


def _judge_all(runs: list[Named], floors: Floors) -> tuple[list[dict], list[dict]]:
    """Every measure all runs share, judged; and those only some runs have."""
    per_run = [_values(r.run) for r in runs]
    tick = largest_tick(runs)
    measures, unmatched = [], []
    for measure in set().union(*per_run):
        present = [r.name for r, values in zip(runs, per_run, strict=True) if measure in values]
        if len(present) < len(runs):
            unmatched.append({**_measure_fields(measure), "present_in": present})
            continue
        old = [values[measure] for r, values in zip(runs, per_run, strict=True) if r.set == "old"]
        new = [values[measure] for r, values in zip(runs, per_run, strict=True) if r.set == "new"]
        measures.append(_judge(measure, old, new, floors, tick))
    return sorted(measures, key=_rank), sorted(unmatched, key=_rank)


def _judge(measure: Measure, old: list[int], new: list[int], floors: Floors, tick: Fraction) -> dict:
    """§ 4.10's table, in exact fractions of a thousandth."""
    old_centre, new_centre = centre(old), centre(new)
    spread = spread_of(old, new)
    change = new_centre - old_centre
    floor = change_floor(measure.category, measure.name, old_centre, floors.minimum(measure.category),
                         floors.min_pct, tick)
    verdict = change_verdict(change, spread, floor)
    if measure.category == "mem":
        verdict = MEM_VERDICTS.get(verdict, verdict)
    return {
        **_measure_fields(measure),
        "old": [v / 1000 for v in old],
        "new": [v / 1000 for v in new],
        "old_centre": _four_places(old_centre),
        "new_centre": _four_places(new_centre),
        "change": _four_places(change),
        "change_pct": None if old_centre == 0 else _round(change / old_centre * 100, 2),
        "spread": _four_places(spread),
        "floor": _four_places(floor),
        "verdict": verdict,
    }


def spread_of(old: list[int], new: list[int]) -> int:
    """The wider set's range, whichever set that is."""
    return max(max(old) - min(old), max(new) - min(new))


def change_floor(category: str, name: str, old_centre: Fraction, minimum: Decimal, min_pct: Decimal,
                 tick: Fraction) -> Fraction:
    """The smallest change that counts, in thousandths: `minimum`, in the
    measure's own unit (--min-ms, or --min-mb for a mem measure), or
    `min_pct` percent of the old centre, whichever is larger. A GPU
    timing is also no finer than the clock that took it."""
    floor = max(Fraction(minimum) * 1000, Fraction(min_pct) / 100 * old_centre)
    if category == "gpu" or (category, name) == ("frame", "gpu_span"):
        floor = max(floor, tick)
    return floor


def change_verdict(change: Fraction, spread: int, floor: Fraction) -> str:
    """§ 4.10's table: "slower", "faster", "noisy" or "unchanged"."""
    if change > spread and change >= floor:
        return "slower"
    if -change > spread and -change >= floor:
        return "faster"
    if spread > 0 and spread >= floor:  # runs that do not vary are never noisy (Vestige)
        return "noisy"
    return "unchanged"


def centre(values: list[int]) -> Fraction:
    """A set of runs' centre: the middle value, or the mean of the two
    middle ones. Not stats.median, the nearest rank `report` gives a
    run's frames, which for two values is the lower."""
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return Fraction(ordered[middle])
    return Fraction(ordered[middle - 1] + ordered[middle], 2)


def largest_tick(runs: list[Named]) -> Fraction:
    """The largest gpu_tick_ns among the runs, in thousandths of a ms (ns
    / 1000); 0 when no run states one."""
    ticks = [Fraction(str(r.run.header["gpu_tick_ns"])) / 1000 for r in runs
             if "gpu_tick_ns" in r.run.header]
    return max(ticks, default=Fraction(0))


def _measure_fields(measure: Measure) -> dict:
    return {"segment_kind": measure.kind, "category": measure.category, "name": measure.name,
            "depth": measure.depth, "statistic": measure.statistic, "unit": unit_of(measure.category)}


def _rank(entry: dict) -> tuple:
    """§ 4.10's order: segment kind, then frame measures in FRAME_MEASURES'
    order, then cpu, gpu and mem by old centre, largest first. An
    unmatched entry has no centre, so ranks by name."""
    frame_rank = (FRAME_MEASURES.index((entry["name"], entry["statistic"]))
                  if entry["category"] == "frame" else 0)
    return (run_report.kind_order(entry["segment_kind"]), CATEGORY_ORDER[entry["category"]], frame_rank,
            -entry.get("old_centre", 0), entry["name"], entry["depth"], entry["statistic"])


def _short_kinds(runs: list[Named]) -> list[str | None]:
    """Segment kinds where some run has fewer than trust.FEWEST_FRAMES frames
    with a wall: their frame time is noisy almost every time (Vestige). A
    run without the kind has 0 of them."""
    per_run = [Counter(run_report.segment_kind(ledger.frame_segment(rows))
                       for rows in r.run.frames.values() if ("frame", "wall") in rows) for r in runs]
    kinds = set().union(*per_run)
    return sorted((k for k in kinds if min(c[k] for c in per_run) < trust.FEWEST_FRAMES),
                  key=run_report.kind_order)


def _verdict(incomplete: list[str], measures: list[dict], short: list) -> tuple[str, list[str]]:
    """§ 4.10's verdict, first match wins, and the sentences saying it. ms
    and MB never rank against each other, so slower passes and larger
    memory each get a sentence."""
    moved = {word: [m for m in measures if m["verdict"] == word]
             for word in ("slower", "larger", "faster", "smaller")}
    noisy_walls = [m for m in measures if (m["category"], m["name"], m["statistic"]) ==
                   ("frame", "wall", "median") and m["verdict"] == "noisy"
                   and m["segment_kind"] not in short]
    if incomplete:
        return "inconclusive", ["The compare is inconclusive: a run is incomplete, so a change could "
                                "be a missing frame."]
    if moved["slower"] or moved["larger"]:
        sentences = []
        if moved["slower"]:
            sentences.append(_worse_sentence("The new runs are slower", "slower", moved["slower"]))
        if moved["larger"]:
            sentences.append(_worse_sentence("The new runs use more memory", "larger", moved["larger"]))
        return "fail", sentences
    if noisy_walls:
        wall = noisy_walls[0]
        return "inconclusive", [f"The compare is inconclusive: {_label(wall)} moved "
                                f"{wall['change']:+.3f} ms, within the runs' spread of "
                                f"{wall['spread']:.3f} ms; re-run with more runs a set."]
    sentence = "No measure got slower or larger between the old and new runs"
    for word in ("faster", "smaller"):
        if moved[word]:
            sentence += f"; {run_report.counted(len(moved[word]), 'measure')} got {word}"
    return "pass", [sentence + "."]


def _worse_sentence(opening: str, word: str, measures: list[dict]) -> str:
    """Names the largest change among `measures`, all in one unit."""
    worst = max(measures, key=lambda m: (m["change"], m["change_pct"] or 0))
    unit = worst["unit"]
    return (f"{opening}: {run_report.counted(len(measures), 'measure')} got {word}; the largest is "
            f"{_label(worst)}, up {worst['change']:.3f} {unit}{_pct(worst)}, beyond the runs' spread of "
            f"{worst['spread']:.3f} {unit}.")


def _wall_sentences(measures: list[dict]) -> list[str]:
    return [f"In {run_report.kind_name(m['segment_kind'])} segments the median frame/wall went from "
            f"{m['old_centre']:.3f} ms to {m['new_centre']:.3f} ms ({m['verdict']})."
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


def _four_places(thousandths: Fraction | int) -> float:
    """A measure's value in its unit, to four places, half away from zero (§ 4.10)."""
    return _round(Fraction(thousandths) / 1000, 4)


def _round(value: Fraction, places: int) -> float:
    """`value` to `places` decimal places, half away from zero, in integers:
    a Decimal division would round once at its own precision first (DOOM
    Ants)."""
    scaled = abs(value) * 10**places
    whole = (2 * scaled.numerator + scaled.denominator) // (2 * scaled.denominator)
    return float(Fraction(whole if value >= 0 else -whole, 10**places))
