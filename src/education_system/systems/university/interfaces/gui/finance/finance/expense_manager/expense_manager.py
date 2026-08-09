"""Fee and expense management - main facade class"""

from education_system.systems.university.interfaces.gui.finance.finance.expense_manager._imports import (
    get_global_auth,
)
from education_system.systems.university.interfaces.gui.finance.finance.expense_manager.fee_types import FeeTypesMixin
from education_system.systems.university.interfaces.gui.finance.finance.expense_manager.fee_assignment import FeeAssignmentMixin
from education_system.systems.university.interfaces.gui.finance.finance.expense_manager.late_fees import LateFeesMixin


class ExpenseManager(
    FeeTypesMixin,
    FeeAssignmentMixin,
    LateFeesMixin,
):
    """Fee and expense management"""

    def __init__(self, gui):
        """Initialize manager with reference to main GUI"""
        self.gui = gui
        self.root = gui.root
        self.conn = gui.conn
        try:
            self.finance_system = gui.finance_system
        except Exception:
            self.finance_system = None
