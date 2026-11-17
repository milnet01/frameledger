frameledger's writer kit
========================

This kit shows whether your own writer of frameledger run files is
right. It is for a writer built from the format spec alone, in any
language. The format is docs/specs/FLED-0001-run-file-format.md in
frameledger's source; § 4.19 is this kit's part of it.

Each case is two files:

  NAME.json   what an engine measured
  NAME.csv    the run file a correct writer makes from it

Each case catches one mistake a writer can make. Its JSON says which,
in "catches".


How to use it
-------------

1. For each case, have your writer turn NAME.json into a run file, as
   your engine would hand it the same measurements. Call it mine.csv.
2. Run:

     frameledger check --expect NAME.csv mine.csv

   Exit 0: your file meets the format and matches. Exit 1: it does not,
   and the first sentence names the first difference. --json lists up
   to 20.
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

  "catches"  the mistake the case catches, in words. Your writer ignores it.
  "warns"    the warning codes NAME.csv gives under check --strict.
             Your writer ignores it.
  "header"   the header to write, as given.
  "static"   the static line to write. Absent: write no static line.
  "frames"   a list of frames, each {"frame", "segment", "rows"}.
  "close"    {"frames": N}: close the run, giving N frames.
             null: the run ends with no close line, as when the
             engine is killed.

Each row is {"category", "name", "depth", "value"}, and may also hold:

  "arrives"  the frame during which the value became known, such as a
             GPU time read back a frame or more late. The row still
             belongs to its own frame. Absent: its own frame.
  "dropped"  true: a row your writer could not keep, as when its buffer
             is full. It is not written, and it counts in the close
             line's rows_dropped.

Write the rows in the order they arrive: by "arrives", then as listed.
A row that arrives after the last frame is written before the close
line.

With frameledger's own C writer, include/frameledger.h, each part is
one call:

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
- frame/wall rows are given as measured. Write them as they are.


Rows that arrive after the last frame
-------------------------------------

A finished run's close line follows every row it will write, so rows
that arrive after the last frame go before it: gpu-after-last.

A writer that cannot wait for such rows counts them in rows_dropped
instead, which is legal. For that writer, gpu-after-last-dropped marks
them dropped. Use it in place of gpu-after-last.
