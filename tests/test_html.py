"""report --html: the picture report, one web page with the run as a graph.

Invariants INV-126 to INV-130 from docs/specs/FLED-0001-run-file-format.md
§ 5, the rules of § 4.21. Each run is built here as text. The page is
well-formed XML, so the tests read it as a tree, and read the graph back
through its own axes: a point's place on the page against the plot's box
and the axes' last labels.
"""

import errno
import json
import math
import os
import re
import xml.etree.ElementTree as ET
from itertools import combinations
from pathlib import Path

import pytest

import cli
from floor_runs import HEADER
from test_cli import closed_pipe

FIXTURES = Path(__file__).parent / "fixtures"
CHARACTER_EM = 0.7  # § 4.21: the width a label is given for each character
LARGER = ":root:has(#larger:checked)"
MORE_CONTRAST = "@media (prefers-contrast:more)"


def run_text(walls: list[float], segment=lambda frame: "", no_wall=(), missing=(), generated=(),
             static: dict | None = None) -> str:
    """A run of len(walls) frames. `segment` names each frame's; frames in
    `no_wall` have no frame/wall row, those in `missing` no row at all, and
    those in `generated` carry event/generated."""
    lines = [HEADER]
    if static is not None:
        lines.append("# frameledger-static " + json.dumps(static))
    lines.append("run_id,segment,frame,category,name,depth,value")
    for frame, wall in enumerate(walls):
        if frame in missing:
            continue
        lines.append(f"f1,{segment(frame)},{frame},frame,cpu_span,0,8.000")
        if frame not in no_wall:
            lines.append(f"f1,{segment(frame)},{frame},frame,wall,0,{wall:.3f}")
        if frame in generated:
            lines.append(f"f1,{segment(frame)},{frame},event,generated,0,1.000")
    lines.append(f'# frameledger-close {{"rows_dropped":0,"frames":{len(walls) - len(missing)}}}')
    return "\n".join(lines) + "\n"


def menu_view_load(frame: int) -> str:
    return "menu:1" if frame < 30 else "view:1" if frame < 99 else "load:1"


def hundred(slow: int = 50, **options) -> str:
    """INV-127's run: 100 frames of 16 ms, frame `slow` 100 ms, in three segments."""
    walls = [16.0] * 100
    walls[slow] = 100.0
    return run_text(walls, menu_view_load, **options)


def flat(frames: int, **options) -> str:
    return run_text([16.0] * frames, **options)


def write_page(capsys, tmp_path, text: str, *flags: str) -> str:
    """The page `report --html` writes for the run `text`."""
    run, page = tmp_path / "run.csv", tmp_path / "page.html"
    run.write_text(text, encoding="utf-8")
    assert cli.main(["report", str(run), "--html", str(page), *flags]) == 0
    capsys.readouterr()
    return page.read_text(encoding="utf-8")


def numbers(element, *names: str) -> list[float]:
    return [float(element.get(name)) for name in names]


class Graph:
    """The page's graph, read back through its own axes."""

    def __init__(self, page: str):
        self.root = ET.fromstring(page)
        self.svg = self.root.find(".//svg")
        self.em = float(self.svg.get("font-size"))
        self.left, self.top, self.width, self.height = numbers(self.one("rect", "plot"), "x", "y", "width", "height")
        self.ms_top = float(self.all("text", "ms-tick")[-1].text)
        self.s_end = float(self.all("text", "s-tick")[-1].text)

    def all(self, tag: str, kind: str) -> list:
        return self.svg.findall(f".//{tag}[@class='{kind}']")

    def one(self, tag: str, kind: str):
        [element] = self.all(tag, kind)
        return element

    def at(self, x: float, y: float) -> tuple[float, float]:
        """The (s, ms) a place on the page stands for."""
        return ((x - self.left) / self.width * self.s_end,
                (self.top + self.height - y) / self.height * self.ms_top)

    def points(self) -> list[tuple[float, float]]:
        """Each frame's point as (s, ms); none when the run is drawn as columns."""
        lines = self.all("polyline", "line")
        return [self.at(*map(float, pair.split(","))) for line in lines for pair in line.get("points").split()]

    def columns(self) -> list[tuple[float, float, float, float]]:
        """Each column as (start s, end s, fastest ms, slowest ms)."""
        spans = []
        for bar in self.all("rect", "column"):
            x, y, width, height = numbers(bar, "x", "y", "width", "height")
            (start, slowest), (end, fastest) = self.at(x, y), self.at(x + width, y + height)
            spans.append((start, end, fastest, slowest))
        return spans

    def markers(self) -> dict[str, tuple[float, float]]:
        """Each marker's (s, ms), by its number."""
        shapes, texts = self.all("circle", "marker"), self.all("text", "marker-number halo")
        assert len(shapes) == len(texts)
        return {text.text: self.at(*numbers(shape, "cx", "cy")) for shape, text in zip(shapes, texts, strict=True)}

    def label_width(self, label: str) -> float:
        return CHARACTER_EM * self.em * len(label)


def sentences(page: str) -> list[str]:
    return ["".join(p.itertext()) for p in ET.fromstring(page).iter("p")]


def near(found: tuple[float, ...], expected: tuple[float, ...]) -> bool:
    """Equal to the page's precision: a place is written to a thousandth of a unit."""
    return all(math.isclose(f, e, abs_tol=0.002) for f, e in zip(found, expected, strict=True))


# INV-126


@pytest.mark.parametrize("form", [[], ["--json"], ["--markdown"]])
def test_page_beside_the_output(capsys, tmp_path, form):
    """INV-126: standard output is what `report` prints without --html; the
    page holds the sentences, then the graph, then the tables, fetches and
    runs nothing, and a second run overwrites it."""
    run, page = tmp_path / "run.csv", tmp_path / "page.html"
    run.write_text(hundred(generated={61}), encoding="utf-8")
    assert cli.main(["report", str(run), *form]) == 0
    alone = capsys.readouterr().out
    assert cli.main(["report", str(run), *form, "--html", str(page), "--fps", "60"]) == 0
    assert capsys.readouterr().out == alone
    first = page.read_text(encoding="utf-8")

    assert cli.main(["report", str(run), "--json"]) == 0
    summary = json.loads(capsys.readouterr().out)["summary"]
    assert any("generated" in sentence for sentence in summary)  # § 4.20's sentence is among them
    assert sentences(first)[:len(summary)] == summary
    graph, tables = first.index("<svg"), first.index("<table")
    assert first.index(f"<p>{summary[-1]}</p>") < graph < first.index("</svg>") < tables
    assert "Worst frames, longest first:" in first[tables:]

    for banned in ("<script", "<object", "<embed", "<iframe", "@import"):
        assert banned not in first
    assert not re.search(r"\son\w*\s*=", first)
    targets = re.findall(r"""(?:url\(|href=|src=)\s*["']?(.)""", first)
    assert targets and set(targets) == {"#"}

    # The second page is a new file put in the first one's place, never
    # the first written over: a reader holding the first sees it whole.
    inode = page.stat().st_ino
    run.write_text(flat(10), encoding="utf-8")
    assert cli.main(["report", str(run), "--html", str(page)]) == 0
    capsys.readouterr()
    second = page.read_text(encoding="utf-8")
    assert second != first and second.startswith("<!DOCTYPE html>") and "view:1" not in second
    assert page.stat().st_ino != inode


def test_the_page_is_a_new_file(tmp_path):
    """INV-126: the page has a new file's permissions, whatever PAGE had;
    and when printing fails after the page is in place, the exit is 3 and
    the new page stays."""
    run, page = tmp_path / "run.csv", tmp_path / "page.html"
    run.write_text(hundred(), encoding="utf-8")
    page.write_text("old", encoding="utf-8")
    page.chmod(0o600)
    mask = os.umask(0o022)
    try:
        assert closed_pipe(["report", str(run), "--html", str(page)]) == cli.ERROR
    finally:
        os.umask(mask)
    assert page.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")
    assert page.stat().st_mode & 0o777 == 0o644


class HalfWritten:
    """A stream that takes half of what it is given, then fails as a full disk does."""

    def __init__(self, stream):
        self.stream = stream

    def __enter__(self):
        return self

    def __exit__(self, *error):
        self.stream.close()

    def write(self, text: str):
        self.stream.write(text[:len(text) // 2])
        self.stream.flush()
        raise OSError(errno.ENOSPC, "No space left on device")


def test_page_refusals(capsys, tmp_path, monkeypatch):
    """INV-126: a refused or failed report leaves PAGE the same file,
    holding what it held, with no new file beside it."""
    run, page, broken = tmp_path / "run.csv", tmp_path / "page.html", tmp_path / "broken.csv"
    run.write_text(hundred(), encoding="utf-8")
    broken.write_text("not a run\n", encoding="utf-8")
    page.write_text("old", encoding="utf-8")
    inode, beside = page.stat().st_ino, sorted(os.listdir(tmp_path))

    def refused(*args: str) -> tuple[str, str]:
        assert cli.main(["report", *args]) == cli.ERROR
        assert (page.stat().st_ino, page.read_text(encoding="utf-8")) == (inode, "old")
        assert sorted(os.listdir(tmp_path)) == beside
        said = capsys.readouterr()
        return said.out, said.err

    for flags in (["--fps", "60"], ["--html", str(page), "--fps", "60", "--fps", "30"],
                  ["--html", str(page), "--fps", "2000000"]):
        out, err = refused(str(run), *flags)
        assert out == "" and "--fps" in err

    # Before anything is read: a FILE that breaks the format is not reached.
    for flags in (["--html", str(page), "--fps", "2000000"], ["--html", ""]):
        out, err = refused(str(broken), *flags)
        assert out == "" and ("--fps" in err or "--html" in err) and "breaks" not in err

    report_alone, _ = refused(str(broken))
    out, _ = refused(str(broken), "--html", str(page))
    assert out == report_alone and "breaks the run-file format" in out

    nowhere = str(tmp_path / "missing" / "page.html")
    out, err = refused(str(run), "--html", nowhere)
    assert out == "" and nowhere in err

    real_fdopen = os.fdopen
    with monkeypatch.context() as patch:
        patch.setattr(os, "fdopen", lambda handle, *args, **kwargs: HalfWritten(real_fdopen(handle, *args, **kwargs)))
        out, err = refused(str(run), "--html", str(page))
    assert out == "" and str(page) in err and "No space left" in err


def test_page_is_never_file(capsys, tmp_path):
    """INV-126: PAGE naming FILE, by any path, is refused and FILE is unchanged."""
    run = tmp_path / "run.csv"
    run.write_text(hundred(), encoding="utf-8")
    written = run.read_bytes()
    (tmp_path / "folder").mkdir()
    (tmp_path / "link.html").symlink_to(run)
    os.link(run, tmp_path / "hard.html")
    for page in ("link.html", "folder/../run.csv", "hard.html"):
        assert cli.main(["report", str(run), "--html", str(tmp_path / page)]) == cli.ERROR
        said = capsys.readouterr()
        assert said.out == "" and "run file" in said.err
        assert run.read_bytes() == written and (tmp_path / "link.html").is_symlink()

    # A PAGE that is a link to some other file is replaced by the page; the
    # file it pointed at is untouched.
    other, link = tmp_path / "other.txt", tmp_path / "elsewhere.html"
    other.write_text("kept", encoding="utf-8")
    link.symlink_to(other)
    assert cli.main(["report", str(run), "--html", str(link)]) == 0
    capsys.readouterr()
    assert other.read_text(encoding="utf-8") == "kept" and not link.is_symlink()
    assert link.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")


# INV-127


def test_graph_of_a_run(capsys, tmp_path):
    """INV-127: the axes, the points and the label of the 100-frame run."""
    page = write_page(capsys, tmp_path, hundred())
    graph = Graph(page)
    assert [title.text for title in graph.all("text", "axis-title")] == ["frame/wall (ms)", "time (s)"]
    assert graph.all("text", "ms-tick")[0].text == "0.000" and graph.all("text", "ms-tick")[-1].text == "110.000"
    assert graph.all("text", "s-tick")[0].text == "0.000" and graph.all("text", "s-tick")[-1].text == "1.684"
    points = graph.points()
    assert len(points) == 100
    assert near(points[0], (0.016, 16.0)) and near(points[50], (0.900, 100.0)) and near(points[99], (1.684, 16.0))
    assert graph.svg.get("role") == "img"
    assert graph.svg.get("aria-label") == ("Frame time against time: median wall 16.000 ms; slowest frame "
                                           "100.000 ms, frame 50, at 0.900 s.")
    # No fact is in a tooltip, and every label is text, not a picture of it.
    assert all(element.tag not in ("title", "image") for element in graph.svg.iter())
    assert all("title" not in element.attrib for element in graph.root.iter())
    # The data line is solid, and without --fps there is no budget line.
    assert graph.one("polyline", "line").get("stroke-dasharray") is None
    assert not graph.all("line", "budget") and "fps budget" not in page


def test_band_labels(capsys, tmp_path):
    """INV-127: bands are patterned and labelled above the plot; one too
    narrow for its label is listed under the graph instead."""
    page = write_page(capsys, tmp_path, hundred())
    graph = Graph(page)
    bands = graph.all("rect", "band")
    assert len(bands) == 3
    spans = [(graph.at(x, 0)[0], graph.at(x + width, 0)[0]) for x, width in (numbers(b, "x", "width") for b in bands)]
    assert all(near(span, expected) for span, expected in zip(spans, [(0, 0.480), (0.480, 1.668), (1.668, 1.684)],
                                                               strict=True))
    fills = [band.get("fill") for band in bands]
    patterns = {f"url(#{p.get('id')})": ET.tostring(p).split(b">", 1)[1] for p in graph.svg.iter("pattern")}
    assert all(fill in patterns for fill in fills)
    assert all(patterns[a] != patterns[b] for a, b in zip(fills, fills[1:], strict=False))
    labels = graph.all("text", "band-label")
    assert [label.text for label in labels] == ["menu:1", "view:1"]
    assert all(float(label.get("y")) < graph.top for label in labels)  # above the plot, never over the line
    assert ["".join(item.itertext()) for item in graph.root.iter("li")] == ["load:1, from 1.668 s to 1.684 s"]

    # A label needs 0.7 em a character and 1 em more. Of 1000 equal frames,
    # `enough` is the fewest whose band is that wide.
    needed = graph.label_width("ab:1") + graph.em
    enough = math.ceil(needed / (graph.width / 1000))
    for frames, labelled in ((enough, True), (enough - 1, False)):
        page = write_page(capsys, tmp_path, flat(1000, segment=lambda frame, n=frames: "ab:1" if frame < n else ""))
        graph = Graph(page)
        assert len(graph.all("rect", "band")) == 1
        assert [label.text for label in graph.all("text", "band-label")] == (["ab:1"] if labelled else [])
        end = f"{frames * 0.016:.3f}"
        assert ["".join(item.itertext()) for item in graph.root.iter("li")] == (
            [] if labelled else [f"ab:1, from 0.000 s to {end} s"])


def test_markers(capsys, tmp_path):
    """INV-127: the worst frames are numbered markers at their points, the
    numbers as large as the page's text and clear of each other."""
    run = tmp_path / "run.csv"
    page = write_page(capsys, tmp_path, hundred())
    assert cli.main(["report", str(run), "--json"]) == 0
    worst = [entry["frame"] for entry in json.loads(capsys.readouterr().out)["result"]["worst_frames"]]
    assert worst == [50, *range(9)]
    graph = Graph(page)
    points, markers = graph.points(), graph.markers()
    assert list(markers) == [str(n) for n in range(1, 11)]
    assert all(near(markers[str(n)], points[frame]) for n, frame in enumerate(worst, start=1))

    # The view box is 1200 units over 75rem, so 16 units are the page's 1rem
    # text; no label sets a size of its own, and the style sheet sets none
    # but the larger text's.
    assert graph.svg.get("viewBox").split()[2] == "1200" and graph.svg.get("width") == "75rem"
    assert graph.em >= 16 and all(text.get("font-size") is None for text in graph.svg.iter("text"))
    assert re.findall(r"\bfont(?:-size)?:[^;}]*", style_sheet(page)) == ["font-size:1.25rem"] * 2
    assert ("Each numbered marker is one of the worst frames, numbered in the order the worst-frames table "
            "below lists them.") in sentences(page)
    assert_numbers_clear(graph)

    # A cluster of slow frames mid-run, under a band label: the numbers
    # stack upward, stay half an em apart on a line, so 1 and 7 never read
    # as 17, and end under the label.
    walls = [16.0] * 1000
    walls[495:505] = [30.0] * 10
    graph = Graph(write_page(capsys, tmp_path, run_text(walls, lambda frame: "view:1")))
    assert len(graph.markers()) == 10 and [label.text for label in graph.all("text", "band-label")] == ["view:1"]
    assert_numbers_clear(graph)


def boxes(graph: Graph, kind: str) -> list[tuple[float, float, float, float]]:
    """Each label of a kind as (left, right, top, bottom): centred on its
    x, 0.7 em a character wide, and 1 em tall above its baseline."""
    found = []
    for text in graph.all("text", kind):
        x, baseline = numbers(text, "x", "y")
        half = graph.label_width(text.text) / 2
        found.append((x - half, x + half, baseline - graph.em, baseline))
    return found


def assert_numbers_clear(graph: Graph) -> None:
    """No two marker numbers on one line are within half an em, and none touches a band label."""
    marker_numbers, gap = boxes(graph, "marker-number halo"), graph.em / 2
    for (left, right, top, bottom), (left2, right2, top2, bottom2) in combinations(marker_numbers, 2):
        assert right + gap <= left2 or right2 + gap <= left or bottom <= top2 or bottom2 <= top
    for left, right, top, bottom in marker_numbers:
        for left2, right2, top2, bottom2 in boxes(graph, "band-label"):
            assert right <= left2 or right2 <= left or bottom <= top2 or bottom2 <= top


@pytest.mark.parametrize(("fps", "label", "budget_ms", "ms_top"), [
    ("60", "60 fps budget: 16.667 ms", 16.667, "110.000"),
    ("59.94", "59.94 fps budget: 16.684 ms", 16.684, "110.000"),
    ("5", "5 fps budget: 200.000 ms", 200.0, "220.000"),
])
def test_budget_line(capsys, tmp_path, fps, label, budget_ms, ms_top):
    """INV-127: --fps adds one dashed line at 1000/N ms, labelled in text
    with N as typed, and a budget above the slowest frame sets the ms axis."""
    page = write_page(capsys, tmp_path, hundred(), "--fps", fps)
    graph = Graph(page)
    line = graph.one("line", "budget")
    assert line.get("stroke-dasharray")
    x1, y1, x2, y2 = numbers(line, "x1", "y1", "x2", "y2")
    assert y1 == y2 and near((graph.at(x1, y1)[1],), (budget_ms,))
    assert (x1, x2) == (graph.left, graph.left + graph.width)
    key = graph.one("text", "budget-label")
    assert key.text == label and float(key.get("y")) > graph.top + graph.height + graph.em  # under the plot
    # And as a sentence, since a screen reader skips the graph's own text.
    assert f"The dashed line is the {label}." in sentences(page)
    assert graph.all("text", "ms-tick")[-1].text == ms_top


def test_a_missing_wall_stops_the_graph(capsys, tmp_path):
    """INV-127: the graph stops where the timeline does, and says where."""
    stops = "The graph stops after frame 69: the timeline cannot be built past frame 70."
    for options in ({"no_wall": {70}}, {"missing": {70}}):
        page = write_page(capsys, tmp_path, hundred(**options))
        graph = Graph(page)
        assert len(graph.points()) == 70 and graph.all("text", "s-tick")[-1].text == "1.204"
        assert stops in sentences(page)
        assert "view:1" in [label.text for label in graph.all("text", "band-label")]

    # A worst frame past the stop has no marker; the table still lists it.
    page = write_page(capsys, tmp_path, hundred(slow=80, no_wall={70}))
    assert list(Graph(page).markers()) == [str(n) for n in range(2, 11)]
    assert "100.000" in page[page.index("Worst frames, longest first:"):]

    page = write_page(capsys, tmp_path, hundred(no_wall={0}))
    assert "<svg" not in page
    assert "There is no graph: the timeline cannot be built past frame 0." in sentences(page)
    # Generated frames before the first application frame: a wall or a
    # frame missing among them stops the timeline before it starts (§ 4.20).
    for options in ({"no_wall": {1}}, {"missing": {1}}):
        page = write_page(capsys, tmp_path, flat(20, generated={0, 1, 2}, **options))
        assert "<svg" not in page
        assert "There is no graph: the timeline cannot be built past frame 1." in sentences(page)

    # One drawn frame that is no worst frame is still a point: a dot.
    walls = [16.0] * 100
    walls[0] = 10.0
    graph = Graph(write_page(capsys, tmp_path, run_text(walls, no_wall={1})))
    assert len(graph.points()) == 1 and "1" not in graph.markers()
    assert near(graph.at(*numbers(graph.one("circle", "point"), "cx", "cy")), (0.010, 10.0))
    assert all("The graph stops" not in sentence for sentence in sentences(write_page(capsys, tmp_path, hundred())))


def test_generated_frames_on_the_graph(capsys, tmp_path):
    """INV-127: the graph reads the frames § 4.20 says: a generated frame's
    wall joins the application frame before it, unless --all-frames."""
    points = Graph(write_page(capsys, tmp_path, flat(100, generated={61}))).points()
    assert len(points) == 99
    assert near(points[60], (0.992, 32.0)) and near(points[61], (1.008, 16.0))
    points = Graph(write_page(capsys, tmp_path, flat(100, generated={61}), "--all-frames")).points()
    assert len(points) == 100
    assert near(points[60], (0.976, 16.0)) and near(points[61], (0.992, 16.0))


def test_no_graph_without_walls(capsys, tmp_path):
    """INV-127: a run with no frame/wall row has a sentence in the graph's place."""
    page = write_page(capsys, tmp_path, flat(10, no_wall=set(range(10))))
    assert "<svg" not in page
    assert "No frame has a wall, so there is no graph." in sentences(page)
    assert "<table" in page


# INV-128


def columns_sentence(frames: int) -> str:
    return f"{frames} frames are drawn as 1200 columns; each shows its fastest and slowest frame."


def test_long_runs_in_columns(capsys, tmp_path):
    """INV-128: over 1200 frames are drawn as 1200 columns, each from its
    fastest wall to its slowest, so one slow frame stays as tall as it was."""
    walls = [16.0] * 6000
    walls[3001] = 200.0
    page = write_page(capsys, tmp_path, run_text(walls))
    graph = Graph(page)
    columns = graph.columns()
    assert len(columns) == 1200 and not graph.points()
    # Frames 3000 to 3004: from frame 3000's start to frame 3004's end.
    assert near(columns[600], (48.0, 48.264, 16.0, 200.0))
    assert columns_sentence(6000) in sentences(page)
    assert near(graph.markers()["1"], (48.216, 200.0))

    page = write_page(capsys, tmp_path, flat(1200))
    graph = Graph(page)
    assert len(graph.points()) == 1200 and not graph.columns()
    assert all("columns" not in sentence for sentence in sentences(page))

    page = write_page(capsys, tmp_path, flat(1201))
    columns = Graph(page).columns()
    assert len(columns) == 1200 and columns_sentence(1201) in sentences(page)
    assert near(columns[-2][:2], (19.168, 19.184)) and near(columns[-1][:2], (19.184, 19.216))

    # The stop comes first: 1201 frames are drawn, and the columns count those.
    page = write_page(capsys, tmp_path, flat(1300, no_wall={1201}))
    columns = Graph(page).columns()
    assert len(columns) == 1200 and columns_sentence(1201) in sentences(page)
    assert near(columns[-1][:2], (19.184, 19.216))


# INV-129

HOSTILE = "a<b>&\"':x</text><script>1"  # a segment the format allows


def test_outside_text_is_escaped(capsys, tmp_path):
    """INV-129: a static value cannot add markup, and is cleaned as plain text is."""
    static = {"note": "</table><script>x</script> & \"q\" 'r'", "name": "a‮b"}
    page = write_page(capsys, tmp_path, flat(10, static=static))
    assert "&lt;/table&gt;&lt;script&gt;x&lt;/script&gt; &amp; &quot;q&quot; &#39;r&#39;" in page
    assert "a\\u202eb" in page
    assert "<script" not in page and "‮" not in page
    [value] = [cells[1].text for cells in (row.findall("td") for row in ET.fromstring(page).iter("tr"))
               if cells and cells[0].text == "note"]
    assert value == static["note"]

    # A segment reaches the graph twice: as a band's label, and in the list
    # of bands too narrow for one.
    page = write_page(capsys, tmp_path, flat(100, segment=lambda frame: HOSTILE if frame < 99 else HOSTILE + "2"))
    graph = Graph(page)
    assert "<script" not in page
    assert [label.text for label in graph.all("text", "band-label")] == [HOSTILE]
    assert ["".join(item.itertext()) for item in graph.root.iter("li")] == [f"{HOSTILE}2, from 1.584 s to 1.600 s"]


# INV-130


def style_sheet(page: str) -> str:
    [sheet] = [style.text for style in ET.fromstring(page).iter("style")]
    return sheet


def rule(sheet: str, selector: str) -> str:
    """The declarations of the first rule whose selector is exactly `selector`."""
    found = re.search(r"(?:^|[{}])\s*" + re.escape(selector) + r"\s*\{([^{}]*)\}", sheet)
    assert found, selector
    return found[1]


def test_normal_vision_first(capsys, tmp_path):
    """INV-130: by default the text is the browser's size, every length is
    in em or rem, the lines are at least 2 units wide and the graph scrolls
    in its own box."""
    page = write_page(capsys, tmp_path, hundred(), "--fps", "60")
    sheet, graph = style_sheet(page), Graph(page)
    assert "font-size" not in rule(sheet, ":root")
    assert not re.search(r"(?:^|[{},])\s*(?:html|body)\s*\{[^}]*font-size", sheet)
    colourless = re.sub(r"#[0-9a-f]{6}\b", "", sheet)
    units = set(re.findall(r"\d([a-z%]+)", colourless))
    assert units and units <= {"em", "rem"}
    assert not re.search(r"\dpx", page)

    assert graph.svg.get("width") == "75rem" and graph.svg.get("viewBox").split()[2] == "1200"
    assert re.fullmatch(r"[\d.]+rem", graph.svg.get("height"))
    outlined = [graph.one("polyline", "line"), graph.one("line", "budget"), *graph.all("circle", "marker")]
    assert len(outlined) == 12 and all(float(shape.get("stroke-width")) >= 2 for shape in outlined)

    [box] = [div for div in graph.root.iter("div") if div.find("svg") is not None]
    assert "overflow-x:auto" in rule(sheet, f".{box.get('class')}")
    first, second = list(graph.root.find("body"))[:2]
    assert first.tag == "input" and first.get("type") == "checkbox"
    assert second.tag == "label" and second.get("for") == first.get("id")
    assert second.text == "Larger text and lines"


def test_larger_text_and_lines(capsys, tmp_path):
    """INV-130: the switch, without script, and prefers-contrast: more each
    set the root text to 1.25rem."""
    page = write_page(capsys, tmp_path, hundred())
    sheet = style_sheet(page)
    assert ET.fromstring(page).find("body")[0].get("id") == "larger" and "<script" not in page
    assert "font-size:1.25rem" in rule(sheet, LARGER)
    assert "font-size:1.25rem" in rule(sheet[sheet.index(MORE_CONTRAST):], ":root")


def luminance(colour: str) -> float:
    """WCAG 2.2's relative luminance of #rrggbb."""
    channels = [int(colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    red, green, blue = (c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(one: str, other: str) -> float:
    lighter, darker = sorted((luminance(one), luminance(other)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def colours(declarations: str) -> dict[str, str]:
    return dict(re.findall(r"--([a-z-]+):(#[0-9a-f]{6})\b", declarations))


def test_contrast(capsys, tmp_path):
    """INV-130: every colour the page sets is one of the style sheet's
    named colours, and each pair meets its contrast: AA by default, 7:1
    under the switch and under prefers-contrast: more."""
    page = write_page(capsys, tmp_path, hundred(), "--fps", "60")
    sheet, graph = style_sheet(page), Graph(page)
    usual = colours(rule(sheet, ":root"))
    larger = [usual | colours(rule(sheet, LARGER)),
              usual | colours(rule(sheet[sheet.index(MORE_CONTRAST):], ":root"))]
    assert set(usual) == {"paper", "ink", "line", "budget", "marker", "band-edge", "band-fill", "grid"}

    # No colour is set anywhere else: not in a rule, and not as an SVG attribute.
    named = sum(len(colours(block)) for block in re.findall(r"\{([^{}]*)\}", sheet))
    assert len(re.findall(r"#[0-9a-f]{3,8}\b", page.replace("#larger", "").replace("url(#", ""))) == named
    assert not re.search(r"rgb|hsl|(?<![-\w])(?:black|white|gr[ae]y|red|blue)(?![-\w])", sheet)
    painted = {element.get(name) for element in graph.svg.iter() for name in ("fill", "stroke", "color", "style")}
    assert painted <= {None, "url(#band-a)", "url(#band-b)"}

    def check(named: dict[str, str], least: float) -> None:
        assert contrast(named["ink"], named["paper"]) >= max(least, 4.5)
        for data in ("line", "budget", "marker"):
            assert contrast(named[data], named["paper"]) >= least, data
            assert contrast(named[data], named["band-fill"]) >= least, data
        assert contrast(named["band-edge"], named["paper"]) >= least

    check(usual, 3)
    for named_colours in larger:
        check(named_colours, 7)
        assert contrast(named_colours["grid"], named_colours["paper"]) >= 3
