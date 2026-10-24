"""The `floor` command: S8's window and single-frame checks.

Invariants from docs/specs/FLED-0001-run-file-format.md § 5: INV-7,
INV-8, INV-9 and INV-18. INV-1's floor half is in test_check.py, beside
its check half. tests/fixtures/make_floor_fixtures.py writes the
fixtures named here.
"""

import json
from pathlib import Path

import cli

FIXTURES = Path(__file__).parent / "fixtures"


def run_floor(capsys, path, *flags):
    code = cli.main(["floor", "--json", str(path), "--fps", "60", *flags])
    out = json.loads(capsys.readouterr().out)
    assert out["exit_code"] == code
    return code, out


def test_unfinished_and_dropped(capsys, tmp_path):
    """INV-7: no close line, or rows dropped, is inconclusive even when
    everything passes, and the first sentence says why."""
    path = FIXTURES / "passing-run.csv"
    code, out = run_floor(capsys, path)
    assert (code, out["verdict"]) == (0, "pass")
    assert out["result"]["finished"] and out["result"]["rows_dropped"] == 0

    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    unfinished = tmp_path / "unfinished.csv"
    unfinished.write_text("".join(lines[:-1]), encoding="utf-8")
    code, out = run_floor(capsys, unfinished)
    assert (code, out["verdict"]) == (2, "inconclusive")
    assert "no close line" in out["summary"][0]
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
    assert [w["start_s"] for w in result["windows"]] == [2.0, 3.699, 4.699]
    assert result["windows_skipped"] == 3

    code, out = run_floor(capsys, FIXTURES / "short-views.csv")
    assert (code, out["verdict"]) == (2, "inconclusive")
    assert out["result"]["windows"] == [] and out["result"]["windows_skipped"] == 4
    assert "no full one-second window" in out["summary"][0]
    # Without the window check, the frames alone decide.
    assert run_floor(capsys, FIXTURES / "short-views.csv", "--no-windows")[0] == 0


def test_timeline_gap_is_inconclusive(capsys, tmp_path):
    """§ 6: a frame other than the last with no wall stops the timeline."""
    rows = (FIXTURES / "passing-run.csv").read_text(encoding="utf-8")
    gap = tmp_path / "gap.csv"
    gap.write_text(rows.replace("f1,view:1,200,frame,wall,0,16.000\n", ""), encoding="utf-8")
    code, out = run_floor(capsys, gap)
    assert (code, out["verdict"]) == (2, "inconclusive")
    assert "frame 200 has no frame/wall" in out["summary"][0]


def test_failure_under_drops_stays_inconclusive(capsys, tmp_path):
    """Dropped rows may have moved frames between windows, so even a
    failure is inconclusive; the summary still names it."""
    rows = (FIXTURES / "fast-with-one-spike.csv").read_text(encoding="utf-8")
    dropped = tmp_path / "dropped.csv"
    dropped.write_text(rows.replace('"rows_dropped":0', '"rows_dropped":1'), encoding="utf-8")
    code, out = run_floor(capsys, dropped)
    assert (code, out["verdict"]) == (2, "inconclusive")
    assert any("would fail" in s and "1 frame" in s for s in out["summary"])


def test_bad_options_are_exit_3(capsys):
    path = str(FIXTURES / "passing-run.csv")
    for flags in (["--fps", "0"], ["--fps", "sixty"], ["--fps", "60", "--budget-ms", "16.6667"],
                  ["--fps", "60", "--warmup-s", "-1"], ["--fps", "60", "--allow-frames", "-1"],
                  ["--fps", "60", "--no-windows", "--no-frames"], []):
        assert cli.main(["floor", path, *flags]) == 3, flags
    capsys.readouterr()


def test_breach_is_exit_3(capsys):
    """§ 6: floor never skips a malformed row; it stops naming the line."""
    code, out = run_floor(capsys, FIXTURES / "zero-wall.csv")
    assert (code, out["verdict"], out["result"]) == (3, "error", {})
    assert "line" in out["summary"][0]
