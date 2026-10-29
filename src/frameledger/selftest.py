"""`--selftest`: the analyser's own checks on built-in sample files.

The samples live here, not in tests/, so frameledger.pyz carries them
and an engine can run the checks on any machine with Python alone.
"""

from __future__ import annotations

import json
from decimal import Decimal

import bisecting
import budgeting
import compare
import ledger
import run_report

_HEADER = "# frameledger " + json.dumps({
    "schema": 1, "run_id": "s1", "engine": "selftest", "tool": {"name": "selftest", "version": "1"},
    "build_type": "release", "commit": "0", "dirty": False, "device": "none", "renderer": "none",
    "driver": "none", "api": "none", "resolution": [640, 480], "render_scale": 1.0, "vsync": False,
    "pipelined": True, "display": "offscreen", "scene": "C:\\samples\\scene.json",
    "inputs": [{"name": "scene", "hash": "md5:" + "0" * 32, "bytes": 1}],
    "started_utc": "2026-10-24T00:00:00Z",
})


def _frame(f: int, last: bool) -> list[str]:
    cpu = [f"s1,view:1,{f},frame,cpu_span,0,{8 + f}.000", f"s1,view:1,{f},cpu,scene,0,5.250"]
    if not last:
        cpu.append(f"s1,view:1,{f},frame,wall,0,16.667")
    return cpu


def _gpu(f: int) -> list[str]:
    return [f"s1,view:1,{f},frame,gpu_span,0,{10 + f}.000", f"s1,view:1,{f},gpu,shadows,0,-0.004"]


def _sample(rows: list[str], header: str = _HEADER) -> bytes:
    lines = [header, ledger.COLUMNS, *rows, '# frameledger-close {"rows_dropped":0,"frames":4}']
    return ("\n".join(lines) + "\n").encode()


_IN_ORDER = [row for f in range(4) for row in _frame(f, f == 3) + _gpu(f)]
_GPU_LATE = [row for f in range(4) for row in _frame(f, f == 3)] + [row for f in range(4) for row in _gpu(f)]
_GOOD = _sample(_IN_ORDER)


def _rules(data: bytes) -> list[tuple[int, str]]:
    return [(b.line, b.rule) for b in ledger.read_bytes(data, "sample").breaches]


def _newer_schema_refused() -> bool:
    try:
        ledger.read_bytes(_sample(_IN_ORDER, _HEADER.replace('"schema": 1', '"schema": 2')), "sample")
    except ledger.LedgerError:
        return True
    return False


def _report(data: bytes) -> dict:
    return run_report.report(ledger.read_bytes(data, "sample"))["result"]


def _gpu_figure(result: dict, name: str) -> float:
    return next(e["median_ms"] for e in result["passes"] + result["frame_times"] if e["name"] == name)


# Frame 1's GPU result never arrived: gpu_span 10, 12 and 13 remain.
_GPU_MISSING = _sample([row for row in _IN_ORDER if row != "s1,view:1,1,frame,gpu_span,0,11.000"])
# A depth-1 row under each frame's shadows pass, which the remainder must not subtract.
_NESTED = _sample(_IN_ORDER + [f"s1,view:1,{f},gpu,shadows/inner,1,2.000" for f in range(4)])

# Five frames of 250 ms: three end inside the first second; the fourth
# ends exactly at 1 s, so it is the next window's.
_QUARTERS = _sample([row for f in range(6) for row in
                     [f"s1,,{f},frame,cpu_span,0,1.000"] + ([f"s1,,{f},frame,wall,0,250.000"] if f < 5 else [])])


def _floor_windows(data: bytes) -> list[dict]:
    run = ledger.read_bytes(data, "sample")
    return run_report.floor(run, Decimal(3), 0, 250_000)["result"]["windows"]


def _compare_verdict(new: bytes) -> str:
    """Three copies of the good sample against three of `new`."""
    def runs(data: bytes) -> list[ledger.Run]:
        return [ledger.read_bytes(data, "sample") for _ in range(compare.FEWEST_RUNS)]
    return compare.compare(runs(_GOOD), runs(new), {}, Decimal("0.050"), Decimal(3))["verdict"]


def _bisect_verdict(bad_above: str) -> str:
    """The good sample as the tested run; its cpu/scene median in view segments is 5.250."""
    wanted = bisecting.Wanted("cpu", "scene", "median", None, "view", None)
    tested = [bisecting.Loaded("sample", ledger.read_bytes(_GOOD, "sample"), None)]
    floors = bisecting.Floors(Decimal("0.050"), Decimal("1.000"), Decimal(3))
    return bisecting.bisect(wanted, tested, [], [], {}, floors, bad_above=Decimal(bad_above))["verdict"]


def _budget_verdict(limit: str) -> str:
    """The good sample against one budget on its cpu/scene median, 5.250."""
    text = f'# frameledger-budget {{"schema":1}}\n{budgeting.COLUMNS}\ncpu,scene,view,,median,{limit}\n'
    budgets = budgeting.read_bytes(text.encode(), "sample")
    return budgeting.judge(ledger.read_bytes(_GOOD, "sample"), budgets, 0)["verdict"]


def run() -> list[tuple[str, bool]]:
    """Each check's name and whether it passed."""
    good = ledger.read_bytes(_GOOD, "sample")
    return [
        ("a conforming sample has no breaches", good.breaches == []),
        ("a negative GPU value is kept and warned on",
         [n.code for n in good.notices] == ["negative_value"] * 4
         and good.frames[0][("gpu", "shadows")].thousandths == -4),
        ("CRLF line endings read the same as LF",
         ledger.read_bytes(_GOOD.replace(b"\n", b"\r\n"), "sample") == good),
        ("GPU rows written late join their own frame",
         ledger.read_bytes(_sample(_GPU_LATE), "sample").frames == good.frames),
        ("a missing header is a breach on line 1", _rules(_GOOD.split(b"\n", 1)[1]) == [(1, "header")]),
        ("a comma decimal point is a breach",
         _rules(_GOOD.replace(b"5.250", b'"5,250"', 1)) == [(4, "value")]),
        ("a zero frame/wall is a breach", _rules(_GOOD.replace(b"16.667", b"0.000", 1)) == [(5, "wall")]),
        ("a newer schema is refused", _newer_schema_refused()),
        ("a missing GPU result is left out, not counted as zero",
         _report(_GPU_MISSING)["missing_gpu_frames"] == 1 and _gpu_figure(_report(_GPU_MISSING), "gpu_span") == 12.0),
        ("the remainder subtracts depth-0 rows only", _gpu_figure(_report(_NESTED), "gpu_remainder") == 11.004),
        ("a window counts the frames ending inside it",
         _floor_windows(_QUARTERS) == [{"start_s": 0.0, "fps": 3, "mean_ms": 250.0, "pass": True}]),
        ("a compare of a run with itself passes, and a slower pass fails it",
         _compare_verdict(_GOOD) == "pass" and _compare_verdict(_GOOD.replace(b"5.250", b"6.250")) == "fail"),
        ("a bisect calls a value at the threshold good and one above it bad",
         _bisect_verdict("5.250") == "good" and _bisect_verdict("5.249") == "bad"),
        ("a pass at its budget holds, and one over it fails",
         _budget_verdict("5.250") == "pass" and _budget_verdict("5.249") == "fail"),
    ]
