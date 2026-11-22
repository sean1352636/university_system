"""Analytics section.

Split out of the former single-file ``superadmin_dashboard.py``; methods are
mixed into :class:`education_system.platform.delivery.gui.superadmin_dashboard.app.SuperAdminDashboard`.
"""

import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

from education_system.platform.delivery.gui.superadmin_dashboard.theme import (
    CARD_BG,
    CONTENT_BG,
    DEFAULT_SYSTEM_COLOR,
    SYSTEM_COLORS,
    SYSTEM_LABELS,
    SYSTEM_ORDER,
    TEXT_DARK,
    TEXT_LIGHT,
    TEXT_MUTED,
)


class AnalyticsMixin:
    # ------------------------------------------------------------------
    # Section: Student Analytics
    # ------------------------------------------------------------------

    def _build_analytics(self):
        _, frame = self._make_scrollable(self._content_frame)

        tk.Label(
            frame,
            text="Student Analytics",
            font=("Segoe UI", 18, "bold"),
            bg=CONTENT_BG,
            fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(20, 4))

        tk.Label(
            frame,
            text="Cross-system student statistics, transfer rates, and retention data.",
            font=("Segoe UI", 10),
            bg=CONTENT_BG,
            fg=TEXT_MUTED,
        ).pack(anchor=tk.W, padx=24, pady=(0, 8))

        # Export button
        export_bar = tk.Frame(frame, bg=CONTENT_BG)
        export_bar.pack(fill=tk.X, padx=24, pady=(0, 12))

        def _export_csv():
            svc = self._get_analytics_service()
            if not svc:
                messagebox.showerror("Error", "Analytics service unavailable.")
                return
            try:
                csv_data = svc.export_summary_csv()
                from tkinter import filedialog
                path = filedialog.asksaveasfilename(
                    title="Export Analytics CSV",
                    defaultextension=".csv",
                    filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
                    initialfile=f"analytics_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    parent=self,
                )
                if path:
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(csv_data)
                    messagebox.showinfo("Exported", f"Analytics exported to:\n{path}")
            except Exception as exc:
                messagebox.showerror("Export Error", str(exc))

        tk.Button(
            export_bar, text="Export CSV", font=("Segoe UI", 9), bg="#27ae60", fg=TEXT_LIGHT,
            relief=tk.FLAT, cursor="hand2", padx=10, pady=2, command=_export_csv,
        ).pack(side=tk.LEFT)

        analytics_svc = self._get_analytics_service()

        # Summary cards
        summary = {}
        if analytics_svc:
            try:
                summary = analytics_svc.get_summary()
            except Exception:
                pass

        cards_row = tk.Frame(frame, bg=CONTENT_BG)
        cards_row.pack(fill=tk.X, padx=20, pady=(0, 12))

        summary_items = [
            ("Total Students", summary.get("total_students", 0), "#2980b9"),
            ("Active", summary.get("total_active", 0), "#27ae60"),
            ("Transferred", summary.get("total_transferred", 0), "#8e44ad"),
            ("Graduated", summary.get("total_graduated", 0), "#e67e22"),
        ]
        for i, (label, val, color) in enumerate(summary_items):
            card = self._make_stat_card(cards_row, label, val, color=color)
            card.grid(row=0, column=i, padx=6, pady=4, sticky=tk.NSEW)
            cards_row.columnconfigure(i, weight=1)

        # Per-system breakdown
        tk.Label(
            frame,
            text="Per-System Breakdown",
            font=("Segoe UI", 13, "bold"),
            bg=CONTENT_BG,
            fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(12, 6))

        per_system = summary.get("systems", [])
        if per_system:
            ps_frame = tk.Frame(frame, bg=CONTENT_BG)
            ps_frame.pack(fill=tk.X, padx=20, pady=(0, 12))

            # 3 columns → a 3×3 grid across the nine systems.
            _ANALYTICS_COLS = 3
            for c in range(_ANALYTICS_COLS):
                ps_frame.columnconfigure(c, weight=1, uniform="sysgrid")

            for i, sys_info in enumerate(per_system):
                sys_key = sys_info.get("system", "")
                color = SYSTEM_COLORS.get(sys_key, DEFAULT_SYSTEM_COLOR)
                grid_row, grid_col = divmod(i, _ANALYTICS_COLS)
                card = tk.Frame(ps_frame, bg=CARD_BG, relief=tk.RAISED, bd=1)
                card.grid(row=grid_row, column=grid_col, padx=6, pady=6, sticky=tk.NSEW)

                accent = tk.Frame(card, bg=color, height=4)
                accent.pack(fill=tk.X, side=tk.TOP)

                tk.Label(
                    card,
                    text=sys_info.get("label", sys_key),
                    font=("Segoe UI", 11, "bold"),
                    bg=CARD_BG,
                    fg=TEXT_DARK,
                ).pack(padx=10, pady=(8, 2), anchor=tk.W)

                for stat_name in ("total", "active", "transferred", "graduated", "dropped_out"):
                    val = sys_info.get(stat_name, 0)
                    row = tk.Frame(card, bg=CARD_BG)
                    row.pack(fill=tk.X, padx=10, pady=1)
                    tk.Label(
                        row,
                        text=stat_name.replace("_", " ").title(),
                        font=("Segoe UI", 9),
                        bg=CARD_BG,
                        fg=TEXT_MUTED,
                    ).pack(side=tk.LEFT)
                    tk.Label(
                        row,
                        text=str(val),
                        font=("Segoe UI", 9, "bold"),
                        bg=CARD_BG,
                        fg=TEXT_DARK,
                    ).pack(side=tk.RIGHT)

                tk.Frame(card, bg=CARD_BG, height=8).pack()

        # Retention stats
        tk.Label(
            frame,
            text="Retention Statistics",
            font=("Segoe UI", 13, "bold"),
            bg=CONTENT_BG,
            fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(12, 6))

        retention = []
        if analytics_svc:
            try:
                retention = analytics_svc.get_retention_stats()
            except Exception:
                pass

        if retention:
            ret_tree_frame = tk.Frame(frame, bg=CONTENT_BG)
            ret_tree_frame.pack(fill=tk.X, padx=24, pady=(0, 12))

            ret_cols = ("system", "total", "active", "retained_pct", "dropped_out", "dropout_pct")
            ret_tree = ttk.Treeview(ret_tree_frame, columns=ret_cols, show="headings", height=5)
            for col, heading, w in [
                ("system", "System", 160),
                ("total", "Total", 80),
                ("active", "Active", 80),
                ("retained_pct", "Retained %", 100),
                ("dropped_out", "Dropped Out", 100),
                ("dropout_pct", "Dropout %", 100),
            ]:
                ret_tree.heading(col, text=heading)
                ret_tree.column(col, width=w, minwidth=60)

            for r in retention:
                ret_tree.insert("", tk.END, values=(
                    r.get("label", ""),
                    r.get("total", 0),
                    r.get("active", 0),
                    f"{r.get('retained_pct', 0)}%",
                    r.get("dropped_out", 0),
                    f"{r.get('dropout_pct', 0)}%",
                ))
            ret_tree.pack(fill=tk.X)

        # Transfer rates
        tk.Label(
            frame,
            text="Transfer Rates",
            font=("Segoe UI", 13, "bold"),
            bg=CONTENT_BG,
            fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(12, 6))

        transfers = []
        if analytics_svc:
            try:
                transfers = analytics_svc.get_transfer_rates()
            except Exception:
                pass

        if transfers:
            tr_frame = tk.Frame(frame, bg=CONTENT_BG)
            tr_frame.pack(fill=tk.X, padx=24, pady=(0, 20))

            tr_cols = ("source", "destination", "count", "rate")
            tr_tree = ttk.Treeview(tr_frame, columns=tr_cols, show="headings", height=min(8, len(transfers)))
            for col, heading, w in [
                ("source", "Source", 160),
                ("destination", "Destination", 160),
                ("count", "Count", 80),
                ("rate", "Rate %", 80),
            ]:
                tr_tree.heading(col, text=heading)
                tr_tree.column(col, width=w, minwidth=60)

            for t in transfers:
                src = SYSTEM_LABELS.get(t.get("source_system", ""), t.get("source_system", ""))
                dst = SYSTEM_LABELS.get(t.get("destination_system", ""), t.get("destination_system", ""))
                tr_tree.insert("", tk.END, values=(
                    src, dst, t.get("count", 0), f"{t.get('rate_pct', 0)}%",
                ))
            tr_tree.pack(fill=tk.X)
        else:
            tk.Label(
                frame,
                text="No transfer data available.",
                font=("Segoe UI", 10),
                bg=CONTENT_BG,
                fg=TEXT_MUTED,
            ).pack(padx=24, pady=8, anchor=tk.W)

        # Year-over-year trends (drill-down analytics, Feature 10)
        tk.Label(
            frame, text="Year-over-Year Trends",
            font=("Segoe UI", 13, "bold"), bg=CONTENT_BG, fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(12, 6))

        trends = []
        if analytics_svc:
            try:
                trends = analytics_svc.get_year_trends()
            except Exception:
                pass

        if trends:
            trend_frame = tk.Frame(frame, bg=CONTENT_BG)
            trend_frame.pack(fill=tk.X, padx=24, pady=(0, 12))

            trend_cols = ("system", "year", "count")
            trend_tree = ttk.Treeview(
                trend_frame, columns=trend_cols, show="headings",
                height=min(10, len(trends)),
            )
            for col, heading, w in [
                ("system", "System", 160),
                ("year", "Year", 80),
                ("count", "Student Count", 120),
            ]:
                trend_tree.heading(col, text=heading)
                trend_tree.column(col, width=w, minwidth=60)

            for t in trends:
                trend_tree.insert("", tk.END, values=(
                    t.get("label", ""), t.get("year", ""), t.get("student_count", 0),
                ))
            trend_tree.pack(fill=tk.X)
        else:
            tk.Label(
                frame, text="No trend data available.",
                font=("Segoe UI", 10), bg=CONTENT_BG, fg=TEXT_MUTED,
            ).pack(padx=24, pady=8, anchor=tk.W)

        # Comparative summary (drill-down analytics, Feature 10)
        tk.Label(
            frame, text="Cross-System Comparison",
            font=("Segoe UI", 13, "bold"), bg=CONTENT_BG, fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(12, 6))

        comp_frame = tk.Frame(frame, bg=CONTENT_BG)
        comp_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

        health_data = []
        svc = self._get_admin_service()
        if svc:
            try:
                health_data = svc.get_system_health()
            except Exception:
                pass

        retention = []
        if analytics_svc:
            try:
                retention = analytics_svc.get_retention_stats()
            except Exception:
                pass

        ret_map = {r["system"]: r for r in retention}

        for i, sys_key in enumerate(SYSTEM_ORDER):
            color = SYSTEM_COLORS.get(sys_key, DEFAULT_SYSTEM_COLOR)
            card = tk.Frame(comp_frame, bg=CARD_BG, relief=tk.RAISED, bd=1)
            card.grid(row=0, column=i, padx=6, pady=4, sticky=tk.NSEW)
            comp_frame.columnconfigure(i, weight=1)

            accent = tk.Frame(card, bg=color, height=4)
            accent.pack(fill=tk.X, side=tk.TOP)

            tk.Label(
                card, text=SYSTEM_LABELS.get(sys_key, sys_key),
                font=("Segoe UI", 10, "bold"), bg=CARD_BG, fg=TEXT_DARK,
            ).pack(padx=8, pady=(6, 2), anchor=tk.W)

            # Find matching health and retention data
            h = next((x for x in health_data if x.get("system") == sys_key), {})
            r = ret_map.get(sys_key, {})

            stats = [
                ("Students", h.get("student_count", 0)),
                ("Staff", h.get("staff_count", 0)),
                ("DB Size", f"{h.get('db_size_mb', 0)} MB"),
                ("Retained", f"{r.get('retained_pct', 0)}%"),
                ("Dropout", f"{r.get('dropout_pct', 0)}%"),
            ]
            for stat_label, stat_val in stats:
                row = tk.Frame(card, bg=CARD_BG)
                row.pack(fill=tk.X, padx=8, pady=1)
                tk.Label(row, text=stat_label, font=("Segoe UI", 8), bg=CARD_BG, fg=TEXT_MUTED).pack(side=tk.LEFT)
                tk.Label(row, text=str(stat_val), font=("Segoe UI", 8, "bold"), bg=CARD_BG, fg=TEXT_DARK).pack(
                    side=tk.RIGHT
                )

            tk.Frame(card, bg=CARD_BG, height=6).pack()
