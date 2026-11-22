# The frameledger guide

> **Purpose — so that a newcomer gets from nothing to a first report,
> and can read what each command says.**

The [spec](specs/FLED-0001-run-file-format.md) is the contract: every
field, flag and exit code. This guide is the way in, and links to the
spec for the rest.

## Quick start

1. **Install the analyser.** With Python 3.10 or newer:

   ```sh
   pipx install frameledger
   ```

   The README's [Install](../README.md#install) section has the other
   ways, the release zip among them.

2. **Write a run file.** Save this as `run.csv`. It is a run of four
   frames, written by hand:

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

   It meets the format, and exits 0. The warning is about `inputs`,
   explained under [The header](#the-header).

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

   Frame 2 took twice as long as the others, and `shadows` is the pass
   that grew in it. [Reading a report](#reading-a-report) explains each
   part.

## What a run file holds

A run file is text, one run of an engine. Its lines, in order:

1. **The header**, `# frameledger` and one line of JSON: what was run,
   on what, and when.
2. **The static line**, `# frameledger-static`, optional: facts about
   the run that are not per frame, such as draw counts.
3. **The column line**, `run_id,segment,frame,category,name,depth,value`.
4. **Rows**, one measurement each, in any order.
5. **The close line**, `# frameledger-close`, once the run ends. A file
   without it is an unfinished run: the engine crashed or was killed.

The spec's [§ 4.1](specs/FLED-0001-run-file-format.md#41-the-file)
to [§ 4.5](specs/FLED-0001-run-file-format.md#45-the-close-line) hold
every rule.

### The header

Every field in the quick start's header is required; the spec's
[§ 4.2](specs/FLED-0001-run-file-format.md#42-the-header) says what
each means, and lists the optional ones. Two need care:

- **`inputs`** lists the content the run loaded, each with a hash, such
  as `{"name":"start-room.map","hash":"sha256:<hex>","bytes":1024}`.
  `compare` uses it to tell whether two runs ran the same content.
  `[]` is legal, and warned on.
- **`run_id`** is unique to the run, and every row repeats it.

`compare` will not judge two runs that differ in a field such as
`resolution`, `device` or `scene`, unless told to: the spec lists
them as the compare-blocking fields.

### Rows

Each row is one number:

| Column | Holds |
|---|---|
| `segment` | the stretch of the run, as `<kind>:<id>`, such as `view:1`; or empty |
| `frame` | the frame's number; a number skipped between two others is warned as `frame_missing` |
| `category` | `frame`, `cpu`, `gpu`, `mem`, `event`, or `ext.<engine>` |
| `name` | the pass or measure |
| `depth` | 0 for a top-level pass, 1 for a pass inside it, and so on |
| `value` | milliseconds for `frame`, `cpu` and `gpu`; megabytes for `mem`; exactly three decimals |

Every frame has three `frame` rows:

- **`cpu_span`**: the frame's CPU work, not counting waits on the GPU.
- **`gpu_span`**: the frame's GPU work. A frame whose GPU result never
  arrived has none.
- **`wall`**: real time from this frame's start to the next frame's
  start. The last frame has none.

A `cpu` or `gpu` row times one pass. The analyser adds
`cpu_remainder` and `gpu_remainder`, the span's time that no depth-0
pass accounts for. In the quick start, no `cpu` passes are timed, so
all 6 ms of CPU time is remainder.

## Making run files

An engine makes run files one of three ways. All three give files
that every command reads the same.

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

#### In C

This program writes a run of 300 frames, with one slow frame, into one
buffer, then writes the buffer out:

```c
/* fake_engine.c: writes one run of 300 frames to the file named first. */
#include <stdio.h>
#include "frameledger.h"

static char buf[1 << 20]; /* room for the whole run */

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
        /* A real engine reads its timers here. */
        double shadows = frame == 200 ? 20.0 : 3.0;
        double lighting = 4.5;
        fled_row(&w, "view:1", frame, "frame", "cpu_span", 0, 6.0);
        fled_row(&w, "view:1", frame, "frame", "gpu_span", 0, shadows + lighting + 1.0);
        if (frame < 299) /* the last frame has no wall */
            fled_row(&w, "view:1", frame, "frame", "wall", 0, frame == 200 ? 33.3 : 16.6);
        fled_row(&w, "view:1", frame, "gpu", "shadows", 0, shadows);
        fled_row(&w, "view:1", frame, "gpu", "lighting", 0, lighting);
    }
    fled_close(&w, 300);

    file = fopen(argv[1], "wb");
    if (file == NULL)
        return 1;
    n = fled_pending(&w, &bytes);
    fwrite(bytes, 1, n, file);
    fled_consume(&w, n);
    return fclose(file) == 0 ? 0 : 1;
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

This one empties a small buffer every frame, so the buffer does not
grow with the run. It also takes the scene's name from the command
line, so it escapes it for JSON with `fled_json_escape`:

```cpp
// fake_engine.cpp: writes one run, emptying a small buffer every frame.
#include <fstream>
#include <string>
#include "frameledger.h"

// Takes whatever the writer holds and writes it out.
static void flush(fled_writer &w, std::ofstream &out)
{
    const char *bytes;
    size_t n = fled_pending(&w, &bytes);
    out.write(bytes, static_cast<std::streamsize>(n));
    fled_consume(&w, n);
}

int main(int argc, char **argv)
{
    if (argc != 3)
        return 1;
    std::ofstream out(argv[1], std::ios::binary);

    // The scene name comes from outside, so escape it for JSON.
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

    static char buf[16 * 1024]; // the opening lines and a few frames
    fled_writer w;
    if (fled_open(&w, buf, sizeof buf, "cpp-run-1", header.c_str(), nullptr) != FLED_OK)
        return 1;
    for (long long frame = 0; frame < 300; frame++) {
        // A real engine reads its timers here.
        fled_row(&w, "view:1", frame, "frame", "cpu_span", 0, 6.0);
        fled_row(&w, "view:1", frame, "frame", "gpu_span", 0, 8.5);
        if (frame < 299) // the last frame has no wall
            fled_row(&w, "view:1", frame, "frame", "wall", 0, 16.6);
        fled_row(&w, "view:1", frame, "gpu", "shadows", 0, 3.0);
        fled_row(&w, "view:1", frame, "gpu", "lighting", 0, 4.5);
        flush(w, out);
    }
    fled_close(&w, 300);
    flush(w, out);
    return out.good() ? 0 : 1;
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
pacing from it:

```text
$ frameledger import presentmon capture.csv -o imported.csv
Wrote 300 frames of game.exe (pid 4120, swap chain 0x1A2B3C) to imported.csv; 0 were not displayed.
The capture has no FrameType column, so every frame is read as the application's.
The header does not know its commit, dirty, build_type, device, renderer, driver, resolution, render_scale, pipelined, display and scene; the fact flags can give them.
```

A capture knows nothing of the build, so the header holds a stand-in
for each fact it lacks, and `check` and every report say which. The
fact flags, such as `--commit` and `--resolution 1920x1080`, fill them
in; `frameledger import presentmon --help` lists them. A capture
holding several programs is refused until `--process` or `--pid`
picks one. The spec's
[§ 4.18](specs/FLED-0001-run-file-format.md#418-importing-a-presentmon-capture)
holds the rest.

## Reading the answers

Every command opens with its warnings and a summary in sentences,
then gives the detail in tables. Its exit code carries the verdict,
for a script. `--json` prints
the result for a script to read, and `--markdown` prints the text to
paste into a pull request.

### Reading a check

`check FILE…` says whether each file meets the format. It exits 0
when every file does, 1 when any breaks it, and 3 when one cannot be
read. A breach names the file and line. A warning, such as
`inputs_empty`, does not change the exit code.

### Reading a report

`report FILE` says where one run's frame time went. The quick start
shows one. Read it top down:

- **The opening sentences** give the warnings, the frame count, and
  the costliest pass. When the header's `pipelined` is true, they also
  give the share of frames that were GPU-bound, their `gpu_span`
  longer than their `cpu_span`, and the share that were CPU-bound.
- **The pass tables**, one for CPU and one for GPU, rank the passes by
  total time. `median ms` is a typical frame's cost; `p99 ms` is the
  99th percentile, which 99% of frames are at or under. `share` is the pass's part of its span's whole
  time. A pass with a small median and a large `p99 ms` is one that
  spikes: in the quick start, `shadows`.
- **The frame-times table** gives each `frame` row's median and 99th
  percentile. `wall change (pairs)` is how much `wall` changes from one
  frame to the next. A run can hold its frame rate and still judder;
  this row shows it.
- **Worst frames** lists the longest `wall` times, and names the
  costliest pass in each frame as its `top pass`.

Each table is per segment kind, the part of `segment` before the
colon, so a level's `view` frames and its `move` frames are judged
apart. `--html PAGE` also writes a web page of the run as a graph, with
its slowest frames marked; `--fps 60` draws a 60 fps budget line on it.

### Reading a floor

`floor FILE --fps N` says whether a run held a frame rate. It makes
two checks, after a warm-up of 2 seconds:

- **Windows:** in each one-second window, the frames' mean `wall` is
  within the budget of 1000/N ms.
- **Frames:** no single frame's `wall` is over that budget. A window's
  mean can hide one long frame among fast ones; this check catches it.

The C example's run has one slow frame, so it fails both:

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

It exits 1 on a fail, 0 on a pass, 2 when it cannot tell, and 3 on an
error. The quick start's run is too short to judge, so `floor` exits 2
on it. `--allow-frames K` lets K frames go over the budget. The spec's
[§ 4.7](specs/FLED-0001-run-file-format.md#47-the-010-commands) lists
the other flags.

### Comparing two builds

`compare` says whether a new build's runs got slower than an old
build's, measure by measure.

#### An A/B with compare

Each build needs at least three runs. Alternate them in one sitting:
old, new, new, old, old, new. Three of one build then three of the
other lets drift over time read as a change, and compare warns
`not_interleaved`. `alternate` runs both builds' commands in that
order, five runs a side by default, then compares what they wrote.
Each command must hold `{run}` where its run file's path goes.
On Windows, stopping `alternate` reaches the engine as Ctrl-Break, not
Ctrl-C. An engine that closes its run file on Ctrl-C must handle
Ctrl-Break the same way, or a stopped run has no close line.
A run whose header records other programs loading the CPU or GPU
while it ran makes the compare inconclusive; `--max-load` and
`--max-gpu-busy` set how much is allowed.

#### Several variants against one base

To cost each effect, give the full frame as `--base` and the frame
with each effect off as a named `--variant`:

```sh
frameledger compare --base full1.csv full2.csv full3.csv --variant no_bloom nb1.csv nb2.csv nb3.csv --variant no_fog nf1.csv nf2.csv nf3.csv
frameledger alternate --base './engine --frame-log={run}' --variant no_bloom './engine --no-bloom --frame-log={run}' --out effects
```

Each variant is judged against the base as `compare` judges new
against old, and the variants are ranked by how much frame time each
saved. A variant that cannot be judged does not stop the others.
`--measure` picks another measure to rank by.
`--measure gpu/opaque`, given once per measure, judges only the
measures named, and adds a table of each run's value of each.
Compare reads each run's start time from its file's `started_utc`
header, so list each build's files together on the command line.

#### A saved baseline

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
refused. Nothing alternates with a baseline, so the machine may have
drifted since it was taken: compare warns `baseline_not_interleaved`
and says how old the baseline is. An A/B in one sitting is the surer
check. frameledger never writes the baseline file; to renew it, keep
a session's run files and list them.

#### Reading a compare

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

`view` is the segment kind these runs wrote: the part before the colon
in a row's `segment`, such as `view:3`. Your engine names its own
kinds, and compare judges each kind apart.

It judges frame times, `cpu` and `gpu` passes, and `mem`. It does not
judge `event` or `ext.<engine>` rows.

The first line names the measure with the largest change in ms. Here
all four moved 0.890 ms, so the tie goes to the largest percentage.

It exits 1 here, because a measure got slower. It exits 0 when nothing
got slower or larger, 2 when the runs are too noisy to judge, and 3 on
an error. Unchanged measures are counted, not listed; `--json` lists
every measure with its verdict.

### The other commands

- `bisect` gives `git bisect run` a good, bad or skip verdict for one
  commit's runs
  ([§ 4.11](specs/FLED-0001-run-file-format.md#411-bisect-verdicts)).
- `budget` says whether any pass, or a frame's whole CPU or GPU span,
  went over its time budget
  ([§ 4.12](specs/FLED-0001-run-file-format.md#412-pass-budgets)).
- `survey` ranks many runs by their slowest frames
  ([§ 4.13](specs/FLED-0001-run-file-format.md#413-surveying-many-runs)).
