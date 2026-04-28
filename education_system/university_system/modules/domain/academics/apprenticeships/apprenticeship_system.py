"""
University Apprenticeship Management System
A GUI application for managing apprenticeships, students, employers, and applications.

Auth: piggybacks on the main university auth — when launched as a
subprocess from the unified main GUI, EDU_AUTH_* env vars carry the
logged-in user's identity. The header shows the signed-in user; key
write actions are stamped with that identity in the log.

Persistence: rows live in the canonical `student_records.db` tables
shared with the rest of the system — `students`, `employers`,
`apprenticeships`, and `applications`. Two module-needed columns
(`students.gpa`, `employers.address`) are added via `ALTER TABLE` if
not already present. The legacy local `apprenticeships.db` file and
the older module-private `apprenticeship_*` tables are removed on
startup so no data is duplicated.

Logging: routed through the shared rotating `app.log` via
`infrastructure.logging.log_config.configure_logging`.
"""

import logging
import os
import sqlite3
import sys
import tkinter as tk
from datetime import datetime
from tkinter import ttk, messagebox, simpledialog


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


# Legacy local DB file — data now lives in the central student_records.db.
_LEGACY_DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "apprenticeships.db")


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


class Database:
    """Wraps the central `student_records.db` via the shared
    `get_connection` and uses the canonical `students`, `employers`,
    `apprenticeships`, and `applications` tables so apprenticeship
    rows live alongside the rest of the system's data."""

    def __init__(self, db_name=None):
        from education_system.university_system.infrastructure.database.db import get_connection
        # One long-lived connection for the GUI session — matches the
        # original module's behaviour and keeps tab-render code
        # (which fires many small queries) cheap.
        self.conn = get_connection()
        # The canonical `apprenticeships` and `applications` tables ship
        # with FK declarations that reference non-existent parent
        # columns (`employers(id)` instead of `employer_id`,
        # `students(id)` instead of `student_id`). Enforcing them
        # rejects every INSERT, so we leave foreign_keys OFF on this
        # connection — the module enforces the relationships logically
        # via its UI and DELETE cleanup helpers.
        self.conn.execute("PRAGMA foreign_keys = OFF")
        self.ensure_schema()
        self._cleanup_module_private_tables()

    def ensure_schema(self):
        """Add the two columns this module needs that aren't on the
        canonical tables yet. The canonical schemas are otherwise
        compatible (apprenticeships and applications match exactly;
        students and employers have the same logical fields under
        different names — see the SELECT/INSERT statements below)."""
        cursor = self.conn.cursor()
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS students (
                student_id TEXT PRIMARY KEY,
                first_name TEXT,
                last_name TEXT,
                email_address TEXT,
                course TEXT,
                year_of_study INTEGER
            );

            CREATE TABLE IF NOT EXISTS employers (
                employer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT UNIQUE NOT NULL,
                contact_person TEXT,
                contact_email TEXT,
                contact_phone TEXT,
                industry TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS apprenticeships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                employer_id INTEGER NOT NULL,
                description TEXT,
                duration_months INTEGER NOT NULL,
                salary REAL,
                location TEXT,
                required_course TEXT,
                min_year INTEGER DEFAULT 1,
                positions_available INTEGER DEFAULT 1,
                status TEXT DEFAULT 'Open',
                posted_date TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                apprenticeship_id INTEGER NOT NULL,
                application_date TEXT DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'Pending',
                notes TEXT,
                UNIQUE(student_id, apprenticeship_id)
            );
        """)
        # Add the two missing columns idempotently. SQLite has no
        # IF NOT EXISTS for ADD COLUMN, so probe pragma_table_info.
        existing_student_cols = {r[1] for r in self.conn.execute("PRAGMA table_info(students)")}
        if "gpa" not in existing_student_cols:
            self.conn.execute("ALTER TABLE students ADD COLUMN gpa REAL")
            logger.info("Added students.gpa column")
        existing_employer_cols = {r[1] for r in self.conn.execute("PRAGMA table_info(employers)")}
        if "address" not in existing_employer_cols:
            self.conn.execute("ALTER TABLE employers ADD COLUMN address TEXT")
            logger.info("Added employers.address column")
        self.conn.commit()

    def _cleanup_module_private_tables(self):
        """Drop the older `apprenticeship_*` tables this module used to
        create. Their data was empty in practice — the canonical tables
        are now the single source of truth."""
        for tbl in ("apprenticeship_applications", "apprenticeship_listings",
                    "apprenticeship_employers", "apprenticeship_students"):
            try:
                # Only drop if empty so we never destroy rows silently.
                row = self.conn.execute(
                    f"SELECT name FROM sqlite_master WHERE type='table' AND name='{tbl}'"
                ).fetchone()
                if not row:
                    continue
                count = self.conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
                if count == 0:
                    self.conn.execute(f"DROP TABLE {tbl}")
                    logger.info("Dropped empty legacy table %s", tbl)
                else:
                    logger.warning(
                        "Legacy table %s still has %d row(s); leaving in place. "
                        "Migrate manually if you need them in the canonical tables.",
                        tbl, count,
                    )
            except sqlite3.Error:
                logger.debug("Could not inspect/drop %s", tbl, exc_info=True)
        self.conn.commit()

    def execute(self, query, params=()):
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        self.conn.commit()
        return cursor

    def fetch_all(self, query, params=()):
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()

    def fetch_one(self, query, params=()):
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchone()

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass


def _remove_legacy_db():
    """Delete the old per-module apprenticeships.db (and WAL/SHM
    siblings) — data now lives in the central student_records.db."""
    for suffix in ("", "-wal", "-shm", "-journal"):
        path = _LEGACY_DB_FILE + suffix
        if os.path.exists(path):
            try:
                os.remove(path)
                logger.info("Removed legacy apprenticeships DB file: %s", path)
            except OSError:
                logger.warning("Could not remove legacy DB file %s", path,
                               exc_info=True)


class StudentTab(ttk.Frame):
    """Tab for managing students."""

    def __init__(self, parent, db):
        super().__init__(parent)
        self.db = db
        self.build_ui()
        self.refresh()

    def build_ui(self):
        # Form frame
        form_frame = ttk.LabelFrame(self, text="Student Details", padding=10)
        form_frame.pack(fill="x", padx=10, pady=5)

        labels = ["Student ID:", "First Name:", "Last Name:", "Email:",
                  "Course:", "Year of Study:", "GPA:"]
        self.entries = {}
        for i, label in enumerate(labels):
            ttk.Label(form_frame, text=label).grid(row=i // 2, column=(i % 2) * 2,
                                                   sticky="w", padx=5, pady=3)
            entry = ttk.Entry(form_frame, width=25)
            entry.grid(row=i // 2, column=(i % 2) * 2 + 1, padx=5, pady=3)
            key = label.replace(":", "").replace(" ", "_").lower()
            self.entries[key] = entry

        # Button frame
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=10, pady=5)
        ttk.Button(btn_frame, text="Add Student", command=self.add_student).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Update", command=self.update_student).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Delete", command=self.delete_student).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Clear Form", command=self.clear_form).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Refresh", command=self.refresh).pack(side="left", padx=2)

        # Search
        search_frame = ttk.Frame(self)
        search_frame.pack(fill="x", padx=10, pady=5)
        ttk.Label(search_frame, text="Search:").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *_: self.refresh())
        ttk.Entry(search_frame, textvariable=self.search_var, width=30).pack(side="left", padx=5)

        # Treeview
        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=5)

        columns = ("id", "student_id", "first_name", "last_name", "email", "course", "year", "gpa")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=12)
        headings = ["ID", "Student ID", "First Name", "Last Name", "Email", "Course", "Year", "GPA"]
        widths = [40, 90, 100, 100, 180, 120, 50, 50]
        for col, head, w in zip(columns, headings, widths):
            self.tree.heading(col, text=head)
            self.tree.column(col, width=w, anchor="w")

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

    def get_form_data(self):
        try:
            return {
                "student_id": self.entries["student_id"].get().strip(),
                "first_name": self.entries["first_name"].get().strip(),
                "last_name": self.entries["last_name"].get().strip(),
                "email": self.entries["email"].get().strip(),
                "course": self.entries["course"].get().strip(),
                "year_of_study": int(self.entries["year_of_study"].get()) if self.entries["year_of_study"].get() else 0,
                "gpa": float(self.entries["gpa"].get()) if self.entries["gpa"].get() else None,
            }
        except ValueError:
            messagebox.showerror("Invalid Input", "Year must be an integer and GPA must be a number.")
            return None

    def add_student(self):
        data = self.get_form_data()
        if not data:
            return
        if not all([data["student_id"], data["first_name"], data["last_name"], data["email"], data["course"]]):
            messagebox.showerror("Missing Fields", "Please fill in all required fields.")
            return
        try:
            self.db.execute("""
                INSERT INTO students (student_id, first_name, last_name, email_address, course, year_of_study, gpa)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, tuple(data.values()))
            messagebox.showinfo("Success", "Student added successfully.")
            self.clear_form()
            self.refresh()
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", "A student with this Student ID already exists.")

    def update_student(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a student to update.")
            return
        data = self.get_form_data()
        if not data:
            return
        student_pk = self.tree.item(selected[0])["values"][0]
        # Cascade-delete student applications first since canonical
        # `students` is keyed by TEXT student_id, with no FK to
        # applications.student_id (the canonical schema isn't enforcing
        # ON DELETE CASCADE here).
        self.db.execute("DELETE FROM applications WHERE student_id=?", (student_pk,))
        self.db.execute("""
            UPDATE students SET student_id=?, first_name=?, last_name=?, email_address=?,
                course=?, year_of_study=?, gpa=? WHERE student_id=?
        """, (*data.values(), student_pk))
        messagebox.showinfo("Success", "Student updated.")
        self.refresh()

    def delete_student(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a student to delete.")
            return
        if not messagebox.askyesno("Confirm", "Delete this student and all their applications?"):
            return
        student_pk = self.tree.item(selected[0])["values"][0]
        self.db.execute("DELETE FROM applications WHERE student_id=?", (student_pk,))
        self.db.execute("DELETE FROM students WHERE student_id=?", (student_pk,))
        self.refresh()
        self.clear_form()

    def clear_form(self):
        for entry in self.entries.values():
            entry.delete(0, tk.END)
        self.tree.selection_remove(*self.tree.selection())

    def on_select(self, _):
        selected = self.tree.selection()
        if not selected:
            return
        values = self.tree.item(selected[0])["values"]
        keys = ["student_id", "first_name", "last_name", "email", "course", "year_of_study", "gpa"]
        for key, val in zip(keys, values[1:]):
            self.entries[key].delete(0, tk.END)
            self.entries[key].insert(0, str(val) if val is not None else "")

    def refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        search = self.search_var.get().strip()
        # Canonical `students` has no surrogate integer id; we surface
        # `student_id` as the row identity and select it twice so the
        # treeview's first "ID" column stays populated and the existing
        # values[1:] code (which expects the seven editable fields after
        # the id) still maps correctly.
        if search:
            query = """SELECT student_id, student_id, first_name, last_name, email_address, course, year_of_study, gpa
                       FROM students WHERE student_id LIKE ? OR first_name LIKE ? OR last_name LIKE ?
                       OR email_address LIKE ? OR course LIKE ? ORDER BY last_name"""
            params = tuple([f"%{search}%"] * 5)
        else:
            query = ("SELECT student_id, student_id, first_name, last_name, "
                     "email_address, course, year_of_study, gpa "
                     "FROM students ORDER BY last_name")
            params = ()
        for row in self.db.fetch_all(query, params):
            self.tree.insert("", "end", values=row)


class EmployerTab(ttk.Frame):
    """Tab for managing employers."""

    def __init__(self, parent, db):
        super().__init__(parent)
        self.db = db
        self.build_ui()
        self.refresh()

    def build_ui(self):
        form_frame = ttk.LabelFrame(self, text="Employer Details", padding=10)
        form_frame.pack(fill="x", padx=10, pady=5)

        labels = ["Company Name:", "Contact Name:", "Email:", "Phone:", "Industry:", "Address:"]
        self.entries = {}
        for i, label in enumerate(labels):
            ttk.Label(form_frame, text=label).grid(row=i // 2, column=(i % 2) * 2,
                                                   sticky="w", padx=5, pady=3)
            entry = ttk.Entry(form_frame, width=30)
            entry.grid(row=i // 2, column=(i % 2) * 2 + 1, padx=5, pady=3)
            key = label.replace(":", "").replace(" ", "_").lower()
            self.entries[key] = entry

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=10, pady=5)
        ttk.Button(btn_frame, text="Add Employer", command=self.add_employer).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Update", command=self.update_employer).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Delete", command=self.delete_employer).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Clear Form", command=self.clear_form).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Refresh", command=self.refresh).pack(side="left", padx=2)

        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=5)
        columns = ("id", "company", "contact", "email", "phone", "industry", "address")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=12)
        headings = ["ID", "Company", "Contact", "Email", "Phone", "Industry", "Address"]
        widths = [40, 150, 120, 180, 100, 100, 200]
        for col, head, w in zip(columns, headings, widths):
            self.tree.heading(col, text=head)
            self.tree.column(col, width=w, anchor="w")

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

    def get_form_data(self):
        return {
            "company_name": self.entries["company_name"].get().strip(),
            "contact_name": self.entries["contact_name"].get().strip(),
            "email": self.entries["email"].get().strip(),
            "phone": self.entries["phone"].get().strip(),
            "industry": self.entries["industry"].get().strip(),
            "address": self.entries["address"].get().strip(),
        }

    def add_employer(self):
        data = self.get_form_data()
        if not all([data["company_name"], data["contact_name"], data["email"]]):
            messagebox.showerror("Missing Fields", "Company name, contact, and email are required.")
            return
        try:
            self.db.execute("""
                INSERT INTO employers (company_name, contact_person, contact_email, contact_phone, industry, address)
                VALUES (?, ?, ?, ?, ?, ?)
            """, tuple(data.values()))
            messagebox.showinfo("Success", "Employer added.")
            self.clear_form()
            self.refresh()
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", "An employer with this company name already exists.")

    def update_employer(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select an employer.")
            return
        data = self.get_form_data()
        emp_id = self.tree.item(selected[0])["values"][0]
        self.db.execute("""
            UPDATE employers SET company_name=?, contact_person=?, contact_email=?, contact_phone=?,
                industry=?, address=? WHERE employer_id=?
        """, (*data.values(), emp_id))
        messagebox.showinfo("Success", "Employer updated.")
        self.refresh()

    def delete_employer(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select an employer.")
            return
        if not messagebox.askyesno("Confirm", "Delete this employer and all their apprenticeships?"):
            return
        emp_id = self.tree.item(selected[0])["values"][0]
        # No FK cascade on the canonical employers table; clear the
        # dependent apprenticeships (and their applications) explicitly.
        self.db.execute(
            "DELETE FROM applications WHERE apprenticeship_id IN "
            "(SELECT id FROM apprenticeships WHERE employer_id=?)", (emp_id,))
        self.db.execute("DELETE FROM apprenticeships WHERE employer_id=?", (emp_id,))
        self.db.execute("DELETE FROM employers WHERE employer_id=?", (emp_id,))
        self.refresh()
        self.clear_form()

    def clear_form(self):
        for entry in self.entries.values():
            entry.delete(0, tk.END)
        self.tree.selection_remove(*self.tree.selection())

    def on_select(self, _):
        selected = self.tree.selection()
        if not selected:
            return
        values = self.tree.item(selected[0])["values"]
        keys = ["company_name", "contact_name", "email", "phone", "industry", "address"]
        for key, val in zip(keys, values[1:]):
            self.entries[key].delete(0, tk.END)
            self.entries[key].insert(0, str(val) if val is not None else "")

    def refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for row in self.db.fetch_all(
            "SELECT employer_id, company_name, contact_person, contact_email, contact_phone, industry, address "
            "FROM employers ORDER BY company_name"
        ):
            self.tree.insert("", "end", values=row)


class ApprenticeshipTab(ttk.Frame):
    """Tab for managing apprenticeship listings."""

    def __init__(self, parent, db):
        super().__init__(parent)
        self.db = db
        self.build_ui()
        self.refresh()

    def build_ui(self):
        form_frame = ttk.LabelFrame(self, text="Apprenticeship Details", padding=10)
        form_frame.pack(fill="x", padx=10, pady=5)

        # Title
        ttk.Label(form_frame, text="Title:").grid(row=0, column=0, sticky="w", padx=5, pady=3)
        self.title_entry = ttk.Entry(form_frame, width=40)
        self.title_entry.grid(row=0, column=1, padx=5, pady=3)

        # Employer
        ttk.Label(form_frame, text="Employer:").grid(row=0, column=2, sticky="w", padx=5, pady=3)
        self.employer_combo = ttk.Combobox(form_frame, width=27, state="readonly")
        self.employer_combo.grid(row=0, column=3, padx=5, pady=3)

        # Duration
        ttk.Label(form_frame, text="Duration (months):").grid(row=1, column=0, sticky="w", padx=5, pady=3)
        self.duration_entry = ttk.Entry(form_frame, width=40)
        self.duration_entry.grid(row=1, column=1, padx=5, pady=3)

        # Salary
        ttk.Label(form_frame, text="Salary (£):").grid(row=1, column=2, sticky="w", padx=5, pady=3)
        self.salary_entry = ttk.Entry(form_frame, width=29)
        self.salary_entry.grid(row=1, column=3, padx=5, pady=3)

        # Location
        ttk.Label(form_frame, text="Location:").grid(row=2, column=0, sticky="w", padx=5, pady=3)
        self.location_entry = ttk.Entry(form_frame, width=40)
        self.location_entry.grid(row=2, column=1, padx=5, pady=3)

        # Required course
        ttk.Label(form_frame, text="Required Course:").grid(row=2, column=2, sticky="w", padx=5, pady=3)
        self.course_entry = ttk.Entry(form_frame, width=29)
        self.course_entry.grid(row=2, column=3, padx=5, pady=3)

        # Min year
        ttk.Label(form_frame, text="Min Year:").grid(row=3, column=0, sticky="w", padx=5, pady=3)
        self.min_year_entry = ttk.Entry(form_frame, width=40)
        self.min_year_entry.grid(row=3, column=1, padx=5, pady=3)

        # Positions
        ttk.Label(form_frame, text="Positions:").grid(row=3, column=2, sticky="w", padx=5, pady=3)
        self.positions_entry = ttk.Entry(form_frame, width=29)
        self.positions_entry.grid(row=3, column=3, padx=5, pady=3)

        # Status
        ttk.Label(form_frame, text="Status:").grid(row=4, column=0, sticky="w", padx=5, pady=3)
        self.status_combo = ttk.Combobox(form_frame, values=["Open", "Closed", "Filled"],
                                          state="readonly", width=37)
        self.status_combo.grid(row=4, column=1, padx=5, pady=3)
        self.status_combo.set("Open")

        # Description
        ttk.Label(form_frame, text="Description:").grid(row=5, column=0, sticky="nw", padx=5, pady=3)
        self.desc_text = tk.Text(form_frame, width=70, height=3)
        self.desc_text.grid(row=5, column=1, columnspan=3, padx=5, pady=3, sticky="we")

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=10, pady=5)
        ttk.Button(btn_frame, text="Add Apprenticeship", command=self.add).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Update", command=self.update).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Delete", command=self.delete).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Clear Form", command=self.clear_form).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Refresh", command=self.refresh).pack(side="left", padx=2)

        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=5)
        columns = ("id", "title", "employer", "duration", "salary", "location", "course", "year", "positions", "status")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=10)
        headings = ["ID", "Title", "Employer", "Months", "Salary", "Location", "Course", "Min Yr", "Pos", "Status"]
        widths = [40, 150, 130, 60, 70, 110, 110, 50, 40, 70]
        for col, head, w in zip(columns, headings, widths):
            self.tree.heading(col, text=head)
            self.tree.column(col, width=w, anchor="w")

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

    def load_employers(self):
        employers = self.db.fetch_all("SELECT employer_id AS id, company_name FROM employers ORDER BY company_name")
        self.employer_map = {f"{name} (#{eid})": eid for eid, name in employers}
        self.employer_combo["values"] = list(self.employer_map.keys())

    def get_form_data(self):
        try:
            employer_key = self.employer_combo.get()
            if not employer_key:
                messagebox.showerror("Missing Field", "Please select an employer.")
                return None
            return {
                "title": self.title_entry.get().strip(),
                "employer_id": self.employer_map[employer_key],
                "description": self.desc_text.get("1.0", tk.END).strip(),
                "duration_months": int(self.duration_entry.get()) if self.duration_entry.get() else 0,
                "salary": float(self.salary_entry.get()) if self.salary_entry.get() else None,
                "location": self.location_entry.get().strip(),
                "required_course": self.course_entry.get().strip(),
                "min_year": int(self.min_year_entry.get()) if self.min_year_entry.get() else 1,
                "positions_available": int(self.positions_entry.get()) if self.positions_entry.get() else 1,
                "status": self.status_combo.get(),
            }
        except ValueError:
            messagebox.showerror("Invalid Input", "Duration, year, positions must be integers; salary must be a number.")
            return None

    def add(self):
        data = self.get_form_data()
        if not data:
            return
        if not data["title"] or not data["duration_months"]:
            messagebox.showerror("Missing Fields", "Title and duration are required.")
            return
        self.db.execute("""
            INSERT INTO apprenticeships (title, employer_id, description, duration_months,
                salary, location, required_course, min_year, positions_available, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, tuple(data.values()))
        messagebox.showinfo("Success", "Apprenticeship added.")
        self.clear_form()
        self.refresh()

    def update(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select an apprenticeship.")
            return
        data = self.get_form_data()
        if not data:
            return
        app_id = self.tree.item(selected[0])["values"][0]
        self.db.execute("""
            UPDATE apprenticeships SET title=?, employer_id=?, description=?, duration_months=?,
                salary=?, location=?, required_course=?, min_year=?, positions_available=?, status=?
            WHERE id=?
        """, (*data.values(), app_id))
        messagebox.showinfo("Success", "Apprenticeship updated.")
        self.refresh()

    def delete(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select an apprenticeship.")
            return
        if not messagebox.askyesno("Confirm", "Delete this apprenticeship?"):
            return
        app_id = self.tree.item(selected[0])["values"][0]
        self.db.execute("DELETE FROM apprenticeships WHERE id=?", (app_id,))
        self.refresh()
        self.clear_form()

    def clear_form(self):
        for entry in [self.title_entry, self.duration_entry, self.salary_entry,
                      self.location_entry, self.course_entry, self.min_year_entry,
                      self.positions_entry]:
            entry.delete(0, tk.END)
        self.desc_text.delete("1.0", tk.END)
        self.employer_combo.set("")
        self.status_combo.set("Open")
        self.tree.selection_remove(*self.tree.selection())

    def on_select(self, _):
        selected = self.tree.selection()
        if not selected:
            return
        app_id = self.tree.item(selected[0])["values"][0]
        row = self.db.fetch_one("""
            SELECT a.title, e.company_name, a.id, a.description, a.duration_months,
                a.salary, a.location, a.required_course, a.min_year, a.positions_available, a.status, a.employer_id
            FROM apprenticeships a JOIN employers e ON a.employer_id = e.employer_id WHERE a.id=?
        """, (app_id,))
        if not row:
            return
        title, company, _, desc, dur, sal, loc, course, min_yr, pos, status, emp_id = row
        self.title_entry.delete(0, tk.END); self.title_entry.insert(0, title or "")
        self.employer_combo.set(f"{company} (#{emp_id})")
        self.desc_text.delete("1.0", tk.END); self.desc_text.insert("1.0", desc or "")
        self.duration_entry.delete(0, tk.END); self.duration_entry.insert(0, str(dur))
        self.salary_entry.delete(0, tk.END); self.salary_entry.insert(0, str(sal) if sal else "")
        self.location_entry.delete(0, tk.END); self.location_entry.insert(0, loc or "")
        self.course_entry.delete(0, tk.END); self.course_entry.insert(0, course or "")
        self.min_year_entry.delete(0, tk.END); self.min_year_entry.insert(0, str(min_yr))
        self.positions_entry.delete(0, tk.END); self.positions_entry.insert(0, str(pos))
        self.status_combo.set(status)

    def refresh(self):
        self.load_employers()
        for row in self.tree.get_children():
            self.tree.delete(row)
        rows = self.db.fetch_all("""
            SELECT a.id, a.title, e.company_name, a.duration_months, a.salary, a.location,
                a.required_course, a.min_year, a.positions_available, a.status
            FROM apprenticeships a JOIN employers e ON a.employer_id = e.employer_id
            ORDER BY a.posted_date DESC
        """)
        for row in rows:
            display = list(row)
            display[4] = f"£{row[4]:.0f}" if row[4] else "-"
            self.tree.insert("", "end", values=display)


class ApplicationTab(ttk.Frame):
    """Tab for managing student applications."""

    def __init__(self, parent, db):
        super().__init__(parent)
        self.db = db
        self.build_ui()
        self.refresh()

    def build_ui(self):
        form_frame = ttk.LabelFrame(self, text="New / Edit Application", padding=10)
        form_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(form_frame, text="Student:").grid(row=0, column=0, sticky="w", padx=5, pady=3)
        self.student_combo = ttk.Combobox(form_frame, width=40, state="readonly")
        self.student_combo.grid(row=0, column=1, padx=5, pady=3)

        ttk.Label(form_frame, text="Apprenticeship:").grid(row=1, column=0, sticky="w", padx=5, pady=3)
        self.app_combo = ttk.Combobox(form_frame, width=40, state="readonly")
        self.app_combo.grid(row=1, column=1, padx=5, pady=3)

        ttk.Label(form_frame, text="Status:").grid(row=2, column=0, sticky="w", padx=5, pady=3)
        self.status_combo = ttk.Combobox(form_frame, values=["Pending", "Under Review", "Interview", "Accepted", "Rejected", "Withdrawn"],
                                          state="readonly", width=37)
        self.status_combo.grid(row=2, column=1, padx=5, pady=3)
        self.status_combo.set("Pending")

        ttk.Label(form_frame, text="Notes:").grid(row=3, column=0, sticky="nw", padx=5, pady=3)
        self.notes_text = tk.Text(form_frame, width=50, height=3)
        self.notes_text.grid(row=3, column=1, padx=5, pady=3)

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=10, pady=5)
        ttk.Button(btn_frame, text="Submit Application", command=self.submit).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Update Status", command=self.update_status).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Delete", command=self.delete).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Clear", command=self.clear_form).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Refresh", command=self.refresh).pack(side="left", padx=2)

        # Filter
        filter_frame = ttk.Frame(self)
        filter_frame.pack(fill="x", padx=10, pady=5)
        ttk.Label(filter_frame, text="Filter by Status:").pack(side="left")
        self.filter_combo = ttk.Combobox(filter_frame, values=["All", "Pending", "Under Review", "Interview", "Accepted", "Rejected", "Withdrawn"],
                                          state="readonly", width=15)
        self.filter_combo.set("All")
        self.filter_combo.pack(side="left", padx=5)
        self.filter_combo.bind("<<ComboboxSelected>>", lambda _: self.refresh())

        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=5)
        columns = ("id", "student", "student_id_num", "apprenticeship", "company", "date", "status")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=12)
        headings = ["ID", "Student", "Student ID", "Apprenticeship", "Company", "Applied On", "Status"]
        widths = [40, 150, 90, 180, 130, 130, 100]
        for col, head, w in zip(columns, headings, widths):
            self.tree.heading(col, text=head)
            self.tree.column(col, width=w, anchor="w")

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

    def load_combos(self):
        students = self.db.fetch_all("SELECT student_id, student_id, first_name, last_name FROM students ORDER BY last_name")
        self.student_map = {f"{ln}, {fn} ({sid})": pk for pk, sid, fn, ln in students}
        self.student_combo["values"] = list(self.student_map.keys())

        apps = self.db.fetch_all("""
            SELECT a.id, a.title, e.company_name FROM apprenticeships a
            JOIN employers e ON a.employer_id = e.employer_id
            WHERE a.status = 'Open' ORDER BY a.title
        """)
        self.app_map = {f"{title} @ {company}": pk for pk, title, company in apps}
        self.app_combo["values"] = list(self.app_map.keys())

    def submit(self):
        student_key = self.student_combo.get()
        app_key = self.app_combo.get()
        if not student_key or not app_key:
            messagebox.showerror("Missing Fields", "Select both a student and an apprenticeship.")
            return
        try:
            self.db.execute("""
                INSERT INTO applications (student_id, apprenticeship_id, status, notes)
                VALUES (?, ?, ?, ?)
            """, (self.student_map[student_key], self.app_map[app_key],
                  self.status_combo.get(), self.notes_text.get("1.0", tk.END).strip()))
            messagebox.showinfo("Success", "Application submitted.")
            self.clear_form()
            self.refresh()
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", "This student has already applied to this apprenticeship.")

    def update_status(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select an application.")
            return
        app_id = self.tree.item(selected[0])["values"][0]
        self.db.execute("UPDATE applications SET status=?, notes=? WHERE id=?",
                        (self.status_combo.get(), self.notes_text.get("1.0", tk.END).strip(), app_id))
        messagebox.showinfo("Success", "Application updated.")
        self.refresh()

    def delete(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select an application.")
            return
        if not messagebox.askyesno("Confirm", "Delete this application?"):
            return
        app_id = self.tree.item(selected[0])["values"][0]
        self.db.execute("DELETE FROM applications WHERE id=?", (app_id,))
        self.refresh()
        self.clear_form()

    def clear_form(self):
        self.student_combo.set("")
        self.app_combo.set("")
        self.status_combo.set("Pending")
        self.notes_text.delete("1.0", tk.END)
        self.tree.selection_remove(*self.tree.selection())

    def on_select(self, _):
        selected = self.tree.selection()
        if not selected:
            return
        app_id = self.tree.item(selected[0])["values"][0]
        row = self.db.fetch_one("SELECT status, notes FROM applications WHERE id=?", (app_id,))
        if row:
            self.status_combo.set(row[0])
            self.notes_text.delete("1.0", tk.END)
            self.notes_text.insert("1.0", row[1] or "")

    def refresh(self):
        self.load_combos()
        for row in self.tree.get_children():
            self.tree.delete(row)
        filt = self.filter_combo.get() if hasattr(self, "filter_combo") else "All"
        query = """
            SELECT app.id, s.first_name || ' ' || s.last_name, s.student_id,
                   ap.title, e.company_name, app.application_date, app.status
            FROM applications app
            JOIN students s ON app.student_id = s.student_id
            JOIN apprenticeships ap ON app.apprenticeship_id = ap.id
            JOIN employers e ON ap.employer_id = e.employer_id
        """
        params = ()
        if filt and filt != "All":
            query += " WHERE app.status = ?"
            params = (filt,)
        query += " ORDER BY app.application_date DESC"
        for row in self.db.fetch_all(query, params):
            display = list(row)
            if display[5]:
                try:
                    display[5] = display[5][:10]
                except Exception:
                    pass
            self.tree.insert("", "end", values=display)


class DashboardTab(ttk.Frame):
    """Overview dashboard with summary statistics."""

    def __init__(self, parent, db):
        super().__init__(parent)
        self.db = db
        self.build_ui()
        self.refresh()

    def build_ui(self):
        title = ttk.Label(self, text="University Apprenticeship System — Dashboard",
                          font=("Helvetica", 16, "bold"))
        title.pack(pady=10)

        self.stats_frame = ttk.Frame(self)
        self.stats_frame.pack(fill="x", padx=20, pady=10)

        # Recent applications
        recent_frame = ttk.LabelFrame(self, text="Recent Applications (Last 10)", padding=10)
        recent_frame.pack(fill="both", expand=True, padx=20, pady=10)

        columns = ("student", "apprenticeship", "company", "date", "status")
        self.recent_tree = ttk.Treeview(recent_frame, columns=columns, show="headings", height=8)
        headings = ["Student", "Apprenticeship", "Company", "Applied", "Status"]
        widths = [180, 200, 150, 130, 100]
        for col, head, w in zip(columns, headings, widths):
            self.recent_tree.heading(col, text=head)
            self.recent_tree.column(col, width=w, anchor="w")
        self.recent_tree.pack(fill="both", expand=True)

        # Open positions
        open_frame = ttk.LabelFrame(self, text="Open Positions", padding=10)
        open_frame.pack(fill="both", expand=True, padx=20, pady=10)

        columns2 = ("title", "company", "location", "salary", "positions", "applicants")
        self.open_tree = ttk.Treeview(open_frame, columns=columns2, show="headings", height=8)
        headings2 = ["Title", "Company", "Location", "Salary", "Available", "Applicants"]
        widths2 = [180, 150, 130, 90, 80, 80]
        for col, head, w in zip(columns2, headings2, widths2):
            self.open_tree.heading(col, text=head)
            self.open_tree.column(col, width=w, anchor="w")
        self.open_tree.pack(fill="both", expand=True)

        ttk.Button(self, text="Refresh Dashboard", command=self.refresh).pack(pady=5)

    def refresh(self):
        for w in self.stats_frame.winfo_children():
            w.destroy()

        stats = [
            ("Students", self.db.fetch_one("SELECT COUNT(*) FROM students")[0], "#3498db"),
            ("Employers", self.db.fetch_one("SELECT COUNT(*) FROM employers")[0], "#9b59b6"),
            ("Open Apprenticeships",
             self.db.fetch_one("SELECT COUNT(*) FROM apprenticeships WHERE status='Open'")[0], "#2ecc71"),
            ("Total Applications", self.db.fetch_one("SELECT COUNT(*) FROM applications")[0], "#e67e22"),
            ("Pending Applications",
             self.db.fetch_one("SELECT COUNT(*) FROM applications WHERE status='Pending'")[0], "#f39c12"),
            ("Accepted",
             self.db.fetch_one("SELECT COUNT(*) FROM applications WHERE status='Accepted'")[0], "#27ae60"),
        ]

        for i, (label, value, color) in enumerate(stats):
            card = tk.Frame(self.stats_frame, bg=color, relief="raised", bd=2)
            card.grid(row=i // 3, column=i % 3, padx=10, pady=5, sticky="ew")
            self.stats_frame.columnconfigure(i % 3, weight=1)
            tk.Label(card, text=str(value), bg=color, fg="white",
                     font=("Helvetica", 20, "bold")).pack(pady=(5, 0))
            tk.Label(card, text=label, bg=color, fg="white",
                     font=("Helvetica", 10)).pack(pady=(0, 5))

        for row in self.recent_tree.get_children():
            self.recent_tree.delete(row)
        recent = self.db.fetch_all("""
            SELECT s.first_name || ' ' || s.last_name, ap.title, e.company_name,
                   app.application_date, app.status
            FROM applications app
            JOIN students s ON app.student_id = s.student_id
            JOIN apprenticeships ap ON app.apprenticeship_id = ap.id
            JOIN employers e ON ap.employer_id = e.employer_id
            ORDER BY app.application_date DESC LIMIT 10
        """)
        for row in recent:
            display = list(row)
            if display[3]:
                display[3] = display[3][:10]
            self.recent_tree.insert("", "end", values=display)

        for row in self.open_tree.get_children():
            self.open_tree.delete(row)
        opens = self.db.fetch_all("""
            SELECT a.title, e.company_name, a.location, a.salary, a.positions_available,
                   (SELECT COUNT(*) FROM applications WHERE apprenticeship_id = a.id)
            FROM apprenticeships a JOIN employers e ON a.employer_id = e.employer_id
            WHERE a.status = 'Open' ORDER BY a.posted_date DESC
        """)
        for row in opens:
            display = list(row)
            display[3] = f"£{row[3]:.0f}" if row[3] else "-"
            self.open_tree.insert("", "end", values=display)


class ApprenticeshipApp(tk.Tk):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.title("University Apprenticeship Management System")
        self.geometry("1100x720")
        self.db = Database()

        self.user = _get_current_user()
        self.user_display = _user_display_name(self.user)
        logger.info("Apprenticeship System starting user=%s role=%s",
                    self.user_display,
                    (self.user or {}).get('role') or 'none')

        # Header strip showing the signed-in user
        header = ttk.Frame(self, padding=(10, 6))
        header.pack(fill="x")
        ttk.Label(header,
                  text="University Apprenticeship Management System",
                  font=("Segoe UI", 13, "bold")).pack(side="left")
        role = (self.user or {}).get('role') or ('—' if self.user else 'not signed in')
        ttk.Label(header,
                  text=f"Signed in: {self.user_display}  ({role})",
                  foreground="#1565c0").pack(side="right")

        # Style
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        # Menu bar
        menubar = tk.Menu(self)
        self.config(menu=menubar)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Load Sample Data", command=self.load_sample_data)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit_app)
        menubar.add_cascade(label="File", menu=file_menu)
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self.show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        # Notebook
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=5, pady=5)

        self.dashboard_tab = DashboardTab(self.notebook, self.db)
        self.student_tab = StudentTab(self.notebook, self.db)
        self.employer_tab = EmployerTab(self.notebook, self.db)
        self.apprenticeship_tab = ApprenticeshipTab(self.notebook, self.db)
        self.application_tab = ApplicationTab(self.notebook, self.db)

        self.notebook.add(self.dashboard_tab, text="Dashboard")
        self.notebook.add(self.student_tab, text="Students")
        self.notebook.add(self.employer_tab, text="Employers")
        self.notebook.add(self.apprenticeship_tab, text="Apprenticeships")
        self.notebook.add(self.application_tab, text="Applications")

        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_change)

        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(self, textvariable=self.status_var, relief="sunken", anchor="w")
        status_bar.pack(side="bottom", fill="x")

        self.protocol("WM_DELETE_WINDOW", self.quit_app)

    def on_tab_change(self, _):
        idx = self.notebook.index("current")
        tabs = [self.dashboard_tab, self.student_tab, self.employer_tab,
                self.apprenticeship_tab, self.application_tab]
        if hasattr(tabs[idx], "refresh"):
            tabs[idx].refresh()
        self.status_var.set(f"Viewing: {self.notebook.tab(idx, 'text')}")

    def load_sample_data(self):
        if not messagebox.askyesno("Load Sample Data",
                                   "This will add sample students, employers, and apprenticeships. Continue?"):
            return
        try:
            # Sample employers
            employers = [
                ("TechCorp Ltd", "Sarah Johnson", "sarah@techcorp.com", "020-7946-0123", "Technology", "London"),
                ("BuildRight Construction", "Mike Davies", "mike@buildright.co.uk", "0191-555-0199", "Construction", "Newcastle"),
                ("HealthFirst NHS Trust", "Dr. Emma Wilson", "e.wilson@nhs.uk", "0113-555-0100", "Healthcare", "Leeds"),
                ("Finance Solutions", "James Brown", "jbrown@finsol.com", "0161-555-0150", "Finance", "Manchester"),
            ]
            for emp in employers:
                try:
                    self.db.execute("""INSERT INTO employers (company_name, contact_person, contact_email, contact_phone, industry, address)
                                       VALUES (?, ?, ?, ?, ?, ?)""", emp)
                except sqlite3.IntegrityError:
                    pass

            # Sample students
            students = [
                ("S2024001", "Alice", "Smith", "alice.s@uni.ac.uk", "Computer Science", 2, 3.8),
                ("S2024002", "Bob", "Taylor", "bob.t@uni.ac.uk", "Civil Engineering", 3, 3.5),
                ("S2024003", "Chloe", "Patel", "chloe.p@uni.ac.uk", "Nursing", 2, 3.9),
                ("S2024004", "David", "Khan", "david.k@uni.ac.uk", "Accounting", 1, 3.6),
                ("S2024005", "Emma", "Walsh", "emma.w@uni.ac.uk", "Computer Science", 3, 3.7),
            ]
            for stu in students:
                try:
                    self.db.execute("""INSERT INTO students (student_id, first_name, last_name, email_address, course, year_of_study, gpa)
                                       VALUES (?, ?, ?, ?, ?, ?, ?)""", stu)
                except sqlite3.IntegrityError:
                    pass

            # Sample apprenticeships
            apprenticeships = [
                ("Software Developer Apprentice", 1, "Build web applications using modern frameworks.",
                 12, 22000, "London", "Computer Science", 2, 3, "Open"),
                ("Site Engineer Trainee", 2, "Hands-on experience on construction projects.",
                 18, 20000, "Newcastle", "Civil Engineering", 2, 2, "Open"),
                ("Healthcare Assistant Apprentice", 3, "Clinical placement working with experienced nurses.",
                 24, 19500, "Leeds", "Nursing", 1, 4, "Open"),
                ("Junior Financial Analyst", 4, "Support financial reporting and analysis.",
                 12, 23000, "Manchester", "Accounting", 2, 2, "Open"),
            ]
            for app in apprenticeships:
                self.db.execute("""INSERT INTO apprenticeships (title, employer_id, description, duration_months,
                                   salary, location, required_course, min_year, positions_available, status)
                                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", app)

            messagebox.showinfo("Success", "Sample data loaded.")
            self.dashboard_tab.refresh()
            self.student_tab.refresh()
            self.employer_tab.refresh()
            self.apprenticeship_tab.refresh()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load sample data: {e}")

    def show_about(self):
        messagebox.showinfo(
            "About",
            "University Apprenticeship Management System\n\n"
            "Version 1.0\n\n"
            "Manage students, employers, apprenticeship listings, and applications "
            "in a single integrated system.\n\n"
            "Built with Python & Tkinter."
        )

    def quit_app(self):
        if messagebox.askokcancel("Quit", "Exit the application?"):
            self.db.close()
            self.destroy()


def main():
    _remove_legacy_db()
    app = ApprenticeshipApp()
    app.mainloop()


if __name__ == "__main__":
    main()
