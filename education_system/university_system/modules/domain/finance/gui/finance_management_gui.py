import tkinter as tk
from tkinter import ttk, messagebox
import sys
import threading
import logging
from datetime import datetime, timedelta

# Import finance modules
try:
    from education_system.university_system.modules.domain.finance.gui.finance import FinanceGUI
    from education_system.university_system.modules.domain.finance.gui.finance_reporting import FinancialManagementGUI as FinanceReportingGUI
    FINANCE_GUI_AVAILABLE = True
    FINANCE_REPORTING_GUI_AVAILABLE = True
except ImportError as e:
    print(f"Finance GUI modules not available: {e}")
    FinanceGUI = None
    FinanceReportingGUI = None
    FINANCE_GUI_AVAILABLE = False
    FINANCE_REPORTING_GUI_AVAILABLE = False

# Import CLI fallback
try:
    from education_system.university_system.modules.shared.cli.cli_main import display_finance_menu as _display_finance_menu
    FINANCE_CLI_AVAILABLE = True
except ImportError:
    _display_finance_menu = None
    FINANCE_CLI_AVAILABLE = False

try:
    from education_system.university_system.modules.finance.core.financial_core import set_finance_auth as _set_finance_cli_auth
except Exception:
    _set_finance_cli_auth = None

from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.modules.shared.utils.i18n import get_text as _t

# Configure logging
logger = logging.getLogger(__name__)


def _launch_finance_cli_menu(auth):
    """Invoke the legacy CLI menu, wiring auth when possible."""
    if not _display_finance_menu:
        print("Finance CLI menu not available")
        return

    if auth and _set_finance_cli_auth:
        try:
            _set_finance_cli_auth(auth)
        except Exception as exc:
            logging.debug(f"Unable to pass auth to finance CLI: {exc}")

    try:
        _display_finance_menu()
    except TypeError:
        # Older versions of the CLI expect no parameters; call again without args
        _display_finance_menu()

class FinanceManagementGUI:
    """Finance management GUI wrapper that handles both Finance GUI and Finance Reporting"""

    def __init__(self, parent_root, auth_manager):
        self.root = parent_root
        self.auth = auth_manager

    def show_finance_management(self, initial_tab=None):
        """Launch the Finance Management GUI in a child window, fallback to CLI if needed.

        Args:
            initial_tab: Optional tab ID to show initially (e.g., 'housing', 'payments')
        """
        if not self.auth.current_user:
            messagebox.showerror(_t("finance_management.error.title"), _t("finance_management.error.login_required"))
            return

        # Permissions: allow any meaningful finance capability
        if not any([
            self.auth.check_permission('manage_finances'),
            self.auth.check_permission('record_payments'),
            self.auth.check_permission('view_financial_reports'),
            self.auth.check_permission('view_own_finances'),
        ]):
            messagebox.showerror(_t("finance_management.error.title"), _t("finance_management.error.no_permission"))
            return

        # Prefer the new Finance GUI
        if FINANCE_GUI_AVAILABLE and FinanceGUI:
            try:
                # Check if self.root is already a Toplevel window (opened from another module)
                # If so, use it directly instead of creating a new one
                if isinstance(self.root, tk.Toplevel):
                    win = self.root
                    # Ensure proper configuration
                    win.title(_t("finance_management.window.title"))
                    win.geometry("1400x900")
                    win.minsize(1200, 800)
                else:
                    # Create a new Toplevel window (standalone launch)
                    win = tk.Toplevel(self.root)
                    win.title(_t("finance_management.window.title"))
                    win.geometry("1400x900")
                    win.minsize(1200, 800)
                    try:
                        win.transient(self.root)
                    except Exception as e:
                        logger.debug(f"Could not set window as transient: {e}")

                # Configure window background
                win.configure(bg='#f0f0f0')

                app = FinanceGUI(win)
                try:
                    # Push auth into the instance too
                    if hasattr(app, 'set_auth'):
                        app.set_auth(self.auth)
                    else:
                        app.auth = self.auth
                except Exception as e:
                    logger.debug(f"Could not set auth on finance app: {e}")

                # Navigate to specific tab if requested
                if initial_tab and hasattr(app, 'layout') and hasattr(app.layout, 'show_tab'):
                    try:
                        # Give the GUI time to initialize before switching tabs
                        win.after(100, lambda: app.layout.show_tab(initial_tab))
                    except Exception as e:
                        print(f"Warning: Could not navigate to tab '{initial_tab}': {e}")

                print("✅ Finance Management GUI opened successfully")
                return
            except Exception as e:
                messagebox.showerror(_t("finance_management.error.title"), _t("finance_management.error.failed_to_open", error=str(e)))

        # Fallback to existing CLI menu if GUI import failed
        if not FINANCE_CLI_AVAILABLE:
            # Provide a simple fallback message instead of failing completely
            messagebox.showwarning(
                _t("finance_management.warning.limited_functionality_title"),
                _t("finance_management.warning.limited_functionality_message")
            )
            return

        try:
            _launch_finance_cli_menu(self.auth)
        except Exception as e:
            messagebox.showwarning(
                _t("finance_management.warning.cli_fallback_title"),
                _t("finance_management.warning.cli_fallback_message", error=str(e))
            )

    def show_finance_reporting_dashboard(self):
        """Launch the Finance Reporting Dashboard GUI in a child window, fallback to CLI if needed."""
        if not self.auth.current_user:
            messagebox.showerror(_t("finance_management.error.title"), _t("finance_management.error.reporting_login_required"))
            return

        # Check permissions for financial reporting
        if not any([
            self.auth.check_permission('view_financial_reports'),
            self.auth.check_permission('manage_finances'),
            self.auth.current_user.get('role') == 'admin'
        ]):
            messagebox.showerror(_t("finance_management.error.title"), _t("finance_management.error.reporting_no_permission"))
            return

        # Try to launch Finance Reporting GUI
        try:
            # Check if Finance Reporting GUI is available
            if FINANCE_REPORTING_GUI_AVAILABLE:
                finance_reporting_window = tk.Toplevel(self.root)
                finance_reporting_window.title(_t("finance_management.reporting.window_title"))
                finance_reporting_window.geometry("1400x900")
                finance_reporting_window.minsize(1200, 800)

                # Center the window
                finance_reporting_window.update_idletasks()
                x = (finance_reporting_window.winfo_screenwidth() - finance_reporting_window.winfo_width()) // 2
                y = (finance_reporting_window.winfo_screenheight() - finance_reporting_window.winfo_height()) // 2
                finance_reporting_window.geometry(f"+{x}+{y}")

                try:
                    finance_reporting_window.transient(self.root)
                except Exception as e:
                    logger.debug(f"Could not set finance reporting window as transient: {e}")

                # Initialize Finance Reporting GUI
                finance_reporting_gui = FinanceReportingGUI(finance_reporting_window, self.auth)

                print("✅ Finance Reporting Dashboard opened successfully")
                return
            else:
                # GUI not available, show info dialog
                messagebox.showinfo(_t("finance_management.reporting.info_title"), _t("finance_management.reporting.not_available"))

        except Exception as e:
            messagebox.showerror(_t("finance_management.error.title"), _t("finance_management.error.reporting_failed", error=str(e)))
            print(f"❌ Finance Reporting Dashboard error: {e}")
