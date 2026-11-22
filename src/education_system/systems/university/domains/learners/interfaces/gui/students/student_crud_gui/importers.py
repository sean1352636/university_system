# Auto-generated module (split from student_crud_gui.py)
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import logging
import random
import secrets
import json
import csv
from education_system.systems.university.infrastructure.database.db import sqlite3
from datetime import datetime
from education_system.platform.delivery.gui.tk_callback_filter import install_clean_close as _install_clean_close

from education_system.systems.university.infrastructure.i18n import get_text as _t
from education_system.systems.university.infrastructure.database.db import get_db_connection, get_connection, transaction, foreign_keys_off
from education_system.systems.university.infrastructure.sql_safety import (
    validate_table_name,
    validate_column_name,
    SQLIdentifierError,
)

logger = logging.getLogger("education_system.systems.university.domains.learners.interfaces.gui.students.student_crud_gui")

try:
    from education_system.systems.university.infrastructure.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False

from .widgets import _DOBPicker, _safe_set_combobox, _safe_entry_insert

from education_system.systems.university.domains.admissions.domain.services.admissions_selection import (
    normalise_grade as _normalise_grade,
    enrol_student_in_curriculum as _enrol_student_in_curriculum,
    ensure_module_chat_rooms_and_join,
    get_course as _get_course,
)
from education_system.systems.university.services.student_provisioning import (
    compute_age as _compute_age,
    default_student_password as _default_student_password,
    provision_student_login as _provision_student_login,
)


#: Eligibility failures that do not stop an *import*.
#:
#: ``not_transferred`` fails exactly when the learner has already been
#: handed over — which on this screen is the precondition, not an
#: objection. The check belongs to the sixth form's progression board,
#: where it means "do not submit this learner twice"; read from here it
#: was refusing to import anybody the sixth form had successfully sent,
#: which is everybody this screen exists for. A learner could be handed
#: over and then never admitted, with the tool for admitting them citing
#: the handover as the reason.
#:
#: The double-import it warns about is still prevented, by the two checks
#: that actually test for it: ``not_already_here`` (does the journey
#: already carry a university slot) and the ``converted_student_id``
#: guard above, which catches an application already enrolled.
_IMPORT_EXEMPT_CHECKS = frozenset({"not_transferred"})


def _import_blockers(readiness):
    """Blocking failures that are real objections to importing."""
    if readiness is None:
        return []
    return [c for c in readiness.blockers
            if c.key not in _IMPORT_EXEMPT_CHECKS]



def _awaiting_admission(readiness) -> bool:
    """Handed over by the college, with no university record to show.

    True when the only thing standing between this applicant and a
    student record is us. ``not_transferred`` failing means the college
    has completed the handover; ``not_already_here`` passing means no
    university slot has been filled. Together they describe a learner who
    has left one system without arriving at the next — the same failure
    the sixth form calls Stranded, seen from the receiving end.
    """
    if readiness is None:
        return False
    failed = {c.key for c in readiness.checks if not c.passed}
    if "not_transferred" not in failed:
        return False
    if "not_already_here" in failed:
        return False
    # Anything else outstanding is a real objection; report that instead.
    return not [c for c in readiness.blockers
                if c.key not in _IMPORT_EXEMPT_CHECKS]


def _import_title():
    """Dialog title. A function, not a constant: ``_t`` resolves against
    the locale in force *now*, and a module-level constant would freeze
    whichever locale happened to be active at import."""
    return _t(
        'gui.learners.students.student_crud_gui.importers.dialogs.admit_from_ucas',
        default="Admit from UCAS")


def _sixth_form_adapter():
    """The sixth form, reached through the platform adapter registry —
    the university never imports it."""
    from education_system.platform.cross_system.adapters import registry
    return registry.require("sixth_form")


def _learner_view(summary):
    """Attribute access over the sixth form's ``learner_summary`` dict, in
    the shape this picker used to read off the sixth form's Student."""
    if not summary:
        return None
    from types import SimpleNamespace
    return SimpleNamespace(
        student_id=summary.get("student_id") or summary.get("id"),
        title=summary.get("title"),
        first_name=summary.get("first_name"),
        middle_name=summary.get("middle_name"),
        last_name=summary.get("last_name"),
        full_name=summary.get("full_name") or " ".join(
            p for p in (summary.get("first_name"), summary.get("last_name")) if p),
        gender=summary.get("gender"),
        date_of_birth=summary.get("date_of_birth") or summary.get("dob"),
        email=summary.get("email"),
        status=summary.get("status"),
        journey_id=summary.get("journey_id"),
        subjects=list(summary.get("subjects") or []),
    )


def _ucas_applicants():
    """Everyone applying to this university, from every source system.

    Not just the sixth form: FE College uses the same UCAS route, and a
    completed higher apprentice can progress onto a degree or top-up.
    ``applicants.list_all_applicants`` merges the UCAS rows with the
    cross-system handover transitions and returns one normalised shape,
    already ordered with the actionable people first.
    """
    from education_system.systems.university.services.bus import admissions_bus
    return admissions_bus.list_applicants()


def _admission_application_for(journey_id):
    """The staged admission application for a journey, if any."""
    if not journey_id:
        return None
    try:
        from education_system.systems.university.services.bus import admissions_bus
        return admissions_bus.application_for_journey(journey_id)
    except Exception:
        logger.debug("Could not look up the admission application",
                     exc_info=True)
        return None


def _actor_name(self):
    """Who is doing this, for the audit line on the clear-down."""
    for attr in ("current_user", "user", "auth"):
        holder = getattr(self, attr, None)
        user = getattr(holder, "current_user", holder)
        if isinstance(user, dict):
            return user.get("username") or user.get("display_name")
        if isinstance(user, str):
            return user
    return None


def _university_student_exists(student_id) -> bool:
    """Is there really a student record behind a converted application?

    An application can carry ``converted_student_id`` for a student that no
    longer exists — deleted, or never created if the conversion half-failed.
    The picker used to trust the field and refuse the import, which left the
    operator told about a record they could not find.
    """
    if not student_id:
        return False
    try:
        from education_system.systems.university.infrastructure.database.db import (
            get_connection,
        )
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT 1 FROM students WHERE student_id = ?",
                (str(student_id),),
            ).fetchone()
        finally:
            conn.close()
        return row is not None
    except Exception:
        logger.exception("Could not check whether student %s exists",
                         student_id)
        # Unverifiable: treat as present, so a database problem never
        # invites a duplicate record.
        return True


def _report_ucas_clear(summary, parent):
    """Tell the operator what the clear-down did."""
    if summary is None:
        messagebox.showwarning(
            _import_title(),
            "The student is enrolled, but their UCAS application could not "
            "be cleared. See the log; they may still appear in this list.",
            parent=parent)
        return
    from education_system.systems.university.services.bus import ucas_bus
    detail = ucas_bus.describe(summary)
    if summary.get("errors"):
        messagebox.showwarning(_import_title(),
                               f"UCAS clear-down finished with problems:\n\n{detail}",
                               parent=parent)
    elif summary.get("choices_removed") or summary.get("choices_placed"):
        messagebox.showinfo(_import_title(), detail, parent=parent)


def _clear_ucas_application(sf_student_id, uni_student_id, *, actor=None):
    """Close the applicant's UCAS application to us, after they are admitted.

    Admission is what ends an application. Without this the learner keeps
    appearing in "Admit from UCAS" for ever — listed as *Enrolled*, with
    Admit refusing them as an existing student, which reports a problem the
    screen offers no way to clear.

    Best-effort: the student exists by the time this runs, and a tidy-up
    failure must not present a successful admission as a failed one.
    """
    if not sf_student_id:
        return None
    try:
        from education_system.systems.university.services.bus import ucas_bus
        summary = ucas_bus.clear_after_admission(
            sf_student_id, uni_student_id, actor=actor)
        logger.info("UCAS clear-down for %s -> %s: %s",
                    sf_student_id, uni_student_id, ucas_bus.describe(summary))
        return summary
    except Exception:
        logger.exception(
            "Could not clear the UCAS application for %s after admitting "
            "them as %s", sf_student_id, uni_student_id)
        return None


def _convert_via_admissions(application_id, parent):
    """Enrol through the supported admissions route.

    ``convert_to_student`` creates the student, registration, history and
    outbox event in one transaction, filling every field from the
    application's accepted choice — so there is no form to complete and
    no chance of the two records disagreeing. It refuses unless the
    application is genuinely ready, which is the whole point of
    preferring it.

    Returns the new student id, or ``None`` if it could not run.
    """
    from education_system.systems.university.services.bus import admissions_bus
    try:
        issues = admissions_bus.readiness_issues(application_id)
    except Exception as exc:
        logger.exception("Readiness check failed for application %s",
                         application_id)
        messagebox.showerror(_import_title(),
                             f"Could not check the application: {exc}",
                             parent=parent)
        return None
    if issues:
        messagebox.showwarning(
            _import_title(),
            f"Application #{application_id} is not ready to enrol:\n\n"
            + "\n".join(f"  • {i}" for i in issues)
            + "\n\nComplete these in Admissions, or use the manual route "
              "below to create the student without those checks.",
            parent=parent)
        return None
    try:
        student_id = admissions_bus.convert_to_student(application_id)
    except Exception as exc:
        logger.exception("convert_to_student failed for %s", application_id)
        messagebox.showerror(_import_title(),
                             f"Could not enrol from the application: {exc}",
                             parent=parent)
        return None
    messagebox.showinfo(
        _import_title(),
        f"Enrolled from application #{application_id}.\n\n"
        f"Student {student_id} was created with their programme, academic "
        f"year and identity taken from the accepted choice — nothing to "
        f"fill in.",
        parent=parent)
    return student_id


def _qualification_grades(record):
    """``{subject: grade}`` from a handover record, achieved before predicted.

    Reads the assembled ``SIXTH_FORM_TO_UNIVERSITY`` record rather than
    re-querying the sixth form's assessment modules. That is not only
    cheaper — it is the same data the *event* route carries, so the two
    routes can no longer disagree about what grades a learner holds.
    """
    grades: dict[str, str] = {}
    for key in ("achieved_qualifications", "predicted_qualifications"):
        for row in record.get(key) or []:
            subject = (row.get("subject") or "").strip()
            grade = (row.get("grade") or "").strip()
            if subject and grade:
                grades.setdefault(subject.lower(), grade)
    return grades


def _existing_university_applications(sf_student_ids):
    """``{sf_student_id: (journey_id, application_or_None)}`` for a cohort.

    The eligibility gate runs source-side and cannot see the university's
    admissions tables. This is the destination half of "protection against
    an existing application/student": a learner the bus already staged as
    an applicant must be *converted*, not enrolled a second time from
    scratch.

    Two batched queries for the whole list, not two per learner — a fresh
    connection to the university database costs about a tenth of a second,
    and this runs for every Year 13 student the moment the picker opens.
    """
    ids = list(sf_student_ids)
    out = {sid: (None, None) for sid in ids}
    if not ids:
        return out
    try:
        from education_system.platform.cross_system import identity_service
        journeys = identity_service.find_by_students("sixth_form", ids)
    except Exception:
        logger.exception(
            "Could not resolve journeys for the Year 13 cohort")
        return out

    by_journey = {}
    for sid, journey in journeys.items():
        journey_id = journey.get("journey_id")
        out[sid] = (journey_id, None)
        if journey_id:
            by_journey.setdefault(journey_id, []).append(sid)
    if not by_journey:
        return out

    from education_system.systems.university.services.bus import admissions_bus
    applications = admissions_bus.applications_for_journeys(
        by_journey.keys())
    for journey_id, application in applications.items():
        for sid in by_journey.get(journey_id, ()):
            out[sid] = (journey_id, application)
    return out


def _select_course_for(fields, course_code):
    """Point the course combobox at the learner's firm-choice course.

    Silent when the code names nothing in the live catalogue: the sixth
    form records a UCAS course code, which is not guaranteed to be one of
    this university's internal codes, and guessing would be worse than
    leaving the operator to choose.
    """
    code = (course_code or "").strip().upper()
    combo = fields.get('course')
    if not code or combo is None:
        return False
    try:
        for label in combo['values']:
            if str(label).split(' - ', 1)[0].strip().upper() == code:
                combo.set(label)
                return True
    except Exception:
        logger.debug("Could not pre-select course %s", code, exc_info=True)
    return False


def _open_sixth_form_import_dialog(parent_dialog, fields):
    """Modal picker of sixth-form leavers who are ready to be admitted.

    This used to list *every* active Year 13 student and let any of them
    be turned into an enrolled undergraduate. It now runs
    ``handover_eligibility`` over each candidate and shows the answer:
    whether this university is their confirmed destination, whether they
    hold an accepted offer, whether its conditions and results are
    confirmed, whether the handover consent exists, and whether they are
    already here. A learner with a blocking failure cannot be imported;
    one with only advisory gaps can be, after the operator has seen them.

    On confirm, the parent create-student dialog is pre-filled from the
    assembled handover record — identity, firm-choice course and entry
    year, and A-level subjects with achieved (falling back to predicted)
    grades — and the released payload is stashed on the dialog for the
    save handler. The UCAS tariff recomputes from the filled grades; visa
    details are intentionally left to the user.

    Errors are surfaced via messagebox and logged; the parent dialog
    is left untouched if anything goes wrong.
    """
    try:
        sixth_form = _sixth_form_adapter()
        right_to_study_note = sixth_form.right_to_study_note()
    except Exception:
        logger.exception("Sixth-form adapter not available")
        messagebox.showerror(
            _import_title(),
            _t('gui.learners.students.student_crud_gui.importers.dialogs.could_not_load_the_sixth_form_student_module_make_sure_the_sixth', default="Could not load the sixth-form student module. "
            "Make sure the sixth-form system is installed alongside "
            "the university system."),
            parent=parent_dialog,
        )
        return

    # Who applied *here*, per UCAS — not "everyone in Year 13". The
    # decision on the choice is what makes someone admissible, and this
    # scope also excludes learners who chose other universities.
    try:
        applicants = _ucas_applicants()
    except Exception as e:
        logger.exception("Could not load UCAS applicants")
        messagebox.showerror(
            _import_title(),
            f"Could not load UCAS applicants: {e}",
            parent=parent_dialog,
        )
        return

    if not applicants:
        messagebox.showinfo(
            _import_title(),
            "No UCAS applicants name this university yet.\n\n"
            "Applicants appear here once a learner lists this university "
            "as a choice in the sixth form's UCAS module.",
            parent=parent_dialog,
        )
        return

    # Join each applicant to the sixth form's own readiness assessment.
    # An applicant with no sixth-form record still lists — they simply
    # have no handover to check, and the manual route can still take them.
    rows = []
    for applicant in applicants:
        readiness = None
        # The sixth form's handover checks only describe sixth-form
        # learners. An FE or apprenticeship applicant is assessed by their
        # own route, so leave readiness unset rather than reporting a
        # sixth-form verdict about somebody who was never there.
        if applicant.source_system == "sixth_form":
            try:
                readiness = sixth_form.handover_readiness(applicant.student_id)
            except Exception:
                logger.debug("Readiness lookup failed for %s",
                             applicant.student_id, exc_info=True)
        student = None
        if applicant.source_system == "sixth_form":
            try:
                student = _learner_view(
                    sixth_form.learner_summary(applicant.student_id))
            except Exception:
                logger.debug("No sixth-form record for %s",
                             applicant.student_id, exc_info=True)
        rows.append((applicant, student, readiness))

    # Destination-side check, folded in as one more advisory/blocking
    # reason per student. Done once here rather than per selection so the
    # duplicate warning is visible in the list, not only after clicking.
    by_id = {}
    admissions_side = _existing_university_applications(
        [a.student_id for a, _s, _r in rows])
    for applicant, student, readiness in rows:
        journey_id, application = admissions_side.get(
            applicant.student_id, (None, None))
        by_id[applicant.student_id] = (applicant, student, readiness,
                                       journey_id, application)

    picker = tk.Toplevel(parent_dialog)
    picker.title(_t(
        'gui.learners.students.student_crud_gui.importers.windows.admit_from_ucas',
        default="Admit from UCAS — applicants to this university"))
    picker.geometry("1120x640")
    picker.minsize(960, 540)
    picker.transient(parent_dialog)
    try:
        picker.grab_set()
    except tk.TclError:
        pass

    ready_count = sum(1 for _a, _s, r in rows if r is not None and r.ready)
    staged_count = sum(1 for v in by_id.values() if v[4])
    header = ttk.Frame(picker, padding=(12, 10, 12, 4))
    header.pack(fill=tk.X)
    ttk.Label(
        header,
        text=(f"{len(rows)} UCAS applicant(s) to this university; "
              f"{ready_count} ready to hand over, {staged_count} with an "
              f"admission application already staged.\n"
              f"Where an application exists and is ready, Admit uses it — "
              f"the student is created from the accepted choice with "
              f"nothing to fill in. Otherwise the form below is pre-filled "
              f"from the UCAS choice and the sixth-form handover."),
        font=('Arial', 10), wraplength=990, justify=tk.LEFT,
    ).pack(side=tk.LEFT)

    body = ttk.Frame(picker, padding=(12, 4, 12, 4))
    body.pack(fill=tk.BOTH, expand=True)

    cols = ("status", "source", "student_id", "name", "decision", "course",
            "issues")
    headings = {
        "status":     "Status",
        "source":     "From",
        "student_id": "Applicant",
        "name":       "Name",
        "decision":   "Decision",
        "course":     "Course applied for",
        "issues":     "Outstanding",
    }
    widths = {"status": 85, "source": 115, "student_id": 100, "name": 175,
              "decision": 175, "course": 215, "issues": 230}

    tree = ttk.Treeview(body, columns=cols, show='headings',
                         selectmode='browse', height=12)
    for c in cols:
        tree.heading(c, text=headings[c])
        tree.column(c, width=widths[c],
                     anchor=tk.W if c in ('student_id', 'name', 'course',
                                          'issues')
                                  else tk.CENTER)
    vsb = ttk.Scrollbar(body, orient='vertical', command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    vsb.pack(side=tk.RIGHT, fill=tk.Y)
    tree.tag_configure("blocked", foreground="#8b0000")
    tree.tag_configure("check", foreground="#8a6d00")
    tree.tag_configure("ready", foreground="#14532d")

    tree.tag_configure("supported", foreground="#0b5394")
    # Louder than "supported": this learner is off their college's roll
    # and waiting on us, which is the one state on this screen that gets
    # worse on its own.
    tree.tag_configure("awaiting", foreground="#8a6d00")

    for sid, (applicant, student, readiness, _jid, application) in by_id.items():
        blocked = bool(_import_blockers(readiness))
        outstanding = []
        if readiness is not None:
            outstanding = [c.label for c in _import_blockers(readiness)]
            outstanding += [c.label for c in readiness.warnings]
        else:
            outstanding.append("no sixth-form record to check")
        staged = bool(application and not application.get("converted_student_id"))
        if staged:
            outstanding.insert(0, f"application #{application['application_id']} staged")

        if application and application.get("converted_student_id"):
            status, tag = "Enrolled", "check"
        elif _awaiting_admission(readiness):
            # Handed over and never admitted. The sixth form names its
            # half of this failure (Stranded) and offers a retry; from
            # here the learner was indistinguishable from anyone else in
            # the list, so nobody could tell that the college had already
            # let them go and was waiting on us.
            status, tag = "Awaiting admission", "awaiting"
        elif staged:
            # The supported route is available for this person: say so
            # rather than reporting it as an obstacle.
            status, tag = "Admit", "supported"
        elif blocked:
            status = readiness.status_label if readiness else "Blocked"
            tag = "blocked"
        elif outstanding:
            status, tag = (readiness.status_label if readiness else "Check"), "check"
        else:
            status, tag = (readiness.status_label if readiness else "Ready"), "ready"

        decision = applicant.decision_status or "—"
        if applicant.final_decision:
            decision = f"{decision} · {applicant.final_decision}"

        tree.insert(
            "", "end", iid=sid,
            values=(status, applicant.source_label, sid,
                      applicant.student_name or
                      (student.full_name if student else "—"),
                      decision, applicant.course_label,
                      ", ".join(outstanding) or "—"),
            tags=(tag,),
        )

    detail_frame = ttk.LabelFrame(picker, text="Handover checks",
                                   padding=(10, 6))
    detail_frame.pack(fill=tk.X, padx=12, pady=(0, 4))
    detail = tk.Text(detail_frame, height=7, wrap=tk.WORD,
                      font=("Courier", 9), relief=tk.FLAT)
    detail.configure(state="disabled")
    detail.pack(fill=tk.BOTH, expand=True)

    def _show_detail(_event=None):
        sel = tree.selection()
        detail.configure(state="normal")
        detail.delete("1.0", tk.END)
        if sel and sel[0] in by_id:
            applicant, _student, readiness, journey_id, application = by_id[sel[0]]
            detail.insert(
                tk.END,
                f"UCAS  {applicant.course_code or '—'} {applicant.course_name}"
                f"  ·  {applicant.decision_status}"
                + (f"  ·  {applicant.final_decision}"
                   if applicant.final_decision else "")
                + (f"  ·  entry {applicant.entry_year}"
                   if applicant.entry_year else "") + "\n")
            if readiness is None:
                detail.insert(
                    tk.END,
                    "!   No sixth-form record for this applicant, so the "
                    "handover checks cannot run.\n")
            for c in (readiness.checks if readiness else ()):
                if not c.passed and c.key in _IMPORT_EXEMPT_CHECKS:
                    # Failing here is the normal state at import time,
                    # not an objection to importing. Reporting it with a
                    # ✗ told the operator to go and fix the one thing
                    # that had to have happened before they could start.
                    detail.insert(
                        tk.END,
                        f"OK  {c.label}: {c.detail}\n"
                        "    (expected here — the handover is what this "
                        "screen imports)\n")
                    continue
                mark = "OK  " if c.passed else ("✗   " if c.blocking
                                                 else "!   ")
                detail.insert(tk.END, f"{mark}{c.label}: {c.detail}\n")
            if application:
                converted = application.get("converted_student_id")
                detail.insert(
                    tk.END,
                    f"{'OK  ' if converted else '!   '}Existing application: "
                    f"#{application['application_id']} "
                    f"({application.get('status') or 'unknown'})"
                    + (f", already enrolled as {converted}\n" if converted
                       else " — complete that admission instead of "
                            "enrolling a second record\n"))
            if journey_id:
                detail.insert(tk.END, f"    journey {journey_id}\n")
        detail.configure(state="disabled")

    tree.bind("<<TreeviewSelect>>", _show_detail)

    # Right to study is the one required condition the sixth form cannot
    # answer — see the sixth form's right_to_study_note(). Rather than
    # carry it as a check that fails for everybody, it is an explicit
    # acknowledgement the operator must give before Import will run. The
    # supported route records it as an admissions requirement and gates
    # conversion on it; this route creates an active student outright, so
    # the acknowledgement is the only thing standing in for that gate.
    ack_frame = ttk.Frame(picker, padding=(12, 0, 12, 0))
    ack_frame.pack(fill=tk.X)
    rts_ack = tk.BooleanVar(value=False)
    ttk.Checkbutton(
        ack_frame, variable=rts_ack,
        text=(right_to_study_note
              + " I will complete it for this student."),
    ).pack(side=tk.LEFT)

    footer = ttk.Frame(picker, padding=(12, 6, 12, 12))
    footer.pack(fill=tk.X)
    info = ttk.Label(footer, text="", foreground="#666", wraplength=600,
                      justify=tk.LEFT)
    info.pack(side=tk.LEFT)

    def _do_import():
        sel = tree.selection()
        if not sel:
            info.config(text=_t('gui.learners.students.student_crud_gui.importers.text.select_a_student_first', default="Select a student first."))
            return
        sid = sel[0]
        entry = by_id.get(sid)
        if entry is None:
            info.config(text=_t('gui.learners.students.student_crud_gui.importers.text.selection_lost_refresh_the_list', default="Selection lost — refresh the list."))
            return
        applicant, student, readiness, journey_id, application = entry

        # ── The supported route, when it is available ───────────────
        # An application that is staged and ready enrols through
        # admissions: everything comes off the accepted choice, the
        # checks actually run, and there is no form to complete. Only
        # fall through to the manual pre-fill when that is not possible.
        if application and not application.get("converted_student_id"):
            new_id = _convert_via_admissions(
                application["application_id"], picker)
            if new_id:
                # They are a student here now, so their application to us
                # is over: mark the UCAS choice placed rather than leaving them in
                # this picker as a permanent "Enrolled" row.
                _clear_ucas_application(sid, new_id,
                                        actor=_actor_name(parent_dialog))
                picker.destroy()
                return
            # _convert_via_admissions has already explained why not; the
            # operator can still use the manual route below.
            if not messagebox.askyesno(
                    _import_title(),
                    "Create the student manually instead, bypassing the "
                    "admissions checks?",
                    parent=picker, icon="warning"):
                return

        if application and application.get("converted_student_id"):
            enrolled_as = application["converted_student_id"]
            exists = _university_student_exists(enrolled_as)
            if not exists:
                # "Enrolled" on the application, but no student record to
                # show for it. Saying only "already enrolled" strands the
                # operator: the record they are told about cannot be found.
                messagebox.showerror(
                    _import_title(),
                    f"{applicant.student_name}'s application is marked "
                    f"enrolled as {enrolled_as}, but no student with that "
                    f"id exists here.\n\n"
                    "The application and the student record disagree — fix "
                    "the application in Admissions (or clear the conversion "
                    "on it) before admitting them again, so this person "
                    "does not end up with two records.",
                    parent=picker)
                return
            # Genuinely enrolled. Offer the clear-down, because this row is
            # otherwise stuck in the picker for good.
            if messagebox.askyesno(
                    _import_title(),
                    f"{applicant.student_name} is already enrolled as "
                    f"{enrolled_as}.\n\n"
                    "Mark their UCAS choice for this university as placed "
                    "so they stop appearing here? (The sixth form keeps "
                    "the application as its record of where they went.)",
                    parent=picker):
                summary = _clear_ucas_application(
                    sid, enrolled_as, actor=_actor_name(parent_dialog))
                _report_ucas_clear(summary, picker)
                picker.destroy()
            return

        if student is None or readiness is None:
            messagebox.showerror(
                _import_title(),
                f"{applicant.student_name} has no sixth-form record, so "
                "there is nothing to pre-fill from. Create the student "
                "manually, or complete their admission in Admissions.",
                parent=picker)
            return

        if not rts_ack.get():
            info.config(
                text="Tick the right-to-study acknowledgement before "
                     "importing.")
            return

        # Hard stop. These are the failures the platform can positively
        # prove, and every one of them describes a learner who should not
        # become a student here today.
        if _import_blockers(readiness):
            messagebox.showerror(
                _import_title(),
                f"{student.full_name} cannot be handed over yet:\n\n"
                + "\n".join(f"  • {c.label} — {c.detail}"
                             for c in _import_blockers(readiness))
                + "\n\nResolve these in the sixth-form system first.",
                parent=picker,
            )
            return

        # A staged application was already offered — and declined — as the
        # supported route above, so by here the operator has chosen the
        # manual path knowingly.
        if readiness.warnings:
            proceed = messagebox.askyesno(
                _import_title(),
                f"{student.full_name} is importable, but these are "
                f"outstanding:\n\n"
                + "\n".join(f"  • {c.label} — {c.detail}"
                             for c in readiness.warnings)
                + "\n\nImport anyway?",
                parent=picker, icon="warning",
            )
            if not proceed:
                return

        # Everything the save handler needs to finish the transfer without
        # re-reading the sixth form: the origin id, the journey it anchors,
        # any application to attach to, and the *released* payload — built
        # through the same handover spec the bus route uses, so consent and
        # restricted-field rules apply to the manual route too.
        released = None
        try:
            released = sixth_form.build_handover(student.student_id)
        except Exception:
            logger.exception(
                "Could not build the handover payload for %s", sid)
        try:
            parent_dialog._sixth_form_origin_id = student.student_id
            parent_dialog._sixth_form_journey_id = journey_id
            parent_dialog._sixth_form_application_id = (
                application["application_id"] if application else None)
            parent_dialog._sixth_form_handover = released
        except Exception:
            logger.exception(
                "Could not stash sixth-form handover state on dialog")

        record = readiness.record
        identity = record.get("student_identity") or {}
        destination = record.get("confirmed_destination") or {}
        try:
            # Pre-fill the parent form. Use _safe_entry_insert helper
            # for entries; combobox uses .set() which is safe.
            if student.title and 'title' in fields:
                _safe_set_combobox(fields['title'], student.title)
            for key, value in (
                ('first_name', identity.get("first_name")
                               or student.first_name),
                ('middle_name', identity.get("middle_name")
                                or student.middle_name),
                ('last_name', identity.get("last_name")
                              or student.last_name),
            ):
                if key in fields:
                    fields[key].delete(0, tk.END)
                    _safe_entry_insert(fields[key], value or "")
            if student.gender and 'gender' in fields:
                from education_system.systems.university.application.students.lifecycle import (
                    gender_label,
                )
                _safe_set_combobox(fields['gender'], gender_label(student.gender))
            dob = identity.get("date_of_birth") or student.date_of_birth
            if dob and 'dob' in fields:
                # The DOB widget is now a _DOBPicker; use its set()
                # rather than delete/insert on a plain Entry.
                try:
                    fields['dob'].set(dob)
                except Exception:
                    # Fallback for the legacy Entry just in case.
                    fields['dob'].delete(0, tk.END)
                    _safe_entry_insert(fields['dob'], dob)
            # The add form's other details, when the sixth form holds them.
            # Medical information is not copied here: it has its own
            # consented import after the student is created.
            # Address lines, split from the one address when the sixth-form
            # record predates its separate lines.
            from education_system.systems.university.application.students import (
                record_rules as _rr,
            )
            lines = tuple(getattr(student, k, None) for k in _rr.ADDRESS_LINE_FIELDS)
            if not any(lines) and getattr(student, 'address', None):
                lines = _rr.split_address(student.address)
            for key, value in zip(_rr.ADDRESS_LINE_FIELDS, lines):
                if key in fields:
                    fields[key].delete(0, tk.END)
                    _safe_entry_insert(fields[key], value or "")
            for key, attr in (('preferred_name', 'preferred_name'),
                              ('postcode', 'postcode'),
                              ('emergency_contact_name', 'emergency_contact_name'),
                              ('emergency_contact_phone', 'emergency_contact_phone')):
                value = getattr(student, attr, None)
                if value and key in fields:
                    fields[key].delete(0, tk.END)
                    _safe_entry_insert(fields[key], value)
            relation = getattr(student, 'emergency_contact_relation', None)
            if relation and 'emergency_contact_relationship' in fields:
                from education_system.systems.university.application.students import (
                    record_rules,
                )
                choice = record_rules.relationship_choice(relation)
                if choice in record_rules.EMERGENCY_RELATIONSHIPS:
                    fields['emergency_contact_relationship'].set(choice)
        except Exception as e:
            logger.exception(
                "Pre-filling form from sixth-form student %s failed", sid)
            messagebox.showerror(
                _import_title(),
                f"Could not pre-fill the form: {e}",
                parent=picker,
            )
            return

        course_set = _select_course_for(fields, destination.get("course_code"))

        # Pre-fill the three A-level subjects + grades from the handover
        # record so the UCAS tariff / course eligibility come from the
        # student's real results rather than being re-keyed. Subjects with
        # no grade on record are left blank for the user to complete.
        filled_grades = 0
        sf_subjects = list(getattr(student, "subjects", []) or [])
        try:
            norm_grades = _qualification_grades(record)
            # The form starts with three rows; add one per extra A level so a
            # student who took four or more keeps every result.
            add_row = getattr(parent_dialog, '_add_qual_row', None)
            while callable(add_row) and f"alevel_subj_{len(sf_subjects)}" not in fields \
                    and len(sf_subjects) > 3:
                add_row()
            for i in range(1, max(4, len(sf_subjects) + 1)):
                if f"alevel_type_{i}" in fields:
                    fields[f"alevel_type_{i}"].set("A level")
                    fields[f"alevel_type_{i}"].event_generate("<<ComboboxSelected>>")
                subj = sf_subjects[i - 1] if i - 1 < len(sf_subjects) else ""
                if f"alevel_subj_{i}" in fields:
                    fields[f"alevel_subj_{i}"].delete(0, tk.END)
                    _safe_entry_insert(fields[f"alevel_subj_{i}"], subj or "")
                if f"alevel_grade_{i}" in fields:
                    grade = _normalise_grade(
                        norm_grades.get((subj or "").strip().lower(), ""))
                    fields[f"alevel_grade_{i}"].set(grade)
                    if grade:
                        filled_grades += 1
            # ``.set()`` doesn't fire <<ComboboxSelected>>, so nudge the tariff
            # label to recompute from the freshly filled grades.
            if "alevel_grade_1" in fields:
                try:
                    fields["alevel_grade_1"].event_generate(
                        "<<ComboboxSelected>>")
                except Exception:
                    logger.debug("Suppressed exception", exc_info=True)
        except Exception:
            logger.exception(
                "Pre-filling A-levels from sixth-form student %s failed", sid)

        logger.info(
            "Imported sixth-form student %s (%s) into university "
            "create-student dialog: journey=%s, application=%s, "
            "course pre-selected=%s, a_levels=%d/%d subjects, grades=%d, "
            "handover fields=%s",
            student.student_id, student.full_name, journey_id,
            application["application_id"] if application else None,
            course_set, len(sf_subjects), 3, filled_grades,
            ", ".join(released.included) if released else "none",
        )

        notes = []
        if sf_subjects and filled_grades < len(sf_subjects):
            notes.append(
                f"{len(sf_subjects) - filled_grades} A-level grade(s) were "
                f"not on record — please complete them before saving.")
        if destination.get("course_code") and not course_set:
            notes.append(
                f"Their firm choice is course "
                f"{destination['course_code']}, which is not in this "
                f"university's catalogue — pick the matching course.")
        if released and released.missing_required:
            notes.append(
                "The handover is missing required field(s): "
                + ", ".join(released.missing_required) + ".")
        if released and released.withheld_no_consent:
            notes.append(
                "Withheld for lack of consent: "
                + ", ".join(released.withheld_no_consent) + ".")
        if notes:
            messagebox.showinfo(
                _import_title(), "\n\n".join(notes), parent=parent_dialog)
        picker.destroy()

    btns = ttk.Frame(footer)
    btns.pack(side=tk.RIGHT)
    ttk.Button(btns, text=_t('gui.learners.students.student_crud_gui.importers.buttons.cancel', default="Cancel"),
                command=picker.destroy).pack(side=tk.RIGHT, padx=4)
    ttk.Button(btns, text=_t('gui.learners.students.student_crud_gui.importers.buttons.admit', default="Admit"),
                command=_do_import).pack(side=tk.RIGHT, padx=4)

    tree.bind("<Double-Button-1>", lambda _e: _do_import())
    if by_id:
        first = next(iter(by_id))
        tree.selection_set(first)
        _show_detail()


def _open_bulk_csv_import_dialog(self, parent_dialog):
    """Bulk-create university students from a CSV file.

    Expected columns (case-insensitive, any subset is fine):
        first_name, middle_name, last_name, gender, dob, title

    For each well-formed row the function does a direct INSERT into
    ``students`` using the same fields the per-student create dialog
    produces, plus the same random course assignment + random module
    enrolment as the singleton create path. Per-row errors are
    collected and shown in a summary panel after the run — they do
    not abort the rest of the import.
    """
    win = tk.Toplevel(parent_dialog)
    win.title(_t('gui.learners.students.student_crud_gui.importers.windows.bulk_import_students_from_csv', default="Bulk import students from CSV"))
    win.geometry("900x680")
    try:
        win.transient(parent_dialog)
        win.grab_set()
    except tk.TclError:
        pass

    # File picker row
    top = ttk.Frame(win, padding=(12, 10))
    top.pack(fill=tk.X)
    ttk.Label(top, text=_t('gui.learners.students.student_crud_gui.importers.labels.csv_file', default="CSV file:")).pack(side=tk.LEFT)
    path_var = tk.StringVar()
    ttk.Entry(top, textvariable=path_var, width=70).pack(
        side=tk.LEFT, padx=(8, 8), fill=tk.X, expand=True)

    def _browse():
        p = filedialog.askopenfilename(
            parent=win,
            title=_t('gui.learners.students.student_crud_gui.importers.dialogs.choose_csv', default="Choose CSV"),
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if p:
            path_var.set(p)
            _refresh_preview()

    ttk.Button(top, text=_t('gui.learners.students.student_crud_gui.importers.buttons.browse', default="Browse…"),
                command=_browse).pack(side=tk.LEFT)

    # Preview area (column → field mapping + first few rows)
    body = ttk.Frame(win, padding=(12, 0))
    body.pack(fill=tk.BOTH, expand=True)

    map_frame = ttk.LabelFrame(body, text=_t('gui.learners.students.student_crud_gui.importers.labels.column_mapping', default="Column mapping"), padding=10)
    map_frame.pack(fill=tk.X, pady=(8, 6))
    map_widgets: dict[str, ttk.Combobox] = {}
    expected = ("first_name", "middle_name", "last_name",
                "gender", "dob", "title",
                "student_id", "email", "course", "registration_date",
                "module_1", "module_2", "module_3",
                "module_4", "module_5", "module_6")
    for i, field in enumerate(expected):
        ttk.Label(map_frame, text=f"{field}:").grid(
            row=i // 3, column=(i % 3) * 2,
            sticky=tk.W, padx=(0, 6), pady=2)
        cb = ttk.Combobox(map_frame, values=[""], state="readonly",
                            width=22)
        cb.grid(row=i // 3, column=(i % 3) * 2 + 1,
                  sticky=tk.W, padx=(0, 16), pady=2)
        map_widgets[field] = cb

    preview_lbl = ttk.LabelFrame(body, text=_t('gui.learners.students.student_crud_gui.importers.labels.preview_first_5_rows', default="Preview (first 5 rows)"),
                                    padding=10)
    preview_lbl.pack(fill=tk.BOTH, expand=True, pady=6)
    preview_text = scrolledtext.ScrolledText(
        preview_lbl, height=8, wrap=tk.NONE, font=("Courier", 9))
    preview_text.pack(fill=tk.BOTH, expand=True)

    # Status / summary at the bottom
    bottom = ttk.Frame(win, padding=(12, 6, 12, 12))
    bottom.pack(fill=tk.X)
    status_lbl = ttk.Label(bottom, text="", foreground="#666")
    status_lbl.pack(side=tk.LEFT)
    btns = ttk.Frame(bottom)
    btns.pack(side=tk.RIGHT)

    csv_rows: list[dict] = []
    csv_headers: list[str] = []

    def _refresh_preview():
        nonlocal csv_rows, csv_headers
        csv_rows = []
        csv_headers = []
        preview_text.configure(state="normal")
        preview_text.delete("1.0", tk.END)
        p = path_var.get().strip()
        if not p:
            preview_text.configure(state="disabled")
            return
        try:
            with open(p, "r", newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                csv_headers = reader.fieldnames or []
                for row in reader:
                    csv_rows.append(row)
        except Exception as e:
            status_lbl.config(text=f"Could not read CSV: {e}",
                                foreground="red")
            preview_text.configure(state="disabled")
            return
        # Populate combobox values
        for cb in map_widgets.values():
            cb.configure(values=[""] + csv_headers)
        # Auto-map by normalised name (case/space/underscore/hyphen-insensitive)
        def _norm(s: str) -> str:
            return "".join(ch for ch in s.lower() if ch.isalnum())
        norm_headers = {_norm(h): h for h in csv_headers}
        aliases = {
            "first_name":  ("firstname", "givenname", "forename"),
            "middle_name": ("middlename",),
            "last_name":   ("lastname", "surname", "familyname"),
            "gender":      ("sex",),
            "dob":         ("dateofbirth", "birthdate", "birthday"),
            "title":       ("salutation", "honorific"),
            "student_id":  ("studentid", "id", "studentnumber"),
            "email":       ("emailaddress", "emailaddr"),
            "course":      ("coursecode", "programme", "program"),
            "registration_date": ("registrationdate", "regdate",
                                  "enrolmentdate", "enrollmentdate"),
            "module_1":    ("module1", "mod1"),
            "module_2":    ("module2", "mod2"),
            "module_3":    ("module3", "mod3"),
            "module_4":    ("module4", "mod4"),
            "module_5":    ("module5", "mod5"),
            "module_6":    ("module6", "mod6"),
        }
        for field, cb in map_widgets.items():
            candidates = (field, *aliases.get(field, ()))
            match = ""
            for cand in candidates:
                if _norm(cand) in norm_headers:
                    match = norm_headers[_norm(cand)]
                    break
            cb.set(match)
        # Preview
        head = "  ".join(f"{h:<16}" for h in csv_headers)
        preview_text.insert("1.0", head + "\n" + "-" * len(head) + "\n")
        for row in csv_rows[:5]:
            line = "  ".join(
                f"{(row.get(h) or ''):<16}" for h in csv_headers)
            preview_text.insert(tk.END, line + "\n")
        preview_text.configure(state="disabled")
        status_lbl.config(
            text=f"{len(csv_rows)} row(s) loaded.  "
                  f"Map columns then click Import.",
            foreground="#444")

    def _import_rows():
        if not csv_rows:
            status_lbl.config(text=_t('gui.learners.students.student_crud_gui.importers.text.no_rows_to_import', default="No rows to import."),
                                foreground="red")
            return
        mapping = {f: w.get() for f, w in map_widgets.items()}
        missing = [f for f in ("first_name", "last_name")
                    if not mapping.get(f)]
        if missing:
            status_lbl.config(
                text="Missing required column mapping: "
                      + ", ".join(missing),
                foreground="red")
            return

        ok_rows: list[str] = []
        err_rows: list[tuple[int, str]] = []

        def _cell(key: str) -> str:
            col = mapping.get(key, "")
            if not col:
                return ""
            return (row.get(col, "") or "").strip()

        def _module_code(raw: str) -> str:
            # Export writes "CODE - Module Name"; accept either form.
            raw = (raw or "").strip()
            if " - " in raw:
                raw = raw.split(" - ", 1)[0]
            return raw.strip()

        for idx, row in enumerate(csv_rows, start=2):  # 1=header line
            try:
                first_name = _cell("first_name")
                last_name  = _cell("last_name")
                gender_raw = _cell("gender").lower()
                dob_text   = _cell("dob")
                middle     = _cell("middle_name")
                title      = _cell("title") or None

                csv_student_id = _cell("student_id")
                csv_email      = _cell("email")
                csv_course     = _cell("course").upper()
                csv_reg_date   = _cell("registration_date")
                csv_modules    = [
                    _module_code(_cell(f"module_{i}"))
                    for i in range(1, 7)
                ]
                csv_modules = [m for m in csv_modules if m]

                if not first_name or not last_name:
                    raise ValueError(
                        "first_name and last_name are required")
                from education_system.systems.university.application.students.lifecycle import (
                    GENDER_OPTIONS,
                )
                codes = [g.lower() for g in GENDER_OPTIONS]
                if not gender_raw:
                    gender_raw = "prefer not to say"
                elif gender_raw not in codes:
                    raise ValueError(
                        "gender must be one of: " + ", ".join(GENDER_OPTIONS))
                dob_given = bool(dob_text)
                if not dob_text:
                    dob_text = "2000-01-01"
                try:
                    dob = datetime.strptime(dob_text, "%Y-%m-%d")
                except ValueError:
                    raise ValueError("dob must be YYYY-MM-DD")
                age = _compute_age(dob)

                # Validate the course against the live catalogue: accept any
                # real course code, fail fast on an unknown one, and only fall
                # back to a random default when the CSV left it blank.
                if csv_course:
                    if not _get_course(csv_course):
                        raise ValueError(f"unknown course code {csv_course!r}")
                    course = csv_course
                else:
                    course = random.choice(['CS', 'DS'])
                if not title:
                    title = {"male": "Mr", "female": "Ms"}.get(gender_raw, "")

                student_id = csv_student_id or str(
                    secrets.randbelow(9000000) + 1000000).zfill(7)
                email_address = csv_email or f"C{student_id}@tees.ac.uk"
                if csv_reg_date:
                    # Accept date-only or full timestamp.
                    reg_time = csv_reg_date if " " in csv_reg_date \
                        else f"{csv_reg_date} 00:00:00"
                else:
                    reg_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                temp_password = _default_student_password(first_name, student_id)

                enrolled_modules: list[str] = []
                conn = get_db_connection()
                if not conn:
                    raise RuntimeError("DB connection failed")
                try:
                    cur = conn.cursor()
                    # Reject a duplicate id; for an auto-generated id, regenerate
                    # on the rare clash instead of failing the row.
                    if csv_student_id:
                        cur.execute(
                            "SELECT 1 FROM students WHERE student_id = ?",
                            (student_id,))
                        if cur.fetchone():
                            raise ValueError(
                                f"student_id {student_id} already exists")
                    else:
                        for _ in range(25):
                            cur.execute(
                                "SELECT 1 FROM students WHERE student_id = ?",
                                (student_id,))
                            if cur.fetchone() is None:
                                break
                            student_id = str(
                                secrets.randbelow(9000000) + 1000000).zfill(7)
                            if not csv_email:
                                email_address = f"C{student_id}@tees.ac.uk"
                    # Email must be unique regardless of where the id came from.
                    cur.execute(
                        "SELECT 1 FROM students WHERE email_address = ?",
                        (email_address,))
                    if cur.fetchone():
                        raise ValueError(
                            f"email {email_address} already in use")
                    # Same likely-duplicate rule as single create (name +
                    # date of birth); skipped when the CSV gave no DOB.
                    from education_system.systems.university.application.students import (
                        record_rules as student_record_rules,
                    )
                    if dob_given:
                        matches = student_record_rules.find_duplicates(
                            conn, first_name, last_name, dob.strftime("%Y-%m-%d"))
                        if matches:
                            raise ValueError(
                                "possible duplicate of "
                                + ", ".join(m["student_id"] for m in matches))
                    # FK checks off so module rows can be written before their
                    # catalog entries; the context manager restores enforcement
                    # even if the body raises.
                    with foreign_keys_off(conn):
                        cur.execute(
                            """INSERT INTO students
                                   (student_id, email_address, title,
                                    first_name, middle_name, last_name,
                                    gender, dob, age, course,
                                    registration_datetime, status,
                                    enrollment_date)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                                       ?, 'Active', ?)""",
                            (student_id, email_address, title,
                             first_name, middle or None, last_name,
                             gender_raw, dob.strftime("%Y-%m-%d"),
                             age, course, reg_time, reg_time),
                        )
                        # Enrol in the course's full 18-module curriculum
                        # (6/year x 3) — the same set the single-create and CLI
                        # paths use, not only the modules the CSV listed.
                        curriculum = _enrol_student_in_curriculum(
                            cur, student_id, course, course)
                        enrolled_modules = [m["module_code"] for m in curriculum]
                        # Honour any explicit module codes from the CSV as extras.
                        extra = [m for m in csv_modules
                                 if m and m not in enrolled_modules]
                        if extra:
                            cur.executemany(
                                "INSERT OR IGNORE INTO student_modules "
                                "(student_id, module_code) VALUES (?, ?)",
                                [(student_id, m) for m in extra],
                            )
                            enrolled_modules.extend(extra)
                        cur.execute(
                            "UPDATE courses SET current_enrollment = "
                            "current_enrollment + 1 "
                            "WHERE course_code = ? AND LOWER(COALESCE(status, 'active')) = 'active'",
                            (course,),
                        )
                        importer = (getattr(getattr(self, "auth", None),
                                            "current_user", None) or {})
                        student_record_rules.record_changes(
                            conn, student_id, {}, {"record": "created"},
                            "Bulk CSV import",
                            str(importer.get("username") or "csv import"))
                    conn.commit()
                finally:
                    conn.close()

                # Provision the login in both auth stores (legacy
                # student_records.db user + central shared-auth) so the student
                # can sign in and be resolved for chat-room membership. The
                # bulk path previously created only the shared-auth row.
                _provision_student_login(
                    getattr(self, "auth", None),
                    username=student_id, password=temp_password,
                    email=email_address, first_name=first_name,
                    last_name=last_name,
                )

                # Auto-join the student to one chat room per enrolled module
                # (creating any missing room), matching the other create
                # paths. Best-effort.
                try:
                    ensure_module_chat_rooms_and_join(student_id, enrolled_modules)
                except Exception as exc:
                    logger.debug(
                        "Chat-room auto-join failed for %s during CSV "
                        "import: %s", student_id, exc)

                ok_rows.append(student_id)
            except Exception as e:
                err_rows.append((idx, str(e)))

        # Show summary
        summary = (
            f"Bulk import finished.\n\n"
            f"  Imported   : {len(ok_rows)} row(s)\n"
            f"  Skipped    : {len(err_rows)} row(s)\n\n"
        )
        if err_rows:
            summary += "Errors (line # — message):\n"
            for ln, msg in err_rows[:30]:
                summary += f"  line {ln}: {msg}\n"
            if len(err_rows) > 30:
                summary += f"  …plus {len(err_rows) - 30} more\n"
        messagebox.showinfo(_t('gui.learners.students.student_crud_gui.importers.dialogs.csv_import', default="CSV import"), summary, parent=win)

        # Refresh the parent views
        try:
            if hasattr(self, "view_students"):
                self.view_students()
            self.refresh_advanced_search()
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)
        if ok_rows and not err_rows:
            win.destroy()

    ttk.Button(btns, text=_t('gui.learners.students.student_crud_gui.importers.buttons.cancel', default="Cancel"),
                command=win.destroy).pack(side=tk.RIGHT, padx=4)
    ttk.Button(btns, text=_t('gui.learners.students.student_crud_gui.importers.buttons.import', default="Import"),
                command=_import_rows).pack(side=tk.RIGHT, padx=4)


