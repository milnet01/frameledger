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
  row. Before each kept row it hands on all but the opening lines'
  length of pending bytes, and before a dropped row nothing, so the kept
  row before it still fills the buffer and fled_row returns FLED_DROPPED.
  So a dropped row must follow a kept one;
- calls fled_close with close.frames, unless close is null.

It stops, exit 1, when a fled_ call returns anything but what the case
expects. Standard library only. Exit 0 on success; 1 when a case cannot
be built or run; 2 on a usage error.
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
static const char *const static_json = {static};
static const struct kit_row rows[] = {{
{rows}
}};
static char buf[{buf_size}];

/* Writes out all but `keep` of the pending bytes. */
static void hand_on(fled_writer *w, size_t keep)
{{
    const char *bytes;
    size_t n = fled_pending(w, &bytes);
    if (n > keep) {{
        fwrite(bytes, 1, n - keep, stdout);
        fled_consume(w, n - keep);
    }}
}}

int main(void)
{{
    fled_writer w;
    size_t opening, i;
    int rc;
    /* Measure the opening lines, then open for real with room for them,
       the close line and one row. */
    if (fled_open(&w, buf, sizeof buf, run_id, header, static_json) != FLED_OK) {{
        fprintf(stderr, "fled_open refused the case\\n");
        return 1;
    }}
    opening = fled_pending(&w, NULL);
    if (fled_open(&w, buf, opening + FLED_CLOSE_MAX + FLED_ROW_MAX, run_id, header, static_json) != FLED_OK) {{
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
                    rows[i].dropped ? "; a dropped row must follow a kept one" : "");
            return 1;
        }}
    }}
    {close}
    hand_on(&w, 0);
    return fflush(stdout) == 0 ? 0 : 1;
}}
"""

CLOSE = """if (fled_close(&w, {frames}LL) != FLED_OK) {{
        fprintf(stderr, "fled_close refused\\n");
        return 1;
    }}"""


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
    """The C driver for one case."""
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
    close = case["close"]
    return DRIVER.format(
        run_id=c_string(case["header"]["run_id"]),
        header=c_string(header),
        static="NULL" if static_text is None else c_string(static_text),
        rows="\n".join(rows),
        # The opening lines take under 100 bytes beyond the JSON; 1024 is room to spare.
        buf_size=f"{len(header.encode()) + len((static_text or '').encode()) + 1024} + FLED_CLOSE_MAX + FLED_ROW_MAX",
        close="" if close is None else CLOSE.format(frames=int(close["frames"])),
    )


def make(case_path: Path, outdir: Path, cc: str, scratch: Path) -> None:
    """Build and run one case's driver; write what it prints to OUTDIR/NAME.csv."""
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
    args.outdir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="make_kit-") as scratch:
        for case_path in cases:
            try:
                make(case_path, args.outdir, args.cc, Path(scratch))
            except (OSError, subprocess.CalledProcessError) as error:
                sys.exit(f"make_kit: {case_path.stem}: {error}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
