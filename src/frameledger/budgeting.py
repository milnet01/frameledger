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
ANY_DEPTH = None  # for _kinds: a pass at whatever depth
# Nine whole digits at most, so int() never meets a huge number (Vestige).
LIMIT_RE = re.compile(r"([0-9]{1,9})(?:\.([0-9]{1,3}))?")
DEPTH_RE = re.compile(r"[0-9]{1,9}")


class Budget(NamedTuple):
    """One line of a budget file."""
    line: int
    category: str
    name: str
    kind: str | None  # EVERY_KIND, a segment kind, or None for frames with no segment
    depth: int | None  # None: the name must be at one depth in the frames judged
    statistic: str  # "median" or "p99"
    limit: int  # thousandths of a ms


class Judged(NamedTuple):
    """What _judge_lines finds."""
    entries: list[dict]  # one per budget line and kind judged, in the file's order
    unmatched: list[Budget]
    notices: list[ledger.Notice]  # budget_few_frames


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
    for field, value in match.items():
        if field not in compare.BLOCKING:
            raise ledger.LedgerError(f"match names {field}, which is not a compare-blocking field "
                                     f"({', '.join(compare.BLOCKING)})", path, 1)
        _, valid, wanted = ledger.HEADER_FIELDS[field]
        if not valid(value):  # as the run header's own field must be
            raise ledger.LedgerError(f"match's {field} must be {wanted}", path, 1)
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
    if depth and not DEPTH_RE.fullmatch(depth):
        raise bad(f"depth '{_clip(depth)}' must be a whole number of at most nine digits, or empty")
    if statistic not in stats.RANKS:
        raise bad(f"statistic '{statistic}' must be median or p99")
    parts = LIMIT_RE.fullmatch(limit)
    thousandths = 0
    if parts:
        whole, places = parts.groups()
        thousandths = int(whole) * 1000 + int((places or "").ljust(3, "0"))
    if thousandths < 1:  # also a limit_ms that is not a number at all
        raise bad(f"limit_ms '{_clip(limit)}' must be 0.001 to 999999999.999, at most three places")
    return Budget(number, category, name, kind or None, int(depth) if depth else None, statistic, thousandths)


def judge(run: ledger.Run, budget_file: BudgetFile, warmup_us: int) -> dict:
    """{"verdict", "summary", "warnings", "result"} for one run that meets
    the format. A run breaking the format, or failing `match`, raises
    LedgerError, as under `report`."""
    run_report.refuse_breaches(run)
    _refuse_mismatch(run, budget_file.match)
    only, stop = _after_warmup(run, warmup_us)
    costs = run_report.Costs(run, only=only)
    frames_judged = len(only) if only is not None else run_report.walled_frames(run)
    notices = run.notices + trust.warnings(run, frames_judged)
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
    if only is not None and not only:
        # Every line is unmatched, but the run is too short, not the file wrong (UT Ants).
        summary.append(f"No frame ends after the {_seconds(warmup_us)} s warm-up, so no budget "
                       "can be judged; a longer run is the fix.")
    else:
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


def _judge_lines(costs: run_report.Costs, budget_file: BudgetFile) -> Judged:
    """Every budget line judged. A line naming a kind replaces a `*` line
    there when both judge one pass: the same category, name and
    statistic, at the same depth once an empty depth is resolved (UT Ants).
    So named lines are resolved first."""
    # (category, name, statistic, kind) -> the depths named lines judge there; a
    # pass can run at two depths, each with its own line (DOOM Ants, UT Ants).
    taken: dict[tuple, set[int]] = {}
    for named in budget_file.budgets:
        depth = _depth(costs, named, [named.kind], budget_file.path) if named.kind != EVERY_KIND else None
        if depth is not None:
            taken.setdefault((named.category, named.name, named.statistic, named.kind), set()).add(depth)
    entries, unmatched, notices = [], [], []
    judged_by: dict[tuple, int] = {}  # (category, name, statistic, kind, depth) -> the line judging it
    for budget in budget_file.budgets:
        everywhere = _kinds(costs, budget, ANY_DEPTH)
        if budget.kind == EVERY_KIND:
            kinds = [k for k in everywhere if not _taken(taken, budget, k, costs)]
        else:
            kinds = [budget.kind] if budget.kind in everywhere else []
        depth = _depth(costs, budget, kinds, budget_file.path)
        judged = [k for k in kinds if k in _kinds(costs, budget, depth)]
        if budget.kind == EVERY_KIND:
            # In no frame at all; a `*` line whose every kind a named line took matched.
            matched = bool(_kinds(costs, budget, ANY_DEPTH if budget.depth is None else budget.depth))
        else:
            matched = bool(judged)
        if not matched:
            unmatched.append(budget)
        for kind in judged:
            key = (budget.category, budget.name, budget.statistic, kind, depth)
            if key in judged_by:  # two lines resolving to one pass, as the literal repeat check cannot see
                raise ledger.LedgerError(
                    f"this line judges {_label(budget.category, budget.name, budget.statistic, kind)} at "
                    f"depth {depth}, as line {judged_by[key]} does", budget_file.path, budget.line)
            judged_by[key] = budget.line
            values = costs.pass_values[(kind, budget.category, budget.name, depth)]
            entries.append(_entry(budget, kind, depth, values))
            if budget.statistic == "p99" and len(values) < trust.FEWEST_FRAMES:
                notices.append(ledger.Notice("budget_few_frames", (
                    f"{_label(budget.category, budget.name, budget.statistic, kind)} is judged over "
                    f"{run_report.counted(len(values), 'frame')}, fewer than {trust.FEWEST_FRAMES}, "
                    "so it is the slowest frame's time")))
    return Judged(entries, unmatched, notices)


def _taken(taken: dict, star: Budget, kind: str | None, costs: run_report.Costs) -> bool:
    """Whether a named line judges the `*` line's pass in `kind`: one with
    the same category, name and statistic, at the `*` line's depth, or at
    a depth the pass has there when the `*` line's is empty."""
    depths = taken.get((star.category, star.name, star.statistic, kind), set())
    if star.depth is not None:
        return star.depth in depths
    return any(kind in _kinds(costs, star, depth) for depth in depths)


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
    frame counts. So at 0 the last frame, which has no frame/wall, counts,
    as in `report`; above 0 it does not, since its end is unknown (DOOM
    Ants)."""
    if not warmup_us:
        return None, None
    timed, _, stop, _ = run_report.timeline(run)
    return {frame for frame, _rows, end, _wall in timed if end >= warmup_us}, stop


def _depth(costs: run_report.Costs, budget: Budget, kinds: list[str | None], path: str) -> int | None:
    """The depth `budget` judges in `kinds`: its own, or else the one depth
    the pass has there, or None when it has none. Two is exit 3, naming the
    pass and both."""
    if budget.depth is not None:
        return budget.depth
    depths = sorted({depth for (kind, category, name, depth) in costs.pass_values
                     if (category, name) == (budget.category, budget.name) and kind in kinds})
    if len(depths) > 1:
        raise ledger.LedgerError(
            f"{budget.category}/{budget.name} is at depths {' and '.join(map(str, depths))} in the frames "
            "this line judges; give it a depth", path, budget.line)
    return depths[0] if depths else None


def _kinds(costs: run_report.Costs, budget: Budget, depth: int | None) -> list[str | None]:
    """The kinds the pass appears in at `depth`, or at any depth for
    ANY_DEPTH, in § 4.8's kind order."""
    return sorted({kind for (kind, category, name, d) in costs.pass_values
                   if (category, name) == (budget.category, budget.name) and depth in (ANY_DEPTH, d)},
                  key=run_report.kind_order)


def _entry(budget: Budget, kind: str | None, depth: int, values: list[int]) -> dict:
    """`depth` is resolved: a kind is judged only where the pass has one."""
    value = stats.percentile(values, stats.RANKS[budget.statistic])
    return {"line": budget.line, "category": budget.category, "name": budget.name, "segment_kind": kind,
            "depth": depth, "statistic": budget.statistic, "limit_ms": budget.limit / 1000,
            "value_ms": value / 1000, "over_ms": (value - budget.limit) / 1000, "frames": len(values),
            "over": value > budget.limit}


def _unmatched_entry(budget: Budget) -> dict:
    return {"line": budget.line, "category": budget.category, "name": budget.name,
            "segment_kind": budget.kind, "depth": budget.depth, "statistic": budget.statistic}


def _label(category: str, name: str, statistic: str, kind: str | None) -> str:
    """`gpu/ssao p99 in view segments`."""
    return f"{category}/{name} {statistic} in {run_report.kind_name(kind)} segments"


def _unmatched_sentence(budget: Budget) -> str:
    frames = "frame" if budget.kind == EVERY_KIND else f"{run_report.kind_name(budget.kind)} frame"
    depth = "" if budget.depth is None else f" at depth {budget.depth}"
    return (f"Line {budget.line}'s {budget.category}/{budget.name}{depth} is in no {frames} judged, "
            f"so its {budget.statistic} budget cannot be judged: the pass is in none of those frames, "
            "so a re-run gives the same: fix the budget file or the engine.")


def _seconds(microseconds: int) -> str:
    return f"{microseconds / run_report.SECOND:g}"


def _clip(text: str) -> str:
    """A field short enough to quote in a sentence."""
    return text if len(text) <= 20 else text[:17] + "..."


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
