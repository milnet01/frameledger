"""What a run file's own text may do to plain-text output: nothing but
be read (FLED-0071).

Invariant from docs/specs/FLED-0001-run-file-format.md § 5: INV-110, the
rule of § 4.8. A header value or a path is quoted in sentences and
tables; here each holds a line break, an escape, a text-direction mark
or far too much, and the text must still be one true line per sentence.
"""

import json

import cli
from test_compare import alike, run_text


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
    assert "sanitizers 'a\\x1bb', 'c\\x00d', 'e\\u202ef'," in sanitizer_line("a\x1bb", "c\x00d", "e\u202ef")
    assert "sanitizer 'адрес'," in sanitizer_line("адрес")  # other alphabets print as written

    flood = sanitizer_line(*(f"s{i}" for i in range(5000)))
    assert "sanitizers 's0', 's1', 's2', 's3', 's4' and 4995 more," in flood and len(flood) < 200
    assert "'s3', 's4' and 1 more," in sanitizer_line(*(f"s{i}" for i in range(6)))  # N is the count left out
    assert "'s3', 's4'," in sanitizer_line(*(f"s{i}" for i in range(5)))

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
