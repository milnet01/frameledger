"""FLED-0047: broken run files never crash the reader.

Each case is a fixture run file broken at random. ledger.read_bytes must
give a Run, or a LedgerError for a file that cannot be judged, and
strict.warnings must then finish on the Run, as `check --strict` asks of
both. A broken file that still conforms is also put through `report`
and `floor`, whose analysis is where an empty list or a zero divisor
would end in a traceback. Any other exception fails the case.

A case number names the same bytes on every Python version: every draw
comes from Random.random(), the one method whose sequence Python keeps
across versions. It holds only for the same fixture files and the same
MUTATIONS list: adding or removing either changes what every case number
means. broken(N) rebuilds case N as (fixture name, mutations, bytes).

A case has no time limit: a reader grown slow shows as a slow suite,
not a failure.

FLED_FUZZ_CASES runs more cases than the gate's, for a longer run before
a release: FLED_FUZZ_CASES=200000 pytest tests/test_fuzz.py.
"""

import os
import random
import re
from pathlib import Path

import pytest

import cli
import ledger
import strict

FIXTURES = Path(__file__).parent / "fixtures"
# The run files each case breaks; the frozen budget files are another format.
STARTS = sorted(path for path in FIXTURES.rglob("*.csv") if not path.name.startswith("budget-"))
BLOCKS = 8  # a failure stops only its own block, so one run can show several
PER_BLOCK = int(os.environ.get("FLED_FUZZ_CASES", "4000")) // BLOCKS

# Text a writer or an editor could leave in a field: numbers too long,
# too large or not numbers, JSON that is no object, nesting past what
# json.loads can follow, quotes, separators and characters past ASCII.
AWKWARD = [
    b"", b"0", b"-0.000", b"0.000", b"-1.000", b"1.0", b"1.0000", b"9" * 21, b"9" * 5000,
    b"1" * 20 + b".000", b"1e999", b"NaN", b"Infinity", b"-Infinity", b"0x10", b"\xe2\x80\x8b1.000",
    b"null", b"true", b"[]", b"{}", b'""', b"[" * 100_000, b'{"a":' * 3000, b'"', b'""""', b",",
    b'"a,b"', b"#", b"\r", b"\x00", b"\xff\xfe", b"\xef\xbb\xbf", b"\xc3\xa9", b"\xf0\x9f\x98\x80",
    b"frame", b"wall", b"cpu_span", b"ext.", b"ext.x", b"9999-99-99T99:99:99Z", b"0000-01-01T00:00:00Z",
    b'{"schema":1}', b'{"schema":99}', b'{"schema":1e400}', b'{"schema":' + b"9" * 400 + b"}",
    b'{"rows_dropped":-1,"frames":0}', b'{"rows_dropped":' + b"9" * 400 + b',"frames":0}',
    b'"' + b"x" * 140_000 + b'"',  # past the csv module's field limit (ExperiRays)
]
CONFLICT = [b"<<<<<<< HEAD", b"=======", b">>>>>>> other-branch"]


class Draws:
    """Random choices built from Random.random() alone, so a case's bytes
    are the same on every Python version."""

    def __init__(self, case: int):
        self._random = random.Random(case)

    def below(self, n: int) -> int:
        return int(self._random.random() * n)

    def between(self, low: int, high: int) -> int:
        return low + self.below(high - low + 1)

    def pick(self, items):
        return items[self.below(len(items))]

    def noise(self, most: int) -> bytes:
        return bytes(self.below(256) for _ in range(self.between(0, most)))


def _flip(draw, data):
    if not data:
        return bytes([draw.below(256)])
    at = draw.below(len(data))
    return data[:at] + bytes([data[at] ^ (1 << draw.below(8))]) + data[at + 1:]


def _insert(draw, data):
    at = draw.below(len(data) + 1)
    return data[:at] + draw.noise(16) + data[at:]


def _cut(draw, data):
    if not data:
        return data
    start = draw.below(len(data))
    return data[:start] + data[start + draw.between(1, 64):]


def _truncate(draw, data):
    return data[:draw.below(len(data) + 1)]


def _zero_tail(draw, data):
    """A power loss can leave the file at its new length with zeros where
    the last writes never landed: zeros after a cut, or over the end
    (Vestige, UT Ants)."""
    zeros = b"\x00" * draw.between(1, 8192)
    if draw.below(2):
        return _truncate(draw, data) + zeros
    return data[:max(0, len(data) - len(zeros))] + zeros[:len(data)]


def _lines(draw, data):
    """Drop, repeat or swap whole lines, as a bad merge or a crash would."""
    lines = data.split(b"\n")
    i, j = draw.below(len(lines)), draw.below(len(lines))
    how = draw.below(3)
    if how == 0:
        del lines[i]
    elif how == 1:
        lines.insert(j, lines[i])
    else:
        lines[i], lines[j] = lines[j], lines[i]
    return b"\n".join(lines)


def _conflict(draw, data):
    """Merge-conflict markers between rows (Vestige)."""
    lines = data.split(b"\n")
    for marker in reversed(CONFLICT):
        lines.insert(draw.below(len(lines) + 1), marker)
    return b"\n".join(lines)


def _line_ends(draw, data):
    """Every line end, or every other one, rewritten as an editor or git
    would: CRLF, CRLF converted twice, or a bare CR (Vestige, DOOM Ants)."""
    lines = data.split(b"\n")
    end = draw.pick([b"\r\n", b"\r\r\n", b"\r"])
    step = draw.pick([1, 2])
    return b"".join(line + (end if i % step == 0 else b"\n") for i, line in enumerate(lines))


def _encoding(draw, data):
    """A byte-order mark before the file, or the whole file saved as
    UTF-16, as a Windows editor does (Vestige)."""
    if draw.below(2):
        return b"\xef\xbb\xbf" + data
    return data.decode("utf-8", "replace").encode(draw.pick(["utf-16", "utf-16-le"]))


def _two_runs(draw, data):
    """A second run file joined into this one, as `cat a b` or a writer
    that appends would leave it (Vestige)."""
    other = draw.pick(STARTS).read_bytes()
    at = draw.pick([len(data), data.find(b"\n# frameledger-close ") + 1 or len(data)])
    return data[:at] + other + data[at:]


def _rewritten(draw, data):
    """A stretch of the file written twice, as a short write retried
    whole would leave it (DOOM Ants)."""
    if not data:
        return data
    start = draw.below(len(data))
    end = start + draw.between(1, 512)
    return data[:end] + data[start:end] + data[end:]


def _deep_json(draw, data):
    """One string value on the header or static line replaced by a value
    nested hundreds deep: still JSON, so it gets past the parser to
    whatever walks it next (ExperiRays)."""
    lines = data.split(b"\n")
    json_lines = [i for i, line in enumerate(lines) if line.startswith(b"# frameledger")]
    if not json_lines:
        return data
    i = draw.pick(json_lines)
    values = list(re.finditer(rb':"[^"]*"', lines[i]))
    if not values:
        return data
    value = draw.pick(values)
    depth = draw.between(100, 2000)
    lines[i] = lines[i][:value.start()] + b":" + b"[" * depth + b'"1"' + b"]" * depth + lines[i][value.end():]
    return b"\n".join(lines)


def _field(draw, data):
    """Put an awkward value in place of one comma-separated field, or one
    JSON value, on a random line."""
    lines = data.split(b"\n")
    i = draw.below(len(lines))
    separator = draw.pick([b",", b":"])
    parts = lines[i].split(separator)
    parts[draw.below(len(parts))] = draw.pick(AWKWARD)
    lines[i] = separator.join(parts)
    return b"\n".join(lines)


def _noise(draw, data):
    return draw.noise(512)


MUTATIONS = [_flip, _insert, _cut, _truncate, _zero_tail, _lines, _conflict, _line_ends, _encoding,
             _two_runs, _rewritten, _deep_json, _field, _noise]


def broken(case: int) -> tuple[str, list[str], bytes]:
    """Case `case`: the fixture it starts from, the mutations that broke
    it, one to four, and the bytes they left."""
    draw = Draws(case)
    start = draw.pick(STARTS)
    data, applied = start.read_bytes(), []
    for _ in range(draw.between(1, 4)):
        mutation = draw.pick(MUTATIONS)
        data = mutation(draw, data)
        applied.append(mutation.__name__)
    return start.name, applied, data


def _conforms(path: Path) -> bool:
    try:
        return not ledger.read(path).breaches
    except ledger.LedgerError:  # schema-99.csv is newer than this reader
        return False


def test_starts_are_run_files():
    """The cases start from real run files, so most reach past the header."""
    assert len(STARTS) > 10
    assert sum(map(_conforms, STARTS)) > 10


def test_a_case_is_the_same_bytes_each_time():
    """A case number rebuilds its bytes, so a failure can be run again."""
    assert broken(17) == broken(17)
    assert broken(17) != broken(18)


def test_a_byte_order_mark_still_reads():
    """§ 4.1: a byte-order mark before an intact file is skipped."""
    for start in filter(_conforms, STARTS):
        assert ledger.read_bytes(b"\xef\xbb\xbf" + start.read_bytes(), start.name).breaches == []


@pytest.mark.parametrize("block", range(BLOCKS))
def test_broken_files_never_crash(block, tmp_path, capsys):
    """Every broken file gives a Run, with any breaches listed, or a
    LedgerError; strict.warnings finishes on every Run; and `report` and
    `floor` finish on every Run that still conforms."""
    conforming = 0
    for case in range(block * PER_BLOCK, (block + 1) * PER_BLOCK):
        start, applied, data = broken(case)
        step = "read_bytes"
        try:
            run = ledger.read_bytes(data, "fuzz.csv")
            step = "strict.warnings"
            strict.warnings(run)
            if not run.breaches:
                conforming += 1
                path = tmp_path / f"case-{case}.csv"
                path.write_bytes(data)
                for argv in (["report", "--json"], ["floor", "--json", "--fps", "60"]):
                    step = argv[0]
                    cli.main([*argv, str(path)])
                capsys.readouterr()
        except ledger.LedgerError:  # from any step: cli.main says it in a sentence, exit 3
            continue
        except Exception as error:
            raise AssertionError(f"case {case}, {start} broken by {', '.join(applied)}: {step} "
                                 f"raised {error!r} on {data[:300]!r}; broken({case}) rebuilds the "
                                 "whole file") from error
    # Most cases break the format, and strict.warnings returns at once on
    # those; enough must conform for strict, report and floor to be tried.
    assert conforming >= PER_BLOCK // 100, f"only {conforming} cases conform"
