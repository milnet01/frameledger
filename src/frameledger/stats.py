"""Numbers in, numbers out. Imports no other analyser file.

Values are exact integers (thousandths, as ledger.py keeps them), so no
statistic here rounds.
"""

from __future__ import annotations


def percentile(values: list[int], p: int) -> int:
    """The p-th percentile by nearest rank (docs/specs/FLED-0001-run-file-format.md
    § 4.8): of n sorted values, the one at rank ceil(p * n / 100)."""
    if not values:
        raise ValueError("a percentile needs at least one value")
    ordered = sorted(values)
    rank = -(-p * len(ordered) // 100)  # ceiling division, in integers
    return ordered[max(rank, 1) - 1]


def median(values: list[int]) -> int:
    """The nearest-rank 50th percentile: the lower middle of an even count."""
    return percentile(values, 50)
