"""Comparing labelled sets of runs (S4, S5's refusal half, S16).

Invariants from docs/specs/FLED-0001-run-file-format.md § 5: INV-30 to
INV-37, the rules of § 4.10. Every run is built here: each frame of a
run carries the same rows, so a measure's per-run value is the value
written.
"""

import json

import pytest

import cli

HEADER = {
    "schema": 1, "run_id": "r", "engine": "vestige", "tool": {"name": "bench", "version": "1.0"},
    "build_type": "release", "commit": "abc123", "dirty": False,
    "device": "AMD Radeon RX 9070 XT", "renderer": "AMD Radeon RX 9070 XT (radeonsi)",
    "driver": "Mesa 26.2", "api": "opengl-4.5", "resolution": [1920, 1080], "render_scale": 1.0,
    "vsync": False, "pipelined": True, "display": "headless", "scene": "atrium",
    "inputs": [{"name": "atrium", "hash": "sha256:" + "ab" * 32, "bytes": 48213}],
    "started_utc": "2026-10-26T12:00:00Z",
}


def alike(opaque, wall=16.0, gpu_span=12.0):
    """INV-30's frame: every measure fixed but the opaque pass."""
    return {("frame", "wall"): wall, ("frame", "cpu_span"): 8.0, ("frame", "gpu_span"): gpu_span,
            ("cpu", "sim"): 5.0, ("gpu", "opaque"): opaque}


def run_text(rows, frames=120, close=True, dropped=0, static=None, spots=0, **header):
    """A run of `frames` frames in view:1, then `spots` in spot:1, each
    carrying `rows` ({(category, name): ms}); the last frame has no wall,
    as in a real run."""
    fields = {**HEADER, **header}
    lines = [f"# frameledger {json.dumps(fields)}"]
    if static is not None:
        lines.append(f"# frameledger-static {json.dumps(static)}")
    lines.append("run_id,segment,frame,category,name,depth,value")
    total = frames + spots
    for frame in range(total):
        segment = "view:1" if frame < frames else "spot:1"
        for (category, name), value in rows.items():
            if (category, name) == ("frame", "wall") and frame == total - 1:
                continue
            lines.append(f"{fields['run_id']},{segment},{frame},{category},{name},0,{value:.3f}")
    if close:
        lines.append(f'# frameledger-close {{"rows_dropped":{dropped},"frames":{total}}}')
    return "\n".join(lines) + "\n"


def compare(capsys, tmp_path, old, new, *flags):
    """Run `compare --json` on two sets, each a list of run texts; old-i
    started before new-i, interleaved, unless a text sets started_utc.
    Returns (exit code, parsed result or None)."""
    args = []
    for label, texts in (("old", old), ("new", new)):
        args.append(f"--{label}")
        for i, text in enumerate(texts, 1):
            path = tmp_path / f"{label}-{i}.csv"
            path.write_text(text, encoding="utf-8")
            args.append(str(path))
    code = cli.main(["compare", *args, *flags, "--json"])
    out = capsys.readouterr().out
    return code, json.loads(out) if out else None


def runs(values, start, **kw):
    """One run per value of `values`, each through alike() unless it is a
    dict of rows already; started `start` minutes past the hour, two apart."""
    texts = []
    for i, value in enumerate(values):
        rows = value if isinstance(value, dict) else alike(value)
        texts.append(run_text(rows, run_id=f"r{start}{i}",
                              **{"started_utc": f"2026-10-26T12:{start + 2 * i:02d}:00Z", **kw}))
    return texts


def old(values, **kw):
    return runs(values, 0, **kw)


def new(values, **kw):
    return runs(values, 1, **kw)


def verdicts(result):
    return {(m["category"], m["name"], m["statistic"]): m["verdict"]
            for m in result["result"]["measures"]}


def test_same_build_and_known_slowdown(capsys, tmp_path):
    """INV-30: two sets from one build report no difference; a known
    slowdown is reported, and named in the verdict sentence (S4)."""
    code, result = compare(capsys, tmp_path, old([10.0, 10.01, 10.02]), new([10.01, 10.02, 10.03]))
    assert (code, result["verdict"]) == (0, "pass")
    assert set(verdicts(result).values()) == {"unchanged"}
    assert len(verdicts(result)) == 8  # wall median and p99, two spans, sim, opaque, two remainders

    code, result = compare(capsys, tmp_path, old([10.0, 10.01, 10.02]), new([11.0, 11.01, 11.02]))
    assert (code, result["verdict"]) == (1, "fail")
    judged = verdicts(result)
    assert judged.pop(("gpu", "opaque", "median")) == "slower"
    assert judged.pop(("gpu", "gpu_remainder", "median")) == "faster"
    assert set(judged.values()) == {"unchanged"}
    opaque = next(m for m in result["result"]["measures"] if m["name"] == "opaque")
    assert opaque["change_ms"] == 1.0
    assert any("gpu/opaque" in s and "slower" in s for s in result["summary"])


def test_pass_judged_by_own_spread(capsys, tmp_path):
    """INV-31: a pass that moved is found though the frame total is too
    noisy to judge (S16); a noisy total alone is inconclusive, unless its
    segment kind has under 100 measured frames."""
    def sets(old_opaque, new_opaque, frames=120):
        def make(walls, opaques, start):
            return [run_text(alike(o, wall=w, gpu_span=25.0), frames=frames, run_id=f"r{start}{i}",
                             started_utc=f"2026-10-26T12:{start + 2 * i:02d}:00Z")
                    for i, (w, o) in enumerate(zip(walls, opaques, strict=True))]
        return make([24.9, 28.0, 32.6], old_opaque, 0), make([25.9, 29.0, 33.6], new_opaque, 1)

    code, result = compare(capsys, tmp_path, *sets([18.2, 18.25, 18.3], [19.5, 19.55, 19.6]))
    assert (code, result["verdict"]) == (1, "fail")
    assert verdicts(result)[("gpu", "opaque", "median")] == "slower"
    wall = next(m for m in result["result"]["measures"]
                if m["name"] == "wall" and m["statistic"] == "median")
    assert (wall["verdict"], wall["change_ms"], wall["spread_ms"], wall["floor_ms"]) == \
        ("noisy", 1.0, 7.7, 0.84)

    code, result = compare(capsys, tmp_path, *sets([18.2, 18.25, 18.3], [18.2, 18.25, 18.3]))
    assert (code, result["verdict"]) == (2, "inconclusive")

    code, result = compare(capsys, tmp_path, *sets([18.2, 18.25, 18.3], [18.2, 18.25, 18.3], 100))
    assert (code, result["verdict"]) == (0, "pass")
    assert any("view" in s and "100" in s for s in result["summary"])


def test_floor(capsys, tmp_path):
    """INV-32: a change beyond the spread but under the floor is unchanged;
    gpu_tick_ns raises the floor of gpu passes and frame/gpu_span."""
    code, result = compare(capsys, tmp_path, old([10.0] * 3), new([10.04] * 3))
    assert code == 0 and verdicts(result)[("gpu", "opaque", "median")] == "unchanged"
    flags = ("--min-ms", "0.010", "--min-pct", "0")
    code, result = compare(capsys, tmp_path, old([10.0] * 3), new([10.04] * 3), *flags)
    assert code == 1 and verdicts(result)[("gpu", "opaque", "median")] == "slower"

    ticked = old([10.0] * 3)
    ticked[0] = ticked[0].replace('"schema": 1', '"schema": 1, "gpu_tick_ns": 100000')
    code, result = compare(capsys, tmp_path, ticked, new([10.04] * 3), *flags)
    assert code == 0 and verdicts(result)[("gpu", "opaque", "median")] == "unchanged"

    span = new([alike(10.0, gpu_span=12.04)] * 3)
    code, result = compare(capsys, tmp_path, old([10.0] * 3), span, *flags)
    assert verdicts(result)[("frame", "gpu_span", "median")] == "slower"
    code, result = compare(capsys, tmp_path, ticked, span, *flags)
    assert verdicts(result)[("frame", "gpu_span", "median")] == "unchanged"


def test_refusal_and_override(capsys, tmp_path):
    """INV-33: a compare-blocking field that differs refuses (exit 3);
    an override with a reason allows it and is named first (S5)."""
    same = [10.0, 10.01, 10.02]
    wide = new(same)
    wide[1] = wide[1].replace('"resolution": [1920, 1080]', '"resolution": [2560, 1440]')
    code, result = compare(capsys, tmp_path, old(same), wide)
    assert (code, result["verdict"]) == (3, "error")
    assert result["result"]["refused"] == [{"field": "resolution", "values": {
        "old-1": [1920, 1080], "old-2": [1920, 1080], "old-3": [1920, 1080],
        "new-1": [1920, 1080], "new-2": [2560, 1440], "new-3": [1920, 1080]}}]
    assert "resolution" in result["summary"][0] and "--override" in result["summary"][0]

    override = ("--override", "resolution=upscaler test")
    code, result = compare(capsys, tmp_path, old(same), wide, *override)
    assert (code, result["overrides"]) == (0, [{"field": "resolution", "reason": "upscaler test"}])
    assert "resolution" in result["summary"][0] and "upscaler test" in result["summary"][0]

    code, result = compare(capsys, tmp_path, old(same), new(same), *override)
    assert code == 0 and "upscaler test" in result["summary"][0]
    assert "override_unused" in {w["code"] for w in result["warnings"]}

    scaled = list(wide)
    scaled[0] = scaled[0].replace('"render_scale": 1.0', '"render_scale": 0.5')
    code, result = compare(capsys, tmp_path, old(same), scaled, *override)
    assert code == 3 and "upscaler test" in result["summary"][0]
    assert "render_scale" in result["summary"][1]

    for field, changed in (("inputs", {"inputs": []}), ("vsync", {"vsync": True}),
                           ("scene", {"scene": "nave"})):
        if field == "inputs":
            sets = old(same, **changed), new(same, **changed)
        else:
            sets = old(same), new(same, **changed)
        code, result = compare(capsys, tmp_path, *sets)
        assert code == 3 and [r["field"] for r in result["result"]["refused"]] == [field]

    for bad in ("pipelined=x", "resolution="):
        assert compare(capsys, tmp_path, old(same), new(same), "--override", bad)[0] == 3


def test_incomplete_run(capsys, tmp_path):
    """INV-34: dropped rows or a missing close line make the compare
    inconclusive, whatever the measures say, and the first sentence says so."""
    slow = new([11.0, 11.01, 11.02])
    slow[0] = slow[0].replace('"rows_dropped":0', '"rows_dropped":3')
    code, result = compare(capsys, tmp_path, old([10.0, 10.01, 10.02]), slow)
    assert (code, result["verdict"]) == (2, "inconclusive")
    assert "new-1" in result["summary"][0] and "3 rows" in result["summary"][0]

    unclosed = old([10.0, 10.01, 10.02])
    unclosed[1] = unclosed[1].rsplit("# frameledger-close", 1)[0]
    code, result = compare(capsys, tmp_path, unclosed, new([11.0, 11.01, 11.02]))
    assert (code, result["verdict"]) == (2, "inconclusive")
    assert "old-2" in result["summary"][0]


def test_interleaving(capsys, tmp_path):
    """INV-35: not_interleaved warns when one set ran wholly before the
    other, judged on started_utc, and changes no verdict."""
    same = [10.0, 10.01, 10.02]
    code, result = compare(capsys, tmp_path, old(same), new(same))
    assert code == 0 and "not_interleaved" not in {w["code"] for w in result["warnings"]}

    later = [text.replace("T12:", "T13:") for text in new(same)]
    code, result = compare(capsys, tmp_path, old(same), later)
    assert code == 0 and "not_interleaved" in {w["code"] for w in result["warnings"]}

    # Given in an order that looks sequential, started interleaved: no warning.
    code, result = compare(capsys, tmp_path, old(same)[::-1], new(same)[::-1])
    assert "not_interleaved" not in {w["code"] for w in result["warnings"]}


def test_runs_and_unmatched(capsys, tmp_path):
    """INV-36: a set of two runs exits 3; a measure some runs lack is
    listed in unmatched and judged nowhere."""
    assert compare(capsys, tmp_path, old([10.0, 10.01]), new([10.0, 10.01, 10.02]))[0] == 3

    extra = new([10.0, 10.01, {**alike(10.02), ("gpu", "bloom"): 1.0}])
    code, result = compare(capsys, tmp_path, old([10.0, 10.01, 10.02]), extra)
    assert code == 0
    assert result["result"]["unmatched"] == [{"segment_kind": "view", "category": "gpu",
                                              "name": "bloom", "depth": 0, "statistic": "median",
                                              "present_in": ["new-3"]}]
    assert ("gpu", "bloom", "median") not in verdicts(result)


def test_static_diff(capsys, tmp_path):
    """INV-37: the static diff lists each dotted key that differs, with every
    run's exact string, and no key that is the same in all."""
    static = {"pipelines": {"opaque": {"vgprs": "64", "waves": "8"}}, "draws": "120"}
    changed = {"pipelines": {"opaque": {"vgprs": "72", "waves": "8"}}, "draws": "120"}
    sets = old([10.0] * 3, static=static), new([10.0] * 3, static=static)
    sets[1][1] = sets[1][1].replace(json.dumps(static), json.dumps(changed))
    code, result = compare(capsys, tmp_path, *sets)
    values = {f"{s}-{i}": "64" for s in ("old", "new") for i in (1, 2, 3)}
    assert result["result"]["static_diff"] == [{"key": "pipelines.opaque.vgprs",
                                                "values": {**values, "new-2": "72"}}]


@pytest.mark.parametrize("opaque", [[10.01, 10.02, 10.03], [11.0, 11.01, 11.02]])
def test_text_matches_json(capsys, tmp_path, opaque):
    """INV-13 for compare: the text opens with the JSON summary, and no
    table line is wider than 100 columns."""
    sets = old([10.0, 10.01, 10.02]), new(opaque)
    code, result = compare(capsys, tmp_path, *sets)
    paths = sorted(str(p) for p in tmp_path.glob("*.csv"))
    args = ["compare", "--old", *[p for p in paths if "old-" in p],
            "--new", *[p for p in paths if "new-" in p]]
    assert cli.main(args) == code
    text = capsys.readouterr().out.splitlines()
    assert text[: len(result["summary"])] == result["summary"]
    body = text[len(result["summary"]):]
    assert body and all(len(line) <= 100 for line in body), max(body, key=len)


def test_short_kind_missing_from_the_first_run(capsys, tmp_path):
    """A segment kind absent from one run has 0 frames there, so it is named
    as short even when the run lacking it comes first (UT Ants' review)."""
    same = [10.0, 10.01, 10.02]
    first = old(same)[:1] + old(same, spots=150)[1:]
    code, result = compare(capsys, tmp_path, first, new(same, spots=150))
    assert result["verdict"] == "pass"
    assert any("spot" in s and "fewer than 100" in s for s in result["summary"])


# DOOM Ants' review found rules whose removal no test above noticed; each
# test below pins one at its edge.

def opaque_verdict(result):
    return verdicts(result)[("gpu", "opaque", "median")]


def test_spread_is_the_wider_set(capsys, tmp_path):
    """INV-31's rule, asymmetric: the spread is the larger range, whichever
    set holds it. A change of 1.000 within a range of 1.600 is noisy."""
    code, result = compare(capsys, tmp_path, old([10.0] * 3), new([10.4, 11.0, 12.0]))
    assert opaque_verdict(result) == "noisy"
    code, result = compare(capsys, tmp_path, old([9.0, 10.0, 10.6]), new([11.0] * 3))
    assert opaque_verdict(result) == "noisy"


def test_verdict_edges(capsys, tmp_path):
    """§ 4.10's table at its edges, with a floor of 0.100: a change equal to
    the spread is not slower; a change equal to the floor is; a spread
    equal to the floor is noisy."""
    flags = ("--min-ms", "0.100", "--min-pct", "0")
    _, result = compare(capsys, tmp_path, old([10.0, 10.0, 10.2]), new([10.2] * 3), *flags)
    assert opaque_verdict(result) == "noisy"
    _, result = compare(capsys, tmp_path, old([10.0] * 3), new([10.1] * 3), *flags)
    assert opaque_verdict(result) == "slower"
    _, result = compare(capsys, tmp_path, old([10.0, 10.0, 10.1]), new([10.0] * 3), *flags)
    assert opaque_verdict(result) == "noisy"


def test_even_sets_and_rounding(capsys, tmp_path):
    """An even set's centre is the mean of its two middle runs, and JSON
    rounds half away from zero: a change of -0.0005 ms on 10.000 ms is
    -0.005%, which is -0.01, not 0."""
    _, result = compare(capsys, tmp_path, old([10.0] * 4), new([9.999, 10.0, 9.999, 10.0]))
    opaque = next(m for m in result["result"]["measures"] if m["name"] == "opaque")
    assert (opaque["new_centre_ms"], opaque["change_ms"], opaque["change_pct"]) == (9.9995, -0.0005, -0.01)


def test_largest_slower_measure_is_named(capsys, tmp_path):
    """The verdict sentence names the slower measure with the largest change
    in ms, ties by percent."""
    def with_sim(opaque, sim):
        return {**alike(opaque), ("cpu", "sim"): sim}
    tie = new([with_sim(11.0, 6.0)] * 3)  # both 1.000 ms: sim is 20%, opaque 10%
    _, result = compare(capsys, tmp_path, old([10.0] * 3), tie)
    assert "the largest is cpu/sim median" in " ".join(result["summary"])
    ms_first = new([with_sim(12.0, 6.5)] * 3)  # opaque 2.000 ms at 20%, sim 1.500 at 30%
    _, result = compare(capsys, tmp_path, old([10.0] * 3), ms_first)
    assert "the largest is gpu/opaque median" in " ".join(result["summary"])


def test_header_matching(capsys, tmp_path):
    """Inputs match in any order; an absent optional field matches only
    another absent one."""
    same = [10.0, 10.01, 10.02]
    two = [{"name": "a", "hash": "md5:" + "1" * 32, "bytes": 1},
           {"name": "b", "hash": "md5:" + "2" * 32, "bytes": 2}]
    code, _ = compare(capsys, tmp_path, old(same, inputs=two), new(same, inputs=two[::-1]))
    assert code == 0
    tiered = new(same)
    tiered[1] = tiered[1].replace('"schema": 1', '"schema": 1, "tier": "high"')
    code, result = compare(capsys, tmp_path, old(same), tiered)
    assert code == 3 and [r["field"] for r in result["result"]["refused"]] == ["tier"]


def test_set_warnings(capsys, tmp_path):
    """not_interleaved fires whichever set ran first; mixed_build fires when
    a set's runs differ in commit."""
    same = [10.0, 10.01, 10.02]
    earlier = [text.replace("T12:", "T11:") for text in new(same)]
    _, result = compare(capsys, tmp_path, old(same), earlier)
    assert "not_interleaved" in {w["code"] for w in result["warnings"]}
    mixed = old(same)
    mixed[1] = mixed[1].replace('"commit": "abc123"', '"commit": "def456"')
    _, result = compare(capsys, tmp_path, mixed, new(same))
    assert "mixed_build" in {w["code"] for w in result["warnings"]}


def test_overrides_stay_first(capsys, tmp_path):
    """S5: the overrides sentence opens the report beside an incomplete run,
    a refusal and an unreadable file; a repeated override exits 3."""
    override = ("--override", "resolution=upscaler test")
    slow = new([11.0, 11.01, 11.02])
    slow[0] = slow[0].replace('"rows_dropped":0', '"rows_dropped":3')
    code, result = compare(capsys, tmp_path, old([10.0, 10.01, 10.02]), slow, *override)
    assert code == 2 and "upscaler test" in result["summary"][0] and "new-1" in result["summary"][1]

    same = [10.0, 10.01, 10.02]
    _, result = compare(capsys, tmp_path, old(same), new(same, vsync=True), *override)
    assert "upscaler test" in result["summary"][0] and "vsync" in result["summary"][1]
    assert any("override_unused" not in s and "resolution was given" in s for s in result["summary"][2:])

    paths = [str(tmp_path / "missing.csv")] * 3
    code = cli.main(["compare", "--old", *paths, "--new", *paths, *override, "--json"])
    result = json.loads(capsys.readouterr().out)
    assert code == 3 and "upscaler test" in result["summary"][0]
    assert result["overrides"] == [{"field": "resolution", "reason": "upscaler test"}]

    twice = (*override, "--override", "resolution=again")
    assert compare(capsys, tmp_path, old(same), new(same), *twice)[0] == 3


# Vestige's review.

def test_equal_numbers_match(capsys, tmp_path):
    """A header number matches by value: render_scale 1 and 1.0 are one
    scale, not a refusal."""
    same = [10.0, 10.01, 10.02]
    whole = [text.replace('"render_scale": 1.0', '"render_scale": 1') for text in new(same)]
    code, result = compare(capsys, tmp_path, old(same), whole)
    assert code == 0, result["summary"]


def test_zero_floor(capsys, tmp_path):
    """With a floor of 0, runs that do not vary are unchanged, not noisy, so
    identical sets pass; any change beyond a spread of 0 is slower."""
    flags = ("--min-ms", "0", "--min-pct", "0")
    code, result = compare(capsys, tmp_path, old([10.0] * 3), new([10.0] * 3), *flags)
    assert code == 0 and set(verdicts(result).values()) == {"unchanged"}
    code, result = compare(capsys, tmp_path, old([10.0] * 3), new([10.001] * 3), *flags)
    assert code == 1 and opaque_verdict(result) == "slower"
