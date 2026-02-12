"""Class Roster Viewer & Export GUI (Feature 24)."""

import csv
import io
import logging
import os
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

from university_system.infrastructure.database.db import get_connection
from university_system.modules.shared.utils.simple_activity_logger import log_activity

logger = logging.getLogger(__name__)


class ClassRosterGUI:
    """Toplevel window for viewing and exporting class rosters."""

    def __init__(self, parent, auth=None):
        self.parent = parent
        self.auth = auth
        self.instructor_id = ''
        if auth and auth.current_user:
            self.instructor_id = auth.current_user.get('username', '')

        self.window = tk.Toplevel(parent)
        self.window.title("Class Roster Viewer")
        self.window.geometry("1100x700")
        self.window.transient(parent)

        self._setup_ui()
        self._load_courses()

    def _setup_ui(self):
        """Build the roster viewer UI."""
        ttk.Label(
            self.window, text="Class Roster Viewer",
            font=('Arial', 16, 'bold')
        ).pack(pady=(10, 5))

        # Top bar: module selector + search
        top_frame = ttk.Frame(self.window)
        top_frame.pack(fill=tk.X, padx=15, pady=5)

        ttk.Label(top_frame, text="Module:").pack(side=tk.LEFT, padx=(0, 5))
        self.course_var = tk.StringVar()
        self.course_combo = ttk.Combobox(
            top_frame, textvariable=self.course_var,
            state='readonly', width=40
        )
        self.course_combo.pack(side=tk.LEFT, padx=(0, 15))
        self.course_combo.bind('<<ComboboxSelected>>', lambda e: self._on_module_selected())

        ttk.Label(top_frame, text="Search:").pack(side=tk.LEFT, padx=(0, 5))
        self.search_var = tk.StringVar()
        self.search_var.trace_add('write', lambda *a: self._filter_roster())
        search_entry = ttk.Entry(top_frame, textvariable=self.search_var, width=25)
        search_entry.pack(side=tk.LEFT, padx=(0, 15))

        # Export buttons
        ttk.Button(top_frame, text="Export CSV", command=self._export_csv).pack(side=tk.RIGHT, padx=5)

        # Timetable section
        timetable_frame = ttk.LabelFrame(self.window, text="Module Timetable", padding="5")
        timetable_frame.pack(fill=tk.X, padx=15, pady=5)

        tt_cols = ('day', 'time', 'room', 'type', 'instructor')
        self.timetable_tree = ttk.Treeview(timetable_frame, columns=tt_cols, show='headings', height=4)
        self.timetable_tree.heading('day', text='Day')
        self.timetable_tree.heading('time', text='Time')
        self.timetable_tree.heading('room', text='Room')
        self.timetable_tree.heading('type', text='Session Type')
        self.timetable_tree.heading('instructor', text='Instructor')
        self.timetable_tree.column('day', width=100)
        self.timetable_tree.column('time', width=150)
        self.timetable_tree.column('room', width=100)
        self.timetable_tree.column('type', width=120)
        self.timetable_tree.column('instructor', width=180)
        self.timetable_tree.pack(fill=tk.X)

        # Roster Treeview
        tree_frame = ttk.Frame(self.window)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)

        cols = ('student_id', 'name', 'email', 'status')
        self.tree = ttk.Treeview(tree_frame, columns=cols, show='headings')
        self.tree.heading('student_id', text='Student ID')
        self.tree.heading('name', text='Name')
        self.tree.heading('email', text='Email')
        self.tree.heading('status', text='Enrollment Status')
        self.tree.column('student_id', width=120)
        self.tree.column('name', width=250)
        self.tree.column('email', width=300)
        self.tree.column('status', width=150)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Status bar
        self.status_var = tk.StringVar(value="Select a module to view roster.")
        ttk.Label(self.window, textvariable=self.status_var).pack(anchor="w", padx=15, pady=5)

        self.roster_data = []

    def _load_courses(self):
        """Load modules into the dropdown based on user role."""
        try:
            role = ''
            if self.auth and self.auth.current_user:
                role = self.auth.current_user.get('role', '')

            with get_connection() as conn:
                if role in ('staff', 'admin'):
                    rows = conn.execute(
                        "SELECT module_code, module_name FROM modules ORDER BY module_code"
                    ).fetchall()
                else:
                    user_id = (
                        self.auth.current_user.get('id', '')
                        if self.auth and self.auth.current_user else ''
                    )
                    rows = conn.execute(
                        "SELECT DISTINCT m.module_code, m.module_name FROM modules m "
                        "INNER JOIN module_schedule ms ON m.module_code = ms.module_code "
                        "WHERE ms.instructor_id = ? ORDER BY m.module_code",
                        (user_id,)
                    ).fetchall()
                courses = [f"{r['module_code']} - {r['module_name']}" for r in (rows or [])]
                self.course_combo['values'] = courses
        except Exception as e:
            logger.error(f"Error loading modules: {e}")

    def _on_module_selected(self):
        """Handle module selection — load timetable and roster."""
        self._load_timetable()
        self._load_roster()

    def _load_timetable(self):
        """Load timetable for the selected module."""
        self.timetable_tree.delete(*self.timetable_tree.get_children())
        selection = self.course_var.get()
        if not selection:
            return
        module_code = selection.split(' - ')[0].strip()

        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT ms.day_of_week, ms.start_time, ms.end_time, "
                    "ms.room_id, ms.session_type, "
                    "COALESCE(i.first_name || ' ' || i.last_name, "
                    "  'Instructor #' || ms.instructor_id) as instructor_name "
                    "FROM module_schedule ms "
                    "LEFT JOIN instructors i ON ms.instructor_id = i.id "
                    "WHERE ms.module_code = ? "
                    "ORDER BY CASE ms.day_of_week "
                    "  WHEN 'Monday' THEN 1 WHEN 'Tuesday' THEN 2 "
                    "  WHEN 'Wednesday' THEN 3 WHEN 'Thursday' THEN 4 "
                    "  WHEN 'Friday' THEN 5 ELSE 6 END",
                    (module_code,)
                ).fetchall()
                for r in (rows or []):
                    self.timetable_tree.insert('', tk.END, values=(
                        r['day_of_week'],
                        f"{r['start_time']} - {r['end_time']}",
                        r['room_id'] or '',
                        r['session_type'] or '',
                        r['instructor_name'] or '',
                    ))
                if not rows:
                    self.timetable_tree.insert('', tk.END, values=(
                        'No timetable data', '', '', '', '',
                    ))
        except Exception as e:
            logger.error(f"Error loading timetable: {e}")

    def _load_roster(self):
        """Load student roster for the selected course."""
        selection = self.course_var.get()
        if not selection:
            return
        module_code = selection.split(' - ')[0].strip()

        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT s.student_id, s.first_name || ' ' || s.last_name as name, "
                    "s.email_address as email, sm.status "
                    "FROM students s "
                    "JOIN student_modules sm ON s.student_id = sm.student_id "
                    "WHERE sm.module_code = ? "
                    "ORDER BY s.last_name, s.first_name",
                    (module_code,)
                ).fetchall()
                self.roster_data = [dict(r) for r in rows] if rows else []
        except Exception as e:
            logger.error(f"Error loading roster: {e}")
            self.roster_data = []

        self._populate_tree(self.roster_data)
        self.status_var.set(f"{len(self.roster_data)} students in {module_code}")

    def _populate_tree(self, data):
        """Populate the treeview with roster data."""
        self.tree.delete(*self.tree.get_children())
        for row in data:
            self.tree.insert('', tk.END, values=(
                row.get('student_id', ''),
                row.get('name', ''),
                row.get('email', ''),
                row.get('status', ''),
            ))

    def _filter_roster(self):
        """Filter roster by search text."""
        query = self.search_var.get().lower()
        if not query:
            self._populate_tree(self.roster_data)
            return
        filtered = [
            r for r in self.roster_data
            if query in r.get('student_id', '').lower()
            or query in r.get('name', '').lower()
            or query in r.get('email', '').lower()
        ]
        self._populate_tree(filtered)

    def _export_csv(self):
        """Export roster to CSV file."""
        if not self.roster_data:
            messagebox.showwarning("No Data", "No roster data to export.", parent=self.window)
            return

        filepath = filedialog.asksaveasfilename(
            parent=self.window,
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile=f"roster_{self.course_var.get().split(' - ')[0]}_{datetime.now().strftime('%Y%m%d')}.csv"
        )
        if not filepath:
            return

        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Student ID', 'Name', 'Email', 'Enrollment Status'])
                for row in self.roster_data:
                    writer.writerow([
                        row.get('student_id', ''),
                        row.get('name', ''),
                        row.get('email', ''),
                        row.get('status', ''),
                    ])

            try:
                uid = self.auth.current_user.get('id', '') if self.auth and self.auth.current_user else ''
                role = self.auth.current_user.get('role', '') if self.auth and self.auth.current_user else ''
                log_activity(
                    uid, self.instructor_id, role,
                    'export_roster', 'roster_viewer',
                    details=f"Exported roster CSV: {os.path.basename(filepath)}"
                )
            except Exception:
                pass

            messagebox.showinfo("Success", f"Roster exported to {filepath}", parent=self.window)
        except Exception as e:
            logger.error(f"Error exporting CSV: {e}")
            messagebox.showerror("Error", f"Failed to export: {e}", parent=self.window)
