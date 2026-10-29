"""Numbers in, numbers out. Imports no other analyser file.

Values are exact integers (thousandths, as ledger.py keeps them), so no
statistic here rounds.
"""

from __future__ import annotations


# The percentile rank each statistic a command can judge stands for.
RANKS = {"median": 50, "p99": 99}


def percentile(values: list[int], p: int) -> int:
    """The p-th percentile by nearest rank (docs/specs/FLED-0001-run-file-format.md
    § 4.8): of n sorted values, the one at rank ceil(p * n / 100)."""
    return percentiles(values, p)[0]


def percentiles(values: list[int], *ps: int) -> tuple[int, ...]:
    """Several nearest-rank percentiles of one list, sorting it once."""
    if not values:
        raise ValueError("a percentile needs at least one value")
    ordered = sorted(values)
    n = len(ordered)
    # -(-p * n // 100) is ceil(p * n / 100), in integers.
    return tuple(ordered[max(-(-p * n // 100), 1) - 1] for p in ps)


def median(values: list[int]) -> int:
    """The nearest-rank 50th percentile: the lower middle of an even count."""
    return percentile(values, 50)
