"""Per-student timetable viewer.

Picks a student, queries the modules they're enrolled in
(student_modules.module_code WHERE status = 'Enrolled'), then shows every
published schedule row for those modules in a Mon–Fri week grid. Sessions
that overlap (same day, intersecting time range) are tagged so an advisor
can spot conflicts at a glance.

Only published rows are shown — drafts/archived stay off the student-facing
view, matching the timetable-export behaviour.
"""

import logging
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.infrastructure import paths

DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH
logger = logging.getLogger(__name__)

_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]


def _times_overlap(a_start: str, a_end: str, b_start: str, b_end: str) -> bool:
    """Half-open overlap on 'HH:MM' strings (lexical compare = correct)."""
    return a_start < b_end and b_start < a_end


class StudentTimetableDialog:
    """Browse one student's full week across every module they're enrolled in."""

    def __init__(self, parent, scheduler=None):
        self.parent = parent
        self.scheduler = scheduler
        self._students = []  # list of (student_id, label)

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Student Timetable")
        self.dialog.geometry("1100x650")
        self.dialog.transient(parent)

        self._build_ui()
        self._load_students()

    def _build_ui(self):
        top = ttk.Frame(self.dialog, padding=10)
        top.pack(fill=tk.X)
        ttk.Label(top, text="Student Timetable",
                  font=("Arial", 13, "bold")).pack(side=tk.LEFT)

        picker = ttk.Frame(self.dialog, padding=(10, 0))
        picker.pack(fill=tk.X)
        ttk.Label(picker, text="Student:").pack(side=tk.LEFT)
        self.student_var = tk.StringVar()
        self.student_combo = ttk.Combobox(picker, textvariable=self.student_var,
                                          width=50, state="readonly")
        self.student_combo.pack(side=tk.LEFT, padx=(4, 12))
        self.student_combo.bind("<<ComboboxSelected>>",
                                lambda _e: self._render())

        ttk.Label(picker, text="Term filter:").pack(side=tk.LEFT)
        now = datetime.now()
        self.semester_var = tk.StringVar(value="(all)")
        ttk.Combobox(picker, textvariable=self.semester_var,
                     values=["(all)", "Fall", "Spring", "Summer", "Winter"],
                     width=10, state="readonly"
                     ).pack(side=tk.LEFT, padx=(4, 4))
        self.year_var = tk.StringVar(value="(all)")
        ttk.Combobox(picker, textvariable=self.year_var,
                     values=["(all)"] + [str(y) for y in
                                         range(now.year - 2, now.year + 4)],
                     width=8, state="readonly"
                     ).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(picker, text="Apply",
                   command=self._render).pack(side=tk.LEFT)

        # Conflicts banner
        self.conflict_var = tk.StringVar(value="")
        ttk.Label(self.dialog, textvariable=self.conflict_var,
                  anchor=tk.W, padding=(10, 4),
                  foreground="#a00").pack(fill=tk.X)

        # Week grid (Treeview is the simplest week renderer Tk gives us).
        grid_frame = ttk.Frame(self.dialog, padding=10)
        grid_frame.pack(fill=tk.BOTH, expand=True)
        cols = ("time",) + tuple(_DAYS)
        self.grid = ttk.Treeview(grid_frame, columns=cols, show="headings",
                                 height=14)
        for c, label, w in [("time", "Time", 110)] + [(d, d, 180) for d in _DAYS]:
            self.grid.heading(c, text=label)
            self.grid.column(c, width=w, anchor=tk.W)
        self.grid.tag_configure("conflict", background="#ffd9d9")
        scroll = ttk.Scrollbar(grid_frame, orient=tk.VERTICAL,
                               command=self.grid.yview)
        self.grid.configure(yscrollcommand=scroll.set)
        self.grid.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.status_var = tk.StringVar(value="")
        ttk.Label(self.dialog, textvariable=self.status_var,
                  anchor=tk.W, padding=(10, 4)).pack(fill=tk.X)
        ttk.Button(self.dialog, text="Close",
                   command=self.dialog.destroy).pack(pady=8)

    def _load_students(self):
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH), timeout=15.0) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                cur = conn.cursor()
                cur.execute(
                    "SELECT student_id, COALESCE(first_name, ''), "
                    "COALESCE(last_name, '') "
                    "FROM students ORDER BY last_name, first_name"
                )
                rows = cur.fetchall()
        except sqlite3.Error as e:
            messagebox.showerror("Error",
                                 f"Failed to load students: {e}",
                                 parent=self.dialog)
            return
        self._students = [(sid, f"{sid} — {fn} {ln}".strip())
                          for sid, fn, ln in rows]
        self.student_combo["values"] = [label for _, label in self._students]
        if self._students:
            self.student_combo.current(0)
            self._render()
        else:
            self.status_var.set("No students found.")

    def _render(self):
        for row in self.grid.get_children():
            self.grid.delete(row)
        idx = self.student_combo.current()
        if idx < 0 or idx >= len(self._students):
            return
        student_id, _label = self._students[idx]

        # Build the term filter the same way the schedules tab does.
        where = ["sm.student_id = ?",
                 "COALESCE(sm.status, 'Enrolled') IN ('Enrolled', 'enrolled', 'Active', 'active')",
                 "COALESCE(ms.status, 'published') = 'published'"]
        params = [student_id]
        if self.semester_var.get() and self.semester_var.get() != "(all)":
            where.append("ms.semester = ?")
            params.append(self.semester_var.get())
        if self.year_var.get() and self.year_var.get() != "(all)":
            try:
                params.append(int(self.year_var.get()))
                where.append("ms.year = ?")
            except ValueError:
                pass

        where_sql = " AND ".join(where)
        sql = f"""
            SELECT ms.id, ms.module_code, m.module_name, ms.day_of_week,
                   ms.start_time, ms.end_time, r.building, r.room_number,
                   i.first_name, i.last_name, ms.session_type
            FROM student_modules sm
            JOIN module_schedule ms ON ms.module_code = sm.module_code
            LEFT JOIN modules m ON m.module_code = ms.module_code
            LEFT JOIN rooms r ON r.id = ms.room_id
            LEFT JOIN instructors i ON i.id = ms.instructor_id
            WHERE {where_sql}
            ORDER BY ms.day_of_week, ms.start_time
        """
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH), timeout=15.0) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                cur = conn.cursor()
                cur.execute(sql, params)
                sessions = cur.fetchall()
        except sqlite3.Error as e:
            messagebox.showerror("Error",
                                 f"Failed to load timetable: {e}",
                                 parent=self.dialog)
            return

        if not sessions:
            self.status_var.set("No published sessions for this student in the selected term.")
            self.conflict_var.set("")
            return

        # Detect overlaps within the same day.
        by_day = {d: [] for d in _DAYS}
        conflict_ids: set[int] = set()
        for s in sessions:
            sid, code, _name, day, start, end, _b, _r, _fn, _ln, _t = s
            if day in by_day:
                by_day[day].append({"id": sid, "code": code, "start": start,
                                    "end": end, "row": s})
        for day, items in by_day.items():
            for i in range(len(items)):
                for j in range(i + 1, len(items)):
                    if _times_overlap(items[i]["start"], items[i]["end"],
                                      items[j]["start"], items[j]["end"]):
                        conflict_ids.add(items[i]["id"])
                        conflict_ids.add(items[j]["id"])

        # Build a row-per-time-slot grid. Use the union of distinct start
        # times so we don't lose sessions that don't start on the hour.
        time_slots = sorted({s[4] for s in sessions if s[4]})
        rows_by_time = {t: {d: "" for d in _DAYS} for t in time_slots}
        cell_has_conflict = {(t, d): False for t in time_slots for d in _DAYS}
        for s in sessions:
            sid, code, _name, day, start, end, building, rnum, fn, ln, stype = s
            if day not in _DAYS or start not in rows_by_time:
                continue
            room = f"{building}-{rnum}" if building and rnum else "TBA"
            inst = f"{fn or ''} {ln or ''}".strip() or "TBA"
            label = f"{code} ({stype or ''})\n{room}\n{inst}"
            existing = rows_by_time[start][day]
            rows_by_time[start][day] = (existing + "\n— ─ —\n" + label) if existing else label
            if sid in conflict_ids:
                cell_has_conflict[(start, day)] = True

        for t in time_slots:
            row_vals = (t,) + tuple(rows_by_time[t][d] for d in _DAYS)
            tag = "conflict" if any(cell_has_conflict[(t, d)] for d in _DAYS) else ""
            self.grid.insert("", tk.END, values=row_vals,
                             tags=(tag,) if tag else ())

        n = len(sessions)
        self.status_var.set(f"{n} published session(s) across {len({s[1] for s in sessions})} module(s).")
        if conflict_ids:
            self.conflict_var.set(
                f"⚠ {len(conflict_ids)} session(s) overlap — see red rows.")
        else:
            self.conflict_var.set("")
