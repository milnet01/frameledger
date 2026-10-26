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
CATEGORY_ORDER = {"frame": 0, "cpu": 1, "gpu": 2}
ABSENT = object()  # a run's header field that is absent: it matches only another absent one
# Notice codes the opening sentences say themselves, per run.
INCOMPLETE_CODES = ("rows_dropped", "unfinished")


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
    refused, unused = _refusals(runs, overrides)
    notices = [ledger.Notice("override_unused", f"--override {field} was given, but every run has the "
                             "same value") for field in unused]
    run_list = [_run_entry(r) for r in runs]
    if refused:
        summary += [_refusal_sentence(refused), *run_report.warning_sentences(notices)]
        return {"verdict": "error", "summary": summary, "warnings": _warnings(notices),
                "overrides": override_list, "result": {"runs": run_list, "refused": refused}}

    incomplete = _incomplete_sentences(runs)
    notices += _run_notices(runs) + _set_notices(runs)
    shown = [n for n in notices if n.code not in INCOMPLETE_CODES]
    summary += incomplete + run_report.warning_sentences(shown)

    measures, unmatched = _judge_all(runs, min_ms, min_pct)
    short = _short_kinds(runs)
    verdict, sentence = _verdict(incomplete, measures, short)
    summary.append(sentence)
    if short:  # straight after the verdict, which it explains (Vestige)
        kinds = ", ".join(run_report.kind_name(k) for k in short)
        summary.append(f"Some run has fewer than {trust.FEWEST_FRAMES} frames with a frame/wall in "
                       f"{kinds} segments, so a noisy frame time there cannot make the compare "
                       "inconclusive.")
    summary += _wall_sentences(measures)
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


def overrides_sentences(overrides: list[dict]) -> list[str]:
    """S5: every override and its reason, in the first sentence, whatever
    else the compare says (DOOM Ants); none when there are none."""
    if not overrides:
        return []
    listed = "; ".join(f"{o['field']} may differ (\"{o['reason']}\")" for o in overrides)
    return [f"Overrides given: {listed}."]


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
    """What two runs must share in `field`, as a string. `inputs` match on
    their name and hash pairs in any order, and numbers by value, so
    render_scale 1 matches 1.0 (Vestige).

    Three stand-ins for "missing": ABSENT is a field the header leaves out,
    and its key "absent" matches only another absent field; None is an
    empty inputs list, which _refusals treats as matching nothing; and in a
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


def _refusal_sentence(refused: list[dict]) -> str:
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
    for measure in set().union(*per_run):
        present = [r.name for r, values in zip(runs, per_run, strict=True) if measure in values]
        if len(present) < len(runs):
            unmatched.append({**_measure_fields(measure), "present_in": present})
            continue
        old = [values[measure] for r, values in zip(runs, per_run, strict=True) if r.set == "old"]
        new = [values[measure] for r, values in zip(runs, per_run, strict=True) if r.set == "new"]
        measures.append(_judge(measure, old, new, min_ms, min_pct, tick))
    return sorted(measures, key=_rank), sorted(unmatched, key=_rank)


def _judge(measure: Measure, old: list[int], new: list[int], min_ms: Decimal, min_pct: Decimal,
           tick: Fraction) -> dict:
    """§ 4.10's table, in exact fractions of a thousandth."""
    old_centre, new_centre = _centre(old), _centre(new)
    spread = _spread(old, new)
    change = new_centre - old_centre
    floor = _floor(measure, old_centre, min_ms, min_pct, tick)
    verdict = _change_verdict(change, spread, floor)
    return {
        **_measure_fields(measure),
        "old_ms": [v / 1000 for v in old],
        "new_ms": [v / 1000 for v in new],
        "old_centre_ms": _ms4(old_centre),
        "new_centre_ms": _ms4(new_centre),
        "change_ms": _ms4(change),
        "change_pct": None if old_centre == 0 else _round(change / old_centre * 100, 2),
        "spread_ms": _ms4(spread),
        "floor_ms": _ms4(floor),
        "verdict": verdict,
    }


def _spread(old: list[int], new: list[int]) -> int:
    """The wider set's range, whichever set that is."""
    return max(max(old) - min(old), max(new) - min(new))


def _floor(measure: Measure, old_centre: Fraction, min_ms: Decimal, min_pct: Decimal,
           tick: Fraction) -> Fraction:
    """The smallest change that counts, in thousandths. GPU timings are
    also no finer than the clock that took them. `min_ms` is in the
    measure's unit, so a mem measure's caller passes --min-mb."""
    floor = max(Fraction(min_ms) * 1000, Fraction(min_pct) / 100 * old_centre)
    if measure.category == "gpu" or (measure.category, measure.name) == ("frame", "gpu_span"):
        floor = max(floor, tick)
    return floor


def _change_verdict(change: Fraction, spread: int, floor: Fraction) -> str:
    if change > spread and change >= floor:
        return "slower"
    if -change > spread and -change >= floor:
        return "faster"
    if spread > 0 and spread >= floor:  # runs that do not vary are never noisy (Vestige)
        return "noisy"
    return "unchanged"


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


def _rank(entry: dict) -> tuple:
    """§ 4.10's order: segment kind, then frame measures in FRAME_MEASURES'
    order, then cpu, then gpu passes by old centre, largest first. An
    unmatched entry has no centre, so ranks by name."""
    frame_rank = (FRAME_MEASURES.index((entry["name"], entry["statistic"]))
                  if entry["category"] == "frame" else 0)
    return (run_report.kind_order(entry["segment_kind"]), CATEGORY_ORDER[entry["category"]], frame_rank,
            -entry.get("old_centre_ms", 0), entry["name"], entry["depth"], entry["statistic"])


def _short_kinds(runs: list[Named]) -> list[str | None]:
    """Segment kinds where some run has fewer than trust.FEWEST_FRAMES frames
    with a wall: their frame time is noisy almost every time (Vestige). A
    run without the kind has 0 of them."""
    per_run = [Counter(run_report.segment_kind(ledger.frame_segment(rows))
                       for rows in r.run.frames.values() if ("frame", "wall") in rows) for r in runs]
    kinds = set().union(*per_run)
    return sorted((k for k in kinds if min(c[k] for c in per_run) < trust.FEWEST_FRAMES),
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
    return _round(Fraction(thousandths) / 1000, 4)


def _round(value: Fraction, places: int) -> float:
    """`value` to `places` decimal places, half away from zero, in integers:
    a Decimal division would round once at its own precision first (DOOM
    Ants)."""
    scaled = abs(value) * 10**places
    whole = (2 * scaled.numerator + scaled.denominator) // (2 * scaled.denominator)
    return float(Fraction(whole if value >= 0 else -whole, 10**places))


# ── Bisect (§ 4.11) ──────────────────────────────────────────────────────────

BISECT_FRAME_NAMES = ("wall", "cpu_span", "gpu_span")  # § 4.10's frame measures
BISECT_CATEGORIES = ("frame", "cpu", "gpu", "mem")
FEWEST_REFERENCES = FEWEST_RUNS  # one noisy reference would move the line for every commit
STOP_SENTENCE = "The bisect stops (exit 128)."


class Wanted(NamedTuple):
    """The one measure a bisect judges, and the frames it is taken over:
    one segment kind, one segment, or frames with no segment (both None)."""
    category: str
    name: str
    statistic: str  # "median" or "p99"
    depth: int | None  # None: whichever one depth the name has
    kind: str | None
    segment: str | None  # KIND:ID; `kind` then holds its kind

    @property
    def unit(self) -> str:
        return "MB" if self.category == "mem" else "ms"


class Tested(NamedTuple):
    """One of the tested commit's run files: its Run, or why it could not be read."""
    path: str
    run: ledger.Run | None
    error: str | None


class Floors(NamedTuple):
    """The reference floor's settings: --min-ms, --min-mb and --min-pct."""
    min_ms: Decimal
    min_mb: Decimal
    min_pct: Decimal


class _Stop(Exception):
    """The bisect cannot go on (exit 128). The message is the sentence
    saying why; a refusal also carries § 4.10's `refused` entries."""

    def __init__(self, sentence: str, refused: list[dict] | None = None):
        super().__init__(sentence)
        self.refused = refused or []


class _Skip(Exception):
    """This commit cannot be judged (exit 125). The message is the sentence."""


def bisect(wanted: Wanted, tested: list[Tested], good: list[ledger.Run], bad: list[ledger.Run],
           overrides: dict[str, str], floors: Floors, bad_above: Decimal | None = None,
           dry_value: Decimal | None = None, skip_straddle: bool = False) -> dict:
    """{"verdict", "summary", "warnings", "overrides", "result"} for one
    commit: good, bad, skip or stop. Reference mode when `good` and `bad`
    are given, threshold mode with `bad_above`; `dry_value` stands in for
    the tested runs. cli.py has checked the flags and read the files."""
    refs = [Named(f"{label}-{i}", label, run.path, run)
            for label, group in (("good", good), ("bad", bad)) for i, run in enumerate(group, 1)]
    # A tested file that could not be read is a Named whose run is None; it skips the commit.
    tested_runs = [Named(f"tested-{i}", "tested", t.path, t.run) for i, t in enumerate(tested, 1)]
    override_list = [{"field": f, "reason": r} for f, r in overrides.items()]
    values: dict[str, int] = {}  # each run's value of the measure, in thousandths
    result = {"measure": _wanted_fields(wanted), "dry_run": dry_value is not None, "runs": [],
              "value": None, "bad_above": None, "references": None, "refused": []}
    notices: list[ledger.Notice] = []
    centres = None  # the good and bad centres, in reference mode
    try:
        if refs:
            line, centres = _reference_line(wanted, refs, overrides, floors, values, result)
        else:
            line = Fraction(bad_above) * 1000
        result["bad_above"] = float(_exact(line))
        if dry_value is None:
            value = _tested_value(wanted, tested, tested_runs, refs, overrides, values)
            notices = _tested_notices(tested_runs, refs, overrides)
            straddle = _straddle(tested_runs, values, line, wanted.unit)
            if straddle and skip_straddle:
                raise _Skip(f"The tested runs fall on both sides of the line: {straddle}; so this "
                            "commit is skipped (exit 125).")
            if straddle:
                notices.append(ledger.Notice("tested_straddle", f"the tested runs fall on both sides of "
                                             f"{_shown(line, wanted.unit)}: {straddle}"))
        else:
            value = Fraction(dry_value) * 1000
    except _Stop as stop:
        verdict, sentences = "stop", [str(stop), STOP_SENTENCE]
        result["refused"] = stop.refused
    except _Skip as skip:
        verdict, sentences = "skip", [str(skip)]
    else:
        verdict = "bad" if value > line else "good"
        result["value"] = float(_exact(value))
        sentences = [*run_report.warning_sentences(notices),
                     _bisect_sentence(wanted, value, line, centres, dry_value is not None)]
    result["runs"] = [_bisect_entry(r, values) for r in refs + tested_runs]
    return {"verdict": verdict, "summary": overrides_sentences(override_list) + sentences,
            "warnings": _warnings(notices), "overrides": override_list, "result": result}


def _reference_line(wanted: Wanted, refs: list[Named], overrides: dict[str, str], floors: Floors,
                    values: dict[str, int], result: dict) -> tuple[Fraction, tuple[Fraction, Fraction]]:
    """The midpoint of the good and bad centres, and the centres, once
    every reference check of § 4.11 has passed; fills `values` and
    result["references"]."""
    for label in ("good", "bad"):
        count = sum(r.set == label for r in refs)
        if count < FEWEST_REFERENCES:
            raise _Stop(f"The {label} references are {run_report.counted(count, 'run')}; each set needs "
                        f"at least {FEWEST_REFERENCES}, since one noisy reference would move the line "
                        "for every commit.")
    for r in refs:
        try:
            run_report.refuse_breaches(r.run)
        except ledger.LedgerError as error:
            raise _Stop(f"{r.name} is a broken reference file: {error}.") from None
        if r.run.close is None:
            raise _Stop(f"{r.name} has no close line, so the run did not finish and cannot be a reference.")
        if r.run.close["rows_dropped"]:
            raise _Stop(f"In {r.name} the writer dropped "
                        f"{run_report.counted(r.run.close['rows_dropped'], 'row')}, so it cannot be a "
                        "reference.")
    refused, _ = _refusals(refs, overrides)
    if refused:
        raise _Stop(_refusal_sentence(refused), refused)
    for r in refs:
        value = _run_value(wanted, r)
        if value is None:
            raise _Stop(f"{r.name} has no {_bisect_label(wanted)}, so it cannot be a reference.")
        values[r.name] = value

    good = [values[r.name] for r in refs if r.set == "good"]
    bad = [values[r.name] for r in refs if r.set == "bad"]
    good_centre, bad_centre = _centre(good), _centre(bad)
    spread = _spread(good, bad)
    # The good runs are the old: the floor's percent is of the good centre.
    tick_rule = Measure(wanted.kind, wanted.category, wanted.name, 0, wanted.statistic)
    min_floor = floors.min_mb if wanted.category == "mem" else floors.min_ms
    floor = _floor(tick_rule, good_centre, min_floor, floors.min_pct, _largest_tick(refs))
    result["references"] = {"good_centre": float(_exact(good_centre)), "bad_centre": float(_exact(bad_centre)),
                            "spread": float(_exact(spread)), "floor": float(_exact(floor))}
    unit = wanted.unit
    centres = (f"the bad runs' centre of {_shown(bad_centre, unit)} against the good runs' "
               f"{_shown(good_centre, unit)}")
    if _change_verdict(bad_centre - good_centre, spread, floor) != "slower":
        if bad_centre < good_centre:
            raise _Stop(f"The references are the wrong way round: {centres}.")
        raise _Stop(f"The references do not separate: {centres} is not above the spread of "
                    f"{_shown(spread, unit)} and at least the floor of {_shown(floor, unit)}.")

    line = (good_centre + bad_centre) / 2
    # A good run above the midpoint, or a bad one at it or below, would itself be misjudged (Vestige).
    wrong = [r for r in refs if (values[r.name] > line if r.set == "good" else values[r.name] <= line)]
    if wrong:
        listed = ", ".join(f"{r.name} at {_shown(values[r.name], unit)}" for r in wrong)
        raise _Stop(f"The references straddle their own midpoint of {_shown(line, unit)}: {listed}, so a "
                    "run like it would be misjudged.")
    return line, (good_centre, bad_centre)


def _tested_value(wanted: Wanted, tested: list[Tested], tested_runs: list[Named], refs: list[Named],
                  overrides: dict[str, str], values: dict[str, int]) -> Fraction:
    """The tested runs' centre, once each can be judged; fills `values`."""
    for t, r in zip(tested, tested_runs, strict=True):
        if t.run is None:
            raise _Skip(f"{r.name} cannot be read ({t.error}), so this commit is skipped (exit 125).")
        if t.run.breaches:
            first = t.run.breaches[0]
            raise _Skip(f"{r.name} breaks the run-file format at line {first.line}: {first.message}; "
                        "so this commit is skipped (exit 125).")
    refused, _ = _refusals(refs + tested_runs, overrides)
    if refused:
        raise _Stop(_refusal_sentence(refused), refused)
    for r in tested_runs:
        if r.run.close is None:
            raise _Skip(f"{r.name} has no close line, so the run did not finish; this commit is skipped "
                        "(exit 125).")
        if r.run.close["rows_dropped"]:
            raise _Skip(f"In {r.name} the writer dropped "
                        f"{run_report.counted(r.run.close['rows_dropped'], 'row')}; this commit is "
                        "skipped (exit 125).")
    for r in tested_runs:
        value = _run_value(wanted, r)
        if value is None:
            kinds = ", ".join(run_report.kind_name(k) for k in _kinds(r.run)) or "none"
            raise _Skip(f"{r.name} has no {_bisect_label(wanted)}; its segment kinds are {kinds}. This "
                        "commit is skipped (exit 125).")
        values[r.name] = value
    return _centre([values[r.name] for r in tested_runs])


def _tested_notices(tested_runs: list[Named], refs: list[Named], overrides: dict[str, str]) -> list[ledger.Notice]:
    """§ 4.9's warnings for each tested run, then override_unused and dirty_build."""
    notices = [n for n in _run_notices(tested_runs) if n.code not in INCOMPLETE_CODES]
    _, unused = _refusals(refs + tested_runs, overrides)
    notices += [ledger.Notice("override_unused", f"--override {field} was given, but every run has "
                              "the same value") for field in unused]
    notices += [ledger.Notice("dirty_build", f"{r.name}: the build had uncommitted changes, so it may "
                              "not be the commit under test") for r in tested_runs if r.run.header["dirty"]]
    return notices


def _straddle(tested_runs: list[Named], values: dict[str, int], line: Fraction, unit: str) -> str:
    """Each tested run and its value when some are above the line and some
    at it or below; empty otherwise. One run cannot straddle."""
    above = [values[r.name] > line for r in tested_runs]
    if all(above) or not any(above):
        return ""
    return ", ".join(f"{r.name} {_shown(values[r.name], unit)}" for r in tested_runs)


def _run_value(wanted: Wanted, named: Named) -> int | None:
    """One run's value of the measure over the chosen frames, in
    thousandths, or None when it has none there."""
    costs = run_report.Costs(named.run, by_segment=wanted.segment is not None)
    group = wanted.segment if wanted.segment is not None else wanted.kind
    if wanted.category == "frame":
        by_depth = {0: costs.frame_values.get((group, wanted.name))}
    else:
        source = costs.mem_values if wanted.category == "mem" else costs.pass_values
        by_depth = {depth: times for (g, category, name, depth), times in source.items()
                    if (g, category, name) == (group, wanted.category, wanted.name)}
    by_depth = {depth: times for depth, times in by_depth.items() if times}
    if wanted.depth is None and len(by_depth) > 1:
        depths = " and ".join(str(d) for d in sorted(by_depth))
        raise _Stop(f"{named.name} has {wanted.category}/{wanted.name} at depths {depths}; --depth picks one.")
    if wanted.depth is None:
        times = next(iter(by_depth.values()), None)
    else:
        times = by_depth.get(wanted.depth)
    if times is None:
        return None
    return stats.percentile(times, 99) if wanted.statistic == "p99" else stats.median(times)


def _kinds(run: ledger.Run) -> list[str | None]:
    return sorted({run_report.segment_kind(ledger.frame_segment(rows)) for rows in run.frames.values()},
                  key=run_report.kind_order)


def _bisect_label(wanted: Wanted) -> str:
    where = (f"segment {wanted.segment}" if wanted.segment else
             f"{wanted.kind} segments" if wanted.kind else "frames with no segment")
    depth = "" if wanted.depth is None else f" at depth {wanted.depth}"
    return f"{wanted.category}/{wanted.name}{depth} {wanted.statistic} in {where}"


def _bisect_sentence(wanted: Wanted, value: Fraction, line: Fraction,
                     centres: tuple[Fraction, Fraction] | None, dry_run: bool) -> str:
    unit = wanted.unit
    side = "above" if value > line else "at or below"
    outcome = "bad (exit 1)" if value > line else "good (exit 0)"
    if centres is None:
        against = f"the threshold of {_shown(line, unit)}"
    else:
        good_centre, bad_centre = centres
        against = (f"the midpoint of {_shown(line, unit)} between the good runs' "
                   f"{_shown(good_centre, unit)} and the bad runs' {_shown(bad_centre, unit)}")
    label = _bisect_label(wanted)
    if dry_run:
        return f"Dry run: {label} of {_shown(value, unit)} would be {side} {against}: {outcome}."
    return f"{label} is {_shown(value, unit)}, {side} {against}: {outcome}."


def _bisect_entry(named: Named, values: dict[str, int]) -> dict:
    """§ 4.11's run entry; a tested file that could not be read has only
    its name, set and path."""
    if named.run is None:
        entry = {"name": named.name, "set": named.set, "path": named.path, "run_id": None, "commit": None,
                 "dirty": None, "rows_dropped": None, "finished": None}
    else:
        entry = {key: value for key, value in _run_entry(named).items() if key != "started_utc"}
    value = values.get(named.name)
    return {**entry, "value": None if value is None else float(_exact(value))}


def _wanted_fields(wanted: Wanted) -> dict:
    return {"segment_kind": wanted.kind, "segment": wanted.segment, "category": wanted.category,
            "name": wanted.name, "depth": wanted.depth, "statistic": wanted.statistic, "unit": wanted.unit}


def _exact(thousandths: Fraction | int) -> Decimal:
    """A value in the measure's unit, exactly, with at least three places.
    A run's value is whole thousandths, a centre half ones and a midpoint
    quarter ones, so five places are the most it needs (§ 4.11)."""
    fraction = Fraction(thousandths) / 1000
    value = Decimal(fraction.numerator) / Decimal(fraction.denominator)
    return value if value.as_tuple().exponent <= -3 else value.quantize(Decimal("0.001"))


def _shown(thousandths: Fraction | int, unit: str) -> str:
    return f"{_exact(thousandths)} {unit}"
