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
from .authorization import require_student_permission
from .importers import _open_sixth_form_import_dialog, _open_bulk_csv_import_dialog
from .sync.visa import _create_visa_record_for_new_student
from .sync.atas import _resync_atas_after_module_change
from .sync.auth import _ensure_shared_auth_user, _purge_user_from_all_chat_rooms
from education_system.systems.university.services.student_provisioning import (
    compute_age as _compute_age,
    default_student_password as _default_student_password,
    provision_student_login as _provision_student_login,
)
from .sync.chat_rooms import _auto_join_module_chat_rooms, _resolve_module_name, _sync_module_chat_rooms
from education_system.systems.university.domains.academics.domain.services.admissions_selection import (
    list_active_courses as _list_active_courses,
    compute_tariff as _compute_tariff,
    format_qualifications as _format_qualifications,
    eligible_courses as _eligible_courses,
    is_eligible as _is_eligible,
    enrol_student_in_curriculum as _enrol_student_in_curriculum,
    GRADE_CHOICES as _GRADE_CHOICES,
)

def _attach_sixth_form_application(*, journey_id, application_id,
                                   student_id, actor_id):
    """Bind an applicant already staged for this learner to the new student.

    The bus intake stages a sixth-form handover as an *applicant*; this
    dialog creates an active *student* directly. Both are legitimate
    records of the same person arriving, and until they were joined the
    learner existed twice — enrolled on one side, stuck in
    ``documents_pending`` on the other, with the admissions team chasing
    documents for somebody who had already started.

    Best-effort throughout: the student has been created and stands
    regardless. A conflict (the application is bound to a *different*
    student) is logged by the lifecycle service and needs a human.
    """
    if not journey_id and not application_id:
        return
    try:
        from education_system.systems.university.domains.admissions.domain import (
            sixthform_intake,
        )
        from education_system.systems.university.domains.admissions.domain.services import (
            admissions_lifecycle,
        )
        if not application_id:
            existing = sixthform_intake.find_application_for_journey(
                journey_id)
            application_id = (existing["application_id"] if existing
                              else None)
        if not application_id:
            return
        admissions_lifecycle.attach_direct_enrolment(
            int(application_id), student_id,
            actor_id=actor_id or "university CRUD GUI",
            reason="Enrolled directly from the sixth-form import picker — "
                   "the admissions readiness gates were not evaluated",
        )
    except Exception:
        logger.exception(
            "Could not attach university student %s to the application "
            "staged on journey %s; check for a duplicate applicant record",
            student_id, journey_id)


def _clear_ucas_application_after_import(sf_student_id, uni_student_id, *,
                                         actor=None):
    """Close the learner's UCAS application to this university.

    The manual import creates the student directly, so nothing else marks
    the UCAS choice as spent. Left alone, the applicant reappears in "Admit
    from UCAS" for ever — shown as enrolled, and refused when clicked.

    Best-effort by design: this runs after the student, the journey link and
    the transfer are all done, and a tidy-up problem must not undo any of it.
    """
    if not sf_student_id:
        return
    try:
        from education_system.systems.university.services.bus import ucas_bus
        summary = ucas_bus.clear_after_admission(
            sf_student_id, uni_student_id, actor=actor)
        logger.info("UCAS clear-down for %s -> %s: %s",
                    sf_student_id, uni_student_id, ucas_bus.describe(summary))
    except Exception:
        logger.exception(
            "Could not clear the UCAS application for %s after importing "
            "them as %s; they may still appear in the UCAS picker",
            sf_student_id, uni_student_id)


def _import_sixth_form_medical_record(*, parent, uni_student_id,
                                      sf_student_id, actor):
    """Copy the learner's health record across, if they consented to it.

    Consent is the sixth form's to hold and this dialog's to respect. When
    there is none, the operator is offered the narrow alternative — the
    safety-critical subset on vital interests — and told plainly that the
    decision is audited against their account. Declining is a valid
    outcome, not an error: the record simply does not cross, and the
    university student is enrolled either way.
    """
    from education_system.systems.university.domains.pastoral.domain.health.records import (
        sixth_form_import as _sf_med_import,
    )
    title = _t('gui.learners.students.student_crud_gui.create.dialogs.sixth_form_medical_import', default="Sixth-form medical import")
    try:
        decision = _sf_med_import.check_release(sf_student_id)
        lawful_basis = None
        if not decision.allowed:
            proceed = messagebox.askyesno(
                title,
                f"{decision.detail}.\n\n"
                "Their health record will NOT be copied.\n\n"
                "If there is an immediate safety need you may copy the "
                "safety-critical subset — allergies, active conditions and "
                "current medications — on the basis of the student's vital "
                "interests. Resolved conditions, blood group and GP details "
                "will not be copied, and the decision is recorded against "
                "your account.\n\n"
                "Copy the safety-critical subset now?",
                parent=parent, icon="warning",
            )
            if not proceed:
                logger.info(
                    "Sixth-form medical record for %s not copied to %s — "
                    "no consent, and the operator declined vital interests",
                    sf_student_id, uni_student_id)
                return
            lawful_basis = _sf_med_import.VITAL_INTERESTS

        summary = _sf_med_import.import_from_sixth_form(
            uni_student_id=uni_student_id,
            sf_student_id=sf_student_id,
            lawful_basis=lawful_basis,
            actor=actor,
            received_by="university student records",
        )
        logger.info(
            "Sixth-form medical record imported for uni student %s: %s",
            uni_student_id, summary)
        if summary.withheld:
            messagebox.showinfo(
                title,
                "Copied the safety-critical subset of their medical "
                "record.\n\nNot copied: "
                + "; ".join(summary.withheld)
                + ".\n\nObtain the handover consent to carry the rest.",
                parent=parent,
            )
    except _sf_med_import.MedicalHandoverRefused as refused:
        logger.warning(
            "Sixth-form medical record refused for sf=%s -> uni=%s: %s",
            sf_student_id, uni_student_id, refused)
        messagebox.showwarning(
            title,
            "The student was transferred successfully, but their medical "
            f"record was NOT copied:\n\n{refused}\n\n"
            "Ask the sixth form to record the handover consent, or enter "
            "their conditions / medications / allergies on the university "
            "health record directly.",
            parent=parent,
        )
    except Exception as med_err:
        logger.exception(
            "Sixth-form medical-record import failed for sf=%s -> uni=%s "
            "(student status/login/email cleanup did succeed)",
            sf_student_id, uni_student_id)
        messagebox.showwarning(
            title,
            "The student was transferred successfully, but their medical "
            f"record could not be imported:\n\n{med_err}\n\n"
            "You can re-enter their conditions / medications / allergies "
            "on the university health record manually.",
            parent=parent,
        )


def create_student_dialog(self):
    """Create comprehensive dialog for adding new student with full form validation"""
    if not require_student_permission(self, "create_student", "create"):
        return
    dialog = self.create_themed_toplevel(_t("student.create_new_student"), "1200x740")
    dialog.minsize(1180, 680)

    # Make dialog visible before grabbing
    dialog.update_idletasks()
    dialog.deiconify()

    try:
        dialog.grab_set()
    except tk.TclError:
        print("Warning: Could not grab dialog focus")

    # Main content frame — laid out as header / two-column body / footer
    # so the whole form fits in the window without a scrollbar.
    main_frame = ttk.Frame(dialog)
    main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

    # Header row (title + import buttons) spans the full width.
    header_frame = ttk.Frame(main_frame)
    header_frame.pack(fill=tk.X, pady=(0, 12))

    # Two-column body: personal info on the left, academic + visa on the
    # right. Both columns share the width evenly and top-align.
    body_frame = ttk.Frame(main_frame)
    body_frame.pack(fill=tk.BOTH, expand=True)
    body_frame.columnconfigure(0, weight=1, uniform="cols")
    body_frame.columnconfigure(1, weight=1, uniform="cols")
    body_frame.rowconfigure(0, weight=1)

    left_col = ttk.Frame(body_frame)
    left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
    right_col = ttk.Frame(body_frame)
    right_col.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

    # Footer (status note, validation message, action buttons) spans the
    # full width below the two columns.
    footer_frame = ttk.Frame(main_frame)
    footer_frame.pack(fill=tk.X, pady=(12, 0))

    # Title
    title_label = ttk.Label(header_frame, text=_t("student.create_new_student"),
                           font=('Arial', 16, 'bold'))
    title_label.pack(side=tk.LEFT)

    # Form fields
    fields = {}

    # Sixth-form import bar — pre-fills the personal-info fields from a
    # Year 13 leaver. Placed in the header so the user can choose to
    # import before filling anything in manually.
    import_bar = ttk.Frame(header_frame)
    import_bar.pack(side=tk.RIGHT)

    def _open_sixth_form_import():
        _open_sixth_form_import_dialog(dialog, fields)

    def _open_csv_import():
        _open_bulk_csv_import_dialog(self, dialog)

    ttk.Button(import_bar, text=_t('gui.learners.students.student_crud_gui.create.buttons.admit_from_ucas', default="Admit from UCAS"),
               command=_open_sixth_form_import).pack(side=tk.RIGHT)
    ttk.Button(import_bar, text=_t('gui.learners.students.student_crud_gui.create.buttons.bulk_import_from_csv', default="Bulk import from CSV"),
               command=_open_csv_import).pack(
        side=tk.RIGHT, padx=(0, 6))

    # Personal Information Section (left column)
    personal_frame = ttk.LabelFrame(left_col, text=_t("student.personal_info"), padding=15)
    personal_frame.pack(fill=tk.BOTH, expand=True)

    # Title/Prefix
    ttk.Label(personal_frame, text=_t("student.title_label")).grid(row=1, column=0, sticky=tk.W, pady=5)
    fields['title'] = ttk.Combobox(personal_frame, values=['Mr', 'Ms', 'Mrs', 'Dr', 'Prof'],
                                  state='readonly', width=27)
    fields['title'].grid(row=1, column=1, pady=5, padx=(10, 0), sticky=tk.W)

    # First Name
    ttk.Label(personal_frame, text=_t("student.first_name_required")).grid(row=2, column=0, sticky=tk.W, pady=5)
    fields['first_name'] = ttk.Entry(personal_frame, width=30)
    fields['first_name'].grid(row=2, column=1, pady=5, padx=(10, 0))

    # Middle Name
    ttk.Label(personal_frame, text=_t("student.middle_name_label")).grid(row=3, column=0, sticky=tk.W, pady=5)
    fields['middle_name'] = ttk.Entry(personal_frame, width=30)
    fields['middle_name'].grid(row=3, column=1, pady=5, padx=(10, 0))

    # Last Name
    ttk.Label(personal_frame, text=_t("student.last_name_required")).grid(row=4, column=0, sticky=tk.W, pady=5)
    fields['last_name'] = ttk.Entry(personal_frame, width=30)
    fields['last_name'].grid(row=4, column=1, pady=5, padx=(10, 0))

    # Gender
    ttk.Label(personal_frame, text=_t("student.gender_required")).grid(row=5, column=0, sticky=tk.W, pady=5)
    fields['gender'] = ttk.Combobox(personal_frame, values=['male', 'female', 'other'],
                                   state='readonly', width=27)
    fields['gender'].grid(row=5, column=1, pady=5, padx=(10, 0), sticky=tk.W)

    # Date of Birth — spinbox trio (year / month / day) instead of a
    # plain Entry, so users can't typo the format and the day range
    # is automatically clamped to the selected month's length.
    ttk.Label(personal_frame, text=_t("student.dob_required")).grid(row=6, column=0, sticky=tk.W, pady=5)
    fields['dob'] = _DOBPicker(
        personal_frame, on_change=lambda: _refresh_live_preview())
    fields['dob'].grid(row=6, column=1, pady=5, padx=(10, 0), sticky=tk.W)

    # Live preview — read-only "Will be created as…" panel that
    # updates as the user types names / picks a DOB, so admissions
    # can spot typos in id / email / temp password BEFORE the
    # record is committed and the welcome email goes out.
    preview_frame = ttk.LabelFrame(
        personal_frame,
        text=_t('gui.learners.students.student_crud_gui.create.labels.will_be_created_as', default="Will be created as …"),
        padding=(10, 6),
    )
    preview_frame.grid(row=7, column=0, columnspan=2,
                        sticky=(tk.W, tk.E),
                        pady=(10, 0))
    preview_vars = {
        "student_id": tk.StringVar(value="—"),
        "email":      tk.StringVar(value="—"),
        "password":   tk.StringVar(value="—"),
    }
    for r, (label, key) in enumerate((
            ("Student ID",       "student_id"),
            ("Email address",    "email"),
            ("Temp password",    "password"),
    )):
        ttk.Label(preview_frame, text=f"{label}:").grid(
            row=r, column=0, sticky=tk.W, pady=1)
        ttk.Label(preview_frame, textvariable=preview_vars[key],
                    foreground="#1a3f8c").grid(
            row=r, column=1, sticky=tk.W, padx=(10, 0), pady=1)

    # The id is generated at save-time (random 7 digits) so we
    # can't predict it pre-save. We show a deterministic format
    # placeholder so the user understands the shape.
    def _refresh_live_preview() -> None:
        fn = fields['first_name'].get().strip()
        if fn:
            preview_vars["student_id"].set("C####### (assigned at save)")
            preview_vars["email"].set("C#######@tees.ac.uk")
            preview_vars["password"].set(
                f"{fn.capitalize()}#######!")
        else:
            preview_vars["student_id"].set("—")
            preview_vars["email"].set("—")
            preview_vars["password"].set("—")

    fields['first_name'].bind(
        "<KeyRelease>", lambda _e: _refresh_live_preview())
    fields['last_name'].bind(
        "<KeyRelease>", lambda _e: _refresh_live_preview())

    # Academic Information Section (right column)
    academic_frame = ttk.LabelFrame(right_col, text=_t("student.academic_info"), padding=15)
    academic_frame.pack(fill=tk.X)

    # Course — chosen from the live catalogue. Reading the catalogue here
    # (rather than hard-coding CS/DS) means any course an admin creates via
    # course management appears in this dropdown automatically.
    ttk.Label(academic_frame, text=_t("student.course_label")).grid(row=0, column=0, sticky=tk.W, pady=5)
    fields['course'] = ttk.Combobox(academic_frame, state='readonly', width=48)
    fields['course'].grid(row=0, column=1, pady=5, padx=(10, 0), sticky=tk.W)

    _all_courses = _list_active_courses()
    # Maps each combobox display label back to its course dict.
    course_label_map = {}

    def _course_label_for(c):
        return f"{c['code']} - {c['name']} (requires {c['min_tariff']} UCAS pts)"

    def _populate_courses(courses):
        course_label_map.clear()
        labels = []
        for c in courses:
            lbl = _course_label_for(c)
            course_label_map[lbl] = c
            labels.append(lbl)
        fields['course']['values'] = labels
        fields['course'].set(labels[0] if labels else '')

    _populate_courses(_all_courses)

    # Sixth-form A-level results → UCAS tariff (gates course eligibility).
    grades_frame = ttk.LabelFrame(academic_frame, text=_t('gui.learners.students.student_crud_gui.create.labels.sixth_form_a_level_results', default="Sixth-form A-level results"), padding=10)
    grades_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(8, 0))

    tariff_var = tk.StringVar(value=_t('gui.learners.students.student_crud_gui.create.values.ucas_tariff_0', default="UCAS tariff: 0"))

    def _recompute_tariff(*_a):
        grades = [fields[f'alevel_grade_{i}'].get() for i in range(1, 4)]
        tariff_var.set(f"UCAS tariff: {_compute_tariff(grades)}")

    for i in range(1, 4):
        ttk.Label(grades_frame, text=f"A-level {i} subject").grid(row=i, column=0, sticky=tk.W, pady=2)
        fields[f'alevel_subj_{i}'] = ttk.Entry(grades_frame, width=22)
        fields[f'alevel_subj_{i}'].grid(row=i, column=1, padx=(8, 16), pady=2)
        ttk.Label(grades_frame, text=_t('gui.learners.students.student_crud_gui.create.labels.grade', default="Grade")).grid(row=i, column=2, sticky=tk.W)
        fields[f'alevel_grade_{i}'] = ttk.Combobox(grades_frame, values=list(_GRADE_CHOICES),
                                                   state='readonly', width=6)
        fields[f'alevel_grade_{i}'].grid(row=i, column=3, padx=8, pady=2)
        fields[f'alevel_grade_{i}'].bind('<<ComboboxSelected>>', _recompute_tariff)

    ttk.Label(grades_frame, textvariable=tariff_var, foreground="#1a3f8c",
              font=('Arial', 10, 'bold')).grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=(6, 0))

    def _filter_to_eligible():
        grades = [fields[f'alevel_grade_{i}'].get() for i in range(1, 4)]
        t = _compute_tariff(grades)
        elig = _eligible_courses(t)
        if not elig:
            messagebox.showwarning(
                _t('gui.learners.students.student_crud_gui.create.dialogs.eligibility', default="Eligibility"),
                f"With a UCAS tariff of {t}, you are not eligible for any "
                "course currently on offer.")
            _populate_courses(_all_courses)
            return
        _populate_courses(elig)
        messagebox.showinfo(
            _t('gui.learners.students.student_crud_gui.create.dialogs.eligibility', default="Eligibility"),
            f"Showing the {len(elig)} course(s) you can study with a tariff of {t}.")

    ttk.Button(grades_frame, text=_t('gui.learners.students.student_crud_gui.create.buttons.show_courses_i_m_eligible_for', default="Show courses I'm eligible for"),
               command=_filter_to_eligible).grid(row=4, column=2, columnspan=2,
                                                  sticky=tk.E, pady=(6, 0))

    # International / visa-sponsorship section.
    # ── Phase 8.117.42: the visa-detail fields now hide unless the
    # "Student Route" checkbox is ticked. Most undergrads are UK
    # applicants who don't need the section, and the extra ~5 rows
    # were padding every create-student session unnecessarily.
    intl_frame = ttk.LabelFrame(right_col,
                                text=_t('gui.learners.students.student_crud_gui.create.labels.international_student_tier_4_student_route', default="International student (Tier-4 / Student Route)"),
                                padding=15)
    intl_frame.pack(fill=tk.X, pady=(10, 0))

    fields['is_international'] = tk.BooleanVar(value=False)
    intl_details_frame = ttk.Frame(intl_frame)

    def _toggle_visa_details() -> None:
        if fields['is_international'].get():
            intl_details_frame.grid(row=1, column=0, columnspan=4,
                                       sticky=(tk.W, tk.E), pady=(6, 0))
        else:
            intl_details_frame.grid_forget()

    ttk.Checkbutton(intl_frame, text=_t('gui.learners.students.student_crud_gui.create.buttons.this_student_is_on_a_student_route_visa', default="This student is on a Student Route visa"),
                    variable=fields['is_international'],
                    command=_toggle_visa_details).grid(
        row=0, column=0, columnspan=4, sticky=tk.W, pady=(0, 6))

    # Visa fields are stacked one-per-row (label + entry) so the section
    # stays within the right column's width when it expands.
    ttk.Label(intl_details_frame, text=_t('gui.learners.students.student_crud_gui.create.labels.nationality', default="Nationality")).grid(row=0, column=0, sticky=tk.W, pady=3)
    fields['nationality'] = ttk.Entry(intl_details_frame, width=28)
    fields['nationality'].grid(row=0, column=1, padx=(8, 0), sticky=tk.W)

    ttk.Label(intl_details_frame, text=_t('gui.learners.students.student_crud_gui.create.labels.passport', default="Passport #")).grid(row=1, column=0, sticky=tk.W, pady=3)
    fields['passport_number'] = ttk.Entry(intl_details_frame, width=28)
    fields['passport_number'].grid(row=1, column=1, padx=(8, 0), sticky=tk.W)

    ttk.Label(intl_details_frame, text=_t('gui.learners.students.student_crud_gui.create.labels.visa_expiry_yyyy_mm_dd', default="Visa expiry (YYYY-MM-DD)")).grid(row=2, column=0, sticky=tk.W, pady=3)
    fields['visa_expiry_date'] = ttk.Entry(intl_details_frame, width=28)
    fields['visa_expiry_date'].grid(row=2, column=1, padx=(8, 0), sticky=tk.W)

    ttk.Label(intl_details_frame, text=_t('gui.learners.students.student_crud_gui.create.labels.brp', default="BRP #")).grid(row=3, column=0, sticky=tk.W, pady=3)
    fields['brp_number'] = ttk.Entry(intl_details_frame, width=28)
    fields['brp_number'].grid(row=3, column=1, padx=(8, 0), sticky=tk.W)
    # Start hidden — _toggle_visa_details has not been called yet
    # and the checkbox defaults to off.

    # Status information
    status_label = ttk.Label(footer_frame,
                            text=_t("student.auto_generated_note"),
                            foreground="blue")
    status_label.pack(pady=(0, 4))

    # Validation feedback
    validation_label = ttk.Label(footer_frame, text="", foreground="red")
    validation_label.pack(pady=(0, 4))

    def validate_form():
        """Validate form inputs"""
        errors = []

        if not fields['first_name'].get().strip():
            errors.append(_t("student.validation_first_name"))

        if not fields['last_name'].get().strip():
            errors.append(_t("student.validation_last_name"))

        if not fields['gender'].get():
            errors.append(_t("student.validation_gender"))

        # The DOB picker always produces a YYYY-MM-DD (or "" if the
        # widget got into a weird state). The age sanity check is
        # the only remaining validation — the format-error path is
        # unreachable now and has been retired.
        dob_text = fields['dob'].get().strip()
        if not dob_text:
            errors.append(_t("student.validation_dob"))
        else:
            dob = datetime.strptime(dob_text, "%Y-%m-%d")
            age = _compute_age(dob)
            if age < 16 or age > 80:
                errors.append(_t("student.validation_age"))

        # Require all three A-level grades and a course selection so the
        # eligibility gate has the data it needs.
        if any(not fields.get(f'alevel_grade_{i}') or not fields[f'alevel_grade_{i}'].get()
               for i in range(1, 4)):
            errors.append("Enter all three A-level grades")
        if not fields.get('course') or not fields['course'].get():
            errors.append("Select a course")

        return errors

    # When ``add_another`` is True the save handler returns to the
    # blank form instead of destroying the dialog; otherwise it
    # destroys on success (the old behaviour). Stored on the dialog
    # so the button command can flip it just before invoking save.
    dialog._add_another_after_save = False

    def _reset_for_next_entry() -> None:
        """Clear personal-info fields after a successful save so the
        admissions team can immediately enter the next student.
        Preserves the visa-section visibility state."""
        for key in (
                'first_name', 'middle_name', 'last_name',
                'nationality', 'passport_number',
                'visa_expiry_date', 'brp_number',
        ):
            w = fields.get(key)
            if w is not None and hasattr(w, 'delete'):
                w.delete(0, tk.END)
        if hasattr(fields.get('title'), 'set'):
            fields['title'].set('')
        if hasattr(fields.get('gender'), 'set'):
            fields['gender'].set('')
        if hasattr(fields.get('dob'), 'delete'):
            fields['dob'].delete(0, 'end')
        # Live preview goes back to its placeholder state.
        try:
            _refresh_live_preview()
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)
        try:
            fields['first_name'].focus_set()
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

    def create_student():
        """Create student with comprehensive data processing and random course assignment"""
        if not require_student_permission(self, "create_student", "create"):
            return
        try:
            # Validate form
            errors = validate_form()
            if errors:
                validation_label.config(text="; ".join(errors))
                return

            validation_label.config(text="")

            # Get form data
            first_name = fields['first_name'].get().strip()
            middle_name = fields['middle_name'].get().strip()
            last_name = fields['last_name'].get().strip()
            gender = fields['gender'].get()
            dob_text = fields['dob'].get().strip()

            # Resolve the chosen course and gate on the UCAS tariff entry
            # requirement derived from the applicant's A-level grades.
            chosen = course_label_map.get(fields['course'].get())
            if not chosen:
                validation_label.config(text=_t('gui.learners.students.student_crud_gui.create.text.please_select_a_course', default="Please select a course."))
                return

            alevel_pairs = [
                (fields[f'alevel_subj_{i}'].get().strip(), fields[f'alevel_grade_{i}'].get())
                for i in range(1, 4)
            ]
            ucas_tariff = _compute_tariff([g for _, g in alevel_pairs])
            entry_qualifications = _format_qualifications(alevel_pairs)

            if not _is_eligible(chosen, ucas_tariff):
                eligible = _eligible_courses(ucas_tariff)
                if eligible:
                    _populate_courses(eligible)
                    messagebox.showwarning(
                        _t('gui.learners.students.student_crud_gui.create.dialogs.entry_requirement_not_met', default="Entry requirement not met"),
                        f"You need {chosen['min_tariff']} UCAS points for "
                        f"{chosen['code']} - {chosen['name']}, but your grades give "
                        f"{ucas_tariff}.\n\nThe course list now shows only the "
                        f"{len(eligible)} course(s) you are eligible to study — "
                        "please choose one and save again.")
                else:
                    messagebox.showwarning(
                        _t('gui.learners.students.student_crud_gui.create.dialogs.entry_requirement_not_met', default="Entry requirement not met"),
                        f"Your tariff of {ucas_tariff} does not meet the entry "
                        "requirement for any course currently on offer.")
                return

            course = chosen['code']
            course_name = chosen['name']

            title = fields['title'].get() or ('Mr' if gender == 'male' else 'Ms')

            # Parse date and calculate age
            dob = datetime.strptime(dob_text, "%Y-%m-%d")
            now_dt = datetime.now()
            age = _compute_age(dob, now_dt)

            # All canonical writes and provisioning state transitions go
            # through the application service. The legacy implementation is
            # retained below temporarily for source-history readability but is
            # unreachable from this adapter.
            from education_system.systems.university.application.student_lifecycle_service import (
                StudentCommand,
                StudentLifecycleService,
            )
            actor = str((getattr(self.auth, 'current_user', {}) or {}).get('id', 'unknown'))
            lifecycle = StudentLifecycleService()
            created = lifecycle.create(
                StudentCommand(
                    first_name=first_name, middle_name=middle_name,
                    last_name=last_name, title=title, gender=gender,
                    dob=dob_text, course=course,
                    entry_qualifications=entry_qualifications,
                    ucas_tariff=ucas_tariff,
                ),
                actor_id=actor,
                idempotency_key=f"gui:create:{secrets.token_urlsafe(18)}",
            )
            provisioned = lifecycle.provision(created.student_id, auth=self.auth)
            if provisioned.provisioning_error:
                messagebox.showwarning(
                    "Provisioning pending",
                    f"Student {created.student_id} was saved safely, but provisioning "
                    f"is pending: {provisioned.provisioning_error}. The outbox can retry it.",
                    parent=dialog,
                )
            else:
                messagebox.showinfo(
                    _t("common.success"),
                    f"Student {created.student_id} was created and provisioned. "
                    "A single-use activation link was sent to their university email.",
                    parent=dialog,
                )
            if hasattr(self, 'view_students'):
                self.view_students()
            self.refresh_advanced_search()
            if getattr(dialog, '_add_another_after_save', False):
                dialog._add_another_after_save = False
                _reset_for_next_entry()
            else:
                dialog.destroy()
            return

            # Generate student ID and email
            student_id = str(secrets.randbelow(9000000) + 1000000).zfill(7)
            email_address = f"C{student_id}@tees.ac.uk"
            registration_time = now_dt.strftime('%Y-%m-%d %H:%M:%S')

            # Create student record in database
            conn = get_db_connection()
            if not conn:
                raise Exception("Database connection failed")

            cursor = conn.cursor()

            # FK checks off so module rows can be written before their catalog
            # entries exist; ``foreign_keys_off`` restores enforcement even if
            # the body raises.
            with foreign_keys_off(conn):
                # Guard against an ID / email collision before inserting — the
                # id is randomly generated, so on the rare clash regenerate it
                # (and its derived email) until unique.
                for _ in range(25):
                    cursor.execute(
                        "SELECT 1 FROM students WHERE student_id = ? OR email_address = ? "
                        "UNION SELECT 1 FROM users WHERE username = ?",
                        (student_id, email_address, student_id))
                    if cursor.fetchone() is None:
                        break
                    student_id = str(secrets.randbelow(9000000) + 1000000).zfill(7)
                    email_address = f"C{student_id}@tees.ac.uk"

                # Insert student record
                cursor.execute('''
                    INSERT INTO students (student_id, email_address, title, first_name, middle_name,
                        last_name, gender, dob, age, course, registration_datetime, status, enrollment_date,
                        entry_qualifications, ucas_tariff)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    student_id, email_address, title, first_name, middle_name,
                    last_name, gender, dob.strftime('%Y-%m-%d'), age, course, registration_time, 'Active', registration_time,
                    entry_qualifications, ucas_tariff
                ))

                # Enrol in the course's 18-module curriculum (6 per year x 3 years).
                curriculum = _enrol_student_in_curriculum(cursor, student_id, course, course_name)
                selected_modules = [m['module_code'] for m in curriculum]

                print(f"Enrolled student {student_id} in {len(selected_modules)} modules "
                      f"for course {course} ({course_name})")

                cursor.execute('''
                    UPDATE courses
                    SET current_enrollment = current_enrollment + 1
                    WHERE course_code = ? AND LOWER(COALESCE(status, 'active')) = 'active'
                ''', (course,))

            # Commit + close BEFORE the cross-domain bus side effects below.
            # Each bus service opens its own connection to write; SQLite
            # serialises writers, so running them while this transaction is
            # still open deadlocks (the inner write waits for this commit,
            # which never comes while we iterate bus calls). Committing first
            # avoids that freeze.
            conn.commit()
            conn.close()

            # ── Bus side effects, on fresh connections ─────────────
            # Each service is best-effort: a failure here never
            # blocks enrolment (the row is already committed above).
            try:
                from education_system.systems.university.domains.finance.domain.services.enrolment_fees import (
                    assess_module_enrolment_fee,
                )
                for code in selected_modules:
                    assess_module_enrolment_fee(student_id, code)
            except Exception as exc:
                print(f"Note: could not assess enrolment fees: {exc}")

            try:
                from education_system.systems.university.plugins.campus_commerce.domain.textbooks.services.library_holds import (
                    place_holds_for_enrolment,
                )
                for code in selected_modules:
                    place_holds_for_enrolment(student_id, code)
            except Exception as exc:
                print(f"Note: could not place library holds: {exc}")

            try:
                from education_system.systems.university.domains.academics.domain.services.course_management.timetable_sync import (
                    sync_for_student_enrolment,
                )
                for code in selected_modules:
                    sync_for_student_enrolment(student_id, code)
            except Exception as exc:
                print(f"Note: could not sync student timetable: {exc}")

            # Send registration confirmation email
            try:
                from education_system.systems.university.infrastructure.email.email_service import send_registration_confirmation
                send_registration_confirmation(student_id)
            except Exception as e:
                logging.warning(f"Failed to send registration confirmation email: {e}")

            # Create the login in both auth stores (legacy student_records.db
            # user + central auth.db shared-auth user). ``shared_ok`` gates
            # whether the student can actually sign in — if it failed we
            # surface a prominent warning below rather than swallowing it.
            temp_password = _default_student_password(first_name, student_id)
            login_result = _provision_student_login(
                self.auth,
                username=student_id,
                password=temp_password,
                email=email_address,
                first_name=first_name,
                last_name=last_name,
            )
            login_ok = login_result["shared_ok"]

            # If the admin flagged this student as international, create the
            # visa-sponsorship record and queue the right-to-study reminder.
            # Best-effort; a failure must not block enrolment.
            try:
                if fields.get('is_international') and fields['is_international'].get():
                    _create_visa_record_for_new_student(
                        student_id=student_id,
                        email_address=email_address,
                        first_name=first_name,
                        nationality=fields['nationality'].get().strip() or None,
                        passport_number=fields['passport_number'].get().strip() or None,
                        visa_expiry_date=fields['visa_expiry_date'].get().strip() or None,
                        brp_number=fields['brp_number'].get().strip() or None,
                        module_codes=selected_modules,
                    )
            except Exception as e:
                logging.warning(f"Visa record setup failed for {student_id}: {e}")

            # Auto-join the new student to the chat room of every module they
            # were enrolled on, then email them the list. Best-effort: a
            # failure here must not block the student create flow.
            try:
                _auto_join_module_chat_rooms(
                    student_id=student_id,
                    email_address=email_address,
                    first_name=first_name,
                    last_name=last_name,
                    module_codes=selected_modules,
                )
            except Exception as e:
                logging.warning(f"Auto-join of module chat rooms failed for {student_id}: {e}")

            # Success message with details
            modules_text = ""
            if curriculum:
                modules_text = f"\n\n    Enrolled in {len(curriculum)} modules (6 per year x 3 years):\n"
                by_year = {}
                for m in curriculum:
                    by_year.setdefault(m['year'], []).append(m)
                for yr in sorted(by_year):
                    modules_text += f"    Year {yr}:\n"
                    for m in by_year[yr]:
                        modules_text += f"      - {m['module_code']} {m['module_name']}\n"

            activation_sent = login_result.get("activation_sent", False)
            login_line = (
                f"Username: {student_id}\n"
                "A single-use account activation link has been sent to the "
                "student's university email address."
                if login_ok and activation_sent else
                f"Username: {student_id}\n"
                "⚠ The account was created, but its activation email could not be sent. "
                "Use the approved password-reset workflow to send a new link."
                if login_ok else
                "⚠ LOGIN ACCOUNT NOT CREATED — the student record was saved but\n"
                "  the sign-in account could not be set up, so they CANNOT log in\n"
                "  yet. An administrator must create their account manually.")

            success_msg = f"""Student created successfully!

{login_line}

Student Details:
- Student ID: {student_id}
- Name: {title} {first_name} {middle_name} {last_name}
- Email: {email_address}
- Course: {course} - {course_name}
- Entry grades: {entry_qualifications} ({ucas_tariff} UCAS pts)
- Age: {age}{modules_text}"""

            if login_ok:
                messagebox.showinfo(_t("common.success"), success_msg)
            else:
                messagebox.showwarning(_t("common.success"), success_msg)

            # Send welcome email to new student
            self._send_welcome_email_to_student(
                student_id=student_id,
                first_name=first_name,
                last_name=last_name,
                email_address=email_address,
                course=course
            )

            # Refresh student list and close dialog
            if hasattr(self, 'view_students'):
                self.view_students()
            self.refresh_advanced_search()  # ADD THIS LINE

            # If this record originated from the sixth-form import
            # picker, finalise the transfer: link the journey, reconcile
            # with any application already staged for this learner, end
            # the sixth-form enrolment, and notify the sixth-form admin
            # inbox. Best-effort: any failure here is logged and surfaced
            # as a warning but never reverses the successful university
            # create.
            sf_origin = getattr(dialog, '_sixth_form_origin_id', None)
            sf_journey_id = getattr(dialog, '_sixth_form_journey_id', None)
            sf_application_id = getattr(
                dialog, '_sixth_form_application_id', None)
            sf_handover = getattr(dialog, '_sixth_form_handover', None)
            # Consume the picker's state immediately so it can't leak onto
            # a later save in this dialog (e.g. via "Save & add another"),
            # which would otherwise re-fire the transfer against the
            # wrong student. Cleared up-front so a failure below can't
            # leave it set either.
            dialog._sixth_form_origin_id = None
            dialog._sixth_form_journey_id = None
            dialog._sixth_form_application_id = None
            dialog._sixth_form_handover = None
            if sf_origin:
                try:
                    from education_system.systems.sixth_form.domain.learners.students import (
                        students as sf_students,
                    )
                    moved_by = "university CRUD GUI"
                    try:
                        current_user = (
                            getattr(self, 'current_user', None)
                            or getattr(getattr(self, 'auth', None),
                                       'current_user', None)
                        )
                        if isinstance(current_user, dict):
                            moved_by = (current_user.get('username')
                                         or moved_by)
                    except Exception:
                        logger.debug("Suppressed exception", exc_info=True)
                    # Fill the journey's university slot BEFORE announcing
                    # the transfer. mark_transferred() publishes a
                    # progression event addressed to the university, and
                    # this process's own bus drainer consumes it within
                    # ~30s; the intake treats an unfilled slot as "not here
                    # yet" and builds a second, applications-side record for
                    # the student just created above. Writing the slot first
                    # is what turns that event into a no-op.
                    #
                    # Resolve the journey by the sixth-form id the picker
                    # handed us rather than by (name, DOB): the admin may
                    # have corrected a spelling or date on the form, and an
                    # identity match would then miss the journey the
                    # sixth-form record anchors and start a second one.
                    # Identity matching is the fallback, for a sixth-form
                    # student that predates the journey registry.
                    # Best-effort throughout: the university student stands
                    # regardless.
                    journey_id = sf_journey_id
                    try:
                        from education_system.platform.cross_system import (
                            identity_service,
                            progression,
                        )
                        if not journey_id:
                            anchor = identity_service.find_by_student(
                                "sixth_form", sf_origin)
                            journey_id = (anchor["journey_id"] if anchor
                                          else None)
                        if journey_id:
                            identity_service.link_system(
                                journey_id, "university",
                                student_id=student_id, set_current=True)
                        else:
                            journey_id = progression.register_local_student(
                                "university",
                                student_id=student_id,
                                first_name=first_name,
                                last_name=last_name,
                                date_of_birth=dob_text,
                            )
                        if journey_id:
                            # Once: mark_transferred() records the same hop
                            # a moment later, and a learner who moved up one
                            # phase should read as one transition, not two.
                            identity_service.record_transition_once(
                                journey_id,
                                from_system="sixth_form",
                                to_system="university",
                                reason=f"Sixth-form import by {moved_by}",
                            )
                    except Exception:
                        logger.exception(
                            "Journey link failed for sixth-form import "
                            "%s -> %s; the bus intake may now create a "
                            "duplicate application", sf_origin, student_id)

                    # Reconcile with the applications side. If the bus
                    # already staged this learner as an applicant, bind the
                    # student just created to it: one person must not end up
                    # as an active student *and* a pending applicant with
                    # nothing joining the two. The picker re-checks at
                    # selection time; re-read here because the drainer runs
                    # every ~30s and may have staged one since.
                    _attach_sixth_form_application(
                        journey_id=journey_id,
                        application_id=sf_application_id,
                        student_id=student_id,
                        actor_id=moved_by,
                    )

                    sf_students.mark_transferred(
                        sf_origin, moved_by=moved_by)

                    # Their application to us is over: remove the UCAS
                    # choice that lists them as an applicant here, so the
                    # import picker stops showing somebody who has already
                    # arrived. Best-effort — the student stands regardless.
                    _clear_ucas_application_after_import(
                        sf_origin, student_id, actor=moved_by)

                    logger.info(
                        "Completed sixth-form transfer for %s -> "
                        "university student %s (journey=%s, handover "
                        "fields=%s)",
                        sf_origin, student_id, journey_id,
                        ", ".join(sf_handover.included)
                        if sf_handover else "not assembled",
                    )
                    # Copy the medical record across — but only if the
                    # learner consented to it. Health data is special
                    # category, the handover spec marks it as needing
                    # consent, and this route used to copy every condition,
                    # medication, allergy and GP detail on the strength of
                    # somebody clicking Save. The import seam now refuses
                    # without a basis; ask the operator to name one rather
                    # than deciding on their behalf. Failure is surfaced
                    # separately so the user sees that the status/login/
                    # email cleanup succeeded even if the medical mapping
                    # had a problem.
                    _import_sixth_form_medical_record(
                        parent=dialog,
                        uni_student_id=student_id,
                        sf_student_id=sf_origin,
                        actor=moved_by,
                    )
                except Exception as transfer_err:
                    logger.exception(
                        "Sixth-form transfer side-effects failed "
                        "for origin=%s (university student %s was "
                        "still created)",
                        sf_origin, student_id,
                    )
                    messagebox.showwarning(
                        _t('gui.learners.students.student_crud_gui.create.dialogs.sixth_form_transfer', default="Sixth-form transfer"),
                        "The university record was created, but the "
                        "sixth-form side-effects could not all be "
                        "applied:\n\n"
                        f"{transfer_err}\n\n"
                        "Please verify the sixth-form student is marked "
                        "'Left' and that their sixth-form access has been "
                        "revoked. Their sign-in account itself stays "
                        "active — it is the same person, now a university "
                        "student.",
                    )

            # Honour "Save & add another": keep the dialog open and
            # reset the personal-info fields so the next student can
            # be entered immediately. Otherwise destroy as before.
            if getattr(dialog, '_add_another_after_save', False):
                dialog._add_another_after_save = False
                _reset_for_next_entry()
            else:
                dialog.destroy()

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("student.failed_create_student").replace("{error}", str(e)))

    # Buttons
    button_frame = ttk.Frame(footer_frame)
    button_frame.pack(pady=(4, 0))

    ttk.Button(button_frame, text=_t("student.create_student"), command=create_student,
              style="Accent.TButton").pack(side=tk.LEFT, padx=10)

    def _save_and_add_another():
        dialog._add_another_after_save = True
        create_student()

    ttk.Button(button_frame, text=_t('gui.learners.students.student_crud_gui.create.buttons.save_add_another', default="Save & add another"),
                command=_save_and_add_another).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_t("student.clear_form"),
              command=lambda: [field.delete(0, tk.END) if hasattr(field, 'delete')
                              else field.set('') for field in fields.values()]).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_t("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    # Set focus
    fields['first_name'].focus()
