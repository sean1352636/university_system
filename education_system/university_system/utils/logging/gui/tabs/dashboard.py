import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta

from education_system.university_system.utils.logging.gui.helpers import _t, STUDENT_SYSTEM_AVAILABLE


class DashboardMixin:
    """Mixin providing dashboard tab functionality."""

    def setup_dashboard_tab(self):
        """Setup the dashboard tab"""
        self.dashboard_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.dashboard_frame, text="📊 " + _t("log_management.tabs.dashboard"))

        # Title
        title_label = ttk.Label(self.dashboard_frame, text=_t("log_management.dashboard.title"),
                                font=("Arial", 16, "bold"))
        title_label.pack(pady=10)

        # Stats frame
        stats_frame = ttk.LabelFrame(self.dashboard_frame, text=_t("log_management.dashboard.quick_stats"))
        stats_frame.pack(fill=tk.X, padx=10, pady=5)

        # Create stats labels
        self.stats_labels = {}
        stats_grid = ttk.Frame(stats_frame)
        stats_grid.pack(padx=10, pady=10)

        stats_items = [
            (_t("log_management.dashboard.total_activities"), "total_activities"),
            (_t("log_management.dashboard.unique_users"), "unique_users"),
            (_t("log_management.dashboard.success_rate"), "success_rate"),
            (_t("log_management.dashboard.failed_activities"), "failed_activities"),
            (_t("log_management.dashboard.peak_hour"), "peak_hour"),
            (_t("log_management.dashboard.last_24h"), "last_24h")
        ]

        for i, (label, key) in enumerate(stats_items):
            row, col = divmod(i, 3)

            stat_frame = ttk.Frame(stats_grid)
            stat_frame.grid(row=row, column=col, padx=20, pady=5, sticky="w")

            ttk.Label(stat_frame, text=f"{label}:", font=("Arial", 10, "bold")).pack(anchor="w")
            self.stats_labels[key] = ttk.Label(stat_frame, text=_t("log_management.dashboard.loading"),
                                                font=("Arial", 12))
            self.stats_labels[key].pack(anchor="w")

        # Recent activity and controls wrapper
        content_wrapper = ttk.Frame(self.dashboard_frame)
        content_wrapper.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        content_wrapper.rowconfigure(0, weight=1)
        content_wrapper.columnconfigure(0, weight=1)

        recent_frame = ttk.LabelFrame(content_wrapper, text=_t("log_management.dashboard.recent_activity"))
        recent_frame.grid(row=0, column=0, sticky="nsew")

        # Recent activity treeview
        columns = ("Time", "User", "Action", "Module", "Status")
        column_texts = [
            _t("log_management.dashboard.columns.time"),
            _t("log_management.dashboard.columns.user"),
            _t("log_management.dashboard.columns.action"),
            _t("log_management.dashboard.columns.module"),
            _t("log_management.dashboard.columns.status")
        ]
        self.recent_tree = ttk.Treeview(recent_frame, columns=columns, show="headings", height=15)

        for col, col_text in zip(columns, column_texts):
            self.recent_tree.heading(col, text=col_text)
            self.recent_tree.column(col, width=120)

        if STUDENT_SYSTEM_AVAILABLE:
            self.create_student_integration_tab()

        # Scrollbars
        recent_v_scroll = ttk.Scrollbar(recent_frame, orient=tk.VERTICAL,
                                       command=self.recent_tree.yview)
        recent_h_scroll = ttk.Scrollbar(recent_frame, orient=tk.HORIZONTAL,
                                       command=self.recent_tree.xview)
        self.recent_tree.configure(yscrollcommand=recent_v_scroll.set,
                                  xscrollcommand=recent_h_scroll.set)

        # Pack treeview and scrollbars
        self.recent_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        recent_v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        recent_h_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        # Refresh / navigation buttons
        refresh_container = ttk.Frame(content_wrapper)
        refresh_container.grid(row=1, column=0, sticky="w", pady=8)

        ttk.Button(
            refresh_container,
            text="🔄 " + _t("log_management.dashboard.refresh"),
            command=self.update_dashboard
        ).pack(side=tk.LEFT, padx=(0, 6))

        ttk.Button(
            refresh_container,
            text="🏠 " + _t("log_management.return_to_homescreen"),
            command=self.return_to_main_menu
        ).pack(side=tk.LEFT)

    def update_dashboard(self):
        """Update dashboard with current statistics"""
        if not self.log_manager:
            self.update_status(_t("log_management.messages.log_manager_not_available"))
            return

        self.update_status(_t("log_management.messages.updating_dashboard"))

        try:
            # Get summary data
            summary = self.log_manager.analytics.generate_activity_summary(7)

            if "error" not in summary:
                # Update stats labels
                self.stats_labels["total_activities"].config(text=f"{summary['total_activities']:,}")
                self.stats_labels["unique_users"].config(text=str(summary['unique_users']))
                self.stats_labels["success_rate"].config(text=f"{summary['success_rate']:.1f}%")
                self.stats_labels["failed_activities"].config(text=str(summary['failed_activities']))
                self.stats_labels["peak_hour"].config(text=f"{summary['peak_activity_hour']}:00")

                # Get last 24h count
                filters_24h = {
                    'date_from': (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d')
                }
                recent_results = self.log_manager.db.search_logs(filters_24h, limit=10000)
                recent_count = len(recent_results) if recent_results else 0
                self.stats_labels["last_24h"].config(text=str(recent_count))

            # Update recent activity
            self.update_recent_activity()

            self.update_status(_t("log_management.messages.dashboard_updated"))

        except Exception as e:
            self.update_status(_t("log_management.errors.update_dashboard", error=str(e)))

    def update_recent_activity(self):
        """Update recent activity display"""
        if not self.log_manager:
            return

        try:
            # Clear existing items
            for item in self.recent_tree.get_children():
                self.recent_tree.delete(item)

            # Get recent logs
            filters = {
                'date_from': (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d')
            }
            recent_logs = self.log_manager.db.search_logs(filters, limit=50)

            # Add to tree
            if recent_logs:
                for log in recent_logs:
                    timestamp = log.get('timestamp', '')[:19]
                    user = log.get('username', '')
                    action = log.get('action', '')
                    module = log.get('module', '')
                    status = log.get('status', '')

                    # Add status icon
                    status_display = f"✅ {status}" if status == "success" else f"❌ {status}"

                    self.recent_tree.insert("", 0, values=(timestamp, user, action, module, status_display))

        except Exception as e:
            print(f"Error updating recent activity: {e}")

    def view_log_details(self, event):
        """View detailed log information"""
        from tkinter import scrolledtext, messagebox

        selection = self.search_tree.selection()
        if not selection:
            return

        item = self.search_tree.item(selection[0])
        values = item['values']

        if not values:
            return

        # Create details window
        details_window = tk.Toplevel(self.root)
        details_window.title(_t("log_management.dialogs.log_details.title"))
        details_window.geometry("600x400")

        # Get full log data
        try:
            details_text = scrolledtext.ScrolledText(details_window, wrap=tk.WORD)
            details_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            details_content = f"""Log Entry Details
====================

ID: {values[0]}
Timestamp: {values[1]}
User: {values[2]}
Action: {values[3]}
Module: {values[4]}
Status: {values[5]}
Details: {values[6]}

This is a simplified view. In a full implementation,
you would display all available log fields including
IP address, user agent, session ID, etc.
"""

            details_text.insert("1.0", details_content)
            details_text.config(state=tk.DISABLED)

        except Exception as e:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.errors.view_details", error=str(e)))
