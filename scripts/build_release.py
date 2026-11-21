"""Build the release archive: frameledger.pyz, its launchers, the writer header
and the licence. Also build the wheel pip installs (FLED-0043).

    python3 -I scripts/build_release.py OUTDIR TAG

writes OUTDIR/frameledger.pyz, OUTDIR/frameledger-TAG.zip and
OUTDIR/frameledger-VERSION-py3-none-any.whl, then prints the archive's path
and its SHA256 (docs/design.md § The stack, and what it rules out). The tag
names the archive file only. Nothing inside the archive carries it, so a
candidate and the stable release cut from the same code are the same bytes
under two file names. The wheel's version is cli.py's VERSION, whatever the
tag's numbers say, and a candidate's tag adds its number, since PyPI holds
one file per version; release.yml checks the tag names VERSION. A tag with
a hyphen must end -rc.N.

The build is reproducible: anyone rebuilding a tagged commit gets the hash
in its release notes. Every entry is stored, not compressed, so no zlib
version can change a byte. Every entry has the same date, whatever the
checkout's, and one of two modes: the Linux launcher's runs, the rest do
not. Entries are in sorted order. Only modules git tracks go in. CRLF line
endings become LF, so a Windows checkout builds the same archive; then the
Windows launcher alone gets CRLF, which cmd needs. The modules, the writer
kit's data, the launchers and header are read from the working tree, so
build from a clean checkout of the tag, as release.yml does.

Standard library only. Exit 0 on success; 1 when a module sits in a
subdirectory of src/frameledger, or anything in a subdirectory of kit/ or
schemas/; 2 on a usage error, a tag with a hyphen that does not end -rc.N
among them.
"""

from __future__ import annotations

import base64
import hashlib
import io
import re
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
RUNNABLE_MODE = 0o100755  # the same, and anyone may run it
RUNNABLE = {"frameledger"}  # the Linux launcher (launcher/frameledger)
SHEBANG = b"#!/usr/bin/env python3\n"
DATA_FOLDERS = ("kit", "schemas")  # plain data beside the modules, read with pkgutil.get_data


def source_bytes(path: Path) -> bytes:
    """The file as git stores it here: LF line endings."""
    return path.read_bytes().replace(b"\r\n", b"\n")


def crlf(text: bytes) -> bytes:
    return text.replace(b"\n", b"\r\n")


def zip_bytes(entries: dict[str, bytes], prefix: bytes = b"", last: str = "") -> bytes:
    """A zip of `entries` (name to contents), stored, in sorted order.

    `prefix` goes before the zip: a .pyz starts with its shebang line.
    Names starting `last` go after the rest, sorted too: a wheel's metadata
    goes last, as the wheel format recommends.
    """
    buffer = io.BytesIO()
    buffer.write(prefix)
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as archive:
        for name in sorted(entries, key=lambda name: (bool(last) and name.startswith(last), name)):
            info = zipfile.ZipInfo(name, ENTRY_DATE)
            info.external_attr = (RUNNABLE_MODE if name in RUNNABLE else ENTRY_MODE) << 16
            # Python writes 0 (MS-DOS) on Windows and 3 (Unix) elsewhere.
            # One value, so the platform that builds does not show.
            info.create_system = 3
            archive.writestr(info, entries[name])
    return buffer.getvalue()


def tracked_files() -> list[str]:
    """The analyser's tracked modules, and the writer kit's tracked data, as
    paths within src/frameledger. Tracked only, so a stray file in the
    checkout never ships.

    The analyser is flat: its modules import each other by bare name
    (docs/design.md § The parts). Its folders are kit/ and schemas/, plain
    data that kit.py and schemas.py read with pkgutil.get_data, with no
    module and no folder of their own. Anything else in a subdirectory stops the build rather than
    going missing from the .pyz.
    """
    listed = subprocess.run(["git", "ls-files", "-z", "--", "*.py", *DATA_FOLDERS], cwd=ANALYSER, capture_output=True,
                            check=True).stdout.decode()
    names = [name for name in listed.split("\0") if name]
    nested = [name for name in names if "/" in name and not _data_file(name)]
    if nested:
        sys.exit("build_release: src/frameledger is flat but for the data in kit/ and schemas/, and git tracks "
                 + ", ".join(nested))
    return names


def _data_file(name: str) -> bool:
    folder, _, rest = name.partition("/")
    return folder in DATA_FOLDERS and "/" not in rest and not name.endswith(".py")


INSTALLED_ONLY = "__init__.py"  # the installed form's entry point; the .pyz never imports it


def build_pyz() -> bytes:
    """The analyser's modules and the kit; the zip's __main__.py runs them as the tree does."""
    files = {name: source_bytes(ANALYSER / name) for name in tracked_files() if name != INSTALLED_ONLY}
    return zip_bytes(files, prefix=SHEBANG)


def build_archive(pyz: bytes) -> bytes:
    schemas = {name: source_bytes(ANALYSER / name) for name in tracked_files() if name.startswith("schemas/")}
    return zip_bytes({
        **schemas,
        "frameledger.pyz": pyz,
        "frameledger": source_bytes(ROOT / "launcher" / "frameledger"),
        "frameledger.cmd": crlf(source_bytes(ROOT / "launcher" / "frameledger.cmd")),
        "include/frameledger.h": source_bytes(ROOT / "include" / "frameledger.h"),
        "LICENSE": source_bytes(ROOT / "LICENSE"),
    })


def package_version(tag: str) -> str | None:
    """The analyser's VERSION as PyPI writes it, a candidate's tag adding its
    number: VERSION 0.9.0 is 0.9.0, or 0.9.0rc1 under tag v0.9.0-rc.1.

    The tag's own numbers are not read: release.yml checks they name
    VERSION. VERSION is read from cli.py's text, the line .claude/bump.json
    bumps.

    None for a tag with a hyphen that does not end -rc.N, N from 1 with no
    leading zero. release.yml makes every tag with a hyphen a pre-release,
    so such a tag would put a stable version on PyPI, which takes each
    version once.
    """
    candidate = None
    if "-" in tag:
        candidate = re.fullmatch(r"[^-]+-rc\.([1-9]\d*)", tag)
        if candidate is None:
            return None
    source = (ANALYSER / "cli.py").read_text(encoding="utf-8")
    found = re.search(r'^VERSION = "(.+)"$', source, re.MULTILINE)
    if found is None:
        sys.exit('build_release: src/frameledger/cli.py has no line VERSION = "X.Y.Z"')
    return found.group(1) + (f"rc{candidate.group(1)}" if candidate else "")


def _record_hash(data: bytes) -> str:
    """A wheel's RECORD form of a hash: SHA256, URL-safe base64, no padding."""
    return "sha256=" + base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()


def build_wheel(version: str) -> bytes:
    """The package pip installs: the .pyz's files under frameledger/, and the
    metadata a wheel needs, which gives it a `frameledger` command.

    Pure Python and no dependencies, so one wheel serves every platform
    (py3-none-any). zip_bytes stores, dates and orders its entries as it
    does the archive's, so it rebuilds to the same bytes.
    """
    info = f"frameledger-{version}.dist-info"
    files = {f"frameledger/{name}": source_bytes(ANALYSER / name) for name in tracked_files()}
    # Summary is README.md's tagline; Requires-Python is the analyser's
    # floor (docs/design.md § The stack, and what it rules out).
    files[f"{info}/METADATA"] = (
        "Metadata-Version: 2.4\n"
        "Name: frameledger\n"
        f"Version: {version}\n"
        "Summary: Finds what slows a game engine's frames.\n"
        "License-Expression: MIT\n"
        "License-File: LICENSE\n"
        "Requires-Python: >=3.10\n"
        "Project-URL: Homepage, https://github.com/milnet01/frameledger\n"
        "Description-Content-Type: text/markdown\n"
        "\n"
        "The frameledger analyser. Its guide, the writer header and the release\n"
        "archive are at https://github.com/milnet01/frameledger.\n"
    ).encode()
    files[f"{info}/WHEEL"] = (
        b"Wheel-Version: 1.0\n"
        b"Generator: frameledger scripts/build_release.py\n"
        b"Root-Is-Purelib: true\n"
        b"Tag: py3-none-any\n"
    )
    files[f"{info}/entry_points.txt"] = b"[console_scripts]\nframeledger = frameledger:main\n"
    files[f"{info}/licenses/LICENSE"] = source_bytes(ROOT / "LICENSE")
    record = "".join(f"{name},{_record_hash(data)},{len(data)}\n" for name, data in sorted(files.items()))
    files[f"{info}/RECORD"] = (record + f"{info}/RECORD,,\n").encode()
    return zip_bytes(files, last=info)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: build_release.py OUTDIR TAG", file=sys.stderr)
        return 2
    outdir, tag = Path(argv[0]), argv[1]
    version = package_version(tag)
    if version is None:
        print(f"build_release.py: {tag} has a hyphen, so it is a pre-release, but it does not end -rc.N",
              file=sys.stderr)
        return 2
    outdir.mkdir(parents=True, exist_ok=True)
    pyz = build_pyz()
    archive = build_archive(pyz)
    (outdir / "frameledger.pyz").write_bytes(pyz)
    (outdir / f"frameledger-{version}-py3-none-any.whl").write_bytes(build_wheel(version))
    archive_path = outdir / f"frameledger-{tag}.zip"
    archive_path.write_bytes(archive)
    print(archive_path)
    print(hashlib.sha256(archive).hexdigest())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
