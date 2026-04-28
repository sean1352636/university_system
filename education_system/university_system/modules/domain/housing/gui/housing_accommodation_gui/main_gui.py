"""
Main GUI module for Housing Accommodation Management System.
This module provides the main HousingGUI class that orchestrates all manager modules.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import os

# Core imports
from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.infrastructure.shared_context import get_auth
from education_system.university_system.modules.shared.utils.simple_activity_logger import (
    log_activity, log_create, log_read, log_update, log_delete
)
from education_system.university_system.modules.shared.constants import paths

# Import immutable audit logging for compliance
try:
    from education_system.university_system.infrastructure.security.audit_helpers import (
        safe_log_security_event,
        get_gui_context,
    )
    from education_system.university_system.infrastructure.security.immutable_audit_log import AuditAction
    IMMUTABLE_AUDIT_AVAILABLE = True
except ImportError:
    IMMUTABLE_AUDIT_AVAILABLE = False

# Import i18n for multi-language support
from education_system.university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from education_system.university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector

# Import all manager modules
from education_system.university_system.modules.domain.housing.gui.housing_accommodation_gui import (
    dashboard_manager,
    building_manager,
    room_manager,
    application_manager,
    assignment_manager,
    maintenance_manager,
    payment_manager,
    refund_manager,
    inventory_manager,
    inspection_manager,
    report_manager,
    export_manager,
    scheduled_reports,
    finance_integration,
)

# Import housing services
from education_system.university_system.modules.domain.housing.services.housing_accommodation import (
    init_housing_db, generate_id, set_auth,
    display_housing_accommodation_menu as orig_display_housing_accommodation_menu,
)


class HousingGUI:
    """Main GUI class for Housing Accommodation Management System."""

    def __init__(self, parent=None, auth_instance=None):
        """Initialize the Housing GUI.

        Args:
            parent: Optional existing Toplevel/Tk to render into. If omitted,
                a new ``tk.Tk()`` is created (standalone mode).
            auth_instance: Authentication instance.
        """
        self.auth = auth_instance
        self.root = parent if parent is not None else tk.Tk()

        # Initialize i18n for multi-language support
        init_i18n()

        self.root.title(_t("housing.window_title"))
        self.root.geometry("1400x900")
        self.root.configure(bg='#f0f0f0')

        # Set the auth instance for backward compatibility
        if auth_instance:
            set_auth(auth_instance)

        # Initialize database
        init_housing_db()

        # Create main interface
        self.create_main_interface()

    def create_main_interface(self):
        """Create the main GUI interface."""
        # Clear any existing widgets
        for widget in self.root.winfo_children():
            widget.destroy()

        # Toolbar with quick actions
        toolbar = ttk.Frame(self.root, padding="6 6 6 6")
        toolbar.grid(row=0, column=0, sticky='ew')
        ttk.Button(toolbar, text=_t("housing.return_to_main"), command=self.return_to_main_menu).pack(side=tk.LEFT)

        # Language button
        self.lang_btn = ttk.Button(
            toolbar,
            text=f"{_t('menu.language')}: {get_current_language_name()}",
            command=self.change_language
        )
        self.lang_btn.pack(side=tk.RIGHT, padx=5)

        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=0)
        self.root.rowconfigure(1, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(0, weight=1)

        # Title
        title_label = ttk.Label(main_frame, text=_t("housing.main_title"),
                               font=('Arial', 18, 'bold'))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))

        # Left sidebar with menu buttons
        sidebar_frame = ttk.Frame(main_frame)
        sidebar_frame.grid(row=1, column=0, sticky=(tk.W, tk.N, tk.S), padx=(0, 20))

        # Main content area
        self.content_frame = ttk.Frame(main_frame)
        self.content_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.content_frame.columnconfigure(0, weight=1)
        self.content_frame.rowconfigure(0, weight=1)

        # Create menu buttons based on permissions
        self.create_menu_buttons(sidebar_frame)

        # Show default content
        self.show_dashboard()

    def return_to_main_menu(self):
        """Close the housing window and return control to the launcher."""
        try:
            self.root.destroy()
        except Exception:
            self.root.quit()

    def change_language(self):
        """Open language selector and refresh UI on change."""
        old_lang = get_current_language()
        show_gui_language_selector(self.root)
        new_lang = get_current_language()
        if old_lang != new_lang:
            self.refresh_ui_text()

    def refresh_ui_text(self):
        """Refresh all UI text after language change."""
        self.root.title(_t("housing.window_title"))
        self.create_main_interface()

    def create_menu_buttons(self, parent):
        """Create menu buttons based on user permissions."""
        if not self.auth or not self.auth.current_user:
            ttk.Label(parent, text=_t("housing.login_required"),
                     foreground='red').pack(pady=10)
            return

        current_role = self.auth.current_user.get('role', '')

        if self.auth.check_permission('manage_accommodations'):
            # Administrator menu
            ttk.Button(parent, text=_t("housing.menu_dashboard"), width=20,
                      command=self.show_dashboard).pack(pady=2)
            ttk.Button(parent, text=_t("housing.menu_building_mgmt"), width=20,
                      command=self.show_building_management).pack(pady=2)
            ttk.Button(parent, text=_t("housing.menu_room_mgmt"), width=20,
                      command=self.show_room_management).pack(pady=2)
            ttk.Button(parent, text=_t("housing.menu_applications"), width=20,
                      command=self.show_applications).pack(pady=2)
            ttk.Button(parent, text=_t("housing.menu_assignments"), width=20,
                      command=self.show_assignments).pack(pady=2)
            ttk.Button(parent, text=_t("housing.menu_maintenance"), width=20,
                      command=self.show_maintenance).pack(pady=2)
            ttk.Button(parent, text=_t("housing.menu_payments"), width=20,
                      command=self.show_payments).pack(pady=2)
            ttk.Button(parent, text=_t("housing.menu_inventory"), width=20,
                      command=self.show_inventory).pack(pady=2)
            ttk.Button(parent, text=_t("housing.menu_inspections"), width=20,
                      command=self.show_inspections).pack(pady=2)
            ttk.Button(parent, text=_t("housing.menu_reports"), width=20,
                      command=self.show_reports).pack(pady=2)

        elif self.auth.check_permission('view_accommodations'):
            # View-only staff menu
            ttk.Button(parent, text=_t("housing.menu_dashboard"), width=20,
                      command=self.show_dashboard).pack(pady=2)
            ttk.Button(parent, text=_t("housing.menu_view_buildings"), width=20,
                      command=self.show_building_view).pack(pady=2)
            ttk.Button(parent, text=_t("housing.menu_view_applications"), width=20,
                      command=self.show_applications_view).pack(pady=2)
            ttk.Button(parent, text=_t("housing.menu_view_assignments"), width=20,
                      command=self.show_assignments_view).pack(pady=2)
            ttk.Button(parent, text=_t("housing.menu_view_maintenance"), width=20,
                      command=self.show_maintenance_view).pack(pady=2)
            ttk.Button(parent, text=_t("housing.menu_view_payments"), width=20,
                      command=self.show_payments_view).pack(pady=2)

        elif self.auth.check_permission('view_own_record'):
            # Student menu
            ttk.Button(parent, text=_t("housing.menu_my_dashboard"), width=20,
                      command=self.show_student_dashboard).pack(pady=2)
            ttk.Button(parent, text=_t("housing.menu_my_application"), width=20,
                      command=self.show_student_application).pack(pady=2)
            ttk.Button(parent, text=_t("housing.menu_my_assignment"), width=20,
                      command=self.show_student_assignment).pack(pady=2)
            ttk.Button(parent, text=_t("housing.menu_maintenance"), width=20,
                      command=self.show_student_maintenance).pack(pady=2)
            ttk.Button(parent, text="Find a Roommate", width=20,
                      command=self.show_find_roommate).pack(pady=2)
        else:
            ttk.Label(parent, text=_t("housing.no_permissions"),
                     foreground='red').pack(pady=10)

        # Backward compatibility button
        ttk.Separator(parent).pack(fill='x', pady=10)
        ttk.Button(parent, text=_t("housing.menu_classic"), width=20,
                  command=self.launch_classic_interface).pack(pady=2)

    def clear_content(self):
        """Clear the content area."""
        for widget in self.content_frame.winfo_children():
            widget.destroy()

    # ========== Manager Function Delegations ==========

    def show_dashboard(self):
        """Show dashboard (delegates to dashboard_manager)."""
        dashboard_manager.show_dashboard(self.content_frame)

    def show_building_management(self):
        """Show building management (delegates to building_manager)."""
        building_manager.show_building_management(self)

    def show_room_management(self):
        """Show room management (delegates to room_manager)."""
        room_manager.show_general_room_management(self)

    def show_applications(self):
        """Show applications (delegates to application_manager)."""
        application_manager.show_applications(self)

    def show_assignments(self):
        """Show assignments (delegates to assignment_manager)."""
        assignment_manager.show_assignments(self)

    def show_maintenance(self):
        """Show maintenance (delegates to maintenance_manager)."""
        maintenance_manager.show_maintenance(self)

    def show_payments(self):
        """Show payments (delegates to payment_manager)."""
        payment_manager.show_payments(self)

    def show_inventory(self):
        """Show inventory (delegates to inventory_manager)."""
        inventory_manager.show_inventory(self)

    def show_inspections(self):
        """Show inspections (delegates to inspection_manager)."""
        inspection_manager.show_inspections(self)

    def show_reports(self):
        """Show reports (delegates to report_manager)."""
        report_manager.show_reports(self)

    # ========== View-Only Functions ==========

    def show_building_view(self):
        """Show building view for staff."""
        self.show_building_management()

    def show_applications_view(self):
        """Show applications view for staff."""
        self.show_applications()

    def show_assignments_view(self):
        """Show assignments view for staff."""
        self.show_assignments()

    def show_maintenance_view(self):
        """Show maintenance view for staff."""
        self.show_maintenance()

    def show_payments_view(self):
        """Show payments view for staff."""
        self.show_payments()

    # ========== Student Portal Functions ==========

    def show_student_dashboard(self):
        """Show the student-facing housing dashboard.

        Panels:
          - Current Assignment (building, room, rent, contract dates)
          - Application Status (latest housing_applications row)
          - Open Maintenance Requests
          - Quick Actions (submit maintenance, find roommate, apply)
        """
        self.clear_content()

        username = self.auth.current_user.get('username', '') if self.auth and self.auth.current_user else ''
        if not username:
            ttk.Label(self.content_frame,
                      text="No student logged in.",
                      foreground='red').pack(pady=20)
            return

        # Scrollable container so everything fits on smaller screens
        outer = ttk.Frame(self.content_frame)
        outer.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(outer, highlightthickness=0)
        vscroll = ttk.Scrollbar(outer, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=vscroll.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vscroll.pack(side=tk.RIGHT, fill='y')
        inner = ttk.Frame(canvas)
        canvas_window = canvas.create_window((0, 0), window=inner, anchor='nw')
        inner.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfig(canvas_window, width=e.width))

        ttk.Label(inner, text="My Housing",
                  font=('Arial', 18, 'bold')).pack(pady=(15, 10), padx=15, anchor='w')

        conn = get_connection()
        try:
            self._render_student_assignment_card(inner, conn, username)
            self._render_student_application_card(inner, conn, username)
            self._render_student_maintenance_card(inner, conn, username)
        finally:
            try:
                conn.close()
            except Exception:
                pass

        self._render_student_quick_actions(inner)

    def _render_student_assignment_card(self, parent, conn, student_id):
        card = ttk.LabelFrame(parent, text="Current Assignment", padding=12)
        card.pack(fill=tk.X, padx=15, pady=8)

        row = conn.execute(
            "SELECT a.assignment_id, a.room_id, a.move_in_date, "
            "a.planned_move_out_date, a.actual_move_out_date, a.contract_number, "
            "a.monthly_rent, a.status, "
            "r.room_number, r.floor_number, r.room_type, "
            "b.building_name, b.address, b.campus_location "
            "FROM housing_assignments a "
            "LEFT JOIN housing_rooms r ON a.room_id = r.room_id "
            "LEFT JOIN housing_buildings b ON r.building_id = b.building_id "
            "WHERE a.student_id = ? "
            "ORDER BY CASE WHEN a.status = 'Active' THEN 0 ELSE 1 END, "
            "a.move_in_date DESC LIMIT 1",
            (student_id,),
        ).fetchone()

        if row is None:
            ttk.Label(card, text="You have no current housing assignment.",
                      foreground='#888').pack(anchor='w')
            return

        building = row['building_name'] or '—'
        room = f"Room {row['room_number']}" if row['room_number'] else '—'
        floor = f"Floor {row['floor_number']}" if row['floor_number'] is not None else '—'
        rent = f"£{row['monthly_rent']:,.2f}/mo" if row['monthly_rent'] else '—'
        rows = [
            ("Building", building),
            ("Room", room),
            ("Floor", floor),
            ("Room type", row['room_type'] or '—'),
            ("Address", row['address'] or '—'),
            ("Move-in", row['move_in_date'] or '—'),
            ("Planned move-out", row['planned_move_out_date'] or '—'),
            ("Actual move-out", row['actual_move_out_date'] or '—'),
            ("Monthly rent", rent),
            ("Contract #", row['contract_number'] or '—'),
            ("Status", row['status'] or '—'),
        ]
        grid = ttk.Frame(card)
        grid.pack(fill=tk.X)
        for i, (label, value) in enumerate(rows):
            ttk.Label(grid, text=f"{label}:", font=('Arial', 10, 'bold')).grid(
                row=i // 2, column=(i % 2) * 2, sticky='w', padx=(0, 8), pady=2)
            ttk.Label(grid, text=str(value)).grid(
                row=i // 2, column=(i % 2) * 2 + 1, sticky='w', padx=(0, 20), pady=2)

    def _render_student_application_card(self, parent, conn, student_id):
        card = ttk.LabelFrame(parent, text="Application Status", padding=12)
        card.pack(fill=tk.X, padx=15, pady=8)

        row = conn.execute(
            "SELECT application_id, application_date, preferred_building_id, "
            "preferred_room_type, requested_move_in_date, "
            "requested_duration_months, status, notes, review_date "
            "FROM housing_applications "
            "WHERE student_id = ? "
            "ORDER BY application_date DESC LIMIT 1",
            (student_id,),
        ).fetchone()

        if row is None:
            ttk.Label(card, text="You have no housing application on file.",
                      foreground='#888').pack(anchor='w')
            ttk.Button(card, text="Apply for Housing",
                       command=self.show_student_application).pack(anchor='w', pady=(8, 0))
            return

        status = (row['status'] or '').lower()
        status_colors = {'approved': '#27ae60', 'pending': '#f39c12',
                         'rejected': '#c0392b', 'cancelled': '#7f8c8d'}
        status_color = status_colors.get(status, '#2c3e50')

        ttk.Label(card, text=f"Application {row['application_id']}",
                  font=('Arial', 10, 'bold')).grid(row=0, column=0, columnspan=2, sticky='w')
        ttk.Label(card, text=f"Status: {row['status'] or '—'}",
                  foreground=status_color,
                  font=('Arial', 11, 'bold')).grid(row=1, column=0, columnspan=2, sticky='w', pady=(2, 8))

        fields = [
            ("Applied", row['application_date']),
            ("Preferred building", row['preferred_building_id'] or '—'),
            ("Preferred room type", row['preferred_room_type'] or '—'),
            ("Requested move-in", row['requested_move_in_date'] or '—'),
            ("Duration (months)", row['requested_duration_months'] or '—'),
            ("Reviewed", row['review_date'] or '—'),
        ]
        for i, (label, value) in enumerate(fields):
            ttk.Label(card, text=f"{label}:", font=('Arial', 10, 'bold')).grid(
                row=2 + i // 2, column=(i % 2) * 2, sticky='w', padx=(0, 8), pady=2)
            ttk.Label(card, text=str(value)).grid(
                row=2 + i // 2, column=(i % 2) * 2 + 1, sticky='w', padx=(0, 20), pady=2)

        if row['notes']:
            ttk.Label(card, text="Notes:", font=('Arial', 10, 'bold')).grid(
                row=10, column=0, sticky='nw', pady=(6, 0))
            ttk.Label(card, text=row['notes'], wraplength=500).grid(
                row=10, column=1, columnspan=3, sticky='w', pady=(6, 0))

    def _render_student_maintenance_card(self, parent, conn, student_id):
        card = ttk.LabelFrame(parent, text="Maintenance Requests", padding=12)
        card.pack(fill=tk.X, padx=15, pady=8)

        rows = conn.execute(
            "SELECT request_id, request_date, issue_type, priority, status, "
            "description, scheduled_date "
            "FROM housing_maintenance_requests "
            "WHERE student_id = ? "
            "ORDER BY CASE WHEN status IN ('Open','In Progress') THEN 0 ELSE 1 END, "
            "request_date DESC LIMIT 10",
            (student_id,),
        ).fetchall()

        if not rows:
            ttk.Label(card, text="No maintenance requests submitted.",
                      foreground='#888').pack(anchor='w')
            ttk.Button(card, text="Submit a Request",
                       command=self.show_student_maintenance).pack(anchor='w', pady=(8, 0))
            return

        cols = ('date', 'issue', 'priority', 'status')
        tree = ttk.Treeview(card, columns=cols, show='headings', height=min(len(rows), 6))
        tree.heading('date', text='Submitted')
        tree.heading('issue', text='Issue')
        tree.heading('priority', text='Priority')
        tree.heading('status', text='Status')
        tree.column('date', width=140)
        tree.column('issue', width=200)
        tree.column('priority', width=90, anchor='center')
        tree.column('status', width=110, anchor='center')
        for r in rows:
            tree.insert('', tk.END, values=(
                r['request_date'] or '', r['issue_type'] or '',
                r['priority'] or '', r['status'] or '',
            ))
        tree.pack(fill=tk.X, pady=(0, 6))
        ttk.Button(card, text="Submit a New Request",
                   command=self.show_student_maintenance).pack(anchor='w')

    def _render_student_quick_actions(self, parent):
        card = ttk.LabelFrame(parent, text="Quick Actions", padding=12)
        card.pack(fill=tk.X, padx=15, pady=(8, 15))
        row = ttk.Frame(card)
        row.pack(fill=tk.X)
        ttk.Button(row, text="Apply / Update Application",
                   command=self.show_student_application).pack(side=tk.LEFT, padx=4)
        ttk.Button(row, text="View Assignment",
                   command=self.show_student_assignment).pack(side=tk.LEFT, padx=4)
        ttk.Button(row, text="Maintenance",
                   command=self.show_student_maintenance).pack(side=tk.LEFT, padx=4)
        ttk.Button(row, text="Find a Roommate",
                   command=self.show_find_roommate).pack(side=tk.LEFT, padx=4)

    def show_student_application(self):
        """Show student application interface."""
        self.show_applications()

    def show_student_assignment(self):
        """Show student assignment interface."""
        self.show_assignments()

    def show_student_maintenance(self):
        """Show student maintenance interface."""
        self.show_maintenance()

    def show_find_roommate(self):
        """Embed the Roommate Finder inside housing's content area."""
        self.clear_content()
        try:
            from education_system.university_system.modules.domain.housing.gui.housing_accommodation_gui.roommate_finder import (
                RoommateFinderGUI,
            )
            RoommateFinderGUI(
                self.root, auth=self.auth, container=self.content_frame
            )
        except Exception as e:
            ttk.Label(
                self.content_frame,
                text=f"Roommate Finder unavailable: {e}",
                foreground='red',
            ).pack(pady=20)

    # ========== Backward Compatibility ==========

    def launch_classic_interface(self):
        """Launch the classic command-line interface for backward compatibility."""
        try:
            # Import and run the original housing menu
            orig_display_housing_accommodation_menu(self.auth)  # Pass the auth instance
        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch classic interface: {str(e)}")

    def run(self):
        """Start the GUI application."""
        self.root.mainloop()


# ========== Backward Compatibility Wrapper Functions ==========

def display_housing_accommodation_menu_gui(auth_instance=None):
    """GUI version of the housing accommodation menu."""
    app = HousingGUI(auth_instance)
    app.run()


# ========== Main Entry Point ==========

if __name__ == "__main__":
    # Create a basic auth instance for testing
    class TestAuth:
        def __init__(self):
            self.current_user = {
                'id': 1,
                'username': 'admin',
                'role': 'admin'
            }

        def check_permission(self, permission):
            # For testing, grant all permissions
            return True

    test_auth = TestAuth()
    app = HousingGUI(test_auth)
    app.run()
