"""University-side UCAS management — view sixth-form UCAS
applications that name *this* university and record admissions
decisions against them.

The university doesn't own UCAS data; the sixth-form system does. This
module reads it through the sixth form's adapter and records our side:

* ``list_applicants(...)`` returns one row per sixth-form UCAS choice
  whose ``university`` matches the configured university name, joined
  with the parent application and the student record. Choices already
  placed (enrolled here) are left out unless ``include_placed=True``.
* ``get_full_application(application_id)`` returns the parent
  application plus all of the student's choices (so an admissions
  officer can see what other universities they applied to and which
  of those replied first).
* ``record_decision(choice_id, decision_status, ...)`` records the
  decision (``Conditional Offer`` / ``Unconditional Offer`` /
  ``Rejected``, plus offer terms) in our own tables — the structured
  offer terms (:mod:`.offer_terms`), who decided and when
  (:mod:`.decision_log`, which also writes the platform audit entry), the
  link to our own admissions application (:mod:`.ucas_links`) — e-mails
  the applicant, and publishes ``ucas.decision.recorded``. The sixth form
  applies that event to its own choice row and tells the learner and
  their tutor; we never write its row.

The sixth form is reached only through its registered adapter
(``platform.cross_system.adapters.registry``); nothing here imports it.

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


# ── The sixth form, reached through its adapter ───────────────────
#
# The university does not import the sixth form. Reads go through the
# sixth form's registered adapter; our decisions go on the cross-system bus
# (``ucas.decision.recorded``) and the sixth form applies them to its own
# row. ``_sf()`` keeps the shape the older callers in this package (results
# day, clearing) were written against, backed by the adapter.

def _sf_adapter():
    from education_system.platform.cross_system.adapters import registry
    from education_system.platform.cross_system.adapters.base import (
        AdapterError,
    )
    try:
        return registry.require("sixth_form")
    except AdapterError as e:
        raise UcasError(
            f"The sixth form's UCAS records are unavailable: {e}") from e


@dataclass
class ChoiceView:
    """A sixth-form UCAS choice as this university sees it.

    Same attribute names as the sixth form's own ``Choice`` so existing
    callers keep working. ``decision_status`` / ``offer_terms`` show *our*
    recorded decision for a choice at this university, which the sixth
    form's copy only reflects once it has applied the published event.
    """
    choice_id: int
    application_id: int
    choice_order: int
    university: str
    course_code: str | None
    course_name: str
    entry_year: int | None
    decision_status: str
    offer_terms: str | None
    final_decision: str | None
    notes: str | None
    choice_status: str = "Open"
    placed_at: str | None = None
    university_student_id: str | None = None
    reply_by: str | None = None
    decided_by: str | None = None
    decided_at: str | None = None
    student_id: str | None = None
    journey_id: str | None = None
    #: The sixth form's own copy of the decision, for a "pending" marker.
    sf_decision_status: str | None = None

    @property
    def is_placed(self) -> bool:
        return self.choice_status == "Placed"

    @property
    def decision_pending_at_sixth_form(self) -> bool:
        return (self.sf_decision_status is not None
                and self.sf_decision_status != self.decision_status)


@dataclass
class ApplicationView:
    """A sixth-form UCAS application, read through the adapter."""
    application_id: int
    student_id: str
    cycle_year: int
    ucas_id: str | None
    status: str
    personal_statement: str | None
    submitted_at: str | None
    notes: str | None


def _choice_view(d: dict) -> ChoiceView:
    return ChoiceView(
        choice_id=d["choice_id"], application_id=d["application_id"],
        choice_order=d.get("choice_order") or 0,
        university=d.get("university") or "",
        course_code=d.get("course_code"),
        course_name=d.get("course_name") or "",
        entry_year=d.get("entry_year"),
        decision_status=d.get("decision_status") or "Awaiting",
        offer_terms=d.get("offer_terms"),
        final_decision=d.get("final_decision"),
        notes=d.get("choice_notes"),
        choice_status=d.get("choice_status") or "Open",
        placed_at=d.get("placed_at"),
        university_student_id=d.get("university_student_id"),
        reply_by=d.get("reply_by"),
        decided_by=d.get("decided_by"),
        decided_at=d.get("decided_at"),
        student_id=d.get("student_id"),
        journey_id=d.get("journey_id"),
        sf_decision_status=d.get("decision_status"),
    )


def _app_view(d: dict) -> ApplicationView:
    return ApplicationView(
        application_id=d["application_id"], student_id=d["student_id"],
        cycle_year=d.get("cycle_year"), ucas_id=d.get("ucas_personal_id"),
        status=d.get("application_status") or "Draft",
        personal_statement=d.get("personal_statement"),
        submitted_at=d.get("submitted_at"), notes=d.get("app_notes"),
    )


def _our_decisions(choice_ids) -> dict:
    """``{choice_id: latest Decision}`` from our own decision log."""
    ids = [int(c) for c in choice_ids if c is not None]
    if not ids:
        return {}
    try:
        from education_system.systems.university.domains.admissions.domain.ucas import (
            decision_log as _log,
        )
        return _log.latest_for_choices(ids)
    except Exception:
        logger.exception("Could not read the UCAS decision log")
        return {}


def _overlay(target, decision, *, ours: bool) -> None:
    """Show our recorded decision on *target* (a choice view or applicant)."""
    if decision is None or not ours:
        return
    target.decision_status = decision.decision_status
    if decision.offer_terms is not None:
        target.offer_terms = decision.offer_terms
    if hasattr(target, "decided_by"):
        target.decided_by = decision.decided_by
        target.decided_at = decision.decided_at


def _placed_here(choice_ids) -> dict:
    """``{choice_id: uni_student_id}`` for choices we have enrolled from."""
    ids = [int(c) for c in choice_ids if c is not None]
    if not ids:
        return {}
    try:
        from education_system.systems.university.domains.admissions.domain.ucas import (
            ucas_links as _links,
        )
        return _links.placed_by_choice(ids)
    except Exception:
        logger.exception("Could not read the UCAS link records")
        return {}


def _is_ours(university: str | None, our_name: str | None = None) -> bool:
    name = (our_name if our_name is not None else _resolve_uni_name(None))
    return (university or "").strip().lower() == (name or "").strip().lower()


def _get_choice(choice_id: int) -> ChoiceView | None:
    """One choice, with our recorded decision overlaid."""
    d = _sf_adapter().ucas_choice(int(choice_id))
    if d is None:
        return None
    view = _choice_view(d)
    _overlay(view, _our_decisions([view.choice_id]).get(view.choice_id),
             ours=_is_ours(view.university))
    placed = _placed_here([view.choice_id]).get(view.choice_id)
    if placed:
        view.choice_status = "Placed"
        view.university_student_id = view.university_student_id or placed
    return view


class _SixthFormUcas:
    """The handful of sixth-form UCAS calls this package used to import,
    now answered by the sixth form's adapter. Writes are limited to the
    ones the university owns synchronously (reply, application status)."""

    def init_db(self) -> None:
        return None

    def get_choice(self, choice_id: int) -> ChoiceView | None:
        return _get_choice(choice_id)

    def get_application(self, application_id: int) -> ApplicationView | None:
        d = _sf_adapter().ucas_application(int(application_id))
        return _app_view(d) if d else None

    def list_choices(self, application_id: int) -> list[ChoiceView]:
        d = _sf_adapter().ucas_application(int(application_id))
        if not d:
            return []
        views = [_choice_view(c) for c in d.get("choices") or []]
        ours = _our_decisions([v.choice_id for v in views])
        name = _resolve_uni_name(None)
        for v in views:
            _overlay(v, ours.get(v.choice_id), ours=_is_ours(v.university, name))
        return views

    def update_application(self, application_id: int,
                           data: dict) -> ApplicationView:
        unsupported = set(data) - {"status"}
        if unsupported:
            raise UcasError(
                "Only the application status is the university's to set "
                f"(not {', '.join(sorted(unsupported))}).")
        try:
            d = _sf_adapter().ucas_set_application_status(
                int(application_id), data["status"])
        except UcasError:
            raise
        except Exception as e:
            raise UcasError(str(e)) from e
        return _app_view(d)

    def update_choice(self, choice_id: int, data: dict, *,
                      issued_by_university: bool = True) -> ChoiceView:
        """Only the applicant's reply. Decisions go through
        :func:`record_decision`, which publishes them."""
        unsupported = set(data) - {"final_decision"}
        if unsupported:
            raise UcasError(
                "Decisions are recorded with record_decision(); this call "
                f"cannot set {', '.join(sorted(unsupported))}.")
        try:
            _sf_adapter().ucas_record_reply(int(choice_id),
                                            data.get("final_decision"))
        except UcasError:
            raise
        except Exception as e:
            raise UcasError(str(e)) from e
        out = _get_choice(choice_id)
        if out is None:
            raise UcasError(f"No UCAS choice with id {choice_id}")
        return out


_SF_UCAS = _SixthFormUcas()


def _sf() -> _SixthFormUcas:
    return _SF_UCAS


@dataclass
class _Learner:
    """The few learner fields an e-mail needs, from the adapter summary."""
    student_id: str
    first_name: str
    full_name: str
    email: str | None

    @classmethod
    def of(cls, student_id: str | None) -> "_Learner | None":
        d = _learner(student_id)
        if not d:
            return None
        return cls(student_id=d.get("student_id") or d.get("id"),
                   first_name=d.get("first_name") or "",
                   full_name=d.get("full_name") or "",
                   email=d.get("email"))


def _learner(student_id: str | None) -> dict | None:
    """The sixth form's summary of a learner (names, email, dob …)."""
    if not student_id:
        return None
    try:
        return _sf_adapter().learner_summary(str(student_id))
    except UcasError:
        raise
    except Exception:
        logger.exception("Could not read sixth-form learner %s", student_id)
        return None


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
    # The link's own state.
    choice_status: str = "Open"          # 'Placed' once enrolled here
    placed_at: str | None = None
    university_student_id: str | None = None
    reply_by: str | None = None
    decided_by: str | None = None
    decided_at: str | None = None
    journey_id: str | None = None
    #: The sixth form's copy of the decision (may lag ours until it has
    #: applied the published ``ucas.decision.recorded`` event).
    sf_decision_status: str | None = None

    @property
    def is_placed(self) -> bool:
        return self.choice_status == "Placed"

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
        from education_system.systems.university.application.programmes import prospectus
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
    include_placed: bool = False,
) -> list[Applicant]:
    """Return one ``Applicant`` per sixth-form UCAS choice naming this
    university. Filter by decision status, parent application status,
    cycle year, and a free-text search across student name / student id /
    course name.

    Choices already *Placed* — the learner was enrolled here — are history
    rather than applicants, and are left out unless ``include_placed``.
    The decision shown is ours (from the decision log), so a decision just
    recorded appears at once, before the sixth form has applied it.
    """
    name = _resolve_uni_name(university_name)
    if not name:
        raise UcasError("University name is empty — set "
                         "UNIVERSITY_NAME or pass university_name=")
    if decision_status and decision_status not in DECISION_STATUSES:
        raise UcasError(
            f"decision_status must be one of: {', '.join(DECISION_STATUSES)}")
    if app_status and app_status not in APP_STATUSES:
        raise UcasError(
            f"app_status must be one of: {', '.join(APP_STATUSES)}")

    try:
        rows = _sf_adapter().ucas_choices_for_institution(
            {name}, include_placed=include_placed)
    except UcasError:
        raise
    except Exception as e:
        raise UcasError(f"Could not read the sixth form's UCAS choices: {e}") from e
    ours = _our_decisions([r["choice_id"] for r in rows])
    # Enrolled here, per our own link record — the sixth form marks the
    # choice Placed only once it has applied the enrolment event.
    placed_here = _placed_here([r["choice_id"] for r in rows])

    needle = (search or "").strip().lower()
    out: list[Applicant] = []
    for r in rows:
        if app_status and r.get("application_status") != app_status:
            continue
        if cycle_year is not None and r.get("cycle_year") != cycle_year:
            continue
        if needle and not any(
                needle in str(r.get(k) or "").lower()
                for k in ("student_id", "student_name", "course_name")):
            continue
        applicant = Applicant(
            choice_id=r["choice_id"],
            application_id=r["application_id"],
            choice_order=r.get("choice_order") or 0,
            course_code=r.get("course_code"),
            course_name=r.get("course_name") or "",
            entry_year=r.get("entry_year"),
            decision_status=r.get("decision_status") or "Awaiting",
            offer_terms=r.get("offer_terms"),
            final_decision=r.get("final_decision"),
            choice_notes=r.get("choice_notes"),
            cycle_year=r.get("cycle_year"),
            app_status=r.get("application_status") or "Draft",
            ucas_id=r.get("ucas_personal_id"),
            submitted_at=r.get("submitted_at"),
            app_notes=r.get("app_notes"),
            personal_statement=r.get("personal_statement"),
            student_id=r["student_id"],
            student_name=(r.get("student_name") or "").strip(),
            student_email=r.get("student_email"),
            student_dob=r.get("student_dob"),
            student_status=r.get("student_status") or "Active",
            choice_status=r.get("choice_status") or "Open",
            placed_at=r.get("placed_at"),
            university_student_id=r.get("university_student_id"),
            reply_by=r.get("reply_by"),
            decided_by=r.get("decided_by"),
            decided_at=r.get("decided_at"),
            journey_id=r.get("journey_id"),
            sf_decision_status=r.get("decision_status"),
        )
        _overlay(applicant, ours.get(applicant.choice_id), ours=True)
        if applicant.choice_id in placed_here:
            if not include_placed:
                continue
            applicant.choice_status = "Placed"
            applicant.university_student_id = (
                applicant.university_student_id
                or placed_here[applicant.choice_id])
        if decision_status and applicant.decision_status != decision_status:
            continue
        out.append(applicant)
    logger.debug(
        "list_applicants(name=%r, dec=%r, app=%r, cy=%r) -> %d",
        name, decision_status, app_status, cycle_year, len(out))
    return out


def get_full_application(application_id: int) -> FullApplication | None:
    try:
        d = _sf_adapter().ucas_application(int(application_id))
    except UcasError:
        raise
    except Exception as e:
        raise UcasError(str(e)) from e
    if d is None:
        return None
    if not d.get("student_known"):
        raise UcasError(
            f"Application {application_id} references unknown "
            f"student {d.get('student_id')}")
    choices = _sf().list_choices(int(application_id))
    uni_name = _resolve_uni_name(None)
    our = next((c for c in choices if _is_ours(c.university, uni_name)
                and not c.is_placed), None) or next(
        (c for c in choices if _is_ours(c.university, uni_name)), None)
    return FullApplication(
        application_id=d["application_id"],
        student_id=d["student_id"],
        student_name=d.get("student_name") or "",
        student_email=d.get("student_email"),
        student_dob=d.get("student_dob"),
        cycle_year=d.get("cycle_year"),
        ucas_id=d.get("ucas_personal_id"),
        app_status=d.get("application_status") or "Draft",
        submitted_at=d.get("submitted_at"),
        personal_statement=d.get("personal_statement"),
        app_notes=d.get("app_notes"),
        choices=choices,
        our_choice_id=(our.choice_id if our is not None else None),
        subjects=list(d.get("subjects") or []),
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

    The decision is recorded in *our* tables (:mod:`.decision_log`, plus
    the structured :mod:`.offer_terms`) and published on the cross-system
    bus as ``ucas.decision.recorded``. The sixth form applies it to its own
    ``ucas_choices`` row, idempotently — the university no longer writes
    that row. Returns a :class:`ChoiceView` showing the decision as
    recorded here, so a screen re-reading it sees it at once. Raises
    :class:`UcasError` for invalid input, an unknown or already-placed
    choice, or a decision that could not be recorded.

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

    current = None
    try:
        current = _get_choice(choice_id)
    except UcasError:
        raise
    except Exception as e:
        raise UcasError(str(e)) from e
    if current is None:
        raise UcasError(f"No UCAS choice with id {choice_id}")
    if current.is_placed:
        raise UcasError(
            "This applicant has already been enrolled from this choice; "
            "its decision is closed.")
    sf_student_id: str | None = current.student_id

    # Our record of the decision — the decision itself now. The sixth form
    # no longer has its row written by us: it receives the event below and
    # applies it to its own copy. If this fails, nothing was decided.
    from education_system.systems.university.domains.admissions.domain.ucas import (
        decision_log as _log,
    )
    try:
        logged = _log.record(
            sf_choice_id=current.choice_id,
            sf_application_id=current.application_id,
            sf_student_id=sf_student_id,
            decision_status=decision_status,
            offer_terms=offer_terms,
            notes=notes,
            decided_by=issued_by,
        )
    except Exception as e:
        logger.exception("Could not record UCAS decision on choice #%d",
                         choice_id)
        raise UcasError(f"The decision could not be recorded: {e}") from e
    logger.info(
        "Recorded UCAS decision #%d: choice #%d -> %s (offer_terms=%s)",
        logged.decision_id, choice_id, decision_status, bool(offer_terms))

    # The structured terms behind the one-line summary, already validated
    # above. Best-effort — a failure storing the scholarship flag must not
    # undo the decision.
    if issue_terms is not None:
        try:
            from education_system.systems.university.domains.admissions.domain.ucas import (
                offer_terms as _terms,
            )
            _terms.save_terms(current.choice_id, issue_terms,
                              issued_by=issued_by)
        except Exception:
            logger.exception(
                "Could not store offer terms for choice #%d "
                "(decision recorded)", choice_id)

    # Tell the sixth form. Durable: it applies the decision to its own row
    # the next time its drainer runs, idempotently on the decision id.
    _publish_decision(current, logged, issue_terms)

    # What this call returns, and what every step below works from: the
    # choice as it now stands *here*.
    out = current
    out.decision_status = decision_status
    if offer_terms is not None:
        out.offer_terms = offer_terms
    if notes is not None:
        out.notes = notes
    out.decided_by = logged.decided_by
    out.decided_at = logged.decided_at

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

    # "Every choice decided -> Replied" is now worked out by the sixth form
    # when it applies this decision (``ucas.promote_to_replied``), because
    # it is the one holding every university's answers.

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



def _conditions_for(terms: dict | None) -> list | None:
    """Structured offer conditions for the event, from the issued terms."""
    if not terms:
        return None
    given = terms.get("conditions")
    if isinstance(given, list):
        return given or None
    # Same shape as structured rows (platform.cross_system.offer_conditions),
    # so the sixth form receives one condition format whichever way the
    # offer was entered; unreadable prose arrives as ``other_text``.
    from education_system.platform.cross_system import (
        offer_conditions as _oc,
    )
    out: list = []
    for key in ("grade_requirement", "grade_alternative"):
        text = (terms.get(key) or "").strip()
        if text:
            rows = _oc.conditions_from_text(text)
            if key == "grade_alternative":
                for r in rows:
                    r["alternative"] = True
            out.extend(rows)
    return out or None


def _publish_decision(choice: ChoiceView, logged, terms: dict | None) -> None:
    """Publish ``ucas.decision.recorded`` for the sixth form to apply."""
    journey_id = choice.journey_id
    if not journey_id and choice.student_id:
        try:
            summary = _learner(choice.student_id)
            journey_id = (summary or {}).get("journey_id")
        except Exception:
            journey_id = None
    try:
        from education_system.platform.integrations.external import (
            cross_system_bus as _bus,
        )
        _bus.publish_cross_system(
            "ucas.decision.recorded",
            source_system="university",
            source_module=__name__,
            target_system="sixth_form",
            journey_id=journey_id,
            idempotency_key=f"ucas.decision.recorded:{logged.decision_id}",
            choice_id=choice.choice_id,
            application_id=choice.application_id,
            sf_student_id=choice.student_id,
            decision_id=logged.decision_id,
            decision_status=logged.decision_status,
            offer_summary=logged.offer_terms,
            conditions=_conditions_for(terms),
            reply_by=(terms or {}).get("reply_deadline"),
            notes=logged.notes,
            decided_by=logged.decided_by,
            decided_at=logged.decided_at,
            university=choice.university,
        )
    except Exception:
        # Our decision stands and is logged; the sixth form's copy will
        # stay behind until this is re-published (``republish_decision``).
        logger.exception(
            "UNDELIVERED DECISION: could not publish decision #%s on "
            "choice #%d to the sixth form", logged.decision_id,
            choice.choice_id)


def republish_decision(choice_id: int) -> bool:
    """Publish our latest decision on *choice_id* again.

    For a decision whose publish failed. The sixth form ignores one it has
    already applied, so this is always safe.
    """
    from education_system.systems.university.domains.admissions.domain.ucas import (
        decision_log as _log,
        offer_terms as _terms,
    )
    logged = _log.last_decision(int(choice_id))
    choice = _get_choice(int(choice_id))
    if logged is None or choice is None:
        return False
    issued = None
    try:
        t = _terms.get_terms(int(choice_id))
        issued = t.as_dict() if t is not None else None
    except Exception:
        issued = None
    _publish_decision(choice, logged, issued)
    return True


def _promote_to_replied(application_id: int) -> bool:
    """Move a Submitted application to Replied once nothing is awaited.

    The sixth form now does this itself when it applies a decision; this
    remains for callers that want to re-evaluate on demand, judged on the
    decisions as *we* have recorded them.
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
#: A firm choice in one of these states frees the insurance place.
_FIRM_LOST = ("Rejected", "Withdrawn")


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
    reply — or their Insurance reply once the Firm has been declined or
    withdrawn. A place is confirmed by the institution holding it.
    """
    choice, _application = _application_for_choice(choice_id)
    university = _resolve_uni_name(None)
    if (choice.university or "").strip().lower() != university.lower():
        raise UcasError(
            f"This choice is at {choice.university}, not {university}. "
            "A place is confirmed by the university holding it.")
    if choice.final_decision == "Insurance":
        # The insurance place is the one held for a missed firm: it can be
        # confirmed once the firm offer has been turned down on results,
        # never alongside a firm that may still come good.
        firm = next((c for c in _sf().list_choices(choice.application_id)
                     if c.final_decision == "Firm"), None)
        if firm is not None and firm.decision_status not in _FIRM_LOST:
            raise UcasError(
                "This is the applicant's Insurance choice. It can be "
                f"confirmed once their Firm choice ({firm.university}) "
                "has been declined — it is currently "
                f"'{firm.decision_status}'.")
    elif choice.final_decision != "Firm":
        raise UcasError(
            "Only a Firm or Insurance choice can be confirmed — this one "
            f"is {choice.final_decision or 'not replied to'}. Record the "
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
        # And any parent login that existed only to follow this learner.
        # One covering a sibling still at the college is left alone — the
        # sixth form makes that call, not us.
        _sf_adapter().close_leaver_logins(student_id)
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
    student = _Learner.of(app.student_id) if app else None
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
    message_id = _sf_adapter().send_learner_template(
        student.student_id, "ucas_cycle_outcome", context)
    logger.info(
        "Sent %s cycle-outcome email to %s for application #%d as "
        "message #%s", status, student.student_id,
        choice.application_id, message_id)


def _send_final_decision_email(choice, final_decision: str) -> None:
    """Confirm a Firm / Insurance / Declined reply to the student.

    Same shape as :func:`_send_decision_email` — renders a sixth-form
    template against the student on the parent application. Best-effort;
    the caller catches.
    """
    sf = _sf()
    app = sf.get_application(choice.application_id)
    student = _Learner.of(app.student_id) if app else None
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

    message_id = _sf_adapter().send_learner_template(
        student.student_id, "ucas_final_decision", context)
    logger.info(
        "Sent %s final-decision email to %s (%s) for choice #%d "
        "as message #%s",
        final_decision, student.student_id, student.email,
        choice.choice_id, message_id)


def _send_decision_email(choice, decision_status: str,
                          offer_terms: str | None,
                          *, template: str) -> None:
    """Render and send one of the decision templates
    (``student_offer`` / ``student_rejection``) to the sixth-form
    student. Reads the parent application + student via the sf API.
    Best-effort — caller is expected to catch."""
    sf = _sf()
    app = sf.get_application(choice.application_id)
    student = _Learner.of(app.student_id) if app else None
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

    message_id = _sf_adapter().send_learner_template(
        student.student_id, template, context)
    logger.info(
        "Sent %s (%s) email to %s (%s) for choice #%d as message #%s",
        decision_status, template, student.student_id, student.email,
        choice.choice_id, message_id,
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
