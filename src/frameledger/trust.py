"""Whether one run's numbers can be trusted: S5's warning half.

The rules are docs/specs/FLED-0001-run-file-format.md § 4.9. A warning
never changes a verdict or an exit code; an absent header field gives
none, since absent means unknown. The warnings come back as
ledger.Notice, so `report` and `floor` turn them into sentences as they
do the file's own. `check` never calls this: it judges the file, not
the run. Comparing two runs (the refusal half of S5) is FLED-0008's.
"""

from __future__ import annotations

import ledger

# Matched anywhere in `renderer` or `device`, in any case.
SOFTWARE_RENDERERS = ("llvmpipe", "lavapipe", "softpipe", "swrast", "swiftshader",
                      "software rasterizer", "gdi generic", "microsoft basic render driver")
CPU_LOAD_LIMIT = 0.5  # `load` is a share of the machine, 1 being every logical CPU busy
GPU_BUSY_LIMIT = 20   # percent
# Below 100 frames the nearest-rank 99th percentile is the slowest frame,
# so the 1% low is one frame's time.
FEWEST_FRAMES = 100


def warnings(run: ledger.Run, measured: int, cut_frames: set[int] | None = None) -> list[ledger.Notice]:
    """The § 4.9 warnings for a run that meets the format, in the spec's
    table order. `measured` is how many frames the command judges; a cut
    counts only on a frame in `cut_frames`, or on any frame when it is
    None."""
    header = run.header
    found = []

    def warn(code: str, message: str) -> None:
        found.append(ledger.Notice(code, message))

    if header["build_type"].casefold() == "debug":
        warn("debug_build", f"the build type is '{header['build_type']}', so the run timed a "
             "Debug build")
    for field in ("renderer", "device"):
        if any(name in header[field].casefold() for name in SOFTWARE_RENDERERS):
            warn("software_renderer", f"the {field} is '{header[field]}', which draws in software, "
                 "so the run says nothing about a GPU")
            break
    load = header.get("load", {}).get("start")
    if load is not None and load > CPU_LOAD_LIMIT:
        warn("cpu_load", f"load.start is {load}, above {CPU_LOAD_LIMIT}: the CPU was busy before the "
             "run, so other work may have slowed it")
    busy = header.get("gpu_busy_pct", {}).get("start")
    if busy is not None and busy > GPU_BUSY_LIMIT:
        warn("gpu_load", f"gpu_busy_pct.start is {busy}, above {GPU_BUSY_LIMIT}: the GPU was busy "
             "before the run, so other work may have slowed it")
    settled, settling = header.get("settled_frames"), header.get("settling_frames")
    if settled is not None and settling is not None and settled < settling:
        warn("settling_short", f"settled_frames is {settled}, below settling_frames {settling}, so a "
             "segment was timed before it settled")
    if measured < FEWEST_FRAMES:
        warn("too_few_frames", f"only {measured} {'frame is' if measured == 1 else 'frames are'} "
             f"measured, fewer than {FEWEST_FRAMES}, so the 99th percentile is the slowest frame")
    for frame in sorted(run.frames):
        rows = run.frames[frame]
        previous = run.frames.get(frame - 1)
        if (("event", "cut") in rows and previous is not None
                and (cut_frames is None or frame in cut_frames)
                and ledger.frame_segment(previous) == ledger.frame_segment(rows)):
            warn("cut_in_stretch", f"frame {frame} has an event/cut inside segment "
                 f"'{ledger.frame_segment(rows) or 'none'}', so the frames after it may cost "
                 "more than the segment's own")
    return found
