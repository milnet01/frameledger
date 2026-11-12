"""Surveying many runs (S9, FLED-0012).

Invariants from docs/specs/FLED-0001-run-file-format.md § 5: INV-69 to
INV-72, the rules of § 4.13. The fixtures are floor's; the other runs
are built here.
"""

import json
from pathlib import Path

import cli
from floor_runs import HEADER, WARMUP

FIXTURES = Path(__file__).parent / "fixtures"


def run_text(frames: list) -> str:
    """One frame per entry, (segment, wall in ms); 125 warm-up frames of
    view:1 come first, so every listed frame is judged. A last frame
    with no wall closes the run."""
    lines = [HEADER, "run_id,segment,frame,category,name,depth,value"]
    walls = [("view:1", wall) for wall in WARMUP] + frames + [(frames[-1][0], None)]
    for number, (segment, wall) in enumerate(walls):
        lines.append(f"f1,{segment},{number},frame,cpu_span,0,8.000")
        if wall is not None:
            lines.append(f"f1,{segment},{number},frame,wall,0,{wall:.3f}")
    lines.append(f'# frameledger-close {{"rows_dropped":0,"frames":{len(walls)}}}')
    return "\n".join(lines) + "\n"


def steady(count: int, wall: float, segment: str = "view:1") -> list:
    return [(segment, wall)] * count


def survey(capsys, paths, *flags) -> tuple[int, dict]:
    """`survey --json` over paths. Returns (exit code, parsed output)."""
    code = cli.main(["survey", *map(str, paths), *flags, "--json"])
    out = json.loads(capsys.readouterr().out)
    assert out["exit_code"] == code
    return code, out


def write(tmp_path, name: str, frames: list) -> Path:
    path = tmp_path / name
    path.write_text(run_text(frames), encoding="utf-8")
    return path


def test_flag_is_floors(capsys, tmp_path):
    """INV-69: survey flags a run exactly when floor's single-frame check
    fails it, with the same count, and is inconclusive exactly when it is."""
    compared = 0
    for path in sorted(FIXTURES.glob("*.csv")):
        assert cli.main(["floor", str(path), "--fps", "60", "--no-windows", "--json"]) is not None
        floor = json.loads(capsys.readouterr().out)
        if floor["verdict"] == "error":
            continue
        code, out = survey(capsys, [path], "--fps", "60")
        entry = out["result"]["runs"][0]
        expected = {"fail": "flagged", "pass": "clean", "inconclusive": "inconclusive"}[floor["verdict"]]
        assert entry["verdict"] == expected, path.name
        assert entry["frames_over_budget"] == floor["result"]["frames_over_budget"], path.name
        compared += 1
    assert compared >= 10

    hitch = FIXTURES / "one-hitch.csv"
    code, out = survey(capsys, [hitch], "--fps", "60")
    assert (code, out["result"]["runs"][0]["frames_over_budget"]) == (1, 1)
    assert survey(capsys, [hitch], "--fps", "60", "--allow-frames", "1")[0] == 0

    slow_start = tmp_path / "slow-start.csv"
    slow_start.write_text(run_text(steady(200, 16.0)).replace(
        "f1,view:1,0,frame,wall,0,16.000", "f1,view:1,0,frame,wall,0,90.000"), encoding="utf-8")
    assert survey(capsys, [slow_start], "--fps", "60")[0] == 0
    assert survey(capsys, [slow_start], "--fps", "60", "--warmup-s", "0")[0] == 1
    # FLED-0024: a long warm-up is shown as given, not as 1e+09.
    code, out = survey(capsys, [slow_start], "--fps", "60", "--warmup-s", "999999999")
    assert any("the 999999999 s warm-up" in s for s in out["summary"]), out["summary"]


def test_rank(capsys, tmp_path):
    """INV-70: runs rank by their worst kind of 100 or more frames' p99,
    naming its worst segment; a shorter kind is listed but ranks nothing."""
    first = write(tmp_path, "a.csv", steady(150, 20.0) + steady(50, 90.0, "load:1"))
    second = write(tmp_path, "b.csv", steady(150, 30.0))
    third = write(tmp_path, "c.csv", steady(150, 25.0))
    short = write(tmp_path, "d.csv", steady(60, 40.0))
    code, out = survey(capsys, [first, second, third, short], "--budget-ms", "100")
    runs = out["result"]["runs"]
    assert code == 0
    assert [(Path(r["path"]).name, r["rank"]) for r in runs] == [
        ("b.csv", 1), ("c.csv", 2), ("a.csv", 3), ("d.csv", None)]
    load = next(k for k in runs[2]["kinds"] if k["segment_kind"] == "load")
    assert (load["ranked"], load["p99_ms"], runs[2]["p99_ms"]) == (False, 90.0, 20.0)
    assert runs[3]["worst_kind"] is None and runs[3]["p99_ms"] is None

    views = write(tmp_path, "e.csv", steady(150, 18.0) + steady(150, 30.0, "view:2"))
    code, out = survey(capsys, [views], "--budget-ms", "100")
    entry = out["result"]["runs"][0]
    assert (entry["worst_kind"], entry["worst_segment"], entry["p99_ms"]) == ("view", "view:2", 30.0)


def test_unjudged_files(capsys, tmp_path):
    """INV-71: a broken file is listed as unjudged and the others are
    judged; exit 2, or 1 with a flagged run, or 0 when all are clean."""
    empty = tmp_path / "empty.csv"
    empty.write_text("", encoding="utf-8")
    breach = FIXTURES / "zero-wall.csv"
    clean = [write(tmp_path, f"clean-{i}.csv", steady(150, 10.0)) for i in (1, 2)]
    code, out = survey(capsys, [empty, breach, *clean], "--fps", "60")
    runs = out["result"]["runs"]
    assert (code, out["verdict"]) == (2, "inconclusive")
    assert [r["verdict"] for r in runs] == ["clean", "clean", "unjudged", "unjudged"]
    assert all(r["reason"] for r in runs[2:]) and all(r["reason"] is None for r in runs[:2])
    assert [r["rank"] for r in runs] == [1, 2, None, None]

    flagged = write(tmp_path, "flagged.csv", steady(150, 10.0) + steady(1, 50.0))
    assert survey(capsys, [empty, breach, *clean, flagged], "--fps", "60")[0] == 1
    code, out = survey(capsys, clean, "--fps", "60")
    assert (code, out["verdict"]) == (0, "pass")


def test_flag_names_its_frame(capsys, tmp_path):
    """INV-72: a flag set by a kind too short to rank names that frame,
    and the text says floor's per-second check was not run."""
    frames = steady(200, 10.0) + steady(20, 10.0, "load:1") + steady(1, 80.0, "load:1") + steady(19, 10.0, "load:1")
    path = write(tmp_path, "maps-with-a-long-name-" + "x" * 80 + "-e1m2.csv", frames)
    code, out = survey(capsys, [path], "--fps", "60")
    entry = out["result"]["runs"][0]
    assert (code, entry["verdict"], entry["worst_kind"]) == (1, "flagged", "view")
    slowest = entry["slowest_over"]
    assert (slowest["segment"], slowest["wall_ms"], slowest["top_pass"]) == ("load:1", 80.0, "cpu/cpu_remainder")
    assert slowest["frame"] == len(WARMUP) + 220

    assert cli.main(["survey", str(path), "--fps", "60"]) == 1
    text = capsys.readouterr().out.splitlines()
    assert "load:1" in text[0] and "per-second check was not run" in text[0]
    table = text[text.index("") + 1:]
    assert all(len(line) <= 100 for line in table), max(table, key=len)
    assert any("…" in line and "e1m2.csv" in line for line in table)
