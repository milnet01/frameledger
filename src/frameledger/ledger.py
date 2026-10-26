"""Read one run file into a Run, listing every way it breaks the format.

The format is docs/specs/FLED-0001-run-file-format.md § 4. A file that
cannot be read at all, or whose schema is newer than this analyser's,
raises LedgerError. Anything else wrong with it is a Breach on the Run,
so `check` can list them all; other commands refuse a Run with any.
"""

from __future__ import annotations

import csv
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

SCHEMA = 1
COLUMNS = "run_id,segment,frame,category,name,depth,value"
HEADER, STATIC, CLOSE = "# frameledger ", "# frameledger-static ", "# frameledger-close "

NAME_MAX = 64
PART_MAX = 32  # category; segment kind; segment id
VALUE_LIMIT = 1_000_000_000_000  # 1 000 000 000, in thousandths

FRAME_NAMES = {"cpu_span", "gpu_span", "wall", "fence_wait", "present_wait"}
SIGNED_CATEGORIES = {"frame", "cpu", "gpu"}  # milliseconds, where a negative is a clock fault

NAME_RE = re.compile(r"[A-Za-z0-9_./-]+")
CATEGORY_RE = re.compile(r"frame|cpu|gpu|mem|event|ext\.[A-Za-z0-9_./-]+")
VALUE_RE = re.compile(r"(-?)([0-9]+)\.([0-9]{3})")
COUNT_RE = re.compile(r"[0-9]+")
HASH_RE = re.compile(r"sha256:[0-9A-Fa-f]{64}|md5:[0-9A-Fa-f]{32}")
UTC_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?Z")


class LedgerError(Exception):
    """A file or argument problem: what was wrong and where."""

    def __init__(self, message: str, path: str | None = None, line: int | None = None):
        where = path if line is None else f"{path}, line {line}"
        super().__init__(f"{where}: {message}" if path else message)
        self.reason, self.path, self.line = message, path, line


@dataclass(frozen=True)
class Breach:
    line: int
    rule: str
    message: str


@dataclass(frozen=True)
class Notice:
    """A warning: worth a reader's attention, but the file still conforms."""

    code: str
    message: str
    line: int | None = None


@dataclass(frozen=True)
class Row:
    segment: str
    frame: int
    category: str
    name: str
    depth: int
    thousandths: int  # the value column as an exact integer; ms rows are microseconds
    line: int = field(compare=False)


@dataclass
class Run:
    path: str = field(compare=False)
    header: dict | None = None
    static: dict | None = None
    close: dict | None = None
    # Rows joined on (run_id, frame) whatever order they came in; one
    # run_id per file, so the key is the frame, then (category, name).
    frames: dict[int, dict[tuple[str, str], Row]] = field(default_factory=dict)
    breaches: list[Breach] = field(default_factory=list)
    notices: list[Notice] = field(default_factory=list)


def read(path: str | Path) -> Run:
    """Read one run file. Raises LedgerError only when it cannot be judged."""
    try:
        with open(path, "rb") as stream:
            return read_bytes(stream.read(), str(path))
    except OSError as error:
        raise LedgerError(error.strerror or "cannot be read", str(path)) from error


def read_bytes(data: bytes, path: str) -> Run:
    """Read a run file's contents; `path` names it in breaches and errors."""
    reader = _Reader(Run(path))
    lines = data.split(b"\n")
    if lines[-1] == b"":
        lines.pop()  # the final line ending, not an empty line
    if data.startswith(b"\xef\xbb\xbf"):
        lines[0] = lines[0][3:]  # some Windows editors add a byte-order mark
    for number, raw in enumerate(lines, start=1):
        if raw.endswith(b"\r"):
            raw = raw[:-1]
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            reader.breach(number, "encoding", "the line is not UTF-8 text")
            continue
        reader.line(number, text)
    reader.finish(len(lines))
    return reader.run


class _Reader:
    """One pass over the lines: header, optional static line, column line,
    rows in any order, then the close line."""

    def __init__(self, run: Run):
        self.run = run
        self.expect = "header"  # then "static", "columns", "rows"
        self.run_id: str | None = None
        self.close_line = 0

    def breach(self, line: int, rule: str, message: str) -> None:
        self.run.breaches.append(Breach(line, rule, message))

    def notice(self, code: str, message: str, line: int | None = None) -> None:
        self.run.notices.append(Notice(code, message, line))

    def line(self, number: int, text: str) -> None:
        if self.close_line:
            self.breach(number, "close", "a line follows the close line, which must come last")
            return
        if self.expect == "header":
            self.expect = "static"
            if text.startswith(HEADER):
                self.header(number, text[len(HEADER):])
                return
            self.breach(number, "header", "the first line must be the '# frameledger {...}' header")
        if self.expect == "static":
            self.expect = "columns"
            if text.startswith(STATIC):
                self.static(number, text[len(STATIC):])
                return
        if self.expect == "columns":
            self.expect = "rows"
            if text == COLUMNS:
                return
            self.breach(number, "columns", f"the column line must be exactly '{COLUMNS}'")
            if not text or text.startswith("#") or text.count(",") != 6:
                return
        if text.startswith(CLOSE):
            self.close(number, text[len(CLOSE):])
        elif text.startswith("#"):
            self.breach(number, "comment", "only the header, static and close lines may begin with '#'")
        else:
            self.row(number, text)

    def json_object(self, number: int, rule: str, text: str) -> dict | None:
        try:
            value = json.loads(text, parse_constant=_reject_constant)
        except ValueError as error:
            self.breach(number, rule, f"not valid JSON: {error}")
            return None
        if not isinstance(value, dict):
            self.breach(number, rule, "must hold one JSON object")
            return None
        return value

    def header(self, number: int, text: str) -> None:
        header = self.json_object(number, "header", text)
        if header is None:
            return
        schema = header.get("schema")
        if _is_int(schema) and schema > SCHEMA:
            raise LedgerError(
                f"the file is schema {schema}, but this analyser reads schema {SCHEMA} and "
                "older; use a newer frameledger",
                self.run.path, number,
            )
        problems = _header_problems(header)
        for problem in problems:
            self.breach(number, "header", problem)
        for name in sorted(header.keys() - HEADER_FIELDS.keys()):
            self.notice("unknown_field", f"the header has a field this format does not define: "
                        f"'{name}'", number)
        if header.get("inputs") == []:
            self.notice("inputs_empty", "the header lists no inputs, so no compare can tell whether the "
                        "same content was run", number)
        self.run.header = header
        if isinstance(header.get("run_id"), str):
            self.run_id = header["run_id"]

    def static(self, number: int, text: str) -> None:
        static = self.json_object(number, "static", text)
        if static is None:
            return
        if _holds_number(static):
            self.breach(number, "static", "a statistic must be a JSON string of its exact digits, "
                        "never a JSON number")
        self.run.static = static

    def close(self, number: int, text: str) -> None:
        self.close_line = number
        close = self.json_object(number, "close", text)
        if close is None:
            return
        for key in ("rows_dropped", "frames"):
            if not (_is_int(close.get(key)) and close[key] >= 0):
                self.breach(number, "close", f"'{key}' must be a whole number, 0 or more")
                return
        self.run.close = close
        if close["rows_dropped"]:
            self.notice("rows_dropped", f"the writer dropped {close['rows_dropped']} rows because its "
                        "buffer was full", number)

    def row(self, number: int, text: str) -> None:
        fields = next(csv.reader([text])) if '"' in text else text.split(",")
        if len(fields) != 7:
            self.breach(number, "row", f"a row has 7 fields; this line has {len(fields) if text else 0}")
            return
        run_id, segment, frame, category, name, depth, value = fields
        problem = _row_problem(run_id, segment, frame, category, name, depth, value, self.run_id)
        if problem:
            self.breach(number, *problem)
            return
        row = Row(segment, int(frame), category, name, int(depth), _thousandths(value), number)
        rows = self.run.frames.setdefault(row.frame, {})
        key = (category, name)
        if key in rows:
            self.breach(number, "duplicate", f"frame {row.frame} already has a {category}/{name} row, "
                        f"on line {rows[key].line}")
            return
        rows[key] = row
        if category == "frame" and name not in FRAME_NAMES:
            self.notice("unknown_frame_name", f"'frame/{name}' is not a frame measure this format "
                        "defines", number)
        if category == "frame" and name == "wall" and row.thousandths <= 0:
            self.breach(number, "wall", "frame/wall must be above zero; the timeline cannot be built from it")
        elif category in SIGNED_CATEGORIES and row.thousandths < 0:
            self.notice("negative_value", f"{category}/{name} is negative ({value}) on frame {row.frame}, "
                        "which points to a clock fault", number)

    def finish(self, line_count: int) -> None:
        if line_count == 0:
            self.breach(1, "header", "the file is empty")
            return
        if self.expect != "rows":
            self.breach(line_count, "columns", f"the column line '{COLUMNS}' is missing")
        last = max(self.run.frames, default=None)
        # A full buffer may drop a frame's CPU rows while its late GPU rows
        # still land, so with drops counted a missing cpu_span is expected.
        dropped = bool(self.run.close and self.run.close["rows_dropped"])
        previous = None
        for frame, rows in sorted(self.run.frames.items()):
            first_line = min(row.line for row in rows.values())
            if previous is not None and frame != previous + 1:
                missing = f"frame {previous + 1}" if frame == previous + 2 else \
                    f"frames {previous + 1} to {frame - 1}"
                self.notice("frame_missing", f"no row names {missing}, so the timeline has a hole "
                            "there", first_line)
            previous = frame
            if ("frame", "cpu_span") not in rows and dropped:
                self.notice("cpu_span_missing", f"frame {frame} has no frame/cpu_span row, "
                            "probably among the dropped rows", first_line)
            elif ("frame", "cpu_span") not in rows:
                self.breach(first_line, "cpu_span", f"frame {frame} has no frame/cpu_span row")
            if ("frame", "wall") not in rows and frame != last:
                self.notice("wall_missing", f"frame {frame} has no frame/wall row, so the timeline "
                            "stops there", first_line)
        if not self.close_line:
            self.notice("unfinished", "the file has no close line: the run did not finish, so the "
                        "engine crashed or was killed")
        self.run.breaches.sort(key=lambda breach: breach.line)


def frame_segment(rows: dict) -> str:
    """A frame's segment (§ 4.8): its frame/cpu_span row's, or else its
    first row's. `rows` is one entry of Run.frames."""
    row = rows.get(("frame", "cpu_span")) or min(rows.values(), key=lambda r: r.line)
    return row.segment


def _row_problem(run_id, segment, frame, category, name, depth, value, header_run_id):
    """The first rule a row's fields break, as (rule, message), or None."""
    if header_run_id is not None and run_id != header_run_id:
        return "run_id", f"run_id '{run_id}' differs from the header's '{header_run_id}'"
    if segment:
        kind, colon, ident = segment.partition(":")
        if not (colon and kind and ident):
            return "segment", f"segment '{segment}' must be '<kind>:<id>' or empty"
        if len(kind.encode()) > PART_MAX or len(ident.encode()) > PART_MAX:
            return "segment", f"a segment's kind and id are at most {PART_MAX} bytes each"
    if not COUNT_RE.fullmatch(frame):
        return "frame", f"frame '{frame}' must be a whole number, 0 or more"
    if not CATEGORY_RE.fullmatch(category) or len(category) > PART_MAX:
        return "category", (f"category '{category}' must be frame, cpu, gpu, mem, event or "
                            f"ext.<engine>, at most {PART_MAX} bytes")
    if not NAME_RE.fullmatch(name) or len(name) > NAME_MAX:
        return "name", (f"name '{name}' must be 1 to {NAME_MAX} ASCII letters, digits "
                        "and '_ . / -'")
    if not COUNT_RE.fullmatch(depth):
        return "depth", f"depth '{depth}' must be a whole number, 0 or more"
    if not VALUE_RE.fullmatch(value):
        return "value", (f"value '{value}' must be a decimal number with '.' as the point "
                         "and exactly three places after it")
    if abs(_thousandths(value)) >= VALUE_LIMIT:
        return "value", f"value '{value}' must be below 1000000000 in size"
    return None


def _thousandths(value: str) -> int:
    sign, whole, places = VALUE_RE.fullmatch(value).groups()
    magnitude = int(whole) * 1000 + int(places)
    return -magnitude if sign else magnitude


def _reject_constant(name: str) -> None:
    raise ValueError(f"{name} is not a JSON number")


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value) -> bool:
    return (_is_int(value) or isinstance(value, float)) and math.isfinite(value)


def _holds_number(value) -> bool:
    if isinstance(value, dict):
        return any(_holds_number(item) for item in value.values())
    if isinstance(value, list):
        return any(_holds_number(item) for item in value)
    return _is_number(value)


def _is_schema(value) -> bool:
    return _is_int(value) and value >= 1


def _is_string(value) -> bool:
    return isinstance(value, str)


def _is_bool(value) -> bool:
    return isinstance(value, bool)


def _is_object(value) -> bool:
    return isinstance(value, dict)


def _is_tool(value) -> bool:
    return isinstance(value, dict) and all(isinstance(value.get(k), str) for k in ("name", "version"))


def _is_resolution(value) -> bool:
    return isinstance(value, list) and len(value) == 2 and all(_is_int(v) and v > 0 for v in value)


def _is_display(value) -> bool:
    return value in ("onscreen", "headless", "offscreen")


def _is_input(value) -> bool:
    return (isinstance(value, dict) and isinstance(value.get("name"), str)
            and isinstance(value.get("hash"), str) and bool(HASH_RE.fullmatch(value["hash"]))
            and _is_int(value.get("bytes")) and value["bytes"] >= 0)


def _is_inputs(value) -> bool:
    return isinstance(value, list) and all(_is_input(item) for item in value)


def _is_utc(value) -> bool:
    return isinstance(value, str) and bool(UTC_RE.fullmatch(value))


def _is_span(value) -> bool:
    return isinstance(value, dict) and all(_is_number(value.get(k)) for k in ("start", "end"))


# Each header field: (required, test, what the test wants), per § 4.2.
HEADER_FIELDS = {
    "schema": (True, _is_schema, "a whole number, 1 or more"),
    "run_id": (True, _is_string, "a string"),
    "engine": (True, _is_string, "a string"),
    "tool": (True, _is_tool, 'an object {"name": string, "version": string}'),
    "build_type": (True, _is_string, "a string"),
    "commit": (True, _is_string, "a string"),
    "dirty": (True, _is_bool, "true or false"),
    "device": (True, _is_string, "a string"),
    "renderer": (True, _is_string, "a string"),
    "driver": (True, _is_string, "a string"),
    "api": (True, _is_string, "a string"),
    "resolution": (True, _is_resolution, "[width, height] in whole pixels"),
    "render_scale": (True, _is_number, "a number"),
    "vsync": (True, _is_bool, "true or false"),
    "pipelined": (True, _is_bool, "true or false"),
    "display": (True, _is_display, "onscreen, headless or offscreen"),
    "scene": (True, _is_string, "a string"),
    "inputs": (True, _is_inputs, 'a list of {"name", "hash": "sha256:<hex>" or "md5:<hex>", "bytes"}'),
    "started_utc": (True, _is_utc, "an ISO 8601 time ending in Z"),
    "tier": (False, _is_string, "a string"),
    "ray_tracing": (False, _is_bool, "true or false"),
    "frames_in_flight": (False, _is_int, "a whole number"),
    "settling_frames": (False, _is_int, "a whole number"),
    "settled_frames": (False, _is_int, "a whole number"),
    "pinned": (False, _is_object, "an object"),
    "gpu_tick_ns": (False, _is_number, "a number"),
    "load": (False, _is_span, '{"start": number, "end": number}'),
    "gpu_busy_pct": (False, _is_span, '{"start": number, "end": number}'),
    "gpu_clock_mhz": (False, _is_span, '{"start": number, "end": number}'),
    "os": (False, _is_string, "a string"),
    "extra": (False, _is_object, "an object"),
}


def _header_problems(header: dict) -> list[str]:
    problems = []
    for name, (required, test, wanted) in HEADER_FIELDS.items():
        if name not in header:
            if required:
                problems.append(f"the header has no '{name}' field")
        elif not test(header[name]):
            problems.append(f"the header's '{name}' must be {wanted}")
    return problems
