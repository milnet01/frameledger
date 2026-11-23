"""Make the kit's expected run files with the shipped writer.

    python3 -I scripts/make_kit.py [--cc CC] [OUTDIR]

For each case src/frameledger/kit/NAME.json, writes a C driver that makes
the case's calls on include/frameledger.h, builds it with CC (default
cc), runs it, and writes what it prints, as bytes, to OUTDIR/NAME.csv.
OUTDIR defaults to src/frameledger/kit, which remakes the kit in place
(docs/design.md § The parts; docs/specs/FLED-0001-run-file-format.md
§ 4.19). This is the one piece of code that turns a case into writer
calls; tests/writer/test_kit.sh runs it under each toolchain.

The driver:

- calls fled_open with the case's header and static line as JSON text,
  and the header's run_id as its own argument;
- calls fled_row for each row, ordered by `arrives`, then as listed;
- sizes the buffer to hold the opening lines, the close line and one
  row. Before each kept row it hands on the pending bytes but keeps the
  opening lines' length of them pending, and before a dropped row hands
  on nothing, so the kept row before it still fills the buffer and
  fled_row returns FLED_DROPPED.
  So a dropped row must follow a kept one;
- calls fled_close with close.frames, unless close is null.

It stops, exit 1, when a fled_ call returns anything but what the case
expects, or the writer writes past the capacity it was given. OUTDIR is
written only once every case has run, so a failure leaves it as it was.
Standard library only. Exit 0 on success; 1 when a case cannot be built
or run; 2 on a usage error.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KIT = ROOT / "src" / "frameledger" / "kit"
FLAGS = ["-std=c99", "-O2", "-Wall", "-Wextra", "-Wpedantic", "-Werror"]

DRIVER = """\
#include <stdio.h>
#include <string.h>
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif
#include "frameledger.h"

struct kit_row {{
    const char *segment;
    long long frame;
    const char *category;
    const char *name;
    int depth;
    double value;
    int dropped;
}};

static const char run_id[] = {run_id};
static const char header[] = {header};
{static_text}static const char *const static_json = {static};
static const struct kit_row rows[] = {{
{rows}
}};
static char buf[{buf_size}];
#define GUARD 0x5a /* fills buf past the capacity; a byte that changes is a write past it */

/* Writes out all but `keep` of the pending bytes. Keeping the opening
   lines' length pending before each kept row leaves exactly one row of
   room, so the kept row fits and fills it, and a dropped row that
   follows meets a full buffer. */
static void hand_on(fled_writer *w, size_t keep)
{{
    const char *bytes;
    size_t n = fled_pending(w, &bytes);
    if (n > keep) {{
        fwrite(bytes, 1, n - keep, stdout);
        fled_consume(w, n - keep);
    }}
}}

/* 1 when the writer stayed inside its `cap` bytes. */
static int inside(const fled_writer *w, size_t cap)
{{
    size_t i;
    if (fled_pending(w, NULL) > cap)
        return 0;
    for (i = cap; i < sizeof buf; i++)
        if (buf[i] != GUARD)
            return 0;
    return 1;
}}

int main(void)
{{
    fled_writer w;
    size_t opening, cap, i;
    int rc;
#ifdef _WIN32
    /* Text mode would write each LF as CRLF, and the case is bytes. */
    _setmode(_fileno(stdout), _O_BINARY);
#endif
    /* Measure the opening lines, then open for real with room for them,
       the close line and one row. */
    if (fled_open(&w, buf, sizeof buf, run_id, header, static_json) != FLED_OK) {{
        fprintf(stderr, "fled_open refused the case\\n");
        return 1;
    }}
    opening = fled_pending(&w, NULL);
    cap = opening + FLED_CLOSE_MAX + FLED_ROW_MAX;
    memset(buf, GUARD, sizeof buf);
    if (fled_open(&w, buf, cap, run_id, header, static_json) != FLED_OK) {{
        fprintf(stderr, "fled_open refused the sized buffer\\n");
        return 1;
    }}
    for (i = 0; i < sizeof rows / sizeof rows[0]; i++) {{
        if (!rows[i].dropped)
            hand_on(&w, opening);
        rc = fled_row(&w, rows[i].segment, rows[i].frame, rows[i].category, rows[i].name, rows[i].depth,
                      rows[i].value);
        if (rc != (rows[i].dropped ? FLED_DROPPED : FLED_OK)) {{
            fprintf(stderr, "row %u: fled_row returned %d%s\\n", (unsigned)i, rc,
                    rows[i].dropped ? "; a dropped row must follow a kept one"
                    : rc == FLED_DROPPED ? "; the buffer was full for a row meant to be kept" : "");
            return 1;
        }}
        if (!inside(&w, cap)) {{
            fprintf(stderr, "row %u: the writer wrote past its capacity\\n", (unsigned)i);
            return 1;
        }}
    }}
    {close}
    if (!inside(&w, cap)) {{
        fprintf(stderr, "the writer wrote past its capacity\\n");
        return 1;
    }}
    hand_on(&w, 0);
    return fflush(stdout) == 0 ? 0 : 1;
}}
"""

CLOSE = """if (fled_close(&w, {frames}LL) != FLED_OK) {{
        fprintf(stderr, "fled_close refused\\n");
        return 1;
    }}"""


def c_chars(text: str) -> str:
    """`text` as a C array initialiser of its UTF-8 bytes and a NUL. An
    array, not a string literal, so no length limit applies: C99 promises
    string literals of 4095 bytes only, which -Wpedantic enforces, and a
    static line can be longer."""
    chars = [f"'{chr(b)}'" if b < 0x80 and chr(b).isalnum() else f"'\\{b:03o}'" for b in text.encode("utf-8")] + ["0"]
    lines = [", ".join(chars[i:i + 16]) for i in range(0, len(chars), 16)]
    return "{\n    " + ",\n    ".join(lines) + "\n}"


def c_string(text: str) -> str:
    """`text` as a C string literal of its UTF-8 bytes. Every byte but a
    letter, digit or a few safe marks is a three-digit octal escape, so
    no trigraph, quote or following digit can change it."""
    safe = b"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 _-.:/{}[],"
    return '"' + "".join(chr(b) if b in safe else f"\\{b:03o}" for b in text.encode("utf-8")) + '"'


def ordered_rows(case: dict) -> list[tuple[dict, dict]]:
    """(frame entry, row) pairs in the order a writer meets them: by
    `arrives`, absent meaning the row's own frame, then as listed."""
    pairs = [(entry, row) for entry in case["frames"] for row in entry["rows"]]
    return sorted(pairs, key=lambda pair: pair[1].get("arrives", pair[0]["frame"]))


def driver(case: dict) -> str:
    """The C driver for one case. Raises ValueError for a case with no
    rows, which C cannot hold as an empty array."""
    header = json.dumps(case["header"], ensure_ascii=False, separators=(",", ":"))
    static = case.get("static")
    static_text = None if static is None else json.dumps(static, ensure_ascii=False, separators=(",", ":"))
    rows = []
    for entry, row in ordered_rows(case):
        # repr gives the shortest text that reads back as the same double,
        # which is the double the JSON number names.
        rows.append(f"    {{{c_string(entry.get('segment', ''))}, {int(entry['frame'])}LL, "
                    f"{c_string(row['category'])}, {c_string(row['name'])}, {int(row['depth'])}, "
                    f"{float(row['value'])!r}, {1 if row.get('dropped') else 0}}},")
    if not rows:
        raise ValueError("a case needs at least one row")
    close = case["close"]
    return DRIVER.format(
        run_id=c_chars(case["header"]["run_id"]),
        header=c_chars(header),
        static_text="" if static_text is None else f"static const char static_text[] = {c_chars(static_text)};\n",
        static="NULL" if static_text is None else "static_text",
        rows="\n".join(rows),
        # The opening lines take under 100 bytes beyond the JSON; 1024 is room to spare.
        buf_size=f"{len(header.encode()) + len((static_text or '').encode()) + 1024} + FLED_CLOSE_MAX + FLED_ROW_MAX",
        close="" if close is None else CLOSE.format(frames=int(close["frames"])),
    )


def make(case_path: Path, outdir: Path, cc: str, scratch: Path) -> None:
    """Build and run one case's driver in `scratch`; write what it prints to
    `outdir`/NAME.csv."""
    name = case_path.stem
    source, program = scratch / f"{name}.c", scratch / name
    source.write_text(driver(json.loads(case_path.read_text(encoding="utf-8"))), encoding="utf-8")
    subprocess.run([cc, *FLAGS, "-I", str(ROOT / "include"), str(source), "-lm", "-o", str(program)],
                   check=True)
    done = subprocess.run([str(program)], capture_output=True, check=False)
    if done.returncode != 0:
        sys.exit(f"make_kit: {name}: {done.stderr.decode(errors='replace').strip()}")
    (outdir / f"{name}.csv").write_bytes(done.stdout)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Make the kit's expected run files with the shipped writer.")
    parser.add_argument("--cc", default="cc", help="the C compiler (default cc)")
    parser.add_argument("outdir", nargs="?", type=Path, default=KIT, help="where NAME.csv goes (default: the kit)")
    args = parser.parse_args(argv)
    cases = sorted(KIT.glob("*.json"))
    if not cases:
        sys.exit(f"make_kit: no cases in {KIT}")
    with tempfile.TemporaryDirectory(prefix="make_kit-") as scratch:
        made = Path(scratch) / "made"
        made.mkdir()
        for case_path in cases:
            try:
                make(case_path, made, args.cc, Path(scratch))
            except (OSError, ValueError, subprocess.CalledProcessError) as error:
                sys.exit(f"make_kit: {case_path.stem}: {error}")
        args.outdir.mkdir(parents=True, exist_ok=True)
        for csv in sorted(made.iterdir()):
            (args.outdir / csv.name).write_bytes(csv.read_bytes())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
