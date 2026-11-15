"""Facts a run does not know (§ 4.18.1).

Invariant INV-114 from docs/specs/FLED-0001-run-file-format.md § 5. Each
run is a copy of tests/fixtures/passing-run.csv with resolution [1, 1]
and build_type debug. A listed copy names commit, dirty, build_type and
resolution in `unknown`; an unlisted copy is the same with nothing
listed. The runs are writer-made, so the rule is tested apart from the
PresentMon import.
"""

import json
from pathlib import Path

import pytest

import cli

FIXTURE = Path(__file__).parent / "fixtures" / "passing-run.csv"
LISTED = ["commit", "dirty", "build_type", "resolution"]
NAMES = "commit, dirty, build_type and resolution"


def copy_text(run_id: str, minute: int = 0, **header) -> str:
    """The fixture under `run_id`, its header changed by `header`; a value
    of None leaves the field out."""
    first, *rest = FIXTURE.read_text(encoding="utf-8").splitlines()
    fields = json.loads(first.removeprefix("# frameledger "))
    fields.update(run_id=run_id, resolution=[1, 1], build_type="debug",
                  started_utc=f"2026-10-24T12:{minute:02d}:00Z")
    fields.update(header)
    fields = {k: v for k, v in fields.items() if v is not None}
    rows = [line.replace("f1,", f"{run_id},", 1) if not line.startswith("#") else line for line in rest]
    return "\n".join([f"# frameledger {json.dumps(fields)}", *rows]) + "\n"


def write(folder: Path, name: str, text: str) -> str:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text(text, encoding="utf-8")
    return str(path)


def listed_copy(folder: Path, name: str = "listed.csv", minute: int = 0, unknown=None, **header) -> str:
    return write(folder, name, copy_text(Path(name).stem, minute, unknown=unknown or LISTED, **header))


def unlisted_copy(folder: Path, name: str = "unlisted.csv", minute: int = 0, **header) -> str:
    return write(folder, name, copy_text(Path(name).stem, minute, **header))


def run(capsys, *args: str) -> tuple[int, dict]:
    code = cli.main([*args, "--json"])
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err
    return code, json.loads(captured.out)


def warnings(out: dict, code: str) -> list[str]:
    return [w["message"] for w in out["warnings"] if w["code"] == code]


def sets(tmp_path: Path, label: str, copy, count: int = 3, start: int = 0) -> list[str]:
    return [copy(tmp_path / label, f"{label}-{i}.csv", start + 2 * i) for i in range(count)]


def every_command(tmp_path: Path, copy) -> dict[str, list[str]]:
    """Each command of § 4.18.1's list, on runs made by `copy`, as args."""
    one = copy(tmp_path / "one")
    old, new = sets(tmp_path, "old", copy), sets(tmp_path, "new", copy, start=1)
    budgets = write(tmp_path, "budgets.csv", "# frameledger-budget {\"schema\":1}\n"
                    "category,name,kind,depth,statistic,limit_ms\n"
                    "cpu,cpu_remainder,view,,median,20.000\n")
    baseline = write(tmp_path, "baseline.txt", "\n".join(["# frameledger-baseline {\"schema\":1}", *old]) + "\n")
    override = ["--override", "resolution=a test", "--override", "build_type=a test"]
    return {
        "check": ["check", one],
        "report": ["report", one],
        "floor": ["floor", one, "--fps", "60"],
        "survey": ["survey", one, "--fps", "60"],
        "budget": ["budget", one, "--budgets", budgets],
        "bisect": ["bisect", "--tested", *new, "--measure", "frame/cpu_span", "--kind", "view",
                   "--bad-above", "20", *override],
        "compare": ["compare", "--old", *old, "--new", *new, *override],
        "compare --baseline": ["compare", "--baseline", baseline, "--new", *new, *override],
    }


@pytest.mark.parametrize("command", ["check", "report", "floor", "survey", "budget", "bisect", "compare",
                                     "compare --baseline"])
def test_every_command_warns(capsys, tmp_path, command):
    """INV-114: facts_unknown on the listed copy, naming each field, and
    not on the unlisted one."""
    _, out = run(capsys, *every_command(tmp_path / "listed", listed_copy)[command])
    said = warnings(out, "facts_unknown")
    assert said and all(NAMES in message for message in said), out["warnings"]
    _, out = run(capsys, *every_command(tmp_path / "unlisted", unlisted_copy)[command])
    assert not warnings(out, "facts_unknown")


def test_compare_refuses_a_listed_field(capsys, tmp_path):
    """INV-114: a listed resolution differs from every value, even the same
    stand-in, so the compare is refused until it is overridden."""
    old = sets(tmp_path, "old", listed_copy)
    new = sets(tmp_path, "new", unlisted_copy, start=1)
    code, out = run(capsys, "compare", "--old", *old, "--new", *new, "--override", "build_type=a test")
    assert code == 3 and out["result"]["refused"]
    refused = {entry["field"]: entry for entry in out["result"]["refused"]}
    assert set(refused) == {"resolution"}
    assert all(value is None for name, value in refused["resolution"]["values"].items() if name.startswith("old"))
    assert "resolution differs: unknown in old-1" in " ".join(out["summary"])
    code, out = run(capsys, "compare", "--old", *old, "--new", *new, "--override", "build_type=a test",
                    "--override", "resolution=a test")
    assert not out["result"].get("refused")
    assert warnings(out, "facts_unknown")
    plain_old = sets(tmp_path, "plain-old", unlisted_copy)
    code, out = run(capsys, "compare", "--old", *plain_old, "--new", *new)
    assert code != 3 and not out["result"].get("refused")


def test_compare_shows_a_listed_commit_as_null(capsys, tmp_path):
    """INV-114: compare's run entries show a listed commit and dirty as null."""
    old = sets(tmp_path, "old", listed_copy)
    new = sets(tmp_path, "new", unlisted_copy, start=1)
    _, out = run(capsys, "compare", "--old", *old, "--new", *new, "--override", "build_type=a test",
                 "--override", "resolution=a test")
    by_name = {entry["name"]: entry for entry in out["result"]["runs"]}
    assert by_name["old-1"]["commit"] is None and by_name["old-1"]["dirty"] is None
    assert by_name["new-1"]["commit"] == "abc123" and by_name["new-1"]["dirty"] is False


def test_a_listed_build_type_is_not_judged(capsys, tmp_path):
    """INV-114: no debug_build on the listed copy, and facts_unknown says
    so; the unlisted copy warns debug_build."""
    _, out = run(capsys, "report", listed_copy(tmp_path))
    assert not warnings(out, "debug_build")
    assert "debug_build is not judged" in warnings(out, "facts_unknown")[0]
    _, out = run(capsys, "report", unlisted_copy(tmp_path))
    assert warnings(out, "debug_build")


def test_a_budget_does_not_match_a_listed_field(capsys, tmp_path):
    budgets = write(tmp_path, "budgets.csv", "# frameledger-budget {\"schema\":1,\"match\":{\"resolution\":[1,1]}}\n"
                    "category,name,kind,depth,statistic,limit_ms\n"
                    "cpu,cpu_remainder,view,,median,20.000\n")
    code, _ = run(capsys, "budget", unlisted_copy(tmp_path), "--budgets", budgets)
    assert code == 0
    code, out = run(capsys, "budget", listed_copy(tmp_path), "--budgets", budgets)
    assert code == 3
    assert "resolution is [1, 1] in the budget file and unknown in the run" in json.dumps(out)


def test_a_listed_pipelined_gives_no_share(capsys, tmp_path):
    _, out = run(capsys, "report", listed_copy(tmp_path, unknown=["pipelined"]))
    assert out["result"]["bound_by"] == {"cpu": None, "gpu": None, "applies": False}
    assert any("pipelined is unknown" in sentence for sentence in out["summary"])


def test_a_listed_scene_is_in_no_scene(capsys, tmp_path):
    old = sets(tmp_path, "old", unlisted_copy)
    new = [listed_copy(tmp_path / "new", f"new-{i}.csv", 2 * i + 1, unknown=["scene"]) for i in range(3)]
    _, out = run(capsys, "compare", "--by-scene", "--old", *old, "--new", *new)
    assert "the header does not know its scene" in json.dumps(out)


def test_a_listed_dirty_is_dirty_unknown(capsys, tmp_path):
    """INV-114: baseline_not_interleaved marks the build "(dirty unknown)",
    and bisect's dirty warning says the value is unknown."""
    old = sets(tmp_path, "old", listed_copy)
    baseline = write(tmp_path, "baseline.txt", "\n".join(["# frameledger-baseline {\"schema\":1}", *old]) + "\n")
    new = sets(tmp_path, "new", unlisted_copy, start=30)
    _, out = run(capsys, "compare", "--baseline", baseline, "--new", *new, "--override", "build_type=a test",
                 "--override", "resolution=a test")
    assert "unknown (dirty unknown)" in warnings(out, "baseline_not_interleaved")[0]
    tested = sets(tmp_path, "tested", listed_copy)
    _, out = run(capsys, "bisect", "--tested", *tested, "--measure", "frame/cpu_span", "--kind", "view",
                 "--bad-above", "20", "--override", "build_type=a test", "--override", "resolution=a test")
    said = warnings(out, "dirty_build")
    assert said and all("does not know" in message for message in said)


@pytest.mark.parametrize("unknown", [["schema"], ["engine"], ["tier"], ["device", "device"], "device", [1]])
def test_a_bad_unknown_is_a_breach(capsys, tmp_path, unknown):
    code, out = run(capsys, "check", write(tmp_path, "bad.csv", copy_text("bad", unknown=unknown)))
    assert code == 1
    assert "the header's 'unknown' must be a list of field names" in json.dumps(out)


def test_a_field_every_run_lists_is_unknown_in_every_run(capsys, tmp_path):
    """The refusal does not say a field differs when no run knows it."""
    old = sets(tmp_path, "old", listed_copy)
    new = sets(tmp_path, "new", listed_copy, start=1)
    code, out = run(capsys, "compare", "--old", *old, "--new", *new, "--override", "build_type=a test")
    assert code == 3
    summary = " ".join(out["summary"])
    assert "resolution is unknown in every run (--override" in summary and "differs" not in summary


def test_a_listed_build_is_a_build_of_its_own(capsys, tmp_path):
    """§ 4.18.1: a listed commit or dirty matches no other run's, so the set
    warns mixed_build, saying the build is not known rather than that it
    differs."""
    new = sets(tmp_path, "new", unlisted_copy, start=1)
    for listed in (["commit"], ["dirty"]):
        old = [listed_copy(tmp_path / "-".join(listed), f"old-{i}.csv", 2 * i, unknown=listed) for i in range(3)]
        _, out = run(capsys, "compare", "--old", *old, "--new", *new)
        assert warnings(out, "mixed_build") == ["the old runs do not all say their commit and dirty, so they may "
                                                "not be one build"], listed
    _, out = run(capsys, "compare", "--old", *sets(tmp_path, "plain", unlisted_copy), "--new", *new)
    assert not warnings(out, "mixed_build")


def test_bisect_names_each_listed_build_fact(capsys, tmp_path):
    """bisect's dirty warning names what the header does not know, and still
    says a known dirty build had uncommitted changes."""
    def said(unknown, **header):
        tested = [listed_copy(tmp_path / "-".join(unknown), f"tested-{i}.csv", 2 * i, unknown=unknown, **header)
                  for i in range(3)]
        _, out = run(capsys, "bisect", "--tested", *tested, "--measure", "frame/cpu_span", "--kind", "view",
                     "--bad-above", "20", "--override", "build_type=a test")
        return warnings(out, "dirty_build")[0]

    assert said(["dirty"]) == ("tested-1: the header does not know its build's dirty, so it may not be the "
                               "commit under test")
    assert said(["commit", "dirty"]).startswith("tested-1: the header does not know its build's commit and dirty,")
    assert said(["commit"], dirty=True) == ("tested-1: the header does not know its build's commit and the build "
                                            "had uncommitted changes, so it may not be the commit under test")


def test_a_listed_driver_differs_from_the_baseline(capsys, tmp_path):
    old = sets(tmp_path, "old", unlisted_copy)
    baseline = write(tmp_path, "baseline.txt", "\n".join(["# frameledger-baseline {\"schema\":1}", *old]) + "\n")
    new = [listed_copy(tmp_path / "new", f"new-{i}.csv", 2 * i + 1, unknown=["driver"]) for i in range(3)]
    _, out = run(capsys, "compare", "--baseline", baseline, "--new", *new)
    assert warnings(out, "baseline_driver_differs") == ["the driver is unknown in some runs, so the new runs may "
                                                        "not be on the baseline's driver"]
    _, out = run(capsys, "compare", "--baseline", baseline, "--new", *sets(tmp_path, "plain", unlisted_copy, start=1))
    assert not warnings(out, "baseline_driver_differs")


@pytest.mark.parametrize("field", ["renderer", "device"])
def test_a_listed_renderer_or_device_is_not_judged(capsys, tmp_path, field):
    """§ 4.9's software_renderer is not judged on a listed renderer or device."""
    _, out = run(capsys, "report", unlisted_copy(tmp_path, **{field: "llvmpipe"}))
    assert warnings(out, "software_renderer")
    _, out = run(capsys, "report", listed_copy(tmp_path, unknown=[field], **{field: "llvmpipe"}))
    assert not warnings(out, "software_renderer")
    assert f"software_renderer on the {field} is not judged" in warnings(out, "facts_unknown")[0]
