from __future__ import annotations

from datetime import datetime
from education_system.university_system.infrastructure.database.db import sqlite3
from flask import jsonify

from education_system.university_system.modules.domain.finance.core.finance_context import get_connection, get_current_user

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

        cursor.executemany('''
        INSERT INTO students 
        (student_id, first_name, last_name, email_address, phone_number, course, enrollment_date, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', sample_students)

        conn.commit()
        print("Sample students created successfully!")
        conn.close()

    except Exception as e:
        print(f"Error creating sample students: {e}")

def view_student_credits():
    """View credits for a specific student"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        student_id = input("Enter student ID: ").strip()

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
        from education_system.university_system.modules.domain.finance.core.security_automation import log_audit_action
        log_audit_action('add_credit', 'student_credits', str(credit_id),
                        {'student_id': student_id, 'amount': credit_amount, 'source': credit_source})

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")

def view_credit_history():
    """View credit history for a student"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        student_id = input("Enter student ID: ").strip()

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
        cursor.execute('SELECT phone_number FROM students WHERE student_id = ?', (student_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else "07000000000"
    except Exception:
        return "07000000000"

def api_get_student_financial_summary(student_id):
    """API endpoint to get student financial summary"""
    try:
        from education_system.university_system.modules.domain.finance.core.security_automation import verify_jwt_in_request
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
        return jsonify({'error': str(e)}), 500

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

        print(f"\nOutstanding Fees:")
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

        print(f"\nCredit application completed!")
        print(f"Total applied: £{apply_amount:.2f}")
        print(f"Remaining available credit: £{total_available_credit - apply_amount:.2f}")

        conn.close()

    except Exception as e:
        print(f"Error applying credit to fees: {e}")
