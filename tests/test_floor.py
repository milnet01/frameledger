"""The `floor` command: S8's window and single-frame checks.

Invariants from docs/specs/FLED-0001-run-file-format.md § 5: INV-7,
INV-8, INV-9 and INV-18. INV-1's floor half is in test_check.py, beside
its check half. tests/floor_runs.py writes the fixtures named here and
builds the one-off runs.
"""

import json
import subprocess
import sys
from pathlib import Path

import cli
from floor_runs import WARMUP, run_text

ROOT = Path(__file__).parent.parent

FIXTURES = Path(__file__).parent / "fixtures"


def run_floor(capsys, path, *flags):
    code = cli.main(["floor", "--json", str(path), "--fps", "60", *flags])
    out = json.loads(capsys.readouterr().out)
    assert out["exit_code"] == code
    return code, out


def run_walls(capsys, tmp_path, walls, *flags, cuts=()):
    path = tmp_path / "run.csv"
    path.write_text(run_text(walls, cuts), encoding="utf-8")
    return run_floor(capsys, path, *flags)


def test_unfinished_and_dropped(capsys, tmp_path):
    """INV-7: no close line, or rows dropped, is inconclusive even when
    everything passes, and the first sentence says why, before any other
    warning."""
    path = FIXTURES / "passing-run.csv"
    code, out = run_floor(capsys, path)
    assert (code, out["verdict"]) == (0, "pass")
    assert out["result"]["finished"] and out["result"]["rows_dropped"] == 0

    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    unfinished = tmp_path / "unfinished.csv"
    negative = "".join(lines[:-1]).replace("f1,view:1,5,frame,cpu_span,0,8.000", "f1,view:1,5,frame,cpu_span,0,-0.004")
    unfinished.write_text(negative, encoding="utf-8")
    code, out = run_floor(capsys, unfinished)
    assert (code, out["verdict"]) == (2, "inconclusive")
    assert "no close line" in out["summary"][0]
    assert any("negative" in s for s in out["summary"][1:])
    assert out["result"]["finished"] is False

    dropped = tmp_path / "dropped.csv"
    dropped.write_text("".join(lines).replace('"rows_dropped":0', '"rows_dropped":3'), encoding="utf-8")
    code, out = run_floor(capsys, dropped)
    assert (code, out["verdict"]) == (2, "inconclusive")
    assert "dropped 3 rows" in out["summary"][0]
    assert out["result"]["rows_dropped"] == 3
    assert all(w["pass"] for w in out["result"]["windows"])


def test_window_rate(capsys):
    """INV-8: a window's rate is the frames ending in it, and a frame
    ending exactly on a window's end belongs to the next window."""
    for name in ("one-hitch.csv", "edge-frame.csv"):
        code, out = run_floor(capsys, FIXTURES / name, "--no-frames")
        assert (code, out["verdict"]) == (1, "fail"), name
        windows = out["result"]["windows"]
        assert [(w["start_s"], w["fps"]) for w in windows if not w["pass"]] == [(2.0, 59)], name
        assert all(w["fps"] >= 60 for w in windows[1:]), name
        assert out["result"]["slow_frames"] == []


def test_single_frame_budget(capsys):
    """INV-9: one frame over the budget fails even when every window passes;
    --no-frames turns the check off; --allow-frames 1 tolerates exactly one;
    a 16.667 ms frame meets the default 60 FPS budget."""
    path = FIXTURES / "fast-with-one-spike.csv"
    code, out = run_floor(capsys, path)
    assert (code, out["verdict"]) == (1, "fail")
    assert all(w["pass"] for w in out["result"]["windows"])
    assert out["result"]["frames_over_budget"] == 1
    assert out["result"]["slow_frames"] == [
        {"frame": 300, "segment": "view:1", "wall_ms": 30.0, "top_pass": "cpu/cpu_remainder"}]

    assert run_floor(capsys, path, "--no-frames")[0] == 0
    code, out = run_floor(capsys, path, "--allow-frames", "1")
    assert (code, out["result"]["allowed"]) == (0, 1)
    assert run_floor(capsys, path, "--budget-ms", "7.999", "--allow-frames", "1")[0] == 1
    # The spike ends at 2.43 s: inside a longer warm-up, it is not judged.
    assert run_floor(capsys, path, "--warmup-s", "2.5")[0] == 0

    code, out = run_floor(capsys, FIXTURES / "exact-budget.csv")
    assert (code, out["result"]["frames_over_budget"]) == (0, 0)
    assert run_floor(capsys, FIXTURES / "exact-budget.csv", "--budget-ms", "16.666")[0] == 1


def test_cuts_and_partial_windows(capsys):
    """INV-18: a cut starts a new window; windows under one second are
    skipped and counted; with no full window the window check is
    inconclusive."""
    code, out = run_floor(capsys, FIXTURES / "cut-mid-second.csv", "--no-frames")
    assert (code, out["verdict"]) == (0, "pass")
    result = out["result"]
    # Each window after a cut starts where the cut frame ends: 3.249 s and 3.715 s.
    assert [w["start_s"] for w in result["windows"]] == [2.0, 3.715, 4.715]
    assert result["windows_skipped"] == 3

    code, out = run_floor(capsys, FIXTURES / "short-views.csv")
    assert (code, out["verdict"]) == (2, "inconclusive")
    assert out["result"]["windows"] == [] and out["result"]["windows_skipped"] == 4
    assert "no full one-second window" in out["summary"][0]
    # Without the window check, the frames alone decide.
    assert run_floor(capsys, FIXTURES / "short-views.csv", "--no-windows")[0] == 0


def test_cut_frame_is_left_out_of_windows(capsys, tmp_path):
    """The three engines' review: a cut frame, such as a 400 ms level load,
    starts the next window at its end, so it fails only the budget."""
    walls = WARMUP + [16.0] * 75 + [400.0] + [16.0] * 200
    code, out = run_walls(capsys, tmp_path, walls, "--no-frames", cuts=(200,))
    assert (code, out["verdict"]) == (0, "pass")
    assert out["result"]["windows"][1]["start_s"] == 3.599
    code, out = run_walls(capsys, tmp_path, walls, cuts=(200,))
    assert code == 1 and out["result"]["slow_frames"][0]["frame"] == 200


def test_cut_on_a_window_boundary(tmp_path):
    """A cut frame ending exactly where a window ends starts the next one
    once. Run apart, so a loop that never ends fails the test."""
    path = tmp_path / "boundary.csv"
    # 77 frames of 13 ms take the timeline from 1.999 s to exactly 3 s.
    path.write_text(run_text(WARMUP + [13.0] * 77 + [16.0] * 130, cuts=(201,)), encoding="utf-8")
    done = subprocess.run([sys.executable, "-I", str(ROOT / "src" / "frameledger"), "floor", "--json",
                           str(path), "--fps", "60"], capture_output=True, text=True, timeout=30, check=False)
    out = json.loads(done.stdout)
    assert (done.returncode, out["verdict"]) == (0, "pass")
    assert [w["start_s"] for w in out["result"]["windows"]] == [2.0, 3.0, 4.0]
    # The cut frame ends at 3 s, so the window starting there leaves it out.
    assert out["result"]["windows"][1]["fps"] == 62


def test_last_window_ending_on_the_run_end(capsys, tmp_path):
    """The frame ending exactly at the run's end opens a last, short
    window, which is skipped and counted."""
    # 187 frames of 16 ms and one of 9 end the run exactly at 5 s.
    code, out = run_walls(capsys, tmp_path, WARMUP + [16.0] * 187 + [9.0])
    assert code == 0
    assert [w["start_s"] for w in out["result"]["windows"]] == [2.0, 3.0, 4.0]
    assert out["result"]["windows_skipped"] == 1


def test_warmup_boundary(capsys):
    """A frame ending exactly when the warm-up ends is judged."""
    path = FIXTURES / "fast-with-one-spike.csv"
    # 300 frames of 8 ms, then the 30 ms spike, ending at 2.430 s.
    assert run_floor(capsys, path, "--warmup-s", "2.43")[0] == 1
    assert run_floor(capsys, path, "--warmup-s", "2.430001")[0] == 0


def test_nothing_judged_is_inconclusive(capsys):
    """A frame check with no frame after the warm-up has not passed."""
    path = FIXTURES / "passing-run.csv"
    code, out = run_floor(capsys, path, "--no-windows", "--warmup-s", "100")
    assert (code, out["verdict"]) == (2, "inconclusive")
    assert "no frame ends after" in out["summary"][0]


def test_timeline_gap_is_inconclusive(capsys, tmp_path):
    """§ 6: a frame other than the last with no wall, or a frame number
    with no rows at all, stops the timeline."""
    rows = (FIXTURES / "passing-run.csv").read_text(encoding="utf-8")
    gap = tmp_path / "gap.csv"
    gap.write_text(rows.replace("f1,view:1,200,frame,wall,0,16.000\n", ""), encoding="utf-8")
    code, out = run_floor(capsys, gap)
    assert (code, out["verdict"]) == (2, "inconclusive")
    assert out["summary"][0].startswith("Frame 200 has no frame/wall row")

    hole = tmp_path / "hole.csv"
    hole.write_text("".join(line for line in rows.splitlines(keepends=True)
                            if not line.startswith("f1,view:1,200,")), encoding="utf-8")
    code, out = run_floor(capsys, hole)
    assert (code, out["verdict"]) == (2, "inconclusive")
    assert out["summary"][0].startswith("Frame 200 is missing")
    assert cli.main(["check", "--json", str(hole)]) == 0
    warnings = json.loads(capsys.readouterr().out)["warnings"]
    assert [w["code"] for w in warnings] == ["frame_missing"]


def test_frame_failure_stands_under_drops(capsys, tmp_path):
    """The three engines' review: a frame's own wall row is real, so a
    frame over the budget fails even with rows dropped. The window check,
    which a missing frame can move, stays inconclusive."""
    rows = (FIXTURES / "fast-with-one-spike.csv").read_text(encoding="utf-8")
    dropped = tmp_path / "dropped.csv"
    dropped.write_text(rows.replace('"rows_dropped":0', '"rows_dropped":1'), encoding="utf-8")
    code, out = run_floor(capsys, dropped)
    assert (code, out["verdict"]) == (1, "fail")
    assert "dropped 1 row" in out["summary"][0]

    rows = (FIXTURES / "one-hitch.csv").read_text(encoding="utf-8")
    dropped.write_text(rows.replace('"rows_dropped":0', '"rows_dropped":1'), encoding="utf-8")
    code, out = run_floor(capsys, dropped, "--no-frames")
    assert (code, out["verdict"]) == (2, "inconclusive")
    assert any("may be an artefact" in s for s in out["summary"])


def test_bad_options_are_exit_3(capsys):
    path = str(FIXTURES / "passing-run.csv")
    for flags in (["--fps", "0"], ["--fps", "sixty"], ["--fps", "60", "--budget-ms", "16.6667"],
                  ["--fps", "60", "--warmup-s", "-1"], ["--fps", "60", "--allow-frames", "-1"],
                  ["--fps", "60", "--no-windows", "--no-frames"], [], ["--fps", "1e-30"], ["--fps", "1e7"],
                  ["--fps", "60", "--budget-ms", "1e30"], ["--fps", "1e-999999"],
                  ["--fps", "60", "--warmup-s", "1e999999"]):
        assert cli.main(["floor", path, *flags]) == 3, flags
    capsys.readouterr()


def test_breach_is_exit_3(capsys):
    """§ 6: floor never skips a malformed row; it stops naming the line."""
    code, out = run_floor(capsys, FIXTURES / "zero-wall.csv")
    assert (code, out["verdict"], out["result"]) == (3, "error", {})
    assert "line" in out["summary"][0]
