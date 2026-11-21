"""Text that names frames with no segment says so in words (FLED-0083).

A segment kind of None once printed "in unsegmented segments". Each
sentence saying where frames are now goes through
run_report.kinds_phrase, and each text heading through render's
_frames_in. JSON is unchanged: segment_kind stays null.
"""

import json

import cli
from test_budget import budget, budget_text, frame
from test_budget import run_text as budget_run
from test_compare import compare
from test_noisy_run import CALM, run_text

NONE = [("", wall) for _, wall in CALM]


def report_text(capsys, tmp_path, run: str) -> str:
    path = tmp_path / "run.csv"
    path.write_text(run, encoding="utf-8")
    cli.main(["report", str(path)])
    return capsys.readouterr().out


def test_report_names_frames_with_no_segment(capsys, tmp_path):
    out = report_text(capsys, tmp_path, budget_run([frame(segment="", ssao=1.5)] * 101))
    assert "The run has 101 frames, none of them in a segment." in out
    assert "In frames with no segment the costliest pass is " in out
    assert "GPU passes in frames with no segment, by time spent:" in out
    assert "Frame times in frames with no segment:" in out
    assert "unsegmented" not in out


def test_report_names_both_when_mixed(capsys, tmp_path):
    frames = [frame(segment="", ssao=1.5)] * 50 + [frame(segment="view:1", ssao=1.5)] * 51
    out = report_text(capsys, tmp_path, budget_run(frames))
    assert "The run has 101 frames, in frames with no segment and view segments." in out


def test_compare_names_frames_with_no_segment(capsys, tmp_path):
    slow = NONE[:-21] + [("", 40.0)] * 21
    old = [run_text(NONE, f"o{i}", 2 * i) for i in range(3)]
    new = [run_text(frames, f"n{i}", 2 * i + 1) for i, frames in enumerate([NONE, slow, NONE])]
    _, result = compare(capsys, tmp_path, old, new)
    text = json.dumps(result)
    assert "new-2: 21 of its 1000 frame/wall values in frames with no segment, 2.10%" in text
    assert "In frames with no segment the median frame/wall went from 16.000 ms" in text
    assert "unsegmented" not in text
    assert {r["noise"][0]["segment_kind"] for r in result["result"]["runs"]} == {None}


def test_budget_names_frames_with_no_segment(capsys, tmp_path):
    run = budget_run([frame(segment="", a=2.5)] * 101)
    _, out = budget(capsys, tmp_path, run, budget_text("gpu,a,,,median,2.000"))
    assert "gpu/a median in frames with no segment is 2.500 ms, over its 2.000 ms budget." in out["summary"]
