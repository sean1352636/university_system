"""Withdrawals: leaving an apprenticeship without completing it.

The record is kept — a withdrawn apprentice still has a funding history
the provider can be asked about — so this module is about getting the
withdrawal record right: the last day of learning, the reason, and what
the timing means for funding.

Dates arrive as ISO ``YYYY-MM-DD`` strings already normalised by the
service, so they compare correctly as strings.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError

# The one withdrawal reason that is really a different status.
TRANSFER_REASON = "Transferred to another provider"


@dataclass(frozen=True)
class Withdrawal:
    """One recorded withdrawal."""

    withdrawal_id: int
    apprentice_id: int
    withdrawal_date: str
    last_activity_date: str | None
    reason: str
    notes: str | None = None
    recorded_by: str | None = None
    created_at: str = ""

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> Withdrawal:
        return cls(
            withdrawal_id=row["withdrawal_id"],
            apprentice_id=row["apprentice_id"],
            withdrawal_date=row["withdrawal_date"],
            last_activity_date=row.get("last_activity_date"),
            reason=row.get("reason") or "",
            notes=row.get("notes"),
            recorded_by=row.get("recorded_by"),
            created_at=row.get("created_at") or "",
        )


def validate_withdrawal(
    *, withdrawal_date: str, last_activity_date: str, start_date: str | None
) -> None:
    """Check the dates on a withdrawal.

    The last day of learning is what the funding return records as the
    end, so it matters more than the day the withdrawal was entered: it
    cannot come after that day, nor before the apprenticeship started.
    """
    if last_activity_date > withdrawal_date:
        raise ValidationError("The last day of learning cannot be after the withdrawal date")
    if start_date and last_activity_date < start_date:
        raise ValidationError(
            "The last day of learning cannot be before the apprenticeship started"
        )


def require_not_a_transfer(reason: str, *, transfer_allowed: bool) -> None:
    """Refuse a withdrawal that is really a move to another provider.

    Only when the Transferred status is actually available from here —
    an applicant who goes elsewhere never started, so for them it is a
    withdrawal after all.
    """
    if reason == TRANSFER_REASON and transfer_allowed:
        raise ValidationError(
            "Moving to another provider is a transfer, not a withdrawal — "
            "choose 'Transferred' instead"
        )


def within_qualifying_period(start_date: str | None, last_activity_date: str) -> bool:
    """Did they leave before the funding qualifying period was up?

    False for someone who never started: there was nothing to qualify.
    """
    if not start_date:
        return False
    try:
        days = (date.fromisoformat(last_activity_date) - date.fromisoformat(start_date)).days
    except ValueError:
        return False
    return days < config.QUALIFYING_PERIOD_DAYS
