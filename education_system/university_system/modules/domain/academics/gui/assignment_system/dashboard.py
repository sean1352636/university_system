"""Dashboard display and statistics"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import shutil
import threading
from datetime import datetime, timedelta
from pathlib import Path
import json
import csv
from PIL import Image, ImageTk
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import seaborn as sns
from education_system.university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.modules.shared.constants import paths
from collections import deque
from education_system.university_system.modules.shared.utils.i18n import get_text as _t



class DashboardManager:
    """Dashboard display and statistics"""

    def __init__(self, gui):
        """Initialize manager with reference to main GUI"""
        self.gui = gui
        self.root = gui.root
        self.auth = gui.auth
        self.assignment_system = gui.assignment_system
        self.style = gui.style

    def show_dashboard(self):
        """Show the main dashboard.

        Pre-8.117.31 the dashboard packed two label-and-buttons rows
        directly under the title — "Open sibling academic GUIs" (4
        buttons) and "Cross-domain reports" (3 buttons) — so the top
        third of the panel was just a wall of buttons before the
        stats cards. Reshaped to a slim topbar with two menu buttons:

        - **Cross-domain ▾** — drops down to the 4 sibling academic
          GUIs (Grade / Course / Module Scheduling / Exam) and the
          3 cross-domain reports (Module Timeline / At-Risk /
          Instructor Workload), grouped with a separator.
        - **About** — small info dialog about the Assignment System.

        The Parent and Integrations rows below are unchanged — those
        are role-specific affordances pointing into the same module,
        not cross-domain jumps.
        """
        self.gui.layout.clear_content_area()

        try:
            role = (self.auth.current_user or {}).get('role', '').lower()
        except Exception:
            role = ''

        # ── Topbar ────────────────────────────────────────────────
        topbar = ttk.Frame(self.gui.layout.content_area)
        topbar.pack(fill='x', pady=(0, 6))

        # Cross-domain dropdown is staff/admin/faculty only — same
        # gate the old grade_bar + cross_bar used.
        if role in ('admin', 'staff', 'instructor', 'faculty'):
            self._build_cross_domain_menubutton(topbar).pack(
                side='left', padx=(0, 6))

        ttk.Button(
            topbar, text="About",
            command=self._show_about_dialog,
        ).pack(side='right')

        ttk.Separator(self.gui.layout.content_area,
                      orient='horizontal').pack(fill='x', pady=(0, 12))

        # ── Title ─────────────────────────────────────────────────
        title = ttk.Label(self.gui.layout.content_area,
                          text=_t("assignments.dashboard"),
                          style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))

        # ── Role-specific affordances (unchanged) ─────────────────
        if role == 'parent':
            parent_bar = ttk.Frame(self.gui.layout.content_area)
            parent_bar.pack(fill='x', pady=(0, 15))
            ttk.Label(
                parent_bar,
                text="Parent view: track your children's assignments",
            ).pack(side='left')
            ttk.Button(
                parent_bar,
                text="My Children's Assignments",
                command=self.gui.show_parent_assignments_view,
            ).pack(side='right')

        if role in ('admin', 'staff', 'instructor', 'faculty'):
            integ_bar = ttk.Frame(self.gui.layout.content_area)
            integ_bar.pack(fill='x', pady=(0, 15))
            ttk.Label(
                integ_bar,
                text=(
                    "Cross-domain activity: fines, dispute tickets, "
                    "integrity cases, gradebook syncs, calendar events"
                ),
            ).pack(side='left')
            ttk.Button(
                integ_bar,
                text="View Integrations Activity",
                command=self.gui.show_integrations_activity,
            ).pack(side='right')

        # Create dashboard content with statistics
        self.create_dashboard_widgets()

    def _build_cross_domain_menubutton(self, parent):
        """Build the "Cross-domain ▾" Menubutton + its dropdown menu.

        Items split into two groups by a separator:
          1. Sibling academic GUIs (Grade / Course / Module
             Scheduling / Exam) — each opens its own Toplevel.
          2. Cross-domain reports (Module Timeline / At-Risk /
             Instructor Workload).

        Wires the same commands the old button rows did, so behaviour
        is unchanged — just compacted into a single dropdown.
        """
        mb = ttk.Menubutton(parent, text="Cross-domain  ▾", direction='below')
        menu = tk.Menu(mb, tearoff=0)

        # Group 1: sibling academic GUIs
        menu.add_command(label="🎓 Grade Management",
                         command=self.gui.open_grade_management)
        menu.add_command(label="📚 Course Management",
                         command=self.gui.open_course_management)
        menu.add_command(label="🗓 Module Scheduling",
                         command=self.gui.open_module_scheduling)
        menu.add_command(label="📝 Exam Scheduler",
                         command=self.gui.open_exam_scheduler)

        menu.add_separator()

        # Group 2: cross-domain reports
        menu.add_command(label="📈 Module Timeline",
                         command=self.gui.show_module_timeline)
        menu.add_command(label="⚠ At-Risk (unified)",
                         command=self.gui.show_at_risk_unified)
        menu.add_command(label="👥 Instructor Workload",
                         command=self.gui.show_instructor_workload)

        mb['menu'] = menu
        # Stash the menu on self so future extensions can add items
        # without rebuilding the menubutton.
        self._cross_domain_menu = menu
        return mb

    def _show_about_dialog(self):
        """Small modal showing what the Assignment System does and
        which sibling modules it integrates with. Not a 'help' page —
        just a one-line orientation for users who land here from a
        cross-domain jump and aren't sure what they're looking at."""
        try:
            from tkinter import messagebox
        except Exception:
            return
        try:
            messagebox.showinfo(
                "About — Assignment System",
                (
                    "Assignment System\n\n"
                    "Manages assignment creation, submission, grading,\n"
                    "extensions, peer review, and analytics.\n\n"
                    "Cross-domain integrations:\n"
                    "  • Grade Management — gradebook sync\n"
                    "  • Course / Module Scheduling — timetabling\n"
                    "  • Exam Scheduler — summative assessments\n"
                    "  • Library — reading-list deadlines\n"
                    "  • Finance — late fines\n"
                    "  • Cases — academic-integrity cases\n"
                    "  • Calendar — due-date publishing\n\n"
                    "Use the Cross-domain ▾ button (top-left) to open\n"
                    "any of the four sibling academic GUIs or one of the\n"
                    "three cross-domain reports."
                ),
                parent=self.root,
            )
        except Exception:
            pass


    def create_dashboard_widgets(self):
        """Create dashboard widgets with statistics"""
        # Statistics frame
        stats_frame = ttk.Frame(self.gui.layout.content_area)
        stats_frame.pack(fill='x', pady=(0, 20))

        # Get statistics from database
        stats = self.get_dashboard_statistics()

        # Create stat cards
        stat_cards = [
            (_t("assignments.active_assignments"), stats.get('active_assignments', 0), '#3498db'),
            (_t("assignments.my_submissions"), stats.get('my_submissions', 0), '#2ecc71'),
            (_t("assignments.pending_grades"), stats.get('pending_grades', 0), '#f39c12'),
            (_t("assignments.upcoming_due"), stats.get('upcoming_due', 0), '#e74c3c')
        ]

        for i, (title, value, color) in enumerate(stat_cards):
            card = self.create_stat_card(stats_frame, title, value, color)
            card.grid(row=0, column=i, padx=10, sticky='ew')
            stats_frame.grid_columnconfigure(i, weight=1)

        # Recent activity section
        activity_frame = ttk.LabelFrame(self.gui.layout.content_area, text=_t("assignments.recent_activity"), padding=10)
        activity_frame.pack(fill='both', expand=True, pady=(0, 10))

        # Activity list
        activity_tree = ttk.Treeview(activity_frame, columns=('Type', 'Description', 'Date'), show='headings')
        activity_tree.heading('Type', text=_t("common.type"))
        activity_tree.heading('Description', text=_t("common.description"))
        activity_tree.heading('Date', text=_t("common.date"))

        activity_tree.column('Type', width=100)
        activity_tree.column('Description', width=400)
        activity_tree.column('Date', width=150)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(activity_frame, orient='vertical', command=activity_tree.yview)
        activity_tree.configure(yscrollcommand=scrollbar.set)

        activity_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Load recent activity
        self.load_recent_activity(activity_tree)


    def create_stat_card(self, parent, title, value, color):
        """Create a statistics card widget"""
        card = ttk.Frame(parent, relief='raised', borderwidth=1)

        # Value label
        value_label = ttk.Label(card, text=str(value), font=('Arial', 24, 'bold'))
        value_label.pack(pady=(10, 5))

        # Title label
        title_label = ttk.Label(card, text=title, font=('Arial', 10))
        title_label.pack(pady=(0, 10))

        return card


    def get_dashboard_statistics(self):
        """Get statistics for dashboard"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            stats = {}  # Initialize stats dictionary

            # Check if tables exist first
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            existing_tables = [row[0] for row in cursor.fetchall()]

            required_tables = ['assignments', 'assignment_submissions', 'student_modules']
            if not all(table in existing_tables for table in required_tables):
                conn.close()
                return {'active_assignments': 0, 'my_submissions': 0, 'pending_grades': 0, 'upcoming_due': 0}

            # Active assignments
            if self.auth.check_permission('view_assignments'):
                student_id = self.assignment_system._get_student_id()
                if student_id:
                    try:
                        cursor.execute('''
                        SELECT COUNT(*) FROM assignments a
                        JOIN student_modules sm ON a.module_code = sm.module_code
                        WHERE sm.student_id = ? AND a.is_active = 1
                        ''', (student_id,))
                        stats['active_assignments'] = cursor.fetchone()[0]
                    except Exception:
                        stats['active_assignments'] = 0

                    try:
                        # My submissions
                        cursor.execute('''
                        SELECT COUNT(*) FROM assignment_submissions
                        WHERE student_id = ?
                        ''', (student_id,))
                        stats['my_submissions'] = cursor.fetchone()[0]
                    except Exception:
                        stats['my_submissions'] = 0

                    try:
                        # Pending grades
                        cursor.execute('''
                        SELECT COUNT(*) FROM assignment_submissions
                        WHERE student_id = ? AND grade IS NULL
                        ''', (student_id,))
                        stats['pending_grades'] = cursor.fetchone()[0]
                    except Exception:
                        stats['pending_grades'] = 0

                    try:
                        # Upcoming due (next 7 days)
                        week_from_now = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
                        cursor.execute('''
                        SELECT COUNT(*) FROM assignments a
                        JOIN student_modules sm ON a.module_code = sm.module_code
                        WHERE sm.student_id = ? AND a.is_active = 1
                        AND a.due_date <= ? AND a.due_date > datetime('now')
                        ''', (student_id, week_from_now))
                        stats['upcoming_due'] = cursor.fetchone()[0]
                    except Exception:
                        stats['upcoming_due'] = 0
                else:
                    # No student ID found
                    stats = {'active_assignments': 0, 'my_submissions': 0, 'pending_grades': 0, 'upcoming_due': 0}

            if self.auth.check_permission('manage_assignments'):
                try:
                    # For instructors, show different stats
                    cursor.execute('SELECT COUNT(*) FROM assignments WHERE is_active = 1')
                    stats['active_assignments'] = cursor.fetchone()[0]
                except Exception:
                    stats['active_assignments'] = 0

                try:
                    cursor.execute('SELECT COUNT(*) FROM assignment_submissions')
                    stats['my_submissions'] = cursor.fetchone()[0]
                except Exception:
                    stats['my_submissions'] = 0

                try:
                    cursor.execute('SELECT COUNT(*) FROM assignment_submissions WHERE grade IS NULL')
                    stats['pending_grades'] = cursor.fetchone()[0]
                except Exception:
                    stats['pending_grades'] = 0

                try:
                    week_from_now = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
                    cursor.execute('''
                    SELECT COUNT(*) FROM assignments
                    WHERE is_active = 1 AND due_date <= ? AND due_date > datetime('now')
                    ''', (week_from_now,))
                    stats['upcoming_due'] = cursor.fetchone()[0]
                except Exception:
                    stats['upcoming_due'] = 0

            # Ensure all keys exist with default values
            default_stats = {'active_assignments': 0, 'my_submissions': 0, 'pending_grades': 0, 'upcoming_due': 0}
            for key in default_stats:
                if key not in stats:
                    stats[key] = default_stats[key]

            conn.close()
            return stats

        except Exception as e:
            print(_t("assignments.error_getting_stats", error=str(e)))
            return {'active_assignments': 0, 'my_submissions': 0, 'pending_grades': 0, 'upcoming_due': 0}



    def load_recent_activity(self, tree):
        """Load recent activity into the tree view"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Get recent submissions, grades, etc.
            if self.auth.check_permission('view_assignments'):
                student_id = self.assignment_system._get_student_id()
                if student_id:
                    cursor.execute('''
                    SELECT 'Submission' as type,
                           'Submitted ' || a.title as description,
                           s.submission_date as date
                    FROM assignment_submissions s
                    JOIN assignments a ON s.assignment_id = a.id
                    WHERE s.student_id = ?
                    ORDER BY s.submission_date DESC
                    LIMIT 10
                    ''', (student_id,))

                    activities = cursor.fetchall()
                    for activity in activities:
                        tree.insert('', 'end', values=activity)

            conn.close()

        except Exception as e:
            print(_t("assignments.error_loading_activity", error=str(e)))

