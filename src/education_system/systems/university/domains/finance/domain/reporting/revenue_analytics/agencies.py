from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from datetime import datetime
import json


def manage_collection_agencies():
    """Manage collection agencies"""
    while True:
        print("\n" + "=" * 40)
        print("COLLECTION AGENCIES MANAGEMENT")
        print("=" * 40)
        print("1. View Collection Agencies")
        print("2. Add New Agency")
        print("3. Edit Agency")
        print("4. Deactivate Agency")
        print("5. Agency Performance")
        print("6. Return to Collection Menu")

        choice = input("Enter your choice (1-6): ").strip()

        if choice == '1':
            view_collection_agencies()
        elif choice == '2':
            add_collection_agency()
        elif choice == '3':
            edit_collection_agency()
        elif choice == '4':
            deactivate_collection_agency()
        elif choice == '5':
            from education_system.systems.university.domains.finance.domain.reporting.revenue_analytics.collection_reports import agency_performance_report
            agency_performance_report()
        elif choice == '6':
            return
        else:
            print("Invalid choice. Please try again.")

def view_collection_agencies():
    """View all collection agencies"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        SELECT agency_id, agency_name, contact_email, contact_phone,
               commission_rate, minimum_amount, is_active
        FROM collection_agencies
        ORDER BY is_active DESC, agency_name
        ''')

        agencies = cursor.fetchall()

        if not agencies:
            print("No collection agencies found.")
            return

        print("\nCollection Agencies:")
        print("=" * 100)
        print(f"{'ID':<5} {'Name':<25} {'Email':<30} {'Phone':<15} {'Commission':<10} {'Min Amount':<10} {'Active':<8}")
        print("-" * 100)

        for agency in agencies:
            agency_id, name, email, phone, commission, min_amount, active = agency
            active_str = "Yes" if active else "No"

            print(f"{agency_id:<5} {name:<25} {email or 'N/A':<30} {phone or 'N/A':<15} {commission or 0:.1f}%{'':<5} £{min_amount or 0:<9.2f} {active_str:<8}")

        print("=" * 100)

        conn.close()

    except Exception as e:
        print(f"Error viewing collection agencies: {e}")

def add_collection_agency():
    """Add a new collection agency"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("\nAdding New Collection Agency:")

        agency_name = input("Enter agency name: ").strip()
        if not agency_name:
            print("Agency name is required.")
            return

        contact_email = input("Enter contact email: ").strip()
        contact_phone = input("Enter contact phone: ").strip()

        try:
            commission_rate = float(input("Enter commission rate (%): "))
            minimum_amount = float(input("Enter minimum debt amount: £"))
        except ValueError:
            print("Invalid numeric input.")
            return

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        INSERT INTO collection_agencies
        (agency_name, contact_email, contact_phone, commission_rate, minimum_amount, is_active, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (agency_name, contact_email, contact_phone, commission_rate, minimum_amount, 1, now, now))

        agency_id = cursor.lastrowid

        conn.commit()

        print("\nCollection agency added successfully!")
        print(f"Agency ID: {agency_id}")
        print(f"Name: {agency_name}")
        print(f"Commission: {commission_rate}%")
        print(f"Minimum Amount: £{minimum_amount:.2f}")

        conn.close()

    except Exception as e:
        print(f"Error adding collection agency: {e}")

def edit_collection_agency():
    """Edit an existing collection agency"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        agency_id = input("Enter agency ID to edit: ").strip()

        # Get current agency details
        cursor.execute('''
        SELECT agency_name, contact_email, contact_phone, commission_rate, minimum_amount
        FROM collection_agencies
        WHERE agency_id = ?
        ''', (agency_id,))

        agency = cursor.fetchone()

        if not agency:
            print("Agency not found.")
            return

        current_name, current_email, current_phone, current_commission, current_minimum = agency

        print(f"\nEditing Agency {agency_id}: {current_name}")

        # Get new values
        new_name = input(f"Enter new name (current: {current_name}): ").strip()
        if not new_name:
            new_name = current_name

        new_email = input(f"Enter new email (current: {current_email}): ").strip()
        if not new_email:
            new_email = current_email

        new_phone = input(f"Enter new phone (current: {current_phone}): ").strip()
        if not new_phone:
            new_phone = current_phone

        commission_input = input(f"Enter new commission rate (current: {current_commission}%): ").strip()
        if commission_input:
            try:
                new_commission = float(commission_input)
            except ValueError:
                print("Invalid commission rate, keeping current value.")
                new_commission = current_commission
        else:
            new_commission = current_commission

        minimum_input = input(f"Enter new minimum amount (current: £{current_minimum}): ").strip()
        if minimum_input:
            try:
                new_minimum = float(minimum_input)
            except ValueError:
                print("Invalid minimum amount, keeping current value.")
                new_minimum = current_minimum
        else:
            new_minimum = current_minimum

        # Update agency
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        UPDATE collection_agencies
        SET agency_name = ?, contact_email = ?, contact_phone = ?,
            commission_rate = ?, minimum_amount = ?, updated_at = ?
        WHERE agency_id = ?
        ''', (new_name, new_email, new_phone, new_commission, new_minimum, now, agency_id))

        conn.commit()

        print(f"Agency {agency_id} updated successfully!")

        conn.close()

    except Exception as e:
        print(f"Error editing collection agency: {e}")

def deactivate_collection_agency():
    """Deactivate a collection agency"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        agency_id = input("Enter agency ID to deactivate: ").strip()

        # Get agency details
        cursor.execute('''
        SELECT agency_name FROM collection_agencies
        WHERE agency_id = ? AND is_active = 1
        ''', (agency_id,))

        agency = cursor.fetchone()

        if not agency:
            print("Agency not found or already inactive.")
            return

        agency_name = agency[0]

        # Check for active cases
        cursor.execute('''
        SELECT COUNT(*) FROM collection_cases
        WHERE agency_id = ? AND case_status NOT IN ('resolved', 'closed')
        ''', (agency_id,))

        active_cases = cursor.fetchone()[0]

        if active_cases > 0:
            print(f"Warning: Agency has {active_cases} active cases.")
            confirm = input("Deactivate anyway? Cases will need to be reassigned. (y/n): ").strip().lower()
            if confirm != 'y':
                return

        confirm = input(f"Deactivate agency '{agency_name}'? (y/n): ").strip().lower()
        if confirm != 'y':
            return

        # Deactivate agency
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        UPDATE collection_agencies
        SET is_active = 0, updated_at = ?
        WHERE agency_id = ?
        ''', (now, agency_id))

        conn.commit()

        print(f"Agency '{agency_name}' deactivated successfully!")

        if active_cases > 0:
            print(f"Remember to reassign {active_cases} active cases to other agencies.")

        conn.close()

    except Exception as e:
        print(f"Error deactivating collection agency: {e}")

def setup_collection_workflows():
    """Create and persist an automated collection workflow."""
    print("\nCollection Workflow Setup:")
    name = input("Workflow name: ").strip() or "Default overdue workflow"
    try:
        minimum_debt = float(input("Minimum overdue debt (£): ").strip() or "100")
        reminder_days = int(input("Reminder interval (days): ").strip() or "14")
        escalation_days = int(input("Escalate after (days): ").strip() or "30")
    except ValueError:
        print("Invalid numeric value.")
        return None
    auto_assign = input("Automatically assign an eligible agency? (y/n): ").strip().lower() == 'y'
    workflow_id = save_collection_workflow(
        name, minimum_debt, reminder_days, escalation_days, auto_assign
    )
    print(f"Workflow saved (ID: {workflow_id}).")
    if input("Run it now? (y/n): ").strip().lower() == 'y':
        result = run_collection_workflow(workflow_id)
        print(f"Created {result['created']} case(s); assigned {result['assigned']} case(s).")
    return workflow_id


def _ensure_workflow_table(conn):
    conn.execute('''
        CREATE TABLE IF NOT EXISTS collection_workflows (
            workflow_id INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_name TEXT NOT NULL,
            minimum_debt REAL NOT NULL DEFAULT 100,
            reminder_days INTEGER NOT NULL DEFAULT 14,
            escalation_days INTEGER NOT NULL DEFAULT 30,
            auto_assign INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            last_run_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS collection_workflow_actions (
            action_id INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_id INTEGER NOT NULL,
            case_id INTEGER NOT NULL,
            action_type TEXT NOT NULL,
            status TEXT NOT NULL,
            details TEXT,
            created_at TEXT NOT NULL
        )
    ''')


def save_collection_workflow(name, minimum_debt=100, reminder_days=14,
                             escalation_days=30, auto_assign=False):
    """Persist workflow configuration and return its identifier."""
    if minimum_debt < 0 or reminder_days < 1 or escalation_days < 1:
        raise ValueError("Workflow thresholds must be positive")
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with transaction() as conn:
        _ensure_workflow_table(conn)
        cursor = conn.execute('''
            INSERT INTO collection_workflows
                (workflow_name, minimum_debt, reminder_days, escalation_days,
                 auto_assign, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (name, minimum_debt, reminder_days, escalation_days,
              int(auto_assign), now, now))
        return cursor.lastrowid


def run_collection_workflow(workflow_id):
    """Create cases for overdue balances and optionally assign agencies."""
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    created = assigned = reminded = escalated = 0
    notifications = []
    with transaction() as conn:
        _ensure_workflow_table(conn)
        workflow = conn.execute(
            "SELECT * FROM collection_workflows WHERE workflow_id=? AND is_active=1",
            (workflow_id,),
        ).fetchone()
        if not workflow:
            raise ValueError(f"Active collection workflow {workflow_id} not found")
        minimum_debt = workflow['minimum_debt']
        active_cases = conn.execute('''
            SELECT case_id, student_id, case_status, created_at
            FROM collection_cases WHERE case_status NOT IN ('resolved','closed')
        ''').fetchall()
        for case in active_cases:
            try:
                opened = datetime.fromisoformat(case['created_at'])
                age_days = (datetime.now() - opened).days
            except (TypeError, ValueError):
                age_days = 0
            if age_days >= workflow['escalation_days'] and case['case_status'] in ('new', 'assigned'):
                conn.execute(
                    "UPDATE collection_cases SET case_status='in_progress', updated_at=? WHERE case_id=?",
                    (now, case['case_id']),
                )
                conn.execute('''INSERT INTO collection_workflow_actions
                    (workflow_id, case_id, action_type, status, details, created_at)
                    VALUES (?, ?, 'escalation', 'completed', ?, ?)''',
                    (workflow_id, case['case_id'], f"Escalated after {age_days} days", now))
                escalated += 1
            last_reminder = conn.execute('''
                SELECT created_at FROM collection_workflow_actions
                WHERE workflow_id=? AND case_id=? AND action_type='reminder'
                ORDER BY action_id DESC LIMIT 1
            ''', (workflow_id, case['case_id'])).fetchone()
            due = not last_reminder
            if last_reminder:
                try:
                    due = (datetime.now() - datetime.fromisoformat(last_reminder[0])).days >= workflow['reminder_days']
                except (TypeError, ValueError):
                    due = True
            if due:
                columns = {row[1] for row in conn.execute("PRAGMA table_info(students)")}
                email_col = 'email' if 'email' in columns else ('email_address' if 'email_address' in columns else None)
                email = None
                if email_col:
                    student = conn.execute(
                        f"SELECT {email_col} FROM students WHERE student_id=?", (case['student_id'],)
                    ).fetchone()
                    email = student[0] if student else None
                status = 'queued' if email else 'no_email'
                conn.execute('''INSERT INTO collection_workflow_actions
                    (workflow_id, case_id, action_type, status, details, created_at)
                    VALUES (?, ?, 'reminder', ?, ?, ?)''',
                    (workflow_id, case['case_id'], status, case['student_id'], now))
                if email:
                    notifications.append((email, case['case_id']))
                reminded += 1
        balances = conn.execute('''
            SELECT sf.student_id,
                   SUM(sf.amount) - COALESCE(SUM(pa.amount), 0) AS debt
            FROM student_fees sf
            LEFT JOIN payment_allocations pa ON pa.student_fee_id=sf.student_fee_id
            WHERE sf.status IN ('unpaid','partial') AND DATE(sf.due_date) < DATE('now')
            GROUP BY sf.student_id
            HAVING debt >= ?
        ''', (minimum_debt,)).fetchall()
        for student_id, debt in balances:
            exists = conn.execute('''
                SELECT 1 FROM collection_cases
                WHERE student_id=? AND case_status NOT IN ('resolved','closed')
            ''', (student_id,)).fetchone()
            if exists:
                continue
            agency_id = None
            status = 'new'
            if workflow['auto_assign']:
                agency = conn.execute('''
                    SELECT agency_id FROM collection_agencies
                    WHERE is_active=1 AND COALESCE(minimum_amount,0) <= ?
                    ORDER BY commission_rate, agency_id LIMIT 1
                ''', (debt,)).fetchone()
                if agency:
                    agency_id, status, assigned = agency[0], 'assigned', assigned + 1
            conn.execute('''
                INSERT INTO collection_cases
                    (student_id, agency_id, total_debt, case_status, assigned_date,
                     notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (student_id, agency_id, debt, status,
                  now if agency_id else None,
                  f"Created by workflow {workflow_id}", now, now))
            created += 1
        conn.execute(
            "UPDATE collection_workflows SET last_run_at=?, updated_at=? WHERE workflow_id=?",
            (now, now, workflow_id),
        )
    # Email only after releasing the finance write lock.
    if notifications:
        from education_system.systems.university.infrastructure.email.email_service import send_email
        for email, case_id in notifications:
            send_email(recipient_email=email, subject="Outstanding account reminder",
                       body=f"Please contact Student Finance regarding collection case {case_id}.")
    return {"created": created, "assigned": assigned,
            "reminded": reminded, "escalated": escalated}
