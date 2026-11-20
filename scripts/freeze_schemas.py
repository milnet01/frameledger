"""Freeze this release's JSON result schemas under tests/fixtures/schemas/.

    python3 -I scripts/freeze_schemas.py

From 0.8.0 every release freezes the schemas it ships, and the tests hold
every later release's output to them
(docs/specs/FLED-0041-json-result-schemas.md § 4.7). This copies
src/frameledger/schemas/ to tests/fixtures/schemas/<VERSION>/, writes
keys.json beside the copies, and adds a line to SHA256SUMS for each file.

keys.json holds, for each sample of tests/schema_samples.py by name, its
command and every key path its output held, such as
`result.runs[].started_utc`. A schema that allows more keys cannot see one
go missing; this record can. A path stops where the schema names no key:
at a map whose keys are data, and at a value that is the engine's own.

Freeze last. It refuses a version whose folder exists, exit 1, writing
nothing: a frozen set is never changed, so run this as the last change
before the tag, when the schemas and the samples are final. Bumping
VERSION makes tests/test_schemas.py fail until the set is frozen; that
is the reminder, not a reason to freeze early. A wrong file that has
shipped stays, and the next release's is right.

The walkers here read a schema as tests/test_schemas.py's INV-2 holds
the files to: keys are named under `properties`, array items under
`items`, a shared part by a `$ref` into `$defs`, and a conditional
(`if`, `then`, `allOf` and the like) names no key the plain
`properties` beside it does not.

`key_paths` and `named_paths` are what tests/test_schemas.py compares
with. Standard library only. Exit 0 on success, 1 on a refusal.
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Under -I neither the analyser's modules nor the samples are on the path.
sys.path[:0] = [str(ROOT / "src" / "frameledger"), str(ROOT / "tests")]

import cli  # noqa: E402
import schema_samples  # noqa: E402
import schemas  # noqa: E402

SCHEMAS = ROOT / "src" / "frameledger" / "schemas"
FROZEN = ROOT / "tests" / "fixtures" / "schemas"
SUMS = "SHA256SUMS"
KEYS = "keys.json"


def file_name(command: str) -> str:
    return f"{command}.schema.json"


def resolved(schema: dict, root: dict) -> dict:
    """`schema`, or the $defs entry it points at."""
    while "$ref" in schema:
        schema = root["$defs"][schema["$ref"].removeprefix("#/$defs/")]
    return schema


def _home(schema: dict, at: str, by_definition: bool) -> str:
    """Where a key of `schema` is counted: under its $defs entry when it
    has one and `by_definition` asks, so a shared definition's keys are
    the same keys in every file; otherwise at its place in the result."""
    return schema["$ref"].removeprefix("#/") if by_definition and "$ref" in schema else at


def key_paths(value, schema: dict, root: dict, at: str = "", by_definition: bool = False) -> set[str]:
    """The path of every key in `value` that `schema` names, array items
    as `[]`. A key the schema does not name is data, and is not followed."""
    at, schema = _home(schema, at, by_definition), resolved(schema, root)
    if isinstance(value, list):
        items = schema.get("items", {})
        return set().union(*(key_paths(item, items, root, f"{at}[]", by_definition) for item in value))
    if not isinstance(value, dict):
        return set()
    found = set()
    for key, item in value.items():
        if key in schema.get("properties", {}):
            path = f"{at}.{key}" if at else key
            found |= {path} | key_paths(item, schema["properties"][key], root, path, by_definition)
    return found


def named_paths(schema: dict, root: dict, at: str = "", by_definition: bool = False) -> set[str]:
    """The path of every key `schema` names, in the form key_paths gives."""
    at, schema = _home(schema, at, by_definition), resolved(schema, root)
    found = named_paths(schema["items"], root, f"{at}[]", by_definition) if "items" in schema else set()
    for key, item in schema.get("properties", {}).items():
        path = f"{at}.{key}" if at else key
        found |= {path} | named_paths(item, root, path, by_definition)
    return found


def tree_schemas() -> dict[str, dict]:
    """Each command's schema as the tree holds it."""
    return {command: json.loads((SCHEMAS / file_name(command)).read_text(encoding="utf-8"))
            for command in schemas.COMMANDS}


def sample_keys(outputs: dict[str, dict], by_command: dict[str, dict]) -> dict[str, dict]:
    """keys.json's content: each sample's command and key paths, from its output."""
    return {name: {"command": output["command"],
                   "keys": sorted(key_paths(output, by_command[output["command"]], by_command[output["command"]]))}
            for name, output in sorted(outputs.items())}


def missing_keys(frozen: list[str], written: set[str]) -> list[str]:
    """The paths of `frozen` that an output holding `written` has lost. A
    path counts only where the object that held it is still there: a list
    now empty, or an object now null, has lost no key, and is data."""
    def beside(path: str) -> str:
        return path.rpartition(".")[0] + "."
    held = {beside(path) for path in written}
    return [path for path in frozen if path not in written and ("." not in path or beside(path) in held)]


def run_samples(work: Path) -> dict[str, dict]:
    """Every sample's output, by sample name; each is run in its own folder under `work`."""
    outputs = {}
    for sample in schema_samples.SAMPLES:
        folder = work / sample.name
        folder.mkdir(parents=True)
        outputs[sample.name] = json.loads(schema_samples.run(sample, folder)[1])
    return outputs


def read_sums(root: Path) -> dict[str, str]:
    """SHA256SUMS as {path under `root`: hash}; empty when there is none."""
    sums = root / SUMS
    if not sums.is_file():
        return {}
    return {name: digest for digest, name in (line.split("  ", 1) for line in
                                              sums.read_text(encoding="utf-8").splitlines())}


def freeze(root: Path, outputs: dict[str, dict], version: str = cli.VERSION) -> list[str]:
    """Write `root`/`version`/ and its lines in SHA256SUMS; return the
    paths written. Raises FileExistsError, writing nothing, when the
    folder is there."""
    folder = root / version
    if folder.exists():
        raise FileExistsError(f"{folder} exists; a frozen set is never changed")
    contents = {file_name(command): (SCHEMAS / file_name(command)).read_bytes() for command in schemas.COMMANDS}
    keys = json.dumps(sample_keys(outputs, tree_schemas()), indent=1) + "\n"
    contents[KEYS] = keys.encode("utf-8")
    folder.mkdir(parents=True)
    sums = read_sums(root)
    for name, data in contents.items():
        (folder / name).write_bytes(data)
        sums[f"{version}/{name}"] = hashlib.sha256(data).hexdigest()
    lines = "".join(f"{digest}  {name}\n" for name, digest in sorted(sums.items()))
    (root / SUMS).write_bytes(lines.encode("utf-8"))  # bytes: LF on any system
    return sorted(f"{version}/{name}" for name in contents)


def main() -> int:
    with tempfile.TemporaryDirectory() as work:
        try:
            written = freeze(FROZEN, run_samples(Path(work)))
        except FileExistsError as error:
            print(f"freeze_schemas: {error}", file=sys.stderr)
            return 1
    print(f"freeze_schemas: wrote {', '.join(written)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
