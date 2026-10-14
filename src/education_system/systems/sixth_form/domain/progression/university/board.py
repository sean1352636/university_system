"""The sixth form's side of the University Progression board.

One question, asked of every Year 13 leaver at once: *where has this
learner got to on the way out of here, and what is stopping them?*

Until now the answer was scattered. Eligibility lived in
:mod:`handover_eligibility`, the released payload in
:mod:`university_handover`, completion in a ``transferred_at`` column, and
the stranded-transfer list in a function nobody called from a screen. A
member of staff could reach all four, one student at a time, from four
different places. On results day that is not a workflow.

This module assembles them into rows and gives the two actions the flow
actually needs:

:func:`prepare`
    A **dry run**. Builds exactly the handover that would be sent and
    reports what it contains, what was withheld for want of consent and
    what is still missing — without publishing anything. This is the step
    that was impossible before: the only way to find out what a handover
    contained was to perform it.

:func:`submit`
    The real thing, which is still :func:`students.mark_transferred` and
    nothing else. Deliberately: that function already ends the enrolment,
    revokes the sixth-form membership, anchors the journey, records the
    transition, publishes to the bus under a deterministic idempotency
    key and emails the office. Reimplementing any of it here would be a
    second answer to a question that already has one.

Headless on purpose. The GUI in ``university_progression_views`` renders
these rows; a CLI or a scheduled results-day job could drive the same
functions without a display.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from education_system.systems.sixth_form.domain.progression import (
    handover_eligibility,
    university_handover,
)

logger = logging.getLogger(__name__)

# ── Row states ──────────────────────────────────────────────────────
#
# Ordered by where the learner is on the way out, not alphabetically:
# the board sorts on this, and "needs attention first" is what a member
# of staff wants on results day.

#: Marked Left, announcement never landed. The learner has gone from the
#: sixth-form workflow without reaching anywhere — the worst state on the
#: board and the reason it sorts first.
STRANDED = "Stranded"
#: A blocking eligibility failure. Not going anywhere today.
BLOCKED = "Blocked"
#: Importable, with advisory gaps the operator should see first.
ATTENTION = "Needs attention"
#: Every check passed. Submit will work.
READY = "Ready"
#: Announced successfully; the university has been told.
SUBMITTED = "Submitted"
#: The university has created a student record for them.
ENROLLED = "Enrolled"
#: Left for somewhere this platform does not run.
DEPARTED = "Left the platform"

STATE_ORDER: tuple[str, ...] = (
    STRANDED, BLOCKED, ATTENTION, READY, SUBMITTED, ENROLLED, DEPARTED,
)


@dataclass(frozen=True)
class Row:
    """One learner's line on the board."""

    student_id: str
    full_name: str
    state: str
    destination: str
    course: str
    #: Short, human phrases naming what is outstanding. Blockers first.
    outstanding: tuple[str, ...] = ()
    #: Louder than ``outstanding``: something is wrong rather than merely
    #: unfinished — a stranded transfer, a duplicate, an unreadable source.
    warnings: tuple[str, ...] = ()
    journey_id: str | None = None
    university_student_id: str | None = None
    transferred_at: str | None = None
    readiness: handover_eligibility.Readiness | None = None

    @property
    def can_submit(self) -> bool:
        """Submitting is worth offering — ready, or a retry of a stranded one."""
        return self.state in (READY, ATTENTION, STRANDED)

    @property
    def is_done(self) -> bool:
        return self.state in (SUBMITTED, ENROLLED, DEPARTED)

    @property
    def sort_key(self) -> tuple[int, str]:
        try:
            rank = STATE_ORDER.index(self.state)
        except ValueError:
            rank = len(STATE_ORDER)
        return rank, self.full_name.lower()


@dataclass(frozen=True)
class Prepared:
    """The dry-run result: what *would* be sent, without sending it."""

    student_id: str
    ok: bool
    boundary: str = ""
    included: tuple[str, ...] = ()
    withheld_no_consent: tuple[str, ...] = ()
    withheld_restricted: tuple[str, ...] = ()
    missing_required: tuple[str, ...] = ()
    destination_system: str = ""
    destination_institution: str = ""
    blockers: tuple[str, ...] = ()
    problems: tuple[str, ...] = ()

    def describe(self) -> str:
        """A readable report, for a detail pane or a terminal."""
        lines = [f"Destination : {self.destination_institution or '—'} "
                 f"({self.destination_system or 'unresolved'})",
                 f"Boundary    : {self.boundary or '—'}", ""]
        for label, values in (
            ("Included", self.included),
            ("Withheld — no consent", self.withheld_no_consent),
            ("Withheld — restricted", self.withheld_restricted),
            ("Missing (required)", self.missing_required),
        ):
            lines.append(f"{label} ({len(values)}):")
            lines.extend(f"    • {v}" for v in values)
            if not values:
                lines.append("    —")
        if self.blockers:
            lines += ["", "Blocked by:"]
            lines += [f"    ✗ {b}" for b in self.blockers]
        if self.problems:
            lines += ["", "Would be rejected at the destination:"]
            lines += [f"    ! {p}" for p in self.problems]
        return "\n".join(lines)


@dataclass(frozen=True)
class SubmitResult:
    """What one submission did."""

    student_id: str
    ok: bool
    detail: str
    state: str = ""


@dataclass
class Board:
    """Every candidate, plus the leavers who never made it."""

    rows: list[Row] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        out = {state: 0 for state in STATE_ORDER}
        for row in self.rows:
            out[row.state] = out.get(row.state, 0) + 1
        return out

    def get(self, student_id: str) -> Row | None:
        return next((r for r in self.rows if r.student_id == student_id), None)

    @property
    def submittable(self) -> list[Row]:
        return [r for r in self.rows if r.can_submit]

    @property
    def stranded(self) -> list[Row]:
        return [r for r in self.rows if r.state == STRANDED]

    def summary_line(self) -> str:
        counts = self.counts()
        parts = [f"{counts[s]} {s.lower()}" for s in STATE_ORDER
                 if counts.get(s)]
        return f"{len(self.rows)} learner(s): " + (", ".join(parts) or "none")


# ── Building the board ──────────────────────────────────────────────

def _course_of(readiness) -> str:
    return handover_eligibility.destination_course(readiness)


def _destination_of(readiness) -> str:
    destination = readiness.destination
    if destination is None:
        return ""
    if destination.is_home:
        return destination.institution or "This university"
    return destination.institution or destination.system


def _state_for(student, readiness, *, uni_student_id: str | None) -> str:
    """Where this learner has got to, most urgent reading first.

    Order matters. A learner who is *already a university student* is
    enrolled whatever their paperwork now says, and a learner marked Left
    with no completed announcement is stranded whatever their eligibility
    says — in both cases the eligibility verdict describes a decision that
    has already been overtaken.
    """
    if uni_student_id:
        return ENROLLED
    if student.transfer_complete:
        destination = readiness.destination
        if destination is not None and not destination.is_home:
            return DEPARTED
        return SUBMITTED
    if getattr(student, "status", "") == "Left":
        # Left, but no completed transfer. This is the failure mode
        # transferred_at exists to make visible.
        return STRANDED
    if readiness.blockers:
        return BLOCKED
    if readiness.warnings:
        return ATTENTION
    return READY


def _warnings_for(student, readiness, state: str) -> tuple[str, ...]:
    out: list[str] = []
    if state == STRANDED:
        out.append(
            "Marked Left but the handover never completed — they have gone "
            "from the sixth-form roll without reaching the university. "
            "Submit again to retry.")
    if state == ENROLLED and not student.transfer_complete:
        out.append(
            "Already a university student, but this sixth-form record was "
            "never closed. Submit to finish the sixth-form side.")
    if state == SUBMITTED and not readiness.passed("consent"):
        out.append(
            "Handed over without a recorded handover consent — the "
            "university will have received the routine fields only.")
    unreadable = readiness.get("not_already_here")
    if unreadable is not None and unreadable.failed_soft:
        out.append(unreadable.detail)
    return tuple(out)


def board() -> Board:
    """Assemble the whole board.

    Includes learners who are already done. A dashboard that hid them
    would answer "who is left to do?" and not "did results day work?",
    and the second question is the one somebody asks at 5pm.

    Builds its own cohort rather than calling
    :func:`handover_eligibility.candidates`, because it needs things that
    function does not return: the stranded leavers and the UCAS
    applicants (neither of whom need be an enrolled Year 13 student, so
    it cannot see them) and the prefetched journey rows (which every row
    needs again for its university slot). Re-reading the registry per
    learner is what makes a cohort screen stall, and this board exists to
    be opened on results day.

    Three sources, because "who is on the way to university?" has three
    answers and the enrolment table only holds one of them.
    """
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    try:
        cohort = _students.list_year_13_students()
    except Exception:
        logger.exception("Could not list the Year 13 cohort")
        cohort = []

    people = list(cohort)
    known = {s.student_id for s in people}
    # Stranded leavers were marked Left and then the announcement failed,
    # so they have dropped out of the enrolled cohort entirely. They are
    # precisely who this board exists for.
    for student in _incomplete_transfers():
        if student.student_id not in known:
            people.append(student)
            known.add(student.student_id)
    # Anyone with a UCAS application, whatever their enrolment says. Every
    # check on this board reads UCAS — the destination is the Firm choice,
    # and the verdicts are about offers, conditions and results — so a
    # learner with an application is by definition one this board is
    # about. Deciding the cohort from the enrolment table alone meant a
    # missing Year 13 enrolment row silently removed them from the one
    # screen that would have shown what was stopping them.
    for student in _ucas_applicants(exclude=known):
        people.append(student)
        known.add(student.student_id)

    journeys = handover_eligibility.journeys_for(
        [s.student_id for s in people])
    rows: list[Row] = []
    for student in people:
        journey = (handover_eligibility._UNSET if journeys is None
                   else journeys.get(student.student_id))
        readiness = handover_eligibility.assess(student, journey=journey)
        rows.append(_row_for(student, readiness, journey=journey))

    rows.sort(key=lambda r: r.sort_key)
    out = Board(rows=rows)
    logger.info("University progression board: %s", out.summary_line())
    return out


def _ucas_applicants(*, exclude: set[str]) -> list[Any]:
    """Students holding a UCAS application, minus those already on board.

    Every application counts, drafts included. A draft that never went
    anywhere is not noise on a board about what is stopping people — it
    is the loudest possible answer to that question.

    Fetches only the students the board does not already have. The common
    case is that almost every applicant is an enrolled Year 13, so the
    remainder is small and worth a lookup each; hydrating the whole roll
    to find two people would cost more than it saved.

    Never raises: a college running without the UCAS module gets the
    board it always had rather than an exception out of the loop.
    """
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    try:
        from education_system.systems.sixth_form.domain.progression.university import ucas as _ucas
        applications = _ucas.list_applications()
    except Exception:
        logger.exception(
            "Could not list UCAS applications — the board will show the "
            "Year 13 cohort only, and applicants outside it will be missing")
        return []

    wanted: list[str] = []
    seen = set(exclude)
    for application in applications:
        if application.student_id in seen:
            continue
        seen.add(application.student_id)
        wanted.append(application.student_id)

    out: list[Any] = []
    for student_id in wanted:
        try:
            student = _students.get_student(student_id)
        except Exception:
            logger.exception(
                "Could not load UCAS applicant %s for the board", student_id)
            continue
        # A deleted student cascades their applications away, so this is
        # only reachable mid-delete. Skipping is right either way: there
        # is no learner to progress.
        if student is not None:
            out.append(student)
    if out:
        logger.info(
            "University progression board: %d UCAS applicant(s) added "
            "outside the Year 13 cohort", len(out))
    return out


def _incomplete_transfers() -> list[Any]:
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    try:
        return _students.list_incomplete_transfers()
    except Exception:
        logger.exception(
            "Could not list incomplete transfers — the board will show the "
            "Year 13 cohort only, and stranded leavers will be missing")
        return []


def _row_for(student, readiness, *,
             journey=handover_eligibility._UNSET) -> Row:
    if journey is handover_eligibility._UNSET:
        journey_id, uni_student_id = _journey_slots(student.student_id)
    elif journey:
        journey_id, uni_student_id = _slots_of(journey)
    else:
        journey_id, uni_student_id = None, None

    state = _state_for(student, readiness, uni_student_id=uni_student_id)
    outstanding = tuple(c.label for c in readiness.blockers) + tuple(
        c.label for c in readiness.warnings)
    return Row(
        student_id=student.student_id,
        full_name=student.full_name,
        state=state,
        destination=_destination_of(readiness),
        course=_course_of(readiness),
        outstanding=outstanding,
        warnings=_warnings_for(student, readiness, state),
        journey_id=journey_id,
        university_student_id=uni_student_id,
        transferred_at=student.transferred_at,
        readiness=readiness,
    )


def _slots_of(journey: dict) -> tuple[str | None, str | None]:
    """``(journey_id, university_student_id)`` from a registry row."""
    try:
        from education_system.platform.cross_system import identity_service
        _pk, id_col = identity_service.SYSTEM_SLOTS["university"]
    except Exception:  # pragma: no cover - the registry is always importable
        id_col = "university_student_id"
    return journey.get("journey_id"), journey.get(id_col)


def _journey_slots(student_id: str) -> tuple[str | None, str | None]:
    """``(journey_id, university_student_id)`` for one learner. Either may
    be None. The single-student fallback; the board prefetches instead."""
    try:
        from education_system.platform.cross_system import identity_service
        journey = identity_service.find_by_student("sixth_form", student_id)
        return _slots_of(journey) if journey else (None, None)
    except Exception:
        logger.exception("Could not read the journey for %s", student_id)
        return None, None


# ── Actions ─────────────────────────────────────────────────────────

def prepare(student_id: str) -> Prepared:
    """Dry-run the handover: build it, report it, send nothing.

    The point of separating this from :func:`submit` is that the release
    decision is reviewable. "Which fields will actually cross, and which
    are being withheld because nobody recorded a consent?" was previously
    answerable only by doing the transfer and reading the log afterwards.
    """
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    student = _students.get_student(student_id)
    if student is None:
        return Prepared(student_id=student_id, ok=False,
                        blockers=(f"No sixth-form student {student_id}",))

    readiness = handover_eligibility.assess(student)
    destination = readiness.destination
    try:
        released = university_handover.build(student)
    except Exception as exc:
        logger.exception("Could not build the handover for %s", student_id)
        return Prepared(
            student_id=student_id, ok=False,
            blockers=(f"The handover could not be assembled: {exc}",))

    # Ask the destination's own validator what it would say. Reporting the
    # answer here is the difference between "we sent it and admissions
    # chased us" and "we knew before we sent it".
    from education_system.platform.cross_system import handover as _handover
    problems = _handover.validate_handover(
        university_handover.SOURCE_SYSTEM,
        university_handover.DESTINATION_SYSTEM,
        released.payload)

    return Prepared(
        student_id=student_id,
        ok=readiness.ready,
        boundary=released.boundary,
        included=tuple(released.included),
        withheld_no_consent=tuple(released.withheld_no_consent),
        withheld_restricted=tuple(released.withheld_restricted),
        missing_required=tuple(released.missing_required),
        destination_system=(destination.system if destination else ""),
        destination_institution=(destination.institution or ""
                                 if destination else ""),
        blockers=tuple(f"{c.label} — {c.detail}" for c in readiness.blockers),
        problems=tuple(problems),
    )


def submit(student_id: str, *, moved_by: str | None = None,
           force: bool = False) -> SubmitResult:
    """Perform the handover for one learner.

    Refuses a blocked learner unless ``force``. The escape hatch exists
    because a blocking check can be wrong about a real person — a consent
    recorded on paper, a UCAS record never keyed — and a board that can
    only ever say no is a board people work around. Forcing is logged as
    such.
    """
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    student = _students.get_student(student_id)
    if student is None:
        return SubmitResult(student_id, False,
                            f"No sixth-form student {student_id}")

    readiness = handover_eligibility.assess(student)
    if readiness.blockers and not force:
        return SubmitResult(
            student_id, False,
            "Blocked: " + "; ".join(f"{c.label} ({c.detail})"
                                    for c in readiness.blockers))
    if readiness.blockers:
        logger.warning(
            "Forcing the handover for %s past %d blocking check(s): %s",
            student_id, len(readiness.blockers),
            "; ".join(c.label for c in readiness.blockers))

    try:
        after = _students.mark_transferred(student_id, moved_by=moved_by)
    except Exception as exc:
        logger.exception("Handover submission failed for %s", student_id)
        return SubmitResult(student_id, False, f"Transfer failed: {exc}")

    if not after.transfer_complete:
        # mark_transferred() is deliberately best-effort: it flips the
        # status and revokes access whatever happens, and leaves
        # transferred_at unset when the announcement did not land. That
        # unset column is the honest answer, so report it as a failure
        # rather than as a success with a caveat.
        return SubmitResult(
            student_id, False,
            "The sixth-form record was closed but the announcement did not "
            "land — the learner is stranded. Submit again to retry.",
            state=STRANDED)

    _journey_id, uni_id = _journey_slots(student_id)
    state = ENROLLED if uni_id else SUBMITTED
    return SubmitResult(
        student_id, True,
        f"Handed over at {after.transferred_at}"
        + (f"; already university student {uni_id}" if uni_id else ""),
        state=state)


def submit_many(student_ids, *, moved_by: str | None = None,
                force: bool = False) -> list[SubmitResult]:
    """Bulk progression, one result per learner.

    Never stops on the first failure. Results day is the whole point of
    this function, and a run that aborts halfway leaves an operator with
    no idea which half went — so every learner is attempted and every
    outcome is reported, successes and validation failures alike.
    """
    results: list[SubmitResult] = []
    for student_id in student_ids:
        try:
            results.append(submit(student_id, moved_by=moved_by, force=force))
        except Exception as exc:
            # submit() already guards itself; this is the belt-and-braces
            # that keeps one unexpected failure from ending the batch.
            logger.exception("Bulk handover crashed for %s", student_id)
            results.append(SubmitResult(student_id, False, f"Crashed: {exc}"))
    ok = sum(1 for r in results if r.ok)
    logger.info("Bulk handover: %d/%d succeeded", ok, len(results))
    return results


def retry_stranded(*, moved_by: str | None = None) -> list[SubmitResult]:
    """Re-attempt every transfer that was left half-applied.

    Safe by construction: the announcement carries a deterministic
    idempotency key, so a learner whose event did land re-announces into a
    no-op, and one whose event did not gets the retry they need.
    """
    stranded = [s.student_id for s in _incomplete_transfers()]
    if not stranded:
        logger.info("No stranded transfers to retry")
        return []
    logger.info("Retrying %d stranded transfer(s)", len(stranded))
    return submit_many(stranded, moved_by=moved_by, force=True)


__all__ = [
    "STRANDED", "BLOCKED", "ATTENTION", "READY", "SUBMITTED", "ENROLLED",
    "DEPARTED", "STATE_ORDER",
    "Row", "Prepared", "SubmitResult", "Board",
    "board", "prepare", "submit", "submit_many", "retry_stranded",
]
