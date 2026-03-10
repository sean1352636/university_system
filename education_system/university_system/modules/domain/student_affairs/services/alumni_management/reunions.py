from datetime import datetime
from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.university_system.infrastructure.email.email_service import send_email
from education_system.university_system.infrastructure.email.template_utils import load_template, render_template
from .core import get_db_connection, safe_execute, auth


def manage_existing_reunion():
    """Manage an existing reunion"""
    global auth
    if not auth or not auth.current_user:
        print("You must be logged in to manage reunions.")
        return

    try:
        reunion_id = input("Enter reunion ID to manage: ")
        if not reunion_id:
            print("Reunion ID is required.")
            return

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM alumni_reunions WHERE reunion_id = ?', (reunion_id,))
        reunion = cursor.fetchone()

        if not reunion:
            print(f"Reunion {reunion_id} not found.")
            conn.close()
            return

        print("\n--- Manage Reunion ---")
        print("1. Update Details")
        print("2. View Attendees")
        print("3. Cancel Reunion")
        choice = input("Enter your choice (1-3): ")

        if choice == '1':
            new_location = input("Enter new location (or press Enter to skip): ")
            new_date = input("Enter new date (YYYY-MM-DD, or press Enter to skip): ")

            if new_location:
                cursor.execute('UPDATE alumni_reunions SET location = ? WHERE reunion_id = ?', (new_location, reunion_id))
            if new_date:
                cursor.execute('UPDATE alumni_reunions SET reunion_date = ? WHERE reunion_id = ?', (new_date, reunion_id))

            conn.commit()
            print("Reunion updated successfully!")

        elif choice == '2':
            cursor.execute('''
                SELECT user_id, rsvp_status
                FROM alumni_reunion_attendees
                WHERE reunion_id = ?
            ''', (reunion_id,))
            attendees = cursor.fetchall()

            print("\nAttendees:")
            for attendee in attendees:
                print(f"User ID: {attendee[0]}, RSVP: {attendee[1]}")

        elif choice == '3':
            confirm = input("Are you sure you want to cancel this reunion? (yes/no): ")
            if confirm.lower() == 'yes':
                cursor.execute('UPDATE alumni_reunions SET status = "cancelled" WHERE reunion_id = ?', (reunion_id,))
                conn.commit()
                print("Reunion cancelled.")

        conn.close()
    except Exception as e:
        print(f"Error managing reunion: {e}")

def view_class_reunions():
    """View class reunions"""
    global auth
    if not auth or not auth.current_user:
        print("You must be logged in to view reunions.")
        return

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT reunion_id, class_year, reunion_date, location, status
            FROM alumni_reunions
            WHERE status = 'active' OR status = 'upcoming'
            ORDER BY reunion_date ASC
        ''')

        reunions = cursor.fetchall()
        conn.close()

        if not reunions:
            print("\nNo upcoming reunions scheduled.")
            return

        print("\n--- Class Reunions ---")
        print(f"{'Reunion ID':<15} {'Class Year':<12} {'Date':<20} {'Location':<25} {'Status':<12}")
        print("-" * 90)
        for reunion in reunions:
            print(f"{reunion[0]:<15} {reunion[1]:<12} {reunion[2]:<20} {reunion[3]:<25} {reunion[4]:<12}")
    except Exception as e:
        print(f"Error viewing reunions: {e}")

def manage_class_reunions():
    """Manage class reunion planning"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to manage class reunions.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    print("\nClass Reunion Management")
    print("========================")
    print("1. Create New Reunion")
    print("2. View Upcoming Reunions")
    print("3. Manage Existing Reunion")

    choice = input("Enter your choice: ")

    if choice == '1':
        create_class_reunion(cursor)
    elif choice == '2':
        view_class_reunions(cursor)
    elif choice == '3':
        manage_existing_reunion(cursor)
    else:
        print("Invalid choice.")

    conn.close()

def create_class_reunion(cursor):
    """Create a new class reunion"""
    global auth

    if not (auth.check_permission('manage_social_features') or auth.check_permission('manage_events_advanced')):
        print("You don't have permission to create reunions.")
        return

    print("\nCreate Class Reunion")
    print("====================")

    # Get graduation year
    while True:
        try:
            graduation_year = int(input("Graduation Year: "))
            current_year = datetime.now().year
            if graduation_year > current_year:
                print("Error: Graduation year cannot be in the future.")
                continue
            elif graduation_year < 1900:
                print("Error: Please enter a valid graduation year.")
                continue
            break
        except ValueError:
            print("Error: Please enter a valid year.")

    # Check how many alumni from this year
    cursor.execute('SELECT COUNT(*) FROM alumni WHERE graduation_year = ?', (graduation_year,))
    alumni_count = cursor.fetchone()[0]
    print(f"Found {alumni_count} alumni from the Class of {graduation_year}")

    if alumni_count == 0:
        print("No alumni found for this graduation year.")
        return

    # Reunion details
    while True:
        reunion_date_str = input("Reunion Date and Time (YYYY-MM-DD HH:MM): ")
        try:
            reunion_date = datetime.strptime(reunion_date_str, "%Y-%m-%d %H:%M")
            if reunion_date < datetime.now():
                print("Error: Reunion date cannot be in the past.")
                continue
            reunion_date_str = reunion_date.strftime("%Y-%m-%d %H:%M:%S")
            break
        except ValueError:
            print("Error: Invalid date format. Please use YYYY-MM-DD HH:MM.")

    location = input("Reunion Location: ")
    while not location:
        print("Error: Location is required.")
        location = input("Reunion Location: ")

    description = input("Reunion Description: ")

    # Registration fee
    while True:
        try:
            registration_fee = float(input("Registration Fee ($, 0 for free): "))
            if registration_fee < 0:
                print("Error: Fee cannot be negative.")
                continue
            break
        except ValueError:
            print("Error: Please enter a valid amount.")

    # Max attendees
    while True:
        try:
            max_attendees = int(input("Maximum Attendees (0 for unlimited): "))
            if max_attendees < 0:
                print("Error: Cannot be negative.")
                continue
            break
        except ValueError:
            print("Error: Please enter a valid number.")

    # Get organizer ID
    organizer_id = None
    cursor.execute('SELECT username FROM users WHERE id = ?', (auth.current_user['id'],))
    result = cursor.fetchone()
    if result and result[0].startswith('A'):
        organizer_id = result[0]
    else:
        organizer_id = input("Enter Alumni ID of the organizer: ")

    # Insert reunion
    cursor.execute('''
        INSERT INTO class_reunions
        (graduation_year, reunion_date, location, organizer_id, description,
         registration_fee, max_attendees, created_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (graduation_year, reunion_date_str, location, organizer_id, description,
          registration_fee, max_attendees, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

    reunion_id = cursor.lastrowid

    print(f"\nClass reunion created successfully! Reunion ID: {reunion_id}")
    print(f"Class of {graduation_year} Reunion")
    print(f"Date: {reunion_date_str}")
    print(f"Location: {location}")

    # Send invitations
    notify = input("Send invitations to all Class of {graduation_year} alumni? (y/n): ").lower()
    if notify == 'y':
        send_reunion_invitations(graduation_year, reunion_id, cursor)

def send_reunion_invitations(graduation_year, reunion_id, cursor):
    """Send reunion invitations to alumni from specific graduation year"""
    # Get reunion details
    cursor.execute('''
        SELECT reunion_date, location, description
        FROM class_reunions
        WHERE reunion_id = ?
    ''', (reunion_id,))
    reunion_info = cursor.fetchone()
    reunion_date = reunion_info[0] if reunion_info else "TBD"
    reunion_location = reunion_info[1] if reunion_info else "TBD"
    reunion_description = reunion_info[2] if reunion_info and reunion_info[2] else "Join us for a memorable reunion with your classmates!"

    cursor.execute('''
        SELECT alumni_id, email_address, first_name, last_name
        FROM alumni
        WHERE graduation_year = ?
    ''', (graduation_year,))

    alumni_list = cursor.fetchall()

    if alumni_list:
        print(f"Sending reunion invitations to {len(alumni_list)} alumni from Class of {graduation_year}...")

        template = load_template('alumni/alumni_reunion_invitation')
        sent_count = 0
        failed_count = 0

        for alumni in alumni_list:
            alumni_id, email, first_name, last_name = alumni[0], alumni[1], alumni[2], alumni[3] if len(alumni) > 3 else ""
            recipient_name = f"{first_name} {last_name}".strip() if last_name else first_name

            if not email:
                continue

            try:
                if template:
                    template_vars = {
                        'recipient_name': recipient_name,
                        'graduation_year': str(graduation_year),
                        'reunion_date': str(reunion_date),
                        'reunion_location': reunion_location,
                        'reunion_description': reunion_description
                    }

                    subject, body = render_template('alumni_reunion_invitation', template_vars)
                    if subject and body:
                        send_email(email, subject, body)
                        sent_count += 1
                    else:
                        # Fallback to simple email
                        _send_simple_reunion_email(email, recipient_name, graduation_year,
                                                  reunion_date, reunion_location, reunion_description)
                        sent_count += 1
                else:
                    # No template, send simple email
                    _send_simple_reunion_email(email, recipient_name, graduation_year,
                                              reunion_date, reunion_location, reunion_description)
                    sent_count += 1

                print(f"Invitation sent to {email}")
            except Exception as e:
                print(f"Failed to send to {email}: {e}")
                failed_count += 1

        print(f"Reunion invitations sent successfully to {sent_count} alumni!")
        if failed_count > 0:
            print(f"Failed to send to {failed_count} alumni.")
    else:
        print("No alumni found to invite.")


def _send_simple_reunion_email(email, recipient_name, graduation_year, reunion_date,
                               reunion_location, reunion_description):
    """Fallback simple reunion email when template is not available - now uses template system"""
    from education_system.university_system.infrastructure.email.template_utils import render_template

    template_vars = {
        'recipient_name': recipient_name,
        'graduation_year': graduation_year,
        'reunion_date': reunion_date,
        'reunion_location': reunion_location,
        'reunion_description': reunion_description
    }

    subject, body = render_template('alumni_reunion_invitation', template_vars)

    if not subject or not body:
        # Final fallback if template fails
        subject = f"You're Invited: Class of {graduation_year} Reunion!"
        body = f"""Dear {recipient_name},

We are excited to invite you to the Class of {graduation_year} Reunion!

Event Details:
--------------
Date: {reunion_date}
Location: {reunion_location}
Description: {reunion_description}

This is a wonderful opportunity to reconnect with your classmates and relive your university memories.

To RSVP for this event, please log in to the Alumni Portal or reply to this email.

We look forward to seeing you there!

Best regards,
The Alumni Relations Team
University Alumni Network"""

    send_email(email, subject, body)
