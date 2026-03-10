"""Grade management GUI."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.secondary_school.modules.domain.academics.grades.services.grade_service import GradeService, ASSESSMENT_TYPES
from education_system.secondary_school.modules.domain.academics.students.services.student_service import StudentService
from education_system.secondary_school.modules.domain.academics.subjects.services.subject_service import SubjectService
from education_system.secondary_school.core.exceptions import GradeError


class _GradeDialog(tk.Toplevel):
    def __init__(self, parent, students, subjects, grade=None):
        super().__init__(parent)
        self.title("Add Grade" if not grade else "Edit Grade")
        self.resizable(False, False)
        self.grab_set()
        self.result = None
        self._students = students
        self._subjects = subjects
        self._grade = grade
        self._build_ui()
        self.update_idletasks()
        px = parent.winfo_rootx() + parent.winfo_width() // 2
        py = parent.winfo_rooty() + parent.winfo_height() // 2
        self.geometry(f"+{px - self.winfo_width() // 2}+{py - self.winfo_height() // 2}")

    def _build_ui(self):
        pad = {"padx": 10, "pady": 5}
        c = tk.Frame(self, padx=20, pady=15)
        c.pack(fill="both", expand=True)
        row = 0

        # Student selection
        tk.Label(c, text="Student", anchor="w", font=("Helvetica", 9, "bold")).grid(
            row=row, column=0, sticky="w", **pad)
        stu_names = [f"{s['student_id']} - {s['first_name']} {s['last_name']}" for s in self._students]
        self._stu_var = tk.StringVar()
        ttk.Combobox(c, textvariable=self._stu_var, values=stu_names,
                     state="readonly", width=33).grid(row=row, column=1, sticky="ew", **pad)

        row += 1
        tk.Label(c, text="Subject", anchor="w", font=("Helvetica", 9, "bold")).grid(
            row=row, column=0, sticky="w", **pad)
        subj_names = [f"{s['subject_code']} - {s['title']}" for s in self._subjects]
        self._subj_var = tk.StringVar()
        ttk.Combobox(c, textvariable=self._subj_var, values=subj_names,
                     state="readonly", width=33).grid(row=row, column=1, sticky="ew", **pad)

        row += 1
        tk.Label(c, text="Assessment Type", anchor="w", font=("Helvetica", 9, "bold")).grid(
            row=row, column=0, sticky="w", **pad)
        self._type_var = tk.StringVar(value="classwork")
        ttk.Combobox(c, textvariable=self._type_var, values=list(ASSESSMENT_TYPES),
                     state="readonly", width=33).grid(row=row, column=1, sticky="ew", **pad)

        self._vars = {}
        for label, key, default in [
            ("Assessment Name", "assessment_name", ""),
            ("Score (0-100)", "score", ""),
            ("Grade (9-1 or U)", "grade", ""),
            ("Term", "term", "Autumn"),
            ("Academic Year", "academic_year", "2025/2026"),
            ("Teacher Comment", "teacher_comment", ""),
        ]:
            row += 1
            tk.Label(c, text=label, anchor="w", font=("Helvetica", 9, "bold")).grid(
                row=row, column=0, sticky="w", **pad)
            val = default
            if self._grade and self._grade.get(key) is not None:
                val = str(self._grade[key])
            var = tk.StringVar(value=val)
            ttk.Entry(c, textvariable=var, width=36).grid(row=row, column=1, sticky="ew", **pad)
            self._vars[key] = var

        btn = tk.Frame(c)
        btn.grid(row=row + 1, column=0, columnspan=2, pady=(15, 0))
        ttk.Button(btn, text="Save", command=self._on_save).pack(side="left", padx=5)
        ttk.Button(btn, text="Cancel", command=self.destroy).pack(side="left", padx=5)

    def _on_save(self):
        stu_val = self._stu_var.get()
        subj_val = self._subj_var.get()
        if not stu_val or not subj_val:
            messagebox.showwarning("Validation", "Select a student and subject.")
            return

        stu_sid = stu_val.split(" - ")[0]
        student_pk = None
        for s in self._students:
            if s["student_id"] == stu_sid:
                student_pk = s["id"]
                break

        subj_code = subj_val.split(" - ")[0]
        subject_pk = None
        for s in self._subjects:
            if s["subject_code"] == subj_code:
                subject_pk = s["id"]
                break

        self.result = {k: v.get().strip() for k, v in self._vars.items()}
        self.result["student_id"] = student_pk
        self.result["subject_id"] = subject_pk
        self.result["assessment_type"] = self._type_var.get()
        self.destroy()


class GradeFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._svc = GradeService(db_path)
        self._stu_svc = StudentService(db_path)
        self._subj_svc = SubjectService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#1a5276", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Grade Management", font=("Helvetica", 15, "bold"),
                 bg="#1a5276", fg="white").pack(side="left", padx=20, pady=10)

        toolbar = tk.Frame(self, bg="#ecf0f1", pady=8)
        toolbar.pack(fill="x", padx=15)
        ttk.Button(toolbar, text="Add Grade", command=self._on_add).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Delete Selected", command=self._on_delete).pack(side="left", padx=4)

        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        columns = ("student", "subject", "type", "name", "score", "grade", "term", "date")
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")

        for col, heading, w in [
            ("student", "Student", 120), ("subject", "Subject", 120),
            ("type", "Type", 80), ("name", "Assessment", 120),
            ("score", "Score", 60), ("grade", "Grade", 50),
            ("term", "Term", 70), ("date", "Date", 90),
        ]:
            self._tree.heading(col, text=heading)
            self._tree.column(col, width=w, anchor="center")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self._status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_var, bg="#ecf0f1", anchor="w",
                 font=("Helvetica", 9), fg="#7f8c8d").pack(fill="x", padx=15, pady=(0, 8))

    def refresh(self):
        self._load_grades()

    def _load_grades(self):
        self._tree.delete(*self._tree.get_children())
        conn = None
        try:
            from education_system.secondary_school.infrastructure.database.db import connect
            conn = connect(self._db_path)
            rows = conn.execute(
                """SELECT g.*, s.student_id as sid, s.first_name, s.last_name,
                          subj.subject_code, subj.title as subj_title
                   FROM grades g
                   JOIN students s ON g.student_id = s.id
                   JOIN subjects subj ON g.subject_id = subj.id
                   ORDER BY g.graded_at DESC LIMIT 500"""
            ).fetchall()

            for row in rows:
                r = dict(row)
                self._tree.insert("", "end", iid=r["id"], values=(
                    f"{r['first_name']} {r['last_name']}",
                    r["subj_title"],
                    r.get("assessment_type", ""),
                    r.get("assessment_name", "") or "",
                    r.get("score", "") if r.get("score") is not None else "",
                    r.get("grade", "") or "",
                    r.get("term", "") or "",
                    r.get("graded_at", "")[:10] if r.get("graded_at") else "",
                ))
            self._status_var.set(f"{len(rows)} grade(s) loaded")
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
        finally:
            if conn:
                conn.close()

    def _on_add(self):
        students = self._stu_svc.list_students(status="active")
        subjects = self._subj_svc.list_subjects(status="active")
        if not students or not subjects:
            messagebox.showwarning("Warning", "Need at least one student and one subject.")
            return

        dlg = _GradeDialog(self, students, subjects)
        self.wait_window(dlg)
        if dlg.result is None:
            return

        d = dlg.result
        try:
            score = float(d["score"]) if d.get("score") else None
        except ValueError:
            score = None

        try:
            self._svc.add_grade(
                student_id=d["student_id"],
                subject_id=d["subject_id"],
                assessment_type=d.get("assessment_type", "classwork"),
                assessment_name=d.get("assessment_name") or None,
                score=score,
                grade=d.get("grade") or None,
                term=d.get("term") or None,
                academic_year=d.get("academic_year") or None,
                teacher_comment=d.get("teacher_comment") or None,
            )
            messagebox.showinfo("Success", "Grade recorded.")
            self._load_grades()
        except GradeError as exc:
            messagebox.showerror("Error", str(exc))

    def _on_delete(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a grade first.")
            return
        if not messagebox.askyesno("Confirm", "Delete this grade record?"):
            return
        try:
            self._svc.delete_grade(int(sel[0]))
            self._load_grades()
        except GradeError as exc:
            messagebox.showerror("Error", str(exc))
