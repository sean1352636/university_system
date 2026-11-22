"""What a destination record connects to elsewhere in the platform.

Destinations started as a silo: nothing outside its own package read
``dest_records``, so a confirmed destination was a note in a table and
nothing more — even though the learner's UCAS firm choice already held
the same facts, and the platform has machinery for moving a learner from
one system to the next.

This module is the seam. Five links, all one-directional (destinations
reads or notifies; nothing here is required for destinations to work):

1. :func:`ucas_prefill` — build a record from the UCAS firm choice
2. :func:`record_journey_transition` — tell the platform a learner left
3. :func:`next_step` — the receiving system's own intake, per type
4. :func:`careers_followups` — who needs a careers conversation
5. :func:`headline` — the KS5 measure, for dashboards outside this window

Every function is lazily imported and best-effort, the same shape
``destination_courses`` uses: a sixth form running without the
university, or without the cross-system tables, gets ``None`` / an empty
list and carries on. A destination record must never fail to save
because something downstream is unavailable.
"""

from __future__ import annotations

import datetime as _dt
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = [
    "FollowUp",
    "HandoverOutcome",
    "NextStep",
    "careers_followups",
    "headline",
    "next_step",
    "perform_handover",
    "record_journey_transition",
    "ucas_prefill",
]


# ── 1. UCAS firm choice → a destination record ───────────────────

def ucas_prefill(student_id: str) -> dict | None:
    """A destination payload built from the learner's UCAS firm choice.

    Returns ``None`` when there is no application, or no firm choice on
    it — there is nothing to capture until the learner has replied.

    Only what UCAS actually knows is filled in. ``study_level`` is left
    blank on purpose: a UCAS choice does not record a level, and
    guessing "Level 6" would be wrong for every foundation year and
    integrated master's in the list.
    """
    try:
        from education_system.systems.sixth_form.domain.progression.university import ucas
        from education_system.systems.sixth_form.domain.progression.university_handover import (
            FIRM_DECISION,
        )
    except Exception:
        logger.debug("UCAS module unavailable", exc_info=True)
        return None

    try:
        application = ucas.get_application_for_student(student_id)
        if application is None:
            return None
        firm = next((c for c in ucas.list_choices(application.application_id)
                     if c.final_decision == FIRM_DECISION), None)
    except Exception:
        logger.exception("Could not read the UCAS application for %s", student_id)
        return None

    if firm is None:
        return None

    return {
        "student_id":       student_id,
        "destination_type": "Higher Education",
        "institution":      (firm.university or "").strip(),
        "course":           (firm.course_name or "").strip(),
        "confirmed_via":    "UCAS Track",
        "confirmed_date":   _dt.date.today().isoformat(),
        # Carried for the caller's benefit, not stored: dest_records has
        # no course-code column, but the handover matches on it.
        "_course_code":     (firm.course_code or "").strip(),
        "_entry_year":      firm.entry_year,
    }


# ── 2. Destination → the platform-wide learner journey ───────────

#: Destination type → the system (or non-phase label) a learner moves to.
#: ``start_transition`` accepts destinations that are not phases, which is
#: what makes employment and NEET recordable at all.
_TRANSITION_TARGET: dict[str, str] = {
    "Higher Education":  "university",
    "Further Education": "fe_college",
    "Apprenticeship":    "apprenticeships",
    "Employment":        "employment",
    "Training":          "training",
    "Gap Year":          "gap_year",
}


_SOURCE_SYSTEM = "sixth_form"


def _iso_date(value) -> str | None:
    """``value`` as an ISO date, or ``None`` if it is not one."""
    try:
        return _dt.date.fromisoformat(str(value)[:10]).isoformat() if value else None
    except ValueError:
        return None


def _record_checkpoint(journey_id: str, record, *, recorded_by: int | None,
                       db_path: str | None) -> None:
    """Mirror one destination checkpoint into the platform's
    ``learner_destination`` table. Best-effort."""
    try:
        from education_system.platform.cross_system import destinations
        destinations.record_destination(
            journey_id, destination=record.destination_type,
            checkpoint=record.checkpoint, source_system=_SOURCE_SYSTEM,
            detail=record.display_target() or None,
            recorded_by=str(recorded_by) if recorded_by is not None else None,
            recorded_on=_iso_date(getattr(record, "confirmed_date", None)),
            db_path=db_path)
    except Exception:
        logger.exception("Destination checkpoint for %s was not mirrored to "
                         "the platform", getattr(record, "student_id", "?"))


def already_arrived(journey_id: str, destination_system: str, *,
                    db_path: str | None = None) -> dict | None:
    """Has the learner already moved on to ``destination_system``?

    True when the journey holds an open enrolment there, or a completed
    transition from the sixth form to it. ``route_support.start`` only reuses
    an *open* transition, so without this a destination recorded after the
    move (the leaving survey, a +6 correction) re-activated the sixth-form
    enrolment and opened a second "expected" transition to a university the
    student was already at — how a duplicate university record was made in
    2026. Returns ``{"transition_id", "reason"}`` or ``None``.
    """
    from education_system.platform.cross_system import enrolments, transitions
    done = next((t for t in reversed(transitions.list_transitions(journey_id, db_path=db_path))
                 if t.get("source_system") == _SOURCE_SYSTEM
                 and t.get("destination_system") == destination_system
                 and t.get("status") == "completed"), None)
    if done is not None:
        return {"transition_id": done["transition_id"],
                "reason": f"the move to {destination_system} is already complete"}
    open_there = enrolments.list_enrolments(journey_id, system=destination_system,
                                            include_closed=False, db_path=db_path)
    if open_there:
        return {"transition_id": None,
                "reason": f"already enrolled at {destination_system} "
                          f"({open_there[-1].get('local_student_id') or 'record'})"}
    return None


def record_journey_transition(record, *, actor_user_id: int | None = None,
                              db_path: str | None = None) -> str | None:
    """Note a confirmed destination on the learner's platform journey.

    * ``LEAVING`` into employment, training or a gap year opens the
      transition and completes it at once. Nothing on this platform admits
      a learner into a job, so it used to sit at ``expected`` for ever.
      ``transitions.complete_non_phase`` closes the platform's sixth-form
      enrolment and records the leaving destination.
    * ``LEAVING`` into university, FE or an apprenticeship opens the
      transition, and the handover action carries it through the receiving
      system's adapter. The leaving checkpoint is mirrored too.
    * The +6 and +12 follow-ups describe the same move, so they never open
      a transition — one departure must not look like three. They are
      mirrored as destination checkpoints, as is a leaving destination with
      no transition (NEET, Unknown).

    Returns the transition id, or ``None`` when no transition applies or
    nothing could be recorded. Never raises: journey bookkeeping must not
    stop a destination being saved.
    """
    try:
        from education_system.platform.cross_system import (
            progression,
            route_support,
            transitions,
        )
        from education_system.systems.sixth_form.domain.learners.students import students
    except Exception:
        logger.debug("Cross-system modules unavailable", exc_info=True)
        return None

    try:
        student = students.get_student(record.student_id)
        if student is None or not getattr(student, "date_of_birth", None):
            # A journey is matched on name and date of birth; without one it
            # would mint a duplicate person rather than find this one.
            logger.info("No journey for %s — missing student or date of birth",
                        record.student_id)
            return None
        journey_id = route_support.journey_for(
            {"first_name": student.first_name, "last_name": student.last_name,
             "date_of_birth": student.date_of_birth},
            system=_SOURCE_SYSTEM, student_id=student.student_id, db_path=db_path)
    except Exception:
        logger.exception("Could not place %s on a learner journey",
                         getattr(record, "student_id", "?"))
        return None

    checkpoint = getattr(record, "checkpoint", None)
    target = (_TRANSITION_TARGET.get(getattr(record, "destination_type", ""))
              if checkpoint == "LEAVING" else None)
    non_phase = target is not None and progression.is_non_phase_destination(target)
    if not non_phase:
        _record_checkpoint(journey_id, record, recorded_by=actor_user_id,
                           db_path=db_path)
    if target is None:
        return None

    if non_phase:
        # A leaving destination already completed on this boundary is the
        # same departure; re-saving the record (a corrected employer, say)
        # updates its checkpoint instead of recording the learner leaving
        # twice.
        done = next((t for t in reversed(transitions.list_transitions(
            journey_id, db_path=db_path))
            if t.get("source_system") == _SOURCE_SYSTEM
            and t.get("destination_system") == target
            and t.get("status") == "completed"), None)
        if done is not None:
            _record_checkpoint(journey_id, record, recorded_by=actor_user_id,
                               db_path=db_path)
            return done["transition_id"]

    if not non_phase:
        # A destination recorded after the learner has already arrived is
        # history, not a new move: keep the checkpoint (recorded above), open
        # nothing, and leave the sixth-form enrolment closed.
        try:
            arrived = already_arrived(journey_id, target, db_path=db_path)
        except Exception:
            logger.exception("Could not check whether %s has already moved on",
                             getattr(record, "student_id", "?"))
            return None
        if arrived is not None:
            logger.info("Destination for %s recorded without a new transition: %s",
                        record.student_id, arrived["reason"])
            return arrived["transition_id"]

    try:
        # Reuses an open transition on this boundary, so re-saving the
        # record, or one opened before this completed them, is not a second.
        opened, _created = route_support.start(
            journey_id, source_system=_SOURCE_SYSTEM, destination_system=target,
            student_id=student.student_id,
            reason=f"KS5 destination: {record.destination_type}"
                   f" — {record.display_target()}",
            actor_user_id=actor_user_id, db_path=db_path)
        if non_phase and opened["status"] not in route_support.TERMINAL:
            opened = transitions.complete_non_phase(
                opened["transition_id"], detail=record.display_target() or None,
                actor_user_id=actor_user_id,
                effective_date=_iso_date(getattr(record, "confirmed_date", None)),
                db_path=db_path)
    except Exception:
        logger.exception("Could not record a journey transition for %s",
                         getattr(record, "student_id", "?"))
        return None

    logger.info("Destination for %s recorded on transition %s -> %s (%s)",
                record.student_id, opened["transition_id"], target,
                opened["status"])
    return opened["transition_id"]


# ── 3. Destination type → the receiving system's intake ──────────

@dataclass(frozen=True)
class NextStep:
    """A follow-on action a confirmed destination makes available."""

    label: str
    detail: str
    kind: str          # "university" | "fe_college" | "apprenticeships"


def next_step(record) -> NextStep | None:
    """The handover this destination invites, if any.

    Returns ``None`` for destinations with no receiving system here —
    an employer, a gap year, NEET. Those are real answers, not gaps.
    """
    dtype = getattr(record, "destination_type", "")
    if dtype == "Higher Education":
        try:
            from education_system.systems.sixth_form.domain.progression import (
                destination_courses,
            )
            home = destination_courses.home_institution_name()
        except Exception:
            home = None
        inst = (getattr(record, "institution", "") or "").strip()
        if home and inst and inst.casefold() == home.casefold():
            return NextStep(
                label="Start university handover…",
                detail=f"{inst} is this platform's university — the learner's "
                       "record can be handed over directly.",
                kind="university")
        return NextStep(
            label="Record university application…",
            detail="Held as an external destination: this platform does not "
                   f"run {inst or 'that institution'}.",
            kind="external")
    if dtype == "Further Education":
        return NextStep(
            label="Refer to FE College…",
            detail="Creates the FE applicant record and the transition.",
            kind="fe_college")
    if dtype == "Apprenticeship":
        return NextStep(
            label="Open apprenticeship application…",
            detail="Hands the learner to the apprenticeships system.",
            kind="apprenticeships")
    return None


@dataclass(frozen=True)
class HandoverOutcome:
    """What a handover attempt did, or why it could not run."""

    ok: bool
    summary: str
    reference: str | None = None
    missing: tuple[str, ...] = ()
    included: tuple[str, ...] = ()

    @property
    def detail(self) -> str:
        """A human-readable account, for a dialog."""
        bits = [self.summary]
        if self.included:
            bits.append("Sending: " + ", ".join(self.included))
        if self.missing:
            bits.append("Missing: " + ", ".join(self.missing))
        return "\n\n".join(bits)


#: The fields ``university_applications.preview`` accepts, mapped from the
#: keys ``university_handover.build_record`` produces. ``reference`` is the
#: one that changes name on the way across.
_UNI_FIELDS = (
    "ucas_application", "choices", "handover_consent", "personal_statement",
    "predicted_qualifications", "achieved_qualifications",
    "offer_conditions", "confirmed_destination",
)


def _uni_fields(student) -> dict:
    from education_system.systems.sixth_form.domain.progression import (
        university_handover,
    )
    record = university_handover.build_record(student)
    fields = {k: v for k, v in record.items() if k in _UNI_FIELDS}
    if record.get("reference"):
        fields["academic_reference"] = record["reference"]
    # The recorded consent doubles as the answer to "may we release the
    # sensitive fields" — releasing them with no consent on file would be
    # the one mistake this whole boundary exists to prevent.
    fields["consent"] = bool(record.get("handover_consent"))
    return fields


def perform_handover(record, *, actor_user_id: int | None = None,
                     dry_run: bool = False,
                     db_path: str | None = None) -> HandoverOutcome:
    """Hand the learner over to the receiving system.

    ``dry_run`` previews: it assembles and consent-filters the payload,
    reports what would be sent and what is missing, and writes nothing.
    The GUI previews first and submits only on confirmation, because a
    submission creates a real applicant in another system.

    Both paths are idempotent at the far end — an open transition for the
    same learner and destination is returned rather than duplicated.
    """
    step = next_step(record)
    if step is None or step.kind == "external":
        return HandoverOutcome(
            False,
            f"{getattr(record, 'destination_type', 'This destination')} has no "
            "receiving system on this platform.")

    try:
        from education_system.systems.sixth_form.domain.learners.students import students
        student = students.get_student(record.student_id)
    except Exception:
        student = None
    if student is None:
        return HandoverOutcome(False, f"No sixth-form learner {record.student_id}.")

    # Handing over a learner who has already arrived would create a second
    # applicant (and so a duplicate student) in the receiving system.
    # Read-only lookup: a preview (dry_run) must not create a journey.
    try:
        from education_system.platform.cross_system import person
        found = person.get_by_student(_SOURCE_SYSTEM, student.student_id, db_path=db_path)
        journey_id = getattr(found, "journey_id", None) if found else None
        arrived = already_arrived(journey_id, step.kind, db_path=db_path) if journey_id else None
    except Exception:
        logger.debug("Arrival check failed for %s", record.student_id, exc_info=True)
        arrived = None
    if arrived is not None:
        return HandoverOutcome(False, f"{record.student_id} has already moved on: "
                                      f"{arrived['reason']}. Nothing was sent.")

    if step.kind == "university":
        try:
            from education_system.platform.cross_system import university_applications as ua
            fields = _uni_fields(student)
            # preview() takes these three as required keyword arguments, so a
            # learner with no UCAS application would raise TypeError about a
            # missing kwarg — true, but useless to whoever pressed the button.
            # Name what is actually absent instead.
            absent = [k for k in ("ucas_application", "choices", "handover_consent")
                      if not fields.get(k)]
            if absent:
                return HandoverOutcome(
                    False,
                    f"{record.student_id} cannot be handed to the university yet: "
                    "the UCAS application, its choices and a recorded handover "
                    "consent all have to be in place first.",
                    missing=tuple(absent))
            prev = ua.preview("sixth_form", record.student_id, **fields)
            if not prev.ready:
                return HandoverOutcome(
                    False, "The university handover is not complete yet.",
                    missing=tuple(prev.missing_required),
                    included=tuple(prev.included))
            if dry_run:
                return HandoverOutcome(
                    True, f"Ready to hand {record.student_id} to the university.",
                    included=tuple(prev.included))
            out = ua.submit("sixth_form", record.student_id,
                            actor_user_id=actor_user_id, db_path=db_path,
                            **fields)
        except Exception as exc:
            logger.exception("University handover failed for %s", record.student_id)
            return HandoverOutcome(False, f"Handover failed: {exc}")
        return HandoverOutcome(
            True,
            f"{record.student_id} handed over to the university.",
            reference=str(out.get("university_application_id")
                          or out.get("transition_id") or ""))

    if step.kind == "apprenticeships":
        programme = (getattr(record, "course", "") or getattr(record, "role", "")
                     or "").strip()
        if not programme:
            return HandoverOutcome(
                False,
                "An apprenticeship handover needs the standard or role.",
                missing=("intended_programme",))
        try:
            from education_system.platform.cross_system import (
                apprenticeship_applications as aa,
            )
            fields = {
                "intended_programme": programme,
                # Destinations does not hold eligibility evidence; the
                # preview reports it as missing rather than this module
                # inventing something to satisfy the boundary.
                "eligibility_evidence": None,
                "employer_details": ({"name": record.employer}
                                     if getattr(record, "employer", None) else None),
                "consent": False,
            }
            prev = aa.preview("sixth_form", record.student_id, **fields)
            if not prev.ready:
                return HandoverOutcome(
                    False,
                    "The apprenticeship handover is not complete yet — finish it "
                    "in the apprenticeships area, where eligibility evidence is "
                    "captured.",
                    missing=tuple(prev.missing_required),
                    included=tuple(prev.included))
            if dry_run:
                return HandoverOutcome(
                    True, f"Ready to hand {record.student_id} to apprenticeships.",
                    included=tuple(prev.included))
            out = aa.submit("sixth_form", record.student_id,
                            reason=f"KS5 destination: {record.display_target()}",
                            actor_user_id=actor_user_id, db_path=db_path, **fields)
        except Exception as exc:
            logger.exception("Apprenticeship handover failed for %s",
                             record.student_id)
            return HandoverOutcome(False, f"Handover failed: {exc}")
        return HandoverOutcome(
            True, f"{record.student_id} handed over to apprenticeships.",
            reference=str(out.get("transition_id") or ""))

    return HandoverOutcome(False, "No handover is defined for this destination.")


# ── 4. Missing / NEET → careers ──────────────────────────────────

@dataclass(frozen=True)
class FollowUp:
    """A learner who should be having a careers conversation."""

    student_id: str
    name: str
    reason: str
    has_careers_record: bool


def careers_followups(checkpoint: str = "LEAVING") -> list[FollowUp]:
    """Learners with no destination, or a NEET one, at *checkpoint*.

    This is the careers intervention list, and the two groups belong
    together: "we don't know" and "not in education or employment" are
    both a conversation waiting to happen. Whether a careers session
    already exists is flagged so the follow-up isn't duplicated.
    """
    from education_system.systems.sixth_form.domain.progression.destinations import (
        destinations as data,
    )

    try:
        missing = set(data.students_missing_at(checkpoint))
        neet = {r.student_id for r in data.list_records(checkpoint=checkpoint)
                if r.destination_type == "NEET"}
    except Exception:
        logger.exception("Could not build the careers follow-up list")
        return []

    try:
        from education_system.systems.sixth_form.domain.learners.students import students
        names = {s.student_id: s.full_name for s in students.list_students()}
    except Exception:
        names = {}

    seen_careers: set[str] = set()
    try:
        from education_system.systems.sixth_form.domain.progression.careers import careers
        for sid in missing | neet:
            if careers.sessions_for_student(sid):
                seen_careers.add(sid)
    except Exception:
        logger.debug("Careers module unavailable", exc_info=True)

    out = [
        FollowUp(student_id=sid,
                 name=names.get(sid, "(unknown)"),
                 reason="NEET" if sid in neet else "No destination recorded",
                 has_careers_record=sid in seen_careers)
        for sid in sorted(missing | neet)
    ]
    return out


# ── 5. The KS5 measure, for dashboards elsewhere ─────────────────

def headline(checkpoint: str = "LEAVING") -> dict | None:
    """The sustained-destination figures, flattened for a KPI tile.

    ``None`` if the summary cannot be produced, so a caller can render
    a dash rather than a zero — "no data" and "nobody progressed" must
    not look the same on a dashboard.
    """
    from education_system.systems.sixth_form.domain.progression.destinations import (
        destinations as data,
    )

    try:
        s = data.summary()
    except Exception:
        logger.debug("Destinations summary unavailable", exc_info=True)
        return None

    positive = {"LEAVING": s.positive_at_leaving,
                "PLUS_6": s.positive_at_plus_6,
                "PLUS_12": s.positive_at_plus_12}.get(checkpoint,
                                                     s.positive_at_leaving)
    captured = s.students_with_leaving
    cohort = captured + s.students_missing_leaving
    return {
        "checkpoint":       checkpoint,
        "total_records":    s.total_records,
        "cohort":           cohort,
        "captured":         captured,
        "missing":          s.students_missing_leaving,
        "positive":         positive,
        "positive_pct":     (positive / captured * 100) if captured else None,
        "capture_pct":      (captured / cohort * 100) if cohort else None,
    }
