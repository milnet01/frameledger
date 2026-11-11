"""The release archive (scripts/build_release.py; docs/design.md § The stack,
and what it rules out): what it holds, that it rebuilds to the same bytes,
that its frameledger.pyz runs, and that its launcher runs it by name; and the
release notes' hash check."""

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
        assert zf.namelist() == ["LICENSE", "frameledger", "frameledger.cmd", "frameledger.pyz",
                                 "include/frameledger.h"]
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


def test_only_the_linux_launcher_runs_and_the_windows_one_has_crlf(tmp_path):
    archive, _ = build(tmp_path, "v9.9.9")
    with zipfile.ZipFile(archive) as zf:
        modes = {info.filename: info.external_attr >> 16 for info in zf.infolist()}
        cmd = zf.read("frameledger.cmd")
    assert modes.pop("frameledger") == 0o100755
    assert set(modes.values()) == {0o100644}
    assert cmd.count(b"\r\n") == cmd.count(b"\n") > 0


def on_path(tmp_path, launcher):
    """A runner for `frameledger ARGS` from a PATH holding only a symlink to
    `launcher`, as the README puts it, and this Python as python3."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "frameledger").symlink_to(launcher)
    (bin_dir / "python3").symlink_to(sys.executable)  # this Python, not the machine's
    env = {"PATH": f"{bin_dir}:/usr/bin:/bin"}
    return lambda *args: subprocess.run(["frameledger", *args], capture_output=True, text=True, env=env,
                                        cwd=tmp_path)


@pytest.mark.skipif(sys.platform == "win32", reason="the POSIX launcher")
def test_the_launcher_runs_by_name_through_a_symlink(tmp_path):
    """It finds the .pyz beside the real file, passes each argument whole and
    returns the analyser's exit."""
    archive, _ = build(tmp_path / "dist", "v9.9.9")
    unpacked = tmp_path / "frameledger"
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(unpacked)
    (unpacked / "frameledger").chmod(0o755)  # extractall drops the mode, as python -m zipfile -e does
    run = on_path(tmp_path, Path("..") / "frameledger" / "frameledger")

    version = run("--version")
    assert version.returncode == 0, version.stderr
    assert version.stdout.startswith("frameledger ")
    direct = subprocess.run([sys.executable, "-I", str(unpacked / "frameledger.pyz"), "check", "no such run.csv"],
                            capture_output=True, text=True, cwd=tmp_path)
    launched = run("check", "no such run.csv")
    assert direct.returncode != 0
    assert (launched.returncode, launched.stdout, launched.stderr) == (direct.returncode, direct.stdout,
                                                                       direct.stderr)


@pytest.mark.skipif(sys.platform == "win32", reason="the POSIX launcher")
def test_the_launcher_runs_a_source_checkout(tmp_path):
    """With no .pyz beside it, the launcher in launcher/ runs src/frameledger."""
    run = on_path(tmp_path, ROOT / "launcher" / "frameledger")
    expected = subprocess.run([sys.executable, "-I", str(ROOT / "src" / "frameledger"), "--version"],
                              capture_output=True, text=True, check=True).stdout
    launched = run("--version")
    assert (launched.returncode, launched.stdout) == (0, expected), launched.stderr


@pytest.mark.skipif(sys.platform == "win32", reason="the POSIX launcher")
def test_a_copied_launcher_says_it_cannot_find_the_analyser(tmp_path):
    """A copy, not a link, has no analyser beside it: a plain message and 127,
    which git bisect run cannot read as a verdict."""
    copy = tmp_path / "copied" / "frameledger"
    copy.parent.mkdir()
    copy.write_bytes((ROOT / "launcher" / "frameledger").read_bytes())
    copy.chmod(0o755)
    launched = on_path(tmp_path, copy)("--version")
    assert launched.returncode == 127
    assert launched.stdout == ""
    assert "no frameledger.pyz beside" in launched.stderr and "do not copy it" in launched.stderr


def test_a_crlf_checkout_ships_the_same_windows_launcher(tmp_path):
    """A Windows checkout holds the .cmd with CRLF; the zip gets CRLF once, not CR CR LF."""
    build_release = load_script("build_release")
    lf = b"@echo off\nexit /b 0\n"
    checkout = tmp_path / "frameledger.cmd"
    checkout.write_bytes(lf.replace(b"\n", b"\r\n"))
    assert build_release.crlf(build_release.source_bytes(checkout)) == b"@echo off\r\nexit /b 0\r\n"


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
