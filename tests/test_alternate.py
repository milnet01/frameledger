"""`alternate`: old and new runs in turn, each into its own file (S21).

Invariants from docs/specs/FLED-0001-run-file-format.md § 5: INV-78 to
INV-81, the rules of § 4.15. Each test runs the analyser from the tree as
a subprocess, as a user would, with tests/fixtures/alternate/fake_engine.py
standing in for the engine.
"""

import json
import os
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from test_compare import alike, run_text

ROOT = Path(__file__).parent.parent
FAKE = Path(__file__).parent / "fixtures" / "alternate" / "fake_engine.py"
TIMED = ["old-1", "new-1", "new-2", "old-2", "old-3", "new-3"]


class Bench:
    """An empty run folder, an order log, and one source run file a side:
    the new build's opaque pass 1 ms slower, so the compare fails."""

    def __init__(self, tmp_path: Path):
        self.out = tmp_path / "ab"
        self.out.mkdir()
        self.log = tmp_path / "order.log"
        self.sources = {}
        for side, opaque in (("old", 10.0), ("new", 11.0)):
            self.sources[side] = tmp_path / f"{side}-source.csv"
            self.sources[side].write_text(run_text(alike(opaque)), encoding="utf-8")

    def command(self, side: str) -> str:
        words = [sys.executable, "-I", str(FAKE), side, str(self.sources[side]), str(self.log)]
        return " ".join(shlex.quote(word) for word in words) + " {run}"

    def args(self, *flags: str) -> list[str]:
        return ["alternate", "--old", self.command("old"), "--new", self.command("new"),
                "--out", str(self.out), "--runs", "3", *flags]

    def order(self) -> list[str]:
        return self.log.read_text(encoding="utf-8").split() if self.log.exists() else []

    def files(self) -> list[str]:
        return sorted(path.name for path in self.out.iterdir())


def analyser(args: list[str], env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-I", str(ROOT / "src" / "frameledger"), *args],
                          capture_output=True, text=True, stdin=subprocess.DEVNULL,
                          env={**os.environ, **(env or {})}, check=False)


def without_added(out: dict) -> dict:
    """The result with alternate's own keys, and the command's name, taken off."""
    result = {k: v for k, v in out["result"].items() if k not in ("commands", "out", "warmup", "stopped")}
    return {**out, "command": None, "result": result}


@pytest.mark.parametrize("warmup", [0, 1])
def test_alternates_and_compares(tmp_path, warmup):
    """INV-78: runs go in pairs, old first in odd pairs and new first in even
    ones, each into its own file, warm-ups first and never compared; the
    timed files are judged exactly as `compare` judges them."""
    bench = Bench(tmp_path)
    done = analyser(bench.args("--warmup", str(warmup), "--json"))
    warmups = ["old-warmup-1", "new-warmup-1"] if warmup else []
    assert bench.order() == [name.split("-")[0] for name in warmups + TIMED]
    assert bench.files() == sorted(f"{name}.csv" for name in warmups + TIMED)
    out = json.loads(done.stdout)
    assert out["result"]["warmup"] == warmup and out["result"]["stopped"] is None
    assert out["result"]["out"] == str(bench.out)

    paths = {side: [str(bench.out / f"{side}-{n}.csv") for n in (1, 2, 3)] for side in ("old", "new")}
    compared = analyser(["compare", "--old", *paths["old"], "--new", *paths["new"], "--json"])
    assert done.returncode == compared.returncode == 1  # the new opaque pass is slower
    assert without_added(out) == without_added(json.loads(compared.stdout))


SETUP_ERRORS = {  # each case, and what its error message must name
    "no placeholder": "must hold {run}", "runs 2": "from 3 to 100", "runs 101": "from 3 to 100",
    "warmup 11": "from 0 to 10", "missing dir": "is not an existing folder",
    "space in dir": "may hold only", "existing run file": "new-2.csv already exists",
    "existing warm-up file": "new-warmup-1.csv already exists",
}


@pytest.mark.parametrize("case", SETUP_ERRORS)
def test_setup_errors_run_nothing(tmp_path, case):
    """INV-79: each setup error gives exit 3 before any command starts, and an
    existing run file is left byte for byte as it was. The message is checked
    too, since an unknown command would also exit 3 and run nothing."""
    bench = Bench(tmp_path)
    args = bench.args()
    existing = None
    if case == "no placeholder":
        args[2] = args[2].replace(" {run}", "")
    elif case.startswith(("runs", "warmup")):
        flag, value = case.split()
        args += [f"--{flag}", value]
    elif case == "missing dir":
        args[6] = str(tmp_path / "nowhere")
    elif case == "space in dir":
        spaced = tmp_path / "a b"
        spaced.mkdir()
        args[6] = str(spaced)
    else:
        name = "new-2.csv" if case == "existing run file" else "new-warmup-1.csv"
        existing = bench.out / name
        existing.write_bytes(b"keep me\r\n")
        if case == "existing warm-up file":
            args += ["--warmup", "1"]
    done = analyser(args)
    assert done.returncode == 3, done.stderr
    assert SETUP_ERRORS[case] in done.stderr
    assert bench.order() == []
    if existing:
        assert existing.read_bytes() == b"keep me\r\n"


@pytest.mark.parametrize("mode", ["exit4", "nofile"])
def test_failed_run_stops(tmp_path, mode):
    """INV-80: a failing run stops the rest; only finished runs' files remain."""
    bench = Bench(tmp_path)
    done = analyser(bench.args("--json"), env={"FAKE_ENGINE": f"new-2={mode}"})
    assert done.returncode == 3
    out = json.loads(done.stdout)
    stopped = out["result"]["stopped"]
    assert stopped["run"] == "new-2" and stopped["finished"] == ["old-1", "new-1"]
    assert bench.order() == ["old", "new", "new"]
    assert bench.files() == ["new-1.csv", "old-1.csv"]
    assert "measures" not in out["result"]
    if mode == "exit4":
        assert stopped["exit_code"] == 4
        assert out["summary"][0] == "new-2 failed: the command exited with code 4."
    else:
        assert stopped["exit_code"] is None
        assert str(bench.out / "new-2.csv") in out["summary"][0]
    assert out["summary"][1] == f"Its command was: {stopped['command']}"
    assert str(bench.out / "new-2.csv") in stopped["command"]


@pytest.mark.skipif(sys.platform == "win32", reason="SIGINT to a process group is POSIX")
def test_interrupted_run_stops(tmp_path):
    """INV-80: an interrupt during new-2 stops it as a failure would."""
    bench = Bench(tmp_path)
    process = subprocess.Popen([sys.executable, "-I", str(ROOT / "src" / "frameledger"),
                                *bench.args("--json")], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               stdin=subprocess.DEVNULL, text=True, start_new_session=True,
                               env={**os.environ, "FAKE_ENGINE": "new-2=wait"})
    deadline = time.monotonic() + 30
    while len(bench.order()) < 3 and time.monotonic() < deadline:
        time.sleep(0.05)
    time.sleep(0.3)  # let new-2's engine reach its sleep
    os.killpg(process.pid, signal.SIGINT)
    stdout, _ = process.communicate(timeout=30)
    assert process.returncode == 3
    stopped = json.loads(stdout)["result"]["stopped"]
    assert stopped["run"] == "new-2" and stopped["exit_code"] is None
    assert stopped["finished"] == ["old-1", "new-1"]
    assert bench.files() == ["new-1.csv", "old-1.csv"]


def test_engine_output_to_stderr(tmp_path):
    """INV-81: the engine's output never reaches standard output."""
    bench = Bench(tmp_path)
    done = analyser(bench.args("--json"), env={"FAKE_ENGINE_SAY": "1"})
    json.loads(done.stdout)  # one JSON object and nothing else
    assert "engine says hi" not in done.stdout
    assert "engine says hi" in done.stderr
    assert "alternate: running new-2 (3 of 6)" in done.stderr
