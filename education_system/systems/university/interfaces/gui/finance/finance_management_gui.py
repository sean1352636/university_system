import tkinter as tk
from tkinter import ttk, messagebox
import sys
import threading
import logging
from datetime import datetime, timedelta

# Import finance modules
try:
    from education_system.systems.university.interfaces.gui.finance.finance import FinanceGUI
    from education_system.systems.university.interfaces.gui.finance.finance_reporting import FinancialManagementGUI as FinanceReportingGUI
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
    from education_system.systems.university.interfaces.gui.finance.finance_reporting.misc import display_finance_menu as _display_finance_menu
    FINANCE_CLI_AVAILABLE = True
except ImportError:
    _display_finance_menu = None
    FINANCE_CLI_AVAILABLE = False

try:
    from education_system.systems.university.domain.finance.core.financial_core import set_finance_auth as _set_finance_cli_auth
except Exception:
    _set_finance_cli_auth = None

from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.interfaces.gui.shell.theme_config import get_theme_manager
from education_system.systems.university.infrastructure.i18n import get_text as _t

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

                # Cross-domain bus: receive charges raised by Library
                # (overdue fines), Exam scheduling (resit fees), Research
                # (grant spend), and refresh the open finance view so the
                # operator sees the new balance/transaction immediately.
                try:
                    from education_system.systems.university.interfaces.gui.academics._event_bus import (
                        subscribe_tk, EVENT_CHARGE_RAISED, EVENT_HOLD_CHANGED,
                    )

                    def _on_finance_change(**_payload):
                        for attr in ("refresh", "reload", "refresh_all_data",
                                     "load_data", "refresh_data"):
                            fn = getattr(app, attr, None)
                            if callable(fn):
                                try:
                                    fn()
                                except Exception:
                                    pass
                                return

                    subscribe_tk(EVENT_CHARGE_RAISED, win, _on_finance_change)
                    subscribe_tk(EVENT_HOLD_CHANGED, win, _on_finance_change)
                except Exception as bus_err:
                    logger.debug(f"Finance bus subscribe failed: {bus_err}")

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

    def show_student_account_summary(self, student_id: str):
        """Open a unified per-student account window combining housing,
        SU and other finance activity via ``finance_bus`` +
        ``student_union_bus``.

        Reads only — useful for Finance staff triaging a student's
        cross-domain charges and active holds in one place.
        """
        if not self.auth or not self.auth.current_user:
            messagebox.showerror("Account Summary", "Login required.")
            return
        if not any([
            self.auth.check_permission('manage_finances'),
            self.auth.check_permission('view_financial_reports'),
            self.auth.current_user.get('role') == 'admin',
        ]):
            messagebox.showerror("Account Summary",
                                 "You don't have permission to view "
                                 "student finance summaries.")
            return

        try:
            from education_system.systems.university.services.bus import (
                finance_bus,
            )
            from education_system.systems.university.services.bus import (
                student_union_bus,
            )
        except Exception as exc:
            messagebox.showerror("Account Summary",
                                 f"Bus modules unavailable: {exc}")
            return

        summary = finance_bus.student_account_summary(student_id)
        su_charges = student_union_bus.list_outstanding_su_charges(student_id)
        clubs = student_union_bus.list_clubs_for(student_id)
        hall = student_union_bus.student_hall(student_id)

        win = tk.Toplevel(self.root)
        win.title(f"Student account — {student_id}")
        win.geometry("700x600")

        header = ttk.Label(
            win,
            text=f"Student {student_id}   |   Balance: £{summary['balance']:.2f}"
                 f"   |   Hall: {hall or '—'}",
            font=("TkDefaultFont", 11, "bold"),
        )
        header.pack(anchor="w", padx=12, pady=(12, 6))

        holds = summary.get("active_holds") or []
        if holds:
            ttk.Label(win, text=f"Active holds ({len(holds)}):",
                      foreground="#a00").pack(anchor="w", padx=12)
            for h in holds:
                ttk.Label(
                    win,
                    text=f"  • {h.get('source')} — {h.get('reason')} "
                         f"(£{float(h.get('amount') or 0):.2f})"
                ).pack(anchor="w", padx=12)
        else:
            ttk.Label(win, text="No active holds.",
                      foreground="#070").pack(anchor="w", padx=12)

        ttk.Separator(win).pack(fill="x", padx=8, pady=6)

        totals = summary.get("totals_by_source") or {}
        ttk.Label(win, text="Charges by source (last 365 days):",
                  font=("TkDefaultFont", 10, "bold")
                  ).pack(anchor="w", padx=12)
        if totals:
            for src, amt in sorted(totals.items(),
                                   key=lambda kv: -kv[1]):
                ttk.Label(win, text=f"  • {src}: £{amt:.2f}"
                          ).pack(anchor="w", padx=12)
        else:
            ttk.Label(win, text="  (none)").pack(anchor="w", padx=12)

        ttk.Separator(win).pack(fill="x", padx=8, pady=6)

        ttk.Label(win,
                  text=f"SU clubs ({len(clubs)}) — recent SU charges "
                       f"({len(su_charges)}):",
                  font=("TkDefaultFont", 10, "bold")
                  ).pack(anchor="w", padx=12)
        for c in clubs[:10]:
            ttk.Label(win,
                      text=f"  • {c.get('name')} ({c.get('category') or '—'})"
                      ).pack(anchor="w", padx=12)

        ttk.Button(win, text="Close",
                   command=win.destroy).pack(pady=10)
