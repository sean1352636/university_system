"""Clear a UCAS applicant down once they have become a student here.

An applicant appears in "Admit from UCAS" because the sixth form holds a
``ucas_choices`` row naming this university. Nothing used to remove that row
when the applicant was actually admitted, so a learner who had already
enrolled kept showing up in the picker for ever — listed as *Enrolled*, and
refused by Admit with "already enrolled as …", which is a dead end: the screen
reports a problem it gives you no way to clear.

Admitting somebody is the event that ends their application to us. This module
performs that ending:

* the university's own link row (:mod:`.ucas_links`) records the student id we
  created and is archived — that is our audit trail, and it stays;
* the sixth form's ``ucas_choices`` row for **this** university is deleted
  through the sixth form's own API, because the choice is what puts them in
  the picker;
* the parent ``ucas_applications`` row is deleted only when that was their
  last choice. Choices at *other* universities are not ours to remove, and
  deleting the application would take them with it.

Deliberately untouched: ``ucas_workflow_stages`` (the college's own checklist
for the whole cycle, not a per-university record), and our
``ucas_decisions`` / ``ucas_offer_terms`` rows, which record what this
university decided and when.

Every step is best-effort and reported rather than raised: the student has
already been created by the time this runs, and a tidy-up failure must not
make a successful admission look like a failed one.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _sf_ucas():
    from education_system.systems.sixth_form.domain.progression.university import (
        ucas as _ucas,
    )
    return _ucas


def choices_for_applicant(sf_student_id: str, *,
                          university_name: Optional[str] = None) -> list[dict]:
    """This university's UCAS choices for *sf_student_id*.

    Returns ``[{choice_id, application_id, university, course_code}, …]`` —
    empty when the applicant has none, which is the normal state for someone
    who arrived by a route other than UCAS.
    """
    try:
        from education_system.systems.university.domains.admissions.domain.ucas import (
            ucas,
        )
        rows = ucas.list_applicants(university_name=university_name)
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
        })
    return out


def clear_after_admission(sf_student_id: str,
                          uni_student_id: Optional[str] = None, *,
                          actor: Optional[str] = None,
                          university_name: Optional[str] = None,
                          delete_choices: bool = True) -> dict[str, Any]:
    """End this applicant's UCAS application to us, now that they are here.

    Pass ``delete_choices=False`` to archive the link and report what *would*
    be removed without touching the sixth form's data.

    Returns a summary::

        {"choices": [...], "choices_removed": n, "application_removed": id|None,
         "links_archived": [link_id, ...], "errors": [str, ...]}
    """
    summary: dict[str, Any] = {
        "student_id": sf_student_id,
        "uni_student_id": uni_student_id,
        "choices": [],
        "choices_removed": 0,
        "application_removed": None,
        "links_archived": [],
        "errors": [],
    }
    if not sf_student_id:
        return summary

    choices = choices_for_applicant(sf_student_id,
                                    university_name=university_name)
    summary["choices"] = choices
    if not choices:
        return summary

    if not delete_choices:
        # Report only. Archiving the link is part of clearing down, not part
        # of describing it — a dry run that quietly changed our link status
        # would not be a dry run.
        return summary

    _archive_links(choices, uni_student_id, summary)

    sf = None
    try:
        sf = _sf_ucas()
    except Exception as exc:
        summary["errors"].append(f"sixth-form UCAS API unavailable: {exc}")
        return summary

    application_ids = set()
    for choice in choices:
        choice_id = choice.get("choice_id")
        if not choice_id:
            continue
        try:
            if sf.delete_choice(int(choice_id)):
                summary["choices_removed"] += 1
                if choice.get("application_id"):
                    application_ids.add(int(choice["application_id"]))
                logger.info(
                    "Removed UCAS choice #%s for %s after admission as %s "
                    "(by %s)", choice_id, sf_student_id, uni_student_id,
                    actor or "unknown")
        except Exception as exc:
            summary["errors"].append(f"choice {choice_id}: {exc}")
            logger.exception("Could not remove UCAS choice #%s", choice_id)

    # Only when nothing is left: other universities' choices are not ours.
    for application_id in application_ids:
        try:
            remaining = sf.list_choices(application_id)
        except Exception as exc:
            summary["errors"].append(f"application {application_id}: {exc}")
            continue
        if remaining:
            continue
        try:
            if sf.delete_application(application_id):
                summary["application_removed"] = application_id
                logger.info(
                    "Removed empty UCAS application #%s for %s after "
                    "admission", application_id, sf_student_id)
        except Exception as exc:
            summary["errors"].append(f"application {application_id}: {exc}")
            logger.exception("Could not remove UCAS application #%s",
                             application_id)

    return summary


def _archive_links(choices: list[dict], uni_student_id: Optional[str],
                   summary: dict[str, Any]) -> None:
    """Stamp our link rows with the student created, then archive them."""
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
    """A one-line, human-readable account of what was cleared."""
    if not summary.get("choices"):
        return "No UCAS application to clear."
    parts = []
    if summary.get("choices_removed"):
        parts.append(f"{summary['choices_removed']} UCAS choice(s) removed")
    if summary.get("application_removed"):
        parts.append(
            f"UCAS application #{summary['application_removed']} removed "
            "(no choices left)")
    if summary.get("links_archived"):
        parts.append(f"{len(summary['links_archived'])} admissions link(s) archived")
    if summary.get("errors"):
        parts.append(f"{len(summary['errors'])} problem(s): "
                     + "; ".join(summary["errors"][:2]))
    return ", ".join(parts) or "Nothing to clear."
