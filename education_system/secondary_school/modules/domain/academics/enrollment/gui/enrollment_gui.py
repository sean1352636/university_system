"""Enrollment management GUI."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.secondary_school.modules.domain.academics.enrollment.services.enrollment_service import EnrollmentService
from education_system.secondary_school.modules.domain.academics.students.services.student_service import StudentService
from education_system.secondary_school.modules.domain.academics.subjects.services.subject_service import SubjectService
from education_system.secondary_school.core.exceptions import EnrollmentError


class EnrollmentFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._svc = EnrollmentService(db_path)
        self._stu_svc = StudentService(db_path)
        self._subj_svc = SubjectService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#1a5276", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Enrollment Management", font=("Helvetica", 15, "bold"),
                 bg="#1a5276", fg="white").pack(side="left", padx=20, pady=10)

        toolbar = tk.Frame(self, bg="#ecf0f1", pady=8)
        toolbar.pack(fill="x", padx=15)
        ttk.Button(toolbar, text="Enroll Student", command=self._on_enroll).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Drop Selected", command=self._on_drop).pack(side="left", padx=4)

        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        columns = ("student", "subject", "status", "enrolled_at")
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")

        for col, heading, w in [
            ("student", "Student", 180), ("subject", "Subject", 180),
            ("status", "Status", 80), ("enrolled_at", "Enrolled At", 120),
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
        self._load_enrollments()

    def _load_enrollments(self):
        self._tree.delete(*self._tree.get_children())
        try:
            from education_system.secondary_school.infrastructure.database.db import connect
            conn = connect(self._db_path)
            rows = conn.execute(
                """SELECT e.*, s.student_id as sid, s.first_name, s.last_name,
                          subj.subject_code, subj.title
                   FROM enrollments e
                   JOIN students s ON e.student_id = s.id
                   JOIN subjects subj ON e.subject_id = subj.id
                   ORDER BY s.last_name LIMIT 500"""
            ).fetchall()
            conn.close()

            self._enrollment_data = []
            for row in rows:
                r = dict(row)
                self._tree.insert("", "end", iid=r["id"], values=(
                    f"{r['sid']} - {r['first_name']} {r['last_name']}",
                    f"{r['subject_code']} - {r['title']}",
                    r["status"],
                    r["enrolled_at"][:10] if r.get("enrolled_at") else "",
                ))
                self._enrollment_data.append(r)

            self._status_var.set(f"{len(rows)} enrollment(s) loaded")
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _on_enroll(self):
        students = self._stu_svc.list_students(status="active")
        subjects = self._subj_svc.list_subjects(status="active")
        if not students or not subjects:
            messagebox.showwarning("Warning", "Need students and subjects.")
            return

        dlg = tk.Toplevel(self)
        dlg.title("Enroll Student")
        dlg.resizable(False, False)
        dlg.grab_set()

        pad = {"padx": 10, "pady": 5}
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()

        tk.Label(c, text="Student", font=("Helvetica", 9, "bold")).grid(row=0, column=0, sticky="w", **pad)
        stu_names = [f"{s['student_id']} - {s['first_name']} {s['last_name']}" for s in students]
        stu_var = tk.StringVar()
        ttk.Combobox(c, textvariable=stu_var, values=stu_names,
                     state="readonly", width=33).grid(row=0, column=1, **pad)

        tk.Label(c, text="Subject", font=("Helvetica", 9, "bold")).grid(row=1, column=0, sticky="w", **pad)
        subj_names = [f"{s['subject_code']} - {s['title']}" for s in subjects]
        subj_var = tk.StringVar()
        ttk.Combobox(c, textvariable=subj_var, values=subj_names,
                     state="readonly", width=33).grid(row=1, column=1, **pad)

        result = [None]

        def save():
            s_val = stu_var.get()
            sub_val = subj_var.get()
            if not s_val or not sub_val:
                messagebox.showwarning("Validation", "Select both student and subject.")
                return
            s_sid = s_val.split(" - ")[0]
            sub_code = sub_val.split(" - ")[0]
            stu_pk = next((s["id"] for s in students if s["student_id"] == s_sid), None)
            sub_pk = next((s["id"] for s in subjects if s["subject_code"] == sub_code), None)
            result[0] = (stu_pk, sub_pk)
            dlg.destroy()

        btn = tk.Frame(c)
        btn.grid(row=2, column=0, columnspan=2, pady=(15, 0))
        ttk.Button(btn, text="Enroll", command=save).pack(side="left", padx=5)
        ttk.Button(btn, text="Cancel", command=dlg.destroy).pack(side="left", padx=5)

        self.wait_window(dlg)
        if result[0] is None:
            return

        stu_pk, sub_pk = result[0]
        try:
            self._svc.enroll_student(stu_pk, sub_pk)
            messagebox.showinfo("Success", "Student enrolled.")
            self._load_enrollments()
        except EnrollmentError as exc:
            messagebox.showerror("Error", str(exc))

    def _on_drop(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select an enrollment.")
            return
        if not messagebox.askyesno("Confirm", "Drop this enrollment?"):
            return

        eid = int(sel[0])
        # Find the enrollment data
        for e in self._enrollment_data:
            if e["id"] == eid:
                try:
                    self._svc.drop_enrollment(e["student_id"], e["subject_id"])
                    messagebox.showinfo("Success", "Enrollment dropped.")
                    self._load_enrollments()
                except EnrollmentError as exc:
                    messagebox.showerror("Error", str(exc))
                return
