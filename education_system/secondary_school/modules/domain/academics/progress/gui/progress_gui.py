"""Progress Tracking GUI."""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.secondary_school.modules.domain.academics.progress.services.progress_service import (
    ProgressService, GCSE_GRADES, EFFORT_GRADES,
)

HEADER_BG = "#1a5276"
MAIN_BG = "#ecf0f1"


class ProgressFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = ProgressService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg=MAIN_BG)
        header = tk.Frame(self, bg=HEADER_BG, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Progress Tracking", font=("Helvetica", 15, "bold"),
                 bg=HEADER_BG, fg="white").pack(side="left", padx=20, pady=10)

        toolbar = tk.Frame(self, bg=MAIN_BG, pady=8)
        toolbar.pack(fill="x", padx=15)
        ttk.Button(toolbar, text="Set Target", command=self._on_set_target).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Update Grade", command=self._on_update_grade).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Delete", command=self._on_delete).pack(side="left", padx=4)
        tk.Label(toolbar, text="Year:", bg=MAIN_BG).pack(side="left", padx=(15, 4))
        self._year_var = tk.StringVar(value="All")
        ttk.Combobox(toolbar, textvariable=self._year_var,
                     values=["All", "7", "8", "9", "10", "11"], state="readonly", width=6).pack(side="left")
        self._year_var.trace_add("write", lambda *_: self._load())

        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        cols = ("student", "year", "subject", "baseline", "target", "autumn", "spring", "summer", "current", "effort")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for col, h, w in [("student", "Student", 120), ("year", "Yr", 30),
                           ("subject", "Subject", 110), ("baseline", "Base", 35),
                           ("target", "Target", 40), ("autumn", "Aut", 35),
                           ("spring", "Spr", 35), ("summer", "Sum", 35),
                           ("current", "Curr", 35), ("effort", "Eff", 30)]:
            self._tree.heading(col, text=h)
            self._tree.column(col, width=w, anchor="center")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self._status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_var, bg=MAIN_BG, anchor="w",
                 font=("Helvetica", 9), fg="#7f8c8d").pack(fill="x", padx=15, pady=(0, 8))

    def refresh(self):
        self._load()

    def _load(self):
        self._tree.delete(*self._tree.get_children())
        year = self._year_var.get()
        try:
            records = self._svc.list_all(year_group=year if year != "All" else None)
            for r in records:
                self._tree.insert("", "end", iid=r["id"], values=(
                    f"{r['first_name']} {r['last_name']}", r.get("year_group") or "",
                    r.get("subject_name") or "", r.get("baseline_grade") or "",
                    r.get("target_grade") or "", r.get("autumn_grade") or "",
                    r.get("spring_grade") or "", r.get("summer_grade") or "",
                    r.get("current_grade") or "", r.get("effort") or ""))
            self._status_var.set(f"{len(records)} target(s)")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _get_students(self):
        from education_system.secondary_school.modules.domain.academics.students.services.student_service import StudentService
        return StudentService(self._db_path).list_students(status="active")

    def _get_subjects(self):
        from education_system.secondary_school.modules.domain.academics.subjects.services.subject_service import SubjectService
        return SubjectService(self._db_path).list_subjects(status="active")

    def _on_set_target(self):
        students = self._get_students()
        subjects = self._get_subjects()
        if not students or not subjects:
            messagebox.showinfo("Info", "Need students and subjects first.")
            return
        dlg = tk.Toplevel(self)
        dlg.title("Set Progress Target")
        dlg.resizable(False, False)
        pad = {"padx": 10, "pady": 4}
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()
        stu_names = [f"{s['student_id']} - {s['first_name']} {s['last_name']}" for s in students]
        sub_names = [f"{s['subject_code']} - {s['title']}" for s in subjects]
        stu_var = tk.StringVar()
        sub_var = tk.StringVar()
        base_var = tk.StringVar()
        tgt_var = tk.StringVar()
        tk.Label(c, text="Student", font=("Helvetica", 9, "bold")).grid(row=0, column=0, sticky="w", **pad)
        ttk.Combobox(c, textvariable=stu_var, values=stu_names, state="readonly", width=28).grid(row=0, column=1, **pad)
        tk.Label(c, text="Subject", font=("Helvetica", 9, "bold")).grid(row=1, column=0, sticky="w", **pad)
        ttk.Combobox(c, textvariable=sub_var, values=sub_names, state="readonly", width=28).grid(row=1, column=1, **pad)
        tk.Label(c, text="Baseline Grade", font=("Helvetica", 9, "bold")).grid(row=2, column=0, sticky="w", **pad)
        ttk.Combobox(c, textvariable=base_var, values=list(GCSE_GRADES), width=6).grid(row=2, column=1, sticky="w", **pad)
        tk.Label(c, text="Target Grade", font=("Helvetica", 9, "bold")).grid(row=3, column=0, sticky="w", **pad)
        ttk.Combobox(c, textvariable=tgt_var, values=list(GCSE_GRADES), width=6).grid(row=3, column=1, sticky="w", **pad)
        result = [None]

        def save():
            sv = stu_var.get()
            sbv = sub_var.get()
            if not sv or not sbv:
                messagebox.showwarning("Validation", "Student and subject required.")
                return
            result[0] = {"stu": sv, "sub": sbv, "base": base_var.get(), "tgt": tgt_var.get()}
            dlg.destroy()

        ttk.Button(c, text="Set Target", command=save).grid(row=4, column=0, columnspan=2, pady=10)
        self.wait_window(dlg)
        if result[0] is None:
            return
        d = result[0]
        sid_str = d["stu"].split(" - ")[0]
        sid = next((s["id"] for s in students if s["student_id"] == sid_str), None)
        sub_code = d["sub"].split(" - ")[0]
        sub_id = next((s["id"] for s in subjects if s["subject_code"] == sub_code), None)
        try:
            self._svc.set_target(sid, sub_id, baseline_grade=d["base"] or None,
                                 target_grade=d["tgt"] or None)
            self._load()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_update_grade(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select a target first.")
            return
        target_id = int(sel[0])
        dlg = tk.Toplevel(self)
        dlg.title("Update Grade")
        dlg.resizable(False, False)
        pad = {"padx": 10, "pady": 5}
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()
        term_var = tk.StringVar(value="autumn")
        grade_var = tk.StringVar()
        effort_var = tk.StringVar()
        tk.Label(c, text="Term", font=("Helvetica", 9, "bold")).grid(row=0, column=0, sticky="w", **pad)
        ttk.Combobox(c, textvariable=term_var, values=["autumn", "spring", "summer"],
                     state="readonly", width=10).grid(row=0, column=1, sticky="w", **pad)
        tk.Label(c, text="Grade", font=("Helvetica", 9, "bold")).grid(row=1, column=0, sticky="w", **pad)
        ttk.Combobox(c, textvariable=grade_var, values=list(GCSE_GRADES), width=6).grid(row=1, column=1, sticky="w", **pad)
        tk.Label(c, text="Effort", font=("Helvetica", 9, "bold")).grid(row=2, column=0, sticky="w", **pad)
        ttk.Combobox(c, textvariable=effort_var, values=list(EFFORT_GRADES), width=6).grid(row=2, column=1, sticky="w", **pad)
        result = [None]

        def save():
            g = grade_var.get().strip()
            if not g:
                messagebox.showwarning("Validation", "Grade required.")
                return
            result[0] = {"term": term_var.get(), "grade": g, "effort": effort_var.get().strip()}
            dlg.destroy()

        ttk.Button(c, text="Update", command=save).grid(row=3, column=0, columnspan=2, pady=10)
        self.wait_window(dlg)
        if result[0] is None:
            return
        d = result[0]
        try:
            self._svc.update_grade(target_id, d["term"], d["grade"], d.get("effort") or None)
            self._load()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_delete(self):
        sel = self._tree.selection()
        if not sel:
            return
        if messagebox.askyesno("Confirm", "Delete this progress target?"):
            self._svc.delete_target(int(sel[0]))
            self._load()
