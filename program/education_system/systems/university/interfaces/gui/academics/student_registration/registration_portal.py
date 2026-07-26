"""
Student Registration Portal

Main entry point that composes the browse and enrollment mixins
into a tabbed notebook interface.

For privileged users (admin/staff/registrar) the portal shows a student
picker so they can view and edit any student's registration on that
student's behalf, instead of trying to enrol their own non-student
account (which previously tripped a foreign-key error).
"""

import tkinter as tk
from tkinter import ttk

from education_system.systems.university.interfaces.gui.academics.student_registration.common_imports import (
    get_auth, get_connection, get_student_id, get_user_role, logger,
)
from education_system.systems.university.interfaces.gui.academics.student_registration.browse_modules import BrowseModulesMixin
from education_system.systems.university.interfaces.gui.academics.student_registration.enrollment import EnrollmentMixin


# Roles permitted to register on behalf of any student.
PRIVILEGED_ROLES = {
    'admin', 'administrator', 'superadmin', 'super_admin',
    'staff', 'registrar',
}


class StudentRegistrationPortal(BrowseModulesMixin, EnrollmentMixin):
    """Portal for students to browse modules, enroll, and drop."""

    def __init__(self, parent_frame, auth_instance=None):
        self.parent_frame = parent_frame
        self.auth = auth_instance or get_auth()
        self.role = get_user_role(self.auth) or ''
        self.is_privileged = self.role in PRIVILEGED_ROLES

        if self.is_privileged:
            # Act on behalf of a picked student — don't default to the
            # admin/staff account's own (non-student) id.
            self.student_id = None
        else:
            self.student_id = get_student_id(self.auth)

        self._build_ui()

    # ------------------------------------------------------------------ #
    #  Layout
    # ------------------------------------------------------------------ #
    def _build_ui(self):
        if self.is_privileged:
            self._build_student_picker()

        self.notebook = ttk.Notebook(self.parent_frame)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)
        self._populate_tabs()

    def _build_student_picker(self):
        """Top bar letting a privileged user choose which student to act
        on. Selecting a student rebuilds the tabs for that student."""
        bar = ttk.Frame(self.parent_frame)
        bar.pack(fill='x', padx=10, pady=(10, 0))

        ttk.Label(bar, text="Acting as student:",
                  font=('Arial', 10, 'bold')).pack(side='left', padx=(0, 6))

        self._student_choices = self._load_students()
        self.student_picker_var = tk.StringVar()
        self.student_combo = ttk.Combobox(
            bar, textvariable=self.student_picker_var, width=42,
            state='readonly',
            values=[label for label, _sid in self._student_choices],
        )
        self.student_combo.pack(side='left')
        self.student_combo.bind('<<ComboboxSelected>>', self._on_student_picked)

        self._picker_status = ttk.Label(
            bar, text="(no student selected)", foreground='#888888')
        self._picker_status.pack(side='left', padx=10)

    def _load_students(self):
        """Return [(label, student_id), …] for the picker."""
        choices = []
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT student_id, "
                    "TRIM(COALESCE(first_name,'')||' '||COALESCE(last_name,'')) "
                    "FROM students ORDER BY student_id"
                ).fetchall()
            for sid, name in rows:
                name = (name or '').strip()
                label = f"{sid} — {name}" if name else str(sid)
                choices.append((label, str(sid)))
        except Exception as exc:
            logger.error("Student picker load failed: %s", exc)
        return choices

    def _on_student_picked(self, _event=None):
        idx = self.student_combo.current()
        if idx < 0 or idx >= len(self._student_choices):
            return
        _label, sid = self._student_choices[idx]
        self.student_id = sid
        self._picker_status.config(
            text=f"Editing registration for {sid}", foreground='#27ae60')
        self._populate_tabs()

    def _populate_tabs(self):
        """(Re)build the dashboard/browse/enrollment tabs for the current
        ``self.student_id``. Safe to call repeatedly — existing tabs are
        cleared first so a privileged user can switch students."""
        for tab_id in self.notebook.tabs():
            self.notebook.forget(tab_id)
        for child in list(self.notebook.winfo_children()):
            child.destroy()

        dash_frame = ttk.Frame(self.notebook)
        self.notebook.add(dash_frame, text='Registration Dashboard')
        self.show_registration_dashboard(dash_frame)

        browse_frame = ttk.Frame(self.notebook)
        self.notebook.add(browse_frame, text='Available Modules')
        self.show_available_modules(browse_frame)

        enroll_frame = ttk.Frame(self.notebook)
        self.notebook.add(enroll_frame, text='My Enrollment')
        self.show_my_enrollment(enroll_frame)

    # Backwards-compatible alias for the original entry point.
    def setup_notebook(self):
        self._build_ui()
