"""Close a UCAS application once the applicant has become a student here.

An applicant appears in "Admit from UCAS" because the sixth form holds a
UCAS choice naming this university. Admitting somebody is the event that
ends their application to us, and this module records that ending — without
deleting anything:

* the university's own link row (:mod:`.ucas_links`) is stamped with the
  student id we created and archived. That is our record that the choice
  was *placed*, and it takes the applicant out of the picker immediately;
* ``university.student.enrolled`` is published on the cross-system bus,
  once per placed choice. The sixth form consumes it and marks its own
  choice *Placed* (with the university student id and date), keeping the
  choice and the application as the record of where the learner went.

This used to delete the sixth form's ``ucas_choices`` row — and its
``ucas_applications`` row when it was the last choice — through the sixth
form's own API, which erased the college's record of the outcome and was
the university writing another system's data. Both are gone.

Deliberately untouched: our ``ucas_decisions`` / ``ucas_offer_terms`` rows,
which record what this university decided and when.

Every step is best-effort and reported rather than raised: the student has
already been created by the time this runs, and a tidy-up failure must not
make a successful admission look like a failed one.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Optional

logger = logging.getLogger(__name__)

EVENT_STUDENT_ENROLLED = "university.student.enrolled"


def choices_for_applicant(sf_student_id: str, *,
                          university_name: Optional[str] = None,
                          include_placed: bool = False) -> list[dict]:
    """This university's UCAS choices for *sf_student_id*.

    Returns ``[{choice_id, application_id, university, course_code,
    course_name, entry_year, journey_id}, …]`` — empty when the applicant
    has none, which is the normal state for someone who arrived by a route
    other than UCAS. Choices already placed are left out unless asked for.
    """
    try:
        from education_system.systems.university.domains.admissions.domain.ucas import (
            ucas,
        )
        rows = ucas.list_applicants(university_name=university_name,
                                    include_placed=include_placed)
    except Exception:
        logger.info("Could not list UCAS applicants", exc_info=True)
        return []
    out = []
    for row in rows:
        if str(getattr(row, "student_id", "")) != str(sf_student_id):
            continue
        out.append({
            "choice_id": getattr(row, "choice_id", None),
            "application_id": getattr(row, "application_id", None),
            "university": getattr(row, "university", None),
            "course_code": getattr(row, "course_code", None),
            "course_name": getattr(row, "course_name", None),
            "entry_year": getattr(row, "entry_year", None),
            "journey_id": getattr(row, "journey_id", None),
        })
    return out


def clear_after_admission(sf_student_id: str,
                          uni_student_id: Optional[str] = None, *,
                          actor: Optional[str] = None,
                          university_name: Optional[str] = None,
                          delete_choices: bool = True) -> dict[str, Any]:
    """End this applicant's UCAS application to us, now that they are here.

    Name kept for its callers; nothing is deleted any more. Each of our
    open choices for the applicant is marked placed (our link archived with
    the student id) and announced with ``university.student.enrolled``.

    Pass ``delete_choices=False`` for a dry run: report what *would* be
    placed without changing anything.

    Returns a summary::

        {"choices": [...], "choices_placed": n, "links_archived": [...],
         "events_published": [event_id, ...], "errors": [str, ...],
         "choices_removed": 0, "application_removed": None}

    ``choices_removed`` / ``application_removed`` stay in the summary, always
    0 / None, for callers written against the old clear-down.
    """
    summary: dict[str, Any] = {
        "student_id": sf_student_id,
        "uni_student_id": uni_student_id,
        "choices": [],
        "choices_placed": 0,
        "choices_removed": 0,
        "application_removed": None,
        "links_archived": [],
        "events_published": [],
        "errors": [],
    }
    if not sf_student_id:
        return summary

    choices = choices_for_applicant(sf_student_id,
                                    university_name=university_name)
    summary["choices"] = choices

    if not delete_choices:
        # Report only. A dry run that quietly archived links would not be a
        # dry run.
        return summary

    student = _university_student(uni_student_id)
    journey_id = (student.get("journey_id")
                  or next((c.get("journey_id") for c in choices
                           if c.get("journey_id")), None)
                  or _journey_for(sf_student_id))

    if not choices:
        if choices_for_applicant(sf_student_id,
                                 university_name=university_name,
                                 include_placed=True):
            # Already placed and announced; nothing new to say.
            return summary
        # Not a UCAS arrival — still worth announcing once, so the sixth
        # form's destinations know where they went.
        _publish_enrolled(summary, sf_student_id=sf_student_id,
                          uni_student_id=uni_student_id, choice=None,
                          student=student, journey_id=journey_id)
        return summary

    _archive_links(choices, sf_student_id, uni_student_id, summary, actor)
    for choice in choices:
        if not choice.get("choice_id"):
            continue
        if _publish_enrolled(summary, sf_student_id=sf_student_id,
                             uni_student_id=uni_student_id, choice=choice,
                             student=student, journey_id=journey_id):
            summary["choices_placed"] += 1
            logger.info(
                "UCAS choice #%s for %s placed after admission as %s (by %s)",
                choice["choice_id"], sf_student_id, uni_student_id,
                actor or "unknown")
    return summary


def _university_student(uni_student_id: Optional[str]) -> dict[str, Any]:
    """The few fields of our student record the enrolment event carries."""
    if not uni_student_id:
        return {}
    try:
        from education_system.systems.university.infrastructure.database.db import (
            get_connection,
        )
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM students WHERE student_id = ?",
                (str(uni_student_id),)).fetchone()
        finally:
            conn.close()
    except Exception:
        logger.debug("Could not read university student %s",
                     uni_student_id, exc_info=True)
        return {}
    if row is None:
        return {}
    keys = row.keys()

    def col(name: str) -> Any:
        return row[name] if name in keys else None

    return {
        "journey_id": col("journey_id"),
        "course": col("course"),
        "start_date": col("enrollment_date"),
    }


def _journey_for(sf_student_id: str) -> Optional[str]:
    try:
        from education_system.platform.cross_system import identity_service
        anchor = identity_service.find_by_student("sixth_form", sf_student_id)
        return anchor["journey_id"] if anchor else None
    except Exception:
        return None


def _publish_enrolled(summary: dict[str, Any], *, sf_student_id: str,
                      uni_student_id: Optional[str], choice: Optional[dict],
                      student: dict[str, Any],
                      journey_id: Optional[str]) -> bool:
    """Publish one ``university.student.enrolled``. Idempotent per
    (student, choice) through the bus's idempotency key."""
    choice = choice or {}
    choice_id = choice.get("choice_id")
    try:
        from education_system.platform.integrations.external import (
            cross_system_bus as _bus,
        )
        event_id = _bus.publish_cross_system(
            EVENT_STUDENT_ENROLLED,
            source_system="university",
            source_module=__name__,
            target_system="sixth_form",
            journey_id=journey_id,
            idempotency_key=(f"{EVENT_STUDENT_ENROLLED}:{uni_student_id}:"
                             f"{choice_id if choice_id else sf_student_id}"),
            sf_student_id=sf_student_id,
            sf_choice_id=choice_id,
            university_student_id=uni_student_id,
            course_code=choice.get("course_code"),
            course_name=choice.get("course_name") or student.get("course"),
            entry_year=choice.get("entry_year"),
            start_date=student.get("start_date"),
            enrolled_on=date.today().isoformat(),
        )
    except Exception as exc:
        summary["errors"].append(
            f"enrolment event for choice {choice_id or '—'}: {exc}")
        logger.exception("Could not publish the enrolment of %s",
                         uni_student_id)
        return False
    summary["events_published"].append(event_id)
    return True


def _archive_links(choices: list[dict], sf_student_id: str,
                   uni_student_id: Optional[str], summary: dict[str, Any],
                   actor: Optional[str]) -> None:
    """Stamp our link rows with the student created, then archive them.

    A choice nobody had decided on yet has no link; one is opened here, so
    the placement is on record on our side too.
    """
    try:
        from education_system.systems.university.domains.admissions.domain.ucas import (
            ucas_links,
        )
    except Exception as exc:
        summary["errors"].append(f"link table unavailable: {exc}")
        return

    for choice in choices:
        choice_id = choice.get("choice_id")
        if not choice_id:
            continue
        try:
            link = ucas_links.get_link_by_choice(int(choice_id))
            if link is None and choice.get("application_id"):
                link = ucas_links.ensure_link_for_choice(
                    sf_application_id=int(choice["application_id"]),
                    sf_choice_id=int(choice_id),
                    sf_student_id=str(sf_student_id),
                    linked_by=actor)
        except Exception as exc:
            summary["errors"].append(f"link for choice {choice_id}: {exc}")
            continue
        if link is None:
            continue
        try:
            if uni_student_id:
                # Skipped rather than failed when the id is not a student
                # here: the link is still worth archiving.
                try:
                    ucas_links.attach_uni_student(link.link_id, uni_student_id)
                except Exception as exc:
                    summary["errors"].append(
                        f"link #{link.link_id} student: {exc}")
            ucas_links.set_link_status(link.link_id, "archived")
            summary["links_archived"].append(link.link_id)
        except Exception as exc:
            summary["errors"].append(f"link #{link.link_id}: {exc}")
            logger.exception("Could not archive UCAS link #%s", link.link_id)


def describe(summary: dict[str, Any]) -> str:
    """A one-line, human-readable account of what was recorded."""
    if not summary.get("choices"):
        if summary.get("events_published"):
            return "No UCAS choice here; the enrolment was announced."
        return "No open UCAS application to clear."
    parts = []
    if summary.get("choices_placed"):
        parts.append(f"{summary['choices_placed']} UCAS choice(s) marked "
                     "placed (the sixth form keeps the record)")
    if summary.get("links_archived"):
        parts.append(f"{len(summary['links_archived'])} admissions link(s) archived")
    if summary.get("errors"):
        parts.append(f"{len(summary['errors'])} problem(s): "
                     + "; ".join(summary["errors"][:2]))
    return ", ".join(parts) or "Nothing to clear."
