"""Admin role-based dashboard tab."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

import tkinter as tk
from tkinter import ttk
import logging

logger = logging.getLogger(__name__)


def create_admin_dashboard(parent_frame, auth, service):
    """Create the admin-specific dashboard content.

    Args:
        parent_frame: The ttk.Frame to populate.
        auth: Auth manager instance.
        service: DashboardService instance.
    """
    data = service.get_admin_dashboard_data()
    username = auth.current_user.get('username', 'Admin') if auth.current_user else 'Admin'

    canvas = tk.Canvas(parent_frame)
    scrollbar = ttk.Scrollbar(parent_frame, orient=tk.VERTICAL, command=canvas.yview)
    scrollable = ttk.Frame(canvas)

    scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas_window = canvas.create_window((0, 0), window=scrollable, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    # Bind canvas resize to stretch scrollable frame to full width
    canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))

    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Welcome
    ttk.Label(scrollable, text=f"Admin Dashboard - {username}",
              font=('Arial', 14, 'bold')).pack(anchor="w", padx=15, pady=(15, 5))

    # Summary Cards
    summary_frame = ttk.LabelFrame(scrollable, text=_t('gui.shell.main.dashboard.admin_dashboard.labels.system_overview', default="System Overview"), padding="10")
    summary_frame.pack(fill=tk.X, padx=15, pady=5)

    cards_frame = ttk.Frame(summary_frame)
    cards_frame.pack(fill=tk.X)
    for i in range(4):
        cards_frame.columnconfigure(i, weight=1)

    _create_stat_card(cards_frame, "Students", str(data['total_students']), 0, 0)
    _create_stat_card(cards_frame, "Instructors", str(data['total_instructors']), 0, 1)
    _create_stat_card(cards_frame, "Courses", str(data['total_courses']), 0, 2)
    _create_stat_card(cards_frame, "Enrollments", str(data['total_active_enrollments']), 0, 3)

    # System Stats
    stats_frame = ttk.LabelFrame(scrollable, text=_t('gui.shell.main.dashboard.admin_dashboard.labels.system_statistics', default="System Statistics"), padding="10")
    stats_frame.pack(fill=tk.X, padx=15, pady=5)

    total_users = data.get('system_stats', {}).get('total_users', 'N/A')
    ttk.Label(stats_frame, text=f"Total Users: {total_users}").pack(anchor="w")

    total_payments = data.get('financial_summary', {}).get('total_payments', 0)
    if isinstance(total_payments, (int, float)):
        ttk.Label(stats_frame, text=f"Total Payments Received: £{total_payments:,.2f}").pack(anchor="w")
    else:
        ttk.Label(stats_frame, text=f"Total Payments Received: £{0:,.2f}").pack(anchor="w")

    # Recent Registrations
    reg_frame = ttk.LabelFrame(scrollable, text=_t('gui.shell.main.dashboard.admin_dashboard.labels.recent_student_registrations_last_7_days', default="Recent Student Registrations (Last 7 Days)"), padding="10")
    reg_frame.pack(fill=tk.X, padx=15, pady=5)

    if data['recent_registrations']:
        cols = ('student_id', 'name', 'date')
        tree = ttk.Treeview(reg_frame, columns=cols, show='headings',
                            height=min(8, len(data['recent_registrations'])))
        tree.heading('student_id', text=_t('gui.shell.main.dashboard.admin_dashboard.headings.student_id', default='Student ID'))
        tree.heading('name', text=_t('gui.shell.main.dashboard.admin_dashboard.headings.name', default='Name'))
        tree.heading('date', text=_t('gui.shell.main.dashboard.admin_dashboard.headings.registered', default='Registered'))
        tree.column('student_id', width=120)
        tree.column('name', width=250)
        tree.column('date', width=150)
        for r in data['recent_registrations']:
            tree.insert('', tk.END, values=(
                r.get('student_id', ''),
                r.get('name', ''),
                r.get('created_at', '')
            ))
        tree.pack(fill=tk.X)
    else:
        ttk.Label(reg_frame, text=_t('gui.shell.main.dashboard.admin_dashboard.labels.no_recent_registrations', default="No recent registrations.")).pack(anchor="w")

    # Admin Tools - quick access to admin-only GUIs
    tools_frame = ttk.LabelFrame(scrollable, text=_t('gui.shell.main.dashboard.admin_dashboard.labels.admin_tools', default="Admin Tools"), padding="10")
    tools_frame.pack(fill=tk.X, padx=15, pady=5)

    tools_grid = ttk.Frame(tools_frame)
    tools_grid.pack(fill=tk.X)
    for i in range(3):
        tools_grid.columnconfigure(i, weight=1)

    def _open_alert_config():
        try:
            from education_system.systems.university.shell.gui.admin.alert_config_gui import AlertConfigConsole
            root = parent_frame.winfo_toplevel()
            AlertConfigConsole(root)
        except Exception as e:
            logger.warning(f"Could not open Alert Config: {e}")

    def _open_dept_management():
        try:
            from education_system.systems.university.shell.gui.admin.department_management_gui import DepartmentManagementGUI
            root = parent_frame.winfo_toplevel()
            DepartmentManagementGUI(root)
        except Exception as e:
            logger.warning(f"Could not open Department Management: {e}")

    # "Branding & Customization" used to sit at row 0, column 2. It now lives
    # in the dashboard title row next to "Close extra tabs".
    ttk.Button(tools_grid, text=_t('gui.shell.main.dashboard.admin_dashboard.buttons.alert_notifications', default="Alert & Notifications"),
               command=_open_alert_config).grid(row=0, column=0, padx=5, pady=5, sticky="ew")
    ttk.Button(tools_grid, text=_t('gui.shell.main.dashboard.admin_dashboard.buttons.department_management', default="Department Management"),
               command=_open_dept_management).grid(row=0, column=1, padx=5, pady=5, sticky="ew")

    from education_system.systems.university.shell.gui.main.dashboard.evaluation_launchers import (
        EVALUATION_MODULES, launch_evaluation_module,
    )
    root = parent_frame.winfo_toplevel()
    for i, (_label, _module) in enumerate(EVALUATION_MODULES):
        ttk.Button(
            tools_grid, text=_label,
            command=lambda m=_module, l=_label: launch_evaluation_module(root, auth, m, l),
        ).grid(row=1, column=i, padx=5, pady=5, sticky="ew")


def _create_stat_card(parent, label, value, row, col):
    """Create a small stat card widget."""
    frame = ttk.Frame(parent, relief="groove", borderwidth=1)
    frame.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
    ttk.Label(frame, text=value, font=('Arial', 18, 'bold')).pack(pady=(8, 2))
    ttk.Label(frame, text=label, font=('Arial', 9)).pack(pady=(0, 8))
