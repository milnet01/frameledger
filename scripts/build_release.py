"""Build the release archive: frameledger.pyz, the writer header and the licence.

    python3 -I scripts/build_release.py OUTDIR TAG

writes OUTDIR/frameledger.pyz and OUTDIR/frameledger-TAG.zip, then prints
the archive's path and its SHA256 (docs/design.md § The stack, and what it
rules out). The tag names the file only. Nothing inside the archive carries
it, so a candidate and the stable release cut from the same code are the
same bytes under two file names.

The build is reproducible: anyone rebuilding a tagged commit gets the hash
in its release notes. Every entry is stored, not compressed, so no zlib
version can change a byte. Every entry has the same date and mode, whatever
the checkout's. Entries are in sorted order. Only modules git tracks go
in. CRLF line endings become LF, so a Windows checkout builds the same
archive. The modules and header are read from the working tree, so build
from a clean checkout of the tag, as release.yml does.

Standard library only. Exit 0 on success, 2 on a usage error.
"""

from __future__ import annotations

import hashlib
import io
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ANALYSER = ROOT / "src" / "frameledger"

# A zip cannot date a file before 1980. One fixed date keeps two builds of
# one commit identical; zipapp stamps the build time, so it is not used.
ENTRY_DATE = (1980, 1, 1, 0, 0, 0)
ENTRY_MODE = 0o100644  # a regular file: read-write for its owner, read for all
SHEBANG = b"#!/usr/bin/env python3\n"


def source_bytes(path: Path) -> bytes:
    """The file as git stores it here: LF line endings."""
    return path.read_bytes().replace(b"\r\n", b"\n")


def zip_bytes(entries: dict[str, bytes], prefix: bytes = b"") -> bytes:
    """A zip of `entries` (name to contents), stored, in sorted order.

    `prefix` goes before the zip: a .pyz starts with its shebang line.
    """
    buffer = io.BytesIO()
    buffer.write(prefix)
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as archive:
        for name in sorted(entries):
            info = zipfile.ZipInfo(name, ENTRY_DATE)
            info.external_attr = ENTRY_MODE << 16
            # Python writes 0 (MS-DOS) on Windows and 3 (Unix) elsewhere.
            # One value, so the platform that builds does not show.
            info.create_system = 3
            archive.writestr(info, entries[name])
    return buffer.getvalue()


def tracked_modules() -> list[Path]:
    """Tracked files only, so a stray module in the checkout never ships."""
    listed = subprocess.run(["git", "ls-files", "-z", "--", "*.py"], cwd=ANALYSER, capture_output=True,
                            check=True).stdout.decode()
    return [ANALYSER / name for name in listed.split("\0") if name and "/" not in name]


def build_pyz() -> bytes:
    """The analyser's modules; the zip's __main__.py runs them as the tree does."""
    modules = {path.name: source_bytes(path) for path in tracked_modules()}
    return zip_bytes(modules, prefix=SHEBANG)


def build_archive(pyz: bytes) -> bytes:
    return zip_bytes({
        "frameledger.pyz": pyz,
        "include/frameledger.h": source_bytes(ROOT / "include" / "frameledger.h"),
        "LICENSE": source_bytes(ROOT / "LICENSE"),
    })


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: build_release.py OUTDIR TAG", file=sys.stderr)
        return 2
    outdir, tag = Path(argv[0]), argv[1]
    outdir.mkdir(parents=True, exist_ok=True)
    pyz = build_pyz()
    archive = build_archive(pyz)
    (outdir / "frameledger.pyz").write_bytes(pyz)
    archive_path = outdir / f"frameledger-{tag}.zip"
    archive_path.write_bytes(archive)
    print(archive_path)
    print(hashlib.sha256(archive).hexdigest())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
