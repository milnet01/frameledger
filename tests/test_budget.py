"""Pass budgets (S12).

Invariants from docs/specs/FLED-0001-run-file-format.md § 5: INV-54 to
INV-63, the rules of § 4.12. Every run and budget file is built here.
"""

import json

import pytest

import cli

HEADER = {
    "schema": 1, "run_id": "r", "engine": "doom-ants", "tool": {"name": "bench", "version": "1.0"},
    "build_type": "release", "commit": "c80d41d", "dirty": False,
    "device": "AMD Radeon RX 9070 XT", "renderer": "AMD Radeon RX 9070 XT (radeonsi)",
    "driver": "Mesa 26.2", "api": "vulkan-1.3", "resolution": [1920, 1080], "render_scale": 1.0,
    "vsync": False, "pipelined": True, "display": "headless", "scene": "e1m1",
    "inputs": [{"name": "e1m1", "hash": "sha256:" + "ab" * 32, "bytes": 48213}],
    "started_utc": "2026-10-29T12:00:00Z",
}
COLUMNS = "category,name,kind,depth,statistic,limit_ms"


def frame(segment="view:1", wall=10.0, gpu_span=True, **gpu):
    """One frame: (segment, {(category, name, depth): value}). Each keyword
    is a gpu pass at depth 0, or at depth D when given as (value, D)."""
    rows = {("frame", "wall", 0): wall, ("frame", "cpu_span", 0): 8.0}
    if gpu_span:
        rows[("frame", "gpu_span", 0)] = 12.0
    for name, value in gpu.items():
        value, depth = value if isinstance(value, tuple) else (value, 0)
        rows[("gpu", name, depth)] = value
    return segment, rows


def run_text(frames, close=True, dropped=0, **header):
    """A run of `frames`; a None leaves that frame number out, a hole. The
    last frame has no frame/wall, as in a real run."""
    fields = {**HEADER, **header}
    lines = [f"# frameledger {json.dumps(fields)}", "run_id,segment,frame,category,name,depth,value"]
    for number, entry in enumerate(frames):
        if entry is None:
            continue
        segment, rows = entry
        for (category, name, depth), value in rows.items():
            if (category, name) == ("frame", "wall") and number == len(frames) - 1:
                continue
            lines.append(f"r,{segment},{number},{category},{name},{depth},{value:.3f}")
    if close:
        lines.append(f'# frameledger-close {{"rows_dropped":{dropped},"frames":{len(frames)}}}')
    return "\n".join(lines) + "\n"


def budget_text(*lines, header='{"schema":1}'):
    return "\n".join([f"# frameledger-budget {header}", COLUMNS, *lines]) + "\n"


def budget(capsys, tmp_path, run, budgets, *flags):
    """Run `budget --json` on a run text and a budget text. Returns (exit
    code, parsed result)."""
    run_path, budget_path = tmp_path / "run.csv", tmp_path / "budgets.csv"
    run_path.write_text(run, encoding="utf-8")
    budget_path.write_text(budgets, encoding="utf-8")
    code = cli.main(["budget", str(run_path), "--budgets", str(budget_path), *flags, "--json"])
    out = json.loads(capsys.readouterr().out)
    assert out["exit_code"] == code
    return code, out


def entry(entries, **match):
    found = [e for e in entries if all(e[k] == v for k, v in match.items())]
    assert len(found) == 1, (match, entries)
    return found[0]


def test_value_is_reports(capsys, tmp_path):
    """INV-54: at the default warm-up, a budget's value is report's figure,
    compared exactly. Three frames with no gpu_span carry a 50 ms ssao row;
    counted, they would make the p99 50.000."""
    frames = [frame(ssao=1.5)] * 98 + [frame(ssao=2.31)] * 2 + [frame(gpu_span=False, ssao=50.0)] * 3
    frames.append(frame(ssao=1.5))
    run = run_text(frames)
    code, out = budget(capsys, tmp_path, run, budget_text("gpu,ssao,view,0,median,1.500",
                                                          "gpu,ssao,view,0,p99,2.309"))
    assert (code, out["verdict"]) == (1, "fail")
    median, p99 = out["result"]["budgets"]
    assert (median["value_ms"], median["over"], median["over_ms"]) == (1.5, False, 0.0)
    assert (p99["value_ms"], p99["over"], p99["over_ms"]) == (2.31, True, 0.001)

    (tmp_path / "run.csv").write_text(run, encoding="utf-8")
    cli.main(["report", "--json", str(tmp_path / "run.csv")])
    passes = json.loads(capsys.readouterr().out)["result"]["passes"]
    reported = entry(passes, category="gpu", name="ssao", segment_kind="view")
    assert (reported["median_ms"], reported["p99_ms"]) == (median["value_ms"], p99["value_ms"])


def test_every_breach_named(capsys, tmp_path):
    """INV-55: every pass over budget is named, most over first."""
    run = run_text([frame(a=2.5, b=3.0, c=1.0)] * 101)
    code, out = budget(capsys, tmp_path, run, budget_text("gpu,a,view,,median,2.000",
                                                          "gpu,b,view,,median,2.000",
                                                          "gpu,c,view,,median,2.000"))
    assert (code, out["verdict"]) == (1, "fail")
    over = [s for s in out["summary"] if "over its" in s]
    assert over == ["gpu/b median in view segments is 3.000 ms, over its 2.000 ms budget.",
                    "gpu/a median in view segments is 2.500 ms, over its 2.000 ms budget."]
    assert [e["name"] for e in out["result"]["budgets"]] == ["a", "b", "c"]


def test_each_kind_apart(capsys, tmp_path):
    """INV-56: `*` judges each kind apart, and takes a warm-up kind too."""
    frames = [frame("view:1", x=1.0)] * 60 + [frame("move:1-2", x=3.0)] * 40
    code, out = budget(capsys, tmp_path, run_text(frames), budget_text("gpu,x,*,,median,2.000"))
    assert (code, out["verdict"]) == (1, "fail")  # pooled, the median is 1.000 and would hold
    budgets = out["result"]["budgets"]
    assert [(e["segment_kind"], e["over"]) for e in budgets] == [("move", True), ("view", False)]

    frames = [frame("warmup:0", x=5.0)] * 10 + frames
    code, out = budget(capsys, tmp_path, run_text(frames), budget_text("gpu,x,*,,median,2.000"))
    assert [e["segment_kind"] for e in out["result"]["budgets"] if e["over"]] == ["move", "warmup"]
    code, out = budget(capsys, tmp_path, run_text(frames), budget_text("gpu,x,view,,median,2.000",
                                                                       "gpu,x,move,,median,4.000"))
    assert (code, [e["segment_kind"] for e in out["result"]["budgets"]]) == (0, ["view", "move"])


def test_unmatched(capsys, tmp_path):
    """INV-57: a budget nothing matches is never a pass."""
    run = run_text([frame(x=1.0)] * 101)
    code, out = budget(capsys, tmp_path, run, budget_text("gpu,x,view,,median,2.000",
                                                          "gpu,renamed,view,,median,2.000",
                                                          "gpu,x,move,,median,2.000",
                                                          "gpu,gone,*,,p99,2.000"))
    assert (code, out["verdict"]) == (2, "inconclusive")
    unmatched = out["result"]["unmatched"]
    assert [(u["line"], u["name"], u["segment_kind"]) for u in unmatched] == [
        (4, "renamed", "view"), (5, "x", "move"), (6, "gone", "*")]
    assert sum("fix the budget file or the engine" in s for s in out["summary"]) == 3

    code, out = budget(capsys, tmp_path, run, budget_text("gpu,x,view,,median,0.500",
                                                          "gpu,renamed,view,,median,2.000"))
    assert (code, out["verdict"]) == (1, "fail")
    assert [u["name"] for u in out["result"]["unmatched"]] == ["renamed"]
    assert any("gpu/renamed" in s for s in out["summary"])


@pytest.mark.parametrize("incomplete", [{"dropped": 3}, {"close": False}])
def test_dropped_and_unfinished(capsys, tmp_path, incomplete):
    """INV-58: dropped rows or no close line: holding budgets are
    inconclusive, and a breach still fails."""
    run = run_text([frame(x=1.0)] * 101, **incomplete)
    code, out = budget(capsys, tmp_path, run, budget_text("gpu,x,view,,median,2.000"))
    assert (code, out["verdict"]) == (2, "inconclusive")
    code, out = budget(capsys, tmp_path, run, budget_text("gpu,x,view,,median,0.500"))
    assert (code, out["verdict"]) == (1, "fail")


GOOD = "gpu,x,view,,median,2.000"


@pytest.mark.parametrize(("text", "line", "says"), [
    (f"{COLUMNS}\n{GOOD}\n", 1, "frameledger-budget"),
    (budget_text(GOOD, header='{"schema":2}'), 1, "schema"),
    ("# frameledger-budget {\"schema\":1}\ncategory,name,kind,statistic,limit_ms\n", 2, "column line"),
    (budget_text("gpu,x,view,,p95,2.000"), 3, "p95"),
    (budget_text("gpu,x,view,,median,2.0005"), 3, "2.0005"),
    (budget_text("frame,wall,view,,median,2.000"), 3, "frame"),
    (budget_text(GOOD, GOOD), 4, "line 3"),
    (budget_text("gpu,y,view,,median,2.000"), 3, "gpu/y is at depths 0 and 1"),
    (budget_text(GOOD, header='{"schema":1,"match":{"fps":60}}'), 1, "fps"),
    (budget_text("gpu,x,view,," + "median," + "9" * 5000), 3, "limit_ms"),
    (budget_text("gpu,x,view," + "9" * 5000 + ",median,2.000"), 3, "depth"),
    (budget_text(GOOD, header='{"schema":1,"match":{"inputs":"abc"}}'), 1, "inputs"),
    (budget_text(GOOD, header='{"schema":1,"match":{"inputs":[1,2]}}'), 1, "inputs"),
    (budget_text(GOOD, header='{"schema":1,"match":{"tier":["a"]}}'), 1, "tier"),
])
def test_bad_budget_files(capsys, tmp_path, text, line, says):
    """INV-59: a bad budget file exits 3 and names its line."""
    run = run_text([frame(x=1.0, y=1.0)] * 50 + [frame(x=1.0, y=(1.0, 1))] * 51)
    code, out = budget(capsys, tmp_path, run, text)
    assert (code, out["verdict"]) == (3, "error")
    sentence = out["summary"][-1]
    assert f"budgets.csv, line {line}:" in sentence and says in sentence, sentence

    code, out = budget(capsys, tmp_path, run, budget_text(GOOD, "", "gpu,x,view,,p99,2.000"))
    assert (code, len(out["result"]["budgets"])) == (0, 2)  # a blank line is skipped


def test_few_frames_warns(capsys, tmp_path):
    """INV-60: a p99 budget over fewer than 100 frames warns, and keeps its
    verdict and exit code."""
    lines = budget_text("gpu,x,view,,p99,2.000", "gpu,y,view,,p99,0.500")
    run = run_text([frame(x=1.0, y=1.0)] * 99 + [frame(y=1.0)] * 2)
    code, out = budget(capsys, tmp_path, run, lines)
    assert code == 1  # y is over; x holds
    assert [w["code"] for w in out["warnings"]] == ["budget_few_frames"]
    assert "gpu/x" in out["warnings"][0]["message"]

    run = run_text([frame(x=1.0, y=1.0)] * 100 + [frame(y=1.0)])
    code, out = budget(capsys, tmp_path, run, lines)
    assert (code, out["warnings"]) == (1, [])


def test_match(capsys, tmp_path):
    """INV-61: a budget file holds only for the settings it names."""
    budgets = budget_text(GOOD, header='{"schema":1,"match":{"tier":"high","render_scale":1}}')
    frames = [frame(x=1.0)] * 101
    code, out = budget(capsys, tmp_path, run_text(frames, tier="high"), budgets)
    assert code == 0  # render_scale 1.0 matches 1
    for header in ({"tier": "low"}, {}):
        code, out = budget(capsys, tmp_path, run_text(frames, **header), budgets)
        assert (code, out["verdict"]) == (3, "error")
        sentence = out["summary"][-1]
        shown = "absent" if not header else '"low"'
        assert 'tier is "high" in the budget file and ' + shown + " in the run" in sentence, sentence


def test_named_kind_replaces_star(capsys, tmp_path):
    """INV-62: a named kind replaces `*` for that kind."""
    run = run_text([frame("view:1", ssao=2.5)] * 101 + [frame("move:1-2", ssao=1.5)] * 101)
    code, out = budget(capsys, tmp_path, run, budget_text("gpu,ssao,*,,p99,2.000",
                                                          "gpu,ssao,view,,p99,3.000"))
    assert code == 0
    budgets = out["result"]["budgets"]
    assert [(e["segment_kind"], e["limit_ms"]) for e in budgets] == [("move", 2.0), ("view", 3.0)]

    code, out = budget(capsys, tmp_path, run, budget_text("gpu,ssao,*,,p99,2.000"))
    assert code == 1
    assert [e["segment_kind"] for e in out["result"]["budgets"] if e["over"]] == ["view"]

    # Depths compare once resolved: an empty depth is the pass's one depth.
    code, out = budget(capsys, tmp_path, run, budget_text("gpu,ssao,*,,p99,2.000",
                                                          "gpu,ssao,view,0,p99,3.000"))
    assert code == 0
    assert [(e["segment_kind"], e["limit_ms"]) for e in out["result"]["budgets"]] == [("move", 2.0), ("view", 3.0)]

    # A kind a named line takes is not the `*` line's: its second depth stops nothing.
    two = run_text([frame("view:1", x=1.0)] * 101 + [frame("view:2", x=(1.0, 1))] * 101
                   + [frame("move:1-2", x=1.0)] * 101)
    code, out = budget(capsys, tmp_path, two, budget_text("gpu,x,*,,median,2.000", "gpu,x,view,1,median,2.000"))
    assert code == 0
    assert [(e["segment_kind"], e["depth"]) for e in out["result"]["budgets"]] == [("move", 0), ("view", 1)]


def test_warmup(capsys, tmp_path):
    """INV-63: --warmup-s leaves out the frames floor leaves out."""
    frames = [frame(x=5.0)] * 20 + [frame(x=1.0)] * 181  # 200 frames with a wall
    budgets = budget_text("gpu,x,view,,p99,2.000")
    code, out = budget(capsys, tmp_path, run_text(frames), budgets)
    assert (code, out["result"]["warmup_s"]) == (1, 0)
    code, out = budget(capsys, tmp_path, run_text(frames), budgets, "--warmup-s", "0.5")
    assert (code, out["result"]["warmup_s"]) == (0, 0.5)
    assert out["result"]["budgets"][0]["frames"] == 151  # frames 49 to 199 end at 0.5 s or later

    holed = frames[:100] + [None] + frames[101:]
    code, out = budget(capsys, tmp_path, run_text(holed), budgets, "--warmup-s", "0.5")
    assert (code, out["verdict"]) == (2, "inconclusive")
    assert any("frame 100 is missing" in s for s in out["summary"])
    code, out = budget(capsys, tmp_path, run_text(holed), budgets)
    assert code == 1
    # Past the hole the ends come too early, so a frame placed after the
    # warm-up truly ended after it: a breach there is real, as floor's.
    slow_later = holed[:150] + [frame(x=5.0)] * 51
    code, out = budget(capsys, tmp_path, run_text(slow_later), budgets, "--warmup-s", "0.5")
    assert (code, out["verdict"]) == (1, "fail")

    code, out = budget(capsys, tmp_path, run_text(frames), budgets, "--warmup-s", "3")
    assert (code, [u["name"] for u in out["result"]["unmatched"]]) == (2, ["x"])
    # One sentence for the run, not a broken budget file per line.
    assert any("No frame ends after the 3 s warm-up" in s for s in out["summary"])
    assert not any("fix the budget file" in s for s in out["summary"])


def test_text_and_errors(capsys, tmp_path):
    """The text form gives the table; a missing budget file and a negative
    --warmup-s are exit 3."""
    run_path, budget_path = tmp_path / "run.csv", tmp_path / "budgets.csv"
    run_path.write_text(run_text([frame(x=1.0)] * 101), encoding="utf-8")
    budget_path.write_text(budget_text(GOOD), encoding="utf-8")
    assert cli.main(["budget", str(run_path), "--budgets", str(budget_path)]) == 0
    text = capsys.readouterr().out
    assert "Every budget holds" in text and "view: gpu/x median" in text
    assert all(len(line) <= 100 for line in text.splitlines())

    assert cli.main(["budget", str(run_path), "--budgets", str(tmp_path / "none.csv")]) == 3
    assert cli.main(["budget", str(run_path), "--budgets", str(budget_path), "--warmup-s", "-1"]) == 3
    budget_path.write_text(budget_text(), encoding="utf-8")
    assert cli.main(["budget", str(run_path), "--budgets", str(budget_path)]) == 3
