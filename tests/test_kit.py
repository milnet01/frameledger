"""The writer kit and `check --expect`.

Invariants from docs/specs/FLED-0001-run-file-format.md § 5: INV-116,
the kit's files; INV-117, matching content, not layout. The kit's C leg,
each case built against include/frameledger.h, is
tests/writer/test_kit.sh.
"""

import json
import subprocess
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pytest

import cli
import expect
import kit
import ledger
from test_release import build

KIT = Path(__file__).parent.parent / "src" / "frameledger" / "kit"


def check(capsys, *args):
    """`check --json` with `args`; its exit code and parsed result."""
    code = cli.main(["check", "--json", *map(str, args)])
    out = json.loads(capsys.readouterr().out)
    assert out["exit_code"] == code
    return code, out


def case(name):
    return json.loads((KIT / f"{name}.json").read_text(encoding="utf-8"))


def test_cases_are_named_in_kit_py():
    """kit.py names each case, since the .pyz cannot list a folder; the
    names are exactly kit/'s, and kit/ holds nothing else."""
    assert sorted(path.stem for path in KIT.glob("*.json")) == sorted(kit.CASES)
    assert sorted(path.name for path in KIT.iterdir()) == sorted(kit.names())


def test_kit_is_written(capsys, tmp_path):
    """INV-116: `kit DIR` into a missing directory writes README.txt and
    each case's NAME.json and NAME.csv, as the analyser holds them. Under
    check --strict each NAME.csv gives exactly the codes its `warns`
    lists, and it matches itself under --expect."""
    target = tmp_path / "made" / "kit"
    assert cli.main(["kit", str(target)]) == 0
    assert "README.txt" in capsys.readouterr().out
    assert sorted(path.name for path in target.iterdir()) == sorted(kit.names())
    for name in kit.names():
        assert (target / name).read_bytes() == (KIT / name).read_bytes(), name
    for name in kit.CASES:
        expected = target / f"{name}.csv"
        code, out = check(capsys, "--strict", "--expect", expected, expected)
        warned = sorted({warning["code"] for warning in out["warnings"]})
        assert warned == sorted(case(name)["warns"]), name
        assert out["result"]["files"][0]["breaches"] == [], name
        assert out["result"]["expect"] == {"matches": True, "differences": []}, name
        assert code == (1 if warned else 0), name


def test_case_values_round_as_their_text():
    """§ 4.19: each kept value, rounded half away from zero as decimal
    text, is what NAME.csv holds, so a writer may round the double or the
    text alike."""
    for name in kit.CASES:
        run = ledger.read(KIT / f"{name}.csv")
        data = json.loads((KIT / f"{name}.json").read_text(encoding="utf-8"), parse_float=Decimal)
        for entry in data["frames"]:
            for row in entry["rows"]:
                if row.get("dropped"):
                    continue
                text = Decimal(row["value"]).quantize(Decimal("0.001"), ROUND_HALF_UP)
                written = run.frames[entry["frame"]][(row["category"], row["name"])].thousandths
                assert written == int(text * 1000), (name, entry["frame"], row)


def test_kit_refuses_a_full_directory(capsys, tmp_path):
    """INV-116: kit into a directory holding one file is exit 3 and writes
    nothing."""
    (tmp_path / "notes.txt").write_text("mine\n", encoding="utf-8")
    assert cli.main(["kit", str(tmp_path)]) == 3
    assert "already holds files" in capsys.readouterr().err
    assert [path.name for path in tmp_path.iterdir()] == ["notes.txt"]


def test_kit_from_the_release(tmp_path):
    """INV-116: run from the release .pyz, kit writes the same files as
    from the tree."""
    build(tmp_path / "release", "v9.9.9")
    done = subprocess.run([sys.executable, "-I", str(tmp_path / "release" / "frameledger.pyz"), "kit",
                           str(tmp_path / "kit")], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    written = {path.name: path.read_bytes() for path in (tmp_path / "kit").iterdir()}
    assert written == {name: (KIT / name).read_bytes() for name in kit.names()}


HEADER = {"schema": 1, "run_id": "r", "engine": "e", "tool": {"name": "t", "version": "1"},
          "build_type": "release", "commit": "c", "dirty": False, "device": "d", "renderer": "r",
          "driver": "v", "api": "a", "resolution": [1, 1], "render_scale": 1, "vsync": False,
          "pipelined": False, "display": "offscreen", "scene": "s",
          "inputs": [{"name": "i", "hash": "sha256:" + "ab" * 32, "bytes": 1}],
          "started_utc": "2026-11-17T12:00:00.5Z", "extra": {"flag": 1}}
ROWS = ["r,view:1,0,frame,cpu_span,0,5.250", "r,view:1,0,frame,wall,0,16.000",
        "r,view:1,1,frame,cpu_span,0,5.000", "r,view:1,1,cpu,scene,0,2.000"]
CLOSE = '# frameledger-close {"rows_dropped":0,"frames":2}'


def run_file(path, header=HEADER, rows=ROWS, close=CLOSE, spaced=False, ending="\n"):
    text = json.dumps(header, indent=None if not spaced else 1).replace("\n", " ")
    lines = [f"# frameledger {text}", ledger.COLUMNS, *rows, *([close] if close else [])]
    path.write_bytes((ending.join(lines) + ending).encode())
    return path


# Each a copy of the expected file differing in one way: (the file's
# arguments, the `where` its first difference names, how many differences
# there are, and the words the summary names it by). A changed row is two
# differences: the expected line missing, and the new one extra.
QUOTED = [ledger.quoted(row, ledger.LONG_QUOTE) for row in ROWS]
DIFFERENT = {
    "a row written twice": ({"rows": [*ROWS, ROWS[3]]}, ROWS[3], 1, QUOTED[3]),
    "one of two identical rows missing": ({"rows": ROWS[:3]}, ROWS[3], 1, QUOTED[3]),
    "a value with another last digit": ({"rows": [ROWS[0].replace("5.250", "5.251"), *ROWS[1:]]}, ROWS[0], 2,
                                        QUOTED[0]),
    "a field quoted that holds no comma or quote": ({"rows": [ROWS[0].replace("view:1", '"view:1"'), *ROWS[1:]]},
                                                    ROWS[0], 2, QUOTED[0]),
    "a header value changed": ({"header": {**HEADER, "scene": "other"}}, "header.scene", 1, "line's 'scene'"),
    "true in place of 1": ({"header": {**HEADER, "extra": {"flag": True}}}, "header.extra", 1, "line's 'extra'"),
    "the close line missing": ({"close": None}, "close", 1, "the close line is"),
}


def test_expect(capsys, tmp_path):
    """INV-117: a copy with its header keys reordered, its JSON spaced,
    its rows shuffled, CRLF endings and 1.0 for 1 matches, exit 0. Each
    of DIFFERENT alone is exit 1, its difference named in the summary.
    Two FILEs, or an expected file that does not exist, is exit 3."""
    expected = run_file(tmp_path / "expected.csv")
    reordered = dict(reversed(list({**HEADER, "render_scale": 1.0}.items())))
    alike = run_file(tmp_path / "alike.csv", header=reordered, rows=[ROWS[2], ROWS[0], ROWS[3], ROWS[1]],
                     spaced=True, ending="\r\n")
    code, out = check(capsys, "--expect", expected, alike)
    assert (code, out["result"]["expect"]) == (0, {"matches": True, "differences": []})
    assert out["summary"][-1] == f"It matches {expected}."

    for how, (options, where, count, named) in DIFFERENT.items():
        if how == "one of two identical rows missing":  # the expected file holds the row twice
            expected_here = run_file(tmp_path / "twice.csv", rows=[*ROWS, ROWS[3]])
            options = {"rows": ROWS}
        else:
            expected_here = expected
        found = run_file(tmp_path / "found.csv", **options)
        code, out = check(capsys, "--expect", expected_here, found)
        assert code == 1, how
        assert out["result"]["expect"]["matches"] is False, how
        differences = out["result"]["expect"]["differences"]
        assert (differences[0]["where"], len(differences)) == (where, count), how
        places = "1 place" if count == 1 else f"{count} places"
        (sentence,) = [s for s in out["summary"] if s.startswith(f"{found} differs from {expected_here} in ")]
        assert sentence.startswith(f"{found} differs from {expected_here} in {places}; the first: "), how
        assert named in sentence, how

    assert cli.main(["check", "--expect", str(expected), str(alike), str(alike)]) == 3
    assert "--expect takes exactly one FILE" in capsys.readouterr().err
    assert cli.main(["check", "--expect", str(tmp_path / "absent.csv"), str(alike)]) == 3
    assert "absent.csv" in capsys.readouterr().err


def test_expect_names_counts_and_values(capsys, tmp_path):
    """INV-117: the summary names a row with how many times each file holds
    it, and a header key with both values."""
    expected = run_file(tmp_path / "expected.csv")
    twice = run_file(tmp_path / "twice.csv", rows=[*ROWS, ROWS[3]])
    out = check(capsys, "--expect", expected, twice)[1]
    assert f"the row '{ledger.quoted(ROWS[3], ledger.LONG_QUOTE)}' is there once in the expected file and twice " \
           "in this one" in " ".join(out["summary"])
    assert out["result"]["expect"]["differences"] == [{"where": ROWS[3], "expected": 1, "found": 2}]
    changed = run_file(tmp_path / "changed.csv", header={**HEADER, "scene": "other"})
    out = check(capsys, "--expect", expected, changed)[1]
    assert "the header line's 'scene' is \"s\" in the expected file and \"other\" in this one" \
        in " ".join(out["summary"])


@pytest.mark.parametrize("a, b, same", [
    (1, 1.0, True), (True, 1, False), (False, 0, False), (True, True, True),
    ({"a": [1, {"b": False}]}, {"a": [1.0, {"b": False}]}, True), ([1], [1, 1], False), ("1", 1, False),
    (None, None, True), (None, False, False),
])
def test_json_values_compare_as_json(a, b, same):
    """INV-117: numbers by value, booleans only with booleans."""
    assert expect.same(a, b) is same
    assert expect.same(b, a) is same


def test_a_file_breaking_the_format_never_matches(capsys, tmp_path):
    """§ 4.19: FILE must first meet the format. A file holding one row
    twice, which breaks it, against itself is exit 1 and does not match,
    though no difference is found."""
    twice = run_file(tmp_path / "twice.csv", rows=[*ROWS, ROWS[3]])
    code, out = check(capsys, "--expect", twice, twice)
    assert (code, out["result"]["expect"]) == (1, {"matches": False, "differences": []})
    assert out["result"]["files"][0]["breaches"][0]["rule"] == "duplicate"


def test_absent_is_not_null(tmp_path):
    """INV-117: a key the file lacks reads as missing, a JSON null as null;
    in JSON, both are null."""
    expected = run_file(tmp_path / "expected.csv")
    lines = expected.read_text(encoding="utf-8").splitlines()
    with_null = tmp_path / "null.csv"
    with_null.write_text("\n".join([lines[0], '# frameledger-static {"draws": null}', *lines[1:]]) + "\n",
                         encoding="utf-8")
    without = tmp_path / "without.csv"
    without.write_text("\n".join([lines[0], '# frameledger-static {}', *lines[1:]]) + "\n", encoding="utf-8")
    (difference,) = expect.compare(str(with_null), str(without))
    assert difference.sentence() == "the static line's 'draws' is null in the expected file and missing in this one"
    assert difference.entry() == {"where": "static.draws", "expected": None, "found": None}
