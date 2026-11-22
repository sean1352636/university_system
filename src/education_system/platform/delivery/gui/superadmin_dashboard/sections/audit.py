"""Audit Log section.

Split out of the former single-file ``superadmin_dashboard.py``; methods are
mixed into :class:`education_system.platform.delivery.gui.superadmin_dashboard.app.SuperAdminDashboard`.
"""

import tkinter as tk
from datetime import datetime, timedelta
from tkinter import messagebox, ttk

from education_system.platform.delivery.gui.superadmin_dashboard.theme import (
    CONTENT_BG,
    TEXT_DARK,
    TEXT_LIGHT,
    TEXT_MUTED,
)


class AuditMixin:
    # ------------------------------------------------------------------
    # Section: Audit Log
    # ------------------------------------------------------------------

    def _build_audit(self):
        tk.Label(
            self._content_frame,
            text="Audit Log",
            font=("Segoe UI", 18, "bold"),
            bg=CONTENT_BG,
            fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(20, 4))

        tk.Label(
            self._content_frame,
            text="Recent cross-system transfers, notifications, and administrative activity.",
            font=("Segoe UI", 10),
            bg=CONTENT_BG,
            fg=TEXT_MUTED,
        ).pack(anchor=tk.W, padx=24, pady=(0, 8))

        # Filter bar
        filter_bar = tk.Frame(self._content_frame, bg=CONTENT_BG)
        filter_bar.pack(fill=tk.X, padx=24, pady=(0, 8))

        tk.Label(filter_bar, text="Type:", font=("Segoe UI", 10), bg=CONTENT_BG).pack(side=tk.LEFT, padx=(0, 4))
        type_var = tk.StringVar(value="All")
        ttk.Combobox(
            filter_bar, textvariable=type_var,
            values=["All", "notification", "transfer"], state="readonly", width=12,
        ).pack(side=tk.LEFT, padx=(0, 10))

        tk.Label(filter_bar, text="From:", font=("Segoe UI", 10), bg=CONTENT_BG).pack(side=tk.LEFT, padx=(0, 4))
        from_var = tk.StringVar(value=(datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"))
        tk.Entry(filter_bar, textvariable=from_var, font=("Segoe UI", 10), width=11).pack(side=tk.LEFT, padx=(0, 8))

        tk.Label(filter_bar, text="To:", font=("Segoe UI", 10), bg=CONTENT_BG).pack(side=tk.LEFT, padx=(0, 4))
        to_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        tk.Entry(filter_bar, textvariable=to_var, font=("Segoe UI", 10), width=11).pack(side=tk.LEFT, padx=(0, 8))

        tk.Label(filter_bar, text="Search:", font=("Segoe UI", 10), bg=CONTENT_BG).pack(side=tk.LEFT, padx=(0, 4))
        search_var = tk.StringVar()
        tk.Entry(filter_bar, textvariable=search_var, font=("Segoe UI", 10), width=16).pack(side=tk.LEFT, padx=(0, 8))

        tree_frame = tk.Frame(self._content_frame, bg=CONTENT_BG)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=24, pady=(0, 8))

        columns = ("type", "timestamp", "description", "details")
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=20)

        for col, heading, w in [
            ("type", "Type", 100),
            ("timestamp", "Timestamp", 160),
            ("description", "Description", 300),
            ("details", "Details", 300),
        ]:
            tree.heading(col, text=heading)
            tree.column(col, width=w, minwidth=60)

        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        no_data_label = tk.Label(
            self._content_frame, text="", font=("Segoe UI", 10), bg=CONTENT_BG, fg=TEXT_MUTED,
        )
        no_data_label.pack(pady=4)

        def _load_entries():
            tree.delete(*tree.get_children())
            no_data_label.config(text="")
            svc = self._get_admin_service()
            if not svc:
                no_data_label.config(text="Admin service unavailable.")
                return
            tf = type_var.get() if type_var.get() != "All" else None
            st = search_var.get().strip() or None
            df = from_var.get().strip() or None
            dt = to_var.get().strip() or None
            try:
                entries = svc.get_audit_summary(
                    limit=200, type_filter=tf, search_text=st,
                    date_from=df, date_to=dt,
                )
            except Exception:
                entries = []
            for e in entries:
                tree.insert("", tk.END, values=(
                    e.get("type", "").title(),
                    e.get("timestamp", "")[:19],
                    e.get("description", ""),
                    e.get("details", ""),
                ))
            if not entries:
                no_data_label.config(text="No audit entries match the current filters.")

        tk.Button(
            filter_bar, text="Apply", font=("Segoe UI", 10), bg="#3498db", fg=TEXT_LIGHT,
            relief=tk.FLAT, cursor="hand2", padx=10, command=_load_entries,
        ).pack(side=tk.LEFT, padx=(0, 6))

        # Export audit log
        def _export_audit():
            svc = self._get_admin_service()
            if not svc:
                return
            tf = type_var.get() if type_var.get() != "All" else None
            st = search_var.get().strip() or None
            df = from_var.get().strip() or None
            dt = to_var.get().strip() or None
            try:
                entries = svc.get_audit_summary(
                    limit=5000, type_filter=tf, search_text=st,
                    date_from=df, date_to=dt,
                )
                import csv
                import io
                from tkinter import filedialog
                path = filedialog.asksaveasfilename(
                    title="Export Audit Log",
                    defaultextension=".csv",
                    filetypes=[("CSV Files", "*.csv")],
                    initialfile=f"audit_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    parent=self,
                )
                if path:
                    with open(path, "w", newline="", encoding="utf-8") as f:
                        writer = csv.writer(f)
                        writer.writerow(["Type", "Timestamp", "Description", "Details"])
                        for e in entries:
                            writer.writerow([
                                e.get("type", ""), e.get("timestamp", ""),
                                e.get("description", ""), e.get("details", ""),
                            ])
                    messagebox.showinfo("Exported", f"Audit log exported to:\n{path}")
            except Exception as exc:
                messagebox.showerror("Export Error", str(exc))

        tk.Button(
            filter_bar, text="Export CSV", font=("Segoe UI", 9), bg="#27ae60", fg=TEXT_LIGHT,
            relief=tk.FLAT, cursor="hand2", padx=10, command=_export_audit,
        ).pack(side=tk.LEFT)

        _load_entries()
