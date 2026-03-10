"""Permissions & Consent GUI."""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.secondary_school.modules.domain.student_life.consent.services.consent_service import (
    ConsentService, CONSENT_TYPES,
)

HEADER_BG = "#1a5276"
MAIN_BG = "#ecf0f1"


class ConsentFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = ConsentService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg=MAIN_BG)
        header = tk.Frame(self, bg=HEADER_BG, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Permissions & Consent", font=("Helvetica", 15, "bold"),
                 bg=HEADER_BG, fg="white").pack(side="left", padx=20, pady=10)

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=15, pady=10)

        # --- Records tab ---
        rtab = tk.Frame(nb, bg=MAIN_BG)
        nb.add(rtab, text="Consent Records")
        toolbar = tk.Frame(rtab, bg=MAIN_BG, pady=8)
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="Add Record", command=self._on_add).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Toggle Consent", command=self._on_toggle).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Delete", command=self._on_delete).pack(side="left", padx=4)
        tk.Label(toolbar, text="Type:", bg=MAIN_BG).pack(side="left", padx=(15, 4))
        self._type_var = tk.StringVar(value="All")
        ttk.Combobox(toolbar, textvariable=self._type_var,
                     values=["All"] + list(CONSENT_TYPES), state="readonly", width=18).pack(side="left")
        self._type_var.trace_add("write", lambda *_: self._load())

        tree_frame = tk.Frame(rtab)
        tree_frame.pack(fill="both", expand=True, pady=(0, 10))
        cols = ("student", "year", "type", "granted", "by", "date", "expires")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for col, h, w in [("student", "Student", 130), ("year", "Year", 35),
                           ("type", "Consent Type", 140), ("granted", "Granted", 50),
                           ("by", "By", 90), ("date", "Date", 80), ("expires", "Expires", 80)]:
            self._tree.heading(col, text=h)
            self._tree.column(col, width=w, anchor="center")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # --- Summary tab ---
        stab = tk.Frame(nb, bg=MAIN_BG)
        nb.add(stab, text="Summary")
        ttk.Button(stab, text="Refresh", command=self._load_summary).pack(anchor="w", padx=10, pady=8)
        sf = tk.Frame(stab)
        sf.pack(fill="both", expand=True, pady=(0, 10))
        scols = ("type", "total", "granted", "pct")
        self._stree = ttk.Treeview(sf, columns=scols, show="headings", selectmode="browse")
        for col, h, w in [("type", "Consent Type", 180), ("total", "Total", 60),
                           ("granted", "Granted", 60), ("pct", "%", 50)]:
            self._stree.heading(col, text=h)
            self._stree.column(col, width=w, anchor="center")
        self._stree.pack(fill="both", expand=True)

        self._status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_var, bg=MAIN_BG, anchor="w",
                 font=("Helvetica", 9), fg="#7f8c8d").pack(fill="x", padx=15, pady=(0, 8))

    def refresh(self):
        self._load()

    def _load(self):
        self._tree.delete(*self._tree.get_children())
        ctype = self._type_var.get()
        try:
            records = self._svc.list_records(
                consent_type=ctype if ctype != "All" else None)
            for r in records:
                self._tree.insert("", "end", iid=r["id"], values=(
                    f"{r['first_name']} {r['last_name']}", r.get("year_group") or "",
                    r["consent_type"], "Yes" if r["granted"] else "No",
                    r.get("granted_by") or "", r.get("granted_date") or "",
                    r.get("expires_at") or ""))
            self._status_var.set(f"{len(records)} record(s)")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _load_summary(self):
        self._stree.delete(*self._stree.get_children())
        try:
            summary = self._svc.summary_by_type()
            for s in summary:
                total = s["total"]
                granted = s["granted_count"] or 0
                pct = f"{(granted / total * 100):.0f}%" if total > 0 else "0%"
                self._stree.insert("", "end", values=(
                    s["consent_type"], total, granted, pct))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_add(self):
        from education_system.secondary_school.modules.domain.academics.students.services.student_service import StudentService
        students = StudentService(self._db_path).list_students(status="active")
        if not students:
            return
        dlg = tk.Toplevel(self)
        dlg.title("Add Consent Record")
        dlg.resizable(False, False)
        pad = {"padx": 10, "pady": 4}
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()
        stu_names = [f"{s['student_id']} - {s['first_name']} {s['last_name']}" for s in students]
        stu_var = tk.StringVar()
        type_var = tk.StringVar(value="photo_internal")
        granted_var = tk.BooleanVar()
        by_var = tk.StringVar()
        date_var = tk.StringVar()
        tk.Label(c, text="Student", font=("Helvetica", 9, "bold")).grid(row=0, column=0, sticky="w", **pad)
        ttk.Combobox(c, textvariable=stu_var, values=stu_names, state="readonly", width=28).grid(row=0, column=1, **pad)
        tk.Label(c, text="Consent Type", font=("Helvetica", 9, "bold")).grid(row=1, column=0, sticky="w", **pad)
        ttk.Combobox(c, textvariable=type_var, values=list(CONSENT_TYPES), state="readonly", width=20).grid(row=1, column=1, **pad)
        tk.Label(c, text="Granted By", font=("Helvetica", 9, "bold")).grid(row=2, column=0, sticky="w", **pad)
        ttk.Entry(c, textvariable=by_var, width=20).grid(row=2, column=1, sticky="w", **pad)
        tk.Label(c, text="Date", font=("Helvetica", 9, "bold")).grid(row=3, column=0, sticky="w", **pad)
        ttk.Entry(c, textvariable=date_var, width=12).grid(row=3, column=1, sticky="w", **pad)
        ttk.Checkbutton(c, text="Consent Granted", variable=granted_var).grid(row=4, column=1, sticky="w", **pad)
        result = [None]

        def save():
            sv = stu_var.get()
            if not sv:
                messagebox.showwarning("Validation", "Student required.")
                return
            sid_str = sv.split(" - ")[0]
            sid = next((s["id"] for s in students if s["student_id"] == sid_str), None)
            result[0] = {"sid": sid, "type": type_var.get(), "granted": granted_var.get(),
                         "by": by_var.get().strip(), "date": date_var.get().strip()}
            dlg.destroy()

        ttk.Button(c, text="Save", command=save).grid(row=5, column=0, columnspan=2, pady=10)
        self.wait_window(dlg)
        if result[0] is None:
            return
        d = result[0]
        try:
            self._svc.add_record(d["sid"], d["type"], d["granted"],
                                 d.get("by") or None, d.get("date") or None)
            self._load()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_toggle(self):
        sel = self._tree.selection()
        if not sel:
            return
        rid = int(sel[0])
        vals = self._tree.item(sel[0], "values")
        currently_granted = vals[3] == "Yes"
        self._svc.toggle_granted(rid, not currently_granted)
        self._load()

    def _on_delete(self):
        sel = self._tree.selection()
        if not sel:
            return
        if messagebox.askyesno("Confirm", "Delete this consent record?"):
            self._svc.delete_record(int(sel[0]))
            self._load()
