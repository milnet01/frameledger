"""`check --expect`: one run file against an expected one, by content, not
layout (docs/specs/FLED-0001-run-file-format.md § 4.19).

The header, static and close lines match when they hold equal JSON
values, so key order and spacing are the writer's. The rows match when
they are the same multiset of lines, each compared as text without its
line ending, since § 4.4's values are exact text and row order is free.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import ledger

ABSENT = object()  # a line or key the file does not have, told apart from a JSON null


@dataclass
class Lines:
    """A run file split into its parts. A JSON line that does not parse is
    kept as its text, which equals no object."""

    header: object = ABSENT
    static: object = ABSENT
    close: object = ABSENT
    rows: Counter = field(default_factory=Counter)
    order: list[str] = field(default_factory=list)  # each distinct row, first seen first


@dataclass(frozen=True)
class Difference:
    kind: str  # "header", "static", "row" or "close"
    where: str  # a header or static key, a row line, or "" for a whole line
    expected: object  # a JSON value, ABSENT, or how many times the row is there
    found: object

    def entry(self) -> dict:
        """§ 4.19's JSON entry: a key is named as `header.KEY`, a whole line
        by its part. JSON has no absent value, so an absent one is null."""
        where = self.where if self.kind == "row" else f"{self.kind}.{self.where}" if self.where else self.kind
        return {"where": where, "expected": _json_value(self.expected), "found": _json_value(self.found)}

    def sentence(self) -> str:
        if self.kind == "row":
            return (f"the row '{ledger.quoted(self.where, ledger.LONG_QUOTE)}' is there {_times(self.expected)} "
                    f"in the expected file and {_times(self.found)} in this one")
        what = f"the {self.kind} line's '{ledger.quoted(self.where)}'" if self.where else f"the {self.kind} line"
        return f"{what} is {_shown(self.expected)} in the expected file and {_shown(self.found)} in this one"


def compare(expected_path: str, path: str) -> list[Difference]:
    """Every difference, in the order a reader meets them: header, static,
    rows, close. Rows go in the expected file's order, then the rest, but
    each with any other of its frame, category and name beside it, so a
    row written wrong shows the expected line and the written one together.
    Raises LedgerError when either file cannot be read."""
    expected, found = _read(expected_path), _read(path)
    differences = _json_differences("header", expected.header, found.header)
    differences += _json_differences("static", expected.static, found.static)
    by_key: dict[tuple, list[Difference]] = {}
    for line in [*expected.order, *(line for line in found.order if line not in expected.rows)]:
        if expected.rows[line] != found.rows[line]:
            by_key.setdefault(_row_key(line), []).append(Difference("row", line, expected.rows[line],
                                                                    found.rows[line]))
    differences += [difference for group in by_key.values() for difference in group]
    if not same(expected.close, found.close):
        differences.append(Difference("close", "", expected.close, found.close))
    return differences


def first(differences: list[Difference]) -> str:
    """The first difference, as the summary names it. A row the expected
    file holds once, beside one this file holds instead for the same
    frame, category and name, is named as the one written for the other."""
    head = differences[0]
    if head.kind == "row" and len(differences) > 1:
        other = differences[1]
        if other.kind == "row" and _row_key(other.where) == _row_key(head.where) \
                and (head.expected, head.found, other.expected, other.found) == (1, 0, 0, 1):
            return (f"the expected row '{ledger.quoted(head.where, ledger.LONG_QUOTE)}' is written "
                    f"'{ledger.quoted(other.where, ledger.LONG_QUOTE)}' in this one")
    return head.sentence()


def _row_key(line: str) -> tuple:
    """A row line's frame, category and name, or the line itself when it
    does not hold seven fields."""
    fields = next(csv.reader([line]))
    return tuple(fields[2:5]) if len(fields) == 7 else (line,)


def same(a, b) -> bool:
    """Equal JSON values. A number equals another of the same value, so 1
    and 1.0 match; a boolean equals only a boolean, though Python's
    True == 1."""
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(same(a[key], b[key]) for key in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b, strict=True))
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a == b
    return type(a) is type(b) and a == b


def _json_value(value):
    return None if value is ABSENT else value


def _shown(value) -> str:
    return "missing" if value is ABSENT else ledger.quoted(json.dumps(value), ledger.LONG_QUOTE)


def _times(count: int) -> str:
    return {0: "no times", 1: "once", 2: "twice"}.get(count, f"{count} times")


def _json_differences(part: str, expected, found) -> list[Difference]:
    """One difference per top-level key whose values differ, a missing key
    or line as null. A line that is not an object differs as a whole."""
    if isinstance(expected, dict) and isinstance(found, dict):
        keys = [*expected, *(key for key in found if key not in expected)]
        return [Difference(part, key, expected.get(key, ABSENT), found.get(key, ABSENT))
                for key in keys if key not in expected or key not in found or not same(expected[key], found[key])]
    return [] if same(expected, found) else [Difference(part, "", expected, found)]


def _read(path: str) -> Lines:
    try:
        data = Path(path).read_bytes()
    except OSError as error:
        raise ledger.LedgerError(error.strerror or "cannot be read", path) from error
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]  # a byte-order mark, which check also allows
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ledger.LedgerError("is not UTF-8 text", path) from error
    lines = Lines()
    for line in text.split("\n"):
        line = line.removesuffix("\r")
        if line.startswith(ledger.HEADER) and lines.header is ABSENT:
            lines.header = _json(line[len(ledger.HEADER):])
        elif line.startswith(ledger.STATIC):
            lines.static = _json(line[len(ledger.STATIC):])
        elif line.startswith(ledger.CLOSE):
            lines.close = _json(line[len(ledger.CLOSE):])
        elif line and line != ledger.COLUMNS:
            if line not in lines.rows:
                lines.order.append(line)
            lines.rows[line] += 1
    return lines


def _json(text: str):
    try:
        return json.loads(text)
    except (ValueError, RecursionError):
        return text
