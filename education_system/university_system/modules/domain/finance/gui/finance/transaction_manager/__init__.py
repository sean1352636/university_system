"""Transaction manager package - split from monolithic transaction_manager.py"""

from education_system.university_system.modules.domain.finance.gui.finance.transaction_manager.transaction_manager import TransactionManager
from tkinter import messagebox

__all__ = ['TransactionManager', 'messagebox']
