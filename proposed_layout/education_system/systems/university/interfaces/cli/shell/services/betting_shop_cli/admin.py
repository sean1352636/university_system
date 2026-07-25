"""
Betting Shop CLI - Admin functions.
"""

from datetime import datetime

from education_system.systems.university.interfaces.cli.shell.services.betting_shop_cli.constants import (
    logger, get_connection, transaction,
    PREDICTION_CATEGORIES,
)
from education_system.systems.university.interfaces.cli.shell.services.betting_shop_cli.helpers import print_subheader, get_current_user, is_admin


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
                    print("   D) Draw")

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
            print("D) Draw")
        print("V) Void event (refund all bets)")

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

        print("\n✅ Event settled successfully!")
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
            print("❌ Invalid category. Using 'other'")
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

        print("\n✅ Market resolved successfully!")
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
