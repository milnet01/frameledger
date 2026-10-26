"""Trust warnings: whether one run's numbers should be trusted (S5).

Invariants from docs/specs/FLED-0001-run-file-format.md § 5: INV-23 to
INV-27, the rules of § 4.9. Runs are passing-run.csv with its header
changed, or built from frame walls by tests/floor_runs.py.
"""

import json
from pathlib import Path

import cli
from floor_runs import WARMUP, run_text

FIXTURES = Path(__file__).parent / "fixtures"
PASSING = (FIXTURES / "passing-run.csv").read_text(encoding="utf-8")
TRUST = {"debug_build", "software_renderer", "cpu_load", "gpu_load", "settling_short",
         "too_few_frames", "cut_in_stretch"}


def with_header(text, **changes):
    """text with its header's fields changed; a value of None removes one."""
    first, rest = text.split("\n", 1)
    header = json.loads(first.removeprefix("# frameledger "))
    for name, value in changes.items():
        if value is None:
            header.pop(name, None)
        else:
            header[name] = value
    return f"# frameledger {json.dumps(header)}\n{rest}"


def with_rows(text, *rows):
    """text with rows added before its close line."""
    body, close = text.rstrip("\n").rsplit("\n", 1)
    return "\n".join([body, *rows, close]) + "\n"


def run(capsys, tmp_path, command, text):
    path = tmp_path / "run.csv"
    path.write_text(text, encoding="utf-8")
    args = [command, "--json", str(path)] + (["--fps", "60"] if command == "floor" else [])
    code = cli.main(args)
    out = json.loads(capsys.readouterr().out)
    assert out["exit_code"] == code
    return out


def trust(out):
    return [w for w in out["warnings"] if w["code"] in TRUST]


def test_header_warnings(capsys, tmp_path):
    cases = [
        ({"build_type": "Debug"}, "debug_build", "Debug"),
        ({"renderer": "LLVMpipe (LLVM 19)"}, "software_renderer", "LLVMpipe (LLVM 19)"),
        ({"device": "GDI Generic"}, "software_renderer", "GDI Generic"),
        ({"load": {"start": 0.51, "end": 0.9}}, "cpu_load", "0.51"),
        ({"gpu_busy_pct": {"start": 21, "end": 99}}, "gpu_load", "21"),
    ]
    for command in ("report", "floor"):
        plain = run(capsys, tmp_path, command, PASSING)
        assert trust(plain) == []
        assert plain["verdict"] in ("none", "pass")
        for changes, code, value in cases:
            out = run(capsys, tmp_path, command, with_header(PASSING, **changes))
            warned = trust(out)
            assert [w["code"] for w in warned] == [code], (command, changes)
            assert value in warned[0]["message"]
            assert f"Warning: {warned[0]['message']}." in out["summary"]
            assert (out["verdict"], out["exit_code"]) == (plain["verdict"], plain["exit_code"])
        # Both fields naming a software renderer is one warning, naming renderer.
        both = trust(run(capsys, tmp_path, command, with_header(PASSING, renderer="llvmpipe",
                                                                device="llvmpipe")))
        assert [w["code"] for w in both] == ["software_renderer"]
        assert "renderer" in both[0]["message"]
        for changes in ({"load": {"start": 0.5, "end": 0.9}}, {"gpu_busy_pct": {"start": 20, "end": 99}}):
            assert trust(run(capsys, tmp_path, command, with_header(PASSING, **changes))) == []


def test_too_few_frames(capsys, tmp_path):
    def warned(command, walls):
        return [w["code"] for w in trust(run(capsys, tmp_path, command, run_text(walls)))]

    assert warned("report", [16.0] * 99) == ["too_few_frames"]
    assert warned("report", [16.0] * 100) == []
    # The warm-up's frames end inside it, so floor does not count them.
    assert warned("floor", WARMUP + [16.0] * 99) == ["too_few_frames"]
    assert warned("floor", WARMUP + [16.0] * 100) == []
    assert warned("report", WARMUP + [16.0] * 99) == []


def test_settling(capsys, tmp_path):
    for command in ("report", "floor"):
        out = run(capsys, tmp_path, command, with_header(PASSING, settled_frames=3, settling_frames=4))
        warned = trust(out)
        assert [w["code"] for w in warned] == ["settling_short"]
        assert "3" in warned[0]["message"] and "4" in warned[0]["message"]
        for changes in ({"settled_frames": 4, "settling_frames": 4}, {"settling_frames": 4},
                        {"settled_frames": 3}):
            assert trust(run(capsys, tmp_path, command, with_header(PASSING, **changes))) == []


def test_cut_in_stretch(capsys, tmp_path):
    walls = WARMUP + [16.0] * 200
    # A cut on frame 0, and one where the segment changes (frame 200), start a stretch.
    planned = with_rows(run_text(walls, cuts=(200,)), "f1,view:1,0,event,cut,0,1.000")
    # Frame 10 ends inside the warm-up; frame 150 after it. Both are mid-segment.
    unplanned = with_rows(planned, "f1,view:1,10,event,cut,0,1.000", "f1,view:1,150,event,cut,0,1.000")

    for command in ("report", "floor"):
        assert trust(run(capsys, tmp_path, command, planned)) == []
        assert trust(run(capsys, tmp_path, command, (FIXTURES / "cut-mid-second.csv").read_text())) == []
    report = trust(run(capsys, tmp_path, "report", unplanned))
    assert [w["code"] for w in report] == ["cut_in_stretch"] * 2
    assert "frame 10 " in report[0]["message"] and "frame 150 " in report[1]["message"]
    floor = trust(run(capsys, tmp_path, "floor", unplanned))
    assert [w["code"] for w in floor] == ["cut_in_stretch"]
    assert "frame 150 " in floor[0]["message"]

    # A mid-segment cut after a missing frame is judged against the frame
    # before the gap (DOOM Ants' review): dropped rows can take a whole frame.
    gap = "\n".join(line for line in run_text([16.0] * 200).split("\n")
                    if not line.startswith("f1,view:1,4,"))
    after_gap = trust(run(capsys, tmp_path, "report", with_rows(gap, "f1,view:1,5,event,cut,0,1.000")))
    assert [w["code"] for w in after_gap] == ["cut_in_stretch"]
    assert "frame 5 " in after_gap[0]["message"]


def test_absent_fields_and_check(capsys, tmp_path):
    header = json.loads(PASSING.split("\n", 1)[0].removeprefix("# frameledger "))
    assert not {"settling_frames", "settled_frames", "load", "gpu_busy_pct"} & header.keys()
    for command in ("report", "floor"):
        assert trust(run(capsys, tmp_path, command, PASSING)) == []
    debug = run(capsys, tmp_path, "check", with_header(PASSING, build_type="Debug",
                                                       renderer="llvmpipe", settled_frames=0,
                                                       settling_frames=4))
    assert debug["exit_code"] == 0
    assert trust(debug) == []
