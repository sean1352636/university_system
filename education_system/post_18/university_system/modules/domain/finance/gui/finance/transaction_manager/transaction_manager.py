"""Payment and transaction processing - main facade class"""

import sys

from education_system.post_18.university_system.modules.domain.finance.gui.finance.transaction_manager._imports import (
    tk, ttk, _, get_connection, get_global_auth,
)
from education_system.post_18.university_system.modules.domain.finance.gui.finance.transaction_manager.payments_tab import PaymentsTabMixin
from education_system.post_18.university_system.modules.domain.finance.gui.finance.transaction_manager.payment_recording import PaymentRecordingMixin
from education_system.post_18.university_system.modules.domain.finance.gui.finance.transaction_manager.payment_search import PaymentSearchMixin
from education_system.post_18.university_system.modules.domain.finance.gui.finance.transaction_manager.refunds import RefundsMixin
from education_system.post_18.university_system.modules.domain.finance.gui.finance.transaction_manager.payment_plans import PaymentPlansMixin
from education_system.post_18.university_system.modules.domain.finance.gui.finance.transaction_manager.student_credits import StudentCreditsMixin
from education_system.post_18.university_system.modules.domain.finance.gui.finance.transaction_manager.analytics_email import AnalyticsEmailMixin
from education_system.post_18.university_system.modules.domain.finance.gui.finance.transaction_manager.financial_statement import FinancialStatementMixin
from education_system.post_18.university_system.modules.domain.finance.gui.finance.transaction_manager.gateway_wrappers import GatewayWrappersMixin


class TransactionManager(
    PaymentsTabMixin,
    PaymentRecordingMixin,
    PaymentSearchMixin,
    RefundsMixin,
    PaymentPlansMixin,
    StudentCreditsMixin,
    AnalyticsEmailMixin,
    FinancialStatementMixin,
    GatewayWrappersMixin,
):
    """Payment and transaction processing"""

    def __init__(self, gui):
        """Initialize manager with reference to main GUI"""
        self.gui = gui
        self.root = gui.root
        self.conn = gui.conn
        self.finance_system = vars(gui).get('finance_system')

    def create_core_finance_tab(self):
        """Create core finance operations tab"""
        tab = tk.Frame(self.gui.layout.content_frame, bg='white')
        self.gui.layout.tab_frames['core_finance'] = tab

        # Create scrollable frame
        canvas = tk.Canvas(tab)
        scrollbar = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Button frame
        button_frame = ttk.LabelFrame(scrollable_frame, text=_("finance_gui.transaction_manager.core_finance_frame"), padding=20)
        button_frame.pack(fill='x', padx=20, pady=10)

        buttons = [
            (_("finance_gui.transaction_manager.btn_assign_fees"), self.gui.expenses.gui_assign_fees_to_student, "#3498db"),
            (_("finance_gui.transaction_manager.btn_record_payment"), self.gui_record_payment, "#27ae60"),
            (_("finance_gui.transaction_manager.btn_generate_invoice"), self.gui.invoices.gui_generate_invoice, "#e74c3c"),
            (_("finance_gui.transaction_manager.btn_process_refund_full"), self.gui_process_refund, "#f39c12"),
            (_("finance_gui.transaction_manager.btn_manage_credits"), self.gui_manage_student_credits, "#9b59b6"),
            (_("finance_gui.transaction_manager.btn_view_statement"), self.gui_view_student_financial_statement, "#34495e")
        ]

        for i, (text, command, color) in enumerate(buttons):
            btn = tk.Button(button_frame, text=text, command=command,
                          font=('Arial', 12, 'bold'), bg=color, fg='white',
                          width=35, height=2, relief='raised', bd=3)
            btn.grid(row=i//2, column=i%2, padx=10, pady=10, sticky='ew')

        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)

        # Quick stats frame
        stats_frame = ttk.LabelFrame(scrollable_frame, text=_("finance_gui.transaction_manager.quick_stats_frame"), padding=20)
        stats_frame.pack(fill='x', padx=20, pady=10)

        self.stats_labels = {}
        self.update_quick_stats(stats_frame)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    # Helper methods
    @staticmethod
    def _transaction_manager_package():
        return sys.modules.get(
            'education_system.post_18.university_system.modules.domain.finance.gui.finance.transaction_manager'
        )

    @classmethod
    def _get_connection(cls):
        package = cls._transaction_manager_package()
        factory = getattr(package, 'get_connection', get_connection) if package else get_connection
        return factory()

    def update_status(self, message):
        """Update status bar message"""
        try:
            if hasattr(self.gui, 'layout') and hasattr(self.gui.layout, 'update_status'):
                self.gui.layout.update_status(message)
            elif hasattr(self.gui, 'update_status'):
                self.gui.update_status(message)
            else:
                print(f"Status: {message}")
        except Exception as e:
            print(f"Status update failed: {message} (Error: {e})")

    def refresh_dashboard(self):
        """Refresh the dashboard if it exists"""
        try:
            if hasattr(self.gui, 'dashboard') and hasattr(self.gui.dashboard, 'refresh_dashboard'):
                self.gui.dashboard.refresh_dashboard()
            elif hasattr(self.gui, 'refresh_dashboard'):
                self.gui.refresh_dashboard()
            else:
                # Dashboard not available, skip silently
                pass
        except Exception as e:
            print(f"Dashboard refresh failed: {e}")
