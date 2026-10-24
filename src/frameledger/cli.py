"""Commands, flags and exit codes (docs/specs/FLED-0001-run-file-format.md § 4.7).

The only module that prints or decides an exit code. Every command
builds one result dict in the shape of § 4.8, and render.py turns it
into text or JSON.
"""

from __future__ import annotations

import argparse
import sys
from decimal import ROUND_HALF_UP, Decimal, DecimalException, InvalidOperation

import ledger
import render
import run_report
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
    report = commands.add_parser("report", help="say where one run's frame time went")
    report.add_argument("file", metavar="FILE")
    report.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                        help="print the JSON result instead of text")
    floor = commands.add_parser("floor", help="did the run hold a frame rate every second, "
                                "and did any single frame take too long?")
    floor.add_argument("file", metavar="FILE")
    floor.add_argument("--fps", type=_positive, required=True, metavar="N", help="the frame rate to hold")
    floor.add_argument("--warmup-s", type=_seconds, default=Decimal(2), metavar="S",
                       help="seconds at the start that are not judged (default 2)")
    floor.add_argument("--budget-ms", type=_milliseconds, metavar="B",
                       help="the longest a single frame may take (default 1000/N, rounded up to three places)")
    floor.add_argument("--no-windows", action="store_true", help="skip the one-second window check")
    floor.add_argument("--no-frames", action="store_true", help="skip the single-frame check")
    floor.add_argument("--allow-frames", type=_whole, default=0, metavar="K",
                       help="frames over the budget to tolerate (default 0)")
    floor.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                       help="print the JSON result instead of text")
    return parser


BUDGET_LIMIT = Decimal(1_000_000_000)  # ms; a file's values are below it (spec § 4.4)


def _number(text: str) -> Decimal:
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise argparse.ArgumentTypeError(f"'{text}' is not a number") from None
    if not value.is_finite():
        raise argparse.ArgumentTypeError(f"'{text}' is not a number")
    return value


def _positive(text: str) -> Decimal:
    value = _number(text)
    if value <= 0:
        raise argparse.ArgumentTypeError(f"'{text}' must be above zero")
    return value


def _seconds(text: str) -> Decimal:
    value = _number(text)
    if value < 0:
        raise argparse.ArgumentTypeError(f"'{text}' must be 0 or more")
    return value


def _milliseconds(text: str) -> Decimal:
    """A budget compares exactly with the file's values, so it has their
    precision and range: at most three decimal places, below 1000000000."""
    value = _positive(text)
    if value >= BUDGET_LIMIT:
        raise argparse.ArgumentTypeError(f"'{text}' must be below {BUDGET_LIMIT}")
    if value != value.quantize(Decimal("0.001")):
        raise argparse.ArgumentTypeError(f"'{text}' has more than three decimal places")
    return value


def _whole(text: str) -> int:
    if not text.isdigit():
        raise argparse.ArgumentTypeError(f"'{text}' must be a whole number, 0 or more")
    return int(text)


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
        elif args.command == "report":
            result = _report(args.file)
        elif args.command == "floor":
            result = _floor(args)
        else:
            raise ledger.LedgerError("name a command (check, report, floor) or --selftest; "
                                     "--help lists them")
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


def _report(path: str) -> dict:
    """§ 4.7: exit 0, or 3 when the file cannot be read or breaks the format."""
    try:
        built = run_report.report(ledger.read(path))
    except ledger.LedgerError as error:
        return _result("report", "error", ERROR, [f"{error}."],
                       [{"code": "file_error", "message": str(error)}], {})
    return _result("report", "none", PASS, built["summary"], built["warnings"], built["result"])


def _floor(args: argparse.Namespace) -> dict:
    """§ 4.7: exit 0 pass, 1 fail, 2 inconclusive, 3 when the file cannot be
    read or breaks the format."""
    if args.no_windows and args.no_frames:
        raise ledger.LedgerError("--no-windows and --no-frames together leave nothing to check")
    try:  # an absurd exponent overflows decimal arithmetic, which is exit 3, not a traceback
        # 1000/N is the window check's limit and the default budget, so it
        # must be in range only when one of those is used.
        if args.budget_ms is None or not args.no_windows:
            raw_frame_ms = 1000 / args.fps
            # Rounded up, anything above 0 ms would pass a lower bound, so
            # the bound is on the exact value.
            if not (raw_frame_ms >= Decimal("0.001")
                    and run_report.frame_time_us(args.fps) < BUDGET_LIMIT * 1000):
                raise ledger.LedgerError(f"--fps {args.fps} gives a frame time of {raw_frame_ms:.3e} ms, "
                                         f"outside 0.001 to {BUDGET_LIMIT} ms; to judge frames alone, "
                                         "pass --budget-ms and --no-windows")
        # --budget-ms has at most three places, so it is a whole number of microseconds.
        budget_us = (run_report.frame_time_us(args.fps) if args.budget_ms is None
                     else int(args.budget_ms * 1000))
        warmup_us = int((args.warmup_s * 1_000_000).to_integral_value(ROUND_HALF_UP))
    except DecimalException as error:
        raise ledger.LedgerError(f"--fps or --warmup-s is out of range ({type(error).__name__})") from None
    try:
        built = run_report.floor(ledger.read(args.file), args.fps, warmup_us,
                                 budget_us, windows=not args.no_windows,
                                 frames=not args.no_frames, allowed=args.allow_frames)
    except ledger.LedgerError as error:
        return _result("floor", "error", ERROR, [f"{error}."],
                       [{"code": "file_error", "message": str(error)}], {})
    code = {"pass": PASS, "fail": FAIL, "inconclusive": INCONCLUSIVE}[built["verdict"]]
    return _result("floor", built["verdict"], code, built["summary"], built["warnings"], built["result"])


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
