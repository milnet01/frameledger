"""Writes the floor check's fixtures (docs/specs/FLED-0001-run-file-format.md
§ 5, INV-7, INV-8, INV-9 and INV-18). Each run is a list of frame walls in
milliseconds; a cut marks the frame it sits on. Run it from anywhere:

    python3 -I tests/fixtures/make_floor_fixtures.py
"""

from pathlib import Path

HEADER = ('# frameledger {"schema":1,"run_id":"f1","engine":"vestige","tool":{"name":"bench",'
          '"version":"1.0"},"build_type":"release","commit":"abc123","dirty":false,'
          '"device":"AMD Radeon RX 9070 XT","renderer":"AMD Radeon RX 9070 XT (radeonsi)",'
          '"driver":"Mesa 26.2","api":"opengl-4.5","resolution":[1920,1080],"render_scale":1.0,'
          '"vsync":false,"pipelined":true,"display":"headless","scene":"atrium",'
          '"inputs":[{"name":"atrium","hash":"sha256:' + "ab" * 32 + '","bytes":48213}],'
          '"started_utc":"2026-10-24T12:00:00Z"}')

# 124 frames of 16 ms and one of 15 end the warm-up at 1999 ms, so no
# frame ends exactly when the first window starts.
WARMUP = [16.0] * 124 + [15.0]


def write(name: str, walls: list[float], cuts: tuple[int, ...] = ()) -> None:
    lines = [HEADER, "run_id,segment,frame,category,name,depth,value"]
    view = 1
    for frame, wall in enumerate([*walls, None]):  # the last frame has no wall
        if frame in cuts:
            view += 1
        segment = f"view:{view}"
        lines.append(f"f1,{segment},{frame},frame,cpu_span,0,8.000")
        if wall is not None:
            lines.append(f"f1,{segment},{frame},frame,wall,0,{wall:.3f}")
        if frame in cuts:
            lines.append(f"f1,{segment},{frame},event,cut,0,1.000")
    lines.append(f'# frameledger-close {{"rows_dropped":0,"frames":{len(walls) + 1}}}')
    (Path(__file__).parent / name).write_text("\n".join(lines) + "\n", encoding="utf-8")


# 62 or 63 frames in every window; no frame over 16.667 ms.
write("passing-run.csv", WARMUP + [16.0] * 190)
# The second after the warm-up: 58 frames of 16 ms and one of 71 end in it,
# 59 frames, though the mean of 1000/wall is above 61.
write("one-hitch.csv", WARMUP + [16.0] * 58 + [71.0] + [16.0] * 130)
# 59 frames end inside the first window; the 60th ends exactly at 3000 ms,
# which is the next window's. Summed as floating-point milliseconds, these
# walls end it at 2999.9999999999945, inside the first window.
write("edge-frame.csv", WARMUP + [16.1] * 59 + [51.1] + [16.0] * 130)
# 8 ms frames (125 per window) and one of 30 ms, after the warm-up.
write("fast-with-one-spike.csv", [8.0] * 300 + [30.0] + [8.0] * 300)
# Every frame exactly the default 60 FPS budget.
write("exact-budget.csv", [16.667] * 330)
# A full second, then a 0.5 s stretch of 20 FPS between two cuts, then 60
# FPS again. Ignoring the cuts puts 41 frames in the window holding it.
write("cut-mid-second.csv", WARMUP + [16.0] * 75 + [50.0] * 10 + [16.0] * 150, cuts=(200, 210))
# Views of about 0.8 s after the warm-up, so no window is full.
write("short-views.csv", WARMUP + [16.0] * 200, cuts=(175, 225, 275))
