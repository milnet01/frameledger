"""Turn a command's result into plain text, Markdown or JSON.

All three come from the one result dict cli.py builds, so they cannot
disagree: text and Markdown open with the result's `summary` sentences,
in order. Each command's body is a list of blocks, a line of prose or a
Table, which the text and the Markdown each lay out in their own way
(docs/specs/FLED-0001-run-file-format.md § 4.8).
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass

WIDTH = 100  # § 4.8: text tables no wider than 100 columns
GAP = 2  # spaces between a per-run table's columns
STATIC_LINES = 20  # UT Ants' review: a large static line must not bury the ranking
SLOW_FRAMES = 10  # the text lists this many; --json lists every one


def _same(text: str) -> str:
    return text


@dataclass
class Column:
    header: str
    width: int = 0  # the text pads the column to this; 0 leaves it unpadded
    right: bool = False  # aligned right, in text and in Markdown
    fit: Callable[[str], str] = _same  # how the text shortens a long cell


@dataclass
class Table:
    title: str | None
    columns: list[Column]
    rows: list[list[str]]
    # The text's own layout of the rows, for a table it prints as a list
    # rather than in columns. None lays the text out in columns, header first.
    # Markdown ignores it: every table is a pipe table there.
    text_layout: Callable[[Table], list[str]] | None = None


Block = str | Table  # a str is one line of prose; "" is a blank line in the text


def to_json(result: dict) -> str:
    return json.dumps(result, indent=2) + "\n"


def to_text(result: dict) -> str:
    lines = list(result["summary"])
    body = _text_lines(_body(result))
    if body:
        lines += ["", *body]
    return "\n".join(lines) + "\n"


def to_markdown(result: dict) -> str:
    """§ 4.8's Markdown: the sentences as a list, then each block apart."""
    sentences = "\n".join(f"- {_line_start(_escape(s))}" for s in result["summary"])
    parts = [sentences, *(_markdown_block(block) for block in _body(result))]
    return "\n\n".join(part for part in parts if part) + "\n"


def _body(result: dict) -> list[Block]:
    return _BODIES.get(result["command"], _no_body)(result)


def _text_lines(blocks: list[Block]) -> list[str]:
    lines = []
    for block in blocks:
        if isinstance(block, str):
            lines.append(block)
            continue
        if block.title is not None:
            lines.append(block.title)
        lines += block.text_layout(block) if block.text_layout else _column_lines(block)
    return lines


def _column_lines(table: Table) -> list[str]:
    def line(cells: list[str]) -> str:
        return "  " + "  ".join(f"{c.fit(cell):>{c.width}}" if c.right else f"{c.fit(cell):<{c.width}}"
                                for c, cell in zip(table.columns, cells, strict=True))
    return [line([c.header for c in table.columns]), *map(line, table.rows)]


# Markdown (§ 4.8). A backslash before each of these, so engine text such as
# a path or a static value cannot format the output or split a cell. An
# underscore inside a word cannot format, so shadow_map stays as it is.
_ALNUM = r"[^\W_]"  # a letter or a digit, not an underscore
_SPECIAL = re.compile(rf"[\\`*~&<\[\]|$]|(?<!{_ALNUM})_|_(?!{_ALNUM})")
# What would make a line a heading, a quotation or a list. All but > need a
# space or the line's end after them, so "100.0% of frames" and "-c.csv"
# are left as they are.
_LIST_OR_HEADING = re.compile(r"^(?:(?P<mark>>|#{1,6}(?=\s|$)|[+-](?=\s|$))"
                              r"|(?P<number>\d+)(?P<dot>[.)])(?=\s|$))")
NBSP = "\u00a0"


# A line break, or any other control character, in a path or a static value
# would end a table row or a sentence's list item early (Vestige).
_CONTROL = re.compile(r"\r\n|[\x00-\x1f\x7f]")


def _escape(text: str) -> str:
    return _SPECIAL.sub(lambda m: "\\" + m[0], _CONTROL.sub(" ", text))


def _line_start(text: str) -> str:
    """Escape what would turn a line opening with it into a heading, a
    quotation, a list or code: a sentence can open with a path or a run
    name. Leading spaces become no-break spaces, which Markdown does not
    read as an indent, so nothing after them can open a list (DOOM Ants)."""
    indent = len(text) - len(text.lstrip(" "))
    if indent:
        return NBSP * indent + text[indent:]

    def escaped(m: re.Match) -> str:
        if m["mark"]:
            return "\\" + m["mark"]
        return m["number"] + "\\" + m["dot"]
    return _LIST_OR_HEADING.sub(escaped, text, count=1)


def _markdown_block(block: Block) -> str:
    if isinstance(block, str):  # the text's blank lines are the gaps between blocks
        return _line_start(_escape(block.strip()))
    title = [] if block.title is None else [_line_start(_escape(block.title)), ""]
    return "\n".join(title + _pipe_table(block))


def _pipe_table(table: Table) -> list[str]:
    """Padded so the pipes line up unrendered. Nothing is cut. A column
    the text keeps only to line up with another table, empty in every
    row, is left out."""
    kept = [i for i, c in enumerate(table.columns) if c.header or any(row[i] for row in table.rows)]
    right = [table.columns[i].right for i in kept]
    header = [_cell(table.columns[i].header) for i in kept]
    rows = [[_cell(row[i]) for i in kept] for row in table.rows]
    widths = [max(3, len(cell), *(len(row[k]) for row in rows)) for k, cell in enumerate(header)]

    def line(cells: list[str]) -> str:
        return "| " + " | ".join(cell.rjust(w) if r else cell.ljust(w)
                                 for cell, w, r in zip(cells, widths, right, strict=True)) + " |"
    rule = "| " + " | ".join("-" * (w - 1) + ":" if r else "-" * w for w, r in zip(widths, right, strict=True)) + " |"
    return [line(header), rule, *map(line, rows)]


def _cell(text: str) -> str:
    """Markdown joins a run of spaces into one, and would lose a nested
    pass's indent, so each two spaces become two no-break spaces. That
    is every pair, not only a leading one: a measure name's indent sits
    after its kind, mid-cell, and a value's double space is kept too."""
    return _escape(text).replace("  ", NBSP * 2)


def _no_body(result: dict) -> list[Block]:
    return []


def _check_body(result: dict) -> list[Block]:
    blocks: list[Block] = []
    for entry in result["result"]["files"]:
        if entry["breaches"]:
            blocks.append(Table(f"Breaches in {entry['path']}:",
                                [Column("line", right=True), Column("breach"), Column("rule")],
                                [[str(b["line"]), b["message"], b["rule"]] for b in entry["breaches"]],
                                text_layout=lambda t: [f"  line {line}: {message} ({rule})"
                                                for line, message, rule in t.rows]))
    if result["warnings"]:
        blocks.append(Table("Warnings:", [Column("warning"), Column("code")],
                            [[w["message"], w["code"]] for w in result["warnings"]],
                            text_layout=lambda t: [f"  {message} ({code})" for message, code in t.rows]))
    return blocks


def _selftest_body(result: dict) -> list[Block]:
    return [Table(None, [Column("result"), Column("check")],
                  [["ok" if c["pass"] else "FAIL", c["name"]] for c in result["result"]["checks"]],
                  text_layout=lambda t: [f"  {outcome:<4}  {name}" for outcome, name in t.rows])]


def _report_body(result: dict) -> list[Block]:
    report = result["result"]
    if not report:  # an error: the opening sentences say why
        return []
    blocks: list[Block] = []
    for (kind, category), passes in _groups(report["passes"], ("segment_kind", "category")):
        blocks += [Table(f"{category.upper()} passes in {_kind_name(kind)} segments, by time spent:",
                         _timing_columns("pass", "share"),
                         [["  " * p["depth"] + p["name"], f"{p['median_ms']:.3f}", f"{p['p99_ms']:.3f}",
                           "-" if p["share"] is None else f"{p['share'] * 100:.1f}%", str(p["frames"])]
                          for p in passes]), ""]
    pacing = {p["segment_kind"]: p for p in report["pacing"]}
    for (kind,), times in _groups(report["frame_times"], ("segment_kind",)):
        rows = []
        for t in times:
            rows.append([t["name"], f"{t['median_ms']:.3f}", f"{t['p99_ms']:.3f}", "", str(t["frames"])])
            if t["name"] == "wall" and kind in pacing:  # § 4.8: the pacing figure sits under wall
                change = pacing[kind]
                rows.append(["wall change (pairs)", f"{change['median_ms']:.3f}", f"{change['p99_ms']:.3f}",
                             "", str(change["pairs"])])
        # The empty column lines the text up with the passes tables.
        blocks += [Table(f"Frame times in {_kind_name(kind)} segments:", _timing_columns("measure", ""), rows), ""]
    if report["worst_frames"]:
        blocks += [_frame_table("Worst frames, longest first:", report["worst_frames"]), ""]
    if report["static"]:
        blocks += _static_blocks(report["static"])
    return _trimmed(blocks)


def _timing_columns(name: str, share: str) -> list[Column]:
    return [Column(name, 50, fit=_fitter(50)), Column("median ms", 12, True), Column("p99 ms", 12, True),
            Column(share, 6, True), Column("frames", 8, True)]


def _floor_body(result: dict) -> list[Block]:
    floor = result["result"]
    if not floor:  # an error: the opening sentences say why
        return []
    blocks: list[Block] = []
    failed = [w for w in floor["windows"] if not w["pass"]]
    if failed:
        blocks += [Table("Windows below the frame rate:",
                         [Column("start s", 10, True), Column("frames", 8, True), Column("mean ms", 10, True)],
                         [[f"{w['start_s']:.3f}", str(w["fps"]),
                           "none" if w["mean_ms"] is None else f"{w['mean_ms']:.3f}"] for w in failed]), ""]
    if floor["slow_frames"]:
        slow = sorted(floor["slow_frames"], key=lambda f: (-f["wall_ms"], f["frame"]))
        blocks.append(_frame_table("Frames over the budget, longest first:", slow[:SLOW_FRAMES]))
        if len(slow) > SLOW_FRAMES:
            blocks.append(f"  {len(slow) - SLOW_FRAMES} more: see --json.")
    return _trimmed(blocks)


def _compare_body(result: dict) -> list[Block]:
    compared = result["result"]
    if not _reached_judging(compared):  # the opening sentences say why
        return []
    if "scenes" in compared:
        return _scenes_body(compared)
    if "variants" in compared:
        return _variants_body(compared)
    blocks: list[Block] = [Table("Runs:", [Column("run"), Column("path")],
                                 [[r["name"], r["path"]] for r in compared["runs"]],
                                 text_layout=lambda t: [_fit(f"  {name:<8}  {path}", WIDTH) for name, path in t.rows])]
    if compared["refused"]:
        return blocks
    blocks.append("")
    changed = [m for m in compared["measures"] if m["verdict"] != "unchanged"]
    for unit, title in (("ms", "Measures"), ("MB", "Memory measures")):
        rows = [m for m in changed if m["unit"] == unit]
        if rows:
            blocks.append(Table(
                f"{title} that moved or are too noisy to judge, old and new as the runs' median:",
                [Column("measure", 40, fit=_fitter(40)), Column(f"old {unit}", 10, True),
                 Column(f"new {unit}", 10, True), Column("change", 10, True), Column("spread", 10, True),
                 Column("verdict")],
                [[_measure_name(m), f"{m['old_centre']:.3f}", f"{m['new_centre']:.3f}", f"{m['change']:+.3f}",
                  f"{m['spread']:.3f}", m["verdict"]] for m in rows]))
    unchanged = len(compared["measures"]) - len(changed)
    blocks += [f"{unchanged} of {len(compared['measures'])} measures unchanged.", ""]
    if compared.get("named_measures") and compared["measures"]:
        blocks += [_per_run_table(compared), ""]
    if compared["unmatched"]:
        blocks += [Table("Not in every run, so not judged:", [Column("measure"), Column("only in")],
                         [[_measure_name(m), ", ".join(m["present_in"])] for m in compared["unmatched"]],
                         text_layout=lambda t: [_fit(f"  {name}: only in {runs}", WIDTH) for name, runs in t.rows]), ""]
    diff = compared["static_diff"]
    if diff:
        blocks.append(Table("Static facts that differ between runs:", [Column("fact"), Column("values")],
                            [[d["key"], ", ".join(f"{name} {_fact(value)}" for name, value in d["values"].items())]
                             for d in diff[:STATIC_LINES]],
                            text_layout=lambda t: [_fit(f"  {key}: {values}", WIDTH) for key, values in t.rows]))
        if len(diff) > STATIC_LINES:
            blocks.append(f"  {len(diff) - STATIC_LINES} more: see --json.")
    return _trimmed(blocks)


def _bisect_body(result: dict) -> list[Block]:
    bisected = result["result"]
    if not bisected["runs"]:  # a threshold dry run reads no runs
        return []
    unit = bisected["measure"]["unit"]
    return [Table(f"Runs, with their {unit}:", [Column("run"), Column(unit, right=True), Column("path")],
                  [[r["name"], "-" if r["value"] is None else format(r["value"], ".3f"), r["path"]]
                   for r in bisected["runs"]],
                  text_layout=lambda t: [_fit(f"  {name:<8}  {value:>14}  {path}", WIDTH)
                                         for name, value, path in t.rows])]


def _budget_body(result: dict) -> list[Block]:
    budgets = result["result"]
    if not budgets:  # an error: the opening sentences say why
        return []
    return [Table("Budgets judged, in the budget file's order:",
                  [Column("budget", 40, fit=_fitter(40)), Column("limit ms", 10, True),
                   Column("value ms", 10, True), Column("over ms", 10, True), Column("frames", 8, True),
                   Column("verdict")],
                  [[f"{_kind_name(b['segment_kind'])}: {'  ' * b['depth']}{b['category']}/{b['name']} "
                    f"{b['statistic']}", f"{b['limit_ms']:.3f}", f"{b['value_ms']:.3f}", f"{b['over_ms']:+.3f}",
                    str(b["frames"]), "over" if b["over"] else "holds"] for b in budgets["budgets"]])]


def _reached_judging(compared: dict) -> bool:
    """Whether a compare's result got as far as the runs' header check:
    a file error and a named measure no run has stop before it, and have
    nothing to show past their sentences."""
    return bool({"scenes", "variants", "measures", "refused"} & compared.keys())


def _per_run_table(compared: dict) -> Table:
    """§ 4.10's *Each run's values*: a row a run, a column a named measure
    that was judged."""
    measures = compared["measures"]
    rows = [[run["name"]] for run in compared["runs"]]  # old-1, old-2, ..., new-1, ...: old + new's order
    for measure in measures:
        for row, value in zip(rows, measure["old"] + measure["new"], strict=True):
            row.append(f"{value:.3f}")
    return Table("Each run's value of each named measure (ms; mem in MB):",
                 [Column("run"), *(Column(header, right=True) for header in _per_run_headers(measures))],
                 rows, text_layout=_per_run_text)


def _per_run_text(table: Table) -> list[str]:
    """Columns past WIDTH go into a further table, which repeats the run
    column; a header too wide for one is cut."""
    room = WIDTH - len(f"  {'run':<8}")  # what the run column leaves
    columns = []  # (width, header, one cell a run)
    for i, column in enumerate(table.columns[1:], 1):
        header = _fit(column.header, room - GAP)
        cells = [row[i] for row in table.rows]
        columns.append((max(len(header), *map(len, cells)), header, cells))
    tables, current, used = [], [], 0
    for width, header, cells in columns:
        if current and used + GAP + width > room:
            tables.append(current)
            current, used = [], 0
        current.append((width, header, cells))
        used += GAP + width
    tables.append(current)
    lines = []
    for part in tables:
        lines.append(f"  {'run':<8}" + "".join(f"{'':{GAP}}{header:>{width}}" for width, header, _ in part))
        lines += [f"  {row[0]:<8}" + "".join(f"{'':{GAP}}{cells[r]:>{width}}" for width, _, cells in part)
                  for r, row in enumerate(table.rows)]
        lines.append("")
    return lines[:-1]


def _per_run_headers(measures: list[dict]) -> list[str]:
    """category/name, then p99, the segment kind when the judged measures
    span more than one, and the depth when the name is at more than one."""
    kinds = {m["segment_kind"] for m in measures}
    depths: dict[tuple, set] = {}
    for m in measures:
        depths.setdefault((m["category"], m["name"]), set()).add(m["depth"])
    headers = []
    for m in measures:
        header = f"{m['category']}/{m['name']}" + (" p99" if m["statistic"] == "p99" else "")
        if len(kinds) > 1:
            header += f" {_kind_name(m['segment_kind'])}"
        if len(depths[(m["category"], m["name"])]) > 1:
            header += f" d{m['depth']}"
        headers.append(header)
    return headers


def _measure_name(measure: dict) -> str:
    statistic = " p99" if measure["statistic"] == "p99" else ""
    indent = "  " * measure["depth"]
    return f"{_kind_name(measure['segment_kind'])}: {indent}{measure['category']}/{measure['name']}{statistic}"


def _fact(value) -> str:
    return "absent" if value is None else value if isinstance(value, str) else json.dumps(value)


def _frame_table(title: str, frames: list[dict]) -> Table:
    return Table(title, [Column("frame", 10, True), Column("segment", 30, fit=_fitter(30)),
                         Column("wall ms", 12, True), Column("top pass", fit=_fitter(36))],
                 [[str(w["frame"]), w["segment"] or "-", f"{w['wall_ms']:.3f}", w["top_pass"] or "-"]
                  for w in frames])


def _groups(entries: list[dict], keys: tuple) -> list[tuple[tuple, list[dict]]]:
    """Consecutive entries sharing `keys`, in the order the result ranks them."""
    groups: list[tuple[tuple, list[dict]]] = []
    for entry in entries:
        key = tuple(entry[k] for k in keys)
        if not groups or groups[-1][0] != key:
            groups.append((key, []))
        groups[-1][1].append(entry)
    return groups


def _static_blocks(static: dict) -> list[Block]:
    """An engine's optional "summary" object is printed whole; otherwise the
    first STATIC_LINES facts. The rest are counted and left to --json."""
    facts = _flatten(static)
    if isinstance(static.get("summary"), dict):
        shown = [f for f in facts if f[0].startswith("summary.")]
    else:
        shown = facts[:STATIC_LINES]
    blocks: list[Block] = [Table("Static facts, as the engine wrote them:", [Column("fact"), Column("value")],
                                 [[key, value] for key, value in shown],
                                 text_layout=lambda t: [_fit(f"  {key}: {value}", WIDTH) for key, value in t.rows])]
    if len(facts) > len(shown):
        blocks.append(f"  {len(facts) - len(shown)} more static facts: see --json.")
    return blocks


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


def _trimmed(blocks: list[Block]) -> list[Block]:
    """Without the blank lines that end a body."""
    while blocks and blocks[-1] == "":
        blocks.pop()
    return blocks


def _fit(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 3] + "..."


def _fitter(width: int) -> Callable[[str], str]:
    return lambda text: _fit(text, width)


def _fit_left(text: str, width: int) -> str:
    """Cut from the left, keeping the end, where a path names its map (§ 4.13)."""
    return text if len(text) <= width else "…" + text[-(width - 1):]


def _kind_name(kind: str | None) -> str:
    return kind or "unsegmented"


def _shared_directory(paths: list[str]) -> str:
    """The directory two or more paths are all in, closing separator and
    all, or "" (§ 4.13). Read from the paths as given, never the disk."""
    if len(paths) < 2:
        return ""
    alike = os.path.commonprefix(paths)  # letter by letter, so `runs` and `runs-old` are alike this far
    end = max(alike.rfind("/"), alike.rfind("\\")) + 1
    shared = alike[:end]
    # A bare "/" opens every absolute path, and "./" says only "here": neither names anything.
    return "" if shared in ("", "/", "\\", "./", ".\\") else shared


def _survey_body(result: dict) -> list[Block]:
    """Every run, ranked first, within 100 columns in the text (§ 4.13).
    A directory every file is in is named once, in the heading (DOOM Ants)."""
    runs = result["result"]["runs"]
    shared = _shared_directory([r["path"] for r in runs])
    return [Table(f"Runs, slowest first, each file in {shared}:" if shared else "Runs, slowest first:",
                  [Column("rank", 4, True), Column("file", 30, fit=lambda p: _fit_left(p, 30)),
                   Column("worst segment", 14, fit=_fitter(14)), Column("median ms", 10, True),
                   Column("p99 ms", 10, True), Column("over", 6, True), Column("verdict")],
                  [[str(r["rank"] or "-"), r["path"][len(shared):], r["worst_segment"] or "-",
                    *(("-", "-") if r["p99_ms"] is None else (f"{r['median_ms']:.3f}", f"{r['p99_ms']:.3f}")),
                    "-" if r["frames_over_budget"] is None else str(r["frames_over_budget"]), r["verdict"]]
                   for r in runs])]


def _scenes_body(compared: dict) -> list[Block]:
    """Every scene, failing first, within 100 columns in the text (§ 4.14)."""
    rows = []
    for s in compared["scenes"]:
        m = s["measure"]
        rows.append([str(s["rank"] or "-"), s["scene"], s["verdict"], "-" if m is None else _measure_name(m),
                     "-" if m is None else f"{m['change']:+.3f} {m['unit']}", s["segment"] or "-"])
    return [Table("Scenes, the largest slowdown first:",
                  [Column("rank", 4, True), Column("scene", 20, fit=lambda s: _fit_left(s, 20)),
                   Column("verdict", 12), Column("measure", 28, fit=_fitter(28)), Column("change", 12, True),
                   Column("segment", fit=_fitter(10))], rows)]


def _variants_body(compared: dict) -> list[Block]:
    """Every variant, the largest saving first, within 100 columns in the
    text (§ 4.16). The figures are the rank measure's; its unit is the
    same in every row."""
    units = {v["measure"]["unit"] for v in compared["variants"] if v["measure"]}
    unit = units.pop() if units else "ms"
    rows = []
    for v in compared["variants"]:
        m = v["measure"]
        figures = ["-"] * 4 if m is None else [
            f"{m['new_centre']:.3f}", f"{m['change']:+.3f}",
            "-" if m["change_pct"] is None else f"{m['change_pct']:+.2f}%", m["verdict"]]
        rows.append([str(v["rank"] or "-"), v["name"], v["verdict"], *figures])
    return [Table("Variants, the largest saving first:",
                  [Column("rank", 4, True), Column("variant", 32), Column("verdict", 12),  # 32: § 4.16's longest name
                   Column(f"median {unit}", 10, True), Column(f"change {unit}", 10, True),
                   Column("change %", 8, True), Column("measure")], rows)]


_BODIES = {"check": _check_body, "report": _report_body, "floor": _floor_body,
           "compare": _compare_body, "alternate": _compare_body, "bisect": _bisect_body,
           "budget": _budget_body, "survey": _survey_body, "selftest": _selftest_body}
