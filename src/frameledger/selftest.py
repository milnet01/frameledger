"""`--selftest`: the analyser's own checks on built-in sample files.

The samples live here, not in tests/, so frameledger.pyz carries them
and an engine can run the checks on any machine with Python alone.
"""

from __future__ import annotations

import json

import ledger

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
    ]
