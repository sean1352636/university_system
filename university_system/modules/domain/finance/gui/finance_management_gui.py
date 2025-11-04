import tkinter as tk
from tkinter import ttk, messagebox
import sys
import threading
import logging
from datetime import datetime, timedelta

# Import finance modules
try:
    from university_system.modules.domain.finance.gui.finance import FinanceGUI
    from university_system.modules.domain.finance.gui.finance_reporting_gui import FinancialManagementGUI as FinanceReportingGUI
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
    from university_system.cli_main import display_finance_menu as _display_finance_menu
    FINANCE_CLI_AVAILABLE = True
except ImportError:
    _display_finance_menu = None
    FINANCE_CLI_AVAILABLE = False

try:
    from university_system.modules.finance.core.financial_core import set_finance_auth as _set_finance_cli_auth
except Exception:
    _set_finance_cli_auth = None

from university_system.infrastructure.auth.user_authentication import UserAuth


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

        # Initialize theme manager for dark mode support
        try:
            from university_system.modules.shared.gui.theme_config import get_theme_manager
            self.theme_manager = get_theme_manager()
            self.theme_manager.register_observer(self.on_theme_changed)
        except Exception as e:
            print(f"Warning: Could not initialize theme manager: {e}")
            self.theme_manager = None

    def on_theme_changed(self):
        """Handle theme changes - update any open windows"""
        if self.theme_manager:
            # Update any cached windows if needed
            pass

    def show_finance_management(self):
        """Launch the Finance Management GUI in a child window, fallback to CLI if needed."""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to access finance management.")
            return

        # Permissions: allow any meaningful finance capability
        if not any([
            self.auth.check_permission('manage_finances'),
            self.auth.check_permission('record_payments'),
            self.auth.check_permission('view_financial_reports'),
            self.auth.check_permission('view_own_finances'),
        ]):
            messagebox.showerror("Error", "You don't have permission to access finance management.")
            return

        # Prefer the new Finance GUI
        if FINANCE_GUI_AVAILABLE and FinanceGUI:
            try:
                win = tk.Toplevel(self.root)
                win.title("Finance Management System")
                win.geometry("1400x900")
                win.minsize(1200, 800)

                # Apply theme to window
                if self.theme_manager:
                    self.theme_manager.apply_theme_to_window(win)
                try:
                    win.transient(self.root)
                    # Don't use grab_set() - it freezes the parent window
                    # win.grab_set()
                except Exception:
                    pass

                app = FinanceGUI(win)
                try:
                    # Push auth into the instance too
                    if hasattr(app, 'set_auth'):
                        app.set_auth(self.auth)
                    else:
                        app.auth = self.auth
                except Exception:
                    pass

                print("✅ Finance Management GUI opened successfully")
                return
            except Exception as e:
                messagebox.showerror("Error", f"Failed to open Finance GUI: {e}")

        # Fallback to existing CLI menu if GUI import failed
        if not FINANCE_CLI_AVAILABLE:
            # Provide a simple fallback message instead of failing completely
            messagebox.showwarning(
                "Limited Functionality",
                "Finance GUI is not available and CLI fallback is not configured.\n\n"
                "Available options:\n"
                "• Use the standalone Finance GUI if available\n"
                "• Check system configuration\n"
                "• Contact system administrator"
            )
            return

        try:
            _launch_finance_cli_menu(self.auth)
        except Exception as e:
            messagebox.showwarning(
                "CLI Fallback Issue",
                f"Finance GUI not available and CLI fallback had issues: {e}\n\n"
                "Please try:\n"
                "• Restarting the application\n"
                "• Using the standalone Finance GUI\n"
                "• Contacting system administrator"
            )

    def show_finance_reporting_dashboard(self):
        """Launch the Finance Reporting Dashboard GUI in a child window, fallback to CLI if needed."""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to access finance reporting.")
            return

        # Check permissions for financial reporting
        if not any([
            self.auth.check_permission('view_financial_reports'),
            self.auth.check_permission('manage_finances'),
            self.auth.current_user.get('role') == 'admin'
        ]):
            messagebox.showerror("Error", "You don't have permission to access finance reporting.")
            return

        # Try to launch Finance Reporting GUI
        try:
            # Check if Finance Reporting GUI is available
            if FINANCE_REPORTING_GUI_AVAILABLE:
                finance_reporting_window = tk.Toplevel(self.root)
                finance_reporting_window.title("Finance Reporting Dashboard")
                finance_reporting_window.geometry("1400x900")
                finance_reporting_window.minsize(1200, 800)

                # Center the window
                finance_reporting_window.update_idletasks()
                x = (finance_reporting_window.winfo_screenwidth() - finance_reporting_window.winfo_width()) // 2
                y = (finance_reporting_window.winfo_screenheight() - finance_reporting_window.winfo_height()) // 2
                finance_reporting_window.geometry(f"+{x}+{y}")

                try:
                    finance_reporting_window.transient(self.root)
                except Exception:
                    pass

                # Initialize Finance Reporting GUI
                finance_reporting_gui = FinanceReportingGUI(finance_reporting_window, self.auth)

                print("✅ Finance Reporting Dashboard opened successfully")
                return
            else:
                # GUI not available, show info dialog
                messagebox.showinfo("Finance Reporting", "Finance Reporting Dashboard GUI not available. Feature exists in CLI mode.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open Finance Reporting Dashboard: {str(e)}")
            print(f"❌ Finance Reporting Dashboard error: {e}")
