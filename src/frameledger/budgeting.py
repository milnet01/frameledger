"""Pass budgets (S12): judge one run's passes against a budget file.

The rules are docs/specs/FLED-0001-run-file-format.md § 4.12. A budget's
value is `report`'s own median or 99th percentile for the pass, per
segment kind, so the two commands never disagree on a run. Values and
limits are exact thousandths; a single frame never breaches.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import NamedTuple

import compare
import ledger
import run_report
import stats
import trust

SCHEMA = 1
KEYWORD = "# frameledger-budget"
COLUMNS = "category,name,kind,depth,statistic,limit_ms"
EVERY_KIND = "*"
LIMIT_RE = re.compile(r"([0-9]+)(?:\.([0-9]{1,3}))?")
LIMIT_MAX = 999_999_999_999  # 999999999.999 ms, in thousandths


class Budget(NamedTuple):
    """One line of a budget file."""
    line: int
    category: str
    name: str
    kind: str | None  # EVERY_KIND, a segment kind, or None for frames with no segment
    depth: int | None  # None: the name must be at one depth in the frames judged
    statistic: str  # "median" or "p99"
    limit: int  # thousandths of a ms


class BudgetFile(NamedTuple):
    path: str
    match: dict  # compare-blocking field -> the value the budgets were set for
    budgets: list[Budget]


def read(path: str | Path) -> BudgetFile:
    """Read a budget file. Raises LedgerError naming the line at fault."""
    path = str(path)
    try:
        data = Path(path).read_bytes()
    except OSError as error:
        raise ledger.LedgerError(error.strerror or "cannot be read", path) from error
    return read_bytes(data, path)


def read_bytes(data: bytes, path: str) -> BudgetFile:
    """Read a budget file's contents; `path` names it in errors."""
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]  # some Windows editors add a byte-order mark
    lines = data.split(b"\n")
    if lines[-1] == b"":
        lines.pop()  # the final line ending, not an empty line
    texts = []
    for number, raw in enumerate(lines, start=1):
        try:
            texts.append(raw.removesuffix(b"\r").decode("utf-8"))
        except UnicodeDecodeError:
            raise ledger.LedgerError("the line is not UTF-8 text", path, number) from None
    if not texts:
        raise ledger.LedgerError(f"the file is empty; its first line must be '{KEYWORD} {{...}}'", path)
    match = _header(texts[0], path)

    budgets: list[Budget] = []
    seen: dict[tuple, int] = {}
    columns_read = False
    for number, text in enumerate(texts[1:], start=2):
        if not text.strip() or text.startswith("#"):
            continue  # a blank line or a comment (Vestige)
        if not columns_read:
            if text != COLUMNS:
                raise ledger.LedgerError(f"the column line must be '{COLUMNS}', not '{text}'", path, number)
            columns_read = True
            continue
        found = _budget(text, number, path)
        key = (found.category, found.name, found.kind, found.depth, found.statistic)
        if key in seen:
            raise ledger.LedgerError(f"this budget repeats line {seen[key]}'s", path, number)
        seen[key] = number
        budgets.append(found)
    if not columns_read:
        raise ledger.LedgerError(f"the file has no column line '{COLUMNS}'", path, len(texts))
    if not budgets:
        raise ledger.LedgerError("the file holds no budget, so there is nothing to judge", path, len(texts))
    return BudgetFile(path, match, budgets)


def _header(text: str, path: str) -> dict:
    keyword, _, rest = text.partition(" {")
    if keyword != KEYWORD:
        raise ledger.LedgerError(f"the first line must be '{KEYWORD} {{\"schema\":{SCHEMA}}}'", path, 1)
    try:
        header = json.loads("{" + rest)
    except json.JSONDecodeError:
        raise ledger.LedgerError("the header is not one JSON object", path, 1) from None
    schema = header.get("schema") if isinstance(header, dict) else None
    if type(schema) is not int or schema != SCHEMA:  # not True, not 1.0
        raise ledger.LedgerError(f"schema must be {SCHEMA}, not {json.dumps(schema)}", path, 1)
    match = header.get("match", {})
    if not isinstance(match, dict):
        raise ledger.LedgerError("match must be an object of compare-blocking fields", path, 1)
    for field in match:
        if field not in compare.BLOCKING:
            raise ledger.LedgerError(f"match names {field}, which is not a compare-blocking field "
                                     f"({', '.join(compare.BLOCKING)})", path, 1)
    return match


def _budget(text: str, number: int, path: str) -> Budget:
    fields = next(csv.reader([text]))
    if len(fields) != len(COLUMNS.split(",")):
        raise ledger.LedgerError(f"the line has {len(fields)} fields; a budget has "
                                 f"{len(COLUMNS.split(','))}: {COLUMNS}", path, number)
    category, name, kind, depth, statistic, limit = fields

    def bad(message: str) -> ledger.LedgerError:
        return ledger.LedgerError(message, path, number)

    if category not in run_report.SPAN:
        raise bad(f"category '{category}' must be cpu or gpu")
    if not ledger.NAME_RE.fullmatch(name) or len(name) > ledger.NAME_MAX:
        raise bad(f"name '{name}' must be 1 to {ledger.NAME_MAX} ASCII letters, digits and '_ . / -'")
    if ":" in kind or len(kind.encode()) > ledger.PART_MAX:
        raise bad(f"kind '{kind}' must be a segment kind of at most {ledger.PART_MAX} bytes, "
                  f"'{EVERY_KIND}', or empty")
    if depth and not ledger.COUNT_RE.fullmatch(depth):
        raise bad(f"depth '{depth}' must be a whole number, 0 or more, or empty")
    if statistic not in stats.RANKS:
        raise bad(f"statistic '{statistic}' must be median or p99")
    parts = LIMIT_RE.fullmatch(limit)
    thousandths = int(parts[1]) * 1000 + int((parts[2] or "").ljust(3, "0")) if parts else 0
    if not 1 <= thousandths <= LIMIT_MAX:
        raise bad(f"limit_ms '{limit}' must be 0.001 to 999999999.999, at most three places")
    return Budget(number, category, name, kind or None, int(depth) if depth else None, statistic, thousandths)


def judge(run: ledger.Run, budget_file: BudgetFile, warmup_us: int) -> dict:
    """{"verdict", "summary", "warnings", "result"} for one run that meets
    the format. A run breaking the format, or failing `match`, raises
    LedgerError, as under `report`."""
    run_report.refuse_breaches(run)
    _refuse_mismatch(run, budget_file.match)
    only, stop = _after_warmup(run, warmup_us)
    costs = run_report.Costs(run, only=only)
    judged = len(only) if only is not None else run_report.walled_frames(run)
    notices = run.notices + trust.warnings(run, judged)
    if costs.missing_gpu:
        notices.append(ledger.Notice("gpu_missing", run_report.missing_gpu_message(costs.missing_gpu)))

    entries, unmatched, few = _judge_lines(costs, budget_file)
    notices += few

    reasons = _incomplete(run, stop)
    over = sorted((e for e in entries if e["over"]), key=lambda e: -e["over_ms"])
    summary = run_report.warning_sentences(notices)
    summary += [f"{_label(e['category'], e['name'], e['statistic'], e['segment_kind'])} is "
                f"{e['value_ms']:.3f} ms, over its "
                f"{e['limit_ms']:.3f} ms budget." for e in over]
    summary += [_unmatched_sentence(b) for b in unmatched]
    if over:
        verdict = "fail"
        summary.append(f"The run is over budget: {len(over)} of {len(entries)} budgets judged are over.")
    elif reasons or unmatched:
        verdict = "inconclusive"
        why = reasons + ([f"{run_report.counted(len(unmatched), 'budget')} matched nothing"]
                         if unmatched else [])
        summary.append(f"No budget is over, but the verdict is inconclusive: {'; '.join(why)}.")
    else:
        verdict = "pass"
        summary.append(f"Every budget holds: {run_report.counted(len(entries), 'budget')} judged.")
    return {"verdict": verdict, "summary": summary, "warnings": run_report.warning_entries(notices),
            "result": {
                "budgets": entries,
                "unmatched": [_unmatched_entry(b) for b in unmatched],
                "warmup_s": warmup_us / run_report.SECOND,
                "rows_dropped": run.close["rows_dropped"] if run.close else None,
                "finished": run.close is not None,
            }}


def _judge_lines(costs: run_report.Costs, budget_file: BudgetFile) -> tuple[list[dict], list[Budget],
                                                                             list[ledger.Notice]]:
    """Every budget line judged: one entry per line and kind, in the file's
    order; the lines nothing matched; and a budget_few_frames warning per
    p99 entry over too few frames."""
    # A line naming a kind replaces a `*` line with the same pass and statistic there (UT Ants).
    replaced = {(b.category, b.name, b.depth, b.statistic, b.kind)
                for b in budget_file.budgets if b.kind != EVERY_KIND}
    entries, unmatched, notices = [], [], []
    for b in budget_file.budgets:
        depth = b.depth if b.depth is not None else _one_depth(costs, b, budget_file.path)
        present = _kinds(costs, b, depth)
        if b.kind == EVERY_KIND:
            judged = [k for k in present if (b.category, b.name, b.depth, b.statistic, k) not in replaced]
        else:
            judged = [b.kind] if b.kind in present else []
        if not present or (b.kind != EVERY_KIND and not judged):
            unmatched.append(b)
        for kind in judged:
            values = costs.pass_values[(kind, b.category, b.name, depth)]
            entries.append(_entry(b, kind, depth, values))
            if b.statistic == "p99" and len(values) < trust.FEWEST_FRAMES:
                notices.append(ledger.Notice("budget_few_frames", (
                    f"{_label(b.category, b.name, b.statistic, kind)} is judged over "
                    f"{run_report.counted(len(values), 'frame')}, fewer than {trust.FEWEST_FRAMES}, "
                    "so it is the slowest frame's time")))
    return entries, unmatched, notices


def _refuse_mismatch(run: ledger.Run, match: dict) -> None:
    """A budget file holds only for the settings it names (UT Ants). A field
    the run leaves out does not match, nor does an empty inputs list."""
    differ = []
    for field, wanted in match.items():
        have = run.header.get(field, compare.ABSENT)
        want_key, have_key = compare.match_key(field, wanted), compare.match_key(field, have)
        if want_key is None or have_key is None or want_key != have_key:
            shown = "absent" if have is compare.ABSENT else json.dumps(have)
            differ.append(f"{field} is {json.dumps(wanted)} in the budget file and {shown} in the run")
    if differ:
        raise ledger.LedgerError("the run does not have the settings the budgets were set for: "
                                 + "; ".join(differ), run.path)


def _after_warmup(run: ledger.Run, warmup_us: int) -> tuple[set[int] | None, str | None]:
    """The frames ending at or after the warm-up, on floor's timeline, and
    what stops the timeline early; (None, None) with no warm-up, when every
    frame counts."""
    if not warmup_us:
        return None, None
    timed, _, stop, _ = run_report.timeline(run)
    return {t[0] for t in timed if t[2] >= warmup_us}, stop


def _one_depth(costs: run_report.Costs, b: Budget, path: str) -> int | None:
    """The one depth the pass has in the frames this budget judges, or None
    when it has none. Two is exit 3, naming the pass and both."""
    depths = sorted({depth for (kind, category, name, depth) in costs.pass_values
                     if (category, name) == (b.category, b.name)
                     and (b.kind == EVERY_KIND or kind == b.kind)})
    if len(depths) > 1:
        raise ledger.LedgerError(
            f"{b.category}/{b.name} is at depths {' and '.join(map(str, depths))} in the frames this "
            "line judges; give it a depth", path, b.line)
    return depths[0] if depths else None


def _kinds(costs: run_report.Costs, b: Budget, depth: int | None) -> list[str | None]:
    """The kinds the pass appears in at `depth`, in § 4.8's kind order."""
    return sorted({kind for (kind, category, name, d) in costs.pass_values
                   if (category, name, d) == (b.category, b.name, depth)}, key=run_report.kind_order)


def _entry(b: Budget, kind: str | None, depth: int, values: list[int]) -> dict:
    value = stats.percentile(values, stats.RANKS[b.statistic])
    return {"line": b.line, "category": b.category, "name": b.name, "segment_kind": kind, "depth": depth,
            "statistic": b.statistic, "limit_ms": b.limit / 1000, "value_ms": value / 1000,
            "over_ms": (value - b.limit) / 1000, "frames": len(values), "over": value > b.limit}


def _unmatched_entry(b: Budget) -> dict:
    return {"line": b.line, "category": b.category, "name": b.name, "segment_kind": b.kind,
            "depth": b.depth, "statistic": b.statistic}


def _label(category: str, name: str, statistic: str, kind: str | None) -> str:
    """`gpu/ssao p99 in view segments`."""
    return f"{category}/{name} {statistic} in {run_report.kind_name(kind)} segments"


def _unmatched_sentence(b: Budget) -> str:
    frames = "frame" if b.kind == EVERY_KIND else f"{run_report.kind_name(b.kind)} frame"
    depth = "" if b.depth is None else f" at depth {b.depth}"
    return (f"Line {b.line}'s {b.category}/{b.name}{depth} is in no {frames} judged, so its "
            f"{b.statistic} budget cannot be judged; a re-run gives the same: fix the budget file "
            "or the engine.")


def _incomplete(run: ledger.Run, stop: str | None) -> list[str]:
    """Why holding budgets cannot pass: dropped rows, no close line, or,
    with a warm-up, a timeline that stops early."""
    reasons = []
    if run.close is None:
        reasons.append("the file has no close line, so the run did not finish")
    elif run.close["rows_dropped"]:
        reasons.append(f"the writer dropped {run_report.counted(run.close['rows_dropped'], 'row')}")
    if stop:
        reasons.append(f"{stop}, so the frames after the warm-up cannot be placed")
    return reasons
