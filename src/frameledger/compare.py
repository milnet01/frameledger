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
import statistics
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
# Why a scene or variant with none of --measure's names is unjudged. One
# sentence, two tests: a scene lacks them when no run of either side has one
# (§ 4.14); a variant when none of its own runs has, whatever the base runs
# have (§ 4.16).
LACKS_NAMED = "none of its runs has a named measure"


class Floors(NamedTuple):
    """The smallest change that counts: --min-ms, --min-mb and --min-pct."""
    min_ms: Decimal
    min_mb: Decimal
    min_pct: Decimal

    def minimum(self, category: str) -> Decimal:
        """The absolute floor, in the unit of a measure of `category`."""
        return self.min_mb if category == "mem" else self.min_ms


class LoadLimits(NamedTuple):
    """--max-load and --max-gpu-busy: above either, a run was taken under
    load (§ 4.10, S22)."""
    max_load: Decimal = Decimal("0.25")
    max_gpu_busy: Decimal = Decimal(20)

    def under_load(self, header: dict) -> list[tuple[str, object, Decimal]]:
        """Each peak above its limit, above and not at: (name, value, limit)."""
        found = []
        for field, limit in (("load", self.max_load), ("gpu_busy_pct", self.max_gpu_busy)):
            peak = header.get(field, {}).get("peak")
            if peak is not None and Decimal(repr(peak)) > limit:
                found.append((f"{field}.peak", peak, limit))
        return found


DEFAULT_LIMITS = LoadLimits()

# § 4.10's difference warnings on a number: (code, field, keys, the largest
# difference allowed, whether that is a share of the old median). The key
# judged is the first of `keys` that every run has.
DIFFERS = (("load_differs", "load", ("start",), Decimal("0.1"), False),
           ("gpu_busy_differs", "gpu_busy_pct", ("start",), Decimal(10), False),
           ("gpu_clock_differs", "gpu_clock_mhz", ("end",), Decimal("0.05"), True),
           ("cpu_clock_differs", "cpu_clock_mhz", ("end",), Decimal("0.05"), True),
           # A short run ends cooler than it ran, so a peak says more (the engines).
           ("cpu_temp_differs", "cpu_temp_c", ("peak", "end"), Decimal(10), False),
           ("gpu_temp_differs", "gpu_temp_c", ("peak", "end"), Decimal(10), False))
# § 4.10's difference warnings on a setting: (code, field).
SETTINGS_DIFFER = (("governor_differs", "cpu_governor"), ("turbo_differs", "turbo"),
                   ("power_differs", "power"), ("sanitizers_differs", "sanitizers"))


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


def compare(old: list[ledger.Run], new: list[ledger.Run], overrides: dict[str, str], floors: Floors,
            limits: LoadLimits = DEFAULT_LIMITS, named_measures: tuple[str, ...] = (),
            sides: tuple[str, str] = ("old", "new"), baseline: bool = False) -> dict:
    """{"verdict", "reason", "summary", "warnings", "overrides", "unused",
    "absent", "result"} for two sets of runs that meet the format. `reason`
    says, in a clause, why the compare is refused or inconclusive, and is
    None otherwise. `unused` lists the overridden fields that differ in no
    run. `named_measures` is --measure's CATEGORY/NAME list: when given,
    only those measures are judged, and `absent` lists the ones no run
    has, which the caller refuses. cli.py checks the run counts, the
    override fields and the names' form; a Run with a breach raises
    LedgerError, as under `report`.

    `sides` names the two sets where a run or a warning names them: under
    § 4.16 the old set is `base` and the new set the variant, so the runs
    are base-1, no_bloom-1. Each run's `set` stays "old" or "new".
    `baseline` says the old set came from a baseline file, which has
    warnings of its own (§ 4.17).

    The opening sentences follow § 4.10's order: the overrides; the named
    measures; a refusal, which ends the compare; each incomplete run; one
    per kind of warning; the verdict; the short kinds; the frame time per
    segment kind."""
    called = dict(zip(("old", "new"), sides, strict=True))
    runs = named_set("old", called["old"], old) + named_set("new", called["new"], new)
    for r in runs:
        run_report.refuse_breaches(r.run)
    override_list = [{"field": f, "reason": r} for f, r in overrides.items()]
    summary = overrides_sentences(override_list)
    if named_measures:
        summary.append(f"Judging only {joined(named_measures)}.")
    refused, unused = refusals(runs, overrides)
    notices = unused_override_notices(unused)
    run_list = [run_entry(r, limits) for r in runs]
    if refused:
        summary += [refusal_sentence(refused), *run_report.warning_sentences(notices)]
        return {"verdict": "error", "reason": refusal_reason(refused), "summary": summary,
                "warnings": run_report.warning_entries(notices), "overrides": override_list,
                "unused": unused, "absent": [], "result": {"runs": run_list, "refused": refused}}

    incomplete = _incomplete_sentences(runs)
    loaded = load_sentences(runs, limits)
    measures, unmatched, absent, outliers = _judge_all(runs, floors, called, named_measures)
    notices += run_notices(runs) + _set_notices(runs, called, baseline) + outliers
    shown = [n for n in notices if n.code not in INCOMPLETE_CODES]
    summary += incomplete + loaded + run_report.warning_sentences(shown)

    short = _short_kinds(runs)
    verdict, sentences, reason = _verdict(incomplete, loaded, measures, short, bool(named_measures), unmatched)
    summary += sentences
    if short and (not named_measures or "frame/wall" in named_measures):
        # Straight after the verdict, which it explains (Vestige); without
        # frame/wall judged, step 3 skips nothing, so nothing to explain.
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
        "max_load": float(limits.max_load),
        "max_gpu_busy": float(limits.max_gpu_busy),
        "named_measures": list(named_measures),
        "measures": measures,
        "unmatched": unmatched,
        "static_diff": _static_diff(runs),
        "refused": [],
    }
    return {"verdict": verdict, "reason": reason, "summary": summary,
            "warnings": run_report.warning_entries(notices), "overrides": override_list, "unused": unused,
            "absent": absent, "result": result}


def named_set(label: str, called: str, runs: list[ledger.Run]) -> list[Named]:
    """One set's runs under the names every sentence and result uses:
    `called`-1, `called`-2, …, in the order given. `label` is "old" or
    "new"."""
    return [Named(f"{called}-{i}", label, run.path, run) for i, run in enumerate(runs, 1)]


def run_entry(named: Named, limits: LoadLimits = DEFAULT_LIMITS) -> dict:
    header, close = named.run.header, named.run.close
    return {"name": named.name, "set": named.set, "path": named.path, "run_id": header["run_id"],
            "commit": header["commit"], "dirty": header["dirty"], "started_utc": header["started_utc"],
            "rows_dropped": close["rows_dropped"] if close else None, "finished": close is not None,
            "under_load": [peak for peak, _, _ in limits.under_load(header)]}


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
    return f"The runs cannot be compared: {refusal_reason(refused)}."


def refusal_reason(refused: list[dict]) -> str:
    """Each refusing field with the runs' values, and the override that
    would allow it."""
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
    return "; ".join(parts)


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


def load_sentences(runs: list[Named], limits: LoadLimits) -> list[str]:
    """A run taken under load cannot pass or fail a compare (S22): other
    programs shared the machine while it ran."""
    sentences = []
    for r in runs:
        peaks = limits.under_load(r.run.header)
        if peaks:
            listed = "; ".join(f"{name} {value}, above {limit}" for name, value, limit in peaks)
            sentences.append(f"{r.name} was taken under load: {listed}.")
    return sentences


def run_notices(runs: list[Named]) -> list[ledger.Notice]:
    """Each run's own notices and § 4.9 warnings, opening with its name."""
    found = []
    for r in runs:
        for notice in r.run.notices + trust.warnings(r.run, run_report.walled_frames(r.run)):
            found.append(ledger.Notice(notice.code, f"{r.name}: {notice.message}"))
    return found


def _set_notices(runs: list[Named], called: dict[str, str], baseline: bool = False) -> list[ledger.Notice]:
    """The warnings about a whole set. `called` is each set's name in
    them; `baseline` says the old set is a baseline's runs (§ 4.17)."""
    found = []
    starts = {label: [ledger.start_time(r.run.header["started_utc"]) for r in runs if r.set == label]
              for label in ("old", "new")}
    if baseline and max(starts["old"]) < min(starts["new"]):
        found.append(_baseline_first_notice(runs, called, min(starts["old"]), min(starts["new"])))
    elif max(starts["old"]) < min(starts["new"]) or max(starts["new"]) < min(starts["old"]):
        found.append(ledger.Notice("not_interleaved", "every run of one set started before every run "
                                   "of the other, so a drift over time reads as a change"))
    for label in ("old", "new"):
        found += mixed_build_notices([r for r in runs if r.set == label], called[label])
    found += _differ_notices(runs, called) + _setting_differ_notices(runs, called)
    return found + (_baseline_differ_notices(runs, called) if baseline else [])


def _baseline_first_notice(runs: list[Named], called: dict[str, str], oldest: tuple[datetime, Fraction],
                           first_new: tuple[datetime, Fraction]) -> ledger.Notice:
    """§ 4.17's stand-in for not_interleaved: what the baseline is, and how
    long before the first new run its oldest run started."""
    builds = dict.fromkeys((r.run.header["commit"], r.run.header["dirty"]) for r in runs if r.set == "old")
    commits = [f"{commit} (dirty)" if dirty else commit for commit, dirty in builds]
    seconds = int((first_new[0] - oldest[0]).total_seconds()) + first_new[1] - oldest[1]
    return ledger.Notice(
        "baseline_not_interleaved",
        f"the {called['old']} runs are a baseline of {'commit' if len(commits) == 1 else 'commits'} "
        f"{joined(commits)}, started {oldest[0].date().isoformat()} (UTC), {_age(seconds)} before the first "
        f"{called['new']} run; nothing ran in turn with them, so a drift on the machine since then reads "
        "as a change")


def _age(seconds: Fraction) -> str:
    """A length of time in whole days, or hours under a day, or minutes
    under an hour, rounded down."""
    for unit, length in (("day", 86400), ("hour", 3600), ("minute", 60)):
        if seconds >= length:
            return run_report.counted(int(seconds // length), unit)
    return "less than a minute"


def _baseline_differ_notices(runs: list[Named], called: dict[str, str]) -> list[ledger.Notice]:
    """§ 4.17: the driver, or the os when every run names one, is not the
    one the baseline was taken on."""
    found = []
    for field in ("driver", "os"):
        old, new = (sorted({r.run.header.get(field) for r in runs if r.set == label}, key=str)
                    for label in ("old", "new"))
        if old != new and None not in old + new:
            # Quoted, so an empty value still shows (UT Ants).
            shown_old, shown_new = (joined(f'"{value}"' for value in values) for values in (old, new))
            found.append(ledger.Notice(f"baseline_{field}_differs",
                                       f"the {called['old']} runs' {field} is {shown_old} and the "
                                       f"{called['new']} runs' is {shown_new}"))
    return found


def mixed_build_notices(one_set: list[Named], called: str) -> list[ledger.Notice]:
    """The one warning that is about a single set: its runs are not all
    one build. § 4.16 gives the base's once, not once per variant."""
    if len({(r.run.header["commit"], r.run.header["dirty"]) for r in one_set}) < 2:
        return []
    return [ledger.Notice("mixed_build", f"the {called} runs differ in commit or dirty, so they may not be "
                          "one build")]


def _differ_notices(runs: list[Named], called: dict[str, str]) -> list[ledger.Notice]:
    """§ 4.10: the two sets' medians of a load, clock or temperature field
    differ by more than its limit. Each needs the field in every run."""
    found = []
    for code, field, keys, limit, relative in DIFFERS:
        spans = [r.run.header.get(field, {}) for r in runs]
        key = next((key for key in keys if all(key in span for span in spans)), None)
        if key is None:
            continue
        values = [span[key] for span in spans]
        old, new = (statistics.median(Decimal(repr(v)) for r, v in zip(runs, values, strict=True)
                                      if r.set == label)
                    for label in ("old", "new"))
        allowed = limit * abs(old) if relative else limit  # abs: a clock below zero is not unlike itself
        if abs(new - old) > allowed:
            shown = f"{(limit * 100).normalize()}% of the {called['old']}" if relative else str(limit)
            found.append(ledger.Notice(code, f"the {called['old']} runs' median {field}.{key} is {old} and "
                                       f"the {called['new']} runs' is {new}, which differ by more than {shown}"))
    return found


def _setting_differ_notices(runs: list[Named], called: dict[str, str]) -> list[ledger.Notice]:
    """§ 4.10: the two sets were not run under the same setting. Each
    needs the field in every run; the same mix on both sides is no
    difference."""
    found = []
    for code, field in SETTINGS_DIFFER:
        if any(field not in r.run.header for r in runs):
            continue
        # Compared whole and as JSON text, so a list can sit in a set and true
        # is not 1; only the sentence cuts a long string short (Vestige).
        old, new = (sorted({_whole(r.run.header[field]) for r in runs if r.set == label})
                    for label in ("old", "new"))
        if old != new:
            shown_old, shown_new = (joined(_shown(json.loads(value)) for value in values) for values in (old, new))
            found.append(ledger.Notice(code, f"the {called['old']} runs' {field} is {shown_old} and the "
                                       f"{called['new']} runs' is {shown_new}"))
    return found


def _whole(value: object) -> str:
    """A header value as JSON text; a list sorted, since its order says
    nothing (Vestige)."""
    return json.dumps(sorted(value) if isinstance(value, list) else value)


def _shown(value: object) -> str:
    """A header value as it is quoted in a sentence: JSON, each string cut
    short."""
    if isinstance(value, list):
        return f"[{', '.join(_shown(item) for item in value)}]"
    return json.dumps(ledger.clip(value) if isinstance(value, str) else value)


def run_values(run: ledger.Run, by_segment: bool = False) -> dict[Measure, int]:
    """One value per measure for one run, in thousandths: the medians and
    the wall's 99th percentile, as `report` gives them. A mem measure's
    value is in MB, the others' in ms. With by_segment, a Measure's kind
    is the whole segment (`view:3`), and its value is over that segment's
    frames alone."""
    costs = run_report.Costs(run, by_segment)
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


def _judge_all(runs: list[Named], floors: Floors, called: dict[str, str], named_measures: tuple[str, ...] = ()
               ) -> tuple[list[dict], list[dict], list[str], list[ledger.Notice]]:
    """Every measure all runs share, judged; those only some runs have;
    the names in `named_measures` no run has; and an `outlier_run` warning
    for each run that stands apart where the frame/wall median is noisy.
    With `named_measures`, only the measures it names count, at every
    depth, kind and statistic, matched exactly. `called` is each set's
    name in a warning."""
    per_run = [run_values(r.run) for r in runs]
    absent = _absent(per_run, named_measures)
    tick = largest_tick(runs)
    measures, unmatched, outliers = [], [], []
    # In kind order, which a set does not keep, so the outlier warnings come in it.
    for measure in sorted(set().union(*per_run), key=lambda m: run_report.kind_order(m.kind)):
        if named_measures and f"{measure.category}/{measure.name}" not in named_measures:
            continue
        present = [r.name for r, values in zip(runs, per_run, strict=True) if measure in values]
        if len(present) < len(runs):
            unmatched.append({**_measure_fields(measure), "present_in": present})
            continue
        sets = {label: [(r.name, values[measure]) for r, values in zip(runs, per_run, strict=True)
                        if r.set == label] for label in ("old", "new")}
        old, new = ([value for _, value in sets[label]] for label in ("old", "new"))
        floor = change_floor(measure.category, measure.name, centre(old), floors.minimum(measure.category),
                             floors.min_pct, tick)
        judged = _judge(measure, old, new, floor)
        measures.append(judged)
        is_wall_median = (measure.category, measure.name, measure.depth, measure.statistic) == \
            ("frame", "wall", 0, "median")
        if is_wall_median and judged["verdict"] == "noisy":
            outliers += [_outlier_notice(judged, called[label], sets[label], floor) for label in ("old", "new")]
    return (sorted(measures, key=_rank), sorted(unmatched, key=_rank), absent,
            [notice for notice in outliers if notice is not None])


def _outlier_notice(wall: dict, called: str, named_values: list[tuple[str, int]],
                    floor: Fraction) -> ledger.Notice | None:
    """§ 4.10's `outlier_run` for one set of a noisy frame/wall median, or
    None: the set's highest or lowest run, when the set's range is at
    least the floor and under half as wide without that run. `wall` is the
    judged measure; `named_values` holds each run's name and value, in
    thousandths.

    In a set of three or more, no more than one run can be it. The range
    without the top run and the range without the bottom run together
    cover the whole range, so they cannot both be under half of it. Nor
    can it be an end two runs share, since dropping one leaves the other."""
    if len(named_values) < FEWEST_RUNS:
        # Two runs cannot say which of them stands apart (Vestige). No
        # command judges so small a set; this holds if one ever does.
        return None
    ordered = sorted(named_values, key=lambda named: named[1])
    width = ordered[-1][1] - ordered[0][1]
    if width == 0 or width < floor:
        return None
    for (name, value), others in ((ordered[0], ordered[1:]), (ordered[-1], ordered[:-1])):
        lowest, highest = others[0][1], others[-1][1]
        if 2 * (highest - lowest) < width:
            return ledger.Notice(
                "outlier_run",
                f"{name} stands apart from the other {called} runs: its {_label(wall)} is {value / 1000:.3f} ms "
                f"and theirs lie from {lowest / 1000:.3f} to {highest / 1000:.3f} ms; re-run it")
    return None


def absent_names(runs: list[ledger.Run], named_measures: tuple[str, ...]) -> list[str]:
    """The names in `named_measures` none of `runs` has: for runs that
    were read and never judged, such as a refused variant's."""
    return _absent([run_values(run) for run in runs], named_measures)


def _absent(per_run: list[dict[Measure, int]], named_measures: tuple[str, ...]) -> list[str]:
    found = {f"{m.category}/{m.name}" for values in per_run for m in values}
    return [n for n in named_measures if n not in found]


def _judge(measure: Measure, old: list[int], new: list[int], floor: Fraction) -> dict:
    """§ 4.10's table, in exact fractions of a thousandth. `floor` is
    change_floor's for the measure."""
    old_centre, new_centre = centre(old), centre(new)
    spread = spread_of(old, new)
    change = new_centre - old_centre
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


def _verdict(incomplete: list[str], loaded: list[str], measures: list[dict], short: list,
             named: bool = False, unmatched: list[dict] | None = None) -> tuple[str, list[str], str | None]:
    """§ 4.10's verdict, first match wins, the sentences saying it, and why
    it is inconclusive, or None. ms and MB never rank against each other,
    so slower passes and larger memory each get a sentence. `named` says
    --measure was given: then a compare that judged nothing cannot pass."""
    moved = {word: [m for m in measures if m["verdict"] == word]
             for word in ("slower", "larger", "faster", "smaller")}
    noisy_walls = [m for m in measures if (m["category"], m["name"], m["statistic"]) ==
                   ("frame", "wall", "median") and m["verdict"] == "noisy"
                   and m["segment_kind"] not in short]
    if incomplete or loaded:
        # One reason only; the sentences before this name every run of
        # both kinds. Incomplete comes first because a missing frame
        # explains a change more directly than load does (UT Ants).
        reason = ("a run is incomplete, so a change could be a missing frame" if incomplete else
                  "a run was taken under load, so its times cannot be trusted; re-run on a quieter machine")
        return "inconclusive", [f"The compare is inconclusive: {reason}."], reason
    if moved["slower"] or moved["larger"]:
        sentences = []
        if moved["slower"]:
            sentences.append(_worse_sentence("The new runs are slower", "slower", moved["slower"]))
        if moved["larger"]:
            sentences.append(_worse_sentence("The new runs use more memory", "larger", moved["larger"]))
        return "fail", sentences, None
    if noisy_walls:
        wall = noisy_walls[0]
        reason = (f"{_label(wall)} moved {wall['change']:+.3f} ms, within the runs' spread of "
                  f"{wall['spread']:.3f} ms; re-run with more runs a set")
        return "inconclusive", [f"The compare is inconclusive: {reason}."], reason
    if named and not measures:  # step 3's second half (UT Ants): never pass by judging nothing
        # Each name once, though unmatched lists it per kind, depth and statistic.
        missing = joined(dict.fromkeys(f"{m['category']}/{m['name']}" for m in unmatched or []))
        # No missing name means no run has any: a plain compare refuses
        # that first, so only a --by-scene scene, which scenes.py leaves
        # out, reaches the second reason.
        reason = (f"no named measure is in every run ({missing}), so nothing was judged" if missing else
                  "no run of this compare has a named measure, so nothing was judged")
        return "inconclusive", [f"The compare is inconclusive: {reason}."], reason
    sentence = "No measure got slower or larger between the old and new runs"
    for word in ("faster", "smaller"):
        if moved[word]:
            sentence += f"; {run_report.counted(len(moved[word]), 'measure')} got {word}"
    return "pass", [sentence + "."], None


def worst_of(measures: list[dict]) -> dict:
    """The largest change among `measures`, all in one unit; ties by
    percent. The verdict sentence names it."""
    return max(measures, key=lambda m: (m["change"], m["change_pct"] or 0))


def worse_measure(measures: list[dict]) -> dict:
    """The measure a failing scene or variant is named for: its largest
    slowdown, or without one its largest growth in memory. Only for a
    compare whose verdict is `fail`, which has one or the other."""
    worse = ([m for m in measures if m["verdict"] == "slower"]
             or [m for m in measures if m["verdict"] == "larger"])
    return worst_of(worse)


def rose_sentence(subject: str, measure: dict, where: str = "") -> str:
    """"atrium is slower: the gpu/opaque median in view rose from 3.100
    to 3.512 ms.": how § 4.14 names a failing scene and § 4.16 a failing
    variant. `where` ends the sentence, for a scene's segment."""
    opening = "is slower" if measure["verdict"] == "slower" else "uses more memory"
    return (f"{subject} {opening}: the {measure_phrase(measure)} rose from {measure['old_centre']:.3f} to "
            f"{measure['new_centre']:.3f} {measure['unit']}{where}.")


def measure_phrase(measure: dict) -> str:
    """"gpu/opaque median in view"; an unsegmented measure names no kind."""
    kind = f" in {measure['segment_kind']}" if measure["segment_kind"] else ""
    return f"{measure['category']}/{measure['name']} {measure['statistic']}{kind}"


def _worse_sentence(opening: str, word: str, measures: list[dict]) -> str:
    """Names the largest change among `measures`, all in one unit."""
    worst = worst_of(measures)
    unit = worst["unit"]
    return (f"{opening}: {run_report.counted(len(measures), 'measure')} got {word}; the largest is "
            f"{_label(worst)}, up {worst['change']:.3f} {unit}{_pct(worst)}, beyond the runs' spread of "
            f"{worst['spread']:.3f} {unit}.")


def _wall_sentences(measures: list[dict]) -> list[str]:
    return [f"In {run_report.kind_name(m['segment_kind'])} segments the median frame/wall went from "
            f"{m['old_centre']:.3f} ms to {m['new_centre']:.3f} ms ({m['verdict']})."
            for m in measures if (m["category"], m["name"], m["statistic"]) == ("frame", "wall", "median")]


def absent_sentence(absent: list[str], all_read: bool = True) -> str:
    """§ 4.10: a named measure no run has refuses the compare. Under
    --by-scene a scene's runs may go unread, and then the sentence claims
    only the runs read (DOOM Ants)."""
    pronoun = "it" if len(absent) == 1 else "they"
    runs = "run" if all_read else "run read"
    return (f"No {runs} has {joined(absent, 'or')}, so {pronoun} cannot be judged; a name matches "
            "exactly, case included.")


def joined(names, word: str = "and") -> str:
    """`a`, `a and b`, `a, b and c`: names as a sentence lists them."""
    names = list(names)
    if len(names) < 2:
        return "".join(names)
    return f"{', '.join(names[:-1])} {word} {names[-1]}"


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
