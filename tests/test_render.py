"""Text and JSON come from one result (docs/specs/FLED-0001-run-file-format.md § 4.8)."""

import json
from pathlib import Path

import pytest

import cli

FIXTURES = Path(__file__).parent / "fixtures"
ALL = sorted(FIXTURES.glob("*.csv"))


@pytest.mark.parametrize("command", ["check", "report"])
@pytest.mark.parametrize("path", ALL, ids=[p.name for p in ALL])
def test_text_matches_json(capsys, command, path):
    """INV-13: the text's opening sentences equal the JSON summary, in order;
    and no line of report's tables is wider than 100 columns. check's
    breach and warning lines carry the file's path, so may be wider."""
    code = cli.main([command, "--json", str(path)])
    summary = json.loads(capsys.readouterr().out)["summary"]
    assert cli.main([command, str(path)]) == code
    text = capsys.readouterr().out.splitlines()
    assert summary and text[: len(summary)] == summary
    assert text[len(summary):len(summary) + 1] in ([], [""])
    body = text[len(summary):] if command == "report" else []
    assert all(len(line) <= 100 for line in body), max(body, key=len)
