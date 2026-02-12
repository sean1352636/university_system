"""
Betting Shop CLI for University Management System

Provides comprehensive betting services including sports betting, prediction markets,
casino games, and account management with finance and email integration.
"""

import logging
import random
from datetime import datetime, timedelta
from typing import Optional, List, Dict

from university_system.core.sql_safety import validate_identifier

# Import centralized database and authentication
from university_system.infrastructure.database.db import get_connection, transaction
from university_system.infrastructure.shared_context import get_auth

# Import betting core services
try:
    from university_system.modules.domain.betting.services.betting_core import (
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
    from university_system.infrastructure.email.email_service import send_email
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False

# Import finance integration
try:
    from university_system.modules.shared.utils.finance_integration import (
        record_payment_to_finance,
        process_student_finance_account_payment
    )
    FINANCE_AVAILABLE = True
except ImportError:
    FINANCE_AVAILABLE = False

logger = logging.getLogger(__name__)


def print_header(text: str):
    """Print a formatted header"""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


def print_subheader(text: str):
    """Print a formatted subheader"""
    print("\n" + "-" * 70)
    print(f"  {text}")
    print("-" * 70)


def get_current_user():
    """Get the currently logged-in user"""
    try:
        auth = get_auth()
        if auth and hasattr(auth, 'current_user') and auth.current_user:
            return auth.current_user
    except Exception as e:
        logger.error(f"Error getting current user: {e}")
    return None


def is_admin():
    """Check if current user is admin/staff"""
    user = get_current_user()
    if not user:
        return False
    role = user.get('role', '').lower()
    return role in ['admin', 'staff', 'administrator']


# ============================================================================
# ACCOUNT MANAGEMENT
# ============================================================================

def view_balance():
    """View betting account balance"""
    user = get_current_user()
    if not user:
        print("❌ You must be logged in to view balance")
        input("\nPress Enter to continue...")
        return

    try:
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT balance, total_deposited, total_withdrawn, total_wagered, total_won
                FROM betting_accounts
                WHERE user_id = ?
            ''', (user.get('username'),))
            row = cursor.fetchone()

            if row:
                balance, deposited, withdrawn, wagered, won = row
                print_subheader("ACCOUNT BALANCE")
                print(f"\n💰 Current Balance: GBP {float(balance):.2f}")
                print(f"\n📊 Account Statistics:")
                print(f"   Total Deposited:  GBP {float(deposited or 0):.2f}")
                print(f"   Total Withdrawn:  GBP {float(withdrawn or 0):.2f}")
                print(f"   Total Wagered:    GBP {float(wagered or 0):.2f}")
                print(f"   Total Won:        GBP {float(won or 0):.2f}")

                net_profit = float(won or 0) - float(wagered or 0)
                print(f"   Net Profit/Loss:  GBP {net_profit:.2f}")
            else:
                print("\n❌ No betting account found. Creating one...")
                with transaction() as conn_tx:
                    conn_tx.execute('''
                        INSERT INTO betting_accounts (user_id, username, email)
                        VALUES (?, ?, ?)
                    ''', (user.get('username'), user.get('username'), user.get('email', '')))
                print("✅ Betting account created with GBP 0.00 balance")

    except Exception as e:
        logger.error(f"Error viewing balance: {e}")
        print(f"❌ Error viewing balance: {e}")

    input("\nPress Enter to continue...")


def deposit_funds():
    """Deposit funds into betting account"""
    user = get_current_user()
    if not user:
        print("❌ You must be logged in to deposit funds")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("DEPOSIT FUNDS")

        print("\n💳 Payment Methods:")
        print("1. Cash")
        print("2. Debit/Credit Card")
        print("3. Student Account")
        print("0. Cancel")

        method_choice = input("\nSelect payment method: ").strip()

        if method_choice == "0":
            return

        payment_methods = {
            "1": "Cash",
            "2": "Card",
            "3": "Student Account"
        }

        payment_method = payment_methods.get(method_choice, "Cash")

        amount_str = input(f"\nEnter amount to deposit (GBP {MIN_DEPOSIT:.2f} - GBP {MAX_DEPOSIT:.2f}): ").strip()

        if not amount_str:
            print("❌ Amount cannot be empty")
            input("\nPress Enter to continue...")
            return

        try:
            amount = float(amount_str)
        except ValueError:
            print("❌ Invalid amount. Please enter a valid number")
            input("\nPress Enter to continue...")
            return

        if amount < MIN_DEPOSIT or amount > MAX_DEPOSIT:
            print(f"❌ Amount must be between GBP {MIN_DEPOSIT:.2f} and GBP {MAX_DEPOSIT:.2f}")
            input("\nPress Enter to continue...")
            return

        # Get current balance
        with get_connection() as conn:
            cursor = conn.execute('SELECT balance FROM betting_accounts WHERE user_id = ?',
                                (user.get('username'),))
            row = cursor.fetchone()
            balance_before = float(row[0]) if row else 0.00

        balance_after = balance_before + amount

        with transaction() as conn:
            # Ensure account exists
            cursor = conn.execute('SELECT account_id FROM betting_accounts WHERE user_id = ?',
                                (user.get('username'),))
            if not cursor.fetchone():
                conn.execute('''
                    INSERT INTO betting_accounts (user_id, username, email)
                    VALUES (?, ?, ?)
                ''', (user.get('username'), user.get('username'), user.get('email', '')))

            # Update balance
            conn.execute('''
                UPDATE betting_accounts
                SET balance = balance + ?,
                    total_deposited = total_deposited + ?,
                    updated_at = ?
                WHERE user_id = ?
            ''', (amount, amount, datetime.now().isoformat(), user.get('username')))

            # Record transaction
            conn.execute('''
                INSERT INTO betting_transactions
                (user_id, transaction_type, amount, balance_before, balance_after,
                 description, payment_method, created_at)
                VALUES (?, 'deposit', ?, ?, ?, ?, ?, ?)
            ''', (user.get('username'), amount, balance_before, balance_after,
                  f'Deposit via {payment_method}', payment_method, datetime.now().isoformat()))

        print(f"\n✅ Successfully deposited GBP {amount:.2f} via {payment_method}")
        print(f"   New Balance: GBP {balance_after:.2f}")
        logger.info(f"User {user.get('username')} deposited GBP {amount:.2f} via {payment_method}")

    except Exception as e:
        logger.error(f"Error depositing funds: {e}")
        print(f"❌ Error depositing funds: {e}")

    input("\nPress Enter to continue...")


def withdraw_funds():
    """Withdraw funds from betting account"""
    user = get_current_user()
    if not user:
        print("❌ You must be logged in to withdraw funds")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("WITHDRAW FUNDS")

        # Get current balance
        with get_connection() as conn:
            cursor = conn.execute('SELECT balance FROM betting_accounts WHERE user_id = ?',
                                (user.get('username'),))
            row = cursor.fetchone()

            if not row:
                print("❌ No betting account found")
                input("\nPress Enter to continue...")
                return

            current_balance = float(row[0])

        print(f"\n💰 Current Balance: GBP {current_balance:.2f}")

        if current_balance <= 0:
            print("❌ Insufficient balance for withdrawal")
            input("\nPress Enter to continue...")
            return

        print("\n💳 Withdrawal Methods:")
        print("1. Bank Transfer")
        print("2. PayPal")
        print("3. Student Account Credit")
        print("0. Cancel")

        method_choice = input("\nSelect withdrawal method: ").strip()

        if method_choice == "0":
            return

        withdrawal_methods = {
            "1": "Bank Transfer",
            "2": "PayPal",
            "3": "Student Account"
        }

        withdrawal_method = withdrawal_methods.get(method_choice, "Bank Transfer")

        amount_str = input(f"\nEnter amount to withdraw (Max: GBP {current_balance:.2f}): ").strip()

        if not amount_str:
            print("❌ Amount cannot be empty")
            input("\nPress Enter to continue...")
            return

        try:
            amount = float(amount_str)
        except ValueError:
            print("❌ Invalid amount. Please enter a valid number")
            input("\nPress Enter to continue...")
            return

        if amount <= 0:
            print("❌ Amount must be greater than zero")
            input("\nPress Enter to continue...")
            return

        if amount > current_balance:
            print(f"❌ Insufficient balance. You have GBP {current_balance:.2f}")
            input("\nPress Enter to continue...")
            return

        # Verification check
        print(f"\n⚠️  Withdrawal Verification:")
        print(f"   Amount: GBP {amount:.2f}")
        print(f"   Method: {withdrawal_method}")
        print(f"   Remaining Balance: GBP {current_balance - amount:.2f}")

        confirm = input("\nConfirm withdrawal? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("❌ Withdrawal cancelled")
            input("\nPress Enter to continue...")
            return

        balance_after = current_balance - amount

        with transaction() as conn:
            # Update balance
            conn.execute('''
                UPDATE betting_accounts
                SET balance = balance - ?,
                    total_withdrawn = total_withdrawn + ?,
                    updated_at = ?
                WHERE user_id = ?
            ''', (amount, amount, datetime.now().isoformat(), user.get('username')))

            # Record transaction
            conn.execute('''
                INSERT INTO betting_transactions
                (user_id, transaction_type, amount, balance_before, balance_after,
                 description, payment_method, created_at)
                VALUES (?, 'withdrawal', ?, ?, ?, ?, ?, ?)
            ''', (user.get('username'), amount, current_balance, balance_after,
                  f'Withdrawal to {withdrawal_method}', withdrawal_method,
                  datetime.now().isoformat()))

        print(f"\n✅ Withdrawal processed successfully!")
        print(f"   Amount: GBP {amount:.2f}")
        print(f"   Method: {withdrawal_method}")
        print(f"   New Balance: GBP {balance_after:.2f}")
        print(f"\n   Processing time: 1-3 business days")

        logger.info(f"User {user.get('username')} withdrew GBP {amount:.2f} via {withdrawal_method}")

    except Exception as e:
        logger.error(f"Error withdrawing funds: {e}")
        print(f"❌ Error withdrawing funds: {e}")

    input("\nPress Enter to continue...")


def view_transaction_history():
    """View account transaction history"""
    user = get_current_user()
    if not user:
        print("❌ You must be logged in to view transaction history")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("TRANSACTION HISTORY")

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT transaction_type, amount, balance_before, balance_after,
                       payment_method, description, created_at
                FROM betting_transactions
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT 50
            ''', (user.get('username'),))
            transactions = cursor.fetchall()

            if not transactions:
                print("\n❌ No transactions found")
            else:
                print(f"\n📜 Last {len(transactions)} Transactions:")
                print("-" * 70)

                for trans in transactions:
                    try:
                        t_type, amount, bal_before, bal_after, method, desc, created = trans
                        print(f"\n{created}")
                        print(f"Type: {t_type.upper()}")
                        print(f"Amount: GBP {float(amount):.2f}")
                        if method:
                            print(f"Method: {method}")
                        print(f"Balance: GBP {float(bal_before or 0):.2f} → GBP {float(bal_after or 0):.2f}")
                        if desc:
                            print(f"Description: {desc}")
                    except Exception as e:
                        logger.error(f"Error displaying transaction: {e}")
                        continue

    except Exception as e:
        logger.error(f"Error viewing transaction history: {e}")
        print(f"❌ Error viewing transaction history: {e}")

    input("\nPress Enter to continue...")


# ============================================================================
# SPORTS BETTING
# ============================================================================

def view_sports_events():
    """View available sports events"""
    try:
        print_subheader("UPCOMING SPORTS EVENTS")

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT event_id, event_name, sport_type, team_a, team_b,
                       odds_a, odds_b, odds_draw, event_date, event_time, status
                FROM betting_events
                WHERE status = 'upcoming'
                ORDER BY event_date, event_time
                LIMIT 30
            ''')
            events = cursor.fetchall()

            if not events:
                print("\n❌ No upcoming events available")
            else:
                print(f"\n📅 {len(events)} Upcoming Events:")
                print("-" * 70)

                for event in events:
                    try:
                        event_id, name, sport, team_a, team_b, odds_a, odds_b, odds_draw, date, time, status = event
                        print(f"\n🏆 Event ID: {event_id}")
                        print(f"   Event: {name}")
                        if sport:
                            print(f"   Sport: {sport}")
                        print(f"   {team_a} (Odds: {float(odds_a):.2f}) vs {team_b} (Odds: {float(odds_b):.2f})")
                        if odds_draw:
                            print(f"   Draw (Odds: {float(odds_draw):.2f})")
                        print(f"   Date: {date}", end="")
                        if time:
                            print(f" at {time}")
                        else:
                            print()
                    except Exception as e:
                        logger.error(f"Error displaying event: {e}")
                        continue

    except Exception as e:
        logger.error(f"Error viewing sports events: {e}")
        print(f"❌ Error viewing sports events: {e}")

    input("\nPress Enter to continue...")


def place_sports_bet():
    """Place a bet on a sports event"""
    user = get_current_user()
    if not user:
        print("❌ You must be logged in to place bets")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("PLACE SPORTS BET")

        # Show available events
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT event_id, event_name, sport_type, team_a, team_b,
                       odds_a, odds_b, odds_draw
                FROM betting_events
                WHERE status = 'upcoming'
                ORDER BY event_date
                LIMIT 20
            ''')
            events = cursor.fetchall()

            if not events:
                print("\n❌ No upcoming events available")
                input("\nPress Enter to continue...")
                return

            print("\n📅 Available Events:")
            for event in events:
                event_id, name, sport, team_a, team_b, odds_a, odds_b, odds_draw = event
                print(f"\n🏆 Event ID: {event_id} - {name}")
                print(f"   {team_a} ({float(odds_a):.2f}) vs {team_b} ({float(odds_b):.2f})", end="")
                if odds_draw:
                    print(f" | Draw ({float(odds_draw):.2f})")
                else:
                    print()

        event_id = input("\nEnter event ID to bet on (0 to cancel): ").strip()
        if event_id == "0":
            return

        if not event_id.isdigit():
            print("❌ Invalid event ID")
            input("\nPress Enter to continue...")
            return

        # Get event details
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT event_name, team_a, team_b, odds_a, odds_b, odds_draw
                FROM betting_events
                WHERE event_id = ? AND status = 'upcoming'
            ''', (event_id,))
            event = cursor.fetchone()

            if not event:
                print("❌ Event not found or no longer available")
                input("\nPress Enter to continue...")
                return

            event_name, team_a, team_b, odds_a, odds_b, odds_draw = event

            print(f"\n🎲 Betting on: {event_name}")
            print("\nBet Types:")
            print("1. Single Bet (Win)")
            print("2. Each-Way Bet (Win or Place)")
            print("0. Cancel")

            bet_type_choice = input("\nSelect bet type: ").strip()

            if bet_type_choice == "0":
                return

            bet_type = "single" if bet_type_choice == "1" else "each-way"

            print(f"\nSelections:")
            print(f"1. {team_a} (Odds: {float(odds_a):.2f})")
            print(f"2. {team_b} (Odds: {float(odds_b):.2f})")
            if odds_draw:
                print(f"3. Draw (Odds: {float(odds_draw):.2f})")

            selection = input("\nSelect your bet (1/2/3): ").strip()

            if selection == "1":
                selected_team = team_a
                odds = float(odds_a)
            elif selection == "2":
                selected_team = team_b
                odds = float(odds_b)
            elif selection == "3" and odds_draw:
                selected_team = "Draw"
                odds = float(odds_draw)
            else:
                print("❌ Invalid selection")
                input("\nPress Enter to continue...")
                return

            stake_str = input(f"\nEnter stake amount (GBP {MIN_BET:.2f} - GBP {MAX_BET:.2f}): ").strip()

            try:
                stake = float(stake_str)
            except ValueError:
                print("❌ Invalid stake amount")
                input("\nPress Enter to continue...")
                return

            if stake < MIN_BET or stake > MAX_BET:
                print(f"❌ Stake must be between GBP {MIN_BET:.2f} and GBP {MAX_BET:.2f}")
                input("\nPress Enter to continue...")
                return

            # For each-way, double the stake
            if bet_type == "each-way":
                actual_stake = stake * 2
                print(f"\n⚠️  Each-way bet requires double stake: GBP {actual_stake:.2f}")
            else:
                actual_stake = stake

            potential_return = actual_stake * odds

            # Check balance
            cursor = conn.execute('SELECT balance FROM betting_accounts WHERE user_id = ?',
                                (user.get('username'),))
            row = cursor.fetchone()
            if not row or float(row[0]) < actual_stake:
                print(f"❌ Insufficient balance. Required: GBP {actual_stake:.2f}")
                input("\nPress Enter to continue...")
                return

            print(f"\n📊 Bet Summary:")
            print(f"   Event: {event_name}")
            print(f"   Selection: {selected_team}")
            print(f"   Bet Type: {bet_type.upper()}")
            print(f"   Stake: GBP {actual_stake:.2f}")
            print(f"   Odds: {odds:.2f}")
            print(f"   Potential Return: GBP {potential_return:.2f}")
            print(f"   Potential Profit: GBP {potential_return - actual_stake:.2f}")

            confirm = input("\nConfirm bet? (yes/no): ").strip().lower()
            if confirm != 'yes':
                print("❌ Bet cancelled")
                input("\nPress Enter to continue...")
                return

            with transaction() as conn_tx:
                # Deduct balance
                conn_tx.execute('''
                    UPDATE betting_accounts
                    SET balance = balance - ?,
                        total_wagered = total_wagered + ?,
                        updated_at = ?
                    WHERE user_id = ?
                ''', (actual_stake, actual_stake, datetime.now().isoformat(), user.get('username')))

                # Place bet
                conn_tx.execute('''
                    INSERT INTO sports_bets
                    (user_id, event_id, bet_type, selection, odds, stake, potential_return, status, placed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)
                ''', (user.get('username'), event_id, bet_type, selected_team,
                      odds, actual_stake, potential_return, datetime.now().isoformat()))

            print("\n✅ Bet placed successfully!")
            print(f"   Bet ID: {cursor.lastrowid}")
            logger.info(f"User {user.get('username')} placed {bet_type} bet of GBP {actual_stake:.2f} on event {event_id}")

    except Exception as e:
        logger.error(f"Error placing bet: {e}")
        print(f"❌ Error placing bet: {e}")

    input("\nPress Enter to continue...")


def view_my_bets():
    """View user's betting history"""
    user = get_current_user()
    if not user:
        print("❌ You must be logged in to view bets")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("MY SPORTS BETS")

        print("\n📊 Filter by status:")
        print("1. All Bets")
        print("2. Pending Bets")
        print("3. Won Bets")
        print("4. Lost Bets")

        filter_choice = input("\nSelect filter (default: 1): ").strip() or "1"

        status_filter = {
            "1": None,
            "2": "pending",
            "3": "won",
            "4": "lost"
        }.get(filter_choice)

        with get_connection() as conn:
            if status_filter:
                cursor = conn.execute('''
                    SELECT sb.bet_id, be.event_name, sb.bet_type, sb.selection, sb.odds,
                           sb.stake, sb.potential_return, sb.actual_return, sb.status, sb.placed_at
                    FROM sports_bets sb
                    JOIN betting_events be ON sb.event_id = be.event_id
                    WHERE sb.user_id = ? AND sb.status = ?
                    ORDER BY sb.placed_at DESC
                    LIMIT 30
                ''', (user.get('username'), status_filter))
            else:
                cursor = conn.execute('''
                    SELECT sb.bet_id, be.event_name, sb.bet_type, sb.selection, sb.odds,
                           sb.stake, sb.potential_return, sb.actual_return, sb.status, sb.placed_at
                    FROM sports_bets sb
                    JOIN betting_events be ON sb.event_id = be.event_id
                    WHERE sb.user_id = ?
                    ORDER BY sb.placed_at DESC
                    LIMIT 30
                ''', (user.get('username'),))

            bets = cursor.fetchall()

            if not bets:
                print("\n❌ No bets found")
            else:
                print(f"\n📜 {len(bets)} Bet(s) Found:")
                print("-" * 70)

                total_staked = 0.0
                total_returned = 0.0

                for bet in bets:
                    try:
                        bet_id, event, bet_type, selection, odds, stake, potential, actual, status, placed = bet
                        stake_val = float(stake)
                        potential_val = float(potential)
                        actual_val = float(actual or 0)

                        total_staked += stake_val
                        total_returned += actual_val

                        print(f"\n🎲 Bet ID: {bet_id}")
                        print(f"   Event: {event}")
                        print(f"   Type: {bet_type.upper()}")
                        print(f"   Selection: {selection}")
                        print(f"   Stake: GBP {stake_val:.2f} @ {float(odds):.2f}")
                        print(f"   Potential: GBP {potential_val:.2f}")

                        if status == 'won':
                            print(f"   Status: ✅ WON - Returned GBP {actual_val:.2f}")
                        elif status == 'lost':
                            print(f"   Status: ❌ LOST")
                        elif status == 'cashed_out':
                            print(f"   Status: 💰 CASHED OUT - GBP {actual_val:.2f}")
                        else:
                            print(f"   Status: ⏳ {status.upper()}")

                        print(f"   Placed: {placed}")
                    except Exception as e:
                        logger.error(f"Error displaying bet: {e}")
                        continue

                print("\n" + "-" * 70)
                print(f"Total Staked: GBP {total_staked:.2f}")
                print(f"Total Returned: GBP {total_returned:.2f}")
                print(f"Net Profit/Loss: GBP {total_returned - total_staked:.2f}")

    except Exception as e:
        logger.error(f"Error viewing bets: {e}")
        print(f"❌ Error viewing bets: {e}")

    input("\nPress Enter to continue...")


def place_accumulator_bet():
    """Place an accumulator/parlay bet on multiple events"""
    user = get_current_user()
    if not user:
        print("❌ You must be logged in to place bets")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("PLACE ACCUMULATOR BET")
        print("\n📝 An accumulator bet combines multiple selections.")
        print("   All selections must win for the bet to pay out.")
        print("   Odds are multiplied together for higher potential returns.")

        selections = []

        while True:
            print(f"\n📊 Current Selections: {len(selections)}")

            if selections:
                combined_odds = 1.0
                for sel in selections:
                    combined_odds *= sel['odds']
                print(f"   Combined Odds: {combined_odds:.2f}")

            print("\n1. Add Selection")
            if len(selections) >= 2:
                print("2. Place Accumulator")
            print("0. Cancel")

            choice = input("\nChoice: ").strip()

            if choice == "0":
                return
            elif choice == "2" and len(selections) >= 2:
                break
            elif choice == "1":
                # Show events
                with get_connection() as conn:
                    cursor = conn.execute('''
                        SELECT event_id, event_name, team_a, team_b, odds_a, odds_b, odds_draw
                        FROM betting_events
                        WHERE status = 'upcoming'
                        ORDER BY event_date
                        LIMIT 15
                    ''')
                    events = cursor.fetchall()

                    if not events:
                        print("\n❌ No events available")
                        continue

                    print("\n📅 Available Events:")
                    for event in events:
                        event_id, name, team_a, team_b, odds_a, odds_b, odds_draw = event
                        print(f"{event_id}. {name}")
                        print(f"   1:{team_a} ({float(odds_a):.2f}) 2:{team_b} ({float(odds_b):.2f})", end="")
                        if odds_draw:
                            print(f" 3:Draw ({float(odds_draw):.2f})")
                        else:
                            print()

                event_id = input("\nEvent ID: ").strip()
                if not event_id.isdigit():
                    continue

                cursor = conn.execute('''
                    SELECT event_name, team_a, team_b, odds_a, odds_b, odds_draw
                    FROM betting_events
                    WHERE event_id = ? AND status = 'upcoming'
                ''', (event_id,))
                event = cursor.fetchone()

                if not event:
                    print("❌ Event not found")
                    continue

                event_name, team_a, team_b, odds_a, odds_b, odds_draw = event

                sel_num = input(f"Selection (1={team_a}, 2={team_b}, 3=Draw): ").strip()

                if sel_num == "1":
                    selections.append({
                        'event_id': int(event_id),
                        'event_name': event_name,
                        'selection': team_a,
                        'odds': float(odds_a)
                    })
                elif sel_num == "2":
                    selections.append({
                        'event_id': int(event_id),
                        'event_name': event_name,
                        'selection': team_b,
                        'odds': float(odds_b)
                    })
                elif sel_num == "3" and odds_draw:
                    selections.append({
                        'event_id': int(event_id),
                        'event_name': event_name,
                        'selection': 'Draw',
                        'odds': float(odds_draw)
                    })
                else:
                    print("❌ Invalid selection")
                    continue

                print(f"✅ Added: {selections[-1]['selection']} in {event_name}")

        # Calculate accumulator
        combined_odds = 1.0
        for sel in selections:
            combined_odds *= sel['odds']

        print(f"\n📊 Accumulator Summary:")
        print(f"   Selections: {len(selections)}")
        for i, sel in enumerate(selections, 1):
            print(f"   {i}. {sel['selection']} in {sel['event_name']} @ {sel['odds']:.2f}")
        print(f"   Combined Odds: {combined_odds:.2f}")

        stake_str = input(f"\nEnter stake (GBP {MIN_BET:.2f} - GBP {MAX_BET:.2f}): ").strip()

        try:
            stake = float(stake_str)
        except ValueError:
            print("❌ Invalid stake")
            input("\nPress Enter to continue...")
            return

        if stake < MIN_BET or stake > MAX_BET:
            print(f"❌ Stake must be between GBP {MIN_BET:.2f} and GBP {MAX_BET:.2f}")
            input("\nPress Enter to continue...")
            return

        potential_return = stake * combined_odds

        print(f"\n💰 Potential Return: GBP {potential_return:.2f}")
        print(f"   Potential Profit: GBP {potential_return - stake:.2f}")

        confirm = input("\nConfirm accumulator bet? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("❌ Bet cancelled")
            input("\nPress Enter to continue...")
            return

        # Check balance and place bet
        with get_connection() as conn:
            cursor = conn.execute('SELECT balance FROM betting_accounts WHERE user_id = ?',
                                (user.get('username'),))
            row = cursor.fetchone()
            if not row or float(row[0]) < stake:
                print(f"❌ Insufficient balance")
                input("\nPress Enter to continue...")
                return

        with transaction() as conn_tx:
            # Deduct balance
            conn_tx.execute('''
                UPDATE betting_accounts
                SET balance = balance - ?,
                    total_wagered = total_wagered + ?,
                    updated_at = ?
                WHERE user_id = ?
            ''', (stake, stake, datetime.now().isoformat(), user.get('username')))

            # Place individual bets as part of accumulator
            for sel in selections:
                conn_tx.execute('''
                    INSERT INTO sports_bets
                    (user_id, event_id, bet_type, selection, odds, stake, potential_return, status, placed_at)
                    VALUES (?, ?, 'accumulator', ?, ?, ?, ?, 'pending', ?)
                ''', (user.get('username'), sel['event_id'], sel['selection'],
                      combined_odds, stake, potential_return, datetime.now().isoformat()))

        print("\n✅ Accumulator bet placed successfully!")
        logger.info(f"User {user.get('username')} placed accumulator with {len(selections)} selections")

    except Exception as e:
        logger.error(f"Error placing accumulator: {e}")
        print(f"❌ Error placing accumulator: {e}")

    input("\nPress Enter to continue...")


# ============================================================================
# CASINO GAMES
# ============================================================================

def play_slots():
    """Play slot machine"""
    user = get_current_user()
    if not user:
        print("❌ You must be logged in to play")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("SLOT MACHINE")

        # Get balance
        with get_connection() as conn:
            cursor = conn.execute('SELECT balance FROM betting_accounts WHERE user_id = ?',
                                (user.get('username'),))
            row = cursor.fetchone()
            if not row:
                print("❌ No betting account found")
                input("\nPress Enter to continue...")
                return

            balance = float(row[0])

        print(f"\n💰 Balance: GBP {balance:.2f}")
        print("\n🎰 Slot Machine Rules:")
        print("   Match 3 symbols to win!")
        print("   7️⃣7️⃣7️⃣ = 100x stake (JACKPOT!)")
        print("   BAR BAR BAR = 50x stake")
        print("   🔔🔔🔔 = 25x stake")
        print("   Other triples = 10x stake")
        print("   Two matching = 2x stake")
        print("   Any CHERRY = 1.5x stake")

        bet_str = input(f"\nEnter bet amount (GBP {MIN_BET:.2f} - GBP {MAX_BET:.2f}, 0 to quit): ").strip()

        if bet_str == "0":
            return

        try:
            bet = float(bet_str)
        except ValueError:
            print("❌ Invalid bet amount")
            input("\nPress Enter to continue...")
            return

        if bet < MIN_BET or bet > MAX_BET:
            print(f"❌ Bet must be between GBP {MIN_BET:.2f} and GBP {MAX_BET:.2f}")
            input("\nPress Enter to continue...")
            return

        if bet > balance:
            print(f"❌ Insufficient balance")
            input("\nPress Enter to continue...")
            return

        # Deduct bet
        with transaction() as conn_tx:
            conn_tx.execute('''
                UPDATE betting_accounts
                SET balance = balance - ?,
                    total_wagered = total_wagered + ?,
                    updated_at = ?
                WHERE user_id = ?
            ''', (bet, bet, datetime.now().isoformat(), user.get('username')))

        # Spin!
        symbols = ['7️⃣', 'BAR', '🍒', '🍋', '🍊', '🍇', '🔔']
        weights = [1, 2, 5, 10, 10, 10, 5]

        print("\n🎰 Spinning...")
        import time
        time.sleep(1)

        reels = []
        for _ in range(3):
            reel = random.choices(symbols, weights=weights, k=1)[0]
            reels.append(reel)

        print(f"\n   [ {reels[0]} | {reels[1]} | {reels[2]} ]")

        # Calculate win
        win_amount = 0.0
        message = ""

        if reels[0] == reels[1] == reels[2]:
            if reels[0] == '7️⃣':
                win_amount = bet * 100
                message = "🎊 JACKPOT! 🎊"
            elif reels[0] == 'BAR':
                win_amount = bet * 50
                message = "💰 BIG WIN!"
            elif reels[0] == '🔔':
                win_amount = bet * 25
                message = "🔔 EXCELLENT!"
            else:
                win_amount = bet * 10
                message = "✨ TRIPLE MATCH!"
        elif reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]:
            win_amount = bet * 2
            message = "👍 Double match!"
        elif '🍒' in reels:
            win_amount = bet * 1.5
            message = "🍒 Cherry bonus!"

        win_amount = round(win_amount, 2)

        if win_amount > 0:
            print(f"\n{message}")
            print(f"💰 You won GBP {win_amount:.2f}!")

            with transaction() as conn_tx:
                conn_tx.execute('''
                    UPDATE betting_accounts
                    SET balance = balance + ?,
                        total_won = total_won + ?,
                        updated_at = ?
                    WHERE user_id = ?
                ''', (win_amount, win_amount, datetime.now().isoformat(), user.get('username')))

                # Record game
                conn_tx.execute('''
                    INSERT INTO casino_games
                    (user_id, game_type, bet_amount, result, win_amount, game_data, played_at)
                    VALUES (?, 'slots', ?, 'win', ?, ?, ?)
                ''', (user.get('username'), bet, win_amount, str(reels), datetime.now().isoformat()))

            new_balance = balance - bet + win_amount
            print(f"   New Balance: GBP {new_balance:.2f}")
        else:
            print(f"\n❌ No win this time!")

            # Record game
            with transaction() as conn_tx:
                conn_tx.execute('''
                    INSERT INTO casino_games
                    (user_id, game_type, bet_amount, result, win_amount, game_data, played_at)
                    VALUES (?, 'slots', ?, 'lose', 0, ?, ?)
                ''', (user.get('username'), bet, str(reels), datetime.now().isoformat()))

            new_balance = balance - bet
            print(f"   Balance: GBP {new_balance:.2f}")

    except Exception as e:
        logger.error(f"Error playing slots: {e}")
        print(f"❌ Error playing slots: {e}")

    input("\nPress Enter to continue...")


def play_roulette():
    """Play roulette"""
    user = get_current_user()
    if not user:
        print("❌ You must be logged in to play")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("ROULETTE")

        # Get balance
        with get_connection() as conn:
            cursor = conn.execute('SELECT balance FROM betting_accounts WHERE user_id = ?',
                                (user.get('username'),))
            row = cursor.fetchone()
            if not row:
                print("❌ No betting account found")
                input("\nPress Enter to continue...")
                return

            balance = float(row[0])

        print(f"\n💰 Balance: GBP {balance:.2f}")
        print("\n🎯 Roulette Betting Options:")
        print("1. Single Number (0-36) - Pays 35:1")
        print("2. Red/Black - Pays 1:1")
        print("3. Odd/Even - Pays 1:1")
        print("4. High (19-36) / Low (1-18) - Pays 1:1")
        print("0. Cancel")

        bet_type = input("\nSelect bet type: ").strip()

        if bet_type == "0":
            return

        bet_value = None

        if bet_type == "1":
            number = input("Enter number (0-36): ").strip()
            if not number.isdigit() or int(number) > 36:
                print("❌ Invalid number")
                input("\nPress Enter to continue...")
                return
            bet_value = number
            bet_type_name = "number"
        elif bet_type == "2":
            color = input("Enter color (red/black): ").strip().lower()
            if color not in ['red', 'black']:
                print("❌ Invalid color")
                input("\nPress Enter to continue...")
                return
            bet_value = color
            bet_type_name = "color"
        elif bet_type == "3":
            parity = input("Enter odd/even: ").strip().lower()
            if parity not in ['odd', 'even']:
                print("❌ Invalid choice")
                input("\nPress Enter to continue...")
                return
            bet_value = parity
            bet_type_name = "odd_even"
        elif bet_type == "4":
            range_choice = input("Enter high/low: ").strip().lower()
            if range_choice not in ['high', 'low']:
                print("❌ Invalid choice")
                input("\nPress Enter to continue...")
                return
            bet_value = range_choice
            bet_type_name = "high_low"
        else:
            print("❌ Invalid bet type")
            input("\nPress Enter to continue...")
            return

        bet_str = input(f"\nEnter bet amount (GBP {MIN_BET:.2f} - GBP {MAX_BET:.2f}): ").strip()

        try:
            bet = float(bet_str)
        except ValueError:
            print("❌ Invalid bet amount")
            input("\nPress Enter to continue...")
            return

        if bet < MIN_BET or bet > MAX_BET:
            print(f"❌ Bet must be between GBP {MIN_BET:.2f} and GBP {MAX_BET:.2f}")
            input("\nPress Enter to continue...")
            return

        if bet > balance:
            print(f"❌ Insufficient balance")
            input("\nPress Enter to continue...")
            return

        # Deduct bet
        with transaction() as conn_tx:
            conn_tx.execute('''
                UPDATE betting_accounts
                SET balance = balance - ?,
                    total_wagered = total_wagered + ?,
                    updated_at = ?
                WHERE user_id = ?
            ''', (bet, bet, datetime.now().isoformat(), user.get('username')))

        # Spin the wheel
        print("\n🎰 Spinning the roulette wheel...")
        import time
        time.sleep(1)

        result_number = random.randint(0, 36)

        red_numbers = [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]
        if result_number == 0:
            result_color = 'green'
        elif result_number in red_numbers:
            result_color = 'red'
        else:
            result_color = 'black'

        print(f"\n🎯 Result: {result_number} ({result_color.upper()})")

        # Check win
        win_amount = 0.0
        win = False

        if bet_type_name == 'number' and str(result_number) == bet_value:
            win_amount = bet * 35
            win = True
            message = "🎊 STRAIGHT UP WIN! 🎊"
        elif bet_type_name == 'color' and bet_value == result_color:
            win_amount = bet * 2
            win = True
            message = f"✅ {result_color.upper()} wins!"
        elif bet_type_name == 'odd_even':
            is_odd = result_number % 2 == 1 and result_number != 0
            if (bet_value == 'odd' and is_odd) or (bet_value == 'even' and not is_odd and result_number != 0):
                win_amount = bet * 2
                win = True
                message = f"✅ {bet_value.upper()} wins!"
        elif bet_type_name == 'high_low':
            if bet_value == 'low' and 1 <= result_number <= 18:
                win_amount = bet * 2
                win = True
                message = "✅ LOW wins!"
            elif bet_value == 'high' and 19 <= result_number <= 36:
                win_amount = bet * 2
                win = True
                message = "✅ HIGH wins!"

        win_amount = round(win_amount, 2)

        if win:
            print(f"\n{message}")
            print(f"💰 You won GBP {win_amount:.2f}!")

            with transaction() as conn_tx:
                conn_tx.execute('''
                    UPDATE betting_accounts
                    SET balance = balance + ?,
                        total_won = total_won + ?,
                        updated_at = ?
                    WHERE user_id = ?
                ''', (win_amount, win_amount, datetime.now().isoformat(), user.get('username')))

                # Record game
                conn_tx.execute('''
                    INSERT INTO casino_games
                    (user_id, game_type, bet_amount, result, win_amount, game_data, played_at)
                    VALUES (?, 'roulette', ?, 'win', ?, ?, ?)
                ''', (user.get('username'), bet, win_amount,
                      f'{result_number},{result_color},{bet_type_name},{bet_value}',
                      datetime.now().isoformat()))

            new_balance = balance - bet + win_amount
            print(f"   New Balance: GBP {new_balance:.2f}")
        else:
            print(f"\n❌ No win this time!")

            # Record game
            with transaction() as conn_tx:
                conn_tx.execute('''
                    INSERT INTO casino_games
                    (user_id, game_type, bet_amount, result, win_amount, game_data, played_at)
                    VALUES (?, 'roulette', ?, 'lose', 0, ?, ?)
                ''', (user.get('username'), bet,
                      f'{result_number},{result_color},{bet_type_name},{bet_value}',
                      datetime.now().isoformat()))

            new_balance = balance - bet
            print(f"   Balance: GBP {new_balance:.2f}")

    except Exception as e:
        logger.error(f"Error playing roulette: {e}")
        print(f"❌ Error playing roulette: {e}")

    input("\nPress Enter to continue...")


def play_blackjack():
    """Play blackjack"""
    user = get_current_user()
    if not user:
        print("❌ You must be logged in to play")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("BLACKJACK")

        # Get balance
        with get_connection() as conn:
            cursor = conn.execute('SELECT balance FROM betting_accounts WHERE user_id = ?',
                                (user.get('username'),))
            row = cursor.fetchone()
            if not row:
                print("❌ No betting account found")
                input("\nPress Enter to continue...")
                return

            balance = float(row[0])

        print(f"\n💰 Balance: GBP {balance:.2f}")
        print("\n🃏 Blackjack Rules:")
        print("   Get closer to 21 than dealer without going over")
        print("   Face cards = 10, Ace = 1 or 11")
        print("   Blackjack pays 2.5x")
        print("   Win pays 2x")

        bet_str = input(f"\nEnter bet amount (GBP {MIN_BET:.2f} - GBP {MAX_BET:.2f}, 0 to quit): ").strip()

        if bet_str == "0":
            return

        try:
            bet = float(bet_str)
        except ValueError:
            print("❌ Invalid bet amount")
            input("\nPress Enter to continue...")
            return

        if bet < MIN_BET or bet > MAX_BET:
            print(f"❌ Bet must be between GBP {MIN_BET:.2f} and GBP {MAX_BET:.2f}")
            input("\nPress Enter to continue...")
            return

        if bet > balance:
            print(f"❌ Insufficient balance")
            input("\nPress Enter to continue...")
            return

        # Deduct bet
        with transaction() as conn_tx:
            conn_tx.execute('''
                UPDATE betting_accounts
                SET balance = balance - ?,
                    total_wagered = total_wagered + ?,
                    updated_at = ?
                WHERE user_id = ?
            ''', (bet, bet, datetime.now().isoformat(), user.get('username')))

        # Deal cards
        def draw_card():
            cards = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
            return random.choice(cards)

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

        player_hand = [draw_card(), draw_card()]
        dealer_hand = [draw_card(), draw_card()]

        print("\n🃏 Cards dealt!")
        print(f"Your hand: {' '.join(player_hand)} = {hand_value(player_hand)}")
        print(f"Dealer shows: {dealer_hand[0]}")

        player_total = hand_value(player_hand)

        # Check for immediate blackjack
        if player_total == 21:
            dealer_total = hand_value(dealer_hand)
            print(f"\n🎊 BLACKJACK! 🎊")
            print(f"Dealer hand: {' '.join(dealer_hand)} = {dealer_total}")

            if dealer_total == 21:
                win_amount = bet
                result = "push"
                print("Dealer also has blackjack - PUSH!")
            else:
                win_amount = bet * 2.5
                result = "blackjack"
                print(f"💰 You won GBP {win_amount:.2f}!")
        else:
            # Player decisions
            while player_total < 21:
                action = input("\n(H)it or (S)tand? ").strip().lower()

                if action == 's':
                    break
                elif action == 'h':
                    new_card = draw_card()
                    player_hand.append(new_card)
                    player_total = hand_value(player_hand)
                    print(f"Drew: {new_card}")
                    print(f"Your hand: {' '.join(player_hand)} = {player_total}")

                    if player_total > 21:
                        print("\n💥 BUST! Over 21!")
                        break

            # Dealer plays
            dealer_total = hand_value(dealer_hand)
            print(f"\nDealer reveals: {' '.join(dealer_hand)} = {dealer_total}")

            while dealer_total < 17 and player_total <= 21:
                new_card = draw_card()
                dealer_hand.append(new_card)
                dealer_total = hand_value(dealer_hand)
                print(f"Dealer draws: {new_card}")
                print(f"Dealer hand: {' '.join(dealer_hand)} = {dealer_total}")

            # Determine winner
            win_amount = 0.0

            if player_total > 21:
                result = "bust"
                print("\n❌ You lose - BUST!")
            elif dealer_total > 21:
                result = "win"
                win_amount = bet * 2
                print(f"\n✅ You win - Dealer BUST!")
                print(f"💰 You won GBP {win_amount:.2f}!")
            elif player_total > dealer_total:
                result = "win"
                win_amount = bet * 2
                print(f"\n✅ You win - {player_total} beats {dealer_total}!")
                print(f"💰 You won GBP {win_amount:.2f}!")
            elif player_total == dealer_total:
                result = "push"
                win_amount = bet
                print(f"\n🤝 PUSH - Tie at {player_total}!")
                print(f"💰 Stake returned: GBP {win_amount:.2f}")
            else:
                result = "lose"
                print(f"\n❌ You lose - Dealer has {dealer_total}")

        win_amount = round(win_amount, 2)

        if win_amount > 0:
            with transaction() as conn_tx:
                conn_tx.execute('''
                    UPDATE betting_accounts
                    SET balance = balance + ?,
                        total_won = total_won + ?,
                        updated_at = ?
                    WHERE user_id = ?
                ''', (win_amount, win_amount, datetime.now().isoformat(), user.get('username')))

                # Record game
                conn_tx.execute('''
                    INSERT INTO casino_games
                    (user_id, game_type, bet_amount, result, win_amount, game_data, played_at)
                    VALUES (?, 'blackjack', ?, ?, ?, ?, ?)
                ''', (user.get('username'), bet, result, win_amount,
                      f'P:{player_hand}({player_total}) D:{dealer_hand}({dealer_total})',
                      datetime.now().isoformat()))

            new_balance = balance - bet + win_amount
            print(f"   New Balance: GBP {new_balance:.2f}")
        else:
            # Record game
            with transaction() as conn_tx:
                conn_tx.execute('''
                    INSERT INTO casino_games
                    (user_id, game_type, bet_amount, result, win_amount, game_data, played_at)
                    VALUES (?, 'blackjack', ?, ?, 0, ?, ?)
                ''', (user.get('username'), bet, result,
                      f'P:{player_hand}({player_total}) D:{dealer_hand}({dealer_total})',
                      datetime.now().isoformat()))

            new_balance = balance - bet
            print(f"   Balance: GBP {new_balance:.2f}")

    except Exception as e:
        logger.error(f"Error playing blackjack: {e}")
        print(f"❌ Error playing blackjack: {e}")

    input("\nPress Enter to continue...")


def view_casino_history():
    """View casino gaming history"""
    user = get_current_user()
    if not user:
        print("❌ You must be logged in to view history")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("CASINO GAMING HISTORY")

        print("\n🎮 Filter by game:")
        print("1. All Games")
        print("2. Slots")
        print("3. Roulette")
        print("4. Blackjack")

        filter_choice = input("\nSelect filter (default: 1): ").strip() or "1"

        game_filter = {
            "1": None,
            "2": "slots",
            "3": "roulette",
            "4": "blackjack"
        }.get(filter_choice)

        with get_connection() as conn:
            if game_filter:
                cursor = conn.execute('''
                    SELECT game_type, bet_amount, result, win_amount, game_data, played_at
                    FROM casino_games
                    WHERE user_id = ? AND game_type = ?
                    ORDER BY played_at DESC
                    LIMIT 30
                ''', (user.get('username'), game_filter))
            else:
                cursor = conn.execute('''
                    SELECT game_type, bet_amount, result, win_amount, game_data, played_at
                    FROM casino_games
                    WHERE user_id = ?
                    ORDER BY played_at DESC
                    LIMIT 30
                ''', (user.get('username'),))

            games = cursor.fetchall()

            if not games:
                print("\n❌ No games found")
            else:
                print(f"\n🎰 Last {len(games)} Game(s):")
                print("-" * 70)

                total_bet = 0.0
                total_won = 0.0

                for game in games:
                    try:
                        game_type, bet_amount, result, win_amount, game_data, played_at = game
                        bet_val = float(bet_amount)
                        win_val = float(win_amount or 0)

                        total_bet += bet_val
                        total_won += win_val

                        print(f"\n🎮 {game_type.upper()} - {played_at}")
                        print(f"   Bet: GBP {bet_val:.2f}")

                        if result in ['win', 'blackjack']:
                            print(f"   Result: ✅ WON - GBP {win_val:.2f}")
                        elif result == 'push':
                            print(f"   Result: 🤝 PUSH")
                        else:
                            print(f"   Result: ❌ LOST")

                        if game_data:
                            print(f"   Details: {game_data}")
                    except Exception as e:
                        logger.error(f"Error displaying game: {e}")
                        continue

                print("\n" + "-" * 70)
                print(f"Total Wagered: GBP {total_bet:.2f}")
                print(f"Total Won: GBP {total_won:.2f}")
                print(f"Net Profit/Loss: GBP {total_won - total_bet:.2f}")

    except Exception as e:
        logger.error(f"Error viewing casino history: {e}")
        print(f"❌ Error viewing casino history: {e}")

    input("\nPress Enter to continue...")


# ============================================================================
# PREDICTION MARKETS
# ============================================================================

def browse_predictions():
    """Browse available prediction markets"""
    try:
        print_subheader("PREDICTION MARKETS")

        print("\n📊 Filter by category:")
        print("1. All Categories")
        print("2. Sports")
        print("3. Politics")
        print("4. Entertainment")
        print("5. Academic")
        print("6. Other")

        cat_choice = input("\nSelect category (default: 1): ").strip() or "1"

        category_map = {
            "1": None,
            "2": "sports",
            "3": "politics",
            "4": "entertainment",
            "5": "academic",
            "6": "other"
        }

        category = category_map.get(cat_choice)

        with get_connection() as conn:
            if category:
                cursor = conn.execute('''
                    SELECT market_id, title, description, category, outcome_a, outcome_b,
                           probability_a, probability_b, total_pool, resolution_date
                    FROM prediction_markets
                    WHERE status = 'open' AND category = ?
                    ORDER BY resolution_date
                ''', (category,))
            else:
                cursor = conn.execute('''
                    SELECT market_id, title, description, category, outcome_a, outcome_b,
                           probability_a, probability_b, total_pool, resolution_date
                    FROM prediction_markets
                    WHERE status = 'open'
                    ORDER BY resolution_date
                ''')

            markets = cursor.fetchall()

            if not markets:
                print("\n❌ No prediction markets available")
            else:
                print(f"\n🔮 {len(markets)} Active Prediction Market(s):")
                print("-" * 70)

                for market in markets:
                    try:
                        (market_id, title, description, cat, outcome_a, outcome_b,
                         prob_a, prob_b, total_pool, res_date) = market

                        print(f"\n🔮 Market ID: {market_id}")
                        print(f"   Title: {title}")
                        print(f"   Category: {cat.upper()}")
                        if description:
                            print(f"   Description: {description}")
                        print(f"\n   Outcomes:")
                        print(f"   A) {outcome_a} - {float(prob_a):.1f}% probability")
                        print(f"   B) {outcome_b} - {float(prob_b):.1f}% probability")
                        print(f"\n   Total Pool: GBP {float(total_pool or 0):.2f}")
                        print(f"   Resolves: {res_date}")
                    except Exception as e:
                        logger.error(f"Error displaying market: {e}")
                        continue

    except Exception as e:
        logger.error(f"Error browsing predictions: {e}")
        print(f"❌ Error browsing predictions: {e}")

    input("\nPress Enter to continue...")


def place_prediction_bet():
    """Place a bet on a prediction market"""
    user = get_current_user()
    if not user:
        print("❌ You must be logged in to place prediction bets")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("PLACE PREDICTION BET")

        # Show markets
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT market_id, title, outcome_a, outcome_b, probability_a, probability_b
                FROM prediction_markets
                WHERE status = 'open'
                ORDER BY resolution_date
                LIMIT 15
            ''')
            markets = cursor.fetchall()

            if not markets:
                print("\n❌ No prediction markets available")
                input("\nPress Enter to continue...")
                return

            print("\n🔮 Available Markets:")
            for market in markets:
                market_id, title, outcome_a, outcome_b, prob_a, prob_b = market
                print(f"\n{market_id}. {title}")
                print(f"   A) {outcome_a} ({float(prob_a):.1f}%)")
                print(f"   B) {outcome_b} ({float(prob_b):.1f}%)")

        market_id = input("\nEnter market ID (0 to cancel): ").strip()
        if market_id == "0":
            return

        if not market_id.isdigit():
            print("❌ Invalid market ID")
            input("\nPress Enter to continue...")
            return

        # Get market details
        cursor = conn.execute('''
            SELECT title, outcome_a, outcome_b, probability_a, probability_b
            FROM prediction_markets
            WHERE market_id = ? AND status = 'open'
        ''', (market_id,))
        market = cursor.fetchone()

        if not market:
            print("❌ Market not found or closed")
            input("\nPress Enter to continue...")
            return

        title, outcome_a, outcome_b, prob_a, prob_b = market

        print(f"\n🔮 Market: {title}")
        print(f"A) {outcome_a} ({float(prob_a):.1f}%)")
        print(f"B) {outcome_b} ({float(prob_b):.1f}%)")

        selection = input("\nSelect outcome (A/B): ").strip().upper()

        if selection == 'A':
            selected_outcome = 'outcome_a'
            selected_text = outcome_a
            probability = float(prob_a) / 100
        elif selection == 'B':
            selected_outcome = 'outcome_b'
            selected_text = outcome_b
            probability = float(prob_b) / 100
        else:
            print("❌ Invalid selection")
            input("\nPress Enter to continue...")
            return

        # Calculate odds
        house_edge = 0.05
        odds = round(1 / probability * (1 - house_edge), 2) if probability > 0 else 2.00

        stake_str = input(f"\nEnter stake (GBP {MIN_BET:.2f} - GBP {MAX_BET:.2f}): ").strip()

        try:
            stake = float(stake_str)
        except ValueError:
            print("❌ Invalid stake")
            input("\nPress Enter to continue...")
            return

        if stake < MIN_BET or stake > MAX_BET:
            print(f"❌ Stake must be between GBP {MIN_BET:.2f} and GBP {MAX_BET:.2f}")
            input("\nPress Enter to continue...")
            return

        potential_return = stake * odds

        print(f"\n📊 Bet Summary:")
        print(f"   Market: {title}")
        print(f"   Selection: {selected_text}")
        print(f"   Stake: GBP {stake:.2f}")
        print(f"   Odds: {odds:.2f}")
        print(f"   Potential Return: GBP {potential_return:.2f}")

        confirm = input("\nConfirm prediction bet? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("❌ Bet cancelled")
            input("\nPress Enter to continue...")
            return

        # Check balance
        cursor = conn.execute('SELECT balance FROM betting_accounts WHERE user_id = ?',
                            (user.get('username'),))
        row = cursor.fetchone()
        if not row or float(row[0]) < stake:
            print(f"❌ Insufficient balance")
            input("\nPress Enter to continue...")
            return

        with transaction() as conn_tx:
            # Deduct balance
            conn_tx.execute('''
                UPDATE betting_accounts
                SET balance = balance - ?,
                    total_wagered = total_wagered + ?,
                    updated_at = ?
                WHERE user_id = ?
            ''', (stake, stake, datetime.now().isoformat(), user.get('username')))

            # Place bet
            conn_tx.execute('''
                INSERT INTO prediction_bets
                (user_id, market_id, selection, stake, odds_at_placement, potential_return, status, placed_at)
                VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
            ''', (user.get('username'), market_id, selected_outcome, stake, odds,
                  potential_return, datetime.now().isoformat()))

            # Update pool
            pool_column = 'pool_a' if selected_outcome == 'outcome_a' else 'pool_b'
            validate_identifier(pool_column, "column")
            conn_tx.execute(f'''
                UPDATE prediction_markets
                SET total_pool = total_pool + ?, {pool_column} = {pool_column} + ?
                WHERE market_id = ?
            ''', (stake, stake, market_id))

            # Recalculate probabilities
            cursor = conn_tx.execute(
                'SELECT pool_a, pool_b, total_pool FROM prediction_markets WHERE market_id = ?',
                (market_id,)
            )
            pools = cursor.fetchone()
            if pools and pools[2] > 0:
                new_prob_a = round((pools[0] / pools[2]) * 100, 2)
                new_prob_b = round((pools[1] / pools[2]) * 100, 2)
                conn_tx.execute('''
                    UPDATE prediction_markets
                    SET probability_a = ?, probability_b = ?
                    WHERE market_id = ?
                ''', (new_prob_a, new_prob_b, market_id))

        print("\n✅ Prediction bet placed successfully!")
        logger.info(f"User {user.get('username')} placed prediction bet on market {market_id}")

    except Exception as e:
        logger.error(f"Error placing prediction bet: {e}")
        print(f"❌ Error placing prediction bet: {e}")

    input("\nPress Enter to continue...")


def view_my_predictions():
    """View user's prediction bets"""
    user = get_current_user()
    if not user:
        print("❌ You must be logged in to view predictions")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("MY PREDICTION BETS")

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT pb.bet_id, pm.title, pb.selection, pm.outcome_a, pm.outcome_b,
                       pb.stake, pb.odds_at_placement, pb.potential_return,
                       pb.actual_return, pb.status, pb.placed_at
                FROM prediction_bets pb
                JOIN prediction_markets pm ON pb.market_id = pm.market_id
                WHERE pb.user_id = ?
                ORDER BY pb.placed_at DESC
                LIMIT 30
            ''', (user.get('username'),))

            bets = cursor.fetchall()

            if not bets:
                print("\n❌ No prediction bets found")
            else:
                print(f"\n🔮 {len(bets)} Prediction Bet(s):")
                print("-" * 70)

                total_staked = 0.0
                total_returned = 0.0

                for bet in bets:
                    try:
                        (bet_id, title, selection, outcome_a, outcome_b, stake,
                         odds, potential, actual, status, placed) = bet

                        stake_val = float(stake)
                        potential_val = float(potential)
                        actual_val = float(actual or 0)

                        total_staked += stake_val
                        total_returned += actual_val

                        selected_text = outcome_a if selection == 'outcome_a' else outcome_b

                        print(f"\n🔮 Bet ID: {bet_id}")
                        print(f"   Market: {title}")
                        print(f"   Selection: {selected_text}")
                        print(f"   Stake: GBP {stake_val:.2f} @ {float(odds):.2f}")
                        print(f"   Potential: GBP {potential_val:.2f}")

                        if status == 'won':
                            print(f"   Status: ✅ WON - Returned GBP {actual_val:.2f}")
                        elif status == 'lost':
                            print(f"   Status: ❌ LOST")
                        else:
                            print(f"   Status: ⏳ PENDING")

                        print(f"   Placed: {placed}")
                    except Exception as e:
                        logger.error(f"Error displaying prediction: {e}")
                        continue

                print("\n" + "-" * 70)
                print(f"Total Staked: GBP {total_staked:.2f}")
                print(f"Total Returned: GBP {total_returned:.2f}")
                print(f"Net Profit/Loss: GBP {total_returned - total_staked:.2f}")

    except Exception as e:
        logger.error(f"Error viewing predictions: {e}")
        print(f"❌ Error viewing predictions: {e}")

    input("\nPress Enter to continue...")


# ============================================================================
# ADMIN FUNCTIONS
# ============================================================================

def create_sports_event():
    """Create a new sports event (Admin only)"""
    if not is_admin():
        print("❌ Admin access required")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("CREATE SPORTS EVENT")

        event_name = input("\nEvent name: ").strip()
        if not event_name:
            print("❌ Event name required")
            input("\nPress Enter to continue...")
            return

        print("\nSport types: Football, Basketball, Tennis, Rugby, Cricket, Boxing, etc.")
        sport_type = input("Sport type: ").strip()

        team_a = input("Team/Player A name: ").strip()
        team_b = input("Team/Player B name: ").strip()

        if not team_a or not team_b:
            print("❌ Both teams/players required")
            input("\nPress Enter to continue...")
            return

        try:
            odds_a = float(input(f"Odds for {team_a} (e.g., 2.50): ").strip())
            odds_b = float(input(f"Odds for {team_b} (e.g., 1.80): ").strip())
        except ValueError:
            print("❌ Invalid odds")
            input("\nPress Enter to continue...")
            return

        has_draw = input("Include draw option? (yes/no): ").strip().lower() == 'yes'
        odds_draw = None
        if has_draw:
            try:
                odds_draw = float(input("Odds for draw (e.g., 3.20): ").strip())
            except ValueError:
                print("❌ Invalid draw odds")
                input("\nPress Enter to continue...")
                return

        event_date = input("Event date (YYYY-MM-DD): ").strip()
        event_time = input("Event time (HH:MM, optional): ").strip() or None

        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO betting_events
                (event_name, event_type, sport_type, team_a, team_b,
                 odds_a, odds_b, odds_draw, event_date, event_time, status, created_by)
                VALUES (?, 'sports', ?, ?, ?, ?, ?, ?, ?, ?, 'upcoming', ?)
            ''', (event_name, sport_type, team_a, team_b, odds_a, odds_b,
                  odds_draw, event_date, event_time, get_current_user().get('username')))

            event_id = cursor.lastrowid

        print(f"\n✅ Event created successfully! Event ID: {event_id}")
        logger.info(f"Admin created sports event: {event_name} (ID: {event_id})")

    except Exception as e:
        logger.error(f"Error creating event: {e}")
        print(f"❌ Error creating event: {e}")

    input("\nPress Enter to continue...")


def update_event_odds():
    """Update odds for an event (Admin only)"""
    if not is_admin():
        print("❌ Admin access required")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("UPDATE EVENT ODDS")

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT event_id, event_name, team_a, team_b, odds_a, odds_b, odds_draw
                FROM betting_events
                WHERE status = 'upcoming'
                ORDER BY event_date
                LIMIT 20
            ''')
            events = cursor.fetchall()

            if not events:
                print("\n❌ No upcoming events")
                input("\nPress Enter to continue...")
                return

            print("\n📅 Upcoming Events:")
            for event in events:
                event_id, name, team_a, team_b, odds_a, odds_b, odds_draw = event
                print(f"\n{event_id}. {name}")
                print(f"   {team_a}: {float(odds_a):.2f}")
                print(f"   {team_b}: {float(odds_b):.2f}")
                if odds_draw:
                    print(f"   Draw: {float(odds_draw):.2f}")

        event_id = input("\nEnter event ID to update: ").strip()
        if not event_id.isdigit():
            print("❌ Invalid event ID")
            input("\nPress Enter to continue...")
            return

        cursor = conn.execute('''
            SELECT event_name, team_a, team_b, odds_draw
            FROM betting_events
            WHERE event_id = ? AND status = 'upcoming'
        ''', (event_id,))
        event = cursor.fetchone()

        if not event:
            print("❌ Event not found")
            input("\nPress Enter to continue...")
            return

        event_name, team_a, team_b, odds_draw = event

        print(f"\n📊 Updating odds for: {event_name}")

        try:
            new_odds_a = float(input(f"New odds for {team_a}: ").strip())
            new_odds_b = float(input(f"New odds for {team_b}: ").strip())

            new_odds_draw = None
            if odds_draw:
                new_odds_draw = float(input("New odds for draw: ").strip())

            with transaction() as conn_tx:
                if new_odds_draw:
                    conn_tx.execute('''
                        UPDATE betting_events
                        SET odds_a = ?, odds_b = ?, odds_draw = ?
                        WHERE event_id = ?
                    ''', (new_odds_a, new_odds_b, new_odds_draw, event_id))
                else:
                    conn_tx.execute('''
                        UPDATE betting_events
                        SET odds_a = ?, odds_b = ?
                        WHERE event_id = ?
                    ''', (new_odds_a, new_odds_b, event_id))

            print("\n✅ Odds updated successfully!")
            logger.info(f"Admin updated odds for event {event_id}")

        except ValueError:
            print("❌ Invalid odds values")

    except Exception as e:
        logger.error(f"Error updating odds: {e}")
        print(f"❌ Error updating odds: {e}")

    input("\nPress Enter to continue...")


def settle_sports_event():
    """Settle a sports event and pay out winners (Admin only)"""
    if not is_admin():
        print("❌ Admin access required")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("SETTLE SPORTS EVENT")

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT event_id, event_name, team_a, team_b, odds_draw
                FROM betting_events
                WHERE status = 'upcoming'
                ORDER BY event_date
            ''')
            events = cursor.fetchall()

            if not events:
                print("\n❌ No events to settle")
                input("\nPress Enter to continue...")
                return

            print("\n📅 Events to Settle:")
            for event in events:
                event_id, name, team_a, team_b, odds_draw = event
                print(f"\n{event_id}. {name}")
                print(f"   A) {team_a}")
                print(f"   B) {team_b}")
                if odds_draw:
                    print(f"   D) Draw")

        event_id = input("\nEnter event ID to settle: ").strip()
        if not event_id.isdigit():
            print("❌ Invalid event ID")
            input("\nPress Enter to continue...")
            return

        cursor = conn.execute('''
            SELECT event_name, team_a, team_b, odds_draw
            FROM betting_events
            WHERE event_id = ? AND status = 'upcoming'
        ''', (event_id,))
        event = cursor.fetchone()

        if not event:
            print("❌ Event not found")
            input("\nPress Enter to continue...")
            return

        event_name, team_a, team_b, odds_draw = event

        print(f"\n🏆 Settling: {event_name}")
        print(f"A) {team_a} won")
        print(f"B) {team_b} won")
        if odds_draw:
            print(f"D) Draw")
        print(f"V) Void event (refund all bets)")

        result_choice = input("\nEnter result: ").strip().upper()

        result_map = {
            'A': team_a,
            'B': team_b,
            'D': 'Draw',
            'V': 'void'
        }

        result = result_map.get(result_choice)
        if not result:
            print("❌ Invalid result")
            input("\nPress Enter to continue...")
            return

        confirm = input(f"\nConfirm settle as '{result}'? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("❌ Settlement cancelled")
            input("\nPress Enter to continue...")
            return

        # Get all bets for this event
        cursor = conn.execute('''
            SELECT bet_id, user_id, selection, stake, potential_return
            FROM sports_bets
            WHERE event_id = ? AND status = 'pending'
        ''', (event_id,))
        bets = cursor.fetchall()

        winners = 0
        losers = 0
        total_payout = 0.0

        with transaction() as conn_tx:
            # Update event
            conn_tx.execute('''
                UPDATE betting_events
                SET status = 'settled', result = ?
                WHERE event_id = ?
            ''', (result, event_id))

            # Process bets
            for bet in bets:
                bet_id, user_id, selection, stake, potential_return = bet
                stake_val = float(stake)
                potential_val = float(potential_return)

                if result == 'void':
                    # Refund
                    conn_tx.execute('''
                        UPDATE sports_bets
                        SET status = 'void', actual_return = ?, settled_at = ?
                        WHERE bet_id = ?
                    ''', (stake_val, datetime.now().isoformat(), bet_id))

                    conn_tx.execute('''
                        UPDATE betting_accounts
                        SET balance = balance + ?, updated_at = ?
                        WHERE user_id = ?
                    ''', (stake_val, datetime.now().isoformat(), user_id))

                    total_payout += stake_val
                elif selection == result:
                    # Winner
                    conn_tx.execute('''
                        UPDATE sports_bets
                        SET status = 'won', actual_return = ?, settled_at = ?
                        WHERE bet_id = ?
                    ''', (potential_val, datetime.now().isoformat(), bet_id))

                    conn_tx.execute('''
                        UPDATE betting_accounts
                        SET balance = balance + ?, total_won = total_won + ?, updated_at = ?
                        WHERE user_id = ?
                    ''', (potential_val, potential_val, datetime.now().isoformat(), user_id))

                    winners += 1
                    total_payout += potential_val
                else:
                    # Loser
                    conn_tx.execute('''
                        UPDATE sports_bets
                        SET status = 'lost', actual_return = 0, settled_at = ?
                        WHERE bet_id = ?
                    ''', (datetime.now().isoformat(), bet_id))
                    losers += 1

        print(f"\n✅ Event settled successfully!")
        print(f"   Result: {result}")
        print(f"   Total Bets: {len(bets)}")
        print(f"   Winners: {winners}")
        print(f"   Losers: {losers}")
        print(f"   Total Payout: GBP {total_payout:.2f}")

        logger.info(f"Admin settled event {event_id} with result: {result}")

    except Exception as e:
        logger.error(f"Error settling event: {e}")
        print(f"❌ Error settling event: {e}")

    input("\nPress Enter to continue...")


def create_prediction_market():
    """Create a new prediction market (Admin only)"""
    if not is_admin():
        print("❌ Admin access required")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("CREATE PREDICTION MARKET")

        title = input("\nMarket title: ").strip()
        if not title:
            print("❌ Title required")
            input("\nPress Enter to continue...")
            return

        description = input("Description (optional): ").strip()

        print("\nCategories: sports, politics, entertainment, academic, other")
        category = input("Category: ").strip().lower()
        if category not in PREDICTION_CATEGORIES:
            print(f"❌ Invalid category. Using 'other'")
            category = 'other'

        outcome_a = input("Outcome A: ").strip()
        outcome_b = input("Outcome B: ").strip()

        if not outcome_a or not outcome_b:
            print("❌ Both outcomes required")
            input("\nPress Enter to continue...")
            return

        resolution_date = input("Resolution date (YYYY-MM-DD): ").strip()

        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO prediction_markets
                (title, description, category, outcome_a, outcome_b, resolution_date,
                 status, created_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'open', ?, ?)
            ''', (title, description, category, outcome_a, outcome_b, resolution_date,
                  get_current_user().get('username'), datetime.now().isoformat()))

            market_id = cursor.lastrowid

        print(f"\n✅ Prediction market created! Market ID: {market_id}")
        logger.info(f"Admin created prediction market: {title} (ID: {market_id})")

    except Exception as e:
        logger.error(f"Error creating market: {e}")
        print(f"❌ Error creating market: {e}")

    input("\nPress Enter to continue...")


def resolve_prediction_market():
    """Resolve a prediction market (Admin only)"""
    if not is_admin():
        print("❌ Admin access required")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("RESOLVE PREDICTION MARKET")

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT market_id, title, outcome_a, outcome_b, total_pool
                FROM prediction_markets
                WHERE status = 'open'
                ORDER BY resolution_date
            ''')
            markets = cursor.fetchall()

            if not markets:
                print("\n❌ No markets to resolve")
                input("\nPress Enter to continue...")
                return

            print("\n🔮 Open Markets:")
            for market in markets:
                market_id, title, outcome_a, outcome_b, total_pool = market
                print(f"\n{market_id}. {title}")
                print(f"   A) {outcome_a}")
                print(f"   B) {outcome_b}")
                print(f"   Pool: GBP {float(total_pool or 0):.2f}")

        market_id = input("\nEnter market ID to resolve: ").strip()
        if not market_id.isdigit():
            print("❌ Invalid market ID")
            input("\nPress Enter to continue...")
            return

        cursor = conn.execute('''
            SELECT title, outcome_a, outcome_b
            FROM prediction_markets
            WHERE market_id = ? AND status = 'open'
        ''', (market_id,))
        market = cursor.fetchone()

        if not market:
            print("❌ Market not found")
            input("\nPress Enter to continue...")
            return

        title, outcome_a, outcome_b = market

        print(f"\n🔮 Resolving: {title}")
        print(f"A) {outcome_a}")
        print(f"B) {outcome_b}")

        result_choice = input("\nEnter result (A/B): ").strip().upper()

        if result_choice == 'A':
            result = 'outcome_a'
            result_text = outcome_a
        elif result_choice == 'B':
            result = 'outcome_b'
            result_text = outcome_b
        else:
            print("❌ Invalid result")
            input("\nPress Enter to continue...")
            return

        confirm = input(f"\nConfirm resolve as '{result_text}'? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("❌ Resolution cancelled")
            input("\nPress Enter to continue...")
            return

        # Get all bets
        cursor = conn.execute('''
            SELECT bet_id, user_id, selection, potential_return
            FROM prediction_bets
            WHERE market_id = ? AND status = 'pending'
        ''', (market_id,))
        bets = cursor.fetchall()

        winners = 0
        losers = 0
        total_payout = 0.0

        with transaction() as conn_tx:
            # Update market
            conn_tx.execute('''
                UPDATE prediction_markets
                SET status = 'resolved', result = ?
                WHERE market_id = ?
            ''', (result, market_id))

            # Process bets
            for bet in bets:
                bet_id, user_id, selection, potential_return = bet
                potential_val = float(potential_return)

                if selection == result:
                    # Winner
                    conn_tx.execute('''
                        UPDATE prediction_bets
                        SET status = 'won', actual_return = ?, settled_at = ?
                        WHERE bet_id = ?
                    ''', (potential_val, datetime.now().isoformat(), bet_id))

                    conn_tx.execute('''
                        UPDATE betting_accounts
                        SET balance = balance + ?, total_won = total_won + ?, updated_at = ?
                        WHERE user_id = ?
                    ''', (potential_val, potential_val, datetime.now().isoformat(), user_id))

                    winners += 1
                    total_payout += potential_val
                else:
                    # Loser
                    conn_tx.execute('''
                        UPDATE prediction_bets
                        SET status = 'lost', actual_return = 0, settled_at = ?
                        WHERE bet_id = ?
                    ''', (datetime.now().isoformat(), bet_id))
                    losers += 1

        print(f"\n✅ Market resolved successfully!")
        print(f"   Result: {result_text}")
        print(f"   Total Bets: {len(bets)}")
        print(f"   Winners: {winners}")
        print(f"   Losers: {losers}")
        print(f"   Total Payout: GBP {total_payout:.2f}")

        logger.info(f"Admin resolved market {market_id} with result: {result}")

    except Exception as e:
        logger.error(f"Error resolving market: {e}")
        print(f"❌ Error resolving market: {e}")

    input("\nPress Enter to continue...")


def view_betting_statistics():
    """View betting shop statistics (Admin only)"""
    if not is_admin():
        print("❌ Admin access required")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("BETTING STATISTICS")

        with get_connection() as conn:
            # Account stats
            cursor = conn.execute('''
                SELECT COUNT(*), SUM(balance), SUM(total_deposited),
                       SUM(total_withdrawn), SUM(total_wagered), SUM(total_won)
                FROM betting_accounts
            ''')
            account_stats = cursor.fetchone()

            # Sports betting stats
            cursor = conn.execute('''
                SELECT COUNT(*), SUM(stake), SUM(actual_return)
                FROM sports_bets
                WHERE status IN ('won', 'lost', 'cashed_out')
            ''')
            sports_stats = cursor.fetchone()

            # Casino stats
            cursor = conn.execute('''
                SELECT COUNT(*), SUM(bet_amount), SUM(win_amount)
                FROM casino_games
            ''')
            casino_stats = cursor.fetchone()

            # Prediction market stats
            cursor = conn.execute('''
                SELECT COUNT(*), SUM(stake), SUM(actual_return)
                FROM prediction_bets
                WHERE status IN ('won', 'lost')
            ''')
            prediction_stats = cursor.fetchone()

        print("\n📊 ACCOUNT STATISTICS:")
        print(f"   Total Accounts: {account_stats[0] or 0}")
        print(f"   Total Balance: GBP {float(account_stats[1] or 0):.2f}")
        print(f"   Total Deposited: GBP {float(account_stats[2] or 0):.2f}")
        print(f"   Total Withdrawn: GBP {float(account_stats[3] or 0):.2f}")
        print(f"   Total Wagered: GBP {float(account_stats[4] or 0):.2f}")
        print(f"   Total Won: GBP {float(account_stats[5] or 0):.2f}")

        print("\n🏆 SPORTS BETTING:")
        print(f"   Total Bets: {sports_stats[0] or 0}")
        print(f"   Total Staked: GBP {float(sports_stats[1] or 0):.2f}")
        print(f"   Total Returned: GBP {float(sports_stats[2] or 0):.2f}")

        sports_profit = float(sports_stats[1] or 0) - float(sports_stats[2] or 0)
        print(f"   House Profit: GBP {sports_profit:.2f}")

        print("\n🎰 CASINO GAMES:")
        print(f"   Total Games: {casino_stats[0] or 0}")
        print(f"   Total Wagered: GBP {float(casino_stats[1] or 0):.2f}")
        print(f"   Total Won: GBP {float(casino_stats[2] or 0):.2f}")

        casino_profit = float(casino_stats[1] or 0) - float(casino_stats[2] or 0)
        print(f"   House Profit: GBP {casino_profit:.2f}")

        print("\n🔮 PREDICTION MARKETS:")
        print(f"   Total Bets: {prediction_stats[0] or 0}")
        print(f"   Total Staked: GBP {float(prediction_stats[1] or 0):.2f}")
        print(f"   Total Returned: GBP {float(prediction_stats[2] or 0):.2f}")

        prediction_profit = float(prediction_stats[1] or 0) - float(prediction_stats[2] or 0)
        print(f"   House Profit: GBP {prediction_profit:.2f}")

        print("\n💰 OVERALL:")
        total_profit = sports_profit + casino_profit + prediction_profit
        print(f"   Total House Profit: GBP {total_profit:.2f}")

    except Exception as e:
        logger.error(f"Error viewing statistics: {e}")
        print(f"❌ Error viewing statistics: {e}")

    input("\nPress Enter to continue...")


# ============================================================================
# MENU SYSTEMS
# ============================================================================

def account_menu():
    """Account management submenu"""
    while True:
        try:
            print_subheader("ACCOUNT MANAGEMENT")
            print("\n1. View Balance")
            print("2. Deposit Funds")
            print("3. Withdraw Funds")
            print("4. Transaction History")
            print("0. Back to Main Menu")

            choice = input("\nChoice: ").strip()

            if choice == "1":
                view_balance()
            elif choice == "2":
                deposit_funds()
            elif choice == "3":
                withdraw_funds()
            elif choice == "4":
                view_transaction_history()
            elif choice == "0":
                break
            else:
                print("❌ Invalid choice")
                input("Press Enter to continue...")

        except Exception as e:
            logger.error(f"Error in account menu: {e}")
            print(f"❌ Error: {e}")
            input("Press Enter to continue...")


def sports_betting_menu():
    """Sports betting submenu"""
    while True:
        try:
            print_subheader("SPORTS BETTING")
            print("\n1. View Sports Events")
            print("2. Place Single Bet")
            print("3. Place Accumulator Bet")
            print("4. View My Bets")
            print("0. Back to Main Menu")

            choice = input("\nChoice: ").strip()

            if choice == "1":
                view_sports_events()
            elif choice == "2":
                place_sports_bet()
            elif choice == "3":
                place_accumulator_bet()
            elif choice == "4":
                view_my_bets()
            elif choice == "0":
                break
            else:
                print("❌ Invalid choice")
                input("Press Enter to continue...")

        except Exception as e:
            logger.error(f"Error in sports betting menu: {e}")
            print(f"❌ Error: {e}")
            input("Press Enter to continue...")


def casino_menu():
    """Casino games submenu"""
    while True:
        try:
            print_subheader("CASINO GAMES")
            print("\n1. Slot Machine")
            print("2. Roulette")
            print("3. Blackjack")
            print("4. View Gaming History")
            print("0. Back to Main Menu")

            choice = input("\nChoice: ").strip()

            if choice == "1":
                play_slots()
            elif choice == "2":
                play_roulette()
            elif choice == "3":
                play_blackjack()
            elif choice == "4":
                view_casino_history()
            elif choice == "0":
                break
            else:
                print("❌ Invalid choice")
                input("Press Enter to continue...")

        except Exception as e:
            logger.error(f"Error in casino menu: {e}")
            print(f"❌ Error: {e}")
            input("Press Enter to continue...")


def prediction_market_menu():
    """Prediction markets submenu"""
    while True:
        try:
            print_subheader("PREDICTION MARKETS")
            print("\n1. Browse Prediction Markets")
            print("2. Place Prediction Bet")
            print("3. View My Predictions")
            print("0. Back to Main Menu")

            choice = input("\nChoice: ").strip()

            if choice == "1":
                browse_predictions()
            elif choice == "2":
                place_prediction_bet()
            elif choice == "3":
                view_my_predictions()
            elif choice == "0":
                break
            else:
                print("❌ Invalid choice")
                input("Press Enter to continue...")

        except Exception as e:
            logger.error(f"Error in prediction market menu: {e}")
            print(f"❌ Error: {e}")
            input("Press Enter to continue...")


def admin_menu():
    """Admin panel submenu"""
    if not is_admin():
        print("❌ Admin access required")
        input("\nPress Enter to continue...")
        return

    while True:
        try:
            print_subheader("ADMIN PANEL")
            print("\n📅 SPORTS EVENTS:")
            print("1. Create Sports Event")
            print("2. Update Event Odds")
            print("3. Settle Sports Event")

            print("\n🔮 PREDICTION MARKETS:")
            print("4. Create Prediction Market")
            print("5. Resolve Prediction Market")

            print("\n📊 REPORTS:")
            print("6. View Statistics")

            print("\n0. Back to Main Menu")

            choice = input("\nChoice: ").strip()

            if choice == "1":
                create_sports_event()
            elif choice == "2":
                update_event_odds()
            elif choice == "3":
                settle_sports_event()
            elif choice == "4":
                create_prediction_market()
            elif choice == "5":
                resolve_prediction_market()
            elif choice == "6":
                view_betting_statistics()
            elif choice == "0":
                break
            else:
                print("❌ Invalid choice")
                input("Press Enter to continue...")

        except Exception as e:
            logger.error(f"Error in admin menu: {e}")
            print(f"❌ Error: {e}")
            input("Press Enter to continue...")


def betting_shop_menu():
    """Main betting shop menu"""
    try:
        # Initialize database
        init_betting_db()
    except Exception as e:
        logger.error(f"Failed to initialize betting database: {e}")
        print(f"❌ Failed to initialize betting system: {e}")
        input("\nPress Enter to continue...")
        return

    user = get_current_user()
    if not user:
        print("❌ You must be logged in to access the Betting Shop")
        input("\nPress Enter to continue...")
        return

    while True:
        try:
            print_header("UNIVERSITY BETTING SHOP")

            if user:
                print(f"\nLogged in as: {user.get('username')} ({user.get('role')})")

                # Show quick balance
                try:
                    with get_connection() as conn:
                        cursor = conn.execute(
                            'SELECT balance FROM betting_accounts WHERE user_id = ?',
                            (user.get('username'),)
                        )
                        row = cursor.fetchone()
                        if row:
                            print(f"Balance: GBP {float(row[0]):.2f}")
                except Exception:
                    logger.debug("Could not retrieve betting account balance")

            print("\n💰 ACCOUNT:")
            print("1. Account Management")

            print("\n🏆 SPORTS BETTING:")
            print("2. Sports Betting")

            print("\n🎰 CASINO:")
            print("3. Casino Games")

            print("\n🔮 PREDICTIONS:")
            print("4. Prediction Markets")

            if is_admin():
                print("\n🔧 ADMIN:")
                print("9. Admin Panel")

            print("\n0. Return to Main Menu")

            choice = input("\nEnter choice: ").strip()

            if choice == "1":
                account_menu()
            elif choice == "2":
                sports_betting_menu()
            elif choice == "3":
                casino_menu()
            elif choice == "4":
                prediction_market_menu()
            elif choice == "9" and is_admin():
                admin_menu()
            elif choice == "0":
                break
            else:
                print("❌ Invalid choice")
                input("Press Enter to continue...")

        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
            break
        except Exception as e:
            logger.error(f"Error in betting shop menu: {e}")
            print(f"❌ An error occurred: {e}")
            input("Press Enter to continue...")


def launch_betting_shop_cli(auth=None):
    """Launch betting shop CLI (called from main menu)"""
    betting_shop_menu()


if __name__ == "__main__":
    betting_shop_menu()
