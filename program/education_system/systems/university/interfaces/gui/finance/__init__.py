"""
Finance GUI Module

This module provides all GUI components for finance management including:
- Finance Management GUI
- Finance Reporting GUI
- Financial Aid & Scholarships GUI
"""

from education_system.systems.university.interfaces.gui.finance.finance_management_gui import FinanceManagementGUI
from education_system.systems.university.interfaces.gui.finance.finance_reporting import FinancialManagementGUI

__all__ = [
    'FinanceManagementGUI',
    'FinancialManagementGUI',
]
