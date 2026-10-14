"""Everyone applying to this university, whatever system they come from.

``ucas.list_applicants()`` shows sixth-form UCAS choices, because the
sixth form is the only system that keeps UCAS tables. It is not the only
system that sends learners here:

* **Sixth form** — a UCAS choice naming this university
* **FE College** — the same UCAS route (``FE_COLLEGE_TO_UNIVERSITY``)
* **Apprenticeships** — a completed higher apprentice progressing onto a
  degree or top-up (``APPRENTICESHIPS_TO_UNIVERSITY``), admitted on their
  standard and EPA grade rather than a UCAS id

Reading only the sixth form's UCAS tables therefore hides two of the
three routes. This module normalises all of them into one
:class:`Applicant` shape so admissions sees a single list.

Two different substrates are merged:

1. **UCAS choices** — the sixth form's own rows, the richest source, and
   the only one that carries a decision the university writes back to.
2. **Cross-system transitions** — ``learner_transition`` rows heading for
   the university, which is how FE and apprenticeships arrive, and how a
   sixth-former appears once their handover has been submitted.

A learner present in both is reported once, with the UCAS row preferred:
it holds the course and decision, and the transition only repeats what
the handover carried.

Best-effort throughout: a system that is absent or unreadable contributes
nothing rather than breaking the list.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

__all__ = ["Applicant", "list_all_applicants", "sources_seen"]

#: Where an applicant was read from, for display and for deciding what
#: actions apply to them.
ROUTE_UCAS = "UCAS"
ROUTE_TRANSITION = "Handover"

#: Sources whose application reference is a UCAS personal id. An
#: apprentice is admitted on their standard and EPA grade, so theirs is
#: not one and must not be shown or matched as one.
_UCAS_ROUTES = frozenset({"sixth_form", "fe_college"})


def _entry_year(choice: dict) -> int | None:
    try:
        return int(str(choice.get("entry_year") or "").strip())
    except (TypeError, ValueError):
        return None


@dataclass
class Applicant:
    """One person applying to this university, from any source system."""

    source_system: str
    student_id: str
    student_name: str
    route: str                      # ROUTE_UCAS | ROUTE_TRANSITION
    course_code: str | None = None
    course_name: str = ""
    entry_year: int | None = None
    decision_status: str = ""
    final_decision: str | None = None
    student_dob: str | None = None
    student_email: str = ""
    ucas_id: str | None = None
    journey_id: str | None = None
    transition_id: str | None = None
    application_id: int | None = None
    application_status: str | None = None
    #: Raw underlying row, for callers that need more than the common shape.
    raw: dict = field(default_factory=dict, repr=False)

    @property
    def source_label(self) -> str:
        return {
            "sixth_form": "Sixth Form",
            "fe_college": "FE College",
            "apprenticeships": "Apprenticeships",
        }.get(self.source_system, self.source_system or "—")

    @property
    def course_label(self) -> str:
        if self.course_code and self.course_name:
            return f"{self.course_code} — {self.course_name}"
        return self.course_name or self.course_code or "—"


def _from_ucas(university_name: str | None) -> list[Applicant]:
    """Sixth-form UCAS choices naming this university."""
    try:
        from education_system.systems.university.domains.admissions.domain.ucas import (
            ucas,
        )
        rows = ucas.list_applicants(university_name=university_name)
    except Exception:
        logger.info("UCAS applicants unavailable", exc_info=True)
        return []

    return [
        Applicant(
            source_system="sixth_form",
            student_id=a.student_id,
            student_name=a.student_name,
            route=ROUTE_UCAS,
            course_code=a.course_code,
            course_name=a.course_name,
            entry_year=a.entry_year,
            decision_status=a.decision_status,
            final_decision=a.final_decision,
            student_dob=a.student_dob,
            student_email=a.student_email,
            ucas_id=a.ucas_id,
            raw={"choice_id": a.choice_id, "application_id": a.application_id},
        )
        for a in rows
    ]


def _identities_for(rows: list[dict]) -> dict[str, tuple[str, str]]:
    """``{transition_id: (student_id, name)}`` for a whole list, one query
    per lookup rather than one connection per row.

    The transition itself often carries neither id nor name. Both are
    recoverable: the id from the *source* enrolment the transition came out
    of, the name from the journey registry — the only place that reliably
    knows a learner's legal name across systems. Doing that per row meant a
    fresh ``connect()`` for every applicant on the screen.
    """
    out: dict[str, tuple[str, str]] = {}
    ids: dict[str, str] = {}      # transition_id -> student_id
    names: dict[str, str] = {}    # journey_id    -> legal name

    unresolved = []
    for row in rows:
        tid = str(row.get("transition_id") or "")
        student_id = str(row.get("local_student_id")
                         or row.get("source_student_id") or "").strip()
        if student_id:
            ids[tid] = student_id
        name = str(row.get("student_name") or "").strip()
        if name and row.get("journey_id"):
            names[str(row["journey_id"])] = name
        if not student_id or not name:
            unresolved.append(row)

    if unresolved:
        try:
            from education_system.platform.identity.auth.db import connect
            conn = connect()
            try:
                _resolve_ids(conn, unresolved, ids)
                _resolve_names(conn, unresolved, names)
            finally:
                conn.close()
        except Exception:
            logger.debug("Could not resolve identities for %d transition(s)",
                         len(unresolved), exc_info=True)

    for row in rows:
        tid = str(row.get("transition_id") or "")
        journey_id = str(row.get("journey_id") or "")
        out[tid] = (ids.get(tid) or journey_id[:8],
                    names.get(journey_id) or "(unknown)")
    return out


def _resolve_ids(conn, rows: list[dict], ids: dict[str, str]) -> None:
    """Fill in local student ids from the source enrolments, in two queries."""
    by_enrolment = {str(r["source_enrolment_id"]): str(r["transition_id"])
                    for r in rows
                    if r.get("source_enrolment_id")
                    and not ids.get(str(r.get("transition_id")))}
    if by_enrolment:
        for chunk in _chunks(list(by_enrolment)):
            for e in conn.execute(
                f"""SELECT enrolment_id, local_student_id FROM learner_enrolment
                     WHERE enrolment_id IN ({_marks(chunk)})""",  # nosec B608
                    chunk).fetchall():
                if e["local_student_id"]:
                    ids[by_enrolment[str(e["enrolment_id"])]] = \
                        str(e["local_student_id"])

    # Anyone still without one: any enrolment of theirs in the source
    # system will do. Keyed on (journey, system) because a learner can hold
    # enrolments in more than one.
    wanted = {(str(r["journey_id"]), str(r.get("source_system") or "")):
              str(r["transition_id"])
              for r in rows
              if r.get("journey_id") and not ids.get(str(r.get("transition_id")))}
    if not wanted:
        return
    journeys = sorted({j for j, _system in wanted})
    for chunk in _chunks(journeys):
        for e in conn.execute(
            f"""SELECT journey_id, system, local_student_id
                  FROM learner_enrolment
                 WHERE journey_id IN ({_marks(chunk)})
                   AND local_student_id IS NOT NULL""",  # nosec B608
                chunk).fetchall():
            key = (str(e["journey_id"]), str(e["system"]))
            if key in wanted:
                ids.setdefault(wanted[key], str(e["local_student_id"]))


def _resolve_names(conn, rows: list[dict], names: dict[str, str]) -> None:
    """Fill in legal names from the journey registry, in one query."""
    wanted = sorted({str(r["journey_id"]) for r in rows
                     if r.get("journey_id")
                     and not names.get(str(r["journey_id"]))})
    for chunk in _chunks(wanted):
        for j in conn.execute(
            f"""SELECT journey_id, legal_first_name, legal_last_name
                  FROM student_journey
                 WHERE journey_id IN ({_marks(chunk)})""",  # nosec B608
                chunk).fetchall():
            full = " ".join(p for p in (j["legal_first_name"],
                                        j["legal_last_name"]) if p)
            if full:
                names[str(j["journey_id"])] = full


def _chunks(items: list[str], size: int = 500):
    """Below SQLITE_MAX_VARIABLE_NUMBER."""
    for start in range(0, len(items), size):
        yield items[start:start + size]


def _marks(chunk: list[str]) -> str:
    return ",".join("?" * len(chunk))


#: Handover statuses that mean the learner is no longer an applicant here.
_CLOSED_TRANSITIONS = frozenset({"completed", "cancelled"})


def _from_transitions() -> list[Applicant]:
    """Learners heading here through the cross-system handover route."""
    try:
        from education_system.platform.cross_system import university_applications as ua
        rows = ua.list_applications()
    except Exception:
        logger.info("Cross-system applications unavailable", exc_info=True)
        return []

    # A handover that has completed is not an application any more: the
    # learner arrived and has a student record here. Listing them keeps
    # somebody admitted weeks ago sitting in "Admit from UCAS" as an
    # applicant, where Admit can only refuse them. Cancelled handovers are
    # not pending either.
    rows = [r for r in rows
            if str(r.get("status") or "").lower() not in _CLOSED_TRANSITIONS]

    out: list[Applicant] = []
    identities = _identities_for(rows)
    for row in rows:
        student_id, name = identities.get(
            str(row.get("transition_id") or ""), ("", "(unknown)"))
        choices = row.get("choices") or []
        first = choices[0] if isinstance(choices, list) and choices else {}
        reference = str(row.get("application_reference") or "") or None
        out.append(Applicant(
            source_system=str(row.get("source_system") or ""),
            student_id=student_id,
            student_name=name,
            route=ROUTE_TRANSITION,
            course_code=(first or {}).get("course_code"),
            course_name=(first or {}).get("course_name") or "",
            entry_year=_entry_year(first),
            # On the two college routes the reference *is* the UCAS
            # personal id, which is what makes this row matchable against
            # the sixth form's own UCAS choice. An apprentice's reference
            # is their standard, so it is not published as a UCAS id.
            ucas_id=(reference
                     if row.get("source_system") in _UCAS_ROUTES else None),
            decision_status=str(row.get("application_status")
                                or row.get("status") or ""),
            journey_id=row.get("journey_id"),
            transition_id=row.get("transition_id"),
            application_id=row.get("university_application_id"),
            application_status=row.get("university_status"),
            raw=row,
        ))
    return out


def _without_enrolled_students(applicants: list[Applicant]) -> list[Applicant]:
    """Drop applicants whose journey already names a student here.

    Closing a handover as ``completed`` is not the only way a learner stops
    being an applicant. A sending system can open a fresh transition for a
    learner who already arrived — the sixth form's KS5 destination capture
    did exactly that for a learner transferred weeks earlier — and the
    ``completed``/``cancelled`` filter cannot see it. Listed, that learner
    offers "Admit" on somebody who is already a student, and the import can
    only fail, because their sixth-form record is gone.

    The journey registry is the authority on who is already here: its
    ``university_student_id`` names the record, and the record must still
    exist — a dangling link does not make somebody enrolled. If the check
    cannot run, the list is returned unfiltered: an outage must not hide
    genuine applicants.
    """
    journey_ids = sorted({str(a.journey_id) for a in applicants if a.journey_id})
    if not journey_ids:
        return applicants
    try:
        enrolled = _journeys_with_university_students(journey_ids)
    except Exception:
        logger.warning("Could not check which applicants are already students",
                       exc_info=True)
        return applicants
    if not enrolled:
        return applicants
    kept = [a for a in applicants if str(a.journey_id or "") not in enrolled]
    logger.info("Left %d already-enrolled learner(s) out of the applicant list",
                len(applicants) - len(kept))
    return kept


def _journeys_with_university_students(journey_ids: list[str]) -> set[str]:
    """Journey ids whose ``university_student_id`` is a student that exists."""
    from education_system.platform.identity.auth.db import connect
    from education_system.systems.university.infrastructure.database.db import (
        get_connection,
    )

    linked: dict[str, str] = {}          # university student id -> journey id
    conn = connect(None)
    try:
        for chunk in _chunks(journey_ids):
            rows = conn.execute(
                f"""SELECT journey_id, university_student_id FROM student_journey
                    WHERE journey_id IN ({_marks(chunk)})
                      AND TRIM(COALESCE(university_student_id, '')) != ''""",  # nosec B608
                chunk).fetchall()
            for row in rows:
                linked[str(row[1]).strip()] = str(row[0])
    finally:
        conn.close()
    if not linked:
        return set()

    present: set[str] = set()
    uni = get_connection()
    try:
        ids = list(linked)
        for chunk in _chunks(ids):
            rows = uni.execute(
                f"SELECT student_id FROM students WHERE student_id IN ({_marks(chunk)})",  # nosec B608
                chunk).fetchall()
            present.update(str(r[0]) for r in rows)
    finally:
        uni.close()
    return {linked[sid] for sid in present}


def list_all_applicants(*, university_name: str | None = None,
                        source_system: str | None = None) -> list[Applicant]:
    """Every applicant to this university, from every system that sends any.

    Deduplicated with the UCAS row winning, since it carries the course
    and the decision. Matched on the UCAS personal id where both sides
    hold one, falling back to ``(source_system, student_id)``: the two
    substrates resolve the local id differently — the UCAS row holds the
    college's own student id, the transition recovers one through a chain
    of fallbacks — so keying on that alone showed one learner twice.
    Sorted so the people an admissions officer can act on come first:
    those with a firm choice, then an offer, then everyone else.
    """
    merged: dict[tuple[str, str], Applicant] = {}
    by_ucas_id: dict[str, tuple[str, str]] = {}

    for applicant in _from_transitions():
        key = (applicant.source_system, applicant.student_id)
        merged[key] = applicant
        if applicant.ucas_id:
            by_ucas_id[str(applicant.ucas_id)] = key
    for applicant in _from_ucas(university_name):
        key = (by_ucas_id.get(str(applicant.ucas_id or ""))
               or (applicant.source_system, applicant.student_id))
        existing = merged.get(key)
        if existing is not None:
            # Keep the transition's admissions context on the richer row.
            applicant.journey_id = applicant.journey_id or existing.journey_id
            applicant.transition_id = existing.transition_id
            applicant.application_id = existing.application_id
            applicant.application_status = existing.application_status
        merged[key] = applicant

    out = _without_enrolled_students(list(merged.values()))
    if source_system:
        out = [a for a in out if a.source_system == source_system]

    final_rank = {"Firm": 0, "Insurance": 1}
    offer_rank = {"Unconditional Offer": 0, "Conditional Offer": 1}
    out.sort(key=lambda a: (final_rank.get(a.final_decision or "", 2),
                            offer_rank.get(a.decision_status, 2),
                            a.source_system, a.student_name or ""))
    return out


def sources_seen(applicants: list[Applicant]) -> dict[str, int]:
    """``{source_system: count}``, for a summary line."""
    counts: dict[str, int] = {}
    for a in applicants:
        counts[a.source_system] = counts.get(a.source_system, 0) + 1
    return counts
