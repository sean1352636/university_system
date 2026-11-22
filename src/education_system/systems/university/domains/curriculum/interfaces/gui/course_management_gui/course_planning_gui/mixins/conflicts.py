"""Split from course_planning_gui.py — provides mixins assembled in
course_planning_gui/__init__.py into the final CoursePlanningGUI class."""
from __future__ import annotations

from education_system.systems.university.infrastructure.i18n import get_text as _t

import json
import logging
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from typing import Optional, Dict, List

from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.domains.curriculum.domain.course_planning.services.planning_service import PlanningService
from education_system.systems.university.domains.assessment.domain.grading.grade_calculation.gpa import calculate_student_gpa
from education_system.systems.university.infrastructure.activity_logger import log_activity


class _ConflictsMixin:
    """Methods extracted from CoursePlanningGUI.conflicts responsibility."""

    def _create_conflicts_tab(self):
        """Add the conflicts tab frame (content built lazily on first view)."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t('gui.academics.course_management_gui.course_planning_gui.mixins.conflicts.tabs.conflicts', default="Conflicts"))
        self._register_lazy_tab(tab, self._populate_conflicts_tab)

    def _populate_conflicts_tab(self, tab):
        """Build the conflicts tab's content."""
        # Control panel
        control_frame = ttk.Frame(tab)
        control_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(control_frame, text=_t('gui.academics.course_management_gui.course_planning_gui.mixins.conflicts.buttons.detect_conflicts', default="Detect Conflicts"),
                  command=self._detect_conflicts).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text=_t('gui.academics.course_management_gui.course_planning_gui.mixins.conflicts.buttons.refresh', default="Refresh"),
                  command=self._detect_conflicts).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text=_t('gui.academics.course_management_gui.course_planning_gui.mixins.conflicts.buttons.export_report', default="Export Report"),
                  command=self._export_conflicts_report).pack(side=tk.LEFT, padx=5)

        # Conflicts display
        conflicts_frame = ttk.LabelFrame(tab, text=_t('gui.academics.course_management_gui.course_planning_gui.mixins.conflicts.labels.detected_conflicts', default="Detected Conflicts"), padding=10)
        conflicts_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create treeview for conflicts
        columns = ('Severity', 'Type', 'Semester', 'Description')
        self.conflicts_tree = ttk.Treeview(conflicts_frame, columns=columns, show='tree headings', height=20)

        self.conflicts_tree.heading('Severity', text=_t('gui.academics.course_management_gui.course_planning_gui.mixins.conflicts.headings.severity', default='Severity'))
        self.conflicts_tree.heading('Type', text=_t('gui.academics.course_management_gui.course_planning_gui.mixins.conflicts.headings.type', default='Type'))
        self.conflicts_tree.heading('Semester', text=_t('gui.academics.course_management_gui.course_planning_gui.mixins.conflicts.headings.semester', default='Semester'))
        self.conflicts_tree.heading('Description', text=_t('gui.academics.course_management_gui.course_planning_gui.mixins.conflicts.headings.description', default='Description'))

        self.conflicts_tree.column('Severity', width=100)
        self.conflicts_tree.column('Type', width=150)
        self.conflicts_tree.column('Semester', width=100)
        self.conflicts_tree.column('Description', width=500)

        self.conflicts_tree.pack(fill=tk.BOTH, expand=True)

        # Scrollbar
        conflicts_scrollbar = ttk.Scrollbar(conflicts_frame, orient=tk.VERTICAL, command=self.conflicts_tree.yview)
        conflicts_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.conflicts_tree.configure(yscrollcommand=conflicts_scrollbar.set)

        # Details panel
        details_frame = ttk.LabelFrame(tab, text=_t('gui.academics.course_management_gui.course_planning_gui.mixins.conflicts.labels.suggestions', default="Suggestions"), padding=10)
        details_frame.pack(fill=tk.X, padx=10, pady=10)

        self.conflict_details_text = scrolledtext.ScrolledText(details_frame, wrap=tk.WORD,
                                                               font=('Arial', 10), height=6)
        self.conflict_details_text.pack(fill=tk.BOTH, expand=True)

        self.conflicts_tree.bind('<<TreeviewSelect>>', self._on_conflict_select)

    # ===== Event Handlers =====

    def _detect_conflicts(self):
        """Detect schedule conflicts."""
        if not self.current_plan_id:
            messagebox.showwarning(_t('gui.academics.course_management_gui.course_planning_gui.mixins.conflicts.dialogs.warning', default="Warning"), _t('gui.academics.course_management_gui.course_planning_gui.mixins.conflicts.dialogs.please_load_a_plan_first', default="Please load a plan first."))
            return

        try:
            conflicts = self.planning_service.detect_plan_schedule_conflicts(self.current_plan_id)

            # Clear tree
            for item in self.conflicts_tree.get_children():
                self.conflicts_tree.delete(item)

            if not conflicts:
                self.conflicts_tree.insert('', tk.END, text="✓ No conflicts detected!")
                self.conflict_details_text.delete(1.0, tk.END)
                self.conflict_details_text.insert(tk.END, "Your schedule looks good!")
                return

            # Populate tree with conflicts
            for conflict in conflicts:
                severity_icon = {
                    'High': '🔴',
                    'Medium': '🟡',
                    'Low': '🟢'
                }.get(conflict['severity'], '')

                self.conflicts_tree.insert('', tk.END, values=(
                    f"{severity_icon} {conflict['severity']}",
                    conflict['type'],
                    conflict.get('semester', 'N/A'),
                    conflict['description']
                ), tags=(conflict['severity'],))

            # Configure tags for coloring
            self.conflicts_tree.tag_configure('High', foreground='red')
            self.conflicts_tree.tag_configure('Medium', foreground='orange')
            self.conflicts_tree.tag_configure('Low', foreground='blue')

            self.status_bar.config(text=f"Detected {len(conflicts)} conflict(s)")

        except Exception as e:
            messagebox.showerror(_t('gui.academics.course_management_gui.course_planning_gui.mixins.conflicts.dialogs.error', default="Error"), f"Failed to detect conflicts: {e}")

    def _on_conflict_select(self, event):
        """Handle conflict selection to show suggestions."""
        selection = self.conflicts_tree.selection()
        if not selection:
            return

        # Get conflict data (would need to store this)
        # For now, show generic message
        self.conflict_details_text.delete(1.0, tk.END)
        self.conflict_details_text.insert(tk.END, "Suggestions:\n\n")
        self.conflict_details_text.insert(tk.END, "• Review the affected courses\n")
        self.conflict_details_text.insert(tk.END, "• Consider moving courses to different semesters\n")
        self.conflict_details_text.insert(tk.END, "• Check prerequisite requirements\n")

    def _export_conflicts_report(self):
        """Export conflicts report."""
        if not self.current_plan_id:
            messagebox.showwarning(_t('gui.academics.course_management_gui.course_planning_gui.mixins.conflicts.dialogs.warning', default="Warning"), _t('gui.academics.course_management_gui.course_planning_gui.mixins.conflicts.dialogs.please_load_a_plan_first', default="Please load a plan first."))
            return

        try:
            conflicts = self.planning_service.get_plan_conflicts(self.current_plan_id)

            filename = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                initialfile=f"conflicts_report_plan_{self.current_plan_id}.json"
            )

            if not filename:
                return

            with open(filename, 'w') as f:
                json.dump(conflicts, f, indent=2, default=str)

            messagebox.showinfo(_t('gui.academics.course_management_gui.course_planning_gui.mixins.conflicts.dialogs.success', default="Success"), f"Conflicts report exported to:\n{filename}")

        except Exception as e:
            messagebox.showerror(_t('gui.academics.course_management_gui.course_planning_gui.mixins.conflicts.dialogs.error', default="Error"), f"Failed to export report: {e}")

