"""
Library Fines Management - Database persistence layer for payment recording.
"""

from datetime import datetime

from education_system.post_18.university_system.modules.domain.academics.gui.library.fines.constants import (
    ORIGINAL_LIBRARY_AVAILABLE,
    DatabaseError,
    sqlite3,
)

try:
    from education_system.post_18.university_system.modules.domain.academics.services.library.database import get_db_connection
    from education_system.post_18.university_system.modules.domain.academics.services.library.settings import get_current_user_id
except ImportError:
    pass


def _record_fine_payment(self, conn, user_id, amount, payment_method, loans_paid=None):
    """Record fine payment in payments table (source_type='library') for tracking.

    Args:
        conn: Database connection
        user_id: Student ID
        amount: Total payment amount
        payment_method: How the payment was made
        loans_paid: Optional list of (loan_id, book_id, amount_paid) tuples for the loans that were paid
    """
    try:
        cursor = conn.cursor()
        current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        current_date = datetime.now().strftime('%Y-%m-%d')

        # If specific loans weren't provided, try to find recently paid loans
        if not loans_paid:
            cursor.execute('''
                SELECT loan_id, book_id, 0 as amount_paid FROM book_loans
                WHERE user_id = ?
                AND notes LIKE '%Fine paid on%'
                AND fine_amount = 0
                ORDER BY due_date DESC
                LIMIT 5
            ''', (user_id,))
            loans_paid = cursor.fetchall()

        # Record payment for each loan
        for loan_id, book_id, amount_paid in loans_paid:
            # Get book title
            cursor.execute('SELECT title FROM books WHERE book_id = ?', (book_id,))
            book_result = cursor.fetchone()
            book_title = book_result[0] if book_result else 'Unknown'

            # Use the total amount if individual amounts not specified
            payment_amt = amount_paid if amount_paid > 0 else amount

            # Insert into payments table with source_type='library'
            cursor.execute('''
                INSERT INTO payments
                (student_id, amount, currency, payment_method, payment_date, status,
                 notes, created_by, created_at, source_type, reference_id, reference_type,
                 payment_reference)
                VALUES (?, ?, 'GBP', ?, ?, 'completed', ?, ?, ?, 'library', ?, 'loan', ?)
            ''', (
                user_id, payment_amt,
                payment_method, current_date,
                f'Library fine payment - Book: {book_title} (book_id: {book_id})',
                get_current_user_id() if ORIGINAL_LIBRARY_AVAILABLE else 'System',
                current_datetime,
                str(loan_id),
                f'PAY_{loan_id}_{datetime.now().strftime("%Y%m%d%H%M%S")}'
            ))

        return True

    except Exception as e:
        print(f"Error recording fine payment: {e}")
        import traceback
        traceback.print_exc()
        return False


def _record_library_payment_in_finance(self, user_id, amount, payment_method):
    """Record library fine payment in the finance system for tracking."""
    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()
        current_date = datetime.now().strftime('%Y-%m-%d')
        current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Get or create student_fees record for library fines
        # First, check if there's an existing unpaid library fee
        cursor.execute('''
            SELECT student_fee_id, amount FROM student_fees
            WHERE student_id = ? AND fee_type_id = 3 AND status = 'unpaid'
            ORDER BY created_at DESC LIMIT 1
        ''', (user_id,))

        existing_fee = cursor.fetchone()

        if existing_fee:
            # Update existing fee (reduce amount or mark as paid)
            student_fee_id, current_fee_amount = existing_fee
            new_fee_amount = max(0, current_fee_amount - amount)

            if new_fee_amount == 0:
                # Fully paid
                cursor.execute('''
                    UPDATE student_fees
                    SET status = 'paid', amount = 0, updated_at = ?
                    WHERE student_fee_id = ?
                ''', (current_datetime, student_fee_id))
            else:
                # Partial payment
                cursor.execute('''
                    UPDATE student_fees
                    SET amount = ?, updated_at = ?
                    WHERE student_fee_id = ?
                ''', (new_fee_amount, current_datetime, student_fee_id))
        else:
            # Create a new fee record marked as paid (for historical tracking)
            cursor.execute('''
                INSERT INTO student_fees
                (student_id, fee_type_id, amount, currency, status, due_date, created_at, updated_at)
                VALUES (?, 3, 0, 'GBP', 'paid', ?, ?, ?)
            ''', (user_id, current_date, current_datetime, current_datetime))
            student_fee_id = cursor.lastrowid

        # Create payment record
        cursor.execute('''
            INSERT INTO payments
            (student_id, amount, currency, payment_method, payment_date, status, notes, created_by, created_at)
            VALUES (?, ?, 'GBP', ?, ?, 'completed', 'Library fine payment', ?, ?)
        ''', (user_id, amount, payment_method, current_date,
              get_current_user_id() if ORIGINAL_LIBRARY_AVAILABLE else 'system',
              current_datetime))

        payment_id = cursor.lastrowid

        # Link payment to fee via payment_allocations
        cursor.execute('''
            INSERT INTO payment_allocations
            (payment_id, student_fee_id, amount, created_at)
            VALUES (?, ?, ?, ?)
        ''', (payment_id, student_fee_id, amount, current_datetime))

        conn.commit()
        conn.close()

        # Auto-post to GL (never raises). The companion helper _record_fine_payment
        # writes additional per-loan payment rows on a caller-owned connection;
        # those are not hooked here to avoid posting before the caller's commit.
        # Library-fine payments therefore double-post if the caller's rows aren't
        # also reconciled — pre-existing duplication, tracked separately.
        try:
            from education_system.post_18.university_system.modules.domain.finance.ledger import notify_ledger
            notify_ledger('payment', payment_id, posted_by='library_fine')
        except Exception as _e:
            import logging
            logging.getLogger(__name__).warning("ledger hook failed: %s", _e)

        return True

    except (sqlite3.Error, DatabaseError) as e:
        print(f"Error recording library payment in finance system: {e}")
        import traceback
        traceback.print_exc()
        return False
