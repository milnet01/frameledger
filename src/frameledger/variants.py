"""`compare --base … --variant NAME …`: named variants, each judged
against one base (S23).

The rules are docs/specs/FLED-0001-run-file-format.md § 4.16. Each
variant is one compare.compare(), unchanged, with the base as its old
set; this module checks the names, sets aside the variants that cannot
be judged, ranks the rest by one measure's change, and counts what was
judged. One variant that cannot be judged must not hide another's
result, so nothing here stops the command but a file that cannot be
read, or no variant judged.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import NamedTuple

import compare
import ledger
import run_report

BASE = "base"
# Safe in a file name on every platform, and never another side's: a-1.csv
# is variant a's first run and no other variant's file.
NAME = re.compile(r"[a-z][a-z0-9_]{0,31}")
# Every side with a flag of its own. alternate.FLAG_SIDES lists the same
# three, to tell --base from --variant NAME: a side added there joins here.
RESERVED = (BASE, "old", "new")
DEFAULT_RANK_MEASURE = "frame/wall"


def check_names(names: list[str]) -> None:
    """Refuse a variant name § 4.16 does not allow, or one given twice."""
    for name in names:
        if not NAME.fullmatch(name):
            raise ledger.LedgerError(f"--variant {name!r} is not a variant name: lowercase ASCII letters, "
                                     "digits and _, starting with a letter, at most 32 characters")
        if name in RESERVED:
            raise ledger.LedgerError(f"--variant {name} is taken: a variant cannot be called "
                                     f"{compare.joined(RESERVED, 'or')}")
    twice = [name for name, count in Counter(names).items() if count > 1]
    if twice:
        raise ledger.LedgerError(f"--variant {twice[0]} is given twice")


class _Judged(NamedTuple):
    """One variant, judged or not."""
    entry: dict  # its entry in the result's "variants"
    warnings: list[dict]  # its compare's warnings; the result lists them apart from the entry
    loaded: list[str]  # § 4.10's sentence for each of its own runs taken under load
    # The overridden fields that differed in none of its compare's runs;
    # None when its runs were not read.
    unused: set[str] | None
    # The names in --measure's list none of its runs has, the base runs'
    # included unless it was refused; None when its runs were not read.
    absent: set[str] | None
    lacks_named: bool  # unjudged because none of its own runs has a named measure


def against_base(base: list[str], variants: dict[str, list[str]], overrides: dict[str, str],
                 floors: compare.Floors, limits: compare.LoadLimits = compare.DEFAULT_LIMITS,
                 named_measures: tuple[str, ...] = (), unread_is_unjudged: bool = False,
                 baseline: bool = False) -> dict:
    """{"verdict", "summary", "warnings", "overrides", "result"} for the
    base's files and each variant's, name to files in the order given.
    `named_measures` is --measure's list, kept in every variant; a name no
    run of any side has is an error.

    A file that cannot be read, or breaks the format, raises LedgerError.
    With `unread_is_unjudged`, `alternate`'s case, only a base file does:
    a variant with such a file is unjudged, and the others go on.
    `baseline` says the base's files came from a baseline file (§ 4.17)."""
    base_runs = [ledger.read(path) for path in base]
    for run in base_runs:
        run_report.refuse_breaches(run)
    # What is about the base alone, said once. Every variant's compare
    # repeats these, word for word, since it names the base runs the same way.
    base_named = compare.named_set("old", BASE, base_runs)
    base_notices = compare.run_notices(base_named) + compare.mixed_build_notices(base_named, BASE)
    base_warnings = run_report.warning_entries(base_notices)

    judged_all = [_judge(name, base_runs, paths, overrides, floors, limits, named_measures, unread_is_unjudged,
                         baseline)
                  for name, paths in variants.items()]
    by_name = sorted(judged_all, key=lambda j: j.entry["name"])
    entries = [j.entry for j in judged_all]
    judged = [e for e in entries if e["verdict"] != "unjudged"]
    lacking = {j.entry["name"] for j in judged_all if j.lacks_named}
    override_list = [{"field": f, "reason": r} for f, r in overrides.items()]

    # § 4.16's step 2. With no variant judged or lacking, the base runs'
    # names were in no `absent`, so step 3 speaks instead.
    absent = set(named_measures).intersection(*(j.absent for j in judged_all if j.absent is not None))
    absent_names = [n for n in named_measures if n in absent] if judged or lacking else []
    if absent_names:  # refused as a plain compare is, with nothing judged shown
        every_run_read = all(j.absent is not None for j in judged_all)
        return {"verdict": "error", "summary": [*compare.overrides_sentences(override_list),
                                                compare.absent_sentence(absent_names, every_run_read)],
                "warnings": [], "overrides": override_list,
                "result": {"named_measures": list(named_measures)}}

    rank_measure = _rank_measure(base_runs, named_measures)
    # Text groups the warnings by side, the base's and then each variant's
    # by name (`_summary`); JSON's "warnings" is the same groups, flat.
    notice_groups = [base_notices, *(_own_notices(j, base_warnings) for j in by_name),
                     compare.unused_override_notices(_unused(overrides, judged_all))]
    # A loaded base run makes every variant inconclusive, so it is named first.
    loaded = [*compare.load_sentences(base_named, limits), *(s for j in by_name for s in j.loaded)]
    entries = _ranked(entries, rank_measure)
    measures = sum(len(e["compare"]["measures"]) for e in judged)
    result = {
        "variants": entries,
        "rank_measure": None if rank_measure is None else {
            "segment_kind": rank_measure.kind, "category": rank_measure.category, "name": rank_measure.name,
            "depth": rank_measure.depth, "statistic": rank_measure.statistic},
        "judged": {"variants": len(judged), "measures": measures},
        "min_ms": float(floors.min_ms),
        "min_mb": float(floors.min_mb),
        "min_pct": float(floors.min_pct),
        "max_load": float(limits.max_load),
        "max_gpu_busy": float(limits.max_gpu_busy),
        "named_measures": list(named_measures),
        "overrides": override_list,
    }
    summary = _summary(override_list, named_measures, entries, len(judged), measures, loaded, notice_groups,
                       _rank_sentence(base_runs, rank_measure, named_measures))
    return {"verdict": _verdict(entries, lacking) if judged else "error", "summary": summary,
            "warnings": run_report.warning_entries([n for group in notice_groups for n in group]),
            "overrides": override_list, "result": result}


def _judge(name: str, base_runs: list[ledger.Run], paths: list[str], overrides: dict[str, str],
           floors: compare.Floors, limits: compare.LoadLimits, named_measures: tuple[str, ...],
           unread_is_unjudged: bool, baseline: bool) -> _Judged:
    """One variant against the base. The variant's runs are let go when
    this returns."""
    entry = {"name": name, "verdict": "unjudged", "reason": None, "rank": None, "measure": None,
             "compare": None}
    try:
        runs = [ledger.read(path) for path in paths]
        built = compare.compare(base_runs, runs, overrides, floors, limits, named_measures, sides=(BASE, name),
                                baseline=baseline)
    except ledger.LedgerError as error:  # cannot be read, or breaks the format
        if not unread_is_unjudged:
            raise
        entry["reason"] = str(error)
        return _Judged(entry, [], [], None, None, False)
    entry["compare"] = built["result"]
    unused = set(built["unused"])
    if built["verdict"] == "error":  # refused, so its compare looked for no measure
        entry["reason"] = built["reason"]
        return _Judged(entry, [], [], unused, set(compare.absent_names(runs, named_measures)), False)
    # override_unused is the command's to give, once: `_unused`.
    warnings = [w for w in built["warnings"] if w["code"] != "override_unused"]
    loaded = compare.load_sentences(compare.named_set("new", name, runs), limits)
    lacks_named = bool(named_measures) and not _own_runs_have_named(built["result"])
    if lacks_named:  # judges nothing here, by the caller's choice; its runs' warnings still stand (Vestige)
        entry["reason"] = compare.LACKS_NAMED
    else:
        entry["verdict"], entry["reason"] = built["verdict"], built["reason"]
    return _Judged(entry, warnings, loaded, unused, set(built["absent"]), lacks_named)


def _own_notices(judged: _Judged, base_warnings: list[dict]) -> list[ledger.Notice]:
    """A variant's warnings without the base's, each opening with the
    variant's name. A run's warning already opens with the run's name,
    `no_bloom-1`, and is left as it is (DOOM Ants)."""
    name = judged.entry["name"]
    return [ledger.Notice(w["code"], w["message"] if w["message"].startswith(f"{name}-")
                          else f"{name}: {w['message']}")
            for w in judged.warnings if w not in base_warnings]


def _unused(overrides: dict[str, str], judged_all: list[_Judged]) -> list[str]:
    """The overridden fields that differed in no variant whose runs were
    read; none when no variant's were, since no field was seen not to
    differ."""
    seen = [j.unused for j in judged_all if j.unused is not None]
    return [f for f in overrides if all(f in unused for unused in seen)] if seen else []


def _own_runs_have_named(result: dict) -> bool:
    """Whether any of the variant's own runs has a named measure. The base
    runs having one is not enough (Vestige): with the effect off, the
    effect's own pass is gone. `result` holds only named measures. In a
    variant's compare the variant is the "new" set and the base the "old"."""
    own = {run["name"] for run in result["runs"] if run["set"] == "new"}
    return bool(result["measures"]) or any(own & set(m["present_in"]) for m in result["unmatched"])


def _rank_measure(base_runs: list[ledger.Run], named_measures: tuple[str, ...]) -> compare.Measure | None:
    """The measure variants rank by: the first --measure name, or
    frame/wall, its median, at the smallest depth the base runs have it,
    in the segment kind with the most base frames carrying it there; ties
    by kind as text. None when no base run has it.

    This counts any frame row, where compare.run_values keeps only
    compare.FRAME_MEASURES' rows. A named frame row compare does not judge
    is in no run's values, so § 4.16's step 2 has stopped the command
    before `_rank_sentence` looks for this measure's values and finds none."""
    category, _, name = (named_measures[0] if named_measures else DEFAULT_RANK_MEASURE).partition("/")
    frames: Counter[tuple[int, str | None]] = Counter()  # (depth, kind): frames carrying the measure
    for run in base_runs:
        costs = run_report.Costs(run)
        for (kind, frame_name), values in costs.frame_values.items():
            if (category, name) == ("frame", frame_name):
                frames[(0, kind)] += len(values)
        for (kind, row_category, row_name, depth), values in (*costs.pass_values.items(),
                                                              *costs.mem_values.items()):
            if (category, name) == (row_category, row_name):
                frames[(depth, kind)] += len(values)
    if not frames:
        return None
    depth = min(depth for depth, _ in frames)
    kinds = [kind for kind_depth, kind in frames if kind_depth == depth]
    kind = min(kinds, key=lambda kind: (-frames[(depth, kind)], kind or ""))
    return compare.Measure(kind, category, name, depth, "median")


def _ranked(entries: list[dict], rank_measure: compare.Measure | None) -> list[dict]:
    """The entries with each one's rank entry and rank filled in: ranked
    variants first, by the rank measure's change, lowest first, so the
    variant that saved most is 1; ties by name. Then the others by name.
    The rank orders; it judges nothing."""
    for entry in entries:
        if rank_measure is not None and entry["verdict"] != "unjudged":
            entry["measure"] = next((m for m in entry["compare"]["measures"] if _is(m, rank_measure)), None)
    ranked = sorted((e for e in entries if e["measure"]), key=lambda e: (e["measure"]["change"], e["name"]))
    for rank, entry in enumerate(ranked, 1):
        entry["rank"] = rank
    return ranked + sorted((e for e in entries if not e["measure"]), key=lambda e: e["name"])


def _is(entry: dict, measure: compare.Measure) -> bool:
    return (entry["segment_kind"], entry["category"], entry["name"], entry["depth"],
            entry["statistic"]) == measure


def _rank_sentence(base_runs: list[ledger.Run], rank_measure: compare.Measure | None,
                   named_measures: tuple[str, ...]) -> str:
    """Names the rank measure and the base's centre of it; or says why no
    variant has a rank. A measure only some base runs have is in every
    variant's `unmatched`, so none has a rank entry (Vestige)."""
    if rank_measure is None:
        return f"Nothing is ranked: no base run has {named_measures[0] if named_measures else DEFAULT_RANK_MEASURE}."
    values = [values[rank_measure] for values in map(compare.run_values, base_runs) if rank_measure in values]
    fields = {"segment_kind": rank_measure.kind, "category": rank_measure.category, "name": rank_measure.name,
              "statistic": rank_measure.statistic}
    if len(values) < len(base_runs):
        return f"Nothing is ranked: not every base run has the {compare.measure_phrase(fields)}."
    return (f"Ranked by the {compare.measure_phrase(fields)}; base {float(compare.centre(values) / 1000):.3f} "
            f"{compare.unit_of(rank_measure.category)}.")


def _verdict(entries: list[dict], lacking: set[str]) -> str:
    """§ 4.16's steps 4 to 6, once a variant was judged. A variant in
    `lacking`, with none of the named measures, was left out by
    --measure's choice: it is unjudged, and does not make the command
    inconclusive."""
    verdicts = {e["verdict"] for e in entries if e["name"] not in lacking}
    if "fail" in verdicts:
        return "fail"
    if verdicts & {"inconclusive", "unjudged"}:
        return "inconclusive"
    return "pass"


def _summary(override_list: list[dict], named_measures: tuple[str, ...], entries: list[dict],
             judged_count: int, measures: int, loaded: list[str],
             notice_groups: list[list[ledger.Notice]], rank_sentence: str) -> list[str]:
    """§ 4.16's text sentences, in its order. `loaded` names each run
    taken under load. `notice_groups` holds the
    base runs' warnings and each variant's apart, so two variants with
    the same warning both say so."""
    summary = compare.overrides_sentences(override_list)
    if named_measures:
        summary.append(f"Judging only {compare.joined(named_measures)}.")
    by_name = sorted(entries, key=lambda e: e["name"])
    if judged_count:
        summary += [compare.rose_sentence(e["name"], compare.worse_measure(e["compare"]["measures"]))
                    for e in by_name if e["verdict"] == "fail"]
        summary += [f"{e['name']} is {e['verdict']}: {e['reason']}." for verdict in ("inconclusive", "unjudged")
                    for e in by_name if e["verdict"] == verdict]
    else:
        # A refusal's reason holds semicolons, so each reason is bracketed.
        summary.append("No variant could be judged: "
                       + ", ".join(f"{e['name']} ({e['reason']})" for e in by_name) + ".")
    summary += loaded
    for group in notice_groups:
        summary += run_report.warning_sentences(group)
    if judged_count:
        summary += [rank_sentence,
                    f"Judged {run_report.counted(judged_count, 'variant')} and "
                    f"{run_report.counted(measures, 'measure')}; with this many, a slower measure can be "
                    "chance, and a base that ran unusually fast or slow moves every variant together."]
    return summary
