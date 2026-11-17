"""Generated frames (FLED-0075): an import marks them, and every command
judges the application's frames unless --all-frames is given.

Invariants INV-119 to INV-121 from docs/specs/FLED-0001-run-file-format.md
§ 5, the rules of § 4.4's event/generated, § 4.18's FrameType and
§ 4.20. Each run is built here as text.
"""

import json

import cli
import generated
import ledger
from floor_runs import HEADER
from test_presentmon import COLUMNS, capture_text, imported, row, values

APPLICATION_FRAMES = 600  # 10 s at 60 a second, so floor has windows after its 2 s warm-up


def run_text(run_id: str, marked: bool = True, missing_wall: int | None = None, mark: str = "1.000") -> str:
    """The application renders every 16.666 ms and a generated frame comes
    half-way, so every wall is 8.333 ms. Even frames are the application's,
    `frame/cpu_span` 5.000 and a pass `cpu/sim` 4.000; odd frames are
    generated, `frame/cpu_span` 0.000, carrying `event/generated` when
    `marked`. The last frame, a generated one, has no wall, nor has frame
    `missing_wall`."""
    header = HEADER.replace('"run_id":"f1"', f'"run_id":"{run_id}"')
    lines = [header, ledger.COLUMNS]
    count = 2 * APPLICATION_FRAMES
    for frame in range(count):
        generated = frame % 2 == 1
        lines.append(f"{run_id},,{frame},frame,cpu_span,0,{'0.000' if generated else '5.000'}")
        if frame != count - 1 and frame != missing_wall:
            lines.append(f"{run_id},,{frame},frame,wall,0,8.333")
        if generated and marked:
            lines.append(f"{run_id},,{frame},event,generated,0,{mark}")
        if not generated:
            lines.append(f"{run_id},,{frame},cpu,sim,0,4.000")
    lines.append(f'# frameledger-close {{"rows_dropped":0,"frames":{count}}}')
    return "\n".join(lines) + "\n"


def write(tmp_path, name: str, **options) -> str:
    path = tmp_path / name
    path.write_text(run_text(name.removesuffix(".csv"), **options), encoding="utf-8")
    return str(path)


def command(capsys, *args: str) -> tuple[int, dict]:
    code = cli.main([*args, "--json"])
    return code, json.loads(capsys.readouterr().out)


def sets(tmp_path) -> tuple[list[str], list[str]]:
    """Three runs with event/generated and three without, rows otherwise the same."""
    marked = [write(tmp_path, f"marked{i}.csv") for i in range(1, 4)]
    plain = [write(tmp_path, f"plain{i}.csv", marked=False) for i in range(1, 4)]
    return marked, plain


def left_out(name: str = "") -> str:
    opening = f"{name}: " if name else ""
    return (f"{opening}600 of 1200 frames were generated, not rendered by the application, and are left out; "
            "--all-frames counts them.")


def counted(name: str = "") -> str:
    opening = f"{name}: " if name else ""
    return (f"{opening}600 of 1200 frames were generated, not rendered by the application, and are counted, "
            "as --all-frames asks.")


def budgets(tmp_path) -> str:
    path = tmp_path / "budgets.csv"
    path.write_text('# frameledger-budget {"schema":1}\ncategory,name,kind,depth,statistic,limit_ms\n'
                    "cpu,cpu_remainder,*,,median,0.500\n", encoding="utf-8")
    return str(path)


def centres(out: dict, name: str) -> tuple[float, float]:
    """The old and new centres of frame/`name`'s median."""
    entry = next(m for m in out["result"]["measures"]
                 if (m["category"], m["name"], m["statistic"]) == ("frame", name, "median"))
    return entry["old_centre"], entry["new_centre"]


# INV-119

def test_import_marks_generated_frames(capsys, tmp_path):
    kinds = ["Application", "AMD AFMF"] * 4 + ["Something New"]
    presents = [row(FrameType=kind) for kind in kinds]
    code, out, _ = imported(capsys, tmp_path, capture_text(presents, [*COLUMNS, "FrameType"]))
    assert code == 0
    run = ledger.read(tmp_path / "run.csv")
    marked = values(run, "generated", "event")
    assert marked == {frame: 1000 for frame, kind in enumerate(kinds) if kind != "Application"}
    assert set(run.frames) == set(range(len(kinds)))  # a generated row is kept, not dropped
    assert out["result"]["import"]["generated"] == {"AMD AFMF": 4, "Something New": 1}
    assert "5 were generated (AMD AFMF 4, Something New 1)." in out["summary"]

    code, out, _ = imported(capsys, tmp_path, capture_text(presents))  # no FrameType column
    assert code == 0
    assert values(ledger.read(tmp_path / "run.csv"), "generated", "event") == {}
    assert out["result"]["import"]["generated"] is None
    assert "The capture has no FrameType column, so every frame is read as the application's." in out["summary"]

    code, out, _ = imported(capsys, tmp_path, capture_text([row(FrameType="Application")] * 3, [*COLUMNS, "FrameType"]))
    assert code == 0  # every frame the application's: an empty count, not null
    assert out["result"]["import"]["generated"] == {}
    assert not any("generated (" in sentence for sentence in out["summary"])


# INV-120

def test_application_frames_are_judged(capsys, tmp_path):
    marked, plain = sets(tmp_path)

    code, out = command(capsys, "floor", marked[0], "--fps", "100")
    assert code == 1  # the application renders 60 a second
    assert not all(window["pass"] for window in out["result"]["windows"])
    assert out["summary"][0] == left_out()
    assert (out["result"]["generated_frames"], out["result"]["all_frames"]) == (600, False)

    code, out = command(capsys, "survey", marked[0], "--budget-ms", "10")
    assert code == 1
    assert out["summary"][0] == left_out(marked[0])
    assert (out["result"]["runs"][0]["generated_frames"], out["result"]["all_frames"]) == (600, False)

    code, out = command(capsys, "report", marked[0])
    wall = next(f for f in out["result"]["frame_times"] if f["name"] == "wall")
    assert (wall["median_ms"], wall["frames"]) == (16.666, APPLICATION_FRAMES - 1)  # the last has no wall
    assert out["summary"][0] == left_out()

    code, out = command(capsys, "budget", marked[0], "--budgets", budgets(tmp_path))
    assert code == 1  # a remainder of 1.000 on every application frame
    assert out["summary"][0] == left_out()

    code, out = command(capsys, "compare", "--old", *marked, "--new", *plain, "--measure", "frame/cpu_span")
    old, new = centres(out, "cpu_span")
    assert old == 5.0 and new < old
    assert left_out("old-1") in out["summary"] and not any("new-1:" in s for s in out["summary"])
    assert [r["generated_frames"] for r in out["result"]["runs"]] == [600, 600, 600, 0, 0, 0]
    assert out["result"]["all_frames"] is False

    code, out = command(capsys, "bisect", "--tested", *marked, "--measure", "frame/cpu_span", "--unsegmented",
                        "--bad-above", "2.5")
    assert code == 1  # 5.000, above 2.5
    assert left_out("tested-1") in out["summary"]

    # Without the mark, every frame is the application's: the --all-frames answers.
    for path in plain:
        assert command(capsys, "floor", path, "--fps", "100")[0] == 0
        assert command(capsys, "survey", path, "--budget-ms", "10")[0] == 0


def test_all_frames_counts_every_frame(capsys, tmp_path):
    marked, plain = sets(tmp_path)
    for path in (marked[0], plain[0]):
        assert command(capsys, "floor", path, "--fps", "100", "--all-frames")[0] == 0
        assert command(capsys, "survey", path, "--budget-ms", "10", "--all-frames")[0] == 0
        assert command(capsys, "budget", path, "--budgets", budgets(tmp_path), "--all-frames")[0] == 0

    code, out = command(capsys, "floor", marked[0], "--fps", "100", "--all-frames")
    assert out["summary"][0] == counted()
    assert (out["result"]["generated_frames"], out["result"]["all_frames"]) == (600, True)
    code, out = command(capsys, "floor", plain[0], "--fps", "100", "--all-frames")
    assert not any("generated" in s for s in out["summary"])  # no mark, nothing said
    assert (out["result"]["generated_frames"], out["result"]["all_frames"]) == (0, True)

    code, out = command(capsys, "report", marked[0], "--all-frames")
    wall = next(f for f in out["result"]["frame_times"] if f["name"] == "wall")
    assert (wall["median_ms"], wall["frames"]) == (8.333, 2 * APPLICATION_FRAMES - 1)

    code, out = command(capsys, "compare", "--old", *marked, "--new", *plain, "--measure", "frame/cpu_span",
                        "--all-frames")
    old, new = centres(out, "cpu_span")
    assert old == new
    assert counted("old-1") in out["summary"]
    assert out["result"]["all_frames"] is True

    code, out = command(capsys, "bisect", "--tested", *marked, "--measure", "frame/cpu_span", "--unsegmented",
                        "--bad-above", "2.5", "--all-frames")
    assert code == 0  # the generated frames' 0.000 brings the median down
    assert counted("tested-1") in out["summary"]


# INV-121

def test_a_missing_generated_wall(capsys, tmp_path):
    whole = write(tmp_path, "whole.csv")
    holed = write(tmp_path, "holed.csv", missing_wall=301)  # a generated frame mid-run
    assert command(capsys, "floor", whole, "--fps", "50")[0] == 0
    code, out = command(capsys, "floor", holed, "--fps", "50")
    assert code == 2  # frame 300 has no wall, so the timeline stops there
    assert "Frame 300 has no frame/wall row, so the timeline stops there." in out["summary"]


def test_the_mark_is_one(capsys, tmp_path):
    assert command(capsys, "check", write(tmp_path, "one.csv"))[0] == 0
    code, out = command(capsys, "check", write(tmp_path, "two.csv", mark="2.000"))
    assert code == 1
    breach = out["result"]["files"][0]["breaches"][0]
    assert "event/generated" in breach["message"] and breach["line"] > 2


def test_no_application_frame(capsys, tmp_path):
    lines = [HEADER, ledger.COLUMNS, *(f"f1,,{frame},frame,cpu_span,0,1.000\nf1,,{frame},frame,wall,0,8.000\n"
                                       f"f1,,{frame},event,generated,0,1.000" for frame in range(300))]
    path = tmp_path / "all.csv"
    path.write_text("\n".join([*lines, '# frameledger-close {"rows_dropped":0,"frames":300}']) + "\n")
    code, out = command(capsys, "floor", str(path), "--fps", "60")
    assert code == 3
    assert "every one of its 300 frames was generated" in out["summary"][0]
    assert command(capsys, "floor", str(path), "--fps", "60", "--warmup-s", "0", "--all-frames")[0] == 0
    code, out = command(capsys, "compare", "--by-scene", "--old", *[str(path)] * 3, "--new", *[str(path)] * 3)
    assert {u["reason"] for u in out["result"]["unread"]} == {
        "every one of its 300 frames was generated, so there is no application frame to judge; "
        "--all-frames counts them"}


def test_a_hole_among_generated_frames(capsys, tmp_path):
    """Frame 2 is missing between two generated frames, so frame 0's wall,
    which runs to the next application frame, is not known."""
    lines = [HEADER, ledger.COLUMNS]
    for frame, generated_frame in ((0, False), (1, True), (3, True), (4, False), (5, False)):
        lines.append(f"f1,,{frame},frame,cpu_span,0,1.000")
        lines.append(f"f1,,{frame},frame,wall,0,5.000")
        if generated_frame:
            lines.append(f"f1,,{frame},event,generated,0,1.000")
    path = tmp_path / "holed.csv"
    path.write_text("\n".join([*lines, '# frameledger-close {"rows_dropped":0,"frames":6}']) + "\n")
    run = generated.read(str(path), all_frames=False)
    assert ("frame", "wall") not in run.frames[0]  # never 10.000 or 15.000
    assert run.frames[4][("frame", "wall")].thousandths == 5000


def leading_run(tmp_path, name: str, missing_wall: int | None = None) -> str:
    """Ten generated frames of 100 ms, a second before the first
    application frame, which takes 50 ms; then 16 ms frames."""
    lines = [HEADER, ledger.COLUMNS]
    walls = [100.0] * 10 + [50.0] + [16.0] * 200
    for frame, wall in enumerate(walls):
        lines.append(f"f1,,{frame},frame,cpu_span,0,1.000")
        if frame != missing_wall and frame != len(walls) - 1:
            lines.append(f"f1,,{frame},frame,wall,0,{wall:.3f}")
        if frame < 10:
            lines.append(f"f1,,{frame},event,generated,0,1.000")
    path = tmp_path / name
    path.write_text("\n".join([*lines, f'# frameledger-close {{"rows_dropped":0,"frames":{len(walls)}}}']) + "\n")
    return str(path)


def test_generated_frames_before_the_first(capsys, tmp_path):
    # Their second moves the timeline, so the 50 ms frame ends after a 1 s warm-up and is judged.
    path = leading_run(tmp_path, "leading.csv")
    code, out = command(capsys, "floor", path, "--fps", "60", "--warmup-s", "1", "--no-windows")
    assert code == 1 and out["result"]["frames_over_budget"] == 1
    assert out["summary"][0].startswith("10 of 211 frames were generated")
    # A wall missing among them leaves the start unknown: the 50 ms frame cannot be placed after the warm-up.
    code, out = command(capsys, "floor", leading_run(tmp_path, "unknown.csv", missing_wall=3), "--fps", "60",
                        "--warmup-s", "1", "--no-windows")
    assert code == 2 and "Frame 3 has no frame/wall row, so the timeline stops there." in out["summary"]


def test_generated_rows_are_not_read(capsys, tmp_path):
    # Pacing pairs application frames across the generated one between them.
    code, out = command(capsys, "report", write(tmp_path, "marked.csv"))
    assert [p["pairs"] for p in out["result"]["pacing"]] == [APPLICATION_FRAMES - 2]
    # A generated frame's segment and events are not read.
    text = run_text("seg").replace("seg,,1,frame,cpu_span", "seg,load:1,1,frame,cpu_span")
    path = tmp_path / "seg.csv"
    path.write_text(text.replace("seg,,1,event,generated",
                                 "seg,load:1,1,event,cut,0,1.000\nseg,load:1,1,event,generated"))
    code, out = command(capsys, "report", str(path))
    assert {f["segment_kind"] for f in out["result"]["frame_times"]} == {None}


def test_every_command_refuses_no_application_frame(capsys, tmp_path):
    lines = [HEADER, ledger.COLUMNS, *(f"f1,,{frame},frame,cpu_span,0,1.000\nf1,,{frame},frame,wall,0,8.000\n"
                                       f"f1,,{frame},event,generated,0,1.000" for frame in range(300))]
    path = tmp_path / "all.csv"
    path.write_text("\n".join([*lines, '# frameledger-close {"rows_dropped":0,"frames":300}']) + "\n")
    good = [write(tmp_path, f"good{i}.csv") for i in range(1, 4)]
    budget_file = budgets(tmp_path)
    for args in (["report", str(path)], ["budget", str(path), "--budgets", budget_file],
                 ["compare", "--old", str(path), *good[1:], "--new", *good]):
        code, out = command(capsys, *args)
        assert code == 3 and "--all-frames counts them" in out["summary"][-1], args
    code, out = command(capsys, "survey", str(path), "--fps", "60")
    assert out["result"]["runs"][0]["verdict"] == "unjudged"
    bisect = ["bisect", "--measure", "frame/cpu_span", "--unsegmented"]
    assert command(capsys, *bisect, "--tested", str(path), "--bad-above", "1")[0] == 125
    assert command(capsys, *bisect, "--tested", good[0], "--good", str(path), *good[1:], "--bad", *good)[0] == 128


def test_all_frames_by_scene_and_by_variant(capsys, tmp_path):
    marked, plain = sets(tmp_path)
    for args in (["--by-scene", "--old", *marked, "--new", *plain], ["--base", *marked, "--variant", "v", *plain]):
        code, out = command(capsys, "compare", *args, "--measure", "frame/cpu_span")
        assert any(s.endswith(left_out("base-1" if "--base" in args else "old-1")) for s in out["summary"]), args
        code, out = command(capsys, "compare", *args, "--measure", "frame/cpu_span", "--all-frames")
        assert any(s.endswith(counted("base-1" if "--base" in args else "old-1")) for s in out["summary"]), args
        assert out["result"]["all_frames"] is True


def test_an_empty_run(capsys, tmp_path):
    """A header and a close line with no frame between: judged as nothing, never a crash."""
    path = tmp_path / "empty.csv"
    path.write_text("\n".join([HEADER, ledger.COLUMNS, '# frameledger-close {"rows_dropped":0,"frames":0}']) + "\n")
    for args in (["floor", str(path), "--fps", "60"], ["survey", str(path), "--fps", "60"],
                 ["budget", str(path), "--budgets", budgets(tmp_path), "--warmup-s", "1"], ["report", str(path)]):
        code = cli.main([*args, "--json"])
        assert "Traceback" not in capsys.readouterr().err and code in (0, 2, 3), args
