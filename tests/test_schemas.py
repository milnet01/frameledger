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

Cutting a release: freeze last. Bumping VERSION makes
test_this_version_is_frozen fail; finish the schemas and the samples,
then run scripts/freeze_schemas.py and commit tests/fixtures/schemas/. A
frozen set is never changed afterwards. A deliberate break goes in
DELIBERATE_BREAKS.

The walkers here (strict, subschemas, described) and in
scripts/freeze_schemas.py read a schema the way INV-2 holds the files to:
only the keywords in KEYWORDS, keys named under `properties`, items under
`items`, and no key named under a conditional that the plain `properties`
beside it does not name. A file that needs another keyword needs them
taught first.
"""

import contextlib
import copy
import hashlib
import importlib.util
import io
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
# Every keyword the files use. strict() and the walkers know these and no
# other: `contains` or `dependentSchemas`, say, would be closed or skipped wrongly.
KEYWORDS = {"$schema", "$defs", "$ref", "title", "description", "type", "properties", "required", "items",
            "additionalProperties", "enum", "const", *CONDITIONAL}
VALUES = ("enum", "const", "required", "type", "title", "description", "$ref", "$schema")  # hold no schema
FIRST_FROZEN = (0, 8, 0)  # § 4.7: from this release, every release freezes its schemas; check-release.sh agrees

# A break made on purpose: (frozen version, command, where, a sentence of
# the CHANGELOG.md entry that names it). `where` is what frozen_breaches
# reports: a key path, `$defs/NAME: VALUE` for a value a closed set gained,
# `$defs/NAME` for a set no longer closed, or `sample NAME` for a sample
# that is gone. Only the listed failure is let off (§ 4.7).
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
    a conditional keyword, whose keys the enclosing object already counts.
    Everything below a conditional stays open, which is right only while a
    conditional names no key of its own: INV-2 holds the files to that."""
    def close(node, open_here):
        if isinstance(node, list):
            return [close(item, open_here) for item in node]
        if not isinstance(node, dict):
            return node
        closed = {}
        for key, item in node.items():
            if key in VALUES:
                closed[key] = item
            elif key in ("properties", "$defs"):  # a map of names to schemas, not a schema
                closed[key] = {name: close(sub, open_here) for name, sub in item.items()}
            else:
                closed[key] = close(item, open_here or key in CONDITIONAL)
        if "properties" in node and not open_here:
            closed["unevaluatedProperties"] = False
        return closed
    return close(schema, False)


def errors(schema, output):
    """Each way `output` fails `schema`, as (key path, message). A missing
    required key is reported at the key, as keys.json would name it, not
    at the object that lacks it."""
    found = []
    for error in jsonschema.Draft202012Validator(schema).iter_errors(output):
        if error.validator == "required":
            found += [(key_path([*error.absolute_path, key]), error.message)
                      for key in error.validator_value if key not in error.instance]
        else:
            found.append((key_path(error.absolute_path), error.message))
    return sorted(found)


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
            elif key not in VALUES:
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
               ("compare-pass", "error"), ("compare-refused", "pass"), ("compare-absent", "pass"),
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
        assert set(node) <= KEYWORDS, f"{sorted(set(node) - KEYWORDS)}: a keyword the walkers do not know"
        assert node.get("additionalProperties") is not False
        if "$ref" in node:
            assert node["$ref"].removeprefix("#/$defs/") in schema["$defs"], node["$ref"]
            assert "properties" not in node
            assert under[-1] not in CONDITIONAL, f"{node['$ref']} sits directly under {under[-1]}"
        if "enum" in node and not set(under) & set(CONDITIONAL):
            assert under[-1:] == ("$defs",) and len(under) == 1, f"the closed set {node['enum']} has no name in $defs"


def keys_only_a_conditional_names(condition, plain, root, at=""):
    """Each key `condition` names that `plain`, the schema it applies
    beside, does not."""
    plain = freeze_schemas.resolved(plain, root)
    found = []
    for key in CONDITIONAL:
        for sub in [condition[key]] if isinstance(condition.get(key), dict) else condition.get(key, []):
            found += keys_only_a_conditional_names(sub, plain, root, at)
    for key, sub in condition.get("properties", {}).items():
        if key not in plain.get("properties", {}):
            found.append(f"{at}{key}")
        else:
            found += keys_only_a_conditional_names(sub, plain["properties"][key], root, f"{at}{key}.")
    return found


@pytest.mark.parametrize("command", schemas.COMMANDS)
def test_a_conditional_names_no_key_of_its_own(command):
    """INV-2: a key named only under `if` or `then` would pass the strict
    form unseen by INV-3, INV-11 and keys.json, which walk the plain
    `properties`. A conditional may only require and narrow."""
    schema = TREE[command]
    for node, under in subschemas(schema):
        if set(under) & set(CONDITIONAL):
            continue  # reached again from the schema it sits in
        conditions = {key: node[key] for key in CONDITIONAL if key in node}
        assert keys_only_a_conditional_names(conditions, node, schema) == []
    probe = {"properties": {"result": {"type": "object"}}, "allOf": [{"then": {"properties": {"result": {
        "properties": {"new": {}}}, "other": {}}}}]}
    assert keys_only_a_conditional_names({"allOf": probe["allOf"]}, probe, probe) == ["result.new", "other"]


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


COMPARE_SHAPES = {"measures": "plain", "scenes": "by_scene", "variants": "variants", "refused": "refused",
                  "named_measures": "absent_measure"}  # § 4.4's "told apart by", first match wins
ALTERNATE_OWN = {"commands", "out", "warmup", "stopped", "baseline"}


def shape_of(output):
    """The shape a result has, by § 4.4's table: what a script would do."""
    command, verdict, result = output["command"], output["verdict"], output["result"]
    if command == "check":
        return "expect" if "expect" in result else "file_unread" if verdict == "error" else "judged"
    if command in ("report", "floor", "budget"):
        return "file_unread" if verdict == "error" else "judged"
    if command == "bisect":
        return "judged" if verdict in ("good", "bad") else "skipped_or_stopped"
    if command in ("compare", "alternate"):
        if result.get("stopped") is not None:
            return "stopped"
        return next((shape for key, shape in COMPARE_SHAPES.items() if key in result), "file_unread")
    return "one"


@pytest.mark.parametrize("sample", schema_samples.SAMPLES, ids=SAMPLE_IDS)
def test_each_sample_shows_its_shape(sample, outputs):
    """INV-3: a sample's output has the shape the sample is listed under,
    so a shape cannot lose its only real sample unseen. An unread file's
    result holds nothing but what § 4.4 gives it, which the schema, never
    capping a result, cannot say."""
    output = outputs[sample.name]
    assert (output["command"], shape_of(output)) == (sample.command, sample.shape)
    if sample.shape == "file_unread" and sample.command != "check":
        assert set(output["result"]) == (ALTERNATE_OWN if sample.command == "alternate" else set())
    if sample.shape == "stopped":
        assert set(output["result"]) == ALTERNATE_OWN


# A key a shape writes whose loss its schema may not refuse: the key that
# tells the shape apart, without which the result is another shape's, and
# the two § 4.4 gives as written only sometimes.
NOT_REQUIRED = {("check", "expect", "expect"), ("compare", "by_scene", "scenes"), ("compare", "variants", "variants"),
                ("compare", "refused", "refused"), ("compare", "absent_measure", "named_measures"),
                ("compare", "absent_measure", "runs"), ("alternate", "variants", "variants"),
                ("alternate", "refused", "refused"), ("alternate", "absent_measure", "named_measures"),
                ("alternate", "absent_measure", "runs")}


@pytest.mark.parametrize("sample", schema_samples.SAMPLES, ids=SAMPLE_IDS)
def test_each_shape_requires_its_keys(sample, outputs):
    """§ 4.4: each `then` lists the keys its shape always writes. With any
    one key of `result` removed the published schema refuses the output,
    so no `if` is dead and no `required` list is short."""
    output = outputs[sample.name]
    for key in output["result"]:
        changed = copy.deepcopy(output)
        del changed["result"][key]
        if (sample.command, sample.shape, key) not in NOT_REQUIRED:
            assert errors(TREE[sample.command], changed), f"{key} can go unnoticed"


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
        for flags in ((), ("--json",), ("--markdown",), ("--json", "--markdown")):
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


def test_schema_command_prints_to_a_text_stream():
    """A caller's own text stream has no bytes under it; the schema is
    written to it as text, not a traceback."""
    printed = io.StringIO()
    with contextlib.redirect_stdout(printed):
        assert cli.main(["schema", "kit"]) == 0
    assert printed.getvalue().encode("utf-8") == (SCHEMAS / "kit.schema.json").read_bytes()


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

def frozen_sets(root):
    """Each frozen set under `root`: (version, {command: schema}, keys.json's content)."""
    for folder in sorted(path for path in root.iterdir() if path.is_dir()) if root.is_dir() else []:
        frozen = {command: json.loads((folder / freeze_schemas.file_name(command)).read_text(encoding="utf-8"))
                  for command in schemas.COMMANDS if (folder / freeze_schemas.file_name(command)).is_file()}
        yield folder.name, frozen, json.loads((folder / freeze_schemas.KEYS).read_text(encoding="utf-8"))


def retyped(frozen, outputs):
    """(command, key path, what) for each output a frozen schema refuses."""
    return [(output["command"], where, f"{name}: {message}") for name, output in outputs.items()
            if output["command"] in frozen for where, message in errors(frozen[output["command"]], output)]


def lost_keys(frozen, keys, outputs):
    """(command, key path, what) for each key a sample wrote when frozen
    and no longer writes, and for each sample that is gone."""
    found = []
    for name, record in keys.items():
        command = record["command"]
        if name not in outputs:
            found.append((command, f"sample {name}", "is gone"))
            continue
        written = freeze_schemas.key_paths(outputs[name], frozen[command], frozen[command])
        found += [(command, path, f"{name} no longer writes it")
                  for path in freeze_schemas.missing_keys(record["keys"], written)]
    return found


def widened_sets(frozen, tree):
    """(command, where, what) for each frozen closed set that today's file
    gives a new value, or no longer holds as a closed set under its name."""
    found = []
    for command, schema in frozen.items():
        for name, definition in schema["$defs"].items():
            if "enum" not in definition:
                continue
            today = tree[command]["$defs"].get(name, {})
            if "enum" not in today:
                found.append((command, f"$defs/{name}", "is no longer a closed set of that name"))
            found += [(command, f"$defs/{name}: {value!r}", "is a new value")
                      for value in today.get("enum", []) if value not in definition["enum"]]
    return found


def frozen_breaches(root, outputs, tree, allowed):
    """Each way today's output or schemas break a frozen set under `root`,
    as (version, command, where, what), but for those `allowed` lists by
    version, command and where."""
    found = []
    for version, frozen, keys in frozen_sets(root):
        breaches = retyped(frozen, outputs) + lost_keys(frozen, keys, outputs) + widened_sets(frozen, tree)
        found += [(version, *breach) for breach in breaches]
    return [breach for breach in found if breach[:3] not in allowed]


ALLOWED = {entry[:3] for entry in DELIBERATE_BREAKS}


def breaks(root, outputs, tree=TREE, allowed=frozenset()):
    """The (command, where) of each breach, once."""
    return sorted({breach[1:3] for breach in frozen_breaches(root, outputs, tree, allowed)})


def changed(outputs, name, change):
    """`outputs` with `change` made to a copy of the result of sample `name`."""
    copied = copy.deepcopy(outputs)
    change(copied[name]["result"])
    return copied


def test_output_matches_every_frozen_set(tmp_path, outputs):
    """INV-6: every frozen set still describes today's output. Then the
    same check is shown to fail: the tree's files are frozen to a folder,
    and each kind of break is made against it."""
    assert frozen_breaches(freeze_schemas.FROZEN, outputs, TREE, ALLOWED) == []

    freeze_schemas.freeze(tmp_path, outputs, "9.9.9")
    assert breaks(tmp_path, outputs) == []
    # Adding is not breaking.
    assert breaks(tmp_path, changed(outputs, "floor-pass", lambda result: result.update(new_key=1))) == []

    retype = changed(outputs, "floor-pass", lambda result: result["windows"][0].update(frames="60"))
    assert breaks(tmp_path, retype) == [("floor", "result.windows[].frames")]
    # A required key gone is named at the key, by the schema and by keys.json alike.
    assert breaks(tmp_path, changed(outputs, "floor-pass", lambda result: result.pop("allowed"))) == [
        ("floor", "result.allowed")]
    # `expect` is optional in the schema, so only keys.json sees it go.
    assert breaks(tmp_path, changed(outputs, "check-expect-match", lambda result: result.pop("expect"))) == [
        ("check", "result.expect")]
    # A list now empty has lost no key: what it holds follows the run.
    assert outputs["floor-pass"]["result"]["windows"]
    assert breaks(tmp_path, changed(outputs, "floor-pass", lambda result: result["windows"].clear())) == []
    assert breaks(tmp_path, {name: output for name, output in outputs.items() if name != "kit"}) == [
        ("kit", "sample kit")]

    wider = copy.deepcopy(TREE)
    wider["budget"]["$defs"]["statistic"]["enum"].append("p95")
    assert breaks(tmp_path, outputs, wider) == [("budget", "$defs/statistic: 'p95'")]
    opened = copy.deepcopy(TREE)
    opened["budget"]["$defs"]["statistic"] = {"type": "string"}
    assert breaks(tmp_path, outputs, opened) == [("budget", "$defs/statistic")]

    # A listed break lets off itself and nothing beside it, in its own version and command only.
    both = changed(retype, "floor-pass", lambda result: result.update(allowed=None))
    listed = ("9.9.9", "floor", "result.windows[].frames")
    assert breaks(tmp_path, both, allowed={listed}) == [("floor", "result.allowed")]
    for other in (("9.9.8", *listed[1:]), ("9.9.9", "budget", listed[2])):
        assert ("floor", "result.windows[].frames") in breaks(tmp_path, both, allowed={other})

    # It is the frozen files that are read, not the tree's: change them alone.
    kit = tmp_path / "9.9.9" / "kit.schema.json"
    frozen_kit = json.loads(kit.read_text(encoding="utf-8"))
    frozen_kit["properties"]["result"]["properties"]["kit"]["properties"]["directory"]["type"] = "integer"
    kit.write_text(json.dumps(frozen_kit), encoding="utf-8")
    keys = tmp_path / "9.9.9" / freeze_schemas.KEYS
    record = json.loads(keys.read_text(encoding="utf-8"))
    record["selftest"]["keys"].append("result.gone")
    keys.write_text(json.dumps(record), encoding="utf-8")
    assert breaks(tmp_path, outputs) == [("kit", "result.kit.directory"), ("selftest", "result.gone")]


def test_each_deliberate_break_names_its_changelog_entry():
    """§ 4.7: a break is let off only with the CHANGELOG.md entry that says so."""
    changelog = " ".join((ROOT / "CHANGELOG.md").read_text(encoding="utf-8").split())
    for version, command, where, entry in DELIBERATE_BREAKS:
        assert " ".join(entry.split()) in changelog, f"{version} {command} {where}: no such CHANGELOG.md entry"


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
