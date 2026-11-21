"""Text that names frames with no segment says so in words (FLED-0083).

A segment kind of None once printed "in unsegmented segments". Each
sentence saying where frames are now goes through
run_report.kinds_phrase, and each text heading through render's
_frames_in. JSON is unchanged: segment_kind stays null.
"""

import cli
import render
import run_report
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
    assert "The run has 101 frames, in frames with no segment and in view segments." in out


def test_kinds_phrase_joins_named_kinds():
    assert run_report.kinds_phrase(["menu", "view"]) == "menu, view segments"
    assert run_report.kinds_phrase([None, "menu", "view"]) == "frames with no segment and in menu, view segments"


def test_render_says_one_kind_as_run_report_does():
    """render may import no analyser module, so it keeps its own copy of
    the one-kind phrase; this holds the two alike."""
    for kind in (None, "view"):
        assert render._frames_in(kind) == run_report.kinds_phrase([kind])


def test_compare_names_frames_with_no_segment(capsys, tmp_path):
    slow = NONE[:-21] + [("", 40.0)] * 21
    old = [run_text(NONE, f"o{i}", 2 * i) for i in range(3)]
    new = [run_text(frames, f"n{i}", 2 * i + 1) for i, frames in enumerate([NONE, slow, NONE])]
    _, result = compare(capsys, tmp_path, old, new)
    noisy = [w["message"] for w in result["warnings"] if w["code"] == "noisy_run"]
    assert [m.split(", 2.10%")[0] for m in noisy] == [
        "new-2: 21 of its 1000 frame/wall values in frames with no segment"]
    assert any(s.startswith("In frames with no segment the median frame/wall went from 16.000 ms")
               for s in result["summary"])
    assert {r["noise"][0]["segment_kind"] for r in result["result"]["runs"]} == {None}


def test_budget_names_frames_with_no_segment(capsys, tmp_path):
    run = budget_run([frame(segment="", a=2.5)] * 101)
    _, out = budget(capsys, tmp_path, run, budget_text("gpu,a,,,median,2.000"))
    assert "gpu/a median in frames with no segment is 2.500 ms, over its 2.000 ms budget." in out["summary"]


def test_compare_short_run_names_frames_with_no_segment(capsys, tmp_path):
    short = NONE[:50]
    old = [run_text(short, f"o{i}", 2 * i) for i in range(3)]
    new = [run_text(short, f"n{i}", 2 * i + 1) for i in range(3)]
    _, result = compare(capsys, tmp_path, old, new)
    assert any(s.startswith("Some run has fewer than 100 frame/wall values in frames with no segment, so")
               for s in result["summary"]), result["summary"]


def test_budget_unmatched_names_frames_outside_a_segment(capsys, tmp_path):
    run = budget_run([frame(segment="", a=2.5)] * 101)
    _, out = budget(capsys, tmp_path, run, budget_text("gpu,missing,,,median,2.000"))
    assert any("gpu/missing is in no frame outside a segment judged" in s for s in out["summary"]), out["summary"]
