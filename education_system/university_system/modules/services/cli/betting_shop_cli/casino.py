"""
Betting Shop CLI - Casino game functions.
"""

import random
import time
from datetime import datetime

from education_system.university_system.modules.services.cli.betting_shop_cli.constants import (
    logger, get_connection, transaction,
    MIN_BET, MAX_BET,
)
from education_system.university_system.modules.services.cli.betting_shop_cli.helpers import print_subheader, get_current_user


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
