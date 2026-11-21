"""`compare`'s `noisy_run`: one run whose own frame times scatter (FLED-0072).

Invariant from docs/specs/FLED-0001-run-file-format.md § 5: INV-132, the
`noisy_run` rule of § 4.10. Each run is built frame by frame here, so a
segment kind's frame/wall values are exactly those written.
"""

import json

import cli
from test_compare import HEADER, compare

CALM = [("view:1", 16.0)] * 1000
VERDICT = (0, "pass")  # every run's frame/wall median is 16 ms, so the compare passes


def run_text(frames: list[tuple[str, float]], run_id: str, minute: int, generated: frozenset[int] = frozenset()
             ) -> str:
    """A run of one frame per (segment, frame/wall ms) in `frames`; each
    frame number in `generated` is marked event/generated."""
    fields = {**HEADER, "run_id": run_id, "started_utc": f"2026-11-21T12:{minute:02d}:00Z"}
    lines = [f"# frameledger {json.dumps(fields)}", "run_id,segment,frame,category,name,depth,value"]
    for frame, (segment, wall) in enumerate(frames):
        for name, value in (("wall", wall), ("cpu_span", 8.0), ("gpu_span", 12.0)):
            lines.append(f"{run_id},{segment},{frame},frame,{name},0,{value:.3f}")
        if frame in generated:
            lines.append(f"{run_id},{segment},{frame},event,generated,0,1.000")
    lines.append(f'# frameledger-close {{"rows_dropped":0,"frames":{len(frames)}}}')
    return "\n".join(lines) + "\n"


def with_slow(count: int, ms: float, frames: int = 1000) -> list[tuple[str, float]]:
    """`frames` view frames: `count` of them at `ms`, the rest at 16.000 ms."""
    return [("view:1", 16.0)] * (frames - count) + [("view:1", ms)] * count


def sides(new_frames: list[list[tuple[str, float]]], generated: frozenset[int] = frozenset()
          ) -> tuple[list[str], list[str]]:
    """Three calm old runs, and one new run per entry; interleaved in time.
    `generated` marks frames of new-2."""
    old = [run_text(CALM, f"o{i}", 2 * i) for i in range(3)]
    new = [run_text(frames, f"n{i}", 2 * i + 1, generated if i == 1 else frozenset())
           for i, frames in enumerate(new_frames)]
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
        "new-2: 21 of its 1000 frame/wall values in view segments, 2.10%, are over twice their median of "
        "16.000 ms, where more than 2% warns; something else may have slowed the run, so re-run it"]
    assert any(s.startswith("Warning: new-2: 21 of its 1000 frame/wall values") for s in result["summary"])
    assert noise(result, "new-2") == [{"segment_kind": "view", "frames": 1000, "median": 16.0, "over_twice": 21,
                                       "share_pct": 2.1, "quartile_spread": 0.0, "judged": True}]

    # The same runs with the slow frames at exactly twice the median warn
    # nothing. Both give the verdict their p99s give, so the warning
    # changes neither verdict nor exit.
    assert (code, result["verdict"]) == VERDICT
    quiet_code, quiet = compare(capsys, tmp_path, *sides([CALM, with_slow(21, 32.0), CALM]))
    assert noisy(quiet) == [] and noise(quiet, "new-2")[0]["over_twice"] == 0
    assert (quiet_code, quiet["verdict"]) == VERDICT

    # A long run just over the limit rounds to 2.00%; the counts show it is over.
    _, result = compare(capsys, tmp_path, *sides([CALM, with_slow(401, 40.0, frames=20001), CALM]))
    assert [m.split(" are ")[0] for m in noisy(result)] == [
        "new-2: 401 of its 20001 frame/wall values in view segments, 2.00%,"]

    # Exactly 2 percent is not more than the limit.
    _, result = compare(capsys, tmp_path, *sides([CALM, with_slow(20, 40.0), CALM]))
    assert noisy(result) == [] and noise(result, "new-2")[0]["share_pct"] == 2.0

    # Each run that warns has its own sentence.
    _, result = compare(capsys, tmp_path, *sides([CALM, with_slow(21, 40.0), with_slow(30, 40.0)]))
    assert [m.split(":")[0] for m in noisy(result)] == ["new-2", "new-3"]
    assert [s.split()[1] for s in result["summary"] if "over twice their median" in s] == ["new-2:", "new-3:"]

    # The quartile spread is reported: (p75 - p25) / median, nearest rank.
    # The ranks 250, 500 and 750 fall on 12, 16 and 24 ms.
    spread = [("view:1", 12.0)] * 250 + [("view:1", 16.0)] * 499 + [("view:1", 24.0)] * 251
    _, result = compare(capsys, tmp_path, *sides([CALM, spread, CALM]))
    assert noise(result, "new-2")[0]["quartile_spread"] == 0.75


def test_short_kind_is_unjudged(capsys, tmp_path):
    """INV-132: a kind with fewer than 1000 values is not judged, and its
    entry says so; the kinds are judged apart, never pooled."""
    short = CALM + [("spot:1", 16.0)] * 899 + [("spot:1", 40.0)] * 100
    _, result = compare(capsys, tmp_path, *sides([CALM, short, CALM]))
    assert noisy(result) == []
    assert [(e["segment_kind"], e["frames"], e["over_twice"], e["judged"]) for e in noise(result, "new-2")] == [
        ("spot", 999, 100, False), ("view", 1000, 0, True)]


def test_segments_of_a_kind_are_pooled(capsys, tmp_path):
    """INV-132: a kind's segments are judged together, as its median is:
    view:1 and view:2 of 500 values each are one view kind of 1000."""
    pooled = [("view:1", 16.0)] * 479 + [("view:1", 40.0)] * 21 + [("view:2", 16.0)] * 500
    _, result = compare(capsys, tmp_path, *sides([CALM, pooled, CALM]))
    assert [(e["segment_kind"], e["frames"], e["judged"]) for e in noise(result, "new-2")] == [("view", 1000, True)]
    assert [m.split(" are ")[0] for m in noisy(result)] == [
        "new-2: 21 of its 1000 frame/wall values in view segments, 2.10%,"]


def test_generated_frames(capsys, tmp_path):
    """INV-132: the values are the application's frames unless
    --all-frames. 1000 frames at 16 ms, each followed by a generated one
    at 4 ms, are 1000 calm walls of 20 ms; with --all-frames they are
    2000 walls whose median is 4 ms, half of them over twice it."""
    frames = [("view:1", ms) for _ in range(1000) for ms in (16.0, 4.0)]
    new_sides = sides([CALM, frames, CALM], generated=frozenset(range(1, 2000, 2)))
    _, result = compare(capsys, tmp_path, *new_sides)
    entry = noise(result, "new-2")[0]
    assert noisy(result) == [] and (entry["frames"], entry["median"], entry["over_twice"]) == (1000, 20.0, 0)
    _, result = compare(capsys, tmp_path, *new_sides, "--all-frames")
    entry = noise(result, "new-2")[0]
    assert (entry["frames"], entry["median"], entry["over_twice"]) == (2000, 4.0, 1000)
    assert [m.split(" are ")[0] for m in noisy(result)] == [
        "new-2: 1000 of its 2000 frame/wall values in view segments, 50.00%,"]


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
    assert len(found) == 1 and found[0].startswith("base-2: 21 of its 1000 frame/wall values")
    assert sum("over twice their median" in s for s in out["summary"]) == 1
