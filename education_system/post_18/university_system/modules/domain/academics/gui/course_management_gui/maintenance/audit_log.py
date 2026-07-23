"""Read-only audit log viewer.

Reads from `activity_log` (high-volume, human-readable user actions) and
`audit_log` (record-level before/after diffs). Both schemas are queried via
PRAGMA so this dialog tolerates the column drift that exists between
conftest.py, services/.../database.py, and the live DB.
"""

import logging
import tkinter as tk
from tkinter import ttk, messagebox

from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from education_system.post_18.university_system.core import paths
from education_system.post_18.university_system.core.i18n import get_text as _

DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH
logger = logging.getLogger(__name__)

_TABLES = ("activity_log", "audit_log")
_DEFAULT_LIMIT = 500


class AuditLogViewerDialog:
    """Filter-and-browse view over the audit/activity log tables."""

    def __init__(self, parent, auth):
        self.parent = parent
        self.auth = auth

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Audit Log Viewer")
        self.dialog.geometry("1100x600")
        self.dialog.transient(parent)

        self._build_ui()
        self._load()

    def _build_ui(self):
        top = ttk.Frame(self.dialog, padding=10)
        top.pack(fill=tk.X)

        ttk.Label(top, text="Audit Log Viewer",
                  font=("Arial", 13, "bold")).grid(row=0, column=0, sticky=tk.W,
                                                   columnspan=8, pady=(0, 8))

        ttk.Label(top, text="Source:").grid(row=1, column=0, sticky=tk.W)
        self.source_var = tk.StringVar(value=_TABLES[0])
        ttk.Combobox(top, textvariable=self.source_var, state="readonly",
                     values=list(_TABLES), width=14
                     ).grid(row=1, column=1, padx=4)

        ttk.Label(top, text="User contains:").grid(row=1, column=2, sticky=tk.W, padx=(12, 0))
        self.user_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.user_var, width=18
                  ).grid(row=1, column=3, padx=4)

        ttk.Label(top, text="Action contains:").grid(row=1, column=4, sticky=tk.W, padx=(12, 0))
        self.action_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.action_var, width=18
                  ).grid(row=1, column=5, padx=4)

        ttk.Label(top, text="Limit:").grid(row=1, column=6, sticky=tk.W, padx=(12, 0))
        self.limit_var = tk.IntVar(value=_DEFAULT_LIMIT)
        ttk.Spinbox(top, from_=50, to=10000, increment=50,
                    textvariable=self.limit_var, width=6
                    ).grid(row=1, column=7, padx=4)

        ttk.Button(top, text=_("common.refresh", default="Refresh"),
                   command=self._load).grid(row=1, column=8, padx=(12, 0))

        # Results
        tree_frame = ttk.Frame(self.dialog, padding=10)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        cols = ("timestamp", "user", "action", "details")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=22)
        for c, label, w in (
            ("timestamp", "Timestamp", 160),
            ("user", "User", 160),
            ("action", "Action", 200),
            ("details", "Details", 540),
        ):
            self.tree.heading(c, text=label)
            self.tree.column(c, width=w, anchor=tk.W)
        yscroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        yscroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<Double-1>", self._show_row_detail)

        self.status_var = tk.StringVar(value="")
        ttk.Label(self.dialog, textvariable=self.status_var,
                  anchor=tk.W, padding=(10, 5)).pack(fill=tk.X)

        ttk.Button(self.dialog, text=_("common.close", default="Close"),
                   command=self.dialog.destroy).pack(pady=8)

    def _load(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

        table = self.source_var.get()
        if table not in _TABLES:
            self.status_var.set(f"Unknown source: {table}")
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0)
            try:
                conn.execute("PRAGMA journal_mode=WAL")
                cur = conn.cursor()
                cur.execute(f"PRAGMA table_info({table})")
                cols = {r[1] for r in cur.fetchall()}
                if not cols:
                    self.status_var.set(f"Table '{table}' not present in this DB.")
                    return

                # Pick best column for each role.
                user_col = next((c for c in ("username", "user_id", "actor")
                                if c in cols), None)
                action_col = "action" if "action" in cols else None
                ts_col = "timestamp" if "timestamp" in cols else None
                details_col = next((c for c in ("details", "new_values", "table_name")
                                    if c in cols), None)
                if not (user_col and action_col and ts_col):
                    self.status_var.set(
                        f"Table '{table}' missing required columns "
                        f"(needs user/action/timestamp).")
                    return

                where = []
                params = []
                user_q = self.user_var.get().strip()
                if user_q:
                    where.append(f"CAST({user_col} AS TEXT) LIKE ?")
                    params.append(f"%{user_q}%")
                action_q = self.action_var.get().strip()
                if action_q:
                    where.append(f"{action_col} LIKE ?")
                    params.append(f"%{action_q}%")
                where_sql = ("WHERE " + " AND ".join(where)) if where else ""

                limit = max(1, min(int(self.limit_var.get() or _DEFAULT_LIMIT), 10000))
                select_cols = [ts_col, user_col, action_col,
                               details_col if details_col else "'' AS details"]
                sql = (f"SELECT {', '.join(select_cols)} FROM {table} "
                       f"{where_sql} ORDER BY {ts_col} DESC LIMIT ?")
                cur.execute(sql, (*params, limit))
                rows = cur.fetchall()
            finally:
                conn.close()
        except sqlite3.Error as e:
            logger.exception("Audit log query failed")
            messagebox.showerror(_("common.database_error"),
                                 f"Failed to read {table}: {e}")
            return

        for ts, user, action, details in rows:
            details_short = (details or "")
            if isinstance(details_short, str) and len(details_short) > 200:
                details_short = details_short[:197] + "..."
            self.tree.insert("", tk.END, values=(ts, user, action, details_short),
                             tags=(str(details or ""),))

        self.status_var.set(f"{len(rows)} row(s) from {table}.")

    def _show_row_detail(self, _event):
        sel = self.tree.selection()
        if not sel:
            return
        tags = self.tree.item(sel[0], "tags")
        full_detail = tags[0] if tags else ""
        if not full_detail:
            return
        win = tk.Toplevel(self.dialog)
        win.title("Audit Detail")
        win.geometry("700x400")
        win.transient(self.dialog)
        text = tk.Text(win, wrap=tk.WORD)
        text.insert("1.0", full_detail)
        text.config(state=tk.DISABLED)
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        ttk.Button(win, text=_("common.close", default="Close"),
                   command=win.destroy).pack(pady=8)
