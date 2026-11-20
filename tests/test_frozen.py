"""The format stability promise: files a release read are read the same
for ever.

Invariants from docs/specs/FLED-0040-format-stability-promise.md § 5.
Every INV below is that spec's, not FLED-0001's.

The files under tests/fixtures/frozen/ are never edited (§ 4.8). A test
that fails here is fixed in the reader, or by a new schema, never by
changing a frozen file or its stored values. scripts/freeze.py adds a
new frozen file; its docstring says how.

Adding schema 2: freeze its files, then give INV-6 to INV-8 a schema 2
form here. Those three build their cases by editing schema 1's bytes, so
they say nothing about another schema until someone writes its cases.
"""

import importlib.util
import json
import shutil
from pathlib import Path

import pytest

import baseline
import budgeting
import cli
import compare
import ledger

ROOT = Path(__file__).parent.parent
FROZEN = ROOT / "tests" / "fixtures" / "frozen"
RUN = FROZEN / "run-schema-1.csv"
BUDGET = FROZEN / "budget-schema-1.csv"
BASELINE = FROZEN / "baseline-schema-1.txt"
BOM = b"\xef\xbb\xbf"


def load_script(name):
    """A scripts/ module; scripts/ is not on the import path, which is the analyser's."""
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


freeze = load_script("freeze")  # values(path): a file in the stored form; same(a, b): equal, types included


def stored(path):
    """The values kept beside a frozen file when it was frozen."""
    return json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))


def check(capsys, path):
    """`check --json PATH`, without --strict: its exit code and result."""
    code = cli.main(["check", "--json", str(path)])
    out = json.loads(capsys.readouterr().out)
    assert out["exit_code"] == code
    return code, out


def breaches(out):
    return [(b["line"], b["rule"]) for b in out["result"]["files"][0]["breaches"]]


def with_schema(tmp_path, source, schema):
    """A copy of a frozen schema 1 file whose line 1 holds `schema`
    instead of 1."""
    data = source.read_bytes()
    assert data.count(b'{"schema":1,') == 1
    path = tmp_path / source.name
    path.write_bytes(data.replace(b'{"schema":1,', b'{"schema":' + schema + b","))
    return path


def frozen(glob):
    return sorted(FROZEN.glob(glob))


@pytest.mark.parametrize("path", frozen("run-*.csv"), ids=lambda path: path.name)
def test_run_file_reads_the_same(capsys, path):
    """INV-1: every frozen run file passes check with no breach, and reads
    to the values stored beside it."""
    code, out = check(capsys, path)
    assert (code, out["verdict"]) == (0, "pass")
    assert breaches(out) == []
    assert freeze.same(freeze.values(path), stored(path))


@pytest.mark.parametrize("path", [*frozen("budget-*.csv"), *frozen("baseline-*.txt")], ids=lambda path: path.name)
def test_budget_and_baseline_read_the_same(path):
    """INV-2: every frozen budget and baseline file is accepted, and its
    reader gives the stored values."""
    assert freeze.same(freeze.values(path), stored(path))


def test_budget_command_takes_the_frozen_budget(capsys):
    """INV-2 through a command: `budget` exits 0, 1 or 2 on the frozen
    files, never 3, which is an error in a file."""
    code = cli.main(["budget", "--json", str(RUN), "--budgets", str(BUDGET), "--all-frames"])
    capsys.readouterr()
    assert code in (0, 1, 2)


def test_frozen_files_are_found():
    """INV-1 and INV-2's guard: the parametrised tests above have files to
    run on, and no frozen file is held by its name alone."""
    assert RUN in frozen("run-*.csv")
    assert BUDGET in frozen("budget-*.csv")
    assert BASELINE in frozen("baseline-*.txt")
    for path in [*frozen("*.csv"), *frozen("*.txt")]:
        assert path.with_suffix(".json").is_file(), f"{path.name} has no stored values; run scripts/freeze.py"


def test_frozen_files_unchanged():
    """INV-3: each frozen file's SHA-256 is its line in SHA256SUMS, and
    SHA256SUMS lists every frozen file."""
    listed = freeze.read_sums(FROZEN)
    present = {path.name for path in FROZEN.iterdir()} - {freeze.SUMS}
    assert present == set(listed)
    for name, digest in listed.items():
        assert freeze.digest_of(FROZEN / name) == digest, name


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
    none of its lines is judged by this reader's rules."""
    path = tmp_path / "newer.csv"
    path.write_text('# frameledger {"schema":99,"run_id":5,"laid_out":"another way"}\n'
                    "frame;wall;16.0\n"
                    "# frameledger-end\n", encoding="utf-8")
    code, out = check(capsys, path)
    assert (code, out["verdict"]) == (3, "error")
    assert "schema 99" in out["summary"][0]
    assert f"schema {ledger.SCHEMA}" in out["summary"][0]  # this reader's own, whichever it is by then
    assert out["result"]["files"] == []  # no file is judged, so no breach is listed


# INV-6's cases: (bytes in the frozen run file, what replaces them). Each
# is something § 4.4 lets a later release add to schema 1. A new row goes
# in just before the close line, on the frozen file's first frame.
FRAME = b"frozen-1,view:1,99999999999999999994"
CLOSE = b"\n# frameledger-close"


def rows_before_close(*rows):
    return CLOSE, b"".join(b"\n" + FRAME + b"," + row for row in rows) + CLOSE


HEADER_FIELD = (b'{"schema":1,', b'{"schema":1,"future_field":{"a":1},')
CLOSE_KEY = (b'{"rows_dropped":0,"frames":6}', b'{"rows_dropped":0,"frames":6,"future_key":"x"}')
INNER_KEY = (b'"tool":{"name":"bench","version":"1.0"}', b'"tool":{"name":"bench","version":"1.0","future_in":1}')
SEGMENT_KIND = (b",move:1-2,", b",zone:1-2,")
EVENT_NAME = rows_before_close(b"event,future_event,0,1.000")
FRAME_NAME = rows_before_close(b"frame,future_wait,0,1.000")
OPEN_NAMES = rows_before_close(b"cpu,future_pass,0,1.000", b"gpu,future_pass,0,1.000", b"mem,future_mb,0,1.000",
                               b"ext.future,future_own,0,1.000")
ADDITIONS = {
    "header field": [HEADER_FIELD],
    "close-line key": [CLOSE_KEY],
    "key inside a header object": [INNER_KEY],
    "segment kind": [SEGMENT_KIND],
    "event name": [EVENT_NAME],
    "frame name": [FRAME_NAME],
    "cpu, gpu, mem and ext names": [OPEN_NAMES],
    "all of them": [HEADER_FIELD, CLOSE_KEY, INNER_KEY, SEGMENT_KIND, EVENT_NAME, FRAME_NAME, OPEN_NAMES],
}


def without_additions(read):
    """`read` with every addition above taken out again, to compare with
    the stored values."""
    read["header"].pop("future_field", None)
    read["header"]["tool"].pop("future_in", None)
    read["close"].pop("future_key", None)
    read["rows"] = [[segment.replace("zone:", "move:"), frame, category, name, depth, value]
                    for segment, frame, category, name, depth, value in read["rows"]
                    if not name.startswith("future_")]
    return read


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
    assert freeze.same(without_additions(freeze.run_values(path)), stored(RUN))


NO_SCHEMA = [b"0", b"1.5", b"true", b"1.0", b"1e0", b'"1"']


@pytest.mark.parametrize("schema", NO_SCHEMA)
def test_a_schema_that_is_no_schema(capsys, tmp_path, schema):
    """INV-7: a `schema` that is not a whole number written in digits, 1
    or more, is a breach of line 1, never read as schema 1."""
    code, out = check(capsys, with_schema(tmp_path, RUN, schema))
    assert (code, out["verdict"]) == (1, "fail")
    assert breaches(out) == [(1, "header")]


@pytest.mark.parametrize("schema", [*NO_SCHEMA, b"99"])
@pytest.mark.parametrize("source, read", [(BUDGET, budgeting.read), (BASELINE, baseline.read)],
                         ids=["budget", "baseline"])
def test_budget_and_baseline_refuse_another_schema(tmp_path, source, read, schema):
    """INV-7's other half, and § 4.7: a budget or baseline file whose
    `schema` is none, or is one this reader does not read, is an error."""
    with pytest.raises(ledger.LedgerError, match="schema must be"):  # not a path that holds the word
        read(str(with_schema(tmp_path, source, schema)))


def test_byte_order_mark_is_skipped(capsys, tmp_path):
    """INV-8: a byte-order mark before the keyword changes nothing, in a
    run, budget or baseline file."""
    for path in [*frozen("run-*.csv"), BUDGET, BASELINE]:  # the baseline's runs must sit beside it
        shutil.copy(path, tmp_path / path.name)
    for source in (RUN, BUDGET, BASELINE):
        marked = tmp_path / source.name
        marked.write_bytes(BOM + source.read_bytes())
        assert freeze.same(freeze.values(marked), stored(source)), source.name

    code, out = check(capsys, tmp_path / RUN.name)
    assert (code, out["verdict"]) == (0, "pass")
    assert breaches(out) == []


BLOCKING_AT_FREEZE = ("resolution", "render_scale", "tier", "ray_tracing", "build_type", "inputs", "display",
                      "api", "device", "vsync", "scene")
FEWEST_RUNS_AT_FREEZE = 3


def test_rules_frozen_with_schema_1():
    """INV-9: what a schema 1 budget file may match on does not shrink,
    and the runs a schema 1 baseline file needs do not rise."""
    assert set(BLOCKING_AT_FREEZE) <= set(compare.BLOCKING)
    assert baseline.FEWEST_RUNS <= FEWEST_RUNS_AT_FREEZE


def copy_of_frozen(tmp_path):
    folder = tmp_path / "frozen"
    shutil.copytree(FROZEN, folder)
    return folder


def test_freeze_adds_nothing_to_a_frozen_folder(tmp_path):
    """scripts/freeze.py on the folder as committed changes no byte."""
    folder = copy_of_frozen(tmp_path)
    assert freeze.freeze(folder) == []
    assert freeze.read_sums(folder) == freeze.read_sums(FROZEN)


def test_freeze_writes_the_stored_values_again(tmp_path):
    """Each committed `.json` is what freeze.py writes for its file."""
    folder = copy_of_frozen(tmp_path)
    (folder / freeze.SUMS).unlink()
    kept = sorted(folder.glob("*.json"))
    for path in kept:
        path.unlink()
    freeze.freeze(folder)
    for path in kept:
        assert path.read_bytes() == (FROZEN / path.name).read_bytes(), path.name


@pytest.mark.parametrize("damage", ["edit", "remove"])
def test_freeze_refuses_a_changed_frozen_file(tmp_path, damage):
    """freeze.py stops, writing nothing, when a listed file was edited or
    removed: it never re-freezes over a change."""
    folder = copy_of_frozen(tmp_path)
    victim = folder / "run-schema-1-b.csv"
    if damage == "edit":
        victim.write_bytes(victim.read_bytes().replace(b"8.000", b"8.001", 1))
    else:
        victim.unlink()
    shutil.copy(folder / "run-schema-1-c.csv", folder / "run-schema-1-new.csv")  # something a freeze would add
    before = (folder / freeze.SUMS).read_bytes()
    with pytest.raises(ledger.LedgerError, match="never"):
        freeze.freeze(folder)
    assert (folder / freeze.SUMS).read_bytes() == before
    assert not (folder / "run-schema-1-new.json").exists()
