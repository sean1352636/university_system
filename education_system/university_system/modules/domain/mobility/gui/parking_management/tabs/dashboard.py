"""Dashboard tab mixin for ParkingManagementGUI."""
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText

from .. import get_connection, _t


class DashboardMixin:
    """Mixin providing dashboard tab functionality."""

    def setup_dashboard_tab(self):
        """Setup the dashboard tab"""
        # Create main dashboard frame
        dashboard_main = ttk.Frame(self.dashboard_frame)
        dashboard_main.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Title
        title_label = ttk.Label(dashboard_main, text=_t("parking.dashboard.title"),
                               font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 20))

        # Create stats frame
        stats_frame = ttk.LabelFrame(dashboard_main, text=_t("parking.dashboard.title"))
        stats_frame.pack(fill=tk.X, pady=(0, 20))

        # Stats grid
        stats_grid = ttk.Frame(stats_frame)
        stats_grid.pack(fill=tk.X, padx=10, pady=10)

        # Create stat labels
        self.stats_labels = {}
        stats = [
            (_t("parking.dashboard.active_permits"), "active_permits"),
            (_t("parking.dashboard.total_vehicles"), "total_vehicles"),
            (_t("parking.dashboard.unpaid_violations"), "unpaid_violations"),
            (_t("parking.dashboard.available_spaces"), "available_spaces")
        ]

        for i, (label, key) in enumerate(stats):
            row, col = i // 2, i % 2

            stat_frame = ttk.Frame(stats_grid)
            stat_frame.grid(row=row, column=col, padx=20, pady=10, sticky="w")

            ttk.Label(stat_frame, text=label + ":", font=("Arial", 10, "bold")).pack()
            self.stats_labels[key] = ttk.Label(stat_frame, text="Loading...",
                                             font=("Arial", 12))
            self.stats_labels[key].pack()

        # Recent activity frame
        activity_frame = ttk.LabelFrame(dashboard_main, text=_t("parking.dashboard.recent_activity"))
        activity_frame.pack(fill=tk.BOTH, expand=True)

        self.activity_text = ScrolledText(activity_frame, height=10, state=tk.DISABLED)
        self.activity_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Refresh dashboard
        self.refresh_dashboard()

    def refresh_dashboard(self):
        """Refresh dashboard statistics"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get statistics
            cursor.execute("SELECT COUNT(*) FROM parking_permits WHERE active_status = 'Active'")
            active_permits = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM vehicles")
            total_vehicles = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM parking_violations WHERE payment_status = 'Unpaid'")
            unpaid_violations = cursor.fetchone()[0]

            cursor.execute("SELECT SUM(available_spaces) FROM parking_lots")
            available_spaces = cursor.fetchone()[0] or 0

            # Update stats labels
            self.stats_labels["active_permits"].config(text=str(active_permits))
            self.stats_labels["total_vehicles"].config(text=str(total_vehicles))
            self.stats_labels["unpaid_violations"].config(text=str(unpaid_violations))
            self.stats_labels["available_spaces"].config(text=str(available_spaces))

            # Get recent activity
            cursor.execute('''
            SELECT 'Permit' as type, permit_id as id, issue_date as date, full_name as details
            FROM parking_permits
            WHERE date(issue_date) >= date('now', '-7 days')
            UNION ALL
            SELECT 'Violation' as type, violation_id as id, violation_date as date,
                   violation_type || ' - ' || license_plate as details
            FROM parking_violations
            WHERE date(violation_date) >= date('now', '-7 days')
            ORDER BY date DESC
            LIMIT 20
            ''')

            activities = cursor.fetchall()

            # Update activity text
            self.activity_text.config(state=tk.NORMAL)
            self.activity_text.delete(1.0, tk.END)

            if activities:
                for activity in activities:
                    self.activity_text.insert(tk.END,
                        f"{activity[1]} - {activity[0]} - {activity[3]} ({activity[2]})\n")
            else:
                self.activity_text.insert(tk.END, "No recent activity")

            self.activity_text.config(state=tk.DISABLED)
            conn.close()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh dashboard: {e}")
