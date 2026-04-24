"""
University Absence Tracker

Integrated into the Education System:
  - No login screen (receives the caller's user context via argv)
  - Uses the main university database (DEFAULT_DB_PATH)
  - Uses real users / students / staff / modules / attendance tables
"""

import argparse
import logging
import sqlite3
import sys
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, date

from education_system.university_system.core.paths import DEFAULT_DB_PATH

logger = logging.getLogger("absence_tracker")
if not logger.handlers:
    logger.setLevel(logging.INFO)
    logger.addHandler(logging.StreamHandler())


# ---------------------------------------------------------------------------
# Database layer (backed by the main student_records.db)
# ---------------------------------------------------------------------------
class Database:
    """Read/write absence data against the main university database."""

    def __init__(self, path=None):
        self.path = path or str(DEFAULT_DB_PATH)
        self.conn = sqlite3.connect(self.path)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.cur = self.conn.cursor()
        self._ensure_absence_requests_table()

    def _ensure_absence_requests_table(self):
        """`absence_requests` isn't part of the core schema — create if missing."""
        self.cur.execute(
            """CREATE TABLE IF NOT EXISTS absence_requests (
                 id           INTEGER PRIMARY KEY AUTOINCREMENT,
                 student_id   TEXT NOT NULL,
                 module_code  TEXT NOT NULL,
                 date         TEXT NOT NULL,
                 reason       TEXT NOT NULL,
                 status       TEXT NOT NULL DEFAULT 'pending'
                              CHECK(status IN ('pending','approved','rejected')),
                 submitted_at TEXT DEFAULT CURRENT_TIMESTAMP
               )"""
        )
        self.conn.commit()

    # ---- User identity ----
    def lookup_user_by_username(self, username):
        self.cur.execute(
            """SELECT id, username, role, first_name, last_name, email, student_id
               FROM users WHERE username = ?""",
            (username,),
        )
        row = self.cur.fetchone()
        if not row:
            return None
        uid, uname, role, first, last, email, sid = row
        name = (f"{first or ''} {last or ''}").strip() or uname
        return {
            "id": uid,
            "username": uname,
            "role": role,
            "name": name,
            "email": email,
            "student_id": sid,
        }

    # ---- Users (read-only views) ----
    def get_users(self, role=None):
        """Return (id, username, role, name, email) rows."""
        if role == "student":
            self.cur.execute(
                """SELECT s.student_id,
                          COALESCE(u.username, s.student_id),
                          'student',
                          TRIM(COALESCE(s.first_name,'') || ' ' || COALESCE(s.last_name,'')),
                          s.email_address
                   FROM students s
                   LEFT JOIN users u ON u.student_id = s.student_id
                   ORDER BY s.last_name, s.first_name"""
            )
            return self.cur.fetchall()
        if role in ("staff", "instructor", "admin"):
            self.cur.execute(
                """SELECT id, username, role,
                          TRIM(COALESCE(first_name,'') || ' ' || COALESCE(last_name,'')),
                          email
                   FROM users WHERE role = ? ORDER BY last_name, first_name""",
                (role,),
            )
            return self.cur.fetchall()
        self.cur.execute(
            """SELECT id, username, role,
                      TRIM(COALESCE(first_name,'') || ' ' || COALESCE(last_name,'')),
                      email
               FROM users ORDER BY role, last_name, first_name"""
        )
        return self.cur.fetchall()

    # ---- Courses (modules) ----
    def get_courses(self, staff_id=None, student_id=None):
        """Return (module_code, module_code, module_name, instructor) rows."""
        if staff_id is not None:
            self.cur.execute(
                """SELECT m.module_code, m.module_code, m.module_name,
                          COALESCE(m.instructor, '')
                   FROM modules m
                   JOIN instructor_modules im ON im.module_code = m.module_code
                   WHERE im.instructor_id = ?
                   ORDER BY m.module_code""",
                (staff_id,),
            )
        elif student_id is not None:
            self.cur.execute(
                """SELECT DISTINCT m.module_code, m.module_code, m.module_name,
                          COALESCE(m.instructor, '')
                   FROM modules m
                   JOIN student_modules sm ON sm.module_code = m.module_code
                   WHERE sm.student_id = ?
                   ORDER BY m.module_code""",
                (student_id,),
            )
        else:
            self.cur.execute(
                """SELECT module_code, module_code, module_name,
                          COALESCE(instructor, '')
                   FROM modules ORDER BY module_code"""
            )
        return self.cur.fetchall()

    # ---- Roster ----
    def get_course_students(self, module_code):
        self.cur.execute(
            """SELECT s.student_id,
                      TRIM(COALESCE(s.first_name,'') || ' ' || COALESCE(s.last_name,'')),
                      COALESCE(u.username, s.student_id),
                      s.email_address
               FROM student_modules sm
               JOIN students s ON s.student_id = sm.student_id
               LEFT JOIN users u ON u.student_id = s.student_id
               WHERE sm.module_code = ?
               ORDER BY s.last_name, s.first_name""",
            (module_code,),
        )
        return self.cur.fetchall()

    # ---- Attendance / absences ----
    def record_absence(self, student_id, module_code, d, status, reason, recorded_by=None):
        self.cur.execute(
            """INSERT INTO attendance (student_id, module_code, date, status, reason)
               VALUES (?, ?, ?, ?, ?)""",
            (student_id, module_code, d, status, reason),
        )
        self.conn.commit()

    def get_absences(self, student_id=None, course_id=None):
        q = """SELECT a.id,
                      TRIM(COALESCE(s.first_name,'') || ' ' || COALESCE(s.last_name,'')),
                      a.module_code,
                      COALESCE(m.module_name, a.module_code),
                      a.date, a.status, COALESCE(a.reason,'')
               FROM attendance a
               LEFT JOIN students s ON s.student_id = a.student_id
               LEFT JOIN modules m  ON m.module_code = a.module_code
               WHERE 1=1"""
        params = []
        if student_id is not None:
            q += " AND a.student_id = ?"
            params.append(student_id)
        if course_id is not None:
            q += " AND a.module_code = ?"
            params.append(course_id)
        q += " ORDER BY a.date DESC"
        self.cur.execute(q, params)
        return self.cur.fetchall()

    def delete_absence(self, absence_id):
        self.cur.execute("DELETE FROM attendance WHERE id = ?", (absence_id,))
        self.conn.commit()

    def get_student_stats(self, student_id):
        self.cur.execute(
            """SELECT m.module_code, m.module_name,
                      SUM(CASE WHEN a.status='absent'  THEN 1 ELSE 0 END),
                      SUM(CASE WHEN a.status='late'    THEN 1 ELSE 0 END),
                      SUM(CASE WHEN a.status='excused' THEN 1 ELSE 0 END),
                      SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END)
               FROM modules m
               JOIN student_modules sm ON sm.module_code = m.module_code
               LEFT JOIN attendance a
                      ON a.module_code = m.module_code AND a.student_id = sm.student_id
               WHERE sm.student_id = ?
               GROUP BY m.module_code, m.module_name
               ORDER BY m.module_code""",
            (student_id,),
        )
        return self.cur.fetchall()

    # ---- Absence requests ----
    def submit_request(self, student_id, module_code, d, reason):
        self.cur.execute(
            """INSERT INTO absence_requests (student_id, module_code, date, reason)
               VALUES (?, ?, ?, ?)""",
            (student_id, module_code, d, reason),
        )
        self.conn.commit()

    def get_requests(self, student_id=None, staff_id=None, status=None):
        q = """SELECT r.id,
                      TRIM(COALESCE(s.first_name,'') || ' ' || COALESCE(s.last_name,'')),
                      r.module_code,
                      COALESCE(m.module_name, r.module_code),
                      r.date, r.reason, r.status, r.submitted_at,
                      r.student_id, r.module_code
               FROM absence_requests r
               LEFT JOIN students s ON s.student_id = r.student_id
               LEFT JOIN modules m  ON m.module_code = r.module_code
               WHERE 1=1"""
        params = []
        if student_id is not None:
            q += " AND r.student_id = ?"
            params.append(student_id)
        if staff_id is not None:
            q += """ AND r.module_code IN (
                        SELECT module_code FROM instructor_modules WHERE instructor_id = ?
                     )"""
            params.append(staff_id)
        if status is not None:
            q += " AND r.status = ?"
            params.append(status)
        q += " ORDER BY r.submitted_at DESC"
        self.cur.execute(q, params)
        return self.cur.fetchall()

    def update_request(self, request_id, new_status):
        self.cur.execute(
            "UPDATE absence_requests SET status = ? WHERE id = ?",
            (new_status, request_id),
        )
        self.conn.commit()

    def close(self):
        self.conn.close()


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def valid_date(s):
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def center(win, w, h):
    win.update_idletasks()
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")


# ---------------------------------------------------------------------------
# Base dashboard
# ---------------------------------------------------------------------------
class BaseDashboard:
    def __init__(self, root, db, user, on_logout=None):
        self.root = root
        self.db = db
        self.user = user
        self.on_logout = on_logout

        role = (user.get("role") or "user").title()
        root.title(f"Absence Tracker - {role}: {user['name']}")
        center(root, 1100, 680)
        root.configure(bg="#f0f4f8")

        header = tk.Frame(root, bg="#1e3a5f", height=60)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(
            header, text=f"🎓 {role} Dashboard",
            font=("Arial", 16, "bold"), bg="#1e3a5f", fg="white",
        ).pack(side="left", padx=20)

        tk.Button(
            header, text="Close", font=("Arial", 10, "bold"),
            bg="#dc2626", fg="white", activebackground="#b91c1c",
            relief="flat", cursor="hand2", command=self._close,
        ).pack(side="right", padx=20, pady=15)

        tk.Label(
            header, text=f"Welcome, {user['name']}",
            font=("Arial", 11), bg="#1e3a5f", fg="#cbd5e1",
        ).pack(side="right", padx=10)

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(expand=True, fill="both", padx=10, pady=10)

        style = ttk.Style()
        style.configure("Treeview", rowheight=26, font=("Arial", 10))
        style.configure("Treeview.Heading", font=("Arial", 10, "bold"))

        self.build_tabs()

    def build_tabs(self):
        raise NotImplementedError

    def _close(self):
        if self.on_logout:
            self.on_logout()
        else:
            self.root.destroy()

    @staticmethod
    def clear_tree(tree):
        for item in tree.get_children():
            tree.delete(item)


# ---------------------------------------------------------------------------
# Admin dashboard (read-only views over real data)
# ---------------------------------------------------------------------------
class AdminDashboard(BaseDashboard):
    def build_tabs(self):
        self._users_tab()
        self._courses_tab()
        self._enrollments_tab()
        self._all_absences_tab()
        self._reports_tab()
        try:
            from education_system.university_system.modules.domain.academics.services.attendance.absence_tracking \
                import admin_features as af
            ctx = af.AdminContext(db=self.db, parent=self.root, user=self.user)
            af.build_admin_tab(self.notebook, ctx)
        except Exception:
            logger.exception("failed to build admin tools tab")
            messagebox.showwarning(
                "Admin Tools",
                "The Admin Tools tab failed to load (see log).",
                parent=self.root,
            )
        try:
            from education_system.university_system.modules.domain.academics.services.attendance.absence_tracking \
                import absence_enhancements as ae
            ae.bootstrap(self, "admin")
        except Exception:
            logger.exception("failed to bootstrap enhancements (admin)")

    def _users_tab(self):
        f = ttk.Frame(self.notebook)
        self.notebook.add(f, text="👥 Users")

        bar = tk.Frame(f)
        bar.pack(fill="x", padx=10, pady=10)
        tk.Label(bar, text="User management lives in the main system; this view is read-only.",
                 fg="#6b7280").pack(side="left", padx=4)
        tk.Button(bar, text="🔄 Refresh", bg="#6b7280", fg="white",
                  relief="flat", padx=12, pady=6, cursor="hand2",
                  command=self._refresh_users).pack(side="right", padx=4)

        cols = ("ID", "Username", "Role", "Name", "Email")
        self.users_tree = ttk.Treeview(f, columns=cols, show="headings")
        for c, w in zip(cols, (100, 140, 100, 220, 240)):
            self.users_tree.heading(c, text=c)
            self.users_tree.column(c, width=w)
        self.users_tree.pack(expand=True, fill="both", padx=10, pady=(0, 10))
        self._refresh_users()

    def _refresh_users(self):
        self.clear_tree(self.users_tree)
        for row in self.db.get_users():
            self.users_tree.insert("", "end", values=row)

    def _courses_tab(self):
        f = ttk.Frame(self.notebook)
        self.notebook.add(f, text="📚 Modules")

        bar = tk.Frame(f)
        bar.pack(fill="x", padx=10, pady=10)
        tk.Button(bar, text="🔄 Refresh", bg="#6b7280", fg="white",
                  relief="flat", padx=12, pady=6, cursor="hand2",
                  command=self._refresh_courses).pack(side="left", padx=4)

        cols = ("ID", "Code", "Name", "Instructor")
        self.courses_tree = ttk.Treeview(f, columns=cols, show="headings")
        for c, w in zip(cols, (100, 100, 360, 220)):
            self.courses_tree.heading(c, text=c)
            self.courses_tree.column(c, width=w)
        self.courses_tree.pack(expand=True, fill="both", padx=10, pady=(0, 10))
        self._refresh_courses()

    def _refresh_courses(self):
        self.clear_tree(self.courses_tree)
        for row in self.db.get_courses():
            self.courses_tree.insert("", "end", values=row)

    def _enrollments_tab(self):
        f = ttk.Frame(self.notebook)
        self.notebook.add(f, text="📝 Enrollments")

        top = tk.Frame(f)
        top.pack(fill="x", padx=10, pady=10)

        tk.Label(top, text="Module:").grid(row=0, column=0, sticky="w", padx=5)
        courses = self.db.get_courses()
        self.crs_map = {f"{c[1]} - {c[2]}": c[0] for c in courses}
        self.crs_var = tk.StringVar()
        ttk.Combobox(top, textvariable=self.crs_var,
                     values=list(self.crs_map.keys()),
                     state="readonly", width=50).grid(row=0, column=1, padx=5)

        tk.Button(top, text="Show Roster", bg="#2563eb", fg="white", relief="flat",
                  padx=12, pady=4,
                  command=self._show_roster).grid(row=0, column=2, padx=5)

        cols = ("Student ID", "Name", "Username", "Email")
        self.roster_tree = ttk.Treeview(f, columns=cols, show="headings")
        for c, w in zip(cols, (120, 240, 150, 240)):
            self.roster_tree.heading(c, text=c)
            self.roster_tree.column(c, width=w)
        self.roster_tree.pack(expand=True, fill="both", padx=10, pady=10)

    def _show_roster(self):
        if not self.crs_var.get():
            messagebox.showerror("Error", "Select a module.")
            return
        self.clear_tree(self.roster_tree)
        for row in self.db.get_course_students(self.crs_map[self.crs_var.get()]):
            self.roster_tree.insert("", "end", values=row)

    def _all_absences_tab(self):
        f = ttk.Frame(self.notebook)
        self.notebook.add(f, text="📋 All Absences")

        bar = tk.Frame(f)
        bar.pack(fill="x", padx=10, pady=10)
        tk.Button(bar, text="🗑 Delete Selected", bg="#dc2626", fg="white",
                  relief="flat", padx=12, pady=6,
                  command=self._delete_abs).pack(side="left", padx=4)
        tk.Button(bar, text="🔄 Refresh", bg="#6b7280", fg="white",
                  relief="flat", padx=12, pady=6,
                  command=self._refresh_abs).pack(side="left", padx=4)

        cols = ("ID", "Student", "Code", "Module", "Date", "Status", "Reason")
        self.abs_tree = ttk.Treeview(f, columns=cols, show="headings")
        widths = (50, 180, 100, 220, 100, 90, 260)
        for c, w in zip(cols, widths):
            self.abs_tree.heading(c, text=c)
            self.abs_tree.column(c, width=w)
        self.abs_tree.pack(expand=True, fill="both", padx=10, pady=(0, 10))
        # #38 filter bar, #40 pagination
        try:
            from education_system.university_system.modules.domain.academics.services.attendance.absence_tracking \
                import absence_enhancements as ae
            self._abs_rows_cache = list(self.db.get_absences())
            ae.add_filter_bar(f, self.abs_tree,
                              lambda: self._abs_rows_cache, list(cols))
            self._abs_paginator = ae.Paginator(
                self.abs_tree, f, lambda: self._abs_rows_cache, page_size=100)
            self._abs_paginator.refresh()
        except Exception:
            logger.exception("pagination wiring (all_absences) failed")
            self._refresh_abs()

    def _refresh_abs(self):
        if hasattr(self, "_abs_paginator"):
            self._abs_rows_cache = list(self.db.get_absences())
            self._abs_paginator.refresh()
            return
        self.clear_tree(self.abs_tree)
        for row in self.db.get_absences():
            self.abs_tree.insert("", "end", values=row)

    def _delete_abs(self):
        sel = self.abs_tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Select an absence record.")
            return
        vals = self.abs_tree.item(sel[0])["values"]
        if messagebox.askyesno("Confirm", f"Delete record #{vals[0]}?"):
            self.db.delete_absence(vals[0])
            self._refresh_abs()

    _REPORT_COLS = ("Module Code", "Module", "Absent", "Late", "Excused", "Present")

    def _reports_tab(self):
        f = ttk.Frame(self.notebook)
        self.notebook.add(f, text="📊 Reports")

        top = tk.Frame(f)
        top.pack(fill="x", padx=10, pady=10)

        tk.Label(top, text="Select student:").pack(side="left", padx=5)
        students = self.db.get_users("student")
        self.rep_map = {
            f"{row[3] or row[1]} ({row[1]})": row[0] for row in students
        }
        self.rep_var = tk.StringVar()
        ttk.Combobox(top, textvariable=self.rep_var,
                     values=list(self.rep_map.keys()),
                     state="readonly", width=45).pack(side="left", padx=5)
        tk.Button(top, text="Generate Report", bg="#2563eb", fg="white",
                  relief="flat", padx=12, pady=4,
                  command=self._gen_report).pack(side="left", padx=5)
        tk.Button(top, text="🗔 Open in new window", bg="#0ea5e9", fg="white",
                  relief="flat", padx=12, pady=4,
                  command=self._open_report_window).pack(side="left", padx=5)

        self.rep_tree = ttk.Treeview(f, columns=self._REPORT_COLS,
                                     show="headings")
        for c, w in zip(self._REPORT_COLS, (120, 280, 80, 80, 80, 80)):
            self.rep_tree.heading(c, text=c)
            self.rep_tree.column(c, width=w, anchor="center")
        self.rep_tree.pack(expand=True, fill="both", padx=10, pady=10)

        self.rep_summary = tk.Label(f, text="", font=("Arial", 11, "bold"),
                                    fg="#1e3a5f")
        self.rep_summary.pack(pady=5)

        # Inline export / email toolbar
        actions = tk.Frame(f)
        actions.pack(fill="x", padx=10, pady=(0, 10))
        tk.Button(actions, text="💾 Save CSV", bg="#16a34a", fg="white",
                  relief="flat", padx=10, pady=4,
                  command=lambda: self._save_report("csv")).pack(side="left", padx=4)
        tk.Button(actions, text="📝 Save TXT", bg="#16a34a", fg="white",
                  relief="flat", padx=10, pady=4,
                  command=lambda: self._save_report("txt")).pack(side="left", padx=4)
        tk.Button(actions, text="📄 Save PDF", bg="#16a34a", fg="white",
                  relief="flat", padx=10, pady=4,
                  command=lambda: self._save_report("pdf")).pack(side="left", padx=4)
        tk.Button(actions, text="✉ Email admin", bg="#2563eb", fg="white",
                  relief="flat", padx=10, pady=4,
                  command=self._email_report).pack(side="left", padx=4)

    def _current_report_rows(self):
        """Re-collect the current report's rows from the tree in display order."""
        return [self.rep_tree.item(i)["values"]
                for i in self.rep_tree.get_children()]

    def _current_report_title(self) -> str:
        name = self.rep_var.get() or "(no student)"
        return f"Attendance report — {name}"

    def _gen_report(self):
        if not self.rep_var.get():
            messagebox.showerror("Error", "Select a student.")
            return
        self.clear_tree(self.rep_tree)
        sid = self.rep_map[self.rep_var.get()]
        total_absent = total_late = 0
        for code, name, a, l, e, p in self.db.get_student_stats(sid):
            a, l, e, p = a or 0, l or 0, e or 0, p or 0
            total_absent += a
            total_late += l
            self.rep_tree.insert("", "end", values=(code, name, a, l, e, p))
        self.rep_summary.config(
            text=f"Total Absent: {total_absent}   |   Total Late: {total_late}"
        )

    def _open_report_window(self):
        """Open the current report in its own window with full export toolbar."""
        rows = self._current_report_rows()
        if not rows:
            messagebox.showwarning("No report",
                                   "Generate a report first.",
                                   parent=self.root)
            return
        try:
            from education_system.university_system.modules.domain.academics.services.attendance.absence_tracking \
                import admin_features as af
            af._report_window(self.root, self._current_report_title(),
                              self._REPORT_COLS, rows,
                              db=self.db, user=self.user)
        except Exception:
            logger.exception("open_report_window failed")
            messagebox.showerror("Error",
                                 "Failed to open the report window.",
                                 parent=self.root)

    def _save_report(self, fmt: str):
        rows = self._current_report_rows()
        if not rows:
            messagebox.showwarning("No report",
                                   "Generate a report first.",
                                   parent=self.root)
            return
        try:
            from education_system.university_system.modules.domain.academics.services.attendance.absence_tracking \
                import admin_features as af
            from tkinter import filedialog as _fd
            title = self._current_report_title()
            if fmt == "csv":
                import csv as _csv
                path = _fd.asksaveasfilename(parent=self.root,
                                             defaultextension=".csv",
                                             initialfile="attendance_report.csv")
                if not path:
                    return
                with open(path, "w", newline="", encoding="utf-8") as fh:
                    w = _csv.writer(fh)
                    w.writerow(self._REPORT_COLS)
                    w.writerows(rows)
            elif fmt == "txt":
                path = _fd.asksaveasfilename(parent=self.root,
                                             defaultextension=".txt",
                                             initialfile="attendance_report.txt")
                if not path:
                    return
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(title + "\n" + ("=" * len(title)) + "\n\n")
                    fh.write(af._rows_to_txt(self._REPORT_COLS, rows))
            elif fmt == "pdf":
                path = _fd.asksaveasfilename(parent=self.root,
                                             defaultextension=".pdf",
                                             initialfile="attendance_report.pdf")
                if not path:
                    return
                af._rows_to_pdf(path, title, self._REPORT_COLS, rows)
            else:
                return
            messagebox.showinfo("Saved", f"Saved: {path}", parent=self.root)
        except Exception as e:
            logger.exception("save_report %s failed", fmt)
            messagebox.showerror("Error", str(e), parent=self.root)

    def _email_report(self):
        rows = self._current_report_rows()
        if not rows:
            messagebox.showwarning("No report",
                                   "Generate a report first.",
                                   parent=self.root)
            return
        try:
            from education_system.university_system.modules.domain.academics.services.attendance.absence_tracking \
                import admin_features as af
            title = self._current_report_title()
            body = af._rows_to_txt(self._REPORT_COLS, rows)
            n = af._email_admin(self.db, f"[Absence Tracker] {title}", body,
                                self.user.get("username", ""))
            if n == 0:
                messagebox.showwarning(
                    "No recipients",
                    "No admin/superadmin users have an email address on file.\n"
                    "Set one in User Management and try again.",
                    parent=self.root)
            else:
                messagebox.showinfo(
                    "Sent",
                    f"Report emailed to {n} admin recipient(s).",
                    parent=self.root)
        except Exception as e:
            logger.exception("email_report failed")
            messagebox.showerror("Error", str(e), parent=self.root)


# ---------------------------------------------------------------------------
# Staff / instructor dashboard
# ---------------------------------------------------------------------------
class StaffDashboard(BaseDashboard):
    def build_tabs(self):
        self.my_courses = self.db.get_courses(staff_id=self.user["id"])
        self._my_courses_tab()
        self._record_tab()
        self._requests_tab()
        self._view_records_tab()
        try:
            from education_system.university_system.modules.domain.academics.services.attendance.absence_tracking \
                import staff_features as stf
            ctx = stf.StaffContext(db=self.db, parent=self.root, user=self.user)
            stf.build_staff_tab(self.notebook, ctx)
        except Exception:
            logger.exception("failed to build staff tools tab")
            messagebox.showwarning(
                "Staff Tools",
                "The Staff Tools tab failed to load (see log).",
                parent=self.root,
            )
        try:
            from education_system.university_system.modules.domain.academics.services.attendance.absence_tracking \
                import absence_enhancements as ae
            ae.bootstrap(self, "staff")
        except Exception:
            logger.exception("failed to bootstrap enhancements (staff)")

    def _my_courses_tab(self):
        f = ttk.Frame(self.notebook)
        self.notebook.add(f, text="📚 My Modules")

        cols = ("Code", "Name", "Instructor")
        tree = ttk.Treeview(f, columns=cols, show="headings")
        for c, w in zip(cols, (120, 500, 220)):
            tree.heading(c, text=c)
            tree.column(c, width=w)
        tree.pack(expand=True, fill="both", padx=10, pady=10)
        for row in self.my_courses:
            tree.insert("", "end", values=(row[1], row[2], row[3]))

        if not self.my_courses:
            tk.Label(f, text="You are not assigned to any modules in instructor_modules.",
                     fg="#6b7280").pack(pady=10)

    def _record_tab(self):
        f = ttk.Frame(self.notebook)
        self.notebook.add(f, text="✏ Record Attendance")

        top = tk.Frame(f)
        top.pack(fill="x", padx=10, pady=10)

        tk.Label(top, text="Module:").grid(row=0, column=0, padx=5, sticky="w")
        self.course_map = {f"{c[1]} - {c[2]}": c[0] for c in self.my_courses}
        self.course_var = tk.StringVar()
        cb = ttk.Combobox(top, textvariable=self.course_var,
                          values=list(self.course_map.keys()),
                          state="readonly", width=40)
        cb.grid(row=0, column=1, padx=5)
        cb.bind("<<ComboboxSelected>>", lambda e: self._load_roster())

        tk.Label(top, text="Date (YYYY-MM-DD):").grid(row=0, column=2, padx=5)
        self.date_entry = tk.Entry(top, width=15)
        self.date_entry.insert(0, date.today().isoformat())
        self.date_entry.grid(row=0, column=3, padx=5)

        tk.Button(top, text="Save Attendance", bg="#16a34a", fg="white",
                  relief="flat", padx=12, pady=4,
                  command=self._save_attendance).grid(row=0, column=4, padx=5)

        wrapper = tk.Frame(f)
        wrapper.pack(expand=True, fill="both", padx=10, pady=5)

        canvas = tk.Canvas(wrapper, bg="white")
        scroll = ttk.Scrollbar(wrapper, orient="vertical", command=canvas.yview)
        self.roster_frame = tk.Frame(canvas, bg="white")
        self.roster_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=self.roster_frame, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", expand=True, fill="both")
        scroll.pack(side="right", fill="y")

        self.roster_rows = []

    def _load_roster(self):
        for w in self.roster_frame.winfo_children():
            w.destroy()
        self.roster_rows = []

        if not self.course_var.get():
            return
        cid = self.course_map[self.course_var.get()]

        tk.Label(self.roster_frame, text="Student", font=("Arial", 10, "bold"),
                 bg="white", width=30, anchor="w").grid(row=0, column=0, padx=5, pady=5)
        tk.Label(self.roster_frame, text="Status", font=("Arial", 10, "bold"),
                 bg="white", width=12).grid(row=0, column=1, padx=5)
        tk.Label(self.roster_frame, text="Reason (optional)",
                 font=("Arial", 10, "bold"), bg="white",
                 width=40, anchor="w").grid(row=0, column=2, padx=5)

        students = self.db.get_course_students(cid)
        if not students:
            tk.Label(self.roster_frame, text="No students enrolled in this module.",
                     bg="white", fg="#6b7280").grid(row=1, column=0, columnspan=3, pady=10)
            return

        for i, (sid, name, username, _email) in enumerate(students, start=1):
            tk.Label(self.roster_frame, text=f"{name} ({username})", bg="white",
                     anchor="w", width=30).grid(row=i, column=0, padx=5, pady=2, sticky="w")
            var = tk.StringVar(value="present")
            ttk.Combobox(self.roster_frame, textvariable=var,
                         values=("present", "absent", "late", "excused"),
                         state="readonly", width=10).grid(row=i, column=1, padx=5)
            e = tk.Entry(self.roster_frame, width=40)
            e.grid(row=i, column=2, padx=5, pady=2)
            self.roster_rows.append((sid, var, e))

    def _save_attendance(self):
        if not self.course_var.get():
            messagebox.showerror("Error", "Select a module.")
            return
        d = self.date_entry.get().strip()
        if not valid_date(d):
            messagebox.showerror("Error", "Date must be YYYY-MM-DD.")
            return
        if not self.roster_rows:
            messagebox.showerror("Error", "No students loaded.")
            return

        cid = self.course_map[self.course_var.get()]
        saved = 0
        for sid, var, reason_e in self.roster_rows:
            self.db.record_absence(sid, cid, d, var.get(),
                                   reason_e.get().strip(), self.user["id"])
            saved += 1
        messagebox.showinfo("Saved", f"Attendance recorded for {saved} students.")

    def _requests_tab(self):
        f = ttk.Frame(self.notebook)
        self.notebook.add(f, text="📬 Absence Requests")

        bar = tk.Frame(f)
        bar.pack(fill="x", padx=10, pady=10)
        tk.Button(bar, text="✅ Approve", bg="#16a34a", fg="white", relief="flat",
                  padx=12, pady=6,
                  command=lambda: self._decide("approved")).pack(side="left", padx=4)
        tk.Button(bar, text="❌ Reject", bg="#dc2626", fg="white", relief="flat",
                  padx=12, pady=6,
                  command=lambda: self._decide("rejected")).pack(side="left", padx=4)
        tk.Button(bar, text="🔄 Refresh", bg="#6b7280", fg="white", relief="flat",
                  padx=12, pady=6,
                  command=self._refresh_req).pack(side="left", padx=4)

        cols = ("ID", "Student", "Code", "Module", "Date", "Reason", "Status", "Submitted")
        self.req_tree = ttk.Treeview(f, columns=cols, show="headings")
        widths = (50, 160, 100, 200, 100, 220, 90, 140)
        for c, w in zip(cols, widths):
            self.req_tree.heading(c, text=c)
            self.req_tree.column(c, width=w)
        self.req_tree.pack(expand=True, fill="both", padx=10, pady=(0, 10))
        self._refresh_req()

    def _refresh_req(self):
        self.clear_tree(self.req_tree)
        for row in self.db.get_requests(staff_id=self.user["id"]):
            self.req_tree.insert("", "end", values=row[:8])

    def _decide(self, decision):
        sel = self.req_tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Pick a request first.")
            return
        vals = self.req_tree.item(sel[0])["values"]
        if vals[6] != "pending":
            messagebox.showinfo("Info", "Request already decided.")
            return

        req_id = vals[0]
        for row in self.db.get_requests(staff_id=self.user["id"]):
            if row[0] == req_id:
                _id, _name, _code, _cname, d, reason, _status, _sub, sid, cid = row
                break
        else:
            return

        self.db.update_request(req_id, decision)
        if decision == "approved":
            self.db.record_absence(sid, cid, d, "excused",
                                   f"[Approved request] {reason}", self.user["id"])
        messagebox.showinfo("Done", f"Request {decision}.")
        self._refresh_req()

    def _view_records_tab(self):
        f = ttk.Frame(self.notebook)
        self.notebook.add(f, text="📋 Records")

        top = tk.Frame(f)
        top.pack(fill="x", padx=10, pady=10)
        tk.Label(top, text="Filter by module:").pack(side="left", padx=5)
        self.view_course_var = tk.StringVar()
        options = ["All my modules"] + [f"{c[1]} - {c[2]}" for c in self.my_courses]
        ttk.Combobox(top, textvariable=self.view_course_var,
                     values=options, state="readonly",
                     width=40).pack(side="left", padx=5)
        self.view_course_var.set("All my modules")
        tk.Button(top, text="Load", bg="#2563eb", fg="white", relief="flat",
                  padx=12, pady=4,
                  command=self._load_records).pack(side="left", padx=5)

        cols = ("ID", "Student", "Code", "Module", "Date", "Status", "Reason")
        self.view_tree = ttk.Treeview(f, columns=cols, show="headings")
        widths = (50, 180, 100, 220, 100, 90, 260)
        for c, w in zip(cols, widths):
            self.view_tree.heading(c, text=c)
            self.view_tree.column(c, width=w)
        self.view_tree.pack(expand=True, fill="both", padx=10, pady=10)
        self._view_rows_cache = []
        try:
            from education_system.university_system.modules.domain.academics.services.attendance.absence_tracking \
                import absence_enhancements as ae
            ae.add_filter_bar(f, self.view_tree,
                              lambda: self._view_rows_cache, list(cols))
            self._view_paginator = ae.Paginator(
                self.view_tree, f, lambda: self._view_rows_cache, page_size=100)
        except Exception:
            logger.exception("pagination wiring (staff records) failed")
        self._load_records()

    def _load_records(self):
        rows: list = []
        if self.view_course_var.get() == "All my modules":
            for c in self.my_courses:
                rows.extend(self.db.get_absences(course_id=c[0]))
        else:
            code = self.view_course_var.get().split(" - ")[0]
            for c in self.my_courses:
                if c[1] == code:
                    rows.extend(self.db.get_absences(course_id=c[0]))
                    break
        self._view_rows_cache = rows
        if hasattr(self, "_view_paginator"):
            self._view_paginator.refresh()
            return
        self.clear_tree(self.view_tree)
        for row in rows:
            self.view_tree.insert("", "end", values=row)


# ---------------------------------------------------------------------------
# Student dashboard
# ---------------------------------------------------------------------------
class StudentDashboard(BaseDashboard):
    def build_tabs(self):
        if not self.user.get("student_id"):
            messagebox.showerror(
                "Missing student_id",
                "Your user account is not linked to a student record. "
                "Contact an administrator.",
            )
        self._my_courses_tab()
        self._my_absences_tab()
        self._submit_request_tab()
        self._my_requests_tab()
        self._stats_tab()
        try:
            from education_system.university_system.modules.domain.academics.services.attendance.absence_tracking \
                import student_features as sf
            ctx = sf.StudentContext(db=self.db, parent=self.root, user=self.user)
            sf.build_student_tab(self.notebook, ctx)
        except Exception:
            logger.exception("failed to build student tools tab")
            messagebox.showwarning(
                "Student Tools",
                "The Student Tools tab failed to load (see log).",
                parent=self.root,
            )
        try:
            from education_system.university_system.modules.domain.academics.services.attendance.absence_tracking \
                import absence_enhancements as ae
            ae.bootstrap(self, "student")
        except Exception:
            logger.exception("failed to bootstrap enhancements (student)")

    def _my_courses_tab(self):
        f = ttk.Frame(self.notebook)
        self.notebook.add(f, text="📚 My Modules")
        cols = ("Code", "Name", "Instructor")
        tree = ttk.Treeview(f, columns=cols, show="headings")
        for c, w in zip(cols, (120, 340, 220)):
            tree.heading(c, text=c)
            tree.column(c, width=w)
        tree.pack(expand=True, fill="both", padx=10, pady=10)
        for row in self.db.get_courses(student_id=self.user.get("student_id")):
            tree.insert("", "end", values=(row[1], row[2], row[3]))

    def _my_absences_tab(self):
        f = ttk.Frame(self.notebook)
        self.notebook.add(f, text="📋 My Absences")

        tk.Button(f, text="🔄 Refresh", bg="#6b7280", fg="white", relief="flat",
                  padx=12, pady=6,
                  command=self._refresh_abs).pack(pady=10)

        cols = ("ID", "Student", "Code", "Module", "Date", "Status", "Reason")
        self.abs_tree = ttk.Treeview(f, columns=cols, show="headings")
        widths = (50, 160, 100, 220, 100, 90, 260)
        for c, w in zip(cols, widths):
            self.abs_tree.heading(c, text=c)
            self.abs_tree.column(c, width=w)
        self.abs_tree.pack(expand=True, fill="both", padx=10, pady=10)
        self._refresh_abs()

    def _refresh_abs(self):
        self.clear_tree(self.abs_tree)
        sid = self.user.get("student_id")
        if not sid:
            return
        for row in self.db.get_absences(student_id=sid):
            self.abs_tree.insert("", "end", values=row)

    def _submit_request_tab(self):
        f = ttk.Frame(self.notebook)
        self.notebook.add(f, text="📤 Submit Request")

        form = tk.Frame(f, bg="white", padx=20, pady=20)
        form.pack(expand=True, fill="both", padx=40, pady=20)

        tk.Label(form, text="Submit Absence Request",
                 font=("Arial", 14, "bold"), bg="white",
                 fg="#1e3a5f").pack(pady=(0, 15))

        tk.Label(form, text="Module:", bg="white",
                 anchor="w").pack(fill="x", pady=(5, 0))
        my_courses = self.db.get_courses(student_id=self.user.get("student_id"))
        self.rq_map = {f"{c[1]} - {c[2]}": c[0] for c in my_courses}
        self.rq_var = tk.StringVar()
        ttk.Combobox(form, textvariable=self.rq_var,
                     values=list(self.rq_map.keys()),
                     state="readonly").pack(fill="x", ipady=3)

        tk.Label(form, text="Date of Absence (YYYY-MM-DD):",
                 bg="white", anchor="w").pack(fill="x", pady=(10, 0))
        self.rq_date = tk.Entry(form)
        self.rq_date.insert(0, date.today().isoformat())
        self.rq_date.pack(fill="x", ipady=3)

        tk.Label(form, text="Reason:", bg="white",
                 anchor="w").pack(fill="x", pady=(10, 0))
        self.rq_reason = tk.Text(form, height=6)
        self.rq_reason.pack(fill="x")

        tk.Button(form, text="Submit Request", bg="#2563eb", fg="white",
                  relief="flat", padx=20, pady=8,
                  command=self._submit).pack(pady=15)

    def _submit(self):
        if not self.user.get("student_id"):
            messagebox.showerror("Error", "Your account isn't linked to a student record.")
            return
        if not self.rq_var.get():
            messagebox.showerror("Error", "Select a module.")
            return
        d = self.rq_date.get().strip()
        if not valid_date(d):
            messagebox.showerror("Error", "Date must be YYYY-MM-DD.")
            return
        reason = self.rq_reason.get("1.0", "end").strip()
        if not reason:
            messagebox.showerror("Error", "Please provide a reason.")
            return
        self.db.submit_request(self.user["student_id"],
                               self.rq_map[self.rq_var.get()], d, reason)
        messagebox.showinfo("Submitted", "Your request has been submitted.")
        self.rq_reason.delete("1.0", "end")

    def _my_requests_tab(self):
        f = ttk.Frame(self.notebook)
        self.notebook.add(f, text="📨 My Requests")

        tk.Button(f, text="🔄 Refresh", bg="#6b7280", fg="white", relief="flat",
                  padx=12, pady=6,
                  command=self._refresh_req).pack(pady=10)

        cols = ("ID", "Student", "Code", "Module", "Date", "Reason", "Status", "Submitted")
        self.req_tree = ttk.Treeview(f, columns=cols, show="headings")
        widths = (50, 140, 100, 200, 100, 220, 90, 140)
        for c, w in zip(cols, widths):
            self.req_tree.heading(c, text=c)
            self.req_tree.column(c, width=w)
        self.req_tree.pack(expand=True, fill="both", padx=10, pady=10)
        self._refresh_req()

    def _refresh_req(self):
        self.clear_tree(self.req_tree)
        sid = self.user.get("student_id")
        if not sid:
            return
        for row in self.db.get_requests(student_id=sid):
            self.req_tree.insert("", "end", values=row[:8])

    def _stats_tab(self):
        f = ttk.Frame(self.notebook)
        self.notebook.add(f, text="📊 My Stats")

        tk.Label(f, text=f"Attendance Summary for {self.user['name']}",
                 font=("Arial", 13, "bold"), fg="#1e3a5f").pack(pady=15)

        cols = ("Module Code", "Module", "Absent", "Late", "Excused", "Present")
        tree = ttk.Treeview(f, columns=cols, show="headings")
        for c, w in zip(cols, (120, 280, 80, 80, 80, 80)):
            tree.heading(c, text=c)
            tree.column(c, width=w, anchor="center")
        tree.pack(expand=True, fill="both", padx=20, pady=10)

        total_absent = total_late = 0
        sid = self.user.get("student_id")
        if sid:
            for code, name, a, l, e, p in self.db.get_student_stats(sid):
                a, l, e, p = a or 0, l or 0, e or 0, p or 0
                total_absent += a
                total_late += l
                tree.insert("", "end", values=(code, name, a, l, e, p))

        tk.Label(f,
                 text=f"Total Absences: {total_absent}   |   Total Lates: {total_late}",
                 font=("Arial", 12, "bold"), fg="#dc2626").pack(pady=15)


# ---------------------------------------------------------------------------
# Entry point — no login; user context comes from the calling harness
# ---------------------------------------------------------------------------
def _parse_args(argv):
    p = argparse.ArgumentParser(description="University Absence Tracker")
    p.add_argument("--username", help="Username of the already-authenticated user")
    p.add_argument("--user-id", type=int, help="users.id of the authenticated user")
    p.add_argument("--role", help="Role override (admin/staff/instructor/student)")
    return p.parse_args(argv)


def _resolve_user(db, args):
    """Resolve caller identity from the main users table. No password prompt."""
    if args.username:
        user = db.lookup_user_by_username(args.username)
        if user:
            if args.role:
                user["role"] = args.role
            return user
    if args.user_id is not None:
        db.cur.execute(
            """SELECT id, username, role, first_name, last_name, email, student_id
               FROM users WHERE id = ?""",
            (args.user_id,),
        )
        row = db.cur.fetchone()
        if row:
            uid, uname, role, first, last, email, sid = row
            return {
                "id": uid, "username": uname,
                "role": args.role or role,
                "name": (f"{first or ''} {last or ''}").strip() or uname,
                "email": email, "student_id": sid,
            }
    return None


def launch_dashboard(root, db, user):
    role = (user.get("role") or "").lower()
    if role == "admin":
        AdminDashboard(root, db, user)
    elif role in ("staff", "instructor", "teacher"):
        StaffDashboard(root, db, user)
    elif role == "student":
        StudentDashboard(root, db, user)
    else:
        AdminDashboard(root, db, user)


def main(argv=None):
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    db = Database()
    user = _resolve_user(db, args)

    root = tk.Tk()
    if not user:
        root.withdraw()
        messagebox.showerror(
            "Absence Tracker",
            "No authenticated user was provided.\n"
            "Launch this tool from the main Education System GUI.",
        )
        root.destroy()
        db.close()
        return 1

    launch_dashboard(root, db, user)
    root.mainloop()
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
