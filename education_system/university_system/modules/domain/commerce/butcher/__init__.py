"""
Butchers Shop Module

Provides comprehensive butcher shop management including
products, orders, inventory, and transaction management
with email and finance integration.
"""

from education_system.university_system.modules.domain.commerce.butcher.gui.butcher_gui import (
    ButcherGUI,
    launch_butcher_gui
)
from education_system.university_system.modules.domain.commerce.butcher.services.butcher_core import (
    ProductManager,
    OrderManager,
    TransactionManager,
    ReportManager,
    init_butcher_db,
    MEAT_CATEGORIES,
    ORDER_STATUSES
)

__all__ = [
    'ButcherGUI',
    'launch_butcher_gui',
    'ProductManager',
    'OrderManager',
    'TransactionManager',
    'ReportManager',
    'init_butcher_db',
    'MEAT_CATEGORIES',
    'ORDER_STATUSES'
]
