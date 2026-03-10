"""
Dashboard management for housing accommodation system.
Displays overview statistics and quick access to key metrics.
"""

import tkinter as tk
from tkinter import ttk
from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.shared.utils.i18n import get_text as _t


def show_dashboard(content_frame):
    """
    Show the main dashboard with statistics and overview.

    Args:
        content_frame: The parent frame to display dashboard in
    """
    # Clear content frame
    for widget in content_frame.winfo_children():
        widget.destroy()

    # Dashboard title
    ttk.Label(content_frame, text=_t("housing.dashboard_title"),
             font=('Arial', 16, 'bold')).grid(row=0, column=0, pady=(0, 20), sticky='w')

    # Create notebook for tabs
    notebook = ttk.Notebook(content_frame)
    notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 20))

    # Overview tab
    overview_frame = ttk.Frame(notebook, padding="20")
    notebook.add(overview_frame, text=_t("housing.tab_overview"))

    # Quick stats frame
    stats_frame = ttk.LabelFrame(overview_frame, text=_t("housing.quick_stats"), padding="10")
    stats_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 20))

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get statistics
        cursor.execute('SELECT COUNT(*) FROM housing_buildings')
        total_buildings = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM housing_rooms')
        total_rooms = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM housing_rooms WHERE status = "Occupied"')
        occupied_rooms = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM housing_assignments WHERE status = "Active"')
        active_assignments = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM housing_applications WHERE status = "Pending"')
        pending_applications = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM housing_maintenance_requests WHERE status != "Complete"')
        open_maintenance = cursor.fetchone()[0]

        occupancy_rate = (occupied_rooms / total_rooms * 100) if total_rooms > 0 else 0

        conn.close()

        # Display stats in grid
        stats = [
            ("Total Buildings", total_buildings),
            ("Total Rooms", total_rooms),
            ("Occupied Rooms", occupied_rooms),
            ("Occupancy Rate", f"{occupancy_rate:.1f}%"),
            ("Active Assignments", active_assignments),
            ("Pending Applications", pending_applications),
            ("Open Maintenance", open_maintenance)
        ]

        for i, (label, value) in enumerate(stats):
            row = i // 3
            col = i % 3
            stat_frame = ttk.Frame(stats_frame)
            stat_frame.grid(row=row, column=col, padx=20, pady=10)

            ttk.Label(stat_frame, text=str(value), font=('Arial', 20, 'bold')).pack()
            ttk.Label(stat_frame, text=label).pack()

    except Exception as e:
        ttk.Label(stats_frame, text=f"Error loading statistics: {str(e)}",
                 foreground='red').pack()

    # Recent activity frame (placeholder)
    activity_frame = ttk.LabelFrame(overview_frame, text="Recent Activity", padding="10")
    activity_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))

    ttk.Label(activity_frame, text="Recent activity will be displayed here").pack()
