"""Finance System GUI Module

Modular finance management system with separate manager classes
for different functionality areas.
"""

from education_system.university_system.modules.domain.finance.gui.finance.finance_gui import FinanceGUI
from education_system.university_system.modules.domain.finance.gui.finance.db_manager import DatabaseManager
from education_system.university_system.modules.domain.finance.gui.finance.layout import LayoutManager
from education_system.university_system.modules.domain.finance.gui.finance.dashboard import DashboardManager
from education_system.university_system.modules.domain.finance.gui.finance.budget_manager import BudgetManager
from education_system.university_system.modules.domain.finance.gui.finance.transaction_manager import TransactionManager
from education_system.university_system.modules.domain.finance.gui.finance.invoice_manager import InvoiceManager
from education_system.university_system.modules.domain.finance.gui.finance.expense_manager import ExpenseManager
from education_system.university_system.modules.domain.finance.gui.finance.report_manager import ReportManager
from education_system.university_system.modules.domain.finance.gui.finance.analytics import AnalyticsManager
from education_system.university_system.modules.domain.finance.gui.finance.compliance import CollectionsManager
from education_system.university_system.modules.domain.finance.gui.finance.settings import SettingsManager

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
