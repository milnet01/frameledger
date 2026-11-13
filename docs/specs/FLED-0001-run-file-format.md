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
(FLED-0010) agreed by the three engines 2026-10-29 at f766388; their
code review settled the resolved depths and the exit-3 stops, and they
confirmed it at e3984fe, with eb47707's depth-set fix. INV-64 and
§ 4.4's digit limit (FLED-0022) reviewed by the three engines at
f5e476b, and confirmed at 0c5b57d. § 4.10's `mem` measures with INV-65
to INV-67 (FLED-0018) agreed by the three engines 2026-10-31 at
3be4465, and confirmed at 0ebcf7d. FLED-0023's limits on `--warmup-s`
and the smallest changes confirmed by the three engines at 8cef832.
§ 4.8's `pacing` with INV-68 (FLED-0011) agreed by the three engines
2026-11-04 at 8f3eae8, with the `wall change (pairs)` label. § 4.11's
depth skip and `skip_reason` with INV-46 amended (FLED-0020) agreed by
the three engines 2026-11-04 at 139c66c, and their code review
confirmed it at d2ff396. § 4.13 `survey` with INV-69 to INV-72
(FLED-0012) agreed by the three engines 2026-11-04 at 991a9de, with
their wording changes. § 4.17 a saved baseline with INV-98 to INV-101
(FLED-0035) designed with the three engines 2026-11-12, and their code
reviews of e5f2758 settled its paths, duplicates and warnings. § 4.2's
real-date rule for `started_utc` with INV-102 (FLED-0070) agreed by
the three engines 2026-11-13 before it was built; their code reviews
of 736b210 added the limit on fraction digits. § 4.2's `sanitizers`
and § 4.9's `sanitizer_build` with INV-103 (FLED-0016) asked for by
Vestige 2026-10-26; the three engines' code reviews of 8e9a970 added
the refusal of an empty name and the cut of a long one. § 4.2's
machine-state fields, § 4.9's `on_battery` and `throttled` and § 4.10's
setting and temperature warnings with INV-104 to INV-107 (FLED-0055)
agreed by the three engines 2026-11-13 before they were built; their
code reviews of 4a67c02 settled that values are compared whole and a
list's order does not count. § 4.13's shared directory in the table
heading with INV-108 (FLED-0025) asked for by DOOM Ants 2026-11-04;
its code review of 8f04c58 added that `./` names nothing. § 4.10's
`outlier_run` with INV-109 (FLED-0053) agreed by the three engines
2026-11-13 before it was built; Vestige's code review of 1b8756b
added that a set of two names no run, and DOOM Ants' that each
named run has its sentence and a base run is named once. § 4.8's
cleaned plain text with INV-110 (FLED-0071) found by DOOM Ants
2026-11-13 and agreed by the three engines before it was built.
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
- For FLED-0029: `alternate` runs old and new in turn and compares as
  § 4.10 (§ 4.15; all three engines); a placeholder gives each run its
  own file (DOOM Ants, Vestige). Reviewed by the three engines
  2026-11-10, agreeing: the name `alternate`; the placeholder `{run}`;
  five runs a side by default; the platform shell; the engine's output
  on standard error; a failed run stops the rest. From the review:
  pairs alternate which side goes first, so steady drift cancels (UT
  Ants, Vestige); `--warmup` discards untimed runs, default 0 (UT Ants
  and Vestige for, DOOM Ants not needing them); a failed run's file is
  deleted (DOOM Ants).
- For FLED-0030: a run may record peak CPU and GPU load; a compare
  using a run taken under load names it and is inconclusive, exit 2;
  the limits are set here and a flag changes them; two sides whose
  load or GPU clock differ are warned of (S22; Vestige, UT Ants, DOOM
  Ants). *Proposed here:* a peak counts other programs only, not the
  run's own work; `--max-load 0.25` and `--max-gpu-busy 20`; a `start`
  never makes a run under load; the difference limits 0.1, 10 points
  and 5%; the clock compared at `end`; `report` and `floor` unchanged.
  Reviewed by the three engines 2026-11-10, agreeing to each; from the
  review: the run's own work may include processes the writer counts
  with it, and a peak is clamped (DOOM Ants); a writer seeing only
  some programs gives their peak (UT Ants); the `end` clock is read
  before the GPU is released (Vestige). `--max-gpu-busy` stays 20:
  UT Ants guessed 10 for itself, unmeasured, and may pass it.
- For FLED-0031: `--measure` keeps only the named measures, and a
  table gives each run's value of each on one row, so DOOM Ants'
  private script is no longer needed (DOOM Ants). *Proposed here:*
  `bisect`'s `CATEGORY/NAME` form; every depth, kind and statistic of
  a name kept; a name no run has is exit 3; the table in text only,
  and not under `--by-scene`. Reviewed by the three engines
  2026-11-11, agreeing to each; from the review: a compare whose kept
  measures are all unmatched is inconclusive, and names match case
  included (UT Ants); a further table repeats the run column, and a
  scene whose kept measures are all unmatched is inconclusive
  (Vestige).

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

Spaces after the object's closing brace are ignored. So a writer that
learns the header's `end` and `peak` (4.2) only after the last frame
may pad line 1 with spaces when it opens the file, and at close write
the finished header over it at the same length (Vestige, 3D_E-0968;
FLED-0068). The padding goes after the closing brace, never inside a
string. Only spaces are promised, not tabs. The spaces come before the
line's ending, and the length to keep counts that ending: a file
opened in text mode on Windows ends line 1 in CRLF, two bytes (UT
Ants).

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
| `started_utc` | string | when the run started, in UTC: `YYYY-MM-DDTHH:MM:SS`, an optional point and 1 to 20 fraction digits, then `Z` |

Optional fields, absent meaning unknown: `tier` (string),
`ray_tracing` (boolean), `frames_in_flight` (integer),
`settling_frames` (integer: untimed frames each segment needs drawn
before its first recorded frame), `settled_frames` (integer: the
fewest untimed frames the run drew before any segment's first recorded
frame), `pinned` (object: clocks the run froze),
`gpu_tick_ns` (number), `load` (`{"start": n, "end": n}`, CPU load
as a share of the machine: 0 idle, 1 every logical CPU busy; `peak`
optional), `gpu_busy_pct` (`{"start": n, "end": n}`, `peak`
optional), `gpu_clock_mhz`
(`{"start": n, "end": n}`), `os` (string), `sanitizers` (array of
strings: each sanitizer the build was compiled with, such as
`"address"`, in the writer's own words, never empty or only spaces;
`[]` says it has none), `cpu_governor` (string), `turbo` (boolean),
`power` (`"mains"` or `"battery"`), `cpu_clock_mhz`
(`{"start": n, "end": n}`), `cpu_temp_c` and `gpu_temp_c`
(`{"start": n, "end": n}`, degrees Celsius, `peak` optional),
`throttled` (boolean), `extra` (object, the engine's own).

`started_utc` names a real date and time: year 0001 to 9999, a month
and day that exist, with 29 February only in a leap year, hour 00 to
23, minute 00 to 59 and second 00 to 59. A second of 60, a leap
second, is refused. Any other value is a header breach, so `compare`
never meets a start it cannot order (DOOM Ants).

A `start` is taken before the engine loads anything or starts GPU
work, so it measures the machine, not the run; an `end` after the
run's last frame. `gpu_busy_pct.start` may be the highest of a few
samples over about half a second, the writer's choice, since one
sample jumps. On Linux, `load` is the one-minute load average divided
by the logical CPU count. It lags, so it is a coarse signal; it counts
tasks waiting on disk; and it can exceed 1, which is legal. On Windows
it is the CPU-busy share at that moment.

A `peak` is the highest share **other programs** used during the run,
from its first frame to its last (S22). The run's own work is left
out: a game keeps the GPU near 100% busy, so a peak that counted it
would mark every run. Samples are about one second long, taken from
the first frame to the last, and the peak is the highest of them.
`load.peak` is the CPU-busy share of every program but the run's, a
share from 0 to 1. `gpu_busy_pct.peak` is the GPU-busy percent of
every program but the run's, from 0 to 100. A sample that works out
below 0 or above the top is clamped to it: a whole-device reading
over a short window, less the run's own share averaged over the
sample, can do either (DOOM Ants).

- **The run's own work** is the writer's process, and any process the
  writer chooses to count with it, such as the compositor a headless
  run starts (DOOM Ants).
- **A writer that can see only some programs** gives the peak of those
  it can see (UT Ants): per-program GPU time may be readable for the
  writer's own user only.
- **A writer that cannot leave its own work out gives no `peak`**:
  absent means unknown, and § 4.10 then judges the run as before.
- **How to sample is the writer's choice.** A `gpu_clock_mhz.end` is
  read after the last frame and before the run releases the GPU,
  since a GPU drops to its idle clock within moments (Vestige).

The machine-state fields say what the machine was set to, since a
governor or a hot machine mimics a regression (FLED-0055):

- **`cpu_governor`** is the writer's own words for the CPU's power
  setting. On Linux it may carry the energy preference beside the
  governor, as `powersave/balance_performance`, since the governor
  alone can mislead (UT Ants). On Windows it may be the power plan's
  name, or be left out (Vestige).
- **`turbo`** is true when turbo or boost is enabled, whatever the CPU
  maker calls it (Vestige).
- **`cpu_clock_mhz`** is one number for the machine: the mean over the
  online cores, since one core's reading swings (Vestige).
- **A temperature's `peak`** is the highest reading from the run's
  first frame to its last. Unlike a load's `peak`, it is the whole
  device's: heat has no share to leave out.
- **`throttled`** is true when the CPU or GPU reported that it was
  slowed for heat or power during the run. A writer with no dependable
  source leaves it out; absent is unknown, never false (the engines).

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
| `frame` | non-negative integer, at most 20 digits; the frame that submitted the work |
| `category` | `frame`, `cpu`, `gpu`, `mem`, `event`, or `ext.<engine>` |
| `name` | the pass or measure; ASCII letters, digits and `_ . / -`, at most 64 bytes |
| `depth` | integer from 0, at most 20 digits; 0 is a top-level pass |
| `value` | decimal number, at most 20 digits before the point, exactly three after it, below 1 000 000 000 in size |

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
#define FLED_VERSION        /* this release's version, a string such as "0.5.0" */
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
- `FLED_VERSION` is a string literal: the version of the release the
  header shipped in, as that release's `frameledger --version` prints
  it. A copy vendored into an engine so says which release it came
  from. It is not `FLED_SCHEMA`, which moves only when the run-file
  format breaks (4.2). A header taken from `main` between releases
  carries the last release's version and may differ from that
  release's header, so vendor the header from a release tag (DOOM
  Ants).

### 4.7 The 0.1.0 commands

Run as `python3 -I frameledger.pyz <command> …`; on Windows `python -I`
or `py -I`. The release's launcher, `frameledger` on Linux and
`frameledger.cmd` on Windows, runs the same as `frameledger <command> …`
and exits with the analyser's code. Every command takes `--json`, printing the JSON result
instead of text, and `--markdown`, printing the text as Markdown
(§ 4.8). Given both, it is a bad argument.

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
  three decimal places; a `--warmup-s` of 1000000000 s or more
  (FLED-0023); and a `--fps` whose 1000/`--fps` ms is below
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
"median_ms", "p99_ms", "frames"}], "pacing": [{"segment_kind",
"median_ms", "p99_ms", "pairs"}], "bound_by": {"cpu", "gpu", "applies"},
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
- **`pacing`** is the frame-to-frame change in `frame/wall` (S14),
  so a run that holds its frame rate but judders shows it: frames
  alternating 12 ms and 16 ms pass `floor` at 60, with a change of
  4 ms. A pair is frame N and frame N−1, both with a `frame/wall`, in
  the same segment, neither carrying `event/cut`; so no pair spans a
  hole, a segment change or a load. Its change is the absolute
  difference of the two walls. Per segment kind of the pair's segment,
  in `frame_times`' order: the median and 99th percentile change, and
  `pairs`, their count. A kind with no pair has no entry. There is no
  warm-up and no verdict (FLED-0011, agreed with the three engines
  2026-11-04). The text gives it as a `wall change (pairs)` row under
  `wall` in the frame-times table, its frames column holding `pairs`.
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

**Markdown** (`--markdown`, FLED-0032) is the text, made to paste into
a commit body, a roadmap note or a pull request. It is GitHub-flavoured
Markdown that also reads as a table unrendered. The verdict and exit
code are the text's.

- **Sentences.** The opening sentences come first, as a list, one
  sentence an item opening `- `. So each stays on its own line,
  rendered or not; a paragraph's lines would join when rendered. A
  result whose text is its sentences alone, an error among them, is
  that list.
- **Tables.** Each text table is a pipe table, under its title line,
  with a blank line before and after. Its header row is the text's;
  number columns align right. Cells are padded with spaces so the
  columns line up unrendered.
- **Lists given without a header** become tables with one: `check`'s
  breaches `line | breach | rule`, its warnings `warning | code`;
  `--selftest`'s checks `result | check`; a runs list `run | path`,
  and `bisect`'s `run | <unit> | path`; `compare`'s unmatched measures
  `measure | only in` and its differing static facts `fact | values`;
  `report`'s static facts `fact | value`.
- **No width limit.** Nothing is cut short, and the per-run table of
  § 4.10 is one table. The row limits stay: 10 frames over budget, 20
  static facts, then the text's line saying how many more the JSON
  holds.
- **Depth.** A nested pass or measure is indented by two no-break
  spaces (U+00A0) per level, which Markdown keeps.
- **Escapes.** In sentences and cells, a backslash goes before each
  `\`, `` ` ``, `*`, `~`, `&`, `<`, `[`, `]`, `|` and `$`, and before each
  `_` not between two letters or digits. So a path, a segment id or a
  static value cannot format the output or split a cell, and a pass
  name such as `shadow_map` is unchanged. A Windows path's backslashes
  are doubled unrendered. A line break, or any other character plain
  text shows as an escape (below), becomes a space, so it cannot end a
  row or a sentence's item, or reorder a sentence as rendered
  (FLED-0073; Vestige, DOOM Ants). A space and not the escape: the
  escape's backslash would need escaping again, and `--json` holds
  what was there.
- **Line starts.** A sentence can open with a path, a run name or an
  error. So a sentence opening `>`, or one to six `#`, a `-` or a `+`
  then a space or the line's end, gets a backslash before it. One opening with digits
  then `.` or `)`, then a space or the line's end, gets one before
  that `.` or `)`. Otherwise it would render as a heading, a quotation
  or a list. `100.0% of frames` and `-c.csv` are neither, so they are
  left as they are. Leading spaces become no-break spaces, so they
  cannot make a list or a code block either. A cell never opens a
  line.
- **GitHub's own links and emoji** — `@name`, `#123`, a commit hash,
  `:smile:` — are not escaped. A value holding one may link it in a
  pull request, or show an emoji. Escaping `:` would mark every path
  and segment.

**Plain text shows what a terminal would obey** (FLED-0071, DOOM
Ants). A header value, a path or a static value is text from outside,
and a line break in one printed a second line that could read
"Warning: …". So every line of the plain text is cleaned where the
lines are joined, and nowhere else:

- **Shown as an escape:** Unicode's control characters (U+0000 to
  U+001F, U+007F to U+009F), the line and paragraph separators U+2028
  and U+2029, and the marks that set text direction, U+061C, U+200E,
  U+200F, U+202A to U+202E and U+2066 to U+2069, which can show a
  line's letters in another order than written (Vestige, UT Ants).
  Also the invisible characters no script needs: U+200B, U+2060 to
  U+2064 and U+FEFF. The joiners U+200C and U+200D print as written,
  since Persian and emoji are written with them. A line
  break is `\n`, a return `\r`, a tab `\t`; any other is `\x1b` or
  `\u202e`, by its code. Every other character prints as written, so
  a name in another alphabet is unchanged.
- **A backslash is doubled only in a quoted header string**: a
  `sanitizers` name, the `renderer` or `device` of
  `software_renderer`, the `driver`, `os` or `commit` of § 4.17's
  warnings, a header key of `unknown_field`. There
  the typed characters `\` and `n` show as `\\n`, apart from a line
  break's `\n`. The values § 4.10's setting warnings give as JSON are
  already so.
- **A path keeps its backslashes single**, so a Windows path can be
  copied as shown. The cost: in a path, a line break reads as the
  typed characters `\` and `n` do. `--json` tells them apart; it is
  exact.
- **A quoted list names its first five entries**, then "and N more",
  N being the count left out. So does a list inside a value given as
  JSON.
- **A quoted value is cut**, keeping both its ends around `...`, since
  two renderers or drivers mostly differ at the end (Vestige). A
  `sanitizers` name, a header key and a row's or a budget file's field
  are cut to 20 characters. Cut to 60: a `renderer`, `device`,
  `driver`, `os` or `commit`; each string of a value in a refusal
  (§ 4.2) or a budget file's mismatch; a scene's name in a sentence of
  § 4.14; a baseline file's line that is no path. Values are compared
  whole and only shown cut. The cut counts characters before they are
  shown as escapes, so a value of nothing but control characters is up
  to six times as wide. `--json`'s `message` is cut the same way.
- **Shown whole:** a path, and a scene's name in § 4.14's table. Each
  is what a reader looks the run up by.
- **`check` adds no breach**: its text is cleaned and cut as any
  other. A refusal could not reach a path, and each new quoted field
  would need its own rule.
- **`--json` and Markdown** carry the sentences uncleaned. JSON
  escapes a control character itself, and Markdown makes it a space,
  above.
- **Standard error** is cleaned the same way, and a setup error is cut
  to 500 characters: it can quote a line of a baseline file, not only
  the command line (Vestige, UT Ants).

A cleaned cell is wider than the table laid it out, so such a table
can pass 100 columns.

### 4.9 Trust warnings

`report` and `floor` warn on a run whose numbers should not be trusted
(S5). FLED-0005 builds this.

| Code | Warns when |
|---|---|
| `debug_build` | `build_type` is `debug`, in any case |
| `sanitizer_build` | `sanitizers` names one or more |
| `software_renderer` | `renderer` or `device` holds, in any case, `llvmpipe`, `lavapipe`, `softpipe`, `swrast`, `swiftshader`, `software rasterizer`, `gdi generic` or `microsoft basic render driver` |
| `cpu_load` | `load.start` is above 0.5 |
| `gpu_load` | `gpu_busy_pct.start` is above 20 |
| `on_battery` | `power` is `battery` |
| `throttled` | `throttled` is true |
| `settling_short` | `settled_frames` is below `settling_frames` |
| `too_few_frames` | fewer than 100 frames are measured: for `report`, frames with a `frame/wall`; for `floor`, frames ending after the warm-up |
| `cut_in_stretch` | an `event/cut` sits on a frame whose nearest earlier frame has the same segment; `floor` counts only frames ending after the warm-up |

- **A warning never changes a verdict or an exit code.** A Debug run
  that holds the floor passes, and says it was a Debug run.
- **An absent optional field gives no warning**: absent means unknown.
  `settling_short` needs both its fields.
- **An empty `sanitizers` gives no warning.** It says the build has
  none. `build_type` cannot say so: a Release build may carry a
  sanitizer (Vestige). The message quotes every name the list holds,
  a long one cut short.
- **Each message names what it judged**, and the threshold where there
  is one: `load.start` 0.62, above 0.5.
- **`check` gives none of these.** It judges the file, not the run.
- **Why 100 frames:** below that, the nearest-rank 99th percentile is
  the slowest frame, so the 1% low is one frame's time.
- **Why only `start` loads:** an `end` includes the run's own work.
- **A governor, a clock or a temperature gives no warning alone.** No
  one value of them is wrong; § 4.10 warns when two sides differ.
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
compare --old FILE… --new FILE… [--by-scene] [--override FIELD=REASON]… [--min-ms M] [--min-mb M] [--min-pct P] [--max-load L] [--max-gpu-busy P] [--measure CATEGORY/NAME]…
```

`--by-scene` judges each scene apart, § 4.14. `--base` and
`--variant` judge named variants against one base, § 4.16.
`--baseline FILE` names the old runs in a file, § 4.17. Without
them, this section holds.

Exit 0 pass, 1 a measure got slower or larger, 2 inconclusive, 3 error
or refused. Defaults: `--min-ms 0.050`, `--min-mb 1.000`, `--min-pct 3`,
`--max-load 0.25`, `--max-gpu-busy 20`. Each is 0 or more and below
1000000000, or exit 3 (FLED-0023). `--max-load` is at most 1 and
`--max-gpu-busy` at most 100, their peaks' tops, or exit 3: no peak
exceeds its top, so a limit above it never fires, as when 25 is
given for 25% (DOOM Ants). A limit at its top turns the check off
(Vestige).

- **Runs are named by set and order**: `old-1`, `old-2`, … and
  `new-1`, …, in the order given. Warnings and sentences use these
  names, never the path.
- **Each set needs at least three runs**, or exit 3 (DOOM Ants). One
  run has no spread, and two give too many false changes (below).
  Interleave them as § 4.15 does: old-1, new-1, new-2, old-2, …, so a
  steady drift cancels.
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

**Taken under load** (S22). A run is taken under load when its
`load.peak` is above `--max-load`, or its `gpu_busy_pct.peak` is above
`--max-gpu-busy`: above, not at. Other programs then shared the
machine during the run, so its times cannot be trusted. `--max-load`
is a share from 0 to 1, as `load.peak` is; `--max-gpu-busy` is a
percent, as `gpu_busy_pct.peak` is. The defaults: a quarter of the
CPU, and § 4.9's `gpu_load` limit for the GPU. A shared machine may
need higher limits: DOOM Ants passes `--max-load 0.6`. A `start` never
makes a run under load; it stays § 4.9's warning.

**Measures.** Each run gives one value per measure and segment kind
(§ 4.8's segment kind):

- `frame/wall` median and 99th percentile;
- `frame/cpu_span` and `frame/gpu_span` median;
- each `cpu` and `gpu` pass, every depth, remainders included: its
  median over the frames it appears in, as `report` gives it;
- each `mem` name, every depth: its median over the frames it appears
  in, in MB, as § 4.11 gives it.

`frame/fence_wait` and `frame/present_wait` are not judged: a wait
moves when the work around it moves. `event` and `ext` rows are not
judged.

A measure is judged only when every run of both sets has it. One
missing from some runs goes into `unmatched`, naming the runs that have
it, and judges nothing.

**Naming measures** (FLED-0031). `--measure CATEGORY/NAME` keeps only
the named measures; give it once per measure. Without it, every
measure above is judged.

- It splits at its first `/`, as under § 4.11: `frame/wall`,
  `frame/cpu_span`, `frame/gpu_span`, a `cpu` or `gpu` pass, or a
  `mem` name. Any other category, any other `frame` name (such as
  `frame/fence_wait`), an empty name, or a measure given twice, is
  exit 3, naming it.
- A name matches exactly, case included: `gpu/TAAU` does not keep
  `gpu/taau` (UT Ants).
- It keeps the name at every depth and in every segment kind, with
  each statistic judged: `frame/wall` keeps its median and its 99th
  percentile.
- A named measure that no run has is exit 3, naming it, so a misspelt
  name never passes by judging nothing. One that only some runs have
  goes into `unmatched`, as above.
- Only kept measures are judged, ranked, counted and listed in
  `unmatched`. So step 3 makes the compare inconclusive for a noisy
  `frame/wall` only when `frame/wall` is kept, and whenever every kept
  measure is unmatched (Vestige). Refusals, warnings, dropped rows, load and the static diff
  are unchanged.

**Judging a measure.** Arithmetic is exact, in fractions; JSON gives
values in the measure's unit, ms or MB, rounded to four places, half
away from zero.

- A set's **centre** is the median of its runs' values: the middle
  one, or the mean of the two middle ones.
- The **spread** is the larger of the two sets' ranges (highest run
  value minus lowest).
- The **change** is the new centre minus the old.
- The **floor** is the larger of `--min-ms` and `--min-pct` percent of
  the old centre. For a `gpu` pass, `gpu_remainder` and
  `frame/gpu_span` it is at least the largest `gpu_tick_ns` among the
  runs. For a `mem` measure `--min-mb` stands in for `--min-ms`, and
  `gpu_tick_ns` does not apply. As under § 4.11, the percent usually
  decides on `mem`.

| Verdict | When |
|---|---|
| `slower` | the change is above the spread and at least the floor |
| `faster` | minus the change is above the spread and at least the floor |
| `noisy` | neither, and the spread is above 0 and at least the floor |
| `unchanged` | otherwise |

A `mem` measure has no speed, so its `slower` is `larger` and its
`faster` is `smaller`.

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

**Many scenes multiply that rate** (Vestige). Each row above is one
compare of 25 measures. If scenes vary independently, the chance that
at least one of N scenes fails is 1 − (1 − p)^N. At 3 runs a set and
1% noise, that is 11% for 10 scenes and 52% for 60. No correction is
made. So § 4.14 counts the scenes and measures it judged, and a reader
weighs one `slower` among them.

**The command's verdict**, first match wins:

1. `inconclusive` (exit 2) when any run has dropped rows or no close
   line, or was taken under load, whatever the measures say (design:
   "nor a compare that uses them"). The first sentences name each such
   run with its drop count, or with each peak above its limit:
   "new-2 was taken under load: load.peak 0.41, above 0.25."
2. `fail` (exit 1) when any measure is `slower` or `larger`.
3. `inconclusive` (exit 2) when the `frame/wall` median is `noisy` in
   any segment kind with at least 100 frames with a `frame/wall` in
   every run (§ 4.9's `too_few_frames` bound): re-run with more runs a
   set. A shorter kind, such as a loading stretch, is noisy almost
   every time; the summary names the kinds this step skipped
   (Vestige). It is also inconclusive when `--measure` kept nothing
   that was judged, every kept measure being in `unmatched`; the
   summary names them (UT Ants).
4. `pass` (exit 0) otherwise. A `faster` or `smaller` measure is
   reported, and does not change the verdict. A `noisy` `mem` measure
   is reported too, and only `frame/wall` makes step 3 inconclusive.

**Warnings** (`warnings`, one sentence per code):

- § 4.9's, for each run, its message opening with the run's name.
  `measured` is the run's frames with a `frame/wall`.
- `not_interleaved` — every run of one set started (`started_utc`)
  before every run of the other, so drift over time reads as a change.
- `mixed_build` — a set's runs differ in `commit` or `dirty`.
- `override_unused`, above.
- `outlier_run` — one run stands apart from the rest of its set
  (FLED-0053). It is judged on the `frame/wall` median alone, in each
  segment kind where that measure is `noisy`, since only it can make
  a compare inconclusive. A kind too short for step 3 is judged too,
  so there the warning can come with a `pass` (DOOM Ants). A set's highest or lowest run is named when
  the set's range is at least the floor and dropping the run cuts the
  range by more than half. So no more than one run of a set is named,
  and never an end that two runs share. The message gives the run, its
  value and the range of the set's other runs, and says to re-run it.
  So each named run has its own sentence, where another warning has
  one per code, and under § 4.16 a base run is named once, not once
  per variant (DOOM Ants).
  The rule is the same for any number of runs: a set is often three,
  where quartiles say nothing. In a noisy set of three it names the
  end further from the middle run, unless the middle is exactly
  half-way.
- `load_differs` — the two sets' medians of `load.start` differ by more
  than 0.1.
- `gpu_busy_differs` — the two sets' medians of `gpu_busy_pct.start`
  differ by more than 10.
- `gpu_clock_differs` — the two sets' medians of `gpu_clock_mhz.end`
  differ by more than 5% of the old one. `end`, because a `start`
  is often the idle clock; the clock after the run's last frame shows
  the boost or throttling it ran at. An old median of 0, as from a driver
  reporting 0 MHz, warns on any other new median: one side's clock
  was not read, which is worth naming.

- `cpu_clock_differs` — the same for `cpu_clock_mhz.end`.
- `cpu_temp_differs` and `gpu_temp_differs` — the two sets' medians of
  `cpu_temp_c` or `gpu_temp_c` differ by more than 10 degrees. They
  are medians of `peak` when every run has one, and of `end`
  otherwise: a short run ends cooler than it ran (the engines).
- `governor_differs`, `turbo_differs`, `power_differs` and
  `sanitizers_differs` — the values of `cpu_governor`, `turbo`, `power`
  or `sanitizers` found among the old runs are not those found among
  the new. The same mix on both sides is no difference, and nor is
  the order of a `sanitizers` list. Values are compared whole; the
  message gives each side's as JSON, a long string cut short.

Each warning from `load_differs` on needs its field in every run; a
run without it gives none. Each message on medians gives both and the
limit, and names the key it judged. So two sides measured on
differently loaded, clocked, heated or set machines are named, even
when no run was under load. None of them refuses the compare: a
difference in a setting is a reason to look, and may be the thing
under test.

**Static-line diff** (UT Ants). The static line is flattened to dotted
keys (`pipelines.opaque.vs_invocations`); an array is one value. Each
key whose value is not the same in every run is listed with every
run's value, exactly as written; absent is null. The text prints the
first 20 and counts the rest.

**Opening sentences**, in order: one sentence naming every override
and its reason; with `--measure`, one naming the kept measures in the
order given ("Judging only gpu/trace and frame/gpu_span."); a refusal; each run's dropped rows, missing close
line or load; one per kind of warning; the verdict sentence, naming the slower
measure with the largest change in milliseconds, ties by percent (or
why it is inconclusive); the `larger` `mem` measure with the largest
change in MB, ties by percent, which is the verdict sentence when no
measure is `slower`; the segment kinds step 3 skipped, when
`frame/wall` is judged (DOOM Ants); the `frame/wall`
median per segment kind, old centre against new. A refusal ends the
compare after its warning sentences; a file that cannot be read still
opens with the overrides. Then a table of every ms measure not `unchanged`, one of
every such `mem` measure in MB, a count of those that are, with
`--measure` each run's values (below), then the static diff.

**Each run's values** (FLED-0031). With `--measure`, a table gives one
row per run, in the order old-1, old-2, …, new-1, …, and one column
per kept measure that was judged. Each cell is the run's value, as in
`old` and `new`, to three places. A column is headed
`category/name`, then ` p99` for a 99th percentile, the segment kind
when the judged named measures span more than one (UT Ants), and the depth when the name has more
than one. Columns that do not fit in 100 characters go into a further
table, which repeats the run column. A header too wide for one table
is cut to fit, as a measure's name is (Vestige). The JSON adds nothing for it: `old` and `new` hold the same values.

**Result:**

```json
{
  "runs": [{"name", "set", "path", "run_id", "commit", "dirty", "started_utc",
            "rows_dropped", "finished", "under_load"}],
  "min_ms", "min_mb", "min_pct", "max_load", "max_gpu_busy", "named_measures",
  "measures": [{"segment_kind", "category", "name", "depth", "statistic", "unit",
                "old": [], "new": [], "old_centre", "new_centre",
                "change", "change_pct", "spread", "floor", "verdict"}],
  "unmatched": [{"segment_kind", "category", "name", "depth", "statistic", "unit",
                 "present_in": []}],
  "static_diff": [{"key", "values": {}}],
  "refused": [{"field", "values": {}}]
}
```

`under_load` lists each peak above its limit, `load.peak` and then
`gpu_busy_pct.peak`, and is empty for a run not under load.
`named_measures` lists `--measure`'s names in the order given, and is
empty without it.
`statistic` is `median` or `p99`; `unit` is `ms` or `MB`, as under
§ 4.11; `old` and `new` list the runs' values in run order; `change_pct` is the change over the old centre,
in percent to two places, or null when the old centre is 0; `values`
maps run names to values. Measures are ranked by segment kind, then
`frame` measures in § 4.8's `frame_times` order, then `cpu`, then
`gpu`, then `mem`, each by old centre, largest first. A refused compare gives only
`runs` and `refused`; one refused for a named measure no run has gives
only `runs` and `named_measures` (Vestige).

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
  no depth to pick, it is 128 (Vestige, UT Ants). Without it, the
  references must have the name at one and the same depth, or 128,
  naming each run's depths: a name at two depths in one run, in
  different frames, or at another depth in another reference (Vestige,
  DOOM Ants). A tested commit whose runs have it at another depth from
  the references, at two depths, or at different depths from each
  other, skips (125): one restructured commit must not end the search
  (FLED-0020, UT Ants). A pass is never judged against itself at
  another depth either way.
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
silently do nothing. So is any of the three outside § 4.10's range. On `mem` the percent usually decides: 3 percent of
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
without the measure in the chosen frames; and tested runs at another
depth, as above. An empty file, the commonest
remains of a crashed benchmark, is one that breaks the format. Each
such run has its own sentence naming it and why. For a missing
measure it also names the segment kinds the run has, or with
`--segment` its segments, so a wrong `--kind` shows on the first skip.
For a depth it names the measure, each tested run's depths and the
references', and says `--depth D` judges such commits, so a range
crossing a re-nested pass shows the way through (DOOM Ants, UT Ants).

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
  "refused": [{"field", "values": {}}],
  "skip_reason": "unreadable | incomplete | missing | depth | straddle"
}
```

`segment` is the `--segment` given, or null; `segment_kind` is its
kind, or `--kind`'s, or null for `--unsegmented`. `set` is `tested`,
`good` or `bad`. `unit` is `ms` or `MB`. `value` is the tested value, or
the dry run's `VALUE`; null on `skip` and `stop`. A run's own `value` is
null when it has none. `bad_above` is `X` or the midpoint. `references`
is null in threshold mode. `skip_reason` names the first skip class
that applied, in the order listed under Skip (125), with `straddle`
last; null unless the verdict is `skip`. git bisect runs one commit at a
time, so a caller counting depth skips apart from missing measures
counts this field (Vestige).

### 4.12 Pass budgets

FLED-0010 builds this (S12). Reviewed by the three engines 2026-10-29;
their changes are folded in.

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
| `depth` | an integer from 0, at most nine digits, or empty |
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
  `category`, `name` and `statistic`, at the same depth once an empty
  depth is resolved (UT Ants, Vestige). `gpu,ssao,*,,p99,2.000` with
  `gpu,ssao,view,0,p99,3.000` judges view at 3.000 and every other kind
  at 2.000, when `ssao` is at depth 0. A named line resolves its depth
  in its own kind; a `*` line in the kinds it still judges. Named lines
  at two depths of one kind each take their own depth (DOOM Ants, UT
  Ants). Two lines that resolve to one pass, kind, depth and statistic
  are exit 3, naming both.
- **`match`**, optional, names § 4.2's compare-blocking fields and the
  values the budgets were set for (UT Ants). The run's values must
  match as § 4.10's refusals match runs: numbers by value, `inputs` as
  `name` and `hash` pairs in any order. There is no tolerance: copy
  each value as the run's header writes it, since `0.667` does not
  match `0.6667` (UT Ants). A field the run leaves out does not match. A mismatch is exit 3, naming each field with both values.
- **`--warmup-s S`**, default 0, leaves out frames ending before S
  seconds, on § 4.7's timeline, as `floor` does (Vestige). At 0 every
  value is `report`'s (UT Ants, DOOM Ants); at 2 the frames judged are
  `floor`'s. Above 0, a hole in the frame numbers or a frame other
  than the last with no `frame/wall` makes the verdict inconclusive:
  the frames after it cannot be placed. A pass over budget still
  fails, as under § 4.7: past a hole the ends come too early, so a frame
  placed after the warm-up truly ended after it. When no frame ends
  after the warm-up, one sentence says so in place of one per unmatched
  budget: the run is too short, not the file wrong (UT Ants). A
  negative `S`, or one of 1000000000 or more, is exit 3, as under
  § 4.7.
- **An empty `depth`** needs the name at one depth in the frames
  judged, as § 4.11's `--depth`; at two it is exit 3, naming the pass
  and both depths (Vestige).
- **A budget nothing matches** is never a pass: a renamed pass would
  otherwise hold its budget forever. A `kind` not in the run, a pass
  in no frame of its kind, or a `*` pass in no frame at all is listed
  in `unmatched` and named in a sentence. It makes the verdict
  inconclusive; it is not a warning. The pass is in none of those
  frames, so a re-run gives the same: the fix is in the budget file or
  the engine (Vestige).
- **Dropped rows or no close line** make the verdict inconclusive: the
  frames judged may be missing their costliest rows.
- **A pass over budget fails regardless** of either, as § 4.7's frame
  check does: its value is over the frames that were measured.
- **`budget_few_frames`** warns when a `p99` budget is judged over
  fewer than 100 frames: below that, the nearest-rank 99th percentile
  is the slowest frame. § 4.9's warnings are given too. A warning never
  changes a verdict.
- **Exit 3** for the budget file: no header or a `schema` other than
  1, a `match` key that is not a compare-blocking field or a value
  breaking § 4.2's rule for that field (Vestige), a different
  column line, a value breaking its column's rule, no budget line, or
  two lines with the same `category`, `name`, `kind`, `depth` and `statistic`. The
  summary names the budget file's line. For the run file, as
  `report`'s.

**Text** opens with § 4.8's warning sentences, then one sentence per
pass over budget, most milliseconds over first, then one per unmatched
budget:
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

### 4.13 Surveying many runs

FLED-0012 builds this (S9, S19). The design was agreed with the three
engines 2026-11-04.

```
survey FILE… (--fps N | --budget-ms B) [--warmup-s S] [--allow-frames K]
```

Exit 0 when every run is judged and none is flagged; 1 when a run is
flagged; 2 when none is flagged but a run is unjudged or its frame
check is inconclusive, so a crashed map never reads as clean (DOOM
Ants, UT Ants, Vestige); 3 for a bad flag. Defaults and limits are
`floor`'s, § 4.7: `--warmup-s 2`, `--allow-frames 0`, the budget
`--budget-ms` or 1000/`--fps` rounded up to three places, and the same
exit-3 bounds on each.

- **Each run is judged on its own**, in the order given. A file that
  cannot be read or breaks the format is listed as unjudged, with the
  reason and its first breach's line, and the survey goes on: one
  crashed benchmark must not hide the other maps.
- **The frames judged are `floor`'s**: those ending at or after the
  warm-up on § 4.7's timeline. A frame carrying `event/cut` is judged,
  as under § 4.7. So survey and `floor` give one answer on one file
  (Vestige, DOOM Ants).
- **The flag is `floor`'s single-frame check**, § 4.7, exactly: a run
  is flagged when more of its judged frames are over the budget than
  `--allow-frames`. It is inconclusive, unless flagged, on § 4.7's
  grounds: dropped rows, no close line, a hole, a frame other than the
  last with no `frame/wall`, or no frame after the warm-up. **The
  per-second window check is not run**, and the text says so, so a run
  not flagged is never read as one that passes `floor` (Vestige).
- **A flagged run names its slowest frame over the budget**: its
  frame number, segment, `frame/wall`, and `top_pass` as § 4.8's
  `worst_frames` gives it. That is S9's costliest pass. It points at
  the frame that set the flag, whichever kind holds it (Vestige).
- **The rank** is over segment kinds with at least 100 judged frames,
  as § 4.10's fewest; a shorter kind would rank on one hitch, since its
  nearest-rank 99th percentile is its slowest frame (Vestige). For each
  kind, `frame/wall`'s median and 99th percentile over its judged
  frames. A run's worst kind has the highest 99th percentile, ties by
  median, then name; its worst segment is that kind's segment with the
  highest 99th percentile, ties by median, then segment compared as
  text, so `view:10` before `view:2` (UT Ants).
  Runs rank by their worst kind's 99th percentile, slowest first, ties
  by its median, then the order given. A run with no kind of 100
  judged frames, or unjudged, has no rank and is listed after the
  ranked runs, in the order given. Every kind is listed with its
  figures, ranked or not.
- **The rank and the flag answer different questions** (UT Ants). A
  run can rank first and pass, its frames slow but under the budget,
  or be flagged by one frame with a low 99th percentile, or by a kind
  too short to rank.
- **§ 4.9's warnings** are given per run, each message opening with
  the run's path.
- **Each file is read once, and let go before the next**, so memory
  grows with the largest file, not with the survey. A million-row file
  took 10.3 s and peaked at 636 MB (2026-11-04, at a load average of
  11; refute by timing `survey` on a generated million-row file), inside
  S19's minute.

**Text** opens with one sentence per flagged run, in rank order, those
with no rank after the ranked in the order given (UT Ants), then one
per inconclusive or unjudged run, then each run's warnings, then
the verdict:
"maps/e1m2.csv is flagged: 3 frames after the 2 s warm-up are over the
16.667 ms budget, the slowest frame 812 in view:3 at 41.200 ms (top
pass gpu/opaque); floor's per-second check was not run." Then a table
of every run: rank, file, worst segment, median, p99, frames over
budget and verdict, within 100 columns. A file name too long for its
column is cut from the left, keeping its end, and opens with `…` to
show the cut (Vestige). Where two or more files are all in one
directory, the heading names it once, "Runs, slowest first, each file
in runs/:", and each row shows the path after it, so the column is not
spent on what every row shares (DOOM Ants). The directory is read from
the paths as given, up to their last shared `/` or `\`; a lone `/` or
`./` is not one. The sentences above the table and `--json` keep whole paths.

**Result.** The verdict is `fail` when a run is flagged;
`inconclusive` when none is but a run is unjudged or inconclusive;
`pass` when every run is judged and none is flagged, which is not
`floor`'s pass, since the window check is not run (UT Ants); or
`error` for a bad flag. They are exits 1, 2, 0 and 3.

```json
{
  "runs": [{"path", "run_id", "verdict", "reason", "rank",
            "worst_kind", "worst_segment", "median_ms", "p99_ms",
            "frames_over_budget", "slowest_over",
            "kinds": [{"segment_kind", "median_ms", "p99_ms", "frames", "ranked"}],
            "warnings": [{"code", "message"}]}],
  "budget_ms", "warmup_s", "allowed"
}
```

A run's `verdict` is `flagged`, `clean`, `inconclusive` or
`unjudged`. `reason` says why a run is inconclusive or unjudged, and
is null otherwise. `rank` counts from 1, or is null. `median_ms` and
`p99_ms` are the worst kind's; with no rank, they and `worst_kind` and
`worst_segment` are null. `slowest_over` is `{"frame", "segment",
"wall_ms", "top_pass"}`, or null when no judged frame is over the
budget. `runs` is in rank order, then the unranked in the order given.
The path is in the result and the text, since a survey names its
files; a run's own figures still name no line number.

### 4.14 Comparing surveys

FLED-0013 builds this (S15). The design was agreed with the three
engines 2026-11-04.

```
compare --by-scene --old FILE… --new FILE… [--override FIELD=REASON]… [--min-ms M] [--min-mb M] [--min-pct P] [--max-load L] [--max-gpu-busy P] [--measure CATEGORY/NAME]…
```

The flags are § 4.10's, with its defaults and bounds.

- **A scene is the header's `scene` field**, matched exactly as text.
  `scene` is required (§ 4.2), so a file without it breaks the format.
  A file that cannot be read, breaks the format, or has an empty
  `scene` is listed as unread with its reason, and the rest go on.
- **Each scene is judged as § 4.10 judges one compare**: its old runs
  against its new, with the same names, refusals, measures, judging,
  verdict and warnings, `not_interleaved` included. `scene` cannot
  refuse, since it is the same in every run of a scene. Every other
  compare-blocking field still refuses, and each `--override` applies
  to every scene.
- **A scene is unjudged, and the others go on** (all three engines),
  when it has no old runs or no new runs, naming the side it lacks
  ("e2m2: no new runs"; DOOM Ants), when a side has fewer than three
  runs, or when it refuses. One broken map must not hide a slowdown on
  another. The scenes need not be the same in both sets: a subset
  judged before a release leaves the others unjudged (DOOM Ants).
- **A scene's runs are read when it is judged, and let go after**, so
  memory grows with the largest scene, not with the survey.
- **A failing scene names its verdict measure**: § 4.10's measure
  named in the verdict sentence, the slower one with the largest
  change in ms, or else the larger `mem` one in MB. Within that
  measure's segment kind, it also names the segment whose centre
  changed most, new minus old, ties by segment compared as text (UT
  Ants). A segment's value in a run is the measure taken over that
  segment's frames alone. Its centre on each side is § 4.10's, over the
  runs that have the segment, and a segment missing from every run of
  one side is not named. This points at where to look. It judges
  nothing.
- **Failing scenes are ranked**: those with a slower measure first, by
  its change in ms, largest first, then those with only a larger
  `mem` measure, by its change in MB; ties by percent, then scene name.
- **`override_unused`** is given once, when the field differs in no
  scene.
- **`--measure`** keeps the same measures in every scene. A named
  measure is exit 3 only when no scene's runs have it (step 2). A scene
  whose kept measures are all unmatched is inconclusive, as § 4.10's
  step 3 makes a compare (Vestige). A scene none of whose runs has
  any named measure is unjudged, "none of its runs has a named
  measure", and the command's step 4 passes over it: naming
  `gpu/water` must not make every scene without water inconclusive
  (Vestige). The text gives no per-run table; each scene's `compare`
  holds the values.

**The command's verdict**, first match wins:

1. `error` (exit 3) for a bad flag, as § 4.10.
2. `error` (exit 3) when no scene could be judged: every scene is
   unjudged, or every file is unread. It is almost always a mistake in
   the setup, such as a wrong folder or a GPU differing in every file
   (UT Ants). The opening sentence says so plainly: "No scene could be
   judged:", then each scene's reason and each unread file's (DOOM
   Ants, Vestige). It is also `error`, checked first, when a named
   measure is in no scene's runs. Then the text is only the overrides
   sentence and § 4.10's sentence naming it, and the result is only
   `named_measures`, every name given, as for a plain compare (UT Ants,
   DOOM Ants). When some file or some scene's runs went unread, the
   sentence says "No run read has" (DOOM Ants).
3. `fail` (exit 1) when any scene fails.
4. `inconclusive` (exit 2) when any scene is inconclusive or unjudged,
   or any file is unread. A scene unjudged for having none of the
   named measures does not count here.
5. `pass` (exit 0) otherwise.

So a scene that is inconclusive under § 4.10, for dropped rows, say,
counts as judged.

**Text** opens with the overrides sentence, as § 4.10; then one
sentence per failing scene, in rank order: "e1m2 is slower: the
gpu/opaque median in view rose from 3.100 to 3.512 ms, most in
view:3." Then one per inconclusive scene with § 4.10's reason, one per
unjudged scene with its reason, one per unread file with its path and
reason, and each scene's warnings, opening with the scene's name.
Then one sentence counting what was judged: "Judged 8 scenes and 412
measures; with this many, a slower measure can be chance (§ 4.10)."
Then a table of every scene: rank, scene, verdict, measure, change and
segment, within 100 columns, cut as § 4.13 cuts a file name.

**Result.**

```json
{
  "scenes": [{"scene", "verdict", "reason", "rank",
              "measure", "segment", "compare"}],
  "unread": [{"path", "set", "reason"}],
  "judged": {"scenes", "measures"},
  "min_ms", "min_mb", "min_pct", "overrides"
}
```

A scene's `verdict` is `fail`, `inconclusive`, `pass` or `unjudged`.
`reason` says why a scene is inconclusive or unjudged, and is null
otherwise. `rank` counts from 1 over failing scenes, or is null.
`measure` is the verdict measure's entry from `compare`'s `measures`,
or null. `segment` is the segment named, or null. `compare` is
§ 4.10's result for the scene, or null when the scene is unjudged for
lacking runs or for a file that changed after it was first read; a
refused scene's is § 4.10's refused result, and a scene with none of
the named measures has its full result.
`judged.scenes` counts the scenes not unjudged; `judged.measures` sums
the measures each of them judged. `scenes` lists failing scenes in
rank order, then the others by scene name. `set` is `old` or `new`.

### 4.15 Alternating runs

FLED-0029 builds this (S21). The engine still times each frame and
writes each run file; this command only starts the engine's command
for each run, in turn, and then compares what they wrote.

```
alternate --old CMD --new CMD --out DIR [--runs N] [--warmup W] [--override FIELD=REASON]… [--min-ms M] [--min-mb M] [--min-pct P] [--max-load L] [--max-gpu-busy P] [--measure CATEGORY/NAME]…
```

The compare flags are § 4.10's, with its defaults and bounds.
`--base` and `--variant` run named variants, § 4.16. `--baseline`
takes the place of `--old`, § 4.17.
A `--measure` name is checked for its form before any command starts,
but whether a run has it only after every run has finished: names come
from the runs (Vestige). The run files stay, for `compare` to re-read.
`--runs` is the number of runs a side: default 5, from 3 to 100, or
exit 3. Five, because § 4.10's table gives 3% false changes at five
runs a set and 35% at three, both at 2% noise.

- **`{run}` is the placeholder.** Each `CMD` must hold it at least
  once, or exit 3. Before each run, every `{run}` in that side's
  command is replaced by the run's own file: `DIR/old-1.csv`,
  `DIR/new-1.csv`, `DIR/new-2.csv`, …, as an absolute path. So no run
  overwrites another (DOOM Ants, Vestige). The command writes its run
  file there, for example `--frame-log={run}`.
- **Runs go in pairs, each pair one run a side**: old first in odd
  pairs, new first in even ones. So the order is old-1, new-1, new-2,
  old-2, old-3, new-3, …, each command finishing before the next
  starts. A steady drift over time then cancels over every two pairs;
  in plain alternation each new run would come one step after its old
  partner, and the drift would read as a change (UT Ants, Vestige).
- **`--warmup W` runs W untimed runs a side first**, default 0, from 0
  to 10, or exit 3. They alternate, old first: `old-warmup-1`,
  `new-warmup-1`, …, each into its own file. They fail as any run does
  and are never compared. One a side takes a cold cache's cost off
  the first compared runs (UT Ants, Vestige).
- **Each command runs through the platform's shell**: `/bin/sh` on
  Linux and macOS, `cmd.exe` on Windows, in the current directory. Its
  standard output and standard error go to this command's standard
  error, so `--json` output is never mixed with the engine's. Before
  each run, one line on standard error names it, counting warm-ups:
  "alternate: running new-2 (3 of 10)".
- **`DIR` must exist, and its absolute path may hold only ASCII
  letters, digits, and `.` `_` `-` `/` `\` `:`**, or exit 3. So the
  filled path needs no quoting in either shell. A space is refused;
  pick a folder without one. This limits `DIR` only; the rest of a
  command may hold anything its shell accepts (UT Ants).
- **No run file is ever overwritten.** If any of the run files,
  warm-ups included, already exists in `DIR`, exit 3 before any
  command starts, naming the file.
- **Setup errors run nothing.** Every exit 3 above is found before the
  first command starts.

**A run that fails stops the rest**, exit 3, verdict `error`, and
nothing is compared. A run fails when its command exits with a code
other than 0, is killed by a signal, or exits 0 and leaves no file at
its path. Setup has already made sure no file was there before. On
Linux and macOS a run also fails when its command exits 0 but a
process it started is still running 2 seconds later, since that
process would overlap the next run (UT Ants). The 2 seconds let a
headless display finish tearing down (DOOM Ants).
Stopping `alternate` with SIGINT (Ctrl-C) or SIGTERM (`kill`,
`timeout`, a service manager) fails the running command the same way
(DOOM Ants).

- **On Linux and macOS each command runs in its own process group**, so
  a stop reaches every process it started, the engine behind a wrapper
  script or a `cd … &&` included. `alternate` passes the stop signal
  on to that group, since the terminal's Ctrl-C reaches only
  `alternate`'s own.
- **On Windows each command runs in its own console process group**
  (FLED-0063), so the console's Ctrl-C reaches only `alternate`.
  Ctrl-C and Ctrl-Break stop it, as SIGINT does. It passes a stop on
  as a Ctrl-Break to the command's group; the kill below is
  `taskkill /T /F`, which ends `cmd.exe` and every process it started
  (Vestige). Both reach a process only while `cmd.exe` still runs, so
  on Windows a process left behind by a command that has exited is
  neither checked for nor ended. A windowed engine never receives a
  Ctrl-Break, and none can be sent when `alternate` has no console (a
  service, a scheduled task); then a stop waits out the 10 seconds
  below and kills (UT Ants). An engine on Windows sees a stop as
  Ctrl-Break, never Ctrl-C, and Ctrl-Break's default ends it at once.
  So an engine that writes its close line on Ctrl-C handles Ctrl-Break
  the same way (`SIGBREAK`, or `CTRL_BREAK_EVENT` in
  `SetConsoleCtrlHandler`), or its stopped runs have no close line
  (Vestige).
- **A failed command's processes are ended before its file is
  deleted.** Any left are sent SIGTERM, or the stop signal, and given
  10 seconds; then they are killed. A second stop signal kills them at
  once. So nothing writes the file after it is deleted. A process that
  still has not ended 10 seconds after being killed, as one stuck in a
  GPU driver can, is not waited for: the reason ends "; process group
  N did not end after being killed" (UT Ants). The kill is SIGKILL on
  Linux and macOS, `taskkill /T /F` on Windows (DOOM Ants).
- **A stop is only recorded when it arrives**, and each wait checks for
  one, so a stop cannot land between two steps (DOOM Ants).
- **Then its file, if it left one, is deleted**; a directory there is
  left alone. So the run files left in `DIR` are exactly the runs in
  `stopped.finished`, and a reader can compare them by hand. To run
  again, give a new `DIR`, or remove its run files.

The text then opens with § 4.10's overrides sentence, when
`--override` is given; next a sentence naming the run and the reason,
"new-2 failed: the command exited with code 4.", "new-2 failed: the
command was killed by signal 11 (SIGSEGV).", "new-2 failed: the
command exited with code 139, as the shell reports a command killed by
signal 11 (SIGSEGV).", "new-2 failed: the command left processes
running.", "new-2 failed: alternate
was stopped by SIGTERM while it ran." or "new-2 failed: the command
wrote no file at /…/new-2.csv."; then its filled command, "Its command
was: …".

**Once every run has finished**, the files are compared as
`compare --old DIR/old-1.csv … --new DIR/new-1.csv …` compares them,
§ 4.10: the same names, refusals, measures, judging, verdict, exit
code, text and warnings. A file that breaks the format is § 4.10's
exit 3.

**Result.** § 4.10's result, with three keys added. For a run of
`--runs 3` stopped at new-2:

```json
{
  "commands": {"old": "./old/engine --frame-log={run}",
               "new": "./new/engine --frame-log={run}"},
  "out": "/home/me/ab",
  "warmup": 0,
  "stopped": {"run": "new-2",
              "command": "./new/engine --frame-log=/home/me/ab/new-2.csv",
              "reason": "the command exited with code 4",
              "exit_code": 4,
              "finished": ["old-1", "new-1"]}
}
```

`commands` holds the two commands as given, placeholder and all.
`out` is `DIR` as an absolute path. `warmup` is `--warmup`. `stopped`
is null when every run finished. When a run failed, `command` is its
filled command; `exit_code` is its command's code, or null when it
wrote no file, was killed by a signal or was stopped; `finished` names the runs before it,
warm-ups included, in the order they ran. The result then holds only
`commands`, `out`, `warmup` and `stopped`.

### 4.16 Variants against one base

FLED-0034 builds this (S23). One base, such as the full frame, and
named variants, such as the frame with each effect switched off in
turn. Each variant is judged against the base as § 4.10 judges new
against old (UT Ants' UTA-0436, each effect's cost).

```
compare --base FILE… --variant NAME FILE… [--variant NAME FILE…]… [--override FIELD=REASON]… [--min-ms M] [--min-mb M] [--min-pct P] [--max-load L] [--max-gpu-busy P] [--measure CATEGORY/NAME]…
alternate --base CMD --variant NAME CMD [--variant NAME CMD]… --out DIR [--runs N] [--warmup W] [the same compare flags]
```

The compare flags are § 4.10's, with its defaults and bounds.

**Setup.** Each of these is exit 3, verdict `error`, before any file is
read or any command starts:

- `--base` with `--old`, `--new` or `--by-scene`; `--base` without
  `--variant`; `--variant` without `--base`.
- A variant name that is not lowercase ASCII letters, digits and `_`,
  starting with a letter, at most 32 characters; the names `base`,
  `old` and `new`; a name given twice. So a name is safe in a file
  name on every platform, and `a-1.csv` cannot be both variant `a`'s
  first run and another variant's file.
- Under `compare`, fewer than three files for the base or any
  variant, as § 4.10.
- Under `alternate`, every § 4.15 setup error, for every side's
  command and files (DOOM Ants).

**Runs are named by side and order**: `base-1`, `base-2`, … and
`<name>-1`, …, in the order given. Within each variant's compare the
base is § 4.10's old set and the variant its new set, under these
names.

**Each variant is judged as § 4.10 judges one compare**: the base runs
against that variant's runs, with the same refusals, measures,
judging, verdict and warnings. Each `--override` applies to every
variant. `override_unused` is given once, when the field differs in no
variant. The base runs are read once and kept; each variant's runs are
read when it is judged and let go after.

- **A file that cannot be read, or breaks the format**, is exit 3, as
  § 4.10: the files were named one by one, so a bad one is a mistake
  in the command. Under `alternate` the tool named the files, and a
  long session must not be lost to one broken variant build: a
  variant file that cannot be read, or breaks the format, makes that
  variant unjudged, naming the file and its reason, with `compare`
  null, and the others go on. Such a base file is still exit 3 (DOOM
  Ants).
- **A variant that refuses is unjudged, and the others go on**, as a
  scene does under § 4.14. Its reason names each field, as § 4.10's
  refusal sentence does.
- **`--measure`** keeps the same measures in every variant. A named
  measure is exit 3 only when no run has it, a refused variant's runs
  included (DOOM Ants). A variant none of whose
  own runs has any named measure is unjudged, "none of its runs has a
  named measure", and step 4 below passes over it, as § 4.14. This
  holds even when the base runs have the measure (Vestige).
- **An effect's own pass is gone when the effect is off.** So
  `--measure gpu/bloom` leaves `no_bloom` unjudged, with no cost. To
  rank effects switched off, name a measure every side keeps, such as
  `frame/wall` or `frame/gpu_span`, or give no `--measure` (Vestige).

**The rank measure** is the first `--measure` name, or `frame/wall`
without one, its median. A pass may appear at more than one depth
(§ 4.4: 0 is a top-level pass, 1 a pass inside one); the rank measure
takes the smallest depth at which the base runs have it (UT Ants).
Its segment kind is the one with the most frames carrying it at that
depth, over the base runs together (UT Ants: depth first, so 3 `load`
frames at depth 0 are chosen over 3000 `view` frames at depth 1); ties
by kind compared as text, frames with no
segment counting as the kind `""`. A variant's **rank entry** is that
measure's entry in its compare's `measures`, or none when the variant
is unjudged or the measure is in its `unmatched`.

**Variants are ranked** by their rank entry's change, lowest first, so
the variant that saved the most time ranks 1: with each effect
switched off in turn, the costliest effect comes first. Ties by name.
A variant with no rank entry is not ranked. The rank orders; it judges
nothing. A change that is `noisy` or `unchanged` still ranks, and the
table shows its verdict beside it.

**The command's verdict**, first match wins:

1. `error` (exit 3) for a setup error or a file as above.
2. `error` (exit 3) when a named measure is in no run of any side,
   base included, worded as § 4.14's step 2 (DOOM Ants).
3. `error` (exit 3) when no variant could be judged, every one
   unjudged. The opening sentence says "No variant could be judged:",
   then each variant's reason.
4. `fail` (exit 1) when any variant fails.
5. `inconclusive` (exit 2) when any variant is inconclusive or
   unjudged. A variant unjudged for having none of the named measures
   does not count here.
6. `pass` (exit 0) otherwise.

**Text** opens with the overrides sentence and, with `--measure`, the
kept measures, as § 4.10. Then one sentence per failing variant, by
name, § 4.10's verdict sentence opening with the variant's name:
"no_bloom is slower: the gpu/opaque median in view rose from 3.100 to
3.512 ms." Then one per inconclusive variant with § 4.10's reason, one
per unjudged variant with its reason. Then § 4.10's sentence for each
run taken under load, the base's first: "a-3 was taken under load:
load.peak 0.9, above 0.25." A loaded base run makes every variant
inconclusive, and this names it once (Vestige). A base run's § 4.9 warnings are
given once, opening with the run's name, not once per variant; so is
the warning that the base runs are not one build (UT Ants, DOOM
Ants). Then each variant's warnings, the variants by name. A run's
opens with the run's name, `no_bloom-1`; one about a whole set opens
with the variant's name and calls the sets "the base runs" and "the
no_bloom runs". A variant unjudged for having none of the named
measures still gives its warnings (Vestige). Then one sentence
naming the rank measure: "Ranked by the frame/wall median in view;
base 16.400 ms." When no base run has it, the sentence is "Nothing is
ranked: no base run has gpu/x.", and every rank cell is `-`, as an
empty cell is in every table (Vestige). When only some base runs have
it, the measure is in every variant's `unmatched`, so no variant has a
rank entry, and the sentence is "Nothing is ranked: not every base run
has the gpu/x median in view." (Vestige). Then one counting what was judged, as § 4.14: "Judged 4
variants and 96 measures; with this many, a slower measure can be
chance, and a base that ran unusually fast or slow moves every variant
together." Every variant shares the base runs, so their verdicts are
not independent: re-run the base before believing several slower
variants at once (Vestige). Then a table of every variant: rank, variant,
verdict, the rank measure's centre, its change in ms or MB and in
percent, and its own verdict (`faster`, `noisy`, …), within 100
columns. Each variant's `compare` holds its full measures; the text
gives no per-measure table.

**Result.**

```json
{
  "variants": [{"name", "verdict", "reason", "rank", "measure", "compare"}],
  "rank_measure": {"segment_kind", "category", "name", "depth", "statistic"},
  "judged": {"variants", "measures"},
  "min_ms", "min_mb", "min_pct", "max_load", "max_gpu_busy",
  "named_measures", "overrides"
}
```

A variant's `verdict` is `fail`, `inconclusive`, `pass` or `unjudged`.
`reason` says why it is inconclusive or unjudged, and is null
otherwise. `rank` counts from 1, or is null. `measure` is its rank
entry, or null. `compare` is § 4.10's result for the variant; a
refused variant's is § 4.10's refused result. `rank_measure` is null
when no base run has the rank measure. `judged.variants` counts the
variants not unjudged; `judged.measures` sums the measures each of
them judged. `variants` lists ranked variants in rank order, then the
others by name.

**`alternate` with variants** runs the base's command and each
variant's as § 4.15 runs old and new: the same placeholder, shell,
failures, stops and files, with files named `DIR/base-1.csv`,
`DIR/<name>-1.csv`, `DIR/base-warmup-1.csv`, ….

- **Runs go in rounds, each round one run a side.** Odd rounds run
  the base, then each variant in the order given; even rounds run the
  reverse. So with variants `a` and `b` the order is base-1, a-1, b-1,
  b-2, a-2, base-2, base-3, …. A steady drift then cancels over every
  two rounds, for every side; with one variant this is § 4.15's order
  (UT Ants: so drift is not read as an effect's cost).
- **Two limits of that order** (DOOM Ants). Drift cancels exactly only
  over an even `--runs`: an odd one ends on a forward round, so each
  side's last run is later the further down the list it is. The first
  and last sides are then one slot fewer than the count of sides
  apart, so the more variants, the larger the bias (UT Ants). And the
  first and last sides run twice in a row at each round's turn, so a
  warm cache favours them; a middle variant never does. Give an even
  `--runs` when drift matters, and judge an end side's small gain
  with this in mind.
- **Warm-ups** run W rounds first, each the base and then each variant
  in order.
- **Once every run has finished**, the files are compared as
  `compare --base … --variant NAME …` compares them, above. The result
  is that compare's, with § 4.15's `out`, `warmup` and `stopped`, and
  `commands` mapping `base` and each variant's name to its command.

### 4.17 A saved baseline

FLED-0035 builds this (S24). A baseline file names a set of reference
runs, and stands in for the old runs of a compare. The engine keeps
the file and the runs it names; the analyser keeps nothing. Agreed by
the three engines 2026-11-12.

```
compare --baseline FILE --new FILE… [--by-scene] [the compare flags]
compare --baseline FILE --variant NAME FILE… [--variant NAME FILE…]… [the compare flags]
alternate --baseline FILE --new CMD --out DIR [--runs N] [--warmup W] [the compare flags]
alternate --baseline FILE --variant NAME CMD [--variant NAME CMD]… --out DIR [--runs N] [--warmup W] [the compare flags]
```

`--baseline FILE` takes the place of `--old`, or of `--base` when
`--variant` is given. `bisect` does not take it: § 4.11 has its own
reference files.

**The baseline file** is UTF-8 text, LF or CRLF, as § 4.12's budget
file. A byte-order mark at its start is skipped.

```
# frameledger-baseline {"schema":1}      line 1, required
runs/meadow-1.csv                        one run file per line
runs/meadow-2.csv
runs/meadow-3.csv
# any later line beginning # is a comment
```

- **Line 1** is the keyword and one JSON object whose `schema` is the
  integer 1. Its other keys are ignored.
- **Each later line is one run file's path**, as written, with spaces
  at both ends removed and no quoting. A blank line is skipped, and so
  is a comment line, whose first character after any spaces is `#`
  (Vestige). A comment line can say what the runs were taken at, such as
  "# scale 50, shot-0069" (DOOM Ants).
- **A relative path starts at the folder that holds the baseline
  file**, not at the current directory. So the file and its runs can
  be committed together, and found from anywhere (UT Ants, DOOM Ants).
  In a relative path `/` and `\` both separate folders, on every
  platform, so one file serves Linux and Windows.
- **A path that opens with a slash or a drive letter must be absolute
  on the system reading it**, or the file is refused: `\runs\a.csv`
  or `C:\runs\a.csv` on Linux, `/runs/a.csv` or `C:a.csv` on Windows
  (UT Ants). A later part that opens with a drive letter,
  `runs/C:a.csv`, is refused too (DOOM Ants). Joined to the folder, it
  would name a file the line never wrote (Vestige).
- **A path may climb out with `..`, or be absolute.** Run files of
  every frame are large to commit. A baseline whose runs sit outside
  the repository serves the one machine that holds them (Vestige).
- **The file names runs and nothing else**: no limits, no measure
  list, no hash of a run. `--min-ms` and `--measure` stay flags, so one
  baseline serves several gates (DOOM Ants).

**Setup.** Each of these is exit 3, before any run file is read or
any command starts:

- `--baseline` with `--old` or `--base`; `--baseline` with neither
  `--new` nor `--variant`.
- A baseline file that cannot be read; a line that is not UTF-8; a
  line 1 that is not the keyword and a JSON object, one nested too
  deep to read included (UT Ants); a `schema` other than 1.
- Fewer than three run files listed, as § 4.10's sets.
- Two lines that name one file, naming both lines. A symbolic
  or hard link to the file, and on Windows another letter case, is the
  same file: one run counted twice would narrow the spread (Vestige,
  UT Ants).
- A path that opens with a slash or a drive letter and is not
  absolute, above.
- A listed path that is not a file, naming the path and its line. So a
  moved run file is never read as a regression (Vestige).

**The listed runs are the old runs**, `old-1`, `old-2`, … in the
file's order, or `base-1`, … with `--variant`. From there the compare
is § 4.10's, § 4.14's with `--by-scene`, or § 4.16's with `--variant`:
the same refusals, runs taken under load, measures, judging, verdict,
exit code and warnings. A listed file that cannot be read, or breaks
the format, is treated as that file given after `--old` or `--base`.
A baseline taken on another `device` or `api` is refused as any old
run is, and needs its `--override` (Vestige).

**Text.** One sentence follows the overrides sentence, or comes first
without one: "The old runs are the baseline /home/me/perf/meadow.txt."
With `--variant` it says "The base runs". It is there on a refusal
and on an error too.

**Warnings**, with `--baseline` only. None changes a verdict or an
exit code.

- `baseline_not_interleaved` — every baseline run started before
  every new run. It is given in place of § 4.10's `not_interleaved`,
  and names the baseline's `commit`, the UTC day its oldest run
  started, and how long that was before the first new run started:
  "the old runs are a baseline of commit 6012f70, started 2026-11-03
  (UTC), 9 days before the first new run; nothing ran in turn with
  them, so a drift on the machine since then reads as a change". The time is in
  whole days, or whole hours under one day, or whole minutes under one
  hour, rounded down; under one minute it reads "less than a minute". Several commits are each named, and a `dirty`
  one is marked "(dirty)". A stored baseline cannot alternate with the
  new runs, so the reader is told every time (all three engines). When
  the baseline runs did not all start first, § 4.10's own rule decides
  `not_interleaved` as ever.
- `baseline_driver_differs` — the baseline runs' `driver` values are
  not the new runs' (UT Ants: two kept results were not baselines at
  all, because the driver had moved). It names both sides' values, each
  in double quotes.
- `baseline_os_differs` — the same for `os`. It needs `os` in every
  run.

Under § 4.14 and § 4.16 each is a set warning, opening with its
scene's or variant's name as `not_interleaved` does. So each variant
has its own, with its own age: its first run started at its own time.

**Result.** Every `compare` and `alternate` result that is not empty
gains `baseline`: the baseline file's absolute path, or null without
`--baseline`. It is the command's own key: a scene's or variant's
`compare` does not hold it.

**`alternate` with a baseline** runs only the new command: `new-1` to
`new-N` one after another, after `new-warmup-1` to `new-warmup-W`.
With `--variant` it runs § 4.16's reversing rounds over the variants
alone. `--runs` counts the runs of each side it runs; the baseline
has the runs it lists. `commands` holds no `old` or `base`. Then the
files are compared as `compare --baseline` compares them. Nothing
alternates with the baseline, so machine drift is not cancelled, and
`baseline_not_interleaved` says so.

**The analyser never writes a baseline file.** To take or renew one,
keep the run files of a session, such as `alternate`'s `DIR/new-1.csv`
to `DIR/new-N.csv`, and list them.

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

- **INV-46** — Without `--depth`, a measure is judged at one depth
  only, and the references have it at one depth (amended by FLED-0020).
  A tested run with `gpu/blur` at depth 0 (2.000) in some frames and at
  depth 1 (5.000) in the others, since one frame cannot hold both:
  `--measure gpu/blur --bad-above 4.000` alone skips with 125, naming
  depths 0 and 1 and `--depth`, `skip_reason` `depth`; with `--depth 1`
  it exits 1, and with `--depth 0` it exits 0; with `--depth 2` it
  skips, `skip_reason` `missing`. References with `gpu/blur` at depth 0
  and a tested run with it at depth 1 only skip with 125, naming both;
  good runs at depth 0 and bad runs at depth 1 stop with 128. A tested
  run without `gpu/blur`, beside one at another depth, gives
  `skip_reason` `missing`. With `--bad-above` and no references, a
  tested run with `gpu/blur` at depth 1 only is judged at depth 1
  (UT Ants).
  *Test:* `tests/test_bisect.py::test_depth`,
  `tests/test_bisect.py::test_one_depth_across_runs`.
  *Breaks when:* one depth is picked silently, in one run or between
  runs; a tested run's depth stops the bisect; references at two depths
  are judged; or `--depth` is ignored.

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
  `fps`; `match` `inputs` of `"abc"`; a `limit_ms` or `depth` of
  5000 digits (Vestige); a header `schema` of 5000 digits (UT Ants); no budget line. A blank line between two budgets is skipped.
  *Test:* `tests/test_budget.py::test_bad_budget_files`.
  *Breaks when:* a bad line is skipped or read as a budget, a blank
  line stops the file, or a bad value crashes to exit 1.

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
  move at 2.000. Without the `view` line, it fails in view. A `view`
  line at depth 0 replaces a `*` line with an empty depth there. A pass
  at depths 0 and 1 in view only, with a `view` line at depth 1, leaves
  the `*` line judging move at depth 0, not exit 3. `view` lines at
  depths 0 and 1 both take view from a `*` line at either depth. A
  `view` line with an empty depth and one at depth 0, for a pass at
  depth 0, exit 3 naming both lines.
  *Test:* `tests/test_budget.py::test_named_kind_replaces_star`.
  *Breaks when:* the stricter line wins, both judge view, depths
  compare as written, or one named line's depth hides another's.

- **INV-63** — `--warmup-s` leaves out the frames `floor` leaves out.
  A run of 200 frames, each with a 10.000 ms `frame/wall`, has
  `gpu/x` at 5.000 ms in its first 20 frames and 1.000 ms after. A p99
  limit of 2.000 fails at the default, and holds at `--warmup-s 0.5`,
  with `warmup_s` 0.5. The same run with a hole at frame 100 is
  inconclusive at `--warmup-s 0.5`, and still fails at 0. With
  `gpu/x` at 5.000 ms from frame 150 on, it fails at 0.5. At
  `--warmup-s 3`, longer than the run, no frame is judged: the budget
  is unmatched, exit 2 (Vestige), in one sentence naming the warm-up,
  with none telling the reader to fix the budget file (UT Ants).
  *Test:* `tests/test_budget.py::test_warmup`.
  *Breaks when:* warm-up frames are judged, the default leaves any
  out, a hole is ignored above 0, or hides a breach.

- **INV-64** — A `frame`, `depth` or value's whole part of 20 digits
  is read; leading zeros count. At 21 digits, and at 5000, it is a
  breach naming the line and rule, quoting the field cut short: `check`
  exits 1 and `report` exits 3. A long `run_id`, `segment`, `category`
  or `name` that breaks its rule is quoted cut short too (DOOM Ants).
  *Test:* `tests/test_check.py::test_twenty_digits_are_read`,
  `tests/test_check.py::test_too_many_digits_is_a_breach`,
  `tests/test_check.py::test_a_long_field_is_quoted_short`,
  `tests/test_check.py::test_too_many_digits_stops_a_report`.
  *Breaks when:* a long number ends in a traceback, a legal one is a
  breach, or the message repeats the whole field.

- **INV-65** — A `mem` measure is judged by its own spread and floor,
  in MB. Every run has one `mem/gpu_mb` value in every frame, and frames
  otherwise alike. Old runs all 500.000. New runs all 515.000, exactly 3
  percent: `larger`, change 15.000, `unit` `MB`, exit 1. New runs all
  514.999: `unchanged`, exit 0. New runs all 485.000: `smaller`, exit 0.
  Old runs 500.000, 510.000 and 520.000, new runs 525.000, 530.000 and
  535.000: change equal to the spread, `noisy`, exit 0. Old runs all
  0.000, new runs all 5.000: `larger`, `change_pct` null, floor 1.000
  (DOOM Ants). One name at depths 0 and 1, in different frames, is two
  measures: only depth 1 growing gives depth 1 `larger` and depth 0
  `unchanged` (DOOM Ants).
  *Test:* `tests/test_compare_mem.py::test_mem_judged`,
  `tests/test_compare_mem.py::test_mem_each_depth_apart`.
  *Breaks when:* `mem` is not judged, a change at the floor is missed,
  a smaller or noisy `mem` measure fails or stops the compare, or a
  `mem` measure reads `slower`.

- **INV-66** — `--min-mb` is a `mem` measure's floor and nothing else's.
  Old runs all 10.000. New runs all 10.999: `unchanged`, under the
  default 1.000 floor. New runs all 11.000: `larger`. The same with
  `--min-mb 2`: `unchanged`. The same with `--min-ms 2`, or a
  `gpu_tick_ns` of 5000000: still `larger`. `--min-mb 5` leaves a
  `gpu/opaque` change of 1.000 ms `slower`. Old 10.000, new 11.000 with
  `--min-pct 20`: `unchanged`, the percent deciding (DOOM Ants).
  `--min-mb -1` exits 3.
  *Test:* `tests/test_compare_mem.py::test_mem_floor`.
  *Breaks when:* a floor in the other unit, or the GPU tick, decides a
  `mem` measure, or `--min-mb` decides a ms one.

- **INV-67** — Memory is reported in its own unit. With only a `mem`
  measure larger, the verdict sentence names it, in MB, with no "ms". With
  `gpu/opaque` 1.000 ms slower and `mem/gpu_mb` 20.000 MB larger, the
  verdict sentence names `gpu/opaque` and the next names `mem/gpu_mb`.
  Of two larger, the larger change in MB is named. `mem` ranks after
  `gpu` in `measures`, and the text puts it in a table headed in MB. A
  `mem` name in only some runs goes into `unmatched`, `unit` `MB`, and
  judges nothing, and the text lists it too. An `event` or `ext` row
  that moves judges nothing.
  *Test:* `tests/test_compare_mem.py::test_mem_sentences`,
  `tests/test_compare_mem.py::test_mem_unmatched_and_unjudged`.
  *Breaks when:* MB and ms are compared with each other, a `mem` figure
  is labelled ms, or an unjudged category is judged.
- **INV-68** — `pacing` is the change between neighbouring frames'
  walls, never across a break. Walls alternating 10.000 and 23.000 ms
  give a median and p99 change of 13.000; a steady 16.667 ms run gives
  0.000. With a 500 ms frame carrying `event/cut`, a hole, or a change
  from `view:1` to `view:2` among steady frames, the change stays
  0.000 and `pairs` falls by the pairs that break removes. A kind with
  no pair has no entry, and the text's `wall change (pairs)` row
  matches the JSON.
  *Test:* `tests/test_pacing.py::test_pacing_figure`,
  `tests/test_pacing.py::test_pacing_pairs`.
  *Breaks when:* a pair spans a cut, a hole or a segment change, or the
  figure is a spread of the walls rather than of their changes.
- **INV-69** — A survey flag is `floor`'s single-frame check. For each
  fixture in `tests/fixtures/` that `floor` reads, `survey FILE --fps 60`
  flags the run exactly when `floor FILE --fps 60 --no-windows` fails,
  with the same count over budget, and is inconclusive exactly when it
  is. `one-hitch.csv` is flagged with 1 frame over, and not flagged with
  `--allow-frames 1`. With `--warmup-s 0` a slow first frame flags a run
  that the default warm-up leaves clean.
  *Test:* `tests/test_survey.py::test_flag_is_floors`.
  *Breaks when:* the flag uses another frame set or statistic than
  `floor`'s frame check, so the two commands disagree on one file.
- **INV-70** — Runs rank by their worst eligible kind's p99. Of three
  runs given with `view` p99s of 20.000, 30.000 and 25.000 ms, the
  second ranks 1, the third 2 and the first 3, and `runs` lists them in
  that order (Vestige); a `load` kind of 50 frames at 90.000 ms in the first is listed
  with `ranked` false and changes nothing. With `view:1` at 18.000 and
  `view:2` at 30.000 ms, `worst_segment` is `view:2`. A run with no kind
  of 100 frames has `rank` null and comes last.
  *Test:* `tests/test_survey.py::test_rank`.
  *Breaks when:* a short kind sets a rank, the worst segment is not
  named, or the order is not the 99th percentile's.
- **INV-71** — A broken file never hides the others. With an empty
  file, a file with a breach, and two clean runs, the two are judged and
  ranked, the two broken ones are `unjudged` with their reasons, and the
  exit is 2. Add a flagged run and it is 1. With every run clean it is
  0.
  *Test:* `tests/test_survey.py::test_unjudged_files`.
  *Breaks when:* one broken file stops the survey, or a survey with an
  unjudged run exits 0.
- **INV-72** — A flag names the frame that set it. A run whose ranked
  `view` frames are all under the budget and whose 40-frame `load` kind
  holds one 80.000 ms frame is flagged, and `slowest_over` names that
  frame, its `load` segment and its top pass; the text names it too and
  says floor's per-second check was not run. The text table holds
  every run within 100 columns.
  *Test:* `tests/test_survey.py::test_flag_names_its_frame`.
  *Breaks when:* the flag points at the ranked kind instead of the
  frame, or the text omits that the window check was not run.
- **INV-73** — Each scene is judged as one compare. With scenes `a`
  and `b`, three runs a side each, given interleaved in one list, each
  scene's `compare` equals `compare --old` and `--new` over that
  scene's files alone, but for § 4.17's `baseline`, and `a`, its old runs all started before its
  new, carries `not_interleaved`. Scene `b`'s runs differ in `scene`
  from `a`'s and refuse nothing.
  *Test:* `tests/test_compare_scenes.py::test_scene_is_one_compare`.
  *Breaks when:* runs of two scenes are judged together, a scene's
  judging differs from `compare`'s, or `scene` refuses.
- **INV-74** — An unjudged scene never hides the others. With scene
  `a` clean at three a side, `b` with no new runs, `c` with two old
  runs, `d` whose new runs differ in `device`, and an empty file: `a`
  passes; `b`'s reason names the missing new side, `c`'s the old
  side's too few runs, `d`'s the `device` field; the file is unread;
  the exit is 2. Make `a` slower and it is 1.
  *Test:* `tests/test_compare_scenes.py::test_unjudged_scenes`.
  *Breaks when:* one unjudged scene or unread file stops the
  command, or a command with one exits 0.
- **INV-75** — No scene judged is an error. With scenes `b`, `c` and
  `d` of INV-74 alone, the exit is 3 and the first sentence after the
  overrides opens "No scene could be judged:" and names each reason. A
  set of only unread files is exit 3 too.
  *Test:* `tests/test_compare_scenes.py::test_nothing_judged`.
  *Breaks when:* a command that judged nothing exits 2 or 0.
- **INV-76** — A failing scene names its measure and segment, and
  failing scenes rank by change. Scene `a` whose `gpu/opaque` median
  rose 0.400 ms, and `b` whose rose 0.900 ms, rank `b` 1 and `a` 2.
  Within `b`'s `view` kind, `view:1` rose 0.100 ms and `view:2` 1.700
  ms, so `segment` is `view:2`. A scene with only a larger `mem`
  measure ranks after both.
  *Test:* `tests/test_compare_scenes.py::test_rank_and_segment`.
  *Breaks when:* scenes rank by another figure, a `mem`-only scene
  ranks among the slower ones, or the segment is not the one that
  changed most.
- **INV-77** — The count judged is given. In INV-74's fixture,
  `judged.scenes` is 1 and `judged.measures` equals the length of
  `a`'s `compare.measures`; the text gives both in its count sentence.
  *Test:* `tests/test_compare_scenes.py::test_judged_count`.
  *Breaks when:* unjudged scenes are counted, or the count is missing
  from the text.
- **INV-78** — Runs alternate, each into its own file, and are judged
  as `compare`. Fixture `alternate/fake_engine.py SIDE SOURCE LOG {run}`
  copies the run file `SOURCE` to its last argument and appends `SIDE`
  to the order log `LOG`. With `--runs 3`, the log reads old, new, new, old, old,
  new; `DIR` holds `old-1.csv` to `old-3.csv` and `new-1.csv` to
  `new-3.csv`; and the result, without `commands`, `out`, `warmup`
  and `stopped`, equals `compare --old` and `--new` over those files,
  with the same exit. With `--warmup 1` too, the log opens old, new
  before the same six, `DIR` also holds `old-warmup-1.csv` and
  `new-warmup-1.csv`, and the result still equals the compare of the
  six. Without `--json`, the text equals `compare`'s text over the
  same files, tables included.
  *Test:* `tests/test_alternate.py::test_alternates_and_compares`,
  `tests/test_alternate.py::test_text_is_compares`.
  *Breaks when:* all old runs go first, the order is plain
  alternation, two runs share a file, a warm-up is compared, the
  judging differs from `compare`'s, or the text stops at the opening
  sentences. The order log alone isolates the first two; the file
  list alone, the third.
- **INV-79** — A setup error runs nothing. Each alone gives exit 3 with
  an empty order log: a command without `{run}`; `--runs 2`;
  `--runs 101`; `--warmup 11`; a `DIR` that does not exist; a `DIR`
  holding a space; a `DIR` already holding `new-2.csv`, which is left
  byte for byte as it was; with `--warmup 1`, a `DIR` already holding
  `new-warmup-1.csv`. Each case's fixture is otherwise INV-78's.
  *Test:* `tests/test_alternate.py::test_setup_errors_run_nothing`.
  *Breaks when:* any check runs after the first command, or an
  existing run file is overwritten.
- **INV-80** — A failing run stops the rest, and only finished runs'
  files remain. INV-78's fixture, with new-2's command writing its
  file and then exiting 4: exit 3, the first sentence names new-2 and
  code 4, and without `--json` the text is that sentence and the
  command's alone; the order log ends at new-2, `stopped.finished` is old-1,
  new-1, their files remain, and `new-2.csv` is gone. With new-2's
  command exiting 0 and writing nothing, the reason names the missing
  path and `exit_code` is null. With `exec` before the command and
  new-2's engine killing itself with SIGKILL, the reason is "the
  command was killed by signal 9 (SIGKILL)" and `exit_code` is null.
  On Linux, with new-2's command `cd . && …` writing its file and
  then waiting: SIGINT to `alternate`'s whole process group, SIGINT to
  `alternate` alone, and SIGTERM to `alternate` alone each give exit
  3, `exit_code` null, the signal named in the reason,
  `stopped.finished` old-1, new-1, no `new-2.csv`, and the engine's
  process ended.
  With the shell still running after the engine (`…; exit $?`), the
  reason is "the command exited with code 137, as the shell reports a
  command killed by signal 9 (SIGKILL)" and `exit_code` is 137. On
  Linux, new-2's command exiting 0 with a child sleeping 30 seconds:
  the reason is "the command left processes running", and the child
  has ended; with a child sleeping 0.3 seconds, every run finishes. A SIGTERM delivered while new-2's command is being started
  still ends it.
  *Test:* `tests/test_alternate.py::test_failed_run_stops`,
  `tests/test_alternate.py::test_stopped_text_is_its_sentences`,
  `tests/test_alternate.py::test_killed_command_names_its_signal`,
  `tests/test_alternate.py::test_left_processes_fail_the_run`,
  `tests/test_alternate.py::test_brief_leftover_is_waited_for`,
  `tests/test_alternate.py::test_stop_while_starting`, and
  `tests/test_alternate.py::test_interrupted_run_stops`. Nothing here
  tests a process that survives SIGKILL.
  *Breaks when:* later runs start, the finished runs are compared,
  their files are removed, the failed run's file is kept, its text
  gains compare's body, a stop
  signal is not a stop, or the engine behind the shell outlives it.
  The compound command keeps the shell between `alternate` and the
  engine, so only a stop reaching the whole group ends the engine.
- **INV-81** — The engine's output never reaches standard output. With
  INV-78's fixture also printing `engine says hi` on its standard
  output, `alternate --json` prints one JSON object and nothing else on
  standard output, and `engine says hi` appears on standard error.
  *Test:* `tests/test_alternate.py::test_engine_output_to_stderr`.
  *Breaks when:* the command inherits standard output.
- **INV-82** — A `peak` is a number. A header whose `load` is
  `{"start": 0.1, "end": 0.2, "peak": 0.3}` passes `check`; with
  `"peak": "high"` it is a breach naming `load`, and likewise for
  `gpu_busy_pct`.
  *Test:* `tests/test_compare_load.py::test_peak_is_a_number`.
  *Breaks when:* a peak that is not a number passes, or a numeric one
  is refused. Only the `peak` key differs between the two headers.
- **INV-83** — A run taken under load makes a compare inconclusive.
  Fixture: three old and three new runs, the new `frame/wall` median
  2 ms slower in every run, so the compare alone fails, exit 1. Each
  case changes only new-2's header. `load.peak` 0.30: exit 2, the
  first sentence names new-2 and `load.peak`, and new-2's
  `under_load` is `["load.peak"]`. `load.peak` 0.25: exit 1. 0.30
  with `--max-load 0.5`: exit 1. `gpu_busy_pct.peak` 21: exit 2,
  `under_load` `["gpu_busy_pct.peak"]`. `load.start` 0.9 and no peak:
  exit 1. Peaks of 1 and 100 with `--max-load 1 --max-gpu-busy 100`:
  exit 1. `--max-load` -1, 1.01 or 25, or `--max-gpu-busy` 100.5,
  gives exit 3.
  *Test:* `tests/test_compare_load.py::test_under_load_inconclusive`, and
  `tests/test_compare_load.py::test_load_limit_bounds` for the bound.
  *Breaks when:* a peak at or below its limit, or a `start`, makes the
  run under load; the flag is ignored; or the slower-times verdict
  (exit 1) is given instead of inconclusive. The fixture fails without the load, so only this rule can
  turn exit 1 into 2.
- **INV-84** — Sides measured under different load or GPU clock are
  warned of, and the verdict is unchanged. Fixture: three old and
  three new runs with equal times, exit 0, no peaks. Old `load.start`
  0.05 in each: new 0.20 gives `load_differs`, new 0.15 gives none.
  Old `gpu_busy_pct.start` 2: new 13 gives `gpu_busy_differs`, 12
  none. Old `gpu_clock_mhz.end` 2000: new 1880 gives
  `gpu_clock_differs`, 1900 none; with new-1 lacking `gpu_clock_mhz`,
  none. Every case exits 0.
  *Test:* `tests/test_compare_load.py::test_side_differs_warnings`.
  *Breaks when:* a limit is crossed at or below it, a run lacking the
  field still warns, or a warning changes the exit.
- **INV-85** — `--measure` judges only the named measures. Fixture:
  three old and three new runs, 120 frames each; `gpu/a` 2 ms slower
  in every new run; `gpu/b` the same in all; `frame/wall` `noisy`
  and `cpu/c` in old-1 only. Without the flag: exit 1. `--measure
  gpu/b`: exit 0, every entry of `measures` is `gpu/b`, `unmatched`
  is empty, `named_measures` is `["gpu/b"]`, and the sentence after
  the overrides names it. `--measure gpu/a`: exit 1. `--measure
  frame/wall`: exit 2. `--measure cpu/c`: exit 2, `cpu/c` in
  `unmatched` and named in the summary. `--measure gpu/b --measure
  cpu/c`: exit 0, since a partly unmatched list still judges `gpu/b`.
  `--measure gpu/z`, `gpu/B`, `event/x`,
  `frame/fence_wait`, `gpu/`, or `gpu/b` twice: exit 3, naming it;
  for `gpu/z`, the JSON still gives `runs` and `named_measures`. In
  text, `--measure gpu/z --measure gpu/y`, plain or under
  `--by-scene`, prints only "No run has gpu/z or gpu/y, so they cannot
  be judged; a name matches exactly, case included." Under
  `--by-scene`, `named_measures` lists every name given, and with a
  scene of two old runs, never read, the sentence opens "No run read
  has". With a 10-frame kind, `--measure gpu/b` gives no sentence on
  kinds too short for step 3.
  Under `--by-scene`, with scene atrium's runs holding `gpu/w` and
  hall's not, `--measure gpu/w`: exit 0 when atrium's `gpu/w` is
  unchanged, exit 1 when 2 ms slower; hall is unjudged, and one scene
  is judged.
  *Test:* `tests/test_compare_measure.py::test_measure_keeps_named`,
  `tests/test_compare_measure.py::test_measure_refused`,
  `tests/test_compare_measure.py::test_absent_refusal_keeps_runs`,
  `tests/test_compare_measure.py::test_absent_text`,
  `tests/test_compare_measure.py::test_by_scene_leaves_out_scenes_without_named`,
  `tests/test_compare_measure.py::test_by_scene_absent_json_and_unread` and
  `tests/test_compare_measure.py::test_short_kind_sentence_needs_frame_wall`.
  *Breaks when:* an unnamed measure is judged or decides the verdict,
  `frame/wall` makes the compare inconclusive when not named, a name
  no run has gives a verdict, a compare judging nothing passes, or a
  scene with none of the names makes `--by-scene` inconclusive.
- **INV-86** — The per-run table gives each run's value. With INV-85's
  fixture and `--measure gpu/b --measure frame/wall`, the text has one
  row per run in run order, as § 4.10, each cell equal to the JSON's
  `old` or `new` value to three places. With twelve more passes named,
  one with a 64-byte name, in runs with a second segment kind whose
  name is 32 bytes, the columns spill into further tables. Each opens
  with the run column, a header is cut, and no table line is over 100
  characters. Without `--measure`, and under `--by-scene`, there is no
  such table.
  *Test:* `tests/test_compare_measure.py::test_per_run_table`.
  *Breaks when:* a run or a judged kept measure is missing, a cell
  differs from the JSON, a further table lacks the run column, or a
  table line is wider than 100.
- **INV-87** — Markdown says what the text says. Over every fixture's
  `check`, `report` and `floor` at 60, `--selftest`, a `bisect` of
  three good runs, and INV-85's `compare` with and without `--measure
  gpu/b --measure frame/wall`: the opening list's items, unescaped,
  equal the JSON `summary`, in order; each pipe table has the text
  table's rows, in order, under § 4.8's header for a list without one;
  the exit code is the text's. Every line of a table has the same
  length, a U+00A0 counting as one, so its pipes line up; a number
  column's separator ends `:`. With INV-86's twelve further passes,
  the per-run table is one table, with a line over 100 characters and
  the 64-byte name whole. A `floor` with 11 frames over budget lists
  10, and a `report` with 21 static facts lists 20; each then gives
  the text's line saying 1 more is in the JSON.
  *Test:* `tests/test_markdown.py::test_markdown_matches_text`,
  `tests/test_markdown.py::test_tables_line_up`,
  `tests/test_markdown.py::test_no_width_limit`,
  `tests/test_markdown.py::test_row_limits_stay`.
  *Breaks when:* Markdown is built from anything but the result; a row
  is dropped, added or reordered; a header is missing; a table is not
  padded or a number column not right-aligned; a table is cut or split
  at 100 columns; or a row limit is lost.
- **INV-88** — Engine text cannot break the Markdown. Fixture: a run
  whose static line holds ``"note": "a|b *c* _d_ <e> [f]g &amp; ~~i~~ `k` $x$ \\j"``,
  a fact `"lines": "a\nb\r\nc"`, a pass `shadow_map`, and a pass at
  depth 1. In `report --markdown`, the `lines` row's cells are `lines`
  and `a b c`, and the `note` row is exactly
  ``| note | a\|b \*c\* \_d\_ \<e> \[f\]g \&amp; \~\~i\~\~ \`k\` \$x\$ \\j |``
  padded to its column; `shadow_map` is unchanged; and the nested
  pass's cell opens with two U+00A0. A `check` of breaching files
  named `# a.csv`, `> b.csv`, `- c.csv`, `+ d.csv`, `1. e.csv` and
  `1) f.csv`, run from their folder, opens sentences `- \# a.csv`,
  `- \> b.csv`, `- \- c.csv`, `- \+ d.csv`, `- 1\. e.csv` and
  `- 1\) f.csv`; one named `100.0.csv` is unescaped, and one named
  `a` and `b.csv` with a line break between opens `- a b.csv`. One
  named ` - c.csv` opens `-`, a space, a no-break space, `- c.csv`;
  one named `    x.csv`, four no-break spaces before `x.csv`.
  `--markdown --json` is exit 3, and under `bisect` exit 128, its
  stop.
  *Test:* `tests/test_markdown.py::test_engine_text_is_escaped`,
  `tests/test_markdown.py::test_line_starts_are_escaped`,
  `tests/test_markdown.py::test_markdown_and_json_refused`.
  *Breaks when:* an escape is missing, so a cell splits, a value
  formats, a line break ends a row or item, or a sentence becomes a
  heading, quotation or list; the
  depth indent is stripped; or both flags are accepted.
- **INV-89** — Each variant is judged as one compare. With three base
  runs and variants `a` and `b` of three runs each, `b` slower in
  `gpu/x`, each variant's `compare` equals `compare --old` over the base
  files and `--new` over that variant's, but for § 4.17's `baseline`
  and for run names: `base-1` in place of `old-1`, `a-1` in place of
  `new-1`. `a` passes, `b` fails,
  and the exit is 1.
  *Test:* `tests/test_compare_variants.py::test_variant_is_one_compare`.
  *Breaks when:* two variants' runs are judged together, a variant's
  judging differs from `compare`'s, or the runs keep `old` and `new`
  names. Only `b`'s runs carry the slower `gpu/x`, so judging them
  with `a`'s moves `a`'s verdict.
- **INV-90** — A setup error reads nothing. Each alone gives exit 3,
  with INV-89's files otherwise: `--base` with `--old`; `--base` with
  `--by-scene`; `--base` without `--variant`; `--variant` without
  `--base`; the names `base`, `New`, `a-b`, `9a`, and one of 33
  letters; `a` given twice; a variant of two files; a base of two
  files.
  *Test:* `tests/test_compare_variants.py::test_setup_errors`.
  *Breaks when:* any of these reaches judging, or a name that is
  unsafe in a file name is accepted.
- **INV-91** — An unjudged variant never hides the others. With `a`
  clean and `b`'s runs differing from the base in `device`: `a`
  passes, `b` is unjudged and its reason names `device`, and the exit
  is 2. Make `a` slower and it is 1. With `b` alone, the exit is 3 and
  the first sentence after the overrides opens "No variant could be
  judged:" and names `device`.
  With the base and `a` lacking `gpu/x`, `b` refused and holding it,
  and `--measure gpu/x --measure cpu/sim`: the exit is 2, `a` passing
  on `cpu/sim`, since a run has `gpu/x` (DOOM Ants). Under `compare` a
  variant file that breaks the format is exit 3. One inconclusive
  variant makes the exit 2. With every variant lacking the named
  measure the base has, the exit is 3.
  *Test:* `tests/test_compare_variants.py::test_refused_variant`,
  `tests/test_compare_variants.py::test_named_measure_only_a_refused_variant_has`,
  `tests/test_compare_variants.py::test_compare_bad_variant_file`,
  `tests/test_compare_variants.py::test_inconclusive_variant`,
  `tests/test_compare_variants.py::test_every_variant_lacks_the_named_measure`.
  *Breaks when:* one refused variant stops the command, a command with
  one exits 0, or a command that judged nothing exits 2; or a refused
  variant's runs are not looked at for a named measure, so step 2
  refuses a name a run has.
- **INV-92** — Variants rank by the rank measure's change, lowest
  first. Base runs with 300 `view` frames and 20 `load` frames;
  variant `a`'s `frame/wall` median in `view` falls 1.200 ms, `b`'s
  0.300 ms, and `c`'s rises 0.500 ms, while in `load` `b`'s falls most.
  `rank_measure` is `frame/wall` median in `view`; `a` ranks 1, `b` 2,
  `c` 3, and `variants` lists them so. With `--measure gpu/x`, where
  `c`'s `gpu/x` falls most, `c` ranks 1. A variant `d` refused on
  `device` has `rank` null and comes last. Under `--measure gpu/x`, a
  variant `e` whose runs lack `gpu/x`, which every base run has, is
  unjudged with "none of its runs has a named measure", has `rank`
  null, and leaves the exit as it is without `e` (Vestige).
  With `gpu/x` at depth 0 in `view:1` and at depth 1 in the longer
  `view:2`, `a` saving most at depth 0 and `b` at depth 1:
  `rank_measure.depth` is 0 and `a` ranks 1. With it at depth 0 in 20
  `load` frames and at depth 1 in 300 `view` frames, the kind is
  `load`; with as many `load` frames as `view`, also `load` (UT Ants).
  Two variants with the same change rank by name. With `gpu/x` in two
  of three base runs, the text says "Nothing is ranked: not every base
  run has the gpu/x median in view." (Vestige).
  *Test:* `tests/test_compare_variants.py::test_rank`,
  `tests/test_compare_variants.py::test_rank_measure_is_the_top_level_pass`,
  `tests/test_compare_variants.py::test_rank_measure_kind_is_chosen_at_that_depth`,
  `tests/test_compare_variants.py::test_rank_ties_go_by_name`,
  `tests/test_compare_variants.py::test_rank_measure_in_some_base_runs`.
  *Breaks when:* variants rank by another kind, by verdict, by size of
  change rather than its sign, or ignore `--measure`; or a variant
  lacking a named measure the base has is judged inconclusive or
  counted in step 4. The `load` kind isolates the kind choice; `c`,
  both slowest and failing, isolates the sign; `e` isolates "its own
  runs". Or the rank measure takes the deepest depth, or a tie between
  kinds goes to the later one as text.
- **INV-93** — The count judged is given, and base warnings once. In
  INV-91's fixture with a base run carrying a § 4.9 warning,
  `judged.variants` is 1 and `judged.measures` equals the length of
  `a`'s `compare.measures`; the text gives both in its count sentence,
  and the base run's warning appears once. With base runs of two
  commits and variants `a` and `b`, `b`'s runs of two commits too,
  `mixed_build` is given twice: "the base runs differ…" and "b: the b
  runs differ…" (UT Ants, DOOM Ants). `override_unused` is given once
  when the field differs in no variant, and not when it differs in one.
  A variant's run with `load.peak` 0.9 is named with its peak, and a
  base run so loaded once, before it. A variant left out for lacking
  the named measure keeps its run's `settling_short` (Vestige).
  *Test:* `tests/test_compare_variants.py::test_judged_count`,
  `tests/test_compare_variants.py::test_run_under_load_is_named`,
  `tests/test_compare_variants.py::test_left_out_variant_keeps_its_warnings`,
  `tests/test_compare_variants.py::test_set_warnings_name_the_sides`,
  `tests/test_compare_variants.py::test_override_unused_is_said_once`.
  *Breaks when:* unjudged variants are counted, the count is missing
  from the text, or a warning about the base alone repeats per
  variant; or a variant is inconclusive for load and no sentence names
  the run.
- **INV-94** — `alternate` runs every side in reversing rounds, and
  judges as `compare`. INV-78's fixture with `--base` and variants `a`
  and `b`, `--runs 3`: the log reads base, a, b, b, a, base, base, a,
  b; `DIR` holds `base-1.csv` to `base-3.csv`, `a-1.csv` to `a-3.csv`
  and `b-1.csv` to `b-3.csv`; and the result, without `commands`,
  `out`, `warmup` and `stopped`, equals `compare --base` and
  `--variant` over those files, with the same exit. With `--warmup 1`
  the log opens base, a, b. With `--old` and `--base` both, or a
  variant command without `{run}`, the exit is 3 and the log is empty.
  With `b-2.csv` written empty, every run still runs, `b` is unjudged
  with a reason naming `b-2`, `a` is judged, and the exit is 2 when
  `a` passes; with
  `base-2.csv` empty instead, the exit is 3 (DOOM Ants).
  *Test:* `tests/test_compare_variants.py::test_alternate_variants`,
  and beside it `test_alternate_variants_warm_up_in_order`,
  `test_alternate_variants_setup_errors` and
  `test_alternate_variants_bad_file`.
  *Breaks when:* the rounds do not reverse, a side's runs share a
  file, the judging differs from `compare`'s, a setup error runs a
  command, or one bad variant file loses the other variants. The
  order log alone isolates the first.
- **INV-95** — On Windows a stop ends the engine behind `cmd.exe`.
  INV-80's interrupted fixture, `cd . && ` before each command so
  `cmd.exe` stays between the analyser and the engine, with the
  analyser in its own console process group and sent Ctrl-Break during
  new-2: exit 3, the reason names SIGBREAK, `stopped.finished` is
  old-1, new-1, only their files remain, and the engine has ended. It
  holds for an engine that ends on Ctrl-Break, and for one that ignores
  it, which only `taskkill /T /F` ends. The first makes `alternate`
  exit in under the 10 seconds a stopped command is given, so the
  Ctrl-Break passed on ended it, not the kill; the second takes at
  least those 10 seconds (DOOM Ants), and under 30, well before the
  fixture's engine would end by itself. Neither reason says a group
  did not end (Vestige).
  On any system, the Windows branch called directly with a stand-in
  `cmd.exe` sends Ctrl-Break for a SIGINT or SIGTERM stop and taskkill
  only for the kill; with no console, a stop sends nothing and raises
  nothing. With SIGKILL absent, as on Windows, the kill is none of the
  stop signals (UT Ants).
  *Test:* `tests/test_alternate.py::test_windows_stop_ends_the_tree`,
  run on Windows only; `tests/test_alternate.py::test_windows_stop_is_never_a_kill`,
  `tests/test_alternate.py::test_windows_kill_is_no_stop_signal`.
  *Breaks when:* the stop is not passed on, so the engine that ends
  on Ctrl-Break lasts until the kill; or the kill ends `cmd.exe`
  alone, so the engine that ignores Ctrl-Break outlives `alternate`.
  Or a SIGTERM stop kills at once, or a stop with no console crashes.
  A command that shares the analyser's group fails the test and ends
  the test run with it: on Vestige's Windows 10 box the Ctrl-Break
  passed on then reached pytest itself.

- **INV-96** — The header names its release. `FLED_VERSION` in
  `include/frameledger.h` is one string literal, equal to `VERSION` in
  `src/frameledger/cli.py`, which `--version` prints. The release bump
  changes both (`.claude/bump.json`).
  *Test:* `tests/test_release.py::test_header_names_the_release`.
  *Breaks when:* a release bumps the analyser's version and leaves the
  header's, so a copied header names an older release; or the macro is
  removed or defined twice.

- **INV-97** — Spaces after a `# frameledger` line's closing brace are
  ignored. `schema-1.csv` with 200 spaces added to its header and close
  lines, its lines ending in LF and again in CRLF: `check` exits 0 with no breach and no warning, and the header
  and close read are those of the file unpadded.
  *Test:* `tests/test_check.py::test_header_may_be_padded`.
  *Breaks when:* the reader refuses, or warns on, a header line that
  ends in spaces, so a header rewritten in place at a fixed length
  stops reading.

- **INV-98** — A baseline's runs are the old runs. With three old runs
  and three new, the new `gpu/opaque` 1 ms slower, and a baseline file
  beside the old runs naming them by relative path: `compare
  --baseline` run from another directory gives the result, summary and
  exit code of `compare --old` over the same files in the baseline's
  order, old-2 listed first, but for `baseline` and the baseline
  sentence; the sets' starts interleave, so no warning differs. A path written with `\`, a path with spaces around it, a
  blank line, a comment line, an indented comment line and a line 1
  with a second key are all read, and so is the file saved with a
  byte-order mark and CRLF. With an `--override`, the baseline
  sentence follows the overrides sentence. It comes first when the new
  runs' `device` refuses the compare, and when a listed run breaks the
  format. With `--by-scene`, and with
  `--variant` in place of `--new`, the same holds against `--old
  --by-scene` and against `--base`.
  *Test:* `tests/test_baseline.py::test_baseline_is_the_old_runs`, and
  beside it `test_by_scene_and_variants`.
  *Breaks when:* a path resolves from the current directory, the
  listed order is not the runs' order, or a baseline is judged by any
  rule `--old` is not.

- **INV-99** — A bad baseline reads no run and starts no command. Each
  alone gives exit 3: an empty file; a line 1 without the keyword; a
  line 1 whose JSON is broken; `schema` 2; a line that is not UTF-8;
  two runs listed; one file listed twice, once as `a.csv` and once as
  `./a.csv`, the sentence naming both lines; a file and a hard link to
  it; a file and a symbolic link to it; `\a.csv`, `C:\runs\a.csv` and
  `runs/C:a.csv`, none absolute on both Linux and Windows; a listed
  path that is a folder; a line 1 of
  200,000 nested brackets; `--baseline`, `--variant` and `--new`
  together, the sentence naming no `--base`; a listed
  path that does not exist, the sentence naming the path and its line; a baseline
  file that does not exist; `--baseline` with `--old`; with `--base`;
  with neither `--new` nor `--variant`. `bisect --baseline` is exit
  128.
  *Test:* `tests/test_baseline.py::test_bad_baseline_files`, and beside
  it `test_flag_setup_errors` and `test_smallest_set_is_compares`.
  *Breaks when:* a bad line is skipped or read as a path, a missing
  run file surfaces as a compare result, or a comment is read as a
  path. The new runs in the fixture are broken files, so reading any
  of them changes the sentence.

- **INV-100** — A baseline's warnings name what it is. Baseline runs
  of commit `abc123` started 2026-10-17 and new runs started
  2026-10-26: the compare warns `baseline_not_interleaved`, its
  message holding "commit abc123", "started 2026-10-17 (UTC)" and
  "9 days",
  and does not warn `not_interleaved`; the verdict and exit code are
  those of `--old`. Started 5 hours before, it says "5 hours"; 40
  minutes before, "40 minutes"; a day and a minute before, "1 day";
  under a minute before, "less than a minute"; with one baseline run `dirty`,
  "abc123 (dirty)". New runs that all started before the baseline's
  warn `not_interleaved` and not `baseline_not_interleaved`. A baseline
  whose newest run started with the first new run gives neither. A new
  `driver` warns `baseline_driver_differs`, naming both values; a new
  `os` warns `baseline_os_differs`, and not when one run has no `os`.
  The same sets under `--old` give none of the three codes.
  *Test:* `tests/test_baseline.py::test_baseline_warnings`.
  *Breaks when:* a baseline compare warns as a plain one, the age is
  measured from any run but the oldest, a warning changes the verdict,
  or a plain compare gains a baseline warning.

- **INV-101** — `alternate` with a baseline runs only the new side.
  INV-78's fixture with `--baseline` naming three kept old runs,
  `--runs 3 --warmup 1`: the log reads new four times; `DIR` holds
  `new-1.csv` to `new-3.csv` and `new-warmup-1.csv` and no `old` file;
  `commands` has `new` alone; and the result, without `commands`,
  `out`, `warmup` and `stopped`, equals `compare --baseline` over
  those files, with the same exit. With `--variant a` and `--variant
  b` the log reads a, b, b, a, a, b. With a baseline naming a missing
  file, or with `--old` beside `--baseline`, the exit is 3 and the log
  is empty.
  *Test:* `tests/test_baseline.py::test_alternate_baseline`, and beside
  it `test_alternate_baseline_variants` and
  `test_alternate_bad_baseline_runs_nothing`.
  *Breaks when:* the old command is asked for or run, the judging
  differs from `compare --baseline`'s, or a bad baseline is found only
  after the new runs have been paid for.

- **INV-102** — `started_utc` names a real date and time.
  `schema-1.csv` with its `started_utc` set to each of month 13,
  month 00, day 00, 30 February, 29 February 2025, hour 24, minute 60,
  second 60, year 0000, and 21 and 5000 fraction digits: `check` exits 1 with one `header` breach on
  line 1 naming `started_utc`; `compare` with that run among its old
  runs, and again among its new, exits 3; and so does `report`. With
  29 February 2024, year 0001, the last second of year 9999, and 20
  fraction digits, `check` exits 0 with no breach.
  *Test:* `tests/test_check.py::test_started_utc_is_a_real_time`, and
  beside it `test_real_started_utc_is_read`.
  *Breaks when:* `check` tests only the digits' shape, so a date that
  does not exist reaches `compare` and ends it in a traceback with
  exit 1, the code for a regression; a real date is refused; or the
  fraction's length is left to Python's own limit on digits, which
  moves with its settings (DOOM Ants).

- **INV-103** — `passing-run.csv` with `sanitizers` set to `"address"`
  and `"undefined"` gives `sanitizer_build` alone under `report` and
  `floor`, quoting both names, with the same verdict and exit code.
  With `[]` it gives no § 4.9 warning. With `build_type` `"Debug"` and
  `sanitizers` holding `"thread"` it gives `debug_build` then
  `sanitizer_build`. A name of 5000 characters is quoted cut short,
  in a message under 200 characters. `check` gives no warning for the
  field, and exits
  1 with one `header` breach when `sanitizers` is a string, or a list
  holding a number, an empty string or one of two spaces.
  *Test:* `tests/test_trust.py::test_sanitizer_build`, and
  `tests/test_check.py::test_header_breaches`.
  *Breaks when:* a Release build with a sanitizer gives no warning, an
  empty list warns, or a list that is not all strings is read, or an
  empty name is, which warns of a sanitizer it cannot name (Vestige).

- **INV-104** — Each machine-state field is read in its § 4.2 shape and
  refused in another: `check` exits 0 on `cpu_governor`
  `"powersave/balance_performance"`, `turbo` false, `power`
  `"battery"`, a `cpu_clock_mhz` with `start` and `end`, a `cpu_temp_c`
  with a `peak`, a `gpu_temp_c` without one, and `throttled` true; and
  exits 1 with one `header` breach naming the field on `cpu_governor`
  1, `turbo` `"on"`, `power` `"ac"`, a `cpu_clock_mhz` with no `end`, a
  `cpu_temp_c` whose `peak` is `"hot"`, `gpu_temp_c` 55 and `throttled`
  `"no"`. A `gpu_clock_mhz.end` of 1 followed by 400 zeros, a whole
  number too large for a float, is one `header` breach too.
  *Test:* `tests/test_machine_state.py::test_field_shapes`, and
  `tests/test_check.py::test_header_breaches`.
  *Breaks when:* a field is read in any shape, so a later command meets
  a value it cannot compare, or a huge whole number ends `check` in a
  traceback (DOOM Ants).

- **INV-105** — `passing-run.csv` with `power` `"battery"` gives
  `on_battery` under `report` and `floor`, with `throttled` true gives
  `throttled`, and with both gives both in that order, each with the
  same verdict and exit code. `power` `"mains"` with `throttled` false
  gives no § 4.9 warning, and nor do a governor, a turbo flag, a CPU
  clock and both temperatures together. `check` gives none.
  *Test:* `tests/test_machine_state.py::test_battery_and_throttled_runs`.
  *Breaks when:* a battery or throttled run goes unnamed, `throttled`
  false warns, or a governor or temperature warns on one run alone.

- **INV-106** — Three old runs and three new, alike but for one header
  field: `cpu_governor` `"performance"` against `"powersave"` gives
  `governor_differs`, `turbo` true against false `turbo_differs`,
  `power` `"mains"` against `"battery"` `power_differs`, and
  `sanitizers` `[]` against `["address", "undefined"]`
  `sanitizers_differs`, each alone among the difference warnings,
  quoting both values, with exit 0. One new run differing is enough.
  The same value on both sides, the same mix on both sides, or a new
  run lacking the field, gives none. A governor of 5000 characters is
  quoted cut short, in a message under 200 characters. `sanitizers`
  holding `"address"` then `"undefined"` against the two in the other
  order gives none; two governors of 31 characters differing in the
  last give `governor_differs`.
  *Test:* `tests/test_machine_state.py::test_side_values_differ`, and
  beside it `test_side_values_are_shown_short` and
  `test_side_values_are_compared_whole`.
  *Breaks when:* a differing setting goes unnamed, a run lacking the
  field reads as differing, sides holding the same mix warn, the cut
  text is what is compared (Vestige), or the warning changes the exit.

- **INV-107** — With old `cpu_clock_mhz.end` 3000, new 2840 gives
  `cpu_clock_differs` and 2850 none; -3000 on both sides gives none.
  With old `cpu_temp_c.end` 60 and
  no `peak`, new 71 gives `cpu_temp_differs` naming `cpu_temp_c.end`
  and 70 none. With a `peak` in every run, old 65, a new `peak` of 76
  with the same `end` warns naming `cpu_temp_c.peak`, and a new `peak`
  of 75 with an `end` of 71 gives none. With a `peak` in only two new
  runs, of 76, and every `end` 60, there is none. The same holds for
  `gpu_temp_c` and `gpu_temp_differs`. A new run lacking the field
  gives none. Every case exits 0.
  *Test:* `tests/test_machine_state.py::test_cpu_clock_differs`, and
  beside it `test_temperature_differs`.
  *Breaks when:* a limit is crossed at or below it, `end` is judged
  though every run has a `peak`, a `peak` is judged that some run
  lacks, a clock below zero differs from itself (DOOM Ants), or a
  warning changes the exit.

- **INV-108** — `survey`'s table names a shared directory once. Over
  `runs/a.csv`, `runs/b.csv` and `runs/deep/c.csv`, the text and the
  Markdown heading read "Runs, slowest first, each file in runs/:" and
  the rows show `a.csv`, `b.csv` and `deep/c.csv`. Over `runs/a.csv`
  with `runs-old/d.csv`, with `e.csv`, or alone, or over `./e.csv`
  with `./runs/a.csv`, the heading is "Runs,
  slowest first:" and each row shows its path whole. `--json` gives
  `runs/a.csv` whole.
  *Test:* `tests/test_survey.py::test_table_names_a_shared_directory_once`.
  *Breaks when:* shared letters are taken for a shared directory, so
  `runs-old/d.csv` is shown as `-old/d.csv`; one file loses its
  directory; or `--json` loses it.

- **INV-109** — `compare` names a run that stands apart. With the
  runs' `frame/wall` medians 16.0, 16.0 and 16.2 ms old and 16.0, 16.1
  and 20.0 new, the one `outlier_run` warning reads "new-3 stands
  apart from the other new runs: its frame/wall median in view
  segments is 20.000 ms and theirs lie from 16.000 to 16.100 ms;
  re-run it", with exit 2. The old runs' range is under the floor, so
  old-3 is not named. New medians of 12.0, 16.0 and 16.1 name new-1.
  Old 16.0, 16.1 and 20.0 against new 16.0, 19.9 and 20.0 name old-3,
  then new-1. New medians of 16.0, 18.0 and 20.0, or of 16.0, 16.0,
  20.0 and 20.0, name none, with exit 2. Old 16.0, 16.1 and 16.2
  against new 26.0, 26.1 and 30.0 is `slower`, exit 1, and names none.
  A `noisy` `gpu/opaque` beside a steady `frame/wall` names none, with
  exit 0. Two runs alone, of 16.0 and 20.0, name neither; no command
  judges a set of two, so the test asks `_outlier_notice` itself.
  New medians of 16.0, 16.0 and 16.48, a range of exactly the floor,
  name new-3. Runs holding the same frames in `spot` and `view`
  segments name new-3 in `spot`, then in `view`. With base medians of
  16.0, 16.1 and 20.0 and two variants of 16.0, 16.05 and 16.1, the
  one `outlier_run` warning opens "base-3 stands apart from the other
  base runs", and one summary sentence says it.
  *Test:* `tests/test_compare.py::test_outlier_run`, and for the base
  run `tests/test_compare_variants.py::test_base_outlier_is_named_once`.
  *Breaks when:* a run is named where `frame/wall` is not `noisy`, or
  for another measure; a set narrower than the floor names one; a run
  is named when dropping it leaves half the range or more; the
  lowest run is never named; a set of two names its lower run
  (Vestige); a range at the floor names none; the text hides a second
  named run; or a base run is named once per variant (DOOM Ants).

- **INV-110** — Plain text shows what a terminal would obey. Under
  `report`, a `sanitizers` name holding a line break then "Warning:
  fake" gives one warning line, quoting it with `\n`; the same name
  with the typed characters `\` and `n` is quoted with `\\n`. Names
  holding U+001B, U+0000 and U+202E show `\x1b`, `\x00` and `\u202e`;
  a Cyrillic name prints as written. 5000 names give the first five
  and "and 4995 more", in a line under 200 characters; six give five
  and "and 1 more"; five give all five. A `renderer` of `llvmpipe`, a
  line break and 50000 more characters gives one line under 200.
  `--json`'s message holds the line break itself, and Markdown has
  the name on one line. Under `survey`, a directory holding a line
  break and U+001B is named in the heading with `\n` and `\x1b`, and
  no line opens "Warning: fake"; `--json` gives the paths exactly. A
  file named `C:\new.csv` is shown with one backslash. In Markdown a
  file named `my_runs*|.csv` has `*` and `|` escaped (Vestige). A
  missing file under that directory is named the same way.
  One character of each listed range is shown as an escape, and the
  joiners print as written. Each header field that may hold any
  string, and an undefined header key, holding a forged line, U+001B,
  a typed `\n` and 50000 characters, leaves every line of `report`,
  `check` and a `compare` under 700 characters with no line opening
  "Warning: fake". § 4.17's warnings quote a `driver` with a typed
  `\n` as `\\n`, and a long `driver` or `commit` with both its ends.
  A baseline file's line of that kind gives one line on standard
  error, under 700 characters, with no control character. So does a
  budget file's long field, and a long `scene` the budgets were not set
  for. Under `--by-scene`, a long scene name is cut in each sentence
  and whole in `--json`. In Markdown each listed character
  becomes a space, and a joiner prints as written.
  *Test:* `tests/test_plain_text.py::test_header_text_cannot_forge_or_flood_a_line`,
  and beside it `test_path_text_cannot_forge_a_line`,
  `test_each_kind_of_unprinted_character_is_shown`,
  `test_joining_characters_print_as_written`,
  `test_no_header_string_forges_or_floods`,
  `test_baseline_warnings_quote_header_strings`,
  `test_a_baseline_file_cannot_forge_or_flood_standard_error`,
  `test_a_budget_file_cannot_flood_a_line`,
  `test_a_scene_name_cannot_flood_a_sentence` and
  `test_markdown_makes_each_unprinted_character_a_space`.
  *Breaks when:* text from a run file or a path starts a line of its
  own, reaches the terminal as a control or direction character, or
  fills a line without limit; a typed `\n` reads as a line break in a
  header string; a Windows path is doubled; or `--json` loses the
  exact value.

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
- FLED-0022: INV-64.
- FLED-0018: INV-65 to INV-67.
- FLED-0011: INV-68.
- FLED-0020: INV-46 as amended.
- FLED-0012: INV-69 to INV-72.
- FLED-0013: INV-73 to INV-77.
- FLED-0029: INV-78 to INV-81.
- FLED-0030: INV-82 to INV-84.
- FLED-0031: INV-85 and INV-86.
- FLED-0032: INV-87 and INV-88.
- FLED-0034: INV-89 to INV-94.
- FLED-0063: INV-95.
- FLED-0067: INV-96.
- FLED-0068: INV-97.
- FLED-0035: INV-98 to INV-101.
- FLED-0070: INV-102.
- FLED-0016: INV-103.
- FLED-0055: INV-104 to INV-107.
- FLED-0025: INV-108.
- FLED-0053: INV-109.
- FLED-0071 and FLED-0073: INV-110.

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

- `survey`'s per-run `floor` window verdict, and its `ext.<engine>`
  per-effect table: not yet queued (the three engines, 2026-11-04).
- Warnings on a single run's timing finer than `gpu_tick_ns`;
  `compare` only raises its floor to it (§ 4.10). Not yet queued.
- Charts or HTML — deferred; not yet queued (discovery, *not yet*).
- `alternate`'s prepare command (none of the three engines needs
  one), a time limit per run (UT Ants: low priority), and
  `--by-scene`: not yet queued.
- Variants with `--by-scene`, each variant judged per scene: not yet
  queued (§ 4.16 refuses the pair).
- A `peak` in `report`'s or `floor`'s warnings: not yet queued. Only
  a compare acts on it (FLED-0030).

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
| INV-64 | `tests/test_check.py::test_twenty_digits_are_read`, `test_too_many_digits_is_a_breach`, `test_too_many_digits_stops_a_report`, `test_a_long_field_is_quoted_short` |
| INV-65 | `tests/test_compare_mem.py::test_mem_judged`, `test_mem_each_depth_apart` |
| INV-66 | `tests/test_compare_mem.py::test_mem_floor` |
| INV-67 | `tests/test_compare_mem.py::test_mem_sentences`, `test_mem_unmatched_and_unjudged` |
| INV-68 | `tests/test_pacing.py::test_pacing_figure`, `test_pacing_pairs` |
| INV-69 | `tests/test_survey.py::test_flag_is_floors` |
| INV-70 | `tests/test_survey.py::test_rank` |
| INV-71 | `tests/test_survey.py::test_unjudged_files` |
| INV-72 | `tests/test_survey.py::test_flag_names_its_frame` |
| INV-73 | `tests/test_compare_scenes.py::test_scene_is_one_compare` |
| INV-74 | `tests/test_compare_scenes.py::test_unjudged_scenes` |
| INV-75 | `tests/test_compare_scenes.py::test_nothing_judged` |
| INV-76 | `tests/test_compare_scenes.py::test_rank_and_segment` |
| INV-77 | `tests/test_compare_scenes.py::test_judged_count` |
| INV-78 | `tests/test_alternate.py::test_alternates_and_compares`, `tests/test_alternate.py::test_text_is_compares` |
| INV-79 | `tests/test_alternate.py::test_setup_errors_run_nothing` |
| INV-80 | `tests/test_alternate.py::test_failed_run_stops`, `tests/test_alternate.py::test_stopped_text_is_its_sentences`, `tests/test_alternate.py::test_killed_command_names_its_signal`, `tests/test_alternate.py::test_left_processes_fail_the_run`, `tests/test_alternate.py::test_brief_leftover_is_waited_for`, `tests/test_alternate.py::test_stop_while_starting`, `tests/test_alternate.py::test_interrupted_run_stops` |
| INV-81 | `tests/test_alternate.py::test_engine_output_to_stderr` |
| INV-82 | `tests/test_compare_load.py::test_peak_is_a_number` |
| INV-83 | `tests/test_compare_load.py::test_under_load_inconclusive`, `tests/test_compare_load.py::test_load_limit_bounds` |
| INV-84 | `tests/test_compare_load.py::test_side_differs_warnings` |
| INV-85 | `tests/test_compare_measure.py::test_measure_keeps_named`, `tests/test_compare_measure.py::test_measure_refused`, `tests/test_compare_measure.py::test_absent_refusal_keeps_runs`, `tests/test_compare_measure.py::test_absent_text`, `tests/test_compare_measure.py::test_by_scene_leaves_out_scenes_without_named`, `tests/test_compare_measure.py::test_by_scene_absent_json_and_unread`, `tests/test_compare_measure.py::test_short_kind_sentence_needs_frame_wall` |
| INV-86 | `tests/test_compare_measure.py::test_per_run_table` |
| INV-87 | `tests/test_markdown.py::test_markdown_matches_text`, `tests/test_markdown.py::test_tables_line_up`, `tests/test_markdown.py::test_no_width_limit`, `tests/test_markdown.py::test_row_limits_stay` |
| INV-88 | `tests/test_markdown.py::test_engine_text_is_escaped`, `tests/test_markdown.py::test_line_starts_are_escaped`, `tests/test_markdown.py::test_markdown_and_json_refused` |
| INV-89 | `tests/test_compare_variants.py::test_variant_is_one_compare` |
| INV-90 | `tests/test_compare_variants.py::test_setup_errors` |
| INV-91 | `tests/test_compare_variants.py::test_refused_variant`, `tests/test_compare_variants.py::test_named_measure_only_a_refused_variant_has`, `tests/test_compare_variants.py::test_compare_bad_variant_file`, `tests/test_compare_variants.py::test_inconclusive_variant`, `tests/test_compare_variants.py::test_every_variant_lacks_the_named_measure` |
| INV-92 | `tests/test_compare_variants.py::test_rank`, `tests/test_compare_variants.py::test_rank_measure_is_the_top_level_pass`, `tests/test_compare_variants.py::test_rank_measure_kind_is_chosen_at_that_depth`, `tests/test_compare_variants.py::test_rank_ties_go_by_name`, `tests/test_compare_variants.py::test_rank_measure_in_some_base_runs` |
| INV-93 | `tests/test_compare_variants.py::test_judged_count`, `tests/test_compare_variants.py::test_set_warnings_name_the_sides`, `tests/test_compare_variants.py::test_override_unused_is_said_once`, `tests/test_compare_variants.py::test_run_under_load_is_named`, `tests/test_compare_variants.py::test_left_out_variant_keeps_its_warnings` |
| INV-94 | `tests/test_compare_variants.py::test_alternate_variants`, `tests/test_compare_variants.py::test_alternate_variants_warm_up_in_order`, `tests/test_compare_variants.py::test_alternate_variants_setup_errors`, `tests/test_compare_variants.py::test_alternate_variants_bad_file` |
| INV-95 | `tests/test_alternate.py::test_windows_stop_ends_the_tree`, on Windows only; `tests/test_alternate.py::test_windows_stop_is_never_a_kill`, `tests/test_alternate.py::test_windows_kill_is_no_stop_signal` |
| INV-96 | `tests/test_release.py::test_header_names_the_release` |
| INV-97 | `tests/test_check.py::test_header_may_be_padded` |
| INV-98 | `tests/test_baseline.py::test_baseline_is_the_old_runs`, `tests/test_baseline.py::test_by_scene_and_variants` |
| INV-99 | `tests/test_baseline.py::test_bad_baseline_files`, `tests/test_baseline.py::test_flag_setup_errors`, `tests/test_baseline.py::test_smallest_set_is_compares` |
| INV-100 | `tests/test_baseline.py::test_baseline_warnings` |
| INV-101 | `tests/test_baseline.py::test_alternate_baseline`, `tests/test_baseline.py::test_alternate_baseline_variants`, `tests/test_baseline.py::test_alternate_bad_baseline_runs_nothing` |
| INV-102 | `tests/test_check.py::test_started_utc_is_a_real_time`, `tests/test_check.py::test_real_started_utc_is_read` |
| INV-103 | `tests/test_trust.py::test_sanitizer_build`, `tests/test_check.py::test_header_breaches` |
| INV-104 | `tests/test_machine_state.py::test_field_shapes`, `tests/test_check.py::test_header_breaches` |
| INV-105 | `tests/test_machine_state.py::test_battery_and_throttled_runs` |
| INV-106 | `tests/test_machine_state.py::test_side_values_differ`, `tests/test_machine_state.py::test_side_values_are_shown_short`, `tests/test_machine_state.py::test_side_values_are_compared_whole` |
| INV-107 | `tests/test_machine_state.py::test_cpu_clock_differs`, `tests/test_machine_state.py::test_temperature_differs` |
| INV-108 | `tests/test_survey.py::test_table_names_a_shared_directory_once` |
| INV-109 | `tests/test_compare.py::test_outlier_run`, `tests/test_compare_variants.py::test_base_outlier_is_named_once` |
| INV-110 | `tests/test_plain_text.py::test_header_text_cannot_forge_or_flood_a_line`, `tests/test_plain_text.py::test_path_text_cannot_forge_a_line`, `tests/test_plain_text.py::test_each_kind_of_unprinted_character_is_shown`, `tests/test_plain_text.py::test_joining_characters_print_as_written`, `tests/test_plain_text.py::test_no_header_string_forges_or_floods`, `tests/test_plain_text.py::test_baseline_warnings_quote_header_strings`, `tests/test_plain_text.py::test_a_baseline_file_cannot_forge_or_flood_standard_error`, `tests/test_plain_text.py::test_a_budget_file_cannot_flood_a_line`, `tests/test_plain_text.py::test_a_scene_name_cannot_flood_a_sentence`, `tests/test_plain_text.py::test_markdown_makes_each_unprinted_character_a_space` |
| 4.13, S19 speed | **`Partial:`** timed by hand on a generated million-row file before each release; nothing here |
| 4.6, MSVC | **`Partial:`** Vestige's and UT Ants' Windows builds, per pinned release; nothing here |
| 4.16, the variants table, a 32-character name shown whole | `tests/test_compare_variants.py::test_text_table`, `tests/test_compare_variants.py::test_markdown_table` |
| 4.8, tables within 100 columns | `tests/test_render.py::test_text_matches_json`, over `report`'s and `floor`'s text for every fixture |

## 11. Cross-doc impact

- `docs/design.md` — none; this spec is the format part it names.
- `README.md` — gains Install and Usage once FLED-0007 ships.
- `CHANGELOG.md` — each later amendment of this spec is a format change
  the release notes name (S6).

## 12. Cold-eyes loop log

Rows live in `../reviews/FLED-0001-run-file-format-loop-log.md`.
