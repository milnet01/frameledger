"""Bisect verdicts (S17).

Invariants from docs/specs/FLED-0001-run-file-format.md § 5: INV-39 to
INV-51, the rules of § 4.11. Every run is built here. Unless a test says
otherwise, each frame of a run carries the same rows, so a measure's
per-run value is the value written.
"""

import json

import pytest

import bisecting
import cli
import ledger
import render

HEADER = {
    "schema": 1, "run_id": "r", "engine": "ut-ants", "tool": {"name": "ut-bench", "version": "1.0"},
    "build_type": "release", "commit": "c80d41d", "dirty": False,
    "device": "AMD Radeon RX 9070 XT", "renderer": "AMD Radeon RX 9070 XT (radeonsi)",
    "driver": "Mesa 26.2", "api": "opengl-4.5", "resolution": [1920, 1080], "render_scale": 1.0,
    "vsync": False, "pipelined": True, "display": "headless", "scene": "DM-ArchNemesis",
    "inputs": [{"name": "DM-ArchNemesis", "hash": "sha256:" + "ab" * 32, "bytes": 48213}],
    "started_utc": "2026-10-26T12:00:00Z",
}
OPAQUE = ["--measure", "gpu/opaque", "--kind", "view"]


def rows(opaque=None, **extra):
    """One frame's rows, {(category, name, depth): value}: every measure
    fixed, and gpu/opaque when given. `extra` adds rows keyed
    "category__name" at depth 0."""
    frame = {("frame", "wall", 0): 16.0, ("frame", "cpu_span", 0): 8.0, ("frame", "gpu_span", 0): 12.0,
             ("cpu", "sim", 0): 5.0}
    if opaque is not None:
        frame[("gpu", "opaque", 0)] = opaque
    for key, value in extra.items():
        category, name = key.split("__")
        frame[(category, name, 0)] = value
    return frame


def run_text(frames, close=True, dropped=0, **header):
    """A run of `frames`, a list of (segment, rows); the last frame has no
    frame/wall, as in a real run."""
    fields = {**HEADER, **header}
    lines = [f"# frameledger {json.dumps(fields)}", "run_id,segment,frame,category,name,depth,value"]
    for number, (segment, frame_rows) in enumerate(frames):
        for (category, name, depth), value in frame_rows.items():
            if (category, name) == ("frame", "wall") and number == len(frames) - 1:
                continue
            lines.append(f"{fields['run_id']},{segment},{number},{category},{name},{depth},{value:.3f}")
    if close:
        lines.append(f'# frameledger-close {{"rows_dropped":{dropped},"frames":{len(frames)}}}')
    return "\n".join(lines) + "\n"


def run(opaque, frames=120, segment="view:1", **header):
    """A run whose every frame has gpu/opaque `opaque`."""
    return run_text([(segment, rows(opaque))] * frames, **header)


def bisect(capsys, tmp_path, tested=(), *flags, good=(), bad=()):
    """Run `bisect --json` on run texts written to files. Returns (exit
    code, parsed result or None)."""
    args = []
    for label, texts in (("tested", tested), ("good", good), ("bad", bad)):
        paths = []
        for i, text in enumerate(texts, 1):
            path = tmp_path / f"{label}-{i}.csv"
            path.write_text(text, encoding="utf-8")
            paths.append(str(path))
        if paths:
            args += [f"--{label}", *paths]
    code = cli.main(["bisect", *args, *flags, "--json"])
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err  # a stop is a sentence, never a crash (DOOM Ants)
    return code, json.loads(captured.out) if captured.out else None


def references(capsys, tmp_path, good, bad, *flags, tested=(), measure=OPAQUE):
    """Reference mode with one run per value in `good` and `bad`; a value
    that is a string is a whole run text already."""
    def texts(values):
        return [v if isinstance(v, str) else run(v) for v in values]
    return bisect(capsys, tmp_path, texts(tested), *measure, *flags, good=texts(good), bad=texts(bad))


def code_of(capsys, tmp_path, tested, *flags):
    return bisect(capsys, tmp_path, [run(v) for v in tested], *OPAQUE, *flags)[0]


# INV-39

def test_threshold_edges(capsys, tmp_path):
    assert code_of(capsys, tmp_path, [10.0], "--bad-above", "10.000") == 0
    assert code_of(capsys, tmp_path, [10.0], "--bad-above", "9.999") == 1


def test_tested_centre(capsys, tmp_path):
    middles = [9.0, 9.0, 11.0, 11.0]  # centre 10.000; the lower middle 9, the upper 11
    assert code_of(capsys, tmp_path, middles, "--bad-above", "9.999") == 1
    assert code_of(capsys, tmp_path, middles, "--bad-above", "10.000") == 0
    # The centre is 10.000; the mean, 11.000, would read bad.
    assert code_of(capsys, tmp_path, [9.0, 9.0, 11.0, 15.0], "--bad-above", "10.000") == 0


def test_equal_sentence(capsys, tmp_path):
    code, result = bisect(capsys, tmp_path, [run(10.0)], *OPAQUE, "--bad-above", "10.000")
    assert result["summary"][-1] == ("gpu/opaque median in view segments is 10.000 ms, at or below the "
                                     "threshold of 10.000 ms: good (exit 0).")


def test_five_place_midpoint(capsys, tmp_path):
    code, result = references(capsys, tmp_path, [10.0, 10.0, 10.001, 10.001], [12.0] * 3, "--dry-run", "11")
    assert code == 0
    assert result["result"]["bad_above"] == 11.00025
    assert "11.00025 ms" in result["summary"][-1]


def test_exact_comparison(capsys, tmp_path):
    code, result = bisect(capsys, tmp_path, [run(10.0), run(10.001)], *OPAQUE, "--bad-above", "10.000")
    assert code == 1
    assert result["result"]["value"] == 10.0005
    assert "10.0005 ms" in result["summary"][-1]


# INV-40

def test_reference_midpoint(capsys, tmp_path):
    good, bad = [10.0] * 3, [12.0] * 3
    assert references(capsys, tmp_path, good, bad, tested=[11.0])[0] == 0
    code, result = references(capsys, tmp_path, good, bad, tested=[11.001])
    assert code == 1
    assert result["result"]["bad_above"] == 11.0
    assert result["result"]["references"] == {"good_centre": 10.0, "bad_centre": 12.0, "spread": 0.0,
                                              "floor": 0.3}
    # The good centre is 10.000; a midpoint of means (11.083) or of the six
    # runs pooled (11.300) would call 11.001 good.
    assert references(capsys, tmp_path, [9.9, 10.0, 10.6], bad, tested=[11.001])[0] == 1


@pytest.mark.parametrize("bad, code", [
    ([10.2, 10.3, 10.4], 0),     # change 0.300, the floor; spread 0.200
    ([10.2, 10.299, 10.4], 128),  # change under the floor
    ([10.5, 11.0, 11.5], 128),    # change equal to the spread
    ([10.501, 11.0, 11.5], 0),
])
def test_references_separate(capsys, tmp_path, bad, code):
    assert references(capsys, tmp_path, [10.0] * 3, bad, "--dry-run", "10.000")[0] == code


def test_good_range_counts(capsys, tmp_path):
    assert references(capsys, tmp_path, [9.5, 10.0, 10.5], [11.0] * 3, "--dry-run", "10.000")[0] == 128
    assert references(capsys, tmp_path, [9.501, 10.0, 10.5], [11.0] * 3, "--dry-run", "10.000")[0] == 0


def test_inverted_and_equal_references(capsys, tmp_path):
    code, result = references(capsys, tmp_path, [12.0] * 3, [10.0] * 3, "--dry-run", "11.000")
    assert code == 128 and "wrong way round" in result["summary"][0]
    code, result = references(capsys, tmp_path, [10.0] * 3, [10.0] * 3, "--dry-run", "11.000")
    assert code == 128 and "do not separate" in result["summary"][0]


# INV-41

@pytest.mark.parametrize("broken", ["dropped", "unclosed", "malformed", "missing"])
def test_skip(capsys, tmp_path, broken):
    text = {"dropped": run_text([("view:1", rows(20.0))] * 120, dropped=1),
            "unclosed": run_text([("view:1", rows(20.0))] * 120, close=False),
            "malformed": run(20.0).replace("20.000", "abc", 1),
            "missing": None}[broken]
    if text is None:
        code = cli.main(["bisect", "--tested", str(tmp_path / "absent.csv"), *OPAQUE, "--bad-above", "10.000",
                         "--json"])
        result = json.loads(capsys.readouterr().out)
    else:
        code, result = bisect(capsys, tmp_path, [text], *OPAQUE, "--bad-above", "10.000")
    assert code == 125
    assert result["verdict"] == "skip"
    assert "tested-1" in result["summary"][0]


def test_skip_names_the_kinds(capsys, tmp_path):
    code, result = bisect(capsys, tmp_path, [run(None)], *OPAQUE, "--bad-above", "10.000")
    assert code == 125
    assert "view" in result["summary"][0]


# INV-42

def stop_args(tmp_path, *flags):
    path = tmp_path / "t.csv"
    path.write_text(run(10.0), encoding="utf-8")
    return ["bisect", "--tested", str(path), *flags]


@pytest.mark.parametrize("flags", [
    ["--help"], ["-h"], ["--version"],
    [*OPAQUE, "--bad-above", "abc"],
    [*OPAQUE, "--bad-above", "1.0001"],
    [*OPAQUE],
    [*OPAQUE, "--bad-above", "10", "--good", "x.csv"],
    [*OPAQUE, "--bad-above", "10", "--min-ms", "1"],
    [*OPAQUE, "--bad-above", "10", "--min-mb", "1"],
    [*OPAQUE, "--bad-above", "10", "--min-pct", "1"],
    ["--measure", "gpu/opaque", "--kind", "view", "--statistic", "p99", "--bad-above", "10"],
    ["--measure", "event/cut", "--kind", "view", "--bad-above", "10"],
    ["--measure", "frame/fence_wait", "--kind", "view", "--bad-above", "10"],
    ["--measure", "gpu/opaque", "--bad-above", "10"],
    ["--measure", "gpu/opaque", "--kind", "view", "--unsegmented", "--bad-above", "10"],
    [*OPAQUE, "--dry-run", "1.0001", "--bad-above", "10"],
    [*OPAQUE, "--bad-above", "1000000000"],
    ["--measure", "frame/wall", "--kind", "view", "--depth", "1", "--bad-above", "10"],
    ["--measure", "gpu/opaque", "--kind", "view:1", "--bad-above", "10"],
    ["--measure", "gpu/opaque", "--segment", "view:", "--bad-above", "10"],
    [*OPAQUE, "--bad-above", "10", "extra.csv"],
])
def test_stop_codes(capsys, tmp_path, flags):
    assert cli.main(stop_args(tmp_path, *flags)) == 128
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err
    # Only --help prints on standard output: a stop's reason goes to standard error.
    assert captured.err or flags in (["--help"], ["-h"])


def test_stop_before_the_command(capsys, tmp_path, monkeypatch):
    assert cli.main(["--version", "bisect"]) == 128
    assert cli.main(["--selftest", *stop_args(tmp_path, *OPAQUE, "--bad-above", "10")]) == 128
    assert "not a bisect" in capsys.readouterr().err
    assert cli.main(["bisect", *OPAQUE, "--bad-above", "10"]) == 128
    assert "give --tested FILE..." in capsys.readouterr().err
    # A check of a file named bisect is not a bisect command line: it exits 3, not 128.
    monkeypatch.chdir(tmp_path)
    assert cli.main(["check", "bisect"]) == 3
    # A command line that is otherwise sound still stops on --version.
    assert cli.main(["--version", *stop_args(tmp_path, *OPAQUE, "--bad-above", "10")]) == 128
    assert cli.main(["--json", *stop_args(tmp_path, *OPAQUE, "--bad-above", "abc")]) == 128
    capsys.readouterr()


def test_stop_on_an_internal_error(capsys, tmp_path, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("a bug")
    monkeypatch.setattr(ledger, "read", broken)  # an error while reading a run, not a file problem
    assert cli.main(stop_args(tmp_path, *OPAQUE, "--bad-above", "10")) == 128
    assert "RuntimeError: a bug" in capsys.readouterr().err
    monkeypatch.undo()
    monkeypatch.setattr(bisecting, "bisect", broken)
    assert cli.main(stop_args(tmp_path, *OPAQUE, "--bad-above", "10")) == 128
    monkeypatch.undo()
    monkeypatch.setattr(render, "to_json", broken)
    assert cli.main(stop_args(tmp_path, *OPAQUE, "--bad-above", "10", "--json")) == 128
    capsys.readouterr()


def test_reference_refusal(capsys, tmp_path):
    good, bad = [10.0] * 3, [12.0] * 3
    assert references(capsys, tmp_path, good[:2], bad, "--dry-run", "11")[0] == 128
    assert references(capsys, tmp_path, good, [run_text([("view:1", rows(12.0))] * 120, dropped=1)] * 3,
                      "--dry-run", "11")[0] == 128
    missing = cli.main(["bisect", "--dry-run", "11", *OPAQUE, "--good", *[str(tmp_path / "no.csv")] * 3,
                        "--bad", *[str(tmp_path / "no.csv")] * 3])
    assert missing == 128
    capsys.readouterr()
    wide = [run(10.0), run(10.0), run(10.0, resolution=[2560, 1440])]
    code, result = references(capsys, tmp_path, wide, bad, "--dry-run", "11")
    assert code == 128
    assert result["result"]["refused"][0]["field"] == "resolution"
    assert references(capsys, tmp_path, wide, bad, "--dry-run", "11",
                      "--override", "resolution=upscaler test")[0] == 0
    elsewhere = [run(11.5, scene="DM-Deck16")]
    assert references(capsys, tmp_path, good, bad, tested=elsewhere)[0] == 128


# INV-43

def test_dry_run(capsys, tmp_path):
    code = cli.main(["bisect", "--dry-run", "10.001", *OPAQUE, "--bad-above", "10.000", "--json"])
    result = json.loads(capsys.readouterr().out)
    assert code == 1 and result["verdict"] == "bad" and result["result"]["dry_run"] is True
    assert result["summary"][-1].startswith("Dry run:")
    code = cli.main(["bisect", "--dry-run", "10.000", *OPAQUE, "--bad-above", "10.000", "--json"])
    result = json.loads(capsys.readouterr().out)
    assert code == 0 and result["verdict"] == "good"
    assert result["summary"][-1].startswith("Dry run:")
    assert code_of(capsys, tmp_path, [10.0], "--dry-run", "10", "--bad-above", "10") == 128
    assert references(capsys, tmp_path, [12.0] * 3, [10.0] * 3, "--dry-run", "11")[0] == 128


# INV-44

MEM = ["--measure", "mem/gpu_mb", "--kind", "view"]


def mem_run(gpu_mb, **header):
    return run_text([("view:1", rows(10.0, mem__gpu_mb=gpu_mb))] * 120, **header)


def test_mem_measure(capsys, tmp_path):
    frames = [("view:1", rows(10.0, mem__gpu_mb=mb)) for mb in (100.0, 500.0, 900.0)]
    frames += [("load:1", rows(10.0, mem__gpu_mb=9000.0))] * 2
    tested = [run_text(frames)]
    assert bisect(capsys, tmp_path, tested, *MEM, "--bad-above", "500.000")[0] == 0
    code, result = bisect(capsys, tmp_path, tested, *MEM, "--bad-above", "499.999")
    assert code == 1
    assert result["result"]["measure"]["unit"] == "MB"
    good = [mem_run(500.0)] * 3
    assert references(capsys, tmp_path, good, [mem_run(500.999)] * 3, "--min-pct", "0",
                      "--dry-run", "500", measure=MEM)[0] == 128
    assert references(capsys, tmp_path, good, [mem_run(501.0)] * 3, "--min-pct", "0",
                      "--dry-run", "500", measure=MEM)[0] == 0
    ticked = [mem_run(500.0, gpu_tick_ns=5000000), *good[1:]]
    assert references(capsys, tmp_path, ticked, [mem_run(501.0)] * 3, "--min-pct", "0",
                      "--dry-run", "500", measure=MEM)[0] == 0
    # A floor in the wrong unit stops, though these references separate without it.
    assert references(capsys, tmp_path, good, [mem_run(501.0)] * 3, "--min-pct", "0", "--min-ms", "5",
                      "--dry-run", "500", measure=MEM)[0] == 128
    assert references(capsys, tmp_path, [10.0] * 3, [12.0] * 3, "--min-mb", "1", "--dry-run", "10")[0] == 128


# INV-45

def test_warning_keeps_code(capsys, tmp_path):
    tested = [run(11.0, build_type="debug"), run(11.0, dirty=True)]
    code, result = bisect(capsys, tmp_path, tested, *OPAQUE, "--bad-above", "10.000",
                          "--override", "build_type=a Debug run on purpose")
    assert code == 1
    messages = {w["code"]: w["message"] for w in result["warnings"]}
    assert messages["debug_build"].startswith("tested-1:")
    assert messages["dirty_build"].startswith("tested-2:")


# INV-46

def test_depth(capsys, tmp_path):
    frames = [("view:1", {**rows(), ("gpu", "blur", 0): 2.0})] * 60
    frames += [("view:1", {**rows(), ("gpu", "blur", 1): 5.0})] * 60
    tested = [run_text(frames)]
    blur = ["--measure", "gpu/blur", "--kind", "view"]
    code, result = bisect(capsys, tmp_path, tested, *blur, "--bad-above", "4.000")
    assert code == 128
    assert result["summary"] == ["gpu/blur is at more than one depth (tested-1 at 0 and 1); --depth picks one.",
                                 "The bisect stops (exit 128)."]
    assert bisect(capsys, tmp_path, tested, *blur, "--depth", "1", "--bad-above", "4.000")[0] == 1
    assert bisect(capsys, tmp_path, tested, *blur, "--depth", "0", "--bad-above", "4.000")[0] == 0
    assert bisect(capsys, tmp_path, tested, *blur, "--depth", "2", "--bad-above", "4.000")[0] == 125


# INV-47

def test_references_straddle(capsys, tmp_path):
    code, result = references(capsys, tmp_path, [10.0, 10.0, 10.9], [11.0, 11.2, 11.3], "--dry-run", "10")
    assert code == 128
    assert "good-3" in result["summary"][0]
    assert references(capsys, tmp_path, [10.0] * 3, [11.0, 12.0, 12.5], "--dry-run", "10")[0] == 128
    assert references(capsys, tmp_path, [10.0] * 3, [11.001, 12.0, 12.5], "--dry-run", "10")[0] == 0


# INV-48

def test_frames_chosen(capsys, tmp_path):
    views = [("view:1", rows(10.0))] * 200 + [("view:2", rows(14.0))] * 100
    tested = [run_text(views)]
    assert bisect(capsys, tmp_path, tested, "--measure", "gpu/opaque", "--segment", "view:2",
                  "--bad-above", "12.000")[0] == 1
    assert bisect(capsys, tmp_path, tested, *OPAQUE, "--bad-above", "12.000")[0] == 0
    assert bisect(capsys, tmp_path, tested, "--measure", "gpu/opaque", "--segment", "view:3",
                  "--bad-above", "12.000")[0] == 125
    mixed = [run_text([("", rows(8.0))] * 50 + views)]
    assert bisect(capsys, tmp_path, mixed, "--measure", "gpu/opaque", "--unsegmented",
                  "--bad-above", "9.000")[0] == 0
    walls = [("view:1", {**rows(), ("frame", "wall", 0): 16.0})] * 99
    walls += [("view:1", {**rows(), ("frame", "wall", 0): 40.0})] * 2 + [("view:1", rows())]
    wall = ["--measure", "frame/wall", "--kind", "view", "--bad-above", "30.000"]
    assert bisect(capsys, tmp_path, [run_text(walls)], *wall, "--statistic", "p99")[0] == 1
    assert bisect(capsys, tmp_path, [run_text(walls)], *wall)[0] == 0
    # One 40.000 in 100 walls: rank 99 is 16.000, so the p99 is not the slowest frame.
    one = [("view:1", {**rows(), ("frame", "wall", 0): 16.0})] * 99
    one += [("view:1", {**rows(), ("frame", "wall", 0): 40.0}), ("view:1", rows())]
    assert bisect(capsys, tmp_path, [run_text(one)], *wall, "--statistic", "p99")[0] == 0
    # A run's median is report's nearest rank, the lower middle: 10.000, not 11.000.
    halves = [run_text([("view:1", rows(10.0))] * 60 + [("view:1", rows(12.0))] * 60)]
    assert bisect(capsys, tmp_path, halves, *OPAQUE, "--bad-above", "10.000")[0] == 0
    code, result = bisect(capsys, tmp_path, tested, "--measure", "gpu/opaque", "--segment", "view:2",
                          "--bad-above", "12.000")
    assert result["result"]["measure"]["segment_kind"] == "view"
    assert result["result"]["measure"]["segment"] == "view:2"


# INV-49

def test_runs_must_match(capsys, tmp_path):
    tested = [run(11.0), run(11.0, resolution=[2560, 1440]), run(11.0)]
    assert bisect(capsys, tmp_path, tested, *OPAQUE, "--bad-above", "10")[0] == 128
    override = ["--override", "resolution=upscaler test"]
    code, result = bisect(capsys, tmp_path, tested, *OPAQUE, "--bad-above", "10", *override)
    assert code == 1
    assert "resolution" in result["summary"][0] and "upscaler test" in result["summary"][0]
    code, result = bisect(capsys, tmp_path, [run(11.0)], *OPAQUE, "--bad-above", "10", *override)
    assert [w["code"] for w in result["warnings"]] == ["override_unused"]
    wide = [run(11.5, resolution=[2560, 1440])]
    assert references(capsys, tmp_path, [10.0] * 3, [12.0] * 3, tested=wide)[0] == 128
    assert references(capsys, tmp_path, [10.0] * 3, [12.0] * 3, *override, tested=wide)[0] == 1
    # The references use the override, so it is not unused though the tested run matches them all.
    mixed = [run(10.0), run(10.0), run(10.0, resolution=[2560, 1440])]
    code, result = references(capsys, tmp_path, mixed, [12.0] * 3, *override, tested=[11.5])
    assert code == 1 and "override_unused" not in [w["code"] for w in result["warnings"]]
    # A dry run warns on an override no reference needs (Vestige).
    code, result = references(capsys, tmp_path, [10.0] * 3, [12.0] * 3, *override, "--dry-run", "11")
    assert [w["code"] for w in result["warnings"]] == ["override_unused"]


# INV-50

def test_reference_floor(capsys, tmp_path):
    good, bad = [10.0] * 3, [10.4] * 3
    assert references(capsys, tmp_path, good, bad, "--dry-run", "10")[0] == 0
    assert references(capsys, tmp_path, good, bad, "--min-ms", "0.500", "--dry-run", "10")[0] == 128
    ticked = [run(10.4), run(10.4), run(10.4, gpu_tick_ns=500000)]  # the tick in bad-3
    assert references(capsys, tmp_path, good, ticked, "--dry-run", "10")[0] == 128
    # Two ticks: the largest, 0.500, is the floor; the smaller, 0.200, would pass.
    two = [run(10.0, gpu_tick_ns=200000), run(10.0), run(10.0)]
    assert references(capsys, tmp_path, two, ticked, "--dry-run", "10")[0] == 128
    assert references(capsys, tmp_path, two, bad, "--dry-run", "10")[0] == 0

    def sim(value, **header):
        return run_text([("view:1", {**rows(), ("cpu", "sim", 0): value})] * 120, **header)
    cpu = ["--measure", "cpu/sim", "--kind", "view"]
    assert references(capsys, tmp_path, [sim(10.0, gpu_tick_ns=500000), sim(10.0), sim(10.0)],
                      [sim(10.4)] * 3, "--dry-run", "10", measure=cpu)[0] == 0


# INV-51

def test_tested_straddle(capsys, tmp_path):
    good, bad = [10.0] * 3, [12.0] * 3
    code, result = references(capsys, tmp_path, good, bad, tested=[10.9, 11.0, 11.1])
    assert code == 0
    straddle = [w["message"] for w in result["warnings"] if w["code"] == "tested_straddle"]
    assert len(straddle) == 1 and all(v in straddle[0] for v in ("10.900", "11.000", "11.100"))
    assert references(capsys, tmp_path, good, bad, "--skip-straddle", tested=[10.9, 11.0, 11.1])[0] == 125
    for flags in ([], ["--skip-straddle"]):
        code, result = references(capsys, tmp_path, good, bad, *flags, tested=[11.001, 11.1, 11.2])
        assert code == 1
        assert "tested_straddle" not in [w["code"] for w in result["warnings"]]
    code, result = bisect(capsys, tmp_path, [run(10.0), run(10.001)], *OPAQUE, "--bad-above", "10.000")
    assert "tested_straddle" in [w["code"] for w in result["warnings"]]
    # Unsorted, the first and last are both above; all at or below never straddle.
    code, result = references(capsys, tmp_path, good, bad, tested=[11.1, 10.9, 11.2])
    assert "tested_straddle" in [w["code"] for w in result["warnings"]]
    code, result = references(capsys, tmp_path, good, bad, tested=[10.9, 10.95, 11.0])
    assert code == 0 and "tested_straddle" not in [w["code"] for w in result["warnings"]]
    code, result = bisect(capsys, tmp_path, [run(10.001)], *OPAQUE, "--bad-above", "10.000")
    assert result["warnings"] == []
    assert cli.main(["bisect", "--dry-run", "10", *OPAQUE, "--bad-above", "10", "--skip-straddle"]) == 128
    capsys.readouterr()


def test_text_names_the_verdict(capsys, tmp_path):
    path = tmp_path / "t.csv"
    path.write_text(run(12.3), encoding="utf-8")
    assert cli.main(["bisect", "--tested", str(path), *OPAQUE, "--bad-above", "11.000"]) == 1
    out = capsys.readouterr().out
    assert "gpu/opaque median in view segments is 12.300 ms, above the threshold of 11.000 ms: " \
           "bad (exit 1)." in out


# INV-41: every tested run is checked, and an empty or headerless file skips.

@pytest.mark.parametrize("text", ["", "# frameledger {\"schema\":1}\n",
                                  "\x00\xff binary garbage\n",
                                  run(20.0).replace('"dirty": false, ', "")])
def test_skip_broken_headers(capsys, tmp_path, text):
    code, result = bisect(capsys, tmp_path, [text], *OPAQUE, "--bad-above", "10.000")
    assert code == 125
    assert result["summary"][-1] == "This commit is skipped (exit 125)."


def test_skip_any_tested_run(capsys, tmp_path):
    whole = run(20.0)
    for broken in (run_text([("view:1", rows(20.0))] * 120, dropped=1), run(20.0).replace("20.000", "abc", 1),
                   run(None)):
        assert bisect(capsys, tmp_path, [whole, broken, whole], *OPAQUE, "--bad-above", "10.000")[0] == 125
    unclosed = run_text([("view:1", rows(20.0))] * 120, close=False)
    code, result = bisect(capsys, tmp_path, [unclosed, whole, unclosed], *OPAQUE, "--bad-above", "10.000")
    assert code == 125
    assert [s.split(" ")[0] for s in result["summary"][:2]] == ["tested-1", "tested-3"]
    code, result = bisect(capsys, tmp_path, [run(10.0)], "--measure", "gpu/opaque", "--segment", "view:9",
                          "--bad-above", "10.000")
    assert code == 125 and "its segments are view:1" in result["summary"][0]


# INV-42: a broken reference stops, by name and without its path.

def test_broken_references(capsys, tmp_path):
    good, bad = [10.0] * 3, [12.0] * 3
    unclosed = run_text([("view:1", rows(10.0))] * 120, close=False)
    for broken in (unclosed, run(10.0).replace("10.000", "abc", 1), run(None), ""):
        code, result = references(capsys, tmp_path, [broken, *good[1:]], bad, "--dry-run", "11")
        assert code == 128
        assert result["summary"][0].startswith("good-1 ")
    code = cli.main(["bisect", "--dry-run", "11", *OPAQUE, "--good", str(tmp_path / "gone.csv"),
                     *[str(tmp_path / "gone.csv")] * 2, "--bad", *[str(tmp_path / "gone.csv")] * 3, "--json"])
    result = json.loads(capsys.readouterr().out)
    assert code == 128
    assert result["summary"][0].startswith("good-1 is a broken reference file: it cannot be read")
    assert str(tmp_path) not in " ".join(result["summary"])


# INV-46: one depth across runs.

def test_one_depth_across_runs(capsys, tmp_path):
    blur = ["--measure", "gpu/blur", "--kind", "view"]

    def at(depth, value):
        return run_text([("view:1", {**rows(), ("gpu", "blur", depth): value})] * 120)
    shallow, deep = [at(0, 2.0)] * 3, [at(0, 5.0)] * 3
    assert references(capsys, tmp_path, shallow, deep, tested=[at(1, 5.0)], measure=blur)[0] == 128
    assert references(capsys, tmp_path, shallow, [at(1, 5.0)] * 3, "--dry-run", "3", measure=blur)[0] == 128
    assert references(capsys, tmp_path, shallow, deep, tested=[at(0, 5.0)], measure=blur)[0] == 1


# INV-53

def test_file_lists(capsys, tmp_path):
    tested = tmp_path / "t1.csv"
    tested.write_text(run(11.5), encoding="utf-8")
    refs = []
    for name, value in (("g1", 10.0), ("g2", 10.0), ("g3", 10.0), ("b1", 12.0), ("b2", 12.0), ("b3", 12.0)):
        path = tmp_path / f"{name}.csv"
        path.write_text(run(value), encoding="utf-8")
        refs.append(str(path))
    code = cli.main(["bisect", "--tested", str(tested), *OPAQUE, "--good", *refs[:3], "--bad", *refs[3:],
                     str(tested), "--json"])
    result = json.loads(capsys.readouterr().out)
    assert code == 1
    assert [r["name"] for r in result["result"]["runs"]][-2:] == ["bad-4", "tested-1"]
    assert cli.main(["bisect", str(tested), *OPAQUE, "--bad-above", "10"]) == 128
    capsys.readouterr()
    code, result = bisect(capsys, tmp_path, [""], *OPAQUE, "--bad-above", "10")
    assert str(tmp_path) not in " ".join(result["summary"])
