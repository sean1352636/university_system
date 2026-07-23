"""
Betting Shop CLI - Sports betting functions.
"""

from datetime import datetime

from education_system.post_18.university_system.modules.services.cli.betting_shop_cli.constants import (
    logger, get_connection, transaction,
    MIN_BET, MAX_BET,
)
from education_system.post_18.university_system.modules.services.cli.betting_shop_cli.helpers import print_subheader, get_current_user


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

            print("\nSelections:")
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

            print("\n📊 Bet Summary:")
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
                            print("   Status: ❌ LOST")
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

        print("\n📊 Accumulator Summary:")
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
                print("❌ Insufficient balance")
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
