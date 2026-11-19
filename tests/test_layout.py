"""The analyser's module rules from docs/design.md § The parts and
§ What may depend on what."""

import ast
import sys
from pathlib import Path

SRC = Path(__file__).parent.parent / "src" / "frameledger"
MODULES = {p.stem for p in SRC.glob("*.py")} - {"__main__"}

# Which analyser modules each may import. A module not listed may not
# exist yet; the test fails until it is given a row.
ALLOWED = {
    "ledger": set(),
    "stats": set(),
    "trust": {"ledger", "stats"},
    "run_report": {"trust", "stats", "ledger"},
    "generated": {"ledger"},
    "compare": {"generated", "run_report", "trust", "stats", "ledger"},
    "bisecting": {"compare", "run_report", "trust", "stats", "ledger"},
    "budgeting": {"compare", "run_report", "trust", "stats", "ledger"},
    "survey": {"generated", "run_report", "trust", "stats", "ledger"},
    "scenes": {"compare", "generated", "run_report", "trust", "stats", "ledger"},
    "variants": {"compare", "generated", "run_report", "trust", "stats", "ledger"},
    "alternate": {"ledger"},
    "baseline": {"ledger"},
    "atomic": {"ledger"},
    "presentmon": {"atomic", "ledger"},
    "expect": {"ledger"},
    "kit": {"ledger"},
    "strict": {"ledger", "stats"},
    "render": set(),
    "picture": {"render", "run_report", "stats", "ledger"},
    "selftest": MODULES - {"cli", "selftest", "render", "picture"},
    "cli": MODULES - {"cli"},
}


def imports_of(path):
    names = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names & MODULES


def test_no_module_shadows_the_standard_library():
    assert MODULES, "no analyser modules found"
    assert sorted(MODULES & set(sys.stdlib_module_names)) == []


def test_imports_run_one_way():
    for name in sorted(MODULES):
        assert name in ALLOWED, f"{name}.py has no row in ALLOWED"
        extra = imports_of(SRC / f"{name}.py") - ALLOWED[name]
        assert not extra, f"{name}.py imports {sorted(extra)}"
