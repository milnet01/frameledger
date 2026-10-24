"""Commands, flags and the exit ladder (docs/design.md § Exit codes)."""

import json
import subprocess
import sys
from pathlib import Path

import cli

ROOT = Path(__file__).parent.parent
FIXTURES = Path(__file__).parent / "fixtures"


def test_version(capsys):
    assert cli.main(["--version"]) == 0
    assert capsys.readouterr().out.startswith("frameledger ")


def test_bad_argument_is_exit_3(capsys):
    """argparse's own exit 2 would read as "inconclusive, re-run"."""
    assert cli.main(["check", "--no-such-flag", "x.csv"]) == 3
    assert cli.main([]) == 3
    assert "no-such-flag" in capsys.readouterr().err


def test_text_opens_with_the_sentences(capsys):
    """The text form starts with the same sentences the JSON summary holds."""
    path = str(FIXTURES / "zero-wall.csv")
    assert cli.main(["check", "--json", path]) == 1
    summary = json.loads(capsys.readouterr().out)["summary"]
    assert cli.main(["check", path]) == 1
    text = capsys.readouterr().out.splitlines()
    assert text[: len(summary)] == summary
    assert any("wall" in line for line in text[len(summary):])


def test_selftest(capsys):
    assert cli.main(["--selftest"]) == 0
    capsys.readouterr()
    assert cli.main(["--selftest", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert (out["command"], out["verdict"]) == ("selftest", "pass")


def test_directory_run_form():
    """`python3 -I src/frameledger` works: isolated mode still finds the modules."""
    done = subprocess.run(
        [sys.executable, "-I", str(ROOT / "src" / "frameledger"), "check", str(FIXTURES / "schema-1.csv")],
        capture_output=True, text=True, check=False,
    )
    assert done.returncode == 0, done.stderr
