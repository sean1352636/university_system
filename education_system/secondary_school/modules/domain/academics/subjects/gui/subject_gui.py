"""Subject management GUI."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.secondary_school.modules.domain.academics.subjects.services.subject_service import SubjectService
from education_system.secondary_school.core.exceptions import SubjectError, ValidationError


class _SubjectDialog(tk.Toplevel):
    def __init__(self, parent, title="Subject", subject=None):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.grab_set()
        self.result = None
        self._subject = subject
        self._build_ui()
        self.update_idletasks()
        px = parent.winfo_rootx() + parent.winfo_width() // 2
        py = parent.winfo_rooty() + parent.winfo_height() // 2
        self.geometry(f"+{px - self.winfo_width() // 2}+{py - self.winfo_height() // 2}")

    def _build_ui(self):
        pad = {"padx": 10, "pady": 5}
        c = tk.Frame(self, padx=20, pady=15)
        c.pack(fill="both", expand=True)

        self._vars = {}
        fields = [
            ("Subject Code", "subject_code"),
            ("Title", "title"),
            ("Description", "description"),
            ("Department", "department"),
            ("Teacher", "teacher"),
            ("Room", "room"),
            ("Capacity", "capacity"),
        ]

        for i, (label, key) in enumerate(fields):
            tk.Label(c, text=label, anchor="w", font=("Helvetica", 9, "bold")).grid(
                row=i, column=0, sticky="w", **pad)
            default = ""
            if self._subject and self._subject.get(key) is not None:
                default = str(self._subject[key])
            var = tk.StringVar(value=default)
            ttk.Entry(c, textvariable=var, width=36).grid(row=i, column=1, sticky="ew", **pad)
            self._vars[key] = var

        row = len(fields)
        tk.Label(c, text="Key Stage", anchor="w", font=("Helvetica", 9, "bold")).grid(
            row=row, column=0, sticky="w", **pad)
        self._vars["key_stage"] = tk.StringVar(
            value=self._subject.get("key_stage", "KS3") if self._subject else "KS3"
        )
        ttk.Combobox(c, textvariable=self._vars["key_stage"],
                     values=["KS3", "KS4"], state="readonly", width=33).grid(
            row=row, column=1, sticky="ew", **pad)

        row += 1
        self._core_var = tk.BooleanVar(
            value=bool(self._subject.get("is_core", 0)) if self._subject else False
        )
        ttk.Checkbutton(c, text="Core Subject", variable=self._core_var).grid(
            row=row, column=0, columnspan=2, sticky="w", **pad)

        if self._subject:
            row += 1
            tk.Label(c, text="Status", anchor="w", font=("Helvetica", 9, "bold")).grid(
                row=row, column=0, sticky="w", **pad)
            self._status_var = tk.StringVar(value=self._subject.get("status", "active"))
            ttk.Combobox(c, textvariable=self._status_var,
                         values=["active", "inactive"], state="readonly", width=33).grid(
                row=row, column=1, sticky="ew", **pad)
        else:
            self._status_var = None

        btn = tk.Frame(c)
        btn.grid(row=row + 1, column=0, columnspan=2, pady=(15, 0))
        ttk.Button(btn, text="Save", command=self._on_save).pack(side="left", padx=5)
        ttk.Button(btn, text="Cancel", command=self.destroy).pack(side="left", padx=5)

    def _on_save(self):
        self.result = {k: v.get().strip() for k, v in self._vars.items()}
        self.result["is_core"] = self._core_var.get()
        if self._status_var:
            self.result["status"] = self._status_var.get()
        self.destroy()


class SubjectFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._svc = SubjectService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#1a5276", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Subject Management", font=("Helvetica", 15, "bold"),
                 bg="#1a5276", fg="white").pack(side="left", padx=20, pady=10)

        toolbar = tk.Frame(self, bg="#ecf0f1", pady=8)
        toolbar.pack(fill="x", padx=15)
        ttk.Button(toolbar, text="Add Subject", command=self._on_add).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Edit Selected", command=self._on_edit).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Delete Selected", command=self._on_delete).pack(side="left", padx=4)

        tk.Label(toolbar, text="Key Stage:", bg="#ecf0f1").pack(side="left", padx=(20, 4))
        self._ks_filter = tk.StringVar(value="All")
        ttk.Combobox(toolbar, textvariable=self._ks_filter,
                     values=["All", "KS3", "KS4"], state="readonly", width=6).pack(side="left", padx=4)
        self._ks_filter.trace_add("write", lambda *_: self._load_subjects())

        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        columns = ("subject_code", "title", "department", "key_stage", "teacher", "room", "is_core", "status")
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")

        for col, heading, w in [
            ("subject_code", "Code", 80), ("title", "Title", 160),
            ("department", "Dept", 100), ("key_stage", "KS", 50),
            ("teacher", "Teacher", 120), ("room", "Room", 60),
            ("is_core", "Core", 50), ("status", "Status", 70),
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
        self._load_subjects()

    def _load_subjects(self):
        self._tree.delete(*self._tree.get_children())
        ks = self._ks_filter.get()
        key_stage = ks if ks != "All" else None
        try:
            subjects = self._svc.list_subjects(key_stage=key_stage)
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            return

        for s in subjects:
            self._tree.insert("", "end", iid=s["id"], values=(
                s["subject_code"], s["title"], s.get("department", "") or "",
                s["key_stage"], s.get("teacher", "") or "", s.get("room", "") or "",
                "Yes" if s.get("is_core") else "No", s["status"],
            ))
        self._status_var.set(f"{len(subjects)} subject(s) loaded")

    def _selected_pk(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a subject first.")
            return None
        return int(sel[0])

    def _on_add(self):
        dlg = _SubjectDialog(self, title="Add Subject")
        self.wait_window(dlg)
        if dlg.result is None:
            return
        d = dlg.result
        if not d.get("subject_code") or not d.get("title"):
            messagebox.showwarning("Validation", "Subject code and title are required.")
            return
        try:
            cap = int(d.get("capacity") or 30)
        except ValueError:
            cap = 30
        try:
            self._svc.create_subject(
                subject_code=d["subject_code"], title=d["title"],
                description=d.get("description") or None,
                department=d.get("department") or None,
                key_stage=d.get("key_stage", "KS3"),
                is_core=d.get("is_core", False),
                capacity=cap, teacher=d.get("teacher") or None,
                room=d.get("room") or None,
            )
            messagebox.showinfo("Success", "Subject created.")
            self._load_subjects()
        except (SubjectError, ValidationError) as exc:
            messagebox.showerror("Error", str(exc))

    def _on_edit(self):
        pk = self._selected_pk()
        if pk is None:
            return
        subject = self._svc.get_subject(pk)
        if not subject:
            messagebox.showerror("Error", "Subject not found.")
            return
        dlg = _SubjectDialog(self, title="Edit Subject", subject=subject)
        self.wait_window(dlg)
        if dlg.result is None:
            return
        d = dlg.result
        try:
            updates = {}
            for key in ("subject_code", "title", "description", "department",
                        "key_stage", "teacher", "room", "status"):
                if d.get(key):
                    updates[key] = d[key]
            if "is_core" in d:
                updates["is_core"] = int(d["is_core"])
            if d.get("capacity"):
                try:
                    updates["capacity"] = int(d["capacity"])
                except ValueError:
                    pass
            if updates:
                self._svc.update_subject(pk, **updates)
                messagebox.showinfo("Success", "Subject updated.")
                self._load_subjects()
        except (SubjectError, ValidationError) as exc:
            messagebox.showerror("Error", str(exc))

    def _on_delete(self):
        pk = self._selected_pk()
        if pk is None:
            return
        if not messagebox.askyesno("Confirm", "Delete this subject and all related data?"):
            return
        try:
            self._svc.delete_subject(pk)
            messagebox.showinfo("Success", "Subject deleted.")
            self._load_subjects()
        except SubjectError as exc:
            messagebox.showerror("Error", str(exc))
