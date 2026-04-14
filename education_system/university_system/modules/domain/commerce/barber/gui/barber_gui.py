"""Barber Shop GUI Module

Provides a comprehensive GUI for barber shop operations including
appointments, services, staff, and reporting with email and finance integration.

This file is the slim orchestrator: it inherits all behaviour from
the mixin modules in ``helpers``, ``tabs/``, and ``features/``.
"""

import logging

from education_system.university_system.modules.domain.commerce.barber.gui.common import (
    tk, ttk, messagebox,
    _t, log_activity,
)

from education_system.university_system.modules.domain.commerce.barber.gui.helpers import HelpersMixin

from education_system.university_system.modules.domain.commerce.barber.gui.tabs import (
    AppointmentsTabMixin,
    ServicesTabMixin,
    StaffTabMixin,
    CustomersTabMixin,
    FinanceTabMixin,
    AnalyticsTabMixin,
    ReportsTabMixin,
    RefundsTabMixin,
)

from education_system.university_system.modules.domain.commerce.barber.gui.features import (
    AppointmentsMixin,
    ServicesMixin,
    StaffMixin,
    CustomersMixin,
    FinanceMixin,
    AnalyticsMixin,
    RefundsMixin,
)

logger = logging.getLogger(__name__)


class BarberGUI(
    HelpersMixin,
    # Tab-creation mixins
    AppointmentsTabMixin,
    ServicesTabMixin,
    StaffTabMixin,
    CustomersTabMixin,
    FinanceTabMixin,
    AnalyticsTabMixin,
    ReportsTabMixin,
    RefundsTabMixin,
    # Feature-logic mixins
    AppointmentsMixin,
    ServicesMixin,
    StaffMixin,
    CustomersMixin,
    FinanceMixin,
    AnalyticsMixin,
    RefundsMixin,
):
    """Main GUI class for Barber Shop operations"""

    def __init__(self, parent: tk.Toplevel, auth=None):
        """Initialize the Barber Shop GUI"""
        self.parent = parent
        self.auth = auth

        # Try to get auth from shared context if not provided
        from education_system.university_system.modules.domain.commerce.barber.gui.common import (
            AUTH_AVAILABLE, get_auth,
        )
        if self.auth is None and AUTH_AVAILABLE and get_auth:
            self.auth = get_auth()

        # Check authentication
        if not self._check_authentication():
            return

        self.parent.title(_t("barber.window_title"))
        self.parent.geometry("1400x900")
        self.parent.minsize(1200, 800)

        # Initialize database
        self._init_database()

        # Create main interface
        self.create_widgets()

        # Load initial data
        self.refresh_all_data()

        log_activity('access', 'barber_shop')

    def create_widgets(self):
        """Create the main GUI widgets"""
        # Header frame
        header_frame = ttk.Frame(self.parent, padding="10")
        header_frame.pack(fill=tk.X)

        ttk.Label(header_frame, text=_t("barber.title"),
                 font=('Helvetica', 16, 'bold')).pack(side=tk.LEFT)

        user_info = f"{self.current_user.get('username')} ({self.current_user.get('role')})"
        ttk.Label(header_frame, text=user_info).pack(side=tk.RIGHT)

        # Main notebook for tabs
        self.notebook = ttk.Notebook(self.parent)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Create tabs
        self.create_appointments_tab()
        self.create_customers_tab()
        self.create_services_tab()
        self.create_staff_tab()
        self.create_finance_tab()
        self.create_analytics_tab()
        self.create_reports_tab()
        self.create_refunds_tab()

        # Bottom buttons
        btn_frame = ttk.Frame(self.parent, padding="10")
        btn_frame.pack(fill=tk.X)

        ttk.Button(btn_frame, text=_t("common.refresh"),
                  command=self.refresh_all_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("barber.btn.return_home"),
                  command=self.return_to_homescreen).pack(side=tk.RIGHT, padx=5)

    def return_to_homescreen(self):
        """Return to the main homescreen"""
        if messagebox.askyesno(_t("common.confirm"), _t("barber.confirm.exit")):
            self.parent.destroy()

    def refresh_all_data(self):
        """Refresh all data in the GUI"""
        try:
            self._load_appointments()
            self._load_services()
            self._load_staff()
        except Exception as e:
            logger.error(f"Error refreshing data: {e}")


def launch_barber_gui(parent=None, auth=None):
    """Launch the Barber Shop GUI"""
    return BarberGUI(parent, auth)
