"""Where a rejected UCAS applicant meets clearing.

``clearing_applications`` has carried a ``ucas_id`` column since the
baseline migration, and nothing has ever put anything in it. The clearing
service takes one as an optional argument to
``submit_clearing_application`` and the CLI asks an operator to type it in
by hand. Meanwhile the UCAS module knows every applicant's UCAS personal
id and knows exactly which of them we turned down — the two halves of the
same person sat in the same database, unjoined.

That costs twice. A learner we rejected in the main cycle rings up on
results day and is taken as a stranger, with their course, their grades
and the reason we said no all sitting one query away. And an applicant who
does come through clearing can never be reconciled with the UCAS choice
they made months earlier, so the same person counts twice in every
admissions total.

This module is the join. It is deliberately not an automation: rejecting
somebody does not put them into clearing, because clearing is something an
applicant chooses to enter and a university chooses to offer. What it does
is make the match *findable* — record that a rejection happened against a
UCAS id, surface any clearing application that already quotes that id, and
give an officer a one-step referral when they decide to make one.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from education_system.systems.university.infrastructure.database.db import (
    get_connection,
)

logger = logging.getLogger(__name__)

__all__ = [
    "ClearingMatch",
    "find_clearing_application",
    "note_rejection",
    "refer_to_clearing",
    "unmatched_clearing_applications",
]


@dataclass
class ClearingMatch:
    """A clearing application and the UCAS choice it belongs to."""

    clearing_id: int
    applicant_name: str
    ucas_id: str | None
    status: str
    preferred_course: str | None
    tariff_points: int
    #: Filled in when the UCAS side knows this person.
    sf_choice_id: int | None = None
    sf_student_id: str | None = None
    ucas_decision: str | None = None


def _service():
    from education_system.systems.university.domains.admissions.domain.clearing_adjustment.services.clearing_adjustment_service import (  # noqa: E501
        ClearingAdjustmentService,
    )
    return ClearingAdjustmentService()


def _normalise_ucas_id(value: str | None) -> str:
    """UCAS personal ids are ten digits; compare them as digits alone so a
    space or a stray hyphen typed into clearing still matches."""
    return "".join(ch for ch in str(value or "") if ch.isdigit())


# ── Rejection side ─────────────────────────────────────────────────

def note_rejection(choice, sf_student_id: str | None) -> ClearingMatch | None:
    """Called when a UCAS choice is rejected.

    Looks for a clearing application already quoting this applicant's UCAS
    id and logs the match if there is one. Creates nothing: a rejection is
    not an application to clearing. Returns the match, or ``None``.
    """
    ucas_id = _ucas_id_for_choice(choice)
    if not ucas_id:
        return None
    match = find_clearing_application(ucas_id)
    if match is None:
        logger.debug(
            "Rejected UCAS choice #%s (UCAS id %s) has no clearing "
            "application", getattr(choice, "choice_id", "?"), ucas_id)
        return None
    match.sf_choice_id = getattr(choice, "choice_id", None)
    match.sf_student_id = sf_student_id
    match.ucas_decision = "Rejected"
    logger.info(
        "Rejected UCAS choice #%s matches clearing application #%d "
        "(UCAS id %s) — the same applicant is in clearing",
        match.sf_choice_id, match.clearing_id, ucas_id)
    return match


def _ucas_id_for_choice(choice) -> str:
    """The applicant's UCAS personal id, via the parent application."""
    try:
        from education_system.systems.university.domains.admissions.domain.ucas import (
            ucas as _ucas,
        )
        app = _ucas._sf().get_application(choice.application_id)
        return _normalise_ucas_id(app.ucas_id if app else None)
    except Exception:
        logger.debug("Could not read the UCAS id for a choice", exc_info=True)
        return ""


# ── Lookup ─────────────────────────────────────────────────────────

def find_clearing_application(ucas_id: str | None) -> ClearingMatch | None:
    """The clearing application quoting *ucas_id*, if one exists."""
    wanted = _normalise_ucas_id(ucas_id)
    if not wanted:
        return None
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT id, applicant_name, email, ucas_id, status,
                      preferred_course, tariff_points
                 FROM clearing_applications
                WHERE ucas_id IS NOT NULL AND ucas_id <> ''
                ORDER BY applied_at DESC""",
        ).fetchall()
    except Exception:
        logger.debug("Clearing applications unavailable", exc_info=True)
        return None
    finally:
        conn.close()
    for r in rows:
        if _normalise_ucas_id(r["ucas_id"]) == wanted:
            return ClearingMatch(
                clearing_id=int(r["id"]),
                applicant_name=r["applicant_name"] or "",
                ucas_id=r["ucas_id"],
                status=r["status"] or "pending",
                preferred_course=r["preferred_course"],
                tariff_points=int(r["tariff_points"] or 0),
            )
    return None


def unmatched_clearing_applications() -> list[ClearingMatch]:
    """Clearing applicants whose UCAS id we hold no choice for.

    The other half of the reconciliation: these are the people clearing
    thinks are new. Some genuinely are; the rest applied to us months ago
    and the two records have never been put side by side.
    """
    from education_system.systems.university.domains.admissions.domain.ucas import (
        ucas as _ucas,
    )
    try:
        known = {_normalise_ucas_id(a.ucas_id)
                 for a in _ucas.list_applicants() if a.ucas_id}
    except Exception:
        logger.info("Could not read UCAS applicants", exc_info=True)
        known = set()

    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT id, applicant_name, ucas_id, status,
                      preferred_course, tariff_points
                 FROM clearing_applications
                ORDER BY applied_at DESC""",
        ).fetchall()
    except Exception:
        logger.debug("Clearing applications unavailable", exc_info=True)
        return []
    finally:
        conn.close()

    out: list[ClearingMatch] = []
    for r in rows:
        if _normalise_ucas_id(r["ucas_id"]) in known:
            continue
        out.append(ClearingMatch(
            clearing_id=int(r["id"]),
            applicant_name=r["applicant_name"] or "",
            ucas_id=r["ucas_id"],
            status=r["status"] or "pending",
            preferred_course=r["preferred_course"],
            tariff_points=int(r["tariff_points"] or 0),
        ))
    return out


# ── Referral ───────────────────────────────────────────────────────

def refer_to_clearing(choice_id: int, *,
                      preferred_course: str | None = None,
                      tariff_points: int = 0,
                      referred_by: str | None = None) -> int:
    """Put a UCAS applicant we turned down into clearing.

    An explicit action by an admissions officer, never a side effect of
    the rejection. Idempotent on the UCAS id, so referring somebody twice
    returns the application they already have rather than creating a
    duplicate for the same person.

    Returns the ``clearing_applications`` row id.
    """
    from education_system.systems.university.domains.admissions.domain.ucas import (
        ucas as _ucas,
    )
    sf = _ucas._sf()
    choice = sf.get_choice(choice_id)
    if choice is None:
        raise ValueError(f"No UCAS choice with id {choice_id}")
    full = _ucas.get_full_application(choice.application_id)
    if full is None:
        raise ValueError(
            f"Choice {choice_id} has no readable parent application")

    ucas_id = _normalise_ucas_id(full.ucas_id)
    existing = find_clearing_application(ucas_id)
    if existing is not None:
        logger.info(
            "UCAS choice #%d already has clearing application #%d",
            choice_id, existing.clearing_id)
        return existing.clearing_id

    qualifications = ", ".join(full.subjects) if full.subjects else None
    clearing_id = _service().submit_clearing_application(
        applicant_name=full.student_name,
        email=full.student_email,
        ucas_id=full.ucas_id,
        tariff_points=tariff_points,
        qualifications=qualifications,
        preferred_course=(preferred_course or choice.course_name),
    )
    logger.info(
        "Referred UCAS choice #%d to clearing as application #%d "
        "(UCAS id %s, by %s)",
        choice_id, clearing_id, full.ucas_id or "—", referred_by or "—")
    return int(clearing_id)
