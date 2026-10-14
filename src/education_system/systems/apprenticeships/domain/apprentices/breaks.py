"""Breaks in learning.

A break pauses an apprenticeship without ending it: funding stops, the
record is kept, and the apprentice is expected back. Taking and ending
one is a lifecycle move (see :mod:`lifecycle`); this module holds the
rules about the break record that move opens and closes.

Dates arrive as ISO ``YYYY-MM-DD`` strings already normalised by the
service, so they compare correctly as strings.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError


@dataclass(frozen=True)
class BreakInLearning:
    """One break, open until the apprentice returns or leaves."""

    break_id: int
    apprentice_id: int
    start_date: str
    expected_return: str | None
    actual_return: str | None
    reason: str
    notes: str | None = None
    created_at: str = ""

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> BreakInLearning:
        return cls(
            break_id=row["break_id"],
            apprentice_id=row["apprentice_id"],
            start_date=row["start_date"],
            expected_return=row.get("expected_return"),
            actual_return=row.get("actual_return"),
            reason=row.get("reason") or "",
            notes=row.get("notes"),
            created_at=row.get("created_at") or "",
        )

    @property
    def is_open(self) -> bool:
        return self.actual_return is None

    def days(self, as_of: date) -> int:
        """Length in days; an open break runs to *as_of*.

        An unreadable date counts as zero rather than raising, because this
        feeds progress figures that are shown for every apprentice.
        """
        try:
            start = date.fromisoformat(self.start_date)
            end = date.fromisoformat(self.actual_return) if self.actual_return else as_of
        except (TypeError, ValueError):
            return 0
        return max(0, (end - start).days)

    def is_overdue(self, as_of: date) -> bool:
        """Still open past the day they were expected back — someone to chase."""
        if not self.is_open or not self.expected_return:
            return False
        try:
            return as_of > date.fromisoformat(self.expected_return)
        except ValueError:
            return False


def total_break_days(breaks: Iterable[BreakInLearning], as_of: date) -> int:
    """Days spent on all breaks, an open one counted to *as_of*."""
    return sum(b.days(as_of) for b in breaks)


def validate_new_break(
    *, start_date: str, expected_return: str | None, programme_start: str | None
) -> None:
    """Check a break before it is opened.

    A break is a pause in training that has started, so it cannot begin
    before the apprenticeship did; and an expected return has to come
    after the break begins or it is not a break.
    """
    if programme_start and start_date < programme_start:
        raise ValidationError("A break cannot start before the apprenticeship did")
    if expected_return and expected_return <= start_date:
        raise ValidationError("The expected return date must be after the break starts")
