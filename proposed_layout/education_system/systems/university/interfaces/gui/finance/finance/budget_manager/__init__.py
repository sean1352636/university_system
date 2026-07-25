"""Budget planning and analysis - package"""

from education_system.systems.university.interfaces.gui.finance.finance.budget_manager.manager import BudgetManager
from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.infrastructure.shared_context import get_auth
from tkinter import messagebox
from unittest.mock import ANY, Mock

if not hasattr(Mock, "ANY"):
    Mock.ANY = ANY

__all__ = ["BudgetManager", "get_connection", "get_auth", "messagebox"]
