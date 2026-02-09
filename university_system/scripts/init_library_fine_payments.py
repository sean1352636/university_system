#!/usr/bin/env python3
"""
Initialize library_fine_payments table and migrate existing payment data

This script:
1. Creates the library_fine_payments table if it doesn't exist
2. Migrates existing fine payment data from book_loans notes
3. Verifies the setup
"""

import sqlite3
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from university_system.modules.shared.constants import paths

def init_library_fine_payments_table():
    """Create library_fine_payments table"""
    try:
        conn = sqlite3.connect(str(paths.DEFAULT_DB_PATH))
        cursor = conn.cursor()

        print("Creating library_fine_payments table...")

        # Create the table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS library_fine_payments (
            payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            loan_id INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            book_id TEXT NOT NULL,
            book_title TEXT,
            fine_amount REAL NOT NULL,
            payment_amount REAL NOT NULL,
            payment_method TEXT NOT NULL,
            payment_date TEXT NOT NULL,
            processed_by TEXT,
            transaction_ref TEXT,
            status TEXT DEFAULT 'completed',
            refund_amount REAL DEFAULT 0.0,
            refunded_date TEXT,
            refunded_by TEXT,
            refund_reason TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (loan_id) REFERENCES book_loans(loan_id)
        )
        ''')

        # Create indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_fine_payments_user ON library_fine_payments(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_fine_payments_loan ON library_fine_payments(loan_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_fine_payments_date ON library_fine_payments(payment_date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_fine_payments_status ON library_fine_payments(status)')

        conn.commit()
        print("✅ Table created successfully!")

        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='library_fine_payments'")
        if cursor.fetchone():
            print("✅ Table verified!")
        else:
            print("❌ Table not found!")
            return False

        conn.close()
        return True

    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
        return False

def migrate_existing_payments():
    """Migrate existing payment data from book_loans notes"""
    try:
        conn = sqlite3.connect(str(paths.DEFAULT_DB_PATH))
        cursor = conn.cursor()

        print("\nMigrating existing paid fines...")

        # Find all loans with "Fine paid" in notes
        cursor.execute('''
            SELECT bl.loan_id, bl.user_id, bl.book_id, b.title, bl.notes, bl.due_date
            FROM book_loans bl
            LEFT JOIN books b ON bl.book_id = b.book_id
            WHERE bl.notes LIKE '%Fine paid%'
            AND NOT EXISTS (
                SELECT 1 FROM library_fine_payments lfp WHERE lfp.loan_id = bl.loan_id
            )
        ''')

        loans_to_migrate = cursor.fetchall()

        if not loans_to_migrate:
            print("No existing paid fines to migrate.")
            conn.close()
            return True

        print(f"Found {len(loans_to_migrate)} paid fines to migrate...")

        migrated = 0
        for loan_id, user_id, book_id, book_title, notes, due_date in loans_to_migrate:
            # Try to extract payment amount from notes
            payment_amount = 0.0
            payment_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            payment_method = 'Unknown'

            if notes:
                # Try to parse amount from notes
                import re
                amount_match = re.search(r'£?([\d.]+)', notes)
                if amount_match:
                    try:
                        payment_amount = float(amount_match.group(1))
                    except:
                        payment_amount = 5.0  # Default fine amount

                # Try to parse date from notes
                date_match = re.search(r'Fine paid on (\d{4}-\d{2}-\d{2})', notes)
                if date_match:
                    payment_date = date_match.group(1) + ' 00:00:00'

                # Try to determine payment method
                if 'Finance Account' in notes:
                    payment_method = 'Student Finance Account'
                elif 'Card' in notes or 'Credit' in notes:
                    payment_method = 'Card'
                elif 'Cash' in notes:
                    payment_method = 'Cash'
                else:
                    payment_method = 'Cash/Card at Library Desk'

            if payment_amount == 0.0:
                payment_amount = 5.0  # Default if we can't determine

            # Insert into library_fine_payments
            cursor.execute('''
                INSERT INTO library_fine_payments
                (loan_id, user_id, book_id, book_title, fine_amount, payment_amount,
                 payment_method, payment_date, processed_by, transaction_ref, status, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                loan_id, user_id, book_id, book_title or 'Unknown',
                payment_amount, payment_amount, payment_method, payment_date,
                'System Migration', f'MIGRATED_{loan_id}', 'completed',
                f'Migrated from book_loans notes: {notes[:100] if notes else ""}'
            ))

            migrated += 1

        conn.commit()
        print(f"✅ Migrated {migrated} paid fines!")
        conn.close()
        return True

    except sqlite3.Error as e:
        print(f"❌ Migration error: {e}")
        if 'conn' in locals():
            conn.close()
        return False

def verify_setup():
    """Verify the setup is working"""
    try:
        conn = sqlite3.connect(str(paths.DEFAULT_DB_PATH))
        cursor = conn.cursor()

        print("\n" + "="*60)
        print("VERIFICATION REPORT")
        print("="*60)

        # Count total payments
        cursor.execute('SELECT COUNT(*) FROM library_fine_payments')
        total_payments = cursor.fetchone()[0]
        print(f"Total fine payments recorded: {total_payments}")

        # Count by status
        cursor.execute('SELECT status, COUNT(*) FROM library_fine_payments GROUP BY status')
        for status, count in cursor.fetchall():
            print(f"  - {status}: {count}")

        # Show users with paid fines
        cursor.execute('''
            SELECT lfp.user_id,
                   s.first_name, s.last_name,
                   COUNT(DISTINCT lfp.payment_id) as payments,
                   SUM(lfp.payment_amount) as total_paid,
                   SUM(COALESCE(lfp.refund_amount, 0)) as total_refunded
            FROM library_fine_payments lfp
            LEFT JOIN students s ON lfp.user_id = s.student_id
            WHERE lfp.status = 'completed'
            GROUP BY lfp.user_id, s.first_name, s.last_name
            HAVING (total_paid - total_refunded) > 0
            ORDER BY total_paid DESC
            LIMIT 10
        ''')

        users = cursor.fetchall()

        print(f"\nUsers with refundable paid fines: {len(users)}")
        if users:
            print("\nTop users with paid fines:")
            print(f"{'User ID':<15} {'Name':<30} {'Payments':<10} {'Paid':<12} {'Refunded':<12} {'Available':<12}")
            print("-" * 95)
            for user_id, first_name, last_name, payments, total_paid, total_refunded in users:
                name = f"{first_name or ''} {last_name or ''}".strip() or 'Unknown'
                available = total_paid - total_refunded
                print(f"{user_id:<15} {name:<30} {payments:<10} £{total_paid:<11.2f} £{total_refunded:<11.2f} £{available:<11.2f}")

        # Show recent payments
        cursor.execute('''
            SELECT payment_id, user_id, book_title, payment_amount, payment_method, payment_date
            FROM library_fine_payments
            ORDER BY payment_date DESC
            LIMIT 5
        ''')

        recent = cursor.fetchall()
        if recent:
            print("\nRecent payments:")
            print(f"{'ID':<8} {'User':<15} {'Book':<30} {'Amount':<10} {'Method':<25} {'Date':<20}")
            print("-" * 110)
            for payment_id, user_id, book_title, amount, method, date in recent:
                book_title = (book_title or 'Unknown')[:28]
                print(f"{payment_id:<8} {user_id:<15} {book_title:<30} £{amount:<9.2f} {method:<25} {date:<20}")

        conn.close()

        print("\n" + "="*60)
        if total_payments > 0:
            print("✅ Setup complete! Refund system is ready.")
        else:
            print("⚠️  No payments found. Process some fine payments to test refunds.")
        print("="*60)

        return True

    except sqlite3.Error as e:
        print(f"❌ Verification error: {e}")
        return False

def main():
    """Main execution"""
    print("="*60)
    print("Library Fine Payments - Initialization Script")
    print("="*60)
    print()

    # Step 1: Create table
    if not init_library_fine_payments_table():
        print("\n❌ Failed to create table!")
        return False

    # Step 2: Migrate existing data
    if not migrate_existing_payments():
        print("\n⚠️  Migration had issues, but continuing...")

    # Step 3: Verify
    verify_setup()

    print("\n" + "="*60)
    print("Next steps:")
    print("1. Run the library GUI")
    print("2. Click 'Refund Fine' button")
    print("3. You should now see users with paid fines")
    print("="*60)

    return True

if __name__ == '__main__':
    main()
