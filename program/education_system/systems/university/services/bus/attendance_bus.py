"""Cross-domain attendance helpers.

Wraps the existing attendance domain in two thin entry-points:

* ``flag_student_concern(student_id, ...)`` — a student crosses an
  attendance threshold; opens a Student-Affairs case via
  ``cases_bus`` so safeguarding/welfare can pick it up. Idempotent
  per `(student_id, week)` so the same student isn't case'd twice
  in seven days.

* ``flag_module_attendance_risk(module_id, ...)`` — a class-wide
  pattern (whole cohort no-show, repeated cancellations) raises a
  row in the risk register tagged ``category='Academic'`` with
  ``reference_id=f"module:{module_id}"`` so module delivery is the
  risk, not the student.

* ``post_research_session_payment(student_id, project_id,
   hours, hourly_rate)`` — closes the loop between attendance
  records of ``kind='research_session'`` and the research grant
  ledger. Pays the participant via ``commerce_bus.post_sale``
  (paid-in-full, balance-neutral) and debits the grant via
  ``finance_bus.raise_charge`` against ``project:{project_id}``.

These are intentionally small wrappers so the existing
``predictive_analytics`` / ``absence_tracking`` modules can call them
without learning about cases / risks / finance schemas.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


# Sliding-window cache of (student_id, week) → True so we don't open
# a duplicate concern case for the same student within seven days.
# In-process only; harmless if it gets reset.
_RECENT_FLAGS: dict[tuple[str, str], float] = {}


def _week_key() -> str:
    iso = datetime.now().isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


# ---------------------------------------------------------------------------
# Student-level concern
# ---------------------------------------------------------------------------

def flag_student_concern(
    student_id: str | int,
    *,
    threshold_pct: float,
    description: str | None = None,
    opened_by: str | None = None,
) -> int | None:
    """Open a ``cases_bus`` ``attendance_concern`` case for the
    student. Returns the case_id, or ``None`` if recently flagged
    (idempotent per week).
    """
    if not student_id:
        return None
    sid = str(student_id)
    key = (sid, _week_key())
    if key in _RECENT_FLAGS:
        return None

    try:
        from education_system.systems.university.services.bus import (
            cases_bus,
        )
    except Exception as exc:
        logger.debug("cases_bus import failed: %s", exc)
        return None

    sev = "Critical" if threshold_pct < 50 else (
          "High" if threshold_pct < 70 else "Minor")
    case_id = cases_bus.open_case(
        kind="attendance_concern",
        subject_id=sid,
        opened_by=opened_by,
        description=description
                    or f"Attendance below threshold ({threshold_pct:.0f}%).",
        severity=sev,
        offense_type="Attendance pattern",
    )
    if case_id:
        _RECENT_FLAGS[key] = datetime.now().timestamp()
    return case_id


# ---------------------------------------------------------------------------
# Module-level (class-wide) risk
# ---------------------------------------------------------------------------

def flag_module_attendance_risk(
    module_id: str | int,
    *,
    cohort_pct: float,
    weeks_observed: int = 1,
    owner: str | None = None,
) -> int | None:
    """Raise a ``risks`` row when a *whole module* shows abnormal
    attendance — cohort_pct is the rolling cohort attendance %.
    """
    if not module_id:
        return None
    try:
        from education_system.systems.university.services.bus import (
            risk_bus,
        )
    except Exception as exc:
        logger.debug("risk_bus import failed: %s", exc)
        return None

    likelihood = 5 if cohort_pct < 50 else (4 if cohort_pct < 65 else 3)
    impact = 4 if weeks_observed >= 3 else 3
    return risk_bus.raise_risk(
        title=f"Module attendance pattern: {module_id}",
        category="Academic",
        department="Academics",
        description=(
            f"Cohort attendance has averaged {cohort_pct:.0f}% over "
            f"{weeks_observed} week(s). Indicates module-delivery "
            "or scheduling issue, not individual student behaviour."
        ),
        likelihood=likelihood, impact=impact,
        owner=owner,
        reference_id=f"module:{module_id}",
    )


# ---------------------------------------------------------------------------
# Research-session payments
# ---------------------------------------------------------------------------

def post_research_session_payment(
    student_id: str | int,
    project_id: str | int,
    hours: float,
    hourly_rate: float,
    *,
    description: str | None = None,
    processed_by: str | None = None,
) -> dict[str, Any]:
    """Close the loop between attendance and research finance.

    Pays the participant (paid-in-full sale → balance-neutral row +
    loyalty points) and debits the project budget against
    ``project:{project_id}`` so ``finance_bus.grant_balance`` shows
    the remaining grant.
    """
    out: dict[str, Any] = {
        "participant_tx_id": None,
        "grant_tx_id": None,
        "amount": 0.0,
    }
    if not student_id or not project_id:
        return out
    amt = round(float(hours or 0) * float(hourly_rate or 0), 2)
    if amt <= 0:
        return out
    out["amount"] = amt
    desc = description or (
        f"Research session ({hours:g}h @ £{hourly_rate}/h, "
        f"project {project_id})"
    )

    try:
        from education_system.systems.university.services.bus import (
            commerce_bus,
        )
        sale = commerce_bus.post_sale(
            student_id,
            source="research_participation",
            amount=amt,
            description=desc,
            reference_id=f"project:{project_id}",
            processed_by=processed_by or "research_portal",
        )
        out["participant_tx_id"] = sale.get("tx_id")
    except Exception as exc:
        logger.debug("research participant payout failed: %s", exc)

    try:
        from education_system.systems.university.services.bus import (
            finance_bus,
        )
        out["grant_tx_id"] = finance_bus.raise_charge(
            student_id, amt,
            source="research_grant_spend",
            description=desc,
            reference_id=str(project_id),
            processed_by=processed_by or "research_portal",
        )
    except Exception as exc:
        logger.debug("research grant debit failed: %s", exc)

    return out


__all__ = [
    "flag_student_concern",
    "flag_module_attendance_risk",
    "post_research_session_payment",
]
