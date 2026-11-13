"""`compare --base … --variant NAME …` and `alternate`'s form of it:
named variants, each judged against one base (S23).

Invariants from docs/specs/FLED-0001-run-file-format.md § 5: INV-89 to
INV-94, the rules of § 4.16. Every frame of a run carries the same rows
within a segment, so a measure's per-run value is the value written.
"""

import json
import re

import pytest

import cli
import ledger
from test_alternate import Bench, analyser, without_added
from test_compare_scenes import Files

LACKS_NAMED = "none of its runs has a named measure"


def rows(x: float | None = 5.0, wall: float = 16.0) -> dict:
    """One frame's rows: every measure fixed but gpu/x and the wall. With
    x None the frame has no gpu/x."""
    frame = {("frame", "wall"): wall, ("frame", "cpu_span"): 8.0, ("frame", "gpu_span"): 12.0,
             ("cpu", "sim"): 5.0}
    return frame if x is None else {**frame, ("gpu", "x"): x}


def side(files: Files, xs: list, **header) -> list[str]:
    """One run in view:1 per value of `xs`, the gpu/x median."""
    return [files.run("atrium", {"view:1": rows(x)}, **header) for x in xs]


def flags(base: list[str], variants: dict[str, list[str]]) -> list[str]:
    args = ["--base", *base]
    for name, paths in variants.items():
        args += ["--variant", name, *paths]
    return args


def against_base(capsys, base: list[str], variants: dict[str, list[str]], *more: str) -> tuple[int, dict]:
    code = cli.main(["compare", *flags(base, variants), *more, "--json"])
    out = json.loads(capsys.readouterr().out)
    assert out["exit_code"] == code
    return code, out


def variant(out: dict, name: str) -> dict:
    return next(v for v in out["result"]["variants"] if v["name"] == name)


SAME, SLOWER = [5.0, 5.01, 5.02], [6.0, 6.01, 6.02]


def test_variant_is_one_compare(capsys, tmp_path):
    """INV-89: each variant's compare is `compare --old BASE --new
    VARIANT`'s result, but for the run names. Only b's runs are slower,
    so judging a's runs with them would fail a too."""
    files = Files(tmp_path)
    base = side(files, SAME)
    variants = {"a": side(files, SAME), "b": side(files, SLOWER)}
    code, out = against_base(capsys, base, variants)
    assert (code, out["verdict"]) == (1, "fail")
    assert (variant(out, "a")["verdict"], variant(out, "b")["verdict"]) == ("pass", "fail")
    for name, paths in variants.items():
        cli.main(["compare", "--old", *base, "--new", *paths, "--json"])
        plain = capsys.readouterr().out
        renamed = re.sub(r"\bnew-(\d+)\b", rf"{name}-\1", re.sub(r"\bold-(\d+)\b", r"base-\1", plain))
        plain_result = json.loads(renamed)["result"]
        assert plain_result.pop("baseline") is None  # the command's own key, § 4.17
        assert variant(out, name)["compare"] == plain_result
        assert [r["name"] for r in variant(out, name)["compare"]["runs"]] == [
            "base-1", "base-2", "base-3", f"{name}-1", f"{name}-2", f"{name}-3"]


FILES = ["f1", "f2", "f3"]  # never read: a setup error stops first


@pytest.mark.parametrize("args", [
    ["--base", *FILES, "--variant", "a", *FILES, "--old", *FILES],
    ["--base", *FILES, "--variant", "a", *FILES, "--new", *FILES],
    ["--base", *FILES, "--variant", "a", *FILES, "--by-scene"],
    ["--base", *FILES],
    ["--variant", "a", *FILES],
    ["--old", *FILES, "--new", *FILES, "--variant", "a", *FILES],
    *(["--base", *FILES, "--variant", name, *FILES] for name in ("base", "old", "new", "New", "a-b", "9a",
                                                                 "a" * 33, "")),
    ["--base", *FILES, "--variant", "a", *FILES, "--variant", "a", *FILES],
    ["--base", *FILES, "--variant", "a", "f1", "f2"],
    ["--base", *FILES, "--variant", "a"],
    ["--base", "f1", "f2", "--variant", "a", *FILES],
], ids=lambda args: " ".join(args)[:60])
def test_setup_errors(capsys, monkeypatch, args):
    """INV-90: each setup error is exit 3, before any file is read."""
    def read_nothing(path):
        raise AssertionError(f"{path} was read")
    monkeypatch.setattr(ledger, "read", read_nothing)
    assert cli.main(["compare", *args, "--json"]) == 3
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err.startswith("frameledger: ")


def test_longest_name_is_allowed(capsys, tmp_path):
    """INV-90's other side: 32 characters, digits and _ are a name."""
    files = Files(tmp_path)
    name = "a" * 29 + "_9z"
    code, out = against_base(capsys, side(files, SAME), {name: side(files, SAME)})
    assert code == 0 and variant(out, name)["verdict"] == "pass"


def test_refused_variant(capsys, tmp_path):
    """INV-91: a variant that cannot be compared with the base is
    unjudged, and never hides the others; a command that judged nothing
    is an error."""
    files = Files(tmp_path)
    base = side(files, SAME)
    refused = side(files, SAME, device="Other GPU")
    code, out = against_base(capsys, base, {"a": side(files, SAME), "b": refused})
    assert (code, out["verdict"]) == (2, "inconclusive")
    assert variant(out, "a")["verdict"] == "pass"
    b = variant(out, "b")
    assert b["verdict"] == "unjudged" and "device differs" in b["reason"]
    assert b["compare"]["refused"][0]["field"] == "device"
    assert any(s.startswith("b is unjudged: device differs") for s in out["summary"])

    code, out = against_base(capsys, base, {"a": side(files, SLOWER), "b": refused})
    assert (code, out["verdict"]) == (1, "fail")
    assert any(s.startswith("a is slower: the gpu/x median in view rose from 5.010 to 6.010 ms")
               for s in out["summary"])

    code, out = against_base(capsys, base, {"b": refused}, "--override", "vsync=a reason")
    assert (code, out["verdict"]) == (3, "error")
    assert out["summary"][0].startswith("Overrides given:")
    assert out["summary"][1].startswith("No variant could be judged: b (device differs")


def ranked_run(files: Files, x: float | None, view_wall: float, load_wall: float, **header) -> str:
    return files.run("atrium", {"view:1": (rows(x, view_wall), 300), "load:1": (rows(x, load_wall), 20)},
                     **header)


def test_rank(capsys, tmp_path):
    """INV-92: variants rank by the rank measure's change, lowest first,
    in the segment kind with the most base frames. b's wall falls most
    in load, the smaller kind; c is both slowest and failing, so ranking
    by size or by verdict would put it first."""
    files = Files(tmp_path)

    def runs(x, view_wall, load_wall, **header):
        return [ranked_run(files, x, view_wall, load_wall, **header) for _ in range(3)]

    base = runs(5.0, 16.0, 30.0)
    variants = {"c": runs(3.0, 16.5, 30.0), "b": runs(5.0, 15.7, 20.0), "a": runs(5.0, 14.8, 30.0),
                "d": runs(5.0, 10.0, 30.0, device="Other GPU")}
    code, out = against_base(capsys, base, variants)
    assert code == 1
    assert out["result"]["rank_measure"] == {"segment_kind": "view", "category": "frame", "name": "wall",
                                             "depth": 0, "statistic": "median"}
    assert [(v["name"], v["rank"]) for v in out["result"]["variants"]] == [
        ("a", 1), ("b", 2), ("c", 3), ("d", None)]
    assert [v["measure"]["change"] for v in out["result"]["variants"][:3]] == [-1.2, -0.3, 0.5]
    assert variant(out, "c")["verdict"] == "fail" and variant(out, "d")["measure"] is None
    assert "Ranked by the frame/wall median in view; base 16.000 ms." in out["summary"]

    del variants["d"]
    code, out = against_base(capsys, base, variants, "--measure", "gpu/x")
    assert code == 0
    assert out["result"]["rank_measure"]["name"] == "x"
    assert [(v["name"], v["rank"]) for v in out["result"]["variants"]] == [("c", 1), ("a", 2), ("b", 3)]

    # e's own runs lack gpu/x, which every base run has (Vestige).
    variants["e"] = runs(None, 16.0, 30.0)
    with_e, out = against_base(capsys, base, variants, "--measure", "gpu/x")
    e = variant(out, "e")
    assert (e["verdict"], e["reason"], e["rank"]) == ("unjudged", LACKS_NAMED, None)
    assert with_e == code and out["result"]["variants"][-1] is e
    assert out["result"]["judged"]["variants"] == 3


def deeper(x: float) -> dict:
    """rows(), with its gpu/x one level down: a pass inside another."""
    frame = rows(None)
    return {**frame, ("gpu", "x", 1): x}


def test_rank_measure_is_the_top_level_pass(capsys, tmp_path):
    """INV-92 (UT Ants): a pass at two depths ranks by the smallest. A
    frame holds a pass once, so view:1 has gpu/x at depth 0 and view:2,
    with more frames, at depth 1. At depth 0 a saves most; at depth 1 b
    does, so ranking by the deepest or the busiest would put b first."""
    files = Files(tmp_path)

    def runs(top, inner):
        return [files.run("atrium", {"view:1": rows(top), "view:2": (deeper(inner), 300)}) for _ in range(3)]

    variants = {"b": runs(4.8, 1.0), "a": runs(4.0, 3.0)}
    _, out = against_base(capsys, runs(5.0, 2.0), variants, "--measure", "gpu/x")
    assert out["result"]["rank_measure"]["depth"] == 0
    assert [(v["name"], v["rank"], v["measure"]["depth"]) for v in out["result"]["variants"]] == [
        ("a", 1, 0), ("b", 2, 0)]


def test_rank_measure_kind_is_chosen_at_that_depth(capsys, tmp_path):
    """INV-92 (UT Ants): the kind is the busiest among the kinds that have
    the measure at the smallest depth, so 20 load frames at depth 0 beat
    300 view frames at depth 1; and kinds with equal frames tie as text."""
    files = Files(tmp_path)
    runs = [files.run("atrium", {"load:1": (rows(), 20), "view:1": (deeper(2.0), 300)}) for _ in range(6)]
    _, out = against_base(capsys, runs[:3], {"a": runs[3:]}, "--measure", "gpu/x")
    assert (out["result"]["rank_measure"]["segment_kind"], out["result"]["rank_measure"]["depth"]) == ("load", 0)

    runs = [files.run("atrium", {"view:1": rows(), "load:1": rows()}) for _ in range(6)]
    _, out = against_base(capsys, runs[:3], {"a": runs[3:]}, "--measure", "gpu/x")
    assert out["result"]["rank_measure"]["segment_kind"] == "load"  # as many frames each: "load" < "view"


def test_rank_ties_go_by_name(capsys, tmp_path):
    """INV-92: variants with the same change rank by name, not by the
    order given."""
    files = Files(tmp_path)
    _, out = against_base(capsys, side(files, SAME), {"b": side(files, SAME), "a": side(files, SAME)})
    assert [(v["name"], v["rank"]) for v in out["result"]["variants"]] == [("a", 1), ("b", 2)]


def test_unranked_and_absent_measures(capsys, tmp_path):
    """§ 4.16: with no base run holding the rank measure nothing is
    ranked; a named measure in no run of any side is an error."""
    files = Files(tmp_path)
    base = [files.run("atrium", {"view:1": rows(None)}) for _ in range(3)]
    variants = {"a": side(files, SAME)}
    code, out = against_base(capsys, base, variants, "--measure", "gpu/x", "--measure", "cpu/sim")
    assert code == 0  # cpu/sim is judged; gpu/x is in no base run
    assert out["result"]["rank_measure"] is None and variant(out, "a")["rank"] is None
    assert "Nothing is ranked: no base run has gpu/x." in out["summary"]

    code, out = against_base(capsys, base, variants, "--measure", "gpu/nothing")
    assert (code, out["verdict"]) == (3, "error")
    assert out["summary"] == ["No run has gpu/nothing, so it cannot be judged; a name matches exactly, "
                              "case included."]


def test_named_measure_only_a_refused_variant_has(capsys, tmp_path):
    """§ 4.16's step 2 (DOOM Ants): a named measure is absent only when no
    run of any side has it, a refused variant's runs included. Here only
    r's runs have gpu/x, and r is refused, so the steps after 2 decide."""
    files = Files(tmp_path)
    base = side(files, [None] * 3)
    variants = {"a": side(files, [None] * 3), "r": side(files, SAME, device="Other GPU")}
    code, out = against_base(capsys, base, variants, "--measure", "gpu/x", "--measure", "cpu/sim")
    assert (code, out["verdict"]) == (2, "inconclusive")  # a passes on cpu/sim; r is unjudged
    assert variant(out, "a")["verdict"] == "pass"

    code, out = against_base(capsys, base, variants, "--measure", "gpu/x")
    assert (code, out["verdict"]) == (3, "error")
    assert out["summary"][1].startswith(f"No variant could be judged: a ({LACKS_NAMED}), r (device differs")


def test_every_variant_lacks_the_named_measure(capsys, tmp_path):
    """§ 4.16's step 3: the base has gpu/x and no variant does, so no
    variant is judged."""
    files = Files(tmp_path)
    variants = {"a": side(files, [None] * 3), "b": side(files, [None] * 3)}
    code, out = against_base(capsys, side(files, SAME), variants, "--measure", "gpu/x")
    assert (code, out["verdict"]) == (3, "error")
    assert out["summary"][1] == f"No variant could be judged: a ({LACKS_NAMED}), b ({LACKS_NAMED})."


def test_inconclusive_variant(capsys, tmp_path):
    """§ 4.16's step 5: one inconclusive variant makes the command
    inconclusive, and its sentence gives § 4.10's reason."""
    files = Files(tmp_path)
    unfinished = side(files, SAME)
    text = open(unfinished[0], encoding="utf-8").read()
    open(unfinished[0], "w", encoding="utf-8").write(text[:text.index("# frameledger-close")])
    code, out = against_base(capsys, side(files, SAME), {"a": side(files, SAME), "b": unfinished})
    assert (code, out["verdict"]) == (2, "inconclusive")
    assert (variant(out, "a")["verdict"], variant(out, "b")["verdict"]) == ("pass", "inconclusive")
    assert any(s.startswith("b is inconclusive: ") for s in out["summary"])


def test_compare_bad_variant_file(capsys, tmp_path):
    """§ 4.16: under `compare` the files were named one by one, so a
    variant file that breaks the format is exit 3, whatever the others
    hold. `alternate`'s other rule is test_alternate_variants_bad_file."""
    files = Files(tmp_path)
    broken = side(files, SAME)
    open(broken[1], "w", encoding="utf-8").close()
    code, out = against_base(capsys, side(files, SAME), {"a": side(files, SAME), "b": broken})
    assert (code, out["verdict"]) == (3, "error")
    assert broken[1] in out["summary"][0] and out["result"] == {}


def test_override_unused_is_said_once(capsys, tmp_path):
    """§ 4.16: `override_unused` is given once, and only when the field
    differs in no variant."""
    files = Files(tmp_path)
    base = side(files, SAME)
    variants = {"a": side(files, SAME), "b": side(files, SAME)}
    code, out = against_base(capsys, base, variants, "--override", "device=a reason")
    assert code == 0 and [w["code"] for w in out["warnings"]].count("override_unused") == 1

    variants["c"] = side(files, SAME, device="Other GPU")  # now the override is used, by c alone
    code, out = against_base(capsys, base, variants, "--override", "device=a reason")
    assert code == 0 and "override_unused" not in [w["code"] for w in out["warnings"]]


def test_set_warnings_name_the_sides(capsys, tmp_path):
    """§ 4.16 and INV-93 (UT Ants, DOOM Ants): a warning about the base
    runs as a set is given once, not once per variant; a variant's own
    opens with its name and calls the set "the b runs"."""
    files = Files(tmp_path)
    base = [*side(files, SAME[:2]), *side(files, SAME[2:], commit="def456")]
    variants = {"a": side(files, SAME), "b": [*side(files, SAME[:2]), *side(files, SAME[2:], commit="def456")]}
    code, out = against_base(capsys, base, variants)
    assert code == 0
    assert [w["message"].partition(" differ")[0] for w in out["warnings"] if w["code"] == "mixed_build"] == [
        "the base runs", "b: the b runs"]
    assert len([s for s in out["summary"] if "differ in commit" in s]) == 2


def test_judged_count(capsys, tmp_path):
    """INV-93: only judged variants are counted, the text says how many,
    and a base run's own warning is given once, not once per variant."""
    files = Files(tmp_path)
    base = [*side(files, SAME[:2]), *side(files, SAME[2:], settled_frames=1, settling_frames=5)]
    variants = {"a": side(files, SAME), "b": side(files, SAME, device="Other GPU")}
    for judged in (1, 2):
        code, out = against_base(capsys, base, variants)
        assert code == 2
        measures = sum(len(variant(out, name)["compare"]["measures"]) for name in ("a", "c")[:judged])
        assert out["result"]["judged"] == {"variants": judged, "measures": measures}
        assert measures == judged * len(variant(out, "a")["compare"]["measures"]) > 0
        counted = "1 variant" if judged == 1 else "2 variants"
        assert any(s.startswith(f"Judged {counted} and {measures} measures;") for s in out["summary"])
        assert len([w for w in out["warnings"] if w["code"] == "settling_short"]) == 1
        warned = [s for s in out["summary"] if "settled_frames" in s]
        assert len(warned) == 1 and warned[0].startswith("Warning: base-3: ")
        variants["c"] = side(files, SAME)  # a second judged variant shares the base run's warning


LOADED = {"load": {"start": 0.1, "end": 0.1, "peak": 0.9}}


def test_run_under_load_is_named(capsys, tmp_path):
    """§ 4.16 (Vestige): a run taken under load is named with its peak, as
    § 4.10 names it; a base run's once, though it makes every variant
    inconclusive."""
    files = Files(tmp_path)
    base = side(files, SAME)
    variants = {"a": [*side(files, SAME[:2]), *side(files, SAME[2:], **LOADED)], "b": side(files, SAME)}
    code, out = against_base(capsys, base, variants)
    assert code == 2 and variant(out, "a")["verdict"] == "inconclusive"
    assert [s for s in out["summary"] if "under load:" in s] == [
        "a-3 was taken under load: load.peak 0.9, above 0.25."]

    code, out = against_base(capsys, [*base[:2], *side(files, SAME[2:], **LOADED)], variants)
    assert code == 2 and variant(out, "b")["verdict"] == "inconclusive"
    assert [s for s in out["summary"] if "under load:" in s] == [
        "base-3 was taken under load: load.peak 0.9, above 0.25.",
        "a-3 was taken under load: load.peak 0.9, above 0.25."]


def test_left_out_variant_keeps_its_warnings(capsys, tmp_path):
    """§ 4.16 (Vestige): a variant unjudged for lacking the named measure
    still gives its runs' warnings."""
    files = Files(tmp_path)
    lacking = [*side(files, [None] * 2), *side(files, [None], settled_frames=1, settling_frames=5)]
    code, out = against_base(capsys, side(files, SAME), {"a": side(files, SAME), "e": lacking},
                             "--measure", "gpu/x")
    assert code == 0 and variant(out, "e")["reason"] == LACKS_NAMED
    assert [w["message"].partition(":")[0] for w in out["warnings"] if w["code"] == "settling_short"] == ["e-3"]


def test_rank_measure_in_some_base_runs(capsys, tmp_path):
    """§ 4.16 (Vestige): with the rank measure in two of three base runs,
    no variant has a rank entry, and the text says why, not a base figure."""
    files = Files(tmp_path)
    base = [*side(files, SAME[:2]), *side(files, [None])]
    _, out = against_base(capsys, base, {"a": side(files, SAME)}, "--measure", "gpu/x", "--measure", "cpu/sim")
    assert variant(out, "a")["rank"] is None
    assert "Nothing is ranked: not every base run has the gpu/x median in view." in out["summary"]
    assert not any(s.startswith("Ranked by") for s in out["summary"])


def test_text_table(capsys, tmp_path):
    """§ 4.16's text: every variant in one table, within 100 columns."""
    files = Files(tmp_path)
    variants = {"no_bloom": side(files, SAME), "z" * 32: side(files, SAME, device="Other GPU")}
    cli.main(["compare", *flags(side(files, SAME), variants)])
    text = capsys.readouterr().out.splitlines()
    table = text[text.index("Variants, the largest saving first:"):]
    assert table[1].split() == ["rank", "variant", "verdict", "median", "ms", "change", "ms", "change", "%", "measure"]
    assert table[2].split() == ["1", "no_bloom", "pass", "16.000", "+0.000", "+0.00%", "unchanged"]
    assert table[3].split()[0] == "-" and table[3].split()[2:] == ["unjudged", "-", "-", "-", "-"]
    assert max(map(len, text[text.index(""):])) <= 100
    assert table[3].split()[1] == "z" * 32  # the longest name is shown whole


def test_markdown_table(capsys, tmp_path):
    """§ 4.16's table under --markdown: one row a variant, the same cells."""
    files = Files(tmp_path)
    cli.main(["compare", *flags(side(files, SAME), {"no_bloom": side(files, SAME)}), "--markdown"])
    text = capsys.readouterr().out.splitlines()
    cells = [[cell.strip() for cell in line.strip("|").split("|")] for line in text if line.startswith("|")]
    assert cells[0] == ["rank", "variant", "verdict", "median ms", "change ms", "change %", "measure"]
    assert cells[2] == ["1", "no_bloom", "pass", "16.000", "+0.000", "+0.00%", "unchanged"]


class VariantBench(Bench):
    """Bench with a base and variants a and b, all the same build."""

    def __init__(self, tmp_path):
        super().__init__(tmp_path)
        for name in ("base", "a", "b"):
            self.sources[name] = self.sources["old"]

    def args(self, *flags: str, sides=("base", "a", "b")) -> list[str]:
        args = ["alternate", "--out", str(self.out), "--runs", "3", *flags]
        for name in sides:
            args += ["--base" if name == "base" else "--variant", *([] if name == "base" else [name]),
                     self.command(name)]
        return args


def test_alternate_variants(tmp_path):
    """INV-94: every side runs in rounds that reverse, each run into its
    own file, and the files are judged as `compare --base` judges them."""
    bench = VariantBench(tmp_path)
    done = analyser(bench.args("--json"))
    out = json.loads(done.stdout)
    assert bench.order() == ["base", "a", "b", "b", "a", "base", "base", "a", "b"]
    names = [f"{name}-{n}" for name in ("a", "b", "base") for n in (1, 2, 3)]
    assert bench.files() == [f"{name}.csv" for name in names]
    paths = {name: [str(bench.out / f"{name}-{n}.csv") for n in (1, 2, 3)] for name in ("base", "a", "b")}
    plain = analyser(["compare", *flags(paths.pop("base"), paths), "--json"])
    assert without_added(out) == without_added(json.loads(plain.stdout))
    assert done.returncode == plain.returncode == 0
    assert out["command"] == "alternate" and out["result"]["stopped"] is None
    assert list(out["result"]["commands"]) == ["base", "a", "b"]


def test_alternate_variants_warm_up_in_order(tmp_path):
    """INV-94: a warm-up round runs the base, then each variant in order."""
    bench = VariantBench(tmp_path)
    assert analyser(bench.args("--warmup", "1")).returncode == 0
    assert bench.order()[:6] == ["base", "a", "b", "base", "a", "b"]
    assert "base-warmup-1.csv" in bench.files() and "b-warmup-1.csv" in bench.files()


def test_alternate_variants_setup_errors(tmp_path):
    """INV-94: a setup error runs no command."""
    bench = VariantBench(tmp_path)
    no_placeholder = [*bench.args(sides=("base", "a")), "--variant", "b", "true"]
    for args in ([*bench.args(), "--old", bench.command("old")], [*bench.args(), "--new", bench.command("new")],
                 no_placeholder, bench.args(sides=("base",)), bench.args(sides=("a",)),
                 [*bench.args(sides=("base", "a")), "--variant", "a", bench.command("a")],
                 [*bench.args(sides=("base", "a")), "--variant", "old", bench.command("a")],
                 [*bench.args(sides=("base", "a")), "--variant", "A", bench.command("a")]):
        done = analyser(args)
        assert done.returncode == 3 and done.stdout == ""
        assert bench.order() == [] and bench.files() == []
    assert "--variant b must hold {run}" in analyser(no_placeholder).stderr


@pytest.mark.parametrize("empty, code", [("b-2", 2), ("base-2", 3)])
def test_alternate_variants_bad_file(tmp_path, empty, code):
    """INV-94 (DOOM Ants): one broken variant file loses that variant
    alone; a broken base file is an error. Every run still runs."""
    bench = VariantBench(tmp_path)
    done = analyser(bench.args("--json"), env={"FAKE_ENGINE": f"{empty}=empty"})
    out = json.loads(done.stdout)
    assert len(bench.order()) == 9 and done.returncode == code
    if empty == "base-2":
        assert out["verdict"] == "error" and "base-2.csv" in out["summary"][0]
        return
    b = variant(out, "b")
    assert b["verdict"] == "unjudged" and "b-2.csv" in b["reason"] and b["compare"] is None
    assert variant(out, "a")["verdict"] == "pass"



def test_base_outlier_is_named_once(capsys, tmp_path):
    """INV-109: a base run that stands apart is named once, without a
    variant's name before it, though every variant's compare finds it
    (DOOM Ants)."""
    files = Files(tmp_path)

    def walls(*values: float) -> list[str]:
        return [files.run("atrium", {"view:1": rows(wall=wall)}) for wall in values]

    code, out = against_base(capsys, walls(16.0, 16.1, 20.0),
                             {"a": walls(16.0, 16.05, 16.1), "b": walls(16.0, 16.05, 16.1)})
    assert code == 2
    found = [w["message"] for w in out["warnings"] if w["code"] == "outlier_run"]
    assert len(found) == 1 and found[0].startswith("base-3 stands apart from the other base runs: ")
    assert sum("stands apart" in s for s in out["summary"]) == 1
