"""The shapes of `result` and the sample runs that show them (FLED-0041 § 4.4
and § 4.6).

`SHAPES` lists every row of § 4.4's shapes table as (command, shape name);
a row naming several commands is an entry for each. `SAMPLES` lists command
lines; each names the shape it shows, and tests/test_schemas.py checks that
it shows it and that between them they write every key the schemas name.
`run(sample, tmp_path)`
builds a sample's files, runs `cli.main` in this process with `--json`, and
returns the exit code and what it printed on standard output.

Each run is built here, as the tests build theirs. A run of a sample has
the same rows in every frame of a segment, so a measure's per-run value is
the value written. Nothing needs the network.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import NamedTuple

import cli
import floor_runs
from test_alternate import command_line

FIXTURES = Path(__file__).parent / "fixtures"
FAKE_ENGINE = FIXTURES / "alternate" / "fake_engine.py"

SHAPES = [
    ("check", "judged"), ("check", "expect"), ("check", "file_unread"),
    ("report", "judged"), ("report", "file_unread"),
    ("floor", "judged"), ("floor", "file_unread"),
    ("budget", "judged"), ("budget", "file_unread"),
    ("compare", "plain"), ("compare", "by_scene"), ("compare", "variants"), ("compare", "refused"),
    ("compare", "absent_measure"), ("compare", "file_unread"),
    ("alternate", "plain"), ("alternate", "variants"), ("alternate", "refused"),
    ("alternate", "absent_measure"), ("alternate", "file_unread"), ("alternate", "stopped"),
    ("bisect", "judged"), ("bisect", "skipped_or_stopped"),
    ("survey", "one"),
    ("import", "one"), ("kit", "one"), ("selftest", "one"),
]


class Folder:
    """The folder a sample's files go in."""

    def __init__(self, root: Path):
        self.root = root

    def put(self, name: str, text: str) -> str:
        path = self.root / name
        path.write_text(text, encoding="utf-8")
        return str(path)


class Sample(NamedTuple):
    name: str  # unique, kebab case
    command: str  # a command of SHAPES
    shape: str  # that command's shape name in SHAPES
    shows: str  # the keys or the side of a key the sample is there for
    build: Callable[[Folder], list[str]]  # writes its files; returns the command line before --json
    env: tuple[tuple[str, str], ...] = ()  # environment variables, for the fake engine


# ---------------------------------------------------------------------------
# Building runs

HEADER = {
    "schema": 1, "run_id": "r", "engine": "vestige", "tool": {"name": "bench", "version": "1.0"},
    "build_type": "release", "commit": "abc123", "dirty": False,
    "device": "AMD Radeon RX 9070 XT", "renderer": "AMD Radeon RX 9070 XT (radeonsi)",
    "driver": "Mesa 26.2", "api": "opengl-4.5", "resolution": [1920, 1080], "render_scale": 1.0,
    "vsync": False, "pipelined": True, "display": "headless", "scene": "atrium",
    "inputs": [{"name": "atrium", "hash": "sha256:" + "ab" * 32, "bytes": 48213}],
    "started_utc": "2026-11-20T12:00:00.250Z",
}
VIEW = "view:1"


def rows(opaque: float | None = 5.0, wall: float = 16.0, gpu_span: float | None = 12.0,
         **extra: float | None) -> dict:
    """One frame's rows, {(category, name, depth): value}. `extra` adds rows
    keyed category__name, or category__name__depth; a None drops the row."""
    frame = {("frame", "wall", 0): wall, ("frame", "cpu_span", 0): 8.0, ("frame", "gpu_span", 0): gpu_span,
             ("cpu", "sim", 0): 5.0, ("gpu", "opaque", 0): opaque}
    for key, value in extra.items():
        category, name, *depth = key.split("__")
        frame[(category, name, int(depth[0]) if depth else 0)] = value
    return {key: value for key, value in frame.items() if value is not None}


def run_text(parts: list[tuple[str, dict, int]], close: bool = True, dropped: int = 0, static: dict | None = None,
             **header) -> str:
    """A run of `parts`, each (segment, rows, frames), then a close line.
    The last frame has no frame/wall, as in a real run."""
    fields = {**HEADER, **header}
    lines = [f"# frameledger {json.dumps(fields)}"]
    if static is not None:
        lines.append(f"# frameledger-static {json.dumps(static)}")
    lines.append("run_id,segment,frame,category,name,depth,value")
    total = sum(count for _, _, count in parts)
    number = 0
    for segment, frame_rows, count in parts:
        for _ in range(count):
            for (category, name, depth), value in frame_rows.items():
                if (category, name) == ("frame", "wall") and number == total - 1:
                    continue
                lines.append(f"{fields['run_id']},{segment},{number},{category},{name},{depth},{value:.3f}")
            number += 1
    if close:
        lines.append(f'# frameledger-close {{"rows_dropped":{dropped},"frames":{total}}}')
    return "\n".join(lines) + "\n"


def steady(opaque: float | None = 5.0, frames: int = 120, segment: str = VIEW, wall: float = 16.0,
           extra: dict | None = None, **options) -> str:
    """A run whose every frame has the same rows; `options` go to run_text."""
    return run_text([(segment, rows(opaque, wall, **(extra or {})), frames)], **options)


class Taken(NamedTuple):
    """One run to write: its text's arguments, and where it starts."""
    opaque: float | None = 5.0
    options: dict = {}  # run_text's and steady's keyword arguments


def runs(folder: Folder, side: str, values: list, start: int = 0, **options) -> list[str]:
    """One run file a value of `values`, named side-1.csv, ..., started
    `start` minutes past the hour, two apart, so a side starting at 0 and
    one at 1 are interleaved. A value is the gpu/opaque median, or a Taken."""
    paths = []
    for i, value in enumerate(values, 1):
        taken = value if isinstance(value, Taken) else Taken(value)
        merged = {**options, **taken.options}
        started = merged.pop("started_utc", f"2026-11-20T12:{start + 2 * (i - 1):02d}:00.250Z")
        text = steady(taken.opaque, run_id=f"{side}{i}", started_utc=started, **merged)
        paths.append(folder.put(f"{side}-{i}.csv", text))
    return paths


SAME, SLOWER = [10.0, 10.01, 10.02], [11.0, 11.01, 11.02]


def compare_args(old: list[str], new: list[str], *flags: str) -> list[str]:
    return ["compare", "--old", *old, "--new", *new, *flags]


def variant_args(base: list[str], variants: dict[str, list[str]], *flags: str) -> list[str]:
    args = ["compare", "--base", *base]
    for name, paths in variants.items():
        args += ["--variant", name, *paths]
    return [*args, *flags]


def baseline_file(folder: Folder, paths: list[str], name: str = "baseline.txt") -> str:
    return folder.put(name, "\n".join(['# frameledger-baseline {"schema":1}', *paths]) + "\n")


# ---------------------------------------------------------------------------
# check

def _check_fixture(*names: str) -> Callable[[Folder], list[str]]:
    return lambda f: ["check", *(str(FIXTURES / name) for name in names)]


def _check_strict(f: Folder) -> list[str]:
    return ["check", "--strict", str(FIXTURES / "passing-run.csv")]


def varied_run() -> str:
    """A run with nothing for --strict to warn of: walls and spans that vary, a start with a fraction of a
    second, and some machine state."""
    parts = [(VIEW, rows(4.0, wall=14.0 + (i * 37 % 11) * 0.173 + i * 0.001, gpu_span=9.0 + (i % 5) * 0.31), 1)
             for i in range(120)]
    return run_text(parts, load={"start": 0.1, "end": 0.1})


def _check_strict_clean(f: Folder) -> list[str]:
    return ["check", "--strict", f.put("clean.csv", varied_run())]


def _expected_pair(f: Folder, **changed) -> tuple[str, str]:
    expected = f.put("expected.csv", steady(static={"gpu": {"vram": "1024"}}))
    found = f.put("found.csv", steady(**changed))
    return expected, found


def _check_expect_match(f: Folder) -> list[str]:
    expected, found = _expected_pair(f, static={"gpu": {"vram": "1024"}})
    return ["check", found, "--expect", expected]


def _check_expect_differs(f: Folder) -> list[str]:
    expected, found = _expected_pair(f, opaque=6.0, resolution=[1280, 720], static={"gpu": {"vram": "2048"}})
    return ["check", found, "--expect", expected]


def _check_expect_many(f: Folder) -> list[str]:
    """More differences than the 20 the result lists."""
    expected = f.put("expected.csv", steady(frames=30))
    found = f.put("found.csv", steady(frames=30, opaque=6.0, wall=17.0))
    return ["check", found, "--expect", expected]


def _check_expect_broken(f: Folder) -> list[str]:
    return ["check", str(FIXTURES / "comma-decimal.csv"), "--expect", str(FIXTURES / "passing-run.csv")]


def _check_unread(f: Folder) -> list[str]:
    return ["check", str(FIXTURES / "passing-run.csv"), str(f.root / "missing.csv")]


def _check_schema_newer(f: Folder) -> list[str]:
    return ["check", str(FIXTURES / "schema-99.csv")]


def _check_strict_uniform(f: Folder) -> list[str]:
    return ["check", "--strict", f.put("uniform.csv", steady())]


def _many_notices_text() -> str:
    """A run with the warnings about the build, the machine and the rows."""
    odd = {**rows(5.0), ("frame", "odd", 0): 1.0}
    cut = {**rows(5.0), ("event", "cut", 0): 1.0}
    return run_text([(VIEW, odd, 30), (VIEW, cut, 1), (VIEW, rows(5.0), 29)], build_type="Debug",
                    renderer="llvmpipe", load={"start": 0.9, "end": 0.9}, gpu_busy_pct={"start": 50, "end": 50},
                    power="battery", throttled=True, settling_frames=10, settled_frames=2, sanitizers=["asan"])


def _check_many_notices(f: Folder) -> list[str]:
    return ["check", f.put("notices.csv", _many_notices_text())]


def _check_odd_run(f: Folder) -> list[str]:
    """Notices that carry no line, and unknown facts."""
    path = f.put("odd.csv", steady(unknown=["commit"], commit="unknown", inputs=[], extra_field=1,
                                   close=False))
    return ["check", path]


CHECKS = [
    Sample("check-pass", "check", "judged", "files with no breaches; verdict pass",
           _check_fixture("passing-run.csv")),
    Sample("check-breaches", "check", "judged", "breaches with line, rule and message; verdict fail",
           _check_fixture("no-header.csv", "comma-decimal.csv", "passing-run.csv")),
    Sample("check-warnings", "check", "judged", "a warning from a notice, which does not fail without --strict",
           _check_fixture("negative-gpu.csv")),
    Sample("check-odd-run", "check", "judged", "notices with no line: unknown_field, facts_unknown, inputs_empty",
           _check_odd_run),
    Sample("check-strict-fails", "check", "judged", "--strict turns warnings into a fail", _check_strict),
    Sample("check-strict-uniform", "check", "judged", "the --strict warnings on fixed walls and spans",
           _check_strict_uniform),
    Sample("check-many-notices", "check", "judged", "build, machine and row warnings", _check_many_notices),
    Sample("check-strict-clean", "check", "judged", "--strict with nothing to warn of", _check_strict_clean),
    Sample("check-expect-match", "check", "expect", "expect.matches true, differences empty", _check_expect_match),
    Sample("check-expect-differs", "check", "expect", "expect.matches false; header, row and static differences",
           _check_expect_differs),
    Sample("check-expect-many", "check", "expect", "differences cut at the 20 listed", _check_expect_many),
    Sample("check-expect-broken", "check", "expect", "a file that breaks the format never matches",
           _check_expect_broken),
    Sample("check-file-unread", "check", "file_unread", "verdict error; files leaves the unread file out",
           _check_unread),
    Sample("check-schema-newer", "check", "file_unread", "a newer schema is an unread file", _check_schema_newer),
]


# ---------------------------------------------------------------------------
# report

def _report_fixture(name: str) -> Callable[[Folder], list[str]]:
    return lambda f: ["report", str(FIXTURES / name)]


def _report_rich(f: Folder) -> list[str]:
    """Two segment kinds, a nested pass, mem, static and a frame with no GPU result."""
    view = rows(5.0, wall=16.0, gpu__shadows=2.0, gpu__blur__1=0.5, mem__vram=100.0)
    spot = rows(6.0, wall=20.0)
    no_gpu = {k: v for k, v in spot.items() if k[:2] != ("frame", "gpu_span")}
    text = run_text([(VIEW, view, 60), ("spot:1", spot, 30), ("", no_gpu, 10)], static={"gpu": {"vram": "1024"}})
    return ["report", f.put("rich.csv", text)]


def _report_not_pipelined(f: Folder) -> list[str]:
    return ["report", f.put("serial.csv", steady(pipelined=False))]


def _report_no_gpu_span(f: Folder) -> list[str]:
    frame = {k: v for k, v in rows().items() if k[:2] != ("frame", "gpu_span") and k[0] != "gpu"}
    return ["report", f.put("cpu-only.csv", run_text([(VIEW, frame, 120)]))]


def _generated_run(**header) -> str:
    """Every fifth frame generated: rows of event/generated, which a command leaves out by default."""
    plain, made = rows(5.0, wall=8.0), {**rows(5.0, wall=8.0), ("event", "generated", 0): 1.0}
    parts = [(VIEW, made if n % 5 == 4 else plain, 1) for n in range(120)]
    return run_text(parts, **header)


def _report_generated(f: Folder, *flags: str) -> list[str]:
    return ["report", f.put("generated.csv", _generated_run()), *flags]


def _report_imported(f: Folder) -> list[str]:
    """A run `import presentmon` wrote: unknown facts, no passes."""
    return ["report", _import_to(f)]


def _report_many_warnings(f: Folder) -> list[str]:
    return ["report", f.put("notices.csv", _many_notices_text())]


def _report_unread(f: Folder) -> list[str]:
    return ["report", str(f.root / "missing.csv")]


def _report_breach(f: Folder) -> list[str]:
    return ["report", str(FIXTURES / "no-header.csv")]


REPORTS = [
    Sample("report-fixture", "report", "judged", "a plain run; static null, no mem",
           _report_fixture("passing-run.csv")),
    Sample("report-rich", "report", "judged", "segment kinds, depth 1, mem, static, missing_gpu_frames",
           _report_rich),
    Sample("report-not-pipelined", "report", "judged", "bound_by.applies false", _report_not_pipelined),
    Sample("report-no-gpu-span", "report", "judged", "bound_by with cpu and gpu null, applies true",
           _report_no_gpu_span),
    Sample("report-generated", "report", "judged", "generated_frames above 0, all_frames false", _report_generated),
    Sample("report-generated-all", "report", "judged", "all_frames true",
           lambda f: _report_generated(f, "--all-frames")),
    Sample("report-imported", "report", "judged", "an imported run: pipelined unknown, no passes", _report_imported),
    Sample("report-negative", "report", "judged", "a warning on a run with a negative value",
           _report_fixture("negative-gpu.csv")),
    Sample("report-many-warnings", "report", "judged", "the warnings on the build, the machine and few frames",
           _report_many_warnings),
    Sample("report-file-unread", "report", "file_unread", "verdict error, result {}", _report_unread),
    Sample("report-breach", "report", "file_unread", "a file that breaks the format is unread", _report_breach),
]


# ---------------------------------------------------------------------------
# floor

def _floor_fixture(name: str, *flags: str) -> Callable[[Folder], list[str]]:
    return lambda f: ["floor", str(FIXTURES / name), "--fps", "60", *flags]


def _floor_text(text: str, *flags: str) -> Callable[[Folder], list[str]]:
    return lambda f: ["floor", f.put("run.csv", text), "--fps", "60", *flags]


def _floor_unread(f: Folder) -> list[str]:
    return ["floor", str(f.root / "missing.csv"), "--fps", "60"]


FLOOR_WARM = floor_runs.WARMUP
FLOOR_EMPTY_WINDOW = floor_runs.run_text(FLOOR_WARM + [16.0] * 59 + [3000.0] + [16.0] * 130)
FLOOR_NO_CLOSE = floor_runs.run_text([16.0] * 400).rsplit("# frameledger-close", 1)[0]
FLOOR_DROPPED = floor_runs.run_text([16.0] * 400).replace('"rows_dropped":0', '"rows_dropped":3')

FLOORS = [
    Sample("floor-pass", "floor", "judged", "pass; windows with a mean, nothing slow",
           _floor_fixture("passing-run.csv")),
    Sample("floor-hitch", "floor", "judged", "fail; a window below the rate and slow frames",
           _floor_fixture("one-hitch.csv")),
    Sample("floor-short-views", "floor", "judged", "windows_skipped above 0; inconclusive",
           _floor_fixture("short-views.csv")),
    Sample("floor-cut", "floor", "judged", "a cut skips a window", _floor_fixture("cut-mid-second.csv")),
    Sample("floor-spike", "floor", "judged", "fail on a single frame alone", _floor_fixture("fast-with-one-spike.csv")),
    Sample("floor-no-windows", "floor", "judged", "--no-windows: windows empty", _floor_fixture(
        "passing-run.csv", "--no-windows")),
    Sample("floor-no-frames", "floor", "judged", "--no-frames: slow_frames empty", _floor_fixture(
        "one-hitch.csv", "--no-frames")),
    Sample("floor-allowed", "floor", "judged", "--allow-frames and --budget-ms", _floor_fixture(
        "fast-with-one-spike.csv", "--allow-frames", "1", "--budget-ms", "40")),
    Sample("floor-empty-window", "floor", "judged", "a window no frame ends in: mean_ms null",
           _floor_text(FLOOR_EMPTY_WINDOW)),
    Sample("floor-no-close", "floor", "judged", "rows_dropped null, finished false; inconclusive",
           _floor_text(FLOOR_NO_CLOSE)),
    Sample("floor-dropped", "floor", "judged", "rows_dropped above 0; inconclusive", _floor_text(FLOOR_DROPPED)),
    Sample("floor-generated", "floor", "judged", "generated_frames above 0",
           lambda f: ["floor", f.put("generated.csv", _generated_run()), "--fps", "60"]),
    Sample("floor-generated-all", "floor", "judged", "all_frames true",
           lambda f: ["floor", f.put("generated.csv", _generated_run()), "--fps", "60", "--all-frames"]),
    Sample("floor-file-unread", "floor", "file_unread", "verdict error, result {}", _floor_unread),
    Sample("floor-breach", "floor", "file_unread", "a file that breaks the format is unread",
           lambda f: ["floor", str(FIXTURES / "no-header.csv"), "--fps", "60"]),
]


# ---------------------------------------------------------------------------
# budget

COLUMNS = "category,name,kind,depth,statistic,limit_ms"


def budget_text(*lines: str, match: dict | None = None) -> str:
    header = json.dumps({"schema": 1, **({"match": match} if match else {})}, separators=(",", ":"))
    return "\n".join([f"# frameledger-budget {header}", COLUMNS, *lines]) + "\n"


def _budget(run: str, budgets: str, *flags: str) -> Callable[[Folder], list[str]]:
    def build(f: Folder) -> list[str]:
        return ["budget", f.put("run.csv", run), "--budgets", f.put("budgets.csv", budgets), *flags]
    return build


BUDGET_RUN = run_text([(VIEW, rows(5.0, gpu__blur__1=0.5), 60), ("spot:1", rows(6.0, wall=20.0), 30),
                       ("", rows(4.0), 30)])
NO_GPU_RUN = run_text([(VIEW, rows(5.0), 60), (VIEW, {k: v for k, v in rows(5.0).items()
                                                      if k[:2] != ("frame", "gpu_span")}, 30)])
BUDGET_HOLDS = budget_text("gpu,opaque,view,,median,10", "frame,cpu_span,*,,p99,9", "gpu,opaque,,,median,6",
                           match={"resolution": [1920, 1080]})
BUDGET_OVER = budget_text("gpu,opaque,*,,median,4.5", "gpu,blur,view,1,p99,1", "frame,gpu_span,spot,,median,11")
BUDGET_UNMATCHED = budget_text("gpu,opaque,view,,median,10", "gpu,none,*,,p99,1", "gpu,opaque,view,3,median,1",
                               "gpu,opaque,nokind,,median,1", "gpu,opaque,,,median,6", "gpu,absent,,,median,1")

BUDGETS = [
    Sample("budget-pass", "budget", "judged", "pass; a frame span has depth null; match in the budget file",
           _budget(BUDGET_RUN, BUDGET_HOLDS)),
    Sample("budget-fail", "budget", "judged", "fail; over true, over_ms above 0; a pass at depth 1",
           _budget(BUDGET_RUN, BUDGET_OVER)),
    Sample("budget-unmatched", "budget", "judged", "inconclusive; unmatched with depth and kind values",
           _budget(BUDGET_RUN, BUDGET_UNMATCHED)),
    Sample("budget-warmup", "budget", "judged", "--warmup-s above 0", _budget(
        BUDGET_RUN, BUDGET_HOLDS, "--warmup-s", "0.5")),
    Sample("budget-few-frames", "budget", "judged", "a budget_few_frames warning, gpu_missing warning",
           _budget(NO_GPU_RUN, budget_text("gpu,opaque,*,,p99,10"))),
    Sample("budget-generated", "budget", "judged", "generated_frames above 0",
           _budget(_generated_run(), budget_text("frame,cpu_span,*,,median,10"))),
    Sample("budget-generated-all", "budget", "judged", "all_frames true", _budget(
        _generated_run(), budget_text("frame,cpu_span,*,,median,10"), "--all-frames")),
    Sample("budget-no-close", "budget", "judged", "finished false, rows_dropped null; inconclusive",
           _budget(steady(close=False), budget_text("gpu,opaque,*,,median,10"))),
    Sample("budget-dropped", "budget", "judged", "rows_dropped above 0",
           _budget(steady(dropped=2), budget_text("gpu,opaque,*,,median,10"))),
    Sample("budget-file-unread", "budget", "file_unread", "the run file is missing",
           lambda f: ["budget", str(f.root / "missing.csv"), "--budgets", f.put("b.csv", BUDGET_HOLDS)]),
    Sample("budget-mismatch", "budget", "file_unread", "the run lacks the settings the budgets were set for",
           _budget(BUDGET_RUN, budget_text("gpu,opaque,*,,median,10", match={"resolution": [640, 480]}))),
    Sample("budget-bad-file", "budget", "file_unread", "the budget file is wrong",
           _budget(BUDGET_RUN, "# frameledger-budget {\"schema\":1}\nnot,the,columns\n")),
]


# ---------------------------------------------------------------------------
# compare

def _compare_mixed(f: Folder) -> list[str]:
    """slower, faster, noisy, unchanged, larger and smaller; an unmatched pass."""
    def one(i: int, side: str, shadows: float, vram: float, wall: float, tex: float) -> Taken:
        extra = {"gpu__shadows": shadows, "mem__vram": vram, "mem__tex": tex,
                 "cpu__idle": 0.0 if side == "old" else 0.3}  # an old centre of zero: change_pct null
        if side == "old" and i == 0:
            extra["cpu__only"] = 2.0
        return Taken(10.0 if side == "old" else 12.0, {"wall": wall, "extra": extra})
    old = [one(i, "old", 4.0 + i / 100, 100.0 + i / 10, w, 50.0 + i) for i, w in enumerate((15.0, 16.0, 17.0))]
    new = [one(i, "new", 3.0 + i / 100, 110.0 + i / 10, w, 40.0 + i) for i, w in enumerate((15.5, 16.5, 16.0))]
    return compare_args(runs(f, "old", old), runs(f, "new", new, 1))


def _compare_pass(f: Folder) -> list[str]:
    return compare_args(runs(f, "old", SAME), runs(f, "new", SAME, 1))


def _compare_noisy(f: Folder) -> list[str]:
    """frame/wall moves within the runs' spread: inconclusive."""
    old = [Taken(10.0, {"wall": w}) for w in (15.0, 15.1, 30.0)]
    new = [Taken(10.0, {"wall": w}) for w in (15.5, 16.5, 16.0)]
    return compare_args(runs(f, "old", old), runs(f, "new", new, 1))


def _compare_measure(f: Folder) -> list[str]:
    return [*compare_args(runs(f, "old", SAME), runs(f, "new", SLOWER, 1)), "--measure", "gpu/opaque"]


def _compare_p99(f: Folder, frames: int, *names: str) -> list[str]:
    old = runs(f, "old", [Taken(v, {"frames": frames}) for v in SAME])
    new = runs(f, "new", [Taken(v, {"frames": frames}) for v in SAME], 1)
    flags = [flag for name in names for flag in ("--measure", name)]
    return [*compare_args(old, new), *flags]


def _compare_baseline(f: Folder) -> list[str]:
    older = runs(f, "old", SAME, 0, driver="Mesa 26.1", os="Linux 6.1", started_utc="2026-09-01T12:00:00.250Z")
    new = runs(f, "new", SLOWER, 1, driver="Mesa 26.2", os="Linux 6.2")
    return ["compare", "--baseline", baseline_file(f, older), "--new", *new]


def _compare_load(f: Folder) -> list[str]:
    old = runs(f, "old", SAME)
    new = runs(f, "new", SAME, 1)
    loaded = f.put("new-2.csv", steady(run_id="new2", started_utc="2026-11-20T12:03:00.250Z",
                                       load={"start": 0.1, "end": 0.2, "peak": 0.4},
                                       gpu_busy_pct={"start": 3, "end": 3, "peak": 30}))
    return compare_args(old, [new[0], loaded, new[2]])


def _compare_static(f: Folder) -> list[str]:
    old = [f.put(f"old-{i}.csv", steady(run_id=f"o{i}", started_utc=f"2026-11-20T12:0{2 * i}:00Z",
                                        static={"gpu": {"vram": "1024"}, "cpu": {"cores": "8"}}))
           for i in (0, 1, 2)]
    new = [f.put(f"new-{i}.csv", steady(run_id=f"n{i}", started_utc=f"2026-11-20T12:0{2 * i + 1}:00Z",
                                        static={"gpu": {"vram": "2048"}} if i else {"cpu": {"cores": "8"}}))
           for i in (0, 1, 2)]
    return compare_args(old, new)


def _compare_override(f: Folder) -> list[str]:
    old = runs(f, "old", SAME)
    new = runs(f, "new", SAME, 1, resolution=[1280, 720])
    return [*compare_args(old, new), "--override", "resolution=lower for the test",
            "--override", "tier=never differs"]


def _compare_refused(f: Folder) -> list[str]:
    old = runs(f, "old", SAME)
    new = runs(f, "new", SAME, 1, resolution=[1280, 720], vsync=True)
    return compare_args(old, new)


def _compare_refused_override(f: Folder) -> list[str]:
    """A refusal with an override given for another field: overrides non-empty."""
    old = runs(f, "old", SAME)
    new = runs(f, "new", SAME, 1, resolution=[1280, 720], vsync=True)
    return [*compare_args(old, new), "--override", "vsync=known"]


def _compare_absent(f: Folder) -> list[str]:
    return [*compare_args(runs(f, "old", SAME), runs(f, "new", SAME, 1)), "--measure", "gpu/nothing"]


def _compare_unread(f: Folder) -> list[str]:
    return compare_args(runs(f, "old", SAME), [*runs(f, "new", SAME, 1)[:2], str(f.root / "missing.csv")])


def _compare_breach(f: Folder) -> list[str]:
    return compare_args(runs(f, "old", SAME), [*runs(f, "new", SAME, 1)[:2], str(FIXTURES / "no-header.csv")])


def _compare_incomplete(f: Folder) -> list[str]:
    old = runs(f, "old", [Taken(10.0, {"close": False}), Taken(10.0), Taken(10.0, {"dropped": 4})])
    return compare_args(old, runs(f, "new", SAME, 1))


def _compare_generated(f: Folder, *flags: str) -> list[str]:
    sides = {side: [f.put(f"{side}-{i}.csv", _generated_run(run_id=f"{side}{i}",
                                                           started_utc=f"2026-11-20T12:{start + 2 * i:02d}:00Z"))
                    for i in range(3)] for side, start in (("old", 0), ("new", 1))}
    return [*compare_args(sides["old"], sides["new"]), *flags]


def _compare_builds(f: Folder) -> list[str]:
    """Runs of two builds: commit and dirty differ; one lists its commit as unknown."""
    old = runs(f, "old", [Taken(10.0, {"commit": "aaa"}), Taken(10.0, {"commit": "bbb", "dirty": True}),
                          Taken(10.0, {"unknown": ["commit", "dirty"], "commit": "unknown", "dirty": True})])
    return compare_args(old, runs(f, "new", SAME, 1))


def _compare_unsegmented(f: Folder) -> list[str]:
    """Frames with no segment: segment_kind null; an unmatched pass at depth 1."""
    old = [Taken(v, {"segment": "", "extra": {"cpu__deep__1": 1.0} if i == 0 else {}}) for i, v in enumerate(SAME)]
    new = [Taken(v, {"segment": ""}) for v in SLOWER]
    return compare_args(runs(f, "old", old), runs(f, "new", new, 1))


def _compare_not_interleaved(f: Folder) -> list[str]:
    old = runs(f, "old", SAME, 0)
    new = runs(f, "new", SAME, 20)
    return compare_args(old, new)


def _compare_machine_state(f: Folder) -> list[str]:
    """The difference warnings on load, clocks, temperatures and settings."""
    def state(clock: float, temp: float, governor: str, load: float) -> dict:
        return {"cpu_governor": governor, "turbo": True, "power": "mains", "sanitizers": [],
                "cpu_clock_mhz": {"start": clock, "end": clock}, "gpu_clock_mhz": {"start": clock, "end": clock},
                "cpu_temp_c": {"start": temp, "end": temp, "peak": temp}, "throttled": True,
                "gpu_temp_c": {"start": temp, "end": temp}, "load": {"start": load, "end": load},
                "gpu_busy_pct": {"start": load * 100, "end": 1}}
    old = runs(f, "old", SAME, **state(3000, 50, "performance", 0.05))
    new = runs(f, "new", SAME, 1, **{**state(2000, 80, "powersave", 0.4), "turbo": False, "power": "battery",
                                     "sanitizers": ["asan"]})
    return compare_args(old, new)


def _compare_pass_pass(f: Folder) -> list[str]:
    return [*_compare_pass(f), "--min-ms", "0.5", "--min-pct", "10", "--max-load", "0.5", "--max-gpu-busy", "50"]


COMPARES = [
    Sample("compare-mixed", "compare", "plain",
           "slower, faster, noisy, unchanged, larger, smaller measures; unmatched with present_in", _compare_mixed),
    Sample("compare-pass", "compare", "plain", "verdict pass, change zero", _compare_pass),
    Sample("compare-flags", "compare", "plain", "floors and load limits other than the defaults",
           _compare_pass_pass),
    Sample("compare-noisy", "compare", "plain", "verdict inconclusive on a noisy frame/wall; outlier_run",
           _compare_noisy),
    Sample("compare-measure", "compare", "plain", "--measure: named_measures non-empty, the unmatched list",
           _compare_measure),
    Sample("compare-measure-p99-few", "compare", "plain", "--measure NAME:p99 on short runs: too_few, suffixed true",
           lambda f: _compare_p99(f, 120, "frame/wall:p99")),
    Sample("compare-measure-p99", "compare", "plain", "--measure NAME:p99 judged, suffixed true, 1000 frames a run",
           lambda f: _compare_p99(f, 1001, "frame/wall:p99", "gpu/opaque:p99", "frame/cpu_span")),
    Sample("compare-baseline", "compare", "plain", "baseline not null; baseline_* warnings", _compare_baseline),
    Sample("compare-under-load", "compare", "plain", "under_load non-empty: load.peak and gpu_busy_pct.peak",
           _compare_load),
    Sample("compare-static-diff", "compare", "plain", "static_diff non-empty; a value absent from a run is null",
           _compare_static),
    Sample("compare-override", "compare", "plain", "overrides non-empty; an override_unused warning",
           _compare_override),
    Sample("compare-incomplete", "compare", "plain", "finished false, rows_dropped null and above 0",
           _compare_incomplete),
    Sample("compare-generated", "compare", "plain", "generated_frames above 0, all_frames false",
           lambda f: _compare_generated(f)),
    Sample("compare-generated-all", "compare", "plain", "all_frames true",
           lambda f: _compare_generated(f, "--all-frames")),
    Sample("compare-builds", "compare", "plain", "commit and dirty differ; commit null when unknown; mixed_build",
           _compare_builds),
    Sample("compare-unsegmented", "compare", "plain", "segment_kind null; an unmatched pass at depth 1",
           _compare_unsegmented),
    Sample("compare-not-interleaved", "compare", "plain", "a not_interleaved warning", _compare_not_interleaved),
    Sample("compare-machine-state", "compare", "plain", "the *_differs warnings", _compare_machine_state),
    Sample("compare-refused", "compare", "refused", "refused with runs, refused and all_frames", _compare_refused),
    Sample("compare-refused-override", "compare", "refused", "refused with an override named",
           _compare_refused_override),
    Sample("compare-absent", "compare", "absent_measure", "named_measures with runs", _compare_absent),
    Sample("compare-file-unread", "compare", "file_unread", "result {}", _compare_unread),
    Sample("compare-file-breach", "compare", "file_unread", "result {} for a file that breaks the format",
           _compare_breach),
]


# --by-scene

def scene_runs(folder: Folder, scene: str, side: str, opaques: list, start: int, segments=None,
               **header) -> list[str]:
    """Runs of `scene`, one a value of `opaques`, started from minute `start` of the hour."""
    paths = []
    for i, opaque in enumerate(opaques, 1):
        parts = segments(opaque) if segments else [(VIEW, rows(opaque), 120)]
        text = run_text(parts, run_id=f"{scene}{side}{i}", scene=scene,
                        started_utc=f"2026-11-20T12:{start + 2 * (i - 1):02d}:00.250Z", **header)
        paths.append(folder.put(f"{scene}-{side}-{i}.csv", text))
    return paths


def _two_views(opaque: float) -> list:
    return [("view:1", rows(opaque), 60), ("view:2", rows(opaque * 2), 60)]


def _scenes_mixed(f: Folder) -> list[str]:
    """fail with segment and rank, pass, inconclusive, unjudged, refused; an unread file."""
    old = [*scene_runs(f, "a", "old", SAME, 0, _two_views), *scene_runs(f, "b", "old", SAME, 6),
           *scene_runs(f, "c", "old", SAME, 12, load={"start": 0.1, "end": 0.1, "peak": 0.5}),
           *scene_runs(f, "d", "old", SAME, 18), *scene_runs(f, "e", "old", SAME, 24),
           str(f.root / "missing.csv")]
    new = [*scene_runs(f, "a", "new", [10.0, 10.01, 14.0], 1, _two_views), *scene_runs(f, "b", "new", SAME, 7),
           *scene_runs(f, "c", "new", SAME, 13), *scene_runs(f, "d", "new", SAME[:2], 19),
           *scene_runs(f, "e", "new", SAME, 25, resolution=[1280, 720])]
    return ["compare", "--by-scene", "--old", *old, "--new", *new]


def _scenes_second_fail(f: Folder) -> list[str]:
    """Two failing scenes, ranked, one by a larger mem measure."""
    mem = lambda opaque: [(VIEW, rows(10.0, mem__vram=opaque), 120)]  # noqa: E731
    old = [*scene_runs(f, "a", "old", SAME, 0), *scene_runs(f, "m", "old", [100.0, 100.1, 100.2], 6, mem)]
    new = [*scene_runs(f, "a", "new", SLOWER, 1), *scene_runs(f, "m", "new", [150.0, 150.1, 150.2], 7, mem)]
    return ["compare", "--by-scene", "--old", *old, "--new", *new]


def _scenes_pass(f: Folder) -> list[str]:
    return ["compare", "--by-scene", "--old", *scene_runs(f, "a", "old", SAME, 0), "--new",
            *scene_runs(f, "a", "new", SAME, 1)]


def _scenes_none_judged(f: Folder) -> list[str]:
    """No scene judged: verdict error, with the full scenes shape."""
    return ["compare", "--by-scene", "--old", *scene_runs(f, "a", "old", SAME, 0), "--new",
            *scene_runs(f, "a", "new", SAME[:2], 1), str(f.root / "missing.csv")]


def _scenes_absent(f: Folder) -> list[str]:
    return [*_scenes_pass(f), "--measure", "gpu/nothing"]


def _scenes_measure(f: Folder) -> list[str]:
    """--measure: a scene whose runs lack the name is unjudged, lacking it."""
    lacking = lambda opaque: [(VIEW, rows(None), 120)]  # noqa: E731
    old = [*scene_runs(f, "a", "old", SAME, 0), *scene_runs(f, "b", "old", SAME, 6, lacking)]
    new = [*scene_runs(f, "a", "new", SAME, 1), *scene_runs(f, "b", "new", SAME, 7, lacking)]
    return ["compare", "--by-scene", "--old", *old, "--new", *new, "--measure", "gpu/opaque"]


def _scenes_baseline(f: Folder) -> list[str]:
    older = scene_runs(f, "a", "old", SAME, 0)
    return ["compare", "--by-scene", "--baseline", baseline_file(f, older), "--new",
            *scene_runs(f, "a", "new", SLOWER, 1), "--override", "tier=unused"]


def _scenes_unknown(f: Folder) -> list[str]:
    """A run whose header does not know its scene, and one with an empty scene."""
    old = [*scene_runs(f, "a", "old", SAME, 0), f.put("lost.csv", steady(unknown=["scene"], scene="unknown")),
           f.put("empty.csv", steady(scene=""))]
    return ["compare", "--by-scene", "--old", *old, "--new", *scene_runs(f, "a", "new", SAME, 1)]


SCENES = [
    Sample("scenes-mixed", "compare", "by_scene",
           "fail, pass, inconclusive, unjudged and refused scenes; rank, segment, measure; unread entries",
           _scenes_mixed),
    Sample("scenes-two-fail", "compare", "by_scene", "two ranked scenes, one by a larger mem measure",
           _scenes_second_fail),
    Sample("scenes-pass", "compare", "by_scene", "verdict pass; rank, measure, segment null", _scenes_pass),
    Sample("scenes-none-judged", "compare", "by_scene", "verdict error with scenes and unread", _scenes_none_judged),
    Sample("scenes-measure", "compare", "by_scene", "--measure: a scene lacking the named measure",
           _scenes_measure),
    Sample("scenes-baseline", "compare", "by_scene", "baseline not null; an unused override", _scenes_baseline),
    Sample("scenes-unknown-scene", "compare", "by_scene", "unread files: scene unknown or empty", _scenes_unknown),
    Sample("scenes-absent", "compare", "absent_measure", "named_measures alone, for --by-scene", _scenes_absent),
]


# --base --variant

def var_rows(x: float | None = 5.0, wall: float = 16.0) -> dict:
    """Every measure fixed but gpu/x and the wall; with x None, no gpu/x."""
    frame = rows(None, wall)
    return frame if x is None else {**frame, ("gpu", "x", 0): x}


def var_runs(folder: Folder, name: str, xs: list, start: int, **header) -> list[str]:
    paths = []
    for i, x in enumerate(xs, 1):
        text = run_text([(VIEW, var_rows(x), 120)], run_id=f"{name}{i}",
                        started_utc=f"2026-11-20T12:{start + 2 * (i - 1):02d}:00.250Z", **header)
        paths.append(folder.put(f"{name}-{i}.csv", text))
    return paths


def _variants_mixed(f: Folder) -> list[str]:
    """pass, fail, refused and inconclusive variants, ranked."""
    base = var_runs(f, "base", SAME, 0)
    loaded = var_runs(f, "d", SAME, 5, load={"start": 0.1, "end": 0.1, "peak": 0.6})
    return variant_args(base, {"a": var_runs(f, "a", [4.0, 4.01, 4.02], 1), "b": var_runs(f, "b", SLOWER, 3),
                               "c": var_runs(f, "c", SAME, 7, resolution=[1280, 720]), "d": loaded})


def _variants_pass(f: Folder) -> list[str]:
    return variant_args(var_runs(f, "base", SAME, 0), {"a": var_runs(f, "a", SAME, 1)}, "--measure", "gpu/x:median")


def _variants_none_judged(f: Folder) -> list[str]:
    """Every variant refused: verdict error, with the full variants shape."""
    return variant_args(var_runs(f, "base", SAME, 0), {"a": var_runs(f, "a", SAME, 1, resolution=[1, 1])})


def _variants_absent(f: Folder) -> list[str]:
    return [*_variants_pass(f), "--measure", "gpu/nothing"]


def _variants_lacking(f: Folder) -> list[str]:
    """A variant with none of the named measures is unjudged, lacking them."""
    return variant_args(var_runs(f, "base", SAME, 0), {"a": var_runs(f, "a", SAME, 1),
                                                       "b": var_runs(f, "b", [None] * 3, 3)}, "--measure", "gpu/x")


def _variants_no_rank(f: Folder) -> list[str]:
    """The named measure is in no base run: rank_measure null."""
    return variant_args(var_runs(f, "base", [None] * 3, 0), {"a": var_runs(f, "a", SAME, 1)}, "--measure", "gpu/x")


def _variants_baseline(f: Folder) -> list[str]:
    older = var_runs(f, "base", SAME, 0)
    return ["compare", "--baseline", baseline_file(f, older), "--variant", "a", *var_runs(f, "a", SLOWER, 1)]


def _variants_unread(f: Folder) -> list[str]:
    return variant_args(var_runs(f, "base", SAME, 0), {"a": [*var_runs(f, "a", SAME, 1)[:2], str(f.root / "no.csv")]})


def _variants_override(f: Folder) -> list[str]:
    base = var_runs(f, "base", SAME, 0)
    return variant_args(base, {"a": var_runs(f, "a", SAME, 1, resolution=[1280, 720])},
                        "--override", "resolution=lower", "--override", "tier=unused")


VARIANTS = [
    Sample("variants-mixed", "compare", "variants",
           "pass, fail, refused and inconclusive variants; rank_measure, rank, measure", _variants_mixed),
    Sample("variants-pass", "compare", "variants", "verdict pass; --measure with a :median suffix", _variants_pass),
    Sample("variants-none-judged", "compare", "variants", "verdict error with the full variants shape",
           _variants_none_judged),
    Sample("variants-lacking", "compare", "variants", "--measure: a variant lacking the named measure",
           _variants_lacking),
    Sample("variants-no-rank", "compare", "variants", "rank_measure null", _variants_no_rank),
    Sample("variants-baseline", "compare", "variants", "baseline not null", _variants_baseline),
    Sample("variants-override", "compare", "variants", "overrides non-empty; override_unused",
           _variants_override),
    Sample("variants-absent", "compare", "absent_measure", "named_measures alone, for variants", _variants_absent),
    Sample("variants-file-unread", "compare", "file_unread", "result {} for variants", _variants_unread),
]


# ---------------------------------------------------------------------------
# alternate

class Bench:
    """An out folder, an order log, and a source run file a side, which the fake engine copies."""

    def __init__(self, folder: Folder):
        self.folder = folder
        self.out = folder.root / "ab"
        self.out.mkdir()
        self.log = folder.root / "order.log"
        self.sources: dict[str, str] = {}

    def source(self, side: str, text: str) -> None:
        self.sources[side] = self.folder.put(f"{side}-source.csv", text)

    def command(self, side: str) -> str:
        words = [sys.executable, "-I", str(FAKE_ENGINE), side, self.sources[side], str(self.log)]
        return command_line(words) + " {run}"

    def pair(self, *flags: str) -> list[str]:
        return ["alternate", "--old", self.command("old"), "--new", self.command("new"), "--out", str(self.out),
                "--runs", "3", *flags]

    def variants(self, *flags: str) -> list[str]:
        args = ["alternate", "--base", self.command("base")]
        for name in ("a", "b"):
            args += ["--variant", name, self.command(name)]
        return [*args, "--out", str(self.out), "--runs", "3", *flags]


def _bench(f: Folder, old: str | None = None, new: str | None = None) -> Bench:
    bench = Bench(f)
    bench.source("old", old if old is not None else steady(10.0))
    bench.source("new", new if new is not None else steady(11.0))
    return bench


def _alt_plain(f: Folder) -> list[str]:
    return _bench(f).pair()


def _alt_warmup(f: Folder) -> list[str]:
    return _bench(f, new=steady(10.0)).pair("--warmup", "1", "--measure", "gpu/opaque", "--min-ms", "0.1")


def _alt_variants(f: Folder) -> list[str]:
    bench = _bench(f)
    for name, opaque in (("base", 10.0), ("a", 10.0), ("b", 12.0)):
        bench.source(name, steady(opaque))
    return bench.variants()


def _alt_variants_unread(f: Folder) -> list[str]:
    """A variant's file that cannot be read leaves that variant unjudged."""
    bench = _bench(f)
    for name, text in (("base", steady(10.0)), ("a", "not a run\n"), ("b", steady(12.0))):
        bench.source(name, text)
    return bench.variants()


def _alt_variants_refused(f: Folder) -> list[str]:
    bench = _bench(f)
    for name, text in (("base", steady(10.0)), ("a", steady(10.0, resolution=[1, 1])), ("b", steady(12.0))):
        bench.source(name, text)
    return bench.variants()


def _alt_variants_absent(f: Folder) -> list[str]:
    return [*_alt_variants(f), "--measure", "gpu/nothing"]


def _alt_baseline(f: Folder) -> list[str]:
    bench = _bench(f)
    older = [f.put(f"older-{i}.csv", steady(10.0, run_id=f"o{i}", started_utc=f"2026-11-0{i}T12:00:00.250Z"))
             for i in (1, 2, 3)]
    return ["alternate", "--baseline", baseline_file(f, older), "--new", bench.command("new"), "--out",
            str(bench.out), "--runs", "3"]


def _alt_refused(f: Folder) -> list[str]:
    return _bench(f, new=steady(11.0, resolution=[1280, 720])).pair("--override", "tier=unused")


def _alt_absent(f: Folder) -> list[str]:
    return _alt_plain(f) + ["--measure", "gpu/nothing"]


def _alt_unread(f: Folder) -> list[str]:
    return _bench(f, new="not a run\n").pair()


def _alt_pass(f: Folder) -> list[str]:
    return _bench(f, new=steady(10.0)).pair()


EXIT4 = (("FAKE_ENGINE", "new-2=exit4"),)
NOFILE = (("FAKE_ENGINE", "new-2=nofile"),)

ALTERNATES = [
    Sample("alternate-plain", "alternate", "plain", "commands, out, warmup 0, stopped null; fail", _alt_plain),
    Sample("alternate-pass", "alternate", "plain", "verdict pass", _alt_pass),
    Sample("alternate-warmup", "alternate", "plain", "warmup above 0; --measure", _alt_warmup),
    Sample("alternate-baseline", "alternate", "plain", "baseline not null; commands holds only new", _alt_baseline),
    Sample("alternate-variants", "alternate", "variants", "commands holds base and each variant", _alt_variants),
    Sample("alternate-variants-unread", "alternate", "variants", "a variant left unjudged for an unread file",
           _alt_variants_unread),
    Sample("alternate-variants-refused", "alternate", "variants", "a refused variant", _alt_variants_refused),
    Sample("alternate-variants-absent", "alternate", "absent_measure", "named_measures with commands, out, warmup",
           _alt_variants_absent),
    Sample("alternate-refused", "alternate", "refused", "refused with commands, out, warmup, stopped null",
           _alt_refused),
    Sample("alternate-absent", "alternate", "absent_measure", "runs and named_measures with commands, out, warmup",
           _alt_absent),
    Sample("alternate-file-unread", "alternate", "file_unread", "commands, out, warmup, stopped, baseline; no {}",
           _alt_unread),
    Sample("alternate-stopped-exit", "alternate", "stopped", "stopped with an exit code", _alt_plain, EXIT4),
    Sample("alternate-stopped-baseline", "alternate", "stopped", "stopped with baseline not null", _alt_baseline,
           EXIT4),
    Sample("alternate-stopped-nofile", "alternate", "stopped", "stopped with exit_code null", _alt_plain, NOFILE),
]


# ---------------------------------------------------------------------------
# bisect

BAD = [14.0, 14.01, 14.02]
LONG = 1001  # frames: 1000 with a frame/wall, the fewest a 99th percentile is judged over
OPAQUE = ["--measure", "gpu/opaque", "--kind", "view"]


def bisect_args(f: Folder, tested: list | None = None, good: list | None = None, bad: list | None = None,
                *flags: str) -> list[str]:
    """Each list holds run texts, or a Taken; or a path in a Folder as a str
    that starts with `file:`. Writes them as tested-1.csv and so on."""
    args = ["bisect"]
    for label, items in (("tested", tested), ("good", good), ("bad", bad)):
        if items is None:
            continue
        paths = []
        for i, item in enumerate(items, 1):
            if isinstance(item, str) and item.startswith("file:"):
                paths.append(item[5:])
            else:
                text = item if isinstance(item, str) else steady(item)
                paths.append(f.put(f"{label}-{i}.csv", text))
        args += [f"--{label}", *paths]
    return [*args, *flags]


def _bisect(tested=None, good=SAME, bad=BAD, flags=tuple(OPAQUE)) -> Callable[[Folder], list[str]]:
    return lambda f: bisect_args(f, tested, good, bad, *flags)


def _threshold(tested, *flags: str) -> Callable[[Folder], list[str]]:
    return lambda f: bisect_args(f, tested, None, None, *OPAQUE, "--bad-above", "12", *flags)


def _walled(opaque: float, wall: float, frames: int, **header) -> str:
    return steady(opaque, frames=frames, wall=wall, **header)


def _long_refs(f: Folder) -> tuple[list[str], list[str]]:
    return ([_walled(10.0, 10.0 + i / 100, LONG) for i in range(3)],
            [_walled(10.0, 20.0 + i / 100, LONG) for i in range(3)])


def _bisect_p99(f: Folder, tested_frames: int) -> list[str]:
    good, bad = _long_refs(f)
    return bisect_args(f, [_walled(10.0, 10.0, tested_frames)], good, bad, "--measure", "frame/wall",
                       "--kind", "view", "--statistic", "p99")


def _bisect_missing_file(f: Folder) -> list[str]:
    return bisect_args(f, [10.0, f"file:{f.root / 'nowhere.csv'}", 10.0], SAME, BAD, *OPAQUE)


def _bisect_broken_file(f: Folder) -> list[str]:
    return bisect_args(f, [10.0, "no header here\n", 10.0], SAME, BAD, *OPAQUE)


def _two_depths(opaque: float) -> str:
    """gpu/opaque at depth 0 in half the frames and at depth 1 in the rest."""
    return run_text([(VIEW, rows(opaque), 60), (VIEW, rows(None, gpu__opaque__1=opaque), 60)])


def _bisect_depth_skip(f: Folder) -> list[str]:
    return bisect_args(f, [_two_depths(10.0)], SAME, BAD, *OPAQUE)


def _bisect_bad_references(f: Folder) -> list[str]:
    return bisect_args(f, [10.0], [f"file:{f.root / 'nowhere.csv'}", 10.0, 10.0], BAD, *OPAQUE)


def _bisect_depth_refs(f: Folder) -> list[str]:
    return bisect_args(f, [10.0], [_two_depths(10.0), 10.0, 10.0], BAD, *OPAQUE)


def _bisect_mem(f: Folder) -> list[str]:
    good = [steady(extra={"mem__vram": 100.0 + i / 10}, run_id=f"g{i}") for i in range(3)]
    bad = [steady(extra={"mem__vram": 200.0 + i / 10}, run_id=f"b{i}") for i in range(3)]
    tested = [steady(extra={"mem__vram": 210.0})]
    return bisect_args(f, tested, good, bad, "--measure", "mem/vram", "--kind", "view", "--min-mb", "5")


def _bisect_segment(f: Folder, *flags: str) -> list[str]:
    def two(opaque: float) -> str:
        return run_text([("view:1", rows(opaque), 60), ("spot:1", rows(opaque), 60)])
    return bisect_args(f, [two(14.0)], [two(v) for v in SAME], [two(v) for v in BAD], *flags)


def _bisect_unsegmented(f: Folder) -> list[str]:
    plain = lambda opaque: run_text([("", rows(opaque), 120)])  # noqa: E731
    return bisect_args(f, [plain(14.0)], [plain(v) for v in SAME], [plain(v) for v in BAD], "--measure",
                       "gpu/opaque", "--unsegmented")


def _bisect_refused_tested(f: Folder) -> list[str]:
    return bisect_args(f, [steady(10.0, resolution=[1280, 720])], SAME, BAD, *OPAQUE)


def _bisect_refused_refs(f: Folder) -> list[str]:
    return bisect_args(f, [10.0], [steady(v, resolution=[1280, 720]) for v in SAME], BAD, *OPAQUE)


def _bisect_override(f: Folder) -> list[str]:
    tested = [steady(10.0, resolution=[1280, 720], commit="def456", dirty=True)]
    return bisect_args(f, tested, SAME, BAD, *OPAQUE, "--override", "resolution=lower", "--override", "tier=unused")


def _bisect_unknown_build(f: Folder) -> list[str]:
    tested = [steady(10.0, unknown=["commit", "dirty"], commit="unknown", dirty=True)]
    return bisect_args(f, tested, SAME, BAD, *OPAQUE)


def _bisect_dry_run(f: Folder) -> list[str]:
    return bisect_args(f, None, SAME, BAD, *OPAQUE, "--dry-run", "13")


BISECTS = [
    Sample("bisect-good", "bisect", "judged", "good against references; references, bad_above, value",
           _bisect([10.0, 10.01, 10.02])),
    Sample("bisect-bad", "bisect", "judged", "bad against references", _bisect([14.0, 14.01, 14.02])),
    Sample("bisect-threshold-bad", "bisect", "judged", "--bad-above: references null, bad_above set",
           _threshold([14.0, 14.01, 14.02])),
    Sample("bisect-threshold-good", "bisect", "judged", "--bad-above: good", _threshold([10.0])),
    Sample("bisect-dry-run", "bisect", "judged", "dry_run true; runs are the references only", _bisect_dry_run),
    Sample("bisect-dry-run-threshold", "bisect", "judged", "dry_run true with no references and no runs",
           lambda f: bisect_args(f, None, None, None, *OPAQUE, "--bad-above", "12", "--dry-run", "11")),
    Sample("bisect-straddle", "bisect", "judged", "a tested_straddle warning", _bisect([10.0, 14.0, 10.0])),
    Sample("bisect-dirty", "bisect", "judged", "a dirty_build warning; an override used", _bisect_override),
    Sample("bisect-unknown-build", "bisect", "judged", "commit and dirty null for a listed build",
           _bisect_unknown_build),
    Sample("bisect-mem", "bisect", "judged", "a mem measure: unit MB", _bisect_mem),
    Sample("bisect-segment", "bisect", "judged", "--segment: measure.segment and segment_kind",
           lambda f: _bisect_segment(f, "--measure", "gpu/opaque", "--segment", "spot:1")),
    Sample("bisect-depth", "bisect", "judged", "--depth: measure.depth set",
           lambda f: _bisect_segment(f, "--measure", "gpu/opaque", "--kind", "view", "--depth", "0")),
    Sample("bisect-unsegmented", "bisect", "judged", "--unsegmented: segment_kind null", _bisect_unsegmented),
    Sample("bisect-p99", "bisect", "judged", "--statistic p99, judged over 1000 frames",
           lambda f: _bisect_p99(f, LONG)),
    Sample("bisect-generated", "bisect", "judged", "generated_frames above 0, all_frames true",
           lambda f: bisect_args(f, [_generated_run()], None, None, *OPAQUE, "--bad-above", "12",
                                 "--all-frames")),
    Sample("bisect-skip-unreadable", "bisect", "skipped_or_stopped", "skip; a run that cannot be read: short entry",
           _bisect_missing_file),
    Sample("bisect-skip-broken", "bisect", "skipped_or_stopped", "skip; a run that breaks the format: short entry",
           _bisect_broken_file),
    Sample("bisect-skip-incomplete", "bisect", "skipped_or_stopped", "skip_reason incomplete",
           _bisect([steady(10.0, close=False)])),
    Sample("bisect-skip-missing", "bisect", "skipped_or_stopped", "skip_reason missing",
           _bisect([steady(None)])),
    Sample("bisect-skip-depth", "bisect", "skipped_or_stopped", "skip_reason depth", _bisect_depth_skip),
    Sample("bisect-skip-short", "bisect", "skipped_or_stopped", "skip_reason short", lambda f: _bisect_p99(f, 120)),
    Sample("bisect-skip-straddle", "bisect", "skipped_or_stopped", "skip_reason straddle",
           _bisect([10.0, 14.0, 10.0], flags=(*OPAQUE, "--skip-straddle"))),
    Sample("bisect-skip-threshold", "bisect", "skipped_or_stopped", "skip with bad_above set and references null",
           _threshold([steady(None)])),
    Sample("bisect-stop-few", "bisect", "skipped_or_stopped", "stop; too few references: bad_above null",
           _bisect([10.0], good=SAME[:2])),
    Sample("bisect-stop-broken-reference", "bisect", "skipped_or_stopped", "stop; an unreadable reference",
           _bisect_bad_references),
    Sample("bisect-stop-reversed", "bisect", "skipped_or_stopped", "stop; references the wrong way round",
           _bisect([10.0], good=BAD, bad=SAME)),
    Sample("bisect-stop-not-separate", "bisect", "skipped_or_stopped", "stop; references that do not separate",
           _bisect([10.0], good=SAME, bad=[10.02, 10.03, 10.04])),
    Sample("bisect-stop-depths", "bisect", "skipped_or_stopped", "stop; a reference at two depths",
           _bisect_depth_refs),
    Sample("bisect-stop-refused-tested", "bisect", "skipped_or_stopped",
           "stop; refused non-empty, references and bad_above set", _bisect_refused_tested),
    Sample("bisect-stop-refused-refs", "bisect", "skipped_or_stopped", "stop; refused non-empty, references null",
           _bisect_refused_refs),
]


# ---------------------------------------------------------------------------
# survey

def survey_text(frames: list) -> str:
    """Frames of (segment, wall) after floor's warm-up, closed by a last frame with no wall."""
    lines = [floor_runs.HEADER, "run_id,segment,frame,category,name,depth,value"]
    walls = [("view:1", wall) for wall in FLOOR_WARM] + frames + [(frames[-1][0], None)]
    for number, (segment, wall) in enumerate(walls):
        lines.append(f"f1,{segment},{number},frame,cpu_span,0,8.000")
        if wall is not None:
            lines.append(f"f1,{segment},{number},frame,wall,0,{wall:.3f}")
    lines.append(f'# frameledger-close {{"rows_dropped":0,"frames":{len(walls)}}}')
    return "\n".join(lines) + "\n"


def _survey(*runs_: str | list, flags: tuple = ("--fps", "60")) -> Callable[[Folder], list[str]]:
    """Run texts are written; a name of a fixture, or `file:PATH` in Folder terms, is used as it is."""
    def build(f: Folder) -> list[str]:
        paths = []
        for i, item in enumerate(runs_, 1):
            if isinstance(item, list):
                paths.append(f.put(f"run-{i}.csv", survey_text(item)))
            elif item.startswith("missing"):
                paths.append(str(f.root / item))
            elif item.endswith(".csv") and (FIXTURES / item).exists():
                paths.append(str(FIXTURES / item))
            else:
                paths.append(f.put(f"run-{i}.csv", item))
        return ["survey", *paths, *flags]
    return build


STEADY = [("view:1", 16.0)] * 120
HITCH = [("view:1", 16.0)] * 60 + [("view:1", 40.0)] + [("view:1", 16.0)] * 59
TWO_KINDS = [("view:1", 16.0)] * 110 + [("spot:1", 16.5)] * 110
SHORT_KIND = [("view:1", 16.0)] * 130 + [("spot:1", 25.0)] * 5
NO_FRAMES_AFTER = [("view:1", 16.0)]

SURVEYS = [
    Sample("survey-pass", "survey", "one", "pass; every run judged", _survey(STEADY, TWO_KINDS)),
    Sample("survey-flagged", "survey", "one", "fail; a flagged run with slowest_over and worst_kind",
           _survey(STEADY, HITCH, TWO_KINDS, flags=("--budget-ms", "30", "--allow-frames", "0"))),
    Sample("survey-short-kind", "survey", "one", "a kind with ranked false", _survey(SHORT_KIND, HITCH)),
    Sample("survey-unjudged", "survey", "one", "an unread run: verdict unjudged, figures null; inconclusive",
           _survey(STEADY, "missing.csv")),
    Sample("survey-inconclusive-run", "survey", "one", "an inconclusive run with no close line",
           _survey(floor_runs.run_text([16.0] * 400).rsplit("# frameledger-close", 1)[0], STEADY)),
    Sample("survey-warnings", "survey", "one", "a run with warnings and a run with generated frames",
           _survey(_generated_run(), "negative-gpu.csv", flags=("--fps", "60", "--all-frames"))),
    Sample("survey-generated", "survey", "one", "generated_frames, all_frames false",
           _survey(_generated_run(), STEADY, flags=("--budget-ms", "20", "--warmup-s", "0.5"))),
]


# ---------------------------------------------------------------------------
# import, kit, selftest

PRESENT_COLUMNS = ["Application", "ProcessID", "SwapChainAddress", "PresentRuntime", "SyncInterval", "MsGPUTime",
                   "MsBetweenPresents", "MsCPUBusy", "MsGPUBusy", "DisplayedTime", "CPUStartDateTime",
                   "FrameType"]
EVERY_FACT = ["--commit", "abc123", "--clean", "--build-type", "release", "--device", "RX 9070 XT",
              "--renderer", "radeonsi", "--driver", "Mesa 26.2", "--resolution", "1920x1080",
              "--render-scale", "1.0", "--pipelined", "--display", "onscreen", "--scene", "atrium"]


def capture(count: int = 8, columns: list[str] | None = None, **changes: dict) -> str:
    """A PresentMon capture of `count` presents, from the first; `changes` maps an index to its replaced values."""
    columns = columns or PRESENT_COLUMNS
    lines = [",".join(columns)]
    for i in range(count):
        values = {"Application": "game.exe", "ProcessID": "4120", "SwapChainAddress": "0x1F2E3D",
                  "PresentRuntime": "DXGI", "SyncInterval": "0", "MsGPUTime": "9.5",
                  "MsBetweenPresents": f"{16 + i / 10:.1f}", "MsCPUBusy": "4.0", "MsGPUBusy": "6.0",
                  "DisplayedTime": "1.2", "CPUStartDateTime": f"2026-11-15T10:00:00.{250 + i}Z",
                  "FrameType": "Application", **changes.get(f"i{i}", {})}
        lines.append(",".join(values[c] for c in columns))
    return "\n".join(lines) + "\n"


def _import_args(f: Folder, text: str, *flags: str) -> list[str]:
    return ["import", "presentmon", f.put("capture.csv", text), "-o", str(f.root / "run.csv"), *flags]


def _import_to(f: Folder) -> str:
    """Run `import` quietly and return the run file's path."""
    with contextlib.redirect_stdout(io.StringIO()):
        cli.main([*_import_args(f, capture()), "--json"])
    return str(f.root / "run.csv")


def _import_generated(f: Folder) -> list[str]:
    text = capture(8, i2={"FrameType": "AMD_AFMF"}, i3={"FrameType": "AMD_AFMF", "DisplayedTime": "NA"},
                   i5={"FrameType": "Intel_XEFG"})
    return _import_args(f, text, *EVERY_FACT, "--presentmon-version", "2.3.0", "--started", "2026-11-15T10:00:00Z")


def _import_out_of_order(f: Folder) -> list[str]:
    return _import_args(f, capture(6, i3={"CPUStartDateTime": "2026-11-15T09:59:59Z"}))


def _import_bare_columns(f: Folder) -> list[str]:
    columns = ["Application", "ProcessID", "SwapChainAddress", "MsBetweenPresents", "MsCPUBusy"]
    return _import_args(f, capture(5, columns), "--started", "2026-11-15T10:00:00Z")


IMPORTS = [
    Sample("import-basic", "import", "one", "unknown non-empty; generated {} and not_displayed 0",
           lambda f: _import_args(f, capture())),
    Sample("import-facts", "import", "one", "every fact given: unknown empty; generated by type; not_displayed",
           _import_generated),
    Sample("import-out-of-order", "import", "one", "a start_out_of_order warning", _import_out_of_order),
    Sample("import-bare-columns", "import", "one", "not_displayed null and generated null; no start column",
           _import_bare_columns),
    Sample("import-selected", "import", "one", "--process, --pid and --swapchain, --engine, --tier, --os",
           lambda f: _import_args(f, capture(), "--process", "GAME.exe", "--pid", "4120", "--swapchain", "0x1F2E3D",
                                  "--engine", "doom-ants", "--dirty", "--not-pipelined", "--tier", "high",
                                  "--os", "Windows 11")),
]
KITS = [Sample("kit", "kit", "one", "files written", lambda f: ["kit", str(f.root / "kit")])]
SELFTESTS = [Sample("selftest", "selftest", "one", "checks with name and pass", lambda f: ["--selftest"])]

SAMPLES = [*CHECKS, *REPORTS, *FLOORS, *BUDGETS, *COMPARES, *SCENES, *VARIANTS, *ALTERNATES, *BISECTS, *SURVEYS,
           *IMPORTS, *KITS, *SELFTESTS]


# ---------------------------------------------------------------------------
# Running a sample

@contextlib.contextmanager
def _environment(extra: tuple[tuple[str, str], ...]) -> Iterator[None]:
    """`extra` in the environment, and nothing of the fake engine's that is already there."""
    saved = dict(os.environ)
    for key in [k for k in os.environ if k.startswith("FAKE_ENGINE")]:
        del os.environ[key]
    os.environ.update(extra)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(saved)


def run(sample: Sample, tmp_path: Path) -> tuple[int, str]:
    """Build the sample's files under `tmp_path`, run it with --json, and
    return the exit code and what it printed on standard output. Standard
    error is left alone: `alternate` points its commands' output at it, so
    it must have a file descriptor, which pytest's capsys does not give."""
    argv = sample.build(Folder(Path(tmp_path)))
    out = io.StringIO()
    with _environment(sample.env), contextlib.redirect_stdout(out):  # standard error stays, for `alternate`'s children
        code = cli.main([*argv, "--json"])
    return code, out.getvalue()
