frameledger's writer kit
========================

This kit shows whether your own writer of frameledger run files is
right. It is for a writer built from the format spec alone, in any
language. The spec is FLED-0001, and § 4.19 is this kit's part of it:
https://github.com/milnet01/frameledger/blob/main/docs/specs/FLED-0001-run-file-format.md
The release archive does not hold the spec.

Each case is two files:

  NAME.json   what an engine measured
  NAME.csv    the run file a correct writer makes from it

Each case catches one mistake a writer can make. Its JSON says which,
in "catches".

You write one small program, a driver, that reads a case's NAME.json
and hands its measurements to your writer, as your engine would. The
kit then tells you whether your writer's file is right.


Getting the kit and running frameledger
---------------------------------------

Below, `frameledger` means the release's launcher, frameledger on
Linux or frameledger.cmd on Windows, or `python3 -I frameledger.pyz`
(`py -I frameledger.pyz` on Windows). To write the kit into a new,
empty folder:

  frameledger kit DIR


How to use it
-------------

1. For each case, have your driver turn NAME.json into a run file
   through your writer. Call it mine.csv.
2. Run:

     frameledger check --expect NAME.csv mine.csv

   Exit 0: your file meets the format and matches. Exit 1: it does
   not; the first sentence check prints names the first difference,
   and --json lists up to 20. Exit 3: a file cannot be read, or more
   than one file follows --expect.
3. Optionally, also run:

     frameledger check --strict mine.csv

   It warns on what is legal but unwise. A correct writer gives
   exactly the warning codes the case lists in "warns", which makes
   --strict exit 1 for those cases. That is expected.

--expect matches content, not layout. The header, static and close
lines may have any key order and spacing; 1 and 1.0 are equal, but
true is never 1. Rows may come in any order, but each row is compared
as text, so a value must have exactly the same digits, and a field
must be quoted only when it holds a comma or a quote.


A case's JSON
-------------

  "catches"  the mistake the case catches, in words. Your driver ignores it.
  "warns"    the warning codes NAME.csv gives under check --strict.
             Your driver ignores it.
  "header"   the header to write, as given.
  "static"   the static line to write. Absent: write no static line.
  "frames"   a list of frames, each {"frame", "segment", "rows"}.
  "close"    {"frames": N}: close the run, giving N frames.
             null: the run ends with no close line, as when the
             engine is killed.

Each row is {"category", "name", "depth", "value"}. Write each row's
run_id, the header's "run_id", and its frame's "frame" and "segment";
write "segment", "category", "name" and "depth" as given. A row may
also hold:

  "arrives"  the frame during which the value became known, such as a
             GPU time read back a frame or more late. The row still
             belongs to its own frame. Absent: its own frame.
  "dropped"  true: a row your writer could not keep, as when its buffer
             is full. It is not written, and it counts in the close
             line's rows_dropped. A writer whose buffer grows, and so
             never fills, skips the row and counts it as if full.

Hand the rows to your writer in the order they arrive: by "arrives",
then as listed. So a row from an earlier frame that arrives during
frame F comes before frame F's own rows. --expect does not check row
order. The order matters for what it does check: which rows a full
buffer drops, and that rows arriving after the last frame come before
the close line.

With frameledger's own C writer, include/frameledger.h, each part is
one call. fled_open takes the run_id on its own, and writes it on
every row:

  header, static   fled_open(w, buf, size, run_id, header_json, static_json)
  each row         fled_row(w, segment, frame, category, name, depth, value)
  close            fled_close(w, frames)


Numbers
-------

- "value" is a JSON number to be read as a C double, then rounded to
  thousandths as the format says: llround(value * 1000.0), ties away
  from zero. The cases' values round the same whether you round the
  double or the decimal text. printf("%.3f") does not round this way:
  5.2505 must be written 5.251, where printf gives 5.250.
- A value that rounds to zero is written 0.000, never -0.000.
- "frame" is a JSON integer to be read exactly, never through a
  double, which loses digits past 15. The largest is
  9223372036854775807, 19 digits.
- Rows with category frame and name wall are given as measured. Write
  them as they are.


Rows that arrive after the last frame
-------------------------------------

A finished run's close line follows every row it will write, so rows
that arrive after the last frame go before it: gpu-after-last.

A writer that cannot wait for such rows counts them in rows_dropped
instead, which is legal. For that writer, gpu-after-last-dropped marks
them dropped. Use it in place of gpu-after-last.
