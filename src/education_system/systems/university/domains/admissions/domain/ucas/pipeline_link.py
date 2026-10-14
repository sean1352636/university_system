"""Open this university's own admissions application for a UCAS offer.

The UCAS route ran entirely beside the university's admissions pipeline.
``ucas_application_links`` had a ``uni_application_id`` column and two
functions to fill it in — ``attach_uni_application`` and
``attach_uni_student`` — and the only things that ever called them were a
CLI menu entry and a GUI button. So making an offer through
``record_decision`` created no ``admission_applications`` row, and an
applicant who came through UCAS was invisible to every report, dashboard
and conversion step that reads that table.

This module closes that. Making an offer is the moment the university has
an application it is actually processing, so that is when the row opens.
A rejection opens nothing — there is no application to track — and neither
does a withdrawal.

It reuses the CRM's own ``ProspectManager`` / ``ApplicationManager``
rather than inserting rows by hand, so a UCAS applicant is the same kind
of record as one that arrived any other way, and reuses the sixth-form
handover's ``external_reference`` convention (the UCAS personal id) so
that when the learner is *later* handed over at the end of Year 13,
``sixthform_intake`` finds this application instead of staging a second
one for the same person.
"""

from __future__ import annotations

import logging

from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    transaction,
)

logger = logging.getLogger(__name__)

__all__ = ["ensure_application_for_link", "find_application_by_reference"]

#: What an application opened from a UCAS offer starts as. The CRM's own
#: default is 'submitted'; an offer is further along than that.
_OFFER_STATUS = "offer_made"


def find_application_by_reference(reference: str) -> int | None:
    """The application already staged under a UCAS personal id, if any.

    The same reference the sixth-form handover writes, so the two routes
    into this university converge on one application per learner instead
    of racing to create two.
    """
    ref = (reference or "").strip()
    if not ref:
        return None
    conn = get_connection()
    try:
        row = conn.execute(
            """SELECT application_id FROM admission_applications
                WHERE external_reference = ?
                ORDER BY application_id DESC LIMIT 1""",
            (ref,),
        ).fetchone()
        return int(row["application_id"]) if row else None
    except Exception:
        # The lifecycle columns are added by a migration the CRM owns; a
        # database that has not had it yet simply has no application to
        # find, which is the same answer.
        logger.debug("Could not search applications by reference",
                     exc_info=True)
        return None
    finally:
        conn.close()


def _applicant_context(choice) -> dict:
    """Name, contact and course for the person behind a UCAS choice.

    Read through this module's own sixth-form adapter rather than the sf
    tables, so the one place that knows how to join a choice to a student
    stays the one place that does it.
    """
    from education_system.systems.university.domains.admissions.domain.ucas import (
        ucas as _ucas,
    )
    full = _ucas.get_full_application(choice.application_id)
    if full is None:
        return {}
    name = (full.student_name or "").strip()
    first, _, last = name.partition(" ")
    return {
        "first_name": first or name,
        "last_name": last.strip() or "",
        "email": full.student_email or "",
        "date_of_birth": full.student_dob or "",
        "ucas_id": full.ucas_id or "",
        "course_name": choice.course_name or "",
        "course_code": choice.course_code or "",
        "entry_year": str(choice.entry_year or full.cycle_year or ""),
    }


def ensure_application_for_link(link, *, choice, decided_by: str | None = None):
    """Attach an ``admission_applications`` row to *link*, creating one if
    this university has not already got one for the applicant.

    Idempotent on three levels, because a decision can legitimately be
    recorded more than once (a conditional offer revised, then confirmed
    on results day): an already-attached link is returned untouched, an
    application already staged under the same UCAS id is adopted rather
    than duplicated, and only a genuinely new applicant causes an insert.

    Returns the ``application_id``, or ``None`` if one could not be
    opened — the caller treats that as best-effort.
    """
    from education_system.systems.university.domains.admissions.domain.ucas import (
        ucas_links as _links,
    )

    if link.uni_application_id:
        return int(link.uni_application_id)

    context = _applicant_context(choice)
    reference = (context.get("ucas_id")
                 or link.sf_student_id
                 or f"sf-choice-{link.sf_choice_id}")

    application_id = find_application_by_reference(reference)
    created = False
    if application_id is None:
        application_id = _create(context, reference)
        created = application_id is not None
    if application_id is None:
        return None

    _links.attach_uni_application(link.link_id, application_id)
    logger.info(
        "UCAS choice #%d %s admissions application #%d (reference %s, by %s)",
        link.sf_choice_id, "opened" if created else "adopted",
        application_id, reference, decided_by or "—")
    return application_id


def _create(context: dict, reference: str) -> int | None:
    """Stage a prospect and an application for a UCAS applicant."""
    from education_system.systems.university.infrastructure.database.schemas.admissions_schemas import (
        init_admissions_crm_system_db,
    )
    from education_system.systems.university.domains.admissions.domain.services.admissions_crm_core import (
        ApplicationManager,
        ProspectManager,
    )

    init_admissions_crm_system_db()
    prospect_id = ProspectManager.create_prospect(
        first_name=context.get("first_name", ""),
        last_name=context.get("last_name", ""),
        email=context.get("email", ""),
        date_of_birth=context.get("date_of_birth", ""),
        intended_major=(context.get("course_name")
                        or context.get("course_code") or ""),
        source="ucas",
    )
    application_id = ApplicationManager.submit_application(
        prospect_id=prospect_id,
        application_type="undergraduate",
        program_applied=(context.get("course_name")
                         or context.get("course_code") or ""),
        academic_year=context.get("entry_year", ""),
        # UCAS undergraduate entry is the autumn intake; the column is
        # NOT NULL, so it needs an answer rather than a blank.
        semester="Autumn",
    )
    with transaction() as conn:
        conn.execute(
            """UPDATE admission_applications
                  SET external_reference = ?, status = ?
                WHERE application_id = ?""",
            (reference, _OFFER_STATUS, application_id),
        )
    return int(application_id)
