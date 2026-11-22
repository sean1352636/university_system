"""Assignment creation form, validation, and execution"""
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t

import tkinter as tk
from tkinter import ttk, scrolledtext
from education_system.systems.university.domains.assessment.interfaces.gui.assignment_system._dialogs import messagebox
from education_system.systems.university.domains.assessment.interfaces.gui.assignment_system._dialogs import make_toplevel
from education_system.platform.delivery.gui.tk_threads import start_thread, ui
from datetime import datetime, timedelta
from education_system.systems.university.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH
from education_system.systems.university.infrastructure.ui.field_pickers import attach_date
from education_system.systems.university.domains.assessment.domain.assignments.assignment_rules import (
    runner as assignment_runner,
    visibility as assignment_visibility,
)


class CreationMixin:
    """Assignment creation operations"""

    def show_create_assignment(self):
        """Show assignment creation form - FIXED DATE PICKER"""
        self.gui.layout.clear_content_area()

        title = ttk.Label(self.gui.layout.content_area, text=_t('gui.academics.assignment_system.assignment_manager.creation.labels.create_assignment', default="Create Assignment"), style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))

        # Create scrollable frame for the form (increased size for better display)
        canvas = tk.Canvas(self.gui.layout.content_area, height=600)
        scrollbar = ttk.Scrollbar(self.gui.layout.content_area, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Assignment creation form
        form_frame = ttk.LabelFrame(scrollable_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.labels.assignment_details', default="Assignment Details"), padding=20)
        form_frame.pack(fill='x', padx=10, pady=10)

        # Module selection
        ttk.Label(form_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.labels.module', default="Module:")).grid(row=0, column=0, sticky='w', pady=5)
        self.module_var = tk.StringVar()
        module_combo = ttk.Combobox(form_frame, textvariable=self.module_var, width=30)
        module_combo.grid(row=0, column=1, sticky='w', pady=5, padx=(10, 0))
        self.load_modules(module_combo)

        # Title
        ttk.Label(form_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.labels.title', default="Title:")).grid(row=1, column=0, sticky='w', pady=5)
        self.title_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.title_var, width=50).grid(row=1, column=1, sticky='ew', pady=5, padx=(10, 0))

        # Description
        ttk.Label(form_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.labels.description', default="Description:")).grid(row=2, column=0, sticky='nw', pady=5)
        self.description_text = scrolledtext.ScrolledText(form_frame, height=4, width=50)
        self.description_text.grid(row=2, column=1, sticky='ew', pady=5, padx=(10, 0))

        # Instructions
        ttk.Label(form_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.labels.instructions', default="Instructions:")).grid(row=3, column=0, sticky='nw', pady=5)
        self.instructions_text = scrolledtext.ScrolledText(form_frame, height=4, width=50)
        self.instructions_text.grid(row=3, column=1, sticky='ew', pady=5, padx=(10, 0))

        # FIXED: Due date without tkcalendar
        ttk.Label(form_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.labels.due_date', default="Due Date:")).grid(row=4, column=0, sticky='w', pady=5)
        due_frame = ttk.Frame(form_frame)
        due_frame.grid(row=4, column=1, sticky='w', pady=5, padx=(10, 0))

        # Date entry with validation
        self.due_date_var = tk.StringVar()
        self.due_time_var = tk.StringVar(value="23:59")

        # Create date entry with helper text
        date_entry_frame = ttk.Frame(due_frame)
        date_entry_frame.pack(side='left')

        # Day / month / year dropdowns. This was a typed YYYY-MM-DD box
        # beside a calendar button that opened a dialog containing...
        # another typed YYYY-MM-DD box, which then rejected anything
        # mis-typed. The dropdowns cannot produce an invalid date, so
        # both the box and the dialog are gone.
        attach_date(date_entry_frame, id_var=self.due_date_var).pack(side='left', padx=(5, 0))

        quick_frame = ttk.Frame(due_frame)
        quick_frame.pack(side='left', padx=(10, 0))

        def _set_due_in(days):
            self.due_date_var.set(
                (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d"))

        for label, days in (
            (_t('gui.academics.assignment_system.assignment_manager.creation.buttons.today', default="Today"), 0),
            (_t('gui.academics.assignment_system.assignment_manager.creation.buttons.tomorrow', default="Tomorrow"), 1),
            (_t('gui.academics.assignment_system.assignment_manager.creation.buttons.value_1_week', default="1 Week"), 7),
            (_t('gui.academics.assignment_system.assignment_manager.creation.buttons.value_2_weeks', default="2 Weeks"), 14),
        ):
            ttk.Button(quick_frame, text=label, width=8,
                       command=lambda d=days: _set_due_in(d)).pack(side='left', padx=2)

        # Time selection
        ttk.Label(due_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.labels.time', default="Time:")).pack(side='left', padx=(10, 5))
        time_combo = ttk.Combobox(due_frame, textvariable=self.due_time_var, width=8, values=[
            "08:00", "09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00",
            "16:00", "17:00", "18:00", "19:00", "20:00", "21:00", "22:00", "23:59"
        ])
        time_combo.pack(side='left')

        # Set default date to one week from now
        default_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        self.due_date_var.set(default_date)

        # Max marks
        ttk.Label(form_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.labels.max_marks', default="Max Marks:")).grid(row=5, column=0, sticky='w', pady=5)
        self.max_marks_var = tk.StringVar(value="100")
        ttk.Entry(form_frame, textvariable=self.max_marks_var, width=10).grid(row=5, column=1, sticky='w', pady=5, padx=(10, 0))

        # File settings frame
        file_frame = ttk.LabelFrame(scrollable_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.labels.file_settings', default="File Settings"), padding=20)
        file_frame.pack(fill='x', padx=10, pady=10)

        # Allowed file types
        ttk.Label(file_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.labels.allowed_file_types', default="Allowed File Types:")).grid(row=0, column=0, sticky='w', pady=5)
        self.file_types_var = tk.StringVar(value=_t('gui.academics.assignment_system.assignment_manager.creation.values.pdf_docx_txt', default=".pdf,.docx,.txt"))
        ttk.Entry(file_frame, textvariable=self.file_types_var, width=30).grid(row=0, column=1, sticky='w', pady=5, padx=(10, 0))
        ttk.Label(file_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.labels.comma_separated_e_g_pdf_docx_txt', default="(comma-separated, e.g., .pdf,.docx,.txt)")).grid(row=0, column=2, sticky='w', pady=5, padx=(5, 0))

        # Max file size
        ttk.Label(file_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.labels.max_file_size_mb', default="Max File Size (MB):")).grid(row=1, column=0, sticky='w', pady=5)
        self.max_size_var = tk.StringVar(value="10")
        ttk.Entry(file_frame, textvariable=self.max_size_var, width=10).grid(row=1, column=1, sticky='w', pady=5, padx=(10, 0))

        # Assignment type frame
        type_frame = ttk.LabelFrame(scrollable_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.labels.assignment_type_category', default="Assignment Type & Category"), padding=20)
        type_frame.pack(fill='x', padx=10, pady=10)

        # Assessment Type Selection
        ttk.Label(type_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.labels.assessment_type', default="Assessment Type:")).grid(row=0, column=0, sticky='w', pady=5)
        self.assessment_type_var = tk.StringVar(value=_t('gui.academics.assignment_system.assignment_manager.creation.values.essay', default="essay"))
        assessment_combo = ttk.Combobox(type_frame, textvariable=self.assessment_type_var, width=20,
                                       values=["essay", "quiz", "project", "presentation", "lab_report",
                                              "case_study", "exam", "homework", "discussion", "other"])
        assessment_combo.grid(row=0, column=1, sticky='w', pady=5, padx=(10, 0))

        # Grading Method Selection
        ttk.Label(type_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.labels.grading_method', default="Grading Method:")).grid(row=1, column=0, sticky='w', pady=5)
        self.grading_method_var = tk.StringVar(value=_t('gui.academics.assignment_system.assignment_manager.creation.values.points', default="points"))
        grading_combo = ttk.Combobox(type_frame, textvariable=self.grading_method_var, width=20,
                                     values=["points", "percentage", "letter_grade", "pass_fail", "rubric"])
        grading_combo.grid(row=1, column=1, sticky='w', pady=5, padx=(10, 0))

        # Visibility Options
        ttk.Label(type_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.labels.visibility', default="Visibility:")).grid(row=2, column=0, sticky='w', pady=5)
        self.visibility_var = tk.StringVar(value=_t('gui.academics.assignment_system.assignment_manager.creation.values.draft', default="draft"))
        visibility_combo = ttk.Combobox(type_frame, textvariable=self.visibility_var, width=20,
                                       values=["draft", "published", "hidden", "scheduled"],
                                       state='readonly')
        visibility_combo.grid(row=2, column=1, sticky='w', pady=5, padx=(10, 0))
        ttk.Label(type_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.labels.draft_not_visible_to_students', default="(Draft = not visible to students)")).grid(row=2, column=2, sticky='w', pady=5, padx=(5, 0))

        # Opening date, for a scheduled assignment
        ttk.Label(type_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.labels.opens_on', default="Opens On:")).grid(row=2, column=3, sticky='w', pady=5, padx=(15, 0))
        self.available_from_var = tk.StringVar()
        ttk.Entry(type_frame, textvariable=self.available_from_var, width=18).grid(row=2, column=4, sticky='w', pady=5, padx=(5, 0))
        ttk.Label(type_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.labels.opens_on_hint', default="(YYYY-MM-DD HH:MM, scheduled only)")).grid(row=2, column=5, sticky='w', pady=5, padx=(5, 0))

        self.assignment_type_var = tk.StringVar(value=_t('gui.academics.assignment_system.assignment_manager.creation.values.individual', default="individual"))
        ttk.Radiobutton(type_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.buttons.individual', default="Individual"), variable=self.assignment_type_var,
                       value="individual").grid(row=3, column=0, sticky='w', pady=5)
        ttk.Radiobutton(type_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.buttons.group', default="Group"), variable=self.assignment_type_var,
                       value="group").grid(row=3, column=1, sticky='w', pady=5, padx=(10, 0))

        # Group size (enabled when group is selected)
        ttk.Label(type_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.labels.group_size_min_max', default="Group Size (min-max):")).grid(row=4, column=0, sticky='w', pady=5)
        group_size_frame = ttk.Frame(type_frame)
        group_size_frame.grid(row=4, column=1, sticky='w', pady=5, padx=(10, 0))

        self.group_min_var = tk.StringVar(value="2")
        self.group_max_var = tk.StringVar(value="4")
        ttk.Entry(group_size_frame, textvariable=self.group_min_var, width=5).pack(side='left')
        ttk.Label(group_size_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.labels.to', default=" to ")).pack(side='left')
        ttk.Entry(group_size_frame, textvariable=self.group_max_var, width=5).pack(side='left')

        # Group assignment options
        ttk.Label(type_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.labels.group_assignment', default="Group Assignment:")).grid(row=5, column=0, sticky='w', pady=5)
        self.auto_assign_groups_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(type_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.buttons.auto_assign_students_to_groups', default="Auto-assign students to groups"),
                       variable=self.auto_assign_groups_var).grid(row=5, column=1, sticky='w', pady=5)

        ttk.Label(type_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.labels.group_submission', default="Group Submission:")).grid(row=6, column=0, sticky='w', pady=5)
        self.group_submission_type_var = tk.StringVar(value=_t('gui.academics.assignment_system.assignment_manager.creation.values.one_per_group', default="one_per_group"))
        group_sub_frame = ttk.Frame(type_frame)
        group_sub_frame.grid(row=6, column=1, sticky='w', pady=5, padx=(10, 0))
        ttk.Radiobutton(group_sub_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.buttons.one_per_group', default="One per group"), variable=self.group_submission_type_var,
                       value="one_per_group").pack(side='left')
        ttk.Radiobutton(group_sub_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.buttons.individual_within_group', default="Individual within group"), variable=self.group_submission_type_var,
                       value="individual").pack(side='left', padx=(10, 0))

        self.peer_eval_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(type_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.buttons.enable_peer_evaluation_within_groups', default="Enable peer evaluation within groups"),
                       variable=self.peer_eval_var).grid(row=7, column=1, sticky='w', pady=5)

        ttk.Button(type_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.buttons.configure_groups_students', default="Configure Groups & Students"),
                  command=self.gui.groups.show_group_configuration).grid(row=8, column=1, sticky='w', pady=10)

        # Additional settings frame
        settings_frame = ttk.LabelFrame(scrollable_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.labels.submission_grading_settings', default="Submission & Grading Settings"), padding=20)
        settings_frame.pack(fill='x', padx=10, pady=10)

        # Late submission settings
        self.allow_late_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(settings_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.buttons.allow_late_submissions', default="Allow Late Submissions"),
                       variable=self.allow_late_var).grid(row=0, column=0, sticky='w', pady=5)

        ttk.Label(settings_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.labels.late_penalty_per_day', default="Late Penalty (% per day):")).grid(row=0, column=1, sticky='w', pady=5, padx=(10, 0))
        self.late_penalty_var = tk.StringVar(value="0")
        ttk.Entry(settings_frame, textvariable=self.late_penalty_var, width=10).grid(row=0, column=2, sticky='w', pady=5, padx=(10, 0))

        # Maximum late days allowed
        ttk.Label(settings_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.labels.max_late_days', default="Max Late Days:")).grid(row=1, column=0, sticky='w', pady=5)
        self.max_late_days_var = tk.StringVar(value="7")
        ttk.Entry(settings_frame, textvariable=self.max_late_days_var, width=10).grid(row=1, column=1, sticky='w', pady=5, padx=(10, 0))
        ttk.Label(settings_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.labels.value_0_unlimited', default="(0 = unlimited)")).grid(row=1, column=2, sticky='w', pady=5, padx=(5, 0))

        # Resubmission settings
        self.allow_resubmit_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(settings_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.buttons.allow_resubmissions', default="Allow Resubmissions"),
                       variable=self.allow_resubmit_var).grid(row=2, column=0, sticky='w', pady=5)

        ttk.Label(settings_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.labels.max_attempts', default="Max Attempts:")).grid(row=2, column=1, sticky='w', pady=5, padx=(10, 0))
        self.max_attempts_var = tk.StringVar(value="1")
        ttk.Entry(settings_frame, textvariable=self.max_attempts_var, width=10).grid(row=2, column=2, sticky='w', pady=5, padx=(10, 0))

        # Other settings
        self.auto_release_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(settings_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.buttons.auto_release_grades', default="Auto-release Grades"),
                       variable=self.auto_release_var).grid(row=3, column=0, sticky='w', pady=5)

        self.peer_review_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(settings_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.buttons.enable_peer_review', default="Enable Peer Review"),
                       variable=self.peer_review_var).grid(row=3, column=1, sticky='w', pady=5)

        self.plagiarism_check_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(settings_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.buttons.enable_plagiarism_check', default="Enable Plagiarism Check"),
                       variable=self.plagiarism_check_var).grid(row=3, column=2, sticky='w', pady=5)

        # Advanced settings collapsible section
        advanced_frame = ttk.LabelFrame(scrollable_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.labels.advanced_settings_optional', default="Advanced Settings (Optional)"), padding=20)
        advanced_frame.pack(fill='x', padx=10, pady=10)

        # Rubric selection
        ttk.Label(advanced_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.labels.rubric_template', default="Rubric Template:")).grid(row=0, column=0, sticky='w', pady=5)
        self.rubric_var = tk.StringVar(value=_t('gui.academics.assignment_system.assignment_manager.creation.values.none', default="None"))
        self.rubric_map = self._load_rubric_choices()
        rubric_combo = ttk.Combobox(advanced_frame, textvariable=self.rubric_var, width=30,
                                    values=["None", *self.rubric_map], state='readonly',
                                    postcommand=lambda: self._refresh_rubric_choices(rubric_combo))
        rubric_combo.grid(row=0, column=1, sticky='w', pady=5, padx=(10, 0))
        ttk.Button(advanced_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.buttons.create_edit_rubric', default="Create/Edit Rubric"),
                  command=self.gui.rubrics.show_rubric_editor).grid(row=0, column=2, padx=(10, 0))

        # Submission notifications
        ttk.Label(advanced_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.labels.notifications', default="Notifications:")).grid(row=1, column=0, sticky='w', pady=5)
        self.notify_on_submit_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(advanced_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.buttons.email_on_submission', default="Email on submission"),
                       variable=self.notify_on_submit_var).grid(row=1, column=1, sticky='w', pady=5)

        # Reminder settings
        ttk.Label(advanced_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.labels.reminder_before_due', default="Reminder Before Due:")).grid(row=2, column=0, sticky='w', pady=5)
        self.reminder_days_var = tk.StringVar(value="2")
        reminder_frame = ttk.Frame(advanced_frame)
        reminder_frame.grid(row=2, column=1, sticky='w', pady=5, padx=(10, 0))
        ttk.Entry(reminder_frame, textvariable=self.reminder_days_var, width=5).pack(side='left')
        ttk.Label(reminder_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.labels.days', default=" days")).pack(side='left', padx=(5, 0))

        # Weight/Points distribution
        ttk.Label(advanced_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.labels.course_weight', default="Course Weight (%):")).grid(row=3, column=0, sticky='w', pady=5)
        self.course_weight_var = tk.StringVar(value="0")
        ttk.Entry(advanced_frame, textvariable=self.course_weight_var, width=10).grid(row=3, column=1, sticky='w', pady=5, padx=(10, 0))
        ttk.Label(advanced_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.labels.value_0_not_weighted', default="(0 = not weighted)")).grid(row=3, column=2, sticky='w', pady=5, padx=(5, 0))

        # Configure grid weights
        form_frame.grid_columnconfigure(1, weight=1)
        file_frame.grid_columnconfigure(1, weight=1)

        # Buttons frame
        buttons_frame = ttk.Frame(scrollable_frame)
        buttons_frame.pack(fill='x', padx=10, pady=20)

        ttk.Button(buttons_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.buttons.create_assignment', default="Create Assignment"),
                  command=self.create_assignment_gui, style='Accent.TButton').pack(side='right', padx=(10, 0))
        ttk.Button(buttons_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.buttons.save_as_draft', default="Save as Draft"),
                  command=self.save_assignment_draft).pack(side='right', padx=(10, 0))
        # Free-room finder for venue-bound assignments (in-class quiz,
        # lab, workshop) — same shared algorithm Module Scheduling and
        # Exam use, so we never invent a fourth implementation.
        ttk.Button(buttons_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.buttons.suggest_venue', default="Suggest Venue"),
                  command=self._suggest_assignment_venue).pack(
            side='left', padx=(10, 0),
        )
        ttk.Button(buttons_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.buttons.load_template', default="Load Template"),
                  command=self.load_assignment_template).pack(side='left')
        ttk.Button(buttons_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.buttons.save_as_template', default="Save as Template"),
                  command=self.save_assignment_template).pack(side='left', padx=(10, 0))
        ttk.Button(buttons_frame, text=_t('gui.academics.assignment_system.assignment_manager.creation.buttons.clear_form', default="Clear Form"),
                  command=self.clear_assignment_form).pack(side='right', padx=(10, 0))

        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Status frame
        self.assignment_status_frame = ttk.Frame(self.gui.layout.content_area)
        self.assignment_status_frame.pack(fill='x', pady=(10, 0))

    def _load_rubric_choices(self):
        """{label: rubric id} for the rubrics that exist."""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                rows = conn.execute("SELECT id, name FROM rubrics WHERE COALESCE(is_active, 1) = 1 "
                                    "ORDER BY name").fetchall()
            finally:
                conn.close()
        except sqlite3.Error:
            logger.debug("Rubrics unavailable", exc_info=True)
            return {}
        return {f"{name} (#{rid})": rid for rid, name in rows}

    def _refresh_rubric_choices(self, combo):
        self.rubric_map = self._load_rubric_choices()
        combo['values'] = ["None", *self.rubric_map]

    # ASSESSMENT SYSTEM METHODS

    def validate_assignment_form(self):
        """Validate the assignment creation form"""
        if not self.module_var.get():
            self.show_assignment_status("Please select a module", "error")
            return False

        if not self.title_var.get().strip():
            self.show_assignment_status("Please enter a title", "error")
            return False

        if not self.due_date_var.get().strip():
            self.show_assignment_status("Please enter a due date", "error")
            return False

        try:
            # Validate date format
            due_date_str = f"{self.due_date_var.get()} {self.due_time_var.get()}"
            due_date = datetime.strptime(due_date_str, "%Y-%m-%d %H:%M")
            if due_date <= datetime.now():
                self.show_assignment_status("Due date must be in the future", "error")
                return False
        except ValueError:
            self.show_assignment_status("Invalid date format. Use YYYY-MM-DD", "error")
            return False

        try:
            max_marks = int(self.max_marks_var.get())
            if max_marks <= 0:
                self.show_assignment_status("Max marks must be positive", "error")
                return False
        except ValueError:
            self.show_assignment_status("Max marks must be a number", "error")
            return False

        for var, name, largest in ((self.max_late_days_var, "Max late days", None),
                                   (self.max_attempts_var, "Max attempts", None),
                                   (self.reminder_days_var, "Reminder before due", None),
                                   (self.course_weight_var, "Course weight", 100)):
            try:
                value = float(var.get() or 0)
            except ValueError:
                self.show_assignment_status(f"{name} must be a number", "error")
                return False
            if value < 0 or (largest is not None and value > largest):
                limit = f"between 0 and {largest}" if largest is not None else "0 or more"
                self.show_assignment_status(f"{name} must be {limit}", "error")
                return False
        if self.allow_resubmit_var.get() and int(float(self.max_attempts_var.get() or 0)) == 1:
            self.show_assignment_status(
                "Allow Resubmissions needs Max Attempts above 1 (0 = no limit)", "error")
            return False

        try:
            assignment_visibility.check_settings(self.visibility_var.get(),
                                                 self.available_from_var.get(), due_date_str)
        except ValueError as e:
            self.show_assignment_status(str(e), "error")
            return False

        return True


    def load_modules(self, combo):
        """Load available modules"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('SELECT module_code, module_name FROM modules ORDER BY module_code')
            modules = cursor.fetchall()

            module_list = [f"{code} - {name}" for code, name in modules]
            combo['values'] = module_list

            # Create mapping for easy lookup
            self.module_map = {f"{code} - {name}": code for code, name in modules}

            conn.close()

        except Exception as e:
            messagebox.showerror(_t('gui.academics.assignment_system.assignment_manager.creation.dialogs.error', default="Error"), f"Failed to load modules: {e}")


    def _suggest_assignment_venue(self):
        """Find rooms free on the assignment's due date (#10).

        For an in-class quiz / lab / workshop the due date doubles as
        the venue date. Reuses the canonical ``find_free_rooms`` so
        Module Scheduling, Exam, and Assignment all share one algo.
        """
        import tkinter as tk
        from tkinter import ttk
        from education_system.systems.university.domains.assessment.interfaces.gui.assignment_system._dialogs import messagebox
        try:
            due_date = (self.due_date_var.get() or "").strip()
            due_time = (self.due_time_var.get() or "10:00").strip()
        except Exception:
            due_date = due_time = ""
        if not due_date:
            messagebox.showwarning(
                _t('gui.academics.assignment_system.assignment_manager.creation.dialogs.pick_a_due_date_first', default="Pick a due date first"),
                _t('gui.academics.assignment_system.assignment_manager.creation.dialogs.set_the_assignment_due_date_so_we_know_when_to_look', default="Set the assignment due date so we know when to look."),
            )
            return
        # 1-hour default slot from the due time.
        try:
            from datetime import datetime as _dt, timedelta as _td
            start = due_time[:5]
            end = (_dt.strptime(start, "%H:%M") + _td(hours=1)).strftime("%H:%M")
        except Exception:
            start, end = "10:00", "11:00"

        try:
            from education_system.systems.university.domains.teaching.interfaces.gui._cross_services import (
                find_free_rooms,
            )
            rows = find_free_rooms(
                on_date=due_date, start_time=start, end_time=end,
            )
        except Exception as exc:
            messagebox.showerror(_t('gui.academics.assignment_system.assignment_manager.creation.dialogs.error', default="Error"),
                                 f"Could not query rooms: {exc}")
            return

        win = make_toplevel()
        win.title(f"Free venues — {due_date} {start}–{end}")
        win.geometry("520x360")

        if not rows:
            ttk.Label(win,
                      text=_t('gui.academics.assignment_system.assignment_manager.creation.labels.no_rooms_available_in_that_window', default="No rooms available in that window."),
                      foreground="#7f8c8d").pack(padx=15, pady=20)
        else:
            cols = ("name", "building", "capacity")
            tree = ttk.Treeview(win, columns=cols, show="headings", height=12)
            for c, w in zip(cols, (140, 160, 100)):
                tree.heading(c, text=c.capitalize())
                tree.column(c, width=w, anchor="w")
            for r in sorted(rows, key=lambda x: -(x.get("capacity") or 0)):
                tree.insert("", "end", values=(
                    r.get("name", ""), r.get("building", ""),
                    r.get("capacity", 0),
                ))
            tree.pack(fill="both", expand=True, padx=10, pady=10)
        ttk.Button(win, text=_t('gui.academics.assignment_system.assignment_manager.creation.buttons.close', default="Close"), command=win.destroy).pack(pady=10)

    def create_assignment_gui(self):
        """Create assignment through GUI"""
        # Clear previous status
        for widget in self.assignment_status_frame.winfo_children():
            widget.destroy()

        # Validate form
        if not self.validate_assignment_form():
            return

        # Asked here, on the Tk thread: creation itself runs in a worker thread.
        if not self._confirm_no_deadline_clash(
                self.module_map.get(self.module_var.get()),
                f"{self.due_date_var.get()} {self.due_time_var.get()}"):
            return

        # Show progress
        self.show_assignment_status("Creating assignment...", "info")
        self.root.update()

        # Read every form value here, on the Tk thread; the worker must not touch Tk.
        form = self._collect_assignment_form()

        # Create assignment in background thread
        start_thread(self.root, self.perform_assignment_creation, form)

    def _collect_assignment_form(self):
        """Snapshot the creation form's raw values (main thread only)."""
        return {
            'module': self.module_var.get(),
            'due_date': self.due_date_var.get(),
            'due_time': self.due_time_var.get(),
            'title': self.title_var.get(),
            'description': self.description_text.get(1.0, tk.END),
            'instructions': self.instructions_text.get(1.0, tk.END),
            'max_marks': self.max_marks_var.get(),
            'file_types': self.file_types_var.get(),
            'max_size': self.max_size_var.get(),
            'assignment_type': self.assignment_type_var.get(),
            'group_min': self.group_min_var.get(),
            'group_max': self.group_max_var.get(),
            'allow_late': self.allow_late_var.get(),
            'late_penalty': self.late_penalty_var.get(),
            'auto_release': self.auto_release_var.get(),
            'peer_review': self.peer_review_var.get(),
            'visibility': self.visibility_var.get(),
            'available_from': self.available_from_var.get(),
            'max_late_days': self.max_late_days_var.get(),
            'allow_resubmit': self.allow_resubmit_var.get(),
            'max_attempts': self.max_attempts_var.get(),
            'automatic_checks': self.plagiarism_check_var.get(),
            'rubric_id': self.rubric_map.get(self.rubric_var.get()),
            'notify_on_submission': self.notify_on_submit_var.get(),
            'reminder_days': self.reminder_days_var.get(),
            'course_weight': self.course_weight_var.get(),
        }



    def _confirm_no_deadline_clash(self, module_code, due_date_str):
        """Warn when the cohort would have several summative deadlines in one week."""
        try:
            from education_system.systems.university.domains.assessment.domain.assignments.assessment_qa import (
                AssessmentQAService,
            )
            from education_system.systems.university.domains.assessment.domain.assignments.assessment_qa.service import (
                CLASH_THRESHOLD, CLASH_WINDOW_DAYS,
            )
            clashes = AssessmentQAService(str(DEFAULT_DB_PATH)).deadline_clashes(module_code, due_date_str)
        except Exception:
            return True
        if not clashes:
            return True
        worst = max(len(c["deadlines"]) + 1 for c in clashes)
        sample = sorted({d["module_code"] + " " + d["title"] for c in clashes for d in c["deadlines"]})[:6]
        return messagebox.askyesno(
            "Deadline clash",
            f"{len(clashes)} student(s) on {module_code} would have {CLASH_THRESHOLD} or more "
            f"summative deadlines within {CLASH_WINDOW_DAYS} days of this one "
            f"(up to {worst}).\n\nNearby deadlines:\n  " + "\n  ".join(sample) +
            "\n\nCreate the assignment anyway?")
    def perform_assignment_creation(self, form):
        """Perform the actual assignment creation (worker thread; ``form`` from _collect_assignment_form)"""
        try:
            # Get module code
            module_code = self.module_map.get(form['module'])

            # Prepare assignment data
            due_date_str = f"{form['due_date']} {form['due_time']}"
            due_date = datetime.strptime(due_date_str, "%Y-%m-%d %H:%M")

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()

                # Temporarily disable foreign key checks to avoid module_code issues
                cursor.execute("PRAGMA foreign_keys = OFF")

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                INSERT INTO assignments
                (module_code, title, description, instructions, due_date, max_marks,
                 file_types_allowed, max_file_size_mb, assignment_type, group_size_min, group_size_max,
                 allow_late_submission, late_penalty_per_day, auto_release_grades, peer_review_enabled,
                 created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    module_code,
                    form['title'].strip(),
                    form['description'].strip(),
                    form['instructions'].strip(),
                    due_date.strftime('%Y-%m-%d %H:%M:%S'),
                    int(form['max_marks']),
                    form['file_types'].strip(),
                    int(form['max_size']),
                    form['assignment_type'],
                    int(form['group_min']) if form['assignment_type'] == 'group' else 1,
                    int(form['group_max']) if form['assignment_type'] == 'group' else 1,
                    form['allow_late'],
                    float(form['late_penalty']) if form['late_penalty'] else 0,
                    form['auto_release'],
                    form['peer_review'],
                    self.auth.current_user['id'],
                    timestamp,
                    timestamp
                ))

                assignment_id = cursor.lastrowid

                # The other settings on the form.
                attempts = int(float(form['max_attempts'] or 0)) if form['allow_resubmit'] else 1
                weight = float(form['course_weight'] or 0)
                cursor.execute(
                    "UPDATE assignments SET max_late_days = ?, max_attempts = ?, "
                    "automatic_checks = ?, rubric_id = ?, notify_on_submission = ?, "
                    "reminder_days = ?, module_weight_pct = ? WHERE id = ?",
                    (int(float(form['max_late_days'] or 0)) or None, attempts or None,
                     1 if form['automatic_checks'] else 0, form['rubric_id'],
                     1 if form['notify_on_submission'] else 0,
                     int(float(form['reminder_days'] or 0)), weight or None, assignment_id))
                tell_students = assignment_visibility.set_visibility(
                    conn, assignment_id, form['visibility'], form['available_from'])

                # Re-enable foreign key checks
                cursor.execute("PRAGMA foreign_keys = ON")

                conn.commit()
            finally:
                conn.close()

            # Students hear about it, and see the deadline on the calendar,
            # only when it is published; a scheduled one is told when it opens.
            if tell_students:
                assignment_runner.announce(assignment_id)

            # Broadcast on the cross-GUI event bus so any open sibling
            # window (Grade / Module / Course / Exam) refreshes. Published
            # from the Tk thread: subscribe_tk listeners call winfo_exists /
            # after_idle synchronously inside publish().
            def _broadcast():
                try:
                    from education_system.systems.university.infrastructure.event_bus import (
                        publish, EVENT_ASSIGNMENT_CHANGED, EVENT_CALENDAR_CHANGED,
                    )
                    publish(EVENT_ASSIGNMENT_CHANGED,
                            assignment_id=assignment_id, module_code=module_code,
                            action="create")
                    publish(EVENT_CALENDAR_CHANGED,
                            event_type="Assignment", source_id=assignment_id,
                            action="create")
                except Exception:
                    logger.debug("Suppressed exception", exc_info=True)
            ui(self.root, _broadcast)

            # Update GUI on main thread
            ui(self.root, lambda: self.show_assignment_status(
                f"Assignment '{form['title']}' created. ID: {assignment_id}. "
                + self._visibility_note(form), "success"))
            ui(self.root, self.clear_assignment_form)

        except Exception as e:
            error_msg = f"Failed to create assignment: {str(e)}"
            ui(self.root, lambda: self.show_assignment_status(error_msg, "error"))


    @staticmethod
    def _visibility_note(form):
        return {
            'published': "Students on the module have been told.",
            'scheduled': f"It opens to students on {form['available_from']}.",
            'hidden': "It is hidden from students.",
        }.get(form['visibility'], "It is a draft, so students can't see it. "
                                  "Publish it from Manage Assignments.")

    def clear_assignment_form(self):
        """Clear the assignment creation form"""
        self.module_var.set('')
        self.title_var.set('')
        self.description_text.delete(1.0, tk.END)
        self.instructions_text.delete(1.0, tk.END)
        self.due_date_var.set('')
        self.due_time_var.set('23:59')
        self.max_marks_var.set('100')
        self.file_types_var.set('.pdf,.docx,.txt')
        self.max_size_var.set('10')
        self.assignment_type_var.set('individual')
        self.group_min_var.set('2')
        self.group_max_var.set('4')
        self.allow_late_var.set(True)
        self.late_penalty_var.set('0')
        self.auto_release_var.set(False)
        self.peer_review_var.set(False)

        # Clear new fields if they exist
        if hasattr(self, 'assessment_type_var'):
            self.assessment_type_var.set('essay')
        if hasattr(self, 'grading_method_var'):
            self.grading_method_var.set('points')
        if hasattr(self, 'visibility_var'):
            self.visibility_var.set('draft')
        if hasattr(self, 'available_from_var'):
            self.available_from_var.set('')
        if hasattr(self, 'max_late_days_var'):
            self.max_late_days_var.set('7')
        if hasattr(self, 'allow_resubmit_var'):
            self.allow_resubmit_var.set(False)
        if hasattr(self, 'max_attempts_var'):
            self.max_attempts_var.set('1')
        if hasattr(self, 'plagiarism_check_var'):
            self.plagiarism_check_var.set(True)
        if hasattr(self, 'rubric_var'):
            self.rubric_var.set('None')
        if hasattr(self, 'notify_on_submit_var'):
            self.notify_on_submit_var.set(True)
        if hasattr(self, 'reminder_days_var'):
            self.reminder_days_var.set('2')
        if hasattr(self, 'course_weight_var'):
            self.course_weight_var.set('0')
