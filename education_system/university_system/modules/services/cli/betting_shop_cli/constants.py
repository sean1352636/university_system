"""
Betting Shop CLI - Constants, imports, and fallback database initialization.
"""

import logging
import random
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict

from education_system.university_system.core.sql_safety import validate_identifier

# Import centralized database and authentication
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.infrastructure.shared_context import get_auth

# Import betting core services
try:
    from education_system.university_system.modules.domain.betting.services.betting_core import (
        init_betting_db, AccountManager, SportsBettingManager,
        PredictionMarketManager, CasinoManager, ReportManager,
        MIN_BET, MAX_BET, MIN_DEPOSIT, MAX_DEPOSIT,
        CASINO_GAMES, PREDICTION_CATEGORIES, BET_STATUSES
    )
    BETTING_CORE_AVAILABLE = True
except ImportError:
    BETTING_CORE_AVAILABLE = False
    MIN_BET = 1.00
    MAX_BET = 500.00
    MIN_DEPOSIT = 10.00
    MAX_DEPOSIT = 1000.00
    CASINO_GAMES = ['slots', 'blackjack', 'roulette', 'poker']
    PREDICTION_CATEGORIES = ['sports', 'politics', 'entertainment', 'academic', 'other']
    BET_STATUSES = ['pending', 'won', 'lost', 'void', 'cashed_out']

    def init_betting_db():
        """Fallback database initialization"""
        try:
            with transaction() as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS betting_accounts (
                        account_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT UNIQUE NOT NULL,
                        username TEXT NOT NULL,
                        email TEXT,
                        balance DECIMAL(10,2) DEFAULT 0.00,
                        total_deposited DECIMAL(10,2) DEFAULT 0.00,
                        total_withdrawn DECIMAL(10,2) DEFAULT 0.00,
                        total_wagered DECIMAL(10,2) DEFAULT 0.00,
                        total_won DECIMAL(10,2) DEFAULT 0.00,
                        status TEXT DEFAULT 'active',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                conn.execute('''
                    CREATE TABLE IF NOT EXISTS betting_events (
                        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_name TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        sport_type TEXT,
                        team_a TEXT,
                        team_b TEXT,
                        odds_a DECIMAL(6,2) DEFAULT 2.00,
                        odds_b DECIMAL(6,2) DEFAULT 2.00,
                        odds_draw DECIMAL(6,2),
                        event_date TEXT NOT NULL,
                        status TEXT DEFAULT 'upcoming',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                conn.execute('''
                    CREATE TABLE IF NOT EXISTS sports_bets (
                        bet_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        event_id INTEGER NOT NULL,
                        bet_type TEXT NOT NULL,
                        selection TEXT NOT NULL,
                        odds DECIMAL(6,2) NOT NULL,
                        stake DECIMAL(10,2) NOT NULL,
                        potential_return DECIMAL(10,2) NOT NULL,
                        status TEXT DEFAULT 'pending',
                        placed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (event_id) REFERENCES betting_events(event_id)
                    )
                ''')

                conn.execute('''
                    CREATE TABLE IF NOT EXISTS betting_transactions (
                        transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        transaction_type TEXT NOT NULL,
                        amount DECIMAL(10,2) NOT NULL,
                        description TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                conn.execute('''
                    CREATE TABLE IF NOT EXISTS prediction_markets (
                        market_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT NOT NULL,
                        description TEXT,
                        category TEXT NOT NULL,
                        outcome_a TEXT NOT NULL,
                        outcome_b TEXT NOT NULL,
                        probability_a DECIMAL(5,2) DEFAULT 50.00,
                        probability_b DECIMAL(5,2) DEFAULT 50.00,
                        total_pool DECIMAL(10,2) DEFAULT 0.00,
                        resolution_date TEXT NOT NULL,
                        status TEXT DEFAULT 'open',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                conn.execute('''
                    CREATE TABLE IF NOT EXISTS prediction_bets (
                        bet_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        market_id INTEGER NOT NULL,
                        selection TEXT NOT NULL,
                        stake DECIMAL(10,2) NOT NULL,
                        odds_at_placement DECIMAL(6,2) NOT NULL,
                        potential_return DECIMAL(10,2) NOT NULL,
                        status TEXT DEFAULT 'pending',
                        placed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (market_id) REFERENCES prediction_markets(market_id)
                    )
                ''')

                conn.execute('''
                    CREATE TABLE IF NOT EXISTS casino_games (
                        game_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        game_type TEXT NOT NULL,
                        bet_amount DECIMAL(10,2) NOT NULL,
                        result TEXT NOT NULL,
                        win_amount DECIMAL(10,2) DEFAULT 0.00,
                        game_data TEXT,
                        played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                conn.execute('''
                    CREATE TABLE IF NOT EXISTS casino_sessions (
                        session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        game_type TEXT NOT NULL,
                        start_balance DECIMAL(10,2) NOT NULL,
                        end_balance DECIMAL(10,2),
                        total_wagered DECIMAL(10,2) DEFAULT 0.00,
                        total_won DECIMAL(10,2) DEFAULT 0.00,
                        hands_played INTEGER DEFAULT 0,
                        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        ended_at TIMESTAMP,
                        status TEXT DEFAULT 'active'
                    )
                ''')

            return True
        except Exception as e:
            logging.error(f"Database initialization error: {e}")
            return False

# Import email service
try:
    from education_system.university_system.infrastructure.email.email_service import send_email
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False

# Import finance integration
try:
    from education_system.university_system.modules.shared.utils.finance_integration import (
        record_payment_to_finance,
        process_student_finance_account_payment
    )
    FINANCE_AVAILABLE = True
except ImportError:
    FINANCE_AVAILABLE = False

logger = logging.getLogger(__name__)
