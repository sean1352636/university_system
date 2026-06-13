"""
Degree Audit & Academic Advising GUI

Full-featured GUI for managing degree progress, prerequisites, what-if scenarios,
advising appointments, and graduation audits.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime
from typing import Optional

from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.core.i18n import get_text as _, init_i18n
init_i18n()
from education_system.university_system.modules.domain.academics.services.degree_audit.degree_audit_core import (
    DegreeProgramManager,
    DegreeProgressManager,
    WhatIfScenarioManager,
    AdvisingAppointmentManager,
    GraduationAuditManager
)
from education_system.university_system.modules.domain.academics.services.degree_audit.db_schema import initialize_degree_audit_database
from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.core.activity_logger import log_activity


class DegreeAuditGUI:
    """Main GUI for Degree Audit & Academic Advising System"""

    def __init__(self, parent, auth: UserAuth):
        self.root = tk.Toplevel(parent)
        self.root.title(_("degree_audit.title"))
        self.root.geometry("1200x700")
        self.auth = auth

        # Initialize database
        try:
            initialize_degree_audit_database()
        except Exception as e:
            print(f"Database initialization warning: {e}")

        self.create_widgets()
        self.load_courses()  # Changed from load_programs to load_courses

    # ------------------------------------------------------------------
    # Shared dropdown helpers (8.117.92)
    # ------------------------------------------------------------------
    def _load_student_options(self):
        """Return [(label, student_id, course_code), ...] sorted by id.

        Label format: ``"S12345 — Jane Doe (CS)"``. Empty courses
        render as ``"(unassigned)"`` so the user can still see the
        student. Cached on first call; call ``_load_student_options(refresh=True)``
        if you've added a student mid-session and want it to appear.
        """
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT student_id, "
                    "       COALESCE(first_name, '') AS fn, "
                    "       COALESCE(last_name, '')  AS ln, "
                    "       COALESCE(course, '')     AS course "
                    "FROM students "
                    "WHERE student_id IS NOT NULL "
                    "ORDER BY student_id"
                ).fetchall()
        except Exception:
            return []
        out = []
        for sid, fn, ln, course in rows:
            name = f"{fn} {ln}".strip() or "—"
            label = f"{sid} — {name} ({course or 'unassigned'})"
            out.append((label, sid, course))
        return out

    def _student_id_from_label(self, label):
        """Reverse the formatted label back to the bare student_id."""
        if not label:
            return ""
        return label.split(" — ", 1)[0].strip()

    def _populate_student_combo(self, combo):
        """Wire a Combobox to ``_load_student_options``."""
        opts = self._load_student_options()
        combo['values'] = [lbl for lbl, _sid, _c in opts]
        return opts

    def _student_modules(self, student_id):
        """Return [(module_code, module_name), ...] the student is
        enrolled on. Empty list if the student has none or the table
        is missing."""
        if not student_id:
            return []
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT sm.module_code, COALESCE(m.module_name, sm.module_code) "
                    "FROM student_modules sm "
                    "LEFT JOIN modules m ON m.module_code = sm.module_code "
                    "WHERE sm.student_id = ? "
                    "AND   LOWER(COALESCE(sm.status, 'enrolled')) = 'enrolled' "
                    "ORDER BY sm.module_code",
                    (student_id,)
                ).fetchall()
            return list(rows)
        except Exception:
            return []

    def _student_course(self, student_id):
        """Return the student's current course code, or empty string."""
        if not student_id:
            return ""
        try:
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT COALESCE(course, '') FROM students WHERE student_id = ?",
                    (student_id,)
                ).fetchone()
            return row[0] if row else ""
        except Exception:
            return ""

    # ------------------------------------------------------------------
    # Appointment email helper (8.117.92)
    # ------------------------------------------------------------------
    def _send_appointment_emails(self, *, student_id, advisor_id, date, time,
                                 duration, appointment_type, topic, notes):
        """Send appointment confirmation to both student and advisor.

        Loads JSON templates from
        ``templates/email/academics/advising/appointment_{student,advisor}.json``
        and substitutes the placeholders. The templates use Python's
        ``string.Template`` ``$name`` syntax so they're shell-safe and
        won't accidentally interpolate stray ``{}`` from notes.
        """
        import json
        import os
        from string import Template
        from education_system.university_system.infrastructure.email.email_service import (
            send_email,
        )

        # Locate the templates dir relative to this module.
        here = os.path.dirname(os.path.abspath(__file__))
        # gui/course_management_gui → gui → academics → modules/domain →
        # modules → university_system
        repo_uni = os.path.normpath(os.path.join(here, "..", "..", "..", "..", ".."))
        tmpl_dir = os.path.join(repo_uni, "templates", "email", "academics", "advising")

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT email_address, first_name, last_name FROM students "
                "WHERE student_id = ?", (student_id,))
            stu = cursor.fetchone()
            cursor.execute(
                "SELECT email, first_name, last_name FROM instructors WHERE id = ?",
                (advisor_id,))
            adv = cursor.fetchone()

        student_name = (
            f"{(stu[1] or '').strip()} {(stu[2] or '').strip()}".strip()
            if stu else student_id) or "Student"
        advisor_name = (
            f"{(adv[1] or '').strip()} {(adv[2] or '').strip()}".strip()
            if adv else advisor_id) or "Advisor"

        common = {
            "student_name":     student_name,
            "student_id":       student_id,
            "advisor_name":     advisor_name,
            "date":             date,
            "time":             time,
            "duration":         str(duration),
            "appointment_type": appointment_type,
            "topic":            topic or "N/A",
            "notes":            notes or "(no additional notes)",
        }

        def _render_and_send(template_file, recipient_email):
            if not recipient_email:
                return
            path = os.path.join(tmpl_dir, template_file)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    tmpl = json.load(f)
            except (OSError, ValueError) as e:
                print(f"Could not load advising template {template_file}: {e}")
                return
            subject = Template(tmpl.get("subject", "")).safe_substitute(common)
            body    = Template(tmpl.get("body", "")).safe_substitute(common)
            send_email(recipient_email=recipient_email,
                       subject=subject, body=body)

        if stu:
            _render_and_send("appointment_student.json", stu[0])
        if adv:
            _render_and_send("appointment_advisor.json", adv[0])

    def create_widgets(self):
        """Create all GUI widgets"""
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Close button frame - pack FIRST to reserve space at bottom
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))
        ttk.Button(button_frame, text=_("common.close_window"),
                  command=self.root.destroy).pack(pady=5)

        # Title
        title = ttk.Label(main_frame, text=_("degree_audit.title"),
                         font=('Arial', 16, 'bold'))
        title.pack(pady=10)

        # Notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Create tabs
        self.create_progress_tab()
        self.create_prerequisites_tab()
        self.create_whatif_tab()
        self.create_advising_tab()
        self.create_graduation_tab()

    def create_progress_tab(self):
        """Create Degree Progress tracking tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_("degree_audit.tabs.degree_progress"))

        # Top frame for student selection
        select_frame = ttk.LabelFrame(tab, text=_("degree_audit.labels.student_selection"), padding="10")
        select_frame.pack(fill=tk.X, pady=5)

        ttk.Label(select_frame, text=_("degree_audit.labels.student_id")).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        # 8.117.92: replaced free-text Entry with Combobox sourced from
        # the students table. The legacy attribute name
        # ``progress_student_entry`` is preserved (and aliased to the
        # combo) so existing callers like ``load_student_progress`` /
        # ``update_progress`` continue to work via ``.get()``.
        self.progress_student_entry = ttk.Combobox(select_frame, width=42, state='readonly')
        self.progress_student_entry.grid(row=0, column=1, padx=5, pady=5)
        self._populate_student_combo(self.progress_student_entry)

        ttk.Button(select_frame, text=_("degree_audit.buttons.load_progress"),
                  command=self.load_student_progress).grid(row=0, column=2, padx=5, pady=5)
        ttk.Button(select_frame, text=_("degree_audit.buttons.update_progress"),
                  command=self.update_progress).grid(row=0, column=3, padx=5, pady=5)
        # 8.117.92: "Initialise Progress" button removed — it conflicted
        # with existing degree-progress data by overwriting it. The
        # ``initialize_progress`` method itself is kept in case other
        # callers use it; it just isn't reachable from the UI.

        # Progress summary frame
        summary_frame = ttk.LabelFrame(tab, text=_("degree_audit.labels.progress_summary"), padding="10")
        summary_frame.pack(fill=tk.X, pady=5)

        self.progress_labels = {}
        self.progress_label_keys = ['Program', 'Credits Earned', 'Credits Required', 'Current GPA',
                 'Completion %', 'Enrollment Year', 'Expected Graduation']
        label_translations = {
            'Program': _("degree_audit.labels.program"),
            'Credits Earned': _("degree_audit.labels.credits_earned"),
            'Credits Required': _("degree_audit.labels.credits_required"),
            'Current GPA': _("degree_audit.labels.current_gpa"),
            'Completion %': _("degree_audit.labels.completion_percent"),
            'Enrollment Year': _("degree_audit.labels.enrollment_year"),
            'Expected Graduation': _("degree_audit.labels.expected_graduation")
        }

        for i, label in enumerate(self.progress_label_keys):
            ttk.Label(summary_frame, text=f"{label_translations[label]}:", font=('Arial', 10, 'bold')).grid(
                row=i//2, column=(i%2)*2, sticky=tk.W, padx=10, pady=5)
            self.progress_labels[label] = ttk.Label(summary_frame, text=_("common.not_available"))
            self.progress_labels[label].grid(row=i//2, column=(i%2)*2+1, sticky=tk.W, padx=10, pady=5)

        # Detailed progress treeview
        list_frame = ttk.LabelFrame(tab, text=_("degree_audit.labels.requirement_details"), padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        columns = ('Requirement Type', 'Name', 'Credits Required', 'Status', 'Grade Required')
        column_translations = {
            'Requirement Type': _("degree_audit.columns.requirement_type"),
            'Name': _("degree_audit.columns.name"),
            'Credits Required': _("degree_audit.columns.credits_required"),
            'Status': _("degree_audit.columns.status"),
            'Grade Required': _("degree_audit.columns.grade_required")
        }
        self.progress_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=12)

        for col in columns:
            self.progress_tree.heading(col, text=column_translations[col])
            width = 200 if col == 'Name' else 120
            self.progress_tree.column(col, width=width)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL,
                                 command=self.progress_tree.yview)
        self.progress_tree.configure(yscrollcommand=scrollbar.set)

        self.progress_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def create_prerequisites_tab(self):
        """Create Prerequisites checking tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_("degree_audit.tabs.prerequisites"))

        ttk.Label(tab, text=_("degree_audit.labels.check_course_prerequisites"),
                 font=('Arial', 12, 'bold')).pack(pady=10)

        # Check prerequisite frame
        check_frame = ttk.LabelFrame(tab, text=_("degree_audit.labels.check_prerequisites"), padding="10")
        check_frame.pack(fill=tk.X, pady=5)

        # 8.117.92: Combobox for the student, with the module Combobox
        # below it scoped to that student's enrolments. Selecting a
        # different student rebuilds the module list.
        ttk.Label(check_frame, text=_("degree_audit.labels.student_id")).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.prereq_student_entry = ttk.Combobox(check_frame, width=42, state='readonly')
        self.prereq_student_entry.grid(row=0, column=1, padx=5, pady=5)
        self._populate_student_combo(self.prereq_student_entry)

        ttk.Label(check_frame, text=_("degree_audit.labels.module_code")).grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.prereq_module_entry = ttk.Combobox(check_frame, width=42, state='readonly')
        self.prereq_module_entry.grid(row=1, column=1, padx=5, pady=5)

        def _refresh_prereq_modules(_e=None):
            sid = self._student_id_from_label(self.prereq_student_entry.get())
            modules = self._student_modules(sid)
            self.prereq_module_entry['values'] = [
                f"{code} — {name}" for code, name in modules]
            if not modules:
                self.prereq_module_entry.set("")
        self.prereq_student_entry.bind('<<ComboboxSelected>>', _refresh_prereq_modules)

        ttk.Button(check_frame, text=_("degree_audit.buttons.check_prerequisites"),
                  command=self.check_prerequisites).grid(row=0, column=2, rowspan=2, padx=10, pady=5)

        # Results display
        results_frame = ttk.LabelFrame(tab, text=_("degree_audit.labels.prerequisite_check_results"), padding="10")
        results_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.prereq_results_text = scrolledtext.ScrolledText(results_frame, wrap=tk.WORD,
                                                             width=80, height=12)
        self.prereq_results_text.pack(fill=tk.BOTH, expand=True)

        # Add prerequisite frame
        add_frame = ttk.LabelFrame(tab, text=_("degree_audit.labels.add_new_prerequisite"), padding="10")
        add_frame.pack(fill=tk.X, pady=5)

        ttk.Label(add_frame, text=_("degree_audit.labels.course")).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.prereq_course_entry = ttk.Entry(add_frame, width=25)
        self.prereq_course_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(add_frame, text=_("degree_audit.labels.prerequisite")).grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        self.prereq_prereq_entry = ttk.Entry(add_frame, width=25)
        self.prereq_prereq_entry.grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(add_frame, text=_("degree_audit.labels.min_grade")).grid(row=0, column=4, sticky=tk.W, padx=5, pady=5)
        self.prereq_grade_entry = ttk.Entry(add_frame, width=10)
        self.prereq_grade_entry.grid(row=0, column=5, padx=5, pady=5)

        ttk.Button(add_frame, text=_("degree_audit.buttons.add_prerequisite"),
                  command=self.add_prerequisite).grid(row=0, column=6, padx=10, pady=5)

    def create_whatif_tab(self):
        """Create What-If Scenarios tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_("degree_audit.tabs.whatif_scenarios"))

        ttk.Label(tab, text=_("degree_audit.labels.analyze_program_change"),
                 font=('Arial', 12, 'bold')).pack(pady=10)

        # Create scenario frame
        create_frame = ttk.LabelFrame(tab, text=_("degree_audit.labels.create_whatif_scenario"), padding="10")
        create_frame.pack(fill=tk.X, pady=5)

        ttk.Label(create_frame, text=_("degree_audit.labels.student_id")).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.whatif_student_entry = ttk.Combobox(create_frame, width=42, state='readonly')
        self.whatif_student_entry.grid(row=0, column=1, padx=5, pady=5)
        self._populate_student_combo(self.whatif_student_entry)

        ttk.Label(create_frame, text=_("degree_audit.labels.scenario_name")).grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.whatif_name_entry = ttk.Entry(create_frame, width=42)
        self.whatif_name_entry.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(create_frame, text=_("degree_audit.labels.target_program")).grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.whatif_program_combo = ttk.Combobox(create_frame, width=40, state='readonly')
        self.whatif_program_combo.grid(row=2, column=1, padx=5, pady=5)

        # 8.117.92: when the student changes, autofill target_program
        # with their *current* course (admin can change it before
        # creating the scenario).
        def _autofill_whatif_course(_e=None):
            sid = self._student_id_from_label(self.whatif_student_entry.get())
            current = self._student_course(sid)
            if not current:
                return
            for opt in self.whatif_program_combo['values']:
                if f": {current} -" in opt or opt.startswith(f"{current} -") \
                        or opt.split(":", 1)[-1].strip().startswith(current):
                    self.whatif_program_combo.set(opt)
                    return
        self.whatif_student_entry.bind('<<ComboboxSelected>>', _autofill_whatif_course)

        ttk.Label(create_frame, text=_("degree_audit.labels.notes")).grid(row=3, column=0, sticky=tk.NW, padx=5, pady=5)
        self.whatif_notes_text = tk.Text(create_frame, width=40, height=4)
        self.whatif_notes_text.grid(row=3, column=1, padx=5, pady=5)

        button_frame = ttk.Frame(create_frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=10)

        ttk.Button(button_frame, text=_("degree_audit.buttons.create_scenario"),
                  command=self.create_whatif_scenario).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_("degree_audit.buttons.analyze"),
                  command=self.analyze_whatif).pack(side=tk.LEFT, padx=5)

        # Analysis results
        results_frame = ttk.LabelFrame(tab, text=_("degree_audit.labels.scenario_analysis_results"), padding="10")
        results_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.whatif_results_text = scrolledtext.ScrolledText(results_frame, wrap=tk.WORD,
                                                             width=80, height=15)
        self.whatif_results_text.pack(fill=tk.BOTH, expand=True)

    def create_advising_tab(self):
        """Create Academic Advising Appointments tab.

        8.117.93: wrapped in a scrollable Canvas so the Schedule
        Appointment button at the bottom of the schedule form (and
        the appointments list below it) stay reachable on smaller
        windows. Previously the form's natural height plus the
        appointments tree exceeded the tab's available space and the
        Schedule button was pushed off-screen with no way to scroll.
        """
        tab_outer = ttk.Frame(self.notebook)
        self.notebook.add(tab_outer, text=_("degree_audit.tabs.advising_appointments"))

        canvas = tk.Canvas(tab_outer, highlightthickness=0)
        vbar = ttk.Scrollbar(tab_outer, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vbar.pack(side=tk.RIGHT, fill=tk.Y)

        tab = ttk.Frame(canvas, padding="10")
        canvas_window = canvas.create_window((0, 0), window=tab, anchor="nw")
        # Keep the inner frame's width matched to the canvas so wide
        # widgets (notes Text, topic Entry) don't trigger horizontal
        # scrolling.
        tab.bind("<Configure>",
                 lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(canvas_window, width=e.width))
        # Mouse-wheel scrolling — bound only while the cursor is over
        # this tab so it doesn't fight the outer notebook.
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-event.delta / 120), "units")
        canvas.bind("<Enter>",
                    lambda _e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>",
                    lambda _e: canvas.unbind_all("<MouseWheel>"))

        ttk.Label(tab, text=_("degree_audit.labels.academic_advising_appointments"),
                 font=('Arial', 12, 'bold')).pack(pady=10)

        # Schedule appointment frame
        schedule_frame = ttk.LabelFrame(tab, text=_("degree_audit.labels.schedule_appointment"), padding="10")
        schedule_frame.pack(fill=tk.X, pady=5)

        fields = {}

        ttk.Label(schedule_frame, text=_("degree_audit.labels.student_id")).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        fields['student'] = ttk.Entry(schedule_frame, width=20)
        fields['student'].grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(schedule_frame, text=_("degree_audit.buttons.lookup"), command=lambda: self._lookup_student_for_appointment(fields['student'])).grid(row=0, column=2, padx=2, pady=5)

        ttk.Label(schedule_frame, text=_("degree_audit.labels.advisor_id")).grid(row=0, column=3, sticky=tk.W, padx=5, pady=5)
        fields['advisor'] = ttk.Entry(schedule_frame, width=20)
        fields['advisor'].grid(row=0, column=4, padx=5, pady=5)
        ttk.Button(schedule_frame, text=_("degree_audit.buttons.lookup"), command=lambda: self._lookup_advisor_for_appointment(fields['advisor'])).grid(row=0, column=5, padx=2, pady=5)

        ttk.Label(schedule_frame, text=_("degree_audit.labels.date_format")).grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        fields['date'] = ttk.Entry(schedule_frame, width=25)
        fields['date'].insert(0, datetime.now().strftime('%Y-%m-%d'))
        fields['date'].grid(row=1, column=1, columnspan=2, padx=5, pady=5)

        ttk.Label(schedule_frame, text=_("degree_audit.labels.time_format")).grid(row=1, column=3, sticky=tk.W, padx=5, pady=5)
        fields['time'] = ttk.Entry(schedule_frame, width=25)
        fields['time'].insert(0, "10:00")
        fields['time'].grid(row=1, column=4, columnspan=2, padx=5, pady=5)

        ttk.Label(schedule_frame, text=_("degree_audit.labels.type")).grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        fields['type'] = ttk.Combobox(schedule_frame, values=[
            _("degree_audit.appointment_types.academic_planning"),
            _("degree_audit.appointment_types.course_selection"),
            _("degree_audit.appointment_types.degree_progress"),
            _("degree_audit.appointment_types.career_advising"),
            _("degree_audit.appointment_types.general"),
            _("degree_audit.appointment_types.other")
        ], width=23, state='readonly')
        fields['type'].current(0)
        fields['type'].grid(row=2, column=1, columnspan=2, padx=5, pady=5)

        ttk.Label(schedule_frame, text=_("degree_audit.labels.duration_min")).grid(row=2, column=3, sticky=tk.W, padx=5, pady=5)
        fields['duration'] = ttk.Entry(schedule_frame, width=25)
        fields['duration'].insert(0, "30")
        fields['duration'].grid(row=2, column=4, columnspan=2, padx=5, pady=5)

        ttk.Label(schedule_frame, text=_("degree_audit.labels.topic")).grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        fields['topic'] = ttk.Entry(schedule_frame, width=58)
        fields['topic'].grid(row=3, column=1, columnspan=5, padx=5, pady=5)

        ttk.Label(schedule_frame, text=_("degree_audit.labels.notes")).grid(row=4, column=0, sticky=tk.NW, padx=5, pady=5)
        fields['notes'] = tk.Text(schedule_frame, width=58, height=4)
        fields['notes'].grid(row=4, column=1, columnspan=5, padx=5, pady=5)

        self.appointment_fields = fields

        ttk.Button(schedule_frame, text=_("degree_audit.buttons.schedule_appointment"),
                  command=self.schedule_appointment).grid(row=5, column=0, columnspan=6, pady=10)

        # Appointments list
        list_frame = ttk.LabelFrame(tab, text=_("degree_audit.labels.scheduled_appointments"), padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # Load appointments button
        ttk.Button(list_frame, text=_("degree_audit.buttons.load_my_appointments"),
                  command=self.load_appointments).pack(anchor=tk.W, pady=5)

        columns = ('ID', 'Student', 'Advisor', 'Date', 'Time', 'Type', 'Topic', 'Status')
        column_translations = {
            'ID': _("degree_audit.columns.id"),
            'Student': _("degree_audit.columns.student"),
            'Advisor': _("degree_audit.columns.advisor"),
            'Date': _("degree_audit.columns.date"),
            'Time': _("degree_audit.columns.time"),
            'Type': _("degree_audit.columns.type"),
            'Topic': _("degree_audit.columns.topic"),
            'Status': _("degree_audit.columns.status")
        }
        self.appointments_tree = ttk.Treeview(list_frame, columns=columns,
                                             show='headings', height=8)

        for col in columns:
            self.appointments_tree.heading(col, text=column_translations[col])
            width = 150 if col == 'Topic' else 100
            self.appointments_tree.column(col, width=width)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL,
                                 command=self.appointments_tree.yview)
        self.appointments_tree.configure(yscrollcommand=scrollbar.set)

        self.appointments_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def create_graduation_tab(self):
        """Create Graduation Audit tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_("degree_audit.tabs.graduation_audit"))

        ttk.Label(tab, text=_("degree_audit.labels.graduation_readiness_audit"),
                 font=('Arial', 12, 'bold')).pack(pady=10)

        # Audit controls frame
        control_frame = ttk.LabelFrame(tab, text=_("degree_audit.labels.run_graduation_audit"), padding="10")
        control_frame.pack(fill=tk.X, pady=5)

        ttk.Label(control_frame, text=_("degree_audit.labels.student_id")).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.grad_student_entry = ttk.Combobox(control_frame, width=42, state='readonly')
        self.grad_student_entry.grid(row=0, column=1, padx=5, pady=5)
        self._populate_student_combo(self.grad_student_entry)

        ttk.Label(control_frame, text=_("degree_audit.labels.program")).grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        self.grad_program_combo = ttk.Combobox(control_frame, width=40, state='readonly')
        self.grad_program_combo.grid(row=0, column=3, padx=5, pady=5)

        # 8.117.92: autofill the program combo with the student's
        # current course on selection.
        def _autofill_grad_course(_e=None):
            sid = self._student_id_from_label(self.grad_student_entry.get())
            current = self._student_course(sid)
            if not current:
                return
            for opt in self.grad_program_combo['values']:
                if f": {current} -" in opt or opt.startswith(f"{current} -") \
                        or opt.split(":", 1)[-1].strip().startswith(current):
                    self.grad_program_combo.set(opt)
                    return
        self.grad_student_entry.bind('<<ComboboxSelected>>', _autofill_grad_course)

        ttk.Button(control_frame, text=_("degree_audit.buttons.run_audit"),
                  command=self.run_graduation_audit).grid(row=0, column=4, padx=10, pady=5)

        # Checklist frame
        checklist_frame = ttk.LabelFrame(tab, text=_("degree_audit.labels.graduation_checklist"), padding="10")
        checklist_frame.pack(fill=tk.X, pady=5)

        self.checklist_vars = {}
        checklist_items = [
            ('all_requirements', _("degree_audit.checklist.all_requirements_met")),
            ('gpa_requirement', _("degree_audit.checklist.gpa_requirement_met")),
            ('credit_requirement', _("degree_audit.checklist.credit_requirement_met")),
            ('residency', _("degree_audit.checklist.residency_requirement_met")),
            ('financial', _("degree_audit.checklist.financial_clearance"))
        ]

        for i, (key, label) in enumerate(checklist_items):
            var = tk.BooleanVar()
            self.checklist_vars[key] = var
            ttk.Checkbutton(checklist_frame, text=label, variable=var,
                           state='disabled').grid(row=i//2, column=(i%2)*2,
                                                 columnspan=2, sticky=tk.W, padx=20, pady=5)

        # Audit results display
        results_frame = ttk.LabelFrame(tab, text=_("degree_audit.labels.audit_results"), padding="10")
        results_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.grad_results_text = scrolledtext.ScrolledText(results_frame, wrap=tk.WORD,
                                                           width=80, height=12)
        self.grad_results_text.pack(fill=tk.BOTH, expand=True)

        # Approval frame
        approval_frame = ttk.Frame(tab)
        approval_frame.pack(fill=tk.X, pady=10)

        ttk.Label(approval_frame, text=_("degree_audit.labels.graduation_date")).pack(side=tk.LEFT, padx=5)
        self.grad_date_entry = ttk.Entry(approval_frame, width=20)
        self.grad_date_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        self.grad_date_entry.pack(side=tk.LEFT, padx=5)

        ttk.Button(approval_frame, text=_("degree_audit.buttons.approve_graduation"),
                  command=self.approve_graduation).pack(side=tk.LEFT, padx=20)

    # ======================== Helper Methods ========================

    def load_courses(self):
        """Load all courses (CS/DS) into combo boxes"""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, code, name
                    FROM courses
                    WHERE LOWER(COALESCE(status, 'active')) = 'active'
                      AND code IN ('CS', 'DS')
                    ORDER BY name
                ''')

                courses = cursor.fetchall()
                if not courses:
                    print("No CS/DS courses found in database")
                    return

                course_list = [f"{row[0]}: {row[1]} - {row[2]}" for row in courses]

                # Update all combo boxes that need courses
                self.whatif_program_combo['values'] = course_list
                self.grad_program_combo['values'] = course_list

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to load courses: {e}")

    def load_student_progress(self):
        """Load and display student degree progress from actual database tables"""
        try:
            # Combobox carries the formatted label "S12345 — Name (Course)";
            # strip back to just the bare ID.
            student_id = self._student_id_from_label(self.progress_student_entry.get())
            if not student_id:
                messagebox.showwarning(_("common.warning"), "Please select a student")
                return

            with get_connection() as conn:
                cursor = conn.cursor()

                # Get student information from students table
                cursor.execute('''
                    SELECT student_id, first_name, last_name, course, registration_datetime, enrollment_date
                    FROM students
                    WHERE student_id = ?
                ''', (student_id,))

                student = cursor.fetchone()
                if not student:
                    messagebox.showerror(_("common.error"), f"Student {student_id} not found in database")
                    return

                course_code = student[3]  # course column (CS or DS)
                enrollment_date = student[5] or student[4]  # enrollment_date or registration_datetime

                if not course_code:
                    messagebox.showerror(_("common.error"), f"Student {student_id} has no course assigned")
                    return

                # Get course information
                cursor.execute('''
                    SELECT id, name, code
                    FROM courses
                    WHERE code = ? OR course_code = ?
                ''', (course_code, course_code))

                course = cursor.fetchone()
                course_name = course[1] if course else course_code

                # Calculate total credits from student_modules
                cursor.execute('''
                    SELECT
                        COUNT(DISTINCT sm.module_code) as module_count,
                        SUM(COALESCE(m.credits, 0)) as total_credits,
                        AVG(
                            CASE
                                WHEN sm.grade = 'A' THEN 4.0
                                WHEN sm.grade = 'B' THEN 3.0
                                WHEN sm.grade = 'C' THEN 2.0
                                WHEN sm.grade = 'D' THEN 1.0
                                WHEN sm.grade = 'F' THEN 0.0
                                ELSE NULL
                            END
                        ) as gpa
                    FROM student_modules sm
                    LEFT JOIN modules m ON sm.module_code = m.module_code
                    WHERE sm.student_id = ?
                ''', (student_id,))

                progress_data = cursor.fetchone()
                total_credits = progress_data[1] or 0
                gpa = progress_data[2] or 0.0

                # Calculate enrollment year
                enrollment_year = _("common.not_available")
                if enrollment_date:
                    try:
                        enroll_dt = datetime.strptime(enrollment_date.split()[0], '%Y-%m-%d')
                        enrollment_year = str(enroll_dt.year)
                    except (ValueError, TypeError):
                        pass

                # Standard degree is typically 120 credits
                credits_required = 120
                completion_pct = (total_credits / credits_required * 100) if credits_required > 0 else 0

                # Calculate expected graduation (4 years from enrollment)
                expected_grad = _("common.not_available")
                if enrollment_date:
                    try:
                        enroll_dt = datetime.strptime(enrollment_date.split()[0], '%Y-%m-%d')
                        grad_year = enroll_dt.year + 4
                        expected_grad = f"{grad_year}"
                    except (ValueError, TypeError):
                        pass

                # Update labels
                self.progress_labels['Program'].config(text=f"{course_code} - {course_name}")
                self.progress_labels['Credits Earned'].config(text=str(int(total_credits)))
                self.progress_labels['Credits Required'].config(text=str(credits_required))
                self.progress_labels['Current GPA'].config(text=f"{gpa:.2f}")
                self.progress_labels['Completion %'].config(text=f"{completion_pct:.1f}%")
                self.progress_labels['Enrollment Year'].config(text=enrollment_year)
                self.progress_labels['Expected Graduation'].config(text=expected_grad)

                # Load module requirements
                self.load_requirements(student_id, course_code)

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to load progress: {e}")

    def load_requirements(self, student_id, course_code):
        """Load student modules from student_modules table"""
        try:
            self.progress_tree.delete(*self.progress_tree.get_children())

            with get_connection() as conn:
                cursor = conn.cursor()

                # Get modules enrolled by student from student_modules
                cursor.execute('''
                    SELECT
                        COALESCE(m.module_type, 'Standard') as module_type,
                        COALESCE(sm.module_code, 'N/A') as module_code,
                        COALESCE(m.module_name, 'Unknown Module') as module_name,
                        COALESCE(m.credits, 0) as credits,
                        COALESCE(sm.status, 'Enrolled') as status,
                        COALESCE(sm.grade, 'Not Graded') as grade
                    FROM student_modules sm
                    LEFT JOIN modules m ON sm.module_code = m.module_code
                    WHERE sm.student_id = ?
                    ORDER BY m.module_type, sm.module_code
                ''', (student_id,))

                modules = cursor.fetchall()

                if not modules:
                    self.progress_tree.insert('', tk.END, values=(
                        'N/A',
                        'No modules found',
                        0,
                        'No enrollment data',
                        'N/A'
                    ))
                else:
                    for module in modules:
                        # module: (module_type, module_code, module_name, credits, status, grade)
                        self.progress_tree.insert('', tk.END, values=(
                            module[0],  # module_type (Requirement Type)
                            f"{module[1]} - {module[2]}",  # module_code - module_name (Name)
                            module[3],  # credits (Credits Required)
                            module[4],  # status (Status)
                            module[5]   # grade (Grade Required)
                        ))

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to load modules: {e}")

    def update_progress(self):
        """Refresh student's degree progress display"""
        try:
            student_id = self._student_id_from_label(self.progress_student_entry.get())
            if not student_id:
                messagebox.showwarning(_("common.warning"), "Please select a student")
                return

            # Simply reload the progress to refresh display
            self.load_student_progress()

            log_activity('update', 'degree_progress', student_id, {})

            messagebox.showinfo(_("common.success"), "Progress refreshed successfully")

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to update progress: {e}")

    def initialize_progress(self):
        """Initialize/update student course assignment"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("degree_audit.dialogs.initialize_student_course"))
        dialog.geometry("400x250")

        ttk.Label(dialog, text=_("degree_audit.labels.student_id")).grid(row=0, column=0, sticky=tk.W, padx=10, pady=10)
        student_entry = ttk.Entry(dialog, width=30)
        student_entry.grid(row=0, column=1, padx=10, pady=10)

        ttk.Label(dialog, text=_("degree_audit.labels.course")).grid(row=1, column=0, sticky=tk.W, padx=10, pady=10)
        course_combo = ttk.Combobox(dialog, width=28, state='readonly')
        course_combo.grid(row=1, column=1, padx=10, pady=10)

        # Load courses (CS/DS)
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, code, name
                    FROM courses
                    WHERE code IN ('CS', 'DS')
                    ORDER BY code
                ''')
                courses = cursor.fetchall()
                course_combo['values'] = [f"{row[1]} - {row[2]}" for row in courses]
        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to load courses: {e}")

        ttk.Label(dialog, text=_("degree_audit.labels.enrollment_year")).grid(row=2, column=0, sticky=tk.W, padx=10, pady=10)
        year_entry = ttk.Entry(dialog, width=30)
        year_entry.insert(0, str(datetime.now().year))
        year_entry.grid(row=2, column=1, padx=10, pady=10)

        def save_init():
            try:
                student_id = student_entry.get().strip()
                course_selection = course_combo.get()
                enrollment_year = year_entry.get().strip()

                if not student_id or not course_selection:
                    messagebox.showerror(_("common.error"), _("degree_audit.messages.all_fields_required"))
                    return

                # Extract course code from selection
                course_code = course_selection.split('-')[0].strip()

                with get_connection() as conn:
                    cursor = conn.cursor()

                    # Check if student exists
                    cursor.execute('SELECT student_id FROM students WHERE student_id = ?', (student_id,))
                    if not cursor.fetchone():
                        messagebox.showerror(_("common.error"), _("degree_audit.messages.student_not_found_db").format(student_id=student_id))
                        return

                    # Update student's course
                    cursor.execute('''
                        UPDATE students
                        SET course = ?, enrollment_date = ?
                        WHERE student_id = ?
                    ''', (course_code, f"{enrollment_year}-09-01", student_id))

                    conn.commit()

                log_activity('create', 'degree_progress', student_id,
                           {'course': course_code, 'year': enrollment_year})

                messagebox.showinfo(_("common.success"),
                                  _("degree_audit.messages.course_assigned_success").format(course_code=course_code, student_id=student_id))
                dialog.destroy()
                self.progress_student_entry.delete(0, tk.END)
                self.progress_student_entry.insert(0, student_id)
                self.load_student_progress()

            except Exception as e:
                messagebox.showerror(_("common.error"), f"Failed to initialize: {e}")

        ttk.Button(dialog, text=_("degree_audit.buttons.initialize"),
                  command=save_init).grid(row=3, column=0, columnspan=2, pady=20)

    def check_prerequisites(self):
        """Check if student met prerequisites for a module using student_modules table"""
        try:
            student_id = self._student_id_from_label(self.prereq_student_entry.get())
            module_label = self.prereq_module_entry.get().strip()
            # Combobox entries are "CIS0001 — Module Name"; pull the code.
            module_code = module_label.split(" — ", 1)[0].strip() if module_label else ""

            if not student_id or not module_code:
                messagebox.showwarning(_("common.warning"),
                                       "Please select both a student and a module")
                return

            with get_connection() as conn:
                cursor = conn.cursor()

                # Check if student exists
                cursor.execute('SELECT student_id FROM students WHERE student_id = ?', (student_id,))
                if not cursor.fetchone():
                    messagebox.showerror(_("common.error"), f"Student {student_id} not found in database")
                    return

                # Check if module exists in student_modules
                cursor.execute('''
                    SELECT sm.module_code, sm.status, sm.grade, m.module_name, m.prerequisites
                    FROM student_modules sm
                    LEFT JOIN modules m ON sm.module_code = m.module_code
                    WHERE sm.student_id = ? AND sm.module_code = ?
                ''', (student_id, module_code))

                module_enrollment = cursor.fetchone()

                self.prereq_results_text.delete('1.0', tk.END)
                self.prereq_results_text.insert(tk.END,
                    f"PREREQUISITE CHECK - {module_code}\n")
                self.prereq_results_text.insert(tk.END, "=" * 60 + "\n\n")
                self.prereq_results_text.insert(tk.END,
                    f"Student ID: {student_id}\n")
                self.prereq_results_text.insert(tk.END,
                    f"Module Code: {module_code}\n\n")

                if module_enrollment:
                    module_name = module_enrollment[3] or "Unknown Module"
                    status = module_enrollment[1] or "Unknown"
                    grade = module_enrollment[2] or "Not Graded"
                    prerequisites = module_enrollment[4] or "None"

                    self.prereq_results_text.insert(tk.END,
                        f"Module Name: {module_name}\n")
                    self.prereq_results_text.insert(tk.END,
                        f"Enrollment Status: {status}\n")
                    self.prereq_results_text.insert(tk.END,
                        f"Current Grade: {grade}\n")
                    self.prereq_results_text.insert(tk.END,
                        f"Prerequisites: {prerequisites}\n\n")

                    # Check if student has completed all prerequisites
                    if prerequisites and prerequisites.lower() != 'none':
                        prereq_list = [p.strip() for p in prerequisites.split(',')]
                        missing = []

                        for prereq in prereq_list:
                            cursor.execute('''
                                SELECT grade, status
                                FROM student_modules
                                WHERE student_id = ? AND module_code = ?
                            ''', (student_id, prereq))

                            prereq_result = cursor.fetchone()
                            if not prereq_result:
                                missing.append(prereq)
                            elif prereq_result[1] != 'Completed':
                                missing.append(f"{prereq} (Not completed)")

                        if missing:
                            self.prereq_results_text.insert(tk.END,
                                "STATUS: Not Eligible\n\n"
                                "Missing Prerequisites:\n")
                            for m in missing:
                                self.prereq_results_text.insert(tk.END, f"  - {m}\n")
                        else:
                            self.prereq_results_text.insert(tk.END,
                                "STATUS: Eligible\n\n"
                                "All prerequisites have been met.\n")
                    else:
                        self.prereq_results_text.insert(tk.END,
                            "STATUS: Eligible\n\n"
                            "No prerequisites required for this module.\n")
                else:
                    self.prereq_results_text.insert(tk.END,
                        f"ERROR: Module {module_code} not found in student's enrolled modules.\n\n"
                        f"Student {student_id} is not enrolled in this module.\n")

                log_activity('check', 'prerequisite', module_code,
                           {'student_id': student_id})

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to check prerequisites: {e}")

    def add_prerequisite(self):
        """Add a new prerequisite relationship"""
        try:
            module_code = self.prereq_course_entry.get().strip()
            prerequisite = self.prereq_prereq_entry.get().strip()
            min_grade = self.prereq_grade_entry.get().strip()

            if not module_code or not prerequisite:
                messagebox.showwarning(_("common.warning"), _("degree_audit.messages.course_prereq_required"))
                return

            prereq_id = DegreeProgramManager.add_prerequisite(
                module_code=module_code,
                prerequisite_module_code=prerequisite,
                min_grade=min_grade if min_grade else None
            )

            log_activity('create', 'prerequisite', str(prereq_id),
                       {'course': module_code, 'prerequisite': prerequisite})

            messagebox.showinfo(_("common.success"),
                              _("degree_audit.messages.prerequisite_added").format(id=prereq_id))

            # Clear fields
            self.prereq_course_entry.delete(0, tk.END)
            self.prereq_prereq_entry.delete(0, tk.END)
            self.prereq_grade_entry.delete(0, tk.END)

        except Exception as e:
            messagebox.showerror(_("common.error"), _("degree_audit.messages.failed_add_prerequisite").format(error=e))

    def _whatif_student_id(self):
        """Extract bare student_id from the formatted Combobox label."""
        return self._student_id_from_label(self.whatif_student_entry.get())

    def create_whatif_scenario(self):
        """Create and analyze what-if scenario for course switching"""
        try:
            student_id = self._whatif_student_id()
            scenario_name = self.whatif_name_entry.get().strip()
            course_selection = self.whatif_program_combo.get()
            notes = self.whatif_notes_text.get('1.0', tk.END).strip()

            if not student_id or not scenario_name or not course_selection:
                messagebox.showwarning(_("common.warning"), "All fields are required")
                return

            # Extract course code from selection (format: "1: CS - Computer Science")
            target_course_code = course_selection.split(':')[1].split('-')[0].strip()

            with get_connection() as conn:
                cursor = conn.cursor()

                # Check if student exists
                cursor.execute('SELECT course FROM students WHERE student_id = ?', (student_id,))
                student_data = cursor.fetchone()
                if not student_data:
                    messagebox.showerror(_("common.error"), f"Student {student_id} not found")
                    return

                current_course = student_data[0]

                # Look up target course details and ensure a matching
                # ``degree_programs`` row exists. ``courses.id`` is a
                # string ('CS', 'DS', …), and the scenario table FKs
                # to ``degree_programs.program_id`` (an INTEGER), so
                # we mirror the course into degree_programs on first
                # use and use the resulting integer id (8.117.91 fix —
                # previously this stored ``target_program_id = 0``,
                # which violated the FK because degree_programs is
                # empty out of the box).
                cursor.execute(
                    "SELECT COALESCE(course_name, name), "
                    "       COALESCE(course_type, 'Bachelors'), "
                    "       COALESCE(department, ''), "
                    "       COALESCE(credits, credit_hours, 360) "
                    "FROM courses "
                    "WHERE UPPER(COALESCE(course_code, code)) = ?",
                    (target_course_code.upper(),))
                course_row = cursor.fetchone()
                if not course_row:
                    messagebox.showerror(_("common.error"),
                                         f"Course {target_course_code} not found")
                    return
                course_name, course_type, department, credits = course_row

                cursor.execute(
                    "INSERT OR IGNORE INTO degree_programs "
                    "(program_code, program_name, degree_type, department, "
                    " total_credits_required) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (target_course_code, course_name, course_type,
                     department, int(credits) if credits else 360))
                cursor.execute(
                    "SELECT program_id FROM degree_programs WHERE program_code = ?",
                    (target_course_code,))
                target_program_id = cursor.fetchone()[0]

                cursor.execute('''
                    INSERT INTO degree_what_if_scenarios
                    (student_id, scenario_name, target_program_id, notes, created_at)
                    VALUES (?, ?, ?, ?, ?)
                ''', (student_id, scenario_name, target_program_id,
                      f"Target Course: {target_course_code}\n{notes}",
                      datetime.now().isoformat()))

                scenario_id = cursor.lastrowid
                conn.commit()

            log_activity('create', 'whatif_scenario', str(scenario_id),
                       {'student_id': student_id, 'target_course': target_course_code})

            messagebox.showinfo(_("common.success"),
                              f"What-if scenario '{scenario_name}' created (ID: {scenario_id})\n"
                              f"Current Course: {current_course}\n"
                              f"Target Course: {target_course_code}")

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to create scenario: {e}")

    def analyze_whatif(self):
        """Analyze what-if scenario for course switching"""
        try:
            student_id = self._whatif_student_id()
            course_selection = self.whatif_program_combo.get()

            if not student_id or not course_selection:
                messagebox.showwarning(_("common.warning"), "Please select a student and target course")
                return

            # Extract target course code
            target_course = course_selection.split(':')[1].split('-')[0].strip()

            with get_connection() as conn:
                cursor = conn.cursor()

                # Get student's current course and modules
                cursor.execute('SELECT course FROM students WHERE student_id = ?', (student_id,))
                student_data = cursor.fetchone()
                if not student_data:
                    messagebox.showerror(_("common.error"), f"Student {student_id} not found")
                    return

                current_course = student_data[0]

                # Get current modules and credits
                cursor.execute('''
                    SELECT COUNT(DISTINCT sm.module_code) as module_count,
                           SUM(COALESCE(m.credits, 0)) as total_credits
                    FROM student_modules sm
                    LEFT JOIN modules m ON sm.module_code = m.module_code
                    WHERE sm.student_id = ?
                ''', (student_id,))

                current_progress = cursor.fetchone()
                current_modules = current_progress[0] or 0
                current_credits = current_progress[1] or 0

                # Get modules of the target course type
                cursor.execute('''
                    SELECT COUNT(*) as available_modules
                    FROM modules
                    WHERE module_type = ? AND is_active = 1
                ''', (target_course,))

                target_modules = cursor.fetchone()[0] or 0

                # Calculate overlap - modules that match target course
                cursor.execute('''
                    SELECT COUNT(*) as matching_modules
                    FROM student_modules sm
                    JOIN modules m ON sm.module_code = m.module_code
                    WHERE sm.student_id = ? AND m.module_type = ?
                ''', (student_id, target_course))

                matching_modules = cursor.fetchone()[0] or 0

            # Calculate analysis
            standard_required = 40  # Typical number of modules for a degree
            completion_pct = (matching_modules / standard_required * 100) if standard_required > 0 else 0
            additional_needed = max(0, standard_required - matching_modules)

            self.whatif_results_text.delete('1.0', tk.END)
            self.whatif_results_text.insert(tk.END, "WHAT-IF SCENARIO ANALYSIS\n")
            self.whatif_results_text.insert(tk.END, "=" * 60 + "\n\n")
            self.whatif_results_text.insert(tk.END, f"Student ID: {student_id}\n")
            self.whatif_results_text.insert(tk.END, f"Current Course: {current_course}\n")
            self.whatif_results_text.insert(tk.END, f"Target Course: {target_course}\n\n")
            self.whatif_results_text.insert(tk.END, f"Current Modules Completed: {current_modules}\n")
            self.whatif_results_text.insert(tk.END, f"Current Credits Earned: {current_credits}\n\n")
            self.whatif_results_text.insert(tk.END, f"Modules Matching Target Course: {matching_modules}\n")
            self.whatif_results_text.insert(tk.END, f"Available {target_course} Modules: {target_modules}\n")
            self.whatif_results_text.insert(tk.END, f"Additional Modules Needed: {additional_needed}\n")
            self.whatif_results_text.insert(tk.END, f"Completion Percentage: {completion_pct:.1f}%\n\n")

            if completion_pct >= 50:
                self.whatif_results_text.insert(tk.END,
                    "RECOMMENDATION: Feasible\n\n"
                    f"You have completed over half of the requirements for {target_course}. "
                    "Switching courses is feasible with manageable additional coursework.")
            elif completion_pct >= 25:
                self.whatif_results_text.insert(tk.END,
                    "RECOMMENDATION: Moderate Effort Required\n\n"
                    f"You have completed {completion_pct:.1f}% of requirements for {target_course}. "
                    "Switching is possible but will require significant additional coursework.")
            else:
                self.whatif_results_text.insert(tk.END,
                    "RECOMMENDATION: Consider Carefully\n\n"
                    f"You have completed only {completion_pct:.1f}% of requirements for {target_course}. "
                    "Switching courses would require substantial additional coursework.")

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to analyze scenario: {e}")

    def _lookup_student_for_appointment(self, entry_widget):
        """Lookup student from database for appointments"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("degree_audit.dialogs.student_lookup_title"))
        dialog.geometry("700x400")
        dialog.transient(self.root)

        ttk.Label(dialog, text=_("degree_audit.labels.search")).pack(pady=5)
        search_entry = ttk.Entry(dialog, width=40)
        search_entry.pack(pady=5)

        tree_frame = ttk.Frame(dialog)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns = ('Student ID', 'Name', 'Course')
        tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=10)
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=200)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def search_students():
            tree.delete(*tree.get_children())
            search_text = search_entry.get().strip()

            with get_connection() as conn:
                cursor = conn.cursor()
                if search_text:
                    cursor.execute('''
                        SELECT student_id, first_name || ' ' || last_name, course
                        FROM students
                        WHERE student_id LIKE ? OR first_name LIKE ? OR last_name LIKE ?
                        ORDER BY student_id
                        LIMIT 50
                    ''', (f'%{search_text}%', f'%{search_text}%', f'%{search_text}%'))
                else:
                    cursor.execute('''
                        SELECT student_id, first_name || ' ' || last_name, course
                        FROM students
                        ORDER BY student_id
                        LIMIT 50
                    ''')

                results = cursor.fetchall()
                for row in results:
                    # Convert Row object to tuple
                    student_id = row[0]
                    name = row[1]
                    course = row[2] if row[2] else 'N/A'
                    tree.insert('', tk.END, values=(student_id, name, course))

        def select_student():
            selection = tree.selection()
            if selection:
                item = tree.item(selection[0])
                student_id = item['values'][0]
                entry_widget.delete(0, tk.END)
                entry_widget.insert(0, student_id)
                dialog.destroy()

        search_entry.bind('<Return>', lambda e: search_students())
        ttk.Button(dialog, text=_("degree_audit.buttons.search"), command=search_students).pack(pady=5)
        ttk.Button(dialog, text=_("degree_audit.buttons.select"), command=select_student).pack(pady=5)

        search_students()  # Load initial data

    def _lookup_advisor_for_appointment(self, entry_widget):
        """Lookup advisor/instructor from database for appointments"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("degree_audit.dialogs.advisor_lookup_title"))
        dialog.geometry("700x400")
        dialog.transient(self.root)

        ttk.Label(dialog, text=_("degree_audit.labels.search")).pack(pady=5)
        search_entry = ttk.Entry(dialog, width=40)
        search_entry.pack(pady=5)

        tree_frame = ttk.Frame(dialog)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns = ('ID', 'Name', 'Department')
        tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=10)
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=200)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def search_advisors():
            tree.delete(*tree.get_children())
            search_text = search_entry.get().strip()

            with get_connection() as conn:
                cursor = conn.cursor()
                if search_text:
                    cursor.execute('''
                        SELECT id, first_name || ' ' || last_name, department
                        FROM instructors
                        WHERE id LIKE ? OR first_name LIKE ? OR last_name LIKE ?
                        ORDER BY last_name
                        LIMIT 50
                    ''', (f'%{search_text}%', f'%{search_text}%', f'%{search_text}%'))
                else:
                    cursor.execute('''
                        SELECT id, first_name || ' ' || last_name, department
                        FROM instructors
                        ORDER BY last_name
                        LIMIT 50
                    ''')

                results = cursor.fetchall()
                for row in results:
                    # Convert Row object to tuple
                    advisor_id = row[0]
                    name = row[1]
                    department = row[2] if row[2] else 'N/A'
                    tree.insert('', tk.END, values=(advisor_id, name, department))

        def select_advisor():
            selection = tree.selection()
            if selection:
                item = tree.item(selection[0])
                advisor_id = item['values'][0]
                entry_widget.delete(0, tk.END)
                entry_widget.insert(0, advisor_id)
                dialog.destroy()

        search_entry.bind('<Return>', lambda e: search_advisors())
        ttk.Button(dialog, text=_("degree_audit.buttons.search"), command=search_advisors).pack(pady=5)
        ttk.Button(dialog, text=_("degree_audit.buttons.select"), command=select_advisor).pack(pady=5)

        search_advisors()  # Load initial data

    def schedule_appointment(self):
        """Schedule an advising appointment"""
        try:
            fields = self.appointment_fields

            student_id = fields['student'].get().strip()
            advisor_id = fields['advisor'].get().strip()
            date = fields['date'].get().strip()
            time = fields['time'].get().strip()
            appt_type = fields['type'].get()
            duration = int(fields['duration'].get())
            topic = fields['topic'].get().strip()
            notes = fields['notes'].get('1.0', tk.END).strip()

            if not all([student_id, advisor_id, date, time]):
                messagebox.showwarning(_("common.warning"), _("degree_audit.messages.appointment_fields_required"))
                return

            # Validate student exists
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT student_id FROM students WHERE student_id = ?', (student_id,))
                if not cursor.fetchone():
                    messagebox.showerror(_("common.error"), _("degree_audit.messages.student_not_found_db").format(student_id=student_id))
                    return

                cursor.execute('SELECT id FROM instructors WHERE id = ?', (advisor_id,))
                if not cursor.fetchone():
                    messagebox.showerror(_("common.error"), _("degree_audit.messages.advisor_not_found_db").format(advisor_id=advisor_id))
                    return

            appointment_id = AdvisingAppointmentManager.schedule_appointment(
                student_id=student_id,
                advisor_id=advisor_id,
                appointment_date=date,
                appointment_time=time,
                appointment_type=appt_type,
                duration_minutes=duration,
                topic=topic,
                notes=notes
            )

            log_activity('create', 'advising_appointment', str(appointment_id),
                       {'student_id': student_id, 'date': date})

            messagebox.showinfo(_("common.success"), _("degree_audit.messages.appointment_scheduled_success").format(appointment_id=appointment_id))

            # Send confirmation emails to student and advisor using
            # the JSON templates at templates/email/academics/advising/
            # (8.117.92 — replaced inline f-strings with file-based
            # templates for consistency with the rest of the project's
            # email infrastructure).
            try:
                self._send_appointment_emails(
                    student_id=student_id, advisor_id=advisor_id,
                    date=date, time=time, duration=duration,
                    appointment_type=appt_type, topic=topic, notes=notes,
                )
            except Exception as email_err:
                print(f"Appointment email notification failed: {email_err}")

            # Clear fields
            fields['student'].delete(0, tk.END)
            fields['advisor'].delete(0, tk.END)
            fields['topic'].delete(0, tk.END)
            fields['notes'].delete('1.0', tk.END)

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to schedule appointment: {e}")

    def load_appointments(self):
        """Load advising appointments for current user"""
        try:
            student_id = self.auth.current_user.get('username') if self.auth.current_user else None
            if not student_id:
                messagebox.showwarning(_("common.warning"), _("degree_audit.messages.no_user_logged_in"))
                return

            self.appointments_tree.delete(*self.appointments_tree.get_children())

            appointments = AdvisingAppointmentManager.get_student_appointments(student_id)

            for appt in appointments:
                self.appointments_tree.insert('', tk.END, values=(
                    appt.get('appointment_id', ''),
                    appt.get('student_id', ''),
                    appt.get('advisor_id', ''),
                    appt.get('appointment_date', ''),
                    appt.get('appointment_time', ''),
                    appt.get('appointment_type', ''),
                    appt.get('topic', ''),
                    appt.get('status', '')
                ))

        except Exception as e:
            messagebox.showerror(_("common.error"), _("degree_audit.messages.failed_load_appointments").format(error=e))

    def run_graduation_audit(self):
        """Run comprehensive graduation audit using actual database data"""
        try:
            student_id = self._student_id_from_label(self.grad_student_entry.get())
            course_selection = self.grad_program_combo.get()

            if not student_id or not course_selection:
                messagebox.showwarning(_("common.warning"), _("degree_audit.messages.enter_student_select_course"))
                return

            # Extract course code from selection
            course_code = course_selection.split(':')[1].split('-')[0].strip()

            with get_connection() as conn:
                cursor = conn.cursor()

                # Get student information
                cursor.execute('''
                    SELECT student_id, first_name, last_name, course
                    FROM students
                    WHERE student_id = ?
                ''', (student_id,))

                student = cursor.fetchone()
                if not student:
                    messagebox.showerror(_("common.error"), _("degree_audit.messages.student_not_found_db").format(student_id=student_id))
                    return

                student_name = f"{student[1]} {student[2]}"
                enrolled_course = student[3]

                # Get credits and GPA
                cursor.execute('''
                    SELECT
                        COUNT(DISTINCT sm.module_code) as module_count,
                        SUM(COALESCE(m.credits, 0)) as total_credits,
                        AVG(
                            CASE
                                WHEN sm.grade = 'A' THEN 4.0
                                WHEN sm.grade = 'B' THEN 3.0
                                WHEN sm.grade = 'C' THEN 2.0
                                WHEN sm.grade = 'D' THEN 1.0
                                WHEN sm.grade = 'F' THEN 0.0
                                ELSE NULL
                            END
                        ) as gpa
                    FROM student_modules sm
                    LEFT JOIN modules m ON sm.module_code = m.module_code
                    WHERE sm.student_id = ?
                ''', (student_id,))

                progress = cursor.fetchone()
                modules_completed = progress[0] or 0
                credits_earned = progress[1] or 0
                current_gpa = progress[2] or 0.0

            # Graduation requirements
            required_credits = 120
            required_gpa = 2.0
            required_modules = 40

            # Check requirements
            credit_met = credits_earned >= required_credits
            gpa_met = current_gpa >= required_gpa
            modules_met = modules_completed >= required_modules
            all_met = credit_met and gpa_met and modules_met

            # Update checklist
            self.checklist_vars['all_requirements'].set(all_met)
            self.checklist_vars['gpa_requirement'].set(gpa_met)
            self.checklist_vars['credit_requirement'].set(credit_met)

            # Display results
            self.grad_results_text.delete('1.0', tk.END)
            self.grad_results_text.insert(tk.END, "GRADUATION AUDIT RESULTS\n")
            self.grad_results_text.insert(tk.END, "=" * 60 + "\n\n")
            self.grad_results_text.insert(tk.END, f"Student: {student_name} ({student_id})\n")
            self.grad_results_text.insert(tk.END, f"Enrolled Course: {enrolled_course}\n")
            self.grad_results_text.insert(tk.END, f"Audit Course: {course_code}\n\n")

            self.grad_results_text.insert(tk.END, "PROGRESS:\n")
            self.grad_results_text.insert(tk.END, f"  Modules Completed: {modules_completed} / {required_modules}\n")
            self.grad_results_text.insert(tk.END, f"  Credits Earned: {credits_earned:.0f} / {required_credits}\n")
            self.grad_results_text.insert(tk.END, f"  Current GPA: {current_gpa:.2f} / {required_gpa:.2f}\n\n")

            self.grad_results_text.insert(tk.END, "REQUIREMENT STATUS:\n")
            self.grad_results_text.insert(tk.END, f"  Module Requirement: {'PASS' if modules_met else 'FAIL'}\n")
            self.grad_results_text.insert(tk.END, f"  Credit Requirement: {'PASS' if credit_met else 'FAIL'}\n")
            self.grad_results_text.insert(tk.END, f"  GPA Requirement: {'PASS' if gpa_met else 'FAIL'}\n")
            self.grad_results_text.insert(tk.END, f"  All Requirements: {'PASS' if all_met else 'FAIL'}\n\n")

            if all_met:
                self.grad_results_text.insert(tk.END,
                    "RESULT: ELIGIBLE FOR GRADUATION\n\n"
                    "The student has met all requirements for graduation.\n"
                    "You may proceed with graduation approval.")
            else:
                self.grad_results_text.insert(tk.END,
                    "RESULT: NOT ELIGIBLE FOR GRADUATION\n\n"
                    "The student has not met all requirements.\n")
                if not modules_met:
                    self.grad_results_text.insert(tk.END, f"  - Complete {required_modules - modules_completed} more modules\n")
                if not credit_met:
                    self.grad_results_text.insert(tk.END, f"  - Earn {required_credits - credits_earned:.0f} more credits\n")
                if not gpa_met:
                    self.grad_results_text.insert(tk.END, f"  - Raise GPA by {required_gpa - current_gpa:.2f} points\n")

            log_activity('run', 'graduation_audit', student_id,
                       {'course': course_code, 'can_graduate': all_met})

            messagebox.showinfo(_("common.success"), _("degree_audit.messages.graduation_audit_completed_short"))

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to run audit: {e}")

    def approve_graduation(self):
        """Approve student for graduation"""
        try:
            student_id = self._student_id_from_label(self.grad_student_entry.get())
            course_selection = self.grad_program_combo.get()
            grad_date = self.grad_date_entry.get().strip()

            if not student_id or not course_selection or not grad_date:
                messagebox.showwarning(_("common.warning"), _("degree_audit.messages.student_course_date_required"))
                return

            course_code = course_selection.split(':')[1].split('-')[0].strip()

            # Confirm approval
            confirm = messagebox.askyesno(_("degree_audit.dialogs.confirm_graduation"),
                _("degree_audit.dialogs.confirm_graduation_question").format(student_id=student_id, grad_date=grad_date, course_code=course_code))

            if not confirm:
                return

            with get_connection() as conn:
                cursor = conn.cursor()

                # Check if student exists
                cursor.execute('SELECT student_id, status FROM students WHERE student_id = ?', (student_id,))
                student = cursor.fetchone()
                if not student:
                    messagebox.showerror(_("common.error"), _("degree_audit.messages.student_not_found").format(student_id=student_id))
                    return

                # Update student status to Graduated
                cursor.execute('''
                    UPDATE students
                    SET status = 'Graduated'
                    WHERE student_id = ?
                ''', (student_id,))

                conn.commit()

            log_activity('approve', 'graduation', student_id,
                       {'course': course_code, 'date': grad_date})

            messagebox.showinfo(_("common.success"),
                _("degree_audit.messages.graduation_approved_success").format(student_id=student_id, grad_date=grad_date, course_code=course_code))

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to approve graduation: {e}")

    def view_requirements(self):
        """Show program requirements"""
        messagebox.showinfo(_("degree_audit.dialogs.view_requirements_title"),
                          _("degree_audit.dialogs.view_requirements_message"))


def launch_degree_audit_gui(root, auth):
    """Launch the Degree Audit & Academic Advising GUI"""
    try:
        if not auth or not hasattr(auth, 'current_user') or not auth.current_user:
            messagebox.showerror(_("common.error"),
                               _("degree_audit.messages.must_be_logged_in"))
            return

        DegreeAuditGUI(root, auth)

    except Exception as e:
        messagebox.showerror(_("common.error"),
                           _("degree_audit.messages.failed_launch").format(error=e))


__all__ = ['DegreeAuditGUI', 'launch_degree_audit_gui']
