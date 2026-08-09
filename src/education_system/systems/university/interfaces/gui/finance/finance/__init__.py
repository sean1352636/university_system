"""Finance System GUI Module

Modular finance management system with separate manager classes
for different functionality areas.
"""

from education_system.systems.university.interfaces.gui.finance.finance.finance_gui import FinanceGUI
from education_system.systems.university.interfaces.gui.finance.finance.db_manager import DatabaseManager
from education_system.systems.university.interfaces.gui.finance.finance.layout import LayoutManager
from education_system.systems.university.interfaces.gui.finance.finance.dashboard import DashboardManager
from education_system.systems.university.interfaces.gui.finance.finance.budget_manager import BudgetManager
from education_system.systems.university.interfaces.gui.finance.finance.transaction_manager import TransactionManager
from education_system.systems.university.interfaces.gui.finance.finance.invoice_manager import InvoiceManager
from education_system.systems.university.interfaces.gui.finance.finance.expense_manager import ExpenseManager
from education_system.systems.university.interfaces.gui.finance.finance.report_manager import ReportManager
from education_system.systems.university.interfaces.gui.finance.finance.analytics import AnalyticsManager
from education_system.systems.university.interfaces.gui.finance.finance.compliance import CollectionsManager
from education_system.systems.university.interfaces.gui.finance.finance.settings import SettingsManager

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
    'CollectionsManager',
    'SettingsManager',
]
