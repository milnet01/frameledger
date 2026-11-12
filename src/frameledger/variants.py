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

import compare
import ledger
import run_report

BASE = "base"
# Safe in a file name on every platform, and never another side's: a-1.csv
# is variant a's first run and no other variant's file.
NAME = re.compile(r"[a-z][a-z0-9_]{0,31}")
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


def against_base(base: list[str], variants: dict[str, list[str]], overrides: dict[str, str],
                 floors: compare.Floors, limits: compare.LoadLimits = compare.DEFAULT_LIMITS,
                 named_measures: tuple[str, ...] = (), unread_is_unjudged: bool = False) -> dict:
    """{"verdict", "summary", "warnings", "overrides", "result"} for the
    base's files and each variant's, name to files in the order given.
    `named_measures` is --measure's list, kept in every variant; a name no
    run of any side has is an error.

    A file that cannot be read, or breaks the format, raises LedgerError.
    With `unread_is_unjudged`, `alternate`'s case, only a base file does:
    a variant with such a file is unjudged, and the others go on."""
    base_runs = [ledger.read(path) for path in base]
    for run in base_runs:
        run_report.refuse_breaches(run)
    base_notices = compare.run_notices([compare.Named(f"{BASE}-{i}", "old", run.path, run)
                                        for i, run in enumerate(base_runs, 1)])
    shared = run_report.warning_entries(base_notices)  # every variant's compare repeats these

    entries, unused, absent = [], set(overrides), set(named_measures)
    all_seen = True  # whether every run's measure names were seen, for the absent sentence
    for name, paths in variants.items():
        entry, variant_unused, variant_absent = _judge(name, base_runs, paths, overrides, floors, limits,
                                                       named_measures, unread_is_unjudged)
        entry["warnings"] = [w for w in entry["warnings"] if w not in shared]
        entries.append(entry)
        if variant_unused is not None:  # the variant's runs were read
            unused &= variant_unused
        if variant_absent is not None:
            absent &= variant_absent
        else:
            all_seen = False
    if not any(e["compare"] for e in entries):
        unused = set()  # no variant was read, so no field was seen not to differ

    judged = [e for e in entries if e["verdict"] != "unjudged"]
    lacking = [e for e in entries if e["reason"] == compare.LACKS_NAMED]
    override_list = [{"field": f, "reason": r} for f, r in overrides.items()]
    absent_names = [n for n in named_measures if n in absent] if judged or lacking else []
    if absent_names:  # refused as a plain compare is, with nothing judged shown
        return {"verdict": "error", "summary": [*compare.overrides_sentences(override_list),
                                                compare.absent_sentence(absent_names, all_seen)],
                "warnings": [], "overrides": override_list,
                "result": {"named_measures": list(named_measures)}}

    rank_measure = _rank_measure(base_runs, named_measures)
    entries = _ranked(entries, rank_measure)
    # Both forms are kept: text groups the warnings by variant (`_summary`),
    # and JSON's "warnings" is one flat list.
    notice_groups = [base_notices,
                     *([ledger.Notice(w["code"], f"{e['name']}: {w['message']}") for w in e.pop("warnings")]
                       for e in entries),
                     compare.unused_override_notices([f for f in overrides if f in unused])]
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
    summary = _summary(override_list, named_measures, entries, len(judged), measures, notice_groups,
                       _rank_sentence(base_runs, rank_measure, named_measures))
    return {"verdict": _verdict(entries) if judged else "error", "summary": summary,
            "warnings": run_report.warning_entries([n for group in notice_groups for n in group]),
            "overrides": override_list, "result": result}


def _judge(name: str, base_runs: list[ledger.Run], paths: list[str], overrides: dict[str, str],
           floors: compare.Floors, limits: compare.LoadLimits, named_measures: tuple[str, ...],
           unread_is_unjudged: bool) -> tuple[dict, set[str] | None, set[str] | None]:
    """One variant's entry; the overridden fields that differed in none of
    its compare's runs, None when its runs were not read; and the names in
    `named_measures` no run of its compare has, None for a variant not
    read or refused, which says nothing of which names it has. The
    variant's runs are let go when this returns."""
    entry = {"name": name, "verdict": "unjudged", "reason": None, "rank": None, "measure": None,
             "compare": None, "warnings": []}
    try:
        built = compare.compare(base_runs, [ledger.read(path) for path in paths], overrides, floors, limits,
                                named_measures, sides=(BASE, name))
    except ledger.LedgerError as error:
        if not unread_is_unjudged:
            raise
        entry["reason"] = str(error)
        return entry, None, None
    entry["compare"] = built["result"]
    unused = set(built["unused"])
    if built["verdict"] == "error":  # refused
        entry["reason"] = built["reason"]
        return entry, unused, None
    if named_measures and not _own_runs_have_named(built["result"]):
        entry["reason"] = compare.LACKS_NAMED  # judges nothing here, by the caller's choice
        return entry, unused, set(built["absent"])
    entry["verdict"], entry["reason"] = built["verdict"], built["reason"]
    entry["warnings"] = [w for w in built["warnings"] if w["code"] != "override_unused"]
    return entry, unused, set(built["absent"])


def _own_runs_have_named(result: dict) -> bool:
    """Whether any of the variant's own runs has a named measure. The base
    runs having one is not enough (Vestige): with the effect off, the
    effect's own pass is gone. `result` holds only named measures."""
    own = {run["name"] for run in result["runs"] if run["set"] == "new"}
    return bool(result["measures"]) or any(own & set(m["present_in"]) for m in result["unmatched"])


def _rank_measure(base_runs: list[ledger.Run], named_measures: tuple[str, ...]) -> compare.Measure | None:
    """The measure variants rank by: the first --measure name, or
    frame/wall, its median, at the smallest depth the base runs have it,
    in the segment kind with the most base frames carrying it there; ties
    by kind as text. None when no base run has it."""
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
    """Names the rank measure and the base's centre of it, over the base
    runs that have it."""
    if rank_measure is None:
        return f"Nothing is ranked: no base run has {named_measures[0] if named_measures else DEFAULT_RANK_MEASURE}."
    values = [values[rank_measure] for values in map(compare.run_values, base_runs) if rank_measure in values]
    fields = {"segment_kind": rank_measure.kind, "category": rank_measure.category, "name": rank_measure.name,
              "statistic": rank_measure.statistic}
    return (f"Ranked by the {compare.measure_phrase(fields)}; base {float(compare.centre(values) / 1000):.3f} "
            f"{compare.unit_of(rank_measure.category)}.")


def _verdict(entries: list[dict]) -> str:
    """§ 4.16's steps 4 to 6, once a variant was judged. A variant with
    none of the named measures was left out by --measure's choice: it is
    unjudged, and does not make the command inconclusive."""
    verdicts = {e["verdict"] for e in entries if e["reason"] != compare.LACKS_NAMED}
    if "fail" in verdicts:
        return "fail"
    if verdicts & {"inconclusive", "unjudged"}:
        return "inconclusive"
    return "pass"


def _summary(override_list: list[dict], named_measures: tuple[str, ...], entries: list[dict],
             judged_count: int, measures: int, notice_groups: list[list[ledger.Notice]],
             rank_sentence: str) -> list[str]:
    """§ 4.16's text sentences, in its order. The base runs' warnings and
    each variant's are grouped apart, so two variants with the same
    warning both say so."""
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
    for group in notice_groups:
        summary += run_report.warning_sentences(group)
    if judged_count:
        summary += [rank_sentence,
                    f"Judged {run_report.counted(judged_count, 'variant')} and "
                    f"{run_report.counted(measures, 'measure')}; with this many, a slower measure can be "
                    "chance, and a base that ran unusually fast or slow moves every variant together."]
    return summary
