"""The documentation checks the gate runs, locally and on GitHub alike.

Over every tracked Markdown file:

- a relative link names a file that exists, and its `#anchor`, if any,
  names a heading in the target, slugged as GitHub slugs them;
- a cited test, `tests/<file>.py::<name>`, names a function in that file.
  A cited file that does not exist yet is a test still to be built (a
  spec names its tests before they are written), so it is not an error.

Standard library only. Exit 0 when every check holds, 1 otherwise, with
one line per problem.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FENCE = re.compile(r"^\s*(```|~~~)")
CODE_SPAN = re.compile(r"`[^`]*`")
INLINE_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
REFERENCE_LINK = re.compile(r"^\s*\[[^\]]+\]:\s*(\S+)")
HEADING = re.compile(r"^#{1,6}\s+(.*?)\s*#*\s*$")
CITED_TEST = re.compile(r"(tests/[\w/.-]+\.py)::(\w+)")


def tracked_markdown() -> list[Path]:
    """Tracked files only, so a local run sees what a GitHub checkout sees."""
    listed = subprocess.run(["git", "ls-files", "-z", "*.md"], cwd=ROOT, capture_output=True,
                            check=True).stdout.decode()
    return [ROOT / name for name in listed.split("\0") if name]


def prose_lines(path: Path) -> list[tuple[int, str]]:
    """(line number, text) for each line outside a fenced code block."""
    lines, fenced = [], False
    for number, text in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if FENCE.match(text):
            fenced = not fenced
        elif not fenced:
            lines.append((number, text))
    return lines


def slug(heading: str) -> str:
    """GitHub's anchor for a heading: a link keeps its text, other markup
    and punctuation go, then lower case with spaces as hyphens."""
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", heading)
    text = re.sub(r"[^\w\- ]", "", text.lower())
    return text.replace(" ", "-")


def anchors(path: Path) -> set[str]:
    """Every heading's anchor; a repeated heading gets -1, -2 and so on."""
    found: set[str] = set()
    seen: dict[str, int] = {}
    for _, text in prose_lines(path):
        match = HEADING.match(text)
        if not match:
            continue
        base = slug(match.group(1))
        count = seen.get(base, 0)
        seen[base] = count + 1
        found.add(base if count == 0 else f"{base}-{count}")
    return found


def link_problems(path: Path) -> list[str]:
    problems = []
    for number, text in prose_lines(path):
        text = CODE_SPAN.sub("", text)
        for target in INLINE_LINK.findall(text) + REFERENCE_LINK.findall(text):
            if "://" in target or target.startswith("mailto:"):
                continue
            file_part, _, anchor = target.partition("#")
            linked = (path.parent / file_part).resolve() if file_part else path
            where = f"{path.relative_to(ROOT)}:{number}"
            if not linked.exists():
                problems.append(f"{where}: link to {target}: no such file")
            elif anchor and linked.suffix == ".md" and anchor not in anchors(linked):
                problems.append(f"{where}: link to {target}: no heading with that anchor")
    return problems


def test_problems(path: Path) -> list[str]:
    problems = []
    for number, text in prose_lines(path):
        for file_name, name in CITED_TEST.findall(text):
            test_file = ROOT / file_name
            if not test_file.exists():
                continue  # a test still to be built
            tree = ast.parse(test_file.read_text(encoding="utf-8"))
            defined = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
            if name not in defined:
                problems.append(f"{path.relative_to(ROOT)}:{number}: cites {file_name}::{name}, "
                                "which that file does not define")
    return problems


def main() -> int:
    problems = []
    for path in tracked_markdown():
        problems += link_problems(path) + test_problems(path)
    for problem in problems:
        print(problem)
    print(f"check_docs: {len(problems)} problems" if problems else "check_docs: links and cited tests hold")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
