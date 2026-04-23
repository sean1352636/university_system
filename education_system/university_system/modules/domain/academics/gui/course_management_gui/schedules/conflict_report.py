"""Cross-course schedule conflict report.

Surfaces three classes of conflicts across all rows in `course_schedule`:
  - room double-booked in overlapping slots
  - instructor double-booked in overlapping slots
  - same course double-scheduled in overlapping slots (data-integrity check)

Conflicts are scoped per (semester, year, day_of_week). The per-create check
in schedules.py only catches the third class on insert; this dialog
audits the existing dataset, including conflicts created before that check
existed.
"""

import logging
import tkinter as tk
from tkinter import ttk, messagebox

from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.modules.shared.constants import paths
from education_system.university_system.modules.shared.utils.i18n import get_text as _

DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH
logger = logging.getLogger(__name__)


def _times_overlap(a_start: str, a_end: str, b_start: str, b_end: str) -> bool:
    """Half-open overlap: [a_start, a_end) intersects [b_start, b_end).

    Times are 'HH:MM' strings — lexical comparison is correct because they
    are zero-padded and same-length.
    """
    return a_start < b_end and b_start < a_end


class ScheduleConflictReportDialog:
    """Read-only report listing every schedule conflict in `course_schedule`."""

    def __init__(self, parent, auth):
        self.parent = parent
        self.auth = auth

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Schedule Conflict Report")
        self.dialog.geometry("950x550")
        self.dialog.transient(parent)

        self._build_ui()
        self._populate()

    def _build_ui(self):
        header = ttk.Frame(self.dialog, padding=10)
        header.pack(fill=tk.X)
        ttk.Label(header, text="Schedule Conflict Report",
                  font=("Arial", 13, "bold")).pack(side=tk.LEFT)
        ttk.Button(header, text=_("common.refresh", default="Refresh"),
                   command=self._populate).pack(side=tk.RIGHT)

        # Filter row
        filter_frame = ttk.Frame(self.dialog, padding=(10, 0))
        filter_frame.pack(fill=tk.X)
        ttk.Label(filter_frame, text="Filter by type:").pack(side=tk.LEFT)
        self.type_filter = tk.StringVar(value="All")
        ttk.Combobox(filter_frame, textvariable=self.type_filter, state="readonly",
                     values=["All", "Room", "Instructor", "Course"], width=12,
                     ).pack(side=tk.LEFT, padx=5)
        self.type_filter.trace_add("write", lambda *_: self._refresh_view())

        # Results tree
        tree_frame = ttk.Frame(self.dialog, padding=10)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        cols = ("type", "term", "day", "slot_a", "slot_b", "shared")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=20)
        for c, label, w in (
            ("type", "Conflict", 90),
            ("term", "Term", 100),
            ("day", "Day", 90),
            ("slot_a", "Slot A", 220),
            ("slot_b", "Slot B", 220),
            ("shared", "Shared", 160),
        ):
            self.tree.heading(c, text=label)
            self.tree.column(c, width=w, anchor=tk.W)
        scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Status bar
        self.status_var = tk.StringVar(value="")
        ttk.Label(self.dialog, textvariable=self.status_var,
                  anchor=tk.W, padding=(10, 5)).pack(fill=tk.X)

        ttk.Button(self.dialog, text=_("common.close", default="Close"),
                   command=self.dialog.destroy).pack(pady=8)

    def _populate(self):
        self._all_conflicts = self._compute_conflicts()
        self._refresh_view()

    def _refresh_view(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        ftype = self.type_filter.get()
        shown = 0
        for conf in self._all_conflicts:
            if ftype != "All" and conf["type"] != ftype:
                continue
            self.tree.insert("", tk.END, values=(
                conf["type"], conf["term"], conf["day"],
                conf["slot_a"], conf["slot_b"], conf["shared"],
            ))
            shown += 1
        total = len(self._all_conflicts)
        if total == 0:
            self.status_var.set("No conflicts found.")
        else:
            self.status_var.set(f"{shown} shown of {total} total conflict(s).")

    def _compute_conflicts(self):
        conflicts = []
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0)
            try:
                conn.execute("PRAGMA journal_mode=WAL")
                cur = conn.cursor()
                # Tolerate either schema variant — column names differ between
                # the CREATE TABLE in schedules.py (course_code/day_of_week) and
                # the one in services/.../database.py (course_id/days_of_week).
                cur.execute("PRAGMA table_info(course_schedule)")
                cols = {row[1] for row in cur.fetchall()}
                if not cols:
                    return conflicts
                course_col = "course_code" if "course_code" in cols else (
                    "course_id" if "course_id" in cols else None)
                day_col = "day_of_week" if "day_of_week" in cols else (
                    "days_of_week" if "days_of_week" in cols else None)
                if not course_col or not day_col:
                    logger.warning("course_schedule missing course/day columns")
                    return conflicts
                room_col = "room_id" if "room_id" in cols else None
                instructor_col = "instructor_id" if "instructor_id" in cols else None

                select_cols = [course_col, day_col, "start_time", "end_time",
                               "semester", "year"]
                if room_col:
                    select_cols.append(room_col)
                if instructor_col:
                    select_cols.append(instructor_col)
                cur.execute(f"SELECT {', '.join(select_cols)} FROM course_schedule")
                rows = cur.fetchall()
            finally:
                conn.close()
        except sqlite3.Error as e:
            logger.exception("Failed to read course_schedule")
            messagebox.showerror(_("common.database_error"),
                                 f"Failed to read schedules: {e}")
            return conflicts

        # Group by (semester, year, day) so we only compare same-slot rows.
        buckets = {}
        for r in rows:
            course, day, s, e, sem, yr = r[0], r[1], r[2], r[3], r[4], r[5]
            extra = list(r[6:])
            if not s or not e:
                continue
            buckets.setdefault((sem, yr, day), []).append({
                "course": course, "day": day, "start": s, "end": e,
                "semester": sem, "year": yr,
                "room": extra.pop(0) if room_col else None,
                "instructor": extra.pop(0) if instructor_col else None,
            })

        for (sem, yr, day), entries in buckets.items():
            n = len(entries)
            for i in range(n):
                a = entries[i]
                for j in range(i + 1, n):
                    b = entries[j]
                    if not _times_overlap(a["start"], a["end"], b["start"], b["end"]):
                        continue
                    term = f"{sem or '?'} {yr or '?'}".strip()
                    slot_a = f"{a['course']} {a['start']}-{a['end']}"
                    slot_b = f"{b['course']} {b['start']}-{b['end']}"
                    if a["room"] and b["room"] and a["room"] == b["room"]:
                        conflicts.append({"type": "Room", "term": term, "day": day,
                                          "slot_a": slot_a, "slot_b": slot_b,
                                          "shared": f"room_id={a['room']}"})
                    if a["instructor"] and b["instructor"] and a["instructor"] == b["instructor"]:
                        conflicts.append({"type": "Instructor", "term": term, "day": day,
                                          "slot_a": slot_a, "slot_b": slot_b,
                                          "shared": f"instructor_id={a['instructor']}"})
                    if a["course"] == b["course"]:
                        conflicts.append({"type": "Course", "term": term, "day": day,
                                          "slot_a": slot_a, "slot_b": slot_b,
                                          "shared": str(a["course"])})
        # Stable order: type, term, day
        conflicts.sort(key=lambda c: (c["type"], c["term"], c["day"]))
        return conflicts
