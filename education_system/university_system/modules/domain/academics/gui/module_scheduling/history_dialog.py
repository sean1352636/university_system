"""Read-only viewer for the schedule_history table.

Shows the per-row change log for a single schedule_id. Records are written
by the service layer (add_module_schedule / update_module_schedule /
delete_module_schedule) so opening this against any row created or modified
through the GUI gives a complete audit trail of who changed what.
"""

import json
import logging
import tkinter as tk
from tkinter import ttk

from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.core import paths

DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH
logger = logging.getLogger(__name__)


def _format_diff(old_json: str | None, new_json: str | None) -> str:
    """Render an old/new JSON pair as a tidy multi-line key: old → new string.

    Falls back to raw JSON if either side isn't parseable.
    """
    try:
        old = json.loads(old_json) if old_json else {}
        new = json.loads(new_json) if new_json else {}
    except (TypeError, json.JSONDecodeError):
        return f"{old_json or ''}\n→\n{new_json or ''}"

    if not isinstance(old, dict) or not isinstance(new, dict):
        return f"{old_json or ''}\n→\n{new_json or ''}"

    keys = sorted(set(old) | set(new))
    if not keys:
        return ""
    lines = []
    for k in keys:
        ov = old.get(k, "—")
        nv = new.get(k, "—")
        if ov == nv:
            continue
        lines.append(f"  {k}: {ov!r} → {nv!r}")
    return "\n".join(lines) if lines else "(no field changes recorded)"


class ScheduleHistoryDialog:
    """Browse schedule_history rows for a single schedule_id."""

    def __init__(self, parent, schedule_id: int):
        self.parent = parent
        self.schedule_id = schedule_id

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"History — Schedule #{schedule_id}")
        self.dialog.geometry("760x520")
        self.dialog.transient(parent)

        self._build_ui()
        self._load()

    def _build_ui(self):
        header = ttk.Frame(self.dialog, padding=10)
        header.pack(fill=tk.X)
        ttk.Label(header, text=f"Change history for schedule #{self.schedule_id}",
                  font=("Arial", 12, "bold")).pack(side=tk.LEFT)
        ttk.Button(header, text="Refresh", command=self._load).pack(side=tk.RIGHT)

        body = ttk.Frame(self.dialog, padding=(10, 0))
        body.pack(fill=tk.BOTH, expand=True)

        cols = ("when", "action", "by")
        self.tree = ttk.Treeview(body, columns=cols, show="headings", height=10)
        for c, label, w in (("when", "When", 170),
                            ("action", "Action", 80),
                            ("by", "Changed by", 140)):
            self.tree.heading(c, text=label)
            self.tree.column(c, width=w, anchor=tk.W)
        scroll = ttk.Scrollbar(body, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._render_diff())

        # Detail pane underneath
        detail_frame = ttk.LabelFrame(self.dialog, text="Diff", padding=10)
        detail_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(8, 10))
        self.detail = tk.Text(detail_frame, wrap=tk.WORD, height=8,
                              font=("Courier", 9))
        self.detail.pack(fill=tk.BOTH, expand=True)
        self.detail.config(state=tk.DISABLED)

        self.status_var = tk.StringVar(value="")
        ttk.Label(self.dialog, textvariable=self.status_var,
                  anchor=tk.W, padding=(10, 5)).pack(fill=tk.X)
        ttk.Button(self.dialog, text="Close",
                   command=self.dialog.destroy).pack(pady=8)

    def _load(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        self._rows = []
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0)
            try:
                conn.execute("PRAGMA journal_mode=WAL")
                cur = conn.cursor()
                cur.execute("""
                    SELECT change_date, action, changed_by, old_values, new_values
                    FROM schedule_history
                    WHERE schedule_id = ?
                    ORDER BY id DESC
                """, (self.schedule_id,))
                self._rows = cur.fetchall()
            finally:
                conn.close()
        except sqlite3.Error as e:
            logger.exception("Failed to read schedule_history")
            self.status_var.set(f"Failed to read history: {e}")
            return

        for when, action, by, _ov, _nv in self._rows:
            self.tree.insert("", tk.END, values=(when, action, by or "—"))
        if not self._rows:
            self.status_var.set("No history recorded for this schedule.")
        else:
            self.status_var.set(f"{len(self._rows)} change record(s).")
            self.tree.selection_set(self.tree.get_children()[0])
            self._render_diff()

    def _render_diff(self):
        sel = self.tree.selection()
        if not sel or not self._rows:
            return
        idx = self.tree.index(sel[0])
        when, action, by, old_v, new_v = self._rows[idx]
        diff = _format_diff(old_v, new_v)
        text = f"{when}  —  {action}  by  {by or '—'}\n\n{diff}"
        self.detail.config(state=tk.NORMAL)
        self.detail.delete("1.0", tk.END)
        self.detail.insert("1.0", text)
        self.detail.config(state=tk.DISABLED)
