"""
Betting Shop CLI - Prediction market functions.
"""

from datetime import datetime

from education_system.university_system.modules.services.cli.betting_shop_cli.constants import (
    logger, get_connection, transaction, validate_identifier,
    MIN_BET, MAX_BET,
)
from education_system.university_system.modules.services.cli.betting_shop_cli.helpers import print_subheader, get_current_user


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
