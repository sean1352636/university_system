"""Domain package: apprentices — the record, its lifecycle, breaks and withdrawals."""

from __future__ import annotations

from education_system.systems.apprenticeships.domain.apprentices.breaks import (  # noqa: F401
    BreakInLearning,
    total_break_days,
    validate_new_break,
)
from education_system.systems.apprenticeships.domain.apprentices.models import (  # noqa: F401
    Apprentice,
    ApprenticeSummary,
    ValidationError,
    elapsed_percent,
    planned_end_for,
    validate_age_at_start,
    validate_date_of_birth,
    validate_uln,
    years_between,
)
from education_system.systems.apprenticeships.domain.apprentices.withdrawals import (  # noqa: F401
    Withdrawal,
    validate_withdrawal,
    within_qualifying_period,
)

__all__ = [
    'Apprentice',
    'ApprenticeSummary',
    'BreakInLearning',
    'ValidationError',
    'Withdrawal',
    'elapsed_percent',
    'planned_end_for',
    'total_break_days',
    'validate_age_at_start',
    'validate_date_of_birth',
    'validate_new_break',
    'validate_uln',
    'validate_withdrawal',
    'within_qualifying_period',
    'years_between',
]
