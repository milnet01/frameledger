"""The release archive (scripts/build_release.py; docs/design.md § The stack,
and what it rules out): what it holds, that it rebuilds to the same bytes,
that its frameledger.pyz runs, and that its launcher runs it by name; and the
release notes' hash check; and that the writer header names the release
(INV-96)."""

import hashlib
import importlib.util
import json
import re
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
                                 "include/frameledger.h",
                                 *sorted(f"schemas/{p.name}" for p in (ROOT / "src/frameledger/schemas").iterdir())]
        assert zf.read("include/frameledger.h") == (ROOT / "include" / "frameledger.h").read_bytes()


def test_header_names_the_release():
    """A vendored copy of the header says which release it came from."""
    import cli
    header = (ROOT / "include" / "frameledger.h").read_text(encoding="utf-8")
    assert re.findall(r'^#define FLED_VERSION\s+"(.*)"$', header, re.MULTILINE) == [cli.VERSION]
    # The release bump replaces this exact text, spacing included, so a
    # reformatted define fails here and not one release later (UT Ants).
    bumped = {entry["path"]: entry["pattern"]
              for entry in json.loads((ROOT / ".claude" / "bump.json").read_text(encoding="utf-8"))["files"]}
    assert header.count(bumped["include/frameledger.h"].replace("{OLD}", cli.VERSION)) == 1


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
    analyser = ROOT / "src" / "frameledger"
    with zipfile.ZipFile(pyz) as zf:
        assert sorted(zf.namelist()) == sorted([*(p.name for p in analyser.glob("*.py")),
                                                *(f"kit/{p.name}" for p in (analyser / "kit").iterdir()),
                                                *(f"schemas/{p.name}" for p in (analyser / "schemas").iterdir())])


def wheel(outdir, tag):
    """Build under `tag`; return the one wheel written."""
    build(outdir, tag)
    [found] = outdir.glob("*.whl")
    return found


def test_the_wheel_holds_the_pyz_files_under_frameledger(tmp_path):
    """FLED-0043: what pip installs is what the .pyz runs, and the metadata pip needs."""
    import cli
    built = wheel(tmp_path, "v9.9.9")
    assert built.name == f"frameledger-{cli.VERSION}-py3-none-any.whl"
    info = f"frameledger-{cli.VERSION}.dist-info"
    with zipfile.ZipFile(tmp_path / "frameledger.pyz") as pyz, zipfile.ZipFile(built) as whl:
        assert whl.namelist() == sorted([*(f"frameledger/{name}" for name in pyz.namelist()),
                                         *(f"{info}/{name}" for name in ("METADATA", "RECORD", "WHEEL",
                                                                         "entry_points.txt", "licenses/LICENSE"))])
        assert f"Version: {cli.VERSION}\n" in whl.read(f"{info}/METADATA").decode()
        assert whl.read(f"{info}/entry_points.txt") == b"[console_scripts]\nframeledger = frameledger:main\n"


def test_a_candidate_wheel_has_its_number_and_a_rebuild_is_the_same_bytes(tmp_path):
    import cli
    candidate = wheel(tmp_path / "rc", "v0.1.0-rc.2")
    assert candidate.name == f"frameledger-{cli.VERSION}rc2-py3-none-any.whl"
    assert wheel(tmp_path / "a", "v0.1.0").read_bytes() == wheel(tmp_path / "b", "v0.1.0").read_bytes()


def test_pip_installs_the_wheel_as_a_frameledger_command(tmp_path):
    """Installed by pip into a fresh environment, with no network: the command
    runs by name and finds its kit and schemas, and `python -m frameledger`
    runs too."""
    import cli
    built = wheel(tmp_path / "dist", "v9.9.9")
    env = tmp_path / "env"
    subprocess.run([sys.executable, "-m", "venv", str(env)], check=True)
    bin_dir = env / ("Scripts" if sys.platform == "win32" else "bin")
    python = bin_dir / "python"
    subprocess.run([str(python), "-m", "pip", "install", "--quiet", "--no-index", "--no-deps", str(built)],
                   check=True, capture_output=True)
    version = subprocess.run([str(bin_dir / "frameledger"), "--version"], capture_output=True, text=True)
    assert version.stdout == f"frameledger {cli.VERSION}\n", version.stderr
    kit = subprocess.run([str(bin_dir / "frameledger"), "kit", str(tmp_path / "kit")], capture_output=True, text=True)
    assert kit.returncode == 0, kit.stderr
    assert (tmp_path / "kit" / "basic.csv").read_bytes() == (ROOT / "src/frameledger/kit/basic.csv").read_bytes()
    schema = subprocess.run([str(bin_dir / "frameledger"), "schema", "check"], capture_output=True)
    assert schema.stdout == (ROOT / "src/frameledger/schemas/check.schema.json").read_bytes(), schema.stderr
    selftest = subprocess.run([str(python), "-I", "-m", "frameledger", "--selftest"], capture_output=True, text=True)
    assert selftest.returncode == 0, selftest.stdout + selftest.stderr


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


@pytest.mark.parametrize("nested", ["sub/extra.py", "kit/extra.py", "kit/sub/case.json", "schemas/extra.py",
                                    "schemas/sub/check.schema.json"])
def test_a_module_in_a_subdirectory_stops_the_build(monkeypatch, nested):
    """The .pyz holds the flat analyser and the flat data of kit/ and
    schemas/; a nested module would go missing from it, and neither
    folder holds a module."""
    build_release = load_script("build_release")
    listed = f"cli.py\0kit/README.txt\0{nested}\0".encode()
    monkeypatch.setattr(build_release.subprocess, "run",
                        lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, stdout=listed))
    with pytest.raises(SystemExit, match=nested):
        build_release.tracked_files()
