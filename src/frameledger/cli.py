"""Commands, flags and exit codes (docs/specs/FLED-0001-run-file-format.md § 4.7).

The only module that prints or decides an exit code. Every command
builds one result dict in the shape of § 4.8, and render.py turns it
into text or JSON.
"""

from __future__ import annotations

import argparse
import sys

import ledger
import render
import selftest

VERSION = "0.1.0.dev0"

# One ladder for every command (docs/design.md § Exit codes).
PASS, FAIL, INCONCLUSIVE, ERROR = 0, 1, 2, 3


class _Parser(argparse.ArgumentParser):
    """argparse exits 2 on a bad argument, which this ladder reserves for
    "inconclusive, worth re-running". A bad argument is exit 3."""

    def error(self, message: str):
        raise ledger.LedgerError(f"{message}\n{self.format_usage().rstrip()}")


def _parser() -> _Parser:
    parser = _Parser(prog="frameledger", description="Read and judge frameledger run files.")
    parser.add_argument("--json", action="store_true", help="print the JSON result instead of text")
    parser.add_argument("--selftest", action="store_true", help="run the analyser's own checks")
    parser.add_argument("--version", action="store_true", help="print the version")
    commands = parser.add_subparsers(dest="command", metavar="COMMAND")
    check = commands.add_parser("check", help="say whether each file meets the run-file format")
    check.add_argument("files", nargs="+", metavar="FILE")
    # SUPPRESS: otherwise the subcommand's default False overwrites a
    # --json given before the command name.
    check.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                       help="print the JSON result instead of text")
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        if args.version:
            print(f"frameledger {VERSION}")
            return PASS
        if args.selftest:
            result = _selftest()
        elif args.command == "check":
            result = _check(args.files)
        else:
            raise ledger.LedgerError("name a command (check) or --selftest; --help lists them")
    except ledger.LedgerError as error:
        print(f"frameledger: {error}", file=sys.stderr)
        return ERROR
    except SystemExit as stop:  # --help prints and stops
        return stop.code if isinstance(stop.code, int) else ERROR
    print(render.to_json(result) if args.json else render.to_text(result), end="")
    return result["exit_code"]


def _result(command: str, verdict: str, exit_code: int, summary: list[str],
            warnings: list[dict], result: dict) -> dict:
    return {
        "frameledger": VERSION,
        "command": command,
        "verdict": verdict,
        "exit_code": exit_code,
        "summary": summary,
        "overrides": [],
        "warnings": warnings,
        "result": result,
    }


def _check(paths: list[str]) -> dict:
    files, warnings, summary = [], [], []
    failed = unreadable = 0
    for path in paths:
        try:
            run = ledger.read(path)
        except ledger.LedgerError as error:
            unreadable += 1
            summary.append(f"{error}.")
            warnings.append({"code": "file_error", "message": str(error)})
            continue
        files.append({"path": path, "breaches": [
            {"line": b.line, "rule": b.rule, "message": b.message} for b in run.breaches]})
        if run.breaches:
            failed += 1
            first = run.breaches[0]
            places = "1 place" if len(run.breaches) == 1 else f"{len(run.breaches)} places"
            summary.append(f"{path} breaks the run-file format in {places}; "
                           f"the first is line {first.line}: {first.message}.")
        for notice in run.notices:
            where = path if notice.line is None else f"{path}, line {notice.line}"
            warnings.append({"code": notice.code, "message": f"{where}: {notice.message}"})
        summary += _notice_sentences(path, run.notices)

    total = len(paths)
    if unreadable:
        verdict, code = "error", ERROR
        summary.append(f"{unreadable} of {total} files could not be read, so they were not checked.")
    elif failed:
        verdict, code = "fail", FAIL
        summary.append(f"{failed} of {total} files break the run-file format.")
    else:
        verdict, code = "pass", PASS
        summary.append("The file meets the run-file format." if total == 1
                       else f"All {total} files meet the run-file format.")
    return _result("check", verdict, code, summary, warnings, {"files": files})


def _notice_sentences(path: str, notices: list[ledger.Notice]) -> list[str]:
    """One sentence per kind of warning, naming its first line, so a run
    with a thousand negative values does not open with a thousand lines."""
    by_code: dict[str, list[ledger.Notice]] = {}
    for notice in notices:
        by_code.setdefault(notice.code, []).append(notice)
    sentences = []
    for group in by_code.values():
        first = group[0]
        where = path if first.line is None else f"{path}, line {first.line}"
        more = f" ({len(group) - 1} more like it)" if len(group) > 1 else ""
        sentences.append(f"{where}: {first.message}{more}.")
    return sentences


def _selftest() -> dict:
    checks = selftest.run()
    failed = [name for name, ok in checks if not ok]
    if failed:
        summary = [f"Self-test check failed: {name}." for name in failed]
        summary.append(f"{len(failed)} of {len(checks)} self-test checks failed; "
                       "this copy of frameledger is not working.")
        verdict, code = "fail", FAIL
    else:
        summary = [f"All {len(checks)} self-test checks passed."]
        verdict, code = "pass", PASS
    return _result("selftest", verdict, code, summary, [],
                   {"checks": [{"name": name, "pass": ok} for name, ok in checks]})
