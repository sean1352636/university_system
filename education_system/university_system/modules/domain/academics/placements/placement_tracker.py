"""
T-Level / Industry Placement Hours Tracker
A desktop GUI application for university systems to track student placement hours.

Auth: piggybacks on the main university auth — when launched as a
subprocess from the unified main GUI, EDU_AUTH_* env vars carry the
logged-in user's identity. The header shows the signed-in user; key
write actions are stamped with that identity in the log.

Persistence: rows live in the central `student_records.db`. Basic
student identity (student_id, first_name, last_name, course,
email_address) is read from / written to the canonical `students`
table so this module shares its student rolodex with the rest of the
system. Placement-specific fields (cohort, employer, supervisor,
start_date, end_date) live in a side table `placement_profiles` keyed
on student_id, and daily hours go in `placement_hours_log` (renamed
from the old generic `hours_log`). The legacy local
`placement_tracker.db` file is removed on startup.

Logging: routed through the shared rotating `app.log` via
`infrastructure.logging.log_config.configure_logging`.
"""

import csv
import logging
import os
import sqlite3
import sys
import tkinter as tk
from datetime import datetime, date
from tkinter import ttk, messagebox, filedialog


# When the main GUI launches us as a subprocess, the child Python is
# invoked directly on this file's path with no PYTHONPATH set, so
# `education_system` isn't importable. Walk up from this file until we
# find the dir that contains the `education_system` package and put
# that on sys.path. No-op when imported normally.
if 'education_system' not in sys.modules:
    _here = os.path.abspath(os.path.dirname(__file__))
    while _here and not os.path.isdir(os.path.join(_here, 'education_system')):
        _parent = os.path.dirname(_here)
        if _parent == _here:
            break
        _here = _parent
    if _here and _here not in sys.path:
        sys.path.insert(0, _here)


logger = logging.getLogger(__name__)

try:
    from education_system.university_system.infrastructure.logging.log_config import configure_logging
    configure_logging(name=__name__)
except Exception:
    logger.debug("Central log config unavailable; falling back to default handlers", exc_info=True)


# T-Level minimum required hours (industry placement requirement)
REQUIRED_HOURS = 315  # Minimum hours required for T-Level industry placement

# Legacy local DB file — data now lives in the central student_records.db.
_LEGACY_DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "placement_tracker.db")


# ---------------------------------------------------------------------------
# AUTH BOOTSTRAP
# ---------------------------------------------------------------------------
def _get_current_user():
    user_id = os.environ.get('EDU_AUTH_USER_ID') or ''
    username = os.environ.get('EDU_AUTH_USERNAME') or ''
    role = os.environ.get('EDU_AUTH_ROLE') or ''
    email = os.environ.get('EDU_AUTH_EMAIL') or ''
    perms_raw = os.environ.get('EDU_AUTH_PERMISSIONS') or ''
    if user_id or username:
        return {
            'id': user_id or None,
            'user_id': user_id or None,
            'username': username,
            'role': role,
            'email': email,
            'permissions': [p for p in perms_raw.split(',') if p],
        }
    try:
        from education_system.university_system.infrastructure.auth import get_global_auth
        ga = get_global_auth()
        if ga and getattr(ga, 'current_user', None):
            return ga.current_user
    except Exception:
        logger.debug("get_global_auth fallback failed", exc_info=True)
    return None


def _user_display_name(user):
    if not user:
        return 'Guest'
    return (user.get('username') or user.get('email') or
            user.get('user_id') or user.get('id') or 'Unknown')


def _remove_legacy_db():
    """Delete the old per-module placement_tracker.db (and WAL/SHM
    siblings) — data now lives in the central student_records.db."""
    for suffix in ("", "-wal", "-shm", "-journal"):
        path = _LEGACY_DB_FILE + suffix
        if os.path.exists(path):
            try:
                os.remove(path)
                logger.info("Removed legacy placement_tracker DB file: %s", path)
            except OSError:
                logger.warning("Could not remove legacy DB file %s", path,
                               exc_info=True)


class Database:
    """Wraps the central `student_records.db` via the shared
    `get_connection`. Basic student identity lives in canonical
    `students`; placement-specific data is split into side tables
    `placement_profiles` and `placement_hours_log`.

    The methods preserve the same return shapes the GUI expects (the
    leading element is the row identity used as the WHERE-clause key);
    that "pk" is now the TEXT student_id (or the integer hours-log id)
    rather than a synthetic surrogate."""

    def __init__(self, db_name=None):
        from education_system.university_system.infrastructure.database.db import get_connection
        self.conn = get_connection()
        # FK enforcement off — the canonical students table has no
        # column named `id` (PK is `student_id` TEXT) so any FK
        # references from older module-private tables would mismatch.
        self.conn.execute("PRAGMA foreign_keys = OFF")
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        self.cursor.executescript("""
            CREATE TABLE IF NOT EXISTS students (
                student_id TEXT PRIMARY KEY,
                first_name TEXT,
                last_name TEXT,
                email_address TEXT,
                course TEXT
            );

            CREATE TABLE IF NOT EXISTS placement_profiles (
                student_id TEXT PRIMARY KEY,
                cohort     TEXT,
                employer   TEXT,
                supervisor TEXT,
                start_date TEXT,
                end_date   TEXT
            );

            CREATE TABLE IF NOT EXISTS placement_hours_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                log_date TEXT NOT NULL,
                hours REAL NOT NULL,
                activity TEXT,
                supervisor_signoff INTEGER DEFAULT 0,
                notes TEXT
            );
        """)
        self.conn.commit()

    # ---------- Student CRUD ----------
    def add_student(self, data):
        """data = (student_id, first_name, last_name, course, cohort,
        email, employer, supervisor, start_date, end_date)."""
        sid, first, last, course, cohort, email, employer, supervisor, start, end = data
        # Upsert canonical students — preserve any existing
        # non-placement columns set elsewhere in the system.
        self.cursor.execute("""
            INSERT INTO students (student_id, first_name, last_name, course, email_address)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(student_id) DO UPDATE SET
                first_name=excluded.first_name,
                last_name=excluded.last_name,
                course=excluded.course,
                email_address=excluded.email_address
        """, (sid, first, last, course, email))
        # Upsert placement profile.
        self.cursor.execute("""
            INSERT INTO placement_profiles
                (student_id, cohort, employer, supervisor, start_date, end_date)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(student_id) DO UPDATE SET
                cohort=excluded.cohort,
                employer=excluded.employer,
                supervisor=excluded.supervisor,
                start_date=excluded.start_date,
                end_date=excluded.end_date
        """, (sid, cohort, employer, supervisor, start, end))
        self.conn.commit()
        return sid

    def update_student(self, student_pk, data):
        """student_pk is the original student_id (TEXT) being edited.
        If the dialog renames the student_id, we cascade-rename across
        the three tables to keep the join key consistent."""
        old_sid = student_pk
        new_sid = data[0]
        sid, first, last, course, cohort, email, employer, supervisor, start, end = data
        if new_sid != old_sid:
            self.cursor.execute("UPDATE students SET student_id=? WHERE student_id=?",
                                (new_sid, old_sid))
            self.cursor.execute("UPDATE placement_profiles SET student_id=? WHERE student_id=?",
                                (new_sid, old_sid))
            self.cursor.execute("UPDATE placement_hours_log SET student_id=? WHERE student_id=?",
                                (new_sid, old_sid))
        self.cursor.execute("""
            UPDATE students SET first_name=?, last_name=?, course=?, email_address=?
            WHERE student_id=?
        """, (first, last, course, email, new_sid))
        # Use INSERT OR REPLACE for placement_profiles in case the row
        # didn't exist yet (older student records added via another
        # subsystem won't have a placement profile).
        self.cursor.execute("""
            INSERT INTO placement_profiles
                (student_id, cohort, employer, supervisor, start_date, end_date)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(student_id) DO UPDATE SET
                cohort=excluded.cohort,
                employer=excluded.employer,
                supervisor=excluded.supervisor,
                start_date=excluded.start_date,
                end_date=excluded.end_date
        """, (new_sid, cohort, employer, supervisor, start, end))
        self.conn.commit()

    def delete_student(self, student_pk):
        """Remove placement enrollment for a student. The canonical
        `students` row is left intact — it's shared with the rest of
        the system and may be referenced by other modules."""
        self.cursor.execute("DELETE FROM placement_hours_log WHERE student_id=?",
                            (student_pk,))
        self.cursor.execute("DELETE FROM placement_profiles WHERE student_id=?",
                            (student_pk,))
        self.conn.commit()

    def get_all_students(self, search=""):
        """Return rows for students that have a placement_profile (i.e.
        are enrolled in placements). Shape: (id, student_id, first,
        last, course, cohort, employer)."""
        base = """
            SELECT s.student_id AS id, s.student_id, s.first_name, s.last_name,
                   s.course, p.cohort, p.employer
            FROM placement_profiles p
            JOIN students s ON s.student_id = p.student_id
        """
        if search:
            q = f"%{search}%"
            self.cursor.execute(base + """
                WHERE s.student_id LIKE ? OR s.first_name LIKE ? OR s.last_name LIKE ?
                   OR s.course LIKE ? OR p.employer LIKE ?
                ORDER BY s.last_name, s.first_name
            """, (q, q, q, q, q))
        else:
            self.cursor.execute(base + " ORDER BY s.last_name, s.first_name")
        return self.cursor.fetchall()

    def get_student(self, student_pk):
        """Shape: (id, student_id, first, last, course, cohort, email,
        employer, supervisor, start_date, end_date) — matches the
        original Database.get_student tuple for GUI compatibility."""
        self.cursor.execute("""
            SELECT s.student_id AS id, s.student_id, s.first_name, s.last_name,
                   s.course, p.cohort, s.email_address, p.employer, p.supervisor,
                   p.start_date, p.end_date
            FROM students s
            LEFT JOIN placement_profiles p ON p.student_id = s.student_id
            WHERE s.student_id = ?
        """, (student_pk,))
        return self.cursor.fetchone()

    # ---------- Hours CRUD ----------
    def add_hours(self, student_pk, log_date, hours, activity, signoff, notes):
        self.cursor.execute("""
            INSERT INTO placement_hours_log
                (student_id, log_date, hours, activity, supervisor_signoff, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (student_pk, log_date, hours, activity, signoff, notes))
        self.conn.commit()

    def update_hours(self, log_pk, log_date, hours, activity, signoff, notes):
        self.cursor.execute("""
            UPDATE placement_hours_log SET log_date=?, hours=?, activity=?,
                                 supervisor_signoff=?, notes=?
            WHERE id=?
        """, (log_date, hours, activity, signoff, notes, log_pk))
        self.conn.commit()

    def delete_hours(self, log_pk):
        self.cursor.execute("DELETE FROM placement_hours_log WHERE id=?", (log_pk,))
        self.conn.commit()

    def get_hours_for_student(self, student_pk):
        self.cursor.execute("""
            SELECT id, log_date, hours, activity, supervisor_signoff, notes
            FROM placement_hours_log WHERE student_id=? ORDER BY log_date DESC
        """, (student_pk,))
        return self.cursor.fetchall()

    def get_total_hours(self, student_pk):
        self.cursor.execute("""
            SELECT COALESCE(SUM(hours), 0) FROM placement_hours_log WHERE student_id=?
        """, (student_pk,))
        return self.cursor.fetchone()[0]

    def get_signed_off_hours(self, student_pk):
        self.cursor.execute("""
            SELECT COALESCE(SUM(hours), 0) FROM placement_hours_log
            WHERE student_id=? AND supervisor_signoff=1
        """, (student_pk,))
        return self.cursor.fetchone()[0]

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass


class PlacementTrackerApp:
    """Main application window."""

    def __init__(self, root):
        self.root = root
        self.root.title("T-Level / Industry Placement Hours Tracker")
        self.root.geometry("1400x900+%d+%d" % ((self.root.winfo_screenwidth() - 1400) // 2, (self.root.winfo_screenheight() - 900) // 2))
        self.root.minsize(1200, 800)

        self.db = Database()
        self.current_student_pk = None

        self.user = _get_current_user()
        self.user_display = _user_display_name(self.user)
        logger.info("Placement Tracker starting user=%s role=%s",
                    self.user_display,
                    (self.user or {}).get('role') or 'none')

        self._configure_styles()
        self._build_ui()
        self.refresh_student_list()

    def _configure_styles(self):
        style = ttk.Style()
        style.configure("Header.TLabel", font=("Segoe UI", 14, "bold"))
        style.configure("SubHeader.TLabel", font=("Segoe UI", 10, "bold"))
        style.configure("Stat.TLabel", font=("Segoe UI", 11, "bold"))
        style.configure("Treeview", rowheight=24)
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

    def _build_ui(self):
        # Top header bar
        header = ttk.Frame(self.root, padding=(10, 8))
        header.pack(fill="x")
        ttk.Label(header, text="📚 Placement Hours Tracker",
                  style="Header.TLabel").pack(side="left")
        ttk.Label(header, text=f"Required: {REQUIRED_HOURS} hours",
                  foreground="#555").pack(side="right")
        role = (self.user or {}).get('role') or ('—' if self.user else 'not signed in')
        ttk.Label(header,
                  text=f"Signed in: {self.user_display}  ({role})",
                  foreground="#1565c0").pack(side="right", padx=(0, 14))

        ttk.Separator(self.root, orient="horizontal").pack(fill="x")

        # Main paned window: left = student list, right = details
        paned = ttk.PanedWindow(self.root, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=8, pady=8)

        self._build_student_panel(paned)
        self._build_detail_panel(paned)

        # Status bar
        self.status = tk.StringVar(value="Ready")
        status_bar = ttk.Label(self.root, textvariable=self.status,
                               relief="sunken", anchor="w", padding=(6, 2))
        status_bar.pack(fill="x", side="bottom")

    # ---------- Left panel: students ----------
    def _build_student_panel(self, parent):
        frame = ttk.Frame(parent, padding=4)
        parent.add(frame, weight=1)

        ttk.Label(frame, text="Students", style="SubHeader.TLabel").pack(anchor="w")

        # Search bar
        search_frame = ttk.Frame(frame)
        search_frame.pack(fill="x", pady=(4, 4))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.refresh_student_list())
        ttk.Entry(search_frame, textvariable=self.search_var).pack(side="left", fill="x", expand=True)
        ttk.Button(search_frame, text="✕", width=3,
                   command=lambda: self.search_var.set("")).pack(side="left", padx=(2, 0))

        # Student treeview
        tree_frame = ttk.Frame(frame)
        tree_frame.pack(fill="both", expand=True)

        cols = ("student_id", "name", "course", "employer")
        self.student_tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                         selectmode="browse")
        self.student_tree.heading("student_id", text="ID")
        self.student_tree.heading("name", text="Name")
        self.student_tree.heading("course", text="Course")
        self.student_tree.heading("employer", text="Employer")
        self.student_tree.column("student_id", width=80, anchor="w")
        self.student_tree.column("name", width=140, anchor="w")
        self.student_tree.column("course", width=120, anchor="w")
        self.student_tree.column("employer", width=120, anchor="w")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.student_tree.yview)
        self.student_tree.configure(yscrollcommand=vsb.set)
        self.student_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self.student_tree.bind("<<TreeviewSelect>>", self._on_student_select)

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x", pady=(6, 0))
        ttk.Button(btn_frame, text="➕ Add", command=self.open_student_dialog).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="✏️ Edit", command=self.edit_selected_student).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="🗑 Delete", command=self.delete_selected_student).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="📤 Export", command=self.export_csv).pack(side="right", padx=2)

    # ---------- Right panel: details ----------
    def _build_detail_panel(self, parent):
        frame = ttk.Frame(parent, padding=4)
        parent.add(frame, weight=2)

        # Student info card
        info_frame = ttk.LabelFrame(frame, text="Student Details", padding=10)
        info_frame.pack(fill="x", pady=(0, 8))

        self.info_labels = {}
        info_grid = ttk.Frame(info_frame)
        info_grid.pack(fill="x")

        fields = [
            ("Name:", "name", 0, 0), ("Student ID:", "student_id", 0, 2),
            ("Course:", "course", 1, 0), ("Cohort:", "cohort", 1, 2),
            ("Employer:", "employer", 2, 0), ("Supervisor:", "supervisor", 2, 2),
            ("Email:", "email", 3, 0), ("Placement:", "dates", 3, 2),
        ]
        for label, key, r, c in fields:
            ttk.Label(info_grid, text=label, foreground="#666").grid(
                row=r, column=c, sticky="w", padx=(0, 6), pady=2)
            self.info_labels[key] = ttk.Label(info_grid, text="—")
            self.info_labels[key].grid(row=r, column=c + 1, sticky="w", padx=(0, 20), pady=2)

        info_grid.columnconfigure(1, weight=1)
        info_grid.columnconfigure(3, weight=1)

        # Progress card
        progress_frame = ttk.LabelFrame(frame, text="Hours Progress", padding=10)
        progress_frame.pack(fill="x", pady=(0, 8))

        stats = ttk.Frame(progress_frame)
        stats.pack(fill="x")
        ttk.Label(stats, text="Logged:", foreground="#666").grid(row=0, column=0, sticky="w")
        self.lbl_total = ttk.Label(stats, text="0.0 h", style="Stat.TLabel")
        self.lbl_total.grid(row=0, column=1, sticky="w", padx=(6, 20))

        ttk.Label(stats, text="Signed off:", foreground="#666").grid(row=0, column=2, sticky="w")
        self.lbl_signed = ttk.Label(stats, text="0.0 h", style="Stat.TLabel", foreground="#1a7a1a")
        self.lbl_signed.grid(row=0, column=3, sticky="w", padx=(6, 20))

        ttk.Label(stats, text="Remaining:", foreground="#666").grid(row=0, column=4, sticky="w")
        self.lbl_remaining = ttk.Label(stats, text=f"{REQUIRED_HOURS} h", style="Stat.TLabel",
                                       foreground="#a04000")
        self.lbl_remaining.grid(row=0, column=5, sticky="w", padx=(6, 0))

        self.progress = ttk.Progressbar(progress_frame, mode="determinate", maximum=REQUIRED_HOURS)
        self.progress.pack(fill="x", pady=(8, 2))
        self.progress_pct = ttk.Label(progress_frame, text="0%", anchor="center")
        self.progress_pct.pack(fill="x")

        # Hours log
        log_frame = ttk.LabelFrame(frame, text="Hours Log", padding=6)
        log_frame.pack(fill="both", expand=True)

        log_btns = ttk.Frame(log_frame)
        log_btns.pack(fill="x", pady=(0, 4))
        ttk.Button(log_btns, text="➕ Log Hours", command=self.open_hours_dialog).pack(side="left", padx=2)
        ttk.Button(log_btns, text="✏️ Edit", command=self.edit_selected_hours).pack(side="left", padx=2)
        ttk.Button(log_btns, text="🗑 Delete", command=self.delete_selected_hours).pack(side="left", padx=2)
        ttk.Button(log_btns, text="🎓 Submit as APL evidence",
                   command=self.submit_as_apl_evidence).pack(side="right", padx=2)

        cols = ("date", "hours", "activity", "signoff", "notes")
        self.hours_tree = ttk.Treeview(log_frame, columns=cols, show="headings", selectmode="browse")
        for col, text, width, anchor in [
            ("date", "Date", 95, "w"), ("hours", "Hours", 65, "e"),
            ("activity", "Activity", 200, "w"), ("signoff", "Signed", 70, "center"),
            ("notes", "Notes", 220, "w"),
        ]:
            self.hours_tree.heading(col, text=text)
            self.hours_tree.column(col, width=width, anchor=anchor)

        vsb2 = ttk.Scrollbar(log_frame, orient="vertical", command=self.hours_tree.yview)
        self.hours_tree.configure(yscrollcommand=vsb2.set)
        self.hours_tree.pack(side="left", fill="both", expand=True)
        vsb2.pack(side="right", fill="y")

    # ---------- Event handlers ----------
    def _on_student_select(self, _event=None):
        sel = self.student_tree.selection()
        if not sel:
            return
        self.current_student_pk = self._tree_pk(sel[0])
        self.load_student_details()

    def _tree_pk(self, item_id):
        # The PK is the canonical TEXT student_id, stored as the row's
        # first tag.
        tags = self.student_tree.item(item_id, "tags")
        return tags[0] if tags else None

    # ---------- Refresh / load ----------
    def refresh_student_list(self):
        for row in self.student_tree.get_children():
            self.student_tree.delete(row)
        students = self.db.get_all_students(self.search_var.get().strip())
        for s in students:
            pk, sid, fn, ln, course, cohort, employer = s
            cohort_str = f" ({cohort})" if cohort else ""
            self.student_tree.insert("", "end",
                                     values=(sid, f"{ln}, {fn}", f"{course}{cohort_str}",
                                             employer or "—"),
                                     tags=(str(pk),))
        self.status.set(f"{len(students)} student(s)")

    def load_student_details(self):
        if not self.current_student_pk:
            return
        s = self.db.get_student(self.current_student_pk)
        if not s:
            return
        # s = (id, student_id, first, last, course, cohort, email, employer, supervisor, start, end)
        self.info_labels["name"].config(text=f"{s[2]} {s[3]}")
        self.info_labels["student_id"].config(text=s[1])
        self.info_labels["course"].config(text=s[4] or "—")
        self.info_labels["cohort"].config(text=s[5] or "—")
        self.info_labels["employer"].config(text=s[7] or "—")
        self.info_labels["supervisor"].config(text=s[8] or "—")
        self.info_labels["email"].config(text=s[6] or "—")
        dates = f"{s[9] or '?'} → {s[10] or '?'}" if (s[9] or s[10]) else "—"
        self.info_labels["dates"].config(text=dates)

        self.refresh_hours_log()

    def refresh_hours_log(self):
        for row in self.hours_tree.get_children():
            self.hours_tree.delete(row)

        if not self.current_student_pk:
            self._update_progress(0, 0)
            return

        logs = self.db.get_hours_for_student(self.current_student_pk)
        for log in logs:
            log_pk, log_date, hours, activity, signoff, notes = log
            self.hours_tree.insert("", "end",
                                   values=(log_date, f"{hours:.1f}",
                                           activity or "—",
                                           "✓" if signoff else "✗",
                                           (notes or "")[:60]),
                                   tags=(str(log_pk),))

        total = self.db.get_total_hours(self.current_student_pk)
        signed = self.db.get_signed_off_hours(self.current_student_pk)
        self._update_progress(total, signed)

    def _update_progress(self, total, signed):
        self.lbl_total.config(text=f"{total:.1f} h")
        self.lbl_signed.config(text=f"{signed:.1f} h")
        remaining = max(0, REQUIRED_HOURS - signed)
        self.lbl_remaining.config(text=f"{remaining:.1f} h")
        self.progress["value"] = min(signed, REQUIRED_HOURS)
        pct = (signed / REQUIRED_HOURS * 100) if REQUIRED_HOURS else 0
        status_text = f"{pct:.1f}% complete"
        if signed >= REQUIRED_HOURS:
            status_text += "  ✅ Requirement met!"
        self.progress_pct.config(text=status_text)

    # ---------- Student dialogs ----------
    def open_student_dialog(self, existing=None):
        StudentDialog(self.root, self.db, existing, on_save=self.refresh_student_list)

    def edit_selected_student(self):
        sel = self.student_tree.selection()
        if not sel:
            messagebox.showinfo("No selection", "Please select a student to edit.")
            return
        pk = self._tree_pk(sel[0])
        student = self.db.get_student(pk)
        self.open_student_dialog(existing=student)

    def delete_selected_student(self):
        sel = self.student_tree.selection()
        if not sel:
            messagebox.showinfo("No selection", "Please select a student to delete.")
            return
        pk = self._tree_pk(sel[0])
        student = self.db.get_student(pk)
        if messagebox.askyesno(
                "Confirm delete",
                f"Remove {student[2]} {student[3]} from the placement tracker "
                f"and delete all their hours logs?\n\n"
                f"(The student's record in the central system will not be removed.)"):
            self.db.delete_student(pk)
            logger.info("Placement enrollment removed for student=%s by user=%s",
                        pk, self.user_display)
            self.current_student_pk = None
            self.refresh_student_list()
            self.refresh_hours_log()
            for k in self.info_labels:
                self.info_labels[k].config(text="—")
            self.status.set("Placement removed")

    # ---------- Hours dialogs ----------
    def submit_as_apl_evidence(self):
        """Push the selected student's placement hours into a draft
        APL/RPL ``work_experience`` claim. Reuses an existing draft if
        one is already open, otherwise creates one."""
        if not self.current_student_pk:
            messagebox.showwarning("No selection", "Select a student first.")
            return
        s = self.db.get_student(self.current_student_pk)
        if not s:
            return
        student_id = s[1]
        course = s[4] or None
        employer = s[7] or "Placement employer"
        date_range = None
        if s[9] or s[10]:
            date_range = f"{s[9] or '?'} → {s[10] or '?'}"
        total_hours = float(self.db.get_total_hours(self.current_student_pk) or 0)
        signed_hours = float(self.db.get_signed_off_hours(self.current_student_pk) or 0)
        try:
            from education_system.university_system.modules.domain.academics.prior_learning_recognition.services.prior_learning_service import (
                PriorLearningService,
            )
            apl = PriorLearningService()
            cid = apl.create_evidence_from_placement(
                student_id,
                employer=employer,
                total_hours=total_hours,
                signed_off_hours=signed_hours,
                date_range=date_range,
                target_course=course,
            )
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create APL evidence: {e}")
            return
        messagebox.showinfo(
            "APL evidence added",
            f"Placement summary added to APL claim #{cid}\n"
            f"for student {student_id} ({employer}, {total_hours:g} h).",
        )

    def open_hours_dialog(self, existing=None):
        if not self.current_student_pk:
            messagebox.showinfo("Select student", "Please select a student first.")
            return
        HoursDialog(self.root, self.db, self.current_student_pk, existing,
                    on_save=self.refresh_hours_log)

    def edit_selected_hours(self):
        sel = self.hours_tree.selection()
        if not sel:
            messagebox.showinfo("No selection", "Please select a log entry.")
            return
        log_pk = int(self.hours_tree.item(sel[0], "tags")[0])
        values = self.hours_tree.item(sel[0])["values"]
        # Re-fetch full data from DB for accuracy
        logs = self.db.get_hours_for_student(self.current_student_pk)
        existing = next((l for l in logs if l[0] == log_pk), None)
        if existing:
            self.open_hours_dialog(existing=existing)

    def delete_selected_hours(self):
        sel = self.hours_tree.selection()
        if not sel:
            messagebox.showinfo("No selection", "Please select a log entry to delete.")
            return
        log_pk = int(self.hours_tree.item(sel[0], "tags")[0])
        if messagebox.askyesno("Confirm delete", "Delete this hours log entry?"):
            self.db.delete_hours(log_pk)
            self.refresh_hours_log()
            self.status.set("Log entry deleted")

    # ---------- Export ----------
    def export_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile=f"placement_hours_{date.today().isoformat()}.csv"
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Student ID", "Name", "Course", "Cohort", "Employer",
                                 "Total Hours", "Signed-off Hours", "Required",
                                 "Remaining", "% Complete"])
                for s in self.db.get_all_students():
                    pk, sid, fn, ln, course, cohort, employer = s
                    total = self.db.get_total_hours(pk)
                    signed = self.db.get_signed_off_hours(pk)
                    remaining = max(0, REQUIRED_HOURS - signed)
                    pct = (signed / REQUIRED_HOURS * 100) if REQUIRED_HOURS else 0
                    writer.writerow([sid, f"{fn} {ln}", course, cohort or "",
                                     employer or "", f"{total:.1f}", f"{signed:.1f}",
                                     REQUIRED_HOURS, f"{remaining:.1f}", f"{pct:.1f}%"])
            self.status.set(f"Exported to {os.path.basename(path)}")
            messagebox.showinfo("Export complete", f"Saved to:\n{path}")
        except Exception as e:
            messagebox.showerror("Export failed", str(e))


class StudentDialog(tk.Toplevel):
    """Modal dialog for adding/editing a student."""

    def __init__(self, parent, db, existing=None, on_save=None):
        super().__init__(parent)
        self.db = db
        self.existing = existing
        self.on_save = on_save

        self.title("Edit Student" if existing else "Add Student")
        self.geometry("420x460")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._build()

        if existing:
            self._populate(existing)

    def _build(self):
        frame = ttk.Frame(self, padding=14)
        frame.pack(fill="both", expand=True)

        self.vars = {}
        fields = [
            ("Student ID *", "student_id"),
            ("First Name *", "first_name"),
            ("Last Name *", "last_name"),
            ("Course *", "course"),
            ("Cohort", "cohort"),
            ("Email", "email"),
            ("Employer", "employer"),
            ("Supervisor", "supervisor"),
            ("Start Date (YYYY-MM-DD)", "start_date"),
            ("End Date (YYYY-MM-DD)", "end_date"),
        ]
        for i, (label, key) in enumerate(fields):
            ttk.Label(frame, text=label).grid(row=i, column=0, sticky="w", pady=3)
            var = tk.StringVar()
            self.vars[key] = var
            ttk.Entry(frame, textvariable=var, width=32).grid(
                row=i, column=1, sticky="ew", pady=3, padx=(8, 0))
        frame.columnconfigure(1, weight=1)

        btns = ttk.Frame(frame)
        btns.grid(row=len(fields), column=0, columnspan=2, pady=(14, 0), sticky="e")
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="right", padx=4)
        ttk.Button(btns, text="Save", command=self._save).pack(side="right")

    def _populate(self, s):
        # s = (id, student_id, first, last, course, cohort, email, employer, sup, start, end)
        keys = ["student_id", "first_name", "last_name", "course", "cohort",
                "email", "employer", "supervisor", "start_date", "end_date"]
        for i, key in enumerate(keys):
            self.vars[key].set(s[i + 1] or "")

    def _save(self):
        # Required field validation
        required = ["student_id", "first_name", "last_name", "course"]
        for key in required:
            if not self.vars[key].get().strip():
                messagebox.showwarning("Missing field", f"'{key.replace('_', ' ').title()}' is required.")
                return

        # Date validation (optional fields, but if set, must be valid)
        for key in ("start_date", "end_date"):
            val = self.vars[key].get().strip()
            if val:
                try:
                    datetime.strptime(val, "%Y-%m-%d")
                except ValueError:
                    messagebox.showwarning("Invalid date",
                                           f"'{key.replace('_', ' ').title()}' must be YYYY-MM-DD.")
                    return

        data = tuple(self.vars[k].get().strip() or None for k in
                     ["student_id", "first_name", "last_name", "course", "cohort",
                      "email", "employer", "supervisor", "start_date", "end_date"])

        try:
            if self.existing:
                self.db.update_student(self.existing[0], data)
                logger.info("Placement student updated student_id=%s", data[0])
            else:
                self.db.add_student(data)
                logger.info("Placement student added student_id=%s employer=%r",
                            data[0], data[6])
        except sqlite3.IntegrityError:
            messagebox.showerror("Duplicate ID", "A student with that Student ID already exists.")
            return
        except Exception as e:
            logger.exception("Placement student save failed")
            messagebox.showerror("Database error", str(e))
            return

        if self.on_save:
            self.on_save()
        self.destroy()


class HoursDialog(tk.Toplevel):
    """Modal dialog for adding/editing an hours log entry."""

    ACTIVITIES = ["Workplace tasks", "Training", "Shadowing", "Project work",
                  "Meeting / review", "Travel (placement-related)", "Other"]

    def __init__(self, parent, db, student_pk, existing=None, on_save=None):
        super().__init__(parent)
        self.db = db
        self.student_pk = student_pk
        self.existing = existing
        self.on_save = on_save

        self.title("Edit Hours Entry" if existing else "Log Hours")
        self.geometry("420x340")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._build()
        if existing:
            self._populate(existing)
        else:
            self.date_var.set(date.today().isoformat())

    def _build(self):
        frame = ttk.Frame(self, padding=14)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Date (YYYY-MM-DD) *").grid(row=0, column=0, sticky="w", pady=3)
        self.date_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.date_var, width=20).grid(
            row=0, column=1, sticky="w", pady=3, padx=(8, 0))

        ttk.Label(frame, text="Hours *").grid(row=1, column=0, sticky="w", pady=3)
        self.hours_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.hours_var, width=20).grid(
            row=1, column=1, sticky="w", pady=3, padx=(8, 0))

        ttk.Label(frame, text="Activity").grid(row=2, column=0, sticky="w", pady=3)
        self.activity_var = tk.StringVar()
        ttk.Combobox(frame, textvariable=self.activity_var, values=self.ACTIVITIES,
                     width=28).grid(row=2, column=1, sticky="w", pady=3, padx=(8, 0))

        self.signoff_var = tk.IntVar()
        ttk.Checkbutton(frame, text="Signed off by supervisor",
                        variable=self.signoff_var).grid(row=3, column=1, sticky="w", pady=6, padx=(8, 0))

        ttk.Label(frame, text="Notes").grid(row=4, column=0, sticky="nw", pady=3)
        self.notes_text = tk.Text(frame, width=32, height=6, wrap="word")
        self.notes_text.grid(row=4, column=1, sticky="ew", pady=3, padx=(8, 0))

        frame.columnconfigure(1, weight=1)

        btns = ttk.Frame(frame)
        btns.grid(row=5, column=0, columnspan=2, pady=(14, 0), sticky="e")
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="right", padx=4)
        ttk.Button(btns, text="Save", command=self._save).pack(side="right")

    def _populate(self, log):
        # log = (id, log_date, hours, activity, supervisor_signoff, notes)
        self.date_var.set(log[1] or "")
        self.hours_var.set(str(log[2]))
        self.activity_var.set(log[3] or "")
        self.signoff_var.set(log[4] or 0)
        self.notes_text.insert("1.0", log[5] or "")

    def _save(self):
        # Validate date
        date_str = self.date_var.get().strip()
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            messagebox.showwarning("Invalid date", "Date must be in YYYY-MM-DD format.")
            return

        # Validate hours
        try:
            hours = float(self.hours_var.get().strip())
            if hours <= 0 or hours > 24:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Invalid hours", "Hours must be a number between 0 and 24.")
            return

        activity = self.activity_var.get().strip() or None
        signoff = self.signoff_var.get()
        notes = self.notes_text.get("1.0", "end").strip() or None

        try:
            if self.existing:
                self.db.update_hours(self.existing[0], date_str, hours, activity, signoff, notes)
                logger.info("Placement hours updated log_id=%s student=%s hours=%s signoff=%s",
                            self.existing[0], self.student_pk, hours, signoff)
            else:
                self.db.add_hours(self.student_pk, date_str, hours, activity, signoff, notes)
                logger.info("Placement hours logged student=%s hours=%s signoff=%s activity=%r",
                            self.student_pk, hours, signoff, activity)
        except Exception as e:
            logger.exception("Placement hours save failed")
            messagebox.showerror("Database error", str(e))
            return

        if self.on_save:
            self.on_save()
        self.destroy()


def main():
    _remove_legacy_db()
    root = tk.Tk()
    app = PlacementTrackerApp(root)

    def on_close():
        app.db.close()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
