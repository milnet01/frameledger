"""`compare`'s `noisy_run`: one run whose own frame times scatter (FLED-0072).

Invariant from docs/specs/FLED-0001-run-file-format.md § 5: INV-132, the
`noisy_run` rule of § 4.10. Each run is built frame by frame here, so a
segment kind's frame/wall values are exactly those written.
"""

import json

import cli
from test_compare import HEADER, compare

CALM = [("view:1", 16.0)] * 1000


def run_text(frames: list[tuple[str, float]], run_id: str, minute: int) -> str:
    """A run of one frame per (segment, frame/wall ms) in `frames`."""
    fields = {**HEADER, "run_id": run_id, "started_utc": f"2026-11-21T12:{minute:02d}:00Z"}
    lines = [f"# frameledger {json.dumps(fields)}", "run_id,segment,frame,category,name,depth,value"]
    for frame, (segment, wall) in enumerate(frames):
        for name, value in (("wall", wall), ("cpu_span", 8.0), ("gpu_span", 12.0)):
            lines.append(f"{run_id},{segment},{frame},frame,{name},0,{value:.3f}")
    lines.append(f'# frameledger-close {{"rows_dropped":0,"frames":{len(frames)}}}')
    return "\n".join(lines) + "\n"


def with_slow(count: int, ms: float) -> list[tuple[str, float]]:
    """1000 view frames: `count` of them at `ms`, the rest at 16.000 ms."""
    return [("view:1", 16.0)] * (1000 - count) + [("view:1", ms)] * count


def sides(new_frames: list[list[tuple[str, float]]]) -> tuple[list[str], list[str]]:
    """Three calm old runs, and one new run per entry; interleaved in time."""
    old = [run_text(CALM, f"o{i}", 2 * i) for i in range(3)]
    new = [run_text(frames, f"n{i}", 2 * i + 1) for i, frames in enumerate(new_frames)]
    return old, new


def noisy(result: dict) -> list[str]:
    return [w["message"] for w in result["warnings"] if w["code"] == "noisy_run"]


def noise(result: dict, name: str) -> list[dict]:
    return next(r["noise"] for r in result["result"]["runs"] if r["name"] == name)


def test_noisy_run(capsys, tmp_path):
    """INV-132: more than 2 percent of a kind's frame/wall values over
    twice its median warns, naming the run and the kind; the warning
    changes neither verdict nor exit."""
    code, result = compare(capsys, tmp_path, *sides([CALM, with_slow(21, 40.0), CALM]))
    assert noisy(result) == [
        "new-2: 2.10% of its frame/wall values in view segments are over twice their median of 16.000 ms, "
        "above 2%, so something else may have slowed the run; re-run it"]
    assert any(s.startswith("Warning: new-2: 2.10% of its frame/wall values") for s in result["summary"])
    assert noise(result, "new-2") == [{"segment_kind": "view", "frames": 1000, "median": 16.0, "over_twice": 21,
                                       "share_pct": 2.1, "quartile_spread": 0.0, "judged": True}]

    # The same runs with the slow frames at exactly twice the median warn
    # nothing, and give the same verdict and exit.
    quiet_code, quiet = compare(capsys, tmp_path, *sides([CALM, with_slow(21, 32.0), CALM]))
    assert noisy(quiet) == [] and noise(quiet, "new-2")[0]["over_twice"] == 0
    assert (quiet_code, quiet["verdict"]) == (code, result["verdict"])

    # Exactly 2 percent is not more than the limit.
    _, result = compare(capsys, tmp_path, *sides([CALM, with_slow(20, 40.0), CALM]))
    assert noisy(result) == [] and noise(result, "new-2")[0]["share_pct"] == 2.0

    # Each run that warns has its own sentence.
    _, result = compare(capsys, tmp_path, *sides([CALM, with_slow(21, 40.0), with_slow(30, 40.0)]))
    assert [m.split(":")[0] for m in noisy(result)] == ["new-2", "new-3"]
    assert [s.split()[1] for s in result["summary"] if "over twice their median" in s] == ["new-2:", "new-3:"]

    # The quartile spread is reported: (p75 - p25) / median.
    spread = [("view:1", 12.0)] * 250 + [("view:1", 16.0)] * 500 + [("view:1", 20.0)] * 250
    _, result = compare(capsys, tmp_path, *sides([CALM, spread, CALM]))
    assert noise(result, "new-2")[0]["quartile_spread"] == 0.25


def test_short_kind_is_unjudged(capsys, tmp_path):
    """INV-132: a kind with fewer than 1000 values is not judged, and its
    entry says so; the kinds are judged apart, never pooled."""
    short = CALM + [("spot:1", 16.0)] * 899 + [("spot:1", 40.0)] * 100
    _, result = compare(capsys, tmp_path, *sides([CALM, short, CALM]))
    assert noisy(result) == []
    assert [(e["segment_kind"], e["frames"], e["over_twice"], e["judged"]) for e in noise(result, "new-2")] == [
        ("spot", 999, 100, False), ("view", 1000, 0, True)]


def test_base_run_is_named_once(capsys, tmp_path):
    """INV-132: under § 4.16 a base run that warns is named once, opening
    with its own name, though every variant's compare finds it."""
    paths = {}
    for i, (label, frames) in enumerate([("base-1", CALM), ("base-2", with_slow(21, 40.0)), ("base-3", CALM),
                                         *((f"{v}-{n}", CALM) for v in "ab" for n in (1, 2, 3))]):
        path = tmp_path / f"{label}.csv"
        path.write_text(run_text(frames, f"r{i}", i), encoding="utf-8")
        paths[label] = str(path)
    code = cli.main(["compare", "--base", *(paths[f"base-{n}"] for n in (1, 2, 3)),
                     *(arg for v in "ab" for arg in ("--variant", v, *(paths[f"{v}-{n}"] for n in (1, 2, 3)))),
                     "--json"])
    out = json.loads(capsys.readouterr().out)
    assert out["exit_code"] == code
    found = noisy(out)
    assert len(found) == 1 and found[0].startswith("base-2: 2.10% of its frame/wall values")
    assert sum("over twice their median" in s for s in out["summary"]) == 1
