"""
Staff Profile Management GUI

Features:
- My Profile - View/edit personal profile information
- Staff Directory - Search and browse staff members
- Documents - Manage employment documents
- Workload - View and manage workload allocation
- Schedules - Manage work schedules
- My Team - A line manager's reports (directory details only)

Everything goes through EmployeeManager, keyed by the signed-in username.
HR may set anyone's line manager (Staff Directory) and open anyone's
documents; the person keeps their own contact details up to date.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Optional
from datetime import datetime
import json

from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.infrastructure.i18n import get_text as get_translation
from education_system.systems.university.domains.staff.domain.staff_hr.services.managers.employee_manager import (
    EmployeeManager,
)
from education_system.systems.university.domains.staff.interfaces.gui.staff_hr import _access as _hr

# Translation helper
_t = get_translation

try:
    from education_system.systems.university.domains.staff.infrastructure.database.staff_hr_schemas_all import (
        init_staff_hr_schemas, get_departments, get_employment_types
    )
except ImportError:
    init_staff_hr_schemas = None
    get_departments = lambda: ['Computer Science', 'Engineering', 'Business', 'Administration', 'Other']
    get_employment_types = lambda: ['full-time', 'part-time', 'contract']


class StaffProfileGUI:
    """Staff Profile Management GUI with multiple tabs."""

    def __init__(self, root, auth: Optional[UserAuth] = None, parent_notebook=None):
        self.root = root
        self.auth = auth
        self.current_user = auth.current_user if auth and auth.current_user else None

        if not self.current_user:
            return

        self.username = _hr.user_key(self)
        self.is_hr = _hr.can(self, 'hr')
        self.is_manager = _hr.can(self, 'manager')
        # Whose documents the Documents tab shows (HR may pick someone else).
        self.docs_owner = self.username

        # Initialize schemas
        try:
            if init_staff_hr_schemas:
                init_staff_hr_schemas()
        except Exception as e:
            print(f"Warning: Could not initialize Staff HR schemas: {e}")

        if parent_notebook:
            self.tab = ttk.Frame(parent_notebook)
            parent_notebook.add(self.tab, text=_t("staff_profile.tabs.my_profile", default="Staff Profiles"))
            self._create_content(self.tab)
        else:
            self._create_standalone_window()

    def _create_standalone_window(self):
        """Create standalone window when not embedded."""
        self.window = tk.Toplevel(self.root)
        self.window.title(_t("staff_profile.window_title", default="Staff Profile Management"))
        self.window.geometry("1400x900")
        self.window.minsize(1200, 800)

        # Bottom frame with close button
        bottom_frame = ttk.Frame(self.window)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)
        ttk.Button(bottom_frame, text=_t("staff_profile.close", default="Close"), command=self.window.destroy).pack(side=tk.RIGHT, padx=5)

        # Status bar
        self.status_bar = ttk.Label(self.window, text=_t("staff_profile.ready", default="Ready"), relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self._create_content(self.window)

    def _create_content(self, parent):
        """Create the main content with notebook tabs."""
        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self._create_my_profile_tab()
        self._create_directory_tab()
        self._create_documents_tab()
        self._create_workload_tab()
        self._create_schedules_tab()
        if self.is_manager:
            self._create_team_tab()

    def _actor(self):
        return _hr.actor(self)

    def _error(self, message):
        messagebox.showerror(_t("staff_profile.common.error", default="Error"), message)

    # ================================================================
    # MY PROFILE TAB
    # ================================================================

    def _create_my_profile_tab(self):
        """Create My Profile tab for viewing/editing own profile."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("staff_profile.tabs.my_profile", default="My Profile"))

        # Form frame with scrolling
        canvas = tk.Canvas(tab)
        scrollbar = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        form_frame = ttk.Frame(canvas)

        form_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=form_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        scrollbar.pack(side="right", fill="y")

        # Personal Information
        personal_frame = ttk.LabelFrame(form_frame, text=_t("staff_profile.my_profile.personal_information", default="Personal Information"), padding=10)
        personal_frame.pack(fill=tk.X, padx=10, pady=5)

        row = 0
        ttk.Label(personal_frame, text=_t("staff_profile.my_profile.labels.employee_id", default="Employee ID:")).grid(row=row, column=0, sticky=tk.W, pady=2)
        self.employee_id_var = tk.StringVar()
        hr_state = 'normal' if self.is_hr else 'readonly'
        ttk.Entry(personal_frame, textvariable=self.employee_id_var, width=30, state=hr_state).grid(row=row, column=1, sticky=tk.W, pady=2)

        row += 1
        ttk.Label(personal_frame, text=_t("staff_profile.my_profile.labels.job_title", default="Job Title:")).grid(row=row, column=0, sticky=tk.W, pady=2)
        self.job_title_var = tk.StringVar()
        ttk.Entry(personal_frame, textvariable=self.job_title_var, width=40, state=hr_state).grid(row=row, column=1, sticky=tk.W, pady=2)

        row += 1
        ttk.Label(personal_frame, text=_t("staff_profile.my_profile.labels.department", default="Department:")).grid(row=row, column=0, sticky=tk.W, pady=2)
        self.department_var = tk.StringVar()
        dept_combo = ttk.Combobox(personal_frame, textvariable=self.department_var, values=get_departments(), width=37,
                                  state='normal' if self.is_hr else 'disabled')
        dept_combo.grid(row=row, column=1, sticky=tk.W, pady=2)

        row += 1
        ttk.Label(personal_frame, text=_t("staff_profile.my_profile.labels.employment_type", default="Employment Type:")).grid(row=row, column=0, sticky=tk.W, pady=2)
        self.employment_type_var = tk.StringVar()
        type_combo = ttk.Combobox(personal_frame, textvariable=self.employment_type_var, values=get_employment_types(), width=37,
                                  state='normal' if self.is_hr else 'disabled')
        type_combo.grid(row=row, column=1, sticky=tk.W, pady=2)

        row += 1
        ttk.Label(personal_frame, text=_t("staff_profile.my_profile.labels.hire_date", default="Hire Date:")).grid(row=row, column=0, sticky=tk.W, pady=2)
        self.hire_date_var = tk.StringVar()
        ttk.Entry(personal_frame, textvariable=self.hire_date_var, width=15, state=hr_state).grid(row=row, column=1, sticky=tk.W, pady=2)
        ttk.Label(personal_frame, text=_t("staff_profile.my_profile.labels.hire_date_format", default="(YYYY-MM-DD)")).grid(row=row, column=2, sticky=tk.W, pady=2)

        row += 1
        ttk.Label(personal_frame, text=_t("staff_profile.my_profile.labels.office_location", default="Office Location:")).grid(row=row, column=0, sticky=tk.W, pady=2)
        self.office_var = tk.StringVar()
        ttk.Entry(personal_frame, textvariable=self.office_var, width=40).grid(row=row, column=1, sticky=tk.W, pady=2)

        row += 1
        ttk.Label(personal_frame, text=_t("staff_profile.my_profile.labels.phone_extension", default="Phone Extension:")).grid(row=row, column=0, sticky=tk.W, pady=2)
        self.phone_ext_var = tk.StringVar()
        ttk.Entry(personal_frame, textvariable=self.phone_ext_var, width=15).grid(row=row, column=1, sticky=tk.W, pady=2)

        row += 1
        ttk.Label(personal_frame, text=_t("staff_profile.my_profile.labels.line_manager", default="Line Manager:")).grid(row=row, column=0, sticky=tk.W, pady=2)
        self.line_manager_var = tk.StringVar()
        ttk.Entry(personal_frame, textvariable=self.line_manager_var, width=30, state='readonly').grid(row=row, column=1, sticky=tk.W, pady=2)
        if self.is_hr:
            ttk.Button(personal_frame, text=_t("staff_profile.my_profile.buttons.change_line_manager", default="Change..."),
                       command=lambda: self._set_line_manager(self.username, after=self._load_profile)).grid(row=row, column=2, sticky=tk.W, padx=5)

        # Emergency Contact
        emergency_frame = ttk.LabelFrame(form_frame, text=_t("staff_profile.my_profile.emergency_contact", default="Emergency Contact"), padding=10)
        emergency_frame.pack(fill=tk.X, padx=10, pady=5)

        row = 0
        ttk.Label(emergency_frame, text=_t("staff_profile.my_profile.labels.contact_name", default="Contact Name:")).grid(row=row, column=0, sticky=tk.W, pady=2)
        self.emergency_name_var = tk.StringVar()
        ttk.Entry(emergency_frame, textvariable=self.emergency_name_var, width=40).grid(row=row, column=1, sticky=tk.W, pady=2)

        row += 1
        ttk.Label(emergency_frame, text=_t("staff_profile.my_profile.labels.contact_phone", default="Contact Phone:")).grid(row=row, column=0, sticky=tk.W, pady=2)
        self.emergency_phone_var = tk.StringVar()
        ttk.Entry(emergency_frame, textvariable=self.emergency_phone_var, width=20).grid(row=row, column=1, sticky=tk.W, pady=2)

        row += 1
        ttk.Label(emergency_frame, text=_t("staff_profile.my_profile.labels.relationship", default="Relationship:")).grid(row=row, column=0, sticky=tk.W, pady=2)
        self.emergency_rel_var = tk.StringVar()
        ttk.Combobox(emergency_frame, textvariable=self.emergency_rel_var,
                     values=[
                         _t("staff_profile.my_profile.relationships.spouse", default="Spouse"),
                         _t("staff_profile.my_profile.relationships.parent", default="Parent"),
                         _t("staff_profile.my_profile.relationships.sibling", default="Sibling"),
                         _t("staff_profile.my_profile.relationships.child", default="Child"),
                         _t("staff_profile.my_profile.relationships.partner", default="Partner"),
                         _t("staff_profile.my_profile.relationships.friend", default="Friend"),
                         _t("staff_profile.my_profile.relationships.other", default="Other")
                     ],
                     width=20).grid(row=row, column=1, sticky=tk.W, pady=2)

        # Bio and Expertise
        bio_frame = ttk.LabelFrame(form_frame, text=_t("staff_profile.my_profile.bio_expertise", default="Bio & Expertise"), padding=10)
        bio_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(bio_frame, text=_t("staff_profile.my_profile.labels.biography", default="Biography:")).pack(anchor=tk.W)
        self.bio_text = tk.Text(bio_frame, height=4, width=70)
        self.bio_text.pack(fill=tk.X, pady=5)

        ttk.Label(bio_frame, text=_t("staff_profile.my_profile.labels.expertise_areas", default="Expertise Areas (comma-separated):")).pack(anchor=tk.W)
        self.expertise_var = tk.StringVar()
        ttk.Entry(bio_frame, textvariable=self.expertise_var, width=70).pack(fill=tk.X, pady=5)

        ttk.Label(bio_frame, text=_t("staff_profile.my_profile.labels.qualifications", default="Qualifications (comma-separated):")).pack(anchor=tk.W)
        self.qualifications_var = tk.StringVar()
        ttk.Entry(bio_frame, textvariable=self.qualifications_var, width=70).pack(fill=tk.X, pady=5)

        # Buttons
        btn_frame = ttk.Frame(form_frame)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(btn_frame, text=_t("staff_profile.my_profile.buttons.save_profile", default="Save Profile"), command=self._save_profile).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("staff_profile.my_profile.buttons.refresh", default="Refresh"), command=self._load_profile).pack(side=tk.LEFT, padx=5)

        # Load existing profile
        self._load_profile()

    def _load_profile(self):
        """Load current user's profile."""
        try:
            profile = EmployeeManager.get_profile(self.username, actor=self._actor()) or {}
        except Exception as e:
            print(f"Error loading profile: {e}")
            return
        self.employee_id_var.set(profile.get('employee_id') or '')
        self.job_title_var.set(profile.get('job_title') or '')
        self.department_var.set(profile.get('department') or '')
        self.employment_type_var.set(profile.get('employment_type') or '')
        self.hire_date_var.set(profile.get('hire_date') or '')
        self.office_var.set(profile.get('office_location') or '')
        self.phone_ext_var.set(profile.get('phone_extension') or '')
        self.emergency_name_var.set(profile.get('emergency_contact_name') or '')
        self.emergency_phone_var.set(profile.get('emergency_contact_phone') or '')
        self.emergency_rel_var.set(profile.get('emergency_contact_relationship') or '')
        self.bio_text.delete('1.0', tk.END)
        self.bio_text.insert('1.0', profile.get('bio') or '')
        self.expertise_var.set(profile.get('expertise_areas') or '')
        self.qualifications_var.set(profile.get('qualifications') or '')
        self.line_manager_var.set(profile.get('manager_id') or '')

    def _save_profile(self):
        """Save profile changes."""
        fields = {
            'office_location': self.office_var.get(),
            'phone_extension': self.phone_ext_var.get(),
            'emergency_contact_name': self.emergency_name_var.get(),
            'emergency_contact_phone': self.emergency_phone_var.get(),
            'emergency_contact_relationship': self.emergency_rel_var.get(),
            'bio': self.bio_text.get('1.0', tk.END).strip(),
            'expertise_areas': self.expertise_var.get(),
            'qualifications': self.qualifications_var.get(),
        }
        if self.is_hr:
            fields.update({
                'employee_id': self.employee_id_var.get(),
                'job_title': self.job_title_var.get(),
                'department': self.department_var.get(),
                'employment_type': self.employment_type_var.get(),
                'hire_date': self.hire_date_var.get(),
            })
        try:
            EmployeeManager.save_profile(self._actor(), self.username, **fields)
            messagebox.showinfo(_t("staff_profile.common.success", default="Success"),
                                _t("staff_profile.my_profile.messages.save_success", default="Profile saved successfully"))
        except Exception as e:
            messagebox.showerror(_t("staff_profile.common.error", default="Error"),
                               _t("staff_profile.my_profile.messages.save_error", default="Failed to save profile: {error}", error=str(e)))

    # ================================================================
    # STAFF DIRECTORY TAB
    # ================================================================

    def _create_directory_tab(self):
        """Create Staff Directory tab for searching staff."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("staff_profile.tabs.staff_directory", default="Staff Directory"))

        # Search frame
        search_frame = ttk.LabelFrame(tab, text=_t("staff_profile.staff_directory.search_frame", default="Search"), padding=10)
        search_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(search_frame, text=_t("staff_profile.staff_directory.search_label", default="Search:")).pack(side=tk.LEFT, padx=5)
        self.dir_search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.dir_search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=5)
        search_entry.bind('<Return>', lambda e: self._search_directory())

        ttk.Label(search_frame, text=_t("staff_profile.staff_directory.department_label", default="Department:")).pack(side=tk.LEFT, padx=5)
        self.dir_dept_var = tk.StringVar(value=_t("staff_profile.staff_directory.all_departments", default="All"))
        dept_combo = ttk.Combobox(search_frame, textvariable=self.dir_dept_var,
                                   values=[_t("staff_profile.staff_directory.all_departments", default="All")] + get_departments(), width=20)
        dept_combo.pack(side=tk.LEFT, padx=5)

        ttk.Button(search_frame, text=_t("staff_profile.staff_directory.search_button", default="Search"), command=self._search_directory).pack(side=tk.LEFT, padx=5)
        if self.is_hr:
            ttk.Button(search_frame, text=_t("staff_profile.staff_directory.set_line_manager", default="Set Line Manager"),
                       command=self._set_selected_line_manager).pack(side=tk.LEFT, padx=5)
            ttk.Button(search_frame, text=_t("staff_profile.staff_directory.open_documents", default="Documents"),
                       command=self._open_selected_documents).pack(side=tk.LEFT, padx=5)

        # Results frame
        results_frame = ttk.Frame(tab)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        columns = ('Name', 'Job Title', 'Department', 'Email', 'Phone', 'Office')
        self.dir_tree = ttk.Treeview(results_frame, columns=columns, show='headings', height=20)

        column_translations = {
            'Name': _t("staff_profile.staff_directory.columns.name", default="Name"),
            'Job Title': _t("staff_profile.staff_directory.columns.job_title", default="Job Title"),
            'Department': _t("staff_profile.staff_directory.columns.department", default="Department"),
            'Email': _t("staff_profile.staff_directory.columns.email", default="Email"),
            'Phone': _t("staff_profile.staff_directory.columns.phone", default="Phone"),
            'Office': _t("staff_profile.staff_directory.columns.office", default="Office")
        }

        for col in columns:
            self.dir_tree.heading(col, text=column_translations[col])
            self.dir_tree.column(col, width=120)

        scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.dir_tree.yview)
        self.dir_tree.configure(yscrollcommand=scrollbar.set)

        self.dir_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.dir_tree.bind('<Double-1>', self._view_staff_details)

        # Load initial data
        self._search_directory()

    def _search_directory(self):
        """Search staff directory."""
        search = self.dir_search_var.get().lower()
        dept = self.dir_dept_var.get()
        all_text = _t("staff_profile.staff_directory.all_departments", default="All")
        na_text = _t("staff_profile.staff_directory.na", default="N/A")

        self.dir_tree.delete(*self.dir_tree.get_children())

        try:
            rows = EmployeeManager.directory(search=search or None,
                                             department=None if dept == all_text else dept)
        except Exception as e:
            print(f"Error searching directory: {e}")
            return
        for row in rows:
            self.dir_tree.insert('', 'end', iid=row['username'], values=(
                row['username'] or na_text,
                row.get('job_title') or na_text,
                row.get('department') or na_text,
                row.get('email') or na_text,
                row.get('phone_extension') or na_text,
                row.get('office_location') or na_text
            ))

    def _selected_directory_user(self):
        selection = self.dir_tree.selection()
        if not selection:
            messagebox.showwarning(_t("staff_profile.common.warning", default="Warning"),
                                   _t("staff_profile.staff_directory.select_person", default="Please select a member of staff"))
            return None
        return selection[0]

    def _view_staff_details(self, event):
        """View detailed staff profile."""
        selection = self.dir_tree.selection()
        if not selection:
            return

        username = selection[0]
        na_text = _t("staff_profile.staff_directory.na", default="N/A")

        # Create details dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("staff_profile.staff_directory.profile_window.title", default="Staff Profile - {username}", username=username))
        dialog.geometry("500x400")
        dialog.transient(self.root)

        try:
            card = EmployeeManager.directory_entry(username)
            if card:
                info_text = tk.Text(dialog, wrap=tk.WORD, padx=10, pady=10)
                info_text.pack(fill=tk.BOTH, expand=True)

                full_name = ' '.join(p for p in (card.get('first_name'), card.get('last_name')) if p)
                info_text.insert(tk.END, _t("staff_profile.staff_directory.profile_window.name", default="Name: {name}",
                                            name=f"{full_name} ({username})" if full_name else username) + "\n")
                info_text.insert(tk.END, _t("staff_profile.staff_directory.profile_window.job_title", default="Job Title: {title}", title=card.get('job_title') or na_text) + "\n")
                info_text.insert(tk.END, _t("staff_profile.staff_directory.profile_window.department", default="Department: {dept}", dept=card.get('department') or na_text) + "\n")
                info_text.insert(tk.END, _t("staff_profile.staff_directory.profile_window.line_manager", default="Line Manager: {manager}", manager=card.get('manager_id') or na_text) + "\n")
                info_text.insert(tk.END, _t("staff_profile.staff_directory.profile_window.email", default="Email: {email}", email=card.get('email') or na_text) + "\n")
                info_text.insert(tk.END, _t("staff_profile.staff_directory.profile_window.office", default="Office: {office}", office=card.get('office_location') or na_text) + "\n")
                info_text.insert(tk.END, _t("staff_profile.staff_directory.profile_window.phone", default="Phone: {phone}", phone=card.get('phone_extension') or na_text) + "\n\n")
                info_text.insert(tk.END, _t("staff_profile.staff_directory.profile_window.bio", default="Bio:\n{bio}", bio=card.get('bio') or na_text) + "\n\n")
                info_text.insert(tk.END, _t("staff_profile.staff_directory.profile_window.expertise", default="Expertise: {expertise}", expertise=card.get('expertise_areas') or na_text) + "\n")
                info_text.insert(tk.END, _t("staff_profile.staff_directory.profile_window.qualifications", default="Qualifications: {quals}", quals=card.get('qualifications') or na_text) + "\n")

                info_text.config(state=tk.DISABLED)
            else:
                ttk.Label(dialog, text=_t("staff_profile.staff_directory.no_profile", default="No profile found")).pack(pady=20)
        except Exception as e:
            ttk.Label(dialog, text=_t("staff_profile.staff_directory.errors.profile_error", default="Error loading profile: {error}", error=str(e))).pack(pady=20)

        buttons = ttk.Frame(dialog)
        buttons.pack(pady=10)
        if self.is_hr:
            ttk.Button(buttons, text=_t("staff_profile.staff_directory.set_line_manager", default="Set Line Manager"),
                       command=lambda: (dialog.destroy(), self._set_line_manager(username, after=self._search_directory))).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons, text=_t("staff_profile.staff_directory.profile_window.close", default="Close"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    # ================================================================
    # LINE MANAGERS (HR)
    # ================================================================

    def _set_selected_line_manager(self):
        username = self._selected_directory_user()
        if username:
            self._set_line_manager(username, after=self._search_directory)

    def _open_selected_documents(self):
        """HR: show the selected person's documents on the Documents tab."""
        username = self._selected_directory_user()
        if not username:
            return
        self.docs_owner_var.set(username)
        self._load_documents()
        self.notebook.select(self.docs_tab)

    def _set_line_manager(self, username, after=None):
        """HR: pick (or clear) ``username``'s line manager."""
        try:
            current = (EmployeeManager.get_profile(username, actor=self._actor()) or {}).get('manager_id') or ''
            people = [r['username'] for r in EmployeeManager.directory() if r['username'] != username]
        except Exception as e:
            self._error(str(e))
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(_t("staff_profile.line_manager.title", default="Line Manager - {username}", username=username))
        dialog.geometry("420x200")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text=_t("staff_profile.line_manager.prompt",
                                  default="Line manager for {username} (leave blank for none):",
                                  username=username)).pack(pady=(15, 5), padx=10, anchor=tk.W)
        manager_var = tk.StringVar(value=current)
        ttk.Combobox(dialog, textvariable=manager_var, values=people, width=40).pack(padx=10, anchor=tk.W)

        def save():
            try:
                boss = EmployeeManager.set_line_manager(self._actor(), username, manager_var.get().strip() or None)
            except (PermissionError, ValueError) as e:
                self._error(str(e))
                return
            except Exception as e:
                self._error(_t("staff_profile.line_manager.error", default="Failed to set line manager: {error}", error=str(e)))
                return
            dialog.destroy()
            messagebox.showinfo(_t("staff_profile.common.success", default="Success"),
                                _t("staff_profile.line_manager.saved", default="{username}'s line manager is now {manager}",
                                   username=username, manager=boss or _t("staff_profile.line_manager.none", default="nobody")))
            if after:
                after()

        btns = ttk.Frame(dialog)
        btns.pack(pady=20)
        ttk.Button(btns, text=_t("staff_profile.line_manager.save", default="Save"), command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text=_t("staff_profile.line_manager.cancel", default="Cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    # ================================================================
    # DOCUMENTS TAB
    # ================================================================

    def _create_documents_tab(self):
        """Create Documents tab for managing employment documents."""
        tab = ttk.Frame(self.notebook)
        self.docs_tab = tab
        self.notebook.add(tab, text=_t("staff_profile.tabs.documents", default="Documents"))

        # Whose documents (HR may open anyone's; every look is audited)
        self.docs_owner_var = tk.StringVar(value=self.username)
        if self.is_hr:
            owner_frame = ttk.Frame(tab)
            owner_frame.pack(fill=tk.X, padx=10, pady=(5, 0))
            ttk.Label(owner_frame, text=_t("staff_profile.documents.staff_member", default="Staff member:")).pack(side=tk.LEFT, padx=5)
            owner_entry = ttk.Entry(owner_frame, textvariable=self.docs_owner_var, width=25)
            owner_entry.pack(side=tk.LEFT, padx=5)
            owner_entry.bind('<Return>', lambda e: self._load_documents())
            ttk.Button(owner_frame, text=_t("staff_profile.documents.buttons.load", default="Load"), command=self._load_documents).pack(side=tk.LEFT, padx=5)
            ttk.Button(owner_frame, text=_t("staff_profile.documents.buttons.mine", default="My Documents"),
                       command=lambda: (self.docs_owner_var.set(self.username), self._load_documents())).pack(side=tk.LEFT, padx=5)

        # Buttons frame
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(btn_frame, text=_t("staff_profile.documents.buttons.upload_document", default="Upload Document"), command=self._upload_document).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("staff_profile.documents.buttons.view_document", default="View Document"), command=self._view_document).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("staff_profile.documents.buttons.delete_document", default="Delete Document"), command=self._delete_document).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("staff_profile.documents.buttons.refresh", default="Refresh"), command=self._load_documents).pack(side=tk.LEFT, padx=5)

        # Documents list
        list_frame = ttk.Frame(tab)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        columns = ('ID', 'Type', 'Name', 'Issue Date', 'Expiry Date', 'Status')
        self.docs_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)

        column_translations = {
            'ID': _t("staff_profile.documents.columns.id", default="ID"),
            'Type': _t("staff_profile.documents.columns.type", default="Type"),
            'Name': _t("staff_profile.documents.columns.name", default="Name"),
            'Issue Date': _t("staff_profile.documents.columns.issue_date", default="Issue Date"),
            'Expiry Date': _t("staff_profile.documents.columns.expiry_date", default="Expiry Date"),
            'Status': _t("staff_profile.documents.columns.status", default="Status")
        }

        for col in columns:
            self.docs_tree.heading(col, text=column_translations[col])
            self.docs_tree.column(col, width=100)

        self.docs_tree.column('ID', width=50)
        self.docs_tree.column('Name', width=200)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.docs_tree.yview)
        self.docs_tree.configure(yscrollcommand=scrollbar.set)

        self.docs_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Status colors
        self.docs_tree.tag_configure('active', background='#90EE90')
        self.docs_tree.tag_configure('expired', background='#FFB6C1')
        self.docs_tree.tag_configure('expiring', background='#FFFFE0')

        self._load_documents()

    def _docs_owner(self):
        return self.docs_owner_var.get().strip() or self.username

    def _load_documents(self):
        """Load the documents of the person shown (yourself unless HR picked
        someone)."""
        self.docs_tree.delete(*self.docs_tree.get_children())

        na_text = _t("staff_profile.documents.na", default="N/A")
        other_text = _t("staff_profile.documents.other", default="Other")
        unknown_text = _t("staff_profile.documents.unknown", default="Unknown")
        active_text = _t("staff_profile.documents.status.active", default="active")
        expired_text = _t("staff_profile.documents.status.expired", default="expired")

        try:
            docs = EmployeeManager.get_documents(self._docs_owner(), actor=self._actor())
        except PermissionError as e:
            self._error(str(e))
            return
        except Exception as e:
            print(f"Error loading documents: {e}")
            return

        today = datetime.now().date()
        for doc in docs:
            status = doc.get('status') or active_text
            tag = 'active'

            if doc.get('expiry_date'):  # Has expiry date
                try:
                    expiry = datetime.strptime(doc['expiry_date'], '%Y-%m-%d').date()
                    if expiry < today:
                        status = expired_text
                        tag = 'expired'
                    elif (expiry - today).days <= 30:
                        tag = 'expiring'
                except (ValueError, TypeError):
                    pass

            self.docs_tree.insert('', 'end', values=(
                doc['document_id'], doc.get('document_type') or other_text,
                doc.get('document_name') or unknown_text,
                doc.get('issue_date') or na_text, doc.get('expiry_date') or na_text, status
            ), tags=(tag,))

    def _upload_document(self):
        """Upload a new document."""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("staff_profile.documents.upload_dialog.title", default="===== UPLOAD DIALOG ====="))
        dialog.geometry("400x350")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text=_t("staff_profile.documents.upload_dialog.document_type", default="Document Type:")).pack(pady=5)
        type_var = tk.StringVar()
        ttk.Combobox(dialog, textvariable=type_var, values=[
            _t("staff_profile.documents.upload_dialog.types.contract", default="contract"),
            _t("staff_profile.documents.upload_dialog.types.id_document", default="id_document"),
            _t("staff_profile.documents.upload_dialog.types.qualification", default="qualification"),
            _t("staff_profile.documents.upload_dialog.types.certification", default="certification"),
            _t("staff_profile.documents.upload_dialog.types.visa", default="visa"),
            _t("staff_profile.documents.upload_dialog.types.right_to_work", default="right_to_work"),
            _t("staff_profile.documents.upload_dialog.types.dbs_check", default="dbs_check"),
            _t("staff_profile.documents.upload_dialog.types.reference", default="reference"),
            _t("staff_profile.documents.upload_dialog.types.other", default="other")
        ], width=30).pack(pady=5)

        ttk.Label(dialog, text=_t("staff_profile.documents.upload_dialog.document_name", default="Document Name:")).pack(pady=5)
        name_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=name_var, width=40).pack(pady=5)

        ttk.Label(dialog, text=_t("staff_profile.documents.upload_dialog.issue_date", default="Issue Date (YYYY-MM-DD):")).pack(pady=5)
        issue_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=issue_var, width=20).pack(pady=5)

        ttk.Label(dialog, text=_t("staff_profile.documents.upload_dialog.expiry_date", default="Expiry Date (YYYY-MM-DD):")).pack(pady=5)
        expiry_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=expiry_var, width=20).pack(pady=5)

        file_path_var = tk.StringVar()
        ttk.Label(dialog, text=_t("staff_profile.documents.upload_dialog.file", default="File:")).pack(pady=5)
        file_frame = ttk.Frame(dialog)
        file_frame.pack(pady=5)
        ttk.Entry(file_frame, textvariable=file_path_var, width=30).pack(side=tk.LEFT)
        ttk.Button(file_frame, text=_t("staff_profile.documents.upload_dialog.browse", default="Browse..."),
                   command=lambda: file_path_var.set(filedialog.askopenfilename())).pack(side=tk.LEFT, padx=5)

        def save_document():
            try:
                EmployeeManager.add_document(self._docs_owner(), type_var.get(), name_var.get(),
                                             file_path_var.get() or None, actor=self._actor(),
                                             issue_date=issue_var.get() or None,
                                             expiry_date=expiry_var.get() or None)
                messagebox.showinfo(_t("staff_profile.common.success", default="Success"),
                                  _t("staff_profile.documents.messages.upload_success", default="Document uploaded successfully"))
                dialog.destroy()
                self._load_documents()
            except Exception as e:
                messagebox.showerror(_t("staff_profile.common.error", default="Error"),
                                   _t("staff_profile.documents.messages.upload_error", default="Failed to upload document: {error}", error=str(e)))

        ttk.Button(dialog, text=_t("staff_profile.documents.upload_dialog.upload_button", default="Upload"), command=save_document).pack(pady=20)

    def _view_document(self):
        """View selected document."""
        selection = self.docs_tree.selection()
        if not selection:
            messagebox.showwarning(_t("staff_profile.common.warning", default="Warning"),
                                 _t("staff_profile.documents.messages.select_to_view", default="Please select a document to view"))
            return

        item = self.docs_tree.item(selection[0])
        doc_id = item['values'][0]

        try:
            doc = EmployeeManager.get_document(doc_id, actor=self._actor()) or {}
            path = doc.get('file_path')
            if path:
                import os
                if os.path.exists(path):
                    if os.name == 'nt':
                        os.startfile(path)
                    else:
                        import subprocess
                        subprocess.run(['xdg-open', path], check=False)
                else:
                    messagebox.showinfo(_t("staff_profile.common.info", default="Info"),
                                        _t("staff_profile.documents.messages.file_path", default="File path: {path}\n\nFile not found on disk.", path=path))
            else:
                messagebox.showinfo(_t("staff_profile.common.info", default="Info"),
                                    _t("staff_profile.documents.messages.no_file_path", default="No file path associated with this document"))
        except Exception as e:
            messagebox.showerror(_t("staff_profile.common.error", default="Error"),
                               _t("staff_profile.documents.messages.open_error", default="Failed to open document: {error}", error=str(e)))

    def _delete_document(self):
        """Delete selected document."""
        selection = self.docs_tree.selection()
        if not selection:
            messagebox.showwarning(_t("staff_profile.common.warning", default="Warning"),
                                 _t("staff_profile.documents.messages.select_to_delete", default="Please select a document to delete"))
            return

        if not messagebox.askyesno(_t("staff_profile.documents.messages.delete_confirm_title", default="Confirm"),
                                   _t("staff_profile.documents.messages.delete_confirm_message", default="Are you sure you want to delete this document?")):
            return

        item = self.docs_tree.item(selection[0])
        doc_id = item['values'][0]

        try:
            EmployeeManager.delete_document(doc_id, actor=self._actor())
            messagebox.showinfo(_t("staff_profile.common.success", default="Success"),
                              _t("staff_profile.documents.messages.delete_success", default="Document deleted successfully"))
            self._load_documents()
        except Exception as e:
            messagebox.showerror(_t("staff_profile.common.error", default="Error"),
                               _t("staff_profile.documents.messages.delete_error", default="Failed to delete document: {error}", error=str(e)))

    # ================================================================
    # WORKLOAD TAB
    # ================================================================

    def _create_workload_tab(self):
        """Create Workload tab for managing workload allocation."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("staff_profile.tabs.workload", default="Workload"))

        # Filter frame
        filter_frame = ttk.Frame(tab)
        filter_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(filter_frame, text=_t("staff_profile.workload.filter_label", default="Label")).pack(side=tk.LEFT, padx=5)
        self.workload_year_var = tk.StringVar(value=str(datetime.now().year))
        ttk.Entry(filter_frame, textvariable=self.workload_year_var, width=10).pack(side=tk.LEFT, padx=5)

        ttk.Button(filter_frame, text=_t("staff_profile.workload.buttons.load", default="Load"), command=self._load_workload).pack(side=tk.LEFT, padx=5)
        ttk.Button(filter_frame, text=_t("staff_profile.workload.buttons.save", default="Save"), command=self._save_workload).pack(side=tk.LEFT, padx=5)

        # Workload form
        form_frame = ttk.LabelFrame(tab, text=_t("staff_profile.workload.workload_allocation", default="Workload Allocation"), padding=10)
        form_frame.pack(fill=tk.X, padx=10, pady=10)

        row = 0
        ttk.Label(form_frame, text=_t("staff_profile.workload.labels.teaching_hours", default="Teaching Hours:")).grid(row=row, column=0, sticky=tk.W, pady=5)
        self.teaching_hours_var = tk.StringVar(value="0")
        ttk.Entry(form_frame, textvariable=self.teaching_hours_var, width=10).grid(row=row, column=1, sticky=tk.W, pady=5)

        row += 1
        ttk.Label(form_frame, text=_t("staff_profile.workload.labels.research_hours", default="Research Hours:")).grid(row=row, column=0, sticky=tk.W, pady=5)
        self.research_hours_var = tk.StringVar(value="0")
        ttk.Entry(form_frame, textvariable=self.research_hours_var, width=10).grid(row=row, column=1, sticky=tk.W, pady=5)

        row += 1
        ttk.Label(form_frame, text=_t("staff_profile.workload.labels.admin_hours", default="Admin Hours:")).grid(row=row, column=0, sticky=tk.W, pady=5)
        self.admin_hours_var = tk.StringVar(value="0")
        ttk.Entry(form_frame, textvariable=self.admin_hours_var, width=10).grid(row=row, column=1, sticky=tk.W, pady=5)

        row += 1
        ttk.Label(form_frame, text=_t("staff_profile.workload.labels.service_hours", default="Service Hours:")).grid(row=row, column=0, sticky=tk.W, pady=5)
        self.service_hours_var = tk.StringVar(value="0")
        ttk.Entry(form_frame, textvariable=self.service_hours_var, width=10).grid(row=row, column=1, sticky=tk.W, pady=5)

        row += 1
        ttk.Label(form_frame, text=_t("staff_profile.workload.labels.total_fte", default="Total FTE:")).grid(row=row, column=0, sticky=tk.W, pady=5)
        self.fte_var = tk.StringVar(value="1.0")
        ttk.Entry(form_frame, textvariable=self.fte_var, width=10).grid(row=row, column=1, sticky=tk.W, pady=5)

        row += 1
        ttk.Label(form_frame, text=_t("staff_profile.workload.labels.notes", default="Notes:")).grid(row=row, column=0, sticky=tk.W, pady=5)
        self.workload_notes = tk.Text(form_frame, height=3, width=50)
        self.workload_notes.grid(row=row, column=1, sticky=tk.W, pady=5)

        # Summary
        summary_frame = ttk.LabelFrame(tab, text=_t("staff_profile.workload.summary", default="Summary"), padding=10)
        summary_frame.pack(fill=tk.X, padx=10, pady=10)

        self.workload_summary_label = ttk.Label(summary_frame, text=_t("staff_profile.workload.summary_default", default="Total: 0 hours"))
        self.workload_summary_label.pack()

        self._load_workload()

    def _load_workload(self):
        """Load workload data (the whole-year allocation for the year shown)."""
        year = self.workload_year_var.get()

        try:
            rows = EmployeeManager.get_workload(self.username, academic_year=year, actor=self._actor())
        except Exception as e:
            print(f"Error loading workload: {e}")
            return
        row = next((r for r in rows if r.get('semester') is None), rows[0] if rows else None)
        if row:
            self.teaching_hours_var.set(str(row.get('teaching_hours') or 0))
            self.research_hours_var.set(str(row.get('research_hours') or 0))
            self.admin_hours_var.set(str(row.get('admin_hours') or 0))
            self.service_hours_var.set(str(row.get('service_hours') or 0))
            self.fte_var.set(str(row.get('total_fte') or 1.0))
            self.workload_notes.delete('1.0', tk.END)
            self.workload_notes.insert('1.0', row.get('notes') or '')
        else:
            self.teaching_hours_var.set("0")
            self.research_hours_var.set("0")
            self.admin_hours_var.set("0")
            self.service_hours_var.set("0")
            self.fte_var.set("1.0")
            self.workload_notes.delete('1.0', tk.END)
        self._loaded_semester = row.get('semester') if row else None

        self._update_workload_summary()

    def _save_workload(self):
        """Save workload data."""
        year = self.workload_year_var.get()

        try:
            EmployeeManager.set_workload(
                self.username, year, getattr(self, '_loaded_semester', None), actor=self._actor(),
                teaching_hours=float(self.teaching_hours_var.get() or 0),
                research_hours=float(self.research_hours_var.get() or 0),
                admin_hours=float(self.admin_hours_var.get() or 0),
                service_hours=float(self.service_hours_var.get() or 0),
                total_fte=float(self.fte_var.get() or 1.0),
                notes=self.workload_notes.get('1.0', tk.END).strip())
            messagebox.showinfo(_t("staff_profile.common.success", default="Success"),
                                _t("staff_profile.workload.messages.save_success", default="Workload saved successfully"))
            self._update_workload_summary()
        except Exception as e:
            messagebox.showerror(_t("staff_profile.common.error", default="Error"),
                               _t("staff_profile.workload.messages.save_error", default="Failed to save workload: {error}", error=str(e)))

    def _update_workload_summary(self):
        """Update workload summary display."""
        try:
            total = (
                float(self.teaching_hours_var.get() or 0) +
                float(self.research_hours_var.get() or 0) +
                float(self.admin_hours_var.get() or 0) +
                float(self.service_hours_var.get() or 0)
            )
            self.workload_summary_label.config(text=_t("staff_profile.workload.summary_text", default="Total: {total} hours per week", total=f"{total:.1f}"))
        except (ValueError, TypeError):
            self.workload_summary_label.config(text=_t("staff_profile.workload.summary_default", default="Total: 0 hours"))

    # ================================================================
    # SCHEDULES TAB
    # ================================================================

    def _create_schedules_tab(self):
        """Create Schedules tab for managing work schedules."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("staff_profile.tabs.schedules", default="Schedules"))

        # Buttons frame
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(btn_frame, text=_t("staff_profile.schedules.buttons.add_schedule", default="Add Schedule"), command=self._add_schedule).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("staff_profile.schedules.buttons.edit_schedule", default="Edit Schedule"), command=self._edit_schedule).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("staff_profile.schedules.buttons.delete_schedule", default="Delete Schedule"), command=self._delete_schedule).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("staff_profile.schedules.buttons.refresh", default="Refresh"), command=self._load_schedules).pack(side=tk.LEFT, padx=5)

        # Schedules list
        list_frame = ttk.Frame(tab)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        columns = ('ID', 'Day', 'Start', 'End', 'Location', 'Type', 'Recurring')
        self.schedules_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)

        column_translations = {
            'ID': _t("staff_profile.schedules.columns.id", default="ID"),
            'Day': _t("staff_profile.schedules.columns.day", default="Day"),
            'Start': _t("staff_profile.schedules.columns.start", default="Start"),
            'End': _t("staff_profile.schedules.columns.end", default="End"),
            'Location': _t("staff_profile.schedules.columns.location", default="Location"),
            'Type': _t("staff_profile.schedules.columns.type", default="Type"),
            'Recurring': _t("staff_profile.schedules.columns.recurring", default="Recurring")
        }

        for col in columns:
            self.schedules_tree.heading(col, text=column_translations[col])
            self.schedules_tree.column(col, width=100)

        self.schedules_tree.column('ID', width=50)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.schedules_tree.yview)
        self.schedules_tree.configure(yscrollcommand=scrollbar.set)

        self.schedules_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._load_schedules()

    def _load_schedules(self):
        """Load user's schedules."""
        self.schedules_tree.delete(*self.schedules_tree.get_children())

        days = [
            _t("staff_profile.schedules.days.monday", default="Monday"),
            _t("staff_profile.schedules.days.tuesday", default="Tuesday"),
            _t("staff_profile.schedules.days.wednesday", default="Wednesday"),
            _t("staff_profile.schedules.days.thursday", default="Thursday"),
            _t("staff_profile.schedules.days.friday", default="Friday"),
            _t("staff_profile.schedules.days.saturday", default="Saturday"),
            _t("staff_profile.schedules.days.sunday", default="Sunday")
        ]

        na_text = _t("staff_profile.schedules.na", default="N/A")
        yes_text = _t("staff_profile.schedules.yes", default="Yes")
        no_text = _t("staff_profile.schedules.no", default="No")

        try:
            rows = EmployeeManager.get_schedules(self.username, actor=self._actor())
        except Exception as e:
            print(f"Error loading schedules: {e}")
            return
        for row in rows:
            day = row.get('day_of_week')
            day_name = days[day] if isinstance(day, int) and 0 <= day < 7 else na_text
            self.schedules_tree.insert('', 'end', values=(
                row.get('schedule_id'), day_name, row.get('start_time') or na_text,
                row.get('end_time') or na_text, row.get('location') or na_text,
                row.get('schedule_type') or na_text,
                yes_text if row.get('is_recurring') else no_text
            ))

    def _add_schedule(self):
        """Add a new schedule entry."""
        self._schedule_dialog()

    def _edit_schedule(self):
        """Edit selected schedule."""
        selection = self.schedules_tree.selection()
        if not selection:
            messagebox.showwarning(_t("staff_profile.common.warning", default="Warning"),
                                 _t("staff_profile.schedules.messages.select_to_edit", default="Please select a schedule to edit"))
            return

        item = self.schedules_tree.item(selection[0])
        schedule_id = item['values'][0]
        self._schedule_dialog(schedule_id)

    def _schedule_dialog(self, schedule_id=None):
        """Show schedule add/edit dialog."""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("staff_profile.schedules.dialog.edit_title", default="Edit Schedule") if schedule_id else _t("staff_profile.schedules.dialog.add_title", default="Add Schedule"))
        dialog.geometry("400x400")
        dialog.transient(self.root)
        dialog.grab_set()

        days = [
            _t("staff_profile.schedules.days.monday", default="Monday"),
            _t("staff_profile.schedules.days.tuesday", default="Tuesday"),
            _t("staff_profile.schedules.days.wednesday", default="Wednesday"),
            _t("staff_profile.schedules.days.thursday", default="Thursday"),
            _t("staff_profile.schedules.days.friday", default="Friday"),
            _t("staff_profile.schedules.days.saturday", default="Saturday"),
            _t("staff_profile.schedules.days.sunday", default="Sunday")
        ]

        ttk.Label(dialog, text=_t("staff_profile.schedules.dialog.day_label", default="Day:")).pack(pady=5)
        day_var = tk.StringVar()
        ttk.Combobox(dialog, textvariable=day_var, values=days, width=20).pack(pady=5)

        ttk.Label(dialog, text=_t("staff_profile.schedules.dialog.start_time_label", default="Start Time (HH:MM):")).pack(pady=5)
        start_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=start_var, width=10).pack(pady=5)

        ttk.Label(dialog, text=_t("staff_profile.schedules.dialog.end_time_label", default="End Time (HH:MM):")).pack(pady=5)
        end_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=end_var, width=10).pack(pady=5)

        ttk.Label(dialog, text=_t("staff_profile.schedules.dialog.location_label", default="Location:")).pack(pady=5)
        location_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=location_var, width=30).pack(pady=5)

        ttk.Label(dialog, text=_t("staff_profile.schedules.dialog.type_label", default="Type:")).pack(pady=5)
        type_var = tk.StringVar()
        ttk.Combobox(dialog, textvariable=type_var,
                     values=[
                         _t("staff_profile.schedules.dialog.types.office_hours", default="office_hours"),
                         _t("staff_profile.schedules.dialog.types.teaching", default="teaching"),
                         _t("staff_profile.schedules.dialog.types.meeting", default="meeting"),
                         _t("staff_profile.schedules.dialog.types.research", default="research"),
                         _t("staff_profile.schedules.dialog.types.admin", default="admin"),
                         _t("staff_profile.schedules.dialog.types.other", default="other")
                     ],
                     width=20).pack(pady=5)

        recurring_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(dialog, text=_t("staff_profile.schedules.dialog.recurring_checkbox", default="Recurring Weekly"), variable=recurring_var).pack(pady=5)

        # Load existing data if editing
        if schedule_id:
            try:
                row = EmployeeManager.get_schedule(schedule_id, actor=self._actor())
                if row:
                    day = row.get('day_of_week')
                    day_var.set(days[day] if isinstance(day, int) and 0 <= day < 7 else '')
                    start_var.set(row.get('start_time') or '')
                    end_var.set(row.get('end_time') or '')
                    location_var.set(row.get('location') or '')
                    type_var.set(row.get('schedule_type') or '')
                    recurring_var.set(bool(row.get('is_recurring')))
            except Exception as e:
                print(f"Error loading schedule: {e}")

        def save():
            day_idx = days.index(day_var.get()) if day_var.get() in days else 0
            fields = dict(location=location_var.get(), schedule_type=type_var.get(),
                          is_recurring=1 if recurring_var.get() else 0)

            try:
                if schedule_id:
                    EmployeeManager.update_schedule(schedule_id, actor=self._actor(), day_of_week=day_idx,
                                                    start_time=start_var.get(), end_time=end_var.get(), **fields)
                else:
                    EmployeeManager.add_schedule(self.username, day_idx, start_var.get(), end_var.get(),
                                                 actor=self._actor(), **fields)
                messagebox.showinfo(_t("staff_profile.common.success", default="Success"),
                                  _t("staff_profile.schedules.messages.save_success", default="Schedule saved successfully"))
                dialog.destroy()
                self._load_schedules()
            except Exception as e:
                messagebox.showerror(_t("staff_profile.common.error", default="Error"),
                                   _t("staff_profile.schedules.messages.save_error", default="Failed to save schedule: {error}", error=str(e)))

        ttk.Button(dialog, text=_t("staff_profile.schedules.dialog.save_button", default="Save"), command=save).pack(pady=20)

    def _delete_schedule(self):
        """Delete selected schedule."""
        selection = self.schedules_tree.selection()
        if not selection:
            messagebox.showwarning(_t("staff_profile.common.warning", default="Warning"),
                                 _t("staff_profile.schedules.messages.select_to_delete", default="Please select a schedule to delete"))
            return

        if not messagebox.askyesno(_t("staff_profile.schedules.messages.delete_confirm_title", default="Confirm"),
                                   _t("staff_profile.schedules.messages.delete_confirm_message", default="Are you sure you want to delete this schedule?")):
            return

        item = self.schedules_tree.item(selection[0])
        schedule_id = item['values'][0]

        try:
            EmployeeManager.delete_schedule(schedule_id, actor=self._actor())
            messagebox.showinfo(_t("staff_profile.common.success", default="Success"),
                              _t("staff_profile.schedules.messages.delete_success", default="Schedule deleted successfully"))
            self._load_schedules()
        except Exception as e:
            messagebox.showerror(_t("staff_profile.common.error", default="Error"),
                               _t("staff_profile.schedules.messages.delete_error", default="Failed to delete schedule: {error}", error=str(e)))

    # ================================================================
    # MY TEAM TAB (line managers)
    # ================================================================

    def _create_team_tab(self):
        """Create My Team tab: the signed-in manager's reports."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("staff_profile.tabs.my_team", default="My Team"))

        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)

        self.team_deep_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(btn_frame, text=_t("staff_profile.team.include_indirect", default="Include indirect reports"),
                        variable=self.team_deep_var, command=self._load_team).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("staff_profile.team.view_profile", default="View Profile"),
                   command=self._view_team_member).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("staff_profile.team.view_schedule", default="View Schedule"),
                   command=self._view_team_schedule).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("staff_profile.team.view_workload", default="View Workload"),
                   command=self._view_team_workload).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("staff_profile.team.refresh", default="Refresh"),
                   command=self._load_team).pack(side=tk.LEFT, padx=5)

        list_frame = ttk.Frame(tab)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        columns = ('Username', 'Name', 'Job Title', 'Department', 'Email', 'Phone', 'Line Manager')
        self.team_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=18)
        headings = {
            'Username': _t("staff_profile.team.columns.username", default="Username"),
            'Name': _t("staff_profile.team.columns.name", default="Name"),
            'Job Title': _t("staff_profile.team.columns.job_title", default="Job Title"),
            'Department': _t("staff_profile.team.columns.department", default="Department"),
            'Email': _t("staff_profile.team.columns.email", default="Email"),
            'Phone': _t("staff_profile.team.columns.phone", default="Phone"),
            'Line Manager': _t("staff_profile.team.columns.line_manager", default="Line Manager"),
        }
        for col in columns:
            self.team_tree.heading(col, text=headings[col])
            self.team_tree.column(col, width=130)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.team_tree.yview)
        self.team_tree.configure(yscrollcommand=scrollbar.set)
        self.team_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.team_tree.bind('<Double-1>', lambda e: self._view_team_member())

        self.team_summary = ttk.Label(tab, text="")
        self.team_summary.pack(anchor=tk.W, padx=10, pady=(0, 5))

        self._load_team()

    def _load_team(self):
        self.team_tree.delete(*self.team_tree.get_children())
        na_text = _t("staff_profile.staff_directory.na", default="N/A")
        try:
            team = EmployeeManager.team_of(self._actor(), deep=self.team_deep_var.get())
        except Exception as e:
            print(f"Error loading team: {e}")
            return
        for row in team:
            name = ' '.join(p for p in (row.get('first_name'), row.get('last_name')) if p)
            self.team_tree.insert('', 'end', iid=row['username'], values=(
                row['username'], name or na_text, row.get('job_title') or na_text,
                row.get('department') or na_text, row.get('email') or na_text,
                row.get('phone_extension') or na_text, row.get('manager_id') or na_text))
        self.team_summary.config(text=_t("staff_profile.team.summary", default="{count} people",
                                         count=len(team)))

    def _selected_team_member(self):
        selection = self.team_tree.selection()
        if not selection:
            messagebox.showwarning(_t("staff_profile.common.warning", default="Warning"),
                                   _t("staff_profile.staff_directory.select_person", default="Please select a member of staff"))
            return None
        return selection[0]

    def _view_team_member(self):
        username = self._selected_team_member()
        if not username:
            return
        # Reuse the directory card.
        if username not in self.dir_tree.get_children():
            self.dir_search_var.set('')
            self.dir_dept_var.set(_t("staff_profile.staff_directory.all_departments", default="All"))
            self._search_directory()
        if username in self.dir_tree.get_children():
            self.dir_tree.selection_set(username)
            self._view_staff_details(None)

    def _read_only_list(self, title, columns, rows):
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry("700x350")
        dialog.transient(self.root)
        tree = ttk.Treeview(dialog, columns=columns, show='headings', height=12)
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=110)
        for row in rows:
            tree.insert('', 'end', values=row)
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        ttk.Button(dialog, text=_t("staff_profile.close", default="Close"), command=dialog.destroy).pack(pady=(0, 10))

    def _view_team_schedule(self):
        username = self._selected_team_member()
        if not username:
            return
        try:
            rows = EmployeeManager.get_schedules(username, actor=self._actor())
        except Exception as e:
            self._error(str(e))
            return
        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        self._read_only_list(
            _t("staff_profile.team.schedule_title", default="Schedule - {username}", username=username),
            ('Day', 'Start', 'End', 'Location', 'Type'),
            [(days[r['day_of_week']] if isinstance(r.get('day_of_week'), int) and 0 <= r['day_of_week'] < 7 else '',
              r.get('start_time') or '', r.get('end_time') or '', r.get('location') or '',
              r.get('schedule_type') or '') for r in rows])

    def _view_team_workload(self):
        username = self._selected_team_member()
        if not username:
            return
        try:
            rows = EmployeeManager.get_workload(username, actor=self._actor())
        except Exception as e:
            self._error(str(e))
            return
        self._read_only_list(
            _t("staff_profile.team.workload_title", default="Workload - {username}", username=username),
            ('Year', 'Semester', 'Teaching', 'Research', 'Admin', 'Service', 'FTE'),
            [(r.get('academic_year') or '', r.get('semester') or '', r.get('teaching_hours') or 0,
              r.get('research_hours') or 0, r.get('admin_hours') or 0, r.get('service_hours') or 0,
              r.get('total_fte') or '') for r in rows])
