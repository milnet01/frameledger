"""ledger.read: one run file into a Run.

INV-3 and INV-4 name `report --json` as their comparison. Until
`report` exists (FLED-0003) they compare the Run itself, which every
report is built from; FLED-0003 adds the report comparison.
"""

from pathlib import Path

import pytest

import ledger

FIXTURES = Path(__file__).parent / "fixtures"


def test_crlf_equals_lf(tmp_path):
    """INV-3: the same rows with LF and CRLF endings read the same."""
    lf = FIXTURES / "small-run.csv"
    crlf = tmp_path / "small-run-crlf.csv"
    crlf.write_bytes(lf.read_bytes().replace(b"\n", b"\r\n"))
    assert b"\r\n" in crlf.read_bytes()

    a, b = ledger.read(lf), ledger.read(crlf)
    assert a.breaches == [] and b.breaches == []
    assert a == b
    assert ("frame", "cpu_span") in b.frames[2]


def test_late_gpu_rows():
    """INV-4: rows join on (run_id, frame), whatever their order."""
    in_order = ledger.read(FIXTURES / "in-order.csv")
    late = ledger.read(FIXTURES / "gpu-late.csv")
    assert in_order.breaches == [] and late.breaches == []
    assert in_order.frames == late.frames
    assert late.frames[0][("frame", "gpu_span")].thousandths == 10_000
    assert late.frames[3][("gpu", "shadows")].thousandths == 7_000


def test_values_are_exact():
    """Values are kept as integer thousandths, so the timeline sums exactly."""
    run = ledger.read(FIXTURES / "negative-gpu.csv")
    assert run.frames[0][("gpu", "shadows")].thousandths == -4
    assert run.frames[0][("frame", "wall")].thousandths == 16_000


def test_static_kept_as_written():
    run = ledger.read(FIXTURES / "small-run.csv")
    assert run.static == {"pipelines": {"draws": "1520", "primitives": "17436423623014656123"}}
    assert run.close == {"rows_dropped": 0, "frames": 3}


def test_unreadable_raises(tmp_path):
    with pytest.raises(ledger.LedgerError) as caught:
        ledger.read(tmp_path / "absent.csv")
    assert caught.value.path == str(tmp_path / "absent.csv")


def test_newer_schema_raises():
    """INV-2 at the reader: the error names the line and both versions."""
    with pytest.raises(ledger.LedgerError) as caught:
        ledger.read(FIXTURES / "schema-99.csv")
    assert caught.value.line == 1
    assert "schema 99" in str(caught.value) and "schema 1" in str(caught.value)
