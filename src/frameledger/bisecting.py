"""One commit's verdict for `git bisect run` (S17).

The rules are docs/specs/FLED-0001-run-file-format.md § 4.11. One
measure is judged against a threshold, or against the midpoint of good
and bad reference runs, with compare.py's judging of a measure (§ 4.10).
The verdict is good, bad, skip or stop; VERDICT_CODES holds the exit
code each means. A check that fails raises _Stop or _Skip, and bisect()
builds the one result from what was settled before it.
"""

from __future__ import annotations

from decimal import Decimal
from fractions import Fraction
from typing import NamedTuple

import compare
import ledger
import run_report
import stats

# git bisect run reads 0 as good and every code from 1 to 127 but 125 as
# bad, so whatever is not a verdict must be 128.
VERDICT_CODES = {"good": 0, "bad": 1, "skip": 125, "stop": 128}
STOP_SENTENCE = "The bisect stops (exit 128)."
SKIP_SENTENCE = "This commit is skipped (exit 125)."
FRAME_NAMES = ("wall", "cpu_span", "gpu_span")  # § 4.10's frame measures
CATEGORIES = ("frame", "cpu", "gpu", "mem")
FEWEST_REFERENCES = compare.FEWEST_RUNS  # one noisy reference would move the line for every commit


class Wanted(NamedTuple):
    """The one measure a bisect judges, and the frames it is taken over:
    a segment kind (--kind), one segment (--segment), or, with both None,
    frames with no segment."""
    category: str
    name: str
    statistic: str  # "median" or "p99"
    depth: int | None  # None: the one depth every run has the name at
    kind: str | None
    segment: str | None

    @property
    def unit(self) -> str:
        return compare.unit_of(self.category)

    @property
    def label(self) -> str:
        where = (f"segment {self.segment}" if self.segment else
                 f"{self.kind} segments" if self.kind else "frames with no segment")
        depth = "" if self.depth is None else f" at depth {self.depth}"
        return f"{self.category}/{self.name}{depth} {self.statistic} in {where}"


class Loaded(NamedTuple):
    """One run file as cli.py read it: its Run, or why it could not be read."""
    path: str
    run: ledger.Run | None
    error: str | None  # the reason alone; sentences never name a path


class _Run(NamedTuple):
    """A run with its bisect name (good-1, tested-2). It has compare.Named's
    fields, which compare's helpers read, and why it could not be read."""
    name: str
    set: str  # "good", "bad" or "tested"
    path: str
    run: ledger.Run | None
    error: str | None


class _References(NamedTuple):
    values: dict[str, int]  # each reference's value, in thousandths
    depth: int | None
    good_centre: Fraction
    bad_centre: Fraction
    spread: int
    floor: Fraction
    midpoint: Fraction


class _Stop(Exception):
    """The bisect cannot go on. The message is the sentence saying why; a
    refusal also carries § 4.10's `refused` entries."""

    def __init__(self, sentence: str, refused: list[dict] | None = None):
        super().__init__(sentence)
        self.refused = refused or []


class _Skip(Exception):
    """This commit cannot be judged: one sentence per run that says why."""

    def __init__(self, sentences: list[str]):
        super().__init__(" ".join(sentences))
        self.sentences = sentences


def bisect(wanted: Wanted, tested: list[Loaded], good: list[Loaded], bad: list[Loaded],
           overrides: dict[str, str], floors: compare.Floors, bad_above: Decimal | None = None,
           dry_value: Decimal | None = None, skip_straddle: bool = False) -> dict:
    """{"verdict", "summary", "warnings", "overrides", "result"} for one
    commit. Reference mode when `good` and `bad` are given, threshold mode
    with `bad_above`; `dry_value` stands in for the tested runs. cli.py has
    checked the flags."""
    refs = _named("good", good) + _named("bad", bad)
    tested_runs = _named("tested", tested)
    override_list = [{"field": f, "reason": r} for f, r in overrides.items()]
    values: dict[str, int] = {}  # each run's value of the measure, in thousandths
    references = None
    line = None
    notices: list[ledger.Notice] = []
    try:
        if refs:
            references = _judge_references(wanted, refs, overrides, floors)
            values.update(references.values)
            line = references.midpoint
        else:
            line = Fraction(bad_above) * 1000
        if dry_value is None:
            depth = references.depth if references else None
            values.update(_tested_values(wanted, refs, tested_runs, overrides, depth))
            value = compare.centre([values[r.name] for r in tested_runs])
            notices = _tested_notices(refs, tested_runs, overrides)
            straddle = _straddle(tested_runs, values, line, wanted.unit)
            if straddle and skip_straddle:
                raise _Skip([f"The tested runs fall on both sides of the line: {straddle}."])
            if straddle:
                notices.append(ledger.Notice("tested_straddle", "the tested runs fall on both sides of "
                                             f"{_shown(line, wanted.unit)}: {straddle}"))
        else:
            value = Fraction(dry_value) * 1000
            notices = _unused_overrides(refs, overrides)
    except _Stop as stop:
        verdict, sentences, value, refused = "stop", [str(stop), STOP_SENTENCE], None, stop.refused
    except _Skip as skip:
        verdict, sentences, value, refused = "skip", [*skip.sentences, SKIP_SENTENCE], None, []
    else:
        verdict, refused = ("bad" if value > line else "good"), []
        sentences = [*run_report.warning_sentences(notices),
                     _verdict_sentence(wanted, value, line, references, dry_value is not None)]
    result = {
        "measure": {"segment_kind": wanted.segment.partition(":")[0] if wanted.segment else wanted.kind,
                    "segment": wanted.segment, "category": wanted.category, "name": wanted.name,
                    "depth": wanted.depth, "statistic": wanted.statistic, "unit": wanted.unit},
        "dry_run": dry_value is not None,
        "runs": [_entry(r, values.get(r.name)) for r in refs + tested_runs],
        "value": None if value is None else _number(value),
        "bad_above": None if line is None else _number(line),
        "references": None if references is None else {
            "good_centre": _number(references.good_centre), "bad_centre": _number(references.bad_centre),
            "spread": _number(references.spread), "floor": _number(references.floor)},
        "refused": refused,
    }
    return {"verdict": verdict, "summary": compare.overrides_sentences(override_list) + sentences,
            "warnings": run_report.warning_entries(notices), "overrides": override_list, "result": result}


def _named(label: str, loaded: list[Loaded]) -> list[_Run]:
    return [_Run(f"{label}-{i}", label, item.path, item.run, item.error) for i, item in enumerate(loaded, 1)]


def _judge_references(wanted: Wanted, refs: list[_Run], overrides: dict[str, str],
                      floors: compare.Floors) -> _References:
    """The references' values and midpoint, once every reference check of
    § 4.11 has passed."""
    for label in ("good", "bad"):
        count = sum(r.set == label for r in refs)
        if count < FEWEST_REFERENCES:
            raise _Stop(f"The {label} references are {run_report.counted(count, 'run')}; each set needs "
                        f"at least {FEWEST_REFERENCES}, since one noisy reference would move the line "
                        "for every commit.")
    for r in refs:
        problem = _unreadable(r) or _incomplete(r)
        if problem:
            raise _Stop(f"{r.name} is a broken reference file: {problem}.")
    refused, _ = compare.refusals(refs, overrides)
    if refused:
        raise _Stop(compare.refusal_sentence(refused), refused)
    found = {r.name: _times_by_depth(wanted, r.run) for r in refs}
    depth = _one_depth(wanted, found)
    values = {}
    for r in refs:
        value = _value(wanted, found[r.name], depth)
        if value is None:
            raise _Stop(f"{r.name} has no {wanted.label}, so it cannot be a reference.")
        values[r.name] = value

    good = [values[r.name] for r in refs if r.set == "good"]
    bad = [values[r.name] for r in refs if r.set == "bad"]
    good_centre, bad_centre = compare.centre(good), compare.centre(bad)
    spread = compare.spread_of(good, bad)
    # The good runs are the old: the floor's percent is of the good centre.
    minimum = floors.minimum(wanted.category)
    floor = compare.change_floor(wanted.category, wanted.name, good_centre, minimum, floors.min_pct,
                                 compare.largest_tick(refs))
    unit = wanted.unit
    centres = (f"the bad runs' centre of {_shown(bad_centre, unit)} against the good runs' "
               f"{_shown(good_centre, unit)}")
    if compare.change_verdict(bad_centre - good_centre, spread, floor) != "slower":
        if bad_centre < good_centre:
            raise _Stop(f"The references are the wrong way round: {centres}.")
        raise _Stop(f"The references do not separate: {centres} is not above the spread of "
                    f"{_shown(spread, unit)} and at least the floor of {_shown(floor, unit)}.")

    midpoint = (good_centre + bad_centre) / 2
    # A good run above the midpoint, or a bad one at it or below, would itself be misjudged (Vestige).
    wrong = [r for r in refs
             if (values[r.name] > midpoint if r.set == "good" else values[r.name] <= midpoint)]
    if wrong:
        listed = ", ".join(f"{r.name} at {_shown(values[r.name], unit)}" for r in wrong)
        raise _Stop(f"The references straddle their own midpoint of {_shown(midpoint, unit)}: {listed}, "
                    "so a run like it would be misjudged.")
    return _References(values, depth, good_centre, bad_centre, spread, floor, midpoint)


def _tested_values(wanted: Wanted, refs: list[_Run], tested_runs: list[_Run], overrides: dict[str, str],
                   ref_depth: int | None) -> dict[str, int]:
    """Each tested run's value, once every one of them can be judged."""
    unreadable = [f"{r.name} cannot be judged: {problem}." for r in tested_runs
                  if (problem := _unreadable(r))]
    if unreadable:
        raise _Skip(unreadable)
    refused, _ = compare.refusals(refs + tested_runs, overrides)
    if refused:
        raise _Stop(compare.refusal_sentence(refused), refused)
    incomplete = [f"{r.name} cannot be judged: {problem}." for r in tested_runs
                  if (problem := _incomplete(r))]
    if incomplete:
        raise _Skip(incomplete)
    found = {r.name: _times_by_depth(wanted, r.run) for r in tested_runs}
    depth = _one_depth(wanted, found, ref_depth if refs else None)
    values = {r.name: _value(wanted, found[r.name], depth) for r in tested_runs}
    missing = [f"{r.name} has no {wanted.label}; {_frames_it_has(wanted, r.run)}." for r in tested_runs
               if values[r.name] is None]
    if missing:
        raise _Skip(missing)
    return values


def _unreadable(r: _Run) -> str | None:
    """Why a run cannot be read or breaks the format, or None. A run that
    breaks the format may have no header, so nothing reads one before this."""
    if r.run is None:
        return f"it cannot be read ({r.error})"
    if r.run.breaches:
        first = r.run.breaches[0]
        return f"it breaks the run-file format at line {first.line}: {first.message}"
    return None


def _incomplete(r: _Run) -> str | None:
    """Why a conforming run's rows cannot all be trusted, or None (docs/design.md:
    "nor a compare that uses them")."""
    if r.run.close is None:
        return "it has no close line, so the run did not finish"
    if r.run.close["rows_dropped"]:
        return f"the writer dropped {run_report.counted(r.run.close['rows_dropped'], 'row')}"
    return None


def _times_by_depth(wanted: Wanted, run: ledger.Run) -> dict[int | None, list[int]]:
    """The measure's per-frame values over the chosen frames, by depth. A
    frame measure has no depth to pick, so its one key is None."""
    costs = run_report.Costs(run, by_segment=wanted.segment is not None)
    group = wanted.segment if wanted.segment is not None else wanted.kind
    if wanted.category == "frame":
        times = costs.frame_values.get((group, wanted.name))
        return {None: times} if times else {}
    source = costs.mem_values if wanted.category == "mem" else costs.pass_values
    return {depth: times for (g, category, name, depth), times in source.items()
            if (g, category, name) == (group, wanted.category, wanted.name) and times}


def _one_depth(wanted: Wanted, found: dict[str, dict[int | None, list[int]]],
               settled: int | None = None) -> int | None:
    """The depth every run's value is taken at: --depth, or the one depth
    every run that has the name has it at, and the references' when they
    have settled one (Vestige, DOOM Ants)."""
    if wanted.depth is not None or wanted.category == "frame":
        return wanted.depth
    depths = {name: sorted(by_depth) for name, by_depth in found.items() if by_depth}
    every = {d for ds in depths.values() for d in ds} | ({settled} if settled is not None else set())
    if len(every) > 1:
        listed = "; ".join(f"{name} at {' and '.join(map(str, ds))}" for name, ds in depths.items())
        if settled is not None:
            listed += f"; the references at {settled}"
        raise _Stop(f"{wanted.category}/{wanted.name} is at more than one depth ({listed}); "
                    "--depth picks one.")
    return next(iter(every), None)


def _value(wanted: Wanted, by_depth: dict[int | None, list[int]], depth: int | None) -> int | None:
    """One run's value, in thousandths, or None when it has none there.
    Its median is report's nearest rank, not compare.centre (§ 4.11)."""
    times = by_depth.get(depth)
    if not times:
        return None
    return stats.percentile(times, stats.RANKS[wanted.statistic])


def _frames_it_has(wanted: Wanted, run: ledger.Run) -> str:
    """The segments, or segment kinds, a run has: so a wrong --kind or
    --segment shows on the first skip (UT Ants)."""
    segments = {ledger.frame_segment(rows) for rows in run.frames.values()}
    if wanted.segment is not None:
        named = sorted(s for s in segments if s)
        return f"its segments are {', '.join(named) or 'none'}"
    kinds = sorted({run_report.segment_kind(s) for s in segments}, key=run_report.kind_order)
    return f"its segment kinds are {', '.join(run_report.kind_name(k) for k in kinds) or 'none'}"


def _tested_notices(refs: list[_Run], tested_runs: list[_Run], overrides: dict[str, str]) -> list[ledger.Notice]:
    """§ 4.9's warnings for each tested run, then override_unused and dirty_build."""
    notices = [n for n in compare.run_notices(tested_runs) if n.code not in compare.INCOMPLETE_CODES]
    notices += _unused_overrides(refs + tested_runs, overrides)
    notices += [ledger.Notice("dirty_build", f"{r.name}: the build had uncommitted changes, so it may "
                              "not be the commit under test") for r in tested_runs if r.run.header["dirty"]]
    return notices


def _unused_overrides(runs: list[_Run], overrides: dict[str, str]) -> list[ledger.Notice]:
    _, unused = compare.refusals(runs, overrides)
    return compare.unused_override_notices(unused)


def _straddle(tested_runs: list[_Run], values: dict[str, int], line: Fraction, unit: str) -> str:
    """Each tested run and its value when some are above the line and some
    at it or below; empty otherwise. One run cannot straddle."""
    above = [values[r.name] > line for r in tested_runs]
    if all(above) or not any(above):
        return ""
    return ", ".join(f"{r.name} {_shown(values[r.name], unit)}" for r in tested_runs)


def _verdict_sentence(wanted: Wanted, value: Fraction, line: Fraction, references: _References | None,
                      dry_run: bool) -> str:
    unit = wanted.unit
    side = "above" if value > line else "at or below"
    outcome = "bad (exit 1)" if value > line else "good (exit 0)"
    if references is None:
        against = f"the threshold of {_shown(line, unit)}"
    else:
        against = (f"the midpoint of {_shown(line, unit)} between the good runs' "
                   f"{_shown(references.good_centre, unit)} and the bad runs' "
                   f"{_shown(references.bad_centre, unit)}")
    if dry_run:
        return f"Dry run: {wanted.label} of {_shown(value, unit)} would be {side} {against}: {outcome}."
    return f"{wanted.label} is {_shown(value, unit)}, {side} {against}: {outcome}."


def _entry(r: _Run, value: int | None) -> dict:
    """§ 4.11's run entry. A run that could not be read, or breaks the
    format, may have no header, so it gives only its name, set and path."""
    if r.run is None or r.run.breaches:
        entry = {"name": r.name, "set": r.set, "path": r.path, "run_id": None, "commit": None,
                 "dirty": None, "rows_dropped": None, "finished": None}
    else:
        entry = {key: item for key, item in compare.run_entry(r).items() if key != "started_utc"}
    return {**entry, "value": None if value is None else _number(value)}


def _exact(thousandths: Fraction | int) -> Decimal:
    """A value in the measure's unit, exactly, with at least three places.
    Every value here is thousandths over a power of 2 and 5 (halves,
    quarters, percents), so it is a finite decimal."""
    fraction = Fraction(thousandths) / 1000
    value = Decimal(fraction.numerator) / Decimal(fraction.denominator)
    return value if value.as_tuple().exponent <= -3 else value.quantize(Decimal("0.001"))


def _number(thousandths: Fraction | int) -> float:
    return float(_exact(thousandths))


def _shown(thousandths: Fraction | int, unit: str) -> str:
    return f"{_exact(thousandths)} {unit}"
