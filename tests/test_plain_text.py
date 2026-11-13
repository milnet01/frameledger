"""What a run file's own text may do to plain-text output: nothing but
be read (FLED-0071).

Invariant from docs/specs/FLED-0001-run-file-format.md § 5: INV-110, the
rule of § 4.8. A header value or a path is quoted in sentences and
tables; here each holds a line break, an escape, a text-direction mark
or far too much, and the text must still be one true line per sentence.
"""

import json
import os
from pathlib import Path

import cli
import ledger
import pytest
import render
from test_baseline import started, write_baseline, write_runs
from test_compare import alike, new, old, run_text
from test_compare_scenes import Files, by_scene


def text_of(capsys, tmp_path, *flags, name="run.csv", **header) -> str:
    """`report`'s output for one run with `header`'s fields."""
    path = tmp_path / name
    path.write_text(run_text(alike(10.0), **header), encoding="utf-8")
    assert cli.main(["report", str(path), *flags]) == 0
    return capsys.readouterr().out


def warning_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith("Warning: ")]


def test_header_text_cannot_forge_or_flood_a_line(capsys, tmp_path):
    """INV-110: a quoted header value shows a control character as an
    escape and a backslash doubled, a long list is cut after five, and a
    long value is cut short."""
    def sanitizer_line(*names: str) -> str:
        (line,) = warning_lines(text_of(capsys, tmp_path, sanitizers=list(names)))
        return line

    # A line break in a name printed a second, forged Warning line (DOOM Ants).
    assert "sanitizer 'addr\\nWarning: fake'," in sanitizer_line("addr\nWarning: fake")
    # The two typed characters \ and n are not a line break, and do not read as one.
    assert "sanitizer 'addr\\\\nWarning: fake'," in sanitizer_line("addr\\nWarning: fake")
    # An escape, a NUL and a right-to-left override, each as what it is.
    assert "sanitizers 'a\\x1bb', 'c\\x00d' and 'e\\u202ef'," in sanitizer_line("a\x1bb", "c\x00d", "e\u202ef")
    assert "sanitizer 'адрес'," in sanitizer_line("адрес")  # other alphabets print as written

    flood = sanitizer_line(*(f"s{i}" for i in range(5000)))
    assert "sanitizers 's0', 's1', 's2', 's3', 's4' and 4995 more," in flood and len(flood) < 200
    assert "'s3', 's4' and 1 more," in sanitizer_line(*(f"s{i}" for i in range(6)))  # N is the count left out
    assert "'s2', 's3' and 's4'," in sanitizer_line(*(f"s{i}" for i in range(5)))

    (line,) = warning_lines(text_of(capsys, tmp_path, renderer="llvmpipe\nWarning: fake " + "x" * 50000))
    assert "the renderer is 'llvmpipe\\nWarning: fake xxx" in line and len(line) < 200

    # --json keeps the name as written: JSON escapes it itself.
    out = json.loads(text_of(capsys, tmp_path, "--json", sanitizers=["addr\nWarning: fake"]))
    assert "'addr\nWarning: fake'" in out["warnings"][0]["message"]
    # Markdown has no line break in the item either.
    assert sum("fake" in line for line in
               text_of(capsys, tmp_path, "--markdown", sanitizers=["addr\nWarning: fake"]).splitlines()) == 1


def test_path_text_cannot_forge_a_line(capsys, tmp_path, monkeypatch):
    """INV-110: a path shows a control character as an escape and keeps
    its backslashes single; --json gives it exactly."""
    monkeypatch.chdir(tmp_path)
    forged = "ru\nWarning: fake\x1b[2Jns"
    (tmp_path / forged).mkdir()
    names = [f"{forged}/a.csv", f"{forged}/b.csv", "C:\\new.csv", "my_runs*|.csv"]
    for i, name in enumerate(names):
        (tmp_path / name).write_text(run_text(alike(10.0), run_id=f"r{i}"), encoding="utf-8")

    cli.main(["survey", names[0], names[1], "--fps", "60"])
    text = capsys.readouterr().out
    assert "Runs, slowest first, each file in ru\\nWarning: fake\\x1b[2Jns/:" in text.splitlines()
    assert not any(line.startswith("Warning: fake") for line in text.splitlines()) and "\x1b" not in text

    cli.main(["survey", "C:\\new.csv", "--fps", "60"])
    text = capsys.readouterr().out
    assert "C:\\new.csv" in text and "C:\\\\new.csv" not in text  # a Windows path is not doubled

    cli.main(["survey", names[0], names[1], "--fps", "60", "--json"])
    paths = [run["path"] for run in json.loads(capsys.readouterr().out)["result"]["runs"]]
    assert sorted(paths) == names[:2]

    # In Markdown, a name's own Markdown characters format nothing (Vestige).
    cli.main(["survey", "my_runs*|.csv", "--fps", "60", "--markdown"])
    assert "my_runs\\*\\|.csv" in capsys.readouterr().out

    # A file that cannot be read is named the same way.
    assert cli.main(["report", f"{forged}/missing.csv"]) == 3
    assert capsys.readouterr().out == "ru\\nWarning: fake\\x1b[2Jns/missing.csv: No such file or directory.\n"


# A value that tries everything at once: a forged line, a screen clear, the
# typed characters \ and n, and far too much.
HOSTILE = "A\nWarning: fake\x1b[2J\\n" + "x" * 50000 + "END"
TIMES = [10.0, 10.01, 10.02]
LONGEST = 700  # no sentence quoting a header value needs more; a flooded line is tens of thousands


def assert_tame(text: str, what: object) -> None:
    """No line of `text` is forged, flooded or obeyed by a terminal."""
    for line in text.splitlines():
        assert len(line) < LONGEST, (what, len(line), line[:120])
        assert not line.startswith("Warning: fake"), (what, line[:120])
        assert not render._UNPRINTED.search(line), (what, line[:120])


MARKS = ["\x00", "\x1b", "\x7f", "\x85", "\x9f", "\u061c", "\u200b", "\u200e", "\u200f", "\u202a",
         "\u202e", "\u2028", "\u2029", "\u2060", "\u2066", "\u2069", "\ufeff"]


@pytest.mark.parametrize("mark", MARKS)
def test_each_kind_of_unprinted_character_is_shown(mark):
    """INV-110: each range of § 4.8's list, by one of its characters."""
    shown = render.visible(f"a{mark}b")
    assert mark not in shown and shown.startswith("a\\") and shown.endswith("b")


def test_joining_characters_print_as_written():
    """§ 4.8: Persian and emoji need the zero-width joiners, so they stay."""
    assert render.visible("می\u200cخواهم 👩\u200d🚀") == "می\u200cخواهم 👩\u200d🚀"


STRING_FIELDS = sorted(name for name, (_, rule, _) in ledger.HEADER_FIELDS.items() if rule is ledger._is_string)


@pytest.mark.parametrize("field", [*STRING_FIELDS, "an unknown key"])
def test_no_header_string_forges_or_floods(capsys, tmp_path, field):
    """INV-110: every header field that may hold any string, and a key
    the format does not define, each hostile in turn, under `report`,
    `check`, and a `compare` whose two sides differ in it."""
    if field == "run_id":  # the one field each row repeats: the rows keep their own, so every row breaks its rule
        text = run_text(alike(10.0), run_id="other").replace('"run_id": "other"', f'"run_id": {json.dumps(HOSTILE)}', 1)
        assert json.dumps(HOSTILE) in text
        texts = [text] * 3
    else:
        texts = new(TIMES, **({HOSTILE: 1} if field == "an unknown key" else {field: HOSTILE}))
    hostile = write_runs(tmp_path / "hostile", "new", texts)
    plain = write_runs(tmp_path / "plain", "old", old(TIMES))
    for command in (["report", hostile[0]], ["check", hostile[0]], ["compare", "--old", *plain, "--new", *hostile]):
        cli.main(command)
        captured = capsys.readouterr()
        assert captured.out or captured.err
        assert_tame(captured.out, command[0])
        assert_tame(captured.err, command[0])


def test_baseline_warnings_quote_header_strings(capsys, tmp_path):
    """INV-110: § 4.17's warnings quote a driver, an os and a commit as
    any header string is quoted."""
    days_before = started(old(TIMES, driver="mesa\\n1", commit=HOSTILE), *["2026-10-18T12:00:00Z"] * 3)
    old_runs = write_runs(tmp_path / "kept", "old", days_before)
    new_runs = write_runs(tmp_path, "new", new(TIMES, driver=HOSTILE))
    baseline = write_baseline(tmp_path / "kept" / "main.baseline", [Path(p).name for p in old_runs])
    cli.main(["compare", "--baseline", baseline, "--new", *new_runs])
    text = capsys.readouterr().out
    assert_tame(text, "baseline")
    (driver,) = [line for line in text.splitlines() if "runs' driver is" in line]
    # The typed characters \ and n are doubled; the long value keeps both its ends.
    assert '"mesa\\\\n1"' in driver and '"A\\nWarning: fake' in driver and 'xxxEND"' in driver
    (first,) = [line for line in text.splitlines() if "are a baseline of commit" in line]
    assert "commit A\\nWarning: fake" in first and "END, started" in first


def test_a_baseline_file_cannot_forge_or_flood_standard_error(capsys, tmp_path):
    """INV-110: a setup error quotes a line of the baseline file, so
    standard error is cleaned and cut as well."""
    for line in (HOSTILE, "C:" + HOSTILE if os.name != "nt" else "\x00" + HOSTILE, "runs/\x00\x1b" + "y" * 50000):
        baseline = write_baseline(tmp_path / "main.baseline", [line])
        assert cli.main(["compare", "--baseline", baseline, "--new", str(tmp_path / "n.csv")]) == 3
        captured = capsys.readouterr()
        assert captured.out == "" and captured.err.startswith("frameledger: ") and "line 2" in captured.err
        assert captured.err.count("\n") == 1
        assert_tame(captured.err, line[:20])


def test_a_budget_file_cannot_flood_a_line(capsys, tmp_path):
    """INV-110: a budget file's fields are cut where an error quotes them,
    and so is a run's value where it is not the one the budgets were set for."""
    run = tmp_path / "run.csv"
    run.write_text(run_text(alike(10.0), scene=HOSTILE), encoding="utf-8")
    budgets = tmp_path / "frame.budget"
    head = '# frameledger-budget {"schema":1,"match":{"scene":"meadow"}}\ncategory,name,kind,depth,statistic,limit_ms\n'
    long = "z" * 50000
    for row in ("cpu,frame,,,median,5.000", f"{long},frame,,,median,5.000", f"cpu,{long},,,median,5.000",
                f"cpu,frame,{long},,median,5.000", f"cpu,frame,,,{long},5.000"):
        budgets.write_text(head + row + "\n", encoding="utf-8")
        assert cli.main(["budget", str(run), "--budgets", str(budgets)]) == 3
        captured = capsys.readouterr()
        assert_tame(captured.out + captured.err, row[:30])


def test_a_scene_name_cannot_flood_a_sentence(capsys, tmp_path):
    """INV-110: --by-scene's sentences cut a scene's name; its table and
    --json name the scene whole, as they do a path."""
    files = Files(tmp_path)
    old_runs, new_runs = files.runs(HOSTILE, [1.0, 1.01, 1.02]), files.runs("atrium", [1.0, 1.01, 1.02])
    _, out = by_scene(capsys, old_runs, new_runs)
    assert any("fake" in sentence for sentence in out["summary"])
    assert all(len(sentence) < LONGEST for sentence in out["summary"]), out["summary"]
    assert HOSTILE in [scene["scene"] for scene in out["result"]["scenes"]]


def test_markdown_makes_each_unprinted_character_a_space(capsys, tmp_path):
    """INV-110: Markdown has plain text's list (FLED-0073). A direction
    mark in a pull-request comment would reorder a sentence as rendered."""
    for mark in MARKS:
        text = text_of(capsys, tmp_path, "--markdown", sanitizers=[f"a{mark}b"])
        assert mark not in text and "'a b'" in text, repr(mark)
    assert "می\u200cخواهم" in text_of(capsys, tmp_path, "--markdown", sanitizers=["می\u200cخواهم"])
