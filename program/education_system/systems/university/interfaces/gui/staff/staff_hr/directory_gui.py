"""
Staff Directory GUI

Provides interface for:
- Staff search and directory browsing
- Department listings
- Profile and expertise management
- Office hours management
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from typing import Optional

from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.domain.staff.staff_hr.services.managers.directory_manager import DirectoryManager
from education_system.systems.university.interfaces.gui.staff.staff_hr.validators import (
    FormValidator, ValidationError, validate_entry, validate_combobox,
    show_validation_error
)


# Day-of-week mapping used throughout the module
DAY_NAMES = {
    "0": "Monday",
    "1": "Tuesday",
    "2": "Wednesday",
    "3": "Thursday",
    "4": "Friday",
    "5": "Saturday",
    "6": "Sunday",
}


class DirectoryGUI:
    """GUI for staff directory."""

    def __init__(self, root, auth: Optional[UserAuth] = None, parent_notebook: Optional[ttk.Notebook] = None):
        self.root = root
        self.auth = auth
        self.current_user = auth.current_user if auth and auth.current_user else None
        self.parent_notebook = parent_notebook
        self.window = None

        if not self.current_user:
            messagebox.showerror("Error", "Login required to access Staff Directory")
            return

        if parent_notebook:
            self.create_as_tab(parent_notebook)
        else:
            self.create_main_window()

    def _get_user_id(self):
        return self.current_user.get('id') or self.current_user.get('username')

    def create_as_tab(self, notebook: ttk.Notebook):
        self.tab_frame = ttk.Frame(notebook)
        notebook.add(self.tab_frame, text="Directory")
        self._build_interface(self.tab_frame)

    def create_main_window(self):
        self.window = tk.Toplevel(self.root)
        self.window.title("Staff Directory")
        self.window.geometry("1200x700")
        self.window.minsize(1000, 600)
        bottom_frame = ttk.Frame(self.window)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)
        ttk.Button(bottom_frame, text="Close", command=self.window.destroy).pack(side=tk.RIGHT, padx=5)
        self.status_bar = ttk.Label(self.window, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        self._build_interface(self.window)

    def _build_interface(self, parent):
        style = ttk.Style()
        style.configure('Header.TLabel', font=('Arial', 14, 'bold'))
        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self._create_search_tab()
        self._create_department_tab()
        self._create_my_profile_tab()
        self._create_expertise_search_tab()

    # ------------------------------------------------------------------
    # Helper: open a staff profile dialog (reused by Tab 1 and Tab 4)
    # ------------------------------------------------------------------

    def _open_profile_dialog(self, user_id: str):
        """Open a Toplevel dialog showing the full profile for *user_id*."""
        try:
            full = DirectoryManager.get_full_profile(user_id)
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to load profile: {exc}")
            return

        profile = full.get('profile')
        expertise_list = full.get('expertise', [])
        office_hours_list = full.get('office_hours', [])

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Staff Profile - {user_id}")
        dialog.geometry("620x560")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # -- Profile information --
        info_frame = ttk.LabelFrame(main_frame, text="Profile Information", padding=10)
        info_frame.pack(fill=tk.X, pady=(0, 8))

        if profile:
            fields = [
                ("User ID:", profile.get('user_id', '')),
                ("First Name:", profile.get('first_name', '')),
                ("Last Name:", profile.get('last_name', '')),
                ("Email:", profile.get('email', '')),
                ("Phone:", profile.get('phone', '')),
                ("Department:", profile.get('department', '')),
                ("Position:", profile.get('position', '')),
                ("Office:", profile.get('office', '')),
            ]
            for i, (label, value) in enumerate(fields):
                ttk.Label(info_frame, text=label, font=('Arial', 10, 'bold')).grid(
                    row=i // 2, column=(i % 2) * 2, sticky='e', padx=5, pady=2)
                ttk.Label(info_frame, text=str(value) if value else "-").grid(
                    row=i // 2, column=(i % 2) * 2 + 1, sticky='w', padx=5, pady=2)
        else:
            ttk.Label(info_frame, text="No profile found for this user.").pack(anchor=tk.W)

        # -- Expertise areas --
        exp_frame = ttk.LabelFrame(main_frame, text="Expertise Areas", padding=10)
        exp_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        if expertise_list:
            exp_columns = ("Area", "Category", "Proficiency", "Keywords")
            exp_tree = ttk.Treeview(exp_frame, columns=exp_columns, show='headings', height=4)
            for col in exp_columns:
                exp_tree.heading(col, text=col)
                exp_tree.column(col, width=130)
            for exp in expertise_list:
                exp_tree.insert('', 'end', values=(
                    exp.get('expertise_area', ''),
                    exp.get('category', ''),
                    exp.get('proficiency', ''),
                    exp.get('keywords', '') or '',
                ))
            exp_tree.pack(fill=tk.BOTH, expand=True)
        else:
            ttk.Label(exp_frame, text="No expertise areas listed.").pack(anchor=tk.W)

        # -- Office hours --
        hours_frame = ttk.LabelFrame(main_frame, text="Office Hours", padding=10)
        hours_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        if office_hours_list:
            oh_columns = ("Day", "Time", "Location")
            oh_tree = ttk.Treeview(hours_frame, columns=oh_columns, show='headings', height=4)
            for col in oh_columns:
                oh_tree.heading(col, text=col)
                oh_tree.column(col, width=160)
            for oh in office_hours_list:
                day_value = str(oh.get('day_of_week', ''))
                day_display = DAY_NAMES.get(day_value, day_value)
                start = oh.get('start_time', '')
                end = oh.get('end_time', '')
                time_range = f"{start} - {end}" if start and end else start or end or "-"
                location = oh.get('location', '') or oh.get('virtual_link', '') or "-"
                oh_tree.insert('', 'end', values=(day_display, time_range, location))
            oh_tree.pack(fill=tk.BOTH, expand=True)
        else:
            ttk.Label(hours_frame, text="No office hours listed.").pack(anchor=tk.W)

        # -- Close button --
        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=(8, 0))

    # ==================================================================
    # Tab 1 -- Search Directory
    # ==================================================================

    def _create_search_tab(self):
        """Create the Search Directory tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Search Directory")

        # -- Header --
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Search Staff Directory", style='Header.TLabel').pack(side=tk.LEFT)

        # -- Search bar --
        search_frame = ttk.LabelFrame(tab, text="Search", padding=10)
        search_frame.pack(fill=tk.X, padx=10, pady=(0, 5))

        ttk.Label(search_frame, text="Name / Email:").pack(side=tk.LEFT, padx=(0, 5))
        self.search_query_entry = ttk.Entry(search_frame, width=30)
        self.search_query_entry.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(search_frame, text="Department:").pack(side=tk.LEFT, padx=(0, 5))
        self.search_dept_entry = ttk.Entry(search_frame, width=20)
        self.search_dept_entry.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(search_frame, text="Search", command=self._do_search_directory).pack(side=tk.LEFT, padx=5)

        # Bind Enter key
        self.search_query_entry.bind('<Return>', lambda e: self._do_search_directory())
        self.search_dept_entry.bind('<Return>', lambda e: self._do_search_directory())

        # -- Results Treeview --
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)

        columns = ("User ID", "First Name", "Last Name", "Email", "Department", "Position")
        self.search_tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                                         yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.search_tree.yview)

        col_widths = {
            "User ID": 90, "First Name": 120, "Last Name": 120,
            "Email": 200, "Department": 140, "Position": 140,
        }
        for col in columns:
            self.search_tree.heading(col, text=col)
            self.search_tree.column(col, width=col_widths.get(col, 100))

        self.search_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Double-click opens profile
        self.search_tree.bind('<Double-1>', self._on_search_tree_double_click)

    def _do_search_directory(self):
        """Execute a directory search and populate the results tree."""
        query = self.search_query_entry.get().strip() or None
        department = self.search_dept_entry.get().strip() or None

        try:
            results = DirectoryManager.search_directory(query=query, department=department)
        except Exception as exc:
            messagebox.showerror("Error", f"Search failed: {exc}")
            return

        self.search_tree.delete(*self.search_tree.get_children())
        for row in results:
            self.search_tree.insert('', 'end', values=(
                row.get('user_id', ''),
                row.get('first_name', ''),
                row.get('last_name', ''),
                row.get('email', ''),
                row.get('department', ''),
                row.get('position', ''),
            ))

    def _on_search_tree_double_click(self, event=None):
        """Handle double-click on a search result row."""
        selection = self.search_tree.selection()
        if not selection:
            return
        item = self.search_tree.item(selection[0])
        user_id = item['values'][0]
        if user_id:
            self._open_profile_dialog(str(user_id))

    # ==================================================================
    # Tab 2 -- Department Browse
    # ==================================================================

    def _create_department_tab(self):
        """Create the Department Browse tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Department Browse")

        # -- Header --
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Browse by Department", style='Header.TLabel').pack(side=tk.LEFT)

        # -- Department entry and button --
        dept_frame = ttk.LabelFrame(tab, text="Department", padding=10)
        dept_frame.pack(fill=tk.X, padx=10, pady=(0, 5))

        ttk.Label(dept_frame, text="Department:").pack(side=tk.LEFT, padx=(0, 5))
        self.dept_browse_entry = ttk.Entry(dept_frame, width=30)
        self.dept_browse_entry.pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(dept_frame, text="Browse", command=self._do_browse_department).pack(side=tk.LEFT, padx=5)

        self.dept_browse_entry.bind('<Return>', lambda e: self._do_browse_department())

        # -- Staff listing Treeview --
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)

        columns = ("User ID", "First Name", "Last Name", "Position", "Email", "Phone")
        self.dept_tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                                       yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.dept_tree.yview)

        col_widths = {
            "User ID": 90, "First Name": 120, "Last Name": 120,
            "Position": 140, "Email": 200, "Phone": 120,
        }
        for col in columns:
            self.dept_tree.heading(col, text=col)
            self.dept_tree.column(col, width=col_widths.get(col, 100))

        self.dept_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def _do_browse_department(self):
        """Load staff for the entered department."""
        department = self.dept_browse_entry.get().strip()
        if not department:
            messagebox.showwarning("Warning", "Please enter a department name.")
            return

        try:
            results = DirectoryManager.get_department_staff(department)
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to load department staff: {exc}")
            return

        self.dept_tree.delete(*self.dept_tree.get_children())
        for row in results:
            self.dept_tree.insert('', 'end', values=(
                row.get('user_id', ''),
                row.get('first_name', ''),
                row.get('last_name', ''),
                row.get('position', ''),
                row.get('email', ''),
                row.get('phone', ''),
            ))

    # ==================================================================
    # Tab 3 -- My Profile
    # ==================================================================

    def _create_my_profile_tab(self):
        """Create the My Profile tab with expertise and office-hours management."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="My Profile")

        # Scrollable canvas so everything fits
        canvas = tk.Canvas(tab, highlightthickness=0)
        v_scroll = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)

        scroll_frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=scroll_frame, anchor='nw')
        canvas.configure(yscrollcommand=v_scroll.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # ---- Profile information ----
        profile_frame = ttk.LabelFrame(scroll_frame, text="My Profile", padding=10)
        profile_frame.pack(fill=tk.X, padx=10, pady=10)

        self.profile_labels = {}
        profile_fields = ["Name", "Email", "Phone", "Department", "Position", "Office"]
        for i, field in enumerate(profile_fields):
            ttk.Label(profile_frame, text=f"{field}:", font=('Arial', 10, 'bold')).grid(
                row=i // 2, column=(i % 2) * 2, sticky='e', padx=5, pady=3)
            lbl = ttk.Label(profile_frame, text="-")
            lbl.grid(row=i // 2, column=(i % 2) * 2 + 1, sticky='w', padx=5, pady=3)
            self.profile_labels[field] = lbl

        # ---- Expertise Management ----
        exp_frame = ttk.LabelFrame(scroll_frame, text="Expertise Management", padding=10)
        exp_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        exp_btn_frame = ttk.Frame(exp_frame)
        exp_btn_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Button(exp_btn_frame, text="Add Expertise", command=self._add_expertise_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(exp_btn_frame, text="Remove Selected", command=self._remove_selected_expertise).pack(side=tk.LEFT, padx=5)

        exp_tree_frame = ttk.Frame(exp_frame)
        exp_tree_frame.pack(fill=tk.BOTH, expand=True)

        exp_scroll = ttk.Scrollbar(exp_tree_frame, orient=tk.VERTICAL)

        exp_columns = ("ID", "Area", "Category", "Proficiency", "Keywords")
        self.my_expertise_tree = ttk.Treeview(exp_tree_frame, columns=exp_columns,
                                               show='headings', height=5,
                                               yscrollcommand=exp_scroll.set)
        exp_scroll.config(command=self.my_expertise_tree.yview)

        exp_col_widths = {"ID": 50, "Area": 180, "Category": 120, "Proficiency": 110, "Keywords": 200}
        for col in exp_columns:
            self.my_expertise_tree.heading(col, text=col)
            self.my_expertise_tree.column(col, width=exp_col_widths.get(col, 100))

        self.my_expertise_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        exp_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # ---- Office Hours Management ----
        hours_frame = ttk.LabelFrame(scroll_frame, text="Office Hours Management", padding=10)
        hours_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        hours_btn_frame = ttk.Frame(hours_frame)
        hours_btn_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Button(hours_btn_frame, text="Add Hours", command=self._add_hours_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(hours_btn_frame, text="Remove Selected", command=self._remove_selected_hours).pack(side=tk.LEFT, padx=5)

        hours_tree_frame = ttk.Frame(hours_frame)
        hours_tree_frame.pack(fill=tk.BOTH, expand=True)

        hours_scroll = ttk.Scrollbar(hours_tree_frame, orient=tk.VERTICAL)

        hours_columns = ("ID", "Day", "Start", "End", "Location", "By Appointment")
        self.my_hours_tree = ttk.Treeview(hours_tree_frame, columns=hours_columns,
                                           show='headings', height=5,
                                           yscrollcommand=hours_scroll.set)
        hours_scroll.config(command=self.my_hours_tree.yview)

        hours_col_widths = {"ID": 50, "Day": 100, "Start": 80, "End": 80, "Location": 180, "By Appointment": 110}
        for col in hours_columns:
            self.my_hours_tree.heading(col, text=col)
            self.my_hours_tree.column(col, width=hours_col_widths.get(col, 100))

        self.my_hours_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        hours_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Load data
        self._load_my_profile()

    # ---- My Profile: data loading ----

    def _load_my_profile(self):
        """Refresh the My Profile tab with current data."""
        user_id = self._get_user_id()

        # Profile info
        try:
            profile = DirectoryManager.get_staff_profile(user_id)
        except Exception:
            profile = None

        if profile:
            first = profile.get('first_name', '')
            last = profile.get('last_name', '')
            self.profile_labels["Name"].config(text=f"{first} {last}".strip() or "-")
            self.profile_labels["Email"].config(text=profile.get('email', '') or "-")
            self.profile_labels["Phone"].config(text=profile.get('phone', '') or "-")
            self.profile_labels["Department"].config(text=profile.get('department', '') or "-")
            self.profile_labels["Position"].config(text=profile.get('position', '') or "-")
            self.profile_labels["Office"].config(text=profile.get('office', '') or "-")
        else:
            for lbl in self.profile_labels.values():
                lbl.config(text="-")

        # Expertise
        self._load_my_expertise()

        # Office hours
        self._load_my_hours()

    def _load_my_expertise(self):
        """Reload the current user's expertise into the treeview."""
        self.my_expertise_tree.delete(*self.my_expertise_tree.get_children())
        user_id = self._get_user_id()
        try:
            items = DirectoryManager.get_expertise(user_id)
        except Exception:
            items = []
        for exp in items:
            self.my_expertise_tree.insert('', 'end', values=(
                exp.get('expertise_id', ''),
                exp.get('expertise_area', ''),
                exp.get('category', ''),
                exp.get('proficiency', ''),
                exp.get('keywords', '') or '',
            ))

    def _load_my_hours(self):
        """Reload the current user's office hours into the treeview."""
        self.my_hours_tree.delete(*self.my_hours_tree.get_children())
        user_id = self._get_user_id()
        try:
            items = DirectoryManager.get_office_hours(user_id)
        except Exception:
            items = []
        for oh in items:
            day_value = str(oh.get('day_of_week', ''))
            day_display = DAY_NAMES.get(day_value, day_value)
            by_appt = "Yes" if oh.get('is_by_appointment') else "No"
            self.my_hours_tree.insert('', 'end', values=(
                oh.get('hours_id', ''),
                day_display,
                oh.get('start_time', ''),
                oh.get('end_time', ''),
                oh.get('location', '') or '',
                by_appt,
            ))

    # ---- My Profile: expertise dialogs ----

    def _add_expertise_dialog(self):
        """Open a dialog to add a new expertise area."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Expertise")
        dialog.geometry("420x300")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Add Expertise Area", font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        fields = {}

        # Area
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text="Expertise Area:", width=16, anchor=tk.W).pack(side=tk.LEFT)
        fields['area'] = ttk.Entry(row, width=28)
        fields['area'].pack(side=tk.LEFT)

        # Category
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text="Category:", width=16, anchor=tk.W).pack(side=tk.LEFT)
        fields['category'] = ttk.Combobox(row, values=[
            'academic', 'research', 'technical', 'administrative',
        ], width=25, state='readonly')
        fields['category'].set('academic')
        fields['category'].pack(side=tk.LEFT)

        # Proficiency
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text="Proficiency:", width=16, anchor=tk.W).pack(side=tk.LEFT)
        fields['proficiency'] = ttk.Combobox(row, values=[
            'beginner', 'intermediate', 'advanced', 'expert',
        ], width=25, state='readonly')
        fields['proficiency'].set('intermediate')
        fields['proficiency'].pack(side=tk.LEFT)

        # Keywords
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text="Keywords:", width=16, anchor=tk.W).pack(side=tk.LEFT)
        fields['keywords'] = ttk.Entry(row, width=28)
        fields['keywords'].pack(side=tk.LEFT)

        error_label = ttk.Label(main_frame, text="", foreground='red')
        error_label.pack(fill=tk.X, pady=5)

        def save():
            area = fields['area'].get().strip()
            if not area:
                error_label.config(text="Expertise Area is required.")
                return
            category = fields['category'].get()
            proficiency = fields['proficiency'].get()
            keywords = fields['keywords'].get().strip() or None

            try:
                DirectoryManager.add_expertise(
                    user_id=self._get_user_id(),
                    expertise_area=area,
                    category=category,
                    proficiency=proficiency,
                    keywords=keywords,
                )
                messagebox.showinfo("Success", "Expertise area added successfully.")
                dialog.destroy()
                self._load_my_expertise()
            except Exception as exc:
                error_label.config(text=f"Error: {exc}")

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=15)
        ttk.Button(btn_frame, text="Save", command=save).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=10)

    def _remove_selected_expertise(self):
        """Remove the selected expertise entry."""
        selection = self.my_expertise_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an expertise entry to remove.")
            return

        item = self.my_expertise_tree.item(selection[0])
        expertise_id = item['values'][0]
        area_name = item['values'][1]

        if not messagebox.askyesno("Confirm", f"Remove expertise '{area_name}'?"):
            return

        try:
            DirectoryManager.remove_expertise(int(expertise_id))
            messagebox.showinfo("Success", "Expertise removed.")
            self._load_my_expertise()
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to remove expertise: {exc}")

    # ---- My Profile: office hours dialogs ----

    def _add_hours_dialog(self):
        """Open a dialog to add new office hours."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Office Hours")
        dialog.geometry("440x380")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Add Office Hours", font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        fields = {}

        # Day of week
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text="Day of Week:", width=16, anchor=tk.W).pack(side=tk.LEFT)
        day_values = [f"{k} - {v}" for k, v in DAY_NAMES.items()]
        fields['day'] = ttk.Combobox(row, values=day_values, width=25, state='readonly')
        fields['day'].set(day_values[0])
        fields['day'].pack(side=tk.LEFT)

        # Start time
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text="Start Time:", width=16, anchor=tk.W).pack(side=tk.LEFT)
        fields['start'] = ttk.Entry(row, width=12)
        fields['start'].insert(0, "09:00")
        fields['start'].pack(side=tk.LEFT)
        ttk.Label(row, text="(HH:MM)", font=('Arial', 8)).pack(side=tk.LEFT, padx=5)

        # End time
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text="End Time:", width=16, anchor=tk.W).pack(side=tk.LEFT)
        fields['end'] = ttk.Entry(row, width=12)
        fields['end'].insert(0, "10:00")
        fields['end'].pack(side=tk.LEFT)
        ttk.Label(row, text="(HH:MM)", font=('Arial', 8)).pack(side=tk.LEFT, padx=5)

        # Location
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text="Location:", width=16, anchor=tk.W).pack(side=tk.LEFT)
        fields['location'] = ttk.Entry(row, width=28)
        fields['location'].pack(side=tk.LEFT)

        # Virtual link
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text="Virtual Link:", width=16, anchor=tk.W).pack(side=tk.LEFT)
        fields['virtual_link'] = ttk.Entry(row, width=28)
        fields['virtual_link'].pack(side=tk.LEFT)

        # By appointment
        fields['by_appointment'] = tk.BooleanVar(value=False)
        ttk.Checkbutton(main_frame, text="By Appointment Only",
                        variable=fields['by_appointment']).pack(anchor=tk.W, pady=5)

        error_label = ttk.Label(main_frame, text="", foreground='red')
        error_label.pack(fill=tk.X, pady=5)

        def save():
            day_raw = fields['day'].get()
            if not day_raw:
                error_label.config(text="Please select a day of week.")
                return
            # Extract numeric key (e.g. "0" from "0 - Monday")
            day_of_week = day_raw.split(" - ")[0].strip()

            start_time = fields['start'].get().strip()
            end_time = fields['end'].get().strip()
            if not start_time or not end_time:
                error_label.config(text="Start and end times are required.")
                return

            location = fields['location'].get().strip() or None
            virtual_link = fields['virtual_link'].get().strip() or None
            by_appt = fields['by_appointment'].get()

            try:
                DirectoryManager.set_office_hours(
                    user_id=self._get_user_id(),
                    day_of_week=day_of_week,
                    start_time=start_time,
                    end_time=end_time,
                    location=location,
                    virtual_link=virtual_link,
                    is_by_appointment=by_appt,
                )
                messagebox.showinfo("Success", "Office hours added successfully.")
                dialog.destroy()
                self._load_my_hours()
            except Exception as exc:
                error_label.config(text=f"Error: {exc}")

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=15)
        ttk.Button(btn_frame, text="Save", command=save).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=10)

    def _remove_selected_hours(self):
        """Remove the selected office-hours entry."""
        selection = self.my_hours_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select office hours to remove.")
            return

        item = self.my_hours_tree.item(selection[0])
        hours_id = item['values'][0]
        day_display = item['values'][1]

        if not messagebox.askyesno("Confirm", f"Remove office hours for {day_display}?"):
            return

        try:
            DirectoryManager.remove_office_hours(int(hours_id))
            messagebox.showinfo("Success", "Office hours removed.")
            self._load_my_hours()
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to remove office hours: {exc}")

    # ==================================================================
    # Tab 4 -- Expertise Search
    # ==================================================================

    def _create_expertise_search_tab(self):
        """Create the Expertise Search tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Expertise Search")

        # -- Header --
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Search by Expertise", style='Header.TLabel').pack(side=tk.LEFT)

        # -- Keyword search --
        search_frame = ttk.LabelFrame(tab, text="Keyword Search", padding=10)
        search_frame.pack(fill=tk.X, padx=10, pady=(0, 5))

        ttk.Label(search_frame, text="Keyword:").pack(side=tk.LEFT, padx=(0, 5))
        self.expertise_keyword_entry = ttk.Entry(search_frame, width=30)
        self.expertise_keyword_entry.pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(search_frame, text="Search", command=self._do_expertise_search).pack(side=tk.LEFT, padx=5)

        self.expertise_keyword_entry.bind('<Return>', lambda e: self._do_expertise_search())

        # -- Results Treeview --
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)

        columns = ("User ID", "Expertise Area", "Category", "Proficiency")
        self.expertise_tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                                            yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.expertise_tree.yview)

        col_widths = {"User ID": 120, "Expertise Area": 220, "Category": 140, "Proficiency": 140}
        for col in columns:
            self.expertise_tree.heading(col, text=col)
            self.expertise_tree.column(col, width=col_widths.get(col, 100))

        self.expertise_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Double-click opens profile
        self.expertise_tree.bind('<Double-1>', self._on_expertise_tree_double_click)

    def _do_expertise_search(self):
        """Execute an expertise keyword search."""
        keyword = self.expertise_keyword_entry.get().strip()
        if not keyword:
            messagebox.showwarning("Warning", "Please enter a keyword to search.")
            return

        try:
            results = DirectoryManager.search_by_expertise(keyword)
        except Exception as exc:
            messagebox.showerror("Error", f"Expertise search failed: {exc}")
            return

        self.expertise_tree.delete(*self.expertise_tree.get_children())
        for row in results:
            self.expertise_tree.insert('', 'end', values=(
                row.get('user_id', ''),
                row.get('expertise_area', ''),
                row.get('category', ''),
                row.get('proficiency', ''),
            ))

    def _on_expertise_tree_double_click(self, event=None):
        """Handle double-click on an expertise search result."""
        selection = self.expertise_tree.selection()
        if not selection:
            return
        item = self.expertise_tree.item(selection[0])
        user_id = item['values'][0]
        if user_id:
            self._open_profile_dialog(str(user_id))


def launch_directory_gui(root, auth):
    """Launch Staff Directory GUI."""
    try:
        return DirectoryGUI(root, auth)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to launch Directory GUI: {e}")
        return None
