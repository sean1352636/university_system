"""University-side UCAS management — view sixth-form UCAS
applications that name *this* university and record admissions
decisions against them.

The university doesn't own UCAS data; the sixth-form system does. This
module is a thin read+write adapter on top of the sixth-form Python
API:

* ``list_applicants(...)`` returns one row per sixth-form
  ``ucas_choices`` entry whose ``university`` matches the configured
  university name, joined with the parent application and the
  student record.
* ``get_full_application(application_id)`` returns the parent
  application plus all of the student's choices (so an admissions
  officer can see what other universities they applied to and which
  of those replied first).
* ``record_decision(choice_id, decision_status, ...)`` writes the
  decision (``Conditional Offer`` / ``Unconditional Offer`` /
  ``Rejected``, plus offer terms) back to the sixth-form
  ``ucas_choices`` row by calling the sf API. The sf module owns
  validation and audit logging.

Configured university name is taken from
``education_system.post_18.university_system.core.defaults.UNIVERSITY_NAME``
(env override: ``UNIVERSITY_NAME``). Override per-call by passing
``university_name=`` to ``list_applicants`` / ``summary``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from education_system.post_18.university_system.core.defaults import (
    UNIVERSITY_NAME,
)

logger = logging.getLogger(__name__)


# ── Re-export sf vocab so callers don't reach across the boundary ──

def _sf():
    from education_system.post_16.sixthform_system.modules.domain.progression.ucas import (
        ucas as _ucas,
    )
    return _ucas


def _sf_students():
    from education_system.post_16.sixthform_system.modules.domain.students.students import (
        students as _s,
    )
    return _s


# Mirror the sf vocab here for callers and as a single import surface.
APP_STATUSES        = ("Draft", "Submitted", "Replied",
                       "Confirmed", "Clearing")
DECISION_STATUSES   = ("Awaiting", "Unconditional Offer",
                       "Conditional Offer", "Rejected", "Withdrawn")
FINAL_DECISIONS     = ("Firm", "Insurance", "Declined")
DECIDABLE           = ("Unconditional Offer", "Conditional Offer",
                       "Rejected", "Withdrawn")


class UcasError(Exception):
    """Raised when a sf-side call fails or input is rejected."""


@dataclass
class Applicant:
    """One UCAS choice naming this university, with parent app +
    student context bundled in. Read-only; persisted on the sf side.
    """
    choice_id: int
    application_id: int
    choice_order: int
    course_code: str | None
    course_name: str
    entry_year: int | None
    decision_status: str
    offer_terms: str | None
    final_decision: str | None
    choice_notes: str | None
    # Application context
    cycle_year: int
    app_status: str
    ucas_id: str | None
    submitted_at: str | None
    app_notes: str | None
    personal_statement: str | None
    # Student context
    student_id: str
    student_name: str
    student_email: str
    student_dob: str | None
    student_status: str        # 'Active' / 'Left' etc.

    @property
    def display_subjects(self) -> str:
        return f"{self.course_code or '—'}  {self.course_name}"


@dataclass
class FullApplication:
    """Parent UCAS application plus every choice. Used in the detail
    view so an admissions officer sees the full picture."""
    application_id: int
    student_id: str
    student_name: str
    student_email: str
    student_dob: str | None
    cycle_year: int
    ucas_id: str | None
    app_status: str
    submitted_at: str | None
    personal_statement: str | None
    app_notes: str | None
    choices: list  # list of sf ucas.Choice
    our_choice_id: int | None   # The choice that names this uni
    subjects: list[str]         # A-level subjects from sf students row


def _resolve_uni_name(name: str | None) -> str:
    return (name or UNIVERSITY_NAME or "").strip()


# ── List / detail ────────────────────────────────────────────────

def list_applicants(
    *,
    university_name: str | None = None,
    decision_status: str | None = None,
    app_status: str | None = None,
    cycle_year: int | None = None,
    search: str | None = None,
) -> list[Applicant]:
    """Return one ``Applicant`` per ``ucas_choices`` row pointing at
    this university. Filter by decision status, parent application
    status, cycle year, and a free-text search across student name /
    student id / course name.
    """
    name = _resolve_uni_name(university_name)
    if not name:
        raise UcasError("University name is empty — set "
                         "UNIVERSITY_NAME or pass university_name=")
    sf = _sf()
    sf.init_db()

    if decision_status and decision_status not in DECISION_STATUSES:
        raise UcasError(
            f"decision_status must be one of: {', '.join(DECISION_STATUSES)}")
    if app_status and app_status not in APP_STATUSES:
        raise UcasError(
            f"app_status must be one of: {', '.join(APP_STATUSES)}")

    # Single SQL roundtrip across the sf DB.
    conn = sf._connect()
    try:
        clauses = ["LOWER(c.university) = LOWER(?)"]
        args: list = [name]
        if decision_status:
            clauses.append("c.decision_status = ?")
            args.append(decision_status)
        if app_status:
            clauses.append("a.status = ?")
            args.append(app_status)
        if cycle_year is not None:
            clauses.append("a.cycle_year = ?")
            args.append(cycle_year)
        if search:
            q = f"%{search.strip()}%"
            clauses.append(
                "(s.student_id LIKE ? OR s.first_name LIKE ? "
                "OR s.last_name LIKE ? OR c.course_name LIKE ?)")
            args.extend([q, q, q, q])
        where = " AND ".join(clauses)
        rows = conn.execute(
            f"""SELECT c.*, a.cycle_year, a.status AS app_status,
                       a.ucas_id, a.submitted_at,
                       a.notes AS app_notes, a.personal_statement,
                       s.student_id, s.first_name, s.middle_name,
                       s.last_name, s.email, s.date_of_birth,
                       s.status AS student_status
                  FROM ucas_choices AS c
                  JOIN ucas_applications AS a
                       ON a.application_id = c.application_id
                  JOIN students AS s
                       ON s.student_id = a.student_id
                 WHERE {where}
                 ORDER BY a.submitted_at DESC NULLS LAST,
                          s.last_name, s.first_name""",
            args,
        ).fetchall()
    finally:
        conn.close()

    out: list[Applicant] = []
    for r in rows:
        full = " ".join(p for p in (
            r["first_name"], r["middle_name"], r["last_name"]) if p)
        out.append(Applicant(
            choice_id=r["choice_id"],
            application_id=r["application_id"],
            choice_order=r["choice_order"],
            course_code=r["course_code"],
            course_name=r["course_name"],
            entry_year=r["entry_year"],
            decision_status=r["decision_status"],
            offer_terms=r["offer_terms"],
            final_decision=r["final_decision"],
            choice_notes=r["notes"],
            cycle_year=r["cycle_year"],
            app_status=r["app_status"],
            ucas_id=r["ucas_id"],
            submitted_at=r["submitted_at"],
            app_notes=r["app_notes"],
            personal_statement=r["personal_statement"],
            student_id=r["student_id"],
            student_name=full.strip(),
            student_email=r["email"],
            student_dob=r["date_of_birth"],
            student_status=r["student_status"] or "Active",
        ))
    logger.debug(
        "list_applicants(name=%r, dec=%r, app=%r, cy=%r) -> %d",
        name, decision_status, app_status, cycle_year, len(out))
    return out


def get_full_application(application_id: int) -> FullApplication | None:
    sf = _sf()
    sfs = _sf_students()
    app = sf.get_application(application_id)
    if app is None:
        return None
    choices = sf.list_choices(application_id)
    student = sfs.get_student(app.student_id)
    if student is None:
        raise UcasError(
            f"Application {application_id} references unknown "
            f"student {app.student_id}")
    uni_name = _resolve_uni_name(None)
    our = next((c for c in choices
                 if (c.university or "").strip().lower()
                    == uni_name.lower()), None)
    subjects = [s for s in (student.subject_1, student.subject_2,
                              student.subject_3) if s]
    return FullApplication(
        application_id=app.application_id,
        student_id=student.student_id,
        student_name=student.full_name,
        student_email=student.email,
        student_dob=student.date_of_birth,
        cycle_year=app.cycle_year,
        ucas_id=app.ucas_id,
        app_status=app.status,
        submitted_at=app.submitted_at,
        personal_statement=app.personal_statement,
        app_notes=app.notes,
        choices=choices,
        our_choice_id=(our.choice_id if our is not None else None),
        subjects=subjects,
    )


# ── Decision write-back ──────────────────────────────────────────

def record_decision(
    choice_id: int,
    decision_status: str,
    *,
    offer_terms: str | None = None,
    notes: str | None = None,
) -> object:
    """Record a uni admissions decision on a sixth-form UCAS choice.

    Wraps the sf ``update_choice`` API: only the decision-related
    fields are touched, the rest of the row (university, course, etc.)
    is left alone. Raises :class:`UcasError` for invalid input or any
    underlying validation error from the sf side. Returns the
    refreshed sf ``Choice`` row.
    """
    if decision_status not in DECISION_STATUSES:
        raise UcasError(
            f"decision_status must be one of: {', '.join(DECISION_STATUSES)}")
    if decision_status == "Conditional Offer" and not (offer_terms or "").strip():
        raise UcasError(
            "A conditional offer must include offer terms "
            "(e.g. 'ABB including B in Mathematics').")
    sf = _sf()
    update = {"decision_status": decision_status}
    if offer_terms is not None:
        update["offer_terms"] = offer_terms
    if notes is not None:
        update["notes"] = notes
    try:
        out = sf.update_choice(choice_id, update)
    except Exception as e:
        # The sf ValidationError extends ValueError; everything else
        # is unexpected. Wrap both as UcasError so callers don't have
        # to cross the boundary again to catch.
        raise UcasError(str(e)) from e
    logger.info(
        "Recorded UCAS decision: choice #%d -> %s (offer_terms=%s)",
        choice_id, decision_status, bool(offer_terms))

    # Auto-create the uni-side link the first time a decision is
    # recorded against a choice. Best-effort: failure here should not
    # roll back the actual decision the admissions officer just made.
    try:
        from education_system.post_18.university_system.modules.domain.admissions.ucas import (
            ucas_links as _links,
        )
        _links.ensure_link_for_choice(
            sf_application_id=out.application_id,
            sf_choice_id=out.choice_id,
            sf_student_id=_sf().get_application(out.application_id).student_id,
        )
    except Exception:
        logger.exception(
            "Could not auto-create UCAS link for choice #%d "
            "(decision write succeeded)", choice_id)

    # Notify the student by email when the decision is one they need
    # to act on: offers (either flavour) get the `student_offer`
    # template, rejections get `student_rejection`. Withdrawals are
    # not auto-emailed — those are usually triggered by the student
    # themselves so the school doesn't need to re-tell them.
    email_template: str | None = None
    if decision_status in ("Conditional Offer", "Unconditional Offer"):
        email_template = "student_offer"
    elif decision_status == "Rejected":
        email_template = "student_rejection"
    if email_template:
        try:
            _send_decision_email(out, decision_status, offer_terms,
                                  template=email_template)
        except Exception:
            logger.exception(
                "Decision email (%s) failed for choice #%d "
                "(decision write succeeded)",
                email_template, choice_id)

    return out


def _send_decision_email(choice, decision_status: str,
                          offer_terms: str | None,
                          *, template: str) -> None:
    """Render and send one of the decision templates
    (``student_offer`` / ``student_rejection``) to the sixth-form
    student. Reads the parent application + student via the sf API.
    Best-effort — caller is expected to catch."""
    sf = _sf()
    sfs = _sf_students()
    app = sf.get_application(choice.application_id)
    student = sfs.get_student(app.student_id) if app else None
    if student is None:
        logger.warning(
            "Offer email skipped: could not find student for "
            "choice #%d (application #%s missing)",
            choice.choice_id, choice.application_id)
        return

    code_suffix = (f" ({choice.course_code})"
                    if choice.course_code else "")
    decision_lower = decision_status[0].lower() + decision_status[1:]
    article = "an" if decision_lower[:1].lower() in "aeiou" else "a"

    if decision_status == "Conditional Offer":
        terms = (offer_terms or "").strip()
        if terms:
            conditions_block = (
                "Your offer is conditional on:\n"
                f"  {terms}\n\n"
                "If your final grades meet these conditions you will "
                "be confirmed automatically on results day.")
        else:
            conditions_block = (
                "Your offer is conditional. The admissions team will "
                "follow up with the specific grade requirements "
                "shortly.")
    else:  # Unconditional Offer
        conditions_block = (
            "This is an unconditional offer — no further academic "
            "conditions apply. Your place is guaranteed subject to "
            "the usual enrolment formalities (right-to-study check, "
            "DBS where applicable, etc.).")

    context = {
        "university":            _resolve_uni_name(None),
        "student_id":            student.student_id,
        "first_name":            student.first_name,
        "full_name":             student.full_name,
        "email":                 student.email,
        "course_name":           choice.course_name,
        "course_code":           choice.course_code or "—",
        "course_code_suffix":    code_suffix,
        "decision_status":       decision_status,
        "decision_status_lower": decision_lower,
        "article":               article,
        "offer_terms":           offer_terms or "—",
        "conditions_block":      conditions_block,
        "cycle_year":            str(app.cycle_year),
        "entry_year":            str(choice.entry_year or app.cycle_year),
        "ucas_id":               app.ucas_id or "—",
        "contact_email":         "admissions@teesside.ac.uk",
    }

    from education_system.post_16.sixthform_system.modules.domain.staff_comms.messages import (
        email_templates as _tpl,
    )
    msg = _tpl.send_from_template(
        template,
        context,
        to_name=student.full_name,
        to_address=student.email,
        student_id=student.student_id,
    )
    logger.info(
        "Sent %s (%s) email to %s (%s) for choice #%d as message #%d",
        decision_status, template, student.student_id, student.email,
        choice.choice_id, msg.message_id,
    )


# ── Summary ──────────────────────────────────────────────────────

@dataclass
class UcasSummary:
    university_name: str
    total_applicants: int
    by_decision: dict[str, int]
    by_app_status: dict[str, int]
    by_course: dict[str, int]
    by_cycle: dict[int, int]
    awaiting_decision: int   # decision_status == 'Awaiting'
    offers_made: int         # Conditional + Unconditional


def summary(*, university_name: str | None = None) -> UcasSummary:
    name = _resolve_uni_name(university_name)
    applicants = list_applicants(university_name=name)
    by_decision = {d: 0 for d in DECISION_STATUSES}
    by_app = {a: 0 for a in APP_STATUSES}
    by_course: dict[str, int] = {}
    by_cycle: dict[int, int] = {}
    for a in applicants:
        by_decision[a.decision_status] = by_decision.get(
            a.decision_status, 0) + 1
        by_app[a.app_status] = by_app.get(a.app_status, 0) + 1
        by_course[a.course_name] = by_course.get(a.course_name, 0) + 1
        by_cycle[a.cycle_year] = by_cycle.get(a.cycle_year, 0) + 1
    return UcasSummary(
        university_name=name,
        total_applicants=len(applicants),
        by_decision=by_decision,
        by_app_status=by_app,
        by_course=by_course,
        by_cycle=by_cycle,
        awaiting_decision=by_decision.get("Awaiting", 0),
        offers_made=(by_decision.get("Conditional Offer", 0)
                       + by_decision.get("Unconditional Offer", 0)),
    )
