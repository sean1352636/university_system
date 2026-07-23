"""
Betting Shop CLI Interface

Provides command-line interface for betting shop management including:
- Account management (create, deposit, withdraw, balance)
- Sports betting (events, place bets, cash out, settle)
- Prediction markets (create, bet, resolve)
- Casino games (slots, blackjack, roulette)
- Reports and analytics
"""

from datetime import datetime

from education_system.post_18.university_system.modules.domain.commerce.betting.services.betting_core import (
    AccountManager,
    SportsBettingManager,
    PredictionMarketManager,
    CasinoManager,
    ReportManager,
    init_betting_db,
    MIN_BET,
    MAX_BET,
    MIN_DEPOSIT,
    MAX_DEPOSIT,
    CASINO_GAMES,
    PREDICTION_CATEGORIES,
    BET_STATUSES,
)


class BettingCLI:
    """Command-line interface for the Betting Shop."""

    def __init__(self):
        """Initialize the Betting CLI and database."""
        init_betting_db()

    def run(self):
        """Run the betting CLI main loop."""
        while True:
            self._display_main_menu()
            choice = input("\nSelect an option: ").strip()

            if choice == '0':
                print("\nReturning to main menu...")
                break
            elif choice == '1':
                self._accounts_menu()
            elif choice == '2':
                self._sports_menu()
            elif choice == '3':
                self._predictions_menu()
            elif choice == '4':
                self._casino_menu()
            elif choice == '5':
                self._reports_menu()
            else:
                print("\nInvalid option. Please try again.")
                input("\nPress Enter to continue...")

    # ========== Main Menu ==========

    def _display_main_menu(self):
        """Display the main menu."""
        print("\n" + "=" * 70)
        print("  BETTING SHOP MANAGEMENT SYSTEM".center(70))
        print("=" * 70)
        print("\n  1. Accounts")
        print("  2. Sports Betting")
        print("  3. Prediction Markets")
        print("  4. Casino Games")
        print("  5. Reports")
        print("  0. Back to Main Menu")

    # ========== Accounts ==========

    def _accounts_menu(self):
        """Accounts sub-menu."""
        while True:
            print("\n" + "-" * 50)
            print("  ACCOUNT MANAGEMENT")
            print("-" * 50)
            print("  1. Create / Get Account")
            print("  2. View Account")
            print("  3. Deposit Funds")
            print("  4. Withdraw Funds")
            print("  5. Transaction History")
            print("  0. Back")

            choice = input("\nSelect an option: ").strip()
            try:
                if choice == '0':
                    break
                elif choice == '1':
                    self._get_or_create_account()
                elif choice == '2':
                    self._view_account()
                elif choice == '3':
                    self._deposit()
                elif choice == '4':
                    self._withdraw()
                elif choice == '5':
                    self._transaction_history()
                else:
                    print("Invalid option.")
            except Exception as e:
                print(f"\nError: {e}")
            input("\nPress Enter to continue...")

    def _get_or_create_account(self):
        """Create or get an account."""
        print("\n--- Create / Get Account ---")
        user_id = input("User ID: ").strip()
        username = input("Username: ").strip()
        email = input("Email (optional): ").strip() or None

        account = AccountManager.get_or_create_account(user_id, username, email)
        if account:
            print(f"\nAccount ID: {account.get('account_id', 'N/A')}")
            print(f"User: {account.get('username', 'N/A')}")
            print(f"Balance: GBP {account.get('balance', 0):.2f}")
            print(f"Status: {account.get('status', 'N/A')}")
        else:
            print("Failed to create/get account.")

    def _view_account(self):
        """View account details."""
        user_id = input("User ID: ").strip()
        account = AccountManager.get_account(user_id)
        if not account:
            print("Account not found.")
            return
        print(f"\nAccount ID: {account['account_id']}")
        print(f"Username: {account['username']}")
        print(f"Email: {account.get('email', 'N/A')}")
        print(f"Balance: GBP {account['balance']:.2f}")
        print(f"Total Deposited: GBP {account.get('total_deposited', 0):.2f}")
        print(f"Total Withdrawn: GBP {account.get('total_withdrawn', 0):.2f}")
        print(f"Total Wagered: GBP {account.get('total_wagered', 0):.2f}")
        print(f"Total Won: GBP {account.get('total_won', 0):.2f}")
        print(f"Status: {account['status']}")

    def _deposit(self):
        """Deposit funds."""
        user_id = input("User ID: ").strip()
        print(f"Min: GBP {MIN_DEPOSIT:.2f}, Max: GBP {MAX_DEPOSIT:.2f}")
        amount = float(input("Amount: ").strip())
        payment_method = input("Payment method (card/bank_transfer/cash): ").strip()

        txn_id = AccountManager.deposit(user_id, amount, payment_method)
        if txn_id:
            print(f"\nDeposit successful (Transaction ID: {txn_id})")
        else:
            print("\nDeposit failed. Check amount limits and account status.")

    def _withdraw(self):
        """Withdraw funds."""
        user_id = input("User ID: ").strip()
        amount = float(input("Amount: ").strip())
        payment_method = input("Payment method (card/bank_transfer): ").strip()

        txn_id = AccountManager.withdraw(user_id, amount, payment_method)
        if txn_id:
            print(f"\nWithdrawal successful (Transaction ID: {txn_id})")
        else:
            print("\nWithdrawal failed. Check balance and account status.")

    def _transaction_history(self):
        """View transaction history."""
        user_id = input("User ID: ").strip()
        transactions = AccountManager.get_transaction_history(user_id)
        if not transactions:
            print("\nNo transactions found.")
            return
        print(f"\n{'ID':<6}{'Type':<15}{'Amount':<12}{'Balance After':<15}{'Date'}")
        print("-" * 60)
        for t in transactions:
            print(f"{t.get('transaction_id', ''):<6}"
                  f"{t.get('transaction_type', ''):<15}"
                  f"GBP {t.get('amount', 0):<10.2f}"
                  f"GBP {t.get('balance_after', 0):<13.2f}"
                  f"{t.get('created_at', '')}")

    # ========== Sports Betting ==========

    def _sports_menu(self):
        """Sports betting sub-menu."""
        while True:
            print("\n" + "-" * 50)
            print("  SPORTS BETTING")
            print("-" * 50)
            print("  1. Create Event")
            print("  2. View Upcoming Events")
            print("  3. View Event Details")
            print("  4. Place Bet")
            print("  5. View My Bets")
            print("  6. Cash Out Bet")
            print("  7. Settle Event")
            print("  0. Back")

            choice = input("\nSelect an option: ").strip()
            try:
                if choice == '0':
                    break
                elif choice == '1':
                    self._create_event()
                elif choice == '2':
                    self._upcoming_events()
                elif choice == '3':
                    self._view_event()
                elif choice == '4':
                    self._place_sports_bet()
                elif choice == '5':
                    self._view_sports_bets()
                elif choice == '6':
                    self._cash_out_bet()
                elif choice == '7':
                    self._settle_event()
                else:
                    print("Invalid option.")
            except Exception as e:
                print(f"\nError: {e}")
            input("\nPress Enter to continue...")

    def _create_event(self):
        """Create a new sports event."""
        print("\n--- Create Sports Event ---")
        event_name = input("Event name: ").strip()
        event_type = input("Event type (match/tournament/race): ").strip()
        sport_type = input("Sport type (football/tennis/basketball/etc): ").strip()
        team_a = input("Team/Player A: ").strip()
        team_b = input("Team/Player B: ").strip()
        odds_a = float(input("Odds for A: ").strip())
        odds_b = float(input("Odds for B: ").strip())
        draw_input = input("Odds for draw (blank if N/A): ").strip()
        odds_draw = float(draw_input) if draw_input else None
        event_date = input("Event date (YYYY-MM-DD): ").strip()
        event_time = input("Event time (HH:MM, optional): ").strip() or None

        event_id = SportsBettingManager.create_event(
            event_name=event_name, event_type=event_type, sport_type=sport_type,
            team_a=team_a, team_b=team_b, odds_a=odds_a, odds_b=odds_b,
            odds_draw=odds_draw, event_date=event_date, event_time=event_time,
        )
        if event_id:
            print(f"\nEvent created (ID: {event_id})")
        else:
            print("\nFailed to create event.")

    def _upcoming_events(self):
        """View upcoming events."""
        sport = input("Filter by sport (blank for all): ").strip() or None
        events = SportsBettingManager.get_upcoming_events(sport_type=sport)
        if not events:
            print("\nNo upcoming events.")
            return
        print(f"\n{'ID':<6}{'Event':<30}{'Sport':<12}{'Date':<12}{'A Odds':<8}{'B Odds':<8}{'Draw'}")
        print("-" * 85)
        for e in events:
            draw = f"{e.get('odds_draw', '')}" if e.get('odds_draw') else "N/A"
            print(f"{e['event_id']:<6}{e['event_name']:<30}{e.get('sport_type', ''):<12}"
                  f"{e['event_date']:<12}{e['odds_a']:<8.2f}{e['odds_b']:<8.2f}{draw}")

    def _view_event(self):
        """View event details."""
        event_id = int(input("Event ID: ").strip())
        event = SportsBettingManager.get_event(event_id)
        if not event:
            print("Event not found.")
            return
        print(f"\nEvent: {event['event_name']}")
        print(f"Type: {event['event_type']}")
        print(f"Sport: {event.get('sport_type', 'N/A')}")
        print(f"Teams: {event['team_a']} vs {event['team_b']}")
        print(f"Odds: {event['team_a']}={event['odds_a']}, {event['team_b']}={event['odds_b']}"
              + (f", Draw={event['odds_draw']}" if event.get('odds_draw') else ""))
        print(f"Date: {event['event_date']} {event.get('event_time', '')}")
        print(f"Status: {event['status']}")
        if event.get('result'):
            print(f"Result: {event['result']}")

    def _place_sports_bet(self):
        """Place a sports bet."""
        print(f"\n--- Place Sports Bet (Min: GBP {MIN_BET}, Max: GBP {MAX_BET}) ---")
        user_id = input("User ID: ").strip()
        event_id = int(input("Event ID: ").strip())

        event = SportsBettingManager.get_event(event_id)
        if not event:
            print("Event not found.")
            return

        print(f"\n{event['event_name']}")
        print(f"  1. {event['team_a']} (odds: {event['odds_a']})")
        print(f"  2. {event['team_b']} (odds: {event['odds_b']})")
        if event.get('odds_draw'):
            print(f"  3. Draw (odds: {event['odds_draw']})")

        sel = input("Selection (1/2/3): ").strip()
        selection_map = {'1': 'team_a', '2': 'team_b', '3': 'draw'}
        selection = selection_map.get(sel)
        if not selection:
            print("Invalid selection.")
            return

        stake = float(input("Stake (GBP): ").strip())

        bet_id = SportsBettingManager.place_bet(user_id, event_id, selection, stake)
        if bet_id:
            print(f"\nBet placed (ID: {bet_id})")
        else:
            print("\nFailed to place bet. Check balance and bet limits.")

    def _view_sports_bets(self):
        """View user's sports bets."""
        user_id = input("User ID: ").strip()
        status_input = input("Status filter (blank for all): ").strip() or None
        bets = SportsBettingManager.get_user_bets(user_id, status=status_input)
        if not bets:
            print("\nNo bets found.")
            return
        print(f"\n{'ID':<6}{'Event':<25}{'Selection':<12}{'Stake':<10}{'Odds':<8}{'Return':<10}{'Status'}")
        print("-" * 85)
        for b in bets:
            print(f"{b['bet_id']:<6}{b.get('event_name', ''):<25}{b['selection']:<12}"
                  f"GBP {b['stake']:<8.2f}{b['odds']:<8.2f}"
                  f"GBP {b.get('actual_return', 0):<8.2f}{b['status']}")

    def _cash_out_bet(self):
        """Cash out a pending bet."""
        bet_id = int(input("Bet ID: ").strip())
        user_id = input("User ID: ").strip()
        amount = SportsBettingManager.cash_out_bet(bet_id, user_id)
        if amount is not None:
            print(f"\nBet cashed out for GBP {amount:.2f}")
        else:
            print("\nCash out failed. Bet may not be eligible.")

    def _settle_event(self):
        """Settle an event."""
        event_id = int(input("Event ID: ").strip())
        event = SportsBettingManager.get_event(event_id)
        if event:
            print(f"Event: {event['event_name']}")
            print(f"  team_a = {event['team_a']}")
            print(f"  team_b = {event['team_b']}")
            print("  draw")
        result = input("Result (team_a/team_b/draw): ").strip()
        settled = SportsBettingManager.settle_event(event_id, result)
        print("Event settled." if settled else "Failed to settle event.")

    # ========== Prediction Markets ==========

    def _predictions_menu(self):
        """Prediction markets sub-menu."""
        while True:
            print("\n" + "-" * 50)
            print("  PREDICTION MARKETS")
            print("-" * 50)
            print("  1. Create Market")
            print("  2. View Open Markets")
            print("  3. View Market Details")
            print("  4. Place Prediction Bet")
            print("  5. View My Predictions")
            print("  6. Resolve Market")
            print("  0. Back")

            choice = input("\nSelect an option: ").strip()
            try:
                if choice == '0':
                    break
                elif choice == '1':
                    self._create_market()
                elif choice == '2':
                    self._open_markets()
                elif choice == '3':
                    self._view_market()
                elif choice == '4':
                    self._place_prediction()
                elif choice == '5':
                    self._view_predictions()
                elif choice == '6':
                    self._resolve_market()
                else:
                    print("Invalid option.")
            except Exception as e:
                print(f"\nError: {e}")
            input("\nPress Enter to continue...")

    def _create_market(self):
        """Create a prediction market."""
        print("\n--- Create Prediction Market ---")
        title = input("Title: ").strip()
        description = input("Description: ").strip()
        print(f"Categories: {', '.join(PREDICTION_CATEGORIES)}")
        category = input("Category: ").strip()
        outcome_a = input("Outcome A: ").strip()
        outcome_b = input("Outcome B: ").strip()
        resolution_date = input("Resolution date (YYYY-MM-DD): ").strip()

        market_id = PredictionMarketManager.create_market(
            title=title, description=description, category=category,
            outcome_a=outcome_a, outcome_b=outcome_b, resolution_date=resolution_date,
        )
        if market_id:
            print(f"\nMarket created (ID: {market_id})")
        else:
            print("\nFailed to create market.")

    def _open_markets(self):
        """View open markets."""
        cat = input("Filter by category (blank for all): ").strip() or None
        markets = PredictionMarketManager.get_open_markets(category=cat)
        if not markets:
            print("\nNo open markets.")
            return
        print(f"\n{'ID':<6}{'Title':<35}{'Category':<12}{'Pool':<12}{'Resolve By'}")
        print("-" * 75)
        for m in markets:
            print(f"{m['market_id']:<6}{m['title']:<35}{m['category']:<12}"
                  f"GBP {m['total_pool']:<10.2f}{m['resolution_date']}")

    def _view_market(self):
        """View market details."""
        market_id = int(input("Market ID: ").strip())
        market = PredictionMarketManager.get_market(market_id)
        if not market:
            print("Market not found.")
            return
        print(f"\nMarket: {market['title']}")
        print(f"Description: {market.get('description', 'N/A')}")
        print(f"Category: {market['category']}")
        print(f"Outcome A: {market['outcome_a']} (Prob: {market['probability_a']}%, Pool: GBP {market['pool_a']:.2f})")
        print(f"Outcome B: {market['outcome_b']} (Prob: {market['probability_b']}%, Pool: GBP {market['pool_b']:.2f})")
        print(f"Total Pool: GBP {market['total_pool']:.2f}")
        print(f"Resolution Date: {market['resolution_date']}")
        print(f"Status: {market['status']}")

    def _place_prediction(self):
        """Place a prediction bet."""
        print(f"\n--- Place Prediction Bet (Min: GBP {MIN_BET}, Max: GBP {MAX_BET}) ---")
        user_id = input("User ID: ").strip()
        market_id = int(input("Market ID: ").strip())

        market = PredictionMarketManager.get_market(market_id)
        if not market:
            print("Market not found.")
            return

        print(f"\n{market['title']}")
        print(f"  1. {market['outcome_a']} (Prob: {market['probability_a']}%)")
        print(f"  2. {market['outcome_b']} (Prob: {market['probability_b']}%)")

        sel = input("Selection (1/2): ").strip()
        selection = 'outcome_a' if sel == '1' else 'outcome_b' if sel == '2' else None
        if not selection:
            print("Invalid selection.")
            return

        stake = float(input("Stake (GBP): ").strip())

        bet_id = PredictionMarketManager.place_prediction_bet(user_id, market_id, selection, stake)
        if bet_id:
            print(f"\nPrediction bet placed (ID: {bet_id})")
        else:
            print("\nFailed to place bet.")

    def _view_predictions(self):
        """View user's prediction bets."""
        user_id = input("User ID: ").strip()
        bets = PredictionMarketManager.get_user_predictions(user_id)
        if not bets:
            print("\nNo prediction bets found.")
            return
        print(f"\n{'ID':<6}{'Market':<30}{'Selection':<15}{'Stake':<10}{'Odds':<8}{'Status'}")
        print("-" * 80)
        for b in bets:
            print(f"{b['bet_id']:<6}{b.get('title', ''):<30}{b['selection']:<15}"
                  f"GBP {b['stake']:<8.2f}{b['odds_at_placement']:<8.2f}{b['status']}")

    def _resolve_market(self):
        """Resolve a prediction market."""
        market_id = int(input("Market ID: ").strip())
        market = PredictionMarketManager.get_market(market_id)
        if market:
            print(f"Market: {market['title']}")
            print(f"  outcome_a = {market['outcome_a']}")
            print(f"  outcome_b = {market['outcome_b']}")
        result = input("Result (outcome_a/outcome_b): ").strip()
        resolved = PredictionMarketManager.resolve_market(market_id, result)
        print("Market resolved." if resolved else "Failed to resolve market.")

    # ========== Casino ==========

    def _casino_menu(self):
        """Casino games sub-menu."""
        while True:
            print("\n" + "-" * 50)
            print("  CASINO GAMES")
            print("-" * 50)
            print("  1. Play Slots")
            print("  2. Play Blackjack")
            print("  3. Play Roulette")
            print("  4. Start Session")
            print("  5. Game History")
            print("  0. Back")

            choice = input("\nSelect an option: ").strip()
            try:
                if choice == '0':
                    break
                elif choice == '1':
                    self._play_slots()
                elif choice == '2':
                    self._play_blackjack()
                elif choice == '3':
                    self._play_roulette()
                elif choice == '4':
                    self._start_session()
                elif choice == '5':
                    self._game_history()
                else:
                    print("Invalid option.")
            except Exception as e:
                print(f"\nError: {e}")
            input("\nPress Enter to continue...")

    def _play_slots(self):
        """Play slots."""
        user_id = input("User ID: ").strip()
        bet = float(input(f"Bet amount (GBP {MIN_BET}-{MAX_BET}): ").strip())
        sid = input("Session ID (optional): ").strip()
        session_id = int(sid) if sid else None

        result = CasinoManager.play_slots(user_id, bet, session_id)
        if not result['success']:
            print(f"\nError: {result.get('error', 'Unknown error')}")
            return
        print(f"\nReels: [ {' | '.join(result['reels'])} ]")
        if result['is_jackpot']:
            print("*** JACKPOT! ***")
        if result['win_amount'] > 0:
            print(f"WIN! GBP {result['win_amount']:.2f}")
        else:
            print("No win this time.")

    def _play_blackjack(self):
        """Play blackjack."""
        user_id = input("User ID: ").strip()
        bet = float(input(f"Bet amount (GBP {MIN_BET}-{MAX_BET}): ").strip())
        sid = input("Session ID (optional): ").strip()
        session_id = int(sid) if sid else None

        result = CasinoManager.play_blackjack(user_id, bet, session_id)
        if not result['success']:
            print(f"\nError: {result.get('error', 'Unknown error')}")
            return
        print(f"\nYour hand: {result['player_hand']} (Total: {result['player_total']})")
        print(f"Dealer hand: {result['dealer_hand']} (Total: {result['dealer_total']})")
        print(f"Result: {result['result'].upper()}")
        if result['win_amount'] > 0:
            print(f"Win: GBP {result['win_amount']:.2f}")

    def _play_roulette(self):
        """Play roulette."""
        user_id = input("User ID: ").strip()
        bet = float(input(f"Bet amount (GBP {MIN_BET}-{MAX_BET}): ").strip())

        print("\nBet types:")
        print("  1. Number (0-36)")
        print("  2. Color (red/black)")
        print("  3. Odd/Even")
        print("  4. High/Low")

        bt = input("Bet type (1-4): ").strip()
        type_map = {'1': 'number', '2': 'color', '3': 'odd_even', '4': 'high_low'}
        bet_type = type_map.get(bt)
        if not bet_type:
            print("Invalid bet type.")
            return

        if bet_type == 'number':
            bet_value = input("Number (0-36): ").strip()
        elif bet_type == 'color':
            bet_value = input("Color (red/black): ").strip()
        elif bet_type == 'odd_even':
            bet_value = input("Odd or Even: ").strip().lower()
        else:
            bet_value = input("High (19-36) or Low (1-18): ").strip().lower()

        sid = input("Session ID (optional): ").strip()
        session_id = int(sid) if sid else None

        result = CasinoManager.play_roulette(user_id, bet, bet_type, bet_value, session_id)
        if not result['success']:
            print(f"\nError: {result.get('error', 'Unknown error')}")
            return
        print(f"\nWheel landed on: {result['result_number']} ({result['result_color']})")
        if result['win']:
            print(f"WIN! GBP {result['win_amount']:.2f}")
        else:
            print("No win this time.")

    def _start_session(self):
        """Start a casino session."""
        user_id = input("User ID: ").strip()
        print(f"Games: {', '.join(CASINO_GAMES)}")
        game_type = input("Game type: ").strip()
        session_id = CasinoManager.start_session(user_id, game_type)
        if session_id:
            print(f"\nSession started (ID: {session_id})")
        else:
            print("\nFailed to start session.")

    def _game_history(self):
        """View game history."""
        user_id = input("User ID: ").strip()
        game_type = input("Game type filter (blank for all): ").strip() or None
        history = CasinoManager.get_game_history(user_id, game_type=game_type)
        if not history:
            print("\nNo game history found.")
            return
        print(f"\n{'ID':<6}{'Game':<12}{'Bet':<10}{'Result':<10}{'Win':<10}{'Date'}")
        print("-" * 65)
        for g in history:
            print(f"{g['game_id']:<6}{g['game_type']:<12}"
                  f"GBP {g['bet_amount']:<8.2f}{g['result']:<10}"
                  f"GBP {g['win_amount']:<8.2f}{g['played_at']}")

    # ========== Reports ==========

    def _reports_menu(self):
        """Reports sub-menu."""
        while True:
            print("\n" + "-" * 50)
            print("  REPORTS & ANALYTICS")
            print("-" * 50)
            print("  1. Overall Statistics")
            print("  2. Admin Report")
            print("  0. Back")

            choice = input("\nSelect an option: ").strip()
            try:
                if choice == '0':
                    break
                elif choice == '1':
                    self._overall_stats()
                elif choice == '2':
                    self._admin_report()
                else:
                    print("Invalid option.")
            except Exception as e:
                print(f"\nError: {e}")
            input("\nPress Enter to continue...")

    def _overall_stats(self):
        """Show overall statistics."""
        stats = ReportManager.get_overall_statistics()
        if not stats:
            print("\nNo statistics available.")
            return
        print("\n--- Overall Statistics ---")
        print(f"Total Accounts: {stats.get('total_accounts', 0)}")
        print(f"Total Balance: GBP {stats.get('total_balance', 0):.2f}")
        print(f"Total Wagered: GBP {stats.get('total_wagered', 0):.2f}")
        print(f"Total Paid Out: GBP {stats.get('total_paid_out', 0):.2f}")
        print(f"House Profit: GBP {stats.get('house_profit', 0):.2f}")
        print(f"Sports Bets: {stats.get('sports_bets', 0)}")
        print(f"Casino Games: {stats.get('casino_games', 0)}")

    def _admin_report(self):
        """Generate admin report."""
        start = input("Start date (blank for all time): ").strip() or None
        end = input("End date (blank for present): ").strip() or None
        report = ReportManager.generate_admin_report(start, end)
        print(report)


def main():
    """Entry point for the Betting Shop CLI."""
    cli = BettingCLI()
    cli.run()


if __name__ == "__main__":
    main()
