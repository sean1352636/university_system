from education_system.university_system.infrastructure.database.db import sqlite3, DatabaseManager
from education_system.university_system.core.paths import DEFAULT_DB_PATH
import datetime


class FinanceMixin:
    def view_student_fees(self):
        """View outstanding fees and payment history for children"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to view fees.")
            return

        if self.auth.current_user.get('role', '') != 'parent':
            print("This function is only available for parent accounts.")
            return

        if not self.auth.check_permission('view_fees'):
            print("You don't have permission to view fees.")
            return

        children = self.view_children()

        if not children:
            print("You have no children registered in the system.")
            return

        print("\nSelect child to view fees:")
        for i, child in enumerate(children):
            print(f"{i+1}. {child[1]} {child[3]} (ID: {child[0]})")

        choice = input("Enter the number of the child: ")
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(children):
                raise ValueError

            selected_child = children[index]
            student_id = selected_child[0]

            conn = None
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
                conn.execute("PRAGMA busy_timeout = 30000")
                cursor = conn.cursor()

                # Get outstanding fees
                cursor.execute('''
                SELECT fee_type, description, amount, due_date, payment_status
                FROM student_fees
                WHERE student_id = ? AND payment_status = 'pending'
                ORDER BY due_date
                ''', (student_id,))

                outstanding_fees = cursor.fetchall()

                # Get payment history
                cursor.execute('''
                SELECT fee_type, description, amount, paid_date, payment_method, transaction_id
                FROM student_fees
                WHERE student_id = ? AND payment_status = 'paid'
                ORDER BY paid_date DESC
                LIMIT 10
                ''', (student_id,))

                payment_history = cursor.fetchall()

                print(f"\nFees for {selected_child[1]} {selected_child[3]}:")

                if outstanding_fees:
                    print("\nOutstanding Fees:")
                    total_outstanding = 0
                    for fee in outstanding_fees:
                        fee_type, description, amount, due_date, status = fee
                        total_outstanding += float(amount)
                        print(f"- {fee_type}: £{amount}")
                        print(f"  Description: {description}")
                        print(f"  Due Date: {due_date}")
                        print()

                    print(f"Total Outstanding: £{total_outstanding:.2f}")
                else:
                    print("\nNo outstanding fees.")

                if payment_history:
                    print("\nRecent Payment History:")
                    for payment in payment_history:
                        fee_type, description, amount, paid_date, method, transaction = payment
                        print(f"- {fee_type}: £{amount} paid on {paid_date}")
                        print(f"  Method: {method}")
                        if transaction:
                            print(f"  Transaction ID: {transaction}")
                        print()

            except sqlite3.Error as e:
                print(f"Database error viewing fees: {e}")
            finally:
                if conn:
                    conn.close()

        except (ValueError, IndexError):
            print("Invalid choice.")

    def manage_meal_account(self):
        """Manage student meal account and view transactions"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to manage meal accounts.")
            return

        if self.auth.current_user.get('role', '') != 'parent':
            print("This function is only available for parent accounts.")
            return

        if not self.auth.check_permission('manage_meal_account'):
            print("You don't have permission to manage meal accounts.")
            return

        children = self.view_children()

        if not children:
            print("You have no children registered in the system.")
            return

        print("\nSelect child to manage meal account:")
        for i, child in enumerate(children):
            print(f"{i+1}. {child[1]} {child[3]} (ID: {child[0]})")

        choice = input("Enter the number of the child: ")
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(children):
                raise ValueError

            selected_child = children[index]
            student_id = selected_child[0]

            conn = None
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
                conn.execute("PRAGMA busy_timeout = 30000")
                cursor = conn.cursor()

                # Get or create meal account
                cursor.execute('SELECT balance, low_balance_threshold, auto_topup_enabled, auto_topup_amount FROM meal_accounts WHERE student_id = ?', (student_id,))
                account = cursor.fetchone()

                if not account:
                    cursor.execute('INSERT INTO meal_accounts (student_id, last_updated) VALUES (?, ?)',
                                 (student_id, datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                    conn.commit()
                    account = (0.00, 10.00, 0, 20.00)

                balance, threshold, auto_topup, topup_amount = account

                print(f"\nMeal Account for {selected_child[1]} {selected_child[3]}:")
                print(f"Current Balance: £{balance:.2f}")
                print(f"Low Balance Threshold: £{threshold:.2f}")
                print(f"Auto Top-up: {'Enabled' if auto_topup else 'Disabled'}")
                if auto_topup:
                    print(f"Auto Top-up Amount: £{topup_amount:.2f}")

                # Get recent transactions
                cursor.execute('''
                SELECT transaction_type, amount, description, created_at, balance_after
                FROM transactions
                WHERE source_type = 'meal' AND student_id = ?
                ORDER BY created_at DESC
                LIMIT 10
                ''', (student_id,))

                transactions = cursor.fetchall()

                if transactions:
                    print("\nRecent Transactions:")
                    for transaction in transactions:
                        trans_type, amount, description, date, balance_after = transaction
                        print(f"- {date}: {trans_type} £{amount:.2f} - {description}")
                        print(f"  Balance after: £{balance_after:.2f}")

                print("\nOptions:")
                print("1. Add funds")
                print("2. View all transactions")
                print("3. Update auto top-up settings")
                print("4. Back to menu")

                option = input("Select option: ")

                if option == '1':
                    try:
                        amount = float(input("Enter amount to add: £"))
                        if amount <= 0:
                            print("Invalid amount.")
                            return

                        new_balance = float(balance) + amount
                        current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                        cursor.execute('UPDATE meal_accounts SET balance = ?, last_updated = ? WHERE student_id = ?',
                                     (new_balance, current_time, student_id))

                        cursor.execute('''INSERT INTO transactions
                                       (source_type, student_id, transaction_type, amount, description, created_at, balance_after)
                                       VALUES ('meal', ?, ?, ?, ?, ?, ?)''',
                                     (student_id, 'credit', amount, 'Parent top-up', current_time, new_balance))

                        conn.commit()
                        print(f"Successfully added £{amount:.2f}. New balance: £{new_balance:.2f}")

                    except ValueError:
                        print("Invalid amount entered.")

                elif option == '3':
                    print("\nAuto Top-up Settings:")
                    enable = input("Enable auto top-up? (y/n): ").lower() == 'y'

                    if enable:
                        try:
                            new_threshold = float(input(f"Low balance threshold (current: £{threshold:.2f}): £"))
                            new_topup_amount = float(input(f"Auto top-up amount (current: £{topup_amount:.2f}): £"))

                            cursor.execute('''UPDATE meal_accounts
                                           SET auto_topup_enabled = ?, low_balance_threshold = ?, auto_topup_amount = ?
                                           WHERE student_id = ?''',
                                         (1, new_threshold, new_topup_amount, student_id))
                            conn.commit()
                            print("Auto top-up settings updated successfully.")
                        except ValueError:
                            print("Invalid values entered.")
                    else:
                        cursor.execute('UPDATE meal_accounts SET auto_topup_enabled = 0 WHERE student_id = ?', (student_id,))
                        conn.commit()
                        print("Auto top-up disabled.")

            except sqlite3.Error as e:
                print(f"Database error managing meal account: {e}")
            finally:
                if conn:
                    conn.close()

        except (ValueError, IndexError):
            print("Invalid choice.")

    def view_fundraising_campaigns(self):
        """View and participate in fundraising campaigns"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to view fundraising campaigns.")
            return

        if self.auth.current_user.get('role', '') != 'parent':
            print("This function is only available for parent accounts.")
            return

        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
            conn.execute("PRAGMA busy_timeout = 30000")
            cursor = conn.cursor()

            # Get active campaigns
            cursor.execute('''
            SELECT id, campaign_name, description, target_amount, current_amount, start_date, end_date
            FROM fundraising_campaigns
            WHERE status = 'active' AND end_date >= date('now')
            ORDER BY end_date
            ''')

            campaigns = cursor.fetchall()

            if not campaigns:
                print("No active fundraising campaigns at this time.")
                return

            print("\nActive Fundraising Campaigns:")
            for campaign in campaigns:
                id, name, description, target, current, start_date, end_date = campaign
                progress = (float(current) / float(target)) * 100 if target > 0 else 0

                print(f"\n{name}")
                print(f"Description: {description}")
                print(f"Target: £{target:.2f}")
                print(f"Raised: £{current:.2f} ({progress:.1f}%)")
                print(f"Campaign ends: {end_date}")

            # Get parent's donation history
            parent_id = self.get_parent_id_from_user(self.auth.current_user['id'])
            if parent_id:
                cursor.execute('''
                SELECT fc.campaign_name, fd.amount, fd.donation_date, s.first_name, s.last_name
                FROM fundraising_donations fd
                JOIN fundraising_campaigns fc ON fd.campaign_id = fc.id
                LEFT JOIN students s ON fd.student_id = s.student_id
                WHERE fd.parent_id = ?
                ORDER BY fd.donation_date DESC
                LIMIT 5
                ''', (parent_id,))

                donations = cursor.fetchall()

                if donations:
                    print("\nYour Recent Donations:")
                    for donation in donations:
                        campaign_name, amount, date, student_first, student_last = donation
                        student_info = f" (for {student_first} {student_last})" if student_first else ""
                        print(f"- £{amount:.2f} to {campaign_name} on {date}{student_info}")

        except sqlite3.Error as e:
            print(f"Database error viewing fundraising campaigns: {e}")
        finally:
            if conn:
                conn.close()

    def donate_to_campaign(self):
        """Make a donation to a fundraising campaign"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to make donations.")
            return

        if self.auth.current_user.get('role', '') != 'parent':
            print("This function is only available for parent accounts.")
            return

        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
            conn.execute("PRAGMA busy_timeout = 30000")
            cursor = conn.cursor()

            # Get active campaigns
            cursor.execute('''
            SELECT id, campaign_name, description, target_amount, current_amount
            FROM fundraising_campaigns
            WHERE status = 'active' AND end_date >= date('now')
            ORDER BY campaign_name
            ''')

            campaigns = cursor.fetchall()

            if not campaigns:
                print("No active fundraising campaigns at this time.")
                return

            print("\nSelect campaign to donate to:")
            for i, campaign in enumerate(campaigns):
                id, name, description, target, current = campaign
                remaining = float(target) - float(current)
                print(f"{i+1}. {name}")
                print(f"   Target: £{target:.2f}, Raised: £{current:.2f}, Remaining: £{remaining:.2f}")
                print(f"   {description}")
                print()

            choice = input("Enter campaign number: ")
            try:
                index = int(choice) - 1
                if index < 0 or index >= len(campaigns):
                    raise ValueError

                selected_campaign = campaigns[index]
                campaign_id = selected_campaign[0]

                # Get donation details
                amount = float(input("Enter donation amount: £"))
                if amount <= 0:
                    print("Invalid donation amount.")
                    return

                children = self.view_children()
                if children:
                    print("\nDonate on behalf of (optional):")
                    print("0. Anonymous donation")
                    for i, child in enumerate(children):
                        print(f"{i+1}. {child[1]} {child[3]}")

                    child_choice = input("Enter choice: ")
                    if child_choice == '0':
                        student_id = None
                        anonymous = True
                    else:
                        try:
                            child_index = int(child_choice) - 1
                            if 0 <= child_index < len(children):
                                student_id = children[child_index][0]
                                anonymous = False
                            else:
                                student_id = None
                                anonymous = True
                        except ValueError:
                            student_id = None
                            anonymous = True
                else:
                    student_id = None
                    anonymous = True

                parent_id = self.get_parent_id_from_user(self.auth.current_user['id'])
                if not parent_id:
                    print("Error retrieving parent ID.")
                    return

                donation_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # Record donation
                cursor.execute('''
                INSERT INTO fundraising_donations
                (campaign_id, parent_id, student_id, amount, donation_date, anonymous)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', (campaign_id, parent_id, student_id, amount, donation_date, anonymous))

                # Update campaign total
                cursor.execute('''
                UPDATE fundraising_campaigns
                SET current_amount = current_amount + ?
                WHERE id = ?
                ''', (amount, campaign_id))

                conn.commit()
                print(f"Thank you for your donation of £{amount:.2f}!")

            except (ValueError, IndexError):
                print("Invalid selection.")
            except ValueError:
                print("Invalid donation amount.")

        except sqlite3.Error as e:
            print(f"Database error processing donation: {e}")
        finally:
            if conn:
                conn.close()

    def view_all_transactions(self, student_id):
        """View all meal account transactions for a student"""
        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
            conn.execute("PRAGMA busy_timeout = 30000")
            cursor = conn.cursor()

            # Get all transactions
            cursor.execute('''
            SELECT transaction_type, amount, description, created_at, balance_after
            FROM transactions
            WHERE source_type = 'meal' AND student_id = ?
            ORDER BY created_at DESC
            ''', (student_id,))

            transactions = cursor.fetchall()

            if not transactions:
                print("No transactions found.")
                return

            print("\nAll Meal Account Transactions:")
            print("-" * 60)

            for transaction in transactions:
                trans_type, amount, description, date, balance_after = transaction
                print(f"{date}: {trans_type.upper()} £{amount:.2f}")
                print(f"  Description: {description}")
                print(f"  Balance after: £{balance_after:.2f}")
                print()

        except sqlite3.Error as e:
            print(f"Database error viewing transactions: {e}")
        finally:
            if conn:
                conn.close()
