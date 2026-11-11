"""`compare --by-scene`: two builds' surveys, each scene's old runs judged
against its new (S15).

The rules are docs/specs/FLED-0001-run-file-format.md § 4.14. Each scene
is one compare.compare(), unchanged; this module groups the files by
their header's `scene`, sets aside the scenes that cannot be judged and
the files that cannot be read, names where a failing scene changed most,
ranks the failing scenes, and counts what was judged. One broken map
must not hide a slowdown on another, so nothing here stops the command
but a scene count of zero.
"""

from __future__ import annotations

from collections import defaultdict

import compare
import ledger
import run_report

# Why a scene with none of --measure's names is unjudged (§ 4.14).
LACKS_NAMED = "none of its runs has a named measure"


def by_scene(old: list[str], new: list[str], overrides: dict[str, str], floors: compare.Floors,
             limits: compare.LoadLimits = compare.DEFAULT_LIMITS,
             named_measures: tuple[str, ...] = ()) -> dict:
    """{"verdict", "summary", "warnings", "overrides", "result"} for the
    files at `old` and `new`, each scene judged apart. `named_measures` is
    --measure's list, kept in every scene; a name no judged scene has is
    an error."""
    unread, paths = [], {"old": defaultdict(list), "new": defaultdict(list)}
    for label, group in (("old", old), ("new", new)):
        for path in group:
            scene, reason = _scene_of(path)
            if reason is None:
                paths[label][scene].append(path)
            else:
                unread.append({"path": path, "set": label, "reason": reason})

    scenes, unused, absent, lacking = [], set(overrides), set(named_measures), set()
    for name in sorted(set(paths["old"]) | set(paths["new"])):
        entry, scene_unused, scene_absent = _judge(name, paths["old"][name], paths["new"][name], overrides,
                                                   floors, limits, named_measures)
        scenes.append(entry)
        if scene_unused is not None:  # the scene's runs were read
            unused &= scene_unused
        if scene_absent is not None:  # judged, or read and left out for lacking every name
            absent &= scene_absent
        if entry["reason"] == LACKS_NAMED:
            lacking.add(name)
    if not any(e["compare"] for e in scenes):
        unused = set()  # no scene was read, so no field was seen not to differ

    failing = sorted((e for e in scenes if e["verdict"] == "fail"), key=_rank_key)
    for rank, entry in enumerate(failing, 1):
        entry["rank"] = rank
    scenes = failing + [e for e in scenes if e["verdict"] != "fail"]
    judged = [e for e in scenes if e["verdict"] != "unjudged"]

    override_list = [{"field": f, "reason": r} for f, r in overrides.items()]
    # Both forms are kept: text groups the warnings by scene (`_summary`),
    # and JSON's "warnings" is one flat list.
    scene_notices = [[ledger.Notice(w["code"], f"{e['scene']}: {w['message']}") for w in e.pop("warnings")]
                     for e in scenes]
    unused_notices = compare.unused_override_notices([f for f in overrides if f in unused])
    notices = [n for group in scene_notices for n in group] + unused_notices
    measures = sum(len(e["compare"]["measures"]) for e in judged)
    absent = [n for n in named_measures if n in absent] if judged or lacking else []
    if absent:  # § 4.14 step 2: refused as a plain compare is, with nothing judged shown
        return {"verdict": "error", "summary": [*compare.overrides_sentences(override_list),
                                                compare.absent_sentence(absent)],
                "warnings": [], "overrides": override_list, "result": {"named_measures": absent}}
    verdict = _verdict(scenes, unread, lacking) if judged else "error"
    summary = _summary(override_list, scenes, unread, failing, len(judged), measures,
                       [*scene_notices, unused_notices])
    result = {
        "scenes": scenes,
        "unread": unread,
        "judged": {"scenes": len(judged), "measures": measures},
        "min_ms": float(floors.min_ms),
        "min_mb": float(floors.min_mb),
        "min_pct": float(floors.min_pct),
        "overrides": override_list,
    }
    return {"verdict": verdict, "summary": summary, "warnings": run_report.warning_entries(notices),
            "overrides": override_list, "result": result}


def _summary(override_list: list[dict], scenes: list[dict], unread: list[dict], failing: list[dict],
             judged_count: int, measures: int, notice_groups: list[list[ledger.Notice]]) -> list[str]:
    """§ 4.14's text sentences, in its order. Each scene's warnings are
    grouped apart, so two scenes with the same warning both say so."""
    summary = compare.overrides_sentences(override_list)
    if judged_count:
        summary += [_fail_sentence(e) for e in failing]
        summary += [f"{e['scene']} is inconclusive: {e['reason']}." for e in scenes if e["verdict"] == "inconclusive"]
        summary += [f"{e['scene']} is unjudged: {e['reason']}." for e in scenes if e["verdict"] == "unjudged"]
        summary += [f"{u['path']} is unread: {u['reason']}." for u in unread]
    else:
        # A refusal's reason holds semicolons, so each reason is bracketed.
        reasons = [f"{e['scene']} ({e['reason']})" for e in scenes] + [f"{u['path']} ({u['reason']})" for u in unread]
        summary.append(f"No scene could be judged: {', '.join(reasons)}.")
    for group in notice_groups:
        summary += run_report.warning_sentences(group)
    if judged_count:
        summary.append(f"Judged {run_report.counted(judged_count, 'scene')} and "
                       f"{run_report.counted(measures, 'measure')}; with this many, a slower measure can be "
                       "chance (§ 4.10).")
    return summary


def _read_failure(error: ledger.LedgerError) -> str:
    """Why a file could not be read, without its path."""
    return error.reason if error.line is None else f"{error.reason} (line {error.line})"


def _scene_of(path: str) -> tuple[str | None, str | None]:
    """The file's scene, or why it is unread. The whole file is read and
    let go, so a breach anywhere in it is found before any scene is
    judged; the scene's own read comes later, one scene at a time."""
    try:
        run = ledger.read(path)
        run_report.refuse_breaches(run)
    except ledger.LedgerError as error:
        return None, _read_failure(error)
    if run.header["scene"] == "":
        return None, "the header's scene is empty, so the run belongs to no scene"
    return run.header["scene"], None


def _judge(name: str, old: list[str], new: list[str], overrides: dict[str, str], floors: compare.Floors,
           limits: compare.LoadLimits,
           named_measures: tuple[str, ...]) -> tuple[dict, set[str] | None, set[str]]:
    """One scene's entry; the overridden fields that differed in none of
    its runs, None when its runs were not read; and the names in
    `named_measures` none of its runs has: every name for a scene left
    out for lacking them all, and None for any other unjudged scene,
    which says nothing of which names it has."""
    entry = {"scene": name, "verdict": "unjudged", "reason": None, "rank": None, "measure": None,
             "segment": None, "compare": None, "warnings": []}
    missing = [label for label, paths in (("old", old), ("new", new)) if not paths]
    short = [f"the {label} side has {run_report.counted(len(paths), 'run')}"
             for label, paths in (("old", old), ("new", new)) if 0 < len(paths) < compare.FEWEST_RUNS]
    if missing:
        entry["reason"] = f"no {missing[0]} runs"
        return entry, None, None
    if short:
        entry["reason"] = f"{' and '.join(short)}; each side needs at least {compare.FEWEST_RUNS}"
        return entry, None, None

    try:
        old_runs, new_runs = [ledger.read(p) for p in old], [ledger.read(p) for p in new]
        for run in old_runs + new_runs:
            run_report.refuse_breaches(run)  # a file broken since may have no header to check
            if run.header["scene"] != name:
                raise ledger.LedgerError(f"its scene is now {run.header['scene']!r}", run.path)
        built = compare.compare(old_runs, new_runs, overrides, floors, limits, named_measures)
    except ledger.LedgerError as error:  # the file changed since it was first read
        entry["reason"] = f"{error.path} changed since it was first read: {_read_failure(error)}"
        return entry, None, None
    unused, absent = set(built["unused"]), set(built["absent"])
    if named_measures and absent == set(named_measures):  # judges nothing here, by the caller's choice
        entry["compare"], entry["reason"] = built["result"], LACKS_NAMED
        return entry, unused, absent
    entry["compare"] = built["result"]
    entry["warnings"] = [w for w in built["warnings"] if w["code"] != "override_unused"]
    if built["verdict"] == "error":  # refused
        entry["reason"] = built["reason"]
        return entry, unused, None
    entry["verdict"], entry["reason"] = built["verdict"], built["reason"]
    if built["verdict"] == "fail":
        measures = built["result"]["measures"]
        worse = [m for m in measures if m["verdict"] == "slower"] or [m for m in measures if m["verdict"] == "larger"]
        entry["measure"] = compare.worst_of(worse)
        entry["segment"] = _segment(entry["measure"], old_runs, new_runs)
    return entry, unused, absent


def _segment(measure: dict, old: list[ledger.Run], new: list[ledger.Run]) -> str | None:
    """Within the measure's segment kind, the segment whose centre rose
    most, new minus old, ties by segment as text (UT Ants). Each side's
    centre is over the runs that have the segment; a segment missing from
    every run of one side is not named. It points; it judges nothing."""
    if measure["segment_kind"] is None:
        return None
    wanted = (measure["category"], measure["name"], measure["depth"], measure["statistic"])
    sides = []
    for runs in (old, new):
        values: dict[str, list[int]] = defaultdict(list)
        for run in runs:
            for m, value in compare.run_values(run, by_segment=True).items():
                if (m.kind and run_report.segment_kind(m.kind) == measure["segment_kind"]
                        and (m.category, m.name, m.depth, m.statistic) == wanted):
                    values[m.kind].append(value)
        sides.append(values)
    changes = [(compare.centre(sides[1][s]) - compare.centre(sides[0][s]), s) for s in sides[0] if s in sides[1]]
    if not changes:
        return None
    return min(changes, key=lambda c: (-c[0], c[1]))[1]


def _rank_key(entry: dict) -> tuple:
    """§ 4.14: a slower measure before a larger mem one, then by change,
    largest first, ties by percent, then scene name."""
    m = entry["measure"]
    return m["verdict"] != "slower", -m["change"], -(m["change_pct"] or 0), entry["scene"]


def _verdict(scenes: list[dict], unread: list[dict], lacking: set[str]) -> str:
    """§ 4.14's steps 3 to 5, once a scene was judged. A scene in
    `lacking` has none of the named measures, so --measure chose to leave
    it out: it is unjudged, and does not make the command inconclusive."""
    verdicts = {e["verdict"] for e in scenes if e["scene"] not in lacking}
    if "fail" in verdicts:
        return "fail"
    if verdicts & {"inconclusive", "unjudged"} or unread:
        return "inconclusive"
    return "pass"


def _fail_sentence(entry: dict) -> str:
    m = entry["measure"]
    opening = "is slower" if m["verdict"] == "slower" else "uses more memory"
    where = f", most in {entry['segment']}" if entry["segment"] else ""
    kind = f" in {m['segment_kind']}" if m["segment_kind"] else ""
    return (f"{entry['scene']} {opening}: the {m['category']}/{m['name']} {m['statistic']}{kind} "
            f"rose from {m['old_centre']:.3f} to "
            f"{m['new_centre']:.3f} {m['unit']}{where}.")
