"""
Butchers Shop Module

Provides comprehensive butcher shop management including
products, orders, inventory, and transaction management
with email and finance integration.
"""

from education_system.systems.university.domain.operations.commerce.butcher.services.butcher_core import (
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

# The GUI classes live in the interfaces layer, which imports back into this
# domain package, so an eager re-export here is a circular import. PEP 562
# lazy lookup keeps these names on the package's public surface without the
# cycle: the interfaces module is only imported on first attribute access.
_LAZY_GUI_EXPORTS = {
    "ButcherGUI": "education_system.systems.university.interfaces.gui.operations.commerce.butcher.butcher_gui",
    "launch_butcher_gui": "education_system.systems.university.interfaces.gui.operations.commerce.butcher.butcher_gui",
}


def __getattr__(name: str):
    module_path = _LAZY_GUI_EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib
    value = getattr(importlib.import_module(module_path), name)
    globals()[name] = value  # cache so subsequent access skips __getattr__
    return value
