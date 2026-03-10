from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime
import json

from .app import auth


def manage_collections():
    """Collection management system for overdue accounts"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to manage collections.")
        return

    if not auth.check_permission('manage_finances'):
        print("You don't have permission to manage collections.")
        return

    while True:
        print("\n" + "=" * 50)
        print("COLLECTION MANAGEMENT SYSTEM")
        print("=" * 50)
        print("1. View Overdue Accounts")
        print("2. Create Collection Case")
        print("3. Assign to Collection Agency")
        print("4. Track Collection Progress")
        print("5. Payment Arrangements")
        print("6. Collection Reports")
        print("7. Manage Collection Agencies")
        print("8. Automated Collection Workflows")
        print("9. Return to Finance Menu")

        choice = input("Enter your choice (1-9): ").strip()

        if choice == '1':
            view_overdue_accounts()
        elif choice == '2':
            create_collection_case()
        elif choice == '3':
            assign_to_collection_agency()
        elif choice == '4':
            track_collection_progress()
        elif choice == '5':
            create_payment_arrangement()
        elif choice == '6':
            from .collection_reports import generate_collection_reports
            generate_collection_reports()
        elif choice == '7':
            from .agencies import manage_collection_agencies
            manage_collection_agencies()
        elif choice == '8':
            from .agencies import setup_collection_workflows
            setup_collection_workflows()
        elif choice == '9':
            return
        else:
            print("Invalid choice. Please try again.")

def create_collection_case():
    """Create a new collection case for an overdue account"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        student_id = input("Enter student ID for collection case: ").strip()

        if not student_exists(student_id):
            print(f"Student with ID {student_id} does not exist.")
            return

        # Calculate total debt
        cursor.execute('''
        SELECT SUM(sf.amount) - COALESCE(SUM(pa.amount), 0) as total_debt,
               COUNT(sf.student_fee_id) as overdue_count
        FROM student_fees sf
        LEFT JOIN payment_allocations pa ON sf.student_fee_id = pa.student_fee_id
        WHERE sf.student_id = ? AND sf.status IN ('unpaid', 'partial')
        AND date(sf.due_date) < date('now')
        ''', (student_id,))

        debt_info = cursor.fetchone()
        total_debt, overdue_count = debt_info

        if not total_debt or total_debt <= 0:
            print(f"No overdue debt found for student {student_id}.")
            return

        print(f"\nCollection Case Details:")
        print(f"Student: {get_student_name(student_id)} ({student_id})")
        print(f"Total Debt: £{total_debt:.2f}")
        print(f"Overdue Fees: {overdue_count}")

        # Check if case already exists
        cursor.execute('''
        SELECT case_id, case_status FROM collection_cases
        WHERE student_id = ? AND case_status NOT IN ('resolved', 'closed')
        ''', (student_id,))

        existing_case = cursor.fetchone()

        if existing_case:
            print(f"Active collection case already exists (Case ID: {existing_case[0]}, Status: {existing_case[1]})")
            return

        # Get case notes
        notes = input("Enter case notes: ").strip()

        # Create collection case
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        INSERT INTO collection_cases
        (student_id, total_debt, case_status, notes, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (student_id, total_debt, 'new', notes, now, now))

        case_id = cursor.lastrowid

        conn.commit()

        print(f"\nCollection case created successfully!")
        print(f"Case ID: {case_id}")
        print(f"Status: New")
        print(f"Total Debt: £{total_debt:.2f}")

        # Log the action
        log_audit_action('create_collection_case', 'collection_cases', str(case_id), {
            'student_id': student_id,
            'total_debt': total_debt,
            'created_by': auth.current_user['username']
        })

        # Ask about immediate actions
        action = input("\nTake immediate action? (1=Send notice, 2=Assign to agency, 3=Skip): ").strip()

        if action == '1':
            send_collection_notice(student_id, case_id)
        elif action == '2':
            assign_case_to_agency(case_id)

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")

def send_collection_notice(student_id, case_id):
    """Send collection notice to student"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get student and case details
        cursor.execute('''
        SELECT s.first_name, s.last_name, s.email_address, cc.total_debt
        FROM students s
        JOIN collection_cases cc ON s.student_id = cc.student_id
        WHERE cc.case_id = ?
        ''', (case_id,))

        result = cursor.fetchone()

        if result:
            first_name, last_name, email, total_debt = result
            student_name = f"{first_name} {last_name}"

            # Use email template
            from education_system.university_system.infrastructure.email.template_utils import render_template

            # Calculate days overdue (you may need to adjust this based on your actual data)
            days_overdue = 30  # Default placeholder

            template_vars = {
                'student_name': student_name,
                'amount_due': f"£{total_debt:.2f}",
                'due_date': 'N/A',  # You may need to fetch this from your data
                'days_overdue': days_overdue
            }

            subject, body = render_template('collection_notice', template_vars)

            if not subject or not body:
                print("Failed to load email template.")
                return

            if send_email_notification(email, subject, body):
                print(f"Collection notice sent to {email}")

                # Update case with notice sent
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('''
                UPDATE collection_cases
                SET notes = notes || ' | Notice sent: ' || ?, updated_at = ?
                WHERE case_id = ?
                ''', (now, now, case_id))

                conn.commit()
            else:
                print("Failed to send collection notice")

        conn.close()

    except Exception as e:
        print(f"Error sending collection notice: {e}")

def assign_to_collection_agency():
    """Assign collection cases to external agencies - Menu wrapper function"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get unassigned collection cases
        cursor.execute('''
        SELECT cc.case_id, cc.student_id, s.first_name, s.last_name,
               cc.total_debt, cc.case_status, cc.created_at
        FROM collection_cases cc
        JOIN students s ON cc.student_id = s.student_id
        WHERE cc.case_status IN ('new', 'in_progress') AND cc.agency_id IS NULL
        ORDER BY cc.total_debt DESC
        ''')

        unassigned_cases = cursor.fetchall()

        if not unassigned_cases:
            print("No unassigned collection cases found.")
            conn.close()
            return

        print(f"\nUnassigned Collection Cases:")
        print("=" * 100)
        for i, case in enumerate(unassigned_cases, 1):
            case_id, student_id, first_name, last_name, debt, status, created = case
            student_name = f"{first_name} {last_name}"
            print(f"{i}. Case ID {case_id}: {student_name} ({student_id}) - £{debt:.2f} - {status}")

        # Select case to assign
        case_choice = input(f"\nSelect case to assign (1-{len(unassigned_cases)}): ").strip()
        try:
            case_index = int(case_choice) - 1
            if 0 <= case_index < len(unassigned_cases):
                selected_case = unassigned_cases[case_index]
                case_id = selected_case[0]

                # Call the existing function with the case_id
                assign_case_to_agency(case_id)
            else:
                print("Invalid selection.")
        except ValueError:
            print("Invalid input.")

        conn.close()

    except Exception as e:
        print(f"Error in assign_to_collection_agency: {e}")

def track_collection_progress():
    """Track progress of collection cases"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get all active collection cases
        cursor.execute('''
        SELECT cc.case_id, cc.student_id, s.first_name, s.last_name,
               cc.total_debt, cc.amount_collected, cc.case_status,
               ca.agency_name, cc.assigned_date, cc.notes
        FROM collection_cases cc
        JOIN students s ON cc.student_id = s.student_id
        LEFT JOIN collection_agencies ca ON cc.agency_id = ca.agency_id
        WHERE cc.case_status NOT IN ('resolved', 'closed')
        ORDER BY cc.assigned_date DESC
        ''')

        active_cases = cursor.fetchall()

        if not active_cases:
            print("No active collection cases found.")
            return

        print(f"\nActive Collection Cases Progress:")
        print("=" * 130)
        print(f"{'Case ID':<8} {'Student':<25} {'Debt':<12} {'Collected':<12} {'Status':<15} {'Agency':<20} {'Assigned':<12}")
        print("-" * 130)

        total_debt = 0
        total_collected = 0

        for case in active_cases:
            case_id, student_id, first_name, last_name, debt, collected, status, agency, assigned, notes = case
            student_name = f"{first_name} {last_name}"
            agency_name = agency if agency else "Unassigned"
            assigned_date = assigned if assigned else "N/A"

            print(f"{case_id:<8} {student_name:<25} £{debt:<11.2f} £{collected or 0:<11.2f} {status:<15} {agency_name:<20} {assigned_date:<12}")

            total_debt += debt
            total_collected += collected or 0

        print("-" * 130)
        print(f"Totals: Debt £{total_debt:,.2f}, Collected £{total_collected:,.2f}, Outstanding £{total_debt - total_collected:,.2f}")

        # Collection efficiency
        if total_debt > 0:
            efficiency = (total_collected / total_debt) * 100
            print(f"Collection Efficiency: {efficiency:.1f}%")

        print("=" * 130)

        # Option to update case status
        update_case = input("\nUpdate a case status? Enter Case ID (or press Enter to skip): ").strip()
        if update_case:
            update_collection_case_status(update_case)

        conn.close()

    except Exception as e:
        print(f"Error tracking collection progress: {e}")

def update_collection_case_status(case_id):
    """Update status of a collection case"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get case details
        cursor.execute('''
        SELECT cc.case_id, cc.student_id, s.first_name, s.last_name,
               cc.total_debt, cc.amount_collected, cc.case_status
        FROM collection_cases cc
        JOIN students s ON cc.student_id = s.student_id
        WHERE cc.case_id = ?
        ''', (case_id,))

        case = cursor.fetchone()

        if not case:
            print(f"Collection case {case_id} not found.")
            return

        case_id, student_id, first_name, last_name, debt, collected, status = case
        student_name = f"{first_name} {last_name}"

        print(f"\nUpdating Case {case_id}: {student_name}")
        print(f"Current Status: {status}")
        print(f"Debt: £{debt:.2f}, Collected: £{collected or 0:.2f}")

        # Status options
        statuses = ['new', 'assigned', 'in_progress', 'resolved', 'closed']
        print("\nAvailable statuses:")
        for i, stat in enumerate(statuses, 1):
            print(f"{i}. {stat.title()}")

        status_choice = input("Select new status (1-5): ").strip()
        try:
            status_index = int(status_choice) - 1
            if 0 <= status_index < len(statuses):
                new_status = statuses[status_index]
            else:
                print("Invalid selection.")
                return
        except ValueError:
            print("Invalid input.")
            return

        # Get additional details
        if new_status in ['resolved', 'closed']:
            try:
                amount_collected = float(input("Enter amount collected: £"))
                resolution_notes = input("Enter resolution notes: ").strip()
            except ValueError:
                print("Invalid amount.")
                return
        else:
            amount_collected = collected or 0
            resolution_notes = input("Enter update notes (optional): ").strip()

        # Update case
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        if new_status in ['resolved', 'closed']:
            cursor.execute('''
            UPDATE collection_cases
            SET case_status = ?, amount_collected = ?, resolution_date = ?,
                notes = COALESCE(notes, '') || ' | ' || ?, updated_at = ?
            WHERE case_id = ?
            ''', (new_status, amount_collected, now, resolution_notes, now, case_id))
        else:
            cursor.execute('''
            UPDATE collection_cases
            SET case_status = ?,
                notes = COALESCE(notes, '') || ' | ' || ?, updated_at = ?
            WHERE case_id = ?
            ''', (new_status, resolution_notes, now, case_id))

        conn.commit()

        print(f"Case {case_id} updated to status: {new_status}")

        # Log the action
        log_audit_action('update_collection_case', 'collection_cases', str(case_id), {
            'old_status': status,
            'new_status': new_status,
            'updated_by': auth.current_user['username']
        })

        conn.close()

    except Exception as e:
        print(f"Error updating collection case: {e}")

def view_student_collection_detail(student_id):
    """View detailed collection information for a student"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get student basic info
        cursor.execute('''
        SELECT first_name, last_name, email_address, phone_number
        FROM students
        WHERE student_id = ?
        ''', (student_id,))

        student = cursor.fetchone()

        if not student:
            print(f"Student {student_id} not found.")
            return

        first_name, last_name, email, phone = student
        student_name = f"{first_name} {last_name}"

        print(f"\nCollection Details for {student_name} ({student_id})")
        print("=" * 60)
        print(f"Email: {email}")
        print(f"Phone: {phone}")

        # Get overdue fees
        cursor.execute('''
        SELECT ft.fee_name, sf.amount, sf.due_date,
               julianday('now') - julianday(sf.due_date) as days_overdue
        FROM student_fees sf
        JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
        WHERE sf.student_id = ? AND sf.status IN ('unpaid', 'partial')
        AND date(sf.due_date) < date('now')
        ORDER BY sf.due_date
        ''', (student_id,))

        overdue_fees = cursor.fetchall()

        if overdue_fees:
            print(f"\nOverdue Fees:")
            print("-" * 50)
            total_overdue = 0
            for fee_name, amount, due_date, days_overdue in overdue_fees:
                print(f"{fee_name}: £{amount:.2f} (due {due_date}, {int(days_overdue)} days overdue)")
                total_overdue += amount

            print(f"-" * 50)
            print(f"Total Overdue: £{total_overdue:.2f}")

        # Get collection case info
        cursor.execute('''
        SELECT cc.case_id, cc.case_status, cc.total_debt, cc.amount_collected,
               ca.agency_name, cc.assigned_date, cc.notes
        FROM collection_cases cc
        LEFT JOIN collection_agencies ca ON cc.agency_id = ca.agency_id
        WHERE cc.student_id = ?
        ORDER BY cc.created_at DESC
        ''', (student_id,))

        cases = cursor.fetchall()

        if cases:
            print(f"\nCollection Cases:")
            print("-" * 60)
            for case_id, status, debt, collected, agency, assigned, notes in cases:
                print(f"Case {case_id}: {status.title()}")
                print(f"  Debt: £{debt:.2f}, Collected: £{collected or 0:.2f}")
                if agency:
                    print(f"  Agency: {agency}")
                if assigned:
                    print(f"  Assigned: {assigned}")
                if notes:
                    print(f"  Notes: {notes[:100]}...")
                print()

        conn.close()

    except Exception as e:
        print(f"Error viewing student collection detail: {e}")
