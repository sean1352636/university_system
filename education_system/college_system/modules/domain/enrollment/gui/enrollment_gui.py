"""Enrollment management GUI for the College Management System."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.enrollment.services.enrollment_service import EnrollmentService
from education_system.college_system.modules.domain.students.services.student_service import StudentService
from education_system.college_system.modules.domain.courses.services.course_service import CourseService
from education_system.college_system.core.exceptions import EnrollmentError


class EnrollmentFrame(tk.Frame):
    """Enrollment management screen.

    Provides enroll / drop actions, a Treeview of current enrollments and a
    secondary panel showing waitlist information for a selected course.
    """

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._enrollment_svc = EnrollmentService(db_path)
        self._student_svc = StudentService(db_path)
        self._course_svc = CourseService(db_path)

        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        # Header
        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Enrollment Management",
                 font=("Helvetica", 15, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=20, pady=10)

        # --- Enroll / Drop form ---
        form_frame = tk.LabelFrame(self, text="Enroll / Drop", padx=12, pady=8,
                                   bg="#ecf0f1", font=("Helvetica", 10, "bold"))
        form_frame.pack(fill="x", padx=15, pady=(10, 5))

        tk.Label(form_frame, text="Student ID:", bg="#ecf0f1").grid(
            row=0, column=0, sticky="w", padx=5, pady=4)
        self._student_id_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self._student_id_var,
                  width=16).grid(row=0, column=1, padx=5, pady=4)

        tk.Label(form_frame, text="Course Code:", bg="#ecf0f1").grid(
            row=0, column=2, sticky="w", padx=5, pady=4)
        self._course_code_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self._course_code_var,
                  width=16).grid(row=0, column=3, padx=5, pady=4)

        ttk.Button(form_frame, text="Enroll",
                   command=self._on_enroll).grid(row=0, column=4, padx=8, pady=4)
        ttk.Button(form_frame, text="Drop",
                   command=self._on_drop).grid(row=0, column=5, padx=4, pady=4)

        # --- Main content: enrollments tree + waitlist panel side-by-side ---
        content = tk.Frame(self, bg="#ecf0f1")
        content.pack(fill="both", expand=True, padx=15, pady=5)
        content.columnconfigure(0, weight=3)
        content.columnconfigure(1, weight=1)
        content.rowconfigure(0, weight=1)

        # Enrollments Treeview
        enroll_lf = tk.LabelFrame(content, text="Enrollments", bg="#ecf0f1",
                                  font=("Helvetica", 10, "bold"))
        enroll_lf.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        tree_frame = tk.Frame(enroll_lf)
        tree_frame.pack(fill="both", expand=True, padx=4, pady=4)

        columns = ("sid", "student_name", "course_code", "course_title",
                   "status", "enrolled_at")
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                                  selectmode="browse")

        headings = {
            "sid":          ("Student ID",  90),
            "student_name": ("Name",       140),
            "course_code":  ("Course",      80),
            "course_title": ("Title",      160),
            "status":       ("Status",      80),
            "enrolled_at":  ("Date",       130),
        }
        for col, (heading, width) in headings.items():
            self._tree.heading(col, text=heading)
            self._tree.column(col, width=width, anchor="center")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Filter bar below tree
        filter_bar = tk.Frame(enroll_lf, bg="#ecf0f1")
        filter_bar.pack(fill="x", padx=4, pady=(0, 4))
        ttk.Button(filter_bar, text="Show All", command=self._load_enrollments).pack(
            side="left", padx=4)
        ttk.Button(filter_bar, text="Active Only",
                   command=lambda: self._load_enrollments(status="enrolled")).pack(
            side="left", padx=4)

        # Waitlist panel
        wl_lf = tk.LabelFrame(content, text="Waitlist", bg="#ecf0f1",
                               font=("Helvetica", 10, "bold"))
        wl_lf.grid(row=0, column=1, sticky="nsew")

        wl_inner = tk.Frame(wl_lf, bg="#ecf0f1")
        wl_inner.pack(fill="both", expand=True, padx=4, pady=4)

        tk.Label(wl_inner, text="Course Code:", bg="#ecf0f1").pack(anchor="w")
        self._wl_course_var = tk.StringVar()
        ttk.Entry(wl_inner, textvariable=self._wl_course_var, width=16).pack(
            anchor="w", pady=(0, 4))
        ttk.Button(wl_inner, text="View Waitlist",
                   command=self._on_view_waitlist).pack(anchor="w", pady=(0, 8))

        wl_cols = ("position", "sid", "name")
        self._wl_tree = ttk.Treeview(wl_inner, columns=wl_cols,
                                     show="headings", height=8)
        for col, heading, w in [("position", "#", 40),
                                ("sid", "Student ID", 90),
                                ("name", "Name", 130)]:
            self._wl_tree.heading(col, text=heading)
            self._wl_tree.column(col, width=w, anchor="center")
        self._wl_tree.pack(fill="both", expand=True)

        # Status bar
        self._status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_var, bg="#ecf0f1",
                 anchor="w", font=("Helvetica", 9), fg="#7f8c8d").pack(
            fill="x", padx=15, pady=(0, 8))

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def refresh(self):
        self._load_enrollments()

    def _load_enrollments(self, status: str | None = None):
        self._tree.delete(*self._tree.get_children())
        try:
            enrollments = self._enrollment_svc.list_enrollments(status=status)
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to load enrollments:\n{exc}")
            return

        for e in enrollments:
            name = f"{e.get('first_name', '')} {e.get('last_name', '')}"
            self._tree.insert("", "end", values=(
                e.get("sid", ""),
                name.strip(),
                e.get("course_code", ""),
                e.get("title", ""),
                e.get("status", ""),
                e.get("enrolled_at", ""),
            ))

        self._status_var.set(f"{len(enrollments)} enrollment(s) loaded")

    # ------------------------------------------------------------------
    # Resolve helpers
    # ------------------------------------------------------------------

    def _resolve_ids(self):
        """Resolve student ID string and course code to their PKs.

        Returns (student_pk, course_pk) or raises EnrollmentError.
        """
        sid_str = self._student_id_var.get().strip()
        code_str = self._course_code_var.get().strip().upper()

        if not sid_str or not code_str:
            raise EnrollmentError("Both student ID and course code are required.")

        student = self._student_svc.get_student_by_student_id(sid_str)
        if not student:
            raise EnrollmentError(f"Student '{sid_str}' not found.")

        course = self._course_svc.get_course_by_code(code_str)
        if not course:
            raise EnrollmentError(f"Course '{code_str}' not found.")

        return student["id"], course["id"]

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _on_enroll(self):
        try:
            student_pk, course_pk = self._resolve_ids()
            result = self._enrollment_svc.enroll_student(student_pk, course_pk)
        except EnrollmentError as exc:
            messagebox.showerror("Enrollment Error", str(exc))
            return
        except Exception as exc:
            messagebox.showerror("Error", f"Unexpected error:\n{exc}")
            return

        status = result.get("status", "unknown")
        if status == "waitlisted":
            messagebox.showinfo(
                "Waitlisted",
                f"Course is full. Student added to waitlist at position "
                f"{result.get('position', '?')}.",
            )
        else:
            messagebox.showinfo("Enrolled",
                                "Student enrolled successfully.")

        self._load_enrollments()

    def _on_drop(self):
        try:
            student_pk, course_pk = self._resolve_ids()
        except EnrollmentError as exc:
            messagebox.showerror("Error", str(exc))
            return

        if not messagebox.askyesno("Confirm Drop",
                                   "Drop this student from the course?"):
            return

        try:
            result = self._enrollment_svc.drop_student(student_pk, course_pk)
        except EnrollmentError as exc:
            messagebox.showerror("Drop Error", str(exc))
            return

        msg = "Student dropped successfully."
        if result.get("promoted_student_pk"):
            msg += "\nA waitlisted student has been auto-promoted."
        messagebox.showinfo("Dropped", msg)
        self._load_enrollments()

    def _on_view_waitlist(self):
        code = self._wl_course_var.get().strip().upper()
        if not code:
            messagebox.showwarning("Input", "Enter a course code.")
            return

        course = self._course_svc.get_course_by_code(code)
        if not course:
            messagebox.showerror("Error", f"Course '{code}' not found.")
            return

        self._wl_tree.delete(*self._wl_tree.get_children())
        try:
            waitlist = self._enrollment_svc.get_waitlist(course["id"])
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to load waitlist:\n{exc}")
            return

        for w in waitlist:
            name = f"{w.get('first_name', '')} {w.get('last_name', '')}"
            self._wl_tree.insert("", "end", values=(
                w.get("position", ""),
                w.get("sid", ""),
                name.strip(),
            ))

        if not waitlist:
            self._status_var.set(f"No students on waitlist for {code}")
        else:
            self._status_var.set(f"{len(waitlist)} student(s) on waitlist for {code}")
