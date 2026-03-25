"""Grade management GUI for the Sixth Form College Management System."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.grades.services.grade_service import GradeService
from education_system.college_system.modules.domain.students.services.student_service import StudentService
from education_system.college_system.modules.domain.courses.services.course_service import CourseService
from education_system.college_system.core.exceptions import GradeError
from education_system.college_system.core.i18n import t


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

        # Pagination state (paginates students in the all-grades view)
        self._page = 0
        self._page_size = 50
        self._total_count = 0

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
        tk.Label(header, text=t("grade.management"),
                 font=("Helvetica", 15, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=20, pady=10)

        # --- Record grade form ---
        form_frame = tk.LabelFrame(self, text=t("grade.record_update"),
                                   padx=12, pady=8, bg="#ecf0f1",
                                   font=("Helvetica", 10, "bold"))
        form_frame.pack(fill="x", padx=15, pady=(10, 5))

        tk.Label(form_frame, text=t("grade.student_id_colon"), bg="#ecf0f1").grid(
            row=0, column=0, sticky="w", padx=5, pady=4)
        self._stu_id_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self._stu_id_var, width=14).grid(
            row=0, column=1, padx=5, pady=4)

        tk.Label(form_frame, text=t("grade.course_code_colon"), bg="#ecf0f1").grid(
            row=0, column=2, sticky="w", padx=5, pady=4)
        self._crs_code_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self._crs_code_var, width=14).grid(
            row=0, column=3, padx=5, pady=4)

        tk.Label(form_frame, text=t("grade.score_label"), bg="#ecf0f1").grid(
            row=0, column=4, sticky="w", padx=5, pady=4)
        self._score_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self._score_var, width=8).grid(
            row=0, column=5, padx=5, pady=4)

        ttk.Button(form_frame, text=t("grade.submit_grade"),
                   command=self._on_submit_grade).grid(
            row=0, column=6, padx=10, pady=4)

        # --- UCAS Points / Transcript lookup ---
        lookup_frame = tk.LabelFrame(self, text=t("grade.student_lookup"), padx=12,
                                     pady=8, bg="#ecf0f1",
                                     font=("Helvetica", 10, "bold"))
        lookup_frame.pack(fill="x", padx=15, pady=5)

        tk.Label(lookup_frame, text=t("grade.student_id_colon"), bg="#ecf0f1").grid(
            row=0, column=0, sticky="w", padx=5, pady=4)
        self._lookup_var = tk.StringVar()
        ttk.Entry(lookup_frame, textvariable=self._lookup_var, width=14).grid(
            row=0, column=1, padx=5, pady=4)

        ttk.Button(lookup_frame, text=t("grade.show_ucas_points"),
                   command=self._on_show_ucas_points).grid(row=0, column=2, padx=5, pady=4)
        ttk.Button(lookup_frame, text=t("grade.view_transcript"),
                   command=self._on_view_transcript).grid(
            row=0, column=3, padx=5, pady=4)
        ttk.Button(lookup_frame, text=t("grade.load_grades"),
                   command=self._on_load_student_grades).grid(
            row=0, column=4, padx=5, pady=4)

        ttk.Button(lookup_frame, text="Export CSV",
                   command=self._export_csv).grid(
            row=0, column=6, padx=5, pady=4)

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
            "sid":          (t("grade.col_student_id"),  90),
            "student_name": (t("grade.col_name"),       140),
            "course_code":  (t("grade.col_course"),      80),
            "course_title": (t("grade.col_title"),      150),
            "score":        (t("grade.col_score"),       70),
            "letter":       (t("grade.col_grade"),       60),
            "term":         (t("grade.col_term"),       100),
        }
        for col, (heading, width) in headings.items():
            self._tree.heading(col, text=heading)
            self._tree.column(col, width=width, anchor="center")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical",
                            command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Pagination bar
        self._pag_frame = tk.Frame(self, bg="#ecf0f1")
        self._pag_frame.pack(fill="x", padx=15, pady=(0, 4))

        self._prev_btn = ttk.Button(self._pag_frame, text="Previous",
                                     command=self._prev_page, state="disabled")
        self._prev_btn.pack(side="left", padx=4)

        self._page_label_var = tk.StringVar(value="Page 1 of 1")
        tk.Label(self._pag_frame, textvariable=self._page_label_var,
                 bg="#ecf0f1", font=("Helvetica", 9)).pack(side="left", padx=8)

        self._next_btn = ttk.Button(self._pag_frame, text="Next",
                                     command=self._next_page, state="disabled")
        self._next_btn.pack(side="left", padx=4)

        self._record_count_var = tk.StringVar(value="")
        tk.Label(self._pag_frame, textvariable=self._record_count_var,
                 bg="#ecf0f1", font=("Helvetica", 9), fg="#7f8c8d").pack(
            side="right", padx=8)

        # Status bar
        self._status_var = tk.StringVar(value=t("common.ready"))
        tk.Label(self, textvariable=self._status_var, bg="#ecf0f1", anchor="w",
                 font=("Helvetica", 9), fg="#7f8c8d").pack(
            fill="x", padx=15, pady=(0, 8))

        # --- Keyboard shortcuts for accessibility ---
        self._tree.bind("<Return>", lambda e: self._on_view_selected_grade())

    def _on_view_selected_grade(self):
        """Handle Return key on grades treeview -- show details of selected grade."""
        sel = self._tree.selection()
        if not sel:
            return
        values = self._tree.item(sel[0], "values")
        if values:
            detail = (
                f"Student ID: {values[0]}\n"
                f"Name: {values[1]}\n"
                f"Course: {values[2]} - {values[3]}\n"
                f"Score: {values[4]}\n"
                f"Grade: {values[5]}\n"
                f"Term: {values[6]}"
            )
            messagebox.showinfo("Grade Details", detail)

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def refresh(self):
        """Called when frame is shown. Reload all grades."""
        self._load_all_grades()

    def _load_all_grades(self):
        """Load grades for students on the current page."""
        self._tree.delete(*self._tree.get_children())
        try:
            self._total_count = self._student_svc.count_students()
            students = self._student_svc.list_students(
                limit=self._page_size,
                offset=self._page * self._page_size,
            )
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

        self._update_pagination()
        self._status_var.set(t("grade.count_loaded", count=count))

    def _load_student_grades(self, student_pk: int, student_id_str: str):
        """Load grades for a single student into the treeview."""
        self._tree.delete(*self._tree.get_children())
        try:
            grades = self._grade_svc.get_student_grades(student_pk)
        except Exception as exc:
            messagebox.showerror(t("common.error"), f"Failed to load grades:\n{exc}")
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
    # Pagination
    # ------------------------------------------------------------------

    def _update_pagination(self):
        """Update pagination controls based on current state."""
        total_pages = max(1, (self._total_count + self._page_size - 1) // self._page_size)
        current = self._page + 1
        self._page_label_var.set(f"Page {current} of {total_pages}")

        start = self._page * self._page_size + 1
        end = min((self._page + 1) * self._page_size, self._total_count)
        if self._total_count == 0:
            self._record_count_var.set("No records")
        else:
            self._record_count_var.set(
                f"Showing students {start}-{end} of {self._total_count}")

        self._prev_btn.configure(
            state="normal" if self._page > 0 else "disabled")
        self._next_btn.configure(
            state="normal" if current < total_pages else "disabled")

    def _next_page(self):
        self._page += 1
        self._load_all_grades()

    def _prev_page(self):
        if self._page > 0:
            self._page -= 1
        self._load_all_grades()

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
            messagebox.showerror(t("common.error"), str(exc))
            return

        try:
            score = float(self._score_var.get().strip())
        except ValueError:
            messagebox.showwarning(t("common.validation"), t("grade.score_must_be_number"))
            return

        try:
            self._grade_svc.record_grade(student_pk, course_pk, score)
            messagebox.showinfo(t("common.success"), t("grade.recorded"))
            self._score_var.set("")
            self._load_all_grades()
        except GradeError as exc:
            messagebox.showerror(t("grade.error"), str(exc))

    def _on_show_ucas_points(self):
        try:
            student_pk, sid_str = self._resolve_student(self._lookup_var.get())
        except GradeError as exc:
            messagebox.showerror(t("common.error"), str(exc))
            return

        try:
            ucas_points = self._grade_svc.calculate_ucas_points(student_pk)
            self._ucas_var.set(t("grade.ucas_points_display", points=ucas_points))
        except Exception as exc:
            messagebox.showerror(t("common.error"), f"Failed to calculate UCAS points:\n{exc}")

    def _on_load_student_grades(self):
        try:
            student_pk, sid_str = self._resolve_student(self._lookup_var.get())
        except GradeError as exc:
            messagebox.showerror(t("common.error"), str(exc))
            return
        self._load_student_grades(student_pk, sid_str)

    def _export_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._tree, default_filename="grades.csv")

    def _on_view_transcript(self):
        try:
            student_pk, sid_str = self._resolve_student(self._lookup_var.get())
        except GradeError as exc:
            messagebox.showerror(t("common.error"), str(exc))
            return

        try:
            transcript = self._grade_svc.get_transcript(student_pk)
        except GradeError as exc:
            messagebox.showerror(t("common.error"), str(exc))
            return

        _TranscriptDialog(self, transcript)


class _TranscriptDialog(tk.Toplevel):
    """Read-only dialog displaying a student's transcript."""

    def __init__(self, parent, transcript: dict):
        super().__init__(parent)
        self.title(t("grade.transcript_title"))
        self.geometry("620x480")
        self.resizable(True, True)
        self.grab_set()

        self._build(transcript)
        self._center_on_parent(parent)
        self.bind("<Escape>", lambda e: self.destroy())

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
            ("course_code", t("grade.col_course"), 80), ("title", t("grade.col_title"), 180),
            ("qualification_type", t("grade.col_qual"), 60), ("score", t("grade.col_score"), 60),
            ("letter", t("grade.col_grade"), 50), ("term", t("grade.col_term"), 100),
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
        ttk.Button(self, text=t("common.close"), command=self.destroy).pack(pady=(0, 10))
