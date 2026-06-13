"""
Workload Dashboard GUI

Provides interface for:
- Personal workload visualization
- Department workload overview
- Allocation management
- Norm configuration
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from typing import Optional

from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.modules.domain.operations.staff_hr.services.managers.workload_manager import WorkloadManager
from education_system.university_system.modules.domain.operations.staff_hr.gui.validators import (
    FormValidator, ValidationError, validate_entry, validate_number_entry,
    validate_combobox, show_validation_error
)


class WorkloadGUI:
    """GUI for workload dashboard."""

    def __init__(self, root, auth: Optional[UserAuth] = None, parent_notebook: Optional[ttk.Notebook] = None):
        self.root = root
        self.auth = auth
        self.current_user = auth.current_user if auth and auth.current_user else None
        self.parent_notebook = parent_notebook
        self.window = None

        if not self.current_user:
            messagebox.showerror("Error", "Login required to access Workload Dashboard")
            return

        if parent_notebook:
            self.create_as_tab(parent_notebook)
        else:
            self.create_main_window()

    def _get_user_id(self):
        return self.current_user.get('id') or self.current_user.get('username')

    def create_as_tab(self, notebook: ttk.Notebook):
        self.tab_frame = ttk.Frame(notebook)
        notebook.add(self.tab_frame, text="Workload")
        self._build_interface(self.tab_frame)

    def create_main_window(self):
        self.window = tk.Toplevel(self.root)
        self.window.title("Workload Dashboard")
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

        self._create_my_workload_tab()
        self._create_department_tab()

        if self.current_user.get('role') in ['admin', 'Admin', 'administrator', 'staff']:
            self._create_allocations_tab()
            self._create_norms_tab()

    # ==================== TAB 1: MY WORKLOAD ====================

    def _create_my_workload_tab(self):
        """Create the personal workload visualization tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="My Workload")

        # Header frame with academic year entry and refresh button
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text="My Workload", style='Header.TLabel').pack(side=tk.LEFT)

        controls_frame = ttk.Frame(header_frame)
        controls_frame.pack(side=tk.RIGHT)

        ttk.Label(controls_frame, text="Academic Year:").pack(side=tk.LEFT, padx=(0, 5))
        self.my_year_entry = ttk.Entry(controls_frame, width=10)
        self.my_year_entry.insert(0, "2025/26")
        self.my_year_entry.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(controls_frame, text="Refresh", command=self._refresh_my_workload).pack(side=tk.LEFT, padx=5)

        # Canvas-based horizontal stacked bar chart
        chart_frame = ttk.LabelFrame(tab, text="Workload Distribution", padding=5)
        chart_frame.pack(fill=tk.X, padx=10, pady=5)

        self.chart_canvas = tk.Canvas(chart_frame, height=80, bg='white', highlightthickness=0)
        self.chart_canvas.pack(fill=tk.X, padx=5, pady=5)
        self.chart_canvas.bind('<Configure>', lambda e: self._draw_workload_chart())

        # Internal state for chart data
        self._workload_summary = {}
        self._balance_analysis = {}

        # Balance analysis section
        balance_frame = ttk.LabelFrame(tab, text="Balance Analysis", padding=10)
        balance_frame.pack(fill=tk.X, padx=10, pady=5)

        balance_tree_frame = ttk.Frame(balance_frame)
        balance_tree_frame.pack(fill=tk.X)

        balance_columns = ('Type', 'Actual Hours', 'Actual %', 'Norm %', 'Difference')
        self.balance_tree = ttk.Treeview(balance_tree_frame, columns=balance_columns,
                                         show='headings', height=4)

        col_widths = {'Type': 120, 'Actual Hours': 120, 'Actual %': 100,
                      'Norm %': 100, 'Difference': 120}
        for col in balance_columns:
            self.balance_tree.heading(col, text=col)
            self.balance_tree.column(col, width=col_widths.get(col, 100), anchor=tk.CENTER)

        self.balance_tree.tag_configure('imbalanced', foreground='red')
        self.balance_tree.tag_configure('balanced', foreground='black')

        self.balance_tree.pack(fill=tk.X)

        # Allocations treeview
        alloc_frame = ttk.LabelFrame(tab, text="My Allocations", padding=5)
        alloc_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        alloc_tree_frame = ttk.Frame(alloc_frame)
        alloc_tree_frame.pack(fill=tk.BOTH, expand=True)

        y_scroll = ttk.Scrollbar(alloc_tree_frame, orient=tk.VERTICAL)

        alloc_columns = ('ID', 'Activity', 'Type', 'Hours/Week', 'Weight', 'Weighted Hours')
        self.my_alloc_tree = ttk.Treeview(alloc_tree_frame, columns=alloc_columns,
                                          show='headings', yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.my_alloc_tree.yview)

        alloc_col_widths = {'ID': 60, 'Activity': 200, 'Type': 100,
                            'Hours/Week': 100, 'Weight': 80, 'Weighted Hours': 120}
        for col in alloc_columns:
            self.my_alloc_tree.heading(col, text=col)
            self.my_alloc_tree.column(col, width=alloc_col_widths.get(col, 100), anchor=tk.CENTER)

        self.my_alloc_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Load initial data
        self._refresh_my_workload()

    def _draw_workload_chart(self):
        """Draw a horizontal stacked bar chart on the canvas."""
        self.chart_canvas.delete('all')
        w = self.chart_canvas.winfo_width() or 800
        h = 60
        bar_y = 10
        bar_h = 40

        summary = self._workload_summary or {}
        total = summary.get('total_hours', 0) or 1

        colors = {
            'teaching': '#27ae60', 'research': '#2980b9',
            'admin': '#95a5a6', 'service': '#e67e22'
        }

        x = 20
        max_w = w - 40
        for activity_type in ['teaching', 'research', 'admin', 'service']:
            hours = summary.get(activity_type, 0)
            seg_w = (hours / total) * max_w if total > 0 else 0
            if seg_w > 0:
                self.chart_canvas.create_rectangle(
                    x, bar_y, x + seg_w, bar_y + bar_h,
                    fill=colors[activity_type], outline='white'
                )
                if seg_w > 30:
                    self.chart_canvas.create_text(
                        x + seg_w / 2, bar_y + bar_h / 2,
                        text=f"{hours:.0f}h", fill='white', font=('Arial', 9, 'bold')
                    )
                x += seg_w

        # Draw norm target line if norm data is available
        norm = self._balance_analysis.get('norm')
        if norm:
            norm_total = norm.get('total_hours_per_week', 0)
            if norm_total > 0 and total > 0:
                # Scale the norm line relative to actual total
                norm_x = 20 + (norm_total / total) * max_w
                if 20 < norm_x < w - 20:
                    self.chart_canvas.create_line(
                        norm_x, bar_y - 5, norm_x, bar_y + bar_h + 5,
                        fill='red', width=2, dash=(4, 2)
                    )
                    self.chart_canvas.create_text(
                        norm_x, bar_y - 8, text=f"Norm: {norm_total}h",
                        fill='red', font=('Arial', 7), anchor='s'
                    )

        # Legend
        legend_x = 20
        legend_y = bar_y + bar_h + 8
        for activity_type, color in colors.items():
            self.chart_canvas.create_rectangle(
                legend_x, legend_y, legend_x + 12, legend_y + 12, fill=color
            )
            self.chart_canvas.create_text(
                legend_x + 16, legend_y + 6, text=activity_type.title(),
                anchor='w', font=('Arial', 8)
            )
            legend_x += 100

    def _refresh_my_workload(self):
        """Refresh the My Workload tab data."""
        try:
            user_id = self._get_user_id()
            academic_year = self.my_year_entry.get().strip()

            # Get workload summary
            self._workload_summary = WorkloadManager.get_user_workload_summary(
                user_id, academic_year
            )

            # Get balance analysis
            self._balance_analysis = WorkloadManager.get_balance_analysis(
                user_id, academic_year
            )

            # Redraw chart
            self._draw_workload_chart()

            # Populate balance analysis treeview
            self.balance_tree.delete(*self.balance_tree.get_children())
            comparison = self._balance_analysis.get('comparison', {})
            for activity_type in ['teaching', 'research', 'admin', 'service']:
                data = comparison.get(activity_type, {})
                actual_hours = data.get('actual_hours', 0)
                actual_pct = data.get('actual_pct', 0)
                norm_pct = data.get('norm_pct', 0)
                difference = data.get('difference', 0)
                is_imbalanced = data.get('is_imbalanced', False)

                tag = 'imbalanced' if is_imbalanced else 'balanced'
                diff_str = f"{difference:+.1f}%"

                self.balance_tree.insert('', 'end', values=(
                    activity_type.title(),
                    f"{actual_hours:.1f}",
                    f"{actual_pct:.1f}%",
                    f"{norm_pct:.1f}%",
                    diff_str
                ), tags=(tag,))

            # Populate allocations treeview
            self.my_alloc_tree.delete(*self.my_alloc_tree.get_children())
            allocations = WorkloadManager.get_user_allocations(user_id, academic_year)
            for alloc in allocations:
                self.my_alloc_tree.insert('', 'end', values=(
                    alloc.get('allocation_id', ''),
                    alloc.get('activity_name', ''),
                    alloc.get('activity_type', '').title(),
                    f"{alloc.get('hours_per_week', 0):.1f}",
                    f"{alloc.get('weighting_factor', 1.0):.2f}",
                    f"{alloc.get('weighted_hours', 0):.1f}"
                ))

            self._update_status(
                f"Loaded workload for {user_id} - "
                f"Total: {self._workload_summary.get('total_hours', 0):.1f}h, "
                f"{self._workload_summary.get('allocation_count', 0)} allocations"
            )

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load workload data: {e}")

    # ==================== TAB 2: DEPARTMENT VIEW ====================

    def _create_department_tab(self):
        """Create the department workload overview tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Department View")

        # Header frame
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text="Department Workload Overview",
                  style='Header.TLabel').pack(side=tk.LEFT)

        # Controls frame
        controls_frame = ttk.Frame(tab)
        controls_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(controls_frame, text="Department:").pack(side=tk.LEFT, padx=(0, 5))
        self.dept_entry = ttk.Entry(controls_frame, width=20)
        self.dept_entry.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(controls_frame, text="Academic Year:").pack(side=tk.LEFT, padx=(0, 5))
        self.dept_year_entry = ttk.Entry(controls_frame, width=10)
        self.dept_year_entry.insert(0, "2025/26")
        self.dept_year_entry.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(controls_frame, text="View", command=self._load_department_workloads).pack(
            side=tk.LEFT, padx=5)

        # Staff workload treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        x_scroll = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL)

        dept_columns = ('User ID', 'Teaching', 'Research', 'Admin', 'Service', 'Total')
        self.dept_tree = ttk.Treeview(tree_frame, columns=dept_columns, show='headings',
                                      yscrollcommand=y_scroll.set,
                                      xscrollcommand=x_scroll.set)

        y_scroll.config(command=self.dept_tree.yview)
        x_scroll.config(command=self.dept_tree.xview)

        dept_col_widths = {'User ID': 150, 'Teaching': 100, 'Research': 100,
                           'Admin': 100, 'Service': 100, 'Total': 100}
        for col in dept_columns:
            self.dept_tree.heading(col, text=col)
            self.dept_tree.column(col, width=dept_col_widths.get(col, 100), anchor=tk.CENTER)

        self.dept_tree.tag_configure('imbalanced', background='#f8d7da')
        self.dept_tree.tag_configure('balanced', background='')

        self.dept_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        x_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        # Summary label
        self.dept_summary_label = ttk.Label(tab, text="Enter a department name and click View.")
        self.dept_summary_label.pack(fill=tk.X, padx=10, pady=5)

    def _load_department_workloads(self):
        """Load and display department workload data."""
        try:
            department = self.dept_entry.get().strip()
            if not department:
                messagebox.showwarning("Warning", "Please enter a department name.")
                return

            academic_year = self.dept_year_entry.get().strip() or None

            self.dept_tree.delete(*self.dept_tree.get_children())

            workloads = WorkloadManager.get_department_workloads(department, academic_year)

            if not workloads:
                self.dept_summary_label.config(
                    text=f"No workload data found for department: {department}")
                return

            for wl in workloads:
                teaching = wl.get('teaching', 0)
                research = wl.get('research', 0)
                admin = wl.get('admin', 0)
                service = wl.get('service', 0)
                total = wl.get('total_hours', 0)

                # Check if any type appears imbalanced (> 60% or total very uneven)
                is_imbalanced = False
                if total > 0:
                    for hours in [teaching, research, admin, service]:
                        pct = (hours / total) * 100 if total > 0 else 0
                        if pct > 60:
                            is_imbalanced = True
                            break

                tag = 'imbalanced' if is_imbalanced else 'balanced'

                self.dept_tree.insert('', 'end', values=(
                    wl.get('user_id', ''),
                    f"{teaching:.1f}",
                    f"{research:.1f}",
                    f"{admin:.1f}",
                    f"{service:.1f}",
                    f"{total:.1f}"
                ), tags=(tag,))

            self.dept_summary_label.config(
                text=f"Showing {len(workloads)} staff member(s) in {department}")
            self._update_status(f"Loaded department workloads for {department}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load department workloads: {e}")

    # ==================== TAB 3: ALLOCATIONS (ADMIN) ====================

    def _create_allocations_tab(self):
        """Create the allocation management tab (admin/staff only)."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Allocations")

        # Header frame
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text="Workload Allocations",
                  style='Header.TLabel').pack(side=tk.LEFT)

        # Controls frame: User ID + Academic Year + Load button
        controls_frame = ttk.Frame(tab)
        controls_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(controls_frame, text="User ID:").pack(side=tk.LEFT, padx=(0, 5))
        self.alloc_user_entry = ttk.Entry(controls_frame, width=20)
        self.alloc_user_entry.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(controls_frame, text="Academic Year:").pack(side=tk.LEFT, padx=(0, 5))
        self.alloc_year_entry = ttk.Entry(controls_frame, width=10)
        self.alloc_year_entry.insert(0, "2025/26")
        self.alloc_year_entry.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(controls_frame, text="Load", command=self._load_allocations).pack(
            side=tk.LEFT, padx=5)

        # Action buttons frame
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(btn_frame, text="Add Allocation",
                   command=self._show_add_allocation_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Remove Selected",
                   command=self._remove_selected_allocation).pack(side=tk.LEFT, padx=5)

        # Allocations treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)

        alloc_columns = ('ID', 'Activity', 'Type', 'Hours', 'Weight', 'Weighted')
        self.admin_alloc_tree = ttk.Treeview(tree_frame, columns=alloc_columns,
                                             show='headings',
                                             yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.admin_alloc_tree.yview)

        admin_col_widths = {'ID': 60, 'Activity': 200, 'Type': 100,
                            'Hours': 100, 'Weight': 80, 'Weighted': 120}
        for col in alloc_columns:
            self.admin_alloc_tree.heading(col, text=col)
            self.admin_alloc_tree.column(col, width=admin_col_widths.get(col, 100),
                                         anchor=tk.CENTER)

        self.admin_alloc_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Summary label
        self.alloc_summary_label = ttk.Label(tab, text="Enter a User ID and click Load.")
        self.alloc_summary_label.pack(fill=tk.X, padx=10, pady=5)

    def _load_allocations(self):
        """Load allocations for the specified user and academic year."""
        try:
            user_id = self.alloc_user_entry.get().strip()
            if not user_id:
                messagebox.showwarning("Warning", "Please enter a User ID.")
                return

            academic_year = self.alloc_year_entry.get().strip() or None

            self.admin_alloc_tree.delete(*self.admin_alloc_tree.get_children())

            allocations = WorkloadManager.get_user_allocations(user_id, academic_year)

            for alloc in allocations:
                self.admin_alloc_tree.insert('', 'end', values=(
                    alloc.get('allocation_id', ''),
                    alloc.get('activity_name', ''),
                    alloc.get('activity_type', '').title(),
                    f"{alloc.get('hours_per_week', 0):.1f}",
                    f"{alloc.get('weighting_factor', 1.0):.2f}",
                    f"{alloc.get('weighted_hours', 0):.1f}"
                ))

            total_weighted = sum(
                a.get('weighted_hours', 0) for a in allocations
            )
            self.alloc_summary_label.config(
                text=f"{len(allocations)} allocation(s) for {user_id} - "
                     f"Total weighted hours: {total_weighted:.1f}"
            )
            self._update_status(f"Loaded {len(allocations)} allocations for {user_id}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load allocations: {e}")

    def _show_add_allocation_dialog(self):
        """Show dialog to add a new workload allocation."""
        user_id = self.alloc_user_entry.get().strip()
        if not user_id:
            messagebox.showwarning("Warning", "Please enter a User ID first.")
            return

        academic_year = self.alloc_year_entry.get().strip()
        if not academic_year:
            messagebox.showwarning("Warning", "Please enter an Academic Year first.")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Add Workload Allocation")
        dialog.geometry("450x450")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Add Workload Allocation",
                  font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Info labels
        info_frame = ttk.Frame(main_frame)
        info_frame.pack(fill=tk.X, pady=5)
        ttk.Label(info_frame, text=f"User: {user_id}  |  Year: {academic_year}",
                  font=('Arial', 9, 'italic')).pack(anchor=tk.W)

        # Activity Name
        name_frame = ttk.Frame(main_frame)
        name_frame.pack(fill=tk.X, pady=5)
        ttk.Label(name_frame, text="Activity Name:", width=18, anchor=tk.W).pack(side=tk.LEFT)
        name_entry = ttk.Entry(name_frame, width=25)
        name_entry.pack(side=tk.LEFT, padx=5)

        # Activity Type
        type_frame = ttk.Frame(main_frame)
        type_frame.pack(fill=tk.X, pady=5)
        ttk.Label(type_frame, text="Activity Type:", width=18, anchor=tk.W).pack(side=tk.LEFT)
        type_combo = ttk.Combobox(type_frame,
                                  values=['teaching', 'research', 'admin', 'service'],
                                  width=22, state='readonly')
        type_combo.pack(side=tk.LEFT, padx=5)

        # Hours per Week
        hours_frame = ttk.Frame(main_frame)
        hours_frame.pack(fill=tk.X, pady=5)
        ttk.Label(hours_frame, text="Hours/Week:", width=18, anchor=tk.W).pack(side=tk.LEFT)
        hours_entry = ttk.Entry(hours_frame, width=25)
        hours_entry.insert(0, "0")
        hours_entry.pack(side=tk.LEFT, padx=5)

        # Weighting Factor
        weight_frame = ttk.Frame(main_frame)
        weight_frame.pack(fill=tk.X, pady=5)
        ttk.Label(weight_frame, text="Weighting Factor:", width=18, anchor=tk.W).pack(side=tk.LEFT)
        weight_entry = ttk.Entry(weight_frame, width=25)
        weight_entry.insert(0, "1.0")
        weight_entry.pack(side=tk.LEFT, padx=5)

        # Semester
        sem_frame = ttk.Frame(main_frame)
        sem_frame.pack(fill=tk.X, pady=5)
        ttk.Label(sem_frame, text="Semester:", width=18, anchor=tk.W).pack(side=tk.LEFT)
        sem_entry = ttk.Entry(sem_frame, width=25)
        sem_entry.pack(side=tk.LEFT, padx=5)

        # Notes
        notes_frame = ttk.Frame(main_frame)
        notes_frame.pack(fill=tk.X, pady=5)
        ttk.Label(notes_frame, text="Notes:", width=18, anchor=tk.W).pack(side=tk.LEFT)
        notes_entry = ttk.Entry(notes_frame, width=25)
        notes_entry.pack(side=tk.LEFT, padx=5)

        # Error label
        error_label = ttk.Label(main_frame, text="", foreground='red')
        error_label.pack(fill=tk.X, pady=5)

        def save_allocation():
            try:
                # Validate using the imported validators
                activity_name = validate_entry(name_entry, "Activity Name")
                activity_type = validate_combobox(type_combo, "Activity Type")
                hours = validate_number_entry(hours_entry, "Hours/Week",
                                              min_value=0, max_value=168)
                weight = validate_number_entry(weight_entry, "Weighting Factor",
                                               min_value=0.01, max_value=10.0)
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            semester = sem_entry.get().strip() or None
            notes = notes_entry.get().strip() or None
            created_by = self._get_user_id()

            try:
                WorkloadManager.add_allocation(
                    user_id=user_id,
                    academic_year=academic_year,
                    activity_name=activity_name,
                    activity_type=activity_type,
                    hours_per_week=hours,
                    weighting_factor=weight,
                    semester=semester,
                    notes=notes,
                    created_by=created_by
                )

                messagebox.showinfo("Success", "Allocation added successfully!", parent=dialog)
                dialog.destroy()
                self._load_allocations()

            except Exception as e:
                error_label.config(text=f"Error: {str(e)}")

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=15)
        ttk.Button(btn_frame, text="Save", command=save_allocation).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=10)

    def _remove_selected_allocation(self):
        """Remove the selected allocation from the treeview and database."""
        selection = self.admin_alloc_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an allocation to remove.")
            return

        item = self.admin_alloc_tree.item(selection[0])
        allocation_id = item['values'][0]
        activity_name = item['values'][1]

        if not messagebox.askyesno(
            "Confirm Removal",
            f"Are you sure you want to remove allocation '{activity_name}' (ID: {allocation_id})?"
        ):
            return

        try:
            WorkloadManager.remove_allocation(int(allocation_id))
            messagebox.showinfo("Success", "Allocation removed successfully!")
            self._load_allocations()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to remove allocation: {e}")

    # ==================== TAB 4: NORMS (ADMIN) ====================

    def _create_norms_tab(self):
        """Create the workload norms configuration tab (admin/staff only)."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Norms")

        # Header frame
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text="Workload Norms Configuration",
                  style='Header.TLabel').pack(side=tk.LEFT)

        ttk.Button(header_frame, text="Refresh", command=self._load_norms).pack(
            side=tk.RIGHT, padx=5)

        # Action buttons frame
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(btn_frame, text="Add Norm",
                   command=self._show_add_norm_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Edit Selected",
                   command=self._show_edit_norm_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Delete Selected",
                   command=self._delete_selected_norm).pack(side=tk.LEFT, padx=5)

        # Norms treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)

        norm_columns = ('ID', 'Name', 'Teaching%', 'Research%', 'Admin%',
                        'Service%', 'Hours/Week')
        self.norms_tree = ttk.Treeview(tree_frame, columns=norm_columns,
                                       show='headings',
                                       yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.norms_tree.yview)

        norm_col_widths = {'ID': 50, 'Name': 180, 'Teaching%': 90, 'Research%': 90,
                           'Admin%': 80, 'Service%': 90, 'Hours/Week': 100}
        for col in norm_columns:
            self.norms_tree.heading(col, text=col)
            self.norms_tree.column(col, width=norm_col_widths.get(col, 80), anchor=tk.CENTER)

        self.norms_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind double-click to edit
        self.norms_tree.bind('<Double-1>', lambda e: self._show_edit_norm_dialog())

        # Summary label
        self.norms_summary_label = ttk.Label(tab, text="")
        self.norms_summary_label.pack(fill=tk.X, padx=10, pady=5)

        # Load initial data
        self._load_norms()

    def _load_norms(self):
        """Load all workload norms into the treeview."""
        try:
            self.norms_tree.delete(*self.norms_tree.get_children())

            norms = WorkloadManager.get_norms()

            for norm in norms:
                self.norms_tree.insert('', 'end', values=(
                    norm.get('norm_id', ''),
                    norm.get('name', ''),
                    f"{norm.get('teaching_pct', 0)}%",
                    f"{norm.get('research_pct', 0)}%",
                    f"{norm.get('admin_pct', 0)}%",
                    f"{norm.get('service_pct', 0)}%",
                    norm.get('total_hours_per_week', 40)
                ))

            self.norms_summary_label.config(text=f"{len(norms)} norm(s) configured")
            self._update_status(f"Loaded {len(norms)} workload norms")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load norms: {e}")

    def _show_add_norm_dialog(self):
        """Show dialog to add a new workload norm."""
        self._show_norm_dialog(mode='add')

    def _show_edit_norm_dialog(self):
        """Show dialog to edit the selected workload norm."""
        selection = self.norms_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a norm to edit.")
            return

        item = self.norms_tree.item(selection[0])
        norm_id = item['values'][0]

        try:
            norm_data = WorkloadManager.get_norm(int(norm_id))
            if not norm_data:
                messagebox.showerror("Error", f"Norm ID {norm_id} not found.")
                return
            self._show_norm_dialog(mode='edit', norm_data=norm_data)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load norm: {e}")

    def _show_norm_dialog(self, mode='add', norm_data=None):
        """Show add/edit norm dialog.

        Args:
            mode: 'add' or 'edit'
            norm_data: Existing norm dict when editing
        """
        dialog = tk.Toplevel(self.root)
        title = "Add Workload Norm" if mode == 'add' else "Edit Workload Norm"
        dialog.title(title)
        dialog.geometry("450x520")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=title,
                  font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Name
        name_frame = ttk.Frame(main_frame)
        name_frame.pack(fill=tk.X, pady=5)
        ttk.Label(name_frame, text="Name:", width=18, anchor=tk.W).pack(side=tk.LEFT)
        name_entry = ttk.Entry(name_frame, width=25)
        if norm_data:
            name_entry.insert(0, norm_data.get('name', ''))
        name_entry.pack(side=tk.LEFT, padx=5)

        # Department
        dept_frame = ttk.Frame(main_frame)
        dept_frame.pack(fill=tk.X, pady=5)
        ttk.Label(dept_frame, text="Department:", width=18, anchor=tk.W).pack(side=tk.LEFT)
        dept_entry = ttk.Entry(dept_frame, width=25)
        if norm_data and norm_data.get('department'):
            dept_entry.insert(0, norm_data['department'])
        dept_entry.pack(side=tk.LEFT, padx=5)

        # Role
        role_frame = ttk.Frame(main_frame)
        role_frame.pack(fill=tk.X, pady=5)
        ttk.Label(role_frame, text="Role:", width=18, anchor=tk.W).pack(side=tk.LEFT)
        role_entry = ttk.Entry(role_frame, width=25)
        if norm_data and norm_data.get('role'):
            role_entry.insert(0, norm_data['role'])
        role_entry.pack(side=tk.LEFT, padx=5)

        # Teaching %
        teaching_frame = ttk.Frame(main_frame)
        teaching_frame.pack(fill=tk.X, pady=5)
        ttk.Label(teaching_frame, text="Teaching %:", width=18, anchor=tk.W).pack(side=tk.LEFT)
        teaching_entry = ttk.Entry(teaching_frame, width=25)
        teaching_entry.insert(0, str(norm_data.get('teaching_pct', 40)) if norm_data else "40")
        teaching_entry.pack(side=tk.LEFT, padx=5)

        # Research %
        research_frame = ttk.Frame(main_frame)
        research_frame.pack(fill=tk.X, pady=5)
        ttk.Label(research_frame, text="Research %:", width=18, anchor=tk.W).pack(side=tk.LEFT)
        research_entry = ttk.Entry(research_frame, width=25)
        research_entry.insert(0, str(norm_data.get('research_pct', 40)) if norm_data else "40")
        research_entry.pack(side=tk.LEFT, padx=5)

        # Admin %
        admin_frame = ttk.Frame(main_frame)
        admin_frame.pack(fill=tk.X, pady=5)
        ttk.Label(admin_frame, text="Admin %:", width=18, anchor=tk.W).pack(side=tk.LEFT)
        admin_entry = ttk.Entry(admin_frame, width=25)
        admin_entry.insert(0, str(norm_data.get('admin_pct', 10)) if norm_data else "10")
        admin_entry.pack(side=tk.LEFT, padx=5)

        # Service %
        service_frame = ttk.Frame(main_frame)
        service_frame.pack(fill=tk.X, pady=5)
        ttk.Label(service_frame, text="Service %:", width=18, anchor=tk.W).pack(side=tk.LEFT)
        service_entry = ttk.Entry(service_frame, width=25)
        service_entry.insert(0, str(norm_data.get('service_pct', 10)) if norm_data else "10")
        service_entry.pack(side=tk.LEFT, padx=5)

        # Total Hours per Week
        hours_frame = ttk.Frame(main_frame)
        hours_frame.pack(fill=tk.X, pady=5)
        ttk.Label(hours_frame, text="Total Hours/Week:", width=18, anchor=tk.W).pack(side=tk.LEFT)
        hours_entry = ttk.Entry(hours_frame, width=25)
        hours_entry.insert(0, str(norm_data.get('total_hours_per_week', 40)) if norm_data else "40")
        hours_entry.pack(side=tk.LEFT, padx=5)

        # Is Default checkbox
        default_var = tk.BooleanVar(
            value=bool(norm_data.get('is_default', False)) if norm_data else False
        )
        default_frame = ttk.Frame(main_frame)
        default_frame.pack(fill=tk.X, pady=5)
        ttk.Label(default_frame, text="", width=18).pack(side=tk.LEFT)
        ttk.Checkbutton(default_frame, text="Set as Default Norm",
                        variable=default_var).pack(side=tk.LEFT, padx=5)

        # Error label
        error_label = ttk.Label(main_frame, text="", foreground='red')
        error_label.pack(fill=tk.X, pady=5)

        def save_norm():
            try:
                name = validate_entry(name_entry, "Name")
                teaching_pct = validate_number_entry(
                    teaching_entry, "Teaching %", min_value=0, max_value=100)
                research_pct = validate_number_entry(
                    research_entry, "Research %", min_value=0, max_value=100)
                admin_pct = validate_number_entry(
                    admin_entry, "Admin %", min_value=0, max_value=100)
                service_pct = validate_number_entry(
                    service_entry, "Service %", min_value=0, max_value=100)
                total_hours = validate_number_entry(
                    hours_entry, "Total Hours/Week", min_value=1, max_value=168)
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            # Validate percentages sum to 100
            pct_sum = teaching_pct + research_pct + admin_pct + service_pct
            if abs(pct_sum - 100) > 0.1:
                messagebox.showwarning(
                    "Validation Warning",
                    f"Percentages sum to {pct_sum:.1f}% instead of 100%. "
                    "Consider adjusting.",
                    parent=dialog
                )

            department = dept_entry.get().strip() or None
            role = role_entry.get().strip() or None
            is_default = default_var.get()

            try:
                if mode == 'add':
                    WorkloadManager.create_norm(
                        name=name,
                        teaching_pct=int(teaching_pct),
                        research_pct=int(research_pct),
                        admin_pct=int(admin_pct),
                        service_pct=int(service_pct),
                        total_hours_per_week=int(total_hours),
                        department=department,
                        role=role,
                        is_default=is_default
                    )
                    messagebox.showinfo("Success", "Norm created successfully!",
                                        parent=dialog)
                else:
                    norm_id = norm_data['norm_id']
                    WorkloadManager.update_norm(
                        norm_id,
                        name=name,
                        teaching_pct=int(teaching_pct),
                        research_pct=int(research_pct),
                        admin_pct=int(admin_pct),
                        service_pct=int(service_pct),
                        total_hours_per_week=int(total_hours),
                        department=department,
                        role=role,
                        is_default=int(is_default)
                    )
                    messagebox.showinfo("Success", "Norm updated successfully!",
                                        parent=dialog)

                dialog.destroy()
                self._load_norms()

            except Exception as e:
                error_label.config(text=f"Error: {str(e)}")

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=15)
        save_text = "Save" if mode == 'add' else "Update"
        ttk.Button(btn_frame, text=save_text, command=save_norm).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=10)

    def _delete_selected_norm(self):
        """Delete the selected workload norm."""
        selection = self.norms_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a norm to delete.")
            return

        item = self.norms_tree.item(selection[0])
        norm_id = item['values'][0]
        norm_name = item['values'][1]

        if not messagebox.askyesno(
            "Confirm Deletion",
            f"Are you sure you want to delete norm '{norm_name}' (ID: {norm_id})?"
        ):
            return

        try:
            WorkloadManager.delete_norm(int(norm_id))
            messagebox.showinfo("Success", "Norm deleted successfully!")
            self._load_norms()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete norm: {e}")

    # ==================== UTILITY METHODS ====================

    def _update_status(self, message: str):
        """Update status bar message."""
        if hasattr(self, 'status_bar') and self.status_bar:
            self.status_bar.config(text=message)


def launch_workload_gui(root, auth):
    """Launch Workload Dashboard GUI."""
    try:
        return WorkloadGUI(root, auth)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to launch Workload Dashboard: {e}")
        return None
