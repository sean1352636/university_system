"""
Portfolio Module - Achievement & Portfolio System

Comprehensive digital portfolio management system for students.
"""

from education_system.systems.university.domain.progression.portfolio.services.portfolio_service import PortfolioService
from education_system.systems.university.interfaces.cli.progression.portfolio.portfolio_cli import PortfolioCLI

__all__ = ['PortfolioService', 'PortfolioCLI', 'PortfolioGUI']

# The GUI classes live in the interfaces layer, which imports back into this
# domain package, so an eager re-export here is a circular import. PEP 562
# lazy lookup keeps these names on the package's public surface without the
# cycle: the interfaces module is only imported on first attribute access.
_LAZY_GUI_EXPORTS = {
    "PortfolioGUI": "education_system.systems.university.interfaces.gui.progression.portfolio.portfolio_gui",
}


def __getattr__(name: str):
    module_path = _LAZY_GUI_EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib
    value = getattr(importlib.import_module(module_path), name)
    globals()[name] = value  # cache so subsequent access skips __getattr__
    return value
