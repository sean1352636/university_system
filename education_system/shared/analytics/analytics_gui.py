"""Cross-system analytics dashboard GUI.

Provides a tkinter Frame that shows aggregate analytics across all
4 education systems: summary cards, transfer rates, retention stats,
and year-over-year trends.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from education_system.shared.analytics.analytics_service import (
    AnalyticsService,
    SYSTEM_LABELS,
    SYSTEM_ORDER,
)


class AnalyticsDashboardFrame(tk.Frame):
    """Cross-system analytics dashboard with summary cards and tabbed detail views."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._auth = auth
        self._service = AnalyticsService()
        self._build_ui()
        self.after(100, self.refresh)
        self.after_idle(self._apply_eqa_context)

    def _apply_eqa_context(self):
        """#6 — Honour an EQA drill-through. When invoked from the EQA
        dashboard's "Open in BI / Analytics" path, surface a banner
        identifying the source so the user knows the dashboard was
        opened in context."""
        ctx = getattr(self, "eqa_context", None)
        if not ctx:
            return
        try:
            import tkinter as _tk
            banner = _tk.Label(
                self,
                text=f"Opened from EQA · {ctx.get('source', '?')}",
                bg="#fff7d6", fg="#5a4500",
                font=("Helvetica", 9, "italic"), pady=3,
            )
            banner.pack(fill="x", before=self._cards_frame
                         if hasattr(self, "_cards_frame") else None)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        # Header bar
        header = tk.Frame(self, bg="#1a5276", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header,
            text="Cross-System Analytics Dashboard",
            font=("Helvetica", 15, "bold"),
            bg="#1a5276",
            fg="white",
        ).pack(side="left", padx=20, pady=10)

        ttk.Button(header, text="Refresh", command=self.refresh).pack(
            side="right", padx=10, pady=10
        )
        ttk.Button(header, text="Export CSV", command=self._export_csv).pack(
            side="right", padx=5, pady=10
        )

        # Summary cards row
        self._cards_frame = tk.Frame(self, bg="#ecf0f1")
        self._cards_frame.pack(fill="x", padx=15, pady=10)

        self._card_vars = {}
        card_defs = [
            ("total_students", "Total Students", "#2980b9"),
            ("total_transfers", "Total Transfers", "#8e44ad"),
            ("avg_progression", "Avg Progression Time", "#27ae60"),
            ("total_active", "Active Students", "#e67e22"),
        ]
        for key, label, colour in card_defs:
            card = tk.Frame(self._cards_frame, bg="white", bd=1, relief="groove",
                            padx=15, pady=10)
            card.pack(side="left", fill="x", expand=True, padx=5)

            tk.Label(card, text=label, font=("Helvetica", 9), bg="white",
                     fg="#7f8c8d").pack(anchor="w")
            var = tk.StringVar(value="--")
            self._card_vars[key] = var
            tk.Label(card, textvariable=var, font=("Helvetica", 20, "bold"),
                     bg="white", fg=colour).pack(anchor="w")

        # Notebook with tabs
        self._notebook = ttk.Notebook(self)
        self._notebook.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        # --- Overview tab ---
        overview_frame = tk.Frame(self._notebook, bg="#ecf0f1")
        self._notebook.add(overview_frame, text="  Overview  ")

        self._overview_tree = self._make_treeview(
            overview_frame,
            columns=("system", "total", "active", "transferred", "graduated"),
            headings=["System", "Total", "Active", "Transferred", "Graduated"],
            widths=[180, 100, 100, 100, 100],
        )

        # --- Transfer Rates tab ---
        transfer_frame = tk.Frame(self._notebook, bg="#ecf0f1")
        self._notebook.add(transfer_frame, text="  Transfer Rates  ")

        self._transfer_tree = self._make_treeview(
            transfer_frame,
            columns=("source", "destination", "count", "rate"),
            headings=["Source System", "Destination System", "Count", "Rate %"],
            widths=[180, 180, 100, 100],
        )

        # --- Retention tab ---
        retention_frame = tk.Frame(self._notebook, bg="#ecf0f1")
        self._notebook.add(retention_frame, text="  Retention  ")

        self._retention_tree = self._make_treeview(
            retention_frame,
            columns=("system", "total", "active", "retained_pct", "dropped", "dropout_pct"),
            headings=["System", "Total", "Active", "Retained %", "Dropped Out", "Dropout %"],
            widths=[180, 80, 80, 90, 90, 90],
        )

        # --- Trends tab ---
        trends_frame = tk.Frame(self._notebook, bg="#ecf0f1")
        self._notebook.add(trends_frame, text="  Trends  ")

        self._trends_tree = self._make_treeview(
            trends_frame,
            columns=("system", "year", "count"),
            headings=["System", "Year", "Student Count"],
            widths=[200, 120, 150],
        )

    # ------------------------------------------------------------------
    # Treeview helper
    # ------------------------------------------------------------------

    @staticmethod
    def _make_treeview(parent, columns, headings, widths):
        """Create a Treeview with scrollbar in *parent*."""
        frame = tk.Frame(parent)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        tree = ttk.Treeview(frame, columns=columns, show="headings",
                            selectmode="browse")
        for col, heading, width in zip(columns, headings, widths):
            tree.heading(col, text=heading)
            anchor = "w" if col in ("system", "source", "destination") else "center"
            tree.column(col, width=width, anchor=anchor)

        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        return tree

    # ------------------------------------------------------------------
    # Data refresh
    # ------------------------------------------------------------------

    def refresh(self):
        """Reload all analytics data from the databases."""
        try:
            self._refresh_summary()
            self._refresh_transfers()
            self._refresh_retention()
            self._refresh_trends()
        except Exception as exc:
            messagebox.showerror("Analytics Error",
                                 f"Failed to load analytics:\n{exc}", parent=self)

    def _refresh_summary(self):
        summary = self._service.get_summary()
        self._card_vars["total_students"].set(str(summary["total_students"]))
        self._card_vars["total_active"].set(str(summary["total_active"]))
        self._card_vars["total_transfers"].set(str(summary["total_transferred"]))

        # Calculate average progression time placeholder (count of systems with students)
        systems_with_students = sum(
            1 for s in summary["systems"] if s["total"] > 0
        )
        self._card_vars["avg_progression"].set(
            f"{systems_with_students} systems"
        )

        # Populate overview tree
        self._overview_tree.delete(*self._overview_tree.get_children())
        for s in summary["systems"]:
            self._overview_tree.insert("", "end", values=(
                s["label"], s["total"], s["active"],
                s["transferred"], s["graduated"],
            ))

    def _refresh_transfers(self):
        transfers = self._service.get_transfer_rates()
        self._transfer_tree.delete(*self._transfer_tree.get_children())
        for t in transfers:
            src_label = SYSTEM_LABELS.get(t["source_system"], t["source_system"])
            dst_label = SYSTEM_LABELS.get(t["destination_system"], t["destination_system"])
            self._transfer_tree.insert("", "end", values=(
                src_label, dst_label, t["count"], f"{t['rate_pct']}%",
            ))
        if not transfers:
            self._transfer_tree.insert("", "end", values=(
                "No transfer data found", "", "", "",
            ))

    def _refresh_retention(self):
        retention = self._service.get_retention_stats()
        self._retention_tree.delete(*self._retention_tree.get_children())
        for r in retention:
            self._retention_tree.insert("", "end", values=(
                r["label"], r["total"], r["active"],
                f"{r['retained_pct']}%", r["dropped_out"],
                f"{r['dropout_pct']}%",
            ))

    def _refresh_trends(self):
        trends = self._service.get_year_trends()
        self._trends_tree.delete(*self._trends_tree.get_children())
        for t in trends:
            self._trends_tree.insert("", "end", values=(
                t["label"], t["year"], t["student_count"],
            ))
        if not trends:
            self._trends_tree.insert("", "end", values=(
                "No trend data available", "", "",
            ))

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def _export_csv(self):
        """Export all analytics data to a CSV file."""
        path = filedialog.asksaveasfilename(
            parent=self,
            title="Export Analytics CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            csv_data = self._service.export_summary_csv()
            with open(path, "w", newline="", encoding="utf-8") as f:
                f.write(csv_data)
            messagebox.showinfo("Export", f"Analytics exported to:\n{path}", parent=self)
        except Exception as exc:
            messagebox.showerror("Export Error", str(exc), parent=self)
