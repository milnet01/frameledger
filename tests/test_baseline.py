"""`--baseline FILE`: a file naming the old runs of a compare (S24).

Invariants from docs/specs/FLED-0001-run-file-format.md § 5: INV-98 to
INV-101, the rules of § 4.17. A baseline compare is held against the
same compare with the files given after `--old` or `--base`.
"""

import json
import os
import re
from pathlib import Path

import cli
from test_alternate import Bench, analyser, without_added
from test_compare import new, old
from test_compare_scenes import Files

LINE_1 = '# frameledger-baseline {"schema":1}'
SLOW, SAME = [11.0, 11.01, 11.02], [10.0, 10.01, 10.02]
BASELINE_CODES = {"baseline_not_interleaved", "baseline_driver_differs", "baseline_os_differs"}


def write_runs(folder: Path, label: str, texts: list[str]) -> list[str]:
    folder.mkdir(parents=True, exist_ok=True)
    paths = [folder / f"{label}-{i}.csv" for i, _ in enumerate(texts, 1)]
    for path, text in zip(paths, texts, strict=True):
        path.write_text(text, encoding="utf-8")
    return [str(path) for path in paths]


def write_baseline(path: Path, lines: list[str], line_1: str = LINE_1) -> str:
    path.write_text("\n".join([line_1, *lines]) + "\n", encoding="utf-8")
    return str(path)


def run(capsys, *args: str) -> tuple[int, dict]:
    code = cli.main([*args, "--json"])
    out = json.loads(capsys.readouterr().out)
    assert out["exit_code"] == code
    return code, out


def refused(capsys, *args: str) -> str:
    """A setup error: exit 3, nothing on standard output; returns the
    sentence on standard error."""
    assert cli.main([*args, "--json"]) == 3, args
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err.startswith("frameledger: ")
    return captured.err


def sentence(path: str, runs: str = "old") -> str:
    return f"The {runs} runs are the baseline {path}."


def held_against(based: dict, plain: dict, baseline: str, runs: str = "old") -> None:
    """A baseline compare is the plain one, but for the `baseline` key
    and the sentence naming the file, which comes first."""
    assert plain["result"]["baseline"] is None
    assert based["result"] == {**plain["result"], "baseline": baseline}
    assert based["summary"] == [sentence(baseline, runs), *plain["summary"]]
    assert (based["verdict"], based["warnings"]) == (plain["verdict"], plain["warnings"])


def test_baseline_is_the_old_runs(capsys, tmp_path, monkeypatch):
    """INV-98: the listed runs are the old runs, in the file's order, each
    path starting at the baseline file's folder whatever the current
    directory, with either slash. The sets' starts interleave, so no
    warning differs."""
    kept = write_runs(tmp_path / "perf" / "runs", "old", old(SAME))
    fresh = write_runs(tmp_path / "fresh", "new", new(SLOW))
    baseline = write_baseline(tmp_path / "perf" / "meadow.txt",
                              ["# taken at scale 50", "runs/old-1.csv", "", "runs\\old-2.csv", "  runs/old-3.csv  "],
                              line_1='# frameledger-baseline {"schema":1,"note":"meadow"}')
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    plain_code, plain = run(capsys, "compare", "--old", *kept, "--new", *fresh)
    code, based = run(capsys, "compare", "--baseline", os.path.relpath(baseline), "--new", *fresh)
    assert code == plain_code == 1
    held_against(based, plain, baseline)
    assert [r["path"] for r in based["result"]["runs"][:3]] == kept


def test_by_scene_and_variants(capsys, tmp_path):
    """INV-98: with --by-scene the baseline is --old; with --variant it is
    --base. These paths are absolute."""
    files = Files(tmp_path)
    kept, fresh = [], []
    for scene in ("a", "b"):  # old-1, new-1, new-2, old-2, old-3, new-3: started in turn
        for i, (first, second) in enumerate(zip(SAME, SLOW, strict=True)):
            pair = [(kept, first), (fresh, second)]
            for group, opaque in pair if i % 2 == 0 else pair[::-1]:
                group += files.runs(scene, [opaque])
    baseline = write_baseline(tmp_path / "all.txt", kept)

    plain_code, plain = run(capsys, "compare", "--by-scene", "--old", *kept, "--new", *fresh)
    code, based = run(capsys, "compare", "--by-scene", "--baseline", baseline, "--new", *fresh)
    assert code == plain_code == 1
    held_against(based, plain, baseline)

    a_kept, a_fresh = kept[:3], fresh[:3]
    baseline = write_baseline(tmp_path / "a.txt", a_kept)
    plain_code, plain = run(capsys, "compare", "--base", *a_kept, "--variant", "slow", *a_fresh)
    code, based = run(capsys, "compare", "--baseline", baseline, "--variant", "slow", *a_fresh)
    assert code == plain_code == 1
    held_against(based, plain, baseline, runs="base")


def test_bad_baseline_files(capsys, tmp_path):
    """INV-99: a bad baseline file is exit 3 naming its line, and no run is
    read: every new run here is a broken file, which would be named."""
    write_runs(tmp_path, "kept", old(SAME))
    broken = write_runs(tmp_path, "new", ["not a run\n"] * 3)
    three = ["kept-1.csv", "kept-2.csv", "kept-3.csv"]
    cases = [
        ("", ["is empty"]),
        ("\n".join(three) + "\n", ["line 1", "# frameledger-baseline"]),
        ('# frameledger-baseline {"schema":\n' + "\n".join(three) + "\n", ["line 1", "JSON"]),
        ("\n".join(['# frameledger-baseline {"schema":2}', *three]) + "\n", ["line 1", "schema must be 1"]),
        ("\n".join([LINE_1, *three[:2]]) + "\n", ["names 2 runs", "at least 3"]),
        ("\n".join([LINE_1, "kept-1.csv", "./kept-1.csv", *three[1:]]) + "\n", ["line 3", "line 2's"]),
        ("\n".join([LINE_1, *three, "gone/kept-4.csv"]) + "\n",
         ["line 5", str(tmp_path / "gone" / "kept-4.csv"), "is not a file"]),
    ]
    path = tmp_path / "baseline.txt"
    for text, wanted in cases:
        path.write_text(text, encoding="utf-8")
        said = refused(capsys, "compare", "--baseline", str(path), "--new", *broken)
        assert all(part in said for part in [str(path), *wanted]), (text, said)
    path.write_bytes(LINE_1.encode() + b"\nkept-\xff.csv\n")
    said = refused(capsys, "compare", "--baseline", str(path), "--new", *broken)
    assert "line 2" in said and "UTF-8" in said
    assert str(tmp_path / "none.txt") in refused(capsys, "compare", "--baseline", str(tmp_path / "none.txt"),
                                                 "--new", *broken)


def test_flag_setup_errors(capsys, tmp_path):
    """INV-99: --baseline replaces --old or --base, needs --new or
    --variant, and is not bisect's."""
    kept = write_runs(tmp_path, "kept", old(SAME))
    fresh = write_runs(tmp_path, "new", new(SAME))
    baseline = write_baseline(tmp_path / "baseline.txt", kept)
    for args in (["--baseline", baseline, "--old", *kept, "--new", *fresh],
                 ["--baseline", baseline, "--base", *kept, "--variant", "a", *fresh],
                 ["--baseline", baseline]):
        assert "--baseline" in refused(capsys, "compare", *args)
    assert cli.main(["bisect", "--baseline", baseline, "--tested", *fresh, "--measure", "frame/wall",
                     "--unsegmented", "--bad-above", "10"]) == 128
    capsys.readouterr()


def compared(capsys, tmp_path, kept_texts: list[str], fresh_texts: list[str]) -> tuple[dict, dict]:
    """The same sets compared with --baseline and with --old."""
    kept = write_runs(tmp_path / "kept", "old", kept_texts)
    fresh = write_runs(tmp_path / "fresh", "new", fresh_texts)
    baseline = write_baseline(tmp_path / "kept" / "baseline.txt", [Path(p).name for p in kept])
    code, based = run(capsys, "compare", "--baseline", baseline, "--new", *fresh)
    plain_code, plain = run(capsys, "compare", "--old", *kept, "--new", *fresh)
    assert (code, based["verdict"]) == (plain_code, plain["verdict"])
    assert not BASELINE_CODES & {w["code"] for w in plain["warnings"]}
    return based, plain


def messages(out: dict) -> dict[str, str]:
    return {w["code"]: w["message"] for w in out["warnings"]}


def started(texts: list[str], *starts: str) -> list[str]:
    """Each run text with its started_utc replaced, in order."""
    return [re.sub(r'"started_utc": "[^"]*"', f'"started_utc": "{start}"', text, count=1)
            for text, start in zip(texts, starts, strict=True)]


def test_baseline_warnings(capsys, tmp_path):
    """INV-100: a baseline that ran first says so with its commit, day and
    age from its oldest run, in place of not_interleaved; a changed
    driver or os warns; no verdict moves and a plain compare gains
    nothing."""
    fresh = new(SLOW)  # started 2026-10-26T12:01, 12:03 and 12:05
    days = started(old(SAME), "2026-10-18T12:00:00Z", "2026-10-17T12:00:00Z", "2026-10-19T12:00:00Z")
    based, plain = compared(capsys, tmp_path / "days", days, fresh)
    message = messages(based)["baseline_not_interleaved"]
    assert all(part in message for part in ("commit abc123,", "started 2026-10-17,", "9 days before"))
    assert "not_interleaved" not in messages(based) and "not_interleaved" in messages(plain)
    assert based["verdict"] == "fail"

    hours = started(old(SAME), "2026-10-26T07:00:00Z", "2026-10-26T07:02:00Z", "2026-10-26T07:04:00Z")
    based, _ = compared(capsys, tmp_path / "hours", hours, fresh)
    assert "5 hours before" in messages(based)["baseline_not_interleaved"]
    minutes = started(old(SAME), "2026-10-26T11:21:00Z", "2026-10-26T11:23:00Z", "2026-10-26T11:25:00Z")
    based, _ = compared(capsys, tmp_path / "minutes", minutes, fresh)
    assert "40 minutes before" in messages(based)["baseline_not_interleaved"]

    dirty = [hours[0].replace('"dirty": false', '"dirty": true'), *hours[1:]]
    based, _ = compared(capsys, tmp_path / "dirty", dirty, fresh)
    assert "commits abc123 (dirty) and abc123," in messages(based)["baseline_not_interleaved"]

    after = started(old(SAME), "2026-10-27T07:00:00Z", "2026-10-27T07:02:00Z", "2026-10-27T07:04:00Z")
    based, _ = compared(capsys, tmp_path / "after", after, fresh)
    assert "not_interleaved" in messages(based) and "baseline_not_interleaved" not in messages(based)

    based, _ = compared(capsys, tmp_path / "same", old(SAME), fresh)
    assert not BASELINE_CODES & set(messages(based))
    based, _ = compared(capsys, tmp_path / "driver", old(SAME), new(SLOW, driver="Mesa 26.3"))
    message = messages(based)["baseline_driver_differs"]
    assert "Mesa 26.2" in message and "Mesa 26.3" in message and "baseline_os_differs" not in messages(based)
    based, _ = compared(capsys, tmp_path / "os", old(SAME, os="Linux 7.2"), new(SLOW, os="Linux 7.3"))
    message = messages(based)["baseline_os_differs"]
    assert "Linux 7.2" in message and "Linux 7.3" in message
    some = [*new(SLOW, os="Linux 7.3")[:2], new(SLOW)[2]]
    based, _ = compared(capsys, tmp_path / "some", old(SAME, os="Linux 7.2"), some)
    assert "baseline_os_differs" not in messages(based)


class BaselineBench(Bench):
    """Bench with three kept old runs named by a baseline file, and
    variants a and b of the new build."""

    def __init__(self, tmp_path: Path):
        super().__init__(tmp_path)
        text = self.sources["old"].read_text(encoding="utf-8")
        self.kept = write_runs(tmp_path / "kept", "old", [text] * 3)
        self.baseline = write_baseline(tmp_path / "kept" / "baseline.txt", [Path(p).name for p in self.kept])
        self.sources["a"] = self.sources["b"] = self.sources["new"]

    def args(self, *flags: str, sides=("new",)) -> list[str]:
        args = ["alternate", "--baseline", self.baseline, "--out", str(self.out), "--runs", "3", *flags]
        for name in sides:
            args += ["--new", self.command(name)] if name == "new" else ["--variant", name, self.command(name)]
        return args


def test_alternate_baseline(tmp_path):
    """INV-101: only the new command runs, warm-ups first, and its files
    are judged as `compare --baseline` judges them."""
    bench = BaselineBench(tmp_path)
    done = analyser(bench.args("--warmup", "1", "--json"))
    out = json.loads(done.stdout)
    assert bench.order() == ["new"] * 4
    assert bench.files() == ["new-1.csv", "new-2.csv", "new-3.csv", "new-warmup-1.csv"]
    fresh = [str(bench.out / f"new-{n}.csv") for n in (1, 2, 3)]
    plain = analyser(["compare", "--baseline", bench.baseline, "--new", *fresh, "--json"])
    assert without_added(out) == without_added(json.loads(plain.stdout))
    assert done.returncode == plain.returncode == 1
    assert list(out["result"]["commands"]) == ["new"]
    assert out["result"]["baseline"] == bench.baseline and out["result"]["stopped"] is None


def test_alternate_baseline_variants(tmp_path):
    """INV-101: with --variant, the rounds reverse over the variants alone."""
    bench = BaselineBench(tmp_path)
    done = analyser(bench.args("--json", sides=("a", "b")))
    out = json.loads(done.stdout)
    assert bench.order() == ["a", "b", "b", "a", "a", "b"]
    assert list(out["result"]["commands"]) == ["a", "b"]
    assert sentence(bench.baseline, "base") in out["summary"]
    assert [v["name"] for v in out["result"]["variants"]] == ["a", "b"]


def test_alternate_bad_baseline_runs_nothing(tmp_path):
    """INV-101: a baseline naming a missing file is found before any
    command starts."""
    bench = BaselineBench(tmp_path)
    Path(bench.kept[1]).unlink()
    done = analyser(bench.args("--json"))
    assert done.returncode == 3 and done.stdout == ""
    assert "line 3" in done.stderr and bench.kept[1] in done.stderr
    assert bench.order() == [] and bench.files() == []
