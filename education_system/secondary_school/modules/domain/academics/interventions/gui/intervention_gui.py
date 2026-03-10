"""Intervention Groups GUI."""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.secondary_school.modules.domain.academics.interventions.services.intervention_service import InterventionService

HEADER_BG = "#1a5276"
MAIN_BG = "#ecf0f1"


class InterventionFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = InterventionService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg=MAIN_BG)
        header = tk.Frame(self, bg=HEADER_BG, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Intervention Groups", font=("Helvetica", 15, "bold"),
                 bg=HEADER_BG, fg="white").pack(side="left", padx=20, pady=10)
        toolbar = tk.Frame(self, bg=MAIN_BG, pady=8)
        toolbar.pack(fill="x", padx=15)
        ttk.Button(toolbar, text="New Group", command=self._on_add).pack(side="left", padx=4)
        ttk.Button(toolbar, text="View Members", command=self._on_view_members).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Add Student", command=self._on_add_member).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Close Group", command=self._on_close).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Delete", command=self._on_delete).pack(side="left", padx=4)

        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        cols = ("name", "subject", "year", "lead", "target", "frequency", "start", "end", "status")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for col, h, w in [("name", "Group", 120), ("subject", "Subject", 90), ("year", "Year", 40),
                           ("lead", "Lead", 80), ("target", "Target", 120),
                           ("frequency", "Frequency", 70), ("start", "Start", 80),
                           ("end", "End", 80), ("status", "Status", 55)]:
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
        try:
            groups = self._svc.list_groups(status=None)
            for g in groups:
                self._tree.insert("", "end", iid=g["id"], values=(
                    g["name"], g.get("subject_title") or "", g.get("year_group") or "",
                    g.get("lead_teacher") or "", g.get("target") or "",
                    g.get("meeting_frequency") or "", g.get("start_date") or "",
                    g.get("end_date") or "", g["status"]))
            self._status_var.set(f"{len(groups)} group(s)")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_add(self):
        from education_system.secondary_school.modules.domain.academics.subjects.services.subject_service import SubjectService
        subjects = SubjectService(self._db_path).list_subjects(status="active")
        dlg = tk.Toplevel(self)
        dlg.title("New Intervention Group")
        dlg.resizable(False, False)
        pad = {"padx": 10, "pady": 4}
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()
        vars_ = {}
        tk.Label(c, text="Name", font=("Helvetica", 9, "bold")).grid(row=0, column=0, sticky="w", **pad)
        vars_["name"] = tk.StringVar()
        ttk.Entry(c, textvariable=vars_["name"], width=25).grid(row=0, column=1, **pad)
        tk.Label(c, text="Subject", font=("Helvetica", 9, "bold")).grid(row=1, column=0, sticky="w", **pad)
        subj_names = ["(none)"] + [f"{s['subject_code']} - {s['title']}" for s in subjects]
        vars_["subject"] = tk.StringVar(value="(none)")
        ttk.Combobox(c, textvariable=vars_["subject"], values=subj_names, state="readonly", width=22).grid(row=1, column=1, **pad)
        for rr, (l, k, d) in enumerate([("Year Group", "year", ""), ("Lead Teacher", "lead", ""),
                                          ("Target", "target", ""), ("Frequency", "frequency", ""),
                                          ("Start Date", "start", ""), ("End Date", "end", "")], start=2):
            tk.Label(c, text=l, font=("Helvetica", 9, "bold")).grid(row=rr, column=0, sticky="w", **pad)
            vars_[k] = tk.StringVar(value=d)
            ttk.Entry(c, textvariable=vars_[k], width=25).grid(row=rr, column=1, **pad)
        result = [None]
        def save():
            n = vars_["name"].get().strip()
            if not n:
                messagebox.showwarning("Validation", "Name required.")
                return
            sv = vars_["subject"].get()
            subj_id = None
            if sv != "(none)":
                code = sv.split(" - ")[0]
                subj_id = next((s["id"] for s in subjects if s["subject_code"] == code), None)
            result[0] = {"name": n, "subject_id": subj_id}
            for k in ("year", "lead", "target", "frequency", "start", "end"):
                result[0][k] = vars_[k].get().strip() or None
            dlg.destroy()
        ttk.Button(c, text="Create", command=save).grid(row=8, column=0, columnspan=2, pady=10)
        self.wait_window(dlg)
        if result[0] is None:
            return
        d = result[0]
        try:
            self._svc.create_group(d["name"], d["subject_id"], d.get("year"),
                                   d.get("lead"), d.get("target"), d.get("start"),
                                   d.get("end"), d.get("frequency"))
            self._load()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_view_members(self):
        sel = self._tree.selection()
        if not sel:
            return
        group_id = int(sel[0])
        members = self._svc.list_members(group_id)
        dlg = tk.Toplevel(self)
        dlg.title(f"Members ({len(members)})")
        dlg.geometry("600x350")
        cols = ("student", "year", "baseline", "target", "current", "notes")
        tree = ttk.Treeview(dlg, columns=cols, show="headings")
        for col, h, w in [("student", "Student", 130), ("year", "Year", 40),
                           ("baseline", "Baseline", 60), ("target", "Target", 60),
                           ("current", "Current", 60), ("notes", "Progress Notes", 180)]:
            tree.heading(col, text=h)
            tree.column(col, width=w, anchor="center")
        for m in members:
            tree.insert("", "end", iid=m["id"], values=(
                f"{m['first_name']} {m['last_name']}", m.get("year_group") or "",
                m.get("baseline_grade") or "", m.get("target_grade") or "",
                m.get("current_grade") or "", m.get("progress_notes") or ""))
        tree.pack(fill="both", expand=True, padx=10, pady=10)

    def _on_add_member(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select a group first.")
            return
        group_id = int(sel[0])
        from education_system.secondary_school.modules.domain.academics.students.services.student_service import StudentService
        students = StudentService(self._db_path).list_students(status="active")
        if not students:
            return
        dlg = tk.Toplevel(self)
        dlg.title("Add Student")
        dlg.resizable(False, False)
        pad = {"padx": 10, "pady": 5}
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()
        stu_names = [f"{s['student_id']} - {s['first_name']} {s['last_name']}" for s in students]
        stu_var = tk.StringVar()
        tk.Label(c, text="Student", font=("Helvetica", 9, "bold")).grid(row=0, column=0, sticky="w", **pad)
        ttk.Combobox(c, textvariable=stu_var, values=stu_names, state="readonly", width=28).grid(row=0, column=1, **pad)
        base_var = tk.StringVar()
        tk.Label(c, text="Baseline Grade", font=("Helvetica", 9, "bold")).grid(row=1, column=0, sticky="w", **pad)
        ttk.Entry(c, textvariable=base_var, width=10).grid(row=1, column=1, sticky="w", **pad)
        target_var = tk.StringVar()
        tk.Label(c, text="Target Grade", font=("Helvetica", 9, "bold")).grid(row=2, column=0, sticky="w", **pad)
        ttk.Entry(c, textvariable=target_var, width=10).grid(row=2, column=1, sticky="w", **pad)
        result = [None]
        def save():
            sv = stu_var.get()
            if not sv:
                return
            sid_str = sv.split(" - ")[0]
            spk = next((s["id"] for s in students if s["student_id"] == sid_str), None)
            result[0] = {"student_id": spk, "baseline": base_var.get().strip() or None,
                         "target": target_var.get().strip() or None}
            dlg.destroy()
        ttk.Button(c, text="Add", command=save).grid(row=3, column=0, columnspan=2, pady=10)
        self.wait_window(dlg)
        if result[0] is None:
            return
        d = result[0]
        try:
            self._svc.add_member(group_id, d["student_id"], d["baseline"], d["target"])
            messagebox.showinfo("Success", "Student added.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_close(self):
        sel = self._tree.selection()
        if not sel:
            return
        self._svc.close_group(int(sel[0]))
        self._load()

    def _on_delete(self):
        sel = self._tree.selection()
        if not sel:
            return
        if messagebox.askyesno("Confirm", "Delete this group and all members?"):
            self._svc.delete_group(int(sel[0]))
            self._load()
