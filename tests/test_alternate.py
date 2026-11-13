"""`alternate`: old and new runs in turn, each into its own file (S21).

Invariants from docs/specs/FLED-0001-run-file-format.md § 5: INV-78 to
INV-81 and INV-95, the rules of § 4.15. Each test runs the analyser from the tree as
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

import alternate
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

    def command(self, side: str, prefix: str = "", suffix: str = "") -> str:
        """The fake engine's command line, between `prefix` and `suffix`:
        "exec " makes the shell become the engine; "; exit $?" keeps the
        shell running after it."""
        words = [sys.executable, "-I", str(FAKE), side, str(self.sources[side]), str(self.log)]
        # cmd.exe reads double quotes, never /bin/sh's single quotes.
        line = subprocess.list2cmdline(words) if sys.platform == "win32" else shlex.join(words)
        return prefix + line + " {run}" + suffix

    def args(self, *flags: str, prefix: str = "", suffix: str = "") -> list[str]:
        return ["alternate", "--old", self.command("old", prefix, suffix),
                "--new", self.command("new", prefix, suffix), "--out", str(self.out), "--runs", "3", *flags]

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


@pytest.mark.parametrize("flags, table", [
    ((), "Runs:"),
    (("--measure", "gpu/opaque"), "Each run's value of each named measure"),  # UT Ants
])
def test_text_is_compares(tmp_path, flags, table):
    """INV-78: the text is compare's text over the same files, tables and all."""
    bench = Bench(tmp_path)
    done = analyser(bench.args(*flags))
    paths = {side: [str(bench.out / f"{side}-{n}.csv") for n in (1, 2, 3)] for side in ("old", "new")}
    compared = analyser(["compare", "--old", *paths["old"], "--new", *paths["new"], *flags])
    assert table in compared.stdout  # compare's tables are there to be matched
    assert done.stdout == compared.stdout


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


def test_stopped_text_is_its_sentences(tmp_path):
    """INV-80: a stopped run's text is its two sentences and nothing of
    compare's, since no run was compared (DOOM Ants)."""
    bench = Bench(tmp_path)
    done = analyser(bench.args(), env={"FAKE_ENGINE": "new-2=exit4"})
    assert done.returncode == 3
    lines = done.stdout.splitlines()
    assert lines[0] == "new-2 failed: the command exited with code 4."
    assert lines[1].startswith("Its command was: ")
    assert len(lines) == 2


@pytest.mark.skipif(sys.platform == "win32", reason="signals and /bin/sh's exec and $? are POSIX (Vestige)")
@pytest.mark.parametrize("shell_stays, reason", [
    (False, "the command was killed by signal 9 (SIGKILL)"),
    (True, "the command exited with code 137, as the shell reports a command killed by signal 9 (SIGKILL)"),
])
def test_killed_command_names_its_signal(tmp_path, shell_stays, reason):
    """INV-80: a command killed by a signal is named by the signal. With
    `exec` the shell becomes the engine, so the analyser sees the signal;
    with the shell still running after it, the shell reports 128 + 9,
    which is decoded."""
    bench = Bench(tmp_path)
    shape = {"suffix": "; exit $?"} if shell_stays else {"prefix": "exec "}
    done = analyser(bench.args("--json", **shape), env={"FAKE_ENGINE": "new-2=killself"})
    assert done.returncode == 3
    out = json.loads(done.stdout)
    assert out["result"]["stopped"]["exit_code"] == (137 if shell_stays else None)
    assert out["summary"][0] == f"new-2 failed: {reason}."


@pytest.mark.skipif(sys.platform == "win32", reason="process groups are POSIX")
def test_brief_leftover_is_waited_for(tmp_path):
    """INV-80: a process that ends within SETTLE_S of its command, as a
    headless display tearing down does, fails nothing (DOOM Ants)."""
    bench = Bench(tmp_path)
    done = analyser(bench.args("--json"), env={"FAKE_ENGINE": "new-2=background:0.3"})
    assert json.loads(done.stdout)["result"]["stopped"] is None
    assert done.returncode == 1  # all six ran and were compared; the new build is slower


@pytest.mark.skipif(sys.platform == "win32", reason="process groups are POSIX")
def test_left_processes_fail_the_run(tmp_path):
    """INV-80: a command that exits 0 but leaves a process running past
    SETTLE_S fails, and the process is ended, so it cannot overlap the
    next run."""
    bench = Bench(tmp_path)
    done = analyser(bench.args("--json"), env={"FAKE_ENGINE": "new-2=background:30"})
    assert done.returncode == 3
    out = json.loads(done.stdout)
    assert out["summary"][0] == "new-2 failed: the command left processes running."
    assert bench.files() == ["new-1.csv", "old-1.csv"]
    assert engine_ended(int(Path(str(bench.log) + ".pid").read_text(encoding="utf-8")))


def engine_ended(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    return False


@pytest.mark.skipif(sys.platform == "win32", reason="process groups are POSIX")
def test_a_group_that_refuses_a_signal_is_waited_for(monkeypatch):
    """INV-80: macOS refuses a signal to a group whose processes have ended
    and are not yet collected, where Linux accepts it (FLED-0038). The
    group is waited for as one still ending, and the run goes on."""
    process = subprocess.Popen([sys.executable, "-c", "pass"], start_new_session=True)
    process.wait()
    refusals = [PermissionError] * 3  # to the signal itself, then to two looks at the group
    asked = []

    def killpg(_pid, signum):
        asked.append(signum)
        raise refusals.pop() if refusals else ProcessLookupError

    monkeypatch.setattr(alternate.os, "killpg", killpg)
    assert alternate._end_group(process, signal.SIGTERM, []) == ""
    assert asked == [signal.SIGTERM, 0, 0, 0]  # never the kill: the group ended in time


@pytest.mark.skipif(sys.platform != "darwin", reason="what macOS answers; Linux accepts the signal")
def test_macos_refuses_a_signal_to_an_ended_group():
    """The premise of the test above, asked of macOS itself: a group whose
    one process has ended and is not yet collected refuses a signal."""
    process = subprocess.Popen([sys.executable, "-c", "pass"], start_new_session=True)
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                os.killpg(process.pid, 0)
            except PermissionError:
                return
            time.sleep(0.01)
        pytest.fail("macOS accepted a signal to the ended group for 30 seconds")
    finally:
        process.wait()


@pytest.mark.skipif(sys.platform == "win32", reason="process groups and SIGTERM are POSIX")
@pytest.mark.parametrize("target, stop", [("group", signal.SIGINT), ("analyser", signal.SIGINT),
                                          ("analyser", signal.SIGTERM)])
def test_interrupted_run_stops(tmp_path, target, stop):
    """INV-80: a stop during new-2 ends it as a failure would, whether the
    signal went to the terminal's whole group (Ctrl-C) or to the analyser
    alone (kill, timeout, a service manager). The command is compound, so
    the shell stays between the analyser and the engine; the engine must
    still end, and its file, written before the stop, be deleted."""
    bench = Bench(tmp_path)
    process = subprocess.Popen([sys.executable, "-I", str(ROOT / "src" / "frameledger"),
                                *bench.args("--json", prefix="cd . && ")],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
                               text=True, start_new_session=True,
                               env={**os.environ, "FAKE_ENGINE": "new-2=wait"})
    pid_file = Path(str(bench.log) + ".pid")
    deadline = time.monotonic() + 30
    while not pid_file.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    time.sleep(0.2)  # the pid file is written; let the engine reach its sleep
    engine = int(pid_file.read_text(encoding="utf-8"))
    if target == "group":
        os.killpg(process.pid, stop)
    else:
        process.send_signal(stop)
    stdout, stderr = process.communicate(timeout=30)
    assert process.returncode == 3 and stdout, stderr
    stopped = json.loads(stdout)["result"]["stopped"]
    assert stopped["run"] == "new-2" and stopped["exit_code"] is None
    assert signal.Signals(stop).name in stopped["reason"]
    assert stopped["finished"] == ["old-1", "new-1"]
    assert bench.files() == ["new-1.csv", "old-1.csv"]
    assert engine_ended(engine)


def windows_process_ended(pid: int) -> bool:
    """os.kill(pid, 0) would end the process on Windows, so ask tasklist.
    taskkill /F can return before its target has gone, and alternate
    waits only for cmd.exe, so ask for up to 5 seconds (DOOM Ants)."""
    deadline = time.monotonic() + 5
    while True:
        listing = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True,
                                 text=True, check=False).stdout
        if str(pid) not in listing.split():
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.1)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows process groups and Ctrl-Break")
@pytest.mark.parametrize("mode", ["wait", "stubborn"])
def test_windows_stop_ends_the_tree(tmp_path, mode):
    """INV-95: Ctrl-Break during new-2 ends the engine behind cmd.exe.
    `wait` ends on the Ctrl-Break passed on to its group; `stubborn`
    ignores it, so only taskkill /T /F, after GRACE_S, can end it. The
    analyser runs in its own group, so the Ctrl-Break sent to it reaches
    nothing else, and the engine is in a third group of its own.

    The time from Ctrl-Break to exit tells the two apart (DOOM Ants):
    without it, a stop never passed on would pass `wait` too, ended by
    the kill. The engine ends by itself after 60 seconds, and the test
    waits for that, since the engine holds the analyser's standard
    error. So `stubborn` has an upper bound too, and the reason must not
    say the kill failed: without them a kill never sent passes
    (Vestige's Windows run)."""
    import alternate

    bench = Bench(tmp_path)
    process = subprocess.Popen([sys.executable, "-I", str(ROOT / "src" / "frameledger"),
                                *bench.args("--json", prefix="cd . && ")],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
                               text=True, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                               env={**os.environ, "FAKE_ENGINE": f"new-2={mode}"})
    pid_file = Path(str(bench.log) + ".pid")
    deadline = time.monotonic() + 30
    while not pid_file.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    time.sleep(0.5)  # the pid file is written; let the engine reach its sleep
    engine = int(pid_file.read_text(encoding="utf-8"))
    process.send_signal(signal.CTRL_BREAK_EVENT)
    sent = time.monotonic()
    stdout, _ = process.communicate(timeout=60)
    took = time.monotonic() - sent
    assert process.returncode == 3
    if mode == "wait":
        assert took < alternate.GRACE_S
    else:
        assert alternate.GRACE_S <= took < 3 * alternate.GRACE_S
    stopped = json.loads(stdout)["result"]["stopped"]
    assert stopped["run"] == "new-2" and "SIGBREAK" in stopped["reason"]
    assert "did not end" not in stopped["reason"]
    assert stopped["finished"] == ["old-1", "new-1"]
    assert bench.files() == ["new-1.csv", "old-1.csv"]
    assert windows_process_ended(engine)


class FakeWindowsCommand:
    """A running cmd.exe as _signal_windows_tree sees it, recording what
    it was sent; `console=False` raises as GenerateConsoleCtrlEvent does
    without a console."""

    pid = 4242

    def __init__(self, console: bool = True):
        self.console, self.sent = console, []

    def poll(self):
        return None

    def send_signal(self, signum):
        if not self.console:
            raise OSError("The handle is invalid")
        self.sent.append(signum)


@pytest.mark.parametrize("stop", [signal.SIGINT, signal.SIGTERM])
@pytest.mark.parametrize("console", [True, False])
def test_windows_stop_is_never_a_kill(monkeypatch, stop, console):
    """INV-95 (UT Ants): every stop, SIGTERM included, is passed on as
    Ctrl-Break and waits out the grace; only the kill runs taskkill. With
    no console, Ctrl-Break cannot be sent and the stop goes on to the
    kill instead of crashing. Runs anywhere: it calls the Windows branch
    directly, with taskkill recorded rather than run."""
    import alternate

    monkeypatch.setattr(alternate.signal, "CTRL_BREAK_EVENT", "ctrl-break", raising=False)
    killed = []
    monkeypatch.setattr(alternate.subprocess, "run", lambda args, **_: killed.append(args))
    command = FakeWindowsCommand(console)
    alternate._signal_windows_tree(command, stop)
    assert killed == [] and command.sent == (["ctrl-break"] if console else [])
    alternate._signal_windows_tree(command, alternate.KILL)
    assert killed == [["taskkill", "/PID", "4242", "/T", "/F"]]


def test_windows_kill_is_no_stop_signal(monkeypatch):
    """INV-95 (UT Ants): on a system without SIGKILL, as Windows is, the
    kill still differs from every stop signal, so a SIGTERM stop is never
    taken for the kill."""
    import importlib

    import alternate

    monkeypatch.delattr(signal, "SIGKILL", raising=False)  # Windows has none to delete (Vestige)
    try:
        windows_like = importlib.reload(alternate)
        assert windows_like.KILL not in windows_like.STOP_SIGNALS
    finally:
        monkeypatch.undo()
        importlib.reload(alternate)


def test_engine_output_to_stderr(tmp_path):
    """INV-81: the engine's output never reaches standard output."""
    bench = Bench(tmp_path)
    done = analyser(bench.args("--json"), env={"FAKE_ENGINE_SAY": "1"})
    json.loads(done.stdout)  # one JSON object and nothing else
    assert "engine says hi" not in done.stdout
    assert "engine says hi" in done.stderr
    assert "alternate: running new-2 (3 of 6)" in done.stderr


@pytest.mark.skipif(sys.platform == "win32", reason="process groups and SIGTERM are POSIX")
def test_stop_while_starting(tmp_path, capfd, monkeypatch):
    """INV-80: a stop that lands while the command is being started, after
    it exists but before the analyser holds it, still ends it."""
    import alternate

    started = []
    real_popen = subprocess.Popen

    def popen_then_stop(*args, **kwargs):
        process = real_popen(*args, **kwargs)
        started.append(process)
        os.kill(os.getpid(), signal.SIGTERM)  # handled before Popen returns
        return process

    monkeypatch.setattr(alternate.subprocess, "Popen", popen_then_stop)
    planned = alternate.plan(str(tmp_path), ["old", "new"], 3, 0)
    stopped = alternate.run_all({"old": "sleep 30; : {run}", "new": "sleep 30; : {run}"}, planned)
    assert stopped["run"] == "old-1" and "SIGTERM" in stopped["reason"]
    assert started[0].poll() is not None  # the shell was ended and reaped, not left running
