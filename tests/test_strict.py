"""`check --strict`: warnings on what is legal but unwise.

Invariant from docs/specs/FLED-0001-run-file-format.md § 5: INV-118, the
codes of § 4.19's table. Every value here is in thousandths, as the
codes count.
"""

import json

import pytest

import cli
import stats

HEADER = {
    "schema": 1, "run_id": "r", "engine": "vestige", "tool": {"name": "bench", "version": "1.0"},
    "build_type": "release", "commit": "abc123", "dirty": False,
    "device": "AMD Radeon RX 9070 XT", "renderer": "AMD Radeon RX 9070 XT (radeonsi)",
    "driver": "Mesa 26.2", "api": "opengl-4.5", "resolution": [1920, 1080], "render_scale": 1.0,
    "vsync": False, "pipelined": False, "display": "headless", "scene": "atrium",
    "inputs": [{"name": "atrium", "hash": "sha256:" + "ab" * 32, "bytes": 48213}],
    "started_utc": "2026-11-17T12:00:00.250Z", "load": {"start": 0.05, "end": 0.07},
}


def frame(wall, cpu=None, gpu=None):
    """One frame's rows, {(category, name, depth): thousandths}: spans under
    the wall, and depth-0 passes well under their spans."""
    cpu = wall - 4000 if cpu is None else cpu
    gpu = wall - 3000 if gpu is None else gpu
    return {("frame", "cpu_span", 0): cpu, ("frame", "gpu_span", 0): gpu, ("frame", "wall", 0): wall,
            ("cpu", "scene", 0): cpu // 2, ("cpu", "ui", 0): cpu // 4, ("cpu", "shadows", 1): cpu // 8,
            ("gpu", "geometry", 0): gpu // 2}


def clean(count=120):
    """The clean fixture's frames: walls from 16.000 to 16.899 ms, no two
    alike within 900 frames, so nothing is fixed, stepped, clamped or slow."""
    return [frame(16000 + index * 37 % 900) for index in range(count)]


def value(thousandths):
    whole, part = divmod(abs(thousandths), 1000)
    return f"{'-' if thousandths < 0 else ''}{whole}.{part:03d}"


def write(tmp_path, frames, first=0, segments=True, skip=(), every=None, **header):
    """A run file of `frames`, numbered from `first`, the first half in
    view:1 and the rest in view:2, or with `every`, a new segment each
    `every` frames; the last frame has no wall, as in a real run. Frame
    numbers in `skip` are left out, leaving a hole."""
    fields = {**HEADER, **header}
    fields = {key: given for key, given in fields.items() if given is not None}
    lines = [f"# frameledger {json.dumps(fields)}", "run_id,segment,frame,category,name,depth,value"]
    for index, rows in enumerate(frames):
        if first + index in skip:
            continue
        segment = f"view:{index // (every or (len(frames) + 1) // 2) + 1}" if segments else ""
        for (category, name, depth), thousandths in rows.items():
            if (category, name) == ("frame", "wall") and index == len(frames) - 1:
                continue
            lines.append(f"r,{segment},{first + index},{category},{name},{depth},{value(thousandths)}")
    lines.append(f'# frameledger-close {{"rows_dropped":0,"frames":{len(frames)}}}')
    path = tmp_path / "run.csv"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def codes(capsys, path, strict=True):
    """check's exit code and the warning codes it gives, sorted."""
    code = cli.main(["check", "--json", *(["--strict"] if strict else []), str(path)])
    out = json.loads(capsys.readouterr().out)
    assert out["exit_code"] == code
    return code, sorted({warning["code"] for warning in out["warnings"]})


def set_walls(frames, walls):
    """`walls` is {index: thousandths}; the spans and passes stay."""
    for index, wall in walls.items():
        frames[index][("frame", "wall", 0)] = wall
    return frames


def periodic(frames, every=10, start=5, count=None):
    """A slow frame every `every` frames, each wall a little different, so
    no one value is a ceiling."""
    slow = list(range(start, len(frames), every))[:count]
    return set_walls(frames, {index: 30000 + index for index in slow})


def stepped(frames):
    """Walls of one, two and three 35 Hz tics: 28.571, 57.143, 85.714 ms."""
    return set_walls(frames, {index: (28571, 57143, 57143, 57143, 85714)[index % 5] for index in range(len(frames))})


def cpu_over(frames, index, cpu, wall=None):
    if wall is not None:
        frames[index][("frame", "wall", 0)] = wall
    frames[index][("frame", "cpu_span", 0)] = cpu
    return frames


def passes_over(frames, index, by):
    """Three depth-0 cpu rows summing to `by` thousandths over the span."""
    rows = frames[index]
    span = rows[("frame", "cpu_span", 0)]
    del rows[("cpu", "ui", 0)]
    rows[("cpu", "scene", 0)] = span // 3
    rows[("cpu", "post", 0)] = span // 3
    rows[("cpu", "sky", 0)] = span - 2 * (span // 3) + by
    return frames


def without_gpu(frames):
    return [{key: v for key, v in rows.items() if key[0] != "gpu" and key[1] != "gpu_span"} for rows in frames]


def gpu_flat(frames):
    for rows in frames:
        rows[("frame", "gpu_span", 0)] = 10000
    return frames


# Each code with the one mistake that gives it: (frames, write()'s keyword arguments).
MISTAKES = {
    "wall_fixed": lambda: (set_walls(clean(), dict.fromkeys(range(120), 16667)), {}),
    "wall_stepped": lambda: (stepped(clean()), {}),
    "wall_ceiling": lambda: (set_walls(clean(), dict.fromkeys((30, 70, 100), 40000)), {}),
    "wall_periodic": lambda: (periodic(clean()), {}),
    "span_over_wall": lambda: (cpu_over(clean(), 50, 16000 * 105 // 100, wall=16000), {}),
    "gpu_span_flat": lambda: (gpu_flat(clean()), {}),
    "no_gpu_span": lambda: (without_gpu(clean()), {}),
    "passes_over_span": lambda: (passes_over(clean(), 50, 3), {}),
    "depth_gap": lambda: ([*clean(50), {**frame(16000), ("gpu", "deep", 2): 100}, *clean(69)], {}),
    "no_segments": lambda: (clean(), {"segments": False}),
    "whole_second_start": lambda: (clean(), {"started_utc": "2026-11-17T12:00:00Z"}),
    "no_machine_state": lambda: (clean(), {"load": None}),
    "says_unknown": lambda: (clean(), {"renderer": "Unknown"}),
}


def test_clean_fixture_gives_nothing(capsys, tmp_path):
    """INV-118: segments, a fraction in started_utc, machine state, inputs
    and walls that vary give no warning of any kind under --strict."""
    assert codes(capsys, write(tmp_path, clean())) == (0, [])


@pytest.mark.parametrize("code", sorted(MISTAKES))
def test_each_mistake_gives_its_code_alone(capsys, tmp_path, code):
    """INV-118: the clean fixture with one mistake warns that code and no
    other, exit 1, under --strict; without it, nothing, exit 0."""
    frames, options = MISTAKES[code]()
    path = write(tmp_path, frames, **options)
    assert codes(capsys, path) == (1, [code])
    assert codes(capsys, path, strict=False) == (0, [])


@pytest.mark.parametrize("count, warned", [(9, []), (10, ["wall_fixed"])])
def test_fixed_walls_from_ten(capsys, tmp_path, count, warned):
    """INV-118: 9 equal walls give no wall_fixed; 10 do. The run has one
    frame more, since the last frame has no wall."""
    frames = set_walls(clean(count + 1), dict.fromkeys(range(count + 1), 16667))
    assert codes(capsys, write(tmp_path, frames))[1] == warned


@pytest.mark.parametrize("count, warned", [(9, []), (10, ["gpu_span_flat"])])
def test_flat_gpu_spans_from_ten(capsys, tmp_path, count, warned):
    """INV-118: 9 equal frame/gpu_span rows give no gpu_span_flat; 10 do."""
    assert codes(capsys, write(tmp_path, gpu_flat(clean(count))))[1] == warned


def test_ceiling_needs_three_frames(capsys, tmp_path):
    """INV-118: a ceiling on 2 frames gives none."""
    frames = set_walls(clean(), dict.fromkeys((30, 70), 40000))
    assert codes(capsys, write(tmp_path, frames)) == (0, [])


def test_whole_millisecond_walls_are_no_ceiling(capsys, tmp_path):
    """INV-118: walls that are all whole milliseconds give no wall_ceiling,
    as a clock counting them lands every missed vsync on one value."""
    walls = {index: (16000, 17000)[index % 2] for index in range(120)}
    frames = set_walls(clean(), {**walls, 30: 40000, 70: 40000, 100: 40000})
    assert codes(capsys, write(tmp_path, frames)) == (0, [])


@pytest.mark.parametrize("frames", [
    pytest.param(lambda: periodic(clean(), count=4), id="four slow frames"),
    pytest.param(lambda: periodic(clean(), every=2, start=20, count=10), id="a median gap of 2"),
])
def test_periodic_thresholds(capsys, tmp_path, frames):
    """INV-118: 4 slow frames, or a median gap of 2, give no wall_periodic."""
    assert codes(capsys, write(tmp_path, frames())) == (0, [])


def test_slow_frames_on_cuts_are_not_periodic(capsys, tmp_path):
    """INV-118: a slow frame on every event/cut gives none; a level load is
    slow by nature."""
    frames = periodic(clean())
    for rows in frames[5::10]:
        rows[("event", "cut", 0)] = 1000
    assert codes(capsys, write(tmp_path, frames)) == (0, [])


def test_stepped_walls(capsys, tmp_path):
    """INV-118: walls of 28.571 and 57.143 ms warn wall_stepped; the same
    with one 0.050 ms wall, or with vsync listed in unknown, do not."""
    assert "wall_stepped" in codes(capsys, write(tmp_path, stepped(clean())))[1]
    short = set_walls(stepped(clean()), {7: 50})
    assert "wall_stepped" not in codes(capsys, write(tmp_path, short))[1]
    listed = write(tmp_path, stepped(clean()), unknown=["vsync"])
    assert "wall_stepped" not in codes(capsys, listed)[1]
    # The margin is one thousandth: 57.144 is two off twice 28.571.
    off = set_walls(stepped(clean()), {1: 57144})
    assert "wall_stepped" not in codes(capsys, write(tmp_path, off))[1]


@pytest.mark.parametrize("cpu, warned", [(20200, []), (20201, ["span_over_wall"])])
def test_cpu_span_over_its_wall_by_one_percent(capsys, tmp_path, cpu, warned):
    """INV-118: a cpu_span 1% over its 20 ms wall in a run not pipelined
    gives none; one thousandth more does."""
    assert codes(capsys, write(tmp_path, cpu_over(clean(), 50, cpu, wall=20000)))[1] == warned


@pytest.mark.parametrize("pipelined, unknown", [(True, None), (False, None), (False, ["pipelined"])])
def test_gpu_span_over_its_wall_on_half_the_frames(capsys, tmp_path, pipelined, unknown):
    """INV-118: a GPU-bound run's gpu_span is over its wall on half the
    frames, its total under the walls'; none, however `pipelined` reads."""
    frames = [frame(16000 + index, gpu=16000 + index + (2000 if index % 2 else -4000)) for index in range(120)]
    path = write(tmp_path, frames, pipelined=pipelined, unknown=unknown)
    assert "span_over_wall" not in codes(capsys, path)[1]


@pytest.mark.parametrize("unknown, warned", [(None, True), (["pipelined"], False)])
def test_one_cpu_span_over_its_wall(capsys, tmp_path, unknown, warned):
    """INV-118: in 100 frames whose other cpu_spans are half their walls,
    one 5% over its wall warns when `pipelined` is false, and not when it
    is listed, since then only the total is judged."""
    frames = [frame(16000 + index, cpu=(16000 + index) // 2) for index in range(100)]
    frames = cpu_over(frames, 50, (16050 * 105) // 100)
    path = write(tmp_path, frames, unknown=unknown)
    assert ("span_over_wall" in codes(capsys, path)[1]) is warned


@pytest.mark.parametrize("by, warned", [(2, []), (3, ["passes_over_span"])])
def test_passes_over_their_span(capsys, tmp_path, by, warned):
    """INV-118: three depth-0 rows over their span by 2 thousandths are
    rounding, (3 + 1) / 2; by 3 they warn."""
    assert codes(capsys, write(tmp_path, passes_over(clean(), 50, by)))[1] == warned


def test_frames_not_from_zero(capsys, tmp_path):
    """INV-118: a run numbered from frame 1000 gives no warning."""
    assert codes(capsys, write(tmp_path, clean(), first=1000)) == (0, [])


def test_a_hole_fails_strict(capsys, tmp_path):
    """INV-118: the format's own frame_missing, on a hole with no dropped
    rows, exits 1 under --strict, and 0 without it."""
    path = write(tmp_path, clean(), skip={60})
    assert codes(capsys, path) == (1, ["frame_missing"])
    assert codes(capsys, path, strict=False) == (0, ["frame_missing"])


def slow_at(frames, positions):
    """Slow frames at `positions`, each wall a little different."""
    return set_walls(frames, {index: 30000 + index for index in positions})


def walls_median(frames):
    """The median wall the codes judge by: every frame but the last has one."""
    return stats.median([rows[("frame", "wall", 0)] for rows in frames[:-1]])


@pytest.mark.parametrize("held, count, warned", [(3, 120, True), (3, 302, False), (4, 302, True)])
def test_ceiling_needs_one_percent(capsys, tmp_path, held, count, warned):
    """§ 4.19: the longest wall must be held by 1% or more of the walls:
    3 of 119 warn, 3 of 301 do not, 4 of 301 do."""
    frames = set_walls(clean(count), dict.fromkeys(range(10, 10 + 20 * held, 20), 40000))
    assert ("wall_ceiling" in codes(capsys, write(tmp_path, frames))[1]) is warned


@pytest.mark.parametrize("over, warned", [(0, True), (-1, False)])
def test_ceiling_needs_twice_the_median(capsys, tmp_path, over, warned):
    """§ 4.19: a ceiling at twice the median wall warns; one thousandth
    below it does not."""
    frames = set_walls(clean(), dict.fromkeys((30, 70, 100), 99999))
    ceiling = 2 * walls_median(frames) + over
    frames = set_walls(frames, dict.fromkeys((30, 70, 100), ceiling))
    assert ("wall_ceiling" in codes(capsys, write(tmp_path, frames))[1]) is warned


@pytest.mark.parametrize("gaps, warned", [
    pytest.param((10, 10, 10, 10, 12), True, id="4 of 5 near"),
    pytest.param((10, 10, 10, 11, 11), True, id="within 1"),
    pytest.param((10, 10, 10, 12, 12), False, id="3 of 5 near"),
])
def test_periodic_share_and_window(capsys, tmp_path, gaps, warned):
    """§ 4.19: 5 times the gaps within 1 of the median must be 4 times all
    gaps or more; a gap 2 from the median is not within it."""
    positions = [5]
    for gap in gaps:
        positions.append(positions[-1] + gap)
    path = write(tmp_path, slow_at(clean(), positions))
    assert ("wall_periodic" in codes(capsys, path)[1]) is warned


def test_segments_first_frames_are_not_periodic(capsys, tmp_path):
    """§ 4.19: each segment's first frame is left out of the slow frames: a
    slow first frame in each of six segments gives none."""
    frames = slow_at(clean(), range(0, 120, 20))
    assert codes(capsys, write(tmp_path, frames, every=20)) == (0, [])


@pytest.mark.parametrize("count, warned", [(9, False), (10, True)])
def test_stepped_needs_ten_walls(capsys, tmp_path, count, warned):
    """§ 4.19: 9 stepped walls give no wall_stepped; 10 do."""
    path = write(tmp_path, stepped(clean(count + 1)))
    assert ("wall_stepped" in codes(capsys, path)[1]) is warned


@pytest.mark.parametrize("step, warned", [(999, False), (1000, True)])
def test_stepped_needs_a_one_millisecond_step(capsys, tmp_path, step, warned):
    """§ 4.19: walls of 1, 2 and 3 steps warn when the step is 1 ms, and
    not when it is 0.999 ms, below the floor."""
    frames = [frame(step * (1 + index % 3), cpu=step // 2, gpu=step // 2) for index in range(30)]
    assert ("wall_stepped" in codes(capsys, write(tmp_path, frames))[1]) is warned


@pytest.mark.parametrize("pipelined, unknown", [(True, None), (False, ["pipelined"])])
def test_cpu_span_total_in_a_pipelined_run(capsys, tmp_path, pipelined, unknown):
    """§ 4.19: in a run whose `pipelined` is true or listed, the cpu_span
    total over the wall total by more than 1% warns."""
    frames = [frame(16000 + index, cpu=(16000 + index) * 102 // 100) for index in range(120)]
    path = write(tmp_path, frames, pipelined=pipelined, unknown=unknown)
    assert "span_over_wall" in codes(capsys, path)[1]


@pytest.mark.parametrize("text", ["unknown", "UNKNOWN", "Unknown"])
def test_says_unknown_in_any_case(capsys, tmp_path, text):
    """§ 4.19: `unknown` in any case warns, for a field `unknown` may list
    and one it may not."""
    assert codes(capsys, write(tmp_path, clean(), renderer=text)) == (1, ["says_unknown"])
    assert codes(capsys, write(tmp_path, clean(), engine=text)) == (1, ["says_unknown"])
