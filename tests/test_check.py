"""The `check` command: does a run file meet the format spec?

Invariants from docs/specs/FLED-0001-run-file-format.md § 5. INV-1's
and INV-21's `report` halves sit beside their `check` halves; INV-1's
`floor` half arrives with that command (FLED-0004).
"""

import json
from pathlib import Path

import pytest

import cli

FIXTURES = Path(__file__).parent / "fixtures"


def run_check(capsys, *paths):
    code = cli.main(["check", "--json", *map(str, paths)])
    out = json.loads(capsys.readouterr().out)
    assert out["exit_code"] == code
    return code, out


def found(out, index=0):
    return [(b["line"], b["rule"]) for b in out["result"]["files"][index]["breaches"]]


def line_of(path, text):
    lines = path.read_text(encoding="utf-8").splitlines()
    return lines.index(text) + 1


def test_missing_header(capsys):
    """INV-1: a file whose first line is not the header fails check, exit 1,
    and report, exit 3."""
    code, out = run_check(capsys, FIXTURES / "no-header.csv")
    assert (code, out["verdict"]) == (1, "fail")
    assert found(out) == [(1, "header")]

    assert cli.main(["report", "--json", str(FIXTURES / "no-header.csv")]) == 3
    out = json.loads(capsys.readouterr().out)
    assert out["verdict"] == "error" and "line 1" in out["summary"][0]


def test_schema_versions(capsys):
    """INV-2: a newer schema is an error naming both versions; schema 1 reads."""
    code, out = run_check(capsys, FIXTURES / "schema-99.csv")
    assert (code, out["verdict"]) == (3, "error")
    assert "schema 99" in out["summary"][0]
    assert "schema 1" in out["summary"][0]

    code, out = run_check(capsys, FIXTURES / "schema-1.csv")
    assert (code, out["verdict"]) == (0, "pass")
    assert found(out) == []


def test_value_format(capsys):
    """INV-6: a comma decimal point, or not three places, is a breach on its line."""
    path = FIXTURES / "comma-decimal.csv"
    code, out = run_check(capsys, path)
    assert code == 1
    assert sorted(found(out)) == [
        (line_of(path, 'r1,view:1,0,frame,gpu_span,0,"1,250"'), "value"),
        (line_of(path, "r1,view:1,0,gpu,shadows,0,1.25"), "value"),
    ]


def test_negative_and_last_wall(capsys):
    """INV-21: a negative gpu value is kept and named; wall <= 0 is a breach;
    the last frame's missing wall is neither."""
    path = FIXTURES / "negative-gpu.csv"
    code, out = run_check(capsys, path)
    assert (code, found(out)) == (0, [])
    negative_line = line_of(path, "r1,view:1,0,gpu,shadows,0,-0.004")
    assert any("negative" in s and str(negative_line) in s for s in out["summary"])
    assert [w["code"] for w in out["warnings"]] == ["negative_value"]

    assert cli.main(["report", "--json", str(path)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert any("negative (-0.004) on frame 0" in s for s in report["summary"])
    assert not any("wall" in w["code"] for w in report["warnings"])

    path = FIXTURES / "zero-wall.csv"
    code, out = run_check(capsys, path)
    assert code == 1
    assert found(out) == [(line_of(path, "r1,view:1,0,frame,wall,0,0.000"), "wall")]


# Every other rule of § 4, each as one edit to schema-1.csv: replace the
# text in the first column, expect the breach in the third on the line
# holding the replacement (or the line given).
HEADER = (FIXTURES / "schema-1.csv").read_text(encoding="utf-8").splitlines()[0]
GOOD_ROW = "r1,view:1,1,cpu,scene,0,6.000"  # a cpu/scene row frame 1 lacks

BREACHES = [
    ("columns", "run_id,segment,frame,category,name,value", "columns"),
    ("row with six fields", "r1,view:1,1,cpu,scene,6.000", "row"),
    ("blank line", "", "row"),
    ("run_id differs", "r2,view:1,1,cpu,scene,0,6.000", "run_id"),
    ("segment without kind", "r1,view1,1,cpu,scene,0,6.000", "segment"),
    ("segment kind too long", f"r1,{'k' * 33}:1,1,cpu,scene,0,6.000", "segment"),
    ("negative frame", "r1,view:1,-1,cpu,scene,0,6.000", "frame"),
    ("unknown category", "r1,view:1,1,disk,scene,0,6.000", "category"),
    ("name with a space", "r1,view:1,1,cpu,scene pass,0,6.000", "name"),
    ("name of 65 bytes", f"r1,view:1,1,cpu,{'n' * 65},0,6.000", "name"),
    ("depth not a number", "r1,view:1,1,cpu,scene,x,6.000", "depth"),
    ("exponent value", "r1,view:1,1,cpu,scene,0,6e3", "value"),
    ("value too large", "r1,view:1,1,cpu,scene,0,1000000000.000", "value"),
    ("duplicate row", "r1,view:1,0,cpu,scene,0,6.000", "duplicate"),
    ("stray comment", "# a note", "comment"),
    ("unknown keyword line", "# frameledger-extra {}", "comment"),
]


@pytest.mark.parametrize(("text", "rule"), [b[1:] for b in BREACHES], ids=[b[0] for b in BREACHES])
def test_row_breaches(capsys, tmp_path, text, rule):
    lines = (FIXTURES / "schema-1.csv").read_text(encoding="utf-8").splitlines()
    at = 2 if rule == "columns" else lines.index("r1,view:1,1,frame,cpu_span,0,9.000") + 1
    if rule == "columns":
        lines[1] = text
    else:
        lines.insert(at, text)
    path = tmp_path / "run.csv"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    code, out = run_check(capsys, path)
    assert code == 1
    expected_line = 2 if rule == "columns" else at + 1
    assert found(out) == [(expected_line, rule)]


def header_with(**changes):
    fields = json.loads(HEADER.split(" ", 2)[2])
    for key, value in changes.items():
        if value is ...:
            del fields[key]
        else:
            fields[key] = value
    return "# frameledger " + json.dumps(fields)


HEADER_BREACHES = [
    ("not JSON", "# frameledger {schema:1}"),
    ("not an object", "# frameledger [1]"),
    ("missing field", header_with(device=...)),
    ("boolean as string", header_with(vsync="no")),
    ("integer field as boolean", header_with(frames_in_flight=True)),
    ("resolution of one number", header_with(resolution=[1920])),
    ("unknown display", header_with(display="window")),
    ("short hash", header_with(inputs=[{"name": "a", "hash": "sha256:ab", "bytes": 1}])),
    ("time without Z", header_with(started_utc="2026-10-24T12:00:00")),
    ("load without end", header_with(load={"start": 1.0})),
    ("schema as text", header_with(schema="1")),
    ("schema 0", header_with(schema=0)),
    ("NaN", HEADER.replace('"render_scale":1.0', '"render_scale":NaN')),
]


@pytest.mark.parametrize("header", [b[1] for b in HEADER_BREACHES], ids=[b[0] for b in HEADER_BREACHES])
def test_header_breaches(capsys, tmp_path, header):
    lines = (FIXTURES / "schema-1.csv").read_text(encoding="utf-8").splitlines()
    lines[0] = header
    path = tmp_path / "run.csv"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    code, out = run_check(capsys, path)
    assert code == 1
    assert found(out) == [(1, "header")]


def edited(tmp_path, edit):
    lines = (FIXTURES / "schema-1.csv").read_text(encoding="utf-8").splitlines()
    edit(lines)
    path = tmp_path / "run.csv"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_static_line_rules(capsys, tmp_path):
    """§ 4.3: a static statistic is a JSON string, never a number."""
    path = edited(tmp_path, lambda ls: ls.insert(1, '# frameledger-static {"draws": "1520"}'))
    assert run_check(capsys, path)[0] == 0
    path = edited(tmp_path, lambda ls: ls.insert(1, '# frameledger-static {"draws": 1520}'))
    code, out = run_check(capsys, path)
    assert (code, found(out)) == (1, [(2, "static")])


def test_close_line_rules(capsys, tmp_path):
    """§ 4.5: the close line comes last and carries two counts."""
    path = edited(tmp_path, lambda ls: ls.append(GOOD_ROW))
    code, out = run_check(capsys, path)
    assert (code, found(out)) == (1, [(len(path.read_text().splitlines()), "close")])

    path = edited(tmp_path, lambda ls: ls.__setitem__(-1, '# frameledger-close {"frames": 2}'))
    code, out = run_check(capsys, path)
    assert (code, found(out)) == (1, [(len(path.read_text().splitlines()), "close")])


def test_frame_without_cpu_span(capsys, tmp_path):
    """§ 4.4: each frame has frame/cpu_span."""
    path = edited(tmp_path, lambda ls: ls.remove("r1,view:1,1,frame,cpu_span,0,9.000"))
    code, out = run_check(capsys, path)
    assert code == 1
    assert [rule for _, rule in found(out)] == ["cpu_span"]


def test_frame_without_cpu_span_after_drops(capsys, tmp_path):
    """When the writer dropped rows, a frame's cpu_span may be among them
    while its late GPU rows still landed: a warning, not a breach
    (Vestige, 2026-10-24)."""
    def edit(lines):
        lines.remove("r1,view:1,1,frame,cpu_span,0,9.000")
        lines[-1] = '# frameledger-close {"rows_dropped":1,"frames":2}'
    code, out = run_check(capsys, edited(tmp_path, edit))
    assert (code, found(out)) == (0, [])
    assert [w["code"] for w in out["warnings"]] == ["rows_dropped", "cpu_span_missing"]


def test_not_utf8(capsys, tmp_path):
    path = tmp_path / "run.csv"
    data = (FIXTURES / "schema-1.csv").read_bytes().replace(b"view:1,1,cpu", b"view:\xff,1,cpu")
    path.write_bytes(data)
    code, out = run_check(capsys, path)
    assert code == 1
    assert [rule for _, rule in found(out)] == ["encoding"]


WARNINGS = [
    ("unfinished", lambda ls: ls.pop()),
    ("rows_dropped", lambda ls: ls.__setitem__(-1, '# frameledger-close {"rows_dropped":3,"frames":2}')),
    ("inputs_empty", lambda ls: ls.__setitem__(0, header_with(inputs=[]))),
    ("unknown_field", lambda ls: ls.__setitem__(0, header_with(colour="blue"))),
    ("wall_missing", lambda ls: ls.remove("r1,view:1,0,frame,wall,0,16.000")),
    ("unknown_frame_name", lambda ls: ls.insert(3, "r1,view:1,0,frame,swap,0,1.000")),
]


@pytest.mark.parametrize(("code_name", "edit"), WARNINGS, ids=[w[0] for w in WARNINGS])
def test_warnings_do_not_fail(capsys, tmp_path, code_name, edit):
    """Things a reader should know that do not break the format: exit 0,
    a warning, and an opening sentence."""
    code, out = run_check(capsys, edited(tmp_path, edit))
    assert (code, found(out)) == (0, [])
    assert [w["code"] for w in out["warnings"]] == [code_name]
    assert len(out["summary"]) == 2  # the warning's sentence, then the verdict


def test_windows_paths_read():
    """S11: a header carrying Windows paths reads, backslashes intact."""
    import ledger

    run = ledger.read(FIXTURES / "schema-1.csv")
    assert run.header["scene"] == "C:\\Games\\Vestige\\scenes\\atrium.json"


def test_several_files(capsys, tmp_path):
    """One exit code for many files: a breach gives 1, an unreadable file 3."""
    good, bad = FIXTURES / "schema-1.csv", FIXTURES / "zero-wall.csv"
    assert run_check(capsys, good, good)[0] == 0
    code, out = run_check(capsys, good, bad)
    assert (code, [f["path"] for f in out["result"]["files"]]) == (1, [str(good), str(bad)])
    code, out = run_check(capsys, good, bad, tmp_path / "absent.csv")
    assert (code, out["verdict"]) == (3, "error")
    assert [w["code"] for w in out["warnings"]] == ["file_error"]
