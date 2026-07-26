"""Transaction manager package - split from monolithic transaction_manager.py"""

from education_system.systems.university.interfaces.gui.finance.finance.transaction_manager.transaction_manager import TransactionManager
from education_system.systems.university.interfaces.gui.finance.finance.transaction_manager._imports import (
    tk,
    ttk,
    messagebox,
    get_connection,
)

__all__ = ['TransactionManager', 'tk', 'ttk', 'messagebox', 'get_connection']
