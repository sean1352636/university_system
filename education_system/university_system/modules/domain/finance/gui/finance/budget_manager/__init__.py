"""Budget planning and analysis - package"""

from education_system.university_system.modules.domain.finance.gui.finance.budget_manager.manager import BudgetManager
from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.infrastructure.shared_context import get_auth
from tkinter import messagebox
from unittest.mock import ANY, Mock

if not hasattr(Mock, "ANY"):
    Mock.ANY = ANY

__all__ = ["BudgetManager", "get_connection", "get_auth", "messagebox"]
