"""Finance System GUI Module

Modular finance management system with separate manager classes
for different functionality areas.
"""

from university_system.modules.domain.finance.gui.finance.finance_gui import FinanceGUI
from university_system.modules.domain.finance.gui.finance.db_manager import DatabaseManager
from university_system.modules.domain.finance.gui.finance.layout_manager import LayoutManager
from university_system.modules.domain.finance.gui.finance.dashboard import DashboardManager
from university_system.modules.domain.finance.gui.finance.budget_manager import BudgetManager
from university_system.modules.domain.finance.gui.finance.transaction_manager import TransactionManager
from university_system.modules.domain.finance.gui.finance.invoice_manager import InvoiceManager
from university_system.modules.domain.finance.gui.finance.expense_manager import ExpenseManager
from university_system.modules.domain.finance.gui.finance.report_manager import ReportManager
from university_system.modules.domain.finance.gui.finance.analytics import AnalyticsManager
from university_system.modules.domain.finance.gui.finance.compliance import ComplianceManager
from university_system.modules.domain.finance.gui.finance.settings import SettingsManager

__all__ = [
    'FinanceGUI',
    'DatabaseManager',
    'LayoutManager',
    'DashboardManager',
    'BudgetManager',
    'TransactionManager',
    'InvoiceManager',
    'ExpenseManager',
    'ReportManager',
    'AnalyticsManager',
    'ComplianceManager',
    'SettingsManager',
]
