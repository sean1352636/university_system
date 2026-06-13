"""Shop management GUI package — public API.

Aggregates the package's main app class (``UniversityShopGUI``) and the
high-level entry points (``run_gui_mode``, ``run_cli_mode``,
``integrate_gui_with_main``) so the canonical import is:

    from education_system.university_system.modules.domain.commerce.gui.shop_management_gui \\
        import UniversityShopGUI, run_gui_mode

Sub-area dialogs (discount editor, product/inventory/order/report managers,
auth helper, email notifications, utils) live in sibling modules — import
those directly when you need them, e.g.::

    from .discount_manager import DiscountEditDialog

This is the canonical aggregator, not a deprecated shim.
"""

from education_system.university_system.modules.domain.commerce.gui.shop_management_gui.main_gui import (
    UniversityShopGUI,
    integrate_gui_with_main,
    run_cli_mode,
    run_gui_mode,
)

__all__ = [
    "UniversityShopGUI",
    "run_gui_mode",
    "run_cli_mode",
    "integrate_gui_with_main",
]
