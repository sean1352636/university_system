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
from education_system.systems.university.domains.admissions.domain.services.admissions_selection import (
    list_active_courses as _list_active_courses,
    compute_tariff as _compute_tariff,
    format_qualifications as _format_qualifications,
    eligible_courses as _eligible_courses,
    is_eligible as _is_eligible,
    enrol_student_in_curriculum as _enrol_student_in_curriculum,
    GRADE_CHOICES as _GRADE_CHOICES,
    QUALIFICATION_TYPES as _QUALIFICATION_TYPES,
    compute_tariff_entries as _compute_tariff_entries,
    format_qualification_entries as _format_qualification_entries,
    grades_for as _grades_for,
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
        from education_system.systems.university.services.bus import admissions_bus
        if not application_id:
            existing = admissions_bus.application_for_journey(
                journey_id)
            application_id = (existing["application_id"] if existing
                              else None)
        if not application_id:
            return
        admissions_bus.attach_direct_enrolment(
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
    from education_system.systems.university.domains.health.domain.health.records import (
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
    dialog = self.create_themed_toplevel(_t("student.create_new_student"), "1340x660")
    dialog.minsize(1180, 560)

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

    # Footer (status note, validation message, action buttons) is packed
    # BEFORE the body and anchored to the bottom, so on a short screen the
    # body gives up height first and the Create button is never pushed off.
    footer_frame = ttk.Frame(main_frame)
    footer_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(12, 0))

    # Three-column body (personal | academic | contact + visa) keeps the
    # form short enough for a 768-pixel-high screen.
    body_frame = ttk.Frame(main_frame)
    body_frame.pack(fill=tk.BOTH, expand=True)
    body_frame.columnconfigure(0, weight=4, uniform="cols")
    body_frame.columnconfigure(1, weight=4, uniform="cols")
    body_frame.columnconfigure(2, weight=3, uniform="cols")
    body_frame.rowconfigure(0, weight=1)

    left_col = ttk.Frame(body_frame)
    left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
    mid_col = ttk.Frame(body_frame)
    mid_col.grid(row=0, column=1, sticky="nsew", padx=8)
    right_col = ttk.Frame(body_frame)
    right_col.grid(row=0, column=2, sticky="nsew", padx=(8, 0))

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
    personal_frame = ttk.LabelFrame(left_col, text=_t("student.personal_info"), padding=(15, 8))
    personal_frame.pack(fill=tk.BOTH, expand=True)
    # Fields stretch with the column rather than fixing a width, so the
    # form fits a 1366-pixel-wide screen instead of running off the side.
    personal_frame.columnconfigure(1, weight=1)

    # Title/Prefix
    ttk.Label(personal_frame, text=_t("student.title_label")).grid(row=1, column=0, sticky=tk.W, pady=3)
    fields['title'] = ttk.Combobox(personal_frame, values=['Mr', 'Ms', 'Mrs', 'Dr', 'Prof'],
                                  state='readonly', width=16)
    fields['title'].grid(row=1, column=1, pady=3, padx=(10, 0), sticky=tk.EW)

    # First Name
    ttk.Label(personal_frame, text=_t("student.first_name_required")).grid(row=2, column=0, sticky=tk.W, pady=3)
    fields['first_name'] = ttk.Entry(personal_frame, width=18)
    fields['first_name'].grid(row=2, column=1, pady=3, padx=(10, 0), sticky=tk.EW)

    # Middle Name
    ttk.Label(personal_frame, text=_t("student.middle_name_label")).grid(row=3, column=0, sticky=tk.W, pady=3)
    fields['middle_name'] = ttk.Entry(personal_frame, width=18)
    fields['middle_name'].grid(row=3, column=1, pady=3, padx=(10, 0), sticky=tk.EW)

    # Last Name
    ttk.Label(personal_frame, text=_t("student.last_name_required")).grid(row=4, column=0, sticky=tk.W, pady=3)
    fields['last_name'] = ttk.Entry(personal_frame, width=18)
    fields['last_name'].grid(row=4, column=1, pady=3, padx=(10, 0), sticky=tk.EW)

    # Preferred name — what the other systems' add forms also ask.
    ttk.Label(personal_frame, text="Preferred name").grid(row=5, column=0, sticky=tk.W, pady=3)
    fields['preferred_name'] = ttk.Entry(personal_frame, width=18)
    fields['preferred_name'].grid(row=5, column=1, pady=3, padx=(10, 0), sticky=tk.EW)

    # Gender
    ttk.Label(personal_frame, text=_t("student.gender_required")).grid(row=6, column=0, sticky=tk.W, pady=3)
    from education_system.systems.university.application.students.lifecycle import (
        GENDER_OPTIONS as _GENDER_OPTIONS,
    )
    fields['gender'] = ttk.Combobox(personal_frame, values=list(_GENDER_OPTIONS),
                                   state='readonly', width=16)
    fields['gender'].grid(row=6, column=1, pady=3, padx=(10, 0), sticky=tk.EW)

    # Date of Birth — spinbox trio (year / month / day) instead of a
    # plain Entry, so users can't typo the format and the day range
    # is automatically clamped to the selected month's length.
    ttk.Label(personal_frame, text=_t("student.dob_required")).grid(row=7, column=0, sticky=tk.W, pady=3)
    fields['dob'] = _DOBPicker(
        personal_frame, on_change=lambda: _refresh_live_preview())
    fields['dob'].grid(row=7, column=1, pady=3, padx=(10, 0), sticky=tk.W)

    # Live preview — read-only "Will be created as…" panel that
    # updates as the user types names / picks a DOB, so admissions
    # can spot typos in id / email / temp password BEFORE the
    # record is committed and the welcome email goes out.
    preview_frame = ttk.LabelFrame(
        personal_frame,
        text=_t('gui.learners.students.student_crud_gui.create.labels.will_be_created_as', default="Will be created as …"),
        padding=(10, 6),
    )
    preview_frame.grid(row=8, column=0, columnspan=2,
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
            preview_vars["student_id"].set("C####### (on save)")
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

    # Emergency contact, medical notes and notes — what the other systems'
    # add forms ask for. The contact and medical notes are saved to the
    # health record (application/students/registration_extras), the notes
    # on the student record. Single-line fields keep the dialog short.
    from education_system.systems.university.application.students import (
        record_rules as _rules,
    )
    care_frame = ttk.LabelFrame(left_col, text="Emergency contact & medical", padding=(12, 6))
    care_frame.pack(fill=tk.X, pady=(8, 0))
    care_frame.columnconfigure(1, weight=1)
    care_frame.columnconfigure(3, weight=1)
    ttk.Label(care_frame, text="Name").grid(row=0, column=0, sticky=tk.W, pady=2)
    fields['emergency_contact_name'] = ttk.Entry(care_frame, width=14)
    fields['emergency_contact_name'].grid(row=0, column=1, padx=(6, 8), pady=2, sticky=tk.EW)
    ttk.Label(care_frame, text="Phone").grid(row=0, column=2, sticky=tk.W, pady=2)
    fields['emergency_contact_phone'] = ttk.Entry(care_frame, width=12)
    fields['emergency_contact_phone'].grid(row=0, column=3, padx=(6, 0), pady=2, sticky=tk.EW)
    ttk.Label(care_frame, text="Relationship").grid(row=1, column=0, sticky=tk.W, pady=2)
    fields['emergency_contact_relationship'] = ttk.Combobox(
        care_frame, values=["", *_rules.EMERGENCY_RELATIONSHIPS], state='readonly', width=14)
    fields['emergency_contact_relationship'].grid(row=1, column=1, padx=(6, 8), pady=2,
                                                  sticky=tk.EW)
    ttk.Label(care_frame, text="Medical notes").grid(row=2, column=0, sticky=tk.W, pady=2)
    fields['medical_notes'] = ttk.Entry(care_frame)
    fields['medical_notes'].grid(row=2, column=1, columnspan=3, padx=(6, 0), pady=2,
                                 sticky=tk.EW)

    # Contact and study details — two pairs per row so the dialog still fits
    # a 768-pixel-high screen without scrolling.
    from education_system.systems.university.application.students import (
        record_rules as _record_rules,
    )
    contact_frame = ttk.LabelFrame(right_col, text="Contact & study", padding=(12, 8))
    contact_frame.pack(fill=tk.X)
    for row, (key, label) in enumerate((("phone", "Phone"), ("personal_email", "Personal email"),
                                        ("address_line1", "Address line 1"),
                                        ("address_line2", "Address line 2"),
                                        ("town", "Town"),
                                        ("postcode", "Postcode"),
                                        ("nationality", "Nationality"))):
        ttk.Label(contact_frame, text=label).grid(row=row, column=0, sticky=tk.W, pady=2)
        fields[key] = ttk.Entry(contact_frame, width=12 if key == "postcode" else 26)
        fields[key].grid(row=row, column=1, padx=(6, 0), pady=2, sticky=tk.W)
    for row, (key, label, values, default) in enumerate((
            ("mode_of_study", "Mode of study", _record_rules.MODES, "full-time"),
            ("fee_status", "Fee status", _record_rules.FEE_STATUSES, "home")), 7):
        ttk.Label(contact_frame, text=label).grid(row=row, column=0, sticky=tk.W, pady=2)
        fields[key] = ttk.Combobox(contact_frame, values=list(values), state='readonly', width=14)
        fields[key].set(default)
        fields[key].grid(row=row, column=1, padx=(6, 0), pady=2, sticky=tk.W)

    # Academic Information Section (right column)
    academic_frame = ttk.LabelFrame(mid_col, text=_t("student.academic_info"), padding=12)
    academic_frame.pack(fill=tk.X)
    # Staff notes on the record (the other systems' add forms ask too).
    notes_frame = ttk.LabelFrame(mid_col, text="Notes", padding=(12, 6))
    notes_frame.pack(fill=tk.X, pady=(8, 0))
    fields['notes'] = ttk.Entry(notes_frame)
    fields['notes'].pack(fill=tk.X)
    academic_frame.columnconfigure(1, weight=1)

    # Course — chosen from the live catalogue. Reading the catalogue here
    # (rather than hard-coding CS/DS) means any course an admin creates via
    # course management appears in this dropdown automatically.
    ttk.Label(academic_frame, text=_t("student.course_label")).grid(row=0, column=0, sticky=tk.W, pady=5)
    fields['course'] = ttk.Combobox(academic_frame, state='readonly', width=30)
    fields['course'].grid(row=0, column=1, pady=5, padx=(10, 0), sticky=tk.EW)

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

    # Level 3 qualifications → UCAS tariff (gates course eligibility). Any
    # mix of A levels, AS levels, EPQ, BTECs and T Levels, as many rows as
    # the student took; three A-level rows to start. The rows scroll inside a
    # fixed-height strip so extra qualifications don't push the form off a
    # 768-pixel screen.
    grades_frame = ttk.LabelFrame(academic_frame, text=_t('gui.learners.students.student_crud_gui.create.labels.qualifications_ucas_tariff', default="Qualifications (UCAS tariff)"), padding=10)
    grades_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(8, 0))

    tariff_var = tk.StringVar(value=_t('gui.learners.students.student_crud_gui.create.values.ucas_tariff_0', default="UCAS tariff: 0"))

    head = ttk.Frame(grades_frame)
    head.grid(row=0, column=0, columnspan=4, sticky=tk.EW)
    for text, width in (("Qualification", 17), ("Subject", 0), ("Grade", 10)):
        ttk.Label(head, text=text, width=width or None, foreground="#555555").pack(
            side=tk.LEFT, fill=tk.X, expand=not width, padx=(0, 4))
    ttk.Label(head, text="", width=3).pack(side=tk.LEFT)

    rows_canvas = tk.Canvas(grades_frame, height=118, highlightthickness=0, borderwidth=0)
    rows_scroll = ttk.Scrollbar(grades_frame, orient=tk.VERTICAL, command=rows_canvas.yview)
    rows_canvas.configure(yscrollcommand=rows_scroll.set)
    rows_holder = ttk.Frame(rows_canvas)
    rows_window = rows_canvas.create_window((0, 0), window=rows_holder, anchor="nw")
    rows_holder.bind("<Configure>", lambda _e: rows_canvas.configure(
        scrollregion=rows_canvas.bbox("all")))
    rows_canvas.bind("<Configure>", lambda e: rows_canvas.itemconfigure(rows_window, width=e.width))
    rows_canvas.grid(row=1, column=0, columnspan=4, sticky=tk.EW)
    rows_scroll.grid(row=1, column=4, sticky=tk.NS)
    qual_rows: list[dict] = []

    def _qual_entries():
        """``[(type, subject, grade), ...]`` for every row, in order."""
        return [(r['type'].get(), r['subject'].get().strip(), r['grade'].get()) for r in qual_rows]

    def _recompute_tariff(*_a):
        graded = [e for e in _qual_entries() if e[2]]
        tariff_var.set(f"UCAS tariff: {_compute_tariff_entries(graded)}")

    def _sync_qual_fields():
        # Row i keeps the alevel_type_/alevel_subj_/alevel_grade_ names the
        # sixth-form import picker fills in.
        for key in [k for k in fields if k.startswith(('alevel_type_', 'alevel_subj_',
                                                       'alevel_grade_'))]:
            del fields[key]
        for i, r in enumerate(qual_rows, 1):
            fields[f'alevel_type_{i}'] = r['type']
            fields[f'alevel_subj_{i}'] = r['subject']
            fields[f'alevel_grade_{i}'] = r['grade']

    def _add_qual_row(qtype="A level", subject="", grade=""):
        row = ttk.Frame(rows_holder)
        row.pack(fill=tk.X, pady=1)
        entry = {'frame': row}
        entry['type'] = ttk.Combobox(row, values=list(_QUALIFICATION_TYPES), state='readonly',
                                     width=17)
        entry['type'].set(qtype)
        entry['subject'] = ttk.Entry(row, width=10)
        entry['subject'].insert(0, subject)
        entry['grade'] = ttk.Combobox(row, values=_grades_for(qtype), state='readonly', width=10)
        if grade:
            entry['grade'].set(grade)

        def _type_changed(_e=None):
            choices = _grades_for(entry['type'].get())
            entry['grade'].config(values=choices)
            if entry['grade'].get() not in choices:
                entry['grade'].set('')
            _recompute_tariff()

        entry['type'].bind('<<ComboboxSelected>>', _type_changed)
        entry['grade'].bind('<<ComboboxSelected>>', _recompute_tariff)
        entry['type'].pack(side=tk.LEFT, padx=(0, 4))
        entry['subject'].pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        entry['grade'].pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(row, text="✕", width=3,
                   command=lambda: _remove_qual_row(entry)).pack(side=tk.LEFT)
        qual_rows.append(entry)
        _sync_qual_fields()
        _recompute_tariff()
        rows_canvas.after_idle(lambda: rows_canvas.yview_moveto(1.0))
        return entry

    def _remove_qual_row(entry):
        if len(qual_rows) == 1:
            # The last row is cleared rather than removed.
            entry['type'].set("A level")
            entry['grade'].config(values=_grades_for("A level"))
            entry['subject'].delete(0, tk.END)
            entry['grade'].set('')
        else:
            qual_rows.remove(entry)
            entry['frame'].destroy()
        _sync_qual_fields()
        _recompute_tariff()

    def _reset_qual_rows():
        for entry in list(qual_rows):
            entry['frame'].destroy()
        qual_rows.clear()
        for _ in range(3):
            _add_qual_row()
        rows_canvas.yview_moveto(0)

    _reset_qual_rows()
    dialog._add_qual_row = _add_qual_row   # the sixth-form import adds rows for extra A levels
    ttk.Button(grades_frame, text="+ Add qualification", command=_add_qual_row).grid(
        row=2, column=0, columnspan=4, sticky=tk.W, pady=(4, 0))

    # Tariff + eligibility button, and the override, sit on rows of their
    # own so their long labels don't widen the subject column.
    tariff_row = ttk.Frame(grades_frame)
    tariff_row.grid(row=4, column=0, columnspan=4, sticky=tk.EW, pady=(6, 0))
    ttk.Label(tariff_row, textvariable=tariff_var, foreground="#1a3f8c",
              font=('Arial', 10, 'bold')).pack(side=tk.LEFT)

    def _filter_to_eligible():
        t = _compute_tariff_entries([e for e in _qual_entries() if e[2]])
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

    ttk.Button(tariff_row, text=_t('gui.learners.students.student_crud_gui.create.buttons.show_courses_i_m_eligible_for', default="Show courses I'm eligible for"),
               command=_filter_to_eligible).pack(side=tk.RIGHT)

    # Admissions override: admit below the tariff with a recorded reason.
    fields['override'] = tk.BooleanVar(value=False)
    override_row = ttk.Frame(grades_frame)
    override_row.grid(row=5, column=0, columnspan=4, sticky=tk.EW, pady=(6, 0))
    ttk.Checkbutton(override_row, text="Admissions override, reason:",
                    variable=fields['override']).pack(side=tk.LEFT)
    fields['override_reason'] = ttk.Entry(override_row, width=20)
    fields['override_reason'].pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0))
    grades_frame.columnconfigure(1, weight=1)

    # Entry route: only A levels are checked against the UCAS tariff;
    # other routes record the qualifications for admissions to judge.
    route_labels = {label: key for key, label in _record_rules.ENTRY_ROUTES.items()}
    ttk.Label(academic_frame, text="Entry route").grid(row=2, column=0, sticky=tk.W, pady=5)
    fields['entry_route'] = ttk.Combobox(academic_frame, values=list(route_labels),
                                         state='readonly', width=30)
    fields['entry_route'].set(_record_rules.ENTRY_ROUTES['a_levels'])
    fields['entry_route'].grid(row=2, column=1, pady=5, padx=(10, 0), sticky=tk.EW)
    qual_label = ttk.Label(academic_frame, text="Qualifications")
    fields['qualifications'] = ttk.Entry(academic_frame, width=30)

    def _route_key():
        return route_labels.get(fields['entry_route'].get(), 'a_levels')

    def _on_route(*_a):
        if _route_key() == 'a_levels':
            qual_label.grid_remove()
            fields['qualifications'].grid_remove()
            grades_frame.grid()
            _populate_courses(_all_courses)
        else:
            grades_frame.grid_remove()
            qual_label.grid(row=3, column=0, sticky=tk.W, pady=5)
            fields['qualifications'].grid(row=3, column=1, pady=5, padx=(10, 0), sticky=tk.EW)
    fields['entry_route'].bind('<<ComboboxSelected>>', _on_route)

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
    # The visa profile entered in the full visa window. The student id only
    # exists after Create, so it's held here and written by _after_create.
    dialog._visa_details = None
    visa_summary = tk.StringVar(value="")

    def _show_visa_summary() -> None:
        d = dialog._visa_details or {}
        parts = [f"Passport {d['passport_number']}" if d.get('passport_number') else None,
                 f"visa expires {d['visa_expiry_date']}" if d.get('visa_expiry_date') else None,
                 f"BRP {d['brp_number']}" if d.get('brp_number') else None,
                 f"status {d.get('status') or 'pending'}"]
        visa_summary.set("Visa details entered: " + ", ".join(p for p in parts if p))
        intl_details_frame.grid(row=1, column=0, columnspan=4,
                                sticky=(tk.W, tk.E), pady=(6, 0))

    def _visa_saved(profile) -> None:
        dialog._visa_details = dict(profile)
        # Nationality is asked for every student; keep the two in step.
        if profile.get('nationality') and not fields['nationality'].get().strip():
            fields['nationality'].insert(0, profile['nationality'])
        _show_visa_summary()

    def _visa_closed() -> None:
        # Closed without saving anything: the student isn't on a visa after all.
        if not dialog._visa_details:
            fields['is_international'].set(False)
            intl_details_frame.grid_forget()

    def _open_visa_window() -> None:
        """The full visa window, filled from this form; saving returns here."""
        chosen = course_label_map.get(fields['course'].get())
        name = " ".join(x for x in (fields['first_name'].get().strip(),
                                     fields['last_name'].get().strip()) if x)
        intake = dict(dialog._visa_details or {})
        intake.update(
            name=name,
            course=f"{chosen['code']} - {chosen['name']}" if chosen else "",
            programme=chosen['name'] if chosen else "",
        )
        if not intake.get('nationality'):
            intake['nationality'] = fields['nationality'].get().strip()
        try:
            from education_system.systems.university.services.bus import visa_bus
            visa_bus.open_new_student_visa(dialog, intake=intake, on_save=_visa_saved,
                                           on_close=_visa_closed)
        except Exception as e:
            logger.exception("Could not open the visa window")
            messagebox.showerror(_t("common.error"), f"Could not open the visa window: {e}",
                                 parent=dialog)
            _visa_closed()

    def _toggle_visa_details() -> None:
        if fields['is_international'].get():
            _open_visa_window()
        else:
            dialog._visa_details = None
            intl_details_frame.grid_forget()

    ttk.Checkbutton(intl_frame, text=_t('gui.learners.students.student_crud_gui.create.buttons.this_student_is_on_a_student_route_visa', default="This student is on a Student Route visa"),
                    variable=fields['is_international'],
                    command=_toggle_visa_details).grid(
        row=0, column=0, columnspan=4, sticky=tk.W, pady=(0, 6))

    # Shown once visa details are saved: what was entered, and a way back in.
    ttk.Label(intl_details_frame, textvariable=visa_summary, wraplength=300,
              justify=tk.LEFT).grid(row=0, column=0, sticky=tk.W)
    ttk.Button(intl_details_frame, text="Edit visa details…",
               command=_open_visa_window).grid(row=1, column=0, sticky=tk.W, pady=(6, 0))

    # Disability and university accommodation (2026-10-19). Like the visa,
    # both are entered here and saved once the student exists: the
    # disabilities through the Disability & Accessibility portal, the
    # accommodation as a Pending application in Housing for staff to
    # approve or reject.
    support_frame = ttk.LabelFrame(right_col, text="Disability & accommodation", padding=(12, 8))
    support_frame.pack(fill=tk.X, pady=(10, 0))
    support_frame.columnconfigure(0, weight=1)

    fields['has_disability'] = tk.BooleanVar(value=False)
    dialog._disabilities = None
    disability_summary = tk.StringVar(value="")
    disability_details = ttk.Frame(support_frame)

    def _show_disability_summary() -> None:
        items = dialog._disabilities or []
        try:
            from education_system.systems.university.services.bus import disability_bus
            labels = disability_bus.categories()
        except Exception:
            labels = {}
        names = [labels.get(i['category'], i['category']).split(' (')[0] for i in items]
        asked = sum(1 for i in items if i.get('adjustment_type'))
        disability_summary.set(
            f"{len(items)} entered: " + "; ".join(names)
            + (f" — {asked} adjustment request(s)" if asked else ""))
        disability_details.grid(row=1, column=0, sticky=tk.EW, pady=(2, 4))

    def _disabilities_saved(items) -> None:
        dialog._disabilities = list(items)
        _show_disability_summary()

    def _disability_window_closed() -> None:
        # Closed without saving anything: untick.
        if not dialog._disabilities:
            fields['has_disability'].set(False)
            disability_details.grid_forget()

    def _open_disability_window() -> None:
        chosen = course_label_map.get(fields['course'].get())
        name = " ".join(x for x in (fields['first_name'].get().strip(),
                                     fields['last_name'].get().strip()) if x)
        try:
            from education_system.systems.university.services.bus import disability_bus
            disability_bus.open_new_student_disabilities(
                dialog, self.auth,
                intake={'name': name, 'items': dialog._disabilities or [],
                        'course': f"{chosen['code']} - {chosen['name']}" if chosen else ""},
                on_save=_disabilities_saved, on_close=_disability_window_closed)
        except Exception as e:
            logger.exception("Could not open the Disability & Accessibility portal")
            messagebox.showerror(_t("common.error"),
                                 f"Could not open Disability & Accessibility: {e}", parent=dialog)
            _disability_window_closed()

    def _toggle_disability() -> None:
        if fields['has_disability'].get():
            _open_disability_window()
        else:
            dialog._disabilities = None
            disability_details.grid_forget()

    ttk.Checkbutton(support_frame, text="Does the student have a disability?",
                    variable=fields['has_disability'],
                    command=_toggle_disability).grid(row=0, column=0, sticky=tk.W)
    ttk.Label(disability_details, textvariable=disability_summary, wraplength=300,
              justify=tk.LEFT).pack(anchor=tk.W)
    ttk.Button(disability_details, text="Edit disabilities…",
               command=_open_disability_window).pack(anchor=tk.W, pady=(2, 0))

    fields['wants_housing'] = tk.BooleanVar(value=False)
    housing_details = ttk.Frame(support_frame)
    hall_ids: dict = {}
    NO_HALL = "No preference"

    def _toggle_housing() -> None:
        if not fields['wants_housing'].get():
            housing_details.grid_forget()
            return
        if not hall_ids:
            try:
                from education_system.systems.university.services.bus import housing_bus
                hall_ids.update({name: bid for bid, name in housing_bus.halls()})
                fields['housing_room_type']['values'] = list(housing_bus.room_types())
            except Exception:
                logger.exception("Could not read the halls of residence")
            fields['housing_hall']['values'] = [NO_HALL, *hall_ids]
        housing_details.grid(row=3, column=0, sticky=tk.EW, pady=(2, 0))

    ttk.Checkbutton(support_frame, text="Does the student want university accommodation?",
                    variable=fields['wants_housing'],
                    command=_toggle_housing).grid(row=2, column=0, sticky=tk.W, pady=(4, 0))
    ttk.Label(housing_details, text="Hall").grid(row=0, column=0, sticky=tk.W, pady=2)
    fields['housing_hall'] = ttk.Combobox(housing_details, state='readonly', width=26)
    fields['housing_hall'].set(NO_HALL)
    fields['housing_hall'].grid(row=0, column=1, columnspan=3, sticky=tk.W, padx=(6, 0))
    ttk.Label(housing_details, text="Room").grid(row=1, column=0, sticky=tk.W, pady=2)
    fields['housing_room_type'] = ttk.Combobox(housing_details, state='readonly', width=10)
    fields['housing_room_type'].grid(row=1, column=1, sticky=tk.W, padx=(6, 0))
    ttk.Label(housing_details, text="Months").grid(row=1, column=2, sticky=tk.W, padx=(8, 0))
    fields['housing_months'] = ttk.Entry(housing_details, width=4)
    fields['housing_months'].insert(0, "9")
    fields['housing_months'].grid(row=1, column=3, sticky=tk.W, padx=(6, 0))
    ttk.Label(housing_details, text="Move in").grid(row=2, column=0, sticky=tk.W, pady=2)
    fields['housing_move_in'] = ttk.Entry(housing_details, width=11)
    fields['housing_move_in'].insert(0, datetime.now().strftime('%Y-%m-%d'))
    fields['housing_move_in'].grid(row=2, column=1, sticky=tk.W, padx=(6, 0))
    ttk.Label(housing_details, text="Filed in Housing as Pending, for staff to approve.",
              foreground="#555555", wraplength=300).grid(row=3, column=0, columnspan=4,
                                                         sticky=tk.W)

    def _clear_support() -> None:
        fields['has_disability'].set(False)
        dialog._disabilities = None
        disability_details.grid_forget()
        fields['wants_housing'].set(False)
        housing_details.grid_forget()
        fields['housing_hall'].set(NO_HALL)
        fields['housing_room_type'].set('')
        fields['housing_months'].delete(0, tk.END)
        fields['housing_months'].insert(0, "9")
        fields['housing_move_in'].delete(0, tk.END)
        fields['housing_move_in'].insert(0, datetime.now().strftime('%Y-%m-%d'))

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

        # A levels need all three grades for the tariff check; any other
        # route needs the qualifications written down.
        if _route_key() == 'a_levels':
            entries = _qual_entries()
            if not any(grade for _t_, _s, grade in entries):
                errors.append("Enter at least one qualification and its grade")
            elif any(subject and not grade for _t_, subject, grade in entries):
                errors.append("Give a grade for every qualification with a subject, "
                              "or remove the row")
        elif not fields['qualifications'].get().strip():
            errors.append("Enter the applicant's qualifications")
        if fields['override'].get() and not fields['override_reason'].get().strip():
            errors.append("Give the reason for the admissions override")
        # Emergency contact / medical notes / postcode: the service's rules,
        # checked here so a half-filled contact is caught before saving.
        values = {k: fields[k].get() for k in (
            'emergency_contact_name', 'emergency_contact_relationship',
            'emergency_contact_phone', 'medical_notes', 'preferred_name',
            'postcode', 'notes', 'address_line1', 'address_line2', 'town')}
        problems = {**_rules.validate_registration(values), **_rules.validate_details(values)}
        errors += [f"{k.replace('_', ' ').capitalize()} {v}" for k, v in problems.items()]
        errors += [f"{k.replace('_', ' ')} {v}" for k, v in _record_rules.validate_details(
            {k: fields[k].get() for k in ('phone', 'personal_email')}).items()]
        if not fields.get('course') or not fields['course'].get():
            errors.append("Select a course")
        if fields['is_international'].get() and not dialog._visa_details:
            errors.append("Enter the visa details, or untick the Student Route visa box")
        if fields['has_disability'].get() and not dialog._disabilities:
            errors.append("Enter the disabilities, or untick the disability box")
        if fields['wants_housing'].get():
            if not fields['housing_room_type'].get():
                errors.append("Choose a room type for the accommodation")
            try:
                datetime.strptime(fields['housing_move_in'].get().strip(), "%Y-%m-%d")
            except ValueError:
                errors.append("Give the accommodation move-in date as YYYY-MM-DD")
            months = fields['housing_months'].get().strip()
            if not (months.isdigit() and 1 <= int(months) <= 60):
                errors.append("Give the accommodation length in months (1-60)")

        return errors

    # When ``add_another`` is True the save handler returns to the
    # blank form instead of destroying the dialog; otherwise it
    # destroys on success (the old behaviour). Stored on the dialog
    # so the button command can flip it just before invoking save.
    dialog._add_another_after_save = False

    def _clear_visa() -> None:
        fields['is_international'].set(False)
        dialog._visa_details = None
        intl_details_frame.grid_forget()

    def _reset_for_next_entry() -> None:
        """Clear personal-info fields after a successful save so the
        admissions team can immediately enter the next student.
        The visa, disability and accommodation details belong to the
        student just saved, so they go too."""
        _clear_visa()
        _clear_support()
        _reset_qual_rows()
        for key in (
                'first_name', 'middle_name', 'last_name', 'nationality',
                'phone', 'personal_email', 'address_line1', 'address_line2', 'town',
                'qualifications',
                'override_reason', 'preferred_name', 'postcode', 'notes',
                'emergency_contact_name', 'emergency_contact_phone', 'medical_notes',
        ):
            w = fields.get(key)
            if w is not None and hasattr(w, 'delete'):
                w.delete(0, tk.END)
        if hasattr(fields.get('title'), 'set'):
            fields['title'].set('')
        if hasattr(fields.get('gender'), 'set'):
            fields['gender'].set('')
        fields['emergency_contact_relationship'].set('')
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

    def _after_create(student_id, email_address, first_name, last_name, dob_text,
                      selected_modules):
        """Steps the lifecycle service does not own: the visa record for an
        international student, and finishing a sixth-form (UCAS) admission.
        Each is best-effort and never undoes the created record."""
        # If the admin flagged this student as international, create the
        # visa-sponsorship record and queue the right-to-study reminder.
        # Best-effort; a failure must not block enrolment.
        try:
            visa = dialog._visa_details
            if fields['is_international'].get() and visa:
                _create_visa_record_for_new_student(
                    student_id=student_id,
                    email_address=email_address,
                    first_name=first_name,
                    nationality=(visa.get('nationality')
                                 or fields['nationality'].get().strip() or None),
                    passport_number=visa.get('passport_number'),
                    visa_expiry_date=visa.get('visa_expiry_date'),
                    brp_number=visa.get('brp_number'),
                    module_codes=selected_modules,
                    details=visa,
                )
        except Exception as e:
            logging.warning(f"Visa record setup failed for {student_id}: {e}")

        # Disabilities and accommodation entered on the form. Each is
        # best-effort: the student stands regardless, and a failure is shown.
        done, problems = [], []
        actor_name = str((getattr(self.auth, 'current_user', {}) or {}).get('username')
                         or 'student records')
        if fields['has_disability'].get() and dialog._disabilities:
            try:
                from education_system.systems.university.services.bus import disability_bus
                result = disability_bus.record_at_enrolment(self.auth, student_id,
                                                            dialog._disabilities)
                done.append(f"{len(result['disabilities'])} disability record(s) saved"
                            + (f", {len(result['requests'])} adjustment request(s) sent to "
                               "disability services" if result['requests'] else ""))
            except Exception as e:
                logger.exception("Disabilities for %s were not recorded", student_id)
                problems.append(f"The disabilities were not saved: {e}. Add them from "
                                "Disability & Accessibility → Disabilities.")
        if fields['wants_housing'].get():
            try:
                from education_system.systems.university.services.bus import housing_bus
                hall = fields['housing_hall'].get()
                result = housing_bus.apply(
                    student_id, room_type=fields['housing_room_type'].get(),
                    move_in_date=fields['housing_move_in'].get().strip(),
                    duration_months=int(fields['housing_months'].get().strip()),
                    building_id=hall_ids.get(hall), actor=actor_name)
                done.append(f"accommodation application {result['application_id']} filed in "
                            "Housing (Pending)")
            except Exception as e:
                logger.exception("Housing application for %s was not filed", student_id)
                problems.append(f"The accommodation application was not filed: {e}. File it "
                                "from Housing → Applications.")
        if problems:
            messagebox.showwarning(_t("common.warning", default="Warning"),
                                   f"Student {student_id} was created, but:\n\n"
                                   + "\n\n".join(problems), parent=dialog)

        dialog._after_create_done = done

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
                from education_system.platform.cross_system.adapters import (
                    registry as _adapters,
                )
                sf_adapter = _adapters.require("sixth_form")
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

                sf_adapter.mark_transferred(
                    sf_origin, moved_by=moved_by)

                # Their application to us is over: mark the UCAS choice
                # placed (the sixth form keeps it as its record), so the
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


    def _entry_details(chosen):
        """``(entry_route, tariff, qualifications, override_reason)``, or
        None after explaining why the applicant cannot be admitted."""
        route = _route_key()
        if route != 'a_levels':
            return route, None, fields['qualifications'].get().strip(), None
        graded = [e for e in _qual_entries() if e[2]]
        ucas_tariff = _compute_tariff_entries(graded)
        qualifications = _format_qualification_entries(graded)
        if _is_eligible(chosen, ucas_tariff):
            return route, ucas_tariff, qualifications, None
        override = fields['override_reason'].get().strip()
        if fields['override'].get() and override:
            return route, ucas_tariff, qualifications, override
        eligible = _eligible_courses(ucas_tariff)
        if eligible:
            _populate_courses(eligible)
        messagebox.showwarning(
            _t('gui.learners.students.student_crud_gui.create.dialogs.entry_requirement_not_met', default="Entry requirement not met"),
            f"You need {chosen['min_tariff']} UCAS points for {chosen['code']} - "
            f"{chosen['name']}, but the grades give {ucas_tariff}.\n\n"
            + (f"The course list now shows the {len(eligible)} course(s) these grades "
               "meet. " if eligible else "")
            + "To admit anyway, tick 'Admissions override' and give the reason.",
            parent=dialog)
        return None

    def _command(chosen, entry):
        from education_system.systems.university.application.students.lifecycle import (
            StudentCommand,
        )
        route, ucas_tariff, qualifications, override = entry
        gender = fields['gender'].get().strip().lower()
        return StudentCommand(
            first_name=fields['first_name'].get().strip(),
            middle_name=fields['middle_name'].get().strip(),
            last_name=fields['last_name'].get().strip(),
            title=fields['title'].get() or {'male': 'Mr', 'female': 'Ms'}.get(gender, ''),
            gender=gender, dob=fields['dob'].get().strip(), course=chosen['code'],
            entry_qualifications=qualifications, ucas_tariff=ucas_tariff,
            phone=fields['phone'].get().strip(),
            personal_email=fields['personal_email'].get().strip(),
            nationality=fields['nationality'].get().strip(),
            mode_of_study=fields['mode_of_study'].get(),
            fee_status=fields['fee_status'].get(),
            entry_route=route, entry_override_reason=override or "",
            **{key: fields[key].get().strip() for key in (
                'preferred_name', 'postcode', 'notes', 'emergency_contact_name',
                'address_line1', 'address_line2', 'town',
                'emergency_contact_relationship', 'emergency_contact_phone',
                'medical_notes')},
        )

    def _create_checked(lifecycle, command, actor):
        """Create, asking before creating a likely duplicate. None if the
        user stopped or the record was refused (reason shown)."""
        from dataclasses import replace
        from education_system.systems.university.application.students.lifecycle import (
            StudentValidationError,
        )
        try:
            return lifecycle.create(command, actor_id=actor,
                                    idempotency_key=f"gui:create:{secrets.token_urlsafe(18)}")
        except StudentValidationError as exc:
            if "duplicate" not in exc.errors:
                validation_label.config(text="; ".join(f"{k}: {v}" for k, v in exc.errors.items()))
                return None
            if not messagebox.askyesno(
                    "Possible duplicate",
                    f"This looks like an existing student: {exc.errors['duplicate']}.\n\n"
                    "Create a new record anyway?", parent=dialog):
                return None
            return _create_checked(lifecycle, replace(command, allow_duplicate=True), actor)

    def _created_details(student_id):
        conn = get_db_connection()
        try:
            email = conn.execute("SELECT email_address FROM students WHERE student_id = ?",
                                 (student_id,)).fetchone()
            modules = [r[0] for r in conn.execute(
                "SELECT module_code FROM student_modules WHERE student_id = ?", (student_id,))]
        finally:
            conn.close()
        return (email[0] if email else None), modules

    def create_student():
        """Create the student through the lifecycle service, then the visa
        record and any sixth-form (UCAS) admission steps."""
        if not require_student_permission(self, "create_student", "create"):
            return
        try:
            errors = validate_form()
            if errors:
                validation_label.config(text="; ".join(errors))
                return
            validation_label.config(text="")
            chosen = course_label_map.get(fields['course'].get())
            if not chosen:
                validation_label.config(text=_t('gui.learners.students.student_crud_gui.create.text.please_select_a_course', default="Please select a course."))
                return
            entry = _entry_details(chosen)
            if entry is None:
                return
            from education_system.systems.university.application.students.lifecycle import (
                StudentLifecycleService,
            )
            actor = str((getattr(self.auth, 'current_user', {}) or {}).get('id', 'unknown'))
            lifecycle = StudentLifecycleService()
            command = _command(chosen, entry)
            created = _create_checked(lifecycle, command, actor)
            if created is None:
                return
            provisioned = lifecycle.provision(created.student_id, auth=self.auth)
            email_address, modules = _created_details(created.student_id)
            _after_create(created.student_id, email_address, command.first_name,
                          command.last_name, command.dob, modules)
            if provisioned.provisioning_error:
                messagebox.showwarning(
                    "Provisioning pending",
                    f"Student {created.student_id} was saved safely, but provisioning "
                    f"is pending: {provisioned.provisioning_error}. The outbox can retry it.",
                    parent=dialog,
                )
            else:
                extra = getattr(dialog, '_after_create_done', None) or []
                messagebox.showinfo(
                    _t("common.success"),
                    f"Student {created.student_id} was created and provisioned. "
                    "A single-use activation link was sent to their university email."
                    + "".join(f"\n\n• {line[0].upper()}{line[1:]}." for line in extra),
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
    def _clear_form() -> None:
        # The tick box and override are BooleanVars; set('') would break them.
        _clear_visa()
        fields['override'].set(False)
        for field in fields.values():
            if hasattr(field, 'delete'):
                field.delete(0, tk.END)
        # Read-only lists ignore delete().
        fields['emergency_contact_relationship'].set('')
        # After the loop, which would empty the accommodation defaults again.
        _clear_support()
        _reset_qual_rows()

    ttk.Button(button_frame, text=_t("student.clear_form"),
              command=_clear_form).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_t("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    # Set focus
    fields['first_name'].focus()
