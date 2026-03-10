"""Homework GUI."""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.secondary_school.modules.domain.academics.homework.services.homework_service import HomeworkService
from education_system.secondary_school.modules.domain.academics.subjects.services.subject_service import SubjectService
from education_system.secondary_school.core.exceptions import HomeworkError

HEADER_BG = "#1a5276"
MAIN_BG = "#ecf0f1"


class HomeworkFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = HomeworkService(db_path)
        self._subj_svc = SubjectService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg=MAIN_BG)
        header = tk.Frame(self, bg=HEADER_BG, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Homework", font=("Helvetica", 15, "bold"),
                 bg=HEADER_BG, fg="white").pack(side="left", padx=20, pady=10)
        toolbar = tk.Frame(self, bg=MAIN_BG, pady=8)
        toolbar.pack(fill="x", padx=15)
        ttk.Button(toolbar, text="Set Homework", command=self._on_add).pack(side="left", padx=4)
        ttk.Button(toolbar, text="View Submissions", command=self._on_view_subs).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Delete", command=self._on_delete).pack(side="left", padx=4)

        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        cols = ("subject", "title", "year", "set_by", "set_date", "due_date", "max_marks", "status")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for col, h, w in [("subject", "Subject", 120), ("title", "Title", 160),
                           ("year", "Year", 40), ("set_by", "Set By", 90),
                           ("set_date", "Set", 80), ("due_date", "Due", 80),
                           ("max_marks", "Marks", 45), ("status", "Status", 55)]:
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
            hws = self._svc.list_homework()
            for h in hws:
                self._tree.insert("", "end", iid=h["id"], values=(
                    h.get("subject_title", ""), h["title"], h.get("year_group") or "",
                    h.get("set_by") or "", h["set_date"], h["due_date"],
                    h.get("max_marks") or "", h["status"]))
            self._status_var.set(f"{len(hws)} homework(s)")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_add(self):
        subjects = self._subj_svc.list_subjects(status="active")
        if not subjects:
            return
        dlg = tk.Toplevel(self)
        dlg.title("Set Homework")
        dlg.resizable(False, False)
        pad = {"padx": 10, "pady": 5}
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()
        vars_ = {}
        subj_names = [f"{s['subject_code']} - {s['title']}" for s in subjects]
        row = 0
        tk.Label(c, text="Subject", font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
        vars_["subject"] = tk.StringVar()
        ttk.Combobox(c, textvariable=vars_["subject"], values=subj_names, state="readonly", width=28).grid(row=row, column=1, **pad)
        for l, k, d in [("Title", "title", ""), ("Year Group", "year_group", ""),
                          ("Description", "description", ""), ("Due Date (YYYY-MM-DD)", "due_date", ""),
                          ("Max Marks", "max_marks", "")]:
            row += 1
            tk.Label(c, text=l, font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
            vars_[k] = tk.StringVar(value=d)
            ttk.Entry(c, textvariable=vars_[k], width=30).grid(row=row, column=1, **pad)
        result = [None]
        def save():
            sv = vars_["subject"].get()
            t = vars_["title"].get().strip()
            dd = vars_["due_date"].get().strip()
            if not sv or not t or not dd:
                messagebox.showwarning("Validation", "Subject, title and due date required.")
                return
            code = sv.split(" - ")[0]
            spk = next((s["id"] for s in subjects if s["subject_code"] == code), None)
            result[0] = {"subject_id": spk, "title": t, "due_date": dd}
            for k in ("year_group", "description", "max_marks"):
                result[0][k] = vars_[k].get().strip() or None
            dlg.destroy()
        row += 1
        ttk.Button(c, text="Save", command=save).grid(row=row, column=0, columnspan=2, pady=10)
        self.wait_window(dlg)
        if result[0] is None:
            return
        d = result[0]
        set_by = self._auth.get("username") if self._auth else None
        try:
            mm = int(d["max_marks"]) if d["max_marks"] else None
        except ValueError:
            mm = None
        try:
            self._svc.create_homework(d["subject_id"], d["title"], d["due_date"],
                                       d["year_group"], d["description"], set_by, mm)
            messagebox.showinfo("Success", "Homework set.")
            self._load()
        except HomeworkError as e:
            messagebox.showerror("Error", str(e))

    def _on_view_subs(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select a homework first.")
            return
        subs = self._svc.get_submissions(int(sel[0]))
        dlg = tk.Toplevel(self)
        dlg.title("Submissions")
        dlg.geometry("500x350")
        cols = ("student", "submitted", "marks", "feedback", "status")
        tree = ttk.Treeview(dlg, columns=cols, show="headings")
        for col, h, w in [("student", "Student", 140), ("submitted", "Submitted", 120),
                           ("marks", "Marks", 50), ("feedback", "Feedback", 120), ("status", "Status", 60)]:
            tree.heading(col, text=h)
            tree.column(col, width=w, anchor="center")
        for s in subs:
            tree.insert("", "end", values=(
                f"{s['first_name']} {s['last_name']}", s.get("submitted_at") or "",
                s.get("marks") if s.get("marks") is not None else "", s.get("feedback") or "", s["status"]))
        tree.pack(fill="both", expand=True, padx=10, pady=10)

    def _on_delete(self):
        sel = self._tree.selection()
        if not sel:
            return
        if messagebox.askyesno("Confirm", "Delete this homework and all submissions?"):
            self._svc.delete_homework(int(sel[0]))
            self._load()
