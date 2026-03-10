"""Grade management GUI for the Sixth Form College Management System."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.grades.services.grade_service import GradeService
from education_system.college_system.modules.domain.students.services.student_service import StudentService
from education_system.college_system.modules.domain.courses.services.course_service import CourseService
from education_system.college_system.core.exceptions import GradeError


class GradeFrame(tk.Frame):
    """Grade management screen.

    Features:
    * Record grade form (student ID, course code, numeric score).
    * Treeview showing all grades.
    * UCAS points display for a selected student.
    * Transcript viewer dialog.
    """

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._grade_svc = GradeService(db_path)
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
        tk.Label(header, text="Grade Management",
                 font=("Helvetica", 15, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=20, pady=10)

        # --- Record grade form ---
        form_frame = tk.LabelFrame(self, text="Record / Update Grade",
                                   padx=12, pady=8, bg="#ecf0f1",
                                   font=("Helvetica", 10, "bold"))
        form_frame.pack(fill="x", padx=15, pady=(10, 5))

        tk.Label(form_frame, text="Student ID:", bg="#ecf0f1").grid(
            row=0, column=0, sticky="w", padx=5, pady=4)
        self._stu_id_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self._stu_id_var, width=14).grid(
            row=0, column=1, padx=5, pady=4)

        tk.Label(form_frame, text="Course Code:", bg="#ecf0f1").grid(
            row=0, column=2, sticky="w", padx=5, pady=4)
        self._crs_code_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self._crs_code_var, width=14).grid(
            row=0, column=3, padx=5, pady=4)

        tk.Label(form_frame, text="Score (0-100):", bg="#ecf0f1").grid(
            row=0, column=4, sticky="w", padx=5, pady=4)
        self._score_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self._score_var, width=8).grid(
            row=0, column=5, padx=5, pady=4)

        ttk.Button(form_frame, text="Submit Grade",
                   command=self._on_submit_grade).grid(
            row=0, column=6, padx=10, pady=4)

        # --- UCAS Points / Transcript lookup ---
        lookup_frame = tk.LabelFrame(self, text="Student Lookup", padx=12,
                                     pady=8, bg="#ecf0f1",
                                     font=("Helvetica", 10, "bold"))
        lookup_frame.pack(fill="x", padx=15, pady=5)

        tk.Label(lookup_frame, text="Student ID:", bg="#ecf0f1").grid(
            row=0, column=0, sticky="w", padx=5, pady=4)
        self._lookup_var = tk.StringVar()
        ttk.Entry(lookup_frame, textvariable=self._lookup_var, width=14).grid(
            row=0, column=1, padx=5, pady=4)

        ttk.Button(lookup_frame, text="Show UCAS Points",
                   command=self._on_show_ucas_points).grid(row=0, column=2, padx=5, pady=4)
        ttk.Button(lookup_frame, text="View Transcript",
                   command=self._on_view_transcript).grid(
            row=0, column=3, padx=5, pady=4)
        ttk.Button(lookup_frame, text="Load Grades",
                   command=self._on_load_student_grades).grid(
            row=0, column=4, padx=5, pady=4)

        self._ucas_var = tk.StringVar(value="UCAS Points: --")
        tk.Label(lookup_frame, textvariable=self._ucas_var, bg="#ecf0f1",
                 font=("Helvetica", 11, "bold"), fg="#2980b9").grid(
            row=0, column=5, padx=(20, 5), pady=4)

        # --- Grades Treeview ---
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=(5, 15))

        columns = ("sid", "student_name", "course_code", "course_title",
                   "score", "letter", "term")
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                                  selectmode="browse")

        headings = {
            "sid":          ("Student ID",  90),
            "student_name": ("Name",       140),
            "course_code":  ("Course",      80),
            "course_title": ("Title",      150),
            "score":        ("Score",       70),
            "letter":       ("Grade",       60),
            "term":         ("Term",       100),
        }
        for col, (heading, width) in headings.items():
            self._tree.heading(col, text=heading)
            self._tree.column(col, width=width, anchor="center")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical",
                            command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Status bar
        self._status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_var, bg="#ecf0f1", anchor="w",
                 font=("Helvetica", 9), fg="#7f8c8d").pack(
            fill="x", padx=15, pady=(0, 8))

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def refresh(self):
        """Called when frame is shown. Reload all grades."""
        self._load_all_grades()

    def _load_all_grades(self):
        """Load grades for ALL students (used as default view)."""
        self._tree.delete(*self._tree.get_children())
        try:
            students = self._student_svc.list_students(limit=500)
        except Exception:
            students = []

        count = 0
        for s in students:
            try:
                grades = self._grade_svc.get_student_grades(s["id"])
            except Exception:
                continue
            for g in grades:
                name = f"{s.get('first_name', '')} {s.get('last_name', '')}"
                self._tree.insert("", "end", values=(
                    s.get("student_id", ""),
                    name.strip(),
                    g.get("course_code", ""),
                    g.get("title", ""),
                    g.get("score", ""),
                    g.get("letter_grade", ""),
                    g.get("term", "") or "",
                ))
                count += 1

        self._status_var.set(f"{count} grade record(s) loaded")

    def _load_student_grades(self, student_pk: int, student_id_str: str):
        """Load grades for a single student into the treeview."""
        self._tree.delete(*self._tree.get_children())
        try:
            grades = self._grade_svc.get_student_grades(student_pk)
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to load grades:\n{exc}")
            return

        student = self._student_svc.get_student(student_pk)
        name = ""
        if student:
            name = f"{student.get('first_name', '')} {student.get('last_name', '')}"

        for g in grades:
            self._tree.insert("", "end", values=(
                student_id_str,
                name.strip(),
                g.get("course_code", ""),
                g.get("title", ""),
                g.get("score", ""),
                g.get("letter_grade", ""),
                g.get("term", "") or "",
            ))

        self._status_var.set(
            f"{len(grades)} grade(s) for {student_id_str}")

    # ------------------------------------------------------------------
    # Resolve helper
    # ------------------------------------------------------------------

    def _resolve_student(self, sid_str: str):
        """Return (pk, student_id_str) or raise GradeError."""
        sid_str = sid_str.strip()
        if not sid_str:
            raise GradeError("Student ID is required.")
        student = self._student_svc.get_student_by_student_id(sid_str)
        if not student:
            raise GradeError(f"Student '{sid_str}' not found.")
        return student["id"], student["student_id"]

    def _resolve_course(self, code_str: str):
        code_str = code_str.strip().upper()
        if not code_str:
            raise GradeError("Course code is required.")
        course = self._course_svc.get_course_by_code(code_str)
        if not course:
            raise GradeError(f"Course '{code_str}' not found.")
        return course["id"]

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _on_submit_grade(self):
        try:
            student_pk, _ = self._resolve_student(self._stu_id_var.get())
            course_pk = self._resolve_course(self._crs_code_var.get())
        except GradeError as exc:
            messagebox.showerror("Error", str(exc))
            return

        try:
            score = float(self._score_var.get().strip())
        except ValueError:
            messagebox.showwarning("Validation", "Score must be a number (0-100).")
            return

        try:
            self._grade_svc.record_grade(student_pk, course_pk, score)
            messagebox.showinfo("Success", "Grade recorded successfully.")
            self._score_var.set("")
            self._load_all_grades()
        except GradeError as exc:
            messagebox.showerror("Grade Error", str(exc))

    def _on_show_ucas_points(self):
        try:
            student_pk, sid_str = self._resolve_student(self._lookup_var.get())
        except GradeError as exc:
            messagebox.showerror("Error", str(exc))
            return

        try:
            ucas_points = self._grade_svc.calculate_ucas_points(student_pk)
            self._ucas_var.set(f"UCAS Points: {ucas_points}")
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to calculate UCAS points:\n{exc}")

    def _on_load_student_grades(self):
        try:
            student_pk, sid_str = self._resolve_student(self._lookup_var.get())
        except GradeError as exc:
            messagebox.showerror("Error", str(exc))
            return
        self._load_student_grades(student_pk, sid_str)

    def _on_view_transcript(self):
        try:
            student_pk, sid_str = self._resolve_student(self._lookup_var.get())
        except GradeError as exc:
            messagebox.showerror("Error", str(exc))
            return

        try:
            transcript = self._grade_svc.get_transcript(student_pk)
        except GradeError as exc:
            messagebox.showerror("Error", str(exc))
            return

        _TranscriptDialog(self, transcript)


class _TranscriptDialog(tk.Toplevel):
    """Read-only dialog displaying a student's transcript."""

    def __init__(self, parent, transcript: dict):
        super().__init__(parent)
        self.title("Student Transcript")
        self.geometry("620x480")
        self.resizable(True, True)
        self.grab_set()

        self._build(transcript)
        self._center_on_parent(parent)

    def _center_on_parent(self, parent):
        self.update_idletasks()
        pw = parent.winfo_rootx() + parent.winfo_width() // 2
        ph = parent.winfo_rooty() + parent.winfo_height() // 2
        w = self.winfo_width()
        h = self.winfo_height()
        self.geometry(f"+{pw - w // 2}+{ph - h // 2}")

    def _build(self, transcript: dict):
        student = transcript.get("student", {})
        grades = transcript.get("grades", [])
        ucas_points = transcript.get("ucas_points", 0)
        total_subjects = transcript.get("total_subjects", 0)
        total_courses = transcript.get("total_courses", 0)

        # Student info header
        info_frame = tk.Frame(self, bg="#2c3e50", padx=15, pady=10)
        info_frame.pack(fill="x")

        name = f"{student.get('first_name', '')} {student.get('last_name', '')}"
        tk.Label(info_frame, text=name.strip(),
                 font=("Helvetica", 14, "bold"), bg="#2c3e50", fg="white"
                 ).pack(anchor="w")
        tk.Label(info_frame,
                 text=f"ID: {student.get('student_id', 'N/A')}  |  "
                      f"Year Group: {student.get('year_group', 'N/A')}  |  "
                      f"Status: {student.get('status', 'N/A')}",
                 font=("Helvetica", 10), bg="#2c3e50", fg="#bdc3c7"
                 ).pack(anchor="w")

        # Summary bar
        summary = tk.Frame(self, bg="#ecf0f1", padx=15, pady=8)
        summary.pack(fill="x")
        tk.Label(summary,
                 text=f"UCAS Tariff Points: {ucas_points}    |    "
                      f"Total Subjects: {total_subjects}    "
                      f"|    Total Courses: {total_courses}",
                 font=("Helvetica", 11, "bold"), bg="#ecf0f1", fg="#2980b9"
                 ).pack(anchor="w")

        # Grades table
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=10)

        columns = ("course_code", "title", "qualification_type", "score", "letter", "term")
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=12)

        for col, heading, w in [
            ("course_code", "Code", 80), ("title", "Title", 180),
            ("qualification_type", "Qual", 60), ("score", "Score", 60),
            ("letter", "Grade", 50), ("term", "Term", 100),
        ]:
            tree.heading(col, text=heading)
            tree.column(col, width=w, anchor="center")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        for g in grades:
            tree.insert("", "end", values=(
                g.get("course_code", ""),
                g.get("title", ""),
                g.get("qualification_type", "") or "",
                g.get("score", ""),
                g.get("letter_grade", ""),
                g.get("term", "") or "",
            ))

        # Close button
        ttk.Button(self, text="Close", command=self.destroy).pack(pady=(0, 10))
