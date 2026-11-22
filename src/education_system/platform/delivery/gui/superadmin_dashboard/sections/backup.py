"""Backup & Restore section and health alerts.

Split out of the former single-file ``superadmin_dashboard.py``; methods are
mixed into :class:`education_system.platform.delivery.gui.superadmin_dashboard.app.SuperAdminDashboard`.
"""

import tkinter as tk
from datetime import datetime
from tkinter import messagebox

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


class BackupMixin:
    # ------------------------------------------------------------------
    # Section: Backup / Restore (Feature 6)
    # ------------------------------------------------------------------

    def _build_backup(self):
        _, frame = self._make_scrollable(self._content_frame)

        tk.Label(
            frame, text="Backup / Restore",
            font=("Segoe UI", 18, "bold"), bg=CONTENT_BG, fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(20, 4))

        tk.Label(
            frame,
            text="Create timestamped backups of system databases.",
            font=("Segoe UI", 10), bg=CONTENT_BG, fg=TEXT_MUTED,
        ).pack(anchor=tk.W, padx=24, pady=(0, 16))

        # Alert thresholds (Feature 7)
        tk.Label(
            frame, text="Health Alert Thresholds",
            font=("Segoe UI", 13, "bold"), bg=CONTENT_BG, fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(0, 6))

        threshold_frame = tk.Frame(frame, bg=CARD_BG, relief=tk.RAISED, bd=1)
        threshold_frame.pack(fill=tk.X, padx=24, pady=(0, 16))

        self._alert_thresholds = getattr(self, "_alert_thresholds", {
            "max_db_size_mb": 500,
            "min_active_students": 1,
        })

        for i, (key, label, default) in enumerate([
            ("max_db_size_mb", "Max DB Size (MB)", 500),
            ("min_active_students", "Min Active Students", 1),
        ]):
            row = tk.Frame(threshold_frame, bg=CARD_BG)
            row.pack(fill=tk.X, padx=12, pady=4)
            tk.Label(
                row, text=label + ":", font=("Segoe UI", 10), bg=CARD_BG, fg=TEXT_DARK, width=22, anchor=tk.W,
            ).pack(side=tk.LEFT)
            var = tk.StringVar(value=str(self._alert_thresholds.get(key, default)))
            ent = tk.Entry(row, textvariable=var, font=("Segoe UI", 10), width=10)
            ent.pack(side=tk.LEFT, padx=4)
            ent._threshold_key = key
            ent._threshold_var = var

        def _save_thresholds():
            for child in threshold_frame.winfo_children():
                for ent in child.winfo_children():
                    if hasattr(ent, "_threshold_key"):
                        try:
                            self._alert_thresholds[ent._threshold_key] = int(ent._threshold_var.get())
                        except ValueError:
                            pass
            messagebox.showinfo("Saved", "Alert thresholds updated.")
            self._check_health_alerts(frame)

        tk.Button(
            threshold_frame, text="Save Thresholds", font=("Segoe UI", 9),
            bg="#2980b9", fg=TEXT_LIGHT, relief=tk.FLAT, cursor="hand2", padx=10,
            command=_save_thresholds,
        ).pack(padx=12, pady=8, anchor=tk.W)

        # Alert display area
        self._alerts_frame = tk.Frame(frame, bg=CONTENT_BG)
        self._alerts_frame.pack(fill=tk.X, padx=24, pady=(0, 12))
        self._check_health_alerts(frame)

        # Backup buttons per system
        tk.Label(
            frame, text="Database Backups",
            font=("Segoe UI", 13, "bold"), bg=CONTENT_BG, fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(4, 6))

        for sys_key in SYSTEM_ORDER:
            sys_label = SYSTEM_LABELS.get(sys_key, sys_key)
            color = SYSTEM_COLORS.get(sys_key, DEFAULT_SYSTEM_COLOR)

            card = tk.Frame(frame, bg=CARD_BG, relief=tk.RAISED, bd=1)
            card.pack(fill=tk.X, padx=24, pady=4)

            accent = tk.Frame(card, bg=color, width=6)
            accent.pack(side=tk.LEFT, fill=tk.Y)

            body = tk.Frame(card, bg=CARD_BG)
            body.pack(fill=tk.X, padx=12, pady=8)

            tk.Label(
                body, text=sys_label, font=("Segoe UI", 11, "bold"), bg=CARD_BG, fg=TEXT_DARK,
            ).pack(side=tk.LEFT)

            # Get DB info
            svc = self._get_admin_service()
            db_info = ""
            if svc:
                try:
                    cfg = svc.get_system_config(sys_key)
                    db_info = f"({cfg.get('db_size_mb', 0)} MB)"
                except Exception:
                    pass

            if db_info:
                tk.Label(
                    body, text=db_info, font=("Segoe UI", 9), bg=CARD_BG, fg=TEXT_MUTED,
                ).pack(side=tk.LEFT, padx=8)

            status_label = tk.Label(body, text="", font=("Segoe UI", 9), bg=CARD_BG, fg="#27ae60")
            status_label.pack(side=tk.RIGHT)

            def _make_backup(sk=sys_key, sl=status_label):
                svc2 = self._get_admin_service()
                if not svc2:
                    return
                try:
                    backup_path = svc2.backup_database(sk)
                    sl.config(text=f"Backed up: {backup_path.split('/')[-1]}", fg="#27ae60")
                except Exception as exc:
                    sl.config(text=f"Error: {exc}", fg="#e74c3c")

            tk.Button(
                body, text="Backup Now", font=("Segoe UI", 9), bg="#27ae60", fg=TEXT_LIGHT,
                relief=tk.FLAT, cursor="hand2", padx=10, command=_make_backup,
            ).pack(side=tk.RIGHT, padx=(0, 8))

        # Auth DB backup
        card = tk.Frame(frame, bg=CARD_BG, relief=tk.RAISED, bd=1)
        card.pack(fill=tk.X, padx=24, pady=4)
        accent = tk.Frame(card, bg="#e74c3c", width=6)
        accent.pack(side=tk.LEFT, fill=tk.Y)
        body = tk.Frame(card, bg=CARD_BG)
        body.pack(fill=tk.X, padx=12, pady=8)
        tk.Label(body, text="Shared Auth Database", font=("Segoe UI", 11, "bold"), bg=CARD_BG, fg=TEXT_DARK).pack(
            side=tk.LEFT
        )
        auth_status = tk.Label(body, text="", font=("Segoe UI", 9), bg=CARD_BG, fg="#27ae60")
        auth_status.pack(side=tk.RIGHT)

        def _backup_auth():
            import shutil
            from pathlib import Path
            auth_path = Path(self._auth_db_path) if self._auth_db_path else None
            if not auth_path:
                try:
                    from education_system.platform.delivery.portals.admin.admin_service import _auth_db_path
                    auth_path = _auth_db_path()
                except Exception:
                    auth_status.config(text="Auth DB path unknown", fg="#e74c3c")
                    return
            if not auth_path.exists():
                auth_status.config(text="Auth DB not found", fg="#e74c3c")
                return
            backup = str(auth_path) + f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(str(auth_path), backup)
            auth_status.config(text=f"Backed up: {backup.split('/')[-1]}", fg="#27ae60")

        tk.Button(
            body, text="Backup Now", font=("Segoe UI", 9), bg="#e74c3c", fg=TEXT_LIGHT,
            relief=tk.FLAT, cursor="hand2", padx=10, command=_backup_auth,
        ).pack(side=tk.RIGHT, padx=(0, 8))

    def _check_health_alerts(self, parent_frame=None):
        """Check current health data against thresholds and show alerts."""
        alerts_frame = getattr(self, "_alerts_frame", None)
        if not alerts_frame:
            return
        for w in alerts_frame.winfo_children():
            w.destroy()

        thresholds = getattr(self, "_alert_thresholds", {})
        max_db = thresholds.get("max_db_size_mb", 500)
        min_students = thresholds.get("min_active_students", 1)

        svc = self._get_admin_service()
        if not svc:
            return

        alerts = []
        try:
            health = svc.get_system_health()
            for h in health:
                if h.get("db_size_mb", 0) > max_db:
                    alerts.append(
                        f"WARNING: {h['label']} DB size ({h['db_size_mb']} MB) exceeds threshold ({max_db} MB)"
                    )
                if h.get("student_count", 0) < min_students and h.get("db_exists"):
                    alerts.append(
                        f"WARNING: {h['label']} has only {h['student_count']} student(s) "
                        f"(threshold: {min_students})"
                    )
                if h.get("status") == "error":
                    alerts.append(f"ERROR: {h['label']} database has errors")
        except Exception:
            pass

        if alerts:
            for alert in alerts:
                color = "#e74c3c" if "ERROR" in alert else "#e67e22"
                tk.Label(
                    alerts_frame, text=alert, font=("Segoe UI", 9, "bold"),
                    bg=CONTENT_BG, fg=color, anchor=tk.W,
                ).pack(fill=tk.X, pady=1)
        else:
            tk.Label(
                alerts_frame, text="All systems within normal thresholds.",
                font=("Segoe UI", 9), bg=CONTENT_BG, fg="#27ae60",
            ).pack(anchor=tk.W)
