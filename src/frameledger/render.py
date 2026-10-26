"""Turn a command's result into plain text or JSON.

Both forms come from the one result dict cli.py builds, so they cannot
disagree: the text opens with the result's `summary` sentences, in order.
"""

from __future__ import annotations

import json


def to_json(result: dict) -> str:
    return json.dumps(result, indent=2) + "\n"


def to_text(result: dict) -> str:
    lines = list(result["summary"])
    body = _BODIES.get(result["command"], _no_body)(result)
    if body:
        lines += ["", *body]
    return "\n".join(lines) + "\n"


def _no_body(result: dict) -> list[str]:
    return []


def _check_body(result: dict) -> list[str]:
    lines = []
    for entry in result["result"]["files"]:
        if entry["breaches"]:
            lines.append(f"Breaches in {entry['path']}:")
            lines += [f"  line {b['line']}: {b['message']} ({b['rule']})" for b in entry["breaches"]]
    if result["warnings"]:
        lines.append("Warnings:")
        lines += [f"  {w['message']} ({w['code']})" for w in result["warnings"]]
    return lines


def _selftest_body(result: dict) -> list[str]:
    return [f"  {'ok  ' if c['pass'] else 'FAIL'}  {c['name']}" for c in result["result"]["checks"]]


WIDTH = 100  # § 4.8: tables no wider than 100 columns
STATIC_LINES = 20  # UT Ants' review: a large static line must not bury the ranking
SLOW_FRAMES = 10  # the text lists this many; --json lists every one


def _report_body(result: dict) -> list[str]:
    report = result["result"]
    if not report:  # an error: the opening sentences say why
        return []
    lines = []
    for (kind, category), passes in _groups(report["passes"], ("segment_kind", "category")):
        lines += [f"{category.upper()} passes in {_kind_name(kind)} segments, by time spent:",
                  _row("pass", "median ms", "p99 ms", "share", "frames")]
        lines += [_row("  " * p["depth"] + p["name"], f"{p['median_ms']:.3f}", f"{p['p99_ms']:.3f}",
                       "-" if p["share"] is None else f"{p['share'] * 100:.1f}%", str(p["frames"]))
                  for p in passes]
        lines.append("")
    for (kind,), times in _groups(report["frame_times"], ("segment_kind",)):
        lines += [f"Frame times in {_kind_name(kind)} segments:", _row("measure", "median ms", "p99 ms", "", "frames")]
        lines += [_row(t["name"], f"{t['median_ms']:.3f}", f"{t['p99_ms']:.3f}", "", str(t["frames"]))
                  for t in times]
        lines.append("")
    if report["worst_frames"]:
        lines += ["Worst frames, longest first:", *_frame_table(report["worst_frames"]), ""]
    if report["static"]:
        lines += ["Static facts, as the engine wrote them:", *_static_lines(report["static"])]
    while lines and not lines[-1]:
        lines.pop()
    return lines


def _floor_body(result: dict) -> list[str]:
    floor = result["result"]
    if not floor:  # an error: the opening sentences say why
        return []
    lines = []
    failed = [w for w in floor["windows"] if not w["pass"]]
    if failed:
        lines += ["Windows below the frame rate:", f"  {'start s':>10}  {'frames':>8}  {'mean ms':>10}"]
        lines += [f"  {w['start_s']:>10.3f}  {w['fps']:>8}  "
                  + (f"{w['mean_ms']:>10.3f}" if w["mean_ms"] is not None else f"{'none':>10}") for w in failed]
        lines.append("")
    if floor["slow_frames"]:
        slow = sorted(floor["slow_frames"], key=lambda f: (-f["wall_ms"], f["frame"]))
        lines += ["Frames over the budget, longest first:", *_frame_table(slow[:SLOW_FRAMES])]
        if len(slow) > SLOW_FRAMES:
            lines.append(f"  {len(slow) - SLOW_FRAMES} more: see --json.")
    while lines and not lines[-1]:
        lines.pop()
    return lines


def _compare_body(result: dict) -> list[str]:
    compared = result["result"]
    if not compared:  # an error: the opening sentences say why
        return []
    lines = ["Runs:", *[_fit(f"  {r['name']:<8}  {r['path']}", WIDTH) for r in compared["runs"]], ""]
    if compared["refused"]:
        return lines[:-1]
    changed = [m for m in compared["measures"] if m["verdict"] != "unchanged"]
    if changed:
        lines += ["Measures that moved or are too noisy to judge, old and new as the runs' median:",
                  _measure_row("measure", "old ms", "new ms", "change", "spread", "verdict")]
        lines += [_measure_row(_measure_name(m), f"{m['old_centre_ms']:.3f}", f"{m['new_centre_ms']:.3f}",
                               f"{m['change_ms']:+.3f}", f"{m['spread_ms']:.3f}", m["verdict"])
                  for m in changed]
    unchanged = len(compared["measures"]) - len(changed)
    lines += [f"{unchanged} of {len(compared['measures'])} measures unchanged.", ""]
    if compared["unmatched"]:
        lines.append("Not in every run, so not judged:")
        lines += [_fit(f"  {_measure_name(m)}: only in {', '.join(m['present_in'])}", WIDTH)
                  for m in compared["unmatched"]]
        lines.append("")
    diff = compared["static_diff"]
    if diff:
        lines.append("Static facts that differ between runs:")
        lines += [_fit(f"  {d['key']}: " + ", ".join(f"{name} {_fact(value)}"
                                                      for name, value in d["values"].items()), WIDTH)
                  for d in diff[:STATIC_LINES]]
        if len(diff) > STATIC_LINES:
            lines.append(f"  {len(diff) - STATIC_LINES} more: see --json.")
    while lines and not lines[-1]:
        lines.pop()
    return lines


def _bisect_body(result: dict) -> list[str]:
    bisected = result["result"]
    if not bisected or not bisected["runs"]:  # an error, or a dry run: the sentences say it all
        return []
    unit = bisected["measure"]["unit"]
    lines = [f"Runs, with their {unit}:"]
    lines += [_fit(f"  {r['name']:<8}  {'-' if r['value'] is None else format(r['value'], '.3f'):>14}  "
                   f"{r['path']}", WIDTH) for r in bisected["runs"]]
    return lines


def _measure_row(name: str, old: str, new: str, change: str, spread: str, verdict: str) -> str:
    return f"  {_fit(name, 40):<40}  {old:>10}  {new:>10}  {change:>10}  {spread:>10}  {verdict}"


def _measure_name(measure: dict) -> str:
    statistic = " p99" if measure["statistic"] == "p99" else ""
    indent = "  " * measure["depth"]
    return f"{_kind_name(measure['segment_kind'])}: {indent}{measure['category']}/{measure['name']}{statistic}"


def _fact(value) -> str:
    return "absent" if value is None else value if isinstance(value, str) else json.dumps(value)


def _frame_table(frames: list[dict]) -> list[str]:
    lines = [f"  {'frame':>10}  {'segment':<30}  {'wall ms':>12}  top pass"]
    lines += [f"  {w['frame']:>10}  {_fit(w['segment'] or '-', 30):<30}  {w['wall_ms']:>12.3f}  "
              f"{_fit(w['top_pass'] or '-', 36)}" for w in frames]
    return lines


def _row(name: str, median: str, p99: str, share: str, frames: str) -> str:
    return f"  {_fit(name, 50):<50}  {median:>12}  {p99:>12}  {share:>6}  {frames:>8}"


def _groups(entries: list[dict], keys: tuple) -> list[tuple[tuple, list[dict]]]:
    """Consecutive entries sharing `keys`, in the order the result ranks them."""
    groups: list[tuple[tuple, list[dict]]] = []
    for entry in entries:
        key = tuple(entry[k] for k in keys)
        if not groups or groups[-1][0] != key:
            groups.append((key, []))
        groups[-1][1].append(entry)
    return groups


def _static_lines(static: dict) -> list[str]:
    """An engine's optional "summary" object is printed whole; otherwise the
    first STATIC_LINES facts. The rest are counted and left to --json."""
    facts = _flatten(static)
    if isinstance(static.get("summary"), dict):
        shown = [f for f in facts if f[0].startswith("summary.")]
    else:
        shown = facts[:STATIC_LINES]
    lines = [_fit(f"  {key}: {value}", WIDTH) for key, value in shown]
    if len(facts) > len(shown):
        lines.append(f"  {len(facts) - len(shown)} more static facts: see --json.")
    return lines


def _flatten(value, prefix: str = "") -> list[tuple[str, str]]:
    if isinstance(value, dict):
        items = value.items()
    elif isinstance(value, list):
        items = ((f"[{i}]", item) for i, item in enumerate(value))
    else:
        return [(prefix, value if isinstance(value, str) else json.dumps(value))]
    facts = []
    for key, item in items:
        joined = f"{prefix}{key}" if key.startswith("[") or not prefix else f"{prefix}.{key}"
        facts += _flatten(item, joined)
    return facts


def _fit(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 3] + "..."


def _kind_name(kind: str | None) -> str:
    return kind or "unsegmented"


_BODIES = {"check": _check_body, "report": _report_body, "floor": _floor_body,
           "compare": _compare_body, "bisect": _bisect_body, "selftest": _selftest_body}
