from __future__ import annotations

import logging
from datetime import datetime
from education_system.systems.university.infrastructure.database.db import sqlite3
from flask import jsonify

logger = logging.getLogger(__name__)

from education_system.systems.university.domains.finance.domain.core.finance_context import get_connection, get_current_user

def student_exists(student_id):
    """Check if a student exists in the database"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) FROM students WHERE student_id = ?', (student_id,))
        count = cursor.fetchone()[0]

        conn.close()
        return count > 0
    except sqlite3.Error:
        return False

def get_student_name(student_id):
    """Get student's full name"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT first_name, last_name FROM students WHERE student_id = ?', (student_id,))
        result = cursor.fetchone()

        conn.close()

        if result:
            return f"{result[0]} {result[1]}"
        return "Unknown Student"
    except sqlite3.Error:
        return "Unknown Student"

def create_sample_students():
    """Create sample students for testing"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Check if sample students already exist
        cursor.execute('SELECT COUNT(*) FROM students')
        if cursor.fetchone()[0] > 0:
            conn.close()
            return

        sample_students = [
            ('STU001', 'John', 'Smith', 'john.smith@university.ac.uk', '07123456789', 'Computer Science', '2024-09-01', 'active'),
            ('STU002', 'Sarah', 'Johnson', 'sarah.johnson@university.ac.uk', '07123456790', 'Business Administration', '2024-09-01', 'active'),
            ('STU003', 'Michael', 'Brown', 'michael.brown@university.ac.uk', '07123456791', 'Engineering', '2024-09-01', 'active'),
            ('STU004', 'Emma', 'Davis', 'emma.davis@university.ac.uk', '07123456792', 'Psychology', '2024-09-01', 'active'),
            ('STU005', 'James', 'Wilson', 'james.wilson@university.ac.uk', '07123456793', 'Mathematics', '2024-09-01', 'active')
        ]

        # The column is ``phone``, not ``phone_number``.
        cursor.executemany('''
        INSERT INTO students
        (student_id, first_name, last_name, email_address, phone, course, enrollment_date, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', sample_students)

        conn.commit()
        print("Sample students created successfully!")
        conn.close()

    except Exception as e:
        print(f"Error creating sample students: {e}")

def view_student_credits(student_id=None):
    """View credits for a specific student"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        student_id = student_id or input("Enter student ID: ").strip()

        if not student_exists(student_id):
            print(f"Student with ID {student_id} does not exist.")
            conn.close()
            return

        cursor.execute('''
        SELECT credit_id, credit_amount, remaining_amount, credit_source, description,
               expiry_date, status, created_at
        FROM student_credits
        WHERE student_id = ? AND status = 'active'
        ORDER BY created_at DESC
        ''', (student_id,))

        credits = cursor.fetchall()

        if not credits:
            print(f"No active credits found for student {student_id}.")
            conn.close()
            return

        print(f"\nActive credits for student {student_id} ({get_student_name(student_id)}):")
        print("=" * 100)
        print(f"{'Credit ID':<10} {'Amount':<12} {'Remaining':<12} {'Source':<15} {'Description':<20} {'Expires':<12}")
        print("-" * 100)

        total_credits = 0
        for credit in credits:
            credit_id, amount, remaining, source, description, expiry, status, created = credit
            expiry_str = expiry if expiry else "No expiry"
            desc_str = description if description else "N/A"

            print(f"{credit_id:<10} £{amount:<11.2f} £{remaining:<11.2f} {source:<15} {desc_str:<20} {expiry_str:<12}")
            total_credits += remaining

        print("-" * 100)
        print(f"Total available credits: £{total_credits:.2f}")
        print("=" * 100)

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")

def add_student_credit():
    """Add credit to a student account"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        student_id = input("Enter student ID: ").strip()

        if not student_exists(student_id):
            print(f"Student with ID {student_id} does not exist.")
            conn.close()
            return

        # Get credit details
        while True:
            try:
                credit_amount = float(input("Enter credit amount (£): "))
                if credit_amount <= 0:
                    print("Credit amount must be greater than zero.")
                    continue
                break
            except ValueError:
                print("Invalid input. Please enter a valid amount.")

        credit_sources = ['overpayment', 'refund', 'scholarship', 'adjustment', 'goodwill', 'other']
        print("\nCredit sources:")
        for i, source in enumerate(credit_sources, 1):
            print(f"{i}. {source.title()}")

        source_choice = input("Select credit source (1-6): ").strip()
        try:
            source_index = int(source_choice) - 1
            if 0 <= source_index < len(credit_sources):
                credit_source = credit_sources[source_index]
            else:
                print("Invalid selection.")
                conn.close()
                return
        except ValueError:
            print("Invalid input.")
            conn.close()
            return

        description = input("Enter description (optional): ").strip()

        # Get expiry date
        expiry_date = input("Enter expiry date (YYYY-MM-DD) or leave blank for no expiry: ").strip()
        if expiry_date:
            try:
                # Validate date format
                datetime.strptime(expiry_date, '%Y-%m-%d')
            except ValueError:
                print("Invalid date format. Credit will have no expiry.")
                expiry_date = None
        else:
            expiry_date = None

        # Create the credit
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        INSERT INTO student_credits
        (student_id, credit_amount, remaining_amount, credit_source, description,
         expiry_date, created_by, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (student_id, credit_amount, credit_amount, credit_source, description,
              expiry_date, get_current_user()['username'] if get_current_user() else 'system', now, now))

        credit_id = cursor.lastrowid

        conn.commit()

        print(f"\nCredit added successfully! Credit ID: {credit_id}")
        print(f"Amount: £{credit_amount:.2f}")
        print(f"Source: {credit_source.title()}")
        if expiry_date:
            print(f"Expires: {expiry_date}")

        # Log the action
        from education_system.systems.university.domains.finance.domain.core.security_automation import log_audit_action
        log_audit_action('add_credit', 'student_credits', str(credit_id),
                        {'student_id': student_id, 'amount': credit_amount, 'source': credit_source})

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")

def view_credit_history(student_id=None):
    """View credit history for a student"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        student_id = student_id or input("Enter student ID: ").strip()

        if not student_exists(student_id):
            print(f"Student with ID {student_id} does not exist.")
            return

        cursor.execute('''
        SELECT credit_id, credit_amount, remaining_amount, credit_source,
               description, status, created_at, expiry_date
        FROM student_credits
        WHERE student_id = ?
        ORDER BY created_at DESC
        ''', (student_id,))

        credits = cursor.fetchall()

        if not credits:
            print(f"No credit history found for student {student_id}.")
            return

        print(f"\nCredit History for {get_student_name(student_id)} ({student_id}):")
        print("=" * 100)
        print(f"{'ID':<5} {'Amount':<12} {'Remaining':<12} {'Source':<15} {'Status':<10} {'Created':<12} {'Expires':<12}")
        print("-" * 100)

        total_credits = 0
        active_credits = 0

        for credit in credits:
            credit_id, amount, remaining, source, desc, status, created, expiry = credit
            expiry_str = expiry if expiry else "No expiry"

            print(f"{credit_id:<5} £{amount:<11.2f} £{remaining:<11.2f} {source:<15} {status:<10} {created[:10]:<12} {expiry_str:<12}")

            total_credits += amount
            if status == 'active':
                active_credits += remaining

        print("-" * 100)
        print(f"Total credits received: £{total_credits:.2f}")
        print(f"Active credits available: £{active_credits:.2f}")
        print("=" * 100)

        conn.close()

    except Exception as e:
        print(f"Error viewing credit history: {e}")

def get_student_email(student_id):
    """Get student email from database"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT email_address FROM students WHERE student_id = ?', (student_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else f"{student_id}@university.ac.uk"
    except Exception:
        return f"{student_id}@university.ac.uk"

def get_student_phone(student_id):
    """Get student phone from database"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT phone FROM students WHERE student_id = ?', (student_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else "07000000000"
    except Exception:
        return "07000000000"

def api_get_student_financial_summary(student_id):
    """API endpoint to get student financial summary"""
    try:
        from education_system.systems.university.domains.finance.domain.core.security_automation import verify_jwt_in_request
        verify_jwt_in_request()

        conn = get_connection()
        cursor = conn.cursor()

        # Get student financial data
        cursor.execute('''
        SELECT
            (SELECT SUM(amount) FROM student_fees WHERE student_id = ?) as total_fees,
            (SELECT SUM(amount) FROM payments WHERE student_id = ?) as total_paid,
            (SELECT COUNT(*) FROM student_fees WHERE student_id = ? AND status = 'unpaid') as unpaid_fees,
            (SELECT SUM(amount) FROM student_scholarships WHERE student_id = ? AND status = 'active') as scholarships
        ''', (student_id, student_id, student_id, student_id))

        result = cursor.fetchone()

        if result:
            total_fees, total_paid, unpaid_fees, scholarships = result

            financial_summary = {
                'student_id': student_id,
                'total_fees': float(total_fees or 0),
                'total_paid': float(total_paid or 0),
                'balance_due': float((total_fees or 0) - (total_paid or 0)),
                'unpaid_fees_count': unpaid_fees or 0,
                'total_scholarships': float(scholarships or 0)
            }

            conn.close()
            return jsonify(financial_summary)
        else:
            conn.close()
            return jsonify({'error': 'Student not found'}), 404

    except Exception as e:
        logger.error("Financial summary retrieval failed: %s", e)
        return jsonify({'error': 'Internal server error'}), 500

def record_student_credit(student_id, amount, source='adjustment', description='',
                          expiry_date=None, created_by=None):
    """Add a credit without prompting (the GUI forms); returns its credit id.

    Raises ValueError for an unknown student, a non-positive amount or a
    badly formed expiry date.
    """
    student_id = str(student_id).strip()
    amount = float(amount)
    if not student_exists(student_id):
        raise ValueError(f"Student with ID {student_id} does not exist")
    if amount <= 0:
        raise ValueError("Credit amount must be greater than zero")
    if expiry_date:
        datetime.strptime(expiry_date, '%Y-%m-%d')
    if created_by is None:
        user = get_current_user()
        created_by = user['username'] if user else 'system'
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_connection()
    try:
        credit_id = conn.execute(
            """INSERT INTO student_credits
               (student_id, credit_amount, remaining_amount, credit_source, description,
                expiry_date, created_by, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (student_id, amount, amount, source or 'other', description or '',
             expiry_date or None, created_by, now, now)).lastrowid
        conn.commit()
    finally:
        conn.close()
    from education_system.systems.university.domains.finance.domain.core.security_automation import log_audit_action
    log_audit_action('add_credit', 'student_credits', str(credit_id),
                     {'student_id': student_id, 'amount': amount, 'source': source})
    return credit_id


def apply_student_credit(student_id, credit_id=None, amount=None):
    """Apply credit to the student's outstanding fees, oldest due first.

    Same bookkeeping as :func:`apply_credit_to_fees` (a payment and allocation
    per fee, fee status, credit balance, ledger post) without prompting.
    ``credit_id`` limits it to one credit and ``amount`` caps the total; by
    default every active credit is used up to what is owed. Returns the amount
    applied. Raises ValueError when there is nothing to apply.
    """
    student_id = str(student_id).strip()
    if not student_exists(student_id):
        raise ValueError(f"Student with ID {student_id} does not exist")
    conn = get_connection()
    payment_ids = []
    try:
        query = ("SELECT credit_id, remaining_amount FROM student_credits "
                 "WHERE student_id = ? AND status = 'active' AND remaining_amount > 0")
        params = [student_id]
        if credit_id is not None:
            query += " AND credit_id = ?"
            params.append(int(credit_id))
        credits = conn.execute(query + " ORDER BY created_at", params).fetchall()
        if not credits:
            raise ValueError(f"No available credit found for student {student_id}")
        fees = conn.execute(
            """SELECT sf.student_fee_id, ft.fee_name, sf.amount,
                      COALESCE(SUM(pa.amount), 0) AS paid_amount,
                      sf.amount - COALESCE(SUM(pa.amount), 0) AS outstanding
               FROM student_fees sf
               JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
               LEFT JOIN payment_allocations pa ON sf.student_fee_id = pa.student_fee_id
               WHERE sf.student_id = ? AND sf.status IN ('unpaid', 'partial')
               GROUP BY sf.student_fee_id
               HAVING outstanding > 0
               ORDER BY sf.due_date""", (student_id,)).fetchall()
        if not fees:
            raise ValueError(f"No outstanding fees for student {student_id}")

        available = sum(c[1] for c in credits)
        owed = sum(f[4] for f in fees)
        to_apply = min(available, owed)
        if amount is not None:
            if float(amount) <= 0:
                raise ValueError("Amount to apply must be greater than zero")
            if float(amount) > available:
                raise ValueError(f"Only £{available:.2f} of credit is available")
            to_apply = min(float(amount), owed)

        user = get_current_user()
        username = user['username'] if user else 'system'
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        left = to_apply
        for fee_id, fee_name, total_amt, paid_amt, outstanding in fees:
            if left <= 0:
                break
            portion = min(left, outstanding)
            payment_id = conn.execute(
                """INSERT INTO payments
                   (student_id, amount, payment_method, payment_date, notes, created_by, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (student_id, portion, 'Credit Application',
                 datetime.now().strftime('%Y-%m-%d'),
                 f'Applied credit to {fee_name}', username, now)).lastrowid
            payment_ids.append(payment_id)
            conn.execute(
                """INSERT INTO payment_allocations
                   (payment_id, student_fee_id, amount, created_at) VALUES (?, ?, ?, ?)""",
                (payment_id, fee_id, portion, now))
            conn.execute(
                "UPDATE student_fees SET status = ?, updated_at = ? WHERE student_fee_id = ?",
                ('paid' if paid_amt + portion >= total_amt else 'partial', now, fee_id))
            left -= portion

        left = to_apply
        for cid, remaining in credits:
            if left <= 0:
                break
            used = min(left, remaining)
            conn.execute(
                """UPDATE student_credits SET remaining_amount = ?, status = ?, updated_at = ?
                   WHERE credit_id = ?""",
                (remaining - used, 'used' if remaining - used <= 0 else 'active', now, cid))
            left -= used
        conn.commit()
    finally:
        conn.close()

    try:
        from education_system.systems.university.domains.finance.domain.ledger import notify_ledger
        for pid in payment_ids:
            notify_ledger('payment', pid, posted_by='credit_application')
    except Exception as e:
        logging.getLogger(__name__).warning("ledger hook failed: %s", e)
    return to_apply


def apply_credit_to_fees():
    """Apply student credit to outstanding fees"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        student_id = input("Enter student ID: ").strip()

        if not student_exists(student_id):
            print(f"Student with ID {student_id} does not exist.")
            return

        # Get available credits
        cursor.execute('''
        SELECT credit_id, credit_amount, remaining_amount, credit_source, description
        FROM student_credits
        WHERE student_id = ? AND status = 'active' AND remaining_amount > 0
        ORDER BY created_at
        ''', (student_id,))

        credits = cursor.fetchall()

        if not credits:
            print(f"No available credits for student {student_id}.")
            return

        # Get outstanding fees
        cursor.execute('''
        SELECT sf.student_fee_id, ft.fee_name, sf.amount,
               COALESCE(SUM(pa.amount), 0) as paid_amount,
               sf.amount - COALESCE(SUM(pa.amount), 0) as outstanding
        FROM student_fees sf
        JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
        LEFT JOIN payment_allocations pa ON sf.student_fee_id = pa.student_fee_id
        WHERE sf.student_id = ? AND sf.status IN ('unpaid', 'partial')
        GROUP BY sf.student_fee_id
        HAVING outstanding > 0
        ORDER BY sf.due_date
        ''', (student_id,))

        fees = cursor.fetchall()

        if not fees:
            print(f"No outstanding fees for student {student_id}.")
            return

        print(f"\nAvailable Credits for {get_student_name(student_id)}:")
        total_available_credit = 0
        for i, credit in enumerate(credits, 1):
            credit_id, total_amt, remaining_amt, source, desc = credit
            print(f"{i}. Credit ID {credit_id}: £{remaining_amt:.2f} available ({source})")
            total_available_credit += remaining_amt

        print("\nOutstanding Fees:")
        total_outstanding = 0
        for i, fee in enumerate(fees, 1):
            fee_id, fee_name, total_amt, paid_amt, outstanding = fee
            print(f"{i}. {fee_name}: £{outstanding:.2f} outstanding")
            total_outstanding += outstanding

        print(f"\nTotal available credit: £{total_available_credit:.2f}")
        print(f"Total outstanding fees: £{total_outstanding:.2f}")

        # Apply credits automatically
        apply_amount = min(total_available_credit, total_outstanding)

        if apply_amount <= 0:
            print("No credits can be applied.")
            return

        confirm = input(f"Apply £{apply_amount:.2f} in credits to outstanding fees? (y/n): ").strip().lower()
        if confirm != 'y':
            return

        # Process applications
        remaining_to_apply = apply_amount
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        credit_application_payment_ids = []

        for fee_id, fee_name, total_amt, paid_amt, outstanding in fees:
            if remaining_to_apply <= 0:
                break

            application_amount = min(remaining_to_apply, outstanding)

            # Create a payment record for the credit application
            cursor.execute('''
            INSERT INTO payments
            (student_id, amount, payment_method, payment_date, notes, created_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (student_id, application_amount, 'Credit Application',
                  datetime.now().strftime('%Y-%m-%d'),
                  f'Applied credit to {fee_name}',
                  get_current_user()['username'] if get_current_user() else 'system', now))

            payment_id = cursor.lastrowid
            credit_application_payment_ids.append(payment_id)

            # Create payment allocation
            cursor.execute('''
            INSERT INTO payment_allocations
            (payment_id, student_fee_id, amount, created_at)
            VALUES (?, ?, ?, ?)
            ''', (payment_id, fee_id, application_amount, now))

            # Update fee status
            new_paid_amount = paid_amt + application_amount
            new_status = 'paid' if new_paid_amount >= total_amt else 'partial'

            cursor.execute('''
            UPDATE student_fees
            SET status = ?, updated_at = ?
            WHERE student_fee_id = ?
            ''', (new_status, now, fee_id))

            remaining_to_apply -= application_amount
            print(f"Applied £{application_amount:.2f} credit to {fee_name}")

        # Update credit balances
        remaining_credit_to_use = apply_amount

        for credit_id, total_amt, remaining_amt, source, desc in credits:
            if remaining_credit_to_use <= 0:
                break

            credit_used = min(remaining_credit_to_use, remaining_amt)
            new_remaining = remaining_amt - credit_used
            new_status = 'used' if new_remaining <= 0 else 'active'

            cursor.execute('''
            UPDATE student_credits
            SET remaining_amount = ?, status = ?, updated_at = ?
            WHERE credit_id = ?
            ''', (new_remaining, new_status, now, credit_id))

            remaining_credit_to_use -= credit_used

        conn.commit()

        # Auto-post each credit-application payment to GL (never raises)
        try:
            from education_system.systems.university.domains.finance.domain.ledger import notify_ledger
            for pid in credit_application_payment_ids:
                notify_ledger('payment', pid, posted_by='credit_application')
        except Exception as _e:
            import logging
            logging.getLogger(__name__).warning("ledger hook failed: %s", _e)

        print("\nCredit application completed!")
        print(f"Total applied: £{apply_amount:.2f}")
        print(f"Remaining available credit: £{total_available_credit - apply_amount:.2f}")

        conn.close()

    except Exception as e:
        print(f"Error applying credit to fees: {e}")
