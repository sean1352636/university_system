"""Academic Misconduct section.

Split out of the former single-file ``superadmin_dashboard.py``; methods are
mixed into :class:`education_system.platform.delivery.gui.superadmin_dashboard.app.SuperAdminDashboard`.
"""

import tkinter as tk
from tkinter import messagebox

from education_system.platform.delivery.gui.superadmin_dashboard.theme import (
    CARD_BG,
    CONTENT_BG,
    DEFAULT_SYSTEM_COLOR,
    SYSTEM_COLORS,
    SYSTEM_LABELS,
    SYSTEM_ORDER,
    TEXT_DARK,
    TEXT_MUTED,
)


class MisconductMixin:
    # ------------------------------------------------------------------
    # Section: Academic Misconduct (Cross-System)
    # ------------------------------------------------------------------

    def _build_misconduct(self):
        """Build the cross-system academic misconduct overview and launch panel."""
        _, frame = self._make_scrollable(self._content_frame)

        tk.Label(
            frame,
            text="Academic Misconduct - Cross-System Overview",
            font=("Segoe UI", 18, "bold"),
            bg=CONTENT_BG,
            fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(20, 4))

        tk.Label(
            frame,
            text="View misconduct cases across all education systems or launch the full misconduct panel.",
            font=("Segoe UI", 10),
            bg=CONTENT_BG,
            fg=TEXT_MUTED,
        ).pack(anchor=tk.W, padx=24, pady=(0, 20))

        # Stats cards across systems
        try:
            import sqlite3
            from education_system.platform.governance.academic_misconduct._imports import DEFAULT_DB_PATH
            from education_system.platform.governance.academic_misconduct.database import init_misconduct_tables

            init_misconduct_tables()
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Global stats
            stats_frame = tk.Frame(frame, bg=CONTENT_BG)
            stats_frame.pack(fill=tk.X, padx=24, pady=(0, 20))

            cursor.execute("SELECT COUNT(*) FROM academic_misconduct_cases")
            total = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM academic_misconduct_cases WHERE status != 'Resolved'")
            active = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM academic_misconduct_cases WHERE status = 'Resolved'")
            resolved = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM academic_misconduct_cases WHERE severity = 'Critical'")
            critical = cursor.fetchone()[0]

            global_stats = [
                ("Total Cases", total, "#3498db"),
                ("Active", active, "#f39c12"),
                ("Resolved", resolved, "#27ae60"),
                ("Critical", critical, "#e74c3c"),
            ]

            for i, (label, value, color) in enumerate(global_stats):
                card = tk.Frame(stats_frame, bg=color, width=160, height=80)
                card.pack(side=tk.LEFT, padx=6, fill=tk.BOTH, expand=True)
                card.pack_propagate(False)
                tk.Label(card, text=str(value), font=("Segoe UI", 24, "bold"),
                         fg="white", bg=color).pack(pady=(10, 0))
                tk.Label(card, text=label, font=("Segoe UI", 9),
                         fg="white", bg=color).pack(pady=(0, 8))

            # Per-system breakdown
            tk.Label(
                frame,
                text="Per-System Breakdown",
                font=("Segoe UI", 14, "bold"),
                bg=CONTENT_BG,
                fg=TEXT_DARK,
            ).pack(anchor=tk.W, padx=24, pady=(10, 10))

            sys_row = tk.Frame(frame, bg=CONTENT_BG)
            sys_row.pack(fill=tk.X, padx=24, pady=(0, 20))

            for sys_key in SYSTEM_ORDER:
                sys_color = SYSTEM_COLORS.get(sys_key, DEFAULT_SYSTEM_COLOR)
                sys_label = SYSTEM_LABELS.get(sys_key, sys_key)

                cursor.execute(
                    "SELECT COUNT(*) FROM academic_misconduct_cases WHERE system_key = ?", (sys_key,))
                sys_total = cursor.fetchone()[0]
                cursor.execute(
                    "SELECT COUNT(*) FROM academic_misconduct_cases WHERE system_key = ? AND status != 'Resolved'",
                    (sys_key,))
                sys_active = cursor.fetchone()[0]
                cursor.execute(
                    "SELECT COUNT(*) FROM academic_misconduct_cases WHERE system_key = ? AND severity = 'Critical'",
                    (sys_key,))
                sys_critical = cursor.fetchone()[0]

                card = tk.Frame(sys_row, bg=CARD_BG, relief="solid", bd=1)
                card.pack(side=tk.LEFT, padx=6, fill=tk.BOTH, expand=True)

                # Colored header
                ch = tk.Frame(card, bg=sys_color, height=35)
                ch.pack(fill=tk.X)
                ch.pack_propagate(False)
                tk.Label(ch, text=sys_label, font=("Segoe UI", 10, "bold"),
                         fg="white", bg=sys_color).pack(expand=True)

                body = tk.Frame(card, bg=CARD_BG)
                body.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

                for sl, sv in [("Total", sys_total), ("Active", sys_active), ("Critical", sys_critical)]:
                    r = tk.Frame(body, bg=CARD_BG)
                    r.pack(fill=tk.X, pady=2)
                    tk.Label(r, text=sl, font=("Segoe UI", 9), fg=TEXT_MUTED, bg=CARD_BG).pack(side=tk.LEFT)
                    val_fg = "#e74c3c" if sl == "Critical" and sv > 0 else TEXT_DARK
                    tk.Label(r, text=str(sv), font=("Segoe UI", 10, "bold"),
                             fg=val_fg, bg=CARD_BG).pack(side=tk.RIGHT)

            conn.close()

        except Exception as e:
            tk.Label(
                frame,
                text=f"Could not load misconduct data: {e}",
                font=("Segoe UI", 10),
                fg="#e74c3c",
                bg=CONTENT_BG,
            ).pack(padx=24, pady=10)

        # Launch buttons
        tk.Label(
            frame,
            text="Launch Misconduct Panel",
            font=("Segoe UI", 14, "bold"),
            bg=CONTENT_BG,
            fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(20, 10))

        btn_row = tk.Frame(frame, bg=CONTENT_BG)
        btn_row.pack(fill=tk.X, padx=24, pady=(0, 10))

        # All Systems (superadmin) button
        sa_btn = tk.Button(
            btn_row,
            text="Open All Systems View (Super Admin)",
            font=("Segoe UI", 11, "bold"),
            bg="#2c3e50",
            fg="white",
            activebackground="#34495e",
            activeforeground="white",
            relief="flat",
            cursor="hand2",
            padx=20,
            pady=10,
            command=lambda: self._open_misconduct_panel(None),
        )
        sa_btn.pack(side=tk.LEFT, padx=(0, 10))

        # Per-system launch buttons
        for sys_key in SYSTEM_ORDER:
            sys_color = SYSTEM_COLORS.get(sys_key, DEFAULT_SYSTEM_COLOR)
            sys_label = SYSTEM_LABELS.get(sys_key, sys_key)
            btn = tk.Button(
                btn_row,
                text=sys_label,
                font=("Segoe UI", 10),
                bg=sys_color,
                fg="white",
                activebackground=sys_color,
                activeforeground="white",
                relief="flat",
                cursor="hand2",
                padx=12,
                pady=8,
                command=lambda sk=sys_key: self._open_misconduct_panel(sk),
            )
            btn.pack(side=tk.LEFT, padx=4)

    def _open_misconduct_panel(self, system_key):
        """Open the Academic Misconduct Panel from superadmin dashboard."""
        try:
            from education_system.platform.governance.academic_misconduct.database import init_misconduct_tables
            from education_system.platform.governance.academic_misconduct.academic_misconduct_gui import AcademicMisconductPanel

            init_misconduct_tables()
            window = tk.Toplevel(self)
            window.geometry("1400x900")

            # Build a minimal auth-like object so the panel doesn't reject us
            class _SuperAdminAuth:
                def __init__(self, user_info):
                    self.current_user = {
                        'username': user_info.get('username', 'superadmin'),
                        'role': 'admin',
                        'display_name': user_info.get('display_name', 'Super Admin'),
                    }

            auth = _SuperAdminAuth(self.user_info)
            AcademicMisconductPanel(window, auth=auth, system_key=system_key)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open misconduct panel:\n{e}")
