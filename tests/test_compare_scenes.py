"""`compare --by-scene`: each scene's old runs against its new (S15).

Invariants from docs/specs/FLED-0001-run-file-format.md § 5: INV-73 to
INV-77, the rules of § 4.14. Every frame of a run carries the same rows
within a segment, so a measure's per-run value is the value written.
"""

import json

import cli
from test_compare import HEADER, alike

FRAMES = 120  # per segment: above § 4.10's 100, so a noisy wall can make a scene inconclusive


def run_text(scene: str, run_id: str, started: str, segments: dict, **header) -> str:
    """A run of `scene`: for each segment, FRAMES frames (or the count
    given with its rows, as (rows, frames)) carrying its rows. The last
    frame has no wall, as in a real run."""
    fields = {**HEADER, "scene": scene, "run_id": run_id, "started_utc": started, **header}
    lines = [f"# frameledger {json.dumps(fields)}", "run_id,segment,frame,category,name,depth,value"]
    frames = [segment for segment, spec in segments.items()
              for _ in range(spec[1] if isinstance(spec, tuple) else FRAMES)]
    for number, segment in enumerate(frames):
        spec = segments[segment]
        for (category, name), value in (spec[0] if isinstance(spec, tuple) else spec).items():
            if (category, name) == ("frame", "wall") and number == len(frames) - 1:
                continue
            lines.append(f"{run_id},{segment},{number},{category},{name},0,{value:.3f}")
    lines.append(f'# frameledger-close {{"rows_dropped":0,"frames":{len(frames)}}}')
    return "\n".join(lines) + "\n"


class Files:
    """Run files written to tmp_path, each started a minute after the last
    unless its start is given."""

    def __init__(self, tmp_path):
        self.tmp_path, self.count = tmp_path, 0

    def write(self, text: str) -> str:
        self.count += 1
        path = self.tmp_path / f"run-{self.count:02d}.csv"
        path.write_text(text, encoding="utf-8")
        return str(path)

    def run(self, scene: str, segments: dict, minute: int | None = None, **header) -> str:
        minute = self.count if minute is None else minute
        return self.write(run_text(scene, f"r{self.count}", f"2026-11-04T12:{minute:02d}:00Z", segments,
                                   **header))

    def runs(self, scene: str, opaques: list, **header) -> list[str]:
        """One run in view:1 per value of `opaques`, the gpu/opaque median."""
        return [self.run(scene, {"view:1": alike(o)}, **header) for o in opaques]


def by_scene(capsys, old, new, *flags) -> tuple[int, dict]:
    code = cli.main(["compare", "--by-scene", "--old", *old, "--new", *new, *flags, "--json"])
    out = json.loads(capsys.readouterr().out)
    assert out["exit_code"] == code
    return code, out


def scene(out: dict, name: str) -> dict:
    return next(s for s in out["result"]["scenes"] if s["scene"] == name)


def interleave(*lists: list) -> list:
    return [item for group in zip(*lists, strict=True) for item in group]


def test_scene_is_one_compare(capsys, tmp_path):
    """INV-73: runs of two scenes given in one list are judged apart, each
    exactly as a compare of its own files, not_interleaved included; the
    scenes differing in `scene` refuses nothing."""
    files = Files(tmp_path)
    a_old = [files.run("a", {"view:1": alike(10.0)}, minute=m) for m in (0, 1, 2)]
    a_new = [files.run("a", {"view:1": alike(10.0)}, minute=m) for m in (10, 11, 12)]
    b_old = [files.run("b", {"view:1": alike(10.0)}, minute=m) for m in (3, 5, 7)]
    b_new = [files.run("b", {"view:1": alike(10.0)}, minute=m) for m in (4, 6, 8)]

    code, out = by_scene(capsys, interleave(a_old, b_old), interleave(a_new, b_new))
    assert (code, out["verdict"]) == (0, "pass")
    for name, old, new in (("a", a_old, a_new), ("b", b_old, b_new)):
        alone = cli.main(["compare", "--old", *old, "--new", *new, "--json"])
        expected = json.loads(capsys.readouterr().out)
        assert alone == 0
        assert scene(out, name)["compare"] == expected["result"], name
        assert scene(out, name)["verdict"] == "pass", name
    warned = {w["code"]: w["message"] for w in out["warnings"]}
    assert warned["not_interleaved"].startswith("a: ")
    assert not any(w["message"].startswith("b: ") for w in out["warnings"])
    assert all(s["compare"]["refused"] == [] for s in out["result"]["scenes"])


def unjudged_fixture(files: Files, a_new_opaque: float = 10.0) -> tuple[list, list]:
    """INV-74's sets: `a` clean at three a side; `b` with no new runs; `c`
    with two old runs; `d` whose new runs differ in device; an empty file."""
    empty = files.write("")
    old = [*files.runs("a", [10.0] * 3), *files.runs("b", [10.0] * 3), *files.runs("c", [10.0] * 2),
           *files.runs("d", [10.0] * 3), empty]
    new = [*files.runs("a", [a_new_opaque] * 3), *files.runs("c", [10.0] * 3),
           *files.runs("d", [10.0] * 3, device="NVIDIA GeForce RTX 5080")]
    return old, new


def test_unjudged_scenes(capsys, tmp_path):
    """INV-74: an unjudged scene or unread file never hides the others, and
    never lets the command exit 0. An empty `scene` makes the file unread."""
    old, new = unjudged_fixture(Files(tmp_path))
    code, out = by_scene(capsys, old, new)
    assert (code, out["verdict"]) == (2, "inconclusive")
    assert scene(out, "a")["verdict"] == "pass"
    verdicts = {s["scene"]: s["verdict"] for s in out["result"]["scenes"]}
    assert verdicts == {"a": "pass", "b": "unjudged", "c": "unjudged", "d": "unjudged"}
    assert "no new runs" in scene(out, "b")["reason"]
    assert "old" in scene(out, "c")["reason"] and "2" in scene(out, "c")["reason"]
    assert "device" in scene(out, "d")["reason"]
    assert scene(out, "b")["compare"] is None and scene(out, "c")["compare"] is None
    assert scene(out, "d")["compare"]["refused"][0]["field"] == "device"
    [unread] = out["result"]["unread"]
    assert (unread["path"], unread["set"]) == (old[-1], "old")
    assert any(old[-1] in s for s in out["summary"])

    slower, blank_scene = tmp_path / "slower", tmp_path / "blank-scene"
    slower.mkdir()
    blank_scene.mkdir()
    code, out = by_scene(capsys, *unjudged_fixture(Files(slower), a_new_opaque=11.0))
    assert (code, out["verdict"], scene(out, "a")["verdict"]) == (1, "fail", "fail")

    files = Files(blank_scene)
    blank = files.run("", {"view:1": alike(10.0)})
    code, out = by_scene(capsys, [*files.runs("a", [10.0] * 3), blank], files.runs("a", [10.0] * 3))
    assert code == 2
    assert [u["path"] for u in out["result"]["unread"]] == [blank]
    assert "scene" in out["result"]["unread"][0]["reason"]
    assert [s["scene"] for s in out["result"]["scenes"]] == ["a"]


def test_nothing_judged(capsys, tmp_path):
    """INV-75: no scene judged is exit 3, opening "No scene could be
    judged:" with each reason; so is a set of only unread files."""
    files = Files(tmp_path)
    old = [*files.runs("b", [10.0] * 3), *files.runs("c", [10.0] * 2), *files.runs("d", [10.0] * 3)]
    new = [*files.runs("c", [10.0] * 3), *files.runs("d", [10.0] * 3, device="NVIDIA GeForce RTX 5080")]
    code, out = by_scene(capsys, old, new)
    assert (code, out["verdict"]) == (3, "error")
    opening = out["summary"][0]
    assert opening.startswith("No scene could be judged:")
    assert "no new runs" in opening and "device" in opening and "c" in opening

    code, out = by_scene(capsys, [files.write("") for _ in range(3)], [files.write("not a run\n") for _ in range(3)])
    assert (code, out["verdict"]) == (3, "error")
    assert out["summary"][0].startswith("No scene could be judged:")

    code, out = by_scene(capsys, old, new, "--override", "api=same driver")
    assert code == 3
    assert out["summary"][0].startswith("Overrides given:")
    assert out["summary"][1].startswith("No scene could be judged:")


def three_segments(view_1: float, view_2: float, view_3: float) -> dict:
    """A view kind whose gpu/opaque median is view:3's, which holds most frames."""
    return {"view:1": (alike(view_1), 50), "view:2": (alike(view_2), 50), "view:3": (alike(view_3), 150)}


def test_rank_and_segment(capsys, tmp_path):
    """INV-76: failing scenes rank by their slower measure's change; the
    segment named is the one whose centre changed most; a scene with only
    a larger mem measure ranks after both."""
    files = Files(tmp_path)
    old = [*files.runs("a", [2.0] * 3),
           *[files.run("b", three_segments(2.0, 2.0, 2.0)) for _ in range(3)],
           *[files.run("c", {"view:1": {**alike(2.0), ("mem", "gpu_mb"): 500.0}}) for _ in range(3)]]
    new = [*files.runs("a", [2.4] * 3),
           *[files.run("b", three_segments(2.1, 3.7, 2.9)) for _ in range(3)],
           *[files.run("c", {"view:1": {**alike(2.0), ("mem", "gpu_mb"): 600.0}}) for _ in range(3)]]
    code, out = by_scene(capsys, old, new)
    assert (code, out["verdict"]) == (1, "fail")
    assert [(s["scene"], s["rank"]) for s in out["result"]["scenes"]] == [("b", 1), ("a", 2), ("c", 3)]
    b = scene(out, "b")
    assert (b["measure"]["category"], b["measure"]["name"], b["measure"]["change"]) == ("gpu", "opaque", 0.9)
    assert b["segment"] == "view:2"
    assert scene(out, "a")["segment"] == "view:1"
    c = scene(out, "c")
    assert (c["measure"]["name"], c["measure"]["verdict"], c["measure"]["change"]) == ("gpu_mb", "larger", 100.0)
    assert out["summary"][0] == ("b is slower: the gpu/opaque median in view rose from 2.000 to 2.900 ms, "
                                 "most in view:2.")


def test_judged_count(capsys, tmp_path):
    """INV-77: the scenes and measures judged are counted, unjudged ones
    left out, in the result and in the text."""
    old, new = unjudged_fixture(Files(tmp_path))
    code, out = by_scene(capsys, old, new)
    measures = len(scene(out, "a")["compare"]["measures"])
    assert out["result"]["judged"] == {"scenes": 1, "measures": measures}

    cli.main(["compare", "--by-scene", "--old", *old, "--new", *new])
    text = capsys.readouterr().out
    assert f"Judged 1 scene and {measures} measures" in text
    table = text.split("Scenes, the largest slowdown first:\n")[1].splitlines()
    assert len(table) == 5  # the column names, then a, b, c and d
    assert all(len(line) <= 100 for line in table)
