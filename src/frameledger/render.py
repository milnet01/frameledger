"""Turn a command's result into plain text or JSON.

Both forms come from the one result dict cli.py builds, so they cannot
disagree: the text opens with the result's `summary` sentences, in order.
"""

from __future__ import annotations

import json


def to_json(result: dict) -> str:
    return json.dumps(result, indent=2) + "\n"


def to_text(result: dict) -> str:
    lines = list(result["summary"])
    body = _BODIES.get(result["command"], _no_body)(result)
    if body:
        lines += ["", *body]
    return "\n".join(lines) + "\n"


def _no_body(result: dict) -> list[str]:
    return []


def _check_body(result: dict) -> list[str]:
    lines = []
    for entry in result["result"]["files"]:
        if entry["breaches"]:
            lines.append(f"Breaches in {entry['path']}:")
            lines += [f"  line {b['line']}: {b['message']} ({b['rule']})" for b in entry["breaches"]]
    if result["warnings"]:
        lines.append("Warnings:")
        lines += [f"  {w['message']} ({w['code']})" for w in result["warnings"]]
    return lines


def _selftest_body(result: dict) -> list[str]:
    return [f"  {'ok  ' if c['pass'] else 'FAIL'}  {c['name']}" for c in result["result"]["checks"]]


_BODIES = {"check": _check_body, "selftest": _selftest_body}
