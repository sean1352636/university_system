"""Betting Shop Core Services Module"""

from education_system.systems.university.plugins.campus_commerce.domain.betting.services.betting_core import (
    AccountManager,
    SportsBettingManager,
    PredictionMarketManager,
    CasinoManager,
    ReportManager,
    init_betting_db,
    generate_reference,
    MIN_BET,
    MAX_BET,
    MIN_DEPOSIT,
    MAX_DEPOSIT,
    CASINO_GAMES,
    PREDICTION_CATEGORIES,
    BET_STATUSES
)

__all__ = [
    'AccountManager',
    'SportsBettingManager',
    'PredictionMarketManager',
    'CasinoManager',
    'ReportManager',
    'init_betting_db',
    'generate_reference',
    'MIN_BET',
    'MAX_BET',
    'MIN_DEPOSIT',
    'MAX_DEPOSIT',
    'CASINO_GAMES',
    'PREDICTION_CATEGORIES',
    'BET_STATUSES'
]
