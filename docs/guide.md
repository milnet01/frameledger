# The frameledger guide

> **Purpose — so that a newcomer gets from nothing to a first report,
> and can read what each command says.**

A game engine draws each frame in passes, such as shadows or
lighting. frameledger gives the engine one file format for how long
each frame and each pass took, the run file. Its analyser reads run
files and answers: where did the time go, did the run hold its frame
rate, did a new build get slower?

The [spec](specs/FLED-0001-run-file-format.md) is the contract: every
field, flag and exit code. This guide is the way in, and links to the
spec for the rest. Adding frameledger to an engine? Read the quick
start, then [Making run files](#making-run-files).

## Quick start

1. **Install the analyser.** It needs Python 3.10 or newer. From
   0.9.0 it is on PyPI:

   ```sh
   pipx install frameledger
   ```

   Before 0.9.0, for a release candidate, or on a machine without
   pipx, use the release zip. The README's
   [Install](../README.md#install) section has every way. An engine can
   also keep a release's `frameledger.pyz` in its own repository and
   run it by path, `python3 -I frameledger.pyz check run.csv`. Every
   `frameledger` command in this guide runs the same that way.

2. **Write a run file.** Save this as `run.csv`. It is a run of four
   frames, written by hand. [What a run file holds](#what-a-run-file-holds)
   explains each part.

   ```text
   # frameledger {"schema":1,"run_id":"first","engine":"my-engine","tool":{"name":"by-hand","version":"1"},"build_type":"release","commit":"abc1234","dirty":false,"device":"My GPU","renderer":"My GPU","driver":"1.0","api":"vulkan-1.3","resolution":[1920,1080],"render_scale":1.0,"vsync":false,"pipelined":false,"display":"onscreen","scene":"start-room","inputs":[],"started_utc":"2026-11-22T12:00:00Z"}
   run_id,segment,frame,category,name,depth,value
   first,view:1,0,frame,cpu_span,0,6.000
   first,view:1,0,frame,gpu_span,0,9.000
   first,view:1,0,frame,wall,0,16.700
   first,view:1,0,gpu,shadows,0,3.000
   first,view:1,0,gpu,lighting,0,4.500
   first,view:1,1,frame,cpu_span,0,6.200
   first,view:1,1,frame,gpu_span,0,9.100
   first,view:1,1,frame,wall,0,16.600
   first,view:1,1,gpu,shadows,0,3.100
   first,view:1,1,gpu,lighting,0,4.400
   first,view:1,2,frame,cpu_span,0,6.100
   first,view:1,2,frame,gpu_span,0,14.000
   first,view:1,2,frame,wall,0,33.400
   first,view:1,2,gpu,shadows,0,8.000
   first,view:1,2,gpu,lighting,0,4.600
   first,view:1,3,frame,cpu_span,0,6.000
   first,view:1,3,frame,gpu_span,0,9.000
   first,view:1,3,gpu,shadows,0,3.000
   first,view:1,3,gpu,lighting,0,4.500
   # frameledger-close {"rows_dropped":0,"frames":4}
   ```

3. **Check it:**

   ```text
   $ frameledger check run.csv
   run.csv, line 1: the header lists no inputs, so no compare can tell whether the same content was run.
   The file meets the run-file format.

   Warnings:
     run.csv, line 1: the header lists no inputs, so no compare can tell whether the same content was run (inputs_empty)
   ```

   The file meets the format, so `check` exits 0. It has one warning,
   given twice: first as a sentence, then in the list with its code,
   `inputs_empty`. A warning is not a breach. This one says the header
   names no content, [The header](#the-header) says why that matters.

4. **Report on it:**

   ```text
   $ frameledger report run.csv
   Warning: the header lists no inputs, so no compare can tell whether the same content was run.
   Warning: only 3 frames are measured, fewer than 100, so the 99th percentile is the slowest frame.
   The run has 4 frames, in view segments.
   In view segments the costliest pass is cpu/cpu_remainder: median 6.000 ms, 100.0% of CPU time.
   The run does not overlap CPU and GPU work (pipelined is false), so the CPU-bound and GPU-bound share does not apply.

   CPU passes in view segments, by time spent:
     pass                                                   median ms        p99 ms   share    frames
     cpu_remainder                                              6.000         6.200  100.0%         4

   GPU passes in view segments, by time spent:
     pass                                                   median ms        p99 ms   share    frames
     lighting                                                   4.500         4.600   43.8%         4
     shadows                                                    3.000         8.000   41.6%         4
     gpu_remainder                                              1.500         1.600   14.6%         4

   Frame times in view segments:
     measure                                                median ms        p99 ms            frames
     cpu_span                                                   6.000         6.200                 4
     gpu_span                                                   9.000        14.000                 4
     wall                                                      16.700        33.400                 3
     wall change (pairs)                                        0.100        16.800                 2

   Worst frames, longest first:
          frame  segment                              wall ms  top pass
              2  view:1                                33.400  gpu/shadows
              0  view:1                                16.700  cpu/cpu_remainder
              1  view:1                                16.600  cpu/cpu_remainder
   ```

   The run has 4 frames, but only 3 have a frame time: the last frame
   has no `wall` row, since nothing follows it. Frame 2 took twice as
   long as the others, and `shadows` is the pass that grew in it.
   [Reading a report](#reading-a-report) explains each term.

## What a run file holds

A run file is text, one run of an engine. Its lines, in order:

1. **The header**, `# frameledger` and one line of JSON: what was run,
   on what, and when.
2. **The static line**, `# frameledger-static`, optional: facts about
   the run that are not per frame.
3. **The column line**, `run_id,segment,frame,category,name,depth,value`.
4. **Rows**, one measurement each, in any order.
5. **The close line**, `# frameledger-close`, once the run ends. A file
   without it is an unfinished run: the engine crashed or was killed.

The spec's [§ 4.1](specs/FLED-0001-run-file-format.md#41-the-file)
to [§ 4.5](specs/FLED-0001-run-file-format.md#45-the-close-line) hold
every rule.

### The header

Every field in the quick start's header is required. The spec's
[§ 4.2](specs/FLED-0001-run-file-format.md#42-the-header) says what
each means, and lists the optional ones, absent meaning unknown. A few
need care:

- **`run_id`** is unique to the run, and every row repeats it.
- **`inputs`** lists the content the run loaded, each with a hash, such
  as `{"name":"start-room.map","hash":"sha256:<hex>","bytes":1024}`.
  `compare` uses it to tell whether two runs ran the same content.
  `[]` is legal: `check` warns, and two runs with `[]` are not known
  to match.
- **`dirty`** is true when the build had changes not yet committed.
  **`driver`** is the graphics driver's name and version. The spec
  leaves how to find them to the engine: for instance, `dirty` is
  whether `git status --porcelain` printed anything when the build
  was made.

`compare` will not judge two runs that differ in `resolution`,
`render_scale`, `tier`, `ray_tracing`, `build_type`, `inputs`,
`display`, `api`, `device`, `vsync` or `scene`. It exits 3 instead.
`--override FIELD=REASON` lets one such field differ, once per field.
`--by-scene` judges each scene apart, with at least three runs a side
for each.

### Rows

Each row is one number:

| Column | Holds |
|---|---|
| `segment` | the stretch of the run, as `<kind>:<id>`, such as `view:1`; or empty, for a frame in no segment |
| `frame` | the frame's number; a number skipped between two others is warned as `frame_missing` |
| `category` | `frame`, `cpu`, `gpu`, `mem`, `event`, or `ext.<engine>` |
| `name` | the pass or measure |
| `depth` | 0 for a top-level pass, 1 for a pass inside it, and so on |
| `value` | exactly three decimals: milliseconds for `frame`, `cpu` and `gpu`; megabytes for `mem`; a count for `event`; the engine's own unit for `ext.<engine>` |

A frame has up to three `frame` rows:

- **`cpu_span`**: the frame's CPU work, not counting waits on the GPU.
- **`gpu_span`**: the frame's GPU work. A frame whose GPU result never
  arrived has none.
- **`wall`**: real time from this frame's start to the next frame's
  start. The last frame has none. So a frame's `wall` can be written
  only once the next frame has started.

An engine typically reads a steady clock once, at the top of each
frame's loop: a frame's `wall` is the next reading minus its own. GPU
times come from timestamp queries around each pass, and arrive a
frame or more later. GPU timestamps count ticks: convert them to
milliseconds before writing. The header's optional `gpu_tick_ns`
records the tick's length.

A `cpu` or `gpu` row times one pass. The analyser adds
`cpu_remainder` and `gpu_remainder`, the span's time that no depth-0
pass accounts for. In the quick start, no `cpu` passes are timed, so
all 6 ms of CPU time is remainder.

### Segments

A segment is a stretch of the run, such as one camera view or one
walk between two points. Every report and compare judges each segment
kind apart: the kind is the part of `segment` before the colon. So
give loading, menus and cutscenes kinds of their own, such as
`load:1` or `menu:1`, and their frames do not mix with play.

A frame where the camera jumps or a level loads carries an
`event/cut` row, with value `1.000`, on the first frame of its new
segment. `floor` starts a new one-second window after it, so a load
is judged on its own frame time alone. A frame with an empty
`segment` is in no segment; a PresentMon import writes all its frames
that way.

### The static line and settling frames

The static line is one JSON object of facts about the run, such as
draw counts. Its shape is the engine's, with one rule: a statistic is
a JSON string of its exact digits, `"17436423623014656123"`, never a
JSON number. A top-level `summary` object holds the facts the text
report prints; without one, it prints the first 20 facts. The spec's
[§ 4.3](specs/FLED-0001-run-file-format.md#43-the-static-line) has
the rest.

A freshly loaded view draws slowly at first, while it fills caches.
The header's optional `settling_frames` says how many untimed frames
each segment needs before its first recorded frame. `settled_frames`
says the fewest the run drew. When it drew fewer than it needs, the
commands that judge a run, such as `report` and `floor`, warn
`settling_short`.

## Making run files

An engine makes run files one of three ways. All three give files
that every command reads the same. For `alternate` to run it, the
engine must also take its run file's path on its command line, such
as `--frame-log=PATH`; the flag's name is the engine's.

### From your own code

Any code that writes the lines above makes a run file. `frameledger
kit DIR` writes the files that prove such a writer, made from the spec
alone: the spec's
[§ 4.19](specs/FLED-0001-run-file-format.md#419-a-kit-proves-a-strangers-writer)
says how to use them.

### With the C header

`include/frameledger.h` is an optional writer for C and C++, in the
release zip. It formats rows into a buffer the engine owns, and does
no file I/O: the engine writes the bytes out when it chooses. It never
allocates, and never touches the locale, so a value is always written
with a `.`. The spec's
[§ 4.6](specs/FLED-0001-run-file-format.md#46-the-writer-includeframeledgerh)
is its contract.

What `fled_row` returns matters:

- **`FLED_OK`**: the row was written.
- **`FLED_DROPPED`**: the buffer was full. The row is lost, and counted
  in the close line's `rows_dropped`. A run with dropped rows cannot
  be trusted to be whole, so `floor`, `compare` and `budget` call it
  inconclusive and exit 2.
- **`FLED_BAD_ARG`**: the row breaks the format, such as a name with a
  space or a value too large, and nothing was written. It is a bug in
  the engine's call.

Wiring it into an engine:

- **Size the buffer.** The opening lines, plus `FLED_CLOSE_MAX`, plus
  N times `FLED_ROW_MAX`, always holds N rows. Rows are written at
  their true size, typically about 40 bytes, so a buffer holds many
  more.
- **Write it out as you go.** A long run cannot fit one buffer. Vestige
  writes the buffer out each time `fled_pending` reaches half of it;
  DOOM Ants writes it out every frame.
- **Use one thread.** The writer is not safe to share between threads.
  GPU times that arrive late on another thread must be handed back to
  the thread that writes rows.
- **Keep the copy in step.** `FLED_VERSION` in the header names the
  release it came from. Vendor it from a release tag, and update it
  with the analyser, whose `frameledger --version` should match.

#### In C

This program writes a run of 300 frames, with one slow frame, into one
buffer, then writes the buffer out:

```c
/* fake_engine.c: writes one run of 300 frames to the file named by its
   one argument. */
#include <stdio.h>
#include "frameledger.h"

/* Room for the opening lines and all 1500 rows at their largest, so no
   row can be dropped. */
static char buf[1 << 20];
static int failed;

/* Adds one row to view:1, and notes any row the writer refused or dropped. */
static void row(fled_writer *w, long long frame, const char *category, const char *name,
                double ms)
{
    if (fled_row(w, "view:1", frame, category, name, 0, ms) != FLED_OK)
        failed = 1;
}

int main(int argc, char **argv)
{
    const char *header =
        "{\"schema\":1,\"run_id\":\"c-run-1\",\"engine\":\"my-engine\","
        "\"tool\":{\"name\":\"my-engine\",\"version\":\"0.1\"},"
        "\"build_type\":\"release\",\"commit\":\"abc1234\",\"dirty\":false,"
        "\"device\":\"My GPU\",\"renderer\":\"My GPU\",\"driver\":\"1.0\","
        "\"api\":\"vulkan-1.3\",\"resolution\":[1920,1080],\"render_scale\":1.0,"
        "\"vsync\":false,\"pipelined\":false,\"display\":\"onscreen\","
        "\"scene\":\"start-room\",\"inputs\":[],"
        "\"started_utc\":\"2026-11-22T12:00:00Z\"}";
    fled_writer w;
    const char *bytes;
    size_t n;
    FILE *file;
    long long frame;

    if (argc != 2 || fled_open(&w, buf, sizeof buf, "c-run-1", header, NULL) != FLED_OK)
        return 1;
    for (frame = 0; frame < 300; frame++) {
        /* A real engine reads its timers here. Frame 200 is slow. */
        double shadows = frame == 200 ? 20.0 : 3.0;
        double lighting = 4.5;
        row(&w, frame, "frame", "cpu_span", 6.0);
        row(&w, frame, "frame", "gpu_span", shadows + lighting + 1.0);
        if (frame < 299) /* the last frame has no wall */
            row(&w, frame, "frame", "wall", frame == 200 ? 33.3 : 16.6);
        row(&w, frame, "gpu", "shadows", shadows);
        row(&w, frame, "gpu", "lighting", lighting);
    }
    fled_close(&w, 300);

    file = fopen(argv[1], "wb");
    if (file == NULL)
        return 1;
    n = fled_pending(&w, &bytes);
    fwrite(bytes, 1, n, file);
    fled_consume(&w, n);
    return fclose(file) == 0 && !failed ? 0 : 1;
}
```

Build and run it, with the header's folder on the include path. Here
the release zip is unpacked into `frameledger`, as the README's
[release zip](../README.md#the-release-zip) section does:

```text
$ cc -std=c99 -I frameledger/include fake_engine.c -o fake_engine -lm
$ ./fake_engine c-run.csv
$ frameledger check c-run.csv
c-run.csv, line 1: the header lists no inputs, so no compare can tell whether the same content was run.
The file meets the run-file format.

Warnings:
  c-run.csv, line 1: the header lists no inputs, so no compare can tell whether the same content was run (inputs_empty)
```

#### In C++

This one writes the buffer out after every frame, so the buffer does
not grow with the run. It also takes the scene's name from the command
line, so it escapes it for JSON with `fled_json_escape`:

```cpp
// fake_engine.cpp: writes one run to the file named by its first argument,
// for the scene its second argument names, emptying the buffer each frame.
#include <fstream>
#include <string>
#include "frameledger.h"

int main(int argc, char **argv)
{
    if (argc != 3)
        return 1;
    std::ofstream out(argv[1], std::ios::binary);

    // The scene's name comes from outside, so escape it for JSON. The
    // first call measures; the second writes, with room for the NUL.
    std::string scene(fled_json_escape(nullptr, 0, argv[2]) + 1, '\0');
    fled_json_escape(&scene[0], scene.size(), argv[2]);
    scene.resize(scene.size() - 1);

    std::string header =
        "{\"schema\":1,\"run_id\":\"cpp-run-1\",\"engine\":\"my-engine\","
        "\"tool\":{\"name\":\"my-engine\",\"version\":\"0.1\"},"
        "\"build_type\":\"release\",\"commit\":\"abc1234\",\"dirty\":false,"
        "\"device\":\"My GPU\",\"renderer\":\"My GPU\",\"driver\":\"1.0\","
        "\"api\":\"vulkan-1.3\",\"resolution\":[1920,1080],\"render_scale\":1.0,"
        "\"vsync\":false,\"pipelined\":false,\"display\":\"onscreen\","
        "\"scene\":\"" + scene + "\",\"inputs\":[],"
        "\"started_utc\":\"2026-11-22T12:00:00Z\"}";

    // Room for the opening lines and one frame's five rows at their
    // largest, since the buffer is emptied after every frame.
    static char buf[16 * 1024];
    fled_writer w;
    if (fled_open(&w, buf, sizeof buf, "cpp-run-1", header.c_str(), nullptr) != FLED_OK)
        return 1;

    bool failed = false;
    auto row = [&](long long frame, const char *category, const char *name, double ms) {
        if (fled_row(&w, "view:1", frame, category, name, 0, ms) != FLED_OK)
            failed = true;
    };
    // Writes out whatever the writer holds, and frees its space.
    auto flush = [&] {
        const char *bytes;
        size_t n = fled_pending(&w, &bytes);
        out.write(bytes, static_cast<std::streamsize>(n));
        fled_consume(&w, n);
    };

    for (long long frame = 0; frame < 300; frame++) {
        // A real engine reads its timers here.
        row(frame, "frame", "cpu_span", 6.0);
        row(frame, "frame", "gpu_span", 8.5);
        if (frame < 299) // the last frame has no wall
            row(frame, "frame", "wall", 16.6);
        row(frame, "gpu", "shadows", 3.0);
        row(frame, "gpu", "lighting", 4.5);
        flush();
    }
    fled_close(&w, 300);
    flush();
    return out.good() && !failed ? 0 : 1;
}
```

```text
$ c++ -std=c++17 -I frameledger/include fake_engine.cpp -o fake_engine_cpp
$ ./fake_engine_cpp cpp-run.csv 'start "room"'
$ grep -o '"scene":"[^,]*' cpp-run.csv
"scene":"start \"room\""
```

### From a PresentMon capture

PresentMon is a free Windows tool that times every frame a game
presents. An engine with no writer can still get frame times and
pacing from it, but no passes: PresentMon sees only whole frames. Here is a short capture, saved as `capture.csv`:

```text
Application,ProcessID,SwapChainAddress,PresentRuntime,SyncInterval,MsBetweenPresents,MsCPUBusy,MsGPUBusy,DisplayedTime,CPUStartDateTime
game.exe,4120,0x1A2B3C,DXGI,0,16.6,6.1,9.4,16.6,2026-11-22T12:00:00.000Z
game.exe,4120,0x1A2B3C,DXGI,0,16.6,6.2,9.5,16.6,2026-11-22T12:00:00.016Z
game.exe,4120,0x1A2B3C,DXGI,0,16.7,6.1,9.4,16.7,2026-11-22T12:00:00.033Z
game.exe,4120,0x1A2B3C,DXGI,0,16.6,6.0,9.3,16.6,2026-11-22T12:00:00.049Z
```

```text
$ frameledger import presentmon capture.csv -o imported.csv --commit abc1234 --resolution 1920x1080
Wrote 4 frames of game.exe (pid 4120, swap chain 0x1A2B3C) to imported.csv; 0 were not displayed.
The capture has no FrameType column, so every frame is read as the application's.
The header does not know its dirty, build_type, device, renderer, driver, render_scale, pipelined, display and scene; the fact flags can give them.
```

A capture knows nothing of the build, so the header holds a stand-in
for each fact it lacks, and `check` and every report say which. Flags
such as `--commit` and `--resolution` give them;
`frameledger import presentmon --help` lists them all. A capture
holding several programs is refused until `--process` or `--pid`
picks one. The spec's
[§ 4.18](specs/FLED-0001-run-file-format.md#418-importing-a-presentmon-capture)
holds the rest.

## Reading the answers

Every command opens with its warnings and a summary in sentences.
Then it gives the detail in tables. A warning never changes the exit
code. `--json` prints the result for a script to read, and
`--markdown` prints the text to paste into a pull request.

The exit codes:

| Command | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| `check` | every file meets the format | a file breaks it | | a file cannot be read |
| `report` | the report was written | | | an error |
| `floor` | the run held the frame rate | it did not | it cannot tell | an error |
| `compare`, `alternate` | nothing got slower or larger | a measure got slower or larger | it cannot tell | an error, or runs it will not compare |
| `budget` | every budget holds | a pass is over budget | it cannot tell | an error |
| `survey` | no run is flagged | a run is flagged | a run could not be judged | a bad flag |
| `import presentmon` | the run file was written | | | a refusal; nothing is written |

`bisect` uses `git bisect run`'s own codes instead: 0 good, 1 bad, 125
skip, 128 stop.

### Reading a check

`check FILE…` says whether each file meets the format. A breach names
the file and line.

### Reading a report

`report FILE` says where one run's frame time went. The quick start
shows one. Read it top down:

- **The opening sentences** give the warnings, the frame count, and
  the costliest pass. When the header's `pipelined` is true, they also
  give the share of frames that were GPU-bound, their `gpu_span`
  longer than their `cpu_span`, and the share that were CPU-bound.
- **The pass tables**, one for CPU and one for GPU, rank the passes by
  total time.
- **`median ms`** is a typical frame's cost.
- **`p99 ms`** is the 99th percentile: 99% of frames are at or under
  it. A pass with a small median and a large `p99 ms` spikes now and
  then, as `shadows` does in the quick start.
- **`share`** is the pass's part of its span's whole time.
- **The frame-times table** gives each `frame` row's median and 99th
  percentile. `wall change (pairs)` is how much `wall` changes from one
  frame to the next. A run can hold its frame rate and still judder;
  this row shows it.
- **Worst frames** lists the longest `wall` times, and names the
  costliest pass in each frame as its `top pass`.

Each table is per segment kind. `--html PAGE` also writes a web page
of the run as a graph, with its slowest frames marked; `--fps 60` draws
a 60 fps budget line on it.

### Reading a floor

`floor FILE --fps N` says whether a run held a frame rate. It makes
two checks, after a warm-up of 2 seconds by default (`--warmup-s`
changes it):

- **Windows:** in each one-second window, the frames' mean `wall` is
  within the budget of 1000/N ms.
- **Frames:** no single frame's `wall` is over that budget. A window's
  mean can hide one long frame among fast ones; this check catches it.

So `floor` needs a run of more than 3 seconds. The quick start's run
is too short, and `floor` exits 2 on it. The run the [C example](#in-c)
writes has one slow frame, so it fails both checks:

```text
$ frameledger floor c-run.csv --fps 60
Warning: the header lists no inputs, so no compare can tell whether the same content was run.
The run fails the 60 FPS floor: 1 one-second window fell below 60 FPS and 1 frame took longer than 16.667 ms (0 allowed).
Windows: 1 of 2 one-second windows after the 2 s warm-up held 60 FPS; the slowest, at 3.000 s, had 59 frames averaging 16.883 ms.
1 window shorter than one second, cut short by an event/cut or the end of the run, was skipped.
Frames: 1 of 179 after the warm-up took longer than the 16.667 ms budget; the longest was frame 200, 33.300 ms.

Windows below the frame rate:
     start s    frames     mean ms
       3.000        59      16.883

Frames over the budget, longest first:
       frame  segment                              wall ms  top pass
         200  view:1                                33.300  gpu/shadows
```

`--allow-frames K` lets K frames go over the budget. The spec's
[§ 4.7](specs/FLED-0001-run-file-format.md#47-the-010-commands) lists
the other flags.

## Comparing builds

`compare` says whether a new build's runs got slower than an old
build's, measure by measure.

### Runs fit to compare

A comparison is only as good as its runs:

- **Judge release builds with vsync off.** Vsync holds each frame to
  the display's rate, which hides a change.
- **Give each build at least three runs**, and run them in one sitting.
- **Run on a quiet machine.** A header can record how busy other
  programs kept the CPU and GPU during the run, as `load.peak` and
  `gpu_busy_pct.peak`. A run above `--max-load`, 0.25 of the CPU by
  default, or `--max-gpu-busy`, 20% of the GPU by default, was taken
  under load. `compare` then exits 2.

### An A/B

Run the two builds in turn: old, new, new, old, old, new. Running all
of one build first and then all of the other would let the machine's
drift over time, such as warming up, look like a change between
builds. `compare` warns `not_interleaved` when the runs' `started_utc`
times show that.

`alternate` runs both builds in that order, then compares them. Each
command holds `{run}`, which `alternate` replaces with that run's file,
such as `ab/old-1.csv`:

```sh
mkdir ab
frameledger alternate --old './old/engine --frame-log={run}' --new './new/engine --frame-log={run}' --out ab
```

`--out` names a folder that must already exist. `--runs N` sets the
runs a side, 5 by default. `--warmup W` first runs each build W times
untimed. To judge the same files again later:

```sh
frameledger compare --old ab/old-1.csv ab/old-2.csv ab/old-3.csv ab/old-4.csv ab/old-5.csv --new ab/new-1.csv ab/new-2.csv ab/new-3.csv ab/new-4.csv ab/new-5.csv
```

On Windows, stopping `alternate` reaches the engine as Ctrl-Break, not
Ctrl-C. An engine that closes its run file on Ctrl-C must handle
Ctrl-Break the same way, or a stopped run has no close line.

### Several variants against one base

To cost each effect, give the full frame as `--base` and the frame
with each effect off as a named `--variant`:

```sh
frameledger compare --base full1.csv full2.csv full3.csv --variant no_bloom nb1.csv nb2.csv nb3.csv --variant no_fog nf1.csv nf2.csv nf3.csv
frameledger alternate --base './engine --frame-log={run}' --variant no_bloom './engine --no-bloom --frame-log={run}' --out effects
```

Each variant is judged against the base as `compare` judges new
against old. The variants are ranked by how much frame time each
saved. A variant that cannot be judged does not stop the others.

`--measure`, given once per measure, judges only the measures named,
and adds a table of each run's value of each. The first one named
ranks the variants, in place of `frame/wall`. Name a measure every
variant has: with `--measure gpu/bloom`, `no_bloom` has no bloom pass,
so it is not judged.

Runs are named by the order their files are given: `base-1`,
`base-2`, and so on.

### A saved baseline

To check each new build against runs you kept, list the kept run
files in a baseline file, one path per line under a first line that
names the format:

```
# frameledger-baseline {"schema":1}
runs/meadow-1.csv
runs/meadow-2.csv
runs/meadow-3.csv
```

A relative path starts at the baseline file's own folder. Give the
file as `--baseline` in place of `--old`, or in place of `--base`:

```sh
frameledger compare --baseline perf/meadow.txt --new b1.csv b2.csv b3.csv
frameledger alternate --baseline perf/meadow.txt --new './new/engine --frame-log={run}' --out today
```

`alternate` then runs only the new build. The kept runs are judged as
any old runs are, so a baseline from another GPU or graphics API is
refused: a baseline belongs to one machine. Nothing alternates with a
baseline, so the machine may have drifted since it was taken: compare
warns `baseline_not_interleaved` and says how old the baseline is. It
also warns `baseline_driver_differs` or `baseline_os_differs` when the
driver or the system changed. An A/B in one sitting is the surer
check.

frameledger never writes the baseline file. To renew it, keep a
session's run files and list them. Renew it when those warnings
appear, or when you accept a build's new times as the normal.

### Reading a compare

For each measure, compare takes each build's median across its runs,
and judges the change against the spread. The spread is the larger of
the two builds' ranges, highest run minus lowest. Here the new build's
opaque pass got slower:

```text
$ frameledger compare --old a1.csv a2.csv a3.csv --new b1.csv b2.csv b3.csv
The new runs are slower: 4 measures got slower; the largest is gpu/opaque median in view segments, up 0.890 ms (+22.1%), beyond the runs' spread of 0.090 ms.
In view segments the median frame/wall went from 16.020 ms to 16.910 ms (slower).

Runs:
  old-1     a1.csv
  old-2     a2.csv
  old-3     a3.csv
  new-1     b1.csv
  new-2     b2.csv
  new-3     b3.csv

Measures that moved or are too noisy to judge, old and new as the runs' median:
  measure                                       old ms      new ms      change      spread  verdict
  view: frame/gpu_span                          12.020      12.910      +0.890       0.090  slower
  view: frame/wall                              16.020      16.910      +0.890       0.090  slower
  view: frame/wall p99                          16.020      16.910      +0.890       0.090  slower
  view: gpu/opaque                               4.020       4.910      +0.890       0.090  slower
4 of 8 measures unchanged.
```

These runs are an illustration; the guide does not give their files.

`view` is the segment kind these runs wrote. It judges frame times,
`cpu` and `gpu` passes, and `mem`. It does not judge `event` or
`ext.<engine>` rows.

The first line names the slower measure with the largest change in
ms. Here all four slower measures rose by the same 0.890 ms, so the
one with the largest change in percent is named: `gpu/opaque`, at
+22.1%.

It exits 1 here, because a measure got slower. Unchanged measures are
counted, not listed; `--json` lists every measure with its verdict.

## Checking every build

An engine's automatic checks can run frameledger on each build:

- **`floor FILE --fps N`** on one run says whether the build holds its
  frame rate.
- **`compare --baseline FILE --new …`** says whether it got slower than
  the runs you kept.

Fail the job on any exit but 0. Exit 2 means the run could not be
judged: dropped rows, a loaded machine, or runs too noisy. A job that
passes on 2 lets a bad run hide a regression, so treat 2 as a fail
and run again.

## The other commands

- `bisect` gives `git bisect run` a good, bad or skip verdict for one
  commit's runs
  ([§ 4.11](specs/FLED-0001-run-file-format.md#411-bisect-verdicts)).
- `budget` says whether any pass, or a frame's whole CPU or GPU span,
  went over its time budget
  ([§ 4.12](specs/FLED-0001-run-file-format.md#412-pass-budgets)).
- `survey` ranks many runs by their slowest frames
  ([§ 4.13](specs/FLED-0001-run-file-format.md#413-surveying-many-runs)).
- `frameledger schema COMMAND` prints the JSON Schema of that command's
  `--json` result, for a script that reads it.
