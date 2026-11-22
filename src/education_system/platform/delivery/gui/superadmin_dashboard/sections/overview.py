"""Dashboard overview: alerts, trends and the system comparison table.

Split out of the former single-file ``superadmin_dashboard.py``; methods are
mixed into :class:`education_system.platform.delivery.gui.superadmin_dashboard.app.SuperAdminDashboard`.
"""

import tkinter as tk
from datetime import datetime
from tkinter import ttk

from education_system.platform.delivery.gui.superadmin_dashboard.theme import (
    ALERT_COLORS,
    ALERT_OK,
    CARD_BG,
    COMPARISON_COLUMNS,
    CONTENT_BG,
    SYSTEM_LABELS,
    SYSTEM_ORDER,
    TEXT_DARK,
    TEXT_LIGHT,
    TEXT_MUTED,
)


class OverviewMixin:
    # ------------------------------------------------------------------
    # "Needs Attention" panel
    # ------------------------------------------------------------------

    def _build_alerts_panel(self, parent):
        """Render a triage panel of cross-system operational alerts.

        Empty state shows an "all clear" row so the panel is reassuring rather
        than blank. Each alert is clickable and jumps to the relevant section.
        """
        alerts = []
        svc = self._get_admin_service()
        if svc:
            try:
                alerts = svc.get_alerts()
            except Exception:
                alerts = []

        critical = sum(1 for a in alerts if a.get("severity") == "critical")
        header_text = "Needs Attention"
        if alerts:
            header_text += f"  ({len(alerts)})"

        header_row = tk.Frame(parent, bg=CONTENT_BG)
        header_row.pack(fill=tk.X, padx=24, pady=(0, 6))

        tk.Label(
            header_row,
            text=header_text,
            font=("Segoe UI", 13, "bold"),
            bg=CONTENT_BG,
            fg="#c0392b" if critical else TEXT_DARK,
        ).pack(side=tk.LEFT)

        panel = tk.Frame(parent, bg=CARD_BG, relief=tk.RAISED, bd=1)
        panel.pack(fill=tk.X, padx=24, pady=(0, 16))

        if not alerts:
            ok_row = tk.Frame(panel, bg=CARD_BG)
            ok_row.pack(fill=tk.X, padx=14, pady=12)
            dot = tk.Canvas(ok_row, width=12, height=12, bg=CARD_BG, highlightthickness=0)
            dot.create_oval(1, 1, 11, 11, fill=ALERT_OK, outline="")
            dot.pack(side=tk.LEFT, padx=(0, 10))
            tk.Label(
                ok_row,
                text="All systems healthy — no alerts.",
                font=("Segoe UI", 10),
                bg=CARD_BG,
                fg=TEXT_DARK,
            ).pack(side=tk.LEFT)
            return

        for i, alert in enumerate(alerts):
            self._build_alert_row(panel, alert, last=(i == len(alerts) - 1))

    def _build_alert_row(self, parent, alert, last=False):
        severity = alert.get("severity", "info")
        color = ALERT_COLORS.get(severity, ALERT_COLORS["info"])
        action = alert.get("action")

        row = tk.Frame(parent, bg=CARD_BG, cursor="hand2" if action else "arrow")
        row.pack(fill=tk.X, padx=14, pady=(8, 8 if last else 0))

        # Severity dot
        dot = tk.Canvas(row, width=12, height=12, bg=CARD_BG, highlightthickness=0)
        dot.create_oval(1, 1, 11, 11, fill=color, outline="")
        dot.pack(side=tk.LEFT, padx=(0, 10), pady=2)

        # Severity pill
        tk.Label(
            row,
            text=severity.upper(),
            font=("Segoe UI", 7, "bold"),
            bg=color,
            fg=TEXT_LIGHT,
            padx=6,
            pady=1,
        ).pack(side=tk.LEFT, padx=(0, 10))

        tk.Label(
            row,
            text=alert.get("message", ""),
            font=("Segoe UI", 10),
            bg=CARD_BG,
            fg=TEXT_DARK,
            anchor=tk.W,
            justify=tk.LEFT,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        if action:
            tk.Label(
                row,
                text="Resolve  →",
                font=("Segoe UI", 9, "bold"),
                bg=CARD_BG,
                fg=color,
            ).pack(side=tk.RIGHT)

            def _go(_e=None, target=action):
                self._show_section(target)

            for widget in (row, *row.winfo_children()):
                widget.bind("<Button-1>", _go)

        # Thin divider between rows
        if not last:
            tk.Frame(parent, bg="#ecf0f1", height=1).pack(fill=tk.X, padx=14)

    # ------------------------------------------------------------------
    # Trends (sparklines)
    # ------------------------------------------------------------------

    _TREND_COLORS = {
        "students": "#2980b9",
        "staff": "#27ae60",
        "users": "#e67e22",
        "storage_mb": "#8e44ad",
    }

    def _build_trends_panel(self, parent):
        """Render 30-day sparklines for the headline aggregate metrics."""
        svc = self._get_admin_service()
        if not svc:
            return
        try:
            svc.record_metrics_snapshot()  # capture today's point (daily-deduped)
            trends = svc.get_trends()
        except Exception:
            return
        if not trends:
            return

        tk.Label(
            parent, text="Trends (last 30 days)",
            font=("Segoe UI", 13, "bold"), bg=CONTENT_BG, fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(8, 6))

        card = tk.Frame(parent, bg=CARD_BG, relief=tk.RAISED, bd=1)
        card.pack(fill=tk.X, padx=24, pady=(0, 16))
        row = tk.Frame(card, bg=CARD_BG)
        row.pack(fill=tk.X, padx=12, pady=12)

        for i, t in enumerate(trends):
            color = self._TREND_COLORS.get(t["metric"], "#3498db")
            cell = tk.Frame(row, bg=CARD_BG)
            cell.grid(row=0, column=i, padx=12, sticky=tk.NSEW)
            row.columnconfigure(i, weight=1)

            tk.Label(
                cell, text=t["label"], font=("Segoe UI", 9),
                bg=CARD_BG, fg=TEXT_MUTED,
            ).pack(anchor=tk.W)

            cur = t["current"]
            cur_text = f"{cur:.1f}" if t["metric"] == "storage_mb" else f"{int(cur)}"
            tk.Label(
                cell, text=cur_text, font=("Segoe UI", 18, "bold"),
                bg=CARD_BG, fg=TEXT_DARK,
            ).pack(anchor=tk.W)

            if t["count"] >= 2:
                change = t["change"]
                if change > 0:
                    sign, ch_color = "▲", "#27ae60"
                elif change < 0:
                    sign, ch_color = "▼", "#e74c3c"
                else:
                    sign, ch_color = "—", TEXT_MUTED
                mag = f"{abs(change):.1f}" if t["metric"] == "storage_mb" else f"{int(abs(change))}"
                tk.Label(
                    cell, text=f"{sign} {mag}  ({t['change_pct']:+}%)",
                    font=("Segoe UI", 9, "bold"), bg=CARD_BG, fg=ch_color,
                ).pack(anchor=tk.W)
                self._draw_sparkline(cell, t["values"], color)
            else:
                tk.Label(
                    cell, text="collecting data…", font=("Segoe UI", 8),
                    bg=CARD_BG, fg=TEXT_MUTED,
                ).pack(anchor=tk.W, pady=(6, 0))

    # ------------------------------------------------------------------
    # Section: Dashboard (Overview)
    # ------------------------------------------------------------------

    def _build_dashboard(self):
        _, frame = self._make_scrollable(self._content_frame)

        # Section title
        tk.Label(
            frame,
            text="Dashboard Overview",
            font=("Segoe UI", 18, "bold"),
            bg=CONTENT_BG,
            fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(20, 4))

        tk.Label(
            frame,
            text=f"Welcome back. Today is {datetime.now().strftime('%A, %d %B %Y')}.",
            font=("Segoe UI", 10),
            bg=CONTENT_BG,
            fg=TEXT_MUTED,
        ).pack(anchor=tk.W, padx=24, pady=(0, 16))

        # "Needs Attention" panel — operational exceptions across all systems
        self._build_alerts_panel(frame)

        # System cards row
        health_data = []
        svc = self._get_admin_service()
        if svc:
            try:
                health_data = svc.get_system_health()
            except Exception:
                pass

        cards_row = tk.Frame(frame, bg=CONTENT_BG)
        cards_row.pack(fill=tk.X, padx=20, pady=(0, 12))

        if health_data:
            for i, info in enumerate(health_data):
                card = self._make_system_card(cards_row, info)
                card.grid(row=0, column=i, padx=6, pady=4, sticky=tk.NSEW)
                cards_row.columnconfigure(i, weight=1)
        else:
            # Fallback: show placeholder cards for all 5 systems
            for i, sys_key in enumerate(SYSTEM_ORDER):
                placeholder = {
                    "system": sys_key,
                    "label": SYSTEM_LABELS.get(sys_key, sys_key),
                    "status": "unknown",
                    "student_count": "N/A",
                    "staff_count": "N/A",
                    "db_size_mb": "N/A",
                }
                card = self._make_system_card(cards_row, placeholder)
                card.grid(row=0, column=i, padx=6, pady=4, sticky=tk.NSEW)
                cards_row.columnconfigure(i, weight=1)

        # Summary stats row
        total_students = sum(h.get("student_count", 0) for h in health_data)
        total_staff = sum(h.get("staff_count", 0) for h in health_data)

        # Get additional summary data
        total_transfers = 0
        active_sessions = 0
        analytics_svc = self._get_analytics_service()
        if analytics_svc:
            try:
                summary = analytics_svc.get_summary()
                total_transfers = summary.get("total_transferred", 0)
            except Exception:
                pass

        user_summary = {}
        if svc:
            try:
                user_summary = svc.get_user_summary()
                active_sessions = user_summary.get("total_users", 0)
            except Exception:
                pass

        stats_row = tk.Frame(frame, bg=CONTENT_BG)
        stats_row.pack(fill=tk.X, padx=20, pady=(0, 16))

        stat_items = [
            ("Total Students", total_students, "#2980b9"),
            ("Total Staff", total_staff, "#27ae60"),
            ("Total Transfers", total_transfers, "#8e44ad"),
            ("Registered Users", active_sessions, "#e67e22"),
        ]
        for i, (label, val, color) in enumerate(stat_items):
            card = self._make_stat_card(stats_row, label, val, color=color)
            card.grid(row=0, column=i, padx=6, pady=4, sticky=tk.NSEW)
            stats_row.columnconfigure(i, weight=1)

        # Trends (30-day sparklines)
        self._build_trends_panel(frame)

        # Recent activity
        tk.Label(
            frame,
            text="Recent Activity",
            font=("Segoe UI", 13, "bold"),
            bg=CONTENT_BG,
            fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(8, 6))

        activity_frame = tk.Frame(frame, bg=CARD_BG, relief=tk.RAISED, bd=1)
        activity_frame.pack(fill=tk.X, padx=24, pady=(0, 20))

        audit_entries = []
        if svc:
            try:
                audit_entries = svc.get_audit_summary(limit=10)
            except Exception:
                pass

        if audit_entries:
            for entry in audit_entries[:10]:
                row = tk.Frame(activity_frame, bg=CARD_BG)
                row.pack(fill=tk.X, padx=12, pady=4)

                etype = entry.get("type", "")
                dot_color = "#3498db" if etype == "notification" else "#9b59b6"
                dot = tk.Canvas(row, width=10, height=10, bg=CARD_BG, highlightthickness=0)
                dot.create_oval(1, 1, 9, 9, fill=dot_color, outline="")
                dot.pack(side=tk.LEFT, padx=(0, 8), pady=4)

                tk.Label(
                    row,
                    text=entry.get("description", ""),
                    font=("Segoe UI", 9),
                    bg=CARD_BG,
                    fg=TEXT_DARK,
                    anchor=tk.W,
                ).pack(side=tk.LEFT, fill=tk.X, expand=True)

                ts = entry.get("timestamp", "")
                if ts:
                    tk.Label(
                        row,
                        text=ts[:16],
                        font=("Segoe UI", 8),
                        bg=CARD_BG,
                        fg=TEXT_MUTED,
                    ).pack(side=tk.RIGHT)
        else:
            tk.Label(
                activity_frame,
                text="No recent activity found.",
                font=("Segoe UI", 10),
                bg=CARD_BG,
                fg=TEXT_MUTED,
            ).pack(padx=12, pady=16)

    # ------------------------------------------------------------------
    # Comparative table (system x metrics, sortable)
    # ------------------------------------------------------------------

    def _build_comparison_table(self, parent, rows):
        """Render all systems as one sortable table so outliers stand out."""
        tk.Label(
            parent,
            text="Systems at a Glance",
            font=("Segoe UI", 13, "bold"),
            bg=CONTENT_BG,
            fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(0, 2))
        tk.Label(
            parent,
            text="Click a column header to sort. Red = offline/error, orange = open issues.",
            font=("Segoe UI", 8),
            bg=CONTENT_BG,
            fg=TEXT_MUTED,
        ).pack(anchor=tk.W, padx=24, pady=(0, 6))

        wrapper = tk.Frame(parent, bg=CARD_BG, relief=tk.RAISED, bd=1)
        wrapper.pack(fill=tk.X, padx=24, pady=(0, 4))

        col_ids = [c[0] for c in COMPARISON_COLUMNS]
        tree = ttk.Treeview(
            wrapper, columns=col_ids, show="headings",
            height=len(rows), selectmode="none",
        )
        for col_id, heading, width, anchor, _key, _fmt in COMPARISON_COLUMNS:
            tree.heading(
                col_id, text=heading,
                command=lambda c=col_id: self._sort_comparison(c),
            )
            tree.column(col_id, width=width, anchor=anchor, stretch=True)

        tree.tag_configure("down", foreground="#e74c3c")
        tree.tag_configure("issue", foreground="#e67e22")
        tree.tag_configure("ok", foreground=TEXT_DARK)

        tree.pack(fill=tk.X, padx=2, pady=2)

        # State for sorting; default order is the configured system order.
        self._cmp_tree = tree
        self._cmp_rows = list(rows)
        self._cmp_sort_col = None
        self._cmp_sort_desc = False
        self._populate_comparison()

    def _populate_comparison(self):
        tree = self._cmp_tree
        tree.delete(*tree.get_children())
        fmts = {c[0]: c[5] for c in COMPARISON_COLUMNS}
        for r in self._cmp_rows:
            values = [fmts[c[0]](r) for c in COMPARISON_COLUMNS]
            if r["status"] != "online":
                tag = "down"
            elif r["open_issues"] > 0:
                tag = "issue"
            else:
                tag = "ok"
            tree.insert("", tk.END, values=values, tags=(tag,))

    def _sort_comparison(self, col_id):
        key_fn = next(c[4] for c in COMPARISON_COLUMNS if c[0] == col_id)
        if self._cmp_sort_col == col_id:
            self._cmp_sort_desc = not self._cmp_sort_desc
        else:
            self._cmp_sort_col = col_id
            self._cmp_sort_desc = False
        self._cmp_rows.sort(key=key_fn, reverse=self._cmp_sort_desc)
        self._populate_comparison()

        # Reflect sort direction in the heading text.
        arrow = " ▼" if self._cmp_sort_desc else " ▲"
        for c in COMPARISON_COLUMNS:
            heading = c[1] + (arrow if c[0] == col_id else "")
            self._cmp_tree.heading(c[0], text=heading)
