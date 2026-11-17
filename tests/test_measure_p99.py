"""A measure's 99th percentile (FLED-0076): --measure CATEGORY/NAME:p99
under compare, and --statistic p99 under bisect, for any measure but mem.

Invariants INV-122 to INV-124 from docs/specs/FLED-0001-run-file-format.md
§ 5, the rules of § 4.10's `:median` and `:p99` and § 4.11's
`--statistic`. Each run is built here as text.
"""

import json

import cli
import ledger
from floor_runs import HEADER

FRAMES = 4000


def run_text(run_id: str, slow: str, holding: int = FRAMES // 2, short_kind: int = 0, frames: int = FRAMES,
             segment_frames: int = FRAMES, depth: int = 0) -> str:
    """`frames` frames of kind view, a new segment every `segment_frames`,
    each with frame/cpu_span, frame/gpu_span and a wall, and gpu/X at
    `depth` on the first `holding` even frames: 2.000 ms, but `slow` on
    one in fifty, the slowest 2%. Then `short_kind` frames of load:1,
    gpu/X on every other one, the same way. Every frame has mem/m."""
    header = HEADER.replace('"run_id":"f1"', f'"run_id":"{run_id}"')
    lines = [header, ledger.COLUMNS]
    total = frames + short_kind
    held = 0
    for frame in range(total):
        segment = f"view:{frame // segment_frames + 1}" if frame < frames else "load:1"
        rows = [("frame", "cpu_span", "5.000"), ("frame", "gpu_span", "5.000"), ("mem", "m", "100.000")]
        if frame != total - 1:
            rows.append(("frame", "wall", "8.000"))
        in_view = frame < frames and frame % 2 == 0 and held < holding
        if in_view or (frame >= frames and frame % 2 == 0):
            held += in_view
            rows.append(("gpu", "X", slow if (frame // 2) % 50 == 0 else "2.000"))
        lines += [f"{run_id},{segment},{frame},{category},{name},{depth if category == 'gpu' else 0},{value}"
                  for category, name, value in rows]
    lines.append(f'# frameledger-close {{"rows_dropped":0,"frames":{total}}}')
    return "\n".join(lines) + "\n"


def write(tmp_path, name: str, slow: str, **options) -> str:
    path = tmp_path / f"{name}.csv"
    path.write_text(run_text(name, slow, **options), encoding="utf-8")
    return str(path)


def sets(tmp_path, **options) -> tuple[list[str], list[str]]:
    """Old runs with their slowest 2% at 4.000 ms, new at 8.000: equal
    medians, the new 99th percentile twice the old. `options` go to the
    first old run only."""
    old = [write(tmp_path, f"old{i}", "4.000", **(options if i == 1 else {})) for i in range(1, 4)]
    new = [write(tmp_path, f"new{i}", "8.000") for i in range(1, 4)]
    return old, new


def compare(capsys, old: list[str], new: list[str], *measures: str, json_out: bool = True) -> tuple[int, dict | str]:
    args = ["compare", "--old", *old, "--new", *new]
    for measure in measures:
        args += ["--measure", measure]
    code = cli.main([*args, "--json"] if json_out else args)
    out = capsys.readouterr()
    return code, json.loads(out.out) if json_out else out.out


def entry(out: dict, statistic: str, kind: str = "view") -> dict:
    return next(m for m in out["result"]["measures"]
                if (m["name"], m["statistic"], m["segment_kind"]) == ("X", statistic, kind))


# INV-122

def test_p99_of_a_pass(capsys, tmp_path):
    old, new = sets(tmp_path)
    code, out = compare(capsys, old, new, "gpu/X")
    assert code == 0
    assert [m["statistic"] for m in out["result"]["measures"]] == ["median"]  # a bare name keeps its median
    assert compare(capsys, old, new, "gpu/X:median")[0] == 0

    code, out = compare(capsys, old, new, "gpu/X:p99")
    assert code == 1
    p99 = entry(out, "p99")
    assert (p99["old_centre"], p99["new_centre"], p99["verdict"]) == (4.0, 8.0, "slower")
    assert p99["old_frames"] == p99["new_frames"] == [2000, 2000, 2000]
    assert out["result"]["named_measures"] == ["gpu/X:p99"]
    assert [m["statistic"] for m in out["result"]["measures"]] == ["p99"]

    code, text = compare(capsys, old, new, "gpu/X:p99", json_out=False)
    assert "slower, 2000 frames" in text  # beside the entry
    assert "8.000 (2000)" in text  # in each run's values

    # Any frame measure takes :p99, ranked beside its median.
    code, out = compare(capsys, old, new, "frame/cpu_span", "frame/gpu_span:p99", "frame/wall:p99")
    assert code == 0
    assert [(m["name"], m["statistic"]) for m in out["result"]["measures"]] == \
        [("cpu_span", "median"), ("gpu_span", "p99"), ("wall", "p99")]

    code, out = compare(capsys, old, new, "gpu/X", "gpu/X:p99")  # two measures
    assert code == 1
    assert sorted(m["statistic"] for m in out["result"]["measures"]) == ["median", "p99"]
    assert entry(out, "median")["old_frames"] == [2000, 2000, 2000]  # JSON gives frames for every measure


def test_suffix_refusals(capsys, tmp_path):
    old, new = sets(tmp_path)
    for measures, named in ((["mem/m:p99"], "mem/m:p99"), (["gpu/X:p95"], "gpu/X:p95"),
                            (["gpu/X:"], "gpu/X:"), (["gpu/X:P99"], "gpu/X:P99"),
                            (["frame/wall", "frame/wall:p99"], "frame/wall:p99"),
                            (["gpu/X", "gpu/X:median"], "gpu/X:median"), (["gpu"], "--measure gpu must")):
        args = ["compare", "--old", *old, "--new", *new]
        for measure in measures:
            args += ["--measure", measure]
        assert cli.main(args) == 3
        assert named in capsys.readouterr().err


# INV-123

def test_too_few_frames(capsys, tmp_path):
    old, new = sets(tmp_path, holding=999)
    code, out = compare(capsys, old, new, "gpu/X:p99")
    assert code == 2
    assert entry(out, "p99")["verdict"] == "too_few"
    assert entry(out, "p99")["old_frames"] == [999, 2000, 2000]
    assert any("999 frames" in sentence for sentence in out["summary"])
    code, text = compare(capsys, old, new, "gpu/X:p99", json_out=False)
    assert "too few, 999 frames" in text  # listed, never absent

    old, new = sets(tmp_path, holding=1000)
    code, out = compare(capsys, old, new, "gpu/X:p99")
    assert (code, entry(out, "p99")["verdict"]) == (1, "slower")

    # A 50-frame kind beside a long one: named, and the long kind's verdict, unchanged, stands.
    old = [write(tmp_path, f"old{i}", "4.000", short_kind=100) for i in range(1, 4)]
    new = [write(tmp_path, f"new{i}", "4.000", short_kind=100) for i in range(1, 4)]
    code, out = compare(capsys, old, new, "gpu/X:p99")
    assert code == 0
    assert (entry(out, "p99", "load")["verdict"], entry(out, "p99")["verdict"]) == ("too_few", "unchanged")
    assert any("load" in sentence and "50 frames" in sentence for sentence in out["summary"])

    # A kind's frames are its segments' together: twenty segments of 60 make 1200.
    old = [write(tmp_path, f"old{i}", "4.000", frames=2400, segment_frames=120, holding=1200) for i in range(1, 4)]
    new = [write(tmp_path, f"new{i}", "8.000", frames=2400, segment_frames=120, holding=1200) for i in range(1, 4)]
    code, out = compare(capsys, old, new, "gpu/X:p99")
    assert (code, entry(out, "p99")["verdict"], entry(out, "p99")["old_frames"]) == (1, "slower", [1200] * 3)

    # A bare frame/wall over 999 frames keeps its 99th percentile, with no bound.
    short = [write(tmp_path, f"short{i}", "4.000", frames=1000) for i in range(1, 4)]  # the last has no wall
    code, out = compare(capsys, short, short, "frame/wall")
    wall = next(m for m in out["result"]["measures"] if (m["name"], m["statistic"]) == ("wall", "p99"))
    assert wall["verdict"] != "too_few"


# INV-124

def test_bisect_p99(capsys, tmp_path):
    old, new = sets(tmp_path)

    def bisect(*args: str) -> tuple[int, dict]:
        code = cli.main(["bisect", *args, "--measure", "gpu/X", "--kind", "view", "--json"])
        out = capsys.readouterr().out
        return code, json.loads(out) if out else {}

    assert bisect("--tested", *new, "--statistic", "p99", "--bad-above", "6")[0] == 1
    assert bisect("--tested", *new, "--bad-above", "6")[0] == 0  # the median, 2.000
    assert cli.main(["bisect", "--tested", *new, "--measure", "mem/m", "--kind", "view", "--statistic", "p99",
                     "--bad-above", "6"]) == 128
    capsys.readouterr()

    short = write(tmp_path, "short", "8.000", holding=999)
    code, out = bisect("--tested", short, *new[1:], "--statistic", "p99", "--bad-above", "6")
    assert (code, out["result"]["skip_reason"]) == (125, "short")
    # Short and at another depth: the depth is settled first, since frames are counted at it.
    deep = write(tmp_path, "deep", "8.000", holding=999, depth=1)
    code, out = bisect("--tested", deep, *new[1:], "--statistic", "p99", "--bad-above", "6")
    assert (code, out["result"]["skip_reason"]) == (125, "depth")
    short_old, _ = sets(tmp_path, holding=999)
    code, out = bisect("--tested", *new, "--good", *short_old, "--bad", *new, "--statistic", "p99")
    assert code == 128
    assert any("999" in sentence for sentence in out["summary"])


def test_variants_rank_by_the_suffix(capsys, tmp_path):
    old, new = sets(tmp_path)
    code = cli.main(["compare", "--base", *old, "--variant", "v", *new, "--measure", "gpu/X:p99", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert code == 1
    assert out["result"]["rank_measure"]["statistic"] == "p99"
    assert out["result"]["variants"][0]["measure"]["change"] == 4.0


def test_nothing_judged_never_passes(capsys, tmp_path):
    old, new = sets(tmp_path)
    empty = tmp_path / "empty.csv"
    empty.write_text("\n".join([HEADER, ledger.COLUMNS, '# frameledger-close {"rows_dropped":0,"frames":0}']) + "\n")
    code, out = compare(capsys, old, [str(empty), *new[1:]])  # every measure unmatched, no --measure
    assert code == 2
    assert "The compare is inconclusive: no measure is in every run, so nothing was judged." in out["summary"]

    # A :p99 measure one run lacks: missing, so a longer run is not the cure.
    lacking = write(tmp_path, "lacking", "8.000", holding=0)
    code, out = compare(capsys, old, [lacking, *new[1:]], "gpu/X:p99")
    assert code == 2 and "longer run" not in " ".join(out["summary"])
    code, out = compare(capsys, old, [lacking, *new[1:]], "gpu/X:p99", "frame/cpu_span")
    assert code == 2
    assert any("gpu/X:p99 is in no kind every run has" in sentence for sentence in out["summary"])

    code, out = compare(capsys, old, new, "gpu/X", "gpu/X:p99")
    assert {m["statistic"]: m["suffixed"] for m in out["result"]["measures"]} == {"median": False, "p99": True}
