"""
Betting Shop Core - Business Logic Managers

Provides manager classes for sports betting, prediction markets,
casino games, and account management with database operations.
"""

import sqlite3
import random
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import uuid
import hashlib

from university_system.infrastructure.database.db import get_connection, transaction
from university_system.modules.shared.utils.activity_logger import log_activity


# Betting configuration
MIN_BET = 1.00
MAX_BET = 500.00
MIN_DEPOSIT = 10.00
MAX_DEPOSIT = 1000.00
HOUSE_EDGE = 0.05  # 5% house edge

# Sports betting odds types
ODDS_TYPES = ['decimal', 'fractional', 'american']

# Bet statuses
BET_STATUSES = ['pending', 'won', 'lost', 'void', 'cashed_out']

# Game types
CASINO_GAMES = ['slots', 'blackjack', 'roulette', 'poker']

# Prediction categories
PREDICTION_CATEGORIES = ['sports', 'politics', 'entertainment', 'academic', 'other']


def init_betting_db():
    """Initialize betting database tables"""
    try:
        with transaction() as conn:
            cursor = conn.cursor()

            # User betting accounts
            cursor.execute('''
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

            # Sports events for betting
            cursor.execute('''
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
                    event_time TEXT,
                    status TEXT DEFAULT 'upcoming',
                    result TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by TEXT
                )
            ''')

            # Sports bets
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sports_bets (
                    bet_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    event_id INTEGER NOT NULL,
                    bet_type TEXT NOT NULL,
                    selection TEXT NOT NULL,
                    odds DECIMAL(6,2) NOT NULL,
                    stake DECIMAL(10,2) NOT NULL,
                    potential_return DECIMAL(10,2) NOT NULL,
                    actual_return DECIMAL(10,2) DEFAULT 0.00,
                    status TEXT DEFAULT 'pending',
                    placed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    settled_at TIMESTAMP,
                    FOREIGN KEY (event_id) REFERENCES betting_events(event_id)
                )
            ''')

            # Prediction markets
            cursor.execute('''
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
                    pool_a DECIMAL(10,2) DEFAULT 0.00,
                    pool_b DECIMAL(10,2) DEFAULT 0.00,
                    resolution_date TEXT NOT NULL,
                    status TEXT DEFAULT 'open',
                    result TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by TEXT
                )
            ''')

            # Prediction bets
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS prediction_bets (
                    bet_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    market_id INTEGER NOT NULL,
                    selection TEXT NOT NULL,
                    stake DECIMAL(10,2) NOT NULL,
                    odds_at_placement DECIMAL(6,2) NOT NULL,
                    potential_return DECIMAL(10,2) NOT NULL,
                    actual_return DECIMAL(10,2) DEFAULT 0.00,
                    status TEXT DEFAULT 'pending',
                    placed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    settled_at TIMESTAMP,
                    FOREIGN KEY (market_id) REFERENCES prediction_markets(market_id)
                )
            ''')

            # Casino game sessions
            cursor.execute('''
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

            # Casino game history
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS casino_games (
                    game_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER,
                    user_id TEXT NOT NULL,
                    game_type TEXT NOT NULL,
                    bet_amount DECIMAL(10,2) NOT NULL,
                    result TEXT NOT NULL,
                    win_amount DECIMAL(10,2) DEFAULT 0.00,
                    game_data TEXT,
                    played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES casino_sessions(session_id)
                )
            ''')

            # Account transactions
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS betting_transactions (
                    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    transaction_type TEXT NOT NULL,
                    amount DECIMAL(10,2) NOT NULL,
                    balance_before DECIMAL(10,2) NOT NULL,
                    balance_after DECIMAL(10,2) NOT NULL,
                    reference TEXT,
                    description TEXT,
                    payment_method TEXT,
                    status TEXT DEFAULT 'completed',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed_by TEXT
                )
            ''')

            # Create indexes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_betting_accounts_user ON betting_accounts(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sports_bets_user ON sports_bets(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_casino_games_user ON casino_games(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_betting_events_date ON betting_events(event_date)')

            print("Betting database initialized successfully")
            return True

    except sqlite3.Error as e:
        print(f"Error initializing betting database: {e}")
        return False


def generate_reference() -> str:
    """Generate unique transaction reference"""
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    unique_id = uuid.uuid4().hex[:8].upper()
    return f"BET-{timestamp}-{unique_id}"


class AccountManager:
    """Manager for betting account operations"""

    @staticmethod
    def get_or_create_account(user_id: str, username: str, email: str = None) -> Dict:
        """Get existing account or create new one"""
        try:
            with get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM betting_accounts WHERE user_id = ?', (user_id,))
                account = cursor.fetchone()

                if account:
                    return dict(account)

            # Create new account
            with transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO betting_accounts (user_id, username, email)
                    VALUES (?, ?, ?)
                ''', (user_id, username, email))

                account_id = cursor.lastrowid

            log_activity('create', 'betting_account', details={'user_id': user_id})

            return {
                'account_id': account_id,
                'user_id': user_id,
                'username': username,
                'email': email,
                'balance': 0.00,
                'status': 'active'
            }

        except sqlite3.Error as e:
            print(f"Error getting/creating account: {e}")
            return None

    @staticmethod
    def get_account(user_id: str) -> Optional[Dict]:
        """Get account by user ID"""
        try:
            with get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM betting_accounts WHERE user_id = ?', (user_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except sqlite3.Error as e:
            print(f"Error getting account: {e}")
            return None

    @staticmethod
    def deposit(user_id: str, amount: float, payment_method: str, processed_by: str = None) -> Optional[int]:
        """Deposit funds to account"""
        if amount < MIN_DEPOSIT or amount > MAX_DEPOSIT:
            return None

        try:
            account = AccountManager.get_account(user_id)
            if not account:
                return None

            balance_before = account['balance']
            balance_after = balance_before + amount
            reference = generate_reference()

            with transaction() as conn:
                cursor = conn.cursor()

                # Update balance
                cursor.execute('''
                    UPDATE betting_accounts
                    SET balance = ?, total_deposited = total_deposited + ?, updated_at = ?
                    WHERE user_id = ?
                ''', (balance_after, amount, datetime.now().isoformat(), user_id))

                # Record transaction
                cursor.execute('''
                    INSERT INTO betting_transactions
                    (user_id, transaction_type, amount, balance_before, balance_after,
                     reference, description, payment_method, processed_by)
                    VALUES (?, 'deposit', ?, ?, ?, ?, ?, ?, ?)
                ''', (user_id, amount, balance_before, balance_after, reference,
                      f'Deposit via {payment_method}', payment_method, processed_by))

                transaction_id = cursor.lastrowid

            log_activity('deposit', 'betting_account', details={
                'user_id': user_id, 'amount': amount, 'reference': reference
            })

            return transaction_id

        except sqlite3.Error as e:
            print(f"Error depositing funds: {e}")
            return None

    @staticmethod
    def withdraw(user_id: str, amount: float, payment_method: str, processed_by: str = None) -> Optional[int]:
        """Withdraw funds from account"""
        try:
            account = AccountManager.get_account(user_id)
            if not account or account['balance'] < amount:
                return None

            balance_before = account['balance']
            balance_after = balance_before - amount
            reference = generate_reference()

            with transaction() as conn:
                cursor = conn.cursor()

                # Update balance
                cursor.execute('''
                    UPDATE betting_accounts
                    SET balance = ?, total_withdrawn = total_withdrawn + ?, updated_at = ?
                    WHERE user_id = ?
                ''', (balance_after, amount, datetime.now().isoformat(), user_id))

                # Record transaction
                cursor.execute('''
                    INSERT INTO betting_transactions
                    (user_id, transaction_type, amount, balance_before, balance_after,
                     reference, description, payment_method, processed_by)
                    VALUES (?, 'withdrawal', ?, ?, ?, ?, ?, ?, ?)
                ''', (user_id, amount, balance_before, balance_after, reference,
                      f'Withdrawal to {payment_method}', payment_method, processed_by))

                transaction_id = cursor.lastrowid

            log_activity('withdraw', 'betting_account', details={
                'user_id': user_id, 'amount': amount, 'reference': reference
            })

            return transaction_id

        except sqlite3.Error as e:
            print(f"Error withdrawing funds: {e}")
            return None

    @staticmethod
    def deduct_stake(user_id: str, amount: float, description: str = 'Bet placed') -> bool:
        """Deduct stake from account balance"""
        try:
            account = AccountManager.get_account(user_id)
            if not account or account['balance'] < amount:
                return False

            with transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE betting_accounts
                    SET balance = balance - ?, total_wagered = total_wagered + ?, updated_at = ?
                    WHERE user_id = ?
                ''', (amount, amount, datetime.now().isoformat(), user_id))

            return True

        except sqlite3.Error as e:
            print(f"Error deducting stake: {e}")
            return False

    @staticmethod
    def add_winnings(user_id: str, amount: float, description: str = 'Bet won') -> bool:
        """Add winnings to account balance"""
        try:
            with transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE betting_accounts
                    SET balance = balance + ?, total_won = total_won + ?, updated_at = ?
                    WHERE user_id = ?
                ''', (amount, amount, datetime.now().isoformat(), user_id))

            return True

        except sqlite3.Error as e:
            print(f"Error adding winnings: {e}")
            return False

    @staticmethod
    def get_transaction_history(user_id: str, limit: int = 50) -> List[Dict]:
        """Get transaction history for user"""
        try:
            with get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM betting_transactions
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                ''', (user_id, limit))
                return [dict(row) for row in cursor.fetchall()]

        except sqlite3.Error as e:
            print(f"Error getting transaction history: {e}")
            return []


class SportsBettingManager:
    """Manager for sports betting operations"""

    @staticmethod
    def create_event(event_name: str, event_type: str, sport_type: str,
                     team_a: str, team_b: str, odds_a: float, odds_b: float,
                     odds_draw: float = None, event_date: str = None,
                     event_time: str = None, created_by: str = None) -> Optional[int]:
        """Create a new betting event"""
        try:
            if not event_date:
                event_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')

            with transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO betting_events
                    (event_name, event_type, sport_type, team_a, team_b,
                     odds_a, odds_b, odds_draw, event_date, event_time, created_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (event_name, event_type, sport_type, team_a, team_b,
                      odds_a, odds_b, odds_draw, event_date, event_time, created_by))

                event_id = cursor.lastrowid

            log_activity('create', 'betting_event', details={'event_id': event_id, 'event_name': event_name})
            return event_id

        except sqlite3.Error as e:
            print(f"Error creating event: {e}")
            return None

    @staticmethod
    def get_upcoming_events(sport_type: str = None) -> List[Dict]:
        """Get upcoming events"""
        try:
            query = '''
                SELECT * FROM betting_events
                WHERE status = 'upcoming' AND event_date >= date('now')
            '''
            params = []

            if sport_type:
                query += ' AND sport_type = ?'
                params.append(sport_type)

            query += ' ORDER BY event_date, event_time'

            with get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]

        except sqlite3.Error as e:
            print(f"Error getting events: {e}")
            return []

    @staticmethod
    def get_event(event_id: int) -> Optional[Dict]:
        """Get event by ID"""
        try:
            with get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM betting_events WHERE event_id = ?', (event_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except sqlite3.Error as e:
            print(f"Error getting event: {e}")
            return None

    @staticmethod
    def place_bet(user_id: str, event_id: int, selection: str, stake: float) -> Optional[int]:
        """Place a sports bet"""
        if stake < MIN_BET or stake > MAX_BET:
            return None

        try:
            event = SportsBettingManager.get_event(event_id)
            if not event or event['status'] != 'upcoming':
                return None

            # Determine odds based on selection
            if selection == 'team_a':
                odds = event['odds_a']
            elif selection == 'team_b':
                odds = event['odds_b']
            elif selection == 'draw':
                odds = event['odds_draw'] or 3.50
            else:
                return None

            potential_return = round(stake * odds, 2)

            # Deduct stake from account
            if not AccountManager.deduct_stake(user_id, stake, f'Bet on {event["event_name"]}'):
                return None

            with transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO sports_bets
                    (user_id, event_id, bet_type, selection, odds, stake, potential_return)
                    VALUES (?, ?, 'single', ?, ?, ?, ?)
                ''', (user_id, event_id, selection, odds, stake, potential_return))

                bet_id = cursor.lastrowid

            log_activity('place_bet', 'sports_betting', details={
                'bet_id': bet_id, 'event_id': event_id, 'stake': stake
            })

            return bet_id

        except sqlite3.Error as e:
            print(f"Error placing bet: {e}")
            return None

    @staticmethod
    def get_user_bets(user_id: str, status: str = None) -> List[Dict]:
        """Get bets for a user"""
        try:
            query = '''
                SELECT sb.*, be.event_name, be.team_a, be.team_b, be.event_date
                FROM sports_bets sb
                JOIN betting_events be ON sb.event_id = be.event_id
                WHERE sb.user_id = ?
            '''
            params = [user_id]

            if status:
                query += ' AND sb.status = ?'
                params.append(status)

            query += ' ORDER BY sb.placed_at DESC'

            with get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]

        except sqlite3.Error as e:
            print(f"Error getting user bets: {e}")
            return []

    @staticmethod
    def cash_out_bet(bet_id: int, user_id: str) -> Optional[float]:
        """Cash out a pending bet early"""
        try:
            with get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM sports_bets WHERE bet_id = ? AND user_id = ? AND status = 'pending'
                ''', (bet_id, user_id))
                bet = cursor.fetchone()

            if not bet:
                return None

            # Calculate cash out value (75% of potential return as example)
            cash_out_value = round(bet['stake'] + (bet['potential_return'] - bet['stake']) * 0.5, 2)

            with transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE sports_bets
                    SET status = 'cashed_out', actual_return = ?, settled_at = ?
                    WHERE bet_id = ?
                ''', (cash_out_value, datetime.now().isoformat(), bet_id))

            # Add cash out amount to balance
            AccountManager.add_winnings(user_id, cash_out_value, 'Cash out')

            log_activity('cash_out', 'sports_betting', details={
                'bet_id': bet_id, 'cash_out_value': cash_out_value
            })

            return cash_out_value

        except sqlite3.Error as e:
            print(f"Error cashing out bet: {e}")
            return None

    @staticmethod
    def settle_event(event_id: int, result: str, settled_by: str = None) -> bool:
        """Settle an event and all related bets"""
        try:
            with transaction() as conn:
                cursor = conn.cursor()

                # Update event status
                cursor.execute('''
                    UPDATE betting_events
                    SET status = 'settled', result = ?
                    WHERE event_id = ?
                ''', (result, event_id))

                # Get all pending bets for this event
                cursor.execute('''
                    SELECT * FROM sports_bets
                    WHERE event_id = ? AND status = 'pending'
                ''', (event_id,))
                bets = cursor.fetchall()

                for bet in bets:
                    bet_id, user_id = bet[0], bet[1]
                    selection = bet[4]
                    potential_return = bet[7]

                    if selection == result:
                        # Winner
                        cursor.execute('''
                            UPDATE sports_bets
                            SET status = 'won', actual_return = ?, settled_at = ?
                            WHERE bet_id = ?
                        ''', (potential_return, datetime.now().isoformat(), bet_id))
                        AccountManager.add_winnings(user_id, potential_return, 'Bet won')
                    else:
                        # Loser
                        cursor.execute('''
                            UPDATE sports_bets
                            SET status = 'lost', actual_return = 0, settled_at = ?
                            WHERE bet_id = ?
                        ''', (datetime.now().isoformat(), bet_id))

            log_activity('settle', 'betting_event', details={'event_id': event_id, 'result': result})
            return True

        except sqlite3.Error as e:
            print(f"Error settling event: {e}")
            return False


class PredictionMarketManager:
    """Manager for prediction market operations"""

    @staticmethod
    def create_market(title: str, description: str, category: str,
                      outcome_a: str, outcome_b: str, resolution_date: str,
                      created_by: str = None) -> Optional[int]:
        """Create a new prediction market"""
        try:
            with transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO prediction_markets
                    (title, description, category, outcome_a, outcome_b, resolution_date, created_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (title, description, category, outcome_a, outcome_b, resolution_date, created_by))

                market_id = cursor.lastrowid

            log_activity('create', 'prediction_market', details={'market_id': market_id, 'title': title})
            return market_id

        except sqlite3.Error as e:
            print(f"Error creating market: {e}")
            return None

    @staticmethod
    def get_open_markets(category: str = None) -> List[Dict]:
        """Get open prediction markets"""
        try:
            query = "SELECT * FROM prediction_markets WHERE status = 'open'"
            params = []

            if category:
                query += ' AND category = ?'
                params.append(category)

            query += ' ORDER BY resolution_date'

            with get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]

        except sqlite3.Error as e:
            print(f"Error getting markets: {e}")
            return []

    @staticmethod
    def get_market(market_id: int) -> Optional[Dict]:
        """Get market by ID"""
        try:
            with get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM prediction_markets WHERE market_id = ?', (market_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except sqlite3.Error as e:
            print(f"Error getting market: {e}")
            return None

    @staticmethod
    def place_prediction_bet(user_id: str, market_id: int, selection: str, stake: float) -> Optional[int]:
        """Place a bet on a prediction market"""
        if stake < MIN_BET or stake > MAX_BET:
            return None

        try:
            market = PredictionMarketManager.get_market(market_id)
            if not market or market['status'] != 'open':
                return None

            # Calculate odds based on current pool
            if selection == 'outcome_a':
                probability = market['probability_a'] / 100
            else:
                probability = market['probability_b'] / 100

            odds = round(1 / probability * (1 - HOUSE_EDGE), 2) if probability > 0 else 2.00
            potential_return = round(stake * odds, 2)

            # Deduct stake
            if not AccountManager.deduct_stake(user_id, stake, f'Prediction bet on {market["title"]}'):
                return None

            with transaction() as conn:
                cursor = conn.cursor()

                # Place bet
                cursor.execute('''
                    INSERT INTO prediction_bets
                    (user_id, market_id, selection, stake, odds_at_placement, potential_return)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (user_id, market_id, selection, stake, odds, potential_return))

                bet_id = cursor.lastrowid

                # Update pool
                pool_column = 'pool_a' if selection == 'outcome_a' else 'pool_b'
                cursor.execute(f'''
                    UPDATE prediction_markets
                    SET total_pool = total_pool + ?, {pool_column} = {pool_column} + ?
                    WHERE market_id = ?
                ''', (stake, stake, market_id))

                # Recalculate probabilities
                cursor.execute('SELECT pool_a, pool_b, total_pool FROM prediction_markets WHERE market_id = ?', (market_id,))
                pools = cursor.fetchone()
                if pools[2] > 0:
                    prob_a = round((pools[0] / pools[2]) * 100, 2)
                    prob_b = round((pools[1] / pools[2]) * 100, 2)
                    cursor.execute('''
                        UPDATE prediction_markets
                        SET probability_a = ?, probability_b = ?
                        WHERE market_id = ?
                    ''', (prob_a, prob_b, market_id))

            log_activity('place_bet', 'prediction_market', details={
                'bet_id': bet_id, 'market_id': market_id, 'stake': stake
            })

            return bet_id

        except sqlite3.Error as e:
            print(f"Error placing prediction bet: {e}")
            return None

    @staticmethod
    def resolve_market(market_id: int, result: str, resolved_by: str = None) -> bool:
        """Resolve a prediction market"""
        try:
            market = PredictionMarketManager.get_market(market_id)
            if not market or market['status'] != 'open':
                return False

            with transaction() as conn:
                cursor = conn.cursor()

                # Update market status
                cursor.execute('''
                    UPDATE prediction_markets
                    SET status = 'resolved', result = ?
                    WHERE market_id = ?
                ''', (result, market_id))

                # Get all pending bets
                cursor.execute('''
                    SELECT * FROM prediction_bets
                    WHERE market_id = ? AND status = 'pending'
                ''', (market_id,))
                bets = cursor.fetchall()

                for bet in bets:
                    bet_id, user_id = bet[0], bet[1]
                    selection = bet[3]
                    potential_return = bet[6]

                    if selection == result:
                        cursor.execute('''
                            UPDATE prediction_bets
                            SET status = 'won', actual_return = ?, settled_at = ?
                            WHERE bet_id = ?
                        ''', (potential_return, datetime.now().isoformat(), bet_id))
                        AccountManager.add_winnings(user_id, potential_return, 'Prediction bet won')
                    else:
                        cursor.execute('''
                            UPDATE prediction_bets
                            SET status = 'lost', actual_return = 0, settled_at = ?
                            WHERE bet_id = ?
                        ''', (datetime.now().isoformat(), bet_id))

            log_activity('resolve', 'prediction_market', details={'market_id': market_id, 'result': result})
            return True

        except sqlite3.Error as e:
            print(f"Error resolving market: {e}")
            return False

    @staticmethod
    def get_user_predictions(user_id: str) -> List[Dict]:
        """Get prediction bets for a user"""
        try:
            with get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT pb.*, pm.title, pm.outcome_a, pm.outcome_b
                    FROM prediction_bets pb
                    JOIN prediction_markets pm ON pb.market_id = pm.market_id
                    WHERE pb.user_id = ?
                    ORDER BY pb.placed_at DESC
                ''', (user_id,))
                return [dict(row) for row in cursor.fetchall()]

        except sqlite3.Error as e:
            print(f"Error getting user predictions: {e}")
            return []


class CasinoManager:
    """Manager for casino game operations"""

    @staticmethod
    def start_session(user_id: str, game_type: str) -> Optional[int]:
        """Start a new casino session"""
        try:
            account = AccountManager.get_account(user_id)
            if not account:
                return None

            with transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO casino_sessions
                    (user_id, game_type, start_balance)
                    VALUES (?, ?, ?)
                ''', (user_id, game_type, account['balance']))

                session_id = cursor.lastrowid

            return session_id

        except sqlite3.Error as e:
            print(f"Error starting session: {e}")
            return None

    @staticmethod
    def play_slots(user_id: str, bet_amount: float, session_id: int = None) -> Dict:
        """Play a slot machine spin"""
        if bet_amount < MIN_BET or bet_amount > MAX_BET:
            return {'success': False, 'error': 'Invalid bet amount'}

        if not AccountManager.deduct_stake(user_id, bet_amount, 'Slots spin'):
            return {'success': False, 'error': 'Insufficient balance'}

        # Slot machine logic
        symbols = ['7', 'BAR', 'CHERRY', 'LEMON', 'ORANGE', 'PLUM', 'BELL']
        weights = [1, 2, 5, 10, 10, 10, 5]  # Weighted probabilities

        reels = []
        for _ in range(3):
            reel = random.choices(symbols, weights=weights, k=1)[0]
            reels.append(reel)

        # Calculate winnings
        win_amount = 0.00
        if reels[0] == reels[1] == reels[2]:
            if reels[0] == '7':
                win_amount = bet_amount * 100  # Jackpot
            elif reels[0] == 'BAR':
                win_amount = bet_amount * 50
            elif reels[0] == 'BELL':
                win_amount = bet_amount * 25
            else:
                win_amount = bet_amount * 10
        elif reels[0] == reels[1] or reels[1] == reels[2]:
            win_amount = bet_amount * 2
        elif 'CHERRY' in reels:
            win_amount = bet_amount * 1.5

        win_amount = round(win_amount, 2)

        if win_amount > 0:
            AccountManager.add_winnings(user_id, win_amount, 'Slots win')

        # Record game
        try:
            with transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO casino_games
                    (session_id, user_id, game_type, bet_amount, result, win_amount, game_data)
                    VALUES (?, ?, 'slots', ?, ?, ?, ?)
                ''', (session_id, user_id, bet_amount, 'win' if win_amount > 0 else 'lose',
                      win_amount, str(reels)))

                if session_id:
                    cursor.execute('''
                        UPDATE casino_sessions
                        SET total_wagered = total_wagered + ?, total_won = total_won + ?, hands_played = hands_played + 1
                        WHERE session_id = ?
                    ''', (bet_amount, win_amount, session_id))

        except sqlite3.Error:
            pass

        return {
            'success': True,
            'reels': reels,
            'win_amount': win_amount,
            'bet_amount': bet_amount,
            'is_jackpot': reels[0] == reels[1] == reels[2] == '7'
        }

    @staticmethod
    def play_blackjack(user_id: str, bet_amount: float, session_id: int = None) -> Dict:
        """Play a hand of blackjack"""
        if bet_amount < MIN_BET or bet_amount > MAX_BET:
            return {'success': False, 'error': 'Invalid bet amount'}

        if not AccountManager.deduct_stake(user_id, bet_amount, 'Blackjack hand'):
            return {'success': False, 'error': 'Insufficient balance'}

        # Simple blackjack simulation
        def draw_card():
            cards = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
            return random.choice(cards)

        def card_value(card, current_total):
            if card in ['J', 'Q', 'K']:
                return 10
            elif card == 'A':
                return 11 if current_total + 11 <= 21 else 1
            else:
                return int(card)

        def hand_value(hand):
            total = 0
            aces = 0
            for card in hand:
                if card == 'A':
                    aces += 1
                    total += 11
                elif card in ['J', 'Q', 'K']:
                    total += 10
                else:
                    total += int(card)
            while total > 21 and aces > 0:
                total -= 10
                aces -= 1
            return total

        # Deal cards
        player_hand = [draw_card(), draw_card()]
        dealer_hand = [draw_card(), draw_card()]

        player_total = hand_value(player_hand)
        dealer_total = hand_value(dealer_hand)

        # Simple AI: player stands on 17+, dealer hits until 17
        while player_total < 17:
            player_hand.append(draw_card())
            player_total = hand_value(player_hand)

        while dealer_total < 17 and player_total <= 21:
            dealer_hand.append(draw_card())
            dealer_total = hand_value(dealer_hand)

        # Determine winner
        win_amount = 0.00
        result = 'lose'

        if player_total > 21:
            result = 'bust'
        elif dealer_total > 21:
            result = 'win'
            win_amount = bet_amount * 2
        elif player_total > dealer_total:
            result = 'win'
            win_amount = bet_amount * 2
        elif player_total == dealer_total:
            result = 'push'
            win_amount = bet_amount  # Return stake

        # Check for blackjack
        if len(player_hand) == 2 and player_total == 21:
            result = 'blackjack'
            win_amount = bet_amount * 2.5

        win_amount = round(win_amount, 2)

        if win_amount > 0:
            AccountManager.add_winnings(user_id, win_amount, 'Blackjack win')

        # Record game
        try:
            with transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO casino_games
                    (session_id, user_id, game_type, bet_amount, result, win_amount, game_data)
                    VALUES (?, ?, 'blackjack', ?, ?, ?, ?)
                ''', (session_id, user_id, bet_amount, result, win_amount,
                      f'Player: {player_hand} ({player_total}), Dealer: {dealer_hand} ({dealer_total})'))

        except sqlite3.Error:
            pass

        return {
            'success': True,
            'player_hand': player_hand,
            'player_total': player_total,
            'dealer_hand': dealer_hand,
            'dealer_total': dealer_total,
            'result': result,
            'win_amount': win_amount,
            'bet_amount': bet_amount
        }

    @staticmethod
    def play_roulette(user_id: str, bet_amount: float, bet_type: str, bet_value: str, session_id: int = None) -> Dict:
        """Play roulette"""
        if bet_amount < MIN_BET or bet_amount > MAX_BET:
            return {'success': False, 'error': 'Invalid bet amount'}

        if not AccountManager.deduct_stake(user_id, bet_amount, 'Roulette bet'):
            return {'success': False, 'error': 'Insufficient balance'}

        # Spin the wheel (0-36)
        result_number = random.randint(0, 36)

        # Determine color
        red_numbers = [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]
        if result_number == 0:
            result_color = 'green'
        elif result_number in red_numbers:
            result_color = 'red'
        else:
            result_color = 'black'

        # Calculate winnings based on bet type
        win_amount = 0.00
        win = False

        if bet_type == 'number' and str(result_number) == bet_value:
            win_amount = bet_amount * 35
            win = True
        elif bet_type == 'color' and bet_value == result_color:
            win_amount = bet_amount * 2
            win = True
        elif bet_type == 'odd_even':
            is_odd = result_number % 2 == 1 and result_number != 0
            if (bet_value == 'odd' and is_odd) or (bet_value == 'even' and not is_odd and result_number != 0):
                win_amount = bet_amount * 2
                win = True
        elif bet_type == 'high_low':
            if bet_value == 'low' and 1 <= result_number <= 18:
                win_amount = bet_amount * 2
                win = True
            elif bet_value == 'high' and 19 <= result_number <= 36:
                win_amount = bet_amount * 2
                win = True

        win_amount = round(win_amount, 2)

        if win_amount > 0:
            AccountManager.add_winnings(user_id, win_amount, 'Roulette win')

        # Record game
        try:
            with transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO casino_games
                    (session_id, user_id, game_type, bet_amount, result, win_amount, game_data)
                    VALUES (?, ?, 'roulette', ?, ?, ?, ?)
                ''', (session_id, user_id, bet_amount, 'win' if win else 'lose', win_amount,
                      f'Number: {result_number}, Color: {result_color}, Bet: {bet_type}={bet_value}'))

        except sqlite3.Error:
            pass

        return {
            'success': True,
            'result_number': result_number,
            'result_color': result_color,
            'bet_type': bet_type,
            'bet_value': bet_value,
            'win': win,
            'win_amount': win_amount,
            'bet_amount': bet_amount
        }

    @staticmethod
    def get_game_history(user_id: str, game_type: str = None, limit: int = 50) -> List[Dict]:
        """Get casino game history"""
        try:
            query = 'SELECT * FROM casino_games WHERE user_id = ?'
            params = [user_id]

            if game_type:
                query += ' AND game_type = ?'
                params.append(game_type)

            query += ' ORDER BY played_at DESC LIMIT ?'
            params.append(limit)

            with get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]

        except sqlite3.Error as e:
            print(f"Error getting game history: {e}")
            return []


class ReportManager:
    """Manager for betting reports and statistics"""

    @staticmethod
    def get_overall_statistics(start_date: str = None, end_date: str = None) -> Dict:
        """Get overall betting statistics"""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                # Account statistics
                cursor.execute('SELECT COUNT(*), SUM(balance), SUM(total_wagered), SUM(total_won) FROM betting_accounts')
                account_stats = cursor.fetchone()

                # Sports betting stats
                cursor.execute('''
                    SELECT COUNT(*), SUM(stake), SUM(actual_return)
                    FROM sports_bets WHERE status IN ('won', 'lost', 'cashed_out')
                ''')
                sports_stats = cursor.fetchone()

                # Casino stats
                cursor.execute('''
                    SELECT COUNT(*), SUM(bet_amount), SUM(win_amount)
                    FROM casino_games
                ''')
                casino_stats = cursor.fetchone()

                # Revenue calculation
                total_wagered = (sports_stats[1] or 0) + (casino_stats[1] or 0)
                total_paid_out = (sports_stats[2] or 0) + (casino_stats[2] or 0)
                house_profit = total_wagered - total_paid_out

                return {
                    'total_accounts': account_stats[0] or 0,
                    'total_balance': account_stats[1] or 0,
                    'total_wagered': total_wagered,
                    'total_paid_out': total_paid_out,
                    'house_profit': house_profit,
                    'sports_bets': sports_stats[0] or 0,
                    'sports_wagered': sports_stats[1] or 0,
                    'casino_games': casino_stats[0] or 0,
                    'casino_wagered': casino_stats[1] or 0
                }

        except sqlite3.Error as e:
            print(f"Error getting statistics: {e}")
            return {}

    @staticmethod
    def generate_admin_report(start_date: str = None, end_date: str = None) -> str:
        """Generate comprehensive admin report"""
        stats = ReportManager.get_overall_statistics(start_date, end_date)

        report = f"""
{'='*70}
                BETTING SHOP - ADMINISTRATION REPORT
{'='*70}

Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Period: {start_date or 'All time'} to {end_date or 'Present'}

{'='*70}
                        ACCOUNT SUMMARY
{'='*70}

Total Active Accounts:    {stats.get('total_accounts', 0)}
Total Account Balances:   GBP {stats.get('total_balance', 0):.2f}

{'='*70}
                      WAGERING SUMMARY
{'='*70}

Total Amount Wagered:     GBP {stats.get('total_wagered', 0):.2f}
Total Amount Paid Out:    GBP {stats.get('total_paid_out', 0):.2f}
House Profit/Loss:        GBP {stats.get('house_profit', 0):.2f}

{'='*70}
                    SPORTS BETTING STATS
{'='*70}

Total Bets Placed:        {stats.get('sports_bets', 0)}
Total Wagered:            GBP {stats.get('sports_wagered', 0):.2f}

{'='*70}
                      CASINO STATS
{'='*70}

Total Games Played:       {stats.get('casino_games', 0)}
Total Wagered:            GBP {stats.get('casino_wagered', 0):.2f}

{'='*70}
                      END OF REPORT
{'='*70}
"""
        return report
