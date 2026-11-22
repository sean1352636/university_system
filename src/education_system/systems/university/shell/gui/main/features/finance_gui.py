# Auto-generated module
import tkinter as tk
from tkinter import ttk, messagebox
import logging
from education_system.platform.delivery.gui.tk_callback_filter import install_clean_close as _install_clean_close

# Alias for translation function (underscore names not exported by import *)
from education_system.systems.university.infrastructure.i18n import get_text as _t

# Import database connection
from education_system.systems.university.infrastructure.database.db import get_db_connection, get_connection, transaction

# Import GUI availability flags and classes
from education_system.systems.university.shell.gui.main.imports.gui_imports import (
    FINANCE_REPORTING_GUI_AVAILABLE,
    FinancialManagementGUI,
    FinancialAidGUI,
)

logger = logging.getLogger(__name__)

def show_finance_management(self):
    """Launch the Finance Management GUI in a child window, fallback to CLI if needed."""
    if self.finance_gui:
        self.finance_gui.show_finance_management()
    else:
        try:
            from education_system.systems.university.domains.finance.interfaces.cli.menu import display_finance_menu
            from education_system.systems.university.domains.finance.domain.core.financial_core import set_finance_auth
            if self.auth:
                try:
                    set_finance_auth(self.auth)
                except Exception as e:
                    logger.warning(f"Failed to set finance auth: {e}")
            display_finance_menu(self.auth)
        except ImportError:
            messagebox.showerror(_t("finance_gui.errors.title"), _t("finance_gui.errors.gui_and_cli_unavailable"))
def show_finance_reporting_dashboard(self):
    """Launch the Finance Reporting Dashboard GUI in a child window."""
    try:
        if not FINANCE_REPORTING_GUI_AVAILABLE:
            messagebox.showerror(_t("finance_gui.errors.title"), _t("finance_gui.errors.reporting_unavailable"))
            return

        # Create new window for Finance Reporting
        finance_window = tk.Toplevel(self.root)
        _install_clean_close(finance_window)
        finance_window.title(_t("finance_gui.reporting.title"))
        finance_window.geometry("1200x800")

        # Initialize Finance Reporting GUI
        finance_gui = FinancialManagementGUI(finance_window, self.auth)
        print("✅ Finance Reporting GUI opened successfully")

    except Exception as e:
        messagebox.showerror(_t("finance_gui.errors.title"), _t("finance_gui.errors.failed_to_open_reporting", error=str(e)))
        print(f"❌ Finance Reporting error: {e}")
def show_student_finance_account(self):
    """Open My Finance Account (balance, top-ups, send money, transactions,
    spending summary) for the signed-in user's own account."""
    if not self.auth or not self.auth.current_user:
        messagebox.showerror(_t("common.error"), _t("finance_gui.errors.login_required"))
        return
    from education_system.systems.university.domains.finance.interfaces.gui.finance_account import (
        build_finance_account,
    )
    account_window = tk.Toplevel(self.root)
    _install_clean_close(account_window)
    account_window.title(_t("finance_gui.account.title"))
    account_window.geometry("1000x800")
    account_window.minsize(900, 700)
    if build_finance_account(account_window, self.auth) is None:
        account_window.destroy()
def show_financial_aid(self):
    """Launch the Financial Aid & Scholarships GUI in a child window."""
    if not self.auth.current_user:
        messagebox.showerror(_t("finance_gui.errors.title"), _t("finance_gui.errors.login_required_aid", default="Login Required Aid"))
        return

    try:
        # Create new window for Financial Aid
        aid_window = tk.Toplevel(self.root)
        _install_clean_close(aid_window)
        aid_window.title(_t("finance_gui.aid.title", default="===== AID ====="))
        aid_window.geometry("1200x800")

        # FinancialAidGUI is a lazy-loaded import — the module-level binding in
        # gui_imports.py starts as None and is only populated when
        # _lazy_import('FinancialAidGUI') is called, so `from ... import
        # FinancialAidGUI` at the top of this file captures None. Resolve the
        # class via the lazy loader at call time instead.
        from education_system.systems.university.shell.gui.main.imports.gui_imports import _lazy_import
        AidCls = _lazy_import('FinancialAidGUI')
        if AidCls is None:
            messagebox.showerror(
                _t("finance_gui.errors.title"),
                _t("finance_gui.errors.failed_to_open_aid",
                   error="FinancialAidGUI module is not available", default="Failed To Open Aid {error}"),
            )
            return

        aid_gui = AidCls(auth_instance=self.auth, parent=aid_window)
        aid_gui.create_embedded_interface()
        print("✅ Financial Aid GUI opened successfully")

    except Exception as e:
        messagebox.showerror(_t("finance_gui.errors.title"), _t("finance_gui.errors.failed_to_open_aid", error=str(e), default="Failed To Open Aid {error}"))
        print(f"❌ Financial Aid error: {e}")
def show_club_payment_management(self):
    """Launch the Club Payment Management interface in a child window."""
    if not self.auth.current_user:
        messagebox.showerror(_t("finance_gui.errors.title"), _t("finance_gui.errors.login_required_club_payment", default="Login Required Club Payment"))
        return

    try:
        # Create new window for Club Payment Management
        payment_window = tk.Toplevel(self.root)
        _install_clean_close(payment_window)
        payment_window.title(_t("finance_gui.club_payment.title", default="===== CLUB PAYMENT ====="))
        payment_window.geometry("1200x800")

        # Create main frame
        main_frame = ttk.Frame(payment_window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = ttk.Label(main_frame, text=_t("finance_gui.club_payment.header", default="Header"),
                               font=('Arial', 16, 'bold'))
        title_label.pack(pady=10)

        # Create notebook for different sections
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=10)

        # Payment Overview Tab
        overview_frame = ttk.Frame(notebook, padding="10")
        notebook.add(overview_frame, text=_t("finance_gui.club_payment.tabs.overview", default="Overview"))
        self._create_payment_overview_tab_finance(overview_frame)

        # Record Payment Tab
        record_frame = ttk.Frame(notebook, padding="10")
        notebook.add(record_frame, text=_t("finance_gui.club_payment.tabs.record", default="Record"))
        self._create_record_payment_tab_finance(record_frame)

        # Payment History Tab
        history_frame = ttk.Frame(notebook, padding="10")
        notebook.add(history_frame, text=_t("finance_gui.club_payment.tabs.history", default="History"))
        self._create_payment_history_tab_finance(history_frame)

        print("✅ Club Payment Management opened successfully")

    except Exception as e:
        messagebox.showerror(_t("finance_gui.errors.title"), _t("finance_gui.errors.failed_to_open_club_payment", error=str(e), default="Failed To Open Club Payment {error}"))
        print(f"❌ Club Payment Management error: {e}")
def _create_payment_overview_tab_finance(self, parent):
    """Create payment overview tab for club payments"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get summary statistics
        cursor.execute('''
            SELECT
                COUNT(*) as total_payments,
                SUM(amount) as total_amount,
                COUNT(DISTINCT reference_id) as clubs_with_payments
            FROM payments
            WHERE source_type = 'club'
              AND payment_date >= date('now', '-30 days')
        ''')
        stats = cursor.fetchone()

        # Display statistics
        stats_frame = ttk.LabelFrame(parent, text=_t("finance_gui.club_payment.stats_section", default="Stats Section"), padding="10")
        stats_frame.pack(fill=tk.X, pady=10)

        if stats:
            ttk.Label(stats_frame, text=_t("finance_gui.club_payment.total_payments", count=stats[0] or 0, default="Total Payments {count}"),
                     font=('Arial', 12)).pack(anchor='w', pady=5)
            ttk.Label(stats_frame, text=_t("finance_gui.club_payment.total_amount", amount=f"{stats[1] or 0:.2f}", default="Total Amount {amount}"),
                     font=('Arial', 12)).pack(anchor='w', pady=5)
            ttk.Label(stats_frame, text=_t("finance_gui.club_payment.clubs_with_payments", count=stats[2] or 0, default="Clubs With Payments {count}"),
                     font=('Arial', 12)).pack(anchor='w', pady=5)

        conn.close()

    except Exception as e:
        ttk.Label(parent, text=_t("finance_gui.errors.loading_stats", error=str(e), default="Loading Stats {error}")).pack()
def _create_record_payment_tab_finance(self, parent):
    """Create tab for recording new club payments"""
    ttk.Label(parent, text=_t("finance_gui.club_payment.record_description", default="Record Description"),
             font=('Arial', 12)).pack(pady=20)
    ttk.Label(parent, text=_t("finance_gui.club_payment.integration_note", default="Integration Note"),
             font=('Arial', 10), foreground='gray').pack()
def _create_payment_history_tab_finance(self, parent):
    """Create tab for viewing payment history"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Create treeview for payment history
        columns = ('Date', 'Club', 'Amount', 'Type', 'Status')
        tree = ttk.Treeview(parent, columns=columns, show='headings', height=15)

        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=150)

        tree.pack(fill=tk.BOTH, expand=True, pady=10)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(parent, orient='vertical', command=tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.configure(yscrollcommand=scrollbar.set)

        # Load recent payments
        cursor.execute('''
            SELECT cp.payment_date, sc.club_name, cp.amount, cp.payment_type, cp.status
            FROM payments cp
            JOIN student_clubs sc ON CAST(cp.reference_id AS INTEGER) = sc.club_id
            WHERE cp.source_type = 'club'
            ORDER BY cp.payment_date DESC
            LIMIT 100
        ''')
        payments = cursor.fetchall()

        for payment in payments:
            tree.insert('', tk.END, values=payment)

        conn.close()

    except Exception as e:
        ttk.Label(parent, text=_t("finance_gui.errors.loading_history", error=str(e), default="Loading History {error}")).pack()

def show_bank_app_gui(self):
    """Student Bank was merged into My Finance Account (2026-10-18); anything
    still calling this opens that screen."""
    self.show_student_finance_account()
