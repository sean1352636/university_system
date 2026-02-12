"""
Staff Profile Management GUI

Features:
- My Profile - View/edit personal profile information
- Staff Directory - Search and browse staff members
- Documents - Manage employment documents
- Workload - View and manage workload allocation
- Schedules - Manage work schedules
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Optional
from datetime import datetime
import json

from university_system.infrastructure.database.db import get_connection, transaction
from university_system.infrastructure.auth import UserAuth
from university_system.modules.shared.utils.activity_logger import log_activity
from university_system.infrastructure.localization import get_translation

# Translation helper
_t = get_translation

try:
    from university_system.infrastructure.database.schemas.staff_hr_schemas_v2 import (
        init_staff_hr_v2_schemas, get_departments, get_employment_types
    )
except ImportError:
    init_staff_hr_v2_schemas = None
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

        # Initialize schemas
        try:
            if init_staff_hr_v2_schemas:
                init_staff_hr_v2_schemas()
        except Exception as e:
            print(f"Warning: Could not initialize Staff HR v2 schemas: {e}")

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
        self.window.geometry("1200x800")
        self.window.minsize(1000, 600)

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
        ttk.Entry(personal_frame, textvariable=self.employee_id_var, width=30).grid(row=row, column=1, sticky=tk.W, pady=2)

        row += 1
        ttk.Label(personal_frame, text=_t("staff_profile.my_profile.labels.job_title", default="Job Title:")).grid(row=row, column=0, sticky=tk.W, pady=2)
        self.job_title_var = tk.StringVar()
        ttk.Entry(personal_frame, textvariable=self.job_title_var, width=40).grid(row=row, column=1, sticky=tk.W, pady=2)

        row += 1
        ttk.Label(personal_frame, text=_t("staff_profile.my_profile.labels.department", default="Department:")).grid(row=row, column=0, sticky=tk.W, pady=2)
        self.department_var = tk.StringVar()
        dept_combo = ttk.Combobox(personal_frame, textvariable=self.department_var, values=get_departments(), width=37)
        dept_combo.grid(row=row, column=1, sticky=tk.W, pady=2)

        row += 1
        ttk.Label(personal_frame, text=_t("staff_profile.my_profile.labels.employment_type", default="Employment Type:")).grid(row=row, column=0, sticky=tk.W, pady=2)
        self.employment_type_var = tk.StringVar()
        type_combo = ttk.Combobox(personal_frame, textvariable=self.employment_type_var, values=get_employment_types(), width=37)
        type_combo.grid(row=row, column=1, sticky=tk.W, pady=2)

        row += 1
        ttk.Label(personal_frame, text=_t("staff_profile.my_profile.labels.hire_date", default="Hire Date:")).grid(row=row, column=0, sticky=tk.W, pady=2)
        self.hire_date_var = tk.StringVar()
        ttk.Entry(personal_frame, textvariable=self.hire_date_var, width=15).grid(row=row, column=1, sticky=tk.W, pady=2)
        ttk.Label(personal_frame, text=_t("staff_profile.my_profile.labels.hire_date_format", default="(YYYY-MM-DD)")).grid(row=row, column=2, sticky=tk.W, pady=2)

        row += 1
        ttk.Label(personal_frame, text=_t("staff_profile.my_profile.labels.office_location", default="Office Location:")).grid(row=row, column=0, sticky=tk.W, pady=2)
        self.office_var = tk.StringVar()
        ttk.Entry(personal_frame, textvariable=self.office_var, width=40).grid(row=row, column=1, sticky=tk.W, pady=2)

        row += 1
        ttk.Label(personal_frame, text=_t("staff_profile.my_profile.labels.phone_extension", default="Phone Extension:")).grid(row=row, column=0, sticky=tk.W, pady=2)
        self.phone_ext_var = tk.StringVar()
        ttk.Entry(personal_frame, textvariable=self.phone_ext_var, width=15).grid(row=row, column=1, sticky=tk.W, pady=2)

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
        user_id = self.current_user.get('id') or self.current_user.get('username')

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT employee_id, job_title, department, employment_type,
                           hire_date, office_location, phone_extension,
                           emergency_contact_name, emergency_contact_phone,
                           emergency_contact_relationship, bio, expertise_areas,
                           qualifications
                    FROM staff_profiles WHERE user_id = ?
                ''', (user_id,))
                row = cursor.fetchone()

                if row:
                    self.employee_id_var.set(row[0] or '')
                    self.job_title_var.set(row[1] or '')
                    self.department_var.set(row[2] or '')
                    self.employment_type_var.set(row[3] or '')
                    self.hire_date_var.set(row[4] or '')
                    self.office_var.set(row[5] or '')
                    self.phone_ext_var.set(row[6] or '')
                    self.emergency_name_var.set(row[7] or '')
                    self.emergency_phone_var.set(row[8] or '')
                    self.emergency_rel_var.set(row[9] or '')
                    self.bio_text.delete('1.0', tk.END)
                    self.bio_text.insert('1.0', row[10] or '')
                    self.expertise_var.set(row[11] or '')
                    self.qualifications_var.set(row[12] or '')
        except Exception as e:
            print(f"Error loading profile: {e}")

    def _save_profile(self):
        """Save profile changes."""
        user_id = self.current_user.get('id') or self.current_user.get('username')

        try:
            with transaction() as conn:
                cursor = conn.cursor()

                # Check if profile exists
                cursor.execute('SELECT profile_id FROM staff_profiles WHERE user_id = ?', (user_id,))
                exists = cursor.fetchone()

                bio = self.bio_text.get('1.0', tk.END).strip()

                if exists:
                    cursor.execute('''
                        UPDATE staff_profiles SET
                            employee_id = ?, job_title = ?, department = ?,
                            employment_type = ?, hire_date = ?, office_location = ?,
                            phone_extension = ?, emergency_contact_name = ?,
                            emergency_contact_phone = ?, emergency_contact_relationship = ?,
                            bio = ?, expertise_areas = ?, qualifications = ?,
                            updated_at = ?
                        WHERE user_id = ?
                    ''', (
                        self.employee_id_var.get(), self.job_title_var.get(),
                        self.department_var.get(), self.employment_type_var.get(),
                        self.hire_date_var.get(), self.office_var.get(),
                        self.phone_ext_var.get(), self.emergency_name_var.get(),
                        self.emergency_phone_var.get(), self.emergency_rel_var.get(),
                        bio, self.expertise_var.get(), self.qualifications_var.get(),
                        datetime.now().isoformat(), user_id
                    ))
                else:
                    cursor.execute('''
                        INSERT INTO staff_profiles (
                            user_id, employee_id, job_title, department,
                            employment_type, hire_date, office_location,
                            phone_extension, emergency_contact_name,
                            emergency_contact_phone, emergency_contact_relationship,
                            bio, expertise_areas, qualifications
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        user_id, self.employee_id_var.get(), self.job_title_var.get(),
                        self.department_var.get(), self.employment_type_var.get(),
                        self.hire_date_var.get(), self.office_var.get(),
                        self.phone_ext_var.get(), self.emergency_name_var.get(),
                        self.emergency_phone_var.get(), self.emergency_rel_var.get(),
                        bio, self.expertise_var.get(), self.qualifications_var.get()
                    ))

                conn.commit()
                log_activity('update', 'staff_profile', user_id=user_id)
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
            with get_connection() as conn:
                cursor = conn.cursor()

                query = '''
                    SELECT u.username, sp.job_title, sp.department, u.email,
                           sp.phone_extension, sp.office_location
                    FROM users u
                    LEFT JOIN staff_profiles sp ON u.username = sp.user_id OR u.user_id = sp.user_id
                    WHERE u.role IN ('admin', 'staff', 'instructor')
                '''
                params = []

                if dept != all_text:
                    query += ' AND sp.department = ?'
                    params.append(dept)

                if search:
                    query += ''' AND (
                        LOWER(u.username) LIKE ? OR
                        LOWER(sp.job_title) LIKE ? OR
                        LOWER(u.email) LIKE ? OR
                        LOWER(sp.expertise_areas) LIKE ?
                    )'''
                    search_pattern = f'%{search}%'
                    params.extend([search_pattern] * 4)

                query += ' ORDER BY u.username'
                cursor.execute(query, params)

                for row in cursor.fetchall():
                    self.dir_tree.insert('', 'end', values=(
                        row[0] or na_text,
                        row[1] or na_text,
                        row[2] or na_text,
                        row[3] or na_text,
                        row[4] or na_text,
                        row[5] or na_text
                    ))
        except Exception as e:
            print(f"Error searching directory: {e}")

    def _view_staff_details(self, event):
        """View detailed staff profile."""
        selection = self.dir_tree.selection()
        if not selection:
            return

        item = self.dir_tree.item(selection[0])
        username = item['values'][0]
        na_text = _t("staff_profile.staff_directory.na", default="N/A")

        # Create details dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("staff_profile.staff_directory.profile_window.title", default="Staff Profile - {username}", username=username))
        dialog.geometry("500x400")
        dialog.transient(self.root)

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT sp.*, u.email, u.first_name, u.last_name
                    FROM staff_profiles sp
                    LEFT JOIN users u ON sp.user_id = u.username OR sp.user_id = CAST(u.user_id AS TEXT)
                    WHERE sp.user_id = ?
                ''', (username,))
                row = cursor.fetchone()

                if row:
                    info_text = tk.Text(dialog, wrap=tk.WORD, padx=10, pady=10)
                    info_text.pack(fill=tk.BOTH, expand=True)

                    info_text.insert(tk.END, _t("staff_profile.staff_directory.profile_window.name", default="Name: {name}", name=username) + "\n")
                    info_text.insert(tk.END, _t("staff_profile.staff_directory.profile_window.job_title", default="Job Title: {title}", title=row[4] or na_text) + "\n")
                    info_text.insert(tk.END, _t("staff_profile.staff_directory.profile_window.department", default="Department: {dept}", dept=row[3] or na_text) + "\n")
                    info_text.insert(tk.END, _t("staff_profile.staff_directory.profile_window.employment_type", default="Employment Type: {type}", type=row[5] or na_text) + "\n")
                    info_text.insert(tk.END, _t("staff_profile.staff_directory.profile_window.office", default="Office: {office}", office=row[9] or na_text) + "\n")
                    info_text.insert(tk.END, _t("staff_profile.staff_directory.profile_window.phone", default="Phone: {phone}", phone=row[10] or na_text) + "\n\n")
                    info_text.insert(tk.END, _t("staff_profile.staff_directory.profile_window.bio", default="Bio:\n{bio}", bio=row[15] or na_text) + "\n\n")
                    info_text.insert(tk.END, _t("staff_profile.staff_directory.profile_window.expertise", default="Expertise: {expertise}", expertise=row[16] or na_text) + "\n")
                    info_text.insert(tk.END, _t("staff_profile.staff_directory.profile_window.qualifications", default="Qualifications: {quals}", quals=row[17] or na_text) + "\n")

                    info_text.config(state=tk.DISABLED)
                else:
                    ttk.Label(dialog, text=_t("staff_profile.staff_directory.no_profile", default="No profile found")).pack(pady=20)
        except Exception as e:
            ttk.Label(dialog, text=_t("staff_profile.staff_directory.errors.profile_error", default="Error loading profile: {error}", error=str(e))).pack(pady=20)

        ttk.Button(dialog, text=_t("staff_profile.staff_directory.profile_window.close", default="Close"), command=dialog.destroy).pack(pady=10)

    # ================================================================
    # DOCUMENTS TAB
    # ================================================================

    def _create_documents_tab(self):
        """Create Documents tab for managing employment documents."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("staff_profile.tabs.documents", default="Documents"))

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

    def _load_documents(self):
        """Load user's documents."""
        user_id = self.current_user.get('id') or self.current_user.get('username')
        self.docs_tree.delete(*self.docs_tree.get_children())

        na_text = _t("staff_profile.documents.na", default="N/A")
        other_text = _t("staff_profile.documents.other", default="Other")
        unknown_text = _t("staff_profile.documents.unknown", default="Unknown")
        active_text = _t("staff_profile.documents.status.active", default="active")
        expired_text = _t("staff_profile.documents.status.expired", default="expired")

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT document_id, document_type, document_name,
                           issue_date, expiry_date, status
                    FROM staff_documents
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                ''', (user_id,))

                today = datetime.now().date()
                for row in cursor.fetchall():
                    status = row[5] or active_text
                    tag = 'active'

                    if row[4]:  # Has expiry date
                        try:
                            expiry = datetime.strptime(row[4], '%Y-%m-%d').date()
                            if expiry < today:
                                status = expired_text
                                tag = 'expired'
                            elif (expiry - today).days <= 30:
                                tag = 'expiring'
                        except (ValueError, TypeError):
                            pass

                    self.docs_tree.insert('', 'end', values=(
                        row[0], row[1] or other_text, row[2] or unknown_text,
                        row[3] or na_text, row[4] or na_text, status
                    ), tags=(tag,))
        except Exception as e:
            print(f"Error loading documents: {e}")

    def _upload_document(self):
        """Upload a new document."""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("staff_profile.documents.upload_dialog.title", default="Upload Document"))
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
            user_id = self.current_user.get('id') or self.current_user.get('username')
            try:
                with transaction() as conn:
                    conn.execute('''
                        INSERT INTO staff_documents (user_id, document_type, document_name,
                                                     file_path, issue_date, expiry_date, uploaded_by)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (user_id, type_var.get(), name_var.get(), file_path_var.get(),
                          issue_var.get() or None, expiry_var.get() or None, user_id))
                    conn.commit()

                log_activity('create', 'staff_document', user_id=user_id)
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
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT file_path FROM staff_documents WHERE document_id = ?', (doc_id,))
                row = cursor.fetchone()
                if row and row[0]:
                    import os
                    if os.path.exists(row[0]):
                        if os.name == 'nt':
                            os.startfile(row[0])
                        else:
                            import subprocess
                            subprocess.run(['xdg-open', row[0]], check=False)
                    else:
                        messagebox.showinfo(_t("staff_profile.common.info", default="Info"),
                                          _t("staff_profile.documents.messages.file_path", default="File path: {path}\n\nFile not found on disk.", path=row[0]))
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
            with transaction() as conn:
                conn.execute('DELETE FROM staff_documents WHERE document_id = ?', (doc_id,))
                conn.commit()

            user_id = self.current_user.get('id') or self.current_user.get('username')
            log_activity('delete', 'staff_document', user_id=user_id, details={'document_id': doc_id})
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

        ttk.Label(filter_frame, text=_t("staff_profile.workload.filter_label", default="Academic Year:")).pack(side=tk.LEFT, padx=5)
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
        """Load workload data."""
        user_id = self.current_user.get('id') or self.current_user.get('username')
        year = self.workload_year_var.get()

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT teaching_hours, research_hours, admin_hours,
                           service_hours, total_fte, notes
                    FROM staff_workload
                    WHERE user_id = ? AND academic_year = ?
                ''', (user_id, year))
                row = cursor.fetchone()

                if row:
                    self.teaching_hours_var.set(str(row[0] or 0))
                    self.research_hours_var.set(str(row[1] or 0))
                    self.admin_hours_var.set(str(row[2] or 0))
                    self.service_hours_var.set(str(row[3] or 0))
                    self.fte_var.set(str(row[4] or 1.0))
                    self.workload_notes.delete('1.0', tk.END)
                    self.workload_notes.insert('1.0', row[5] or '')
                else:
                    self.teaching_hours_var.set("0")
                    self.research_hours_var.set("0")
                    self.admin_hours_var.set("0")
                    self.service_hours_var.set("0")
                    self.fte_var.set("1.0")
                    self.workload_notes.delete('1.0', tk.END)

                self._update_workload_summary()
        except Exception as e:
            print(f"Error loading workload: {e}")

    def _save_workload(self):
        """Save workload data."""
        user_id = self.current_user.get('id') or self.current_user.get('username')
        year = self.workload_year_var.get()

        try:
            with transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT workload_id FROM staff_workload WHERE user_id = ? AND academic_year = ?',
                               (user_id, year))
                exists = cursor.fetchone()

                notes = self.workload_notes.get('1.0', tk.END).strip()

                if exists:
                    cursor.execute('''
                        UPDATE staff_workload SET
                            teaching_hours = ?, research_hours = ?, admin_hours = ?,
                            service_hours = ?, total_fte = ?, notes = ?, updated_at = ?
                        WHERE user_id = ? AND academic_year = ?
                    ''', (
                        float(self.teaching_hours_var.get() or 0),
                        float(self.research_hours_var.get() or 0),
                        float(self.admin_hours_var.get() or 0),
                        float(self.service_hours_var.get() or 0),
                        float(self.fte_var.get() or 1.0),
                        notes, datetime.now().isoformat(), user_id, year
                    ))
                else:
                    cursor.execute('''
                        INSERT INTO staff_workload (user_id, academic_year, teaching_hours,
                                                    research_hours, admin_hours, service_hours,
                                                    total_fte, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        user_id, year,
                        float(self.teaching_hours_var.get() or 0),
                        float(self.research_hours_var.get() or 0),
                        float(self.admin_hours_var.get() or 0),
                        float(self.service_hours_var.get() or 0),
                        float(self.fte_var.get() or 1.0), notes
                    ))

                conn.commit()
                log_activity('update', 'staff_workload', user_id=user_id)
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
        user_id = self.current_user.get('id') or self.current_user.get('username')
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
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT schedule_id, day_of_week, start_time, end_time,
                           location, schedule_type, is_recurring
                    FROM staff_schedules
                    WHERE user_id = ?
                    ORDER BY day_of_week, start_time
                ''', (user_id,))

                for row in cursor.fetchall():
                    day_name = days[row[1]] if row[1] is not None and 0 <= row[1] < 7 else na_text
                    self.schedules_tree.insert('', 'end', values=(
                        row[0], day_name, row[2] or na_text, row[3] or na_text,
                        row[4] or na_text, row[5] or na_text,
                        yes_text if row[6] else no_text
                    ))
        except Exception as e:
            print(f"Error loading schedules: {e}")

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
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT day_of_week, start_time, end_time, location,
                               schedule_type, is_recurring
                        FROM staff_schedules WHERE schedule_id = ?
                    ''', (schedule_id,))
                    row = cursor.fetchone()
                    if row:
                        day_var.set(days[row[0]] if row[0] is not None else '')
                        start_var.set(row[1] or '')
                        end_var.set(row[2] or '')
                        location_var.set(row[3] or '')
                        type_var.set(row[4] or '')
                        recurring_var.set(bool(row[5]))
            except Exception as e:
                print(f"Error loading schedule: {e}")

        def save():
            user_id = self.current_user.get('id') or self.current_user.get('username')
            day_idx = days.index(day_var.get()) if day_var.get() in days else 0

            try:
                with transaction() as conn:
                    if schedule_id:
                        conn.execute('''
                            UPDATE staff_schedules SET
                                day_of_week = ?, start_time = ?, end_time = ?,
                                location = ?, schedule_type = ?, is_recurring = ?
                            WHERE schedule_id = ?
                        ''', (day_idx, start_var.get(), end_var.get(),
                              location_var.get(), type_var.get(), 1 if recurring_var.get() else 0,
                              schedule_id))
                    else:
                        conn.execute('''
                            INSERT INTO staff_schedules (user_id, day_of_week, start_time,
                                                         end_time, location, schedule_type, is_recurring)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (user_id, day_idx, start_var.get(), end_var.get(),
                              location_var.get(), type_var.get(), 1 if recurring_var.get() else 0))
                    conn.commit()

                log_activity('update' if schedule_id else 'create', 'staff_schedule', user_id=user_id)
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
            with transaction() as conn:
                conn.execute('DELETE FROM staff_schedules WHERE schedule_id = ?', (schedule_id,))
                conn.commit()

            user_id = self.current_user.get('id') or self.current_user.get('username')
            log_activity('delete', 'staff_schedule', user_id=user_id)
            messagebox.showinfo(_t("staff_profile.common.success", default="Success"),
                              _t("staff_profile.schedules.messages.delete_success", default="Schedule deleted successfully"))
            self._load_schedules()
        except Exception as e:
            messagebox.showerror(_t("staff_profile.common.error", default="Error"),
                               _t("staff_profile.schedules.messages.delete_error", default="Failed to delete schedule: {error}", error=str(e)))
