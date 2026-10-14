"""Workflow extracted from the legacy event-management module."""
from __future__ import annotations
from education_system.systems.university.domains.pastoral.domain.student_life.student_union.events.application.ports import (
    AcademicCalendarManager, DatabaseManager, HAS_AUTH, UserAuth, datetime,
    get_connection, get_events_support_phone, os, random,
    send_confirmation_email, set_auth_instance, sqlite3, string,
)
from education_system.systems.university.domains.pastoral.interfaces.cli.student_union_events.context import auth
from education_system.systems.university.domains.pastoral.domain.student_life.student_union.events.reporting.financial_report import generate_event_financial_report
from education_system.systems.university.domains.pastoral.interfaces.cli.student_union_events.context import auth
from education_system.systems.university.domains.pastoral.interfaces.cli.student_union_events.ticketing import manage_event_tickets
from education_system.systems.university.domains.pastoral.domain.student_life.student_union.identity import (
    current_student_id as _current_student_id,
)

def _track_event_finances_simple():
    """Track expenses and income for club events."""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to manage event finances.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        student_id = _current_student_id(cursor, auth)

        if not student_id:
            print("No student record is associated with your account.")
            conn.close()
            return


        cursor.execute('''
        SELECT c.club_id, c.club_name
        FROM student_clubs c
        JOIN club_members m ON c.club_id = m.club_id
        WHERE m.student_id = ?
        ''', (student_id,))
        clubs = cursor.fetchall()

        if not clubs:
            print("You are not an officer of any club.")
            conn.close()
            return

        cursor.execute('''
        SELECT e.event_id, e.event_name, e.event_date
        FROM (SELECT event_id, title AS event_name, description, organizer_id, event_date, start_time, end_time, location, event_category AS category, max_capacity AS max_attendees, (SELECT COUNT(*) FROM unified_event_registrations ur WHERE ur.event_id = ue.event_id) AS current_attendees, status, created_at, start_time AS event_time FROM unified_events ue WHERE ue.source_type = 'union') e
        WHERE e.organizer_id IN (
            SELECT club_id FROM club_members WHERE student_id = ?
        )
        ORDER BY e.event_date DESC
        ''', (student_id,))
        events = cursor.fetchall()

        if not events:
            print("No events found for your clubs.")
            conn.close()
            return

        print("\nEvent Financial Tracking")
        print("1. Add event expense")
        print("2. Record event income")
        print("3. View financial summary")
        print("4. Return")

        choice = input("Choose an option: ").strip()
        if choice not in {'1', '2', '3'}:
            conn.close()
            return

        event_id = input("Enter event ID: ").strip()
        if not event_id.isdigit():
            print("Invalid event ID.")
            conn.close()
            return

        if choice in {'1', '2'}:
            amount = input("Amount: ").strip()
            description = input("Description: ").strip()
            entry_type = 'expense' if choice == '1' else 'income'
            cursor.execute('''
            INSERT INTO event_finances (event_id, amount, entry_type, description, entry_date)
            VALUES (?, ?, ?, ?, ?)
            ''', (event_id, float(amount), entry_type, description, datetime.now().strftime('%Y-%m-%d')))
            conn.commit()
            print("Financial entry recorded.")
        else:
            cursor.execute('''
            SELECT SUM(amount) FROM event_finances
            WHERE event_id = ? AND entry_type = 'income'
            ''', (event_id,))
            total_income = cursor.fetchone()[0] or 0

            cursor.execute('''
            SELECT SUM(amount) FROM event_finances
            WHERE event_id = ? AND entry_type = 'expense'
            ''', (event_id,))
            total_expense = cursor.fetchone()[0] or 0

            cursor.execute('''
            SELECT amount, entry_type, description, entry_date
            FROM event_finances
            WHERE event_id = ? AND entry_type = 'expense'
            ORDER BY entry_date DESC
            ''', (event_id,))
            expenses = cursor.fetchall()

            cursor.execute('''
            SELECT amount, entry_type, description, entry_date
            FROM event_finances
            WHERE event_id = ? AND entry_type = 'income'
            ORDER BY entry_date DESC
            ''', (event_id,))
            income = cursor.fetchall()

            print(f"\nTotal income: {total_income}")
            print(f"Total expenses: {total_expense}")
            print(f"Net: {total_income - total_expense}")
            if expenses or income:
                print("Details available.")

        conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def track_event_finances():
    """Track financial aspects of events"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to track event finances.")
        return

    if not (auth.check_permission('create_club_events') or auth.check_permission('manage_all_events')):
        print("You don't have permission to manage event finances.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get student ID
        student_id = _current_student_id(cursor, auth)

        if not student_id:
            print("No student record is associated with your account.")
            conn.close()
            return


        # Get events user can manage
        if auth.check_permission('manage_all_events'):
            cursor.execute('''
            SELECT e.event_id, e.event_name, c.club_name, e.event_date
            FROM (SELECT event_id, title AS event_name, description, organizer_id, event_date, start_time, end_time, location, event_category AS category, max_capacity AS max_attendees, (SELECT COUNT(*) FROM unified_event_registrations ur WHERE ur.event_id = ue.event_id) AS current_attendees, status, created_at, start_time AS event_time FROM unified_events ue WHERE ue.source_type = 'union') e
            JOIN student_clubs c ON e.organizer_id = c.club_id
            ORDER BY e.event_date DESC
            ''')
        else:
            cursor.execute('''
            SELECT e.event_id, e.event_name, c.club_name, e.event_date
            FROM (SELECT event_id, title AS event_name, description, organizer_id, event_date, start_time, end_time, location, event_category AS category, max_capacity AS max_attendees, (SELECT COUNT(*) FROM unified_event_registrations ur WHERE ur.event_id = ue.event_id) AS current_attendees, status, created_at, start_time AS event_time FROM unified_events ue WHERE ue.source_type = 'union') e
            JOIN student_clubs c ON e.organizer_id = c.club_id
            WHERE (c.president_id = ? OR c.treasurer_id = ? OR c.secretary_id = ?)
            ORDER BY e.event_date DESC
            ''', (student_id, student_id, student_id))

        events = cursor.fetchall()

        if not events:
            print("No events available for financial tracking.")
            conn.close()
            return

        print("\nYour events:")
        for i, event in enumerate(events[:10]):  # Show last 10 events
            print(f"{i+1}. {event[1]} ({event[2]}) - {event[3]}")

        choice = input("Select an event to manage finances (enter number): ").strip()
        if not choice.isdigit() or int(choice) < 1 or int(choice) > min(len(events), 10):
            print("Invalid selection.")
            conn.close()
            return

        selected_event = events[int(choice)-1]
        event_id = selected_event[0]
        event_name = selected_event[1]

        while True:
            print(f"\nEvent Financial Management - {event_name}")
            print("1. Add expense")
            print("2. Add revenue")
            print("3. View financial summary")
            print("4. Manage ticket sales")
            print("5. Generate profit/loss report")
            print("6. Return to previous menu")

            action = input("Choose an action: ").strip()

            if action == '1':
                # Add expense
                expense_type = input("Expense type (Venue, Catering, Materials, etc.): ").strip()
                if not expense_type:
                    print("Expense type cannot be empty.")
                    continue

                try:
                    amount = float(input("Amount (£): ").strip())
                    if amount <= 0:
                        print("Amount must be positive.")
                        continue
                except ValueError:
                    print("Invalid amount format.")
                    continue

                description = input("Description: ").strip()
                receipt_path = input("Receipt file path (optional): ").strip()

                date_recorded = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                INSERT INTO event_finances (
                    event_id, expense_type, amount, description, date_recorded, receipt_path
                ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (event_id, expense_type, -amount, description, date_recorded, receipt_path))

                conn.commit()
                print(f"Expense recorded: £{amount:.2f} for {expense_type}")

            elif action == '2':
                # Add revenue
                revenue_type = input("Revenue type (Ticket Sales, Sponsorship, Donations, etc.): ").strip()
                if not revenue_type:
                    print("Revenue type cannot be empty.")
                    continue

                try:
                    amount = float(input("Amount (£): ").strip())
                    if amount <= 0:
                        print("Amount must be positive.")
                        continue
                except ValueError:
                    print("Invalid amount format.")
                    continue

                description = input("Description: ").strip()
                date_recorded = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                INSERT INTO event_finances (
                    event_id, revenue_type, amount, description, date_recorded
                ) VALUES (?, ?, ?, ?, ?)
                ''', (event_id, revenue_type, amount, description, date_recorded))

                conn.commit()
                print(f"Revenue recorded: £{amount:.2f} from {revenue_type}")

            elif action == '3':
                # View financial summary
                cursor.execute('''
                SELECT
                    COALESCE(expense_type, revenue_type) as transaction_type,
                    amount,
                    description,
                    date_recorded
                FROM event_finances
                WHERE event_id = ?
                ORDER BY date_recorded DESC
                ''', (event_id,))

                transactions = cursor.fetchall()

                if not transactions:
                    print("No financial records found for this event.")
                else:
                    print(f"\nFinancial Summary - {event_name}")
                    print("=" * 50)

                    total_revenue = 0
                    total_expenses = 0

                    print(f"{'Type':<20} {'Amount':<12} {'Description':<30}")
                    print("-" * 65)

                    for transaction in transactions:
                        amount = transaction[1]
                        if amount > 0:
                            total_revenue += amount
                            print(f"{transaction[0]:<20} +£{amount:<11.2f} {transaction[2]:<30}")
                        else:
                            total_expenses += abs(amount)
                            print(f"{transaction[0]:<20} -£{abs(amount):<11.2f} {transaction[2]:<30}")

                    print("-" * 65)
                    profit_loss = total_revenue - total_expenses
                    print(f"{'Total Revenue:':<20} £{total_revenue:.2f}")
                    print(f"{'Total Expenses:':<20} £{total_expenses:.2f}")
                    print(f"{'Profit/Loss:':<20} £{profit_loss:.2f}")

            elif action == '4':
                # Manage ticket sales
                manage_event_tickets(event_id, event_name, cursor, conn)

            elif action == '5':
                # Generate profit/loss report
                generate_event_financial_report(event_id, event_name, cursor)

            elif action == '6':
                break

            else:
                print("Invalid choice.")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
