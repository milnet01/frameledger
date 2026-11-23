"""docs/guide.md's examples, run as a reader runs them (FLED-0044).

The guide's files are written out of its code blocks, and each `$`
command in a `text` block is run in that folder. Its output must be the
guide's, byte for byte, so a change to the analyser or the header that
breaks an example fails here. `frameledger` runs this tree's analyser,
and `frameledger/include` is this tree's include/. A command shown with
run files the guide does not give, `compare` and `alternate`, is not
run. A missing compiler fails: a check that did not run must not read
as a pass.
"""

import re
import shlex
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).parent.parent
GUIDE = ROOT / "docs" / "guide.md"
# A fenced block, indented or not: its indent, its language, its body.
BLOCK = re.compile(r"^( *)```(\w*)\n(.*?)^\1```", re.M | re.S)
NOT_RUN = ("frameledger compare", "frameledger alternate")


def blocks() -> list[tuple[str, str]]:
    text = GUIDE.read_text(encoding="utf-8")
    return [(lang, textwrap.dedent(body)) for _, lang, body in BLOCK.findall(text)]


def files() -> dict[str, str]:
    """The files a reader saves from the guide, found by what they hold."""
    found = {}
    for lang, body in blocks():
        if body.startswith("# frameledger {"):
            found["run.csv"] = body
        elif body.startswith("Application,"):
            found["capture.csv"] = body
        elif lang == "c":
            found["fake_engine.c"] = body
        elif lang == "cpp":
            found["fake_engine.cpp"] = body
    return found


def commands() -> list[tuple[str, str]]:
    """(command, the output the guide shows) for each `$` line, in order."""
    shown = []
    for lang, body in blocks():
        if lang == "text" and body.startswith("$ "):
            for chunk in re.split(r"^\$ ", body, flags=re.M)[1:]:
                command, _, output = chunk.partition("\n")
                shown.append((command, output))
    return shown


def test_the_guide_gives_every_file_its_commands_use():
    assert sorted(files()) == ["capture.csv", "fake_engine.c", "fake_engine.cpp", "run.csv"]


def test_every_command_prints_what_the_guide_shows(tmp_path):
    for tool in ("cc", "c++"):
        assert shutil.which(tool), f"{tool} is not installed, so the guide's examples cannot be built"
    for name, body in files().items():
        (tmp_path / name).write_text(body, encoding="utf-8")
    analyser = f"{shlex.quote(sys.executable)} -I {shlex.quote(str(ROOT / 'src' / 'frameledger'))}"
    ran = []
    for command, output in commands():
        if command.startswith(NOT_RUN):
            continue
        real = re.sub(r"^frameledger ", lambda _: analyser + " ", command)
        real = real.replace("frameledger/include", shlex.quote(str(ROOT / "include")))
        # which(), not a bare "bash": Windows looks in System32 first, and finds WSL's.
        got = subprocess.run([shutil.which("bash"), "-c", real], cwd=tmp_path, capture_output=True, text=True)
        # The analyser's verdict is in its output; a build or an example
        # program must also succeed, so a failed build stops here.
        if not command.startswith("frameledger "):
            assert got.returncode == 0, f"$ {command} exited {got.returncode}\n{got.stderr}"
        assert got.stdout == output, f"$ {command}\n{got.stderr}"
        ran.append(command)
    # The commands the guide's sections rest on, so a lost block is not a pass.
    for needed in ("frameledger check run.csv", "frameledger report run.csv", "./fake_engine c-run.csv",
                   "./fake_engine_cpp", "frameledger import presentmon", "frameledger floor c-run.csv"):
        assert any(command.startswith(needed) for command in ran), f"the guide no longer runs {needed}"
