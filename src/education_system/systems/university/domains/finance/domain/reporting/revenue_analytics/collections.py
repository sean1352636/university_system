from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection, transaction
from datetime import datetime
import json

from education_system.systems.university.domains.finance.domain.reporting.revenue_analytics.app import auth
from education_system.systems.university.domains.finance.domain.core.aid import create_payment_arrangement
from education_system.systems.university.domains.finance.domain.core.students import student_exists, get_student_name
from education_system.systems.university.domains.finance.domain.core.security_automation import log_audit_action, send_email_notification


def manage_collections():
    """Collection management system for overdue accounts"""
    from education_system.systems.university.domains.finance.domain.core.analytics import view_overdue_accounts
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
            from education_system.systems.university.domains.finance.domain.reporting.revenue_analytics.collection_reports import generate_collection_reports
            generate_collection_reports()
        elif choice == '7':
            from education_system.systems.university.domains.finance.domain.reporting.revenue_analytics.agencies import manage_collection_agencies
            manage_collection_agencies()
        elif choice == '8':
            from education_system.systems.university.domains.finance.domain.reporting.revenue_analytics.agencies import setup_collection_workflows
            setup_collection_workflows()
        elif choice == '9':
            return
        else:
            print("Invalid choice. Please try again.")

def create_collection_case():
    """Create a new collection case for an overdue account"""
    from education_system.systems.university.domains.finance.domain.core.analytics import assign_case_to_agency
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

        print("\nCollection Case Details:")
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

        print("\nCollection case created successfully!")
        print(f"Case ID: {case_id}")
        print("Status: New")
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
            from education_system.systems.university.infrastructure.email.template_utils import render_template

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

# ---------------------------------------------------------------------------
# Non-interactive API
#
# The functions below take every value as an argument and return data. The
# menu wrappers further down prompt for those values and print the result, so
# the CLI and the GUI share one implementation instead of drifting apart —
# which is what left the GUI calling `assign_to_collection_agency(case_id,
# agency_id)` against a zero-argument function.
# ---------------------------------------------------------------------------

CASE_STATUSES = ('new', 'assigned', 'in_progress', 'resolved', 'closed')

#: Statuses that close a case and therefore carry a resolution date.
_CLOSING_STATUSES = ('resolved', 'closed')


def _current_username(explicit=None):
    """Best-effort actor name for audit rows; never raises."""
    if explicit:
        return explicit
    try:
        return auth.current_user['username']
    except Exception:
        return 'system'


def list_active_agencies():
    """Return the active collection agencies as a list of dicts."""
    conn = get_connection()
    try:
        rows = conn.execute('''
        SELECT agency_id, agency_name, commission_rate, minimum_amount
        FROM collection_agencies
        WHERE is_active = 1
        ORDER BY agency_name
        ''').fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def list_unassigned_cases():
    """Return open collection cases that have no agency yet."""
    conn = get_connection()
    try:
        rows = conn.execute('''
        SELECT cc.case_id, cc.student_id, s.first_name, s.last_name,
               cc.total_debt, cc.case_status, cc.created_at
        FROM collection_cases cc
        JOIN students s ON cc.student_id = s.student_id
        WHERE cc.case_status IN ('new', 'in_progress') AND cc.agency_id IS NULL
        ORDER BY cc.total_debt DESC
        ''').fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def list_active_cases():
    """Return every collection case that is not yet resolved or closed."""
    conn = get_connection()
    try:
        rows = conn.execute('''
        SELECT cc.case_id, cc.student_id, s.first_name, s.last_name,
               cc.total_debt, cc.amount_collected, cc.case_status,
               ca.agency_name, cc.assigned_date, cc.notes
        FROM collection_cases cc
        JOIN students s ON cc.student_id = s.student_id
        LEFT JOIN collection_agencies ca ON cc.agency_id = ca.agency_id
        WHERE cc.case_status NOT IN ('resolved', 'closed')
        ORDER BY cc.assigned_date DESC
        ''').fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def list_cases(limit=500):
    """Every collection case, newest first — the Collections table in the GUI."""
    conn = get_connection()
    try:
        rows = conn.execute('''
        SELECT cc.case_id, cc.student_id, s.first_name, s.last_name,
               cc.total_debt, cc.case_status, cc.assigned_date,
               cc.amount_collected, cc.resolution_date, cc.agency_id,
               ca.agency_name, cc.created_at
        FROM collection_cases cc
        LEFT JOIN students s ON cc.student_id = s.student_id
        LEFT JOIN collection_agencies ca ON cc.agency_id = ca.agency_id
        ORDER BY cc.created_at DESC, cc.case_id DESC
        LIMIT ?
        ''', (int(limit),)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_case(case_id):
    """One collection case with the student's name and email, or ``None``."""
    conn = get_connection()
    try:
        row = conn.execute('''
        SELECT cc.case_id, cc.student_id, s.first_name, s.last_name, s.email_address,
               cc.total_debt, cc.case_status, cc.assigned_date, cc.resolution_date,
               cc.amount_collected, cc.agency_id, ca.agency_name, cc.notes,
               cc.created_at, cc.updated_at
        FROM collection_cases cc
        LEFT JOIN students s ON cc.student_id = s.student_id
        LEFT JOIN collection_agencies ca ON cc.agency_id = ca.agency_id
        WHERE cc.case_id = ?
        ''', (case_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def open_case(student_id, total_debt, notes='', created_by=None):
    """Open a collection case for a stated debt (the GUI's Create Case form).

    Unlike :func:`create_collection_case`, the debt is supplied rather than
    derived from overdue fees. Raises ValueError for an unknown student, a
    non-positive debt, or when the student already has an open case.
    """
    student_id = str(student_id).strip()
    if not student_id or not student_exists(student_id):
        raise ValueError(f"Student with ID {student_id!r} does not exist")
    total_debt = float(total_debt)
    if total_debt <= 0:
        raise ValueError("Total debt must be greater than zero")

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with transaction() as conn:
        existing = conn.execute('''
        SELECT case_id, case_status FROM collection_cases
        WHERE student_id = ? AND case_status NOT IN ('resolved', 'closed')
        ''', (student_id,)).fetchone()
        if existing:
            raise ValueError(
                f"Student {student_id} already has an open case "
                f"(Case ID {existing['case_id']}, status {existing['case_status']})")
        cursor = conn.execute('''
        INSERT INTO collection_cases
        (student_id, total_debt, case_status, amount_collected, notes, created_at, updated_at)
        VALUES (?, ?, 'new', 0, ?, ?, ?)
        ''', (student_id, total_debt, notes or '', now, now))
        case_id = cursor.lastrowid

    log_audit_action('create_collection_case', 'collection_cases', str(case_id), {
        'student_id': student_id,
        'total_debt': total_debt,
        'created_by': _current_username(created_by),
    })
    return case_id


def assign_case(case_id, agency_id, assigned_by=None):
    """Assign one collection case to one agency.

    Returns a summary dict. Raises ValueError when the case or agency is
    missing, the agency is inactive, or the case is already closed.
    """
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with transaction() as conn:
        case = conn.execute(
            'SELECT case_id, student_id, total_debt, case_status, agency_id '
            'FROM collection_cases WHERE case_id = ?', (case_id,)
        ).fetchone()
        if case is None:
            raise ValueError(f"Collection case {case_id} not found")
        if case['case_status'] in _CLOSING_STATUSES:
            raise ValueError(
                f"Case {case_id} is {case['case_status']} and cannot be reassigned")

        agency = conn.execute(
            'SELECT agency_id, agency_name, is_active FROM collection_agencies '
            'WHERE agency_id = ?', (agency_id,)
        ).fetchone()
        if agency is None:
            raise ValueError(f"Collection agency {agency_id} not found")
        if not agency['is_active']:
            raise ValueError(f"Collection agency {agency['agency_name']} is inactive")

        conn.execute('''
        UPDATE collection_cases
        SET agency_id = ?, case_status = 'assigned', assigned_date = ?, updated_at = ?
        WHERE case_id = ?
        ''', (agency_id, now, now, case_id))

        result = {
            'case_id': case_id,
            'agency_id': agency_id,
            'agency_name': agency['agency_name'],
            'student_id': case['student_id'],
            'total_debt': case['total_debt'],
            'previous_agency_id': case['agency_id'],
        }

    log_audit_action('assign_collection_case', 'collection_cases', str(case_id), {
        **result, 'assigned_by': _current_username(assigned_by),
    })
    return result


def set_case_status(case_id, new_status, notes='', amount_collected=None, updated_by=None):
    """Move a collection case to ``new_status``.

    ``amount_collected`` is recorded when supplied; resolving or closing a case
    also stamps the resolution date. Raises ValueError for an unknown status or
    a missing case.
    """
    if new_status not in CASE_STATUSES:
        raise ValueError(
            f"Invalid case status '{new_status}'. Expected one of: {', '.join(CASE_STATUSES)}")

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with transaction() as conn:
        case = conn.execute(
            'SELECT case_status, amount_collected FROM collection_cases WHERE case_id = ?',
            (case_id,)
        ).fetchone()
        if case is None:
            raise ValueError(f"Collection case {case_id} not found")

        old_status = case['case_status']
        collected = case['amount_collected'] or 0
        if amount_collected is not None:
            collected = float(amount_collected)
            if collected < 0:
                raise ValueError("Amount collected cannot be negative")

        if new_status in _CLOSING_STATUSES:
            conn.execute('''
            UPDATE collection_cases
            SET case_status = ?, amount_collected = ?, resolution_date = ?,
                notes = COALESCE(notes, '') || ' | ' || ?, updated_at = ?
            WHERE case_id = ?
            ''', (new_status, collected, now, notes, now, case_id))
        else:
            conn.execute('''
            UPDATE collection_cases
            SET case_status = ?, amount_collected = ?,
                notes = COALESCE(notes, '') || ' | ' || ?, updated_at = ?
            WHERE case_id = ?
            ''', (new_status, collected, notes, now, case_id))

    log_audit_action('update_collection_case', 'collection_cases', str(case_id), {
        'old_status': old_status,
        'new_status': new_status,
        'amount_collected': collected,
        'notes': notes,
        'updated_by': _current_username(updated_by),
    })
    return {'case_id': case_id, 'old_status': old_status, 'new_status': new_status,
            'amount_collected': collected}


def format_collection_progress(cases=None):
    """Render active collection cases as a fixed-width report.

    Returns the text rather than printing it, so the GUI can show it without
    capturing stdout.
    """
    if cases is None:
        cases = list_active_cases()

    if not cases:
        return "No active collection cases found."

    lines = [
        "",
        "Active Collection Cases Progress:",
        "=" * 130,
        f"{'Case ID':<8} {'Student':<25} {'Debt':<12} {'Collected':<12} "
        f"{'Status':<15} {'Agency':<20} {'Assigned':<12}",
        "-" * 130,
    ]

    total_debt = 0
    total_collected = 0
    for case in cases:
        debt = case['total_debt'] or 0
        collected = case['amount_collected'] or 0
        student_name = f"{case['first_name']} {case['last_name']}"
        lines.append(
            f"{case['case_id']:<8} {student_name:<25} £{debt:<11.2f} "
            f"£{collected:<11.2f} {case['case_status']:<15} "
            f"{case['agency_name'] or 'Unassigned':<20} {case['assigned_date'] or 'N/A':<12}"
        )
        total_debt += debt
        total_collected += collected

    lines.append("-" * 130)
    lines.append(
        f"Totals: Debt £{total_debt:,.2f}, Collected £{total_collected:,.2f}, "
        f"Outstanding £{total_debt - total_collected:,.2f}")
    if total_debt > 0:
        lines.append(f"Collection Efficiency: {(total_collected / total_debt) * 100:.1f}%")
    lines.append("=" * 130)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Interactive menu wrappers (CLI only — these prompt on stdin)
# ---------------------------------------------------------------------------

def assign_to_collection_agency():
    """Assign collection cases to external agencies - Menu wrapper function"""
    from education_system.systems.university.domains.finance.domain.core.analytics import assign_case_to_agency
    try:
        unassigned_cases = list_unassigned_cases()

        if not unassigned_cases:
            print("No unassigned collection cases found.")
            return

        print("\nUnassigned Collection Cases:")
        print("=" * 100)
        for i, case in enumerate(unassigned_cases, 1):
            student_name = f"{case['first_name']} {case['last_name']}"
            print(f"{i}. Case ID {case['case_id']}: {student_name} ({case['student_id']}) "
                  f"- £{case['total_debt']:.2f} - {case['case_status']}")

        # Select case to assign
        case_choice = input(f"\nSelect case to assign (1-{len(unassigned_cases)}): ").strip()
        try:
            case_index = int(case_choice) - 1
            if 0 <= case_index < len(unassigned_cases):
                # Call the existing function with the case_id
                assign_case_to_agency(unassigned_cases[case_index]['case_id'])
            else:
                print("Invalid selection.")
        except ValueError:
            print("Invalid input.")

    except Exception as e:
        print(f"Error in assign_to_collection_agency: {e}")

def track_collection_progress():
    """Track progress of collection cases"""
    try:
        active_cases = list_active_cases()
        print(format_collection_progress(active_cases))

        if not active_cases:
            return

        # Option to update case status
        update_case = input("\nUpdate a case status? Enter Case ID (or press Enter to skip): ").strip()
        if update_case:
            update_collection_case_status(update_case)

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
        statuses = list(CASE_STATUSES)
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
            except ValueError:
                print("Invalid amount.")
                return
            resolution_notes = input("Enter resolution notes: ").strip()
        else:
            amount_collected = None
            resolution_notes = input("Enter update notes (optional): ").strip()

        conn.close()

        set_case_status(case_id, new_status, resolution_notes, amount_collected)
        print(f"Case {case_id} updated to status: {new_status}")

    except Exception as e:
        print(f"Error updating collection case: {e}")

def view_student_collection_detail(student_id):
    """View detailed collection information for a student"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get student basic info
        cursor.execute('''
        SELECT first_name, last_name, email_address, phone
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
            print("\nOverdue Fees:")
            print("-" * 50)
            total_overdue = 0
            for fee_name, amount, due_date, days_overdue in overdue_fees:
                print(f"{fee_name}: £{amount:.2f} (due {due_date}, {int(days_overdue)} days overdue)")
                total_overdue += amount

            print("-" * 50)
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
            print("\nCollection Cases:")
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
