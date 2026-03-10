"""Incident Log GUI."""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.secondary_school.modules.domain.facilities.incidents.services.incident_service import (
    IncidentService, INCIDENT_TYPES, SEVERITY_LEVELS,
)

HEADER_BG = "#1a5276"
MAIN_BG = "#ecf0f1"


class IncidentFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = IncidentService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg=MAIN_BG)
        header = tk.Frame(self, bg=HEADER_BG, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Incident Log", font=("Helvetica", 15, "bold"),
                 bg=HEADER_BG, fg="white").pack(side="left", padx=20, pady=10)

        toolbar = tk.Frame(self, bg=MAIN_BG, pady=8)
        toolbar.pack(fill="x", padx=15)
        ttk.Button(toolbar, text="Log Incident", command=self._on_add).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Close", command=self._on_close).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Delete", command=self._on_delete).pack(side="left", padx=4)
        tk.Label(toolbar, text="Type:", bg=MAIN_BG).pack(side="left", padx=(15, 4))
        self._type_var = tk.StringVar(value="All")
        ttk.Combobox(toolbar, textvariable=self._type_var,
                     values=["All"] + list(INCIDENT_TYPES), state="readonly", width=14).pack(side="left")
        self._type_var.trace_add("write", lambda *_: self._load())
        tk.Label(toolbar, text="Status:", bg=MAIN_BG).pack(side="left", padx=(10, 4))
        self._status_filter = tk.StringVar(value="All")
        ttk.Combobox(toolbar, textvariable=self._status_filter,
                     values=["All", "open", "closed"], state="readonly", width=8).pack(side="left")
        self._status_filter.trace_add("write", lambda *_: self._load())

        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        cols = ("date", "type", "severity", "location", "description", "reported_by", "riddor", "status")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for col, h, w in [("date", "Date", 75), ("type", "Type", 90),
                           ("severity", "Severity", 65), ("location", "Location", 80),
                           ("description", "Description", 200), ("reported_by", "Reported By", 90),
                           ("riddor", "RIDDOR", 45), ("status", "Status", 55)]:
            self._tree.heading(col, text=h)
            self._tree.column(col, width=w, anchor="center" if w < 150 else "w")
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
        itype = self._type_var.get()
        status = self._status_filter.get()
        try:
            records = self._svc.list_incidents(
                incident_type=itype if itype != "All" else None,
                status=status if status != "All" else None)
            for r in records:
                desc = (r["description"] or "")[:80]
                self._tree.insert("", "end", iid=r["id"], values=(
                    r["date"], r["incident_type"], r["severity"],
                    r.get("location") or "", desc,
                    r.get("reported_by") or "",
                    "Yes" if r["riddor_reportable"] else "",
                    r["status"]))
            self._status_var.set(f"{len(records)} incident(s)")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_add(self):
        dlg = tk.Toplevel(self)
        dlg.title("Log Incident")
        dlg.resizable(False, False)
        pad = {"padx": 10, "pady": 4}
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()
        vars_ = {}
        fields = [("Type", "type", "accident", list(INCIDENT_TYPES)),
                  ("Severity", "severity", "minor", list(SEVERITY_LEVELS)),
                  ("Location", "location", "", None),
                  ("Date (YYYY-MM-DD)", "date", "", None),
                  ("Time", "time", "", None),
                  ("Description", "desc", "", None),
                  ("People Involved", "people", "", None),
                  ("Witnesses", "witnesses", "", None),
                  ("Action Taken", "action", "", None),
                  ("Reported By", "by", "", None),
                  ("Reported To", "to", "", None)]
        for row, (l, k, d, vals) in enumerate(fields):
            tk.Label(c, text=l, font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
            vars_[k] = tk.StringVar(value=d)
            if vals:
                ttk.Combobox(c, textvariable=vars_[k], values=vals, state="readonly", width=18).grid(row=row, column=1, **pad)
            else:
                ttk.Entry(c, textvariable=vars_[k], width=30).grid(row=row, column=1, **pad)
        row = len(fields)
        riddor_var = tk.BooleanVar()
        ttk.Checkbutton(c, text="RIDDOR Reportable", variable=riddor_var).grid(row=row, column=1, sticky="w", **pad)
        result = [None]

        def save():
            desc = vars_["desc"].get().strip()
            if not desc:
                messagebox.showwarning("Validation", "Description required.")
                return
            result[0] = {k: v.get().strip() for k, v in vars_.items()}
            result[0]["riddor"] = riddor_var.get()
            dlg.destroy()

        ttk.Button(c, text="Log", command=save).grid(row=row + 1, column=0, columnspan=2, pady=10)
        self.wait_window(dlg)
        if result[0] is None:
            return
        d = result[0]
        try:
            self._svc.log_incident(
                d["desc"], d["type"], d["severity"],
                d.get("location") or None, d.get("date") or None,
                d.get("time") or None, d.get("people") or None,
                d.get("witnesses") or None, d.get("action") or None,
                d.get("by") or None, d.get("to") or None,
                d.get("riddor", False))
            self._load()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_close(self):
        sel = self._tree.selection()
        if not sel:
            return
        if messagebox.askyesno("Confirm", "Close this incident?"):
            self._svc.close_incident(int(sel[0]))
            self._load()

    def _on_delete(self):
        sel = self._tree.selection()
        if not sel:
            return
        if messagebox.askyesno("Confirm", "Delete this incident record?"):
            self._svc.delete_incident(int(sel[0]))
            self._load()
