"""--markdown: the text, as GitHub-flavoured Markdown.

Invariants from docs/specs/FLED-0001-run-file-format.md § 5: INV-87 and
INV-88, the rules of § 4.8's *Markdown*.
"""

import json
import re
from pathlib import Path

import pytest

import bisecting
import cli
import floor_runs
from test_bisect import run as bisect_run
from test_compare_measure import EXTRA, LONG_KIND, LONG_PASS, fixture, two_kind_run

FIXTURES = Path(__file__).parent / "fixtures"
ALL = sorted(FIXTURES.glob("*.csv"))
NBSP = "\u00a0"
NUMBER = re.compile(r"[+-]?\d+(\.\d+)?%?|-")


def write_runs(tmp_path: Path, label: str, texts: list[str]) -> list[str]:
    paths = []
    for i, text in enumerate(texts, 1):
        path = tmp_path / f"{label}-{i}.csv"
        path.write_text(text, encoding="utf-8")
        paths.append(str(path))
    return paths


def compare_args(tmp_path: Path) -> list[str]:
    old, new = fixture()
    return ["compare", "--old", *write_runs(tmp_path, "old", old), "--new", *write_runs(tmp_path, "new", new)]


def case_args(case: str, tmp_path: Path) -> list[str]:
    """INV-87's command lines, by name."""
    if case == "selftest":
        return ["--selftest"]
    if case == "bisect":
        good = write_runs(tmp_path, "good", [bisect_run(4.0)] * 3)
        return ["bisect", "--tested", *good, "--measure", "gpu/opaque", "--kind", "view", "--bad-above", "5"]
    if case == "compare":
        return compare_args(tmp_path)
    if case == "compare-measure":
        return [*compare_args(tmp_path), "--measure", "gpu/b", "--measure", "frame/wall"]
    command, name = case.split(":")
    return [command, str(FIXTURES / name), *(["--fps", "60"] if command == "floor" else [])]


CASES = ([f"{command}:{p.name}" for command in ("check", "report", "floor") for p in ALL]
         + ["selftest", "bisect", "compare", "compare-measure"])


def outputs(capsys, args: list[str]) -> tuple[int, str, str, dict]:
    """The exit code, then the Markdown, the text and the JSON of one command line."""
    code = cli.main([*args, "--markdown"])
    markdown = capsys.readouterr().out
    assert cli.main(args) == code
    text = capsys.readouterr().out
    assert cli.main([*args, "--json"]) == code
    return code, markdown, text, json.loads(capsys.readouterr().out)


def unescape(text: str) -> str:
    return re.sub(r"\\([!-/:-@\[-`{-~])", r"\1", text)


def cells(line: str) -> list[str]:
    """A pipe-table line's cells as written: split at each pipe no
    backslash escapes, without the padding."""
    found, cell, escaped = [], "", False
    for char in line.strip()[1:-1]:
        if char == "|" and not escaped:
            found.append(cell.strip(" "))
            cell = ""
            continue
        cell += char
        escaped = char == "\\" and not escaped
    return [*found, cell.strip(" ")]


def tables(markdown: str) -> list[tuple[str | None, list[str]]]:
    """Each pipe table's title, the paragraph before it if any, and its lines."""
    blocks = markdown.rstrip("\n").split("\n\n")
    found = []
    for i, block in enumerate(blocks):
        if block.startswith("|"):
            title = blocks[i - 1] if i and not blocks[i - 1].startswith(("|", "- ")) else None
            found.append((title, block.split("\n")))
    return found


def text_rows(text: str, title: str | None, summary: list[str]) -> list[str]:
    """The text's indented lines under `title`, or after the sentences
    for a table with none, up to a blank line or a "see --json" line."""
    lines = text.splitlines()
    start = lines.index(title) + 1 if title is not None else len(summary) + 1
    rows = []
    for line in lines[start:]:
        if not line.startswith("  ") or "see --json" in line:
            break
        rows.append(line)
    return rows


@pytest.mark.parametrize("case", CASES)
def test_markdown_matches_text(capsys, tmp_path, case):
    """INV-87: the opening list is the JSON summary; each table has the
    text table's rows, in order; the exit code is the text's."""
    code, markdown, text, result = outputs(capsys, case_args(case, tmp_path))
    assert code == result["exit_code"]
    lines = markdown.split("\n")
    sentences = lines[: lines.index("")] if "" in lines else lines[:-1]
    assert [unescape(line[2:]) for line in sentences] == result["summary"]
    assert all(line.startswith("- ") for line in sentences)
    for title, table in tables(markdown):
        header, rows = cells(table[0]), [cells(line) for line in table[2:]]
        assert all(len(row) == len(header) for row in [cells(table[1]), *rows])
        plain = None if title is None else unescape(title)
        under = text_rows(text, plain, result["summary"])
        assert len(under) in (len(rows), len(rows) + 1), (title, under)  # a columns table has a header line
        for row, line in zip(rows, under[len(under) - len(rows):], strict=True):
            assert_row_in_line(row, line)


def assert_row_in_line(row: list[str], line: str) -> None:
    """Every Markdown cell, unescaped, is in the text's line, in order. A
    cell the text cut short keeps one end there, beside a "..." or "…"."""
    at = 0
    for cell in row:
        plain = unescape(cell).replace(NBSP, " ").strip()
        found = line.find(plain, at)
        if found < 0:
            assert ("..." in line or "…" in line) and (plain[:8] in line or plain[-8:] in line), (cell, line)
            continue
        at = found + len(plain)


@pytest.mark.parametrize("case", CASES)
def test_tables_line_up(capsys, tmp_path, case):
    """INV-87: a table's lines are all one length, so its pipes line up
    unrendered; a column of numbers aligns right."""
    _, markdown, _, _ = outputs(capsys, case_args(case, tmp_path))
    for title, table in tables(markdown):
        assert len({len(line) for line in table}) == 1, title
        if len(table) == 2:  # a header and no rows: no column to judge
            continue
        columns = list(zip(*[cells(line) for line in table[2:]], strict=True))
        for name, marker, column in zip(cells(table[0]), cells(table[1]), columns, strict=True):
            numbers = all(NUMBER.fullmatch(c) for c in column) and any(c != "-" for c in column)
            if numbers and name not in ("value", "values"):  # a static value is the engine's text
                assert marker.endswith(":"), (title, name)


def test_no_width_limit(capsys, tmp_path):
    """INV-87: a per-run table wider than 100 characters is one table,
    nothing in it cut."""
    for label in ("old", "new"):
        texts = [two_kind_run(f"{label}{i}", f"2026-11-11T13:{2 * i + (label == 'new'):02d}:00Z",
                              (i + 3 * (label == "new")) / 100) for i in range(3)]
        write_runs(tmp_path, label, texts)
    flags = [arg for name in ["gpu/b", "frame/wall", *(f"gpu/{n}" for n in EXTRA)] for arg in ("--measure", name)]
    old = [str(tmp_path / f"old-{i}.csv") for i in (1, 2, 3)]
    new = [str(tmp_path / f"new-{i}.csv") for i in (1, 2, 3)]
    cli.main(["compare", "--old", *old, "--new", *new, *flags, "--markdown"])
    markdown = capsys.readouterr().out
    [table] = [t for title, t in tables(markdown) if title and title.startswith("Each run's value")]
    assert len(table) == 2 + 6
    assert max(map(len, table)) > 100
    assert LONG_PASS in table[0] and LONG_KIND in table[0] and "..." not in table[0]


def test_row_limits_stay(capsys, tmp_path):
    """INV-87: 11 frames over budget list 10, and 21 static facts list
    20, each then saying one more is in the JSON."""
    path = tmp_path / "slow.csv"
    path.write_text(floor_runs.run_text([16.0] * 50 + [30.0] * 11 + [16.0] * 50), encoding="utf-8")
    assert cli.main(["floor", str(path), "--fps", "60", "--warmup-s", "0", "--no-windows", "--markdown"]) == 1
    markdown = capsys.readouterr().out
    [(_, table)] = tables(markdown)
    assert len(table) == 2 + 10
    assert "\n\n1 more: see --json.\n" in markdown

    lines = (FIXTURES / "nested.csv").read_text(encoding="utf-8").splitlines()
    lines.insert(1, "# frameledger-static " + json.dumps({f"fact{i:02d}": f"v{i}" for i in range(21)}))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    cli.main(["report", str(path), "--markdown"])
    markdown = capsys.readouterr().out
    [table] = [t for title, t in tables(markdown) if title == "Static facts, as the engine wrote them:"]
    assert len(table) == 2 + 20
    assert markdown.endswith("\n\n1 more static facts: see --json.\n")


NOTE = r"a|b *c* _d_ <e> [f]g &amp; ~~i~~ `k` $x$ \j"
ESCAPED = r"a\|b \*c\* \_d\_ \<e> \[f\]g \&amp; \~\~i\~\~ \`k\` \$x\$ \\j"


def test_engine_text_is_escaped(capsys, tmp_path):
    """INV-88: a static value cannot split its cell or format, nor a line
    break end its row; a pass name keeps its inner underscore; a nested
    pass keeps its indent."""
    lines = (FIXTURES / "nested.csv").read_text(encoding="utf-8").splitlines()
    lines.insert(1, "# frameledger-static " + json.dumps({"note": NOTE, "lines": "a\nb\r\nc"}))
    lines.insert(-1, "r1,view:1,0,gpu,shadow_map,0,1.000")
    path = tmp_path / "escaped.csv"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert cli.main(["report", str(path), "--markdown"]) == 0
    markdown = capsys.readouterr().out
    assert f"| note  | {ESCAPED} |" in markdown.split("\n")
    [row] = [line for line in markdown.split("\n") if line.startswith("| lines ")]
    assert cells(row) == ["lines", "a b c"] and row.endswith(" |")
    assert unescape(ESCAPED) == NOTE
    assert "shadow_map" in markdown and r"shadow\_map" not in markdown
    nested = [line for line in markdown.split("\n") if "cascade0" in line]
    assert nested and all(cells(line)[0].startswith(NBSP * 2 + "shadows/cascade0") for line in nested)


@pytest.mark.parametrize(("name", "opening"), [
    ("# a.csv", r"- \# a.csv"), ("> b.csv", r"- \> b.csv"), ("- c.csv", r"- \- c.csv"),
    ("+ d.csv", r"- \+ d.csv"), ("1. e.csv", r"- 1\. e.csv"), ("1) f.csv", r"- 1\) f.csv"),
    ("100.0.csv", "- 100.0.csv"), ("a\nb.csv", "- a b.csv"),
    (" - c.csv", f"- {NBSP}- c.csv"), ("    x.csv", f"- {NBSP * 4}x.csv"),
])
def test_line_starts_are_escaped(capsys, tmp_path, monkeypatch, name, opening):
    """INV-88: a sentence opening with a path cannot become a heading, a
    quotation or a list, nor a line break in it end its item; one that
    would not is left as it is."""
    monkeypatch.chdir(tmp_path)
    Path(name).write_text("not a run\n", encoding="utf-8")
    assert cli.main(["check", name, "--markdown"]) == 1
    assert capsys.readouterr().out.startswith(f"{opening} breaks the run-file format")


def test_markdown_and_json_refused(capsys):
    """INV-88: asking for both forms is a bad argument, and under bisect a stop."""
    nested = str(FIXTURES / "nested.csv")
    assert cli.main(["report", nested, "--markdown", "--json"]) == cli.ERROR
    assert cli.main(["--markdown", "report", nested, "--json"]) == cli.ERROR
    assert cli.main(["bisect", "--dry-run", "1.000", "--measure", "gpu/opaque", "--kind", "view",
                     "--bad-above", "2", "--markdown", "--json"]) == bisecting.VERDICT_CODES["stop"]
    assert "not both" in capsys.readouterr().err
