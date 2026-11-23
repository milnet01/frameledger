"""FLED-0047: broken run files never crash the reader.

Each case is a fixture run file broken at random, with a fixed seed so a
failure comes back the same. `check` reads it as ledger.read does, then
under --strict asks strict.warnings for its warnings; each step must end
in a Run, or a LedgerError for a file that cannot be judged, and never
in any other exception.
"""

import random
from pathlib import Path

import pytest

import ledger
import strict

FIXTURES = Path(__file__).parent / "fixtures"
SEEDS = sorted(FIXTURES.rglob("*.csv"))
BLOCKS, PER_BLOCK = 8, 500

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
]


def _flip(rng, data):
    if not data:
        return bytes([rng.randrange(256)])
    at = rng.randrange(len(data))
    return data[:at] + bytes([data[at] ^ (1 << rng.randrange(8))]) + data[at + 1:]


def _insert(rng, data):
    at = rng.randrange(len(data) + 1)
    return data[:at] + bytes(rng.randrange(256) for _ in range(rng.randint(1, 16))) + data[at:]


def _cut(rng, data):
    if not data:
        return data
    start = rng.randrange(len(data))
    return data[:start] + data[start + rng.randint(1, 64):]


def _truncate(rng, data):
    return data[:rng.randrange(len(data) + 1)]


def _lines(rng, data):
    """Drop, repeat or swap whole lines, as a bad merge or a crash would."""
    lines = data.split(b"\n")
    i, j = rng.randrange(len(lines)), rng.randrange(len(lines))
    how = rng.randrange(3)
    if how == 0:
        del lines[i]
    elif how == 1:
        lines.insert(j, lines[i])
    else:
        lines[i], lines[j] = lines[j], lines[i]
    return b"\n".join(lines)


def _field(rng, data):
    """Put an awkward value in place of one comma-separated field, or one
    JSON value, on a random line."""
    lines = data.split(b"\n")
    i = rng.randrange(len(lines))
    separator = rng.choice([b",", b":"])
    parts = lines[i].split(separator)
    parts[rng.randrange(len(parts))] = rng.choice(AWKWARD)
    lines[i] = separator.join(parts)
    return b"\n".join(lines)


def _noise(rng, data):
    return bytes(rng.randrange(256) for _ in range(rng.randint(0, 512)))


MUTATIONS = [_flip, _insert, _cut, _truncate, _lines, _field, _noise]


def broken(case: int) -> tuple[str, bytes]:
    """Case `case`: the fixture it starts from, broken one to four times."""
    rng = random.Random(case)
    source = rng.choice(SEEDS)
    data = source.read_bytes()
    for _ in range(rng.randint(1, 4)):
        data = rng.choice(MUTATIONS)(rng, data)
    return source.name, data


def _conforms(path: Path) -> bool:
    try:
        return not ledger.read(path).breaches
    except ledger.LedgerError:  # schema-99.csv is newer than this reader
        return False


def test_seeds_are_run_files():
    """The cases start from real run files, so most reach past the header."""
    assert len(SEEDS) > 10
    assert sum(map(_conforms, SEEDS)) > 10


@pytest.mark.parametrize("block", range(BLOCKS))
def test_broken_files_never_crash(block):
    """Every broken file gives a Run, with any breaches listed, or a
    LedgerError; strict.warnings then finishes on every Run."""
    for case in range(block * PER_BLOCK, (block + 1) * PER_BLOCK):
        source, data = broken(case)
        try:
            run = ledger.read_bytes(data, "fuzz.csv")
        except ledger.LedgerError:
            continue
        except Exception as error:
            pytest.fail(f"case {case}, from {source}: read_bytes raised {error!r} on {data[:300]!r}")
        try:
            strict.warnings(run)
        except Exception as error:
            pytest.fail(f"case {case}, from {source}: strict.warnings raised {error!r} on {data[:300]!r}")
