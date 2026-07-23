"""
Betting Shop Module

Provides comprehensive betting shop functionality including sports betting,
prediction markets, casino games, and account management with email
and finance integration.
"""

from education_system.post_18.university_system.modules.domain.commerce.betting.gui.betting_shop_gui import (
    BettingShopGUI,
    launch_betting_shop_gui
)
from education_system.post_18.university_system.modules.domain.commerce.betting.services.betting_core import (
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
