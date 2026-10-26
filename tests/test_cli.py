"""Commands, flags and the exit ladder (docs/design.md § Exit codes)."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

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



@pytest.fixture(scope="module")
def pyz(tmp_path_factory):
    """frameledger.pyz as the release builds it: what an engine runs."""
    outdir = tmp_path_factory.mktemp("release")
    subprocess.run([sys.executable, "-I", str(ROOT / "scripts" / "build_release.py"), str(outdir), "v0.0.0"],
                   capture_output=True, check=True)
    return outdir / "frameledger.pyz"


def headless(target, args):
    """Run `target` with no display, no terminal and no input: only PATH,
    and on Windows SYSTEMROOT, which Python needs to start; no LANG, so
    Python runs in the C locale."""
    env = {key: os.environ[key] for key in ("PATH", "SYSTEMROOT") if key in os.environ}
    return subprocess.run([sys.executable, "-I", str(target), *args], env=env, stdin=subprocess.DEVNULL,
                          capture_output=True, text=True, encoding="utf-8", start_new_session=True,
                          check=False)


RUN = str(FIXTURES / "in-order.csv")
HEADLESS = [
    ["--selftest"],
    ["check", RUN],
    ["report", RUN],
    ["floor", RUN, "--fps", "60", "--warmup-s", "0"],
    ["compare", "--old", RUN, RUN, RUN, "--new", RUN, RUN, RUN],
    ["bisect", RUN, "--measure", "frame/wall", "--kind", "view", "--bad-above", "15.999"],
    ["bisect", RUN, "--measure", "frame/wall", "--kind", "view", "--bad-above", "15.999", "--json"],
    ["bisect", RUN, "--measure", "frame/wall", "--kind", "view"],
]


@pytest.mark.parametrize("args", HEADLESS, ids=lambda args: " ".join(a for a in args if a != RUN))
def test_headless(capsys, pyz, args):
    """S20: run headless from the release's frameledger.pyz, each command
    gives the same output and exit code as it does in this process,
    reading real run files (DOOM Ants)."""
    code = cli.main(list(args))
    expected = capsys.readouterr()
    done = headless(pyz, args)
    assert (done.returncode, done.stdout, done.stderr) == (code, expected.out, expected.err)


def test_headless_results_are_whole(pyz):
    """The output is right, not only present: a sentence, a JSON result, and
    an error message all come through intact."""
    done = headless(pyz, ["check", RUN])
    assert (done.returncode, done.stdout) == (0, "The file meets the run-file format.\n")
    done = headless(pyz, HEADLESS[6])
    assert done.returncode == 1 and json.loads(done.stdout)["verdict"] == "bad"
    done = headless(pyz, HEADLESS[7])
    assert done.returncode == 128
    assert "give --bad-above X, or --good FILE... and --bad FILE..." in done.stderr


def test_headless_tree():
    """The tree runs headless too: `python3 -I src/frameledger`."""
    done = headless(ROOT / "src" / "frameledger", ["--selftest"])
    assert done.returncode == 0, done.stderr
