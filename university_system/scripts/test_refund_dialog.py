#!/usr/bin/env python3
"""
Test script to diagnose refund dialog issues
"""

from university_system.infrastructure.database.db import sqlite3
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from university_system.modules.shared.constants import paths

def test_query():
    """Test the exact query used in the refund dialog"""
    try:
        print("="*60)
        print("Testing Refund Dialog Query")
        print("="*60)

        conn = sqlite3.connect(str(paths.DEFAULT_DB_PATH))
        cursor = conn.cursor()

        # Test 1: Check table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='library_fine_payments'")
        if not cursor.fetchone():
            print("❌ Table 'library_fine_payments' does not exist!")
            return False
        print("✅ Table exists")

        # Test 2: Count records
        cursor.execute('SELECT COUNT(*) FROM library_fine_payments')
        count = cursor.fetchone()[0]
        print(f"✅ Found {count} payment records")

        # Test 3: Test the exact query from refund dialog (without search)
        print("\nTesting query without search term:")
        cursor.execute('''
            SELECT lfp.user_id,
                   s.first_name, s.last_name, s.email_address,
                   SUM(lfp.payment_amount) as total_paid,
                   SUM(COALESCE(lfp.refund_amount, 0)) as total_refunded,
                   COUNT(DISTINCT lfp.payment_id) as payment_count
            FROM library_fine_payments lfp
            JOIN students s ON lfp.user_id = s.student_id
            WHERE lfp.status = 'completed'
            GROUP BY lfp.user_id, s.first_name, s.last_name, s.email_address
            HAVING (total_paid - total_refunded) > 0
            ORDER BY s.last_name, s.first_name
        ''')

        users = cursor.fetchall()

        if not users:
            print("❌ Query returned no results!")

            # Debug: Check why
            cursor.execute('SELECT status, COUNT(*) FROM library_fine_payments GROUP BY status')
            print("\nPayment status breakdown:")
            for status, cnt in cursor.fetchall():
                print(f"  {status}: {cnt}")

            cursor.execute('''
                SELECT lfp.user_id, SUM(lfp.payment_amount) as paid, SUM(COALESCE(lfp.refund_amount, 0)) as refunded
                FROM library_fine_payments lfp
                GROUP BY lfp.user_id
            ''')
            print("\nPayment/Refund by user:")
            for user_id, paid, refunded in cursor.fetchall():
                print(f"  {user_id}: Paid=£{paid:.2f}, Refunded=£{refunded:.2f}, Available=£{paid-refunded:.2f}")

            return False

        print(f"✅ Query returned {len(users)} users\n")

        print("Users with refundable paid fines:")
        print(f"{'User ID':<15} {'Name':<30} {'Email':<30} {'Payments':<10} {'Paid':<12} {'Refunded':<12} {'Available':<12}")
        print("-" * 125)

        for user_id, first_name, last_name, email, total_paid, total_refunded, payment_count in users:
            full_name = f"{first_name} {last_name}"
            available = total_paid - total_refunded
            print(f"{user_id:<15} {full_name:<30} {email or 'N/A':<30} {payment_count:<10} £{total_paid:<11.2f} £{total_refunded:<11.2f} £{available:<11.2f}")

        # Test 4: Test query with search term
        print("\n" + "="*60)
        print("Testing query with search term 'sean':")
        search_term = "sean"
        cursor.execute('''
            SELECT lfp.user_id,
                   s.first_name, s.last_name, s.email_address,
                   SUM(lfp.payment_amount) as total_paid,
                   SUM(COALESCE(lfp.refund_amount, 0)) as total_refunded,
                   COUNT(DISTINCT lfp.payment_id) as payment_count
            FROM library_fine_payments lfp
            JOIN students s ON lfp.user_id = s.student_id
            WHERE lfp.status = 'completed'
            AND (lfp.user_id LIKE ? OR s.first_name LIKE ? OR s.last_name LIKE ? OR s.email_address LIKE ?)
            GROUP BY lfp.user_id, s.first_name, s.last_name, s.email_address
            HAVING (total_paid - total_refunded) > 0
            ORDER BY s.last_name, s.first_name
        ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))

        users = cursor.fetchall()
        print(f"Found {len(users)} users matching 'sean':")
        for user_id, first_name, last_name, email, total_paid, total_refunded, payment_count in users:
            full_name = f"{first_name} {last_name}"
            available = total_paid - total_refunded
            print(f"  {user_id}: {full_name} - {payment_count} payments, £{available:.2f} available")

        # Test 5: Get payment details for first user
        if users:
            test_user_id = users[0][0]
            print(f"\n" + "="*60)
            print(f"Testing payment details for user: {test_user_id}")

            cursor.execute('''
                SELECT lfp.payment_id, lfp.loan_id, lfp.book_id, lfp.book_title,
                       lfp.payment_amount, lfp.payment_method, lfp.payment_date,
                       lfp.refund_amount
                FROM library_fine_payments lfp
                WHERE lfp.user_id = ?
                AND lfp.status = 'completed'
                AND (lfp.payment_amount - COALESCE(lfp.refund_amount, 0)) > 0
                ORDER BY lfp.payment_date DESC
            ''', (test_user_id,))

            payments = cursor.fetchall()
            print(f"Found {len(payments)} refundable payments for this user:")

            for payment_id, loan_id, book_id, book_title, payment_amount, payment_method, payment_date, refund_amount in payments:
                refund_amount = refund_amount or 0.0
                available = payment_amount - refund_amount
                print(f"  Payment #{payment_id}: {book_title[:30]} - £{payment_amount:.2f} paid, £{refund_amount:.2f} refunded, £{available:.2f} available")

        conn.close()

        print("\n" + "="*60)
        print("✅ All queries working correctly!")
        print("="*60)

        return True

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    test_query()
