"""Safeguarding GUI."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.secondary_school.modules.domain.pastoral_care.safeguarding.services.safeguarding_service import (
    SafeguardingService, CONCERN_TYPES, SEVERITY_LEVELS,
)
from education_system.secondary_school.modules.domain.academics.students.services.student_service import StudentService
from education_system.secondary_school.core.exceptions import SafeguardingError

HEADER_BG = "#1a5276"
MAIN_BG = "#ecf0f1"


class SafeguardingFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = SafeguardingService(db_path)
        self._stu_svc = StudentService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg=MAIN_BG)
        header = tk.Frame(self, bg="#922b21", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Safeguarding", font=("Helvetica", 15, "bold"),
                 bg="#922b21", fg="white").pack(side="left", padx=20, pady=10)

        toolbar = tk.Frame(self, bg=MAIN_BG, pady=8)
        toolbar.pack(fill="x", padx=15)
        ttk.Button(toolbar, text="Log Concern", command=self._on_add).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Resolve", command=self._on_resolve).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Delete", command=self._on_delete).pack(side="left", padx=4)
        tk.Label(toolbar, text="Show:", bg=MAIN_BG).pack(side="left", padx=(15, 4))
        self._filter_var = tk.StringVar(value="Open")
        ttk.Combobox(toolbar, textvariable=self._filter_var, values=["All", "Open", "Resolved"],
                     state="readonly", width=8).pack(side="left", padx=4)
        self._filter_var.trace_add("write", lambda *_: self._load())

        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        cols = ("date", "student", "year", "type", "severity", "reported_by", "resolved")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for col, h, w in [("date", "Date", 80), ("student", "Student", 140),
                           ("year", "Year", 40), ("type", "Type", 100),
                           ("severity", "Severity", 65), ("reported_by", "Reported By", 100),
                           ("resolved", "Resolved", 55)]:
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
        filt = self._filter_var.get()
        resolved = None
        if filt == "Open":
            resolved = False
        elif filt == "Resolved":
            resolved = True
        try:
            concerns = self._svc.list_concerns(is_resolved=resolved)
            for c in concerns:
                self._tree.insert("", "end", iid=c["id"], values=(
                    c["incident_date"], f"{c['first_name']} {c['last_name']}",
                    c["year_group"], c["concern_type"], c["severity"],
                    c["reported_by"], "Yes" if c["is_resolved"] else "No"))
            self._status_var.set(f"{len(concerns)} concern(s)")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_add(self):
        students = self._stu_svc.list_students(status="active")
        if not students:
            return
        dlg = tk.Toplevel(self)
        dlg.title("Log Safeguarding Concern")
        dlg.resizable(False, False)
        pad = {"padx": 10, "pady": 4}
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()
        vars_ = {}
        stu_names = [f"{s['student_id']} - {s['first_name']} {s['last_name']}" for s in students]
        row = 0
        tk.Label(c, text="Student", font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
        vars_["student"] = tk.StringVar()
        ttk.Combobox(c, textvariable=vars_["student"], values=stu_names, state="readonly", width=30).grid(row=row, column=1, **pad)
        for label, key, default, values in [
            ("Type", "concern_type", "welfare", list(CONCERN_TYPES)),
            ("Severity", "severity", "low", list(SEVERITY_LEVELS)),
            ("Description", "description", "", None),
            ("Action Taken", "action_taken", "", None),
            ("Referred To", "referred_to", "", None),
        ]:
            row += 1
            tk.Label(c, text=label, font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
            vars_[key] = tk.StringVar(value=default)
            if values:
                ttk.Combobox(c, textvariable=vars_[key], values=values, state="readonly", width=30).grid(row=row, column=1, **pad)
            else:
                ttk.Entry(c, textvariable=vars_[key], width=32).grid(row=row, column=1, **pad)
        result = [None]
        def save():
            sv = vars_["student"].get()
            desc = vars_["description"].get().strip()
            if not sv or not desc:
                messagebox.showwarning("Validation", "Student and description required.")
                return
            sid = sv.split(" - ")[0]
            stu_pk = next((s["id"] for s in students if s["student_id"] == sid), None)
            result[0] = {"student_id": stu_pk, "description": desc}
            for k in ("concern_type", "severity", "action_taken", "referred_to"):
                result[0][k] = vars_[k].get().strip() or None
            dlg.destroy()
        row += 1
        btn = tk.Frame(c)
        btn.grid(row=row, column=0, columnspan=2, pady=(10, 0))
        ttk.Button(btn, text="Save", command=save).pack(side="left", padx=5)
        ttk.Button(btn, text="Cancel", command=dlg.destroy).pack(side="left", padx=5)
        self.wait_window(dlg)
        if result[0] is None:
            return
        reported_by = self._auth.get("username", "system") if self._auth else "system"
        try:
            self._svc.log_concern(reported_by=reported_by, **result[0])
            messagebox.showinfo("Logged", "Safeguarding concern logged.")
            self._load()
        except SafeguardingError as e:
            messagebox.showerror("Error", str(e))

    def _on_resolve(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select a concern.")
            return
        self._svc.resolve_concern(int(sel[0]))
        self._load()

    def _on_delete(self):
        sel = self._tree.selection()
        if not sel:
            return
        if messagebox.askyesno("Confirm", "Delete this safeguarding record?"):
            self._svc.delete_concern(int(sel[0]))
            self._load()
