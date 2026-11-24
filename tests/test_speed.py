"""S19 (FLED-0046): a survey of about a million rows is analysed in under
a minute. 60 s is S19's bar, not a measurement, so it is never tightened
to fit one machine. Marked slow, so `pytest -m "not slow"` skips it; the
gate runs it once on each Python it tests, about 10 s each. It writes
about 35 MB to tmp_path, which is in RAM on the owner's machine.
"""

import json
import random
import time

import pytest

import cli
from floor_runs import HEADER

RUN_ID = json.loads(HEADER.removeprefix("# frameledger "))["run_id"]
RUNS = 10
ROWS_PER_RUN = 100_000  # ten runs, a million rows: S19's survey
LIMIT_S = 60


def wall_ms(rng: random.Random) -> float:
    """Walls either side of the 16.667 ms budget at --fps 60, so every
    run is flagged and survey takes its flagged path, with a few spikes
    to lift the 99th percentile above the median."""
    return 15.5 + rng.random() * 2 + (30 if rng.random() < 0.002 else 0)


def vestige_like(rng: random.Random) -> list[str]:
    """Vestige's shape (its perf_compare captures): eight rows a frame, no
    segment, and each frame's GPU rows written two frames late, after a
    later frame's wall, as its timers are read back."""
    rows, late = [], {}
    for frame in range(ROWS_PER_RUN // 8):
        wall = wall_ms(rng)
        at = f"{RUN_ID},,{frame}"
        rows += [f"{at},frame,cpu_span,0,{wall * 0.6:.3f}", f"{at},cpu,RenderScene,0,{wall * 0.4:.3f}",
                 f"{at},frame,wall,0,{wall:.3f}", f"{at},frame,present_wait,0,{wall * 0.05:.3f}",
                 f"{at},mem,gpu_mb,0,{900 + frame % 5:.3f}"]
        late[frame] = [f"{at},frame,gpu_span,0,{wall * 0.8:.3f}", f"{at},gpu,Shadow,0,{wall * 0.2:.3f}",
                       f"{at},gpu,PostProcess,0,{wall * 0.3:.3f}"]
        rows += late.pop(frame - 2, [])
    for frame in sorted(late):  # the last two frames' GPU rows, read back after the run
        rows += late[frame]
    return rows


GPU_STEPS = ("fires", "shadows", "clusters", "fog", "depth", "opaque", "grass", "translucent",
             "flames", "bloom", "post")
MOSTLY_ZERO = {"fires", "shadows", "flames"}  # a still camera redraws no shadow tiles (UT Ants)


def ut_like(rng: random.Random) -> list[str]:
    """UT Ants' shape (ut-bench frame): twenty rows a frame, three host
    steps and eleven flat GPU steps, some 0.000 on most frames, and a new
    view every 60 or 120 frames, so survey pools many short segments."""
    rows, view, left = [], 0, 0
    for frame in range(ROWS_PER_RUN // 20):
        if left == 0:
            view, left = view + 1, (60 if view % 2 else 120)
        left -= 1
        wall = wall_ms(rng)
        at = f"{RUN_ID},view:{view},{frame}"
        rows += [f"{at},frame,wall,0,{wall:.3f}", f"{at},frame,cpu_span,0,{wall * 0.5:.3f}",
                 f"{at},frame,gpu_span,0,{wall * 0.9:.3f}", f"{at},frame,fence_wait,0,{wall * 0.1:.3f}",
                 f"{at},frame,present_wait,0,{wall * 0.05:.3f}", f"{at},mem,vram_mb,0,{1200 + view % 9:.3f}"]
        rows += [f"{at},cpu,{step},0,{wall * share:.3f}"
                 for step, share in (("prepare", 0.1), ("record", 0.2), ("submit", 0.15))]
        rows += [f"{at},gpu,{step},0,{0 if step in MOSTLY_ZERO and rng.random() < 0.9 else wall * 0.07:.3f}"
                 for step in GPU_STEPS]
    return rows


DOOM_PASSES = ("temporal", "atrous", "composite", "bloom", "tonemap", "taau", "sky", "hud", "post")


def doom_like(rng: random.Random) -> list[str]:
    """DOOM Ants' shape (run_ledger.c): twenty rows a frame, the frame's
    waits, four host steps, nine traced passes, a tic event, or a cut
    where the view changes every 500 frames, and an ext.doom row."""
    rows = []
    for frame in range(ROWS_PER_RUN // 20):
        wall = wall_ms(rng)
        at = f"{RUN_ID},view:{1 + frame // 500},{frame}"
        event = "cut" if frame % 500 == 0 else "tic"
        rows += [f"{at},frame,cpu_span,0,{wall * 0.5:.3f}", f"{at},frame,fence_wait,0,{wall * 0.1:.3f}",
                 f"{at},frame,present_wait,0,{wall * 0.05:.3f}", f"{at},frame,wall,0,{wall:.3f}",
                 f"{at},frame,gpu_span,0,{wall * 0.9:.3f}", f"{at},event,{event},0,1.000",
                 f"{at},ext.doom,view_lag,0,{rng.random():.3f}"]
        rows += [f"{at},cpu,{step},0,{wall * 0.1:.3f}" for step in ("game", "build", "record", "submit")]
        rows += [f"{at},gpu,{name},0,{wall * 0.09:.3f}" for name in DOOM_PASSES]
    return rows


SHAPES = (vestige_like, ut_like, doom_like)


@pytest.mark.slow
def test_a_million_row_survey_is_under_a_minute(capsys, tmp_path):
    """S19 as written: `survey` over ten runs, a million rows, in under
    60 s. Timed around cli.main alone: reading, judging and writing the
    JSON count. Writing the files, interpreter start-up and parsing the
    output do not, and the files are read from the cache, as they were
    just written; at about 6 s against 60 s none of that matters."""
    paths = []
    for seed in range(RUNS):
        shape = SHAPES[seed % len(SHAPES)]
        rows = shape(random.Random(seed))
        assert len(rows) == ROWS_PER_RUN, (shape.__name__, len(rows))
        frames = int(rows[-1].split(",")[2]) + 1
        path = tmp_path / f"run{seed}.csv"
        path.write_text("\n".join([HEADER, "run_id,segment,frame,category,name,depth,value", *rows,
                                   f'# frameledger-close {{"rows_dropped":0,"frames":{frames}}}']) + "\n",
                        encoding="utf-8")
        paths.append(str(path))

    start = time.perf_counter()
    code = cli.main(["survey", *paths, "--fps", "60", "--json"])
    taken = time.perf_counter() - start
    out = json.loads(capsys.readouterr().out)
    # Every run read and judged: a file breaking the format would be
    # "unjudged" with no p99, and timing it would prove nothing.
    assert [(e["verdict"], e["p99_ms"] is not None) for e in out["result"]["runs"]] == [("flagged", True)] * RUNS
    assert code == 1  # survey's code when a run is flagged
    assert taken < LIMIT_S, f"a {RUNS * ROWS_PER_RUN}-row survey took {taken:.1f} s, over S19's {LIMIT_S} s"
