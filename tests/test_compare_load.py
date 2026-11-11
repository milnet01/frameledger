"""A compare on a busy machine (S22).

Invariants from docs/specs/FLED-0001-run-file-format.md § 5: INV-82 to
INV-84, the rules of § 4.2's `peak` and § 4.10's *Taken under load* and
its three difference warnings.
"""

import json

import pytest

import cli
from test_compare import HEADER, alike, compare, run_text


def sets(old_wall: float, new_wall: float, old_headers=None, new_headers=None) -> tuple[list, list]:
    """Three old and three new runs, interleaved in time; the frame/wall of
    each set as given, every other measure alike. old_headers and
    new_headers give each run's extra header fields, one dict a run."""
    texts = {}
    for side, wall, headers, offset in (("old", old_wall, old_headers, 0), ("new", new_wall, new_headers, 1)):
        texts[side] = [run_text(alike(10.0, wall=wall), run_id=f"{side}{i}",
                                started_utc=f"2026-11-10T12:{offset + 2 * i:02d}:00Z",
                                **((headers or [{}] * 3)[i]))
                       for i in range(3)]
    return texts["old"], texts["new"]


def new_2(**header) -> list[dict]:
    return [{}, header, {}]


def test_peak_is_a_number(capsys, tmp_path):
    """INV-82: a `peak` must be a number; only the `peak` key differs
    between the passing and the breaching header."""
    for field in ("load", "gpu_busy_pct"):
        path = tmp_path / f"{field}.csv"
        for peak, code in ((0.3, 0), ("high", 1)):
            path.write_text(run_text(alike(10.0), **{field: {"start": 0.1, "end": 0.2, "peak": peak}}),
                            encoding="utf-8")
            assert cli.main(["check", str(path), "--json"]) == code, (field, peak)
            out = json.loads(capsys.readouterr().out)
            if code:
                assert field in json.dumps(out["result"])


UNDER_LOAD_CASES = {
    "load above": (new_2(load={"start": 0.0, "end": 0.0, "peak": 0.30}), [], 2, ["load.peak"]),
    "load at the limit": (new_2(load={"start": 0.0, "end": 0.0, "peak": 0.25}), [], 1, []),
    "load under a raised limit": (new_2(load={"start": 0.0, "end": 0.0, "peak": 0.30}),
                                  ["--max-load", "0.5"], 1, []),
    "limits at their tops": (new_2(load={"start": 0.0, "end": 0.0, "peak": 1.0},
                                   gpu_busy_pct={"start": 0, "end": 0, "peak": 100}),
                             ["--max-load", "1", "--max-gpu-busy", "100"], 1, []),
    "gpu above": (new_2(gpu_busy_pct={"start": 0, "end": 0, "peak": 21}), [], 2, ["gpu_busy_pct.peak"]),
    "start only": (new_2(load={"start": 0.9, "end": 0.9}), [], 1, []),
}


@pytest.mark.parametrize("case", UNDER_LOAD_CASES)
def test_under_load_inconclusive(capsys, tmp_path, case):
    """INV-83: the new frame/wall is 2 ms slower in every run, so without
    the load the compare fails, exit 1; only the load rule can make it 2."""
    headers, flags, want_code, want_under = UNDER_LOAD_CASES[case]
    code, result = compare(capsys, tmp_path, *sets(16.0, 18.0, new_headers=headers), *flags)
    assert code == want_code
    runs = {r["name"]: r for r in result["result"]["runs"]}
    assert runs["new-2"]["under_load"] == want_under
    assert all(r["under_load"] == [] for name, r in runs.items() if name != "new-2")
    if want_under:
        assert result["verdict"] == "inconclusive"
        first = next(s for s in result["summary"] if "under load" in s)
        assert first.startswith("new-2 was taken under load: ") and want_under[0] in first


@pytest.mark.parametrize("flag, value", [("--max-load", "-1"), ("--max-load", "1.01"),
                                         ("--max-load", "25"), ("--max-gpu-busy", "100.5")])
def test_load_limit_bounds(capsys, flag, value):
    """INV-83: a limit outside its peak's range is exit 3, refused for its
    value; an unknown flag would exit 3 too, so the message is checked.
    No peak exceeds its range, so a limit above it never fires, as when
    25 is meant as 25%."""
    assert cli.main(["compare", "--old", "a", "b", "c", "--new", "d", "e", "f", flag, value]) == 3
    error = capsys.readouterr().err
    assert flag in error and f"'{value}' must be" in error and "unrecognized" not in error


DIFFER_CASES = {
    "load_differs": ("load", "start", 0.05, 0.20, 0.15),
    "gpu_busy_differs": ("gpu_busy_pct", "start", 2, 13, 12),
    "gpu_clock_differs": ("gpu_clock_mhz", "end", 2000, 1880, 1900),
}


@pytest.mark.parametrize("code_name", DIFFER_CASES)
def test_side_differs_warnings(capsys, tmp_path, code_name):
    """INV-84: sides measured under different load or GPU clock are warned
    of when their medians differ by more than the limit, not at it, and
    the verdict is unchanged."""
    field, key, old_value, new_over, new_at = DIFFER_CASES[code_name]

    def span(value):
        return {field: {"start": value, "end": value} | {key: value}}

    for new_value, warned in ((new_over, True), (new_at, False)):
        code, result = compare(capsys, tmp_path, *sets(16.0, 16.0, [span(old_value)] * 3,
                                                       [span(new_value)] * 3))
        assert code == 0
        codes = [w["code"] for w in result["warnings"]]
        assert (code_name in codes) == warned, (new_value, codes)
    lacking = [span(new_over), {}, span(new_over)]  # new-2 has no such field
    code, result = compare(capsys, tmp_path, *sets(16.0, 16.0, [span(old_value)] * 3, lacking))
    assert code == 0 and code_name not in [w["code"] for w in result["warnings"]]


def test_alike_header_has_no_load():
    """The fixture header carries no load field, so only the cases above set one."""
    assert not {"load", "gpu_busy_pct", "gpu_clock_mhz"} & set(HEADER)
