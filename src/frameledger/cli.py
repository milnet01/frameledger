"""Commands, flags and exit codes (docs/specs/FLED-0001-run-file-format.md
§ 4.7, § 4.10 for `compare`, § 4.11 for `bisect` and § 4.12 for `budget`).

The only module that prints or decides an exit code. Every command
builds one result dict in the shape of § 4.8, and render.py turns it
into text or JSON.
"""

from __future__ import annotations

import argparse
import os
import sys
import traceback
from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal, DecimalException, InvalidOperation

import bisecting
import budgeting
import compare
import ledger
import render
import run_report
import selftest

VERSION = "0.1.0"

# One ladder for every command (docs/design.md § Exit codes), but bisect's,
# which are git bisect run's: bisecting.VERDICT_CODES. Whatever on a bisect
# command line is not a verdict is STOP.
PASS, FAIL, INCONCLUSIVE, ERROR = 0, 1, 2, 3
STOP = bisecting.VERDICT_CODES["stop"]
# The references' floor when no flag sets it; the flags default to None, so
# a floor given with --bad-above can be refused.
BISECT_FLOORS = compare.Floors(min_ms=Decimal("0.050"), min_mb=Decimal("1.000"), min_pct=Decimal(3))


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
    floor.add_argument("--warmup-s", type=_non_negative, default=Decimal(2), metavar="S",
                       help="seconds at the start that are not judged (default 2)")
    floor.add_argument("--budget-ms", type=_milliseconds, metavar="B",
                       help="the longest a single frame may take (default 1000/N, rounded up to three places)")
    floor.add_argument("--no-windows", action="store_true", help="skip the one-second window check")
    floor.add_argument("--no-frames", action="store_true", help="skip the single-frame check")
    floor.add_argument("--allow-frames", type=_whole, default=0, metavar="K",
                       help="frames over the budget to tolerate (default 0)")
    floor.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                       help="print the JSON result instead of text")
    compare_cmd = commands.add_parser("compare", help="did the new runs get slower than the old, "
                                      "measure by measure?")
    compare_cmd.add_argument("--old", nargs="+", required=True, metavar="FILE",
                             help=f"the old build's runs, at least {compare.FEWEST_RUNS}")
    compare_cmd.add_argument("--new", nargs="+", required=True, metavar="FILE",
                             help=f"the new build's runs, at least {compare.FEWEST_RUNS}")
    compare_cmd.add_argument("--override", action="append", type=_override, default=[],
                             metavar="FIELD=REASON", help="let one compare-blocking header field differ")
    compare_cmd.add_argument("--min-ms", type=_smallest_change, default=Decimal("0.050"), metavar="M",
                             help="the smallest change that counts, in ms (default 0.050)")
    compare_cmd.add_argument("--min-mb", type=_smallest_change, default=Decimal("1.000"), metavar="M",
                             help="the smallest change that counts for a mem measure, in MB (default 1.000)")
    compare_cmd.add_argument("--min-pct", type=_non_negative, default=Decimal(3), metavar="P",
                             help="the smallest change that counts, in percent of the old (default 3)")
    compare_cmd.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                             help="print the JSON result instead of text")
    _add_bisect(commands)
    budget = commands.add_parser("budget", help="is any pass over its time budget?")
    budget.add_argument("file", metavar="FILE")
    budget.add_argument("--budgets", required=True, metavar="BUDGETS", help="the budget file")
    budget.add_argument("--warmup-s", type=_non_negative, default=Decimal(0), metavar="S",
                        help="seconds at the start that are not judged, as floor's (default 0)")
    budget.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                        help="print the JSON result instead of text")
    return parser


def _add_bisect(commands) -> None:
    bisect = commands.add_parser("bisect", help="exit with git bisect run's code for one commit's runs: "
                                 "0 good, 1 bad, 125 skip, 128 stop")
    # Every file list follows its own flag, so a file cannot join the wrong
    # set by being written after --bad (UT Ants).
    bisect.add_argument("--tested", nargs="+", metavar="FILE", help="the runs of the commit under test")
    bisect.add_argument("--measure", required=True, metavar="CATEGORY/NAME",
                        help="frame/wall, frame/cpu_span, frame/gpu_span, a cpu or gpu pass, or a mem row")
    frames = bisect.add_mutually_exclusive_group(required=True)
    frames.add_argument("--kind", metavar="KIND", help="judge the frames of this segment kind")
    frames.add_argument("--segment", metavar="KIND:ID", help="judge the frames of this one segment")
    frames.add_argument("--unsegmented", action="store_true", help="judge the frames with no segment")
    bisect.add_argument("--statistic", choices=("median", "p99"), default="median",
                        help="p99 is for frame/wall only (default median)")
    bisect.add_argument("--depth", type=_whole, metavar="D", help="the depth, where a name has two")
    bisect.add_argument("--bad-above", type=_value, metavar="X", help="bad when the value is above X")
    bisect.add_argument("--good", nargs="+", metavar="FILE", help=f"at least {bisecting.FEWEST_REFERENCES} "
                        "runs of a known-good commit")
    bisect.add_argument("--bad", nargs="+", metavar="FILE", help=f"at least {bisecting.FEWEST_REFERENCES} "
                        "runs of a known-bad commit")
    bisect.add_argument("--override", action="append", type=_override, default=[],
                        metavar="FIELD=REASON", help="let one compare-blocking header field differ")
    bisect.add_argument("--min-ms", type=_smallest_change, metavar="M",
                        help=f"the references' smallest change, in ms (default {BISECT_FLOORS.min_ms})")
    bisect.add_argument("--min-mb", type=_smallest_change, metavar="M",
                        help="the references' smallest change for a mem measure, in MB "
                        f"(default {BISECT_FLOORS.min_mb})")
    bisect.add_argument("--min-pct", type=_non_negative, metavar="P",
                        help="the references' smallest change, in percent of the good runs "
                        f"(default {BISECT_FLOORS.min_pct})")
    bisect.add_argument("--skip-straddle", action="store_true",
                        help="skip a commit whose runs fall on both sides of the line")
    bisect.add_argument("--dry-run", type=_value, metavar="VALUE",
                        help="judge VALUE instead of run files, and exit with its code")
    bisect.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                        help="print the JSON result instead of text")


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


def _non_negative(text: str) -> Decimal:
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


def _value(text: str) -> Decimal:
    """A threshold or a dry-run value compares exactly with the file's
    values, so it has their precision and range."""
    value = _number(text)
    if abs(value) >= BUDGET_LIMIT:
        raise argparse.ArgumentTypeError(f"'{text}' must be below {BUDGET_LIMIT} in size")
    if value != value.quantize(Decimal("0.001")):
        raise argparse.ArgumentTypeError(f"'{text}' has more than three decimal places")
    return value


def _smallest_change(text: str) -> Decimal:
    value = _non_negative(text)
    if value >= BUDGET_LIMIT:
        raise argparse.ArgumentTypeError(f"'{text}' must be below {BUDGET_LIMIT}")
    return value


def _override(text: str) -> tuple[str, str]:
    """FIELD=REASON: a compare-blocking field, and a reason that is not empty."""
    field, _, reason = text.partition("=")
    if field not in compare.BLOCKING:
        raise argparse.ArgumentTypeError(f"'{field}' is not a compare-blocking field; those are "
                                         f"{', '.join(compare.BLOCKING)}")
    if not reason.strip():
        raise argparse.ArgumentTypeError(f"--override {field} needs a reason: {field}=REASON")
    return field, reason


def _whole(text: str) -> int:
    # str.isdigit alone takes any script's digits, and superscripts int() refuses.
    if not (text.isascii() and text.isdigit()):
        raise argparse.ArgumentTypeError(f"'{text}' must be a whole number, 0 or more")
    return int(text)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    if _command(argv) == "bisect":
        return _bisect_main(argv)
    try:
        args = _parser().parse_args(argv)
        if args.version:
            _write(f"frameledger {VERSION}\n")
            return PASS
        result = _dispatch(args)
        _write(render.to_json(result) if args.json else render.to_text(result))
    except ledger.LedgerError as error:
        print(f"frameledger: {error}", file=sys.stderr)
        return ERROR
    except SystemExit as stop:  # --help prints and stops
        return stop.code if isinstance(stop.code, int) else ERROR
    except OSError as error:  # standard output closed early, or the disk is full
        return _failed_write(error, ERROR)
    return result["exit_code"]


def _command(argv: list[str]) -> str | None:
    """The command a command line names: its first argument not starting
    with -. The options before a command take no value, so it cannot be an
    option's value."""
    return next((arg for arg in argv if not arg.startswith("-")), None)


def _dispatch(args: argparse.Namespace) -> dict:
    if args.selftest:
        return _selftest()
    if args.command == "check":
        return _check(args.files)
    if args.command == "report":
        return _report(args.file)
    if args.command == "floor":
        return _floor(args)
    if args.command == "compare":
        return _compare(args)
    if args.command == "budget":
        return _budget(args)
    raise ledger.LedgerError("name a command (check, report, floor, compare, bisect, budget) or --selftest; "
                             "--help lists them")


def _bisect_main(argv: list[str]) -> int:
    """A bisect command line exits with a verdict's code or STOP, and nothing
    else: git bisect run reads --help's and --version's 0 as good, and a bad
    argument's 3, a traceback's 1 or a failed write's 120 as bad (DOOM Ants,
    UT Ants). Only the verdict is printed on standard output."""
    try:
        args = _parser().parse_args(argv)
        if args.version or args.selftest:
            raise ledger.LedgerError("--version and --selftest are not a bisect; git bisect run would "
                                     "read their 0 as good")
        result = _bisect(args)
        _write(render.to_json(result) if args.json else render.to_text(result))
        return result["exit_code"]
    except ledger.LedgerError as error:
        print(f"frameledger: {error}", file=sys.stderr)
    except SystemExit as stop:  # --help prints and stops; anything else says so
        if stop.code:
            print(f"frameledger: stopped ({stop.code})", file=sys.stderr)
    except OSError as error:
        return _failed_write(error, STOP)
    except Exception:  # a bug in the analyser must not mark the commit bad
        traceback.print_exc()
    return STOP


def _write(text: str) -> None:
    """Print `text` and flush it now, so a write that fails raises here and
    not at exit, where Python would end with 120."""
    if sys.stdout is None:  # standard output was closed before the start
        return
    sys.stdout.write(text)
    sys.stdout.flush()


def _failed_write(error: OSError, code: int) -> int:
    """After a failed write, point standard output at the null device, so the
    flush at exit has nothing to fail on (the signal module's note on SIGPIPE)."""
    try:
        null = os.open(os.devnull, os.O_WRONLY)
        os.dup2(null, sys.stdout.fileno())
        os.close(null)
        print(f"frameledger: the output could not be written ({error.strerror or error})", file=sys.stderr)
    except (OSError, ValueError):
        pass
    return code


def _result(command: str, verdict: str, exit_code: int, summary: list[str],
            warnings: list[dict], result: dict, overrides: Sequence[dict] = ()) -> dict:
    return {
        "frameledger": VERSION,
        "command": command,
        "verdict": verdict,
        "exit_code": exit_code,
        "summary": summary,
        "overrides": list(overrides),
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


def _compare(args: argparse.Namespace) -> dict:
    """§ 4.10: exit 0 pass, 1 a measure got slower, 2 inconclusive, 3 when a
    file cannot be read or breaks the format, or the compare is refused."""
    for label, paths in (("--old", args.old), ("--new", args.new)):
        if len(paths) < compare.FEWEST_RUNS:
            raise ledger.LedgerError(f"{label} has {len(paths)} runs; each set needs at least "
                                     f"{compare.FEWEST_RUNS}, since two give too many false changes")
    overrides = _overrides(args.override)
    try:
        built = compare.compare([ledger.read(p) for p in args.old], [ledger.read(p) for p in args.new],
                                overrides, compare.Floors(args.min_ms, args.min_mb, args.min_pct))
    except ledger.LedgerError as error:  # S5: the overrides are named even here
        listed = [{"field": f, "reason": r} for f, r in overrides.items()]
        return _result("compare", "error", ERROR, [*compare.overrides_sentences(listed), f"{error}."],
                       [{"code": "file_error", "message": str(error)}], {}, listed)
    code = {"pass": PASS, "fail": FAIL, "inconclusive": INCONCLUSIVE, "error": ERROR}[built["verdict"]]
    return _result("compare", built["verdict"], code, built["summary"], built["warnings"],
                   built["result"], built["overrides"])


def _budget(args: argparse.Namespace) -> dict:
    """§ 4.12: exit 0 every budget holds, 1 a pass is over budget, 2
    inconclusive, 3 when either file cannot be read or is wrong, or the run
    does not have the budget file's settings."""
    try:
        warmup_us = int((args.warmup_s * 1_000_000).to_integral_value(ROUND_HALF_UP))
    except DecimalException as error:
        raise ledger.LedgerError(f"--warmup-s is out of range ({type(error).__name__})") from None
    try:
        built = budgeting.judge(ledger.read(args.file), budgeting.read(args.budgets), warmup_us)
    except ledger.LedgerError as error:
        return _result("budget", "error", ERROR, [f"{error}."],
                       [{"code": "file_error", "message": str(error)}], {})
    code = {"pass": PASS, "fail": FAIL, "inconclusive": INCONCLUSIVE}[built["verdict"]]
    return _result("budget", built["verdict"], code, built["summary"], built["warnings"], built["result"])


def _overrides(pairs: list[tuple[str, str]]) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for field, reason in pairs:
        if field in overrides:
            raise ledger.LedgerError(f"--override {field} is given twice")
        overrides[field] = reason
    return overrides


def _bisect(args: argparse.Namespace) -> dict:
    """§ 4.11: exit 0 good, 1 bad, 125 skip, 128 stop. A flag problem raises
    LedgerError, which _bisect_main turns into STOP."""
    wanted = _wanted(args)
    overrides = _overrides(args.override)
    _check_bisect_flags(args, wanted)
    floors = compare.Floors(
        min_ms=BISECT_FLOORS.min_ms if args.min_ms is None else args.min_ms,
        min_mb=BISECT_FLOORS.min_mb if args.min_mb is None else args.min_mb,
        min_pct=BISECT_FLOORS.min_pct if args.min_pct is None else args.min_pct)
    built = bisecting.bisect(wanted, _load(args.tested), _load(args.good), _load(args.bad), overrides,
                             floors, bad_above=args.bad_above, dry_value=args.dry_run,
                             skip_straddle=args.skip_straddle)
    return _result("bisect", built["verdict"], bisecting.VERDICT_CODES[built["verdict"]], built["summary"],
                   built["warnings"], built["result"], built["overrides"])


def _wanted(args: argparse.Namespace) -> bisecting.Wanted:
    """The measure and frames, refusing what would skip every commit."""
    category, slash, name = args.measure.partition("/")
    if not (slash and name) or category not in bisecting.CATEGORIES:
        raise ledger.LedgerError(f"--measure {args.measure} must be frame/NAME, cpu/NAME, gpu/NAME or "
                                 "mem/NAME")
    if category == "frame" and name not in bisecting.FRAME_NAMES:
        raise ledger.LedgerError(f"--measure frame/{name} is not judged; the frame measures are "
                                 + ", ".join(f"frame/{n}" for n in bisecting.FRAME_NAMES))
    if args.statistic == "p99" and (category, name) != ("frame", "wall"):
        raise ledger.LedgerError("--statistic p99 is for frame/wall only")
    if category == "frame" and args.depth is not None:
        raise ledger.LedgerError("--depth picks a pass's depth; a frame measure has none")
    if args.kind is not None and ":" in args.kind:
        raise ledger.LedgerError(f"--kind {args.kind} is a segment; --segment {args.kind} judges one segment")
    if args.segment is not None:
        kind, colon, ident = args.segment.partition(":")
        if not (colon and kind and ident):
            raise ledger.LedgerError(f"--segment {args.segment} must be KIND:ID, such as view:2")
    return bisecting.Wanted(category, name, args.statistic, args.depth, args.kind, args.segment)


def _check_bisect_flags(args: argparse.Namespace, wanted: bisecting.Wanted) -> None:
    """The flag combinations § 4.11 stops on."""
    references = args.good is not None or args.bad is not None
    if references and args.bad_above is not None:
        raise ledger.LedgerError("give --bad-above X, or --good FILE... and --bad FILE..., not both")
    if not references and args.bad_above is None:
        raise ledger.LedgerError("give --bad-above X, or --good FILE... and --bad FILE...")
    if references and (args.good is None or args.bad is None):
        raise ledger.LedgerError("--good and --bad go together")
    floors = [flag for flag, given in (("--min-ms", args.min_ms), ("--min-mb", args.min_mb),
                                       ("--min-pct", args.min_pct)) if given is not None]
    if floors and not references:
        raise ledger.LedgerError(f"{floors[0]} sets the references' floor, so it does nothing with --bad-above")
    # A floor in the wrong unit would silently do nothing (DOOM Ants).
    if wanted.category == "mem" and args.min_ms is not None:
        raise ledger.LedgerError("--min-ms is in ms; a mem measure's floor is --min-mb")
    if wanted.category != "mem" and args.min_mb is not None:
        raise ledger.LedgerError("--min-mb is in MB, for a mem measure; this measure's floor is --min-ms")
    if args.dry_run is not None and args.tested:
        raise ledger.LedgerError("--dry-run judges a value instead of run files; give one or the other")
    if args.dry_run is not None and args.skip_straddle:
        raise ledger.LedgerError("--skip-straddle needs tested runs, and a dry run has none")
    if args.dry_run is None and not args.tested:
        raise ledger.LedgerError("give --tested FILE... for the commit under test, or --dry-run VALUE")


def _load(paths: list[str] | None) -> list[bisecting.Loaded]:
    """Each file's Run, or why it could not be read. bisecting.py decides what
    that means: a tested file skips the commit (UT Ants), a reference stops."""
    loaded = []
    for path in paths or []:
        try:
            loaded.append(bisecting.Loaded(path, ledger.read(path), None))
        except ledger.LedgerError as error:
            loaded.append(bisecting.Loaded(path, None, error.reason))
    return loaded


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
