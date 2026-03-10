"""
Curriculum Design Tools GUI

Provides interface for:
- Programme management
- Programme design (module mapping)
- Learning outcomes and alignment
- Syllabus building
- Programme approvals
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime
from typing import Optional
import json

from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.modules.domain.staff_hr.services.managers.curriculum_manager import CurriculumManager
from education_system.university_system.modules.domain.staff_hr.gui.validators import (
    FormValidator, ValidationError, validate_entry, validate_date_entry,
    validate_currency_entry, validate_combobox, show_validation_error
)


class CurriculumGUI:
    """GUI for curriculum design and programme management."""

    def __init__(self, root, auth: Optional[UserAuth] = None, parent_notebook: Optional[ttk.Notebook] = None):
        self.root = root
        self.auth = auth
        self.current_user = auth.current_user if auth and auth.current_user else None
        self.parent_notebook = parent_notebook
        self.window = None

        # Track selected programme across tabs
        self.selected_programme_id = None
        self.programmes_data = []
        self.syllabus_widgets = {}
        self.current_syllabus_id = None

        if not self.current_user:
            messagebox.showerror("Error", "Login required to access Curriculum Design")
            return

        if parent_notebook:
            self.create_as_tab(parent_notebook)
        else:
            self.create_main_window()

    def _get_user_id(self):
        """Get user ID from current user dict."""
        return self.current_user.get('id') or self.current_user.get('username')

    def create_as_tab(self, notebook: ttk.Notebook):
        """Create as a tab in parent notebook."""
        self.tab_frame = ttk.Frame(notebook)
        notebook.add(self.tab_frame, text="Curriculum")
        self._build_interface(self.tab_frame)

    def create_main_window(self):
        """Create as standalone window."""
        self.window = tk.Toplevel(self.root)
        self.window.title("Curriculum Design Tools")
        self.window.geometry("1200x700")
        self.window.minsize(1000, 600)

        bottom_frame = ttk.Frame(self.window)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)
        ttk.Button(bottom_frame, text="Close", command=self.window.destroy).pack(side=tk.RIGHT, padx=5)

        self.status_bar = ttk.Label(self.window, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self._build_interface(self.window)

    def _build_interface(self, parent):
        """Build the main interface."""
        style = ttk.Style()
        style.configure('Header.TLabel', font=('Arial', 14, 'bold'))

        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self._create_programmes_tab()
        self._create_design_tab()
        self._create_outcomes_tab()
        self._create_syllabus_tab()

        if self.current_user.get('role') in ['admin', 'Admin', 'administrator', 'staff']:
            self._create_approvals_tab()

    # ==================== TAB 1: PROGRAMMES ====================

    def _create_programmes_tab(self):
        """Create the programmes management tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Programmes")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Academic Programmes", style='Header.TLabel').pack(side=tk.LEFT)

        # Filter frame
        filter_frame = ttk.Frame(header_frame)
        filter_frame.pack(side=tk.RIGHT)

        ttk.Label(filter_frame, text="Department:").pack(side=tk.LEFT, padx=5)
        self.prog_dept_entry = ttk.Entry(filter_frame, width=20)
        self.prog_dept_entry.pack(side=tk.LEFT, padx=5)

        ttk.Label(filter_frame, text="Status:").pack(side=tk.LEFT, padx=5)
        self.prog_status_filter = ttk.Combobox(
            filter_frame,
            values=['All', 'Draft', 'Pending', 'Approved', 'Rejected'],
            width=12, state='readonly'
        )
        self.prog_status_filter.set('All')
        self.prog_status_filter.pack(side=tk.LEFT, padx=5)
        self.prog_status_filter.bind('<<ComboboxSelected>>', lambda e: self._load_programmes())

        ttk.Button(filter_frame, text="Refresh", command=self._load_programmes).pack(side=tk.LEFT, padx=5)
        ttk.Button(filter_frame, text="New Programme", command=self._create_programme_dialog).pack(side=tk.LEFT, padx=5)

        # Programmes treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        columns = ('ID', 'Code', 'Name', 'Level', 'Department', 'Credits', 'Duration', 'Status')
        self.programmes_tree = ttk.Treeview(
            tree_frame, columns=columns, show='headings', yscrollcommand=y_scroll.set
        )
        y_scroll.config(command=self.programmes_tree.yview)

        widths = {
            'ID': 50, 'Code': 80, 'Name': 200, 'Level': 110,
            'Department': 130, 'Credits': 70, 'Duration': 80, 'Status': 100
        }
        for col in columns:
            self.programmes_tree.heading(col, text=col)
            self.programmes_tree.column(col, width=widths.get(col, 100))

        self.programmes_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Tag colours for status
        self.programmes_tree.tag_configure('draft', background='#e2e3e5')
        self.programmes_tree.tag_configure('pending_approval', background='#fff3cd')
        self.programmes_tree.tag_configure('approved', background='#d4edda')
        self.programmes_tree.tag_configure('rejected', background='#f8d7da')

        # Double-click to select programme for Design tab
        self.programmes_tree.bind('<Double-1>', self._on_programme_double_click)

        # Action buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(btn_frame, text="Submit for Approval", command=self._submit_for_approval).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Edit Programme", command=self._edit_programme_dialog).pack(side=tk.LEFT, padx=5)

        self._load_programmes()

    def _load_programmes(self):
        """Load programmes into the treeview."""
        for item in self.programmes_tree.get_children():
            self.programmes_tree.delete(item)

        status = self.prog_status_filter.get().lower()
        if status == 'all':
            status = None
        elif status == 'pending':
            status = 'pending_approval'

        department = self.prog_dept_entry.get().strip() or None

        try:
            self.programmes_data = CurriculumManager.get_programmes(
                status=status, department=department
            )
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load programmes: {e}")
            self.programmes_data = []
            return

        for p in self.programmes_data:
            prog_status = p.get('status', 'draft').lower()
            display_status = prog_status.replace('_', ' ').title()
            self.programmes_tree.insert('', tk.END, values=(
                p.get('programme_id'),
                p.get('code', ''),
                p.get('name', ''),
                p.get('level', '').title(),
                p.get('department', ''),
                p.get('total_credits', 0),
                f"{p.get('duration_years', 0)} years",
                display_status
            ), tags=(prog_status,))

        # Refresh the design tab programme selector
        self._refresh_programme_selector()

    def _create_programme_dialog(self):
        """Open dialog to create a new programme."""
        dialog = tk.Toplevel(self.root)
        dialog.title("New Programme")
        dialog.geometry("500x480")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Create New Programme", style='Header.TLabel').grid(
            row=0, column=0, columnspan=2, pady=(0, 15), sticky='w'
        )

        # Code
        ttk.Label(frame, text="Code:").grid(row=1, column=0, sticky='e', padx=10, pady=8)
        code_entry = ttk.Entry(frame, width=30)
        code_entry.grid(row=1, column=1, padx=10, pady=8, sticky='w')

        # Name
        ttk.Label(frame, text="Name:").grid(row=2, column=0, sticky='e', padx=10, pady=8)
        name_entry = ttk.Entry(frame, width=30)
        name_entry.grid(row=2, column=1, padx=10, pady=8, sticky='w')

        # Level
        ttk.Label(frame, text="Level:").grid(row=3, column=0, sticky='e', padx=10, pady=8)
        level_combo = ttk.Combobox(
            frame, values=['undergraduate', 'postgraduate', 'doctoral'],
            width=27, state='readonly'
        )
        level_combo.set('undergraduate')
        level_combo.grid(row=3, column=1, padx=10, pady=8, sticky='w')

        # Department
        ttk.Label(frame, text="Department:").grid(row=4, column=0, sticky='e', padx=10, pady=8)
        dept_entry = ttk.Entry(frame, width=30)
        dept_entry.grid(row=4, column=1, padx=10, pady=8, sticky='w')

        # Credits
        ttk.Label(frame, text="Total Credits:").grid(row=5, column=0, sticky='e', padx=10, pady=8)
        credits_entry = ttk.Entry(frame, width=15)
        credits_entry.insert(0, "360")
        credits_entry.grid(row=5, column=1, padx=10, pady=8, sticky='w')

        # Duration
        ttk.Label(frame, text="Duration (years):").grid(row=6, column=0, sticky='e', padx=10, pady=8)
        duration_entry = ttk.Entry(frame, width=15)
        duration_entry.insert(0, "3")
        duration_entry.grid(row=6, column=1, padx=10, pady=8, sticky='w')

        # Description
        ttk.Label(frame, text="Description:").grid(row=7, column=0, sticky='ne', padx=10, pady=8)
        desc_text = tk.Text(frame, width=40, height=4)
        desc_text.grid(row=7, column=1, padx=10, pady=8, sticky='w')

        def save():
            # Validate required fields
            try:
                code = validate_entry(code_entry, "Code")
                name = validate_entry(name_entry, "Name")
                level = validate_combobox(level_combo, "Level")
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            department = dept_entry.get().strip() or None
            description = desc_text.get("1.0", "end-1c").strip() or None

            try:
                total_credits = int(credits_entry.get().strip())
            except ValueError:
                messagebox.showerror("Error", "Credits must be a valid integer", parent=dialog)
                return

            try:
                duration = int(duration_entry.get().strip())
            except ValueError:
                messagebox.showerror("Error", "Duration must be a valid integer", parent=dialog)
                return

            try:
                programme_id = CurriculumManager.create_programme(
                    code=code,
                    name=name,
                    level=level,
                    department=department,
                    total_credits=total_credits,
                    duration_years=duration,
                    description=description,
                    created_by=self._get_user_id()
                )
                messagebox.showinfo("Success", f"Programme created successfully. ID: {programme_id}", parent=dialog)
                dialog.destroy()
                self._load_programmes()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dialog)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=8, column=0, columnspan=2, pady=15)
        ttk.Button(btn_frame, text="Save", command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _edit_programme_dialog(self):
        """Edit the selected programme."""
        selection = self.programmes_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select a programme to edit")
            return

        item = self.programmes_tree.item(selection[0])
        programme_id = item['values'][0]

        try:
            programme = CurriculumManager.get_programme(programme_id)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        if not programme:
            messagebox.showerror("Error", "Programme not found")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Programme")
        dialog.geometry("500x480")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Edit Programme", style='Header.TLabel').grid(
            row=0, column=0, columnspan=2, pady=(0, 15), sticky='w'
        )

        # Code (read-only for editing)
        ttk.Label(frame, text="Code:").grid(row=1, column=0, sticky='e', padx=10, pady=8)
        code_label = ttk.Label(frame, text=programme.get('code', ''))
        code_label.grid(row=1, column=1, padx=10, pady=8, sticky='w')

        # Name
        ttk.Label(frame, text="Name:").grid(row=2, column=0, sticky='e', padx=10, pady=8)
        name_entry = ttk.Entry(frame, width=30)
        name_entry.insert(0, programme.get('name', ''))
        name_entry.grid(row=2, column=1, padx=10, pady=8, sticky='w')

        # Level
        ttk.Label(frame, text="Level:").grid(row=3, column=0, sticky='e', padx=10, pady=8)
        level_combo = ttk.Combobox(
            frame, values=['undergraduate', 'postgraduate', 'doctoral'],
            width=27, state='readonly'
        )
        level_combo.set(programme.get('level', 'undergraduate'))
        level_combo.grid(row=3, column=1, padx=10, pady=8, sticky='w')

        # Department
        ttk.Label(frame, text="Department:").grid(row=4, column=0, sticky='e', padx=10, pady=8)
        dept_entry = ttk.Entry(frame, width=30)
        dept_entry.insert(0, programme.get('department', ''))
        dept_entry.grid(row=4, column=1, padx=10, pady=8, sticky='w')

        # Credits
        ttk.Label(frame, text="Total Credits:").grid(row=5, column=0, sticky='e', padx=10, pady=8)
        credits_entry = ttk.Entry(frame, width=15)
        credits_entry.insert(0, str(programme.get('total_credits', 360)))
        credits_entry.grid(row=5, column=1, padx=10, pady=8, sticky='w')

        # Duration
        ttk.Label(frame, text="Duration (years):").grid(row=6, column=0, sticky='e', padx=10, pady=8)
        duration_entry = ttk.Entry(frame, width=15)
        duration_entry.insert(0, str(programme.get('duration_years', 3)))
        duration_entry.grid(row=6, column=1, padx=10, pady=8, sticky='w')

        # Description
        ttk.Label(frame, text="Description:").grid(row=7, column=0, sticky='ne', padx=10, pady=8)
        desc_text = tk.Text(frame, width=40, height=4)
        desc_text.insert("1.0", programme.get('description', '') or '')
        desc_text.grid(row=7, column=1, padx=10, pady=8, sticky='w')

        def save():
            try:
                name = validate_entry(name_entry, "Name")
                level = validate_combobox(level_combo, "Level")
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            department = dept_entry.get().strip() or None
            description = desc_text.get("1.0", "end-1c").strip() or None

            try:
                total_credits = int(credits_entry.get().strip())
            except ValueError:
                messagebox.showerror("Error", "Credits must be a valid integer", parent=dialog)
                return

            try:
                duration = int(duration_entry.get().strip())
            except ValueError:
                messagebox.showerror("Error", "Duration must be a valid integer", parent=dialog)
                return

            try:
                CurriculumManager.update_programme(
                    programme_id,
                    name=name,
                    level=level,
                    department=department,
                    total_credits=total_credits,
                    duration_years=duration,
                    description=description
                )
                messagebox.showinfo("Success", "Programme updated successfully", parent=dialog)
                dialog.destroy()
                self._load_programmes()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dialog)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=8, column=0, columnspan=2, pady=15)
        ttk.Button(btn_frame, text="Save", command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _on_programme_double_click(self, event):
        """Handle double-click on programme to select it for the Design tab."""
        selection = self.programmes_tree.selection()
        if not selection:
            return

        item = self.programmes_tree.item(selection[0])
        programme_id = item['values'][0]
        programme_name = item['values'][2]
        programme_code = item['values'][1]

        self.selected_programme_id = programme_id

        # Update the design tab selector
        display = f"{programme_code} - {programme_name}"
        if display in self.design_programme_combo['values']:
            self.design_programme_combo.set(display)
        else:
            self.design_programme_combo.set(display)

        # Switch to Design tab and load modules
        self.notebook.select(1)
        self._load_programme_modules()

    def _submit_for_approval(self):
        """Submit the selected programme for approval."""
        selection = self.programmes_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select a programme to submit")
            return

        item = self.programmes_tree.item(selection[0])
        programme_id = item['values'][0]
        programme_name = item['values'][2]

        if not messagebox.askyesno(
            "Confirm",
            f"Submit '{programme_name}' for approval?\n\n"
            "This will create approval entries at department, faculty, and senate levels."
        ):
            return

        try:
            CurriculumManager.submit_for_approval(
                programme_id, submitted_by=self._get_user_id()
            )
            messagebox.showinfo("Success", "Programme submitted for approval")
            self._load_programmes()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ==================== TAB 2: PROGRAMME DESIGN ====================

    def _create_design_tab(self):
        """Create the programme design (module mapping) tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Programme Design")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Programme Design", style='Header.TLabel').pack(side=tk.LEFT)

        # Programme selector
        selector_frame = ttk.LabelFrame(tab, text="Select Programme", padding=10)
        selector_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(selector_frame, text="Programme:").pack(side=tk.LEFT, padx=5)
        self.design_programme_combo = ttk.Combobox(selector_frame, width=50, state='readonly')
        self.design_programme_combo.pack(side=tk.LEFT, padx=5)
        self.design_programme_combo.bind('<<ComboboxSelected>>', lambda e: self._on_design_programme_selected())

        ttk.Button(selector_frame, text="Load", command=self._load_programme_modules).pack(side=tk.LEFT, padx=5)

        # Credit summary
        self.credit_summary_label = ttk.Label(selector_frame, text="Total Credits: 0 / 0", font=('Arial', 11, 'bold'))
        self.credit_summary_label.pack(side=tk.RIGHT, padx=10)

        # Module mapping treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        columns = ('ID', 'Code', 'Name', 'Year', 'Semester', 'Core/Elective', 'Credits')
        self.modules_tree = ttk.Treeview(
            tree_frame, columns=columns, show='headings', yscrollcommand=y_scroll.set
        )
        y_scroll.config(command=self.modules_tree.yview)

        widths = {
            'ID': 50, 'Code': 100, 'Name': 220, 'Year': 60,
            'Semester': 80, 'Core/Elective': 100, 'Credits': 70
        }
        for col in columns:
            self.modules_tree.heading(col, text=col)
            self.modules_tree.column(col, width=widths.get(col, 100))

        self.modules_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.modules_tree.tag_configure('core', background='#d4edda')
        self.modules_tree.tag_configure('elective', background='#cce5ff')

        # Button frame
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(btn_frame, text="Add Module", command=self._add_module_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Remove Module", command=self._remove_module).pack(side=tk.LEFT, padx=5)

        # Populate programme selector
        self._refresh_programme_selector()

    def _refresh_programme_selector(self):
        """Refresh the programme selector combobox in the Design tab."""
        if not hasattr(self, 'design_programme_combo'):
            return

        prog_values = []
        self._programme_lookup = {}
        for p in self.programmes_data:
            display = f"{p.get('code', '')} - {p.get('name', '')}"
            prog_values.append(display)
            self._programme_lookup[display] = p

        self.design_programme_combo['values'] = prog_values

    def _on_design_programme_selected(self):
        """Handle programme selection in the Design tab."""
        display = self.design_programme_combo.get()
        if display in self._programme_lookup:
            prog = self._programme_lookup[display]
            self.selected_programme_id = prog.get('programme_id')
            self._load_programme_modules()

    def _load_programme_modules(self):
        """Load modules for the selected programme."""
        for item in self.modules_tree.get_children():
            self.modules_tree.delete(item)

        if not self.selected_programme_id:
            self.credit_summary_label.config(text="Total Credits: 0 / 0")
            return

        try:
            modules = CurriculumManager.get_programme_modules(self.selected_programme_id)
            programme = CurriculumManager.get_programme(self.selected_programme_id)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load modules: {e}")
            return

        total_credits = 0
        target_credits = programme.get('total_credits', 0) if programme else 0

        for m in modules:
            credits = m.get('credits', 0) or 0
            total_credits += credits
            is_core = m.get('is_core', True)
            core_display = 'Core' if is_core else 'Elective'
            tag = 'core' if is_core else 'elective'

            self.modules_tree.insert('', tk.END, values=(
                m.get('mapping_id'),
                m.get('module_code', ''),
                m.get('module_name', ''),
                m.get('year_of_study', ''),
                m.get('semester', ''),
                core_display,
                credits
            ), tags=(tag,))

        self.credit_summary_label.config(
            text=f"Total Credits: {total_credits} / {target_credits}"
        )

    def _add_module_dialog(self):
        """Open dialog to add a module to the programme."""
        if not self.selected_programme_id:
            messagebox.showinfo("Info", "Please select a programme first")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Add Module to Programme")
        dialog.geometry("450x380")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Add Module", style='Header.TLabel').grid(
            row=0, column=0, columnspan=2, pady=(0, 15), sticky='w'
        )

        # Module Code
        ttk.Label(frame, text="Module Code:").grid(row=1, column=0, sticky='e', padx=10, pady=8)
        code_entry = ttk.Entry(frame, width=25)
        code_entry.grid(row=1, column=1, padx=10, pady=8, sticky='w')

        # Module Name
        ttk.Label(frame, text="Module Name:").grid(row=2, column=0, sticky='e', padx=10, pady=8)
        name_entry = ttk.Entry(frame, width=25)
        name_entry.grid(row=2, column=1, padx=10, pady=8, sticky='w')

        # Year
        ttk.Label(frame, text="Year:").grid(row=3, column=0, sticky='e', padx=10, pady=8)
        year_combo = ttk.Combobox(
            frame, values=['1', '2', '3', '4', '5', '6'],
            width=10, state='readonly'
        )
        year_combo.set('1')
        year_combo.grid(row=3, column=1, padx=10, pady=8, sticky='w')

        # Semester
        ttk.Label(frame, text="Semester:").grid(row=4, column=0, sticky='e', padx=10, pady=8)
        semester_combo = ttk.Combobox(
            frame, values=['1', '2'],
            width=10, state='readonly'
        )
        semester_combo.set('1')
        semester_combo.grid(row=4, column=1, padx=10, pady=8, sticky='w')

        # Core/Elective
        ttk.Label(frame, text="Type:").grid(row=5, column=0, sticky='e', padx=10, pady=8)
        type_combo = ttk.Combobox(
            frame, values=['Core', 'Elective'],
            width=15, state='readonly'
        )
        type_combo.set('Core')
        type_combo.grid(row=5, column=1, padx=10, pady=8, sticky='w')

        # Credits
        ttk.Label(frame, text="Credits:").grid(row=6, column=0, sticky='e', padx=10, pady=8)
        credits_entry = ttk.Entry(frame, width=15)
        credits_entry.insert(0, "20")
        credits_entry.grid(row=6, column=1, padx=10, pady=8, sticky='w')

        def save():
            try:
                module_code = validate_entry(code_entry, "Module Code")
                module_name = validate_entry(name_entry, "Module Name")
                year = validate_combobox(year_combo, "Year")
                semester = validate_combobox(semester_combo, "Semester")
                module_type = validate_combobox(type_combo, "Type")
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            try:
                credits = int(credits_entry.get().strip())
                if credits <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Error", "Credits must be a positive integer", parent=dialog)
                return

            is_core = module_type == 'Core'

            try:
                mapping_id = CurriculumManager.add_module_to_programme(
                    programme_id=self.selected_programme_id,
                    module_code=module_code,
                    module_name=module_name,
                    year_of_study=int(year),
                    semester=int(semester),
                    is_core=is_core,
                    credits=credits
                )
                messagebox.showinfo("Success", f"Module added. Mapping ID: {mapping_id}", parent=dialog)
                dialog.destroy()
                self._load_programme_modules()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dialog)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=7, column=0, columnspan=2, pady=15)
        ttk.Button(btn_frame, text="Save", command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _remove_module(self):
        """Remove the selected module from the programme."""
        selection = self.modules_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select a module to remove")
            return

        item = self.modules_tree.item(selection[0])
        mapping_id = item['values'][0]
        module_code = item['values'][1]
        module_name = item['values'][2]

        if not messagebox.askyesno(
            "Confirm",
            f"Remove module '{module_code} - {module_name}' from this programme?"
        ):
            return

        try:
            CurriculumManager.remove_module_from_programme(mapping_id)
            messagebox.showinfo("Success", "Module removed from programme")
            self._load_programme_modules()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ==================== TAB 3: LEARNING OUTCOMES ====================

    def _create_outcomes_tab(self):
        """Create the learning outcomes and alignment tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Learning Outcomes")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Learning Outcomes & Alignment", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text="Refresh", command=self._refresh_outcomes_tab).pack(side=tk.RIGHT, padx=5)

        # PanedWindow for side-by-side layout
        paned = ttk.PanedWindow(tab, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Left: Programme Outcomes
        left_frame = ttk.LabelFrame(paned, text="Programme Outcomes", padding=10)
        paned.add(left_frame, weight=1)

        outcomes_tree_frame = ttk.Frame(left_frame)
        outcomes_tree_frame.pack(fill=tk.BOTH, expand=True)

        y_scroll_left = ttk.Scrollbar(outcomes_tree_frame, orient=tk.VERTICAL)
        outcome_columns = ('ID', 'Code', 'Description', 'Bloom Level')
        self.outcomes_tree = ttk.Treeview(
            outcomes_tree_frame, columns=outcome_columns, show='headings',
            yscrollcommand=y_scroll_left.set
        )
        y_scroll_left.config(command=self.outcomes_tree.yview)

        widths_left = {'ID': 40, 'Code': 70, 'Description': 200, 'Bloom Level': 90}
        for col in outcome_columns:
            self.outcomes_tree.heading(col, text=col)
            self.outcomes_tree.column(col, width=widths_left.get(col, 100))

        self.outcomes_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll_left.pack(side=tk.RIGHT, fill=tk.Y)

        # Outcome action buttons
        outcome_btn_frame = ttk.Frame(left_frame)
        outcome_btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(outcome_btn_frame, text="Add", command=self._add_outcome_dialog).pack(side=tk.LEFT, padx=3)
        ttk.Button(outcome_btn_frame, text="Edit", command=self._edit_outcome_dialog).pack(side=tk.LEFT, padx=3)
        ttk.Button(outcome_btn_frame, text="Delete", command=self._delete_outcome).pack(side=tk.LEFT, padx=3)

        # Right: Alignment Matrix
        right_frame = ttk.LabelFrame(paned, text="Alignment Matrix", padding=10)
        paned.add(right_frame, weight=2)

        alignment_tree_frame = ttk.Frame(right_frame)
        alignment_tree_frame.pack(fill=tk.BOTH, expand=True)

        x_scroll_right = ttk.Scrollbar(alignment_tree_frame, orient=tk.HORIZONTAL)
        y_scroll_right = ttk.Scrollbar(alignment_tree_frame, orient=tk.VERTICAL)

        # Start with a basic alignment tree; columns will be dynamic
        self.alignment_tree = ttk.Treeview(
            alignment_tree_frame, show='headings',
            xscrollcommand=x_scroll_right.set,
            yscrollcommand=y_scroll_right.set
        )
        x_scroll_right.config(command=self.alignment_tree.xview)
        y_scroll_right.config(command=self.alignment_tree.yview)

        self.alignment_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll_right.pack(side=tk.RIGHT, fill=tk.Y)
        x_scroll_right.pack(side=tk.BOTTOM, fill=tk.X)

        # Alignment legend
        legend_frame = ttk.Frame(right_frame)
        legend_frame.pack(fill=tk.X, pady=5)
        ttk.Label(legend_frame, text="Legend:  ", font=('Arial', 9)).pack(side=tk.LEFT)
        for strength, colour in [('Strong', '#2e7d32'), ('Moderate', '#f57f17'), ('Weak', '#e65100'), ('None', '#9e9e9e')]:
            ttk.Label(legend_frame, text=f"  {strength}  ", font=('Arial', 9),
                      foreground=colour).pack(side=tk.LEFT)

    def _refresh_outcomes_tab(self):
        """Refresh both outcomes and alignment data."""
        self._load_programme_outcomes()
        self._load_alignment_matrix()

    def _load_programme_outcomes(self):
        """Load programme outcomes into the outcomes treeview."""
        for item in self.outcomes_tree.get_children():
            self.outcomes_tree.delete(item)

        if not self.selected_programme_id:
            return

        try:
            outcomes = CurriculumManager.get_programme_outcomes(self.selected_programme_id)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load outcomes: {e}")
            return

        for o in outcomes:
            desc = o.get('description', '')
            if len(desc) > 60:
                desc = desc[:57] + '...'
            self.outcomes_tree.insert('', tk.END, values=(
                o.get('outcome_id'),
                o.get('code', ''),
                desc,
                o.get('bloom_level', '').title()
            ))

    def _load_alignment_matrix(self):
        """Load the alignment matrix for the selected programme."""
        # Clear existing columns and data
        self.alignment_tree['columns'] = ()
        for item in self.alignment_tree.get_children():
            self.alignment_tree.delete(item)

        if not self.selected_programme_id:
            return

        try:
            matrix_data = CurriculumManager.get_alignment_matrix(self.selected_programme_id)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load alignment matrix: {e}")
            return

        programme_outcomes = matrix_data.get('programme_outcomes', [])
        modules = matrix_data.get('modules', [])
        matrix = matrix_data.get('matrix', {})

        if not programme_outcomes or not modules:
            self.alignment_tree['columns'] = ('Outcome',)
            self.alignment_tree.heading('Outcome', text='Outcome')
            self.alignment_tree.column('Outcome', width=200)
            self.alignment_tree.insert('', tk.END, values=('No data available',))
            return

        # Build columns: first is Outcome Code, then one per module
        module_codes = [m['module_code'] for m in modules]
        all_columns = ['Outcome'] + module_codes
        self.alignment_tree['columns'] = all_columns

        self.alignment_tree.heading('Outcome', text='Outcome')
        self.alignment_tree.column('Outcome', width=80, minwidth=60)
        for mc in module_codes:
            self.alignment_tree.heading(mc, text=mc)
            self.alignment_tree.column(mc, width=80, minwidth=60)

        # Tag configurations for alignment strengths
        self.alignment_tree.tag_configure('has_strong', foreground='#2e7d32')
        self.alignment_tree.tag_configure('has_moderate', foreground='#f57f17')
        self.alignment_tree.tag_configure('has_weak', foreground='#e65100')

        # Populate matrix rows
        for po in programme_outcomes:
            po_id = po['outcome_id']
            po_code = po.get('code', '')
            row_values = [po_code]

            for mc in module_codes:
                strength = matrix.get(po_id, {}).get(mc)
                if strength:
                    row_values.append(strength.title())
                else:
                    row_values.append('-')

            self.alignment_tree.insert('', tk.END, values=row_values)

    def _add_outcome_dialog(self):
        """Open dialog to add a new learning outcome."""
        if not self.selected_programme_id:
            messagebox.showinfo("Info", "Please select a programme first (from the Programmes tab)")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Add Learning Outcome")
        dialog.geometry("520x450")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="New Learning Outcome", style='Header.TLabel').grid(
            row=0, column=0, columnspan=2, pady=(0, 15), sticky='w'
        )

        # Code
        ttk.Label(frame, text="Code:").grid(row=1, column=0, sticky='e', padx=10, pady=8)
        code_entry = ttk.Entry(frame, width=25)
        code_entry.grid(row=1, column=1, padx=10, pady=8, sticky='w')

        # Type
        ttk.Label(frame, text="Type:").grid(row=2, column=0, sticky='e', padx=10, pady=8)
        type_combo = ttk.Combobox(
            frame, values=['programme', 'module'],
            width=22, state='readonly'
        )
        type_combo.set('programme')
        type_combo.grid(row=2, column=1, padx=10, pady=8, sticky='w')

        # Module code (only for module-level outcomes)
        ttk.Label(frame, text="Module Code:").grid(row=3, column=0, sticky='e', padx=10, pady=8)
        module_code_entry = ttk.Entry(frame, width=25)
        module_code_entry.grid(row=3, column=1, padx=10, pady=8, sticky='w')
        module_code_entry.config(state='disabled')

        def on_type_change(event=None):
            if type_combo.get() == 'module':
                module_code_entry.config(state='normal')
            else:
                module_code_entry.config(state='disabled')
                module_code_entry.delete(0, tk.END)

        type_combo.bind('<<ComboboxSelected>>', on_type_change)

        # Bloom Level
        ttk.Label(frame, text="Bloom Level:").grid(row=4, column=0, sticky='e', padx=10, pady=8)
        bloom_combo = ttk.Combobox(
            frame, values=['remember', 'understand', 'apply', 'analyze', 'evaluate', 'create'],
            width=22, state='readonly'
        )
        bloom_combo.set('understand')
        bloom_combo.grid(row=4, column=1, padx=10, pady=8, sticky='w')

        # Description
        ttk.Label(frame, text="Description:").grid(row=5, column=0, sticky='ne', padx=10, pady=8)
        desc_text = scrolledtext.ScrolledText(frame, width=35, height=6)
        desc_text.grid(row=5, column=1, padx=10, pady=8, sticky='w')

        def save():
            try:
                code = validate_entry(code_entry, "Code")
                outcome_type = validate_combobox(type_combo, "Type")
                bloom_level = validate_combobox(bloom_combo, "Bloom Level")
                description = validate_entry(desc_text, "Description")
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            module_code = None
            if outcome_type == 'module':
                mc = module_code_entry.get().strip()
                if not mc:
                    messagebox.showerror("Error", "Module Code is required for module-level outcomes", parent=dialog)
                    return
                module_code = mc

            programme_id = self.selected_programme_id if outcome_type == 'programme' else None

            try:
                outcome_id = CurriculumManager.create_outcome(
                    code=code,
                    description=description,
                    programme_id=programme_id,
                    module_code=module_code,
                    bloom_level=bloom_level,
                    outcome_type=outcome_type
                )
                messagebox.showinfo("Success", f"Outcome created. ID: {outcome_id}", parent=dialog)
                dialog.destroy()
                self._refresh_outcomes_tab()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dialog)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=6, column=0, columnspan=2, pady=15)
        ttk.Button(btn_frame, text="Save", command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _edit_outcome_dialog(self):
        """Edit the selected learning outcome."""
        selection = self.outcomes_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select an outcome to edit")
            return

        item = self.outcomes_tree.item(selection[0])
        outcome_id = item['values'][0]

        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Learning Outcome")
        dialog.geometry("520x400")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Edit Learning Outcome", style='Header.TLabel').grid(
            row=0, column=0, columnspan=2, pady=(0, 15), sticky='w'
        )

        # ID display
        ttk.Label(frame, text="Outcome ID:").grid(row=1, column=0, sticky='e', padx=10, pady=8)
        ttk.Label(frame, text=str(outcome_id)).grid(row=1, column=1, padx=10, pady=8, sticky='w')

        # Code
        ttk.Label(frame, text="Code:").grid(row=2, column=0, sticky='e', padx=10, pady=8)
        code_entry = ttk.Entry(frame, width=25)
        code_entry.insert(0, str(item['values'][1]))
        code_entry.grid(row=2, column=1, padx=10, pady=8, sticky='w')

        # Bloom Level
        ttk.Label(frame, text="Bloom Level:").grid(row=3, column=0, sticky='e', padx=10, pady=8)
        bloom_combo = ttk.Combobox(
            frame, values=['remember', 'understand', 'apply', 'analyze', 'evaluate', 'create'],
            width=22, state='readonly'
        )
        current_bloom = str(item['values'][3]).lower()
        bloom_combo.set(current_bloom)
        bloom_combo.grid(row=3, column=1, padx=10, pady=8, sticky='w')

        # Description
        ttk.Label(frame, text="Description:").grid(row=4, column=0, sticky='ne', padx=10, pady=8)
        desc_text = scrolledtext.ScrolledText(frame, width=35, height=6)
        # Use full description from item (may be truncated in treeview)
        desc_text.insert("1.0", str(item['values'][2]))
        desc_text.grid(row=4, column=1, padx=10, pady=8, sticky='w')

        def save():
            try:
                code = validate_entry(code_entry, "Code")
                bloom_level = validate_combobox(bloom_combo, "Bloom Level")
                description = validate_entry(desc_text, "Description")
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            try:
                CurriculumManager.update_outcome(
                    outcome_id,
                    code=code,
                    bloom_level=bloom_level,
                    description=description
                )
                messagebox.showinfo("Success", "Outcome updated successfully", parent=dialog)
                dialog.destroy()
                self._refresh_outcomes_tab()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dialog)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=15)
        ttk.Button(btn_frame, text="Save", command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _delete_outcome(self):
        """Delete the selected learning outcome."""
        selection = self.outcomes_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select an outcome to delete")
            return

        item = self.outcomes_tree.item(selection[0])
        outcome_id = item['values'][0]
        outcome_code = item['values'][1]

        if not messagebox.askyesno(
            "Confirm",
            f"Delete outcome '{outcome_code}'?\n\nThis will also remove all associated alignments."
        ):
            return

        try:
            CurriculumManager.delete_outcome(outcome_id)
            messagebox.showinfo("Success", "Outcome deleted")
            self._refresh_outcomes_tab()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ==================== TAB 4: SYLLABUS BUILDER ====================

    def _create_syllabus_tab(self):
        """Create the syllabus builder tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Syllabus Builder")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Syllabus Builder", style='Header.TLabel').pack(side=tk.LEFT)

        # Selector frame
        selector_frame = ttk.LabelFrame(tab, text="Syllabus Selection", padding=10)
        selector_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(selector_frame, text="Module Code:").grid(row=0, column=0, sticky='e', padx=5, pady=5)
        self.syllabus_module_entry = ttk.Entry(selector_frame, width=20)
        self.syllabus_module_entry.grid(row=0, column=1, padx=5, pady=5, sticky='w')

        ttk.Label(selector_frame, text="Academic Year:").grid(row=0, column=2, sticky='e', padx=5, pady=5)
        self.syllabus_year_entry = ttk.Entry(selector_frame, width=15)
        self.syllabus_year_entry.insert(0, "2025-2026")
        self.syllabus_year_entry.grid(row=0, column=3, padx=5, pady=5, sticky='w')

        ttk.Label(selector_frame, text="Template:").grid(row=0, column=4, sticky='e', padx=5, pady=5)
        self.syllabus_template_combo = ttk.Combobox(selector_frame, width=25, state='readonly')
        self.syllabus_template_combo.grid(row=0, column=5, padx=5, pady=5, sticky='w')
        self._load_syllabus_templates()

        btn_sel_frame = ttk.Frame(selector_frame)
        btn_sel_frame.grid(row=1, column=0, columnspan=6, pady=5)
        ttk.Button(btn_sel_frame, text="Load Syllabus", command=self._load_syllabus).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_sel_frame, text="New from Template", command=self._new_from_template).pack(side=tk.LEFT, padx=5)

        # Status label
        self.syllabus_status_label = ttk.Label(selector_frame, text="Status: No syllabus loaded", font=('Arial', 10))
        self.syllabus_status_label.grid(row=1, column=3, columnspan=3, sticky='e', padx=10)

        # Content frame with scrollable area
        content_outer = ttk.Frame(tab)
        content_outer.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Canvas + scrollbar for scrolling through sections
        canvas = tk.Canvas(content_outer)
        scrollbar = ttk.Scrollbar(content_outer, orient=tk.VERTICAL, command=canvas.yview)
        self.syllabus_content_frame = ttk.Frame(canvas)

        self.syllabus_content_frame.bind(
            '<Configure>',
            lambda e: canvas.configure(scrollregion=canvas.bbox('all'))
        )

        canvas.create_window((0, 0), window=self.syllabus_content_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind mousewheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')

        canvas.bind_all('<MouseWheel>', _on_mousewheel, add='+')

        # Save button frame
        save_frame = ttk.Frame(tab)
        save_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(save_frame, text="Save Syllabus", command=self._save_syllabus).pack(side=tk.LEFT, padx=5)
        ttk.Button(save_frame, text="Submit for Review", command=self._submit_syllabus_for_review).pack(side=tk.LEFT, padx=5)

    def _load_syllabus_templates(self):
        """Load available syllabus templates into the combobox."""
        try:
            templates = CurriculumManager.get_syllabus_templates()
            self._templates_data = {}
            template_names = []
            for t in templates:
                name = t.get('name', 'Unknown')
                template_names.append(name)
                self._templates_data[name] = t

            self.syllabus_template_combo['values'] = template_names
            if template_names:
                self.syllabus_template_combo.set(template_names[0])
        except Exception:
            self._templates_data = {}
            self.syllabus_template_combo['values'] = []

    def _build_syllabus_sections(self, sections):
        """Build section LabelFrames with ScrolledText widgets for each section."""
        # Clear existing widgets
        for widget in self.syllabus_content_frame.winfo_children():
            widget.destroy()
        self.syllabus_widgets = {}

        if not sections:
            ttk.Label(self.syllabus_content_frame, text="No sections available.").pack(padx=10, pady=10)
            return

        for idx, section in enumerate(sections):
            if isinstance(section, dict):
                title = section.get('title', f'Section {idx + 1}')
            else:
                title = str(section)

            section_frame = ttk.LabelFrame(self.syllabus_content_frame, text=title, padding=10)
            section_frame.pack(fill=tk.X, padx=10, pady=5, expand=False)

            text_widget = scrolledtext.ScrolledText(section_frame, width=80, height=6)
            text_widget.pack(fill=tk.X, expand=True)

            # Pre-fill with content if available
            if isinstance(section, dict) and section.get('content'):
                text_widget.insert("1.0", section['content'])

            self.syllabus_widgets[title] = text_widget

    def _load_syllabus(self):
        """Load an existing syllabus for the given module and year."""
        module_code = self.syllabus_module_entry.get().strip()
        academic_year = self.syllabus_year_entry.get().strip()

        if not module_code:
            messagebox.showerror("Error", "Module Code is required")
            return

        try:
            syllabus = CurriculumManager.get_syllabus(module_code, academic_year or None)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load syllabus: {e}")
            return

        if not syllabus:
            messagebox.showinfo("Info", f"No syllabus found for {module_code}" +
                                (f" ({academic_year})" if academic_year else ""))
            self.current_syllabus_id = None
            self.syllabus_status_label.config(text="Status: No syllabus found")
            return

        self.current_syllabus_id = syllabus.get('syllabus_id')
        status = syllabus.get('status', 'draft').title()
        self.syllabus_status_label.config(text=f"Status: {status} (ID: {self.current_syllabus_id})")

        # Parse content_json
        content_json = syllabus.get('content_json', '{}')
        try:
            content = json.loads(content_json) if isinstance(content_json, str) else content_json
        except (json.JSONDecodeError, TypeError):
            content = {}

        # Build sections from content
        if isinstance(content, dict):
            sections = []
            for key, value in content.items():
                sections.append({'title': key, 'content': value if isinstance(value, str) else str(value)})
        elif isinstance(content, list):
            sections = content
        else:
            sections = [{'title': 'Content', 'content': str(content)}]

        self._build_syllabus_sections(sections)

    def _new_from_template(self):
        """Create a new syllabus from the selected template."""
        module_code = self.syllabus_module_entry.get().strip()
        if not module_code:
            messagebox.showerror("Error", "Module Code is required")
            return

        template_name = self.syllabus_template_combo.get()
        if not template_name or template_name not in self._templates_data:
            messagebox.showerror("Error", "Please select a template")
            return

        template = self._templates_data[template_name]

        # Parse template sections from template content
        template_content = template.get('content_json', template.get('sections_json', '[]'))
        try:
            if isinstance(template_content, str):
                sections_raw = json.loads(template_content)
            else:
                sections_raw = template_content
        except (json.JSONDecodeError, TypeError):
            sections_raw = []

        # Build section structures
        if isinstance(sections_raw, list):
            sections = []
            for s in sections_raw:
                if isinstance(s, dict):
                    sections.append({
                        'title': s.get('title', s.get('name', 'Section')),
                        'content': s.get('default_content', s.get('content', ''))
                    })
                elif isinstance(s, str):
                    sections.append({'title': s, 'content': ''})
        elif isinstance(sections_raw, dict):
            sections = []
            for key, value in sections_raw.items():
                sections.append({'title': key, 'content': value if isinstance(value, str) else ''})
        else:
            sections = [
                {'title': 'Module Information', 'content': ''},
                {'title': 'Learning Outcomes', 'content': ''},
                {'title': 'Assessment Strategy', 'content': ''},
                {'title': 'Teaching Methods', 'content': ''},
                {'title': 'Reading List', 'content': ''},
                {'title': 'Weekly Schedule', 'content': ''},
            ]

        self.current_syllabus_id = None
        self.syllabus_status_label.config(text=f"Status: New (Template: {template_name})")
        self._build_syllabus_sections(sections)

    def _save_syllabus(self):
        """Save the current syllabus content."""
        module_code = self.syllabus_module_entry.get().strip()
        academic_year = self.syllabus_year_entry.get().strip()

        if not module_code:
            messagebox.showerror("Error", "Module Code is required")
            return

        if not academic_year:
            messagebox.showerror("Error", "Academic Year is required")
            return

        if not self.syllabus_widgets:
            messagebox.showerror("Error", "No syllabus content to save")
            return

        # Collect section texts
        content = {}
        for title, widget in self.syllabus_widgets.items():
            content[title] = widget.get("1.0", "end-1c")

        content_json = json.dumps(content, indent=2)

        try:
            if self.current_syllabus_id:
                # Update existing
                CurriculumManager.update_syllabus(
                    self.current_syllabus_id,
                    content_json=content_json
                )
                messagebox.showinfo("Success", "Syllabus updated successfully")
            else:
                # Create new
                template_name = self.syllabus_template_combo.get()
                template_id = None
                if template_name in self._templates_data:
                    template_id = self._templates_data[template_name].get('template_id')

                syllabus_id = CurriculumManager.create_syllabus(
                    module_code=module_code,
                    academic_year=academic_year,
                    content_json=content_json,
                    template_id=template_id,
                    created_by=self._get_user_id()
                )
                self.current_syllabus_id = syllabus_id
                messagebox.showinfo("Success", f"Syllabus created. ID: {syllabus_id}")

            self.syllabus_status_label.config(
                text=f"Status: Draft (ID: {self.current_syllabus_id})"
            )
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _submit_syllabus_for_review(self):
        """Submit the syllabus for review by changing its status."""
        if not self.current_syllabus_id:
            messagebox.showinfo("Info", "Please save the syllabus first")
            return

        if not messagebox.askyesno("Confirm", "Submit this syllabus for review?"):
            return

        try:
            CurriculumManager.update_syllabus(self.current_syllabus_id, status='submitted')
            messagebox.showinfo("Success", "Syllabus submitted for review")
            self.syllabus_status_label.config(
                text=f"Status: Submitted (ID: {self.current_syllabus_id})"
            )
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ==================== TAB 5: APPROVALS (ADMIN) ====================

    def _create_approvals_tab(self):
        """Create the programme approvals tab (admin only)."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Approvals")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Programme Approvals", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text="Refresh", command=self._load_pending_approvals).pack(side=tk.RIGHT)

        # Pending approvals treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        columns = ('ID', 'Programme', 'Code', 'Level', 'Department', 'Approval Level', 'Status')
        self.approvals_tree = ttk.Treeview(
            tree_frame, columns=columns, show='headings', yscrollcommand=y_scroll.set
        )
        y_scroll.config(command=self.approvals_tree.yview)

        widths = {
            'ID': 50, 'Programme': 200, 'Code': 80, 'Level': 110,
            'Department': 130, 'Approval Level': 120, 'Status': 100
        }
        for col in columns:
            self.approvals_tree.heading(col, text=col)
            self.approvals_tree.column(col, width=widths.get(col, 100))

        self.approvals_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.approvals_tree.tag_configure('pending', background='#fff3cd')
        self.approvals_tree.tag_configure('approved', background='#d4edda')
        self.approvals_tree.tag_configure('rejected', background='#f8d7da')

        # Action buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(btn_frame, text="Approve", command=self._approve_programme).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Return for Revision", command=self._return_for_revision).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Reject", command=self._reject_programme).pack(side=tk.LEFT, padx=5)

        self._load_pending_approvals()

    def _load_pending_approvals(self):
        """Load pending programme approvals."""
        for item in self.approvals_tree.get_children():
            self.approvals_tree.delete(item)

        try:
            approvals = CurriculumManager.get_pending_approvals(self._get_user_id())
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load approvals: {e}")
            return

        for a in approvals:
            approval_status = a.get('status', 'pending').lower()
            self.approvals_tree.insert('', tk.END, values=(
                a.get('approval_id'),
                a.get('programme_name', ''),
                a.get('programme_code', ''),
                a.get('level', '').title(),
                a.get('department', ''),
                a.get('approval_level', '').title(),
                a.get('status', '').title()
            ), tags=(approval_status,))

    def _approve_programme(self):
        """Approve the selected programme approval."""
        selection = self.approvals_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select an approval to approve")
            return

        item = self.approvals_tree.item(selection[0])
        approval_id = item['values'][0]
        programme_name = item['values'][1]

        comments = tk.simpledialog.askstring(
            "Comments",
            f"Enter approval comments for '{programme_name}' (optional):",
            parent=self.root
        )

        try:
            CurriculumManager.review_programme(
                approval_id=approval_id,
                reviewer_id=self._get_user_id(),
                status='approved',
                comments=comments or ''
            )
            messagebox.showinfo("Success", "Programme approved")
            self._load_pending_approvals()
            self._load_programmes()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _return_for_revision(self):
        """Return the selected programme for revision."""
        selection = self.approvals_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select an approval to return for revision")
            return

        item = self.approvals_tree.item(selection[0])
        approval_id = item['values'][0]
        programme_name = item['values'][1]

        comments = tk.simpledialog.askstring(
            "Revision Comments",
            f"Enter revision comments for '{programme_name}':",
            parent=self.root
        )

        if not comments:
            messagebox.showerror("Error", "Comments are required when returning for revision")
            return

        try:
            CurriculumManager.review_programme(
                approval_id=approval_id,
                reviewer_id=self._get_user_id(),
                status='revision_required',
                comments=comments
            )
            messagebox.showinfo("Success", "Programme returned for revision")
            self._load_pending_approvals()
            self._load_programmes()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _reject_programme(self):
        """Reject the selected programme approval."""
        selection = self.approvals_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select an approval to reject")
            return

        item = self.approvals_tree.item(selection[0])
        approval_id = item['values'][0]
        programme_name = item['values'][1]

        comments = tk.simpledialog.askstring(
            "Rejection Reason",
            f"Enter rejection reason for '{programme_name}':",
            parent=self.root
        )

        if not comments:
            messagebox.showerror("Error", "Rejection reason is required")
            return

        try:
            CurriculumManager.review_programme(
                approval_id=approval_id,
                reviewer_id=self._get_user_id(),
                status='rejected',
                comments=comments
            )
            messagebox.showinfo("Success", "Programme rejected")
            self._load_pending_approvals()
            self._load_programmes()
        except Exception as e:
            messagebox.showerror("Error", str(e))


# Add simpledialog import for the approval dialogs
try:
    from tkinter import simpledialog
    tk.simpledialog = simpledialog
except ImportError:
    pass
