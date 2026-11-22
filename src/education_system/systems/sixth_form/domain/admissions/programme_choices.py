"""Programme choices: every qualification an applicant wants to study.

Split out of :mod:`admissions` (file-size limit); ``admissions`` re-exports
every public name here, so ``admissions.set_programme_choices`` etc. keep
working. Any mix is allowed — A levels, a fourth A level, BTEC, T Level,
EPQ, Core Maths, GCSE resits. ``subject_1..3`` on the applicant mirror the
first three A-level-type choices.
"""

from __future__ import annotations

import logging
from typing import Any

from education_system.systems.sixth_form.domain.admissions.admissions import (
    ProgrammeChoice,
    ValidationError,
    _connect,
    _log_event,
    _validate_subject,
    get_applicant,
    init_db,
)

logger = logging.getLogger(__name__)


# ── Programme choices (any qualification mix) ──────────────────────

#: Qualification types that last one academic year when planning aims.
ONE_YEAR_TYPES: frozenset[str] = frozenset(
    {"GCSE", "Functional Skills", "AS Level", "EPQ"})


def _grade_scales():
    from education_system.systems.sixth_form.domain.academics.qualifications import (
        grade_scales,
    )
    return grade_scales


def programme_types() -> tuple[str, ...]:
    """Qualification types an applicant can choose (the grade-scale list)."""
    try:
        return tuple(_grade_scales().QUALIFICATION_TYPES)
    except Exception:
        return ("A Level",)


def _a_level_types() -> tuple[str, ...]:
    try:
        return tuple(_grade_scales().A_LEVEL_TYPES)
    except Exception:
        return ("A Level", "AS Level")


def _normalise_choice(choice: Any, order: int) -> tuple[str, str, str | None]:
    """(qualification_type, subject, notes) from a dict or tuple."""
    if isinstance(choice, dict):
        qtype = choice.get("qualification_type") or "A Level"
        subject = choice.get("subject")
        notes = choice.get("notes")
    elif isinstance(choice, (tuple, list)) and len(choice) >= 2:
        qtype, subject = choice[0], choice[1]
        notes = choice[2] if len(choice) > 2 else None
    else:
        raise ValidationError(f"Choice {order + 1}: expected type + subject")
    qtype = str(qtype or "").strip()
    try:
        canon = _grade_scales().canonical_type(qtype)
    except Exception:
        canon = qtype or None
    if not canon:
        raise ValidationError(
            f"Choice {order + 1}: qualification type must be one of: "
            + ", ".join(programme_types()))
    subj = str(subject or "").strip()
    if not subj:
        raise ValidationError(f"Choice {order + 1}: subject is required")
    if len(subj) > 120:
        raise ValidationError(f"Choice {order + 1}: subject is too long")
    if canon in _a_level_types():
        _validate_subject(subj, f"Choice {order + 1}")
    return canon, subj, (str(notes).strip() or None) if notes else None


def set_programme_choices(applicant_id: str,
                          choices: list[Any]) -> list[ProgrammeChoice]:
    """Replace the applicant's programme choices.

    ``choices`` is a list of ``{"qualification_type", "subject"}`` dicts
    (or ``(type, subject)`` tuples), best first. The subject_1..3 slots
    are rewritten from the first three A-level-type choices.
    """
    init_db()
    if get_applicant(applicant_id) is None:
        raise ValidationError(f"No applicant {applicant_id!r}")
    if len(choices) > 8:
        raise ValidationError("At most 8 programme choices")
    rows: list[tuple[str, str, str | None]] = []
    seen: set[tuple[str, str]] = set()
    for i, c in enumerate(choices):
        q, s, n = _normalise_choice(c, i)
        if (q, s.lower()) in seen:
            raise ValidationError(f"{q} {s} is chosen twice")
        seen.add((q, s.lower()))
        rows.append((q, s, n))
    alevels = [s for q, s, _ in rows if q in _a_level_types()]
    slots = (alevels + [None, None, None])[:3]
    with _connect() as conn:
        conn.execute("DELETE FROM admissions_programme_choices "
                     "WHERE applicant_id = ?", (applicant_id,))
        for order, (q, s, n) in enumerate(rows):
            conn.execute(
                "INSERT INTO admissions_programme_choices "
                "(applicant_id, qualification_type, subject, sort_order, notes)"
                " VALUES (?, ?, ?, ?, ?)", (applicant_id, q, s, order, n))
        conn.execute(
            "UPDATE admissions_applicants SET subject_1 = ?, subject_2 = ?, "
            "subject_3 = ?, updated_at = datetime('now') "
            "WHERE applicant_id = ?", (*slots, applicant_id))
        _log_event(conn, applicant_id,
                   "Programme choices: " + (", ".join(
                       f"{q} {s}" for q, s, _ in rows) or "(none)"),
                   kind="update")
        conn.commit()
    return list_programme_choices(applicant_id)


def _stored_choices(applicant_id: str) -> list[ProgrammeChoice]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM admissions_programme_choices WHERE applicant_id = ?"
            " ORDER BY sort_order, id", (applicant_id,)).fetchall()
    return [ProgrammeChoice(id=r["id"], applicant_id=r["applicant_id"],
                            qualification_type=r["qualification_type"],
                            subject=r["subject"], sort_order=r["sort_order"],
                            notes=r["notes"]) for r in rows]


def list_programme_choices(applicant_id: str) -> list[ProgrammeChoice]:
    """Stored choices, or the subject slots read as A levels if none."""
    init_db()
    stored = _stored_choices(applicant_id)
    if stored:
        return stored
    a = get_applicant(applicant_id)
    if a is None:
        return []
    return [ProgrammeChoice(id=None, applicant_id=applicant_id,
                            qualification_type="A Level", subject=s,
                            sort_order=i)
            for i, s in enumerate(a.subjects)]


def add_programme_choice(applicant_id: str, qualification_type: str,
                         subject: str) -> list[ProgrammeChoice]:
    current = [{"qualification_type": c.qualification_type,
                "subject": c.subject, "notes": c.notes}
               for c in list_programme_choices(applicant_id)]
    current.append({"qualification_type": qualification_type,
                    "subject": subject})
    return set_programme_choices(applicant_id, current)


def remove_programme_choice(applicant_id: str, qualification_type: str,
                            subject: str) -> list[ProgrammeChoice]:
    current = [{"qualification_type": c.qualification_type,
                "subject": c.subject, "notes": c.notes}
               for c in list_programme_choices(applicant_id)
               if not (c.qualification_type == qualification_type
                       and c.subject == subject)]
    return set_programme_choices(applicant_id, current)


def _reconcile_choices_with_slots(applicant_id: str,
                                  slots: list[str | None]) -> None:
    """Keep stored choices in step after the subject slots were edited
    on the applicant form: A-level-type choices follow the slots, other
    qualifications are kept."""
    stored = _stored_choices(applicant_id)
    if not stored:
        return
    alevel = _a_level_types()
    kept_types = {c.subject: c.qualification_type for c in stored
                  if c.qualification_type in alevel}
    new = [{"qualification_type": kept_types.get(s, "A Level"), "subject": s}
           for s in slots if s]
    new += [{"qualification_type": c.qualification_type,
             "subject": c.subject, "notes": c.notes}
            for c in stored if c.qualification_type not in alevel]
    try:
        set_programme_choices(applicant_id, new)
    except ValidationError:
        logger.exception("Could not reconcile programme choices for %s",
                         applicant_id)
