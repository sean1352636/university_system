import tkinter as tk
from tkinter import ttk, messagebox

from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH
from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.utils.logging.gui.helpers import _t


class AlertsMixin:
    """Mixin providing alerts tab functionality."""

    def setup_alerts_tab(self):
        """Setup the alerts tab"""
        self.alerts_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.alerts_frame, text="🚨 " + _t("log_management.tabs.alerts"))

        # Alert controls
        controls_frame = ttk.LabelFrame(self.alerts_frame, text=_t("log_management.alerts.title"))
        controls_frame.pack(fill=tk.X, padx=10, pady=5)

        button_frame = ttk.Frame(controls_frame)
        button_frame.pack(padx=10, pady=10)

        ttk.Button(button_frame, text="🔍 " + _t("log_management.alerts.buttons.check_alerts"),
                  command=self.check_alerts).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="🔄 " + _t("log_management.alerts.buttons.refresh"),
                  command=self.refresh_alerts).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="✅ " + _t("log_management.alerts.buttons.mark_all_read"),
                  command=self.mark_alerts_read).pack(side=tk.LEFT)

        # Alerts display
        alerts_display_frame = ttk.LabelFrame(self.alerts_frame, text=_t("log_management.alerts.recent_alerts"))
        alerts_display_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Alerts treeview
        alert_columns = ("Time", "Type", "Severity", "Message", "Status")
        alert_column_texts = [
            _t("log_management.alerts.columns.time"),
            _t("log_management.alerts.columns.type"),
            _t("log_management.alerts.columns.severity"),
            _t("log_management.alerts.columns.message"),
            _t("log_management.alerts.columns.status")
        ]
        self.alerts_tree = ttk.Treeview(alerts_display_frame, columns=alert_columns, show="headings")

        for col, col_text in zip(alert_columns, alert_column_texts):
            self.alerts_tree.heading(col, text=col_text)
            self.alerts_tree.column(col, width=120)

        # Alerts scrollbar
        alerts_scroll = ttk.Scrollbar(alerts_display_frame, orient=tk.VERTICAL,
                                     command=self.alerts_tree.yview)
        self.alerts_tree.configure(yscrollcommand=alerts_scroll.set)

        self.alerts_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        alerts_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Load alerts on startup
        self.refresh_alerts()

    def check_alerts(self):
        """Check for alerts"""
        if not self.log_manager:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.messages.log_manager_not_available"))
            return

        self.update_status(_t("log_management.messages.checking_alerts"))

        try:
            alerts = self.log_manager.alerts.run_alert_checks()

            if not alerts:
                messagebox.showinfo(_t("log_management.alerts.title"), _t("log_management.messages.no_alerts"))
            else:
                messagebox.showinfo(_t("log_management.alerts.title"), _t("log_management.messages.alerts_found", count=len(alerts)))

            self.refresh_alerts()
            self.update_status(_t("log_management.alerts.alerts_checked"))

        except Exception as e:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.errors.alerts", error=str(e)))
            self.update_status(_t("log_management.messages.alert_check_failed"))

    def refresh_alerts(self):
        """Refresh alerts display"""
        if not self.log_manager:
            return

        try:
            # Clear existing alerts
            for item in self.alerts_tree.get_children():
                self.alerts_tree.delete(item)

            # Get recent alerts from database
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT * FROM alerts
                    WHERE triggered_at > datetime('now', '-24 hours')
                    ORDER BY triggered_at DESC
                    LIMIT 50
                ''')

                alerts = cursor.fetchall()
            finally:
                conn.close()

            # Add alerts to tree
            for alert in alerts:
                time_str = alert['triggered_at'][:19]
                alert_type = alert['alert_type']
                severity = alert['severity']
                message = alert['message']
                status = _t("log_management.alert_status.resolved") if alert['resolved'] else _t("log_management.alert_status.active")

                # Add severity icon
                severity_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(severity, "⚪")
                severity_display = f"{severity_icon} {severity}"

                self.alerts_tree.insert("", "end", values=(
                    time_str, alert_type, severity_display, message, status
                ))

        except Exception as e:
            print(f"Error refreshing alerts: {e}")

    def mark_alerts_read(self):
        """Mark all alerts as read/resolved"""
        if not self.log_manager:
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
                UPDATE alerts
                SET resolved = TRUE, resolved_at = CURRENT_TIMESTAMP
                WHERE resolved = FALSE
            ''')

            updated_count = cursor.rowcount
            conn.commit()
            conn.close()

            messagebox.showinfo(_t("log_management.messages.success"), _t("log_management.messages.alerts_marked_read", count=updated_count))
            self.refresh_alerts()

        except Exception as e:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.errors.mark_alerts", error=str(e)))
