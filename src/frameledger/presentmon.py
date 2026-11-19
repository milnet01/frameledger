"""A PresentMon capture (S25), turned into a run file.

The rules are docs/specs/FLED-0001-run-file-format.md § 4.18. This is
the one place that reads a capture: every other command reads the run
file it writes. Values go from the capture's decimal text to the run's
thousandths with no float between, so `1.0005` is `1.001`.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from fractions import Fraction

import ledger

NEEDED = ("Application", "ProcessID", "SwapChainAddress", "MsBetweenPresents", "MsCPUBusy")
VERSION_1 = ("msBetweenPresents", "TimeInSeconds")  # PresentMon 1, or 2 with --v1_metrics
# --qpc_time, --qpc_time_ms, the default, --date_time; the first present is used.
START_COLUMNS = ("CPUStartQPC", "CPUStartQPCTime", "CPUStartTime", "CPUStartDateTime")
THOUSANDTH = Decimal("0.001")
TOO_LARGE = Decimal(1_000_000_000)  # § 4.4 holds values below this, in ms
# A number as a capture writes it. Decimal() alone also takes "1_000",
# "Infinity" and "NaN".
NUMBER = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")
NO_VALUE = ("", "NA")  # what PresentMon writes in a column with nothing to say
# --track_frame_type's FrameType for a frame the application rendered; any
# other value, one PresentMon adds later included, is a generated frame (§ 4.18).
APPLICATION = "Application"
# CPUStartDateTime: a date, a time, an optional fraction, an optional zone.
DATE_TIME = re.compile(r"([0-9]{4}-[0-9]{2}-[0-9]{2})[T ]([0-9]{2}:[0-9]{2}:[0-9]{2})(?:\.([0-9]+))?"
                       r"(Z|[+-][0-9]{2}:[0-9]{2})?")
# § 4.18's stand-ins: what a required field holds when nothing says its value.
STAND_INS = {"commit": "unknown", "dirty": True, "build_type": "unknown", "device": "unknown",
             "renderer": "unknown", "driver": "unknown", "api": "unknown", "resolution": [1, 1],
             "render_scale": 0, "vsync": False, "pipelined": False, "display": "onscreen", "scene": "unknown"}
OPTIONAL_FACTS = ("tier", "os")


@dataclass(frozen=True)
class Chosen:
    """--process, --pid and --swapchain: which rows to keep."""
    process: str | None = None
    pid: str | None = None
    swapchain: str | None = None


@dataclass(frozen=True)
class _Row:
    line: int
    values: dict[str, str]  # column name -> its text, for every column the capture has

    def get(self, column: str) -> str | None:
        return self.values.get(column)


def import_capture(capture: str, run_path: str, chosen: Chosen, facts: dict, engine: str | None = None,
                   started: str | None = None, version: str | None = None) -> dict:
    """Write the run file `run_path` from `capture`. `facts` holds each
    fact flag given, as its header field and value. Returns {"summary",
    "notices", "import"}; raises LedgerError, with nothing written, on
    any refusal (§ 4.18)."""
    if os.path.lexists(run_path):
        raise _exists(run_path)
    for field, value in facts.items():
        test, wanted = ledger.HEADER_FIELDS[field][1:]
        if not test(value):
            raise ledger.LedgerError(f"the {field} given must be {wanted}")
    try:
        with open(capture, "rb") as stream:
            data = stream.read()
    except OSError as error:
        raise ledger.LedgerError(error.strerror or "cannot be read", capture) from error
    columns, rows = _read_capture(data, capture)
    rows = _choose(rows, chosen, capture)
    notices, said = _start_order(rows, columns)
    header = _header(rows, columns, facts, engine, started, version, data, capture)
    lines, not_displayed, generated = _run_lines(rows, columns, header, capture)
    write_atomically(run_path, "\n".join(lines) + "\n")

    first = rows[0]
    process, pid, swapchain = (first.get(c) for c in ("Application", "ProcessID", "SwapChainAddress"))
    shown = "" if not_displayed is None else \
        f"; {not_displayed} {'was' if not_displayed == 1 else 'were'} not displayed"
    summary = [f"Wrote {len(rows)} {'frame' if len(rows) == 1 else 'frames'} of {ledger.quoted(process)} (pid "
               f"{ledger.quoted(pid)}, swap chain {ledger.quoted(swapchain)}) to {run_path}{shown}.", *said]
    if generated:
        total = sum(generated.values())
        kinds = ", ".join(f"{ledger.quoted(name)} {count}" for name, count in generated.items())
        summary.append(f"{total} {'was' if total == 1 else 'were'} generated ({kinds}).")
    if not_displayed is None:
        summary.append("The capture has no DisplayedTime column, so no frame is marked not displayed.")
    if generated is None:
        summary.append("The capture has no FrameType column, so every frame is read as the application's.")
    unknown = header.get("unknown", [])
    if unknown:
        summary.append(f"The header does not know its {ledger.listed_names(unknown)}; the fact flags "
                       "can give them.")
    return {"summary": summary, "notices": notices,
            "import": {"path": run_path, "process": process, "pid": pid, "swapchain": swapchain,
                       "frames": len(rows), "not_displayed": not_displayed, "generated": generated,
                       "unknown": unknown}}


def _read_capture(data: bytes, capture: str) -> tuple[set[str], list[_Row]]:
    """The capture's column names and its rows, refusing a capture whose
    columns are not PresentMon 2's."""
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise ledger.LedgerError("the capture is not UTF-8 text", capture) from None
    reader = csv.reader(io.StringIO(text, newline=""))
    names = next(reader, None)
    if not names:
        raise ledger.LedgerError("the capture is empty; its first line must name its columns", capture)
    names = [name.strip() for name in names]
    columns = set(names)
    if "MsCPUBusy" not in columns and columns & set(VERSION_1):
        found = ", ".join(name for name in VERSION_1 if name in columns)
        raise ledger.LedgerError(f"the capture has PresentMon 1's columns ({found}) and no MsCPUBusy column, so "
                                 "no frame has the frame/cpu_span a run needs; capture again with PresentMon "
                                 "2's default metrics", capture)
    lacking = [name for name in NEEDED if name not in columns]
    if lacking:
        raise ledger.LedgerError(f"the capture has no {ledger.listed_names(lacking)} "
                                 f"{'column' if len(lacking) == 1 else 'columns'}, which an import needs",
                                 capture)
    rows = []
    try:
        for fields in reader:
            if not any(field.strip() for field in fields):
                continue  # a blank line
            if len(fields) != len(names):
                raise ledger.LedgerError(f"the row has {len(fields)} fields and the column line {len(names)}",
                                         capture, reader.line_num)
            rows.append(_Row(reader.line_num, {name: field.strip()
                                               for name, field in zip(names, fields, strict=True)}))
    except csv.Error as error:  # such as a field longer than csv's limit
        raise ledger.LedgerError(f"the row is not CSV the import can read ({error})", capture,
                                 reader.line_num) from None
    if not rows:
        raise ledger.LedgerError("the capture has no rows", capture)
    return columns, rows


def _choose(rows: list[_Row], chosen: Chosen, capture: str) -> list[_Row]:
    """The rows of one process and one swap chain, or a refusal listing
    what is left to pick from."""
    for flag, column, wanted in (("--process", "Application", chosen.process), ("--pid", "ProcessID", chosen.pid),
                                 ("--swapchain", "SwapChainAddress", chosen.swapchain)):
        if wanted is None:
            continue
        rows = [row for row in rows if row.get(column).casefold() == wanted.casefold()]
        if not rows:
            raise ledger.LedgerError(f"no row matches {flag} {ledger.quoted(wanted)}", capture)
    processes = _counted(rows, lambda row: (row.get("Application"), row.get("ProcessID")))
    if len(processes) > 1:
        listed = ", ".join(f"{ledger.quoted(name)} (pid {ledger.quoted(pid)}, {count} frames)"
                           for (name, pid), count in processes)
        raise ledger.LedgerError(f"the capture holds {len(processes)} processes: {listed}; pick one with "
                                 "--process or --pid", capture)
    chains = _counted(rows, lambda row: row.get("SwapChainAddress"))
    if len(chains) > 1:
        listed = ", ".join(f"{ledger.quoted(chain)} ({count} frames)" for chain, count in chains)
        raise ledger.LedgerError(f"the process holds {len(chains)} swap chains: {listed}; pick one with "
                                 "--swapchain", capture)
    return rows


def _counted(rows: list[_Row], key) -> list[tuple[object, int]]:
    """Each distinct key and its rows, most rows first, then in file order."""
    counts: dict[object, int] = {}
    for row in rows:
        counts[key(row)] = counts.get(key(row), 0) + 1
    return sorted(counts.items(), key=lambda item: -item[1])  # sorted is stable: ties keep file order


def _start_order(rows: list[_Row], columns: set[str]) -> tuple[list[ledger.Notice], list[str]]:
    """start_out_of_order when a start goes back, and the summary sentence
    when there is no start column. The rows stay in file order whatever
    this finds: PresentMon writes presents in order (DOOM Ants)."""
    column = next((name for name in START_COLUMNS if name in columns), None)
    if column is None:
        return [], ["The capture has no start column, so the order of its rows was not checked."]
    read = _date_time if column == "CPUStartDateTime" else _number
    back = []  # (the row before, the row whose start is lower)
    previous = None  # (start, row) of the last row whose start reads
    for row in rows:
        start = read(row.get(column))
        if start is None:
            continue
        if previous is not None and start < previous[0]:
            back.append((previous[1], row))
        previous = (start, row)
    if not back:
        return [], []
    before, after = back[0]
    more = f", and {len(back) - 1} more starts go back" if len(back) > 1 else ""
    late = ledger.quoted(after.get(column), ledger.LONG_QUOTE)
    early = ledger.quoted(before.get(column), ledger.LONG_QUOTE)
    return [ledger.Notice("start_out_of_order", f"line {after.line}'s {column} ({late}) is before line "
                          f"{before.line}'s ({early}){more}; the rows are kept in file order")], []


def _number(text: str | None) -> Decimal | None:
    """A capture's number, or None when the text is not one, such as NA."""
    if text is None or not NUMBER.fullmatch(text):
        return None
    try:
        return Decimal(text)
    except InvalidOperation:  # an exponent past what Decimal holds
        return None


def _date_time(text: str | None) -> tuple[datetime, Fraction] | None:
    """A CPUStartDateTime as a time to compare: in UTC when it names a
    zone, as written when not. None when it does not read. A time with a
    zone and one without are compared as if both were UTC: a capture
    mixing them is not expected, and the zone flag is not used here."""
    parsed = _parse_date_time(text or "")
    if parsed is None:
        return None
    moment, fraction, _ = parsed
    return moment, Fraction(f"0.{fraction or 0}")


def _parse_date_time(text: str) -> tuple[datetime, str, bool] | None:
    """(the whole seconds in UTC, the fraction's digits, whether a zone was
    named), or None when the text is not a date and time that exist."""
    match = DATE_TIME.fullmatch(text)
    if not match:
        return None
    date, clock, fraction, zone = match.groups()
    try:
        moment = datetime.strptime(f"{date}T{clock}", "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None
    if zone and zone != "Z":
        sign = 1 if zone[0] == "+" else -1
        offset = timedelta(hours=int(zone[1:3]), minutes=int(zone[4:6]))
        try:
            moment = moment.replace(tzinfo=timezone(sign * offset)).astimezone(timezone.utc)
        except (ValueError, OverflowError):
            return None
    return moment.replace(tzinfo=None), fraction or "", zone is not None


def _header(rows: list[_Row], columns: set[str], facts: dict, engine: str | None, started: str | None,
            version: str | None, data: bytes, capture: str) -> dict:
    """§ 4.18's header: each fact from a flag, from the capture, or a
    stand-in listed in `unknown`."""
    derived = {}
    runtimes = {row.get("PresentRuntime") for row in rows} if "PresentRuntime" in columns else set()
    if len(runtimes) == 1 and next(iter(runtimes)) not in NO_VALUE:
        derived["api"] = next(iter(runtimes)).lower()
    intervals = [_number(row.get("SyncInterval")) for row in rows] if "SyncInterval" in columns else []
    if intervals and all(value is not None for value in intervals):
        if all(value > 0 for value in intervals):
            derived["vsync"] = True
        elif all(value == 0 for value in intervals):
            derived["vsync"] = False
    known = {**derived, **facts}
    header = {"schema": ledger.SCHEMA,
              "run_id": "presentmon-" + hashlib.sha256(data).hexdigest()[:16],
              "engine": engine if engine is not None else rows[0].get("Application"),
              "tool": {"name": "PresentMon", "version": version if version is not None else "unknown"}}
    unknown = []
    for field in ledger.HEADER_FIELDS:
        if field in STAND_INS:
            if field not in known:
                unknown.append(field)
            header[field] = known.get(field, STAND_INS[field])
        elif field == "inputs":
            header["inputs"] = []
        elif field == "started_utc":
            header["started_utc"] = _started(rows, columns, started, capture)
        elif field in OPTIONAL_FACTS and field in facts:
            header[field] = facts[field]
    if unknown:
        header["unknown"] = sorted(unknown, key=ledger.UNKNOWABLE.index)
    return header


def _started(rows: list[_Row], columns: set[str], started: str | None, capture: str) -> str:
    """--started, or the first frame's CPUStartDateTime when it names its
    zone. A file's own time is not the run's, so nothing else is used."""
    if started is not None:
        try:
            ledger.start_time(started)
        except ValueError:
            raise ledger.LedgerError(f"--started {ledger.quoted(started)} must be a real UTC date and time, "
                                     "written as 2026-10-24T12:00:00Z") from None
        return started
    text = rows[0].get("CPUStartDateTime") if "CPUStartDateTime" in columns else None
    parsed = _parse_date_time(text or "")
    if parsed is None or not parsed[2]:
        said = "has no CPUStartDateTime" if text is None else \
            f"starts at CPUStartDateTime {ledger.quoted(text, ledger.LONG_QUOTE)}, which names no time zone"
        raise ledger.LedgerError(f"the capture {said}, so the run's start in UTC is unknown; give --started",
                                 capture)
    moment, fraction, _ = parsed
    fraction = fraction[:ledger.DIGITS_MAX]
    return f"{moment:%Y-%m-%dT%H:%M:%S}{'.' + fraction if fraction else ''}Z"


def _run_lines(rows: list[_Row], columns: set[str], header: dict,
               capture: str) -> tuple[list[str], int | None, dict[str, int] | None]:
    """The run file's lines; how many frames were not displayed (None
    without a DisplayedTime column); and each FrameType other than
    Application with its frame count, most first (None without a
    FrameType column). Frame i's wall is row i + 1's MsBetweenPresents,
    which counts from the present before it."""
    run_id = header["run_id"]
    lines = [f"# frameledger {json.dumps(header, separators=(',', ':'))}", ledger.COLUMNS]
    displayed = "DisplayedTime" in columns
    typed = "FrameType" in columns
    not_displayed = 0
    generated: dict[str, int] = {}
    for frame, row in enumerate(rows):
        cpu = _value(row, "MsCPUBusy", capture)
        if cpu is None:
            raise ledger.LedgerError(f"MsCPUBusy is {ledger.quoted(row.get('MsCPUBusy'))}, not a number, so "
                                     "the frame has no frame/cpu_span", capture, row.line)
        lines.append(f"{run_id},,{frame},frame,cpu_span,0,{cpu:f}")
        gpu = _value(row, "MsGPUBusy", capture) if "MsGPUBusy" in columns else None
        if gpu is not None:
            lines.append(f"{run_id},,{frame},frame,gpu_span,0,{gpu:f}")
        # A wall of zero or less is left out, and § 4.4 warns wall_missing.
        wall = _value(rows[frame + 1], "MsBetweenPresents", capture) if frame + 1 < len(rows) else None
        if wall is not None and wall > 0:
            lines.append(f"{run_id},,{frame},frame,wall,0,{wall:f}")
        if displayed and row.get("DisplayedTime") == "NA":
            lines.append(f"{run_id},,{frame},event,not_displayed,0,1.000")
            not_displayed += 1
        frame_type = row.get("FrameType")
        # Matched as written, so a blank or NA FrameType is generated too, unlike
        # NO_VALUE elsewhere: § 4.18 marks anything but Application (FLED-0075).
        if typed and frame_type != APPLICATION:
            lines.append(f"{run_id},,{frame},event,generated,0,1.000")
            generated[frame_type] = generated.get(frame_type, 0) + 1
    lines.append(f'# frameledger-close {{"rows_dropped":0,"frames":{len(rows)}}}')
    by_count = dict(sorted(generated.items(), key=lambda item: (-item[1], item[0])))
    return lines, not_displayed if displayed else None, by_count if typed else None


def _value(row: _Row, column: str, capture: str) -> Decimal | None:
    """The column's value in thousandths, rounded half away from zero from
    its decimal text; None when it is not a number."""
    number = _number(row.get(column))
    if number is None:
        return None
    # The size is checked before and after rounding: quantize raises on a
    # number too long for Decimal's precision, and 999999999.9996 rounds up.
    value = None if abs(number) >= TOO_LARGE else number.quantize(THOUSANDTH, rounding=ROUND_HALF_UP)
    if value is None or abs(value) >= TOO_LARGE:
        raise ledger.LedgerError(f"{column} is {ledger.quoted(row.get(column))}, and a run holds values below "
                                 "1000000000 ms", capture, row.line)
    return abs(value) if value == 0 else value  # never -0.000


def _exists(path: str) -> ledger.LedgerError:
    return ledger.LedgerError("the file exists, and an import never overwrites a run", path)


def write_atomically(path: str, text: str, place: Callable[[str, str], None] | None = None) -> None:
    """Write `path` through a temporary file beside it, so a failure leaves
    no half file, and `path` as it was. `place` puts the temporary file at
    `path`. An import leaves it out and the file is linked, which fails if
    `path` appeared meanwhile, where a rename would overwrite it; the
    picture report's page passes os.replace, since it overwrites (§ 4.21)."""
    folder = os.path.dirname(os.path.abspath(path))
    try:
        handle, temporary = tempfile.mkstemp(dir=folder, prefix=".frameledger-")
    except OSError as error:
        raise ledger.LedgerError(error.strerror or "cannot be written", path) from error
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        os.chmod(temporary, 0o666 & ~_umask())  # mkstemp's 0600, made what open() would give
        (place or _link)(temporary, path)
    except OSError as error:
        raise ledger.LedgerError(error.strerror or "cannot be written", path) from error
    finally:
        if os.path.lexists(temporary):
            os.unlink(temporary)


def _link(temporary: str, path: str) -> None:
    """Put `temporary` at `path`, never over a file there. A file system
    with no hard links falls back to a rename after one more look."""
    try:
        os.link(temporary, path)
    except FileExistsError:
        raise _exists(path) from None
    except OSError:
        if os.path.lexists(path):
            raise _exists(path) from None
        os.replace(temporary, path)


def _umask() -> int:
    mask = os.umask(0)
    os.umask(mask)
    return mask
