"""Workflow extracted from the legacy event-management module."""
from __future__ import annotations
from datetime import timedelta
from education_system.systems.university.domains.student_life.domain.student_life.student_union.events.application.ports import (
    AcademicCalendarManager, DatabaseManager, HAS_AUTH, UserAuth, datetime,
    get_connection, get_events_support_phone, os, random,
    send_confirmation_email, set_auth_instance, sqlite3, string,
)
from education_system.systems.university.domains.student_life.interfaces.cli.student_union_events.context import auth
from education_system.systems.university.domains.student_life.interfaces.cli.student_union_events.context import auth
from education_system.systems.university.domains.student_life.domain.student_life.student_union.identity import (
    current_student_id as _current_student_id,
)
from education_system.systems.university.domains.student_life.domain.student_life.student_union.recurring_series import (
    create_series, generate_occurrences,
)

def _create_recurring_event_simple():
    """Create a recurring event for a club."""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to create recurring events.")
        return

    if not auth.check_permission('manage_events'):
        print("You don't have permission to create recurring events.")
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

        if len(clubs) == 1:
            club_id = clubs[0][0]
        else:
            print("\nYour clubs:")
            for i, club in enumerate(clubs):
                print(f"{i+1}. {club[1]}")
            choice = input("Select a club (enter number): ").strip()
            if not choice.isdigit() or int(choice) < 1 or int(choice) > len(clubs):
                print("Invalid selection.")
                conn.close()
                return
            club_id = clubs[int(choice)-1][0]

        event_name = input("Event name: ").strip()
        description = input("Description: ").strip()
        start_time = input("Start time (HH:MM): ").strip()
        location = input("Location: ").strip()
        max_attendees = input("Max attendees: ").strip()
        cost = input("Cost: ").strip()
        category = input("Category: ").strip()
        start_date = input("Start date (YYYY-MM-DD): ").strip()
        end_date = input("End date (YYYY-MM-DD): ").strip()
        recurrence_type = input("Recurrence (weekly/monthly): ").strip().lower()
        recurrence_value = input("Day (e.g., Monday or day of month): ").strip()

        if recurrence_type not in ('weekly', 'monthly'):
            print("Recurrence must be weekly or monthly.")
            conn.close()
            return

        series_id, _parent = create_series(
            cursor, name=event_name, frequency=recurrence_type,
            start_date=start_date, end_date=end_date,
            start_time=start_time, description=description, location=location,
            organizer_id=club_id, category=category,
            max_capacity=int(max_attendees) if max_attendees.isdigit() else None,
            event_fee=float(cost) if cost else 0,
            days_of_week=recurrence_value if recurrence_type == 'weekly' else "",
            day_of_month=(int(recurrence_value) if recurrence_type == 'monthly'
                          and recurrence_value.isdigit() else None),
            created_by=student_id)
        generated = generate_occurrences(cursor, series_id)
        conn.commit()
        print(f"Recurring event created with {generated} individual events.")
        conn.close()
    except ValueError as e:
        print(f"Invalid value: {e}")
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def create_recurring_event():
    """Create a recurring event series"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to create recurring events.")
        return

    if not (auth.check_permission('create_club_events') or auth.check_permission('manage_all_events')):
        print("You don't have permission to create events.")
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


        # Get clubs user can create events for
        cursor.execute('''
        SELECT c.club_id, c.club_name
        FROM student_clubs c
        WHERE (c.president_id = ? OR c.treasurer_id = ? OR c.secretary_id = ?)
        AND c.status = 'active'
        ORDER BY c.club_name
        ''', (student_id, student_id, student_id))

        clubs = cursor.fetchall()

        if not clubs:
            print("You are not an officer of any club.")
            conn.close()
            return

        print("\nYour clubs:")
        for i, club in enumerate(clubs):
            print(f"{i+1}. {club[1]}")

        choice = input("Select a club to create recurring event (enter number): ").strip()
        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(clubs):
            print("Invalid selection.")
            conn.close()
            return

        club_id = clubs[int(choice)-1][0]

        print("\nCreate Recurring Event Series")
        print("============================")

        event_name = input("Event name: ").strip()
        if not event_name:
            print("Event name cannot be empty.")
            conn.close()
            return

        description = input("Description: ").strip()
        location = input("Location: ").strip()
        category = input("Category: ").strip()
        start_time = input("Start time (HH:MM): ").strip()
        end_time = input("End time (HH:MM): ").strip()

        try:
            max_attendees = int(input("Maximum attendees (0 for unlimited): ").strip())
        except ValueError:
            max_attendees = 0

        # Recurrence settings
        print("\nRecurrence Settings:")
        print("1. Weekly")
        print("2. Bi-weekly (every 2 weeks)")
        print("3. Monthly")
        print("4. Custom interval")

        recurrence_choice = input("Select recurrence type: ").strip()

        if recurrence_choice == '1':
            recurrence_type = 'weekly'
            recurrence_interval = 1
        elif recurrence_choice == '2':
            recurrence_type = 'weekly'
            recurrence_interval = 2
        elif recurrence_choice == '3':
            recurrence_type = 'monthly'
            recurrence_interval = 1
        elif recurrence_choice == '4':
            recurrence_type = input("Recurrence type (daily/weekly/monthly): ").strip().lower()
            try:
                recurrence_interval = int(input(f"Interval (every X {recurrence_type}): ").strip())
            except ValueError:
                print("Invalid interval.")
                conn.close()
                return
        else:
            print("Invalid choice.")
            conn.close()
            return

        # Date settings
        start_date = input("First event date (YYYY-MM-DD): ").strip()
        end_date = input("Series end date (YYYY-MM-DD): ").strip()

        try:
            max_occurrences = int(input("Maximum number of occurrences (0 for unlimited): ").strip())
        except ValueError:
            max_occurrences = 0

        # Days of week for weekly events
        days_of_week = ""
        if recurrence_type == 'weekly':
            print("\nDays of week (for weekly events):")
            print("Enter days as numbers: 1=Monday, 2=Tuesday, ..., 7=Sunday")
            days_input = input("Days (comma-separated, e.g., 1,3,5): ").strip()
            days_of_week = days_input

        # Create the parent event and the recurring event record
        _series_id, parent_event_id = create_series(
            cursor, name=event_name, frequency=recurrence_type, interval=recurrence_interval,
            start_date=start_date, end_date=end_date, start_time=start_time, end_time=end_time,
            description=description, location=location, organizer_id=club_id, category=category,
            max_capacity=max_attendees, days_of_week=days_of_week,
            max_occurrences=max_occurrences, created_by=student_id)

        # Generate individual event occurrences
        current_date = datetime.strptime(start_date, '%Y-%m-%d')
        end_datetime = datetime.strptime(end_date, '%Y-%m-%d')
        occurrence_count = 0

        while current_date <= end_datetime and (max_occurrences == 0 or occurrence_count < max_occurrences):
            occurrence_count += 1

            # Create individual event
            cursor.execute('''
            INSERT INTO unified_events (
                title, description, event_date, start_time, end_time, location, organizer_id, event_category, max_capacity, status, source_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'union')
            ''', (
                f"{event_name} #{occurrence_count}", description,
                current_date.strftime('%Y-%m-%d'), start_time, end_time,
                location, club_id, category, max_attendees, 'upcoming'
            ))

            # Calculate next occurrence
            if recurrence_type == 'daily':
                current_date += timedelta(days=recurrence_interval)
            elif recurrence_type == 'weekly':
                current_date += timedelta(weeks=recurrence_interval)
            elif recurrence_type == 'monthly':
                # Add months (approximate)
                new_month = current_date.month + recurrence_interval
                new_year = current_date.year + (new_month - 1) // 12
                new_month = ((new_month - 1) % 12) + 1

                try:
                    current_date = current_date.replace(year=new_year, month=new_month)
                except ValueError:
                    # Handle month end edge cases
                    import calendar
                    max_day = calendar.monthrange(new_year, new_month)[1]
                    current_date = current_date.replace(year=new_year, month=new_month, day=min(current_date.day, max_day))

        # Update occurrence count
        cursor.execute('''
        UPDATE recurring_events
        SET current_occurrences = ?
        WHERE parent_event_id = ?
        ''', (occurrence_count, parent_event_id))

        conn.commit()
        print("Recurring event series created successfully!")
        print(f"Generated {occurrence_count} individual events.")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def manage_recurring_events():
    """Manage existing recurring event series"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to manage recurring events.")
        return

    if not (auth.check_permission('create_club_events') or auth.check_permission('manage_all_events')):
        print("You don't have permission to manage events.")
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


        # Get recurring events user can manage
        if auth.check_permission('manage_all_events'):
            cursor.execute('''
            SELECT r.id, e.event_name, c.club_name, r.recurrence_type,
                   r.current_occurrences, r.max_occurrences, r.status
            FROM recurring_events r
            JOIN (SELECT event_id, title AS event_name, description, organizer_id, event_date, start_time, end_time, location, event_category AS category, max_capacity AS max_attendees, (SELECT COUNT(*) FROM unified_event_registrations ur WHERE ur.event_id = ue.event_id) AS current_attendees, status, created_at, start_time AS event_time FROM unified_events ue WHERE ue.source_type = 'union') e ON r.parent_event_id = e.event_id
            JOIN student_clubs c ON e.organizer_id = c.club_id
            WHERE r.status = 'active'
            ORDER BY e.event_name
            ''')
        else:
            cursor.execute('''
            SELECT r.id, e.event_name, c.club_name, r.recurrence_type,
                   r.current_occurrences, r.max_occurrences, r.status
            FROM recurring_events r
            JOIN (SELECT event_id, title AS event_name, description, organizer_id, event_date, start_time, end_time, location, event_category AS category, max_capacity AS max_attendees, (SELECT COUNT(*) FROM unified_event_registrations ur WHERE ur.event_id = ue.event_id) AS current_attendees, status, created_at, start_time AS event_time FROM unified_events ue WHERE ue.source_type = 'union') e ON r.parent_event_id = e.event_id
            JOIN student_clubs c ON e.organizer_id = c.club_id
            WHERE (c.president_id = ? OR c.treasurer_id = ? OR c.secretary_id = ?)
            AND r.status = 'active'
            ORDER BY e.event_name
            ''', (student_id, student_id, student_id))

        recurring_events = cursor.fetchall()

        if not recurring_events:
            print("No active recurring event series found.")
            conn.close()
            return

        print("\nActive Recurring Event Series:")
        for i, event in enumerate(recurring_events):
            max_occ = f"/{event[5]}" if event[5] > 0 else ""
            print(f"{i+1}. {event[1]} ({event[2]}) - {event[3]} - {event[4]}{max_occ} occurrences")

        choice = input("Select a series to manage (enter number): ").strip()
        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(recurring_events):
            print("Invalid selection.")
            conn.close()
            return

        selected = recurring_events[int(choice)-1]
        recurring_id = selected[0]
        event_name = selected[1]

        while True:
            print(f"\nManage Recurring Series - {event_name}")
            print("1. View all occurrences")
            print("2. Add more occurrences")
            print("3. Cancel future occurrences")
            print("4. Modify series settings")
            print("5. End series")
            print("6. Return to previous menu")

            action = input("Choose an action: ").strip()

            if action == '1':
                # View all occurrences
                cursor.execute('''
                SELECT parent_event_id FROM recurring_events WHERE id = ?
                ''', (recurring_id,))
                parent_id = cursor.fetchone()[0]

                cursor.execute('''
                SELECT event_id, event_name, event_date, start_time, status, current_attendees
                FROM (SELECT event_id, title AS event_name, description, organizer_id, event_date, start_time, end_time, location, event_category AS category, max_capacity AS max_attendees, (SELECT COUNT(*) FROM unified_event_registrations ur WHERE ur.event_id = ue.event_id) AS current_attendees, status, created_at, start_time AS event_time FROM unified_events ue WHERE ue.source_type = 'union')
                WHERE organizer_id = (
                    SELECT organizer_id FROM (SELECT event_id, title AS event_name, description, organizer_id, event_date, start_time, end_time, location, event_category AS category, max_capacity AS max_attendees, (SELECT COUNT(*) FROM unified_event_registrations ur WHERE ur.event_id = ue.event_id) AS current_attendees, status, created_at, start_time AS event_time FROM unified_events ue WHERE ue.source_type = 'union') WHERE event_id = ?
                ) AND event_name LIKE ?
                ORDER BY event_date
                ''', (parent_id, f"{event_name.split(' (Series)')[0]}%"))

                occurrences = cursor.fetchall()

                print(f"\nAll Occurrences of {event_name}:")
                print(f"{'ID':<6} {'Name':<30} {'Date':<12} {'Time':<8} {'Status':<12} {'Attendees':<10}")
                print("-" * 80)

                for occ in occurrences:
                    print(f"{occ[0]:<6} {occ[1][:30]:<30} {occ[2]:<12} {occ[3]:<8} {occ[4]:<12} {occ[5]:<10}")

            elif action == '2':
                # Add more occurrences
                try:
                    additional_count = int(input("Number of additional occurrences to create: ").strip())
                    if additional_count <= 0:
                        print("Must be a positive number.")
                        continue
                except ValueError:
                    print("Invalid number format.")
                    continue

                # Get last occurrence date
                cursor.execute('''
                SELECT r.parent_event_id, r.recurrence_type, r.recurrence_interval,
                       r.current_occurrences
                FROM recurring_events r
                WHERE r.id = ?
                ''', (recurring_id,))

                series_info = cursor.fetchone()
                parent_id = series_info[0]
                recurrence_type = series_info[1]
                recurrence_interval = series_info[2]
                current_count = series_info[3]

                # Get the template event details
                cursor.execute('''
                SELECT event_name, description, start_time, end_time, location,
                       organizer_id, category, max_attendees
                FROM (SELECT event_id, title AS event_name, description, organizer_id, event_date, start_time, end_time, location, event_category AS category, max_capacity AS max_attendees, (SELECT COUNT(*) FROM unified_event_registrations ur WHERE ur.event_id = ue.event_id) AS current_attendees, status, created_at, start_time AS event_time FROM unified_events ue WHERE ue.source_type = 'union')
                WHERE event_id = ?
                ''', (parent_id,))

                template = cursor.fetchone()

                # Find last occurrence date
                cursor.execute('''
                SELECT MAX(event_date) FROM (SELECT event_id, title AS event_name, description, organizer_id, event_date, start_time, end_time, location, event_category AS category, max_capacity AS max_attendees, (SELECT COUNT(*) FROM unified_event_registrations ur WHERE ur.event_id = ue.event_id) AS current_attendees, status, created_at, start_time AS event_time FROM unified_events ue WHERE ue.source_type = 'union')
                WHERE organizer_id = ? AND event_name LIKE ?
                ''', (template[5], f"{template[0].split(' (Series)')[0]}%"))

                last_date_str = cursor.fetchone()[0]
                if last_date_str:
                    last_date = datetime.strptime(last_date_str, '%Y-%m-%d')
                else:
                    print("Could not find last occurrence date.")
                    continue

                # Generate additional occurrences
                base_name = template[0].split(' (Series)')[0]

                for i in range(additional_count):
                    # Calculate next date
                    if recurrence_type == 'daily':
                        last_date += timedelta(days=recurrence_interval)
                    elif recurrence_type == 'weekly':
                        last_date += timedelta(weeks=recurrence_interval)
                    elif recurrence_type == 'monthly':
                        new_month = last_date.month + recurrence_interval
                        new_year = last_date.year + (new_month - 1) // 12
                        new_month = ((new_month - 1) % 12) + 1

                        try:
                            last_date = last_date.replace(year=new_year, month=new_month)
                        except ValueError:
                            import calendar
                            max_day = calendar.monthrange(new_year, new_month)[1]
                            last_date = last_date.replace(year=new_year, month=new_month, day=min(last_date.day, max_day))

                    current_count += 1

                    # Create the occurrence
                    cursor.execute('''
                    INSERT INTO unified_events (
                title, description, event_date, start_time, end_time, location, organizer_id, event_category, max_capacity, status, source_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'union')
                    ''', (
                        f"{base_name} #{current_count}", template[1],
                        last_date.strftime('%Y-%m-%d'), template[2], template[3],
                        template[4], template[5], template[6], template[7], 'upcoming'
                    ))

                # Update occurrence count
                cursor.execute('''
                UPDATE recurring_events
                SET current_occurrences = ?
                WHERE id = ?
                ''', (current_count, recurring_id))

                conn.commit()
                print(f"Added {additional_count} additional occurrences.")

            elif action == '3':
                # Cancel future occurrences
                cursor.execute('''
                SELECT parent_event_id FROM recurring_events WHERE id = ?
                ''', (recurring_id,))
                parent_id = cursor.fetchone()[0]

                cursor.execute('''
                SELECT organizer_id, event_name FROM (SELECT event_id, title AS event_name, description, organizer_id, event_date, start_time, end_time, location, event_category AS category, max_capacity AS max_attendees, (SELECT COUNT(*) FROM unified_event_registrations ur WHERE ur.event_id = ue.event_id) AS current_attendees, status, created_at, start_time AS event_time FROM unified_events ue WHERE ue.source_type = 'union') WHERE event_id = ?
                ''', (parent_id,))

                org_info = cursor.fetchone()
                base_name = org_info[1].split(' (Series)')[0]

                current_date = datetime.now().strftime('%Y-%m-%d')

                cursor.execute('''
                UPDATE unified_events
                SET status = 'cancelled'
                WHERE source_type = 'union'
                  AND organizer_id = ? AND title LIKE ? AND event_date > ?
                  AND status = 'upcoming'
                ''', (org_info[0], f"{base_name}%", current_date))

                cancelled_count = cursor.rowcount
                conn.commit()

                print(f"Cancelled {cancelled_count} future occurrences.")

            elif action == '4':
                # Modify series settings
                print("Series modification options:")
                print("1. Change end date")
                print("2. Change max occurrences")
                print("3. Pause/Resume series")

                mod_choice = input("Choose modification: ").strip()

                if mod_choice == '1':
                    new_end_date = input("New end date (YYYY-MM-DD): ").strip()
                    cursor.execute('''
                    UPDATE recurring_events
                    SET end_date = ?
                    WHERE id = ?
                    ''', (new_end_date, recurring_id))

                    print("End date updated.")

                elif mod_choice == '2':
                    try:
                        new_max = int(input("New maximum occurrences (0 for unlimited): ").strip())
                        cursor.execute('''
                        UPDATE recurring_events
                        SET max_occurrences = ?
                        WHERE id = ?
                        ''', (new_max, recurring_id))

                        print("Maximum occurrences updated.")
                    except ValueError:
                        print("Invalid number format.")

                elif mod_choice == '3':
                    current_status = selected[6]
                    new_status = 'paused' if current_status == 'active' else 'active'

                    cursor.execute('''
                    UPDATE recurring_events
                    SET status = ?
                    WHERE id = ?
                    ''', (new_status, recurring_id))

                    print(f"Series status changed to {new_status}.")

                conn.commit()

            elif action == '5':
                # End series
                confirm = input("Are you sure you want to end this series? (y/n): ").strip().lower()
                if confirm == 'y':
                    cursor.execute('''
                    UPDATE recurring_events
                    SET status = 'ended'
                    WHERE id = ?
                    ''', (recurring_id,))

                    conn.commit()
                    print("Series ended.")
                    break

            elif action == '6':
                break

            else:
                print("Invalid choice.")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
