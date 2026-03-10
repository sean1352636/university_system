"""Audit log GUI for the Primary School Management System."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.primary_school.modules.domain.admin.audit_log.services.audit_service import AuditService
import traceback


class AuditLogFrame(tk.Frame):
    """Read-only audit log viewer."""

    HEADER_BG = "#1a5276"

    def __init__(self, parent, db_path, auth=None):
        super().__init__(parent)
        self._db_path = db_path
        self._auth = auth
        self._service = AuditService(db_path)

        # Header
        header = tk.Frame(self, bg=self.HEADER_BG, height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Audit Log", fg="white", bg=self.HEADER_BG,
                 font=("Helvetica", 14, "bold")).pack(side="left", padx=15)

        # Toolbar / Filters
        toolbar = tk.Frame(self, bg="#d5dbdb", padx=5, pady=5)
        toolbar.pack(fill="x")

        tk.Label(toolbar, text="Username:", bg="#d5dbdb").pack(side="left")
        self._user_filter = tk.Entry(toolbar, width=14)
        self._user_filter.pack(side="left", padx=3)

        tk.Label(toolbar, text="Action:", bg="#d5dbdb").pack(side="left", padx=(8, 0))
        self._action_filter = tk.Entry(toolbar, width=14)
        self._action_filter.pack(side="left", padx=3)

        tk.Label(toolbar, text="From:", bg="#d5dbdb").pack(side="left", padx=(8, 0))
        self._date_from = tk.Entry(toolbar, width=12)
        self._date_from.pack(side="left", padx=3)

        tk.Label(toolbar, text="To:", bg="#d5dbdb").pack(side="left", padx=(4, 0))
        self._date_to = tk.Entry(toolbar, width=12)
        self._date_to.pack(side="left", padx=3)

        tk.Button(toolbar, text="Filter", command=self._load_items).pack(side="left", padx=5)
        tk.Button(toolbar, text="Clear", command=self._clear_filters).pack(side="left", padx=3)

        # Treeview
        columns = ("id", "username", "action", "table_name", "record_id", "details", "created_at")
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        for col in columns:
            self._tree.heading(col, text=col.replace("_", " ").title())
            self._tree.column(col, width=110)
        self._tree.column("id", width=50)
        self._tree.column("details", width=220)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Status bar
        self._status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_var, anchor="w", bg="#ecf0f1",
                 padx=10).pack(fill="x", side="bottom")

        self._load_items()

    def refresh(self):
        self._load_items()

    def _load_items(self):
        for item in self._tree.get_children():
            self._tree.delete(item)
        filters = {}
        username = self._user_filter.get().strip()
        if username:
            filters["username"] = username
        action = self._action_filter.get().strip()
        if action:
            filters["action"] = action
        date_from = self._date_from.get().strip()
        if date_from:
            filters["date_from"] = date_from
        date_to = self._date_to.get().strip()
        if date_to:
            filters["date_to"] = date_to
        try:
            logs = self._service.get_log(**filters)
            for log in logs:
                self._tree.insert("", tk.END, iid=log.get("id"), values=(
                    log.get("id", ""), log.get("username", ""),
                    log.get("action", ""), log.get("table_name", ""),
                    log.get("record_id", ""), log.get("details", ""),
                    log.get("created_at", ""),
                ))
            self._status_var.set(f"{len(logs)} log entry(ies) loaded")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to load audit logs: {e}")

    def _clear_filters(self):
        self._user_filter.delete(0, tk.END)
        self._action_filter.delete(0, tk.END)
        self._date_from.delete(0, tk.END)
        self._date_to.delete(0, tk.END)
        self._load_items()
