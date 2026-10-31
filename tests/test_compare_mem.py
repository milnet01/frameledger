"""`compare` on mem measures: docs/specs/FLED-0001-run-file-format.md § 4.10,
INV-65 to INV-67. Every run is built by test_compare's helpers."""

import re

import cli
from test_compare import alike, compare, new, old


def rows(gpu_mb, opaque=10.0, **more_mem):
    """INV-30's frame, with mem/gpu_mb and any other mem rows."""
    mem = {("mem", name): value for name, value in more_mem.items()}
    return {**alike(opaque), ("mem", "gpu_mb"): gpu_mb, **mem}


def sets(old_mb, new_mb, **kw):
    return old([rows(v) for v in old_mb], **kw), new([rows(v) for v in new_mb], **kw)


def gpu_mb(result):
    return next(m for m in result["result"]["measures"] if m["name"] == "gpu_mb")


def judged(capsys, tmp_path, old_mb, new_mb, *flags, **kw):
    code, result = compare(capsys, tmp_path, *sets(old_mb, new_mb, **kw), *flags)
    return code, gpu_mb(result)


def test_mem_judged(capsys, tmp_path):
    """INV-65: judged by its own spread and floor, in MB."""
    code, mem = judged(capsys, tmp_path, [500.0] * 3, [515.0] * 3)
    assert (code, mem["verdict"], mem["change"], mem["floor"], mem["unit"]) == (1, "larger", 15.0, 15.0, "MB")
    assert (mem["old"], mem["new"], mem["old_centre"], mem["new_centre"]) == ([500.0] * 3, [515.0] * 3, 500.0, 515.0)

    code, mem = judged(capsys, tmp_path, [500.0] * 3, [514.999] * 3)
    assert (code, mem["verdict"]) == (0, "unchanged")

    code, mem = judged(capsys, tmp_path, [500.0] * 3, [485.0] * 3)
    assert (code, mem["verdict"]) == (0, "smaller")

    code, mem = judged(capsys, tmp_path, [500.0, 510.0, 520.0], [525.0, 530.0, 535.0])
    assert (code, mem["verdict"], mem["change"], mem["spread"]) == (0, "noisy", 20.0, 20.0)

    code, mem = judged(capsys, tmp_path, [0.0] * 3, [5.0] * 3)
    assert (code, mem["verdict"], mem["change_pct"], mem["floor"]) == (1, "larger", None, 1.0)
    code, mem = judged(capsys, tmp_path, [0.0] * 3, [0.999] * 3)
    assert (code, mem["verdict"]) == (0, "unchanged")


def test_mem_each_depth_apart(capsys, tmp_path):
    """INV-65: one name at two depths gives two measures. A frame holds a
    name once, so the depths are in different frames."""
    def at_two_depths(texts, deep):
        # Frames 60 on hold the row at depth 1 with the value `deep`.
        late_row = r"^(.*?,(?:[6-9][0-9]|1[0-9][0-9]),mem,gpu_mb),0,[0-9.]+$"
        return [re.sub(late_row, rf"\g<1>,1,{deep:.3f}", text, flags=re.M) for text in texts]

    code, result = compare(capsys, tmp_path, at_two_depths(old([rows(100.0)] * 3), 200.0),
                           at_two_depths(new([rows(100.0)] * 3), 220.0))
    mem = {m["depth"]: m for m in result["result"]["measures"] if m["category"] == "mem"}
    assert code == 1
    assert (mem[0]["verdict"], mem[0]["old_centre"]) == ("unchanged", 100.0)
    assert (mem[1]["verdict"], mem[1]["change"]) == ("larger", 20.0)


def test_mem_floor(capsys, tmp_path):
    """INV-66: --min-mb is a mem measure's floor and nothing else's."""
    assert judged(capsys, tmp_path, [10.0] * 3, [10.999] * 3)[1]["verdict"] == "unchanged"
    assert judged(capsys, tmp_path, [10.0] * 3, [11.0] * 3)[1]["verdict"] == "larger"
    assert judged(capsys, tmp_path, [10.0] * 3, [11.0] * 3, "--min-mb", "2")[1]["verdict"] == "unchanged"
    assert judged(capsys, tmp_path, [10.0] * 3, [11.0] * 3, "--min-ms", "2")[1]["verdict"] == "larger"
    assert judged(capsys, tmp_path, [10.0] * 3, [11.0] * 3, gpu_tick_ns=5000000)[1]["verdict"] == "larger"
    assert judged(capsys, tmp_path, [10.0] * 3, [11.0] * 3, "--min-pct", "20")[1]["verdict"] == "unchanged"

    code, result = compare(capsys, tmp_path, old([rows(10.0)] * 3), new([rows(10.0, opaque=11.0)] * 3),
                           "--min-mb", "5")
    opaque = next(m for m in result["result"]["measures"] if m["name"] == "opaque")
    assert (code, opaque["verdict"], opaque["unit"]) == (1, "slower", "ms")
    assert result["result"]["min_mb"] == 5.0

    assert compare(capsys, tmp_path, *sets([10.0] * 3, [11.0] * 3), "--min-mb", "-1")[0] == 3


def test_mem_sentences(capsys, tmp_path):
    """INV-67: memory is reported in its own unit, and MB and ms never
    rank against each other."""
    code, result = compare(capsys, tmp_path, *sets([500.0] * 3, [520.0] * 3))
    sentence = next(s for s in result["summary"] if "mem/gpu_mb" in s)
    assert code == 1 and result["verdict"] == "fail"
    assert sentence.startswith("The new runs use more memory: 1 measure got larger")
    assert "up 20.000 MB (+4.0%)" in sentence and "spread of 0.000 MB" in sentence and " ms" not in sentence

    args = [f"{label}-{i}.csv" for label in ("old", "new") for i in (1, 2, 3)]
    paths = [str(tmp_path / name) for name in args]
    assert cli.main(["compare", "--old", *paths[:3], "--new", *paths[3:]]) == 1
    text = capsys.readouterr().out
    assert "Memory measures that moved" in text and "old MB" in text and "old ms" not in text

    code, result = compare(capsys, tmp_path, old([rows(500.0)] * 3), new([rows(520.0, opaque=11.0)] * 3))
    slower = next(i for i, s in enumerate(result["summary"]) if s.startswith("The new runs are slower"))
    assert "gpu/opaque" in result["summary"][slower] and "1.000 ms" in result["summary"][slower]
    assert "mem/gpu_mb" in result["summary"][slower + 1] and "20.000 MB" in result["summary"][slower + 1]
    categories = [m["category"] for m in result["result"]["measures"]]
    assert categories == sorted(categories, key=["frame", "cpu", "gpu", "mem"].index) and categories[-1] == "mem"

    code, result = compare(capsys, tmp_path, old([rows(500.0, sys_mb=500.0)] * 3),
                           new([rows(520.0, sys_mb=530.0)] * 3))
    assert any("2 measures got larger" in s and "mem/sys_mb" in s and "30.000 MB" in s for s in result["summary"])
    code, result = compare(capsys, tmp_path, old([rows(500.0, sys_mb=100.0)] * 3),
                           new([rows(520.0, sys_mb=120.0)] * 3))
    assert any("the largest is mem/sys_mb" in s for s in result["summary"])  # a tie goes to the larger percent

    code, result = compare(capsys, tmp_path, *sets([500.0] * 3, [480.0] * 3))
    assert any("No measure got slower or larger" in s and "1 measure got smaller" in s for s in result["summary"])


def test_mem_unmatched_and_unjudged(capsys, tmp_path):
    """INV-67: a mem name in only some runs is named and judges nothing, in
    the text too (Vestige); an event or ext row judges nothing."""
    code, result = compare(capsys, tmp_path, old([rows(500.0)] * 3), new([alike(10.0)] * 3))
    assert code == 0 and result["result"]["unmatched"] == [
        {"segment_kind": "view", "category": "mem", "name": "gpu_mb", "depth": 0, "statistic": "median",
         "unit": "MB", "present_in": ["old-1", "old-2", "old-3"]}]
    paths = [str(tmp_path / f"{label}-{i}.csv") for label in ("old", "new") for i in (1, 2, 3)]
    assert cli.main(["compare", "--old", *paths[:3], "--new", *paths[3:]]) == 0
    text = capsys.readouterr().out
    assert "Not in every run, so not judged:" in text and "mem/gpu_mb: only in old-1, old-2, old-3" in text

    def other(value):
        return {**alike(10.0), ("event", "cut"): value, ("ext.vestige", "draws"): value}

    code, result = compare(capsys, tmp_path, old([other(1.0)] * 3), new([other(100.0)] * 3))
    assert code == 0
    assert {m["category"] for m in result["result"]["measures"]} == {"frame", "cpu", "gpu"}
