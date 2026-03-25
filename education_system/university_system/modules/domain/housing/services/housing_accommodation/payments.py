from education_system.university_system.modules.domain.housing.services.housing_accommodation import common as _common
from education_system.university_system.modules.domain.housing.services.housing_accommodation.common import (
    sqlite3, datetime, get_text, get_connection, generate_id,
    record_payment_to_finance, log_create, log_read,
)
from education_system.university_system.modules.domain.housing.services.housing_accommodation.applications import select_student


# Payment Functions
@log_create(module="housing", description="Recording housing payment")
def record_payment():
    """Record a housing payment"""
    auth = _common.auth

    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to record payments.")
        return

    if not auth.check_permission('manage_accommodations'):
        print("You don't have permission to record payments.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Select an active assignment for payment
        cursor.execute('''
        SELECT a.assignment_id, a.student_id, s.first_name, s.last_name, r.room_number,
               b.building_name, a.monthly_rent
        FROM housing_assignments a
        JOIN students s ON a.student_id = s.student_id
        JOIN housing_rooms r ON a.room_id = r.room_id
        JOIN housing_buildings b ON r.building_id = b.building_id
        WHERE a.status = 'Active'
        ORDER BY s.last_name, s.first_name
        ''')

        assignments = cursor.fetchall()

        if not assignments:
            print("No active housing assignments found.")
            conn.close()
            return

        print("\nSelect Assignment for Payment:")
        print("============================")

        for i, asn in enumerate(assignments, 1):
            print(f"{i}. {asn[2]} {asn[3]} ({asn[1]}) - Room {asn[4]} in {asn[5]}")
            print(f"   Monthly Rent: ${asn[6]}")
            print()

        while True:
            try:
                choice = int(input("\nSelect assignment (enter number): "))
                if 1 <= choice <= len(assignments):
                    assignment = assignments[choice - 1]
                    assignment_id = assignment[0]
                    student_id = assignment[1]
                    student_name = f"{assignment[2]} {assignment[3]}"
                    monthly_rent = assignment[6]
                    break
                else:
                    print(f"Please enter a number between 1 and {len(assignments)}.")
            except ValueError:
                print("Please enter a valid number.")

        # Get payment details
        print(f"\nRecording Payment for {student_name}")
        print(f"Regular Monthly Rent: ${monthly_rent}")

        while True:
            try:
                payment_amount = float(input("\nPayment Amount: $"))
                if payment_amount <= 0:
                    print("Payment amount must be greater than 0.")
                    continue
                break
            except ValueError:
                print("Please enter a valid amount.")

        # Payment method
        print("\nSelect Payment Method:")
        print("1. Credit Card")
        print("2. Bank Transfer")
        print("3. Cash")
        print("4. Check")
        print("5. Other")

        while True:
            method_choice = input("\nSelect method (1-5): ")
            if method_choice == '1':
                payment_method = 'Credit Card'
                break
            elif method_choice == '2':
                payment_method = 'Bank Transfer'
                break
            elif method_choice == '3':
                payment_method = 'Cash'
                break
            elif method_choice == '4':
                payment_method = 'Check'
                break
            elif method_choice == '5':
                payment_method = input("Specify payment method: ").strip()
                if not payment_method:
                    print("Payment method cannot be empty.")
                    continue
                break
            else:
                print("Invalid choice. Please select 1-5.")

        # Get transaction reference
        transaction_ref = input("Transaction Reference (optional): ").strip() or None

        # Payment period
        while True:
            try:
                period_start = input("Payment Period Start Date (YYYY-MM-DD): ")
                # Validate date format
                datetime.datetime.strptime(period_start, '%Y-%m-%d')
                break
            except ValueError:
                print("Invalid date format. Please use YYYY-MM-DD.")

        while True:
            try:
                period_end = input("Payment Period End Date (YYYY-MM-DD): ")
                # Validate date format
                datetime.datetime.strptime(period_end, '%Y-%m-%d')
                # Check that end date is after start date
                if datetime.datetime.strptime(period_end, '%Y-%m-%d') <= datetime.datetime.strptime(period_start, '%Y-%m-%d'):
                    print("End date must be after start date.")
                    continue
                break
            except ValueError:
                print("Invalid date format. Please use YYYY-MM-DD.")

        # Create payment record
        payment_id = generate_id('PAY')
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        INSERT INTO payments (
            source_payment_id, source_type, reference_id, reference_type,
            student_id, amount, payment_date, payment_method,
            payment_reference, payment_period_start, payment_period_end, status,
            processed_by, created_at, updated_at
        ) VALUES (?, 'housing', ?, 'assignment', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            payment_id, assignment_id, student_id, payment_amount, timestamp, payment_method,
            transaction_ref, period_start, period_end, 'Completed',
            auth.current_user['username'], timestamp, timestamp
        ))

        conn.commit()

        # Record payment to central finance system
        finance_payment_id = record_payment_to_finance(
            student_id=student_id,
            amount=payment_amount,
            payment_method=payment_method,
            transaction_source='Housing',
            transaction_ref=payment_id,
            notes=f'Housing rent payment for period {period_start} to {period_end}',
            created_by=auth.current_user['username'] if auth and auth.current_user else None
        )

        print(f"\nPayment recorded successfully with ID: {payment_id}")
        print(f"Amount: ${payment_amount} | Method: {payment_method}")
        print(f"Period: {period_start} to {period_end}")
        if finance_payment_id:
            print(f"Finance System Payment ID: {finance_payment_id}")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error recording payment: {e}")

@log_read(module="housing", description="Viewing payment history")
def view_payment_history():
    """View payment history"""
    auth = _common.auth

    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to view payment history.")
        return

    current_role = auth.current_user.get('role', '')

    try:
        conn = get_connection()
        cursor = conn.cursor()

        if current_role == 'student':
            # Students can only view their own payment history
            if not auth.check_permission('view_own_record'):
                print("You don't have permission to view payment history.")
                conn.close()
                return

            # Get the student ID associated with this user
            cursor.execute('''
            SELECT student_id FROM users WHERE id = ?
            ''', (auth.current_user['id'],))

            result = cursor.fetchone()
            if not result or not result[0]:
                print("No student ID associated with your account.")
                conn.close()
                return

            student_id = result[0]

            # Fetch student's payments
            cursor.execute('''
            SELECT p.source_payment_id, p.reference_id, p.amount, p.payment_date, p.payment_method,
                   p.payment_period_start, p.payment_period_end, p.status,
                   r.room_number, b.building_name
            FROM payments p
            JOIN housing_assignments a ON p.reference_id = a.assignment_id
            JOIN housing_rooms r ON a.room_id = r.room_id
            JOIN housing_buildings b ON r.building_id = b.building_id
            WHERE p.source_type = 'housing' AND p.student_id = ?
            ORDER BY p.payment_date DESC
            ''', (student_id,))

            payments = cursor.fetchall()

            if not payments:
                print("You don't have any housing payment records.")
                conn.close()
                return

            print("\nYour Housing Payment History:")
            print("============================")

            for i, payment in enumerate(payments, 1):
                print(f"{i}. ${payment[2]} - Paid on {payment[3]} via {payment[4]}")
                print(f"   Room {payment[8]} in {payment[9]}")
                print(f"   Period: {payment[5]} to {payment[6]} | Status: {payment[7]}")
                print()

            # Display payment summary
            cursor.execute('''
            SELECT SUM(amount), COUNT(payment_id)
            FROM payments
            WHERE source_type = 'housing' AND student_id = ?
            ''', (student_id,))

            total = cursor.fetchone()

            print("\nPayment Summary:")
            print(f"Total Payments: {total[1]}")
            print(f"Total Amount Paid: ${total[0]}")

        else:
            # Admin/staff can view any payment history
            if not (auth.check_permission('manage_accommodations') or auth.check_permission('view_accommodations')):
                print("You don't have permission to view payment history.")
                conn.close()
                return

            # Allow filtering options
            print("\nView Payment History:")
            print("1. View by student")
            print("2. View by building")
            print("3. View by date range")
            print("4. View recent payments")

            filter_choice = input("\nEnter choice (1-4): ")

            if filter_choice == '1':
                # View by student
                student_id = select_student()
                if not student_id:
                    conn.close()
                    return

                cursor.execute('''
                SELECT p.source_payment_id, p.reference_id, p.amount, p.payment_date, p.payment_method,
                       p.payment_period_start, p.payment_period_end, p.status,
                       r.room_number, b.building_name
                FROM payments p
                JOIN housing_assignments a ON p.reference_id = a.assignment_id
                JOIN housing_rooms r ON a.room_id = r.room_id
                JOIN housing_buildings b ON r.building_id = b.building_id
                WHERE p.source_type = 'housing' AND p.student_id = ?
                ORDER BY p.payment_date DESC
                ''', (student_id,))

                payments = cursor.fetchall()

                if not payments:
                    print("No payment records found for this student.")
                    conn.close()
                    return

                cursor.execute('SELECT first_name, last_name FROM students WHERE student_id = ?', (student_id,))
                student = cursor.fetchone()

                print(f"\nPayment History for {student[0]} {student[1]} ({student_id}):")
                print("=" * 60)

                for i, payment in enumerate(payments, 1):
                    print(f"{i}. ${payment[2]} - Paid on {payment[3]} via {payment[4]}")
                    print(f"   Room {payment[8]} in {payment[9]}")
                    print(f"   Period: {payment[5]} to {payment[6]} | Status: {payment[7]}")
                    print()

                # Display payment summary
                cursor.execute('''
                SELECT SUM(amount), COUNT(payment_id)
                FROM payments
                WHERE source_type = 'housing' AND student_id = ?
                ''', (student_id,))

                total = cursor.fetchone()

                print("\nPayment Summary:")
                print(f"Total Payments: {total[1]}")
                print(f"Total Amount Paid: ${total[0]}")

            elif filter_choice == '2':
                # View by building
                cursor.execute('SELECT building_id, building_name FROM housing_buildings ORDER BY building_name')
                buildings = cursor.fetchall()

                if not buildings:
                    print("No buildings found in the system.")
                    conn.close()
                    return

                print("\nSelect Building:")
                for i, (bid, bname) in enumerate(buildings, 1):
                    print(f"{i}. {bname}")

                while True:
                    try:
                        choice = int(input("\nSelect building (enter number): "))
                        if 1 <= choice <= len(buildings):
                            building_id = buildings[choice - 1][0]
                            building_name = buildings[choice - 1][1]
                            break
                        else:
                            print(f"Please enter a number between 1 and {len(buildings)}.")
                    except ValueError:
                        print("Please enter a valid number.")

                cursor.execute('''
                SELECT p.source_payment_id, p.student_id, s.first_name, s.last_name,
                       p.amount, p.payment_date, p.payment_method,
                       p.payment_period_start, p.payment_period_end, p.status,
                       r.room_number
                FROM payments p
                JOIN students s ON p.student_id = s.student_id
                JOIN housing_assignments a ON p.reference_id = a.assignment_id
                JOIN housing_rooms r ON a.room_id = r.room_id
                WHERE p.source_type = 'housing' AND r.building_id = ?
                ORDER BY p.payment_date DESC
                LIMIT 50  -- Limit to prevent too many results
                ''', (building_id,))

                payments = cursor.fetchall()

                if not payments:
                    print(f"No payment records found for {building_name}.")
                    conn.close()
                    return

                print(f"\nPayment History for {building_name}:")
                print("=" * 60)

                for i, payment in enumerate(payments, 1):
                    print(f"{i}. {payment[2]} {payment[3]} ({payment[1]}) - ${payment[4]}")
                    print(f"   Room: {payment[10]} | Paid on: {payment[5]} via {payment[6]}")
                    print(f"   Period: {payment[7]} to {payment[8]} | Status: {payment[9]}")
                    print()

                # Display payment summary
                cursor.execute('''
                SELECT SUM(p.amount), COUNT(p.payment_id)
                FROM payments p
                JOIN housing_assignments a ON p.reference_id = a.assignment_id
                JOIN housing_rooms r ON a.room_id = r.room_id
                WHERE p.source_type = 'housing' AND r.building_id = ?
                ''', (building_id,))

                total = cursor.fetchone()

                print("\nPayment Summary:")
                print(f"Total Payments: {total[1]}")
                print(f"Total Amount Paid: ${total[0]}")

            elif filter_choice == '3':
                # View by date range
                while True:
                    try:
                        start_date = input("Start Date (YYYY-MM-DD): ")
                        # Validate date format
                        datetime.datetime.strptime(start_date, '%Y-%m-%d')
                        break
                    except ValueError:
                        print("Invalid date format. Please use YYYY-MM-DD.")

                while True:
                    try:
                        end_date = input("End Date (YYYY-MM-DD): ")
                        # Validate date format
                        datetime.datetime.strptime(end_date, '%Y-%m-%d')
                        break
                    except ValueError:
                        print("Invalid date format. Please use YYYY-MM-DD.")

                cursor.execute('''
                SELECT p.source_payment_id, p.student_id, s.first_name, s.last_name,
                       p.amount, p.payment_date, p.payment_method,
                       r.room_number, b.building_name, p.status
                FROM payments p
                JOIN students s ON p.student_id = s.student_id
                JOIN housing_assignments a ON p.reference_id = a.assignment_id
                JOIN housing_rooms r ON a.room_id = r.room_id
                JOIN housing_buildings b ON r.building_id = b.building_id
                WHERE p.source_type = 'housing' AND p.payment_date BETWEEN ? AND ?
                ORDER BY p.payment_date DESC
                ''', (start_date, end_date + ' 23:59:59'))

                payments = cursor.fetchall()

                if not payments:
                    print(f"No payment records found between {start_date} and {end_date}.")
                    conn.close()
                    return

                print(f"\nPayment History ({start_date} to {end_date}):")
                print("=" * 60)

                for i, payment in enumerate(payments, 1):
                    print(f"{i}. {payment[2]} {payment[3]} ({payment[1]}) - ${payment[4]}")
                    print(f"   Paid on: {payment[5]} via {payment[6]}")
                    print(f"   Room: {payment[7]} in {payment[8]} | Status: {payment[9]}")
                    print()

                # Display payment summary
                cursor.execute('''
                SELECT SUM(amount), COUNT(payment_id)
                FROM payments
                WHERE source_type = 'housing' AND payment_date BETWEEN ? AND ?
                ''', (start_date, end_date + ' 23:59:59'))

                total = cursor.fetchone()

                print("\nPayment Summary:")
                print(f"Total Payments: {total[1]}")
                print(f"Total Amount Paid: ${total[0]}")

            elif filter_choice == '4':
                # View recent payments (last 30 days)
                thirty_days_ago = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime('%Y-%m-%d')
                today = datetime.datetime.now().strftime('%Y-%m-%d')

                cursor.execute('''
                SELECT p.source_payment_id, p.student_id, s.first_name, s.last_name,
                       p.amount, p.payment_date, p.payment_method,
                       r.room_number, b.building_name, p.status
                FROM payments p
                JOIN students s ON p.student_id = s.student_id
                JOIN housing_assignments a ON p.reference_id = a.assignment_id
                JOIN housing_rooms r ON a.room_id = r.room_id
                JOIN housing_buildings b ON r.building_id = b.building_id
                WHERE p.source_type = 'housing' AND p.payment_date BETWEEN ? AND ?
                ORDER BY p.payment_date DESC
                ''', (thirty_days_ago, today + ' 23:59:59'))

                payments = cursor.fetchall()

                if not payments:
                    print("No payment records found in the last 30 days.")
                    conn.close()
                    return

                print(f"\nRecent Payments (Last 30 Days):")
                print("=" * 60)

                for i, payment in enumerate(payments, 1):
                    print(f"{i}. {payment[2]} {payment[3]} ({payment[1]}) - ${payment[4]}")
                    print(f"   Paid on: {payment[5]} via {payment[6]}")
                    print(f"   Room: {payment[7]} in {payment[8]} | Status: {payment[9]}")
                    print()

                # Display payment summary
                cursor.execute('''
                SELECT SUM(amount), COUNT(payment_id)
                FROM payments
                WHERE source_type = 'housing' AND payment_date BETWEEN ? AND ?
                ''', (thirty_days_ago, today + ' 23:59:59'))

                total = cursor.fetchone()

                print("\nPayment Summary:")
                print(f"Total Payments: {total[1]}")
                print(f"Total Amount Paid: ${total[0]}")

            else:
                print("Invalid choice.")
                conn.close()
                return

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error viewing payment history: {e}")
