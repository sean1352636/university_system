"""Audit Log GUI."""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.secondary_school.modules.domain.admin.audit_log.services.audit_service import (
    AuditService, AUDIT_ACTIONS,
)

HEADER_BG = "#1a5276"
MAIN_BG = "#ecf0f1"


class AuditFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = AuditService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg=MAIN_BG)
        header = tk.Frame(self, bg=HEADER_BG, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Audit Log", font=("Helvetica", 15, "bold"),
                 bg=HEADER_BG, fg="white").pack(side="left", padx=20, pady=10)

        toolbar = tk.Frame(self, bg=MAIN_BG, pady=8)
        toolbar.pack(fill="x", padx=15)
        ttk.Button(toolbar, text="Refresh", command=self._load).pack(side="left", padx=4)
        tk.Label(toolbar, text="Action:", bg=MAIN_BG).pack(side="left", padx=(15, 4))
        self._action_var = tk.StringVar(value="All")
        ttk.Combobox(toolbar, textvariable=self._action_var,
                     values=["All"] + list(AUDIT_ACTIONS), state="readonly", width=14).pack(side="left")
        self._action_var.trace_add("write", lambda *_: self._load())
        tk.Label(toolbar, text="Module:", bg=MAIN_BG).pack(side="left", padx=(10, 4))
        self._module_var = tk.StringVar()
        ttk.Entry(toolbar, textvariable=self._module_var, width=12).pack(side="left")
        self._module_var.trace_add("write", lambda *_: self._load())

        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        cols = ("time", "user", "action", "module", "record", "details")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for col, h, w in [("time", "Timestamp", 130), ("user", "User", 90),
                           ("action", "Action", 80), ("module", "Module", 90),
                           ("record", "Record ID", 60), ("details", "Details", 250)]:
            self._tree.heading(col, text=h)
            self._tree.column(col, width=w, anchor="center" if w < 200 else "w")
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
        action = self._action_var.get()
        module = self._module_var.get().strip()
        try:
            entries = self._svc.list_entries(
                action=action if action != "All" else None,
                module=module or None)
            for e in entries:
                self._tree.insert("", "end", iid=e["id"], values=(
                    e["created_at"], e.get("username") or "",
                    e["action"], e.get("module") or "",
                    e.get("record_id") or "", e.get("details") or ""))
            total = self._svc.entry_count()
            self._status_var.set(f"Showing {len(entries)} of {total} entries")
        except Exception as e:
            messagebox.showerror("Error", str(e))
