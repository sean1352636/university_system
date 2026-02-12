#!/usr/bin/env python3
"""
Generate test data for library fine payments

This script creates sample paid fines for testing the refund system.
"""

from university_system.infrastructure.database.db import sqlite3
import sys
import os
import random
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from university_system.modules.shared.constants import paths

def generate_test_payments():
    """Generate test fine payment data"""
    try:
        conn = sqlite3.connect(str(paths.DEFAULT_DB_PATH))
        cursor = conn.cursor()

        print("="*60)
        print("Generating Test Fine Payment Data")
        print("="*60)

        # Get some student IDs
        cursor.execute('SELECT student_id, first_name, last_name FROM students LIMIT 10')
        students = cursor.fetchall()

        if not students:
            print("❌ No students found in database!")
            print("Please add students first before generating test data.")
            conn.close()
            return False

        # Get some book IDs
        cursor.execute('SELECT book_id, title FROM books LIMIT 20')
        books = cursor.fetchall()

        if not books:
            print("❌ No books found in database!")
            print("Please add books first before generating test data.")
            conn.close()
            return False

        print(f"\nFound {len(students)} students and {len(books)} books")
        print("Generating test fine payments...\n")

        payment_methods = [
            'Cash',
            'Card',
            'Student Finance Account',
            'Cash/Card at Library Desk'
        ]

        generated = 0

        # Generate 15-20 test payments
        num_payments = random.randint(15, 20)

        for i in range(num_payments):
            student = random.choice(students)
            book = random.choice(books)

            student_id = student[0]
            student_name = f"{student[1]} {student[2]}"
            book_id = book[0]
            book_title = book[1]

            # Random fine amount between £2 and £25
            fine_amount = round(random.uniform(2.0, 25.0), 2)
            payment_amount = fine_amount

            # Random payment method
            payment_method = random.choice(payment_methods)

            # Random date in the last 60 days
            days_ago = random.randint(1, 60)
            payment_date = (datetime.now() - timedelta(days=days_ago)).strftime('%Y-%m-%d %H:%M:%S')

            # Create or get loan_id (we'll create fake ones)
            loan_id = 10000 + i

            # Insert payment
            cursor.execute('''
                INSERT INTO library_fine_payments
                (loan_id, user_id, book_id, book_title, fine_amount, payment_amount,
                 payment_method, payment_date, processed_by, transaction_ref, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                loan_id, student_id, book_id, book_title, fine_amount, payment_amount,
                payment_method, payment_date, 'System Test',
                f'TEST_{loan_id}_{datetime.now().strftime("%Y%m%d")}',
                'completed'
            ))

            print(f"  ✓ Generated payment #{i+1}: {student_name} - {book_title[:30]} - £{fine_amount:.2f} ({payment_method})")
            generated += 1

        # Add some partial refunds to a few payments
        cursor.execute('SELECT payment_id, payment_amount FROM library_fine_payments ORDER BY RANDOM() LIMIT 3')
        payments_to_refund = cursor.fetchall()

        print(f"\nAdding partial refunds to {len(payments_to_refund)} payments...")

        for payment_id, payment_amount in payments_to_refund:
            refund_amount = round(payment_amount * random.uniform(0.3, 0.7), 2)
            refund_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
                UPDATE library_fine_payments
                SET refund_amount = ?,
                    refunded_date = ?,
                    refunded_by = ?,
                    refund_reason = ?
                WHERE payment_id = ?
            ''', (
                refund_amount, refund_date, 'System Test',
                'Test partial refund',
                payment_id
            ))

            print(f"  ✓ Added refund of £{refund_amount:.2f} to payment #{payment_id}")

        conn.commit()
        conn.close()

        print(f"\n{'='*60}")
        print(f"✅ Successfully generated {generated} test fine payments!")
        print(f"{'='*60}")

        return True

    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
        if 'conn' in locals():
            conn.close()
        return False

def show_summary():
    """Show summary of test data"""
    try:
        conn = sqlite3.connect(str(paths.DEFAULT_DB_PATH))
        cursor = conn.cursor()

        print("\n" + "="*60)
        print("TEST DATA SUMMARY")
        print("="*60)

        # Total payments
        cursor.execute('SELECT COUNT(*), SUM(payment_amount) FROM library_fine_payments')
        count, total = cursor.fetchone()
        print(f"Total payments: {count}")
        print(f"Total amount paid: £{total:.2f}")

        # By method
        cursor.execute('SELECT payment_method, COUNT(*), SUM(payment_amount) FROM library_fine_payments GROUP BY payment_method')
        print("\nBy Payment Method:")
        for method, count, total in cursor.fetchall():
            print(f"  {method}: {count} payments, £{total:.2f}")

        # Users with payments
        cursor.execute('''
            SELECT lfp.user_id, s.first_name, s.last_name,
                   COUNT(*) as payments,
                   SUM(lfp.payment_amount) as paid,
                   SUM(COALESCE(lfp.refund_amount, 0)) as refunded
            FROM library_fine_payments lfp
            LEFT JOIN students s ON lfp.user_id = s.student_id
            GROUP BY lfp.user_id, s.first_name, s.last_name
            ORDER BY paid DESC
            LIMIT 5
        ''')

        print("\nTop 5 Users with Payments:")
        print(f"{'User ID':<15} {'Name':<30} {'Payments':<10} {'Paid':<12} {'Refunded':<12} {'Available':<12}")
        print("-" * 95)

        for user_id, first_name, last_name, payments, paid, refunded in cursor.fetchall():
            name = f"{first_name or ''} {last_name or ''}".strip() or 'Unknown'
            available = paid - refunded
            print(f"{user_id:<15} {name:<30} {payments:<10} £{paid:<11.2f} £{refunded:<11.2f} £{available:<11.2f}")

        conn.close()

        print("\n" + "="*60)
        print("✅ Test data is ready! You can now test the refund system.")
        print("="*60)

        return True

    except sqlite3.Error as e:
        print(f"❌ Error: {e}")
        return False

def main():
    """Main execution"""
    print("\n")

    # Check if table exists
    try:
        conn = sqlite3.connect(str(paths.DEFAULT_DB_PATH))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='library_fine_payments'")
        if not cursor.fetchone():
            print("❌ Table 'library_fine_payments' not found!")
            print("Please run 'python university_system/scripts/init_library_fine_payments.py' first.")
            conn.close()
            return False
        conn.close()
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
        return False

    # Check if data already exists
    try:
        conn = sqlite3.connect(str(paths.DEFAULT_DB_PATH))
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM library_fine_payments')
        count = cursor.fetchone()[0]
        conn.close()

        if count > 0:
            print(f"⚠️  Found {count} existing payments in the database.")
            response = input("Do you want to add more test data? (y/n): ")
            if response.lower() != 'y':
                print("Cancelled.")
                return False
    except sqlite3.Error:
        pass

    # Generate test data
    if not generate_test_payments():
        print("\n❌ Failed to generate test data!")
        return False

    # Show summary
    show_summary()

    print("\n" + "="*60)
    print("Next Steps:")
    print("1. Open Library GUI")
    print("2. Go to Fine Management")
    print("3. Click '🔄 Refund Fine' button")
    print("4. You should now see users with paid fines!")
    print("="*60)
    print()

    return True

if __name__ == '__main__':
    main()
