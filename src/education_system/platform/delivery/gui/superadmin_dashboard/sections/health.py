"""System Health section.

Split out of the former single-file ``superadmin_dashboard.py``; methods are
mixed into :class:`education_system.platform.delivery.gui.superadmin_dashboard.app.SuperAdminDashboard`.
"""

import tkinter as tk

from education_system.platform.delivery.gui.superadmin_dashboard.theme import (
    CARD_BG,
    CONTENT_BG,
    DEFAULT_SYSTEM_COLOR,
    SYSTEM_COLORS,
    TEXT_DARK,
    TEXT_MUTED,
)


class HealthMixin:
    # ------------------------------------------------------------------
    # Section: System Health
    # ------------------------------------------------------------------

    def _build_health(self):
        _, frame = self._make_scrollable(self._content_frame)

        tk.Label(
            frame,
            text="System Health",
            font=("Segoe UI", 18, "bold"),
            bg=CONTENT_BG,
            fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(20, 4))

        tk.Label(
            frame,
            text="Database status and resource usage for each education system.",
            font=("Segoe UI", 10),
            bg=CONTENT_BG,
            fg=TEXT_MUTED,
        ).pack(anchor=tk.W, padx=24, pady=(0, 16))

        svc = self._get_admin_service()

        # Comparative table — all systems side by side, sortable.
        comparison = []
        if svc:
            try:
                comparison = svc.get_comparison()
            except Exception:
                comparison = []
        if comparison:
            self._build_comparison_table(frame, comparison)

        health_data = []
        if svc:
            try:
                health_data = svc.get_system_health()
            except Exception:
                pass

        if not health_data:
            if not comparison:
                tk.Label(
                    frame,
                    text="Unable to retrieve system health data.",
                    font=("Segoe UI", 11),
                    bg=CONTENT_BG,
                    fg="#e74c3c",
                ).pack(pady=30)
            return

        tk.Label(
            frame,
            text="Per-System Detail",
            font=("Segoe UI", 13, "bold"),
            bg=CONTENT_BG,
            fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(16, 6))

        for info in health_data:
            sys_key = info.get("system", "")
            color = SYSTEM_COLORS.get(sys_key, DEFAULT_SYSTEM_COLOR)

            card = tk.Frame(frame, bg=CARD_BG, relief=tk.RAISED, bd=1)
            card.pack(fill=tk.X, padx=24, pady=6)

            accent = tk.Frame(card, bg=color, width=6)
            accent.pack(side=tk.LEFT, fill=tk.Y)

            body = tk.Frame(card, bg=CARD_BG)
            body.pack(fill=tk.BOTH, expand=True, padx=16, pady=12)

            # Title + status
            title_row = tk.Frame(body, bg=CARD_BG)
            title_row.pack(fill=tk.X)

            tk.Label(
                title_row,
                text=info.get("label", sys_key),
                font=("Segoe UI", 13, "bold"),
                bg=CARD_BG,
                fg=TEXT_DARK,
            ).pack(side=tk.LEFT)

            status = info.get("status", "offline")
            status_text = status.upper()
            status_fg = "#2ecc71" if status == "online" else (
                "#e74c3c" if status == "error" else "#95a5a6"
            )
            tk.Label(
                title_row,
                text=status_text,
                font=("Segoe UI", 10, "bold"),
                bg=CARD_BG,
                fg=status_fg,
            ).pack(side=tk.RIGHT)

            # Details grid
            details_frame = tk.Frame(body, bg=CARD_BG)
            details_frame.pack(fill=tk.X, pady=(8, 0))

            detail_items = [
                ("Database Exists", "Yes" if info.get("db_exists") else "No"),
                ("DB Size", f"{info.get('db_size_mb', 0)} MB"),
                ("Students", str(info.get("student_count", 0))),
                ("Staff", str(info.get("staff_count", 0))),
                ("Last Activity", info.get("last_activity", "N/A") or "N/A"),
            ]

            for i, (dlabel, dval) in enumerate(detail_items):
                col = i % 5
                tk.Label(
                    details_frame,
                    text=dlabel,
                    font=("Segoe UI", 8),
                    bg=CARD_BG,
                    fg=TEXT_MUTED,
                ).grid(row=0, column=col, padx=(0, 20), sticky=tk.W)
                tk.Label(
                    details_frame,
                    text=dval,
                    font=("Segoe UI", 10, "bold"),
                    bg=CARD_BG,
                    fg=TEXT_DARK,
                ).grid(row=1, column=col, padx=(0, 20), sticky=tk.W)

            # DB path
            svc2 = self._get_admin_service()
            db_path_text = ""
            if svc2:
                try:
                    cfg = svc2.get_system_config(sys_key)
                    db_path_text = cfg.get("db_path", "")
                except Exception:
                    pass

            if db_path_text:
                tk.Label(
                    body,
                    text=f"Path: {db_path_text}",
                    font=("Segoe UI", 8),
                    bg=CARD_BG,
                    fg=TEXT_MUTED,
                ).pack(anchor=tk.W, pady=(6, 0))
