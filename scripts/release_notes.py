"""Print one version's CHANGELOG section: the release notes, verbatim.

    python3 -I scripts/release_notes.py VERSION [--sha256 HASH]

VERSION is the plain triple, 0.1.0; a candidate's tag v0.1.0-rc.1 takes
the 0.1.0 section. The section runs from its `## [VERSION]` heading, dated
or not, to the next `## [` heading, with the heading itself left out.

With --sha256, the section must carry HASH, the archive just built, and no
other SHA256. So the hash in the notes is one an independent build
reproduced, not one typed in.

Standard library only. Exit 0 with the notes on stdout; 1 when the section
is missing or empty, or its hash differs from HASH, naming both; 2 on a
usage error.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

CHANGELOG = Path(__file__).resolve().parent.parent / "CHANGELOG.md"
SHA256 = re.compile(r"\b[0-9a-f]{64}\b")


def section(text: str, version: str) -> str | None:
    """The body under `## [version]`, trimmed; None when there is no such heading."""
    lines = text.splitlines()
    heading = f"## [{version}]"
    starts = [i for i, line in enumerate(lines) if line == heading or line.startswith(heading + " ")]
    if not starts:
        return None
    start = starts[0]
    body = []
    for line in lines[start + 1:]:
        if line.startswith("## ["):
            break
        body.append(line)
    return "\n".join(body).strip()


def main(argv: list[str]) -> int:
    if len(argv) not in (1, 3) or (len(argv) == 3 and argv[1] != "--sha256"):
        print("usage: release_notes.py VERSION [--sha256 HASH]", file=sys.stderr)
        return 2
    version = argv[0]
    notes = section(CHANGELOG.read_text(encoding="utf-8"), version)
    if not notes:
        print(f"release_notes: CHANGELOG.md has no section, or an empty one, for {version}", file=sys.stderr)
        return 1
    if len(argv) == 3:
        built = argv[2]
        stated = SHA256.findall(notes)
        if stated != [built]:
            print(f"release_notes: the archive built has SHA256 {built};"
                  f" the {version} section states {', '.join(stated) or 'none'}", file=sys.stderr)
            return 1
    # Windows writes a redirected stdout in its legacy code page, which has
    # no `§` or `→`; the notes are UTF-8 wherever they are printed.
    sys.stdout.reconfigure(encoding="utf-8")
    print(notes)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
