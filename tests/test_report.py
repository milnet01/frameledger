"""The `report` command: where one run's frame time went.

Invariants from docs/specs/FLED-0001-run-file-format.md § 5: INV-5,
INV-10, INV-11 and INV-12. INV-1's and INV-21's report halves are in
test_check.py, INV-3's and INV-4's in test_ledger.py, beside their check
halves.
"""

import json
from pathlib import Path

import cli

FIXTURES = Path(__file__).parent / "fixtures"


def run_report(capsys, path):
    code = cli.main(["report", "--json", str(path)])
    out = json.loads(capsys.readouterr().out)
    assert out["exit_code"] == code
    return code, out


def entry(entries, **match):
    found = [e for e in entries if all(e[k] == v for k, v in match.items())]
    assert len(found) == 1, (match, entries)
    return found[0]


def test_missing_gpu_span(capsys):
    """INV-5: a frame with no gpu_span is counted missing, never as 0 ms."""
    code, out = run_report(capsys, FIXTURES / "gpu-missing.csv")
    assert (code, out["verdict"]) == (0, "none")
    result = out["result"]
    assert result["missing_gpu_frames"] == 1
    gpu_span = entry(result["frame_times"], name="gpu_span")
    assert (gpu_span["median_ms"], gpu_span["frames"]) == (10.0, 4)
    assert entry(result["passes"], name="gpu_remainder")["frames"] == 4
    assert any("no GPU result" in s for s in out["summary"])


def test_bound_by_not_pipelined(capsys, tmp_path):
    """INV-10: with pipelined false the share does not apply, and says so."""
    path = FIXTURES / "pipelined.csv"
    code, out = run_report(capsys, path)
    assert code == 0
    assert out["result"]["bound_by"] == {"cpu": 0.25, "gpu": 0.75, "applies": True}

    serial = tmp_path / "not-pipelined.csv"
    serial.write_bytes(path.read_bytes().replace(b'"pipelined":true', b'"pipelined":false', 1))
    code, out = run_report(capsys, serial)
    assert code == 0
    assert out["result"]["bound_by"] == {"cpu": None, "gpu": None, "applies": False}
    assert any("does not apply" in s for s in out["summary"])
    assert not any("GPU-bound" in s and "%" in s for s in out["summary"])


def test_remainder(capsys):
    """INV-11: the remainder subtracts depth-0 rows only."""
    code, out = run_report(capsys, FIXTURES / "nested.csv")
    assert code == 0
    passes = out["result"]["passes"]
    assert entry(passes, name="gpu_remainder")["median_ms"] == 3.0
    nested = entry(passes, name="shadows/cascade0")
    assert nested["depth"] == 1
    assert entry(passes, name="cpu_remainder")["median_ms"] == 8.0


def test_static_exact(capsys):
    """INV-12: static statistics come out as the exact strings written."""
    code, out = run_report(capsys, FIXTURES / "static-hash.csv")
    assert code == 0
    assert out["result"]["static"] == {"pipelines": {"primitives": "17436423623014656123"}}
    code, out = run_report(capsys, FIXTURES / "in-order.csv")
    assert out["result"]["static"] is None


def test_ranking_is_by_total_time(capsys, tmp_path):
    """Vestige's review: a pass in every frame outranks a costlier-per-frame
    pass that ran in one, because the run spent more on it."""
    path = FIXTURES / "in-order.csv"
    rare = tmp_path / "rare-pass.csv"
    rows = path.read_text(encoding="utf-8").replace(
        "r1,view:1,0,gpu,shadows,0,4.000\n", "r1,view:1,0,gpu,shadows,0,4.000\nr1,view:1,0,gpu,bloom,0,9.000\n")
    rare.write_text(rows, encoding="utf-8")
    code, out = run_report(capsys, rare)
    assert code == 0
    gpu = [e["name"] for e in out["result"]["passes"] if e["category"] == "gpu"]
    assert gpu.index("shadows") < gpu.index("bloom")
    bloom = entry(out["result"]["passes"], name="bloom")
    assert (bloom["median_ms"], bloom["frames"]) == (9.0, 1)


def test_shares_and_worst_frames(capsys):
    code, out = run_report(capsys, FIXTURES / "in-order.csv")
    assert code == 0
    result = out["result"]
    # gpu spans 10..14 total 60; shadows 4..8 total 30.
    shadows = entry(result["passes"], name="shadows")
    assert (shadows["segment_kind"], shadows["share"], shadows["p99_ms"]) == ("view", 0.5, 8.0)
    # Frame 4 is the last, so it has no wall; every other wall is 16.000.
    worst = result["worst_frames"]
    assert [w["frame"] for w in worst] == [0, 1, 2, 3]
    # Frame 0: cpu_span 8 - scene 5 = 3; gpu_span 10 - shadows 4 = 6; shadows 4.
    assert worst[0] == {"frame": 0, "segment": "view:1", "wall_ms": 16.0, "top_pass": "gpu/gpu_remainder"}


def test_breach_is_exit_3(capsys):
    """§ 6: report never skips a malformed row; it stops naming the line."""
    code, out = run_report(capsys, FIXTURES / "zero-wall.csv")
    assert (code, out["verdict"]) == (3, "error")
    assert "line" in out["summary"][0]


def test_static_text_is_capped(capsys, tmp_path):
    """UT Ants' review: a large static line does not bury the ranking. An
    optional "summary" object is printed whole; the rest only in --json."""
    path = FIXTURES / "in-order.csv"
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)

    def with_static(static):
        out = tmp_path / "static.csv"
        out.write_text(lines[0] + "# frameledger-static " + json.dumps(static) + "\n" + "".join(lines[1:]),
                       encoding="utf-8")
        assert cli.main(["report", str(out)]) == 0
        return capsys.readouterr().out.splitlines()

    stats = {f"stage{i}": {"vgprs": str(i)} for i in range(30)}
    text = with_static({"stats": stats})
    assert sum(line.startswith("  stats.") for line in text) == 20
    assert "  10 more static facts: see --json." in text

    text = with_static({"summary": {"stage0": {"vgprs": "64"}}, "stats": stats})
    assert "  summary.stage0.vgprs: 64" in text
    assert not any(line.startswith("  stats.") for line in text)
    assert "  30 more static facts: see --json." in text
