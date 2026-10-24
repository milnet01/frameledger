# frameledger — starting brief (2026-10-24)

Handoff from the Vestige session (vestige-6f) to the new frameledger
session. Delete this file once its content lives in the frameledger
repository.

## User decisions, 2026-10-24

- One shared benchmarking tool for Vestige, UT Ants and DOOM Ants, to
  find each project's bottlenecks.
- Its own repository at `/mnt/Games/Scripts/Linux/frameledger`, local
  only until the user says otherwise.
- Its own session builds and owns it. The three game sessions are its
  customers.
- Name: frameledger.
- Projects call a pinned version rather than vendoring a copy.

## Agreed shape (all three sessions)

- Each engine keeps its own repeatable run and capture code, and writes
  one shared file format.
- One shared analyser: Python 3 standard library only, run with
  `python3 -I`.
- Nothing is built to the format until its spec, in the frameledger
  repository, has passed a cold review (`write-spec`, then
  `review-contract`).

## Draft format (Vestige's proposal, with UT Ants' amendments folded in)

One CSV per run.

- Line 1: `# frameledger {json}`, the run header.
- Optional line 2: `# frameledger-static {json}`, per-run facts that are
  not per frame (shader register or wave counts per pipeline, draw
  counts, scene facts). Never rows with a fake frame number: they would
  pollute the floor statistics.
- Then the column header and one row per measurement per frame:
  `run_id,segment,frame,category,name,depth,ms`, with ms to 3 decimal
  places.

Header fields: schema, engine, tool (capture tool and version), build_type,
commit, dirty, device, driver, api, resolution, render_scale, tier, vsync,
pipelined, scene, input {name, sha256}, settling_frames, pinned {clocks
the run froze}, gpu_tick_ns, load_start and load_end, gpu_clock_mhz at
start and end (AMD Linux: the starred line of
`/sys/class/drm/card*/device/pp_dpm_sclk`), started_utc, extra {}.

Segment naming: `<kind>:<id>`, for example `view:3`, `move:3-4`, `leg:2`,
`spot:e1m1-a`; "" if none. The analyser groups by segment kind too.

Categories: frame, cpu, gpu, mem (MB in the ms column), ext.<engine>.

Required frame rows each frame: frame/cpu_span, frame/gpu_span,
frame/wall. Optional: frame/fence_wait, frame/present_wait. The analyser,
not the engine, computes frame/cpu_remainder and frame/gpu_remainder:
the span minus the sum of that category's depth-0 rows.

## Analyser, first version

- Floor: 1% low, 0.1% low, worst N frames with segment and frame number,
  frames over a budget (16.67 ms default).
- Cost ranking: per pass median and p99, share of span, both remainders.
- Bound-by: per frame, GPU if gpu_span > cpu_span or fence_wait is high,
  else CPU; reported as a share of frames. One-line caveat when
  `pipelined` is false.
- Compare: interleaved A/B repeats with a spread-based verdict; a
  baseline mode taking Vestige's `tools/perf_gate.py` verdict ladder,
  exit codes and `--selftest`. Refuses to compare runs whose headers
  differ in resolution, render_scale, tier, build_type or input hash,
  unless forced.
- Trust: warns on high load, Debug or software-renderer runs, too few
  frames, and differences under the timestamp resolution.

## What each engine has today

- **Vestige** (C++17, OpenGL 4.5): `--profile-log` CSV about once a
  second; `--demo-flythrough --no-vsync`; `tools/fps_floor.py`;
  `tools/perf_gate.py`. Its frame row is an average of a 300-frame
  rolling average (roadmap 3D_E-0786), so per-frame capture is new
  work.
- **UT Ants** (C++23, Vulkan 1.3): `ut-bench frame`, surfaceless, a
  camera file with still views and moves, per-step GPU timestamps.
  Writes one JSON object of medians today; will add `--ledger PATH` that
  writes the CSV from per-frame stats. Spec: `docs/specs/UTA-0129-benchmark-tool.md`
  in its repository.
- **DOOM Ants** (C engine plus a C++ Vulkan back-end, raster and ray
  traced): about once a second, `[raster_profile]`, `[rt_profile]` and
  `[cpu_profile]` stdout lines; `-warp ... -devshot N` for a fixed
  frame. Its planned one-second harness DOOM-0431 is parked; switching
  it to frameledger is the DOOM user's call.

## Peers

Message `vestige-6f`, `ut-ants-aa` and `doom-ants-26` (names as
`ListAgents` shows them) for format questions. All three have asked to
review the spec before anything is built to it.
