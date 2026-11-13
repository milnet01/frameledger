"""The machine's state in the header, and what is said of it (FLED-0055).

Invariants from docs/specs/FLED-0001-run-file-format.md § 5: INV-104 to
INV-107, the rules of § 4.2's machine-state fields, § 4.9's `on_battery`
and `throttled`, and § 4.10's warnings when the two sides differ.
"""

import json

import pytest

import cli
from test_compare import alike, compare, run_text
from test_compare_load import sets
from test_trust import PASSING, run, trust, with_header

GOOD_FIELDS = {
    "cpu_governor": "powersave/balance_performance",
    "turbo": False,
    "power": "battery",
    "cpu_clock_mhz": {"start": 3400.5, "end": 4100},
    "cpu_temp_c": {"start": 41, "end": 62.5, "peak": 71},
    "gpu_temp_c": {"start": 38, "end": 55},
    "throttled": True,
}
BAD_FIELDS = {
    "cpu_governor": 1,
    "turbo": "on",
    "power": "ac",
    "cpu_clock_mhz": {"start": 3400},
    "cpu_temp_c": {"start": 41, "end": 62, "peak": "hot"},
    "gpu_temp_c": 55,
    "throttled": "no",
}


@pytest.mark.parametrize("field", GOOD_FIELDS)
def test_field_shapes(capsys, tmp_path, field):
    """INV-104: each field is read in its § 4.2 shape, and refused in
    another."""
    path = tmp_path / "run.csv"
    for value, code in ((GOOD_FIELDS[field], 0), (BAD_FIELDS[field], 1)):
        path.write_text(run_text(alike(10.0), **{field: value}), encoding="utf-8")
        assert cli.main(["check", str(path), "--json"]) == code, value
        out = json.loads(capsys.readouterr().out)
        breaches = out["result"]["files"][0]["breaches"]
        assert [b["rule"] for b in breaches] == (["header"] if code else [])
        if code:
            assert field in breaches[0]["message"]


def test_battery_and_throttled_runs(capsys, tmp_path):
    """INV-105: a run on battery, or one that was throttled, says so, and
    its verdict stays."""
    cases = [({"power": "battery"}, ["on_battery"]),
             ({"throttled": True}, ["throttled"]),
             ({"power": "battery", "throttled": True}, ["on_battery", "throttled"]),
             ({"power": "mains", "throttled": False}, []),
             # Neither a governor, a clock nor a temperature warns alone.
             ({name: GOOD_FIELDS[name] for name in ("cpu_governor", "turbo", "cpu_clock_mhz",
                                                    "cpu_temp_c", "gpu_temp_c")}, [])]
    for command in ("report", "floor"):
        plain = run(capsys, tmp_path, command, PASSING)
        for changes, codes in cases:
            out = run(capsys, tmp_path, command, with_header(PASSING, **changes))
            assert [w["code"] for w in trust(out)] == codes, (command, changes)
            assert (out["verdict"], out["exit_code"]) == (plain["verdict"], plain["exit_code"])
    checked = run(capsys, tmp_path, "check", with_header(PASSING, power="battery", throttled=True))
    assert checked["exit_code"] == 0 and trust(checked) == []


def warned(capsys, tmp_path, old_headers, new_headers) -> dict[str, str]:
    """Each difference warning's message, by code, from a compare of two
    sets alike but for their headers."""
    code, result = compare(capsys, tmp_path, *sets(16.0, 16.0, old_headers, new_headers))
    assert code == 0
    return {w["code"]: w["message"] for w in result["warnings"] if w["code"].endswith("_differs")}


VALUE_CASES = {
    "governor_differs": ("cpu_governor", "performance", "powersave", '"performance"', '"powersave"'),
    "turbo_differs": ("turbo", True, False, "true", "false"),
    "power_differs": ("power", "mains", "battery", '"mains"', '"battery"'),
    "sanitizers_differs": ("sanitizers", [], ["address", "undefined"], "[]", '["address", "undefined"]'),
}


@pytest.mark.parametrize("code_name", VALUE_CASES)
def test_side_values_differ(capsys, tmp_path, code_name):
    """INV-106: the two sides' values of a setting differ. One run of the
    three differing is enough; a run lacking the field gives none."""
    field, old_value, new_value, shown_old, shown_new = VALUE_CASES[code_name]
    old, new = {field: old_value}, {field: new_value}

    messages = warned(capsys, tmp_path, [old] * 3, [new] * 3)
    assert list(messages) == [code_name]
    assert shown_old in messages[code_name] and shown_new in messages[code_name]
    mixed = warned(capsys, tmp_path, [old] * 3, [old, new, old])
    assert list(mixed) == [code_name]
    assert warned(capsys, tmp_path, [old] * 3, [old] * 3) == {}
    assert warned(capsys, tmp_path, [old] * 3, [new, {}, new]) == {}
    # The same mix on both sides is no difference between them.
    assert warned(capsys, tmp_path, [old, new, old], [new, old, old]) == {}


def test_side_values_are_shown_short(capsys, tmp_path):
    """INV-106: a long governor is cut short in the message."""
    messages = warned(capsys, tmp_path, [{"cpu_governor": "a" * 5000}] * 3, [{"cpu_governor": "b"}] * 3)
    assert "..." in messages["governor_differs"] and len(messages["governor_differs"]) < 200


def span(field, end, peak=None):
    return {field: {"start": 30, "end": end} | ({} if peak is None else {"peak": peak})}


def test_cpu_clock_differs(capsys, tmp_path):
    """INV-107: the CPU clock is judged as the GPU's is, on `end` and by
    5% of the old median, above and not at."""
    old = [span("cpu_clock_mhz", 3000)] * 3
    assert list(warned(capsys, tmp_path, old, [span("cpu_clock_mhz", 2840)] * 3)) == ["cpu_clock_differs"]
    assert warned(capsys, tmp_path, old, [span("cpu_clock_mhz", 2850)] * 3) == {}
    assert warned(capsys, tmp_path, old, [span("cpu_clock_mhz", 2840), {}, span("cpu_clock_mhz", 2840)]) == {}


@pytest.mark.parametrize("field", ["cpu_temp_c", "gpu_temp_c"])
def test_temperature_differs(capsys, tmp_path, field):
    """INV-107: temperatures differ by more than 10 degrees, on `peak`
    when every run has one and on `end` otherwise."""
    code_name = field.removesuffix("_c") + "_differs"
    old = [span(field, 60)] * 3
    by_end = warned(capsys, tmp_path, old, [span(field, 71)] * 3)
    assert list(by_end) == [code_name] and f"{field}.end" in by_end[code_name]
    assert warned(capsys, tmp_path, old, [span(field, 70)] * 3) == {}
    assert warned(capsys, tmp_path, old, [span(field, 71), {}, span(field, 71)]) == {}

    # Every run has a peak: the ends are alike, and the peaks decide.
    peaked_old = [span(field, 60, peak=65)] * 3
    by_peak = warned(capsys, tmp_path, peaked_old, [span(field, 60, peak=76)] * 3)
    assert list(by_peak) == [code_name] and f"{field}.peak" in by_peak[code_name]
    assert warned(capsys, tmp_path, peaked_old, [span(field, 71, peak=75)] * 3) == {}
    # One run without a peak: the ends decide again.
    some_peaks = [span(field, 60, peak=76), span(field, 60), span(field, 60, peak=76)]
    assert warned(capsys, tmp_path, peaked_old, some_peaks) == {}
