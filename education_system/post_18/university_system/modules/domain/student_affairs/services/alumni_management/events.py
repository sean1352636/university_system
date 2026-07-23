from datetime import datetime
from education_system.post_18.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.post_18.university_system.infrastructure.email import send_event_invitation
from education_system.post_18.university_system.infrastructure.email.email_service import send_email
from education_system.post_18.university_system.infrastructure.email.template_utils import load_template, render_template
from education_system.post_18.university_system.modules.domain.student_affairs.services.alumni_management.core import get_db_connection, safe_execute, auth
from education_system.post_18.university_system.modules.domain.student_affairs.services.alumni_management.gamification import award_engagement_points


def view_events():
   """View alumni events"""
   global auth

   if not auth or not auth.current_user:
       print("You must be logged in to view events.")
       return

   if not (auth.check_permission('view_events') or auth.check_permission('manage_events') or
           auth.check_permission('manage_events_advanced')):
       print("You don't have permission to view events.")
       return

   try:
       conn = get_connection()
       cursor = conn.cursor()

       print("\nView Alumni Events")
       print("==================")
       print("1. View Upcoming Events")
       print("2. View Past Events")
       print("3. View All Events")
       print("4. Search Events")
       print("5. My Event Registrations")

       choice = input("Enter your choice: ").strip()

       events_list = []

       if choice == '1':
           # Upcoming events
           try:
               safe_execute(cursor, '''
                   SELECT event_id, title, start_datetime, location, description,
                          registration_required, max_capacity, event_fee, payment_required,
                          event_type, created_by, registration_deadline
                   FROM unified_events
                   WHERE source_type = 'alumni' AND datetime(start_datetime) >= datetime('now')
                   ORDER BY start_datetime ASC
               ''')
               events_list = cursor.fetchall()

           except sqlite3.Error as e:
               print(f"Error retrieving upcoming events: {e}")
               conn.close()
               return

       elif choice == '2':
           # Past events
           try:
               safe_execute(cursor, '''
                   SELECT event_id, title, start_datetime, location, description,
                          registration_required, max_capacity, event_fee, payment_required,
                          event_type, created_by, registration_deadline
                   FROM unified_events
                   WHERE source_type = 'alumni' AND datetime(start_datetime) < datetime('now')
                   ORDER BY start_datetime DESC
                   LIMIT 20
               ''')
               events_list = cursor.fetchall()

           except sqlite3.Error as e:
               print(f"Error retrieving past events: {e}")
               conn.close()
               return

       elif choice == '3':
           # All events
           try:
               safe_execute(cursor, '''
                   SELECT event_id, title, start_datetime, location, description,
                          registration_required, max_capacity, event_fee, payment_required,
                          event_type, created_by, registration_deadline
                   FROM unified_events
                   WHERE source_type = 'alumni'
                   ORDER BY start_datetime DESC
               ''')
               events_list = cursor.fetchall()

           except sqlite3.Error as e:
               print(f"Error retrieving all events: {e}")
               conn.close()
               return

       elif choice == '4':
           # Search events
           search_events(cursor)
           conn.close()
           return

       elif choice == '5':
           # My registrations
           view_my_event_registrations(cursor)
           conn.close()
           return

       else:
           print("Invalid choice.")
           conn.close()
           return

       # Display events
       if not events_list:
           print("No events found.")
       else:
           print(f"\nFound {len(events_list)} events:")
           print("-" * 120)
           print(f"{'ID':<5} {'Event Name':<30} {'Date':<19} {'Location':<20} {'Type':<10} {'Fee':<8} {'Reg Req':<8}")
           print("-" * 120)

           for event in events_list:
               event_id, name, date, location, desc, reg_req, max_att, fee, pay_req, event_type, created_by, reg_deadline = event

               # Format data for display
               name_display = name[:29] if name else "N/A"
               location_display = location[:19] if location else "N/A"
               event_type_display = event_type[:9] if event_type else "N/A"
               fee_display = f"£{fee:.2f}" if fee and fee > 0 else "Free"
               reg_req_display = "Yes" if reg_req else "No"

               # Check if event is in the past
               try:
                   event_datetime = datetime.strptime(date, "%Y-%m-%d %H:%M:%S")
                   if event_datetime < datetime.now():
                       name_display += " (Past)"
               except (ValueError, TypeError):
                   pass

               print(f"{event_id:<5} {name_display:<30} {date:<19} {location_display:<20} "
                     f"{event_type_display:<10} {fee_display:<8} {reg_req_display:<8}")

           print("-" * 120)

           # Option to view event details
           view_details = input("\nWould you like to view details for a specific event? (y/n): ").lower()
           if view_details == 'y':
               try:
                   event_id = int(input("Enter Event ID: "))
                   view_event_details(event_id, cursor)
               except ValueError:
                   print("Please enter a valid Event ID.")
               except Exception as e:
                   print(f"Error viewing event details: {e}")

   except sqlite3.Error as e:
       print(f"Database error: {e}")
   except Exception as e:
       print(f"An unexpected error occurred: {e}")
   finally:
       try:
           conn.close()
       except Exception:
           pass


def search_events(cursor):
   """Search events by various criteria"""
   print("\nSearch Events")
   print("=============")
   print("1. Search by Event Name")
   print("2. Search by Date Range")
   print("3. Search by Location")
   print("4. Search by Event Type")
   print("5. Search Free Events")

   choice = input("Enter your choice: ").strip()

   try:
       if choice == '1':
           # Search by name
           event_name = input("Enter event name (partial match): ").strip()
           if not event_name:
               print("Event name cannot be empty.")
               return

           safe_execute(cursor, '''
               SELECT event_id, title, start_datetime, location, event_fee, event_type
               FROM unified_events
               WHERE source_type = 'alumni' AND title LIKE ?
               ORDER BY start_datetime DESC
           ''', (f'%{event_name}%',))

       elif choice == '2':
           # Search by date range
           start_date = input("Enter start date (YYYY-MM-DD): ").strip()
           end_date = input("Enter end date (YYYY-MM-DD): ").strip()

           try:
               datetime.strptime(start_date, "%Y-%m-%d")
               datetime.strptime(end_date, "%Y-%m-%d")
           except ValueError:
               print("Invalid date format.")
               return

           safe_execute(cursor, '''
               SELECT event_id, title, start_datetime, location, event_fee, event_type
               FROM unified_events
               WHERE source_type = 'alumni' AND date(start_datetime) BETWEEN ? AND ?
               ORDER BY start_datetime ASC
           ''', (start_date, end_date))

       elif choice == '3':
           # Search by location
           location = input("Enter location: ").strip()
           if not location:
               print("Location cannot be empty.")
               return

           safe_execute(cursor, '''
               SELECT event_id, title, start_datetime, location, event_fee, event_type
               FROM unified_events
               WHERE source_type = 'alumni' AND location LIKE ?
               ORDER BY start_datetime DESC
           ''', (f'%{location}%',))

       elif choice == '4':
           # Search by event type
           event_types = ["in-person", "virtual", "hybrid"]
           print("\nEvent Types:")
           for i, etype in enumerate(event_types, 1):
               print(f"{i}. {etype}")

           type_choice = input("Select event type (1-3): ").strip()
           if type_choice in ['1', '2', '3']:
               selected_type = event_types[int(type_choice) - 1]

               safe_execute(cursor, '''
                   SELECT event_id, title, start_datetime, location, event_fee, event_type
                   FROM unified_events
                   WHERE source_type = 'alumni' AND event_type = ?
                   ORDER BY start_datetime DESC
               ''', (selected_type,))
           else:
               print("Invalid choice.")
               return

       elif choice == '5':
           # Search free events
           safe_execute(cursor, '''
               SELECT event_id, title, start_datetime, location, event_fee, event_type
               FROM unified_events
               WHERE source_type = 'alumni' AND (event_fee = 0 OR event_fee IS NULL)
               ORDER BY start_datetime DESC
           ''')

       else:
           print("Invalid choice.")
           return

       results = cursor.fetchall()

       if not results:
           print("No events found matching your criteria.")
       else:
           print(f"\nFound {len(results)} events:")
           print("-" * 90)
           print(f"{'ID':<5} {'Event Name':<30} {'Date':<19} {'Location':<20} {'Fee':<10}")
           print("-" * 90)

           for event in results:
               event_id, name, date, location, fee, event_type = event
               name_display = name[:29] if name else "N/A"
               location_display = location[:19] if location else "N/A"
               fee_display = f"£{fee:.2f}" if fee and fee > 0 else "Free"

               print(f"{event_id:<5} {name_display:<30} {date:<19} {location_display:<20} {fee_display:<10}")

           print("-" * 90)

   except sqlite3.Error as e:
       print(f"Error searching events: {e}")
   except Exception as e:
       print(f"An unexpected error occurred: {e}")


def view_event_details(event_id, cursor):
   """View detailed information for a specific event"""
   try:
       safe_execute(cursor, 'SELECT * FROM unified_events WHERE event_id = ? AND source_type = \'alumni\'', (event_id,))
       event_data = cursor.fetchone()

       if not event_data:
           print(f"Event with ID {event_id} not found.")
           return

       print(f"\n{'='*70}")
       print(f"EVENT DETAILS - ID: {event_data[0]}")
       print(f"{'='*70}")

       print(f"Event Name: {event_data[1]}")
       print(f"Date & Time: {event_data[2]}")
       print(f"Location: {event_data[3]}")
       print(f"Event Type: {event_data[8] or 'in-person'}")

       if event_data[9]:  # virtual_link
           print(f"Virtual Link: {event_data[9]}")

       print("\nDescription:")
       print(event_data[4] or "No description available")

       print("\nRegistration Details:")
       print(f"Registration Required: {'Yes' if event_data[5] else 'No'}")

       if event_data[5]:  # registration_required
           print(f"Registration Deadline: {event_data[12] or 'Event date'}")

           if event_data[6]:  # max_attendees
               print(f"Maximum Attendees: {event_data[6]}")

               # Get current registration count
               safe_execute(cursor, '''
                   SELECT COUNT(*) FROM unified_event_registrations
                   WHERE event_id = ? AND is_waitlisted = 0
               ''', (event_id,))
               current_registrations = cursor.fetchone()[0]

               print(f"Current Registrations: {current_registrations}")
               remaining_spots = event_data[6] - current_registrations
               print(f"Remaining Spots: {max(0, remaining_spots)}")

               if remaining_spots <= 0 and event_data[13]:  # waitlist_enabled
                   print("Waitlist: Available")
           else:
               print("Maximum Attendees: Unlimited")

       print("\nPayment Information:")
       if event_data[7]:  # payment_required
           print(f"Event Fee: £{event_data[6]:.2f}")
           print("Payment Required: Yes")
       else:
           print("Event Fee: Free")
           print("Payment Required: No")

       print("\nEvent Management:")
       print(f"Created By: {event_data[10]}")
       print(f"Created Date: {event_data[11]}")

       if event_data[14]:  # qr_code_path
           print("QR Code: Available for check-in")

       print(f"{'='*70}")

       # Show registration status for current user
       if auth and auth.current_user:
           cursor.execute('SELECT username FROM users WHERE id = ?', (auth.current_user['id'],))
           result = cursor.fetchone()
           if result and result[0].startswith('A'):
               user_alumni_id = result[0]

               safe_execute(cursor, '''
                   SELECT * FROM unified_event_registrations
                   WHERE event_id = ? AND alumni_id = ?
               ''', (event_id, user_alumni_id))

               registration = cursor.fetchone()

               if registration:
                   status = "Waitlisted" if registration[7] else "Registered"
                   payment_status = registration[5] if registration[5] else "N/A"
                   print(f"\nYour Status: {status}")
                   print(f"Registration Date: {registration[3]}")
                   if event_data[7]:  # payment_required
                       print(f"Payment Status: {payment_status}")
               else:
                   print("\nYou are not registered for this event.")

   except sqlite3.Error as e:
       print(f"Error retrieving event details: {e}")
   except Exception as e:
       print(f"An unexpected error occurred: {e}")


def view_my_event_registrations(cursor):
   """View current user's event registrations"""
   global auth

   if not auth or not auth.current_user:
       print("You must be logged in to view your registrations.")
       return

   try:
       # Get current user's alumni ID
       cursor.execute('SELECT username FROM users WHERE id = ?', (auth.current_user['id'],))
       result = cursor.fetchone()
       if not result or not result[0].startswith('A'):
           print("Alumni profile not found for current user.")
           return

       user_alumni_id = result[0]

       # Get registrations
       safe_execute(cursor, '''
           SELECT er.*, ae.title, ae.start_datetime, ae.location, ae.event_fee
           FROM unified_event_registrations er
           JOIN unified_events ae ON er.event_id = ae.event_id
           WHERE er.alumni_id = ? AND ae.source_type = 'alumni'
           ORDER BY ae.start_datetime DESC
       ''', (user_alumni_id,))

       registrations = cursor.fetchall()

       if not registrations:
           print("You are not registered for any events.")
           return

       print(f"\nYour Event Registrations ({len(registrations)} total):")
       print("-" * 100)
       print(f"{'Event Name':<30} {'Date':<19} {'Status':<12} {'Payment':<10} {'Attended':<10}")
       print("-" * 100)

       for reg in registrations:
           event_name = reg[9][:29] if reg[9] else "N/A"
           event_date = reg[10]
           status = "Waitlisted" if reg[7] else "Registered"
           payment_status = reg[5] if reg[5] else "N/A"
           attended = "Yes" if reg[4] else "No"

           # Check if event is in the past
           try:
               event_datetime = datetime.strptime(event_date, "%Y-%m-%d %H:%M:%S")
               if event_datetime < datetime.now():
                   status += " (Past)"
           except (ValueError, TypeError):
               pass

           print(f"{event_name:<30} {event_date:<19} {status:<12} {payment_status:<10} {attended:<10}")

       print("-" * 100)

   except sqlite3.Error as e:
       print(f"Error retrieving your registrations: {e}")
   except Exception as e:
       print(f"An unexpected error occurred: {e}")

def register_for_event():
    """Register for an event"""
    global auth
    if not auth or not auth.current_user:
        print("You must be logged in to register for events.")
        return

    try:
        event_id = input("Enter event ID to register for: ")
        if not event_id:
            print("Event ID is required.")
            return

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if event exists
        cursor.execute('SELECT * FROM unified_events WHERE event_id = ? AND source_type = \'alumni\'', (event_id,))
        if not cursor.fetchone():
            print(f"Event {event_id} not found.")
            conn.close()
            return

        # Register for event
        cursor.execute('''
            INSERT INTO unified_event_registrations (event_id, user_id, registration_date, status)
            VALUES (?, ?, ?, 'registered')
        ''', (event_id, auth.current_user['user_id'], datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

        conn.commit()
        conn.close()
        print(f"Successfully registered for event {event_id}!")
    except sqlite3.IntegrityError:
        print("You are already registered for this event.")
    except Exception as e:
        print(f"Error registering for event: {e}")

def create_enhanced_event():
    """Create an enhanced alumni event with payment and advanced features"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to create events.")
        return

    if not auth.check_permission('manage_events_advanced'):
        print("You don't have permission to create advanced events.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    print("\nCreate Enhanced Alumni Event")
    print("============================")

    # Basic event details
    event_name = input("Event Name: ")
    while not event_name:
        print("Error: Event name is required.")
        event_name = input("Event Name: ")

    # Event date and time
    while True:
        event_date_str = input("Event Date and Time (YYYY-MM-DD HH:MM:SS): ")
        try:
            event_date = datetime.strptime(event_date_str, "%Y-%m-%d %H:%M:%S")
            if event_date < datetime.now():
                print("Error: Event date cannot be in the past.")
                continue
            event_date_str = event_date.strftime("%Y-%m-%d %H:%M:%S")
            break
        except ValueError:
            print("Error: Invalid date format. Please use YYYY-MM-DD HH:MM:SS.")

    event_location = input("Event Location: ")
    while not event_location:
        print("Error: Event location is required.")
        event_location = input("Event Location: ")

    event_description = input("Event Description: ")

    # Event type
    event_types = ["in-person", "virtual", "hybrid"]
    print("\nEvent Types:")
    for i, etype in enumerate(event_types, 1):
        print(f"{i}. {etype}")

    try:
        type_choice = int(input("Select event type: "))
        if 1 <= type_choice <= len(event_types):
            event_type = event_types[type_choice - 1]
        else:
            event_type = "in-person"
    except ValueError:
        event_type = "in-person"

    # Virtual link for virtual/hybrid events
    virtual_link = ""
    if event_type in ["virtual", "hybrid"]:
        virtual_link = input("Virtual meeting link (Zoom, Teams, etc.): ")

    # Registration settings
    registration_required = input("Registration Required? (y/n): ").lower() == 'y'

    max_attendees = 0
    registration_deadline = None
    waitlist_enabled = False

    if registration_required:
        while True:
            try:
                max_attendees_str = input("Maximum Number of Attendees (0 for unlimited): ")
                max_attendees = int(max_attendees_str)
                if max_attendees < 0:
                    print("Error: Maximum attendees cannot be negative.")
                    continue
                break
            except ValueError:
                print("Error: Please enter a valid number.")

        # Registration deadline
        deadline_input = input("Registration deadline (YYYY-MM-DD HH:MM, press Enter for event date): ")
        if deadline_input:
            try:
                registration_deadline = datetime.strptime(deadline_input, "%Y-%m-%d %H:%M").strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                print("Invalid deadline format, using event date.")
                registration_deadline = event_date_str
        else:
            registration_deadline = event_date_str

        if max_attendees > 0:
            waitlist_enabled = input("Enable waitlist for overbooked events? (y/n): ").lower() == 'y'

    # Payment settings
    payment_required = input("Is payment required for this event? (y/n): ").lower() == 'y'
    event_fee = 0.0

    if payment_required:
        while True:
            try:
                event_fee = float(input("Event fee ($): "))
                if event_fee < 0:
                    print("Error: Fee cannot be negative.")
                    continue
                break
            except ValueError:
                print("Error: Please enter a valid amount.")

    # Insert the event
    cursor.execute('''
        INSERT INTO unified_events
        (title, start_datetime, location, description, registration_required,
         max_capacity, event_fee, payment_required, event_type, virtual_link,
         created_by, created_at, registration_deadline, waitlist_enabled, source_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'alumni')
    ''', (event_name, event_date_str, event_location, event_description,
          1 if registration_required else 0,
          max_attendees, event_fee, 1 if payment_required else 0,
          event_type, virtual_link,
          auth.current_user['username'], datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
          registration_deadline, 1 if waitlist_enabled else 0))

    event_id = cursor.lastrowid

    # Generate QR code for event check-in
    qr_code_path = generate_event_qr_code(event_id)
    if qr_code_path:
        cursor.execute('UPDATE unified_events SET qr_code_path = ? WHERE event_id = ?', (qr_code_path, event_id))

    conn.commit()

    print(f"\nEnhanced event created successfully with ID: {event_id}")
    print(f"Event Type: {event_type}")
    if payment_required:
        print(f"Event Fee: £{event_fee:.2f}")
    if virtual_link:
        print(f"Virtual Link: {virtual_link}")

    # Automatically send event invitations to all alumni
    try:
        # Get all alumni
        cursor.execute('SELECT alumni_id, email, first_name, last_name FROM alumni_profiles')
        alumni_list = cursor.fetchall()

        if alumni_list:
            print(f"\n\u2709\ufe0f  Sending event invitations to {len(alumni_list)} alumni...")
            sent_count = 0

            for alumni_id, email, first_name, last_name in alumni_list:
                try:
                    send_event_invitation(
                        alumni_id=alumni_id,
                        event_id=event_id,
                        email_address=email,
                        event_name=event_name,
                        event_date=event_date_str,
                        event_location=event_location
                    )
                    sent_count += 1
                except Exception as e:
                    print(f"   \u26a0\ufe0f  Could not send invitation to {email}: {e}")

            print(f"\u2705 Event invitations sent successfully to {sent_count} alumni!")
        else:
            print("\u26a0\ufe0f  No alumni found to notify.")
    except Exception as e:
        print(f"\u26a0\ufe0f  Could not send event invitations: {e}")

    conn.close()

def generate_event_qr_code(event_id):
    """Generate QR code for event check-in"""
    try:
        import qrcode

        # Create QR code data
        qr_data = f"EVENT_CHECKIN:{event_id}"

        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(qr_data)
        qr.make(fit=True)

        # Create QR code image
        img = qr.make_image(fill_color="black", back_color="white")

        # Save QR code
        qr_path = f"event_qr_{event_id}.png"
        img.save(qr_path)

        return qr_path
    except ImportError:
        print("QR code generation requires 'qrcode' library.")
        return None
    except Exception as e:
        print(f"Error generating QR code: {e}")
        return None

def send_enhanced_event_notifications(event_id, cursor):
    """Send enhanced event notifications"""
    # Get event details
    cursor.execute('SELECT * FROM unified_events WHERE event_id = ? AND source_type = \'alumni\'', (event_id,))
    event = cursor.fetchone()
    if not event:
        return

    # Get all alumni emails
    cursor.execute('SELECT alumni_id, email_address, first_name FROM alumni')
    alumni_list = cursor.fetchall()

    if alumni_list:
        print(f"Sending enhanced event invitations to {len(alumni_list)} alumni...")

        for alumni in alumni_list:
            alumni_id, email, first_name = alumni
            # Enhanced notification with event type, fees, etc.
            send_enhanced_event_invitation(
                alumni_id, email, first_name, event_id,
                event[1], event[2], event[3], event[8],
                event[6], event[7], event[9]
            )

        print("Enhanced event invitations sent successfully!")
    else:
        print("No alumni found to notify.")

def send_enhanced_event_invitation(alumni_id, email, first_name, event_id, event_name,
                                 event_date, event_location, event_type, event_fee,
                                 payment_required, virtual_link):
    """Send enhanced event invitation with all details"""
    if not email:
        print(f"No email address for alumni {alumni_id}")
        return

    try:
        # Build payment section
        payment_section = ""
        if payment_required and event_fee:
            payment_section = f"Registration Fee: £{event_fee}\nPayment Required: Yes\nPlease complete payment through the Alumni Portal to confirm your registration."
        elif event_fee:
            payment_section = f"Registration Fee: £{event_fee}"
        else:
            payment_section = "Registration: Free"

        # Build virtual section
        virtual_section = ""
        if virtual_link:
            virtual_section = f"Virtual Attendance Option:\nJoin online at: {virtual_link}"

        template = load_template('alumni/alumni_enhanced_event_invitation')
        if template:
            template_vars = {
                'recipient_name': first_name,
                'event_name': event_name,
                'event_type': event_type if event_type else "General Event",
                'event_date': str(event_date) if event_date else "TBD",
                'event_location': event_location if event_location else "TBD",
                'payment_section': payment_section,
                'virtual_section': virtual_section
            }

            subject, body = render_template('alumni_enhanced_event_invitation', template_vars)
            if subject and body:
                send_email(email, subject, body)
                print(f"Enhanced invitation sent to {email}")
            else:
                # Fallback to simple email
                _send_simple_event_email(email, first_name, event_name, event_date,
                                        event_location, event_type, payment_section, virtual_section)
        else:
            # No template available, send simple email
            _send_simple_event_email(email, first_name, event_name, event_date,
                                    event_location, event_type, payment_section, virtual_section)
    except Exception as e:
        print(f"Failed to send enhanced invitation to {email}: {e}")


def _send_simple_event_email(email, first_name, event_name, event_date, event_location,
                            event_type, payment_section, virtual_section):
    """Fallback simple event email when template is not available - now uses template system"""
    from education_system.post_18.university_system.infrastructure.email.template_utils import render_template

    template_vars = {
        'first_name': first_name,
        'event_name': event_name,
        'event_type': event_type if event_type else 'Alumni Event',
        'event_date': event_date if event_date else 'TBD',
        'event_location': event_location if event_location else 'TBD',
        'payment_section': payment_section,
        'virtual_section': virtual_section
    }

    subject, body = render_template('alumni_enhanced_event_invitation', template_vars)

    if not subject or not body:
        # Final fallback if template fails
        subject = f"Invitation: {event_name} - {event_type if event_type else 'Alumni Event'}"
        body = f"""Dear {first_name},

You are cordially invited to our upcoming alumni event!

Event Details:
--------------
Event: {event_name}
Type: {event_type if event_type else 'General Event'}
Date: {event_date if event_date else 'TBD'}
Location: {event_location if event_location else 'TBD'}

{payment_section}

{virtual_section}

To RSVP or register for this event, please log in to the Alumni Portal.

We hope to see you there!

Best regards,
The Alumni Relations Team
University Alumni Network"""

    send_email(email, subject, body)
    print(f"Simple invitation sent to {email}")

def event_check_in_system():
    """Event check-in system using QR codes or manual entry"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to use the check-in system.")
        return

    if not auth.check_permission('manage_events_advanced'):
        print("You don't have permission to manage event check-ins.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    print("\nEvent Check-In System")
    print("=====================")

    # Get today's events
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('''
        SELECT event_id, title, start_datetime, location
        FROM unified_events
        WHERE source_type = 'alumni' AND date(start_datetime) = ?
        ORDER BY start_datetime
    ''', (today,))

    today_events = cursor.fetchall()

    if not today_events:
        print("No events scheduled for today.")
        conn.close()
        return

    print("Today's Events:")
    for i, event in enumerate(today_events, 1):
        print(f"{i}. {event[1]} - {event[2]} at {event[3]}")

    try:
        event_choice = int(input(f"Select event for check-in (1-{len(today_events)}): "))
        if 1 <= event_choice <= len(today_events):
            selected_event = today_events[event_choice - 1]
            event_id = selected_event[0]
        else:
            print("Invalid selection.")
            conn.close()
            return
    except ValueError:
        print("Invalid input.")
        conn.close()
        return

    print(f"\nCheck-In for: {selected_event[1]}")
    print("1. Manual Check-In (Enter Alumni ID)")
    print("2. QR Code Check-In (Scan QR Code)")
    print("3. View Current Attendance")

    checkin_choice = input("Select check-in method: ")

    if checkin_choice == '1':
        # Manual check-in
        alumni_id = input("Enter Alumni ID: ")
        process_event_checkin(event_id, alumni_id, cursor)

    elif checkin_choice == '2':
        # QR Code check-in (simulated)
        print("QR Code scanner ready...")
        qr_data = input("Scan QR code or enter QR data: ")

        if qr_data.startswith("EVENT_CHECKIN:"):
            scanned_event_id = qr_data.split(":")[1]
            if scanned_event_id == str(event_id):
                alumni_id = input("Enter Alumni ID from registration: ")
                process_event_checkin(event_id, alumni_id, cursor)
            else:
                print("QR code is for a different event.")
        else:
            print("Invalid QR code format.")

    elif checkin_choice == '3':
        # View attendance
        cursor.execute('''
            SELECT er.*, a.first_name, a.last_name
            FROM unified_event_registrations er
            JOIN alumni a ON er.alumni_id = a.alumni_id
            WHERE er.event_id = ? AND er.attendance_confirmed = 1
            ORDER BY er.check_in_time
        ''', (event_id,))

        attendees = cursor.fetchall()

        print(f"\nCurrent Attendance: {len(attendees)}")
        if attendees:
            print("-" * 60)
            for attendee in attendees:
                name = f"{attendee[7]} {attendee[8]}"
                checkin_time = attendee[6] if attendee[6] else "Unknown"
                print(f"{name} - Checked in: {checkin_time}")
    else:
        print("Invalid choice.")

    conn.commit()
    conn.close()

def process_event_checkin(event_id, alumni_id, cursor):
    """Process event check-in for an alumni"""
    # Check if alumni is registered
    cursor.execute('''
        SELECT * FROM unified_event_registrations
        WHERE event_id = ? AND alumni_id = ?
    ''', (event_id, alumni_id))

    registration = cursor.fetchone()

    if not registration:
        print(f"Alumni {alumni_id} is not registered for this event.")
        return

    if registration[4]:  # attendance_confirmed
        print(f"Alumni {alumni_id} has already checked in.")
        return

    # Check payment status if required
    if registration[5] == 'pending':  # payment_status
        print(f"Alumni {alumni_id} has pending payment. Please process payment first.")
        return

    # Update check-in
    check_in_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('''
        UPDATE unified_event_registrations
        SET attendance_confirmed = 1, check_in_time = ?
        WHERE event_id = ? AND alumni_id = ?
    ''', (check_in_time, event_id, alumni_id))

    # Get alumni name for confirmation
    cursor.execute('SELECT first_name, last_name FROM alumni WHERE alumni_id = ?', (alumni_id,))
    alumni_info = cursor.fetchone()

    if alumni_info:
        name = f"{alumni_info[0]} {alumni_info[1]}"
        print(f"\u2705 {name} ({alumni_id}) checked in successfully at {check_in_time}")

        # Award engagement points
        award_engagement_points(alumni_id, 'event_attendance', 20)
