<!-- ants-spec-format: 1 -->
# FLED-0001 — Define the run file, the writer's interface and the 0.1.0 commands

**Status:** accepted (2026-10-24).
**Kind:** doc.
**Source:** ROADMAP FLED-0001 (design-2026-10-24; requirements from the Vestige, UT Ants and DOOM Ants sessions).
**Blocker for:** FLED-0002, FLED-0006.

What an engine writes after a benchmark run, and what the analyser
promises to say about it, written down once so all three engines and
any later engine produce the same file.

## 1. Goal

A run file has one written definition. An engine can write one from
this document alone (S7), with or without the optional C header. The
analyser's 0.1.0 commands (`check`, `report`, `floor`), its exit codes
and the outer shape of its JSON result are fixed, so engines can script
against them before the analyser exists.

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
`settling_frames` (integer), `pinned` (object: clocks the run froze),
`gpu_tick_ns` (number), `load` (`{"start": n, "end": n}`, CPU load
average), `gpu_busy_pct` (`{"start": n, "end": n}`), `gpu_clock_mhz`
(`{"start": n, "end": n}`), `os` (string), `extra` (object, the
engine's own).

**Compare-blocking fields**: `resolution`, `render_scale`, `tier`,
`ray_tracing`, `build_type`, `inputs`, `display`, `api`, `device`.
Two runs differing in any of them are not comparable without an
override (FLED-0008 builds the compare). Two empty `inputs` lists are
unknown, not equal.

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
and event name. Other event names are allowed.

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
  built; `fled_json_escape` helps build them.
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
  "verdict": "pass | fail | inconclusive | error | none",
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
"breaches": [{"line", "rule", "message"}]}]}`.

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
  per other kind of warning, frames without a GPU result; then the frame
  count, the costliest depth-0 pass per segment kind by total time, and
  the bound-by share or that it does not apply.

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
- FLED-0006: INV-14, INV-15, INV-16, INV-17, INV-19, INV-20, INV-22.

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

## 9. Out of scope

- `compare` and its flags, overrides and result — FLED-0008, which
  amends this spec before it is built.
- Bisect mode's flags — FLED-0009, which amends this spec.
- The budget file — FLED-0010, which amends this spec.
- The pacing figure — FLED-0011, which amends this spec.
- `survey` and survey comparison — FLED-0012 and FLED-0013, which amend
  this spec.
- Trust warnings beyond the dropped and unfinished runs above —
  FLED-0005.
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
| INV-14 | `tests/writer/test_compile.sh` (not yet written) |
| INV-15 | `tests/writer/test_writer.c::test_drops` (not yet written) |
| INV-16 | `tests/writer/test_writer.c::test_output_conforms` (not yet written) |
| INV-17 | `tests/writer/test_writer.c::test_name_limit` (not yet written) |
| INV-18 | `tests/test_floor.py::test_cuts_and_partial_windows`, `tests/test_floor.py::test_cut_frame_is_left_out_of_windows`, `tests/test_floor.py::test_long_cut_frame_overlaps_no_window`, `tests/test_floor.py::test_cut_on_a_window_boundary` |
| INV-19 | `tests/writer/test_writer.c::test_rounding` (not yet written) |
| INV-20 | `tests/writer/test_writer.c::test_bad_values` (not yet written) |
| INV-21 | `tests/test_check.py::test_negative_and_last_wall` |
| INV-22 | `tests/writer/test_writer.c::test_consume_reuses` (not yet written) |
| 4.6, MSVC | **`Partial:`** Vestige's and UT Ants' Windows builds, per pinned release; nothing here |
| 4.8, tables within 100 columns | `tests/test_render.py::test_text_matches_json`, over `report`'s and `floor`'s text for every fixture |

## 11. Cross-doc impact

- `docs/design.md` — none; this spec is the format part it names.
- `README.md` — gains Install and Usage once FLED-0007 ships.
- `CHANGELOG.md` — each later amendment of this spec is a format change
  the release notes name (S6).

## 12. Cold-eyes loop log

Rows live in `../reviews/FLED-0001-run-file-format-loop-log.md`.
