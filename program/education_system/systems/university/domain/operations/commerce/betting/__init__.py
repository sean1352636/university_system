"""
Betting Shop Module

Provides comprehensive betting shop functionality including sports betting,
prediction markets, casino games, and account management with email
and finance integration.
"""

from education_system.systems.university.domain.operations.commerce.betting.services.betting_core import (
    AccountManager,
    SportsBettingManager,
    PredictionMarketManager,
    CasinoManager,
    ReportManager,
    init_betting_db,
    MIN_BET,
    MAX_BET,
    CASINO_GAMES,
    PREDICTION_CATEGORIES
)

__all__ = [
    'BettingShopGUI',
    'launch_betting_shop_gui',
    'AccountManager',
    'SportsBettingManager',
    'PredictionMarketManager',
    'CasinoManager',
    'ReportManager',
    'init_betting_db',
    'MIN_BET',
    'MAX_BET',
    'CASINO_GAMES',
    'PREDICTION_CATEGORIES'
]

# The GUI classes live in the interfaces layer, which imports back into this
# domain package, so an eager re-export here is a circular import. PEP 562
# lazy lookup keeps these names on the package's public surface without the
# cycle: the interfaces module is only imported on first attribute access.
_LAZY_GUI_EXPORTS = {
    "BettingShopGUI": "education_system.systems.university.interfaces.gui.operations.commerce.betting.betting_shop_gui",
    "launch_betting_shop_gui": "education_system.systems.university.interfaces.gui.operations.commerce.betting.betting_shop_gui",
}


def __getattr__(name: str):
    module_path = _LAZY_GUI_EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib
    value = getattr(importlib.import_module(module_path), name)
    globals()[name] = value  # cache so subsequent access skips __getattr__
    return value
