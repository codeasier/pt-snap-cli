"""Cancellation helpers shared by dataset validation and query execution.

The small protocol avoids a dependency on the query/source resolver. Validators
can also be used at publication time without a query deadline.
"""

from __future__ import annotations

import math
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from typing import Protocol, TypeVar

from .errors import QueryCancelledError, QueryTimeoutError


class ValidationBudget(Protocol):
    def remaining(self) -> float | None: ...


def check_budget(budget: ValidationBudget | None) -> None:
    if budget is not None:
        budget.remaining()


def sqlite_timeout(budget: ValidationBudget | None) -> float:
    """SQLite's busy wait must not outlive the remaining shared deadline."""
    remaining = budget.remaining() if budget is not None else None
    # SQLite truncates to whole milliseconds. Round up so an exhausted busy
    # wait is classified as timeout, not a spurious schema/locked error just
    # before the deadline (the additional wait is at most one millisecond).
    return 5.0 if remaining is None else min(5.0, math.ceil(remaining * 1000) / 1000)


_T = TypeVar("_T")


def checked_rows(rows: Iterable[_T], budget: ValidationBudget | None) -> Iterator[_T]:
    """Bound Python-side work between deadline checks, including cursor iteration."""
    check_budget(budget)
    for index, row in enumerate(rows):
        if index % 256 == 0:
            check_budget(budget)
        yield row
    check_budget(budget)


@contextmanager
def validation_progress(
    conn: sqlite3.Connection, budget: ValidationBudget | None
) -> Iterator[None]:
    """Preserve timeout/cancellation instead of reporting an invalid schema."""
    check_budget(budget)
    interrupted: QueryTimeoutError | QueryCancelledError | None = None

    def progress() -> int:
        nonlocal interrupted
        try:
            check_budget(budget)
        except (QueryTimeoutError, QueryCancelledError) as exc:
            interrupted = exc
            return 1
        return 0

    if budget is not None:
        conn.set_progress_handler(progress, 1000)
    try:
        try:
            yield
        except sqlite3.DatabaseError:
            if interrupted is not None:
                raise interrupted from None
            check_budget(budget)
            raise
        check_budget(budget)
    finally:
        if budget is not None:
            conn.set_progress_handler(None, 0)
