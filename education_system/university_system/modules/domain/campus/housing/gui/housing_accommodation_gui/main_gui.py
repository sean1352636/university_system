"""
Main GUI module for Housing Accommodation Management System.
This module provides the main HousingGUI class that orchestrates all manager modules.
"""

import logging
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import os

logger = logging.getLogger(__name__)

# Core imports
from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.infrastructure.shared_context import get_auth
from education_system.university_system.modules.shared.utils.simple_activity_logger import (
    log_activity, log_create, log_read, log_update, log_delete
)
from education_system.university_system.core import paths

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
from education_system.university_system.core.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from education_system.university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector

# Import all manager modules
from education_system.university_system.modules.domain.campus.housing.gui.housing_accommodation_gui import (
    dashboard_manager,
    building_manager,
    room_manager,
    application_manager,
    assignment_manager,
    maintenance_manager,
    payment_manager,
    refund_manager,
    deposit_manager,
    inventory_manager,
    inspection_manager,
    report_manager,
    export_manager,
    scheduled_reports,
    finance_integration,
    moveout_manager,
    waitlist_manager,
    vacancy_board,
    bulk_operations,
    broadcasts,
    resident_search,
    keys_manager,
    contracts_manager,
    checklists_manager,
    guests_manager,
    damages_ledger,
    audit_log_viewer,
    staff_roommate_finder,
)

# Import housing services
from education_system.university_system.modules.domain.campus.housing.services.housing_accommodation import (
    init_housing_db, generate_id, set_auth,
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
        # Clamp to the available screen so a smaller display can't push
        # the dashboard off the right edge / below the taskbar.
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        win_w = min(1400, max(960, screen_w - 40))
        win_h = min(900, max(640, screen_h - 80))
        x = max(0, (screen_w - win_w) // 2)
        y = max(0, (screen_h - win_h) // 2)
        self.root.geometry(f"{win_w}x{win_h}+{x}+{y}")
        self.root.minsize(960, 640)
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

        # Left sidebar — scrollable so the admin menu (25+ buttons) can
        # be reached without growing the window or pushing the right
        # pane off-screen.
        sidebar_outer = ttk.Frame(main_frame)
        sidebar_outer.grid(row=1, column=0, sticky=(tk.W, tk.N, tk.S),
                            padx=(0, 20))
        sidebar_outer.rowconfigure(0, weight=1)

        side_canvas = tk.Canvas(sidebar_outer, width=180,
                                  highlightthickness=0, borderwidth=0)
        side_scroll = ttk.Scrollbar(sidebar_outer, orient="vertical",
                                      command=side_canvas.yview)
        side_canvas.configure(yscrollcommand=side_scroll.set)
        side_canvas.grid(row=0, column=0, sticky="ns")
        side_scroll.grid(row=0, column=1, sticky="ns")

        sidebar_frame = ttk.Frame(side_canvas)
        side_window = side_canvas.create_window(
            (0, 0), window=sidebar_frame, anchor="nw")

        def _on_sidebar_configure(_e=None) -> None:
            side_canvas.configure(scrollregion=side_canvas.bbox("all"))
        sidebar_frame.bind("<Configure>", _on_sidebar_configure)
        side_canvas.bind(
            "<Configure>",
            lambda e: side_canvas.itemconfigure(side_window, width=e.width))

        # Mousewheel only when pointer is over the sidebar — avoids
        # stealing scroll from the content pane.
        def _on_mw(event):
            side_canvas.yview_scroll(int(-event.delta / 120), "units")
        for w in (side_canvas, sidebar_frame):
            w.bind("<Enter>",
                   lambda _e: side_canvas.bind_all("<MouseWheel>", _on_mw))
            w.bind("<Leave>",
                   lambda _e: side_canvas.unbind_all("<MouseWheel>"))

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
            ttk.Button(parent, text="Deposits", width=20,
                      command=self.show_deposits).pack(pady=2)
            ttk.Button(parent, text=_t("housing.menu_inventory"), width=20,
                      command=self.show_inventory).pack(pady=2)
            ttk.Button(parent, text=_t("housing.menu_inspections"), width=20,
                      command=self.show_inspections).pack(pady=2)
            ttk.Button(parent, text=_t("housing.menu_reports"), width=20,
                      command=self.show_reports).pack(pady=2)
            # Previously built but unexposed admin tools
            ttk.Button(parent, text="Refunds", width=20,
                      command=self.show_refunds).pack(pady=2)
            ttk.Button(parent, text="Outstanding Balances", width=20,
                      command=self.show_outstanding_balances).pack(pady=2)
            ttk.Button(parent, text="TDP Compliance", width=20,
                      command=self.show_tdp_compliance).pack(pady=2)
            ttk.Button(parent, text="Deposit Interest", width=20,
                      command=self.show_deposit_interest).pack(pady=2)
            ttk.Button(parent, text="Scheduled Reports", width=20,
                      command=self.show_scheduled_reports).pack(pady=2)
            ttk.Button(parent, text="Vacancy Board", width=20,
                      command=self.show_vacancy_board).pack(pady=2)
            ttk.Button(parent, text="Waitlist", width=20,
                      command=self.show_waitlist).pack(pady=2)
            ttk.Button(parent, text="Move-Out Workflow", width=20,
                      command=self.show_moveout_workflow).pack(pady=2)
            ttk.Button(parent, text="Bulk Operations", width=20,
                      command=self.show_bulk_operations).pack(pady=2)
            ttk.Button(parent, text="Resident Broadcasts", width=20,
                      command=self.show_broadcasts).pack(pady=2)
            ttk.Button(parent, text="Resident Search", width=20,
                      command=self.show_resident_search).pack(pady=2)
            ttk.Button(parent, text="Keys & Access Cards", width=20,
                      command=self.show_keys).pack(pady=2)
            ttk.Button(parent, text="Contracts / Leases", width=20,
                      command=self.show_contracts).pack(pady=2)
            ttk.Button(parent, text="Move-in/out Checklists", width=20,
                      command=self.show_checklists).pack(pady=2)
            ttk.Button(parent, text="Guest Passes", width=20,
                      command=self.show_guests).pack(pady=2)
            ttk.Button(parent, text="Damages Ledger", width=20,
                      command=self.show_damages_ledger).pack(pady=2)
            ttk.Button(parent, text="Activity Log", width=20,
                      command=self.show_audit_log).pack(pady=2)
            ttk.Button(parent, text="Roommate Finder", width=20,
                      command=self.show_staff_roommate_finder).pack(pady=2)

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
            ttk.Button(parent, text="My Deposit Deductions", width=20,
                      command=self.show_student_deductions).pack(pady=2)
        else:
            ttk.Label(parent, text=_t("housing.no_permissions"),
                     foreground='red').pack(pady=10)

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

    def show_deposits(self):
        """Show deposit lifecycle panel (delegates to deposit_manager)."""
        deposit_manager.show_deposits(self)

    def show_student_deductions(self):
        """Student deposit deductions review (delegates to deposit_manager)."""
        deposit_manager.show_student_deductions(self)

    def show_inventory(self):
        """Show inventory (delegates to inventory_manager)."""
        inventory_manager.show_inventory(self)

    def show_inspections(self):
        """Show inspections (delegates to inspection_manager)."""
        inspection_manager.show_inspections(self)

    def show_reports(self):
        """Show reports (delegates to report_manager)."""
        report_manager.show_reports(self)

    # ========== Newly-exposed admin tools ==========

    def show_refunds(self):
        """Housing payments & refunds (delegates to refund_manager)."""
        self.clear_content()
        refund_manager.create_payments_refunds_tab(self, self.content_frame)

    def show_outstanding_balances(self):
        """Outstanding housing balances (uses HousingFinanceManager)."""
        try:
            # Lightweight construction: instantiate against a hidden host
            # so the manager's auto-built interface doesn't pollute our
            # content frame, then call the standalone window method.
            host = tk.Toplevel(self.root)
            host.withdraw()
            mgr = finance_integration.HousingFinanceManager(host, auth=self.auth)
            mgr.show_outstanding_balances()
        except Exception as e:
            messagebox.showerror("Error",
                                 f"Failed to open outstanding balances: {e}",
                                 parent=self.root)

    def show_scheduled_reports(self):
        """Scheduled reports manager (delegates to scheduled_reports)."""
        scheduled_reports.show_scheduled_reports_manager(self)

    def show_moveout_workflow(self):
        """End-of-tenancy workflow (delegates to moveout_manager)."""
        try:
            moveout_manager.show_moveout_workflow(self)
        except Exception as e:
            messagebox.showerror("Move-out",
                                 f"Could not open the move-out workflow:\n\n{e}",
                                 parent=self.root)

    def show_waitlist(self):
        """Housing waitlist (delegates to waitlist_manager)."""
        try:
            waitlist_manager.show_waitlist(self)
        except Exception as e:
            messagebox.showerror("Waitlist",
                                 f"Could not open the waitlist:\n\n{e}",
                                 parent=self.root)

    def show_vacancy_board(self):
        """Live cross-building vacancy board (delegates to vacancy_board)."""
        try:
            vacancy_board.show_vacancy_board(self)
        except Exception as e:
            messagebox.showerror("Vacancy board",
                                 f"Could not open the vacancy board:\n\n{e}",
                                 parent=self.root)

    def show_bulk_operations(self):
        """Bulk approve / mass move-out / rent adjustments."""
        try:
            bulk_operations.show_bulk_operations(self)
        except Exception as e:
            messagebox.showerror("Bulk operations",
                                 f"Could not open bulk operations:\n\n{e}",
                                 parent=self.root)

    def show_broadcasts(self):
        """Resident broadcast / mass communication."""
        try:
            broadcasts.show_broadcasts(self)
        except Exception as e:
            messagebox.showerror("Broadcasts",
                                 f"Could not open broadcasts:\n\n{e}",
                                 parent=self.root)

    def show_resident_search(self):
        """Cross-building resident search."""
        try:
            resident_search.show_resident_search(self)
        except Exception as e:
            messagebox.showerror("Resident search",
                                 f"Could not open resident search:\n\n{e}",
                                 parent=self.root)

    def show_keys(self):
        try:
            keys_manager.show_keys(self)
        except Exception as e:
            messagebox.showerror("Keys",
                                 f"Could not open keys screen:\n\n{e}",
                                 parent=self.root)

    def show_contracts(self):
        try:
            contracts_manager.show_contracts(self)
        except Exception as e:
            messagebox.showerror("Contracts",
                                 f"Could not open contracts:\n\n{e}",
                                 parent=self.root)

    def show_checklists(self):
        try:
            checklists_manager.show_checklists(self)
        except Exception as e:
            messagebox.showerror("Checklists",
                                 f"Could not open checklists:\n\n{e}",
                                 parent=self.root)

    def show_guests(self):
        try:
            guests_manager.show_guests(self)
        except Exception as e:
            messagebox.showerror("Guests",
                                 f"Could not open guest passes:\n\n{e}",
                                 parent=self.root)

    def show_damages_ledger(self):
        try:
            damages_ledger.show_damages_ledger(self)
        except Exception as e:
            messagebox.showerror("Damages ledger",
                                 f"Could not open damages ledger:\n\n{e}",
                                 parent=self.root)

    def show_audit_log(self):
        try:
            audit_log_viewer.show_audit_log(self)
        except Exception as e:
            messagebox.showerror("Activity log",
                                 f"Could not open activity log:\n\n{e}",
                                 parent=self.root)

    def show_staff_roommate_finder(self):
        try:
            staff_roommate_finder.show_staff_roommate_finder(self)
        except Exception as e:
            messagebox.showerror("Roommate finder",
                                 f"Could not open roommate finder:\n\n{e}",
                                 parent=self.root)

    def show_tdp_compliance(self):
        """TDP (Tenancy Deposit Protection) compliance report."""
        from education_system.university_system.modules.domain.campus.housing.services.housing_accommodation import (
            tdp,
        )
        self._show_captured_output(
            "TDP Compliance", tdp.tdp_compliance_report)

    def show_deposit_interest(self):
        """Deposit interest accruals — view + accrue."""
        from education_system.university_system.modules.domain.campus.housing.services.housing_accommodation import (
            interest,
        )
        self.clear_content()
        bar = ttk.Frame(self.content_frame, padding=6)
        bar.pack(fill="x")
        ttk.Label(bar, text="Deposit Interest",
                  font=("Arial", 12, "bold")).pack(side="left")
        ttk.Button(bar, text="Accrue now",
                   command=lambda: self._show_captured_output(
                       "Deposit Interest — Accrual",
                       interest.accrue_deposit_interest)
                   ).pack(side="right", padx=4)
        ttk.Button(bar, text="View accruals",
                   command=lambda: self._show_captured_output(
                       "Deposit Interest — Accruals",
                       interest.view_interest_accruals)
                   ).pack(side="right", padx=4)
        ttk.Label(self.content_frame,
                  text="Choose an action above.",
                  foreground="#555").pack(anchor="w", padx=8, pady=8)

    def _show_captured_output(self, title: str, fn) -> None:
        """Run a CLI-style service function (which prints to stdout)
        and surface its output in the content area."""
        import io
        import contextlib
        self.clear_content()
        ttk.Label(self.content_frame, text=title,
                  font=("Arial", 12, "bold")).pack(anchor="w", padx=6, pady=(6, 4))
        text = tk.Text(self.content_frame, wrap="word", height=30,
                       font=("Courier", 10))
        sb = ttk.Scrollbar(self.content_frame, orient="vertical",
                           command=text.yview)
        text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        text.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=4)
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                fn()
        except Exception as e:
            buf.write(f"\n[Error: {e}]\n")
        text.insert("1.0", buf.getvalue() or "(no output)")
        text.configure(state="disabled")

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
            from education_system.university_system.modules.domain.campus.housing.gui.housing_accommodation_gui.roommate_finder import (
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
