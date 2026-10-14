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
  ``ucas_choices`` row by calling the sf API, and records everything
  about that decision that is ours: the structured offer terms
  (:mod:`.offer_terms`), who decided and when (:mod:`.decision_log`,
  which also writes the platform audit entry), the link to our own
  admissions application (:mod:`.ucas_links`), and the applicant's
  email.

  The sixth form owns *validation* of the choice row. It does not own
  audit logging and never did — this docstring used to say it did, while
  the sixth form's ``update_choice`` logged one INFO line and nothing
  reached the platform audit log at all. An offer is now audited on our
  side, which is where it is actually decided.

The name matched against ``ucas_choices.university`` is the institution
name this university publishes (``application.prospectus``), falling back
to the ``UNIVERSITY_NAME`` environment default. Override per-call by
passing ``university_name=`` to ``list_applicants`` / ``summary``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from education_system.systems.university.infrastructure.defaults import (
    UNIVERSITY_NAME,
)

logger = logging.getLogger(__name__)


# ── Re-export sf vocab so callers don't reach across the boundary ──

def _sf():
    from education_system.systems.sixth_form.domain.progression.university import ucas as _ucas
    return _ucas


def _sf_students():
    from education_system.systems.sixth_form.domain.learners.students import (
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
    """What to match ``ucas_choices.university`` against.

    There were two answers to "what are we called": this module used the
    ``UNIVERSITY_NAME`` environment default while the sixth form asked for
    the admin-editable ``institution_name`` setting. They share a default
    string, so nothing looked wrong — but an administrator renaming the
    institution in the GUI changed only one of them, and the match below
    is exact. The symptom would have been an admissions officer opening
    the applicant list and finding it empty, with every sixth-form choice
    still naming the university perfectly correctly.

    So there is one answer now, and it is the one an administrator can
    actually change. The environment default remains the fallback for a
    deployment whose settings file has never been written.
    """
    if name and name.strip():
        return name.strip()
    published = None
    try:
        from education_system.systems.university.application import prospectus
        published = prospectus.institution_name()
    except Exception:
        logger.debug("Could not read the published institution name",
                     exc_info=True)
    return (published or UNIVERSITY_NAME or "").strip()


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
        # db-audit: ignore[DBW001] - join over a code-controlled list
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
    terms: dict | None = None,
    issued_by: str | None = None,
) -> object:
    """Record a uni admissions decision on a sixth-form UCAS choice.

    Wraps the sf ``update_choice`` API: only the decision-related
    fields are touched, the rest of the row (university, course, etc.)
    is left alone. Raises :class:`UcasError` for invalid input or any
    underlying validation error from the sf side. Returns the
    refreshed sf ``Choice`` row.

    ``terms`` carries the rest of what an offer actually says — reply
    deadline, expiry, scholarship, guaranteed accommodation, an
    alternative grade pathway. ``offer_terms`` remains the one-line
    summary that goes on the choice itself and into the student's email;
    these are the structured fields behind it, stored on our side by
    :mod:`.offer_terms` and read back by the sixth form. Ignored for a
    rejection or a withdrawal, which have no terms to carry.

    ``issued_by`` is the admissions officer making the decision. It is
    recorded against both the terms and the link.
    """
    if decision_status not in DECISION_STATUSES:
        raise UcasError(
            f"decision_status must be one of: {', '.join(DECISION_STATUSES)}")
    if decision_status == "Conditional Offer" and not (offer_terms or "").strip():
        raise UcasError(
            "A conditional offer must include offer terms "
            "(e.g. 'ABB including B in Mathematics').")

    # Checked before anything is written. Storing the terms is best-effort
    # once the decision has landed — which is right for a failing database
    # and wrong for a mistyped date, because the officer would never hear
    # about it. So the mistyped date is caught here instead, while the
    # decision can still be refused as a whole.
    issue_terms = None
    if terms and decision_status in ("Conditional Offer",
                                     "Unconditional Offer"):
        from education_system.systems.university.domains.admissions.domain.ucas import (
            offer_terms as _terms,
        )
        try:
            issue_terms = _terms.validate_terms(terms)
        except _terms.OfferTermsError as e:
            raise UcasError(str(e)) from e

    sf = _sf()
    update = {"decision_status": decision_status}
    if offer_terms is not None:
        update["offer_terms"] = offer_terms
    if notes is not None:
        update["notes"] = notes
    try:
        # ``issued_by_university`` is what makes this write legal: the sf
        # data layer refuses decision fields on a choice naming us from
        # every other caller, so this is the only door into them.
        out = sf.update_choice(choice_id, update, issued_by_university=True)
    except Exception as e:
        # The sf ValidationError extends ValueError; everything else
        # is unexpected. Wrap both as UcasError so callers don't have
        # to cross the boundary again to catch.
        raise UcasError(str(e)) from e
    logger.info(
        "Recorded UCAS decision: choice #%d -> %s (offer_terms=%s)",
        choice_id, decision_status, bool(offer_terms))

    # The structured terms behind the one-line summary, already validated
    # above. Best-effort like the link below — the decision itself is
    # written, and a failure storing the scholarship flag must not undo it.
    if issue_terms is not None:
        try:
            from education_system.systems.university.domains.admissions.domain.ucas import (
                offer_terms as _terms,
            )
            _terms.save_terms(out.choice_id, issue_terms, issued_by=issued_by)
        except Exception:
            logger.exception(
                "Could not store offer terms for choice #%d "
                "(decision write succeeded)", choice_id)

    # The applicant behind the choice, resolved once — the steps below
    # all want it and each used to fetch it again.
    sf_student_id: str | None = None
    try:
        parent = _sf().get_application(out.application_id)
        sf_student_id = parent.student_id if parent else None
    except Exception:
        logger.exception(
            "Could not resolve the student behind choice #%d", choice_id)

    # Who decided, and when. Logged loudly on failure rather than
    # silently: everything after the sf write is best-effort so a failing
    # database cannot appear to the officer as a decision that did not
    # happen, but a decision nobody can be held to is the exact problem
    # this record exists to solve.
    try:
        from education_system.systems.university.domains.admissions.domain.ucas import (
            decision_log as _log,
        )
        _log.record(
            sf_choice_id=out.choice_id,
            sf_application_id=out.application_id,
            sf_student_id=sf_student_id,
            decision_status=decision_status,
            offer_terms=offer_terms,
            notes=notes,
            decided_by=issued_by,
        )
    except Exception:
        logger.exception(
            "UNATTRIBUTED DECISION: could not log choice #%d -> %s by %s "
            "(decision write succeeded)",
            choice_id, decision_status, issued_by or "unknown")

    # Auto-create the uni-side link the first time a decision is
    # recorded against a choice. Best-effort: failure here should not
    # roll back the actual decision the admissions officer just made.
    link = None
    try:
        from education_system.systems.university.domains.admissions.domain.ucas import (
            ucas_links as _links,
        )
        link = _links.ensure_link_for_choice(
            sf_application_id=out.application_id,
            sf_choice_id=out.choice_id,
            sf_student_id=sf_student_id or "",
            linked_by=issued_by,
        )
    except Exception:
        logger.exception(
            "Could not auto-create UCAS link for choice #%d "
            "(decision write succeeded)", choice_id)

    # An offer is an application to this university, so open one in our
    # own admissions pipeline rather than leaving the UCAS route running
    # entirely beside it. A rejection opens nothing; there is no
    # application to track.
    if link is not None and decision_status in ("Conditional Offer",
                                                "Unconditional Offer"):
        try:
            from education_system.systems.university.domains.admissions.domain.ucas import (
                pipeline_link as _pipeline,
            )
            _pipeline.ensure_application_for_link(
                link, choice=out, decided_by=issued_by)
        except Exception:
            logger.exception(
                "Could not open an admissions application for choice #%d "
                "(decision write succeeded)", choice_id)

    # A rejected applicant is a clearing candidate, and clearing already
    # keys on the UCAS id. Referring them is the university's call, not an
    # automatic one — this only makes the match findable.
    if decision_status == "Rejected":
        try:
            from education_system.systems.university.domains.admissions.domain.ucas import (
                clearing_link as _clearing,
            )
            _clearing.note_rejection(out, sf_student_id)
        except Exception:
            logger.exception(
                "Could not reconcile choice #%d with clearing "
                "(decision write succeeded)", choice_id)

    # Every choice decided? Then the application is Replied. The status
    # existed in APP_STATUSES and nothing could reach it — the sixth form
    # never set it and no university call did either, so a cycle went
    # straight from Submitted to Confirmed and the one status describing
    # "all the universities have answered" was decorative.
    try:
        _promote_to_replied(out.application_id)
    except Exception:
        logger.exception(
            "Could not re-evaluate the application status for choice #%d "
            "(the decision itself was recorded)", choice_id)

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



def _promote_to_replied(application_id: int) -> bool:
    """Move a Submitted application to Replied once nothing is awaited.

    Only from Submitted, and only when no choice is still ``Awaiting``.
    A withdrawn or rejected choice counts as answered — the question is
    whether the applicant is still waiting to hear, not whether the news
    was good.

    Never moves a settled application: Confirmed and Clearing are further
    along, and walking one back to Replied would undo the outcome.
    """
    sf = _sf()
    application = sf.get_application(application_id)
    if application is None or application.status != "Submitted":
        return False
    choices = sf.list_choices(application_id)
    if not choices or any(c.decision_status == "Awaiting" for c in choices):
        return False
    sf.update_application(application_id, {"status": "Replied"})
    logger.info(
        "UCAS application #%d -> Replied (all %d choice(s) decided)",
        application_id, len(choices))
    return True


#: Decisions a student can only reply to. Firm / Insurance / Declined is
#: an answer to an offer; against a rejection or a still-awaited choice
#: there is nothing to answer.
_REPLYABLE = ("Conditional Offer", "Unconditional Offer")


def record_final_decision(
    choice_id: int,
    final_decision: str | None,
    *,
    issued_by: str | None = None,
) -> object:
    """Record the applicant's Firm / Insurance / Declined reply.

    This lives on the university side rather than the sixth form's: the
    reply is an answer to an offer *we* made, it is the event that closes
    or keeps open a place in our intake, and it is the point at which the
    student needs a written confirmation of what they have accepted. The
    sixth form's choice screen now shows the value and no longer sets it,
    so there is one place it can be typed instead of two that could
    disagree.

    Pass ``None`` (or ``""``) to clear a reply recorded in error. Setting
    a reply requires an offer on the choice; the sixth-form data layer
    separately enforces at most one Firm and one Insurance across the
    application, and that rejection surfaces here as
    :class:`UcasError`.

    Emails the student on any *change* to a non-empty reply. Clearing is
    silent — there is no outcome to announce — and re-saving the same
    value sends nothing, so reopening the dialog and clicking Save does
    not re-confirm a decision the student already has in writing.
    """
    reply = (final_decision or "").strip() or None
    if reply is not None and reply not in FINAL_DECISIONS:
        raise UcasError(
            f"final_decision must be blank or one of: "
            f"{', '.join(FINAL_DECISIONS)}")

    sf = _sf()
    try:
        current = sf.get_choice(choice_id)
    except Exception as e:
        raise UcasError(str(e)) from e
    if current is None:
        raise UcasError(f"No UCAS choice with id {choice_id}")
    if reply is not None and current.decision_status not in _REPLYABLE:
        raise UcasError(
            f"This choice is '{current.decision_status}' — a "
            f"{reply} reply can only be recorded against an offer.")

    previous = current.final_decision or None
    try:
        out = sf.update_choice(choice_id, {"final_decision": reply or ""},
                                issued_by_university=True)
    except Exception as e:
        raise UcasError(str(e)) from e
    logger.info(
        "Recorded UCAS final decision: choice #%d -> %s (was %s, by %s)",
        choice_id, reply or "(cleared)", previous or "(none)",
        issued_by or "unknown")

    if reply is not None and reply != previous:
        try:
            _send_final_decision_email(out, reply)
        except Exception:
            logger.exception(
                "Final-decision email failed for choice #%d "
                "(the reply itself was saved)", choice_id)
    return out


#: Application statuses that close the cycle. Both are ours to set, for
#: the same reason the decision and the reply are: they are records of
#: what a university did, and the sixth form reads them.
SETTLED_STATUSES = ("Confirmed", "Clearing")


def _application_for_choice(choice_id: int):
    """``(choice, application)`` for a choice id, or raise."""
    sf = _sf()
    try:
        choice = sf.get_choice(choice_id)
    except Exception as e:
        raise UcasError(str(e)) from e
    if choice is None:
        raise UcasError(f"No UCAS choice with id {choice_id}")
    application = sf.get_application(choice.application_id)
    if application is None:
        raise UcasError(
            f"Choice #{choice_id} has no application behind it")
    return choice, application


def _settle(choice_id: int, status: str, *, issued_by: str | None) -> object:
    """Move the parent application to a settled status. Returns it."""
    sf = _sf()
    choice, application = _application_for_choice(choice_id)
    if application.status == status:
        raise UcasError(f"This application is already {status}.")
    if application.status == "Draft":
        raise UcasError(
            "This application has not been submitted, so its cycle "
            "cannot be closed.")
    try:
        out = sf.update_application(application.application_id,
                                     {"status": status})
    except Exception as e:
        raise UcasError(str(e)) from e
    logger.info(
        "UCAS application #%d -> %s (from choice #%d, by %s)",
        application.application_id, status, choice_id,
        issued_by or "unknown")
    # The end of the cycle is the most consequential thing that happens
    # to an applicant, and it was the only step that told them nothing:
    # the offer emailed, the reply emailed, and confirmation — the point
    # at which the place is actually theirs — went out in silence.
    try:
        # The *choice* — the course being confirmed or given up. ``out``
        # is the updated application, which knows none of that.
        _send_outcome_email(choice, application, status)
    except Exception:
        logger.exception(
            "Cycle-outcome email failed for application #%d "
            "(the status itself was saved)", application.application_id)
    return out


def confirm_place(choice_id: int, *, issued_by: str | None = None) -> object:
    """Confirm the applicant's place — results day going their way.

    Ours to record, and only ours: confirming is the university saying
    the offer's conditions have been met, which is a judgement about a
    decision we made. The sixth form used to set this on its own copy of
    the application, which meant a college could mark a place confirmed
    at a university that had not confirmed it.

    It also carries weight beyond the status. The sixth form's handover
    eligibility discharges its ``Offer conditions`` check on exactly this
    value, so this call is what makes a learner transferable.

    Refuses unless the choice is *ours* and is the applicant's Firm
    reply. A place is confirmed by the institution holding it, and the
    Firm choice is the one being held.
    """
    choice, _application = _application_for_choice(choice_id)
    university = _resolve_uni_name(None)
    if (choice.university or "").strip().lower() != university.lower():
        raise UcasError(
            f"This choice is at {choice.university}, not {university}. "
            "A place is confirmed by the university holding it.")
    if choice.final_decision != "Firm":
        raise UcasError(
            "Only a Firm choice can be confirmed — this one is "
            f"{choice.final_decision or 'not replied to'}. Record the "
            "applicant's reply first.")
    if choice.decision_status not in _REPLYABLE:
        raise UcasError(
            f"This choice is '{choice.decision_status}', so there is no "
            "offer to confirm.")
    out = _settle(choice_id, "Confirmed", issued_by=issued_by)

    # Their sixth form is over. Closing the login here rather than at the
    # handover is deliberate: confirmation is what ends the school phase,
    # and the handover can be days later — until now a learner with a
    # confirmed university place kept a working college login for as long
    # as nobody got round to submitting them.
    #
    # Not done for clearing. A learner in clearing has no place, is very
    # much still their college's, and needs that account more than ever.
    #
    # The sixth form decides whether the account can actually close: its
    # ``disable_leaver_login`` leaves alone any account still carrying
    # another membership, because shared auth means the row is a person
    # who may also be a parent or part-time staff. Best-effort — a place
    # is confirmed whatever an auth database says.
    student_id = _application_for_choice(choice_id)[1].student_id
    try:
        students = _sf_students()
        students.disable_leaver_login(student_id)
        # And any parent login that existed only to follow this learner.
        # One covering a sibling still at the college is left alone — the
        # sixth form makes that call, not us.
        students.disable_orphaned_parent_logins(student_id)
    except Exception:
        logger.exception(
            "Could not close the sixth-form logins after confirming "
            "choice #%d (the confirmation itself stands)", choice_id)
    return out


def enter_clearing(choice_id: int, *, issued_by: str | None = None) -> object:
    """Record that the applicant has gone into UCAS Clearing.

    The other way a cycle ends. Not restricted to our own choices: an
    applicant reaches clearing because *no* university took them, and the
    one recording it is whichever is looking at them — which, on this
    platform, is us.

    Deliberately not a referral and not an offer. The clearing match is
    made by :mod:`.clearing_link`, which is explicit that rejecting
    somebody does not put them into clearing, because clearing is
    something an applicant chooses to enter and a university chooses to
    offer. This records the entering.

    Replies already on the application are left alone — they are the
    record of the offers that did not come off, and that is the reason
    the applicant is in clearing at all.
    """
    return _settle(choice_id, "Clearing", issued_by=issued_by)



def _send_outcome_email(choice, app, status: str) -> None:
    """Tell the student how their cycle ended.

    Two very different messages behind one template: a confirmed place is
    an arrival and needs next steps, and clearing is a redirection and
    needs the deadline pressure said out loud. Best-effort; the caller
    catches.
    """
    student = _sf_students().get_student(app.student_id) if app else None
    if student is None:
        logger.warning(
            "Cycle-outcome email skipped: no student behind choice #%d",
            choice.choice_id)
        return

    university = _resolve_uni_name(None)
    if status == "Confirmed":
        subject_line = f"Your place at {university} is confirmed"
        outcome_block = (
            f"Your place at {university} is confirmed. The conditions of "
            "your offer have been met and the place is yours.")
        next_steps = (
            "What happens next\n"
            "-----------------\n"
            "  - We will be in touch about enrolment, your student number "
            "and module registration.\n"
            "  - Look out for accommodation and welcome-week information.\n"
            "  - Keep an eye on the email address you gave UCAS — that is "
            "where the enrolment details go.")
    else:  # Clearing
        subject_line = f"Your UCAS application at {university}: clearing"
        outcome_block = (
            "Your UCAS application has been moved into Clearing. That "
            "means the cycle has closed without a place on this course, "
            "and you can now be considered for courses with vacancies.")
        next_steps = (
            "What happens next\n"
            "-----------------\n"
            "  - Clearing moves quickly. Speak to your sixth-form careers "
            "team today rather than at the end of the week.\n"
            "  - Search course vacancies on the UCAS site and ring the "
            "universities directly — offers in clearing are usually made "
            "on the phone.\n"
            "  - Have your UCAS ID, your grades and your subjects in "
            "front of you when you call.")

    code_suffix = f" ({choice.course_code})" if choice.course_code else ""
    context = {
        "university":         university,
        "first_name":         student.first_name,
        "full_name":          student.full_name,
        "student_id":         student.student_id,
        "subject_line":       subject_line,
        "outcome_block":      outcome_block,
        "next_steps":         next_steps,
        "course_name":        choice.course_name,
        "course_code_suffix": code_suffix,
        "decision_status":    choice.decision_status,
        "offer_terms":        choice.offer_terms or "—",
        "entry_year":         str(choice.entry_year or app.cycle_year),
        "cycle_year":         str(app.cycle_year),
        "ucas_id":            app.ucas_id or "—",
        "contact_email":      "admissions@teesside.ac.uk",
    }
    from education_system.systems.sixth_form.domain.operations.communications.messages import (
        email_templates as _tpl,
    )
    msg = _tpl.send_from_template(
        "ucas_cycle_outcome", context,
        to_name=student.full_name, to_address=student.email,
        student_id=student.student_id)
    logger.info(
        "Sent %s cycle-outcome email to %s for application #%d as "
        "message #%d", status, student.student_id,
        choice.application_id, msg.message_id)


def _send_final_decision_email(choice, final_decision: str) -> None:
    """Confirm a Firm / Insurance / Declined reply to the student.

    Same shape as :func:`_send_decision_email` — renders a sixth-form
    template against the student on the parent application. Best-effort;
    the caller catches.
    """
    sf = _sf()
    sfs = _sf_students()
    app = sf.get_application(choice.application_id)
    student = sfs.get_student(app.student_id) if app else None
    if student is None:
        logger.warning(
            "Final-decision email skipped: could not find student for "
            "choice #%d (application #%s missing)",
            choice.choice_id, choice.application_id)
        return

    university = _resolve_uni_name(None)
    if final_decision == "Firm":
        outcome_block = (
            "You have made this your FIRM choice — your first-choice "
            "place.\n\n"
            "If your offer is conditional, meeting its conditions on "
            "results day confirms this place automatically and UCAS "
            "will show it as unconditional firm. If your offer is "
            "already unconditional, your place is confirmed now and we "
            "will be in touch about enrolment, accommodation and "
            "welcome week.")
    elif final_decision == "Insurance":
        outcome_block = (
            "You have made this your INSURANCE choice — your back-up "
            "place.\n\n"
            "It comes into play only if you do not meet the conditions "
            "of your firm choice. Hold on to the conditions of this "
            "offer as well as your firm one: on results day UCAS looks "
            "at your firm choice first and this one second.")
    else:  # Declined
        outcome_block = (
            "You have DECLINED this offer, so we have closed it and "
            "released the place.\n\n"
            "This does not affect any of your other UCAS choices. If "
            "you declined by mistake, contact us at {contact} straight "
            "away — a decline can sometimes be reversed early in the "
            "cycle, but not indefinitely.").format(
                contact="admissions@teesside.ac.uk")

    code_suffix = f" ({choice.course_code})" if choice.course_code else ""
    context = {
        "university":          university,
        "student_id":          student.student_id,
        "first_name":          student.first_name,
        "full_name":           student.full_name,
        "course_name":         choice.course_name,
        "course_code":         choice.course_code or "—",
        "course_code_suffix":  code_suffix,
        "final_decision":      final_decision,
        "final_decision_upper": final_decision.upper(),
        "decision_status":     choice.decision_status,
        "offer_terms":         choice.offer_terms or "—",
        "outcome_block":       outcome_block,
        "cycle_year":          str(app.cycle_year),
        "entry_year":          str(choice.entry_year or app.cycle_year),
        "ucas_id":             app.ucas_id or "—",
        "contact_email":       "admissions@teesside.ac.uk",
    }

    from education_system.systems.sixth_form.domain.operations.communications.messages import (
        email_templates as _tpl,
    )
    msg = _tpl.send_from_template(
        "ucas_final_decision",
        context,
        to_name=student.full_name,
        to_address=student.email,
        student_id=student.student_id,
    )
    logger.info(
        "Sent %s final-decision email to %s (%s) for choice #%d "
        "as message #%d",
        final_decision, student.student_id, student.email,
        choice.choice_id, msg.message_id)


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

    from education_system.systems.sixth_form.domain.operations.communications.messages import (
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
