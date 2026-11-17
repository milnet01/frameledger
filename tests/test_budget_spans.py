"""Budgets on a frame's CPU and GPU spans (FLED-0077).

Invariant INV-125 from docs/specs/FLED-0001-run-file-format.md § 5, the
rules of § 4.12's frame lines. Each run and budget file is built here as
text.
"""

import json

import cli
import ledger
from floor_runs import HEADER


def run_text(gpu: bool = True, gpu_missing: range = range(0)) -> str:
    """200 view frames, frame/gpu_span 10.000 ms but 20.000 on the three
    slowest, the first three, then 50 load frames at 30.000;
    frame/cpu_span 5.000 throughout, and frame/gpu_span on none of the
    frames in `gpu_missing`. Every row is at depth 0."""
    lines = [HEADER, ledger.COLUMNS]
    spans = [("view:1", 20.0 if frame < 3 else 10.0) for frame in range(200)] + [("load:1", 30.0)] * 50
    for frame, (segment, span) in enumerate(spans):
        lines.append(f"f1,{segment},{frame},frame,cpu_span,0,5.000")
        if gpu and frame not in gpu_missing:
            lines.append(f"f1,{segment},{frame},frame,gpu_span,0,{span:.3f}")
        if frame != len(spans) - 1:
            lines.append(f"f1,{segment},{frame},frame,wall,0,33.000")
    lines.append(f'# frameledger-close {{"rows_dropped":0,"frames":{len(spans)}}}')
    return "\n".join(lines) + "\n"


def budget(capsys, tmp_path, *budgets: str, gpu: bool = True, gpu_missing: range = range(0),
           flags: tuple[str, ...] = ()) -> tuple[int, dict]:
    run = tmp_path / ("run.csv" if gpu else "no-gpu.csv")
    run.write_text(run_text(gpu, gpu_missing), encoding="utf-8")
    path = tmp_path / "budgets.csv"
    path.write_text('# frameledger-budget {"schema":1}\ncategory,name,kind,depth,statistic,limit_ms\n'
                    + "".join(f"{line}\n" for line in budgets), encoding="utf-8")
    code = cli.main(["budget", str(run), "--budgets", str(path), *flags, "--json"])
    return code, json.loads(capsys.readouterr().out)


def test_frame_span_budgets(capsys, tmp_path):
    code, out = budget(capsys, tmp_path, "frame,gpu_span,view,,p99,16.667")
    assert code == 1
    entry = out["result"]["budgets"][0]
    assert (entry["category"], entry["name"], entry["depth"], entry["value_ms"], entry["frames"]) == \
        ("frame", "gpu_span", None, 20.0, 200)
    assert "frame/gpu_span p99 in view segments is 20.000 ms, over its 16.667 ms budget." in out["summary"]

    code, out = budget(capsys, tmp_path, "frame,gpu_span,view,,median,16.667", "frame,gpu_span,view,,p99,20.000")
    assert code == 0
    assert [b["value_ms"] for b in out["result"]["budgets"]] == [10.0, 20.0]
    cli.main(["report", str(tmp_path / "run.csv"), "--json"])
    report = json.loads(capsys.readouterr().out)["result"]["frame_times"]
    view = next(f for f in report if (f["name"], f["segment_kind"]) == ("gpu_span", "view"))
    assert (view["median_ms"], view["p99_ms"]) == (10.0, 20.0)  # report's figures

    # A named kind replaces `*` there; the load entry is over 50 frames, so it warns.
    code, out = budget(capsys, tmp_path, "frame,gpu_span,*,,p99,20.000", "frame,gpu_span,load,,p99,40.000")
    assert code == 0
    assert [(b["segment_kind"], b["limit_ms"]) for b in out["result"]["budgets"]] == \
        [("view", 20.0), ("load", 40.0)]
    assert [w["code"] for w in out["warnings"]].count("budget_few_frames") == 1

    assert budget(capsys, tmp_path, "frame,cpu_span,*,,median,5.000")[0] == 0
    assert budget(capsys, tmp_path, "frame,cpu_span,*,,median,4.999")[0] == 1

    code, out = budget(capsys, tmp_path, "frame,gpu_span,*,,p99,20.000", gpu=False)
    assert code == 2
    assert out["result"]["unmatched"][0]["name"] == "gpu_span"
    code, out = budget(capsys, tmp_path, "frame,gpu_span,view,,p99,20.000", gpu=False)
    assert code == 2
    assert out["result"]["unmatched"] == [{"line": 3, "category": "frame", "name": "gpu_span",
                                           "segment_kind": "view", "depth": None, "statistic": "p99"}]
    assert any("the span is in none of those frames" in s for s in out["summary"])


def test_frames_holding_the_span(capsys, tmp_path):
    # Fifty view frames without a GPU span: the count, and the 100-frame warning, are over the other 150.
    code, out = budget(capsys, tmp_path, "frame,gpu_span,view,,p99,20.000", gpu_missing=range(100, 150))
    assert out["result"]["budgets"][0]["frames"] == 150
    code, out = budget(capsys, tmp_path, "frame,gpu_span,view,,p99,20.000", gpu_missing=range(60, 160))
    assert out["result"]["budgets"][0]["frames"] == 100
    assert "budget_few_frames" not in [w["code"] for w in out["warnings"]]
    code, out = budget(capsys, tmp_path, "frame,gpu_span,view,,p99,20.000", gpu_missing=range(60, 161))
    assert "budget_few_frames" in [w["code"] for w in out["warnings"]]


def test_a_span_has_no_depth(capsys, tmp_path):
    """Span rows at two depths are one span: a pass line's empty depth would refuse them."""
    run = tmp_path / "deep.csv"
    run.write_text("".join(line.replace(",frame,gpu_span,0,", ",frame,gpu_span,3,") if i % 2 else line
                           for i, line in enumerate(run_text().splitlines(keepends=True))), encoding="utf-8")
    path = tmp_path / "budgets.csv"
    path.write_text('# frameledger-budget {"schema":1}\ncategory,name,kind,depth,statistic,limit_ms\n'
                    "frame,gpu_span,view,,p99,20.000\n", encoding="utf-8")
    code = cli.main(["budget", str(run), "--budgets", str(path), "--json"])
    out = json.loads(capsys.readouterr().out)
    assert code == 0 and out["result"]["budgets"][0]["frames"] == 200


def test_a_span_after_the_warm_up(capsys, tmp_path):
    # The three slow frames come first, so a 1 s warm-up (33 ms frames) leaves them out.
    assert budget(capsys, tmp_path, "frame,gpu_span,view,,p99,16.667")[0] == 1
    code, out = budget(capsys, tmp_path, "frame,gpu_span,view,,p99,16.667", flags=("--warmup-s", "1"))
    assert code == 0 and out["result"]["budgets"][0]["value_ms"] == 10.0


def test_frame_span_refusals(capsys, tmp_path):
    code, out = budget(capsys, tmp_path, "frame,wall,*,,p99,16.667")
    assert code == 3
    assert "line 3" in out["summary"][0] and "floor" in out["summary"][0]
    for line in ("frame,fence_wait,*,,p99,16.667", "frame,gpu_span,view,0,p99,16.667"):
        code, out = budget(capsys, tmp_path, line)
        assert code == 3
        assert "line 3" in out["summary"][0]
