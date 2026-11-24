"""S19 (FLED-0046): a survey of about a million rows is analysed in under
a minute. Marked slow, so `pytest -m "not slow"` skips it; the gate runs
it on every Python it tests.
"""

import json
import random
import time

import pytest

import cli
from floor_runs import HEADER

RUNS, FRAMES = 10, 10_000  # ten rows a frame: a million rows in all
LIMIT_S = 60


def run_text(seed: int) -> str:
    """One run shaped like an engine's: per frame a wall, CPU and GPU
    spans, six passes and a mem row; about one frame in a thousand a
    30 ms hitch; a new view every 2000 frames."""
    rng = random.Random(seed)
    lines = [HEADER, "run_id,segment,frame,category,name,depth,value"]
    for frame in range(FRAMES):
        at = f"f1,view:{1 + frame // 2000},{frame}"
        wall = 16.0 + rng.random() * 2 + (30 if rng.random() < 0.001 else 0)
        lines += [
            f"{at},frame,wall,0,{wall:.3f}",
            f"{at},frame,cpu_span,0,{wall * 0.6:.3f}",
            f"{at},cpu,scene,0,{wall * 0.3:.3f}",
            f"{at},cpu,culling,1,{wall * 0.1:.3f}",
            f"{at},cpu,ui,0,{wall * 0.1:.3f}",
            f"{at},frame,gpu_span,0,{wall * 0.8:.3f}",
            f"{at},gpu,shadows,0,{wall * 0.2:.3f}",
            f"{at},gpu,gbuffer,0,{wall * 0.3:.3f}",
            f"{at},gpu,lighting,0,{wall * 0.2:.3f}",
            f"{at},mem,vram,0,{1000 + frame % 7:.3f}",
        ]
    lines.append(f'# frameledger-close {{"rows_dropped":0,"frames":{FRAMES}}}')
    return "\n".join(lines) + "\n"


@pytest.mark.slow
def test_a_million_row_survey_is_under_a_minute(capsys, tmp_path):
    """S19 as written: `survey` over ten runs, 1000000 rows, in under
    60 s. Timed from the command's start to its parsed result, so reading
    the files counts; writing them does not."""
    paths, rows = [], 0
    for seed in range(RUNS):
        text = run_text(seed)
        rows += sum(not line.startswith(("#", "run_id,")) for line in text.splitlines())
        path = tmp_path / f"run{seed}.csv"
        path.write_text(text, encoding="utf-8")
        paths.append(str(path))
    assert rows == 1_000_000, rows

    start = time.perf_counter()
    code = cli.main(["survey", *paths, "--fps", "60", "--json"])
    taken = time.perf_counter() - start
    out = json.loads(capsys.readouterr().out)
    assert (code, len(out["result"]["runs"])) == (out["exit_code"], RUNS)
    assert taken < LIMIT_S, f"a {rows}-row survey took {taken:.1f} s, over S19's {LIMIT_S} s"
