"""The JSON result schemas (docs/specs/FLED-0041-json-result-schemas.md).

INV-1, every sample's output meets the strict form of its command's
schema; INV-2, each file is a draft 2020-12 schema of the agreed kind;
INV-3, the samples show every shape and write every named key; INV-4 and
INV-10, `schema COMMAND` prints the file and takes no path; INV-5, shared
definitions agree; INV-6 and INV-7, the frozen sets; INV-8, every result
names its release; INV-9, no NaN is printed; INV-11, the strict form
refuses what it should.

The published files allow keys they do not name, so a script survives a
later release. `strict` closes them for these tests, so no key reaches a
result without being described.

Cutting a release: scripts/freeze_schemas.py, then commit
tests/fixtures/schemas/. A deliberate break goes in DELIBERATE_BREAKS.
"""

import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import jsonschema
import pytest

import cli
import schema_samples
import schemas

ROOT = Path(__file__).parent.parent
SCHEMAS = ROOT / "src" / "frameledger" / "schemas"
DIALECT = "https://json-schema.org/draft/2020-12/schema"
# Keywords whose subschemas describe an object some other schema names the
# keys of: the strict form leaves them open (§ 4.6).
CONDITIONAL = ("if", "then", "else", "allOf", "anyOf", "oneOf", "not")
FIRST_FROZEN = (0, 8, 0)  # § 4.7: from this release, every release freezes its schemas

# A break made on purpose: (frozen version, command, where, the CHANGELOG.md
# entry that names it). `where` is a key path, or `$defs/NAME` for a closed
# set. Only the listed failure is let off (§ 4.7).
DELIBERATE_BREAKS: list[tuple[str, str, str, str]] = []


def load_script(name):
    """A scripts/ module; scripts/ is not on the import path, which is the analyser's."""
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


freeze_schemas = load_script("freeze_schemas")
TREE = freeze_schemas.tree_schemas()
SAMPLE_IDS = [sample.name for sample in schema_samples.SAMPLES]


@pytest.fixture(scope="module")
def ran(tmp_path_factory):
    """Every sample, run once: {name: (exit code, standard output)}."""
    work = tmp_path_factory.mktemp("samples")
    results = {}
    for sample in schema_samples.SAMPLES:
        folder = work / sample.name
        folder.mkdir()
        results[sample.name] = schema_samples.run(sample, folder)
    return results


@pytest.fixture(scope="module")
def outputs(ran):
    return {name: json.loads(printed) for name, (_, printed) in ran.items()}


def strict(schema):
    """§ 4.6's strict form: each object closed once. A schema with
    `properties` gains `unevaluatedProperties: false` unless it sits under
    a conditional keyword, whose keys the enclosing object already counts."""
    def close(node, open_here):
        if isinstance(node, list):
            return [close(item, open_here) for item in node]
        if not isinstance(node, dict):
            return node
        closed = {}
        for key, item in node.items():
            if key in ("properties", "$defs"):  # a map of names to schemas, not a schema
                closed[key] = {name: close(sub, open_here) for name, sub in item.items()}
            else:
                closed[key] = close(item, open_here or key in CONDITIONAL)
        if "properties" in node and not open_here:
            closed["unevaluatedProperties"] = False
        return closed
    return close(schema, False)


def errors(schema, output):
    """Each way `output` fails `schema`, as (key path, message)."""
    found = jsonschema.Draft202012Validator(schema).iter_errors(output)
    return sorted((key_path(error.absolute_path), error.message) for error in found)


def key_path(parts):
    """A validator's path as keys.json writes one: result.runs[].commit."""
    path = ""
    for part in parts:
        path += "[]" if isinstance(part, int) else f".{part}" if path else part
    return path


def subschemas(node, under=()):
    """Every schema in `node`, each with the keywords it sits under."""
    if isinstance(node, list):
        for item in node:
            yield from subschemas(item, under)
    elif isinstance(node, dict):
        yield node, under
        for key, item in node.items():
            if key in ("properties", "$defs"):
                for sub in item.values():
                    yield from subschemas(sub, (*under, key))
            elif key not in ("enum", "const", "required"):
                yield from subschemas(item, (*under, key))


# ---------------------------------------------------------------- INV-1, INV-11

@pytest.mark.parametrize("name", SAMPLE_IDS)
def test_output_matches_its_schema(name, ran, outputs):
    """INV-1: the output meets the strict form, so it has no key its schema
    does not name, lacks none it requires, and each value has its type."""
    code, _ = ran[name]
    output = outputs[name]
    assert errors(strict(TREE[output["command"]]), output) == []
    assert output["exit_code"] == code


def objects(value, at=()):
    """Every object in `value`, with its path."""
    if isinstance(value, dict):
        yield at
        for key, item in value.items():
            yield from objects(item, (*at, key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from objects(item, (*at, index))


def dig(value, path):
    for part in path:
        value = value[part]
    return value


def described(schema, root, path):
    """Whether the schema names the keys of the object at `path`: false
    inside a map whose keys are data, or a value that is the engine's own."""
    for part in path:
        schema = freeze_schemas.resolved(schema, root)
        if isinstance(part, int):
            schema = schema.get("items", {})
        elif part in schema.get("properties", {}):
            schema = schema["properties"][part]
        else:
            return False
    return "properties" in freeze_schemas.resolved(schema, root)


@pytest.mark.parametrize("name", SAMPLE_IDS)
def test_strict_form_refuses_an_unknown_key(name, outputs):
    """INV-11: a key added to any object the schema describes fails the
    strict form, and passes the published one. A strict form that closed a
    `then`, or skipped a nested object, would fail one half or the other."""
    output = outputs[name]
    schema = TREE[output["command"]]
    closed = strict(schema)
    places = [path for path in objects(output) if described(schema, schema, path)]
    assert () in places
    for path in places:
        changed = copy.deepcopy(output)
        dig(changed, path)["not_in_the_schema"] = 1
        assert errors(closed, changed), f"an unknown key at {key_path(path) or 'the top'} passed"
        assert errors(schema, changed) == [], f"the published schema refused a new key at {key_path(path)}"


# Where a command's shapes differ in their keys, the verdict of one shape
# on the output of another is refused: (sample, the verdict it is given).
OTHER_SHAPE = [("report-file-unread", "none"), ("floor-file-unread", "pass"), ("budget-file-unread", "pass"),
               ("bisect-good", "skip"), ("bisect-skip-unreadable", "good"),
               ("compare-pass", "error"), ("compare-refused", "pass"), ("compare-file-unread", "pass"),
               ("alternate-stopped-exit", "pass")]


@pytest.mark.parametrize(("name", "verdict"), OTHER_SHAPE)
def test_strict_form_refuses_another_shapes_verdict(name, verdict, outputs):
    """INV-11: an `if` that never matched would let these through."""
    changed = {**outputs[name], "verdict": verdict}
    assert errors(strict(TREE[changed["command"]]), changed)


# ----------------------------------------------------------------------- INV-2

def test_schemas_names_every_file():
    """schemas.py names each command, since the .pyz cannot list a folder."""
    assert sorted(path.name for path in SCHEMAS.iterdir()) == sorted(map(freeze_schemas.file_name, schemas.COMMANDS))


@pytest.mark.parametrize("command", schemas.COMMANDS)
def test_each_file_is_a_schema(command):
    """INV-2: a valid draft 2020-12 schema that names its dialect, has no
    $id, closes no object, and whose every $ref stays inside the file,
    stands alone and sits under no conditional keyword."""
    data = (SCHEMAS / freeze_schemas.file_name(command)).read_bytes()
    assert b"\r" not in data and data.endswith(b"\n")
    schema = json.loads(data.decode("utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    assert schema["$schema"] == DIALECT
    assert schema["properties"]["command"]["const"] == command
    for node, under in subschemas(schema):
        assert "$id" not in node
        assert node.get("additionalProperties") is not False
        assert "unevaluatedProperties" not in node
        if "$ref" in node:
            assert node["$ref"].removeprefix("#/$defs/") in schema["$defs"], node["$ref"]
            assert "properties" not in node
            assert under[-1] not in CONDITIONAL, f"{node['$ref']} sits directly under {under[-1]}"
        if "enum" in node and not set(under) & set(CONDITIONAL):
            assert under[-1:] == ("$defs",) and len(under) == 1, f"the closed set {node['enum']} has no name in $defs"


@pytest.mark.parametrize("command", schemas.COMMANDS)
def test_every_named_key_is_described(command):
    """§ 4.3: every key a file names has a description."""
    schema = TREE[command]
    for node, under in subschemas(schema):
        if set(under) & set(CONDITIONAL):
            continue
        for key, sub in node.get("properties", {}).items():
            assert freeze_schemas.resolved(sub, schema).get("description"), f"{key} has no description"


# ----------------------------------------------------------------------- INV-3

def test_every_shape_has_a_sample():
    """INV-3: SHAPES lists § 4.4's table, and each entry is shown."""
    shown = {(sample.command, sample.shape) for sample in schema_samples.SAMPLES}
    assert shown == set(schema_samples.SHAPES)
    assert {command for command, _ in schema_samples.SHAPES} == set(schemas.COMMANDS)
    assert len(SAMPLE_IDS) == len(set(SAMPLE_IDS))


def test_samples_cover_the_schemas(outputs):
    """INV-3: every key a file names is written by at least one sample, so
    INV-1 checks each of them. A key of a shared definition is one key
    whichever file names it (INV-5), so any command's sample may write it:
    `kit` has no warning to show."""
    written = set().union(*(freeze_schemas.key_paths(output, TREE[output["command"]], TREE[output["command"]],
                                                     output["command"], by_definition=True)
                            for output in outputs.values()))
    named = set().union(*(freeze_schemas.named_paths(schema, schema, command, by_definition=True)
                          for command, schema in TREE.items()))
    assert sorted(named - written) == []


# ------------------------------------------------------------- INV-4, INV-10

def run_frameledger(target, *args):
    return subprocess.run([sys.executable, "-I", str(target), *args], capture_output=True)


def build(tmp_path):
    done = subprocess.run([sys.executable, "-I", str(ROOT / "scripts" / "build_release.py"), str(tmp_path), "v9.9.9"],
                          capture_output=True, text=True, check=True)
    return Path(done.stdout.split()[0])


@pytest.fixture(scope="module")
def release(tmp_path_factory):
    return build(tmp_path_factory.mktemp("release"))


@pytest.mark.parametrize("command", schemas.COMMANDS)
def test_schema_command_prints_the_file(command, release):
    """INV-4: the file's bytes, from the tree and from the .pyz; --json and
    --markdown change nothing."""
    wanted = (SCHEMAS / freeze_schemas.file_name(command)).read_bytes()
    for target in (ROOT / "src" / "frameledger", release.parent / "frameledger.pyz"):
        for flags in ((), ("--json",), ("--markdown",)):
            done = run_frameledger(target, "schema", command, *flags)
            assert (done.returncode, done.stdout, done.stderr) == (0, wanted, b"")


@pytest.mark.parametrize("name", [None, "schema", "nothing", "../cli.py", "check.schema.json", "kit/README.txt",
                                  str(SCHEMAS / "check.schema.json")])
def test_schema_command_takes_a_name_not_a_path(name, release):
    """INV-4 and INV-10: a missing name, an unknown one or a path is exit 3,
    prints nothing on standard output, and is told the names there are."""
    for target in (ROOT / "src" / "frameledger", release.parent / "frameledger.pyz"):
        done = run_frameledger(target, "schema", *([] if name is None else [name]))
        assert (done.returncode, done.stdout) == (3, b"")
        assert ", ".join(schemas.COMMANDS) in done.stderr.decode("utf-8")


def test_archive_holds_the_schemas(release):
    """INV-4: the archive holds each file under schemas/, as the tree has it."""
    with zipfile.ZipFile(release) as archive:
        held = {name: archive.read(name) for name in archive.namelist() if name.startswith("schemas/")}
    assert held == {f"schemas/{path.name}": path.read_bytes() for path in SCHEMAS.iterdir()}


# ----------------------------------------------------------------------- INV-5

def test_shared_definitions_agree():
    """INV-5: a $defs entry of one name is the same in every file."""
    seen = {}
    for command, schema in TREE.items():
        for name, definition in schema["$defs"].items():
            first_command, first = seen.setdefault(name, (command, definition))
            assert definition == first, f"$defs/{name} differs between {first_command} and {command}"
    assert "warning" in seen


# ----------------------------------------------------------------------- INV-6

def frozen_breaches(root, outputs, tree, allowed):
    """Each way today's output or schemas break a frozen set under `root`,
    as (version, command, where, what), but for those `allowed` lists."""
    found = []
    for folder in sorted(path for path in root.iterdir() if path.is_dir()) if root.is_dir() else []:
        frozen = {command: json.loads((folder / freeze_schemas.file_name(command)).read_text(encoding="utf-8"))
                  for command in schemas.COMMANDS if (folder / freeze_schemas.file_name(command)).is_file()}
        keys = json.loads((folder / freeze_schemas.KEYS).read_text(encoding="utf-8"))
        for name, output in outputs.items():
            command = output["command"]
            if command in frozen:
                found += [(folder.name, command, where, f"{name}: {message}")
                          for where, message in errors(frozen[command], output)]
        for name, paths in keys.items():
            if name not in outputs:
                found.append((folder.name, name, "", f"the sample {name} is gone"))
                continue
            command = outputs[name]["command"]
            written = freeze_schemas.key_paths(outputs[name], frozen[command], frozen[command])
            found += [(folder.name, command, path, f"{name} no longer writes it") for path in paths
                      if path not in written]
        for command, schema in frozen.items():
            for name, definition in schema["$defs"].items():
                new = [value for value in tree[command]["$defs"].get(name, {}).get("enum", [])
                       if "enum" in definition and value not in definition["enum"]]
                found += [(folder.name, command, f"$defs/{name}", f"gained {value!r}") for value in new]
    return [breach for breach in found if breach[:3] not in allowed]


ALLOWED = {entry[:3] for entry in DELIBERATE_BREAKS}


def test_output_matches_every_frozen_set(tmp_path, outputs):
    """INV-6: every frozen set still describes today's output. Then the
    same check is shown to fail: the tree's files are frozen to a folder,
    and four breaks are made against it."""
    assert frozen_breaches(freeze_schemas.FROZEN, outputs, TREE, ALLOWED) == []

    freeze_schemas.freeze(tmp_path, outputs, "9.9.9")
    assert frozen_breaches(tmp_path, outputs, TREE, set()) == []

    retyped = copy.deepcopy(outputs)
    retyped["floor-pass"]["result"]["windows"][0]["frames"] = "60"
    assert [breach[:3] for breach in frozen_breaches(tmp_path, retyped, TREE, set())] == [
        ("9.9.9", "floor", "result.windows[].frames")]

    # `expect` is optional in the schema, so only keys.json sees it go.
    dropped = copy.deepcopy(outputs)
    del dropped["check-expect-match"]["result"]["expect"]
    assert {breach[2] for breach in frozen_breaches(tmp_path, dropped, TREE, set())} == {
        "result.expect", "result.expect.matches", "result.expect.differences"}

    wider = copy.deepcopy(TREE)
    wider["budget"]["$defs"]["statistic"]["enum"].append("p95")
    assert [breach[:3] for breach in frozen_breaches(tmp_path, outputs, wider, set())] == [
        ("9.9.9", "budget", "$defs/statistic")]

    # A listed break lets off itself and nothing beside it.
    both = copy.deepcopy(retyped)
    both["floor-pass"]["result"]["allowed"] = None
    listed = {("9.9.9", "floor", "result.windows[].frames")}
    assert [breach[:3] for breach in frozen_breaches(tmp_path, both, TREE, listed)] == [
        ("9.9.9", "floor", "result.allowed")]


# ----------------------------------------------------------------------- INV-7

def sums_faults(root):
    """Each frozen file whose hash is not its line in SHA256SUMS, and each
    line or file with no partner."""
    listed = freeze_schemas.read_sums(root)
    present = {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
               for path in root.rglob("*") if path.is_file() and path.name != freeze_schemas.SUMS} \
        if root.is_dir() else {}
    return sorted(name for name in listed.keys() | present.keys() if listed.get(name) != present.get(name))


def test_frozen_sets_unchanged(tmp_path, outputs):
    """INV-7: no frozen file differs from its line; an edited file, a
    removed one and a stray one are each caught."""
    assert sums_faults(freeze_schemas.FROZEN) == []
    freeze_schemas.freeze(tmp_path, outputs, "9.9.9")
    assert sums_faults(tmp_path) == []
    kit = tmp_path / "9.9.9" / "kit.schema.json"
    kit.write_bytes(kit.read_bytes() + b"\n")
    assert sums_faults(tmp_path) == ["9.9.9/kit.schema.json"]
    kit.unlink()
    (tmp_path / "9.9.9" / "stray.json").write_text("{}")
    assert sums_faults(tmp_path) == ["9.9.9/kit.schema.json", "9.9.9/stray.json"]


def owes_a_frozen_set(version, root):
    """Whether `version` must have a frozen set under `root` and has none."""
    number = tuple(int(part) for part in version.split("-")[0].split("."))
    return number >= FIRST_FROZEN and not (root / version).is_dir()


def test_this_version_is_frozen(tmp_path):
    """INV-7: from 0.8.0 a release without its frozen set fails here, as
    soon as VERSION is bumped. Run scripts/freeze_schemas.py."""
    assert not owes_a_frozen_set(cli.VERSION, freeze_schemas.FROZEN)
    assert owes_a_frozen_set("0.8.0", tmp_path) and owes_a_frozen_set("1.0.0-rc.1", tmp_path)
    assert not owes_a_frozen_set("0.7.9", tmp_path)
    (tmp_path / "0.8.0").mkdir()
    assert not owes_a_frozen_set("0.8.0", tmp_path)


def test_freeze_refuses_an_existing_folder(tmp_path, outputs):
    """INV-7: a second freeze of one version writes nothing."""
    freeze_schemas.freeze(tmp_path, outputs, "9.9.9")
    before = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    with pytest.raises(FileExistsError):
        freeze_schemas.freeze(tmp_path, outputs, "9.9.9")
    assert {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()} == before


# ---------------------------------------------------------------- INV-8, INV-9

@pytest.mark.parametrize("name", SAMPLE_IDS)
def test_every_result_names_its_release(name, outputs):
    """INV-8: all eight keys, and this release's version, error shapes included."""
    output = outputs[name]
    assert list(output) == ["frameledger", "command", "verdict", "exit_code", "summary", "overrides", "warnings",
                            "result"]
    assert output["frameledger"] == cli.VERSION


def test_the_samples_include_each_error_shape(outputs):
    verdicts = {(output["command"], output["verdict"]) for output in outputs.values()}
    with_error = ("check", "report", "floor", "budget", "compare", "alternate")
    assert {(command, "error") for command in with_error} <= verdicts


@pytest.mark.parametrize("argv", [["floor"], ["floor", "run.csv"], ["nothing"], ["compare", "--old", "a.csv"],
                                  ["check", "a.csv", "--json", "--markdown"], ["bisect", "--json"]])
def test_a_bad_argument_prints_no_result(argv, capsys):
    """INV-8: a bad argument is exit 3, or 128 under bisect, and standard
    output holds nothing; a script tells it from a result by that."""
    assert cli.main([*argv, "--json"]) == (128 if argv[0] == "bisect" else 3)
    printed = capsys.readouterr()
    assert printed.out == "" and printed.err.startswith("frameledger: ")


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
@pytest.mark.parametrize(("argv", "code"), [
    (["--selftest", "--json"], 3), (["bisect", "--measure", "frame/wall", "--kind", "view", "--json"], 128)])
def test_json_holds_no_nan(bad, argv, code, monkeypatch, capsys):
    """INV-9: a NaN or an infinity in a result, at any depth, ends the
    command with a message and prints nothing: JSON holds neither."""
    result = cli._result("selftest", "pass", 0, [], [], {"checks": [{"name": "deep", "pass": [bad]}]})
    monkeypatch.setattr(cli, "_dispatch", lambda args: result)
    monkeypatch.setattr(cli, "_bisect", lambda args: result)
    assert cli.main(argv) == code
    printed = capsys.readouterr()
    assert printed.out == "" and "cannot be written as JSON" in printed.err
