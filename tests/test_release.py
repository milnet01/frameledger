"""The release archive (scripts/build_release.py; docs/design.md § The stack,
and what it rules out): what it holds, that it rebuilds to the same bytes,
and that its frameledger.pyz runs; and the release notes' hash check."""

import hashlib
import importlib.util
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "scripts" / "build_release.py"


def load_script(name):
    """A scripts/ module; scripts/ is not on the import path, which is the analyser's."""
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


release_notes = load_script("release_notes")
HASH_A = "a" * 64
HASH_B = "b" * 64
CHANGELOG = f"""# Changelog

## [Unreleased]

## [0.2.0]

**Theme:** Candidate.

### Added

- Thing. SHA256 `{HASH_A}`.

## [0.1.0] - 2026-10-26

### Fixed

- Other thing.
"""


def build(outdir, tag):
    """Run the script as the release workflow does; return (archive, printed hash)."""
    done = subprocess.run([sys.executable, "-I", str(SCRIPT), str(outdir), tag],
                          capture_output=True, text=True, check=True)
    path, sha = done.stdout.split()
    return Path(path), sha


def test_archive_holds_the_analyser_header_and_licence(tmp_path):
    archive, sha = build(tmp_path, "v9.9.9")
    assert archive.name == "frameledger-v9.9.9.zip"
    assert sha == hashlib.sha256(archive.read_bytes()).hexdigest()
    with zipfile.ZipFile(archive) as zf:
        assert zf.namelist() == ["LICENSE", "frameledger.pyz", "include/frameledger.h"]
        assert zf.read("include/frameledger.h") == (ROOT / "include" / "frameledger.h").read_bytes()


def test_a_rebuild_under_another_tag_is_the_same_bytes(tmp_path):
    """A candidate's Windows runs are on the bytes the stable release pins."""
    first, first_sha = build(tmp_path / "a", "v0.1.0-rc.1")
    second, second_sha = build(tmp_path / "b", "v0.1.0")
    assert first_sha == second_sha
    assert first.read_bytes() == second.read_bytes()


def test_the_pyz_runs_its_selftest(tmp_path):
    """Isolated, as an engine runs it: the modules import by bare name from the zip."""
    build(tmp_path, "v9.9.9")
    pyz = tmp_path / "frameledger.pyz"
    done = subprocess.run([sys.executable, "-I", str(pyz), "--selftest"], capture_output=True, text=True)
    assert done.returncode == 0, done.stdout + done.stderr
    with zipfile.ZipFile(pyz) as zf:
        assert sorted(zf.namelist()) == sorted(p.name for p in (ROOT / "src" / "frameledger").glob("*.py"))


def test_notes_are_the_section_dated_or_not():
    candidate = f"**Theme:** Candidate.\n\n### Added\n\n- Thing. SHA256 `{HASH_A}`."
    assert release_notes.section(CHANGELOG, "0.2.0") == candidate
    assert release_notes.section(CHANGELOG, "0.1.0") == "### Fixed\n\n- Other thing."
    assert release_notes.section(CHANGELOG, "0.1") is None
    assert release_notes.section(CHANGELOG, "Unreleased") == ""


def test_notes_must_state_the_built_hash(tmp_path, monkeypatch, capsys):
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(CHANGELOG, encoding="utf-8")
    monkeypatch.setattr(release_notes, "CHANGELOG", changelog)
    assert release_notes.main(["0.2.0", "--sha256", HASH_A]) == 0
    assert capsys.readouterr().out.startswith("**Theme:** Candidate.")
    assert release_notes.main(["0.2.0", "--sha256", HASH_B]) == 1
    err = capsys.readouterr().err
    assert HASH_A in err and HASH_B in err
    assert release_notes.main(["0.1.0", "--sha256", HASH_B]) == 1
    assert "states none" in capsys.readouterr().err
    assert release_notes.main(["Unreleased"]) == 1
    assert release_notes.main(["0.2.0", "--sha", HASH_A]) == 2


def test_a_module_in_a_subdirectory_stops_the_build(monkeypatch):
    """The .pyz holds the flat analyser; a nested module would go missing from it."""
    build_release = load_script("build_release")
    listed = b"cli.py\0sub/extra.py\0"
    monkeypatch.setattr(build_release.subprocess, "run",
                        lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, stdout=listed))
    with pytest.raises(SystemExit, match="sub/extra.py"):
        build_release.tracked_modules()
