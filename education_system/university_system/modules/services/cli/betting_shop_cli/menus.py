"""
Betting Shop CLI - Menu systems and entry points.
"""

from .constants import logger, get_connection, init_betting_db
from .helpers import print_header, print_subheader, get_current_user, is_admin
from .account import view_balance, deposit_funds, withdraw_funds, view_transaction_history
from .sports import view_sports_events, place_sports_bet, view_my_bets, place_accumulator_bet
from .casino import play_slots, play_roulette, play_blackjack, view_casino_history
from .predictions import browse_predictions, place_prediction_bet, view_my_predictions
from .admin import (
    create_sports_event, update_event_odds, settle_sports_event,
    create_prediction_market, resolve_prediction_market, view_betting_statistics
)


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
