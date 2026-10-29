<!-- ants-spec-format: 1 -->
# FLED-0001 — Define the run file, the writer's interface and the 0.1.0 commands

**Status:** accepted (2026-10-24); § 4.9 and INV-23 to INV-27
(FLED-0005) agreed by the three engines 2026-10-26 at a3eea64;
§ 4.10 and INV-30 to INV-38 (FLED-0008) agreed by the three engines
2026-10-26 at f7dd566, with `scene` added; their code review
settled the § 4.10 edges and INV-38. § 4.11 and INV-39 to INV-53
(FLED-0009) agreed by the three engines 2026-10-26 at d68c994, with
`tested_straddle` and `--skip-straddle` added from their answers; their
code review settled `--tested`, the stops and INV-52 to INV-53, and
they confirmed it at 32b87ac. § 4.12 and INV-54 to INV-63
(FLED-0010) proposed 2026-10-29; the three engines' review is folded
in, for their confirmation.
**Kind:** doc.
**Source:** ROADMAP FLED-0001 (design-2026-10-24; requirements from the Vestige, UT Ants and DOOM Ants sessions).
**Blocker for:** FLED-0002, FLED-0006.

What an engine writes after a benchmark run, and what the analyser
promises to say about it, written down once so all three engines and
any later engine produce the same file.

## 1. Goal

A run file has one written definition. An engine can write one from
this document alone (S7), with or without the optional C header. The
analyser's 0.1.0 commands (`check`, `report`, `floor`), 0.2.0's
`compare`, `bisect` and `budget`, its exit codes and the outer shape of its JSON
result are fixed, so engines can script against them before the analyser exists.

## 2. Problem

Nothing exists yet: `src/` is empty and `include/` does not exist. Each engine
measures differently today
([discovery](../discovery.md) § The problem). Without one contract:

1. Each engine would invent its own columns, units and header fields,
   and the analyser could not compare them.
2. Details the engines raised — GPU rows arriving frames late, frames
   with no GPU result, dropped rows, a run that never closed, numbers
   written under a comma-decimal locale — would each be settled
   differently by each writer.
3. Engines' scripts and CI gates bind to the command names, exit codes
   and JSON fields. Changing them after adoption breaks three projects.

## 3. Scope decisions (agreed with the user)

The owner delegated decisions to the three engine sessions on
2026-10-24. Each choice below was made by them, recorded in
[discovery answers](../reviews/2026-10-24-discovery-customer-answers.md)
and [design answers](../reviews/2026-10-24-design-customer-answers.md),
unless marked *proposed here*, which the engines' review of this spec
settles.

- One CSV file per run, with a JSON header line, an optional static
  line, and rows; Vestige's draft with UT Ants' amendments (the brief,
  all three engines).
- GPU rows count against the frame that submitted the work, and rows
  may come in any order (Vestige, DOOM Ants).
- A frame with no GPU result is written by leaving its row out, and
  counted as missing (Vestige).
- Microsecond resolution: three decimal places of milliseconds (DOOM
  Ants).
- Several named inputs, each with a content hash (UT Ants).
- Static statistics are carried as exact text, not as floating point
  (UT Ants).
- The writer takes a buffer from the engine, never allocates, drops and
  counts rows when full, states the largest row, and formats numbers
  without the locale (DOOM Ants, Vestige, design).
- Exit ladder 0/1/2/3, and bisect codes 0/1/125/128 (Vestige, UT Ants,
  design).
- *Proposed here:* the row column `ms` becomes `value`, because `mem`
  rows carry MB and `event` rows carry counts. A column named `ms`
  holding megabytes would mislead every writer.
- *Proposed here:* camera cuts and simulation tics are `event` rows,
  not new columns.
- *Proposed here:* a close line ends every finished run, carrying the
  drop count.
- *Proposed here:* the writer does no file I/O at all. It fills the
  engine's buffer; the engine writes the bytes out.
- Trust warnings for a Debug build, a software renderer, too few
  frames, load above a threshold, settling below the header's need,
  and a camera cut inside a measured stretch (the brief; Vestige, UT
  Ants, DOOM Ants). For FLED-0005, agreed by the three engines
  2026-10-26: they warn and never change a verdict (§ 4.9); `load` is a
  share of the machine, so one threshold fits every CPU count; loads
  are sampled before the engine loads anything (Vestige, UT Ants);
  settling compares two header fields (UT Ants); a cut sits on the
  frame that starts its segment (DOOM Ants).
- For FLED-0008, agreed by the three engines 2026-10-26: `compare`
  judges each measure by its own spread and a minimum change (§ 4.10);
  interleaved labelled sets of at least three runs (UT Ants, DOOM
  Ants); per-field overrides named in one first sentence (S5; DOOM
  Ants); `vsync` and `scene` block a compare (DOOM Ants; all three
  for `scene`); a short segment kind
  cannot make it inconclusive (Vestige); a static-line diff (UT Ants).
- For FLED-0009, reviewed by the three engines 2026-10-26: `bisect`
  judges one measure against a threshold or the midpoint of good and
  bad reference runs (§ 4.11); on a bisect command line every outcome
  but good, bad and skip is 128 (DOOM Ants); three runs a reference set,
  which must not straddle its midpoint (Vestige, DOOM Ants); one
  segment can be judged alone (UT Ants); a `mem` measure has a floor in
  MB (Vestige); tested runs straddling the line warn, and skip only
  with `--skip-straddle` (UT Ants, DOOM Ants; Vestige would skip).
- For FLED-0010: `budget` judges each pass's median
  or p99 over the run against a limit in a budget file (§ 4.12), never
  a single frame (DOOM Ants, DOOM-0502); a CSV file, as the run file
  is; `*` judges every kind apart (S2); a budget nothing matches is
  inconclusive, never a pass. Reviewed by the three engines
  2026-10-29: `match` ties a budget file to its settings and a named
  kind replaces `*` (UT Ants); *proposed here*, `--warmup-s` with default
  0, between Vestige's floor-style 2 and UT Ants' and DOOM Ants' none; `over_ms` (DOOM
  Ants, UT Ants).

## 4. Design

### 4.1 The file

UTF-8 text. Lines end in LF or CRLF; a reader treats them the same.
Numbers use `.` as the decimal point, never `,`, whatever the writer's
locale.

```
# frameledger {"schema":1,"run_id":"...",...}        line 1: header, required
# frameledger-static {"pipelines":[...],...}          line 2: static, optional
run_id,segment,frame,category,name,depth,value        column line, required
<rows>                                                any order
# frameledger-close {"rows_dropped":0,"frames":3600}  last line, required in a finished run
```

A line beginning `# frameledger` holds one JSON object after the first
space following the keyword. JSON is on one line. No other line begins
with `#`.

### 4.2 The header

Required fields:

| Field | Type | Meaning |
|---|---|---|
| `schema` | integer | `1` for this spec |
| `run_id` | string | unique per run; every row repeats it |
| `engine` | string | `vestige`, `ut-ants`, `doom-ants`, or any other name |
| `tool` | object | `{"name": ..., "version": ...}` — the capture tool |
| `build_type` | string | `debug`, `release`, `relwithdebinfo`, or another word |
| `commit` | string | the engine's commit id |
| `dirty` | boolean | uncommitted changes in the build |
| `device` | string | GPU name |
| `renderer` | string | what the API reports (`GL_RENDERER`, Vulkan device name) |
| `driver` | string | driver name and version |
| `api` | string | `opengl-4.5`, `vulkan-1.3`, … |
| `resolution` | array | `[width, height]` in pixels |
| `render_scale` | number | `1.0` for native |
| `vsync` | boolean | |
| `pipelined` | boolean | does CPU work for frame N+1 overlap GPU work for frame N |
| `display` | string | `onscreen`, `headless` (a private display) or `offscreen` (no display) |
| `scene` | string | what was run |
| `inputs` | array | `[{"name": ..., "hash": "sha256:<hex>" or "md5:<hex>", "bytes": n}]`; `[]` is legal, and `check` warns on it |
| `started_utc` | string | ISO 8601, `Z` suffix |

Optional fields, absent meaning unknown: `tier` (string),
`ray_tracing` (boolean), `frames_in_flight` (integer),
`settling_frames` (integer: untimed frames each segment needs drawn
before its first recorded frame), `settled_frames` (integer: the
fewest untimed frames the run drew before any segment's first recorded
frame), `pinned` (object: clocks the run froze),
`gpu_tick_ns` (number), `load` (`{"start": n, "end": n}`, CPU load
as a share of the machine: 0 idle, 1 every logical CPU busy),
`gpu_busy_pct` (`{"start": n, "end": n}`), `gpu_clock_mhz`
(`{"start": n, "end": n}`), `os` (string), `extra` (object, the
engine's own).

A `start` is taken before the engine loads anything or starts GPU
work, so it measures the machine, not the run; an `end` after the
run's last frame. `gpu_busy_pct.start` may be the highest of a few
samples over about half a second, the writer's choice, since one
sample jumps. On Linux, `load` is the one-minute load average divided
by the logical CPU count. It lags, so it is a coarse signal; it counts
tasks waiting on disk; and it can exceed 1, which is legal. On Windows
it is the CPU-busy share at that moment.

**Compare-blocking fields**: `resolution`, `render_scale`, `tier`,
`ray_tracing`, `build_type`, `inputs`, `display`, `api`, `device`,
`vsync`, `scene`.
Two runs differing in any of them are not comparable without an
override (§ 4.10). Two empty `inputs` lists are unknown, not
equal.

### 4.3 The static line

A JSON object of per-run facts that are not per frame: pipeline
statistics, draw counts, scene facts. Its shape is the engine's, with
one rule: a statistic value is a JSON **string** of its exact decimal
text (`"17436423623014656123"`), never a JSON number, so no reader
rounds it. The analyser prints the static line's contents beside the
ranking and does not interpret them. An optional top-level `summary`
object holds the facts the engine wants in the text report; the text
prints it whole and leaves the rest to `--json`. Without one, the text
prints the first 20 facts and counts the rest.

### 4.4 Rows

| Column | Rule |
|---|---|
| `run_id` | equals the header's |
| `segment` | `<kind>:<id>` (`view:3`, `move:3-4`, `leg:2`, `spot:e1m1-a`), or empty |
| `frame` | non-negative integer; the frame that submitted the work |
| `category` | `frame`, `cpu`, `gpu`, `mem`, `event`, or `ext.<engine>` |
| `name` | the pass or measure; ASCII letters, digits and `_ . / -`, at most 64 bytes |
| `depth` | integer from 0; 0 is a top-level pass |
| `value` | decimal number, exactly three places after the point, below 1 000 000 000 in size |

Segment kind and id are at most 32 bytes each; category at most 32.
Fields are quoted only when they hold a comma or a quote, CSV-style
(RFC 4180).

Units by category: `frame`, `cpu`, `gpu` — milliseconds; `mem` —
megabytes; `event` — a count; `ext.<engine>` — the engine's own unit.

**Rounding.** A value is the measured number rounded to the nearest
thousandth, ties away from zero, computed as C99
`llround(value * 1000.0)` on a `double`. So two writers given the same
`double` write the same text.

**Negative values** are written as measured, never clamped to zero: a
clamp hides a clock fault. `check` and every report warn on each
negative `cpu`, `gpu` or `frame` value, in the opening sentences. A
`frame/wall` of zero or less is a breach: the timeline cannot be built
from it.

**Frame rows.** Each frame has `frame/cpu_span`, `frame/gpu_span` and
`frame/wall`. `frame/cpu_span` is the frame's CPU work, excluding time
spent waiting on the GPU (fence and present waits). `frame/wall` is
real elapsed time from this frame's start to the next frame's start,
never a fixed simulation step; so the last frame of a run has no
`frame/wall` row, and that is not a breach. Optional:
`frame/fence_wait`, `frame/present_wait`. A frame whose GPU result never
arrived has no `frame/gpu_span` row.

**Frame numbers** run without holes. A number missing between two
present ones is a hole: not a breach, but `check` and every report warn
`frame_missing`, naming the frames.

**Events.** `event/cut` on a frame where the camera jumped or a level
loaded; `event/tic` on a frame where the simulation stepped, its value
the number of steps (`2.000` when it caught up two). One row per frame
and event name. Other event names are allowed. A planned cut sits on
the first frame of its new segment, not a frame before or after, or
§ 4.9 warns `cut_in_stretch`.

**Remainders** are the analyser's: per frame, `cpu_remainder` is
`frame/cpu_span` minus the sum of the `cpu` depth-0 rows, and
`gpu_remainder` likewise for `gpu`. No other category, `ext` included,
is ever subtracted. Writers never write them.

### 4.5 The close line

```
# frameledger-close {"rows_dropped": <integer>, "frames": <integer>}
```

Written once, last, when the run ends. A file without it is an
unfinished run: the engine crashed or was killed.

### 4.6 The writer: `include/frameledger.h`

```c
#define FLED_SCHEMA         1
#define FLED_NAME_MAX       64   /* name */
#define FLED_PART_MAX       32   /* category; segment kind; segment id */
#define FLED_RUN_ID_MAX     64
#define FLED_ROW_MAX        /* largest row in bytes, computed from the above */
#define FLED_CLOSE_MAX      /* largest close line in bytes */

typedef struct fled_writer { /* fields visible, contents private */ } fled_writer;

/* Every function is `static inline`; the declarations sit inside
   #ifdef __cplusplus extern "C" { ... } guards. */

enum { FLED_OK = 0, FLED_DROPPED = 1, FLED_BAD_ARG = 2 };

int    fled_open (fled_writer *w, char *buf, size_t cap,
                  const char *run_id, const char *header_json,
                  const char *static_json /* or NULL */);
int    fled_row  (fled_writer *w, const char *segment, long long frame,
                  const char *category, const char *name, int depth,
                  double value);
size_t fled_pending (const fled_writer *w, const char **bytes);
void   fled_consume (fled_writer *w, size_t n);
int    fled_close (fled_writer *w, long long frames);
size_t fled_json_escape (char *dst, size_t cap, const char *src);
```

- `fled_open` writes the header, static and column lines into `buf`.
  `header_json` and `static_json` are complete JSON objects the engine
  built; `fled_json_escape` helps build them, and `fled_open` takes
  whatever it returns. `fled_open` returns `FLED_BAD_ARG`, writing
  nothing, when `cap` cannot hold those lines plus `FLED_CLOSE_MAX`. A
  refused writer has nothing pending. Adding N times `FLED_ROW_MAX`
  guarantees N rows; rows take their true size, so typical rows fit
  about ten times as many.
- `fled_row` appends one row, or returns `FLED_DROPPED` and adds one to
  the drop count when fewer than `FLED_ROW_MAX` bytes remain. It
  returns `FLED_BAD_ARG`, and writes nothing, for a name over its
  limit, a character outside 4.4's set, or a value that is not finite
  or is 1 000 000 000 or more in size.
- `fled_pending` and `fled_consume` hand the filled bytes to the engine,
  which writes them out when it chooses; the writer does no file I/O.
  `fled_consume(n)` moves the unconsumed bytes to the buffer's start,
  so the space is reused: an engine can flush between levels instead
  of sizing the buffer for the whole run.
- `fled_close` appends the close line. It is never dropped: `fled_open`
  keeps room for it.
- No allocation, no file I/O, no `printf` family, no locale. It may
  call `memmove`, `memcpy`, `strlen` and `llround`. One thread: the
  caller's; one writer may be used from C and C++ files of the same
  program. Compiles as C99 and as C++17.

### 4.7 The 0.1.0 commands

Run as `python3 -I frameledger.pyz <command> …`; on Windows `python -I`
or `py -I`. Every command takes `--json`, printing the JSON result
instead of text.

| Command | Does | Exit |
|---|---|---|
| `check FILE…` | says whether each file meets this spec | 0 all conform; 1 any breach; 3 unreadable |
| `report FILE` | cost ranking per pass and segment kind, bound-by share, worst frames | 0; 3 file error |
| `floor FILE --fps N [--warmup-s S] [--budget-ms B] [--no-windows] [--no-frames] [--allow-frames K]` | S8's two checks | 0 pass; 1 fail; 2 inconclusive; 3 error |
| `--selftest` | the analyser's own checks on built-in samples | 0 pass; 1 fail |
| `--version` | prints the version | 0 |

`floor` defaults: `--warmup-s 2`, `--budget-ms` = 1000/`--fps`
rounded up to three places (16.667 at 60, 6.945 at 144),
`--allow-frames 0`.

- **The timeline** is built by summing `frame/wall` from the first
  frame, in integer microseconds (each value is an exact number of
  them), never in floating point.
- **Windows** are half-open, `[start, start + 1 s)`. The first starts
  when the warm-up ends; a new one starts after each full second and at
  the end of every frame carrying `event/cut`. A frame belongs to the
  window holding its end. A cut frame, often a level load, also closes
  the window open when it starts. So no window overlaps it, and it is
  judged by the budget alone.
- **A window's frame rate** is the frames that end in it divided by one
  second, and is reported as `fps`. Their mean `frame/wall` is reported
  as `mean_ms`, or null when no frame ends in the window.
- **A window passes** when the mean `frame/wall` of the frames ending
  in it is at most 1000/`--fps` ms rounded up to three places (16.667
  at 60, 6.945 at 144, 16.684 at 59.94), whatever `--budget-ms` is. Up,
  because a display locked to N records walls either side of 1000/N.
  A window with no frame ending in it fails. So a steady 16.667 ms run
  passes at 60, though a window starting just before a frame ends holds
  only 59 frames.
- **The window check alone misses a single hitch** among fast frames:
  one 500 ms frame among 4 ms ones leaves its window's mean below
  16.667 ms. The frame check catches it, so `--no-frames` loses it.
- **A window shorter than one second** — cut short by an `event/cut`
  or by the end of the run — is skipped and counted, never judged.
- **A frame fails the budget** when its `frame/wall` is greater than
  the budget. Frames ending before the warm-up are not judged.
- **Inconclusive.** Dropped rows, no close line, a hole in the frame
  numbers, or a frame other than the last with no `frame/wall` make the
  window check inconclusive: a missing frame moves every later one into
  the wrong window. So does having no full window. The frame check is
  inconclusive on the same grounds, or when no frame ends after the
  warm-up, but more frames over the budget than `--allow-frames` fail
  it regardless: each such frame's own `frame/wall` is real. The
  summary says which applied.
- **Exit 3** besides a file error: `--no-windows` with `--no-frames`;
  a `--budget-ms` outside 0.001 to 999999999.999 ms or with more than
  three decimal places; and a `--fps` whose 1000/`--fps` ms is below
  0.001, or is 1000000000 or more once rounded up to three places,
  unless `--budget-ms` is given and the window check is off.

### 4.8 Text and JSON results

Text opens with plain sentences — every override and its reason,
dropped rows, an unfinished run, and the verdict — then tables no wider
than 100 columns. No meaning is carried by colour.

```json
{
  "frameledger": "0.1.0",
  "command": "floor",
  "verdict": "pass | fail | inconclusive | error | none | good | bad | skip | stop",
  "exit_code": 0,
  "summary": ["<the opening sentences, in order>"],
  "overrides": [{"field": "...", "reason": "..."}],
  "warnings": [{"code": "...", "message": "..."}],
  "result": { }
}
```

`result` is the command's own. For `floor`:
`{"windows": [{"start_s", "fps", "mean_ms", "pass"}], "windows_skipped",
"slow_frames": [{"frame", "segment", "wall_ms", "top_pass"}],
"frames_over_budget", "allowed", "rows_dropped", "finished"}`. For `report`:
`{"passes": [{"category", "name", "segment_kind", "depth", "median_ms",
"p99_ms", "share", "frames"}], "frame_times": [{"name", "segment_kind",
"median_ms", "p99_ms", "frames"}], "bound_by": {"cpu", "gpu", "applies"},
"worst_frames": [{"frame", "segment", "wall_ms", "top_pass"}],
"missing_gpu_frames", "static"}`. For `check`: `{"files": [{"path",
"breaches": [{"line", "rule", "message"}]}]}`. For `compare`: § 4.10.
For `bisect`, whose verdicts are the last four: § 4.11. For `budget`:
§ 4.12.

1% low is 1000 divided by the 99th-percentile `frame/wall`;
percentiles are nearest-rank.

The `report` result, agreed with the three engines for FLED-0003:

- **A frame's segment** is its `frame/cpu_span` row's, or else its
  first row's. Everything below is per segment kind; `segment_kind` is
  null for frames with no segment.
- **`passes`** holds the `cpu` and `gpu` rows of every depth, plus
  `cpu_remainder` and `gpu_remainder` as depth-0 entries. A pass counts
  only in frames that have its category's span. `frames` counts the
  frames it appears in; its median and 99th percentile are over those
  frames, since a pass absent from a frame did not run. `share` is its
  total time over its span's total time, from 0 to 1, rounded to four
  places. Entries are ranked by segment kind, then category, then total
  time, most first; ties by median, then name.
- **`frame_times`** holds each `frame` row name per segment kind.
  `frame/gpu_span` figures leave out frames without one; those are
  counted in `missing_gpu_frames`.
- **`bound_by`** is over frames with both spans: GPU-bound when
  `gpu_span` is greater than `cpu_span`, otherwise CPU-bound. With
  `pipelined` false, `cpu` and `gpu` are null and `applies` false.
- **`worst_frames`** are the 10 longest `frame/wall`, longest first,
  ties by frame number. `top_pass` is `category/name` of the frame's
  largest depth-0 `cpu` or `gpu` cost, remainders included.
- **`static`** is the static line exactly as written, or null.
- **`mem`, `event` and `ext.<engine>` rows** are not reported in 0.1.0.
- **No file path and no line number** appear in the summary, warnings
  or result, so INV-3 and INV-4 hold; warnings name the frame. A file
  `report` cannot read, or one with any breach, gives verdict `error`,
  exit 3, an empty `result`, and a summary naming the path and the
  first breach's line.
- **Opening sentences**: dropped rows, an unfinished run, one sentence
  per other kind of warning (the file's, then § 4.9's in its table
  order), frames without a GPU result; then the frame
  count, the costliest depth-0 pass per segment kind by total time, and
  the bound-by share or that it does not apply.

### 4.9 Trust warnings

`report` and `floor` warn on a run whose numbers should not be trusted
(S5). FLED-0005 builds this.

| Code | Warns when |
|---|---|
| `debug_build` | `build_type` is `debug`, in any case |
| `software_renderer` | `renderer` or `device` holds, in any case, `llvmpipe`, `lavapipe`, `softpipe`, `swrast`, `swiftshader`, `software rasterizer`, `gdi generic` or `microsoft basic render driver` |
| `cpu_load` | `load.start` is above 0.5 |
| `gpu_load` | `gpu_busy_pct.start` is above 20 |
| `settling_short` | `settled_frames` is below `settling_frames` |
| `too_few_frames` | fewer than 100 frames are measured: for `report`, frames with a `frame/wall`; for `floor`, frames ending after the warm-up |
| `cut_in_stretch` | an `event/cut` sits on a frame whose nearest earlier frame has the same segment; `floor` counts only frames ending after the warm-up |

- **A warning never changes a verdict or an exit code.** A Debug run
  that holds the floor passes, and says it was a Debug run.
- **An absent optional field gives no warning**: absent means unknown.
  `settling_short` needs both its fields.
- **Each message names what it judged**, and the threshold where there
  is one: `load.start` 0.62, above 0.5.
- **`check` gives none of these.** It judges the file, not the run.
- **Why 100 frames:** below that, the nearest-rank 99th percentile is
  the slowest frame, so the 1% low is one frame's time.
- **Why only `start` loads:** an `end` includes the run's own work.
- **A frame's segment** is as § 4.8 defines it. A cut on frame 0, or
  where the segment changes, starts a stretch and gives no warning. A
  missing frame is skipped, not taken as a change, since dropped rows
  can take a whole frame. A `cut_in_stretch` warning names the frame,
  one entry per cut.
- **Missing timings are already counted, never zeroed**: `gpu_missing`
  (INV-5), `wall_missing`, `frame_missing`, `cpu_span_missing`,
  `rows_dropped` and `unfinished`. FLED-0005 adds none.

### 4.10 Comparing labelled sets of runs

FLED-0008 builds this (S4, S5's refusal half, S16). Reviewed by the
three engines 2026-10-26; their changes are folded in.

```
compare --old FILE… --new FILE… [--override FIELD=REASON]… [--min-ms M] [--min-pct P]
```

Exit 0 pass, 1 a measure got slower, 2 inconclusive, 3 error or
refused. Defaults: `--min-ms 0.050`, `--min-pct 3`.

- **Runs are named by set and order**: `old-1`, `old-2`, … and
  `new-1`, …, in the order given. Warnings and sentences use these
  names, never the path.
- **Each set needs at least three runs**, or exit 3 (DOOM Ants). One
  run has no spread, and two give too many false changes (below).
  Interleave them: old-1, new-1, old-2, new-2, ….
- **A file that cannot be read, or breaks the format**, gives exit 3,
  as under `report`.

**Refusals.** Every run is held against every other, within a set and
across the two, on § 4.2's compare-blocking fields. `inputs` match when
they hold the same `name` and `hash` pairs, in any order; two empty
lists are unknown, not equal, so they refuse. An absent optional field
(`tier`, `ray_tracing`) matches only another absent one. Numbers match
by value: `render_scale` `1` matches `1.0`. Any mismatch
gives verdict `error`, exit 3, and a sentence naming each field with
the runs' values and the `--override` that would allow it. It follows
the overrides sentence, when there is one.

- **`--override FIELD=REASON`** allows one field to differ. `FIELD`
  must be a compare-blocking field and `REASON` must not be empty, or
  exit 3; so does a field given twice. Each override goes into `overrides`. The first sentence is
  one sentence naming every override with its reason (S5), whatever
  else the compare says.
- **An override for a field that does not differ** gives the warning
  `override_unused`, and is still named.

**Measures.** Each run gives one value per measure and segment kind
(§ 4.8's segment kind):

- `frame/wall` median and 99th percentile;
- `frame/cpu_span` and `frame/gpu_span` median;
- each `cpu` and `gpu` pass, every depth, remainders included: its
  median over the frames it appears in, as `report` gives it.

`frame/fence_wait` and `frame/present_wait` are not judged: a wait
moves when the work around it moves. `mem`, `event` and `ext` rows are
not judged.

A measure is judged only when every run of both sets has it. One
missing from some runs goes into `unmatched`, naming the runs that have
it, and judges nothing.

**Judging a measure.** Arithmetic is exact, in fractions; JSON gives
milliseconds rounded to four places, half away from zero.

- A set's **centre** is the median of its runs' values: the middle
  one, or the mean of the two middle ones.
- The **spread** is the larger of the two sets' ranges (highest run
  value minus lowest).
- The **change** is the new centre minus the old.
- The **floor** is the larger of `--min-ms` and `--min-pct` percent of
  the old centre. For a `gpu` pass, `gpu_remainder` and
  `frame/gpu_span` it is at least the largest `gpu_tick_ns` among the
  runs.

| Verdict | When |
|---|---|
| `slower` | the change is above the spread and at least the floor |
| `faster` | minus the change is above the spread and at least the floor |
| `noisy` | neither, and the spread is above 0 and at least the floor |
| `unchanged` | otherwise |

So each measure is judged by its own spread (S16): a pass that moved
is found even when `frame/wall` is `noisy`. The floor stops a pass
whose runs happen not to overlap from counting as a change: between
two sets from one build, about one measure in five would, at two runs
a set.

**How often two sets from one build fail.** Simulated 2026-10-26: 25
measures, each with normal run-to-run noise, the default floor; refute
by simulating it. The noise is its standard deviation as a share of
the measure.

| Runs a set | Noise 1% | Noise 2% |
|---|---|---|
| 2 | 2.5% | 68% |
| 3 | 1.2% | 35% |
| 5 | 0% | 3% |

An engine whose measures vary by more than about 1% between runs
gives more runs a set, or a higher `--min-pct`.

**The command's verdict**, first match wins:

1. `inconclusive` (exit 2) when any run has dropped rows or no close
   line, whatever the measures say (design: "nor a compare that uses
   them"). The first sentences name each such run and its drop count.
2. `fail` (exit 1) when any measure is `slower`.
3. `inconclusive` (exit 2) when the `frame/wall` median is `noisy` in
   any segment kind with at least 100 frames with a `frame/wall` in
   every run (§ 4.9's `too_few_frames` bound): re-run with more runs a
   set. A shorter kind, such as a loading stretch, is noisy almost
   every time; the summary names the kinds this step skipped
   (Vestige).
4. `pass` (exit 0) otherwise. A `faster` measure is reported, and does
   not change the verdict.

**Warnings** (`warnings`, one sentence per code):

- § 4.9's, for each run, its message opening with the run's name.
  `measured` is the run's frames with a `frame/wall`.
- `not_interleaved` — every run of one set started (`started_utc`)
  before every run of the other, so drift over time reads as a change.
- `mixed_build` — a set's runs differ in `commit` or `dirty`.
- `override_unused`, above.

**Static-line diff** (UT Ants). The static line is flattened to dotted
keys (`pipelines.opaque.vs_invocations`); an array is one value. Each
key whose value is not the same in every run is listed with every
run's value, exactly as written; absent is null. The text prints the
first 20 and counts the rest.

**Opening sentences**, in order: one sentence naming every override
and its reason; a refusal; each run's dropped rows or missing close
line; one per kind of warning; the verdict sentence, naming the slower
measure with the largest change in milliseconds, ties by percent (or
why it is inconclusive); the segment kinds step 3 skipped; the `frame/wall`
median per segment kind, old centre against new. A refusal ends the
compare after its warning sentences; a file that cannot be read still
opens with the overrides. Then a table of every measure not `unchanged`, then a
count of those that are, then the static diff.

**Result:**

```json
{
  "runs": [{"name", "set", "path", "run_id", "commit", "dirty", "started_utc",
            "rows_dropped", "finished"}],
  "min_ms", "min_pct",
  "measures": [{"segment_kind", "category", "name", "depth", "statistic",
                "old_ms": [], "new_ms": [], "old_centre_ms", "new_centre_ms",
                "change_ms", "change_pct", "spread_ms", "floor_ms", "verdict"}],
  "unmatched": [{"segment_kind", "category", "name", "depth", "statistic",
                 "present_in": []}],
  "static_diff": [{"key", "values": {}}],
  "refused": [{"field", "values": {}}]
}
```

`statistic` is `median` or `p99`; `old_ms` and `new_ms` list the runs'
values in run order; `change_pct` is the change over the old centre,
in percent to two places, or null when the old centre is 0; `values`
maps run names to values. Measures are ranked by segment kind, then
`frame` measures in § 4.8's `frame_times` order, then `cpu`, then
`gpu`, each by old centre, largest first. A refused compare gives only
`runs` and `refused`.

### 4.11 Bisect verdicts

FLED-0009 builds this (S17). Reviewed by the three engines 2026-10-26;
their changes are folded in.

```
bisect --tested FILE… --measure CATEGORY/NAME (--kind KIND | --segment KIND:ID | --unsegmented)
       [--statistic median|p99] [--depth D] [--override FIELD=REASON]… [--skip-straddle]
       (--bad-above X | --good FILE… --bad FILE… [--min-ms M | --min-mb M] [--min-pct P])
bisect --dry-run VALUE   with the same measure and mode flags, and no --tested
```

`--tested FILE…` are the runs of the commit under test, named
`tested-1`, … in the order given; the references are `good-1`, … and
`bad-1`, …. Every list of files follows its own flag, so a file cannot
join the wrong set: a bare file after `--bad b1 b2 b3` would otherwise
be a fourth bad run (UT Ants). Warnings and sentences use these names,
never the path.

**Exit codes** are `git bisect run`'s (docs/design.md § Exit codes):
0 good, 1 bad, 125 skip this commit, 128 stop the bisect. `git bisect
run` reads 0 as good and every code from 1 to 127 except 125 as bad.
So on a bisect command line, one whose first argument not starting
with `-` is `bisect`, every other outcome is 128 (DOOM Ants). The
options before the command take no value, so that first argument is
always the command.

- a bad argument;
- `--help`, `-h` and `--version`, which exit 0 elsewhere, and
  `--selftest`, which is not a bisect;
- an error anywhere in the analyser, from reading the arguments to
  printing the result, which would otherwise exit 1;
- a write to standard output that fails, such as a pipe closed early
  or a full disk, which Python would end with 120 (UT Ants, DOOM Ants).

A bad argument or an error inside the analyser is reported on standard
error alone; standard output holds nothing, with or without `--json`.
A standard output closed before the start is not a failed write: no
one asked for the sentences, so they are dropped, and the exit code is
the verdict's (DOOM Ants).

Not covered: a failure before the analyser's own code runs, such as a
missing or too old `python3` or a broken archive. A shell exits 127
when it cannot find `python3`, which reads as bad. Running the dry run
below by hand first shows these.

A script builds, runs the benchmark, then calls `bisect`. A build that
fails skips. The run files are deleted first, so a benchmark that
writes nothing skips too, rather than leaving the last commit's files
to be judged. Three tested runs, as here, give a steadier value; one is
allowed.

```
git bisect run sh -c 'make || exit 125; rm -f t1.csv t2.csv t3.csv; for i in 1 2 3; do ./bench --out t$i.csv; done; python3 -I frameledger.pyz bisect --tested t1.csv t2.csv t3.csv --measure gpu/opaque --kind view --good g1.csv g2.csv g3.csv --bad b1.csv b2.csv b3.csv'
```

**The measure** is one of § 4.10's, or a `mem` row (Vestige):

- `--measure` splits at its first `/`: `frame/wall`, `frame/cpu_span`,
  `frame/gpu_span`, a `cpu` or `gpu` pass (remainders included), or a
  `mem` name such as `mem/gpu_mb`. Any other category, or a frame
  measure § 4.10 does not judge, is 128.
- **Which frames**, exactly one of: `--kind KIND`, the frames of that
  segment kind (S2); `--segment KIND:ID`, the frames of that one
  segment, so a slowdown in one camera view is not pooled away (UT
  Ants); `--unsegmented`, frames with no segment. A frame's segment is
  § 4.8's. A `KIND` holding `:`, or a `--segment` without both parts,
  is 128, since it would skip every commit (Vestige, DOOM Ants).
- `--statistic` is `median`, the default, or `p99` for `frame/wall`
  only, as § 4.10 judges them. `p99` on another measure is 128.
- `--depth D` picks the measure's depth; on a frame measure, which has
  no depth to pick, it is 128 (Vestige, UT Ants). Without it, every
  run must have the name at one and the same depth, or 128, naming each
  run's depths: a name at two depths in one run, in different frames,
  or at another depth in another run (Vestige, DOOM Ants).
- **A run's value** is § 4.10's: the measure's median, or `frame/wall`'s
  99th percentile, over the chosen frames that have it. A `mem`
  measure's value is the median of its rows in the chosen frames. That
  median is `report`'s nearest rank, the lower middle of an even count,
  not a set's centre below.
  Values and thresholds are in the measure's unit: ms, or MB for `mem`.
- **The tested value** is the tested runs' centre, as § 4.10 defines
  it.
- **Arithmetic is exact**, in fractions, as § 4.10's. Sentences and
  JSON give values exactly too, every one a finite decimal, and
  sentences print at least three places, so "10.0005 ms, above 10.000
  ms" shows why it is bad.

**The runs must match.** Every run, tested and reference, is held
against every other on § 4.10's compare-blocking fields, as its
refusals are, in both modes: tested runs of one commit that differ in
`scene` would be judged silently otherwise (DOOM Ants). A mismatch is
128, and the sentence names each field, the runs' values and the
`--override` that would allow it. `--override` and its
`override_unused` warning are § 4.10's.

**Threshold mode.** `--bad-above X`: bad when the tested value is above
`X`, good when it is `X` or less. `X` has at most three decimal places
and is below 1000000000. `--min-ms`, `--min-mb` and `--min-pct` are 128
here, since none of them would change anything.

**Reference mode.** `--good FILE…` and `--bad FILE…`: runs of a
known-good and a known-bad commit. Bad when the tested value is above
the **midpoint** of the good and bad centres, good when it is at the
midpoint or below. Before any tested run is read, each of these is 128:

- a reference set of fewer than three runs: one run has no spread, as
  under § 4.10, and one noisy reference would move the midpoint for
  every commit (Vestige, DOOM Ants);
- a reference with dropped rows, no close line, a breach, or that cannot
  be read ("a broken reference file", docs/design.md), named as
  `good-2` and with its reason, not its path;
- a reference without the measure;
- a bad centre that is not **slower** than the good one, as § 4.10
  judges a measure, with the good runs as old: above the spread and at
  least the floor. A bad centre below the good one is reported as
  references the wrong way round; one equal to it or above it but not
  slower, as references that do not separate;
- a reference on the wrong side of the midpoint: a good run above it,
  or a bad run at it or below (Vestige). Otherwise a good run could
  itself be judged bad, and nothing later in the bisect would show it.

**The floor** is § 4.10's: the larger of `--min-ms` (default 0.050) and
`--min-pct` (default 3) percent of the good centre, and for a `gpu`
pass, `gpu_remainder` and `frame/gpu_span` at least the largest
`gpu_tick_ns` among the references. For a `mem` measure, `--min-mb`
(default 1.000, as Vestige's `perf_gate.py`) stands in for `--min-ms`,
and `gpu_tick_ns` does not apply. `--min-mb` on a ms measure, or
`--min-ms` on a `mem` one, is 128: a floor in the wrong unit would
silently do nothing. On `mem` the percent usually decides: 3 percent of
500 MB is 15 MB, so `--min-mb 1` matters only with a lower `--min-pct`.

**Tested runs on both sides of the line.** With two or more tested
runs, they straddle when one run's value is above the line (`X` or the
midpoint) and another's is at it or below. By default the centre still
decides, and the warning `tested_straddle` names each run's value, so a
verdict near the line leaves a trace in the bisect log. More tested
runs straddle more often, so a default skip would punish the steadier
setup, and a gradual slowdown would end in a range rather than a
commit (UT Ants, DOOM Ants). `--skip-straddle` skips (125) instead, for
an engine that prefers a visible skip to a silent wrong turn
(Vestige). One tested run cannot straddle. `--skip-straddle` with
`--dry-run` is 128, since a dry run has no tested runs.

**Skip (125).** Each of these makes the tested commit untestable,
whatever its value: a tested file that is missing, cannot be read or
breaks the format (UT Ants); a tested run with dropped rows or no close
line (docs/design.md: "nor a compare that uses them"); a tested run
without the measure in the chosen frames. An empty file, the commonest
remains of a crashed benchmark, is one that breaks the format. Each
such run has its own sentence naming it and why. For a missing
measure it also names the segment kinds the run has, or with
`--segment` its segments, so a wrong `--kind` shows on the first skip.

**Dry run.** `--dry-run VALUE` judges `VALUE` as the tested value, in
the measure's unit, with at most three decimal places, and reads no
tested file. With references, every reference check above runs, and
an override no reference needs warns `override_unused`. It
exits with the code the value would get: 0, 1, or 128 when a check
fails. Its verdict sentence opens "Dry run:", so a `--dry-run` left in
a bisect script shows why every commit gets one answer (DOOM Ants). Run
it by hand with a value from each side before `git bisect run`: it is
the guard against an inverted verdict.

**Warnings**: § 4.9's for each tested run, its message opening with the
run's name; `override_unused`; `dirty_build`, for a tested run with
`dirty` true, which may not be the commit under test (Vestige); and
`tested_straddle`, above. A warning never changes the exit code.

**Opening sentences**, in order: one naming every override and its
reason; why the bisect stops, then "The bisect stops (exit 128)."; each
tested run's dropped rows or missing
close line, or why it skips; one per kind of warning; the verdict
sentence. That sentence gives the tested value, the threshold or the
midpoint with both references' centres, and the exit code: "gpu/opaque
median in view segments is 12.300 ms, above the midpoint of 11.150 ms
between the good runs' 10.000 ms and the bad runs' 12.300 ms: bad
(exit 1)."

**Result.** The verdict is `good`, `bad`, `skip` or `stop`.

```json
{
  "measure": {"segment_kind", "segment", "category", "name", "depth", "statistic", "unit"},
  "dry_run": false,
  "runs": [{"name", "set", "path", "run_id", "commit", "dirty",
            "rows_dropped", "finished", "value"}],
  "value", "bad_above",
  "references": {"good_centre", "bad_centre", "spread", "floor"},
  "refused": [{"field", "values": {}}]
}
```

`segment` is the `--segment` given, or null; `segment_kind` is its
kind, or `--kind`'s, or null for `--unsegmented`. `set` is `tested`,
`good` or `bad`. `unit` is `ms` or `MB`. `value` is the tested value, or
the dry run's `VALUE`; null on `skip` and `stop`. A run's own `value` is
null when it has none. `bad_above` is `X` or the midpoint. `references`
is null in threshold mode.

### 4.12 Pass budgets

FLED-0010 builds this (S12). Reviewed by the three engines 2026-10-29;
their changes are folded in, for their confirmation.

```
budget FILE --budgets BUDGETS [--warmup-s S]
```

Exit codes are § 4.7's ladder: 0 every budget holds; 1 a pass is over
budget; 2 inconclusive; 3 an error in either file.

**The budget file** is UTF-8 CSV, as § 4.1's: LF or CRLF, `.` as the
decimal point, fields quoted CSV-style. A blank line is skipped
(Vestige).

```
# frameledger-budget {"schema":1,"match":{"tier":"high"}}   line 1, required
category,name,kind,depth,statistic,limit_ms           column line, required
gpu,ssao,view,0,p99,2.000                             one budget per line
cpu,cpu_remainder,*,,median,1.500
# any later line beginning # is a comment
```

| Column | Rule |
|---|---|
| `category` | `cpu` or `gpu` |
| `name` | a pass name, as § 4.4's; `cpu_remainder` and `gpu_remainder` included |
| `kind` | a segment kind; `*` for every kind in the run, frames with no segment included, each judged apart; empty for frames with no segment |
| `depth` | an integer from 0, or empty |
| `statistic` | `median` or `p99` |
| `limit_ms` | 0.001 to 999999999.999, at most three places |

- **A budget's value is `report`'s figure**: the pass's median or 99th
  percentile over the frames of its kind that have it, as § 4.8
  defines `passes`, less any warm-up. A frame without its category's
  span is left out, never counted as 0 (INV-5). Values and limits are exact thousandths.
- **A pass is over budget** when its value is greater than the limit.
  Equal holds. A single frame never breaches: the statistic is over
  the run (DOOM Ants, DOOM-0502).
- **A pass budget is not a frame-time budget.** With frames in
  flight, two frames' passes overlap, so a frame's pass limits need not
  add up to its frame time. `floor` judges frame time (DOOM Ants).
- **`*` takes every kind**, a warm-up kind too. A run with one names
  its kinds instead of using `*` (DOOM Ants).
- **A named kind replaces `*`** for that kind, on a line with the same
  `category`, `name`, `depth` and `statistic` (UT Ants).
  `gpu,ssao,*,,p99,2.000` with `gpu,ssao,view,,p99,3.000` judges view
  at 3.000 and every other kind at 2.000.
- **`match`**, optional, names § 4.2's compare-blocking fields and the
  values the budgets were set for (UT Ants). The run's values must
  match as § 4.10's refusals match runs: numbers by value, `inputs` as
  `name` and `hash` pairs in any order. A field the run leaves out does
  not match. A mismatch is exit 3, naming each field with both values.
- **`--warmup-s S`**, default 0, leaves out frames ending before S
  seconds, on § 4.7's timeline, as `floor` does (Vestige). At 0 every
  value is `report`'s (UT Ants, DOOM Ants); at 2 the frames judged are
  `floor`'s. Above 0, a hole in the frame numbers or a frame other
  than the last with no `frame/wall` makes the verdict inconclusive:
  the frames after it cannot be placed. A negative `S` is exit 3.
- **An empty `depth`** needs the name at one depth in the frames
  judged, as § 4.11's `--depth`; at two it is exit 3, naming the pass
  and both depths (Vestige).
- **A budget nothing matches** is never a pass: a renamed pass would
  otherwise hold its budget forever. A `kind` not in the run, a pass
  in no frame of its kind, or a `*` pass in no frame at all is listed
  in `unmatched` and named in a sentence. It makes the verdict
  inconclusive; it is not a warning. A re-run gives the same: the fix
  is in the budget file or the engine (Vestige).
- **Dropped rows or no close line** make the verdict inconclusive: the
  frames judged may be missing their costliest rows.
- **A pass over budget fails regardless** of either, as § 4.7's frame
  check does: its value is over the frames that were measured.
- **`budget_few_frames`** warns when a `p99` budget is judged over
  fewer than 100 frames: below that, the nearest-rank 99th percentile
  is the slowest frame. § 4.9's warnings are given too. A warning never
  changes a verdict.
- **Exit 3** for the budget file: no header or a `schema` other than
  1, a `match` key that is not a compare-blocking field, a different
  column line, a value breaking its column's rule, or two lines with
  the same `category`, `name`, `kind`, `depth` and `statistic`. The
  summary names the budget file's line. For the run file, as
  `report`'s.

**Text** opens with § 4.8's sentences, then one sentence per pass over
budget, most milliseconds over first, then one per unmatched budget:
"gpu/ssao p99 in view segments is 2.310 ms, over its 2.000 ms
budget." Then the verdict, and a table of every
budget judged.

**Result.** The verdict is `pass`, `fail`, `inconclusive` or `error`.

```json
{
  "budgets": [{"line", "category", "name", "segment_kind", "depth",
               "statistic", "limit_ms", "value_ms", "over_ms", "frames", "over"}],
  "unmatched": [{"line", "category", "name", "segment_kind", "depth", "statistic"}],
  "warmup_s", "rows_dropped", "finished"
}
```

`over_ms` is `value_ms` minus `limit_ms`, exactly; negative when the
budget holds (DOOM Ants, UT Ants). The sentences rank by it.
`segment_kind` in `unmatched` is the line's `kind`: `*`, a kind, or
null for an empty one.

`budgets` holds one entry per budget line and kind judged, in the
file's order, then § 4.8's kind order. `line` is the budget file's
line. A `*` line gives one entry per kind the pass appears in, except
a kind a named line replaces.

## 5. Invariants

Each clause names its fixture under `tests/fixtures/` and the one rule that fixture
breaks.

- **INV-1** — A file whose first line is not a `# frameledger` header
  fails `check` with exit 1 and fails `report` and `floor` with exit 3.
  *Test:* `tests/test_check.py::test_missing_header`, fixture
  `no-header.csv` (valid in every other way).
  *Breaks when:* the reader skips blank or unknown lines looking for a
  header further down.

- **INV-2** — A file with `schema` greater than the analyser's fails
  with exit 3 and a message naming both versions; a file with an older
  supported schema is read.
  *Test:* `tests/test_check.py::test_schema_versions`, fixtures
  `schema-99.csv` and `schema-1.csv`.
  *Breaks when:* the reader ignores `schema`.

- **INV-3** — The same rows with LF and with CRLF line endings give
  byte-identical `report --json` output.
  *Test:* `tests/test_ledger.py::test_crlf_equals_lf`, fixture
  `small-run.csv` and its CRLF copy made by the test.
  *Breaks when:* `\r` stays on the last field and `value` fails to
  parse, or a name gains a trailing `\r`.

- **INV-4** — Rows are joined on `(run_id, frame)` whatever their
  order: a file with each frame's GPU rows written two frames late gives
  the same `report --json` as the file in frame order.
  *Test:* `tests/test_ledger.py::test_late_gpu_rows`, fixtures
  `in-order.csv` and `gpu-late.csv` (same rows, reordered).
  *Breaks when:* the reader assigns rows to the most recent frame seen.

- **INV-5** — A frame with no `frame/gpu_span` row is counted in
  `missing_gpu_frames` and left out of GPU statistics; it is never
  counted as 0 ms.
  *Test:* `tests/test_report.py::test_missing_gpu_span`, fixture
  `gpu-missing.csv` (one frame lacks the row; every other gpu_span is
  10.000).
  *Breaks when:* a missing value defaults to zero, which drags the GPU
  median below 10.000.

- **INV-6** — A `value` written with a comma decimal point or with
  other than three decimal places is a `check` breach naming the line.
  *Test:* `tests/test_check.py::test_value_format`, fixture
  `comma-decimal.csv`, whose bad values are a quoted `"1,250"` (so the
  column count is right) and `1.25`.
  *Breaks when:* the reader parses `value` with `float()` alone, which
  accepts `1.25`, or swaps a comma for a point before parsing.

- **INV-7** — `floor` returns inconclusive (exit 2) when the close line
  is missing or `rows_dropped` is above zero, even if every window and
  frame passes, and says why in the first summary sentence. A frame
  over the budget still fails it (exit 1).
  *Test:* `tests/test_floor.py::test_unfinished_and_dropped`, fixtures
  `passing-run.csv`, the same without its close line, and the same
  with `rows_dropped` 3; `tests/test_floor.py::test_frame_failure_stands_under_drops`,
  `fast-with-one-spike.csv` with `rows_dropped` 1.
  *Breaks when:* `floor` judges only the rows it has, or lets a drop
  excuse a slow frame.

- **INV-8** — A window passes when the mean `frame/wall` of the frames
  ending in it is at most 1000/`--fps` ms rounded up to three places: 58
  frames of 16.000 ms and one of 71.000 ms end inside one window, a
  mean of 16.932 ms, so it fails `--fps 60`, although the mean of the
  per-frame rates is above 61. Frames of exactly 16.667 ms pass, even
  in a window holding only 59 of them. Frames locked to 144 Hz or
  59.94 Hz, their walls either side of 1000/N, pass at that rate. A
  frame ending exactly on a window's end belongs to the next window.
  *Test:* `tests/test_floor.py::test_window_rate`, fixtures
  `one-hitch.csv` (that second, just after the warm-up, followed by
  full 60 FPS seconds) and `edge-frame.csv` (59 frames of 16.100 ms,
  then one of 51.100 ms ending exactly at the window's end, which would
  raise the mean to 16.683 ms if counted);
  `tests/test_floor.py::test_steady_frame_time_passes`,
  `exact-budget.csv` with `--warmup-s 1.98339`, each with `--no-frames`
  so only the window check can fail;
  `tests/test_floor.py::test_vsync_rates_pass`, walls built from
  display ticks rounded to whole microseconds.
  *Breaks when:* the window is judged by the mean of 1000/wall or by
  counting its frames against N, or the timeline is summed in floating
  point, or windows are closed at both ends, or 1000/N is rounded to
  the nearest.

- **INV-9** — One frame over `--budget-ms` fails `floor` (exit 1) even
  when every window passes; `--no-frames` turns that check off;
  `--allow-frames 1` tolerates exactly one; a 16.667 ms frame passes the
  default 60 FPS budget.
  *Test:* `tests/test_floor.py::test_single_frame_budget`, fixtures
  `fast-with-one-spike.csv` (120 FPS windows, one 30.000 ms frame) and
  `exact-budget.csv` (every frame 16.667).
  *Breaks when:* only windows are judged, or the allowance is
  off by one.

- **INV-10** — With `pipelined` false, `report` sets
  `bound_by.applies` to false and its summary says the CPU/GPU share
  does not apply.
  *Test:* `tests/test_report.py::test_bound_by_not_pipelined`, fixtures
  `pipelined.csv` and the same with `pipelined` false.
  *Breaks when:* the share is printed from `gpu_span > cpu_span`
  regardless.

- **INV-11** — The remainder is the span minus the sum of that
  category's depth-0 rows; depth-1 rows are not subtracted.
  *Test:* `tests/test_report.py::test_remainder`, fixture
  `nested.csv` (gpu_span 10.000; depth-0 rows 4.000 and 3.000; a
  depth-1 row 2.000 under the first) → `gpu_remainder` 3.000.
  *Breaks when:* every depth is subtracted, giving 1.000.

- **INV-12** — Static statistic values come out of `report --json`
  as the exact strings written.
  *Test:* `tests/test_report.py::test_static_exact`, fixture
  `static-hash.csv` holding `"17436423623014656123"`.
  *Breaks when:* the value is converted to a float on reading.

- **INV-13** — The text report's opening sentences equal the JSON
  `summary` array, in order.
  *Test:* `tests/test_render.py::test_text_matches_json`, over every
  fixture.
  *Breaks when:* text and JSON are built separately.

- **INV-14** — The writer header compiles with no warnings as C99 and
  as C++17 under GCC, Clang and mingw-w64 at
  `-Wall -Wextra -Wpedantic -Werror`, and its object file references no
  allocation, file I/O or `printf`-family symbol.
  *Test:* `tests/writer/test_compile.sh`, which also builds one C file
  and one C++ file into one program sharing a writer, and runs `nm -u`
  on each object.
  *Breaks when:* the header calls `malloc`, `fopen` or `snprintf`, uses
  syntax one language rejects, defines a function not `static inline`,
  or lacks the `extern "C"` guards.

- **INV-15** — With a buffer that fills, `fled_row` returns
  `FLED_DROPPED`, and the close line's `rows_dropped` equals the number
  of such returns.
  *Test:* `tests/writer/test_writer.c::test_drops`, a buffer sized for
  the header plus ten rows, fed twenty.
  *Breaks when:* the close line is not reserved and itself gets
  dropped, or drops are not counted.

- **INV-16** — Writer output passes `check`, with `setlocale(LC_ALL,
  "de_DE.UTF-8")` in force.
  *Test:* `tests/writer/test_writer.c::test_output_conforms`, piped to
  `check`.
  *Breaks when:* the writer formats numbers through the locale.

- **INV-17** — `fled_row` rejects a name over `FLED_NAME_MAX` bytes
  with `FLED_BAD_ARG` and writes nothing, so no row exceeds
  `FLED_ROW_MAX`.
  *Test:* `tests/writer/test_writer.c::test_name_limit`, a 65-byte name.
  *Breaks when:* the name is truncated or written whole.

- **INV-18** — `floor` starts a new window at the end of every frame
  carrying `event/cut` and closes the one open when it starts, so that
  frame is in no window, and skips, and
  counts in `windows_skipped`, every window shorter than one second;
  with no full window the window check is inconclusive.
  *Test:* `tests/test_floor.py::test_cuts_and_partial_windows`,
  fixtures `cut-mid-second.csv` (a 0.5 s stretch of 20 FPS frames
  between two cuts, the rest at 60 FPS) and `short-views.csv` (every
  view under one second); `tests/test_floor.py::test_cut_frame_is_left_out_of_windows`
  (a 400 ms cut frame), `tests/test_floor.py::test_long_cut_frame_overlaps_no_window`
  (a 3000 ms one) and `tests/test_floor.py::test_cut_on_a_window_boundary`.
  *Breaks when:* windows ignore cuts, so the slow stretch drags a mixed
  window below 60, a cut frame is counted in a window, a cut frame
  longer than a second leaves windows no frame ends in, or a partial
  window is judged.

- **INV-19** — The writer rounds to thousandths with ties away from
  zero: `0.0625` is written `0.063` and `-0.0625` is written `-0.063`.
  *Test:* `tests/writer/test_writer.c::test_rounding` (both values are
  exact in binary, so the tie is real).
  *Breaks when:* the writer truncates, or rounds ties to even.

- **INV-20** — `fled_row` returns `FLED_BAD_ARG` and writes nothing for
  NaN, infinity and 1e9.
  *Test:* `tests/writer/test_writer.c::test_bad_values`.
  *Breaks when:* the value is formatted without a range check, writing
  an over-long row or `nan`.

- **INV-21** — A negative `gpu` value is read, kept, and named in the
  opening sentences of `check` and `report`; a `frame/wall` of zero or
  less is a `check` breach; the last frame's missing `frame/wall` is
  neither.
  *Test:* `tests/test_check.py::test_negative_and_last_wall`, fixture
  `negative-gpu.csv` (one gpu row of -0.004, a run whose last frame has
  no wall) and `zero-wall.csv`.
  *Breaks when:* negatives are clamped or rejected, or the last frame
  is reported as missing its wall.

- **INV-22** — `fled_consume` frees space: a buffer sized for ten rows
  takes thirty when the engine consumes after every ten, with no drops.
  *Test:* `tests/writer/test_writer.c::test_consume_reuses`.
  *Breaks when:* consumed bytes are only marked, not reclaimed.

- **INV-23** — A run that differs from `passing-run.csv` in one header
  field gives that field's § 4.9 warning under `report` and `floor`,
  with the same verdict and exit code, and its message names the value:
  `build_type` `"Debug"`, `renderer` `"LLVMpipe (LLVM 19)"`, `device`
  `"GDI Generic"`, `load.start` 0.51, `gpu_busy_pct.start` 21.
  `load.start` 0.5 and `gpu_busy_pct.start` 20 give none.
  *Test:* `tests/test_trust.py::test_header_warnings`, runs built from
  `passing-run.csv`'s rows with the header changed by the test.
  *Breaks when:* a match is case-sensitive, a threshold is `≥` rather
  than `>`, or a warning turns the pass into another verdict.

- **INV-24** — `report` warns `too_few_frames` on 99 frames with a
  `frame/wall` and not on 100; `floor` warns on 99 frames ending after
  the warm-up and not on 100, however many end inside it.
  *Test:* `tests/test_trust.py::test_too_few_frames`, runs of 16 ms
  frames built by the test.
  *Breaks when:* `floor` counts the warm-up's frames, or the bound is
  `≤`.

- **INV-25** — `report` and `floor` warn `settling_short` when
  `settled_frames` is 3 and `settling_frames` 4, and not when both are
  4 or either is absent.
  *Test:* `tests/test_trust.py::test_settling`, runs built from
  `passing-run.csv`'s rows with the header changed by the test.
  *Breaks when:* the bound is `≤`, one command skips it, or an absent
  field reads as zero.

- **INV-26** — An `event/cut` on a frame whose nearest earlier frame
  has the same segment gives `cut_in_stretch` naming that frame, also
  across a missing frame; a cut where the segment changes, or on frame
  0, gives none; under `floor`, a mid-segment cut on a frame ending
  inside the warm-up gives none.
  *Test:* `tests/test_trust.py::test_cut_in_stretch`, runs built by the
  test, and `cut-mid-second.csv`, whose cuts all change segment.
  *Breaks when:* every cut warns, so `cut-mid-second.csv` does, a
  warm-up cut warns under `floor`, or a cut after a missing frame goes
  unjudged.

- **INV-27** — A run with no optional header field gives no § 4.9
  warning, and `check` gives none of them on any run.
  *Test:* `tests/test_trust.py::test_absent_fields_and_check`,
  `passing-run.csv` and its Debug copy from INV-23.
  *Breaks when:* an absent field reads as a value that warns, or
  `check` reports a trust warning.

- **INV-28** — A refused `fled_open` leaves the writer with nothing
  pending, whatever its memory held before, and refuses rows.
  *Test:* `tests/writer/test_writer.c::test_failed_open`, a writer
  filled with `0xa5` and a 16-byte buffer.
  *Breaks when:* `fled_open` returns before resetting the writer, so
  `fled_pending` hands back a stale pointer and length.

- **INV-29** — `fled_open` takes any header `fled_json_escape` built:
  DEL and control characters come out as `\u00XX`.
  *Test:* `tests/writer/test_writer.c::test_escape_opens`.
  *Breaks when:* the escape passes a byte `fled_open` refuses.

- **INV-30** — Two sets from one build report no difference, and a
  known slowdown is reported (S4). Each run's frames are all alike:
  `frame/wall` 16.000, `frame/cpu_span` 8.000, `frame/gpu_span`
  12.000, `cpu/sim` 5.000, and a `gpu/opaque` pass. Opaque in old runs
  10.000, 10.010 and 10.020, in new runs 10.010, 10.020 and 10.030:
  every measure `unchanged`, verdict `pass`, exit 0. New runs 11.000,
  11.010 and 11.020: `gpu/opaque` `slower`, change 1.000 ms,
  `gpu_remainder` `faster`, every other measure `unchanged`; verdict
  `fail`, exit 1, and the verdict sentence names `gpu/opaque`.
  With two slower measures, the sentence names the larger change in ms,
  and of two equal in ms, the larger in percent.
  *Test:* `tests/test_compare.py::test_same_build_and_known_slowdown`,
  runs built by the test; `tests/test_compare.py::test_largest_slower_measure_is_named`.
  *Breaks when:* the compare judges one run against one run, or never
  finds a change, or a measure the runs do not move is judged changed,
  or the wrong slower measure is named.

- **INV-31** — A pass is judged by its own spread, not the frame
  total's (S16). `frame/wall` per run: old 24.900, 28.000 and 32.600,
  new 25.900, 29.000 and 33.600, so its median is `noisy` (change
  1.000, spread 7.700, floor 0.840). `gpu/opaque`: old 18.200, 18.250
  and 18.300, new 19.500, 19.550 and 19.600, so it is `slower`. Verdict `fail`, exit 1. Without the
  opaque change the verdict is `inconclusive`, exit 2. Without it, and
  with every run holding 99 frames, the verdict is `pass` and the
  summary names the skipped kind.
  The spread is the wider set's range, whichever set that is. A kind
  missing from a run counts 0 frames there.
  *Test:* `tests/test_compare.py::test_pass_judged_by_own_spread`,
  `tests/test_compare.py::test_spread_is_the_wider_set`,
  `tests/test_compare.py::test_short_kind_missing_from_the_first_run`.
  *Breaks when:* every measure is judged against `frame/wall`'s spread,
  so opaque is missed; or the spread is ignored, so `frame/wall` reads
  `slower`; or a short segment kind makes the compare inconclusive; or
  one set's range stands for both.

- **INV-32** — A change beyond the spread but under the floor is
  `unchanged`. Every old run's `gpu/opaque` is 10.000 and every new
  run's 10.040, a change of 0.040 ms, under the default floor of
  0.300. With `--min-ms 0.010 --min-pct 0` it is `slower`. With
  `gpu_tick_ns` 100000 (0.100 ms) in one run's header and those flags,
  it is `unchanged` again, and so is a 0.040 ms change in
  `frame/gpu_span`.
  At a floor of 0.100: a change equal to the spread is `noisy`, a change
  equal to the floor is `slower`, a spread equal to the floor is
  `noisy`. At a floor of 0, identical sets pass.
  *Test:* `tests/test_compare.py::test_floor`, `tests/test_compare.py::test_verdict_edges`,
  `tests/test_compare.py::test_zero_floor`.
  *Breaks when:* the floor is not applied, or `gpu_tick_ns` is ignored
  or left off `frame/gpu_span`, or a bound is strict where the table
  says "at least", or runs that do not vary read `noisy`.

- **INV-33** — Runs differing in a compare-blocking field are refused,
  and an override with a reason allows it (S5). `new-2` with
  `resolution` `[2560,1440]`: verdict `error`, exit 3, `refused` names
  `resolution` with every run's value. With `--override
  "resolution=upscaler test"`: compared, `overrides` holds the field
  and reason, and the first sentence names both. With the same
  override and a matching `new-2`, the first sentence still names it,
  with the warning `override_unused`. With a valid override and a
  second field differing, the first sentence is the override's and the
  second the refusal's. Two runs whose `inputs` are both `[]` are
  refused, and so are two differing only in `vsync`, or only in
  `scene`. `--override pipelined=x` and `--override resolution=` exit
  3.
  `render_scale` `1` against `1.0` compares; inputs listed in another
  order compare; a `tier` in one run only refuses. The overrides
  sentence stays first beside an incomplete run, a refusal with its
  warning sentences, and an unreadable file; a field overridden twice
  exits 3.
  *Test:* `tests/test_compare.py::test_refusal_and_override`,
  `tests/test_compare.py::test_header_matching`, `tests/test_compare.py::test_equal_numbers_match`,
  `tests/test_compare.py::test_overrides_stay_first`.
  *Breaks when:* a field is not compared, an override is silent or
  not first, empty inputs count as equal, or numbers match as text.

- **INV-34** — A run with dropped rows, or with no close line, makes
  the compare `inconclusive`, exit 2, even with a `slower` measure, and
  the first sentence after any overrides sentence names the run and
  its drop count.
  *Test:* `tests/test_compare.py::test_incomplete_run`, INV-30's
  slowdown sets with `rows_dropped` 3 in `new-1`, then with `old-2`'s
  close line removed.
  *Breaks when:* a `slower` measure wins over the incomplete run.

- **INV-35** — `not_interleaved` warns when every old run started
  before every new run, and not for old, new, old, new; it changes no
  verdict.
  It fires whichever set ran first. `mixed_build` warns when a set's
  runs differ in `commit`.
  *Test:* `tests/test_compare.py::test_interleaving`, INV-30's
  same-build sets with `started_utc` set by the test;
  `tests/test_compare.py::test_set_warnings`.
  *Breaks when:* the order given on the command line is judged instead
  of `started_utc`, or the warning changes the exit code.

- **INV-36** — A set of two runs exits 3. A measure present in only
  some runs goes into `unmatched` and is not judged.
  *Test:* `tests/test_compare.py::test_runs_and_unmatched`.
  *Breaks when:* one run's spread is taken as zero, or a missing
  measure is taken as zero.

- **INV-37** — The static diff lists each dotted key whose value
  differs between runs, with each run's exact string, and no key that
  is the same in all.
  *Test:* `tests/test_compare.py::test_static_diff`, runs whose static
  lines differ in one nested statistic.
  *Breaks when:* values are converted to numbers, or equal keys are
  listed.

- **INV-38** — A set of four runs has the mean of its two middle runs
  as its centre, and JSON rounds half away from zero: old runs all
  10.000, new runs 9.999, 10.000, 9.999 and 10.000 give a new centre of
  9.9995, a change of -0.0005 ms and a `change_pct` of -0.01, not 0.
  *Test:* `tests/test_compare.py::test_even_sets_and_rounding`.
  *Breaks when:* the centre is the lower middle, or rounding is half
  to even or toward zero.

- **INV-39** — Threshold mode: a value equal to `X` is good, and the
  tested value is the exact centre. One tested run whose `view` frames
  all have `gpu/opaque` 10.000: `--bad-above 10.000` exits 0,
  `--bad-above 9.999` exits 1. Four tested runs at 9.000, 9.000, 11.000
  and 11.000 have a tested value of 10.000: `--bad-above 9.999` exits 1
  and `--bad-above 10.000` exits 0. Runs at 9.000, 9.000, 11.000 and
  15.000 (centre 10.000, mean 11.000) exit 0 at `--bad-above 10.000`.
  Runs at 10.000 and 10.001 (centre 10.0005) exit 1 at `--bad-above
  10.000`, and the verdict sentence shows 10.0005.
  *Test:* `tests/test_bisect.py::test_threshold_edges`,
  `tests/test_bisect.py::test_tested_centre`,
  `tests/test_bisect.py::test_exact_comparison`,
  `tests/test_bisect.py::test_equal_sentence`,
  `tests/test_bisect.py::test_five_place_midpoint`, runs built by the test.
  *Breaks when:* a value at `X` reads bad, or one tested run stands for
  all, or the centre is the lower middle, the upper middle or the mean,
  or values are rounded before they are compared.

- **INV-40** — Reference mode judges against the midpoint of the
  centres, and stops on references that do not separate. Good runs'
  `gpu/opaque` 10.000, 10.000 and 10.000; bad runs' 12.000, 12.000 and
  12.000; midpoint 11.000. A tested 11.000 exits 0 and 11.001 exits 1.
  Good runs at 9.900, 10.000 and 10.600 (centre 10.000, mean 10.167)
  against the same bad runs: a tested 11.001 exits 1. With the default
  floor of 0.300, good runs all 10.000: bad runs at 10.200, 10.300 and
  10.400 separate (change 0.300, spread 0.200); at 10.200, 10.299 and
  10.400 they stop with 128 (change under the floor); at 10.500, 11.000
  and 11.500 they stop (change equal to the spread); at 10.501, 11.000
  and 11.500 they separate. The good set's range counts: good runs at
  9.500, 10.000 and 10.500 against bad runs all 11.000 stop (change
  equal to the spread), and at 9.501, 10.000 and 10.500 separate. Good
  runs all 12.000 and bad all 10.000 stop as the wrong way round; good
  and bad all 10.000 stop as not separating.
  *Test:* `tests/test_bisect.py::test_reference_midpoint`,
  `tests/test_bisect.py::test_references_separate`,
  `tests/test_bisect.py::test_good_range_counts`,
  `tests/test_bisect.py::test_inverted_and_equal_references`.
  *Breaks when:* the tested value is judged against one reference, or
  the midpoint uses means or pools the runs, or the separation check is
  missing, or its bounds are off by one thousandth, or the spread is
  one set's range, or equal centres read as the wrong way round.

- **INV-41** — A tested commit that cannot be judged skips with 125,
  however far its value is over `X`. Against `--bad-above 10.000`, a
  tested run with `gpu/opaque` 20.000 skips when it has `rows_dropped`
  1, when its close line is removed, when one of its rows is malformed,
  and when its path does not exist; so does an empty file, a header
  alone, and a header missing `dirty`, with no traceback. With three
  tested runs and only `tested-2` broken, it still skips, and with
  `tested-1` and `tested-3` broken, each has its own sentence. A tested
  run without `gpu/opaque` skips, and the sentence names the kinds it
  has (`view`); with `--segment view:9`, the segments (`view:1`).
  *Test:* `tests/test_bisect.py::test_skip`,
  `tests/test_bisect.py::test_skip_names_the_kinds`,
  `tests/test_bisect.py::test_skip_any_tested_run`,
  `tests/test_bisect.py::test_skip_broken_headers`.
  *Breaks when:* an incomplete or broken tested run is judged bad, or
  any of these exits 3 or 128, or only the first tested run is checked.

- **INV-42** — Every other outcome of a bisect command line exits 128,
  never 0 from help or 1, 2 or 3 from an error, and standard error holds
  no traceback but for an error inside the analyser: `--help`, `-h`,
  `--version` and `--selftest`; `--bad-above abc`; `--bad-above
  1.0001`; `--bad-above 1000000000`; `--dry-run 1.0001`; neither mode;
  both modes; `--min-ms 1`, `--min-mb 1` or `--min-pct 1` with
  `--bad-above`; `--min-mb 1` on `gpu/opaque`; `--statistic p99` on
  `gpu/opaque`; `--measure event/cut`; `--measure frame/fence_wait`;
  `--depth 1` on `frame/wall`; `--kind view:1`; `--segment view:`;
  none of `--kind`, `--segment` and `--unsegmented`, or two of them;
  no `--tested` and no `--dry-run`; a bare file; `--json` given before
  `bisect` with a bad argument after it; a reference set of two runs; a
  reference with `rows_dropped` 1, with no close line, with a breach,
  or without the measure; a reference path that does not exist, named
  `good-1` and not by its path; good runs differing in `resolution`; a
  tested run differing from the references in `scene`; an exception
  raised while reading a run; and one raised while rendering the
  result. With `--override "resolution=upscaler test"`, the
  `resolution` case is judged. `check bisect`, a check of a file named
  `bisect`, is not a bisect command line.
  *Test:* `tests/test_bisect.py::test_stop_codes`,
  `tests/test_bisect.py::test_stop_before_the_command`,
  `tests/test_bisect.py::test_stop_on_an_internal_error`, the exceptions
  patched in by the test; `tests/test_bisect.py::test_reference_refusal`,
  `tests/test_bisect.py::test_broken_references`.
  *Breaks when:* any case exits 0, or with the ladder's 2 or 3, or a
  Python traceback's 1, which `git bisect run` would read as good or
  bad; or a stop reads as a crash.

- **INV-43** — The dry run judges a value and reads no tested file.
  `--dry-run 10.001 --bad-above 10.000` exits 1 and `--dry-run 10.000
  --bad-above 10.000` exits 0; each verdict sentence opens "Dry run:".
  `--dry-run` with a `FILE` is 128. With INV-40's wrong-way-round
  references, the dry run stops with 128.
  *Test:* `tests/test_bisect.py::test_dry_run`.
  *Breaks when:* the dry run always exits 0, or skips the reference
  checks, or reads like a real verdict.

- **INV-44** — A `mem` measure is the median of its rows in the chosen
  frames, in MB, with `--min-mb` for its floor and no tick floor. A
  tested run whose `view` frames have `mem/gpu_mb` 100.000, 500.000 and
  900.000, and whose two `load` frames have 9000.000: with `--kind
  view`, `--bad-above 500.000` exits 0 and `--bad-above 499.999` exits
  1, and the result's `unit` is `MB`. With `--min-pct 0` and three runs
  a set: good runs at 500.000 and bad at 500.999 stop with 128; bad at
  501.000 separate, and still do with `gpu_tick_ns` 5000000 in a good
  run's header. `--min-ms 5` on `mem/gpu_mb` is 128.
  *Test:* `tests/test_bisect.py::test_mem_measure`.
  *Breaks when:* the rows are not filtered by kind, or a `mem` floor
  uses `--min-ms` or the tick, or a wrong-unit floor is ignored.

- **INV-45** — A warning never changes the exit code. A tested run with
  `build_type` `debug` and `dirty` true, and `gpu/opaque` 11.000,
  against `--bad-above 10.000` exits 1, with `debug_build` and
  `dirty_build` each opening `tested-1:`.
  *Test:* `tests/test_bisect.py::test_warning_keeps_code`.
  *Breaks when:* a trust warning turns bad into skip, or a dirty tested
  run gives no warning.

- **INV-46** — Without `--depth`, every run has the name at one depth.
  A run with `gpu/blur` at depth 0 (2.000) in some frames and at depth
  1 (5.000) in the others, since one frame cannot hold both: `--measure
  gpu/blur` alone stops with 128, naming depths 0 and 1; with `--depth
  1 --bad-above 4.000` it exits 1, and with `--depth 0` it exits 0; with
  `--depth 2` it skips. References with `gpu/blur` at depth 0 and a
  tested run with it at depth 1 only stop with 128, and so do good runs
  at depth 0 and bad runs at depth 1.
  *Test:* `tests/test_bisect.py::test_depth`,
  `tests/test_bisect.py::test_one_depth_across_runs`.
  *Breaks when:* one depth is picked silently, in one run or between
  runs, or `--depth` is ignored.

- **INV-47** — References that straddle their own midpoint stop the
  bisect (Vestige). Good runs at 10.000, 10.000 and 10.900, bad at
  11.000, 11.200 and 11.300: they separate (change 1.200, spread 0.900)
  but the midpoint is 10.600, so they stop with 128, naming `good-3`.
  Good runs all 10.000 and bad at 11.000, 12.000 and 12.500: the
  midpoint is 11.000, so `bad-1` at it stops; with `bad-1` at 11.001
  they are accepted.
  *Test:* `tests/test_bisect.py::test_references_straddle`.
  *Breaks when:* only the centres are checked, or a bad run at the
  midpoint is accepted.

- **INV-48** — The frames judged are the ones chosen. A run with
  `gpu/opaque` 10.000 in 200 `view:1` frames and 14.000 in 100 `view:2`
  frames: `--segment view:2 --bad-above 12.000` exits 1, `--kind view
  --bad-above 12.000` exits 0, and `--segment view:3` skips with 125.
  With frames of no segment at 8.000 added, `--unsegmented --bad-above
  9.000` exits 0. A run of 102 `view` frames whose `frame/wall` is
  16.000 in 99 of them and 40.000 in two, the last frame having none
  (§ 4.4): `--measure frame/wall
  --statistic p99 --bad-above 30.000` exits 1, and the median exits 0.
  *Test:* `tests/test_bisect.py::test_frames_chosen`.
  *Breaks when:* `--segment` pools its kind, `--unsegmented` takes
  segmented frames, or `--statistic` is ignored.

- **INV-49** — The runs must match in both modes. Threshold mode: three
  tested runs, `tested-2` with `resolution` `[2560,1440]`, stop with
  128; with `--override "resolution=upscaler test"` they are judged,
  and the first sentence names the override. The same override with
  matching runs warns `override_unused`. Reference mode: references
  that match each other and a tested run whose `resolution` differs
  from theirs stop with 128, and are judged with the override.
  *Test:* `tests/test_bisect.py::test_runs_must_match`.
  *Breaks when:* threshold mode skips the check, or an override does
  not reach the tested runs.

- **INV-50** — The reference floor is § 4.10's. Good runs' `gpu/opaque`
  all 10.000 and bad all 10.400 separate at the default floor of 0.300,
  and stop with 128 under `--min-ms 0.500`. The same with
  `gpu_tick_ns` 500000 (0.500 ms) in `good-1`'s header stop; with
  `cpu/sim` in place of `gpu/opaque`, the tick does not apply and they
  separate.
  *Test:* `tests/test_bisect.py::test_reference_floor`.
  *Breaks when:* `--min-ms` cannot raise the floor above the percent,
  or the tick is ignored, or it reaches a `cpu` pass.

- **INV-51** — Tested runs that straddle the line warn, and skip only
  with `--skip-straddle`. Against INV-40's references (midpoint
  11.000), tested runs at 10.900, 11.000 and 11.100 exit 0 on their
  centre of 11.000, with `tested_straddle` naming all three values;
  with `--skip-straddle` they skip with 125. Runs at 11.001, 11.100 and
  11.200 exit 1 with no warning, and so do they with `--skip-straddle`.
  Against `--bad-above 10.000`, runs at 10.000 and 10.001 straddle.
  One tested run never warns. `--skip-straddle` with `--dry-run` is
  128.
  *Test:* `tests/test_bisect.py::test_tested_straddle`.
  *Breaks when:* a run at the line counts as above it, or the straddle
  changes the code without the flag, or the flag skips runs on one side.

- **INV-52** — A failed write never reads as a verdict. A bisect whose
  standard output is a pipe closed before it writes, or `/dev/full`,
  exits 128; `check` in the same case exits 3.
  *Test:* `tests/test_cli.py::test_failed_write`.
  *Breaks when:* Python's exit 120 on a failed flush reaches `git
  bisect run`, which reads it as bad.

- **INV-53** — Every file list follows its own flag. `--tested t1.csv
  --good g1 g2 g3 --bad b1 b2 b3 t2.csv` judges `t2.csv` as `bad-4`,
  as written, and `bisect t1.csv …` with a bare file stops with 128.
  No sentence holds a path.
  *Test:* `tests/test_bisect.py::test_file_lists`.
  *Breaks when:* a positional file list returns, or a sentence names a
  path.

- **INV-54** — At `--warmup-s 0`, a budget's value is `report`'s
  figure, compared exactly. In a run whose `gpu/ssao` in view frames has `report`'s
  median 1.500 and p99 2.310, a median limit of 1.500 holds and a p99
  limit of 2.309 fails with exit 1. Its `value_ms` equals `report`'s
  `p99_ms`.
  *Test:* `tests/test_budget.py::test_value_is_reports`.
  *Breaks when:* equal counts as over, or the value is over other
  frames than `report`'s, such as GPU rows in frames with no
  `frame/gpu_span`.

- **INV-55** — Every pass over budget is named. Two over and one under
  give exit 1, a sentence for each of the two, most over first, and
  none for the third.
  *Test:* `tests/test_budget.py::test_every_breach_named`.
  *Breaks when:* the check stops at the first breach.

- **INV-56** — `*` judges each kind apart. A pass at 1.000 ms in 60
  view frames and 3.000 ms in 40 move frames, against a `*` median
  limit of 2.000, fails in move only. Pooled, its median is 1.000 and
  it would hold. Add a `warmup` kind at 5.000 ms and the `*` line fails
  there too; `view` and `move` lines in its place leave `warmup`
  unjudged, with no entry.
  *Test:* `tests/test_budget.py::test_each_kind_apart`.
  *Breaks when:* the kinds are pooled.

- **INV-57** — A budget nothing matches is never a pass. A budget for
  a pass not in the run gives exit 2 and names it. With a breach
  beside it, the exit is 1 and it is still named.
  *Test:* `tests/test_budget.py::test_unmatched`.
  *Breaks when:* an unmatched budget is skipped, or holds.

- **INV-58** — Dropped rows and a missing close line make holding
  budgets inconclusive, and leave a breach failing. With either, every
  budget holding gives exit 2; one over gives exit 1.
  *Test:* `tests/test_budget.py::test_dropped_and_unfinished`.
  *Breaks when:* a run missing rows passes, or its breach is hidden.

- **INV-59** — A bad budget file exits 3 and names its line. Each
  alone: no header; `schema` 2; another column line; `statistic` `p95`;
  `limit_ms` `2.0005`; `category` `frame`; a repeated line; an empty
  `depth` for a pass at two depths, named with both; a `match` key
  `fps`. A blank line between two budgets is skipped.
  *Test:* `tests/test_budget.py::test_bad_budget_files`.
  *Breaks when:* a bad line is skipped or read as a budget, or a
  blank line stops the file.

- **INV-60** — A `p99` budget over 99 frames warns `budget_few_frames`
  and keeps its verdict and exit code; over exactly 100 frames it
  does not warn.
  *Test:* `tests/test_budget.py::test_few_frames_warns`.
  *Breaks when:* the warning changes the verdict, or fires at 100.

- **INV-61** — A budget file holds only for the settings it names. With
  `"match":{"tier":"high","render_scale":1}`, a run with `tier` `high`
  and `render_scale` `1.0` is judged; one with `tier` `low`, or with no
  `tier`, exits 3 naming `tier` and both values.
  *Test:* `tests/test_budget.py::test_match`.
  *Breaks when:* `match` is ignored, numbers match as text, or an
  absent field matches.

- **INV-62** — A named kind replaces `*` for that kind. `gpu/ssao` at
  2.500 ms in view and 1.500 ms in move, against `*` p99 2.000 and
  `view` p99 3.000, holds with exit 0: one entry each, view at 3.000 and
  move at 2.000. Without the `view` line, it fails in view.
  *Test:* `tests/test_budget.py::test_named_kind_replaces_star`.
  *Breaks when:* the stricter line wins, or both judge view.

- **INV-63** — `--warmup-s` leaves out the frames `floor` leaves out.
  A run of 200 frames, each with a 10.000 ms `frame/wall`, has
  `gpu/x` at 5.000 ms in its first 20 frames and 1.000 ms after. A p99
  limit of 2.000 fails at the default, and holds at `--warmup-s 0.5`,
  with `warmup_s` 0.5. The same run with a hole at frame 100 is
  inconclusive at `--warmup-s 0.5`, and still fails at 0.
  *Test:* `tests/test_budget.py::test_warmup`.
  *Breaks when:* warm-up frames are judged, the default leaves any
  out, or a hole is ignored above 0.

## 6. Failure modes

- **A malformed row.** `check` lists it with its line. `report` and
  `floor` stop with exit 3 naming the line; they never skip it, since a
  skipped row hides a frame.
- **Two rows for the same frame, category and name.** A breach; the
  analyser cannot tell which is real.
- **A frame other than the last with no `frame/wall`, or a hole in the
  frame numbers.** The timeline cannot be built past it: `floor` is
  inconclusive unless frames fail the budget (§ 4.7); `report` warns,
  and leaves a frame with no wall out of its wall figures.
- **A header field of the wrong type.** A `check` breach; other
  commands exit 3.
- **A writer whose engine never calls `fled_consume`.** The buffer
  fills and rows are dropped and counted (INV-15). Never silent.
- **An engine killed before `fled_close`.** No close line; INV-7.

## 7. Tests

The analyser's tests live in `tests/`, run by pytest, with fixtures in
`tests/fixtures/`; the writer's in `tests/writer/`, run by the gate
script. Each test is first seen failing against an analyser or writer
without the rule, then passing — per `testing.md`. Who builds each:

- FLED-0002: INV-1, INV-2, INV-3, INV-4, INV-6, INV-21.
- FLED-0003: INV-5, INV-10, INV-11, INV-12, INV-13.
- FLED-0004: INV-7, INV-8, INV-9, INV-18.
- FLED-0005: INV-23, INV-24, INV-25, INV-26, INV-27.
- FLED-0006: INV-14, INV-15, INV-16, INV-17, INV-19, INV-20, INV-22,
  INV-28, INV-29.
- FLED-0008: INV-30 to INV-38.
- FLED-0009: INV-39 to INV-53.
- FLED-0010: INV-54 to INV-63.

MSVC is not tested here. Vestige and UT Ants compile the header with
it on each release they pin.

## 8. Alternatives considered (and rejected)

- **One JSON object per run.** UT Ants' format today. Rejected: a
  survey of about a million rows would be one huge object, and a
  crashed run would leave a truncated, unreadable file.
- **A binary format.** Rejected: not readable by a person or a plain
  CSV tool, and a writer from the spec alone (S7) gets harder.
- **Integer microseconds instead of three-decimal milliseconds.**
  Equal precision; rejected because every engine and every existing
  tool here already speaks milliseconds.
- **Separate columns for events and tics.** Rejected: most frames would
  carry empty cells, and each new event would change the column line.
- **The writer owning a `FILE *`.** Rejected: file I/O in the frame
  loop is what DOOM Ants and Vestige ruled out, and the engine already
  owns its files.
- **A TOML or JSON budget file.** Rejected: TOML needs Python 3.11's
  `tomllib`, above the 3.10 floor; JSON has no comments, and a budget
  without its reason beside it gets loosened. CSV is the run file's
  own form.
- **Budgets as a flag on `report` or `floor`.** Rejected: `report`
  has no failing exit, and `floor` judges frames against a frame rate. A
  budget breach needs its own exit 1.

## 9. Out of scope

- The pacing figure — FLED-0011, which amends this spec.
- `survey` and survey comparison — FLED-0012 and FLED-0013, which amend
  this spec.
- Warnings on a single run's timing finer than `gpu_tick_ns`;
  `compare` only raises its floor to it (§ 4.10). Not yet queued.
- Charts or HTML — deferred; not yet queued (discovery, *not yet*).

## 10. What checks this

| Rule | What catches a breach |
|------|----------------------|
| INV-1 | `tests/test_check.py::test_missing_header` |
| INV-2 | `tests/test_check.py::test_schema_versions` |
| INV-3 | `tests/test_ledger.py::test_crlf_equals_lf` |
| INV-4 | `tests/test_ledger.py::test_late_gpu_rows` |
| INV-5 | `tests/test_report.py::test_missing_gpu_span` |
| INV-6 | `tests/test_check.py::test_value_format` |
| INV-7 | `tests/test_floor.py::test_unfinished_and_dropped`, `tests/test_floor.py::test_frame_failure_stands_under_drops` |
| INV-8 | `tests/test_floor.py::test_window_rate`, `tests/test_floor.py::test_steady_frame_time_passes`, `tests/test_floor.py::test_vsync_rates_pass` |
| INV-9 | `tests/test_floor.py::test_single_frame_budget` |
| INV-10 | `tests/test_report.py::test_bound_by_not_pipelined` |
| INV-11 | `tests/test_report.py::test_remainder` |
| INV-12 | `tests/test_report.py::test_static_exact` |
| INV-13 | `tests/test_render.py::test_text_matches_json` |
| INV-14 | `tests/writer/test_compile.sh` |
| INV-15 | `tests/writer/test_writer.c::test_drops` |
| INV-16 | `tests/writer/test_writer.c::test_output_conforms` |
| INV-17 | `tests/writer/test_writer.c::test_name_limit` |
| INV-18 | `tests/test_floor.py::test_cuts_and_partial_windows`, `tests/test_floor.py::test_cut_frame_is_left_out_of_windows`, `tests/test_floor.py::test_long_cut_frame_overlaps_no_window`, `tests/test_floor.py::test_cut_on_a_window_boundary` |
| INV-19 | `tests/writer/test_writer.c::test_rounding` |
| INV-20 | `tests/writer/test_writer.c::test_bad_values` |
| INV-21 | `tests/test_check.py::test_negative_and_last_wall` |
| INV-22 | `tests/writer/test_writer.c::test_consume_reuses` |
| INV-23 | `tests/test_trust.py::test_header_warnings` |
| INV-24 | `tests/test_trust.py::test_too_few_frames` |
| INV-25 | `tests/test_trust.py::test_settling` |
| INV-26 | `tests/test_trust.py::test_cut_in_stretch` |
| INV-27 | `tests/test_trust.py::test_absent_fields_and_check` |
| INV-28 | `tests/writer/test_writer.c::test_failed_open` |
| INV-29 | `tests/writer/test_writer.c::test_escape_opens` |
| INV-30 | `tests/test_compare.py::test_same_build_and_known_slowdown`, `tests/test_compare.py::test_largest_slower_measure_is_named` |
| INV-31 | `tests/test_compare.py::test_pass_judged_by_own_spread`, `tests/test_compare.py::test_spread_is_the_wider_set`, `tests/test_compare.py::test_short_kind_missing_from_the_first_run` |
| INV-32 | `tests/test_compare.py::test_floor`, `tests/test_compare.py::test_verdict_edges`, `tests/test_compare.py::test_zero_floor` |
| INV-33 | `tests/test_compare.py::test_refusal_and_override`, `tests/test_compare.py::test_header_matching`, `tests/test_compare.py::test_equal_numbers_match`, `tests/test_compare.py::test_overrides_stay_first` |
| INV-34 | `tests/test_compare.py::test_incomplete_run` |
| INV-35 | `tests/test_compare.py::test_interleaving`, `tests/test_compare.py::test_set_warnings` |
| INV-36 | `tests/test_compare.py::test_runs_and_unmatched` |
| INV-37 | `tests/test_compare.py::test_static_diff` |
| INV-38 | `tests/test_compare.py::test_even_sets_and_rounding` |
| INV-39 | `tests/test_bisect.py::test_threshold_edges`, `tests/test_bisect.py::test_tested_centre`, `tests/test_bisect.py::test_exact_comparison`, `tests/test_bisect.py::test_equal_sentence`, `tests/test_bisect.py::test_five_place_midpoint` |
| INV-40 | `tests/test_bisect.py::test_reference_midpoint`, `tests/test_bisect.py::test_references_separate`, `tests/test_bisect.py::test_good_range_counts`, `tests/test_bisect.py::test_inverted_and_equal_references` |
| INV-41 | `tests/test_bisect.py::test_skip`, `tests/test_bisect.py::test_skip_names_the_kinds`, `tests/test_bisect.py::test_skip_any_tested_run`, `tests/test_bisect.py::test_skip_broken_headers` |
| INV-42 | `tests/test_bisect.py::test_stop_codes`, `tests/test_bisect.py::test_stop_before_the_command`, `tests/test_bisect.py::test_stop_on_an_internal_error`, `tests/test_bisect.py::test_reference_refusal`, `tests/test_bisect.py::test_broken_references` |
| INV-43 | `tests/test_bisect.py::test_dry_run` |
| INV-44 | `tests/test_bisect.py::test_mem_measure` |
| INV-45 | `tests/test_bisect.py::test_warning_keeps_code` |
| INV-46 | `tests/test_bisect.py::test_depth`, `tests/test_bisect.py::test_one_depth_across_runs` |
| INV-47 | `tests/test_bisect.py::test_references_straddle` |
| INV-48 | `tests/test_bisect.py::test_frames_chosen` |
| INV-49 | `tests/test_bisect.py::test_runs_must_match` |
| INV-50 | `tests/test_bisect.py::test_reference_floor` |
| INV-51 | `tests/test_bisect.py::test_tested_straddle` |
| INV-52 | `tests/test_cli.py::test_failed_write` |
| INV-53 | `tests/test_bisect.py::test_file_lists` |
| INV-54 | `tests/test_budget.py::test_value_is_reports` |
| INV-55 | `tests/test_budget.py::test_every_breach_named` |
| INV-56 | `tests/test_budget.py::test_each_kind_apart` |
| INV-57 | `tests/test_budget.py::test_unmatched` |
| INV-58 | `tests/test_budget.py::test_dropped_and_unfinished` |
| INV-59 | `tests/test_budget.py::test_bad_budget_files` |
| INV-60 | `tests/test_budget.py::test_few_frames_warns` |
| INV-61 | `tests/test_budget.py::test_match` |
| INV-62 | `tests/test_budget.py::test_named_kind_replaces_star` |
| INV-63 | `tests/test_budget.py::test_warmup` |
| 4.6, MSVC | **`Partial:`** Vestige's and UT Ants' Windows builds, per pinned release; nothing here |
| 4.8, tables within 100 columns | `tests/test_render.py::test_text_matches_json`, over `report`'s and `floor`'s text for every fixture |

## 11. Cross-doc impact

- `docs/design.md` — none; this spec is the format part it names.
- `README.md` — gains Install and Usage once FLED-0007 ships.
- `CHANGELOG.md` — each later amendment of this spec is a format change
  the release notes name (S6).

## 12. Cold-eyes loop log

Rows live in `../reviews/FLED-0001-run-file-format-loop-log.md`.
