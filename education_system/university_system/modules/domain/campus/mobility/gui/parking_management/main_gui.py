"""Main ParkingManagementGUI class assembled from mixins."""
import tkinter as tk
from tkinter import ttk, messagebox
import logging

from education_system.university_system.modules.domain.campus.mobility.gui.parking_management import (
    init_i18n, _t, get_connection, init_db, set_auth, get_auth, UserAuth,
)
from education_system.university_system.modules.domain.campus.mobility.gui.parking_management.tabs import (
    PermitsMixin, VehiclesMixin, ViolationsMixin,
    LotsMixin, PaymentsMixin, DashboardMixin,
)
from education_system.university_system.modules.domain.campus.mobility.gui.parking_management.reports import ReportsMixin
from education_system.university_system.modules.domain.campus.mobility.gui.parking_management.exports import ExportsMixin


class ParkingManagementGUI(
    PermitsMixin, VehiclesMixin, ViolationsMixin,
    LotsMixin, PaymentsMixin, DashboardMixin,
    ReportsMixin, ExportsMixin,
):
    def __init__(self, root, auth_system=None):
        # Initialize i18n for language support
        init_i18n()

        self.root = root
        self.root.title(_t("parking.title"))
        self.root.geometry("1400x900+%d+%d" % ((self.root.winfo_screenwidth() - 1400) // 2, (self.root.winfo_screenheight() - 900) // 2))
        self.root.minsize(1200, 800)

        # Initialize authentication - use provided auth system or centralized auth
        if auth_system:
            self.auth = auth_system
        else:
            # Use centralized auth system
            self.auth = get_auth()
            if self.auth is None:
                self.auth = UserAuth()
        set_auth(self.auth)

        # Initialize database
        init_db()

        # Initialize payment and refund tables
        self._init_payment_refund_tables()

        # Current user info
        self.current_user = None

        # Setup current user from existing authentication system
        self.setup_current_user()

        # Create the main interface
        self.setup_gui()

        # Show appropriate interface based on authentication status
        if self.current_user:
            self.update_user_status()
            self.update_status("Using authenticated user session")
            self.update_tab_access()
        else:
            # User must log in through main University System GUI
            messagebox.showerror(
                _t("common.error"),
                _t("parking.messages.auth_required")
            )
            self.root.destroy()

    def setup_current_user(self):
        """Setup current user from existing authentication system"""
        try:
            # Check if auth system has a current authenticated user
            if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
                auth_user = self.auth.current_user

                # auth_user is already a dictionary from UserAuth system
                if isinstance(auth_user, dict):
                    self.current_user = {
                        "username": auth_user.get('username', 'Unknown'),
                        "role": auth_user.get('role', 'user'),
                        "permissions": auth_user.get('permissions', []),
                        "first_name": auth_user.get('first_name', ''),
                        "last_name": auth_user.get('last_name', ''),
                        "id": auth_user.get('id', 0)
                    }
                else:
                    # Handle case where it might be an object
                    self.current_user = {
                        "username": getattr(auth_user, 'username', 'Unknown'),
                        "role": getattr(auth_user, 'role', 'user'),
                        "permissions": getattr(auth_user, 'permissions', []),
                        "first_name": getattr(auth_user, 'first_name', ''),
                        "last_name": getattr(auth_user, 'last_name', ''),
                        "id": getattr(auth_user, 'id', 0)
                    }

                print(f"✓ Parking Management GUI: Using authenticated user {self.current_user['username']} ({self.current_user['role']})")
            else:
                self.current_user = None
                print("ℹ Parking Management GUI: No authenticated user - will show login screen")
        except Exception as e:
            print(f"✗ Error setting up current user: {e}")
            self.current_user = None

    def _init_payment_refund_tables(self):
        """Initialize payment and refund tables in the database"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Add payment_status column to parking_violations if it doesn't exist
            try:
                cursor.execute("SELECT payment_status FROM parking_violations LIMIT 1")
            except Exception:
                cursor.execute("ALTER TABLE parking_violations ADD COLUMN payment_status TEXT DEFAULT 'Unpaid'")

            conn.commit()
            conn.close()
            logging.info("Payment and refund tables initialized")
        except Exception as e:
            logging.error(f"Error initializing payment/refund tables: {e}")

    def setup_gui(self):
        """Set up the main GUI interface"""
        # Create main frame
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create menu bar
        self.create_menu_bar()

        # Create status bar
        self.create_status_bar()

        # Ensure a persistent top-corner main menu button is available
        self.create_main_menu_button()

        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 30))

        # Create tabs
        self.create_tabs()

    def create_menu_bar(self):
        """Create the menu bar"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("menu.file"), menu=file_menu)
        file_menu.add_command(label=_t("parking.menu.export_data"), command=self.show_export_dialog)
        file_menu.add_separator()
        file_menu.add_command(label=_t("common.exit"), command=self.root.quit)

        # Reports menu
        reports_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("parking.menu.reports"), menu=reports_menu)
        reports_menu.add_command(label=_t("parking.menu.permit_report"), command=self.generate_permit_report)
        reports_menu.add_command(label=_t("parking.menu.violation_report"), command=self.generate_violation_report)
        reports_menu.add_command(label=_t("parking.menu.occupancy_report"), command=self.generate_occupancy_report)
        reports_menu.add_command(label=_t("parking.menu.revenue_report"), command=self.generate_revenue_report)
        reports_menu.add_command(label=_t("parking.menu.user_activity_report"), command=self.generate_user_activity_report)
        reports_menu.add_command(label=_t("parking.menu.compliance_report"), command=self.generate_compliance_report)
        reports_menu.add_command(label=_t("parking.menu.analytics_dashboard"), command=self.show_analytics)

        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("menu.tools"), menu=tools_menu)
        tools_menu.add_command(label=_t("parking.menu.refresh_all"), command=self.refresh_all_data)
        tools_menu.add_command(label=_t("parking.menu.database_backup"), command=self.backup_database)
        tools_menu.add_command(label=_t("parking.menu.update_spaces"), command=self.update_available_spaces_dialog)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("menu.help"), menu=help_menu)
        help_menu.add_command(label=_t("parking.menu.about"), command=self.show_about)

    def create_main_menu_button(self):
        """Place a top-corner button to return to the main menu"""
        try:
            if hasattr(self, "main_menu_button") and self.main_menu_button.winfo_exists():
                return
        except Exception:
            pass

        self.main_menu_button = ttk.Button(
            self.root,
            text=_t("common.return_to_main_menu"),
            command=self.return_to_main_menu,
        )
        # Place in the top-right corner with a slight margin
        self.main_menu_button.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)

    def create_status_bar(self):
        """Create the status bar"""
        self.status_frame = ttk.Frame(self.main_frame)
        self.status_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self.status_label = ttk.Label(self.status_frame, text=_t("common.ready"))
        self.status_label.pack(side=tk.LEFT)

        self.user_label = ttk.Label(self.status_frame, text=_t("parking.not_logged_in"))
        self.user_label.pack(side=tk.RIGHT)

    def create_tabs(self):
        """Create all the tabs"""
        # Permits tab
        self.permits_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.permits_frame, text=_t("parking.tabs.permits"))
        self.setup_permits_tab()

        # Vehicles tab
        self.vehicles_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.vehicles_frame, text=_t("parking.tabs.vehicles"))
        self.setup_vehicles_tab()

        # Violations tab
        self.violations_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.violations_frame, text=_t("parking.tabs.violations"))
        self.setup_violations_tab()

        # Parking Lots tab
        self.lots_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.lots_frame, text=_t("parking.tabs.parking_lots"))
        self.setup_lots_tab()

        # Payments & Refunds tab
        self.payments_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.payments_frame, text="Payments & Refunds")
        self.setup_payments_tab()

        # Dashboard tab
        self.dashboard_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.dashboard_frame, text=_t("parking.tabs.dashboard"))
        self.setup_dashboard_tab()

    def update_user_status(self):
        """Update the user status in the status bar"""
        if self.current_user:
            self.user_label.config(text=f"{_t('common.user')}: {self.current_user['first_name']} {self.current_user['last_name']} ({self.current_user['role']})")
        else:
            self.user_label.config(text=_t("parking.not_logged_in"))

    def update_status(self, message):
        """Update the status bar message"""
        self.status_label.config(text=message)
        # Clear status after 3 seconds
        self.root.after(3000, lambda: self.status_label.config(text=_t("common.ready")))

    def update_tab_access(self):
        """Enable/disable tabs based on user permissions"""
        if not self.current_user:
            return

        user_role = self.current_user.get('role', '').lower()

        if user_role in ['admin', 'administrator', 'staff', 'faculty']:
            pass
        elif user_role == 'student':
            pass
        else:
            pass

        self._update_tab_buttons_state()

    def _update_tab_buttons_state(self):
        """Update button states in tabs based on user role"""
        if not self.current_user:
            return

        user_role = self.current_user.get('role', '').lower()
        is_staff_or_admin = user_role in ['admin', 'administrator', 'staff', 'faculty']
        pass

    def refresh_all_data(self):
        """Refresh all data in all tabs"""
        self.refresh_permits()
        self.refresh_vehicles()
        self.refresh_violations()
        self.refresh_lots()
        self.refresh_dashboard()
        self.update_status("All data refreshed")

    def return_to_main_menu(self):
        """Return to the main menu"""
        try:
            if isinstance(self.root, tk.Toplevel):
                self.root.destroy()
            else:
                self.root.destroy()
                from education_system.university_system.modules.shared.gui.main import UnifiedManagementGUI
                app = UnifiedManagementGUI(self.auth)
                app.run()
        except Exception as e:
            print(f"Error returning to main menu: {e}")
            import traceback
            traceback.print_exc()

    def show_about(self):
        """Show about dialog"""
        about_text = """
Parking Management System GUI

Version: 1.0
Author: System Administrator

This is a comprehensive parking management system
with both GUI and console interfaces.

Features:
- Permit Management
- Vehicle Registration
- Violation Tracking
- Parking Lot Management
- Reports and Analytics
- Data Export
- Email Notifications
        """
        messagebox.showinfo("About", about_text)


# Console compatibility function
def run_console_interface():
    """Run the original console interface"""
    try:
        from parking_management import display_parking_menu
        display_parking_menu()
    except ImportError:
        print("Console interface not available")


def main():
    """Main function to choose between GUI and console interface"""
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == '--console':
        run_console_interface()
    else:
        root = tk.Tk()
        app = ParkingManagementGUI(root)

        try:
            existing_menubar = root.nametowidget(root['menu']) if root['menu'] else None
            if existing_menubar:
                console_menu = tk.Menu(existing_menubar, tearoff=0)
                console_menu.add_command(label="Switch to Console", command=run_console_interface)
                existing_menubar.add_cascade(label="Interface", menu=console_menu)
        except Exception as e:
            print(f"Warning: Could not add console menu: {e}")

        root.mainloop()


if __name__ == "__main__":
    main()
