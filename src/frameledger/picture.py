"""The picture report: one run as a web page with a graph (S26).

The rules are docs/specs/FLED-0001-run-file-format.md § 4.21. The page's
sentences and tables are render.py's, from the same result, so the page
and the text cannot disagree. The graph is drawn here, as SVG, from the
run's timeline. Nothing on the page runs or is fetched.

Lengths inside the graph are view-box units. The graph is 75rem wide
over a view box of 1200 units, so a unit is 1/16 rem, and EM units are
the page's text size whatever the browser's zoom.
"""

from __future__ import annotations

from itertools import groupby
from typing import NamedTuple

import ledger
import render
import run_report
import stats

COLUMNS = 1200  # § 4.21: a run of more frames than this is drawn as this many columns
BANDS = 1200  # § 4.21: a run of more bands than this draws none
LISTED = 100  # § 4.21: the list under the graph holds this many bands, then counts the rest
EM = 16  # units to the page's 1rem
CHARACTER = 0.7 * EM  # § 4.21: the width a label is given for each of its characters
VIEW_WIDTH = 1200
LEFT, RIGHT = 120, 1180  # the plot's sides; the ms labels sit left of it
PLOT_HEIGHT = 360
# The graph's rows, top to bottom. The band labels' row is first, and the
# plot starts under it, or lower when stacked marker numbers need the room.
LABEL_BASELINE = 1.25 * EM
LABEL_ROW = 1.75 * EM  # that row's height
# Under the plot, each a baseline measured from the plot's bottom edge: the
# time labels, the time axis's name, and the budget line's key on a row of
# its own, so a long --fps cannot reach the axis's name.
TICK_BASELINE = 1.25 * EM
TITLE_BASELINE = 3 * EM
KEY_BASELINE = 4.5 * EM
ROW_DESCENT = 0.75 * EM  # the room under the last baseline
HEADROOM = 1.1  # § 4.21: the ms axis ends this far above the largest thing drawn
TICKS = 4  # each axis is labelled at 0 and at this many even steps from it
LINE_WIDTH = 2  # § 4.21: the least the data line, the budget line and a marker's outline may be
MARKER_RADIUS = 5
NUMBER_RISE = MARKER_RADIUS + 0.4 * EM  # a marker's number sits this far above its point
NUMBER_LINE = 1.25 * EM  # how far a number is raised to clear another
NUMBER_GAP = 0.5 * EM  # § 4.21: the least space between two numbers on one line, so 1 and 7 never read as 17


class Budget(NamedTuple):
    """--fps N's budget line."""
    typed: str  # N as it was typed, which the line's label shows
    us: int  # 1000/N ms in microseconds, rounded up as floor's window check has it


class Frame(NamedTuple):
    """One drawn frame; times are microseconds on the run's timeline."""
    number: int
    segment: str
    start: int
    end: int
    wall: int


class Band(NamedTuple):
    """A stretch of drawn frames sharing a segment."""
    segment: str
    start: int
    end: int


class _Plot:
    """Where a time and a wall, both in microseconds, fall in the view box."""

    def __init__(self, end: int, wall_top: float, y_top: float):
        """`end` is the time axis's last value and `wall_top` the ms axis's,
        both above zero, since ledger.py refuses a frame/wall that is not;
        `y_top` is where the plot's top edge sits in the view box."""
        self.end, self.wall_top = end, wall_top
        self.y_top, self.bottom = y_top, y_top + PLOT_HEIGHT

    def x(self, time: float) -> float:
        return LEFT + (RIGHT - LEFT) * time / self.end

    def y(self, wall: float) -> float:
        return self.bottom - PLOT_HEIGHT * wall / self.wall_top


def page(result: dict, run: ledger.Run, budget: Budget | None) -> str:
    """The whole page for `report`'s `result` on `run`, in § 4.21's order:
    the opening sentences, the graph and what it needs said, the tables."""
    parts = [f"<p>{_escaped(sentence)}</p>" for sentence in result["summary"]]
    parts += _graph(run, result["result"]["worst_frames"], budget)
    parts += [_block(block) for block in render.body_blocks(result) if block != ""]
    return _HEAD + "\n".join(parts) + "\n</body></html>\n"


_ENTITIES = {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}  # & first: the rest add one


def _escaped(text: str) -> str:
    """Text as the page holds it: cleaned as plain text is (§ 4.8), then
    escaped, so nothing from a run file or the command line adds markup."""
    cleaned = render.visible(text)
    for character, entity in _ENTITIES.items():
        cleaned = cleaned.replace(character, entity)
    return cleaned


def _block(block: render.Block) -> str:
    """One of the text's blocks: a line as a paragraph, a table as a table
    in a box of its own, which scrolls sideways when the window is narrower."""
    if isinstance(block, str):
        return f"<p>{_escaped(block.strip())}</p>"
    shown = render.shown_columns(block)

    def row(cells: list[str], tag: str) -> str:
        opening = {False: f"<{tag}>", True: f'<{tag} class="number">'}  # a number column is aligned right
        cells_shown = (f"{opening[block.columns[i].right]}{_escaped(cells[i])}</{tag}>" for i in shown)
        return "<tr>" + "".join(cells_shown) + "</tr>"
    caption = "" if block.title is None else f"<caption>{_escaped(block.title)}</caption>"
    head = row([column.header for column in block.columns], "th")
    rows = "\n".join(row(cells, "td") for cells in block.rows)
    return f'<div class="scroll"><table>{caption}<thead>{head}</thead>\n<tbody>{rows}</tbody></table></div>'


def _graph(run: ledger.Run, worst: list[dict], budget: Budget | None) -> list[str]:
    """The graph, then the sentences and the list it needs; or the one
    sentence that takes its place. `worst` is the result's worst_frames."""
    if not run_report.walled_frames(run):
        return ["<p>No frame has a wall, so there is no graph.</p>"]
    frames, past = _drawn(run)
    if not frames:
        return [f"<p>There is no graph: the timeline cannot be built past frame {past}.</p>"]
    slowest = max(frames, key=lambda f: (f.wall, -f.number))
    by_number = {f.number: f for f in frames}
    # A worst frame past the stop keeps its number and has no marker.
    marked = [(str(n), by_number[w["frame"]]) for n, w in enumerate(worst, start=1) if w["frame"] in by_number]
    wall_top = HEADROOM * max(slowest.wall, budget.us if budget else 0)
    plot, baselines = _plot_and_numbers(frames[-1].end, wall_top, marked)
    bands = _bands(frames)
    label = (f"Frame time against time: median wall {_ms(stats.median([f.wall for f in frames]))} ms; "
             f"slowest frame {_ms(slowest.wall)} ms, frame {slowest.number}, at {_s(slowest.end)} s.")
    height = plot.bottom + (KEY_BASELINE if budget else TITLE_BASELINE) + ROW_DESCENT
    svg = [f'<div class="graph"><svg role="img" aria-label="{_escaped(label)}" '
           f'viewBox="0 0 {VIEW_WIDTH} {_n(height)}" width="{VIEW_WIDTH // EM}rem" height="{_n(height / EM)}rem" '
           f'font-size="{EM}">',
           _PATTERNS, *(_band_shapes(plot, bands) if len(bands) <= BANDS else []), *_axes(plot),
           *_data(plot, frames)]
    if budget:
        svg += _budget_line(plot, budget)
    svg += _markers(plot, marked, baselines)
    sentences = [f"<p>{sentence}</p>" for sentence in _said(frames, past, len(bands), marked, budget)]
    return ["\n".join(svg) + "\n</svg></div>", *sentences, *_band_list(bands)]


def _plot_and_numbers(end: int, wall_top: float, marked: list[tuple[str, Frame]]) -> tuple[_Plot, list[float]]:
    """The plot, and the baseline of each marker's number in it. Numbers
    stacked over a cluster of slow frames can rise above the plot's top
    edge, so the plot starts lower by that much, and the stack ends under
    the band labels' row. Moving the plot down moves every y in it by the
    same amount: the numbers are placed on a plot starting at 0, then moved
    with it."""
    at_zero = _Plot(end, wall_top, 0)
    baselines = _number_baselines([(number, at_zero.x(f.end), at_zero.y(f.wall)) for number, f in marked])
    y_top = LABEL_ROW + max(0, EM - min(baselines, default=EM))  # a number is 1 em tall, above its baseline
    return _Plot(end, wall_top, y_top), [y_top + baseline for baseline in baselines]


def _said(frames: list[Frame], past: int | None, bands: int, marked: list[tuple[str, Frame]],
          budget: Budget | None) -> list[str]:
    """The sentences under the graph, each ready for the page: where it
    stops, that it is drawn as columns, that its `bands` bands are too many
    to draw, what its numbered markers are, and the budget, which is
    otherwise only inside the graph, where a screen reader or a search of
    the page does not look (§ 4.21)."""
    said = []
    if past is not None:
        said.append(f"The graph stops after frame {frames[-1].number}: the timeline cannot be built "
                    f"past frame {past}.")
    if len(frames) > COLUMNS:
        said.append(f"{len(frames)} frames are drawn as {COLUMNS} columns; each shows its fastest and slowest frame.")
    if bands > BANDS:
        said.append(f"The run has {bands} segment bands; the graph draws at most {BANDS}, so it draws none.")
    if marked:
        said.append("Each numbered marker is one of the worst frames, numbered in the order the worst-frames "
                    "table below lists them.")
    if budget:
        said.append(f"The dashed line is the {_budget_label(budget)}.")
    return said


def _budget_label(budget: Budget) -> str:
    """The budget line's label, ready for the page, with N as it was typed."""
    return f"{_escaped(budget.typed)} fps budget: {_ms(budget.us)} ms"


def _drawn(run: ledger.Run) -> tuple[list[Frame], int | None]:
    """The frames the graph draws, and the frame the timeline cannot be
    built past, or None when it reaches the run's end. Nothing from that
    frame on is drawn: its place in time would be a guess."""
    timed, _cuts, stop, _stopped_at = run_report.timeline(run)
    past = None if stop is None else stop.frame
    return [Frame(number, ledger.frame_segment(rows), end - wall, end, wall)
            for number, rows, end, wall in timed if past is None or number < past], past


def _bands(frames: list[Frame]) -> list[Band]:
    """Frames with no segment have no band."""
    stretches = ((segment, list(stretch)) for segment, stretch in groupby(frames, key=lambda f: f.segment))
    return [Band(segment, stretch[0].start, stretch[-1].end) for segment, stretch in stretches if segment]


def _fits(plot: _Plot, band: Band) -> bool:
    """Whether a band is wide enough for its label: 0.7 em for each
    character, and 1 em more (§ 4.21)."""
    return plot.x(band.end) - plot.x(band.start) >= CHARACTER * len(render.visible(band.segment)) + EM


def _band_shapes(plot: _Plot, bands: list[Band]) -> list[str]:
    """Each band behind the line, neighbours in different patterns, and its
    label where it fits: in the graph's first row, above the plot and above
    any marker numbers stacked over it."""
    shapes = []
    for position, band in enumerate(bands):
        left, right = plot.x(band.start), plot.x(band.end)
        shapes.append(f'<rect class="band" x="{_n(left)}" y="{_n(plot.y_top)}" width="{_n(right - left)}" '
                      f'height="{PLOT_HEIGHT}" fill="url(#band-{"ab"[position % 2]})"/>')
        if _fits(plot, band):
            shapes.append(f'<text class="band-label" x="{_n((left + right) / 2)}" y="{_n(LABEL_BASELINE)}" '
                          f'text-anchor="middle">{_escaped(band.segment)}</text>')
    return shapes


def _band_list(bands: list[Band]) -> list[str]:
    """Under the graph: the run's first bands by segment, labelled and
    drawn or not, so each one's name is text a screen reader reaches; then
    how many bands the list leaves out."""
    if not bands:
        return []
    entries = [f"<li>{_escaped(band.segment)}, from {_s(band.start)} s to {_s(band.end)} s</li>"
               for band in bands[:LISTED]]
    listed = ["<p>Segments, in run order:</p>", "<ul>" + "\n".join(entries) + "</ul>"]
    if len(bands) > LISTED:
        listed.append(f"<p>and {len(bands) - LISTED} more.</p>")
    return listed


def _axes(plot: _Plot) -> list[str]:
    """The plot's box, its grid lines, and both axes' labels and names."""
    middle = (plot.y_top + plot.bottom) / 2
    shapes = [f'<rect class="plot" x="{LEFT}" y="{_n(plot.y_top)}" width="{RIGHT - LEFT}" height="{PLOT_HEIGHT}"/>',
              f'<text class="axis-title" x="{EM}" y="{_n(middle)}" text-anchor="middle" '
              f'transform="rotate(-90 {EM} {_n(middle)})">frame/wall (ms)</text>',
              f'<text class="axis-title" x="{(LEFT + RIGHT) // 2}" y="{_n(plot.bottom + TITLE_BASELINE)}" '
              'text-anchor="middle">time (s)</text>']
    for step in range(TICKS + 1):
        wall, time = plot.wall_top * step / TICKS, plot.end * step / TICKS
        y, x = plot.y(wall), plot.x(time)
        if 0 < step < TICKS:
            shapes.append(f'<line class="grid" x1="{LEFT}" y1="{_n(y)}" x2="{RIGHT}" y2="{_n(y)}"/>')
        shapes.append(f'<text class="ms-tick" x="{LEFT - 0.5 * EM}" y="{_n(y)}" text-anchor="end" '
                      f'dominant-baseline="middle">{_ms(wall)}</text>')
        anchor = "start" if step == 0 else "end" if step == TICKS else "middle"  # the end labels stay inside the view
        shapes.append(f'<text class="s-tick" x="{_n(x)}" y="{_n(plot.bottom + TICK_BASELINE)}" '
                      f'text-anchor="{anchor}">{_s(time)}</text>')
    return shapes


def _data(plot: _Plot, frames: list[Frame]) -> list[str]:
    """Each frame as a point at its end, joined by a line; or, for a long
    run, columns, each a bar from its frames' fastest wall to their slowest,
    so one slow frame stays as tall as it was."""
    if len(frames) <= COLUMNS:
        points = [f"{_n(plot.x(f.end))},{_n(plot.y(f.wall))}" for f in frames]
        line = [f'<polyline class="line" stroke-width="{LINE_WIDTH}" points="{" ".join(points)}"/>']
        if len(points) == 1:  # a line through one point paints nothing, so the point is drawn as a dot
            x, y = points[0].split(",")
            line.append(f'<circle class="point" cx="{x}" cy="{y}" r="{LINE_WIDTH}"/>')
        return line
    bars = []
    for held in _columns(frames):
        left, top = plot.x(held[0].start), plot.y(max(f.wall for f in held))
        # A column of equal walls is still as thick as the line would be.
        height = max(plot.y(min(f.wall for f in held)) - top, LINE_WIDTH)
        bars.append(f'<rect class="column" x="{_n(left)}" y="{_n(top)}" width="{_n(plot.x(held[-1].end) - left)}" '
                    f'height="{_n(height)}"/>')
    return bars


def _columns(frames: list[Frame]) -> list[list[Frame]]:
    """§ 4.21: with N frames, column i holds those from position
    floor(i * N / COLUMNS) up to, not including, floor((i + 1) * N / COLUMNS)."""
    count = len(frames)
    return [frames[i * count // COLUMNS:(i + 1) * count // COLUMNS] for i in range(COLUMNS)]


def _budget_line(plot: _Plot, budget: Budget) -> list[str]:
    """The dashed line across the plot, and under the plot a short piece
    of it beside its label: on the line, the label would sit over the data."""
    y, key_y = plot.y(budget.us), plot.bottom + KEY_BASELINE
    dashed = f'stroke-width="{LINE_WIDTH}" stroke-dasharray="12 8"'
    return [f'<line class="budget" x1="{LEFT}" y1="{_n(y)}" x2="{RIGHT}" y2="{_n(y)}" {dashed}/>',
            f'<line class="budget key" x1="{LEFT}" y1="{_n(key_y - 0.3 * EM)}" x2="{LEFT + 3 * EM}" '
            f'y2="{_n(key_y - 0.3 * EM)}" {dashed}/>',
            f'<text class="budget-label" x="{LEFT + 3.5 * EM}" y="{_n(key_y)}">'
            f'{_budget_label(budget)}</text>']


def _number_baselines(points: list[tuple[str, float, float]]) -> list[float]:
    """The baseline of each marker's number, from (number, x, y) of its
    point: above the marker, and raised a line at a time until it is clear
    of every number placed before it, by NUMBER_GAP on its own line. A
    number is CHARACTER wide for each of its characters and centred on its
    point."""
    placed: list[tuple[float, float, float]] = []  # left, right, baseline
    for number, x, y in points:
        half = CHARACTER * len(number) / 2
        baseline = y - NUMBER_RISE
        while any(left - NUMBER_GAP < x + half and x - half < right + NUMBER_GAP
                  and abs(baseline - other) < NUMBER_LINE
                  for left, right, other in placed):
            baseline -= NUMBER_LINE
        placed.append((x - half, x + half, baseline))
    return [baseline for _left, _right, baseline in placed]


def _markers(plot: _Plot, marked: list[tuple[str, Frame]], baselines: list[float]) -> list[str]:
    """A ring at each worst frame's point, then the numbers, so no ring covers one."""
    places = [(number, _n(plot.x(f.end)), _n(plot.y(f.wall))) for number, f in marked]
    rings = [f'<circle class="marker" cx="{x}" cy="{y}" r="{MARKER_RADIUS}" stroke-width="{LINE_WIDTH}"/>'
             for _number, x, y in places]
    numbers = [f'<text class="marker-number halo" x="{x}" y="{_n(baseline)}" text-anchor="middle">{number}</text>'
               for (number, x, _y), baseline in zip(places, baselines, strict=True)]
    return rings + numbers


def _n(value: float) -> str:
    """A length or a place in the view box, to a thousandth of a unit."""
    return f"{value:.3f}".rstrip("0").rstrip(".")


def _ms(microseconds: float) -> str:
    return f"{microseconds / 1000:.3f}"


def _s(microseconds: float) -> str:
    """Seconds to a thousandth, a half rounded up. In whole numbers: a
    float's own rounding would label 0.0025 s up and 0.0075 s down."""
    whole, thousandths = divmod(int((microseconds + 500) // 1000), 1000)
    return f"{whole}.{thousandths:03d}"


# Two patterns, so neighbouring bands differ in more than shade (§ 4.21).
_PATTERNS = ('<defs><pattern id="band-a" width="12" height="12" patternUnits="userSpaceOnUse">'
             '<path class="hatch" d="M0 12L12 0" stroke-width="1.5"/></pattern>'
             '<pattern id="band-b" width="12" height="12" patternUnits="userSpaceOnUse">'
             '<circle class="dots" cx="6" cy="6" r="1.5"/></pattern></defs>')

# Every colour the page sets (§ 4.21, INV-130). By default: 4.5:1 for text;
# 3:1 for the line, the budget line and the markers against the paper and
# the band fill, and for band edges against the paper.
_USUAL = {"paper": "#ffffff", "ink": "#1a1a1a", "line": "#0b3d91", "budget": "#8a1c1c", "marker": "#1a1a1a",
          "band-edge": "#6e6e6e", "band-fill": "#a8a8a8", "grid": "#d0d0d0"}
# Under the switch and under prefers-contrast: more, each of those is 7:1,
# and grid lines 3:1.
_LARGER = {"ink": "#000000", "line": "#000000", "budget": "#000000", "marker": "#000000",
           "band-edge": "#000000", "grid": "#767676"}


def _named(colours: dict[str, str]) -> str:
    return "".join(f"--{name}:{colour};" for name, colour in colours.items())


# The root text at 1.25rem grows the graph with it: its width is in rem.
_LARGER_RULE = "font-size:1.25rem;" + _named(_LARGER)
# No px anywhere: a length in the style sheet is in em or rem, and one
# with no unit, on an SVG shape, is in view-box units. No rule sets a font
# size but the larger one, so every label in the graph is the page's text
# size. This is an f-string: a rule's own braces are doubled.
_STYLE = f""":root{{{_named(_USUAL)}}}
:root:has(#larger:checked){{{_LARGER_RULE}}}
@media (prefers-contrast:more){{:root{{{_LARGER_RULE}}}}}
body{{margin:1.5rem;background:var(--paper);color:var(--ink);font-family:system-ui,sans-serif;line-height:1.5}}
label{{margin-left:0.25em}}
p,ul{{max-width:60rem}}
.graph{{overflow-x:auto;margin:1rem 0}}
.scroll{{overflow-x:auto;margin:1rem 0}}
svg{{display:block;font-family:ui-monospace,Menlo,Consolas,"DejaVu Sans Mono",monospace}}
text{{fill:var(--ink)}}
.halo{{paint-order:stroke;stroke:var(--paper);stroke-width:4;stroke-linejoin:round}}
.plot{{fill:none;stroke:var(--ink)}}
.grid{{stroke:var(--grid)}}
.band{{stroke:var(--band-edge)}}
.hatch{{stroke:var(--band-fill)}}
.dots{{fill:var(--band-fill)}}
.line{{fill:none;stroke:var(--line);stroke-linejoin:round}}
.column{{fill:var(--line)}}
.point{{fill:var(--line)}}
.budget{{stroke:var(--budget)}}
.marker{{fill:var(--paper);stroke:var(--marker)}}
table{{border-collapse:collapse;font-family:ui-monospace,Menlo,Consolas,"DejaVu Sans Mono",monospace}}
caption{{text-align:left;font-family:system-ui,sans-serif;font-weight:600;padding-bottom:0.25rem}}
th,td{{padding:0.125rem 0.75rem;text-align:left;white-space:pre;border-bottom:0.0625rem solid var(--grid)}}
.number{{text-align:right}}
"""

# The switch is first on the page, and works without script: the style
# sheet reads its checked state.
_HEAD = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>frameledger report</title>
<style>
{_STYLE}</style></head>
<body><input type="checkbox" id="larger"/><label for="larger">Larger text and lines</label>
"""
