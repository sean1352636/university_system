"""
Betting Shop CLI - Account management functions.
"""

from datetime import datetime

from education_system.post_18.university_system.modules.services.cli.betting_shop_cli.constants import (
    logger, get_connection, transaction,
    MIN_DEPOSIT, MAX_DEPOSIT,
)
from education_system.post_18.university_system.modules.services.cli.betting_shop_cli.helpers import print_subheader, get_current_user


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
                print("\n📊 Account Statistics:")
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
                INSERT INTO transactions
                (source_type, student_id, transaction_type, amount, balance_before, balance_after,
                 description, payment_method, created_at)
                VALUES ('betting', ?, 'deposit', ?, ?, ?, ?, ?, ?)
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
        print("\n⚠️  Withdrawal Verification:")
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
                INSERT INTO transactions
                (source_type, student_id, transaction_type, amount, balance_before, balance_after,
                 description, payment_method, created_at)
                VALUES ('betting', ?, 'withdrawal', ?, ?, ?, ?, ?, ?)
            ''', (user.get('username'), amount, current_balance, balance_after,
                  f'Withdrawal to {withdrawal_method}', withdrawal_method,
                  datetime.now().isoformat()))

        print("\n✅ Withdrawal processed successfully!")
        print(f"   Amount: GBP {amount:.2f}")
        print(f"   Method: {withdrawal_method}")
        print(f"   New Balance: GBP {balance_after:.2f}")
        print("\n   Processing time: 1-3 business days")

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
                FROM transactions
                WHERE source_type = 'betting' AND student_id = ?
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
