"""compare --measure and its per-run table.

Invariants from docs/specs/FLED-0001-run-file-format.md § 5: INV-85 and
INV-86, the rules of § 4.10's *Naming measures* and *Each run's values*.
"""

import json

import pytest

import cli
from test_compare import HEADER, compare, run_text

LONG_KIND = "loading_screen_with_a_long_name1"  # 32 bytes, the most a segment kind may hold
LONG_PASS = "p" * 64  # 64 bytes, the most a name may hold
EXTRA = [f"p{i:02d}" for i in range(1, 12)] + [LONG_PASS]


def rows(wall: float, a: float, c: bool = False) -> dict:
    """One run's frame: gpu/a as given, gpu/b the same in every run, and
    cpu/c only where asked."""
    found = {("frame", "wall"): wall, ("frame", "cpu_span"): 8.0, ("frame", "gpu_span"): 12.0,
             ("gpu", "a"): a, ("gpu", "b"): 3.0}
    return {**found, ("cpu", "c"): 2.0} if c else found


def fixture() -> tuple[list, list]:
    """INV-85's runs: 120 frames each; gpu/a 2 ms slower in every new
    run; frame/wall noisy (both centres 16, spread 2); cpu/c in old-1 only."""
    old = [run_text(rows(wall, 5.0, c=i == 0), run_id=f"old{i}", started_utc=f"2026-11-11T12:{2 * i:02d}:00Z")
           for i, wall in enumerate((15.0, 16.0, 17.0))]
    new = [run_text(rows(wall, 7.0), run_id=f"new{i}", started_utc=f"2026-11-11T12:{2 * i + 1:02d}:00Z")
           for i, wall in enumerate((15.5, 16.5, 16.0))]
    return old, new


def test_measure_keeps_named(capsys, tmp_path):
    """INV-85: only the named measures are judged and decide the verdict.
    Without the flag gpu/a fails it; naming gpu/b alone passes, which only
    the filter can do, since frame/wall is noisy and gpu/a slower."""
    old, new = fixture()
    assert compare(capsys, tmp_path, old, new)[0] == 1

    code, result = compare(capsys, tmp_path, old, new, "--measure", "gpu/b")
    assert code == 0
    measures = result["result"]["measures"]
    assert measures and {(m["category"], m["name"]) for m in measures} == {("gpu", "b")}
    assert result["result"]["unmatched"] == []
    assert result["result"]["named_measures"] == ["gpu/b"]
    assert result["summary"][0] == "Judging only gpu/b."

    assert compare(capsys, tmp_path, old, new, "--measure", "gpu/a")[0] == 1
    assert compare(capsys, tmp_path, old, new, "--measure", "frame/wall")[0] == 2

    code, result = compare(capsys, tmp_path, old, new, "--measure", "cpu/c")
    assert code == 2 and result["verdict"] == "inconclusive"
    assert [m["name"] for m in result["result"]["unmatched"]] == ["c"]
    assert any("cpu/c" in s for s in result["summary"][1:])

    code, result = compare(capsys, tmp_path, old, new, "--measure", "gpu/b", "--measure", "cpu/c")
    assert code == 0  # a partly unmatched list still judges gpu/b


@pytest.mark.parametrize("flags, named", [
    (["--measure", "gpu/z"], "gpu/z"),
    (["--measure", "gpu/B"], "gpu/B"),
    (["--measure", "event/x"], "event/x"),
    (["--measure", "frame/fence_wait"], "frame/fence_wait"),
    (["--measure", "gpu/"], "gpu/"),
    (["--measure", "gpu/b", "--measure", "gpu/b"], "gpu/b"),
])
def test_measure_refused(capsys, tmp_path, flags, named):
    """INV-85: a name no run has, case included, a bad name and a repeat
    are each exit 3, naming it."""
    old, new = fixture()
    args = []
    for label, texts in (("old", old), ("new", new)):
        args.append(f"--{label}")
        for i, text in enumerate(texts, 1):
            path = tmp_path / f"{label}-{i}.csv"
            path.write_text(text, encoding="utf-8")
            args.append(str(path))
    assert cli.main(["compare", *args, *flags, "--json"]) == 3
    captured = capsys.readouterr()
    said = captured.out + captured.err
    assert named in said and "unrecognized arguments" not in said  # refused for its name, not as a flag


def two_kind_run(run_id: str, started: str, offset: float) -> str:
    """120 frames in view:1, then 120 in LONG_KIND:1, each with gpu/b,
    frame/wall and every EXTRA pass; each value moved by `offset`, so
    every run's cells differ."""
    fields = {**HEADER, "run_id": run_id, "started_utc": started}
    lines = [f"# frameledger {json.dumps(fields)}", "run_id,segment,frame,category,name,depth,value"]
    for frame in range(240):
        segment = "view:1" if frame < 120 else f"{LONG_KIND}:1"
        values = {("frame", "wall"): 16.0, ("frame", "cpu_span"): 8.0, ("frame", "gpu_span"): 12.0,
                  ("gpu", "b"): 3.0,
                  **{("gpu", name): 1.0 + i / 10 for i, name in enumerate(EXTRA)}}
        for (category, name), value in values.items():
            if (category, name) == ("frame", "wall") and frame == 239:
                continue
            lines.append(f"{run_id},{segment},{frame},{category},{name},0,{value + offset:.3f}")
    lines.append('# frameledger-close {"rows_dropped":0,"frames":240}')
    return "\n".join(lines) + "\n"


def per_run_tables(text: str) -> list[list[str]]:
    """The per-run tables' lines: each table a header line, then one line
    a run; the tables follow their title, separated by a blank line."""
    lines = text.splitlines()
    start = lines.index("Each run's value of each named measure (ms; mem in MB):") + 1
    tables, table = [], []
    for line in lines[start:]:
        if not line:
            if not table:
                break
            tables.append(table)
            table = []
            continue
        table.append(line)
    return tables + ([table] if table else [])


def test_per_run_table(capsys, tmp_path):
    """INV-86: one row a run, in run order, each cell the JSON's value to
    three places; spilled tables repeat the run column, a too-wide header
    is cut, and no table line is over 100 characters."""
    old, new = fixture()
    paths = {}
    for label, texts in (("old", old), ("new", new)):
        paths[label] = []
        for i, text in enumerate(texts, 1):
            path = tmp_path / f"{label}-{i}.csv"
            path.write_text(text, encoding="utf-8")
            paths[label].append(str(path))
    base = ["compare", "--old", *paths["old"], "--new", *paths["new"]]
    names = ["old-1", "old-2", "old-3", "new-1", "new-2", "new-3"]

    def run(*flags):
        cli.main([*base, *flags])
        text = capsys.readouterr().out
        cli.main([*base, *flags, "--json"])
        return text, json.loads(capsys.readouterr().out)

    text, result = run("--measure", "gpu/b", "--measure", "frame/wall")
    [table] = per_run_tables(text)
    assert table[0].split()[0] == "run"
    assert [line.split()[0] for line in table[1:]] == names
    measures = result["result"]["measures"]
    for row, name in zip(table[1:], names, strict=True):
        side, index = name.split("-")
        assert row.split()[1:] == [f"{m[side][int(index) - 1]:.3f}" for m in measures]

    assert "Each run's value" not in run()[0]
    assert "Each run's value" not in run("--by-scene", "--measure", "gpu/b")[0]

    for label in ("old", "new"):
        for i, path in enumerate(paths[label]):
            started = f"2026-11-11T13:{2 * i + (label == 'new'):02d}:00Z"
            offset = (i + 3 * (label == "new")) / 100
            with open(path, "w", encoding="utf-8") as out:
                out.write(two_kind_run(f"{label}{i}", started, offset))
    flags = [arg for name in ["gpu/b", "frame/wall", *(f"gpu/{n}" for n in EXTRA)]
             for arg in ("--measure", name)]
    text, result = run(*flags)
    tables = per_run_tables(text)
    assert len(tables) > 1
    assert all(t[0].split()[0] == "run" and [line.split()[0] for line in t[1:]] == names for t in tables)
    measures = result["result"]["measures"]
    for row, name in enumerate(names, 1):
        side, index = name.split("-")
        cells = [cell for t in tables for cell in t[row].split()[1:]]
        assert cells == [f"{m[side][int(index) - 1]:.3f}" for m in measures]
    headers = " ".join(t[0] for t in tables)
    assert "..." in headers and LONG_KIND[:10] in headers
    assert max(len(line) for t in tables for line in t) <= 100  # § 4.8 bounds tables, not sentences


def scene_runs(scene: str, water: float | None, new_water: float | None) -> tuple[list, list]:
    """Three old and three new runs of one scene; gpu/w only where given."""
    texts = {}
    for side, w, offset in (("old", water, 0), ("new", new_water, 1)):
        found = {("frame", "wall"): 16.0, ("frame", "cpu_span"): 8.0, ("frame", "gpu_span"): 12.0,
                 ("gpu", "b"): 3.0, **({("gpu", "w"): w} if w is not None else {})}
        texts[side] = [run_text(found, run_id=f"{scene}{side}{i}", scene=scene,
                                started_utc=f"2026-11-11T14:{offset + 2 * i:02d}:00Z") for i in range(3)]
    return texts["old"], texts["new"]


@pytest.mark.parametrize("new_water, want", [(4.0, 0), (6.0, 1)])
def test_by_scene_leaves_out_scenes_without_named(capsys, tmp_path, new_water, want):
    """INV-85: under --by-scene, a scene with none of the named measures is
    unjudged and does not make the command inconclusive (Vestige); the
    scene that has gpu/w decides. Without the rule the command is exit 2
    when gpu/w passes."""
    old_a, new_a = scene_runs("atrium", 4.0, new_water)
    old_h, new_h = scene_runs("hall", None, None)
    code, result = compare(capsys, tmp_path, old_a + old_h, new_a + new_h, "--by-scene", "--measure", "gpu/w")
    assert code == want
    hall = next(s for s in result["result"]["scenes"] if s["scene"] == "hall")
    assert hall["verdict"] == "unjudged" and "named measure" in hall["reason"]
    assert result["result"]["judged"]["scenes"] == 1


def test_absent_refusal_keeps_runs(capsys, tmp_path):
    """INV-85: a name no run has still gives the runs and the names in JSON."""
    code, result = compare(capsys, tmp_path, *fixture(), "--measure", "gpu/z")
    assert code == 3
    assert result["result"]["named_measures"] == ["gpu/z"] and len(result["result"]["runs"]) == 6


@pytest.mark.parametrize("scenes", [[], ["--by-scene"]])
def test_absent_text(capsys, tmp_path, scenes):
    """INV-85: a name no run has, in text, is exit 3 with only that
    sentence, as a plain compare and under --by-scene (UT Ants); no
    scene's sentences or table follow it."""
    old, new = fixture()
    args = []
    for label, texts in (("old", old), ("new", new)):
        args.append(f"--{label}")
        for i, text in enumerate(texts, 1):
            path = tmp_path / f"{label}-{i}.csv"
            path.write_text(text, encoding="utf-8")
            args.append(str(path))
    assert cli.main(["compare", *args, *scenes, "--measure", "gpu/z", "--measure", "gpu/y"]) == 3
    out = capsys.readouterr().out
    assert out == ("No run has gpu/z or gpu/y, so they cannot be judged; a name matches exactly, "
                   "case included.\n")


def test_by_scene_absent_json_and_unread(capsys, tmp_path):
    """INV-85: under --by-scene, a refusal's named_measures is every name
    given, as a plain compare's (DOOM Ants); and when some scene's runs
    were not read, the sentence claims only the runs read."""
    old_h, new_h = scene_runs("hall", None, None)
    code, result = compare(capsys, tmp_path, old_h, new_h, "--by-scene", "--measure", "gpu/b",
                           "--measure", "gpu/zz")
    assert code == 3 and result["result"]["named_measures"] == ["gpu/b", "gpu/zz"]
    assert result["summary"][0].startswith("No run has gpu/zz,")

    old_c, new_c = scene_runs("cellar", 4.0, 4.0)  # two old runs: unjudged, never read
    code, result = compare(capsys, tmp_path, old_h + old_c[:2], new_h + new_c, "--by-scene",
                           "--measure", "gpu/w")
    assert code == 3 and result["summary"][0].startswith("No run read has gpu/w,")


def test_short_kind_sentence_needs_frame_wall(capsys, tmp_path):
    """§ 4.10: the sentence on kinds too short for step 3 is said only
    when frame/wall is judged, since step 3 skips nothing otherwise
    (DOOM Ants)."""
    texts = {side: [run_text(rows(16.0, 5.0), run_id=f"{side}{i}", spots=10,
                             started_utc=f"2026-11-11T15:{2 * i + (side == 'new'):02d}:00Z") for i in range(3)]
             for side in ("old", "new")}
    said = " ".join(compare(capsys, tmp_path, texts["old"], texts["new"])[1]["summary"])
    assert "fewer than" in said
    said = " ".join(compare(capsys, tmp_path, texts["old"], texts["new"], "--measure", "gpu/b")[1]["summary"])
    assert "fewer than" not in said
