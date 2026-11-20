"""The format stability promise: files a release read are read the same
for ever.

Invariants from docs/specs/FLED-0040-format-stability-promise.md § 5.
Every INV below is that spec's, not FLED-0001's.

The files under tests/fixtures/frozen/ are never edited (§ 4.8). A test
that fails here is fixed in the reader, or by a new schema, never by
changing a frozen file or its stored values.
"""

import hashlib
import json
from pathlib import Path

import pytest

import baseline
import budgeting
import cli
import ledger

FROZEN = Path(__file__).parent / "fixtures" / "frozen"
RUN = FROZEN / "run-schema-1.csv"
BOM = b"\xef\xbb\xbf"


def stored(path):
    """The values kept beside a frozen file when it was frozen."""
    return json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))


def values(run):
    """A read run in the stored form (§ 4.8): the three objects, and every
    row in file order."""
    rows = sorted((row for frame in run.frames.values() for row in frame.values()), key=lambda row: row.line)
    return {
        "header": run.header,
        "static": run.static,
        "close": run.close,
        "rows": [[r.segment, r.frame, r.category, r.name, r.depth, r.thousandths] for r in rows],
    }


def check(capsys, path):
    """`check --json PATH`, without --strict: its exit code and result."""
    code = cli.main(["check", "--json", str(path)])
    out = json.loads(capsys.readouterr().out)
    assert out["exit_code"] == code
    return code, out


def breaches(out):
    return [(b["line"], b["rule"]) for b in out["result"]["files"][0]["breaches"]]


def changed(tmp_path, old, new, count=1):
    """A copy of the frozen run file with `old` replaced by `new`, which
    must occur `count` times."""
    data = RUN.read_bytes()
    assert data.count(old) == count, f"{old!r} is in the frozen file {data.count(old)} times, not {count}"
    path = tmp_path / "changed.csv"
    path.write_bytes(data.replace(old, new))
    return path


def frozen_runs():
    return sorted(FROZEN.glob("run-*.csv"))


@pytest.mark.parametrize("path", frozen_runs(), ids=lambda path: path.name)
def test_run_file_reads_the_same(capsys, path):
    """INV-1: every frozen run file passes check with no breach, and reads
    to the values stored beside it."""
    code, out = check(capsys, path)
    assert (code, out["verdict"]) == (0, "pass")
    assert breaches(out) == []
    assert values(ledger.read(path)) == stored(path)


def test_frozen_run_files_are_found():
    """INV-1's guard: the parametrised test above has files to run on."""
    assert RUN in frozen_runs()


def test_budget_and_baseline_read_the_same():
    """INV-2: the frozen budget and baseline files are accepted, and their
    readers give the stored values."""
    path = FROZEN / "budget-schema-1.csv"
    budget = budgeting.read(path)
    assert {
        "match": budget.match,
        "budgets": [[b.category, b.name, b.kind, b.depth, b.statistic, b.limit] for b in budget.budgets],
    } == stored(path)

    path = FROZEN / "baseline-schema-1.txt"
    runs = baseline.read(str(path))
    assert {"runs": [Path(run).relative_to(FROZEN.resolve()).as_posix() for run in runs]} == stored(path)


def test_frozen_files_unchanged():
    """INV-3: each frozen file's SHA-256 is its line in SHA256SUMS, and
    SHA256SUMS lists every frozen file."""
    listed = {}
    for line in (FROZEN / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ")
        listed[name] = digest
    present = {path.name for path in FROZEN.iterdir()} - {"SHA256SUMS"}
    assert present == set(listed)
    for name, digest in listed.items():
        assert hashlib.sha256((FROZEN / name).read_bytes()).hexdigest() == digest, name


@pytest.mark.parametrize("module, name", [
    (ledger, "run-schema-{}.csv"),
    (budgeting, "budget-schema-{}.csv"),
    (baseline, "baseline-schema-{}.txt"),
], ids=["run", "budget", "baseline"])
def test_every_schema_is_frozen(module, name):
    """INV-4: every schema number up to the reader's own has a frozen file
    of exactly this name."""
    assert module.SCHEMA >= 1
    for number in range(1, module.SCHEMA + 1):
        assert (FROZEN / name.format(number)).is_file(), name.format(number)


def test_newer_schema_is_judged_from_line_1(capsys, tmp_path):
    """INV-5: a file of a newer schema is exit 3 naming both versions, and
    none of its lines is judged by schema 1's rules."""
    path = tmp_path / "newer.csv"
    path.write_text('# frameledger {"schema":99,"run_id":5,"laid_out":"another way"}\n'
                    "frame;wall;16.0\n"
                    "# frameledger-end\n", encoding="utf-8")
    code, out = check(capsys, path)
    assert (code, out["verdict"]) == (3, "error")
    assert "schema 99" in out["summary"][0]
    assert "schema 1" in out["summary"][0]
    assert "breaks the run-file format" not in " ".join(out["summary"])


FUTURE_FIELD = (b'{"schema":1,', b'{"schema":1,"future_field":{"a":1},')
FUTURE_CLOSE_KEY = (b'{"rows_dropped":0,"frames":6}', b'{"rows_dropped":0,"frames":6,"future_key":"x"}')
FUTURE_EVENT = (b"\n# frameledger-close", b"\nfrozen-1,view:1,99999999999999999994,event,future_event,0,1.000"
                                          b"\n# frameledger-close")
FUTURE_FRAME_NAME = (b"\n# frameledger-close", b"\nfrozen-1,view:1,99999999999999999994,frame,future_wait,0,1.000"
                                               b"\n# frameledger-close")
FUTURE_KIND = (b",move:1-2,", b",zone:1-2,")
ADDITIONS = {
    "header field": [FUTURE_FIELD],
    "close-line key": [FUTURE_CLOSE_KEY],
    "event name": [FUTURE_EVENT],
    "frame name": [FUTURE_FRAME_NAME],
    "segment kind": [FUTURE_KIND],
    "all five": [FUTURE_FIELD, FUTURE_CLOSE_KEY, FUTURE_EVENT, FUTURE_FRAME_NAME, FUTURE_KIND],
}


@pytest.mark.parametrize("edits", ADDITIONS.values(), ids=list(ADDITIONS))
def test_additions_do_not_break_the_reader(capsys, tmp_path, edits):
    """INV-6: what § 4.4 lets a later release add is no breach to this
    reader, and every other value reads as stored."""
    data = RUN.read_bytes()
    for old, new in edits:
        assert old in data, old
        data = data.replace(old, new)
    path = tmp_path / "added.csv"
    path.write_bytes(data)

    code, out = check(capsys, path)
    assert (code, out["verdict"]) == (0, "pass")
    assert breaches(out) == []

    read = values(ledger.read(path))
    read["header"].pop("future_field", None)
    read["close"].pop("future_key", None)
    read["rows"] = [[row[0].replace("zone:", "move:"), *row[1:]] for row in read["rows"]
                    if not row[3].startswith("future_")]
    assert read == stored(RUN)


@pytest.mark.parametrize("schema", [b"0", b"1.5", b"true"])
def test_a_schema_that_is_no_schema(capsys, tmp_path, schema):
    """INV-7: a `schema` that is not a whole number, 1 or more, is a
    breach of line 1, never read as schema 1."""
    path = changed(tmp_path, b'{"schema":1,', b'{"schema":' + schema + b",")
    code, out = check(capsys, path)
    assert (code, out["verdict"]) == (1, "fail")
    assert breaches(out) == [(1, "header")]


def test_byte_order_mark_is_skipped(capsys, tmp_path):
    """INV-8: a byte-order mark before the keyword changes nothing."""
    path = tmp_path / "marked.csv"
    path.write_bytes(BOM + RUN.read_bytes())
    code, out = check(capsys, path)
    assert (code, out["verdict"]) == (0, "pass")
    assert breaches(out) == []
    assert values(ledger.read(path)) == stored(RUN)
