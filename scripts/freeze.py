"""Freeze new files under tests/fixtures/frozen/.

    python3 -I scripts/freeze.py

A frozen file is a run, budget or baseline file that a release read, kept
so every later release is shown to read it the same
(docs/specs/FLED-0040-format-stability-promise.md § 4.8). To freeze one,
put it in tests/fixtures/frozen/ under the name § 4.8 gives and run this.
For each `run-*.csv`, `budget-*.csv` and `baseline-*.txt` there with no
`.json` beside it, this reads the file with today's reader and writes the
values as that `.json`. Then it adds a line to SHA256SUMS for each file
that has none.

It never changes what is already frozen: a file whose SHA-256 differs
from its line in SHA256SUMS stops the run, exit 1, before anything is
written. So does a file today's reader does not accept. Read the new
`.json` before committing it: it is what every later reader is held to,
so a reader fault frozen here is kept.

`values(path)` gives the stored form of one file; tests/test_frozen.py
compares with it. Standard library only. Exit 0 on success, 1 on a
refusal.
"""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src" / "frameledger"))  # under -I the analyser's modules are not on the path

import baseline  # noqa: E402
import budgeting  # noqa: E402
import ledger  # noqa: E402

FROZEN = ROOT / "tests" / "fixtures" / "frozen"
SUMS = "SHA256SUMS"
DATA_GLOBS = ("run-*.csv", "budget-*.csv", "baseline-*.txt")


def run_values(path) -> dict:
    """A run file's header, static and close objects, and every row in
    file order as [segment, frame, category, name, depth, thousandths].
    A row's run_id is the header's, so it is not stored again."""
    run = ledger.read(path)
    if run.breaches:
        first = run.breaches[0]
        raise ledger.LedgerError(f"breaks the format: {first.message}", str(path), first.line)
    rows = sorted((row for frame in run.frames.values() for row in frame.values()), key=lambda row: row.line)
    return {
        "header": run.header,
        "static": run.static,
        "close": run.close,
        "rows": [[r.segment, r.frame, r.category, r.name, r.depth, r.thousandths] for r in rows],
    }


def budget_values(path) -> dict:
    """A budget file's `match`, and every budget in file order as
    [category, name, kind, depth, statistic, limit in thousandths of a
    ms]. An empty kind or depth is null."""
    budget = budgeting.read(path)
    return {
        "match": budget.match,
        "budgets": [[b.category, b.name, b.kind, b.depth, b.statistic, b.limit] for b in budget.budgets],
    }


def baseline_values(path) -> dict:
    """A baseline file's runs in file order, each as a path relative to
    the file's folder: the reader gives absolute paths, which differ
    from one checkout to the next."""
    folder = Path(path).resolve().parent
    return {"runs": [Path(run).relative_to(folder).as_posix() for run in baseline.read(str(path))]}


def values(path) -> dict:
    """The stored form of a frozen file, chosen by its name's first word."""
    name = Path(path).name
    if name.startswith("budget-"):
        return budget_values(path)
    if name.startswith("baseline-"):
        return baseline_values(path)
    return run_values(path)


def same(read, kept) -> bool:
    """Whether two sets of values are the same, types included. Plain ==
    calls false and 0 equal, and 1.0 and 1 (ExperiRays, UT Ants)."""
    return json.dumps(read, sort_keys=True) == json.dumps(kept, sort_keys=True)


def read_sums(folder: Path) -> dict[str, str]:
    """SHA256SUMS as name -> digest. Each line is the digest, two spaces,
    the file's name, as `sha256sum` writes it."""
    path = folder / SUMS
    if not path.is_file():
        return {}
    sums = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        sums[name] = digest
    return sums


def digest_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze(folder: Path = FROZEN) -> list[str]:
    """Write the missing `.json` files and SHA256SUMS lines in `folder`.
    Returns the names added. Raises ledger.LedgerError, having written
    nothing, when a listed file has changed or a new one cannot be read."""
    sums = read_sums(folder)
    for name, digest in sums.items():
        path = folder / name
        if not path.is_file():
            raise ledger.LedgerError("is listed in SHA256SUMS and is gone; a frozen file is never removed", str(path))
        if digest_of(path) != digest:
            raise ledger.LedgerError("differs from its line in SHA256SUMS; a frozen file is never edited", str(path))

    data = sorted(path for glob in DATA_GLOBS for path in folder.glob(glob))
    new_values = {path.with_suffix(".json"): values(path) for path in data
                  if not path.with_suffix(".json").is_file()}

    for path, kept in new_values.items():
        path.write_text(json.dumps(kept, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    added = sorted(path.name for path in folder.iterdir() if path.name != SUMS and path.name not in sums)
    for name in added:
        sums[name] = digest_of(folder / name)
    (folder / SUMS).write_text("".join(f"{sums[name]}  {name}\n" for name in sorted(sums)), encoding="utf-8")
    return added


def main() -> int:
    try:
        added = freeze()
    except ledger.LedgerError as error:
        print(f"freeze: {error}", file=sys.stderr)
        return 1
    print(f"freeze: added {', '.join(added)}" if added else "freeze: nothing new to freeze")
    return 0


if __name__ == "__main__":
    sys.exit(main())
