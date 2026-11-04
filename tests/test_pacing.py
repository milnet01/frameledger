"""The pacing figure (S14, FLED-0011).

Invariant from docs/specs/FLED-0001-run-file-format.md § 5: INV-68, the
`pacing` rule of § 4.8. Every run is built here.
"""

import json

import cli
from floor_runs import HEADER

WALL_CHANGE = "wall change (pairs)"


def run_text(frames: list) -> str:
    """One frame per entry, (segment, wall in ms, cut); None leaves that
    frame number out, a hole. A frame closes the run with no wall."""
    lines = [HEADER, "run_id,segment,frame,category,name,depth,value"]
    for number, entry in enumerate([*frames, ("view:9", None, False)]):
        if entry is None:
            continue
        segment, wall, cut = entry
        lines.append(f"f1,{segment},{number},frame,cpu_span,0,8.000")
        if wall is not None:
            lines.append(f"f1,{segment},{number},frame,wall,0,{wall:.3f}")
        if cut:
            lines.append(f"f1,{segment},{number},event,cut,0,1.000")
    lines.append(f'# frameledger-close {{"rows_dropped":0,"frames":{len(frames) + 1}}}')
    return "\n".join(lines) + "\n"


def steady(count: int, segment: str = "view:1", wall: float = 16.667) -> list:
    return [(segment, wall, False)] * count


def report(capsys, tmp_path, frames: list) -> tuple[dict, list[str]]:
    """`report --json`'s result and `report`'s text lines for one run."""
    path = tmp_path / "run.csv"
    path.write_text(run_text(frames), encoding="utf-8")
    assert cli.main(["report", str(path), "--json"]) == 0
    result = json.loads(capsys.readouterr().out)["result"]
    assert cli.main(["report", str(path)]) == 0
    return result, capsys.readouterr().out.splitlines()


def test_pacing_figure(capsys, tmp_path):
    """INV-68: walls alternating 10 and 23 ms change by 13.000 at the
    median and p99; a steady run by 0.000. The text row matches."""
    alternating = [("view:1", 10.0 if i % 2 else 23.0, False) for i in range(200)]
    result, text = report(capsys, tmp_path, alternating)
    assert result["pacing"] == [{"segment_kind": "view", "median_ms": 13.0, "p99_ms": 13.0,
                                 "pairs": 199}]
    rows = [line.split() for line in text if line.strip().startswith(WALL_CHANGE)]
    assert rows == [[*WALL_CHANGE.split(), "13.000", "13.000", "199"]]
    # The row sits under wall, in the frame-times table.
    walls = [i for i, line in enumerate(text)
             if line.split()[:1] == ["wall"] and WALL_CHANGE not in line]
    assert [i + 1 for i in walls] == [i for i, line in enumerate(text) if WALL_CHANGE in line]

    result, _ = report(capsys, tmp_path, steady(200))
    assert result["pacing"] == [{"segment_kind": "view", "median_ms": 0.0, "p99_ms": 0.0,
                                 "pairs": 199}]


def test_pacing_pairs(capsys, tmp_path):
    """INV-68: no pair spans a cut, a hole or a segment change, so a
    break among steady frames leaves the change at 0.000 and removes
    the pairs it sits in. A kind with no pair has no entry."""
    cut = steady(100) + [("view:1", 500.0, True)] + steady(99)
    result, _ = report(capsys, tmp_path, cut)
    assert result["pacing"] == [{"segment_kind": "view", "median_ms": 0.0, "p99_ms": 0.0,
                                 "pairs": 197}]  # 199 less the two the cut frame is in

    hole = steady(100) + [None] + steady(99)
    result, _ = report(capsys, tmp_path, hole)
    assert result["pacing"][0]["pairs"] == 197  # the hole's two neighbours lose a pair each

    segments = steady(100) + steady(100, "view:2", 33.333)
    result, _ = report(capsys, tmp_path, segments)
    assert result["pacing"] == [{"segment_kind": "view", "median_ms": 0.0, "p99_ms": 0.0,
                                 "pairs": 198}]

    alone = steady(100) + [("move:1", 16.667, False)] + steady(99, "view:2")
    result, text = report(capsys, tmp_path, alone)
    assert [e["segment_kind"] for e in result["pacing"]] == ["view"]
    assert sum(WALL_CHANGE in line for line in text) == 1  # none for move
