"""`import presentmon` (S25): a PresentMon capture becomes a run file.

Invariants INV-111 to INV-113 and INV-115 from
docs/specs/FLED-0001-run-file-format.md § 5, the rules of § 4.18. Each
capture is built here as CSV text.
"""

import json
import os
import sys
from pathlib import Path

import pytest

import cli
import ledger
import presentmon

COLUMNS = ["Application", "ProcessID", "SwapChainAddress", "PresentRuntime", "SyncInterval", "MsGPUTime",
           "MsBetweenPresents", "Extra", "MsCPUBusy", "MsGPUBusy", "DisplayedTime", "CPUStartDateTime"]
EVERY_FACT = ["--commit", "abc123", "--clean", "--build-type", "release", "--device", "RX 9070 XT",
              "--renderer", "radeonsi", "--driver", "Mesa 26.2", "--resolution", "1920x1080",
              "--render-scale", "1.0", "--pipelined", "--display", "onscreen", "--scene", "atrium"]


def row(**values) -> dict:
    """One present, every column filled; `values` replaces any."""
    return {"Application": "game.exe", "ProcessID": "4120", "SwapChainAddress": "0x1F2E3D",
            "PresentRuntime": "DXGI", "SyncInterval": "0", "MsGPUTime": "9.5", "MsBetweenPresents": "16.6",
            "Extra": "x", "MsCPUBusy": "4.0", "MsGPUBusy": "6.0", "DisplayedTime": "1.2",
            "CPUStartDateTime": "2026-11-15T10:00:00.25Z", **values}


def capture_text(rows: list[dict], columns: list[str] = COLUMNS) -> str:
    return "\n".join([",".join(columns), *(",".join(r[c] for c in columns) for r in rows)]) + "\n"


def frames(count: int, **values) -> list[dict]:
    """`count` presents whose MsBetweenPresents are 16.0, 16.1, …, so
    each frame's wall says which row it came from."""
    return [row(MsBetweenPresents=f"{16 + i / 10:.1f}", **values) for i in range(count)]


def write(tmp_path: Path, text: str, name: str = "capture.csv") -> str:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


def imported(capsys, tmp_path: Path, text: str, *flags: str) -> tuple[int, dict, str]:
    """Import `text`; (exit code, the JSON result or None, standard error)."""
    run_path = tmp_path / "run.csv"
    if run_path.exists():
        run_path.unlink()
    code = cli.main(["import", "presentmon", write(tmp_path, text), "-o", str(run_path), *flags, "--json"])
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err
    return code, json.loads(captured.out) if captured.out else None, captured.err


def values(run: ledger.Run, name: str, category: str = "frame") -> dict[int, int]:
    return {frame: rows[(category, name)].thousandths for frame, rows in run.frames.items()
            if (category, name) in rows}


def command(capsys, *args: str) -> tuple[int, dict]:
    code = cli.main([*args, "--json"])
    return code, json.loads(capsys.readouterr().out)


def warned(out: dict, code: str) -> list[str]:
    return [w["message"] for w in out["warnings"] if w["code"] == code]


# INV-111

def test_capture_becomes_a_run(capsys, tmp_path):
    presents = frames(6)
    presents[2]["DisplayedTime"] = "NA"
    presents[3]["MsCPUBusy"] = "1.0005"
    presents[4]["MsCPUBusy"] = "-1.0005"
    code, out, _ = imported(capsys, tmp_path, capture_text(presents))
    assert code == 0, out
    run_path = str(tmp_path / "run.csv")
    run = ledger.read(run_path)
    assert run.breaches == []
    assert command(capsys, "check", run_path)[0] == 0
    assert sorted(run.frames) == list(range(6))
    # Each wall is the next row's MsBetweenPresents; the last frame has none.
    assert values(run, "wall") == {i: 16_100 + 100 * i for i in range(5)}
    assert values(run, "gpu_span") == dict.fromkeys(range(6), 6_000)  # MsGPUBusy, never MsGPUTime's 9.5
    assert values(run, "not_displayed", "event") == {2: 1_000}
    assert values(run, "cpu_span")[3] == 1_001 and values(run, "cpu_span")[4] == -1_001
    assert out["result"]["import"] == {"path": run_path, "process": "game.exe", "pid": "4120",
                                       "swapchain": "0x1F2E3D", "frames": 6, "not_displayed": 1,
                                       "generated": None, "unknown": run.header["unknown"]}
    assert run.header["unknown"]  # no fact flags, so the header lists what it lacks


def test_a_bom_and_crlf_are_read(capsys, tmp_path):
    """§ 4.18: a byte-order mark is skipped, CRLF ends a line, and a quoted
    field reads as its text."""
    capture = tmp_path / "capture.csv"
    presents = frames(3)
    presents[0]["Extra"] = '"a, quoted ""field"""'
    capture.write_bytes(b"\xef\xbb\xbf" + capture_text(presents).replace("\n", "\r\n").encode())
    run_path = tmp_path / "run.csv"
    assert cli.main(["import", "presentmon", str(capture), "-o", str(run_path)]) == 0
    capsys.readouterr()
    assert values(ledger.read(run_path), "wall") == {0: 16_100, 1: 16_200}


@pytest.mark.skipif(sys.platform == "win32", reason="Windows files have no POSIX mode")
def test_the_run_file_follows_the_umask(capsys, tmp_path):
    """The run file gets the mode open() would give, not mkstemp's 0600."""
    mask = os.umask(0o022)
    try:
        code, _, _ = imported(capsys, tmp_path, capture_text(frames(2)))
    finally:
        os.umask(mask)
    assert code == 0
    assert (tmp_path / "run.csv").stat().st_mode & 0o777 == 0o644


def test_every_stand_in_is_knowable():
    """Each field that can hold a stand-in is one `unknown` may list."""
    assert set(presentmon.STAND_INS) == set(ledger.UNKNOWABLE)


def test_commands_read_an_import(capsys, tmp_path):
    """INV-111: report, floor and survey read an imported run and exit 0.
    300 frames of 16 ms outlast floor's two-second warm-up."""
    code, _, _ = imported(capsys, tmp_path, capture_text([row(MsBetweenPresents="16.0")] * 300))
    assert code == 0
    run_path = str(tmp_path / "run.csv")
    for args in (["report"], ["floor", "--fps", "60"], ["survey", "--fps", "60"]):
        assert command(capsys, args[0], run_path, *args[1:])[0] == 0, args


def test_zero_between_presents(capsys, tmp_path):
    """INV-111: a MsBetweenPresents of 0 gives the frame before it no wall,
    and check warns wall_missing on it."""
    presents = frames(4)
    presents[2]["MsBetweenPresents"] = "0"
    code, _, _ = imported(capsys, tmp_path, capture_text(presents))
    assert code == 0
    run = ledger.read(tmp_path / "run.csv")
    assert 1 not in values(run, "wall") and 0 in values(run, "wall")
    _, out = command(capsys, "check", str(tmp_path / "run.csv"))
    assert any("frame 1 has no frame/wall" in message for message in warned(out, "wall_missing"))


def test_start_order(capsys, tmp_path):
    """INV-111: a start going back warns, naming both lines, and the rows
    stay in file order; dates are compared as times, not as text."""
    columns = [c for c in COLUMNS if c != "CPUStartDateTime"] + ["CPUStartTime"]
    presents = frames(3)
    for present, start in zip(presents, ["10.5", "10.4", "10.6"], strict=True):
        present["CPUStartTime"] = start
    code, out, _ = imported(capsys, tmp_path, capture_text(presents, columns), "--started", "2026-11-15T10:00:00Z")
    assert code == 0
    said = warned(out, "start_out_of_order")
    assert len(said) == 1 and "line 3's CPUStartTime (10.4) is before line 2's (10.5); the rows" in said[0]

    for name in ("CPUStartQPC", "CPUStartQPCTime"):  # --qpc_time and --qpc_time_ms
        qpc = [c for c in COLUMNS if c != "CPUStartDateTime"] + [name]
        for present, start in zip(presents, ["105", "104", "106"], strict=True):
            present[name] = start
        _, out, _ = imported(capsys, tmp_path, capture_text(presents, qpc), "--started", "2026-11-15T10:00:00Z")
        assert f"line 3's {name} (104) is before line 2's (105)" in warned(out, "start_out_of_order")[0], name
    assert values(ledger.read(tmp_path / "run.csv"), "wall") == {0: 16_100, 1: 16_200}

    presents = frames(5)  # three starts go back: one warning, counting the other two
    for present, start in zip(presents, ["10.5", "10.4", "10.3", "10.6", "10.1"], strict=True):
        present["CPUStartTime"] = start
    code, out, _ = imported(capsys, tmp_path, capture_text(presents, columns), "--started", "2026-11-15T10:00:00Z")
    said = warned(out, "start_out_of_order")
    assert len(said) == 1 and "(10.5), and 2 more starts go back;" in said[0]

    presents = frames(2)
    presents[0]["CPUStartDateTime"] = "2026-11-15T11:59:00+02:00"  # 09:59 UTC: back as text, forward as times
    presents[1]["CPUStartDateTime"] = "2026-11-15T10:00:00Z"
    code, out, _ = imported(capsys, tmp_path, capture_text(presents))
    assert code == 0 and not warned(out, "start_out_of_order")
    assert ledger.read(tmp_path / "run.csv").header["started_utc"] == "2026-11-15T09:59:00Z"


# INV-112

@pytest.mark.parametrize(("text", "flags", "says"), [
    ("Application,ProcessID,msBetweenPresents,TimeInSeconds\ngame.exe,1,16.6,0.1\n", [],
     "PresentMon 1's columns (msBetweenPresents, TimeInSeconds) and no MsCPUBusy column"),
    ("Application,ProcessID,Frame\ngame.exe,1,2\n", [],
     "no SwapChainAddress, MsBetweenPresents and MsCPUBusy columns"),
    (capture_text(frames(3) + frames(5, Application="obs64.exe", ProcessID="990")), [],
     "the capture holds 2 processes: obs64.exe (pid 990, 5 frames), game.exe (pid 4120, 3 frames); "
     "pick one with --process or --pid"),
    (capture_text(frames(3)), ["--process", "other.exe"], "no row matches --process other.exe"),
    (capture_text(frames(3) + frames(2, SwapChainAddress="0x2")), ["--process", "game.exe"],
     "2 swap chains: 0x1F2E3D (3 frames), 0x2 (2 frames); pick one with --swapchain"),
    (capture_text([row(), row(MsCPUBusy="NA"), row()]), [], "line 3: MsCPUBusy is NA, not a number"),
    (capture_text([row(), row(MsBetweenPresents="1000000000"), row()]), [], "line 3: MsBetweenPresents is 1000000000"),
    (capture_text([row(), row(MsCPUBusy="1e30"), row()]), [], "line 3: MsCPUBusy is 1e30, and a run holds"),
    (capture_text([row(), row(MsCPUBusy="1_000"), row()]), [], "line 3: MsCPUBusy is 1_000, not a number"),
    (capture_text(frames(2, CPUStartDateTime="2026-11-15T10:00:00")), [], "which names no time zone"),
    (capture_text(frames(2), COLUMNS[:-1]), [], "the capture has no CPUStartDateTime, so"),
    (capture_text(frames(2)), ["--resolution", "0x1080"], "the resolution given must be"),
    (capture_text(frames(2)), ["--pid", "1"], "no row matches --pid 1"),
    (capture_text(frames(2)), ["--swapchain", "0x9"], "no row matches --swapchain 0x9"),
    ("", [], "the capture is empty"),
    (capture_text([]), [], "the capture has no rows"),
    (capture_text(frames(2)) + "game.exe,4120\n", [], "line 4: the row has 2 fields and the column line 12"),
    # A short id: the row itself would exceed Windows' limit on an environment
    # variable, and PYTEST_CURRENT_TEST holds the test's id.
    pytest.param(capture_text([row(), row(Extra="x" * 200_000)]), [], "line 3: the row is not CSV the import can read",
                 id="oversized-field"),
])
def test_refusals(capsys, tmp_path, text, flags, says):
    code, out, err = imported(capsys, tmp_path, text, *flags)
    assert code == 3 and out is None
    assert says in err
    assert not (tmp_path / "run.csv").exists()
    assert [p.name for p in tmp_path.iterdir()] == ["capture.csv"]  # no temporary file left


def test_an_existing_run_is_kept(capsys, tmp_path):
    run_path = tmp_path / "run.csv"
    run_path.write_bytes(b"kept")
    code = cli.main(["import", "presentmon", write(tmp_path, capture_text(frames(2))), "-o", str(run_path)])
    assert code == 3 and "never overwrites" in capsys.readouterr().err
    assert run_path.read_bytes() == b"kept"


def test_a_run_made_during_the_import_is_kept(capsys, tmp_path, monkeypatch):
    """A file that appears at RUN after the first look is not overwritten."""
    run_path = tmp_path / "run.csv"
    lines = presentmon._run_lines

    def a_file_appears(*args):
        run_path.write_bytes(b"kept")
        return lines(*args)

    monkeypatch.setattr(presentmon, "_run_lines", a_file_appears)
    code = cli.main(["import", "presentmon", write(tmp_path, capture_text(frames(2))), "-o", str(run_path)])
    assert code == 3 and "never overwrites" in capsys.readouterr().err
    assert run_path.read_bytes() == b"kept"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["capture.csv", "run.csv"]  # no temporary file left


def test_picking_a_process_and_swap_chain(capsys, tmp_path):
    two = capture_text(frames(3) + frames(5, Application="obs64.exe", ProcessID="990"))
    for flags in (["--process", "GAME.EXE"], ["--pid", "4120"]):
        code, out, _ = imported(capsys, tmp_path, two, *flags)
        assert code == 0 and out["result"]["import"]["frames"] == 3
    chains = capture_text(frames(3) + frames(2, SwapChainAddress="0x2"))
    code, out, _ = imported(capsys, tmp_path, chains, "--swapchain", "0x2")
    assert code == 0 and out["result"]["import"]["swapchain"] == "0x2"
    assert out["result"]["import"]["frames"] == 2


# INV-113

def test_header(capsys, tmp_path):
    _, out, _ = imported(capsys, tmp_path, capture_text(frames(3)))
    header = ledger.read(tmp_path / "run.csv").header
    listed = ["commit", "dirty", "build_type", "device", "renderer", "driver", "resolution", "render_scale",
              "pipelined", "display", "scene"]
    assert header["unknown"] == listed == out["result"]["import"]["unknown"]
    assert {field: header[field] for field in listed} == {
        "commit": "unknown", "dirty": True, "build_type": "unknown", "device": "unknown", "renderer": "unknown",
        "driver": "unknown", "resolution": [1, 1], "render_scale": 0, "pipelined": False,
        "display": "onscreen", "scene": "unknown"}
    assert header["api"] == "dxgi" and header["vsync"] is False
    assert header["tool"] == {"name": "PresentMon", "version": "unknown"} and header["inputs"] == []

    def unknown_of(presents, columns=COLUMNS):
        imported(capsys, tmp_path, capture_text(presents, columns), *EVERY_FACT)
        return ledger.read(tmp_path / "run.csv").header.get("unknown", [])

    assert unknown_of(frames(3)) == []
    assert unknown_of([row(), row(PresentRuntime="Vulkan")]) == ["api"]
    assert unknown_of(frames(2, PresentRuntime="NA")) == ["api"]  # PresentMon's "nothing to say"
    assert unknown_of(frames(2), [c for c in COLUMNS if c != "PresentRuntime"]) == ["api"]
    assert unknown_of([row(SyncInterval="0"), row(SyncInterval="1")]) == ["vsync"]
    assert unknown_of(frames(2), [c for c in COLUMNS if c != "SyncInterval"]) == ["vsync"]

    first = ledger.read(tmp_path / "run.csv").header["run_id"]
    imported(capsys, tmp_path, capture_text(frames(2), [c for c in COLUMNS if c != "SyncInterval"]))
    assert ledger.read(tmp_path / "run.csv").header["run_id"] == first  # the capture's bytes alone decide it
    imported(capsys, tmp_path, capture_text(frames(3), [c for c in COLUMNS if c != "SyncInterval"]))
    assert ledger.read(tmp_path / "run.csv").header["run_id"] != first  # other bytes, another id


# INV-115

def test_report_says_imported(capsys, tmp_path):
    imported(capsys, tmp_path, capture_text(frames(5)))
    run_path = tmp_path / "run.csv"
    _, out = command(capsys, "report", str(run_path))
    summary = " ".join(out["summary"])
    assert "imported from PresentMon, so it has no passes" in summary
    assert "costliest pass" not in summary
    assert out["result"]["passes"] == []
    assert all(frame["top_pass"] is None for frame in out["result"]["worst_frames"])

    run_path.write_text(run_path.read_text(encoding="utf-8").replace('"name":"PresentMon"', '"name":"bench"'),
                        encoding="utf-8")
    _, out = command(capsys, "report", str(run_path))
    assert "imported from PresentMon" not in " ".join(out["summary"])
    assert {entry["name"] for entry in out["result"]["passes"]} == {"cpu_remainder", "gpu_remainder"}
    assert all(frame["top_pass"] is not None for frame in out["result"]["worst_frames"])  # so None above is the rule
