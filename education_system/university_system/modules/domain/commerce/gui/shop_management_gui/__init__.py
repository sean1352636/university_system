"""
Re-export the main GUI class for backwards compatibility.
Importers should use direct submodule imports for other symbols, e.g.:
    from education_system.university_system.modules.domain.commerce.gui.shop_management_gui.discount_manager import DiscountEditDialog
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
