# Standard library imports
import os
import random
from education_system.university_system.infrastructure.database.db import sqlite3
import string
from datetime import datetime
from typing import Optional

# Local imports
from education_system.university_system.infrastructure.database.db import DatabaseManager, get_connection
from education_system.university_system.infrastructure.email import send_confirmation_email
from education_system.university_system.modules.domain.academics.services.academic_calendar.calendar_core import AcademicCalendarManager
from education_system.university_system.modules.shared.constants.institution_settings import get_events_support_phone

# --- Shared auth wiring ---
try:
    from education_system.university_system.infrastructure.auth import UserAuth, get_current_user, set_auth_instance
    HAS_AUTH = True
except ImportError:
    # Fallback so type hints don't explode if import order differs in some environments
    class UserAuth:  # type: ignore
        pass
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None

# This module will receive the shared auth instance from the app entrypoint.
auth: Optional[UserAuth] = None

def set_auth(auth_obj: UserAuth) -> None:
    """Inject the shared authentication instance for this module."""
    global auth
    auth = auth_obj
    # Also set it in the global auth instance if available
    if HAS_AUTH:
        set_auth_instance(auth_obj)

def view_events():
    """View upcoming events"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to view events.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get current date
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        # Fetch upcoming events
        cursor.execute('''
        SELECT e.event_id, e.event_name, e.description, e.event_date, e.start_time, e.end_time,
               e.location, c.club_name, e.category, e.max_attendees, e.current_attendees
        FROM union_events e
        JOIN student_clubs c ON e.organizer_id = c.club_id
        WHERE e.event_date >= ? AND e.status = 'upcoming'
        ORDER BY e.event_date, e.start_time
        ''', (current_date,))
        
        events = cursor.fetchall()
        
        if not events:
            print("No upcoming events found.")
            conn.close()
            return
        
        print("\nUpcoming Events:")
        print("================")
        
        for event in events:
            print(f"\nID: {event[0]}")
            print(f"Name: {event[1]}")
            print(f"Organized by: {event[7]}")
            print(f"Description: {event[2]}")
            print(f"Date: {event[3]}")
            print(f"Time: {event[4]} - {event[5]}")
            print(f"Location: {event[6]}")
            print(f"Category: {event[8]}")
            
            if event[9] > 0:
                print(f"Attendance: {event[10]}/{event[9]}")
            else:
                print(f"Attendance: {event[10]} (unlimited)")
                
            print("-" * 40)
        
        conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def register_for_event():
    """Register for an event"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to register for events.")
        return
    
    if not auth.check_permission('register_for_events'):
        print("You don't have permission to register for events.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get student ID
        cursor.execute('SELECT student_id FROM users WHERE id = ?', (auth.current_user['id'],))
        result = cursor.fetchone()
        
        if not result:
            print("No student record is associated with your account.")
            conn.close()
            return
        
        student_id = result[0]
        
        # Show available events
        view_events()
        
        event_id = input("\nEnter the ID of the event you want to register for: ").strip()
        if not event_id.isdigit():
            print("Invalid event ID.")
            conn.close()
            return
        
        # Check if event exists and is upcoming
        cursor.execute('''
        SELECT event_name, max_attendees, current_attendees
        FROM union_events
        WHERE event_id = ? AND status = 'upcoming'
        ''', (event_id,))
        
        event = cursor.fetchone()
        
        if not event:
            print("Event not found or not available for registration.")
            conn.close()
            return
        
        # Check if already registered
        cursor.execute('''
        SELECT COUNT(*) FROM unified_event_registrations
        WHERE event_id = ? AND user_id = ?
        ''', (event_id, student_id))
        
        if cursor.fetchone()[0] > 0:
            print(f"You are already registered for {event[0]}.")
            conn.close()
            return
        
        # Check if event is full
        if event[1] > 0 and event[2] >= event[1]:
            print(f"Sorry, {event[0]} is already full.")
            conn.close()
            return
        
        # Register for the event
        registration_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
        INSERT INTO unified_event_registrations (event_id, user_id, user_type, registration_date, attendance_status)
        VALUES (?, ?, 'student', ?, ?)
        ''', (event_id, student_id, registration_date, 'registered'))

        
        # Update attendee count
        cursor.execute('''
        UPDATE union_events SET current_attendees = current_attendees + 1
        WHERE event_id = ?
        ''', (event_id,))
        
        conn.commit()
        print(f"You have successfully registered for {event[0]}!")
        
        # Send confirmation email
        send_confirmation_email(student_id, f"Event Registration: {event[0]}", 
                               f"You have successfully registered for the {event[0]} event.")
        
        conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def view_my_events():
    """View events I'm registered for"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to view your events.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get student ID
        cursor.execute('SELECT student_id FROM users WHERE id = ?', (auth.current_user['id'],))
        result = cursor.fetchone()
        
        if not result:
            print("No student record is associated with your account.")
            conn.close()
            return
        
        student_id = result[0]
        
        # Get events the student is registered for
        cursor.execute('''
        SELECT e.event_id, e.event_name, e.event_date, e.start_time, e.location,
               c.club_name, r.registration_date, r.attendance_status
        FROM union_events e
        JOIN student_clubs c ON e.organizer_id = c.club_id
        JOIN unified_event_registrations r ON e.event_id = r.event_id
        WHERE r.user_id = ?
        ORDER BY e.event_date, e.start_time
        ''', (student_id,))
        
        events = cursor.fetchall()
        
        if not events:
            print("You are not registered for any events.")
            conn.close()
            return
        
        print("\nYour Registered Events:")
        print("=======================")
        
        for event in events:
            print(f"\nID: {event[0]}")
            print(f"Name: {event[1]}")
            print(f"Date: {event[2]} at {event[3]}")
            print(f"Location: {event[4]}")
            print(f"Organized by: {event[5]}")
            print(f"Registration Date: {event[6]}")
            print(f"Status: {event[7]}")
            print("-" * 40)
        
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
        cursor.execute('SELECT student_id FROM users WHERE id = ?', (auth.current_user['id'],))
        result = cursor.fetchone()
        
        if not result:
            print("No student record is associated with your account.")
            conn.close()
            return
        
        student_id = result[0]
        
        # Get events user can manage
        if auth.check_permission('manage_all_events'):
            cursor.execute('''
            SELECT e.event_id, e.event_name, c.club_name, e.event_date
            FROM union_events e
            JOIN student_clubs c ON e.organizer_id = c.club_id
            ORDER BY e.event_date DESC
            ''')
        else:
            cursor.execute('''
            SELECT e.event_id, e.event_name, c.club_name, e.event_date
            FROM union_events e
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

def manage_event_tickets(event_id, event_name, cursor, conn):
    """Manage ticket sales for an event"""
    try:
        while True:
            print(f"\nTicket Management - {event_name}")
            print("1. Create ticket type")
            print("2. View ticket sales")
            print("3. Record ticket sale")
            print("4. Return to financial menu")
            
            action = input("Choose an action: ").strip()
            
            if action == '1':
                # Create ticket type
                ticket_type = input("Ticket type (e.g., Standard, VIP, Student): ").strip()
                if not ticket_type:
                    print("Ticket type cannot be empty.")
                    continue
                
                try:
                    price = float(input("Price per ticket (£): ").strip())
                    quantity = int(input("Quantity available: ").strip())
                    
                    if price < 0 or quantity <= 0:
                        print("Invalid price or quantity.")
                        continue
                except ValueError:
                    print("Invalid price or quantity format.")
                    continue
                
                cursor.execute('''
                INSERT INTO event_tickets (
                    event_id, ticket_type, price, quantity_available
                ) VALUES (?, ?, ?, ?)
                ''', (event_id, ticket_type, price, quantity))
                
                conn.commit()
                print(f"Ticket type '{ticket_type}' created: £{price:.2f} x {quantity}")
            
            elif action == '2':
                # View ticket sales
                cursor.execute('''
                SELECT ticket_type, price, quantity_available, quantity_sold,
                       (quantity_available - quantity_sold) as remaining,
                       (price * quantity_sold) as revenue
                FROM event_tickets
                WHERE event_id = ?
                GROUP BY ticket_type, price, quantity_available
                ''', (event_id,))
                
                tickets = cursor.fetchall()
                
                if not tickets:
                    print("No ticket types created for this event.")
                else:
                    print(f"\nTicket Sales Summary:")
                    print(f"{'Type':<15} {'Price':<8} {'Available':<10} {'Sold':<8} {'Remaining':<10} {'Revenue':<10}")
                    print("-" * 70)
                    
                    total_revenue = 0
                    for ticket in tickets:
                        total_revenue += ticket[5]
                        print(f"{ticket[0]:<15} £{ticket[1]:<7.2f} {ticket[2]:<10} {ticket[3]:<8} {ticket[4]:<10} £{ticket[5]:<9.2f}")
                    
                    print("-" * 70)
                    print(f"{'TOTAL REVENUE:':<59} £{total_revenue:.2f}")
            
            elif action == '3':
                # Record ticket sale
                cursor.execute('''
                SELECT ticket_type, price, (quantity_available - quantity_sold) as available
                FROM event_tickets
                WHERE event_id = ? AND quantity_available > quantity_sold
                GROUP BY ticket_type, price
                ''', (event_id,))
                
                available_tickets = cursor.fetchall()
                
                if not available_tickets:
                    print("No tickets available for sale.")
                    continue
                
                print("\nAvailable ticket types:")
                for i, ticket in enumerate(available_tickets):
                    print(f"{i+1}. {ticket[0]} - £{ticket[1]:.2f} ({ticket[2]} remaining)")
                
                choice = input("Select ticket type (enter number): ").strip()
                if not choice.isdigit() or int(choice) < 1 or int(choice) > len(available_tickets):
                    print("Invalid selection.")
                    continue
                
                selected_ticket = available_tickets[int(choice)-1]
                
                try:
                    quantity = int(input(f"Quantity to sell (max {selected_ticket[2]}): ").strip())
                    if quantity <= 0 or quantity > selected_ticket[2]:
                        print("Invalid quantity.")
                        continue
                except ValueError:
                    print("Invalid quantity format.")
                    continue
                
                student_id = input("Student ID (optional): ").strip()
                purchase_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # Update ticket sales
                cursor.execute('''
                UPDATE event_tickets 
                SET quantity_sold = quantity_sold + ?
                WHERE event_id = ? AND ticket_type = ? AND price = ?
                ''', (quantity, event_id, selected_ticket[0], selected_ticket[1]))
                
                # Record individual sale if student ID provided
                if student_id:
                    cursor.execute('''
                    INSERT INTO event_tickets (
                        event_id, ticket_type, price, quantity_available, 
                        quantity_sold, student_id, purchase_date, payment_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        event_id, selected_ticket[0], selected_ticket[1], 0,
                        quantity, student_id, purchase_date, 'completed'
                    ))
                
                # Add to event finances
                revenue_amount = selected_ticket[1] * quantity
                cursor.execute('''
                INSERT INTO event_finances (
                    event_id, revenue_type, amount, description, date_recorded
                ) VALUES (?, ?, ?, ?, ?)
                ''', (
                    event_id, 'Ticket Sales', revenue_amount,
                    f"{quantity}x {selected_ticket[0]} tickets", purchase_date
                ))
                
                conn.commit()
                print(f"Recorded sale: {quantity}x {selected_ticket[0]} tickets = £{revenue_amount:.2f}")
            
            elif action == '4':
                break
            
            else:
                print("Invalid choice.")
                
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def generate_event_financial_report(event_id, event_name, cursor):
    """Generate detailed financial report for an event"""
    try:
        print(f"\n{'='*60}")
        print(f"FINANCIAL REPORT - {event_name}")
        print(f"{'='*60}")
        
        # Revenue breakdown
        cursor.execute('''
        SELECT revenue_type, SUM(amount) as total_amount
        FROM event_finances
        WHERE event_id = ? AND amount > 0
        GROUP BY revenue_type
        ORDER BY total_amount DESC
        ''', (event_id,))
        
        revenues = cursor.fetchall()
        total_revenue = sum(rev[1] for rev in revenues)
        
        print(f"\nREVENUE BREAKDOWN:")
        print("-" * 30)
        for revenue in revenues:
            print(f"{revenue[0]:<20} £{revenue[1]:.2f}")
        print("-" * 30)
        print(f"{'TOTAL REVENUE:':<20} £{total_revenue:.2f}")
        
        # Expense breakdown
        cursor.execute('''
        SELECT expense_type, SUM(ABS(amount)) as total_amount
        FROM event_finances
        WHERE event_id = ? AND amount < 0
        GROUP BY expense_type
        ORDER BY total_amount DESC
        ''', (event_id,))
        
        expenses = cursor.fetchall()
        total_expenses = sum(exp[1] for exp in expenses)
        
        print(f"\nEXPENSE BREAKDOWN:")
        print("-" * 30)
        for expense in expenses:
            print(f"{expense[0]:<20} £{expense[1]:.2f}")
        print("-" * 30)
        print(f"{'TOTAL EXPENSES:':<20} £{total_expenses:.2f}")
        
        # Profit/Loss calculation
        profit_loss = total_revenue - total_expenses
        
        print(f"\nPROFIT/LOSS ANALYSIS:")
        print("-" * 30)
        print(f"{'Total Revenue:':<20} £{total_revenue:.2f}")
        print(f"{'Total Expenses:':<20} £{total_expenses:.2f}")
        print(f"{'Net Profit/Loss:':<20} £{profit_loss:.2f}")
        
        if total_revenue > 0:
            profit_margin = (profit_loss / total_revenue) * 100
            print(f"{'Profit Margin:':<20} {profit_margin:.1f}%")
        
        # Budget vs Actual (if budget was set)
        cursor.execute('''
        SELECT description FROM union_events WHERE event_id = ?
        ''', (event_id,))
        
        event_details = cursor.fetchone()
        
        print(f"\nEVENT PERFORMANCE:")
        print("-" * 30)
        
        if profit_loss > 0:
            print(f"✓ Event was profitable")
        elif profit_loss == 0:
            print(f"= Event broke even")
        else:
            print(f"✗ Event had a loss")
        
        # Recommendations
        print(f"\nRECOMMENDations:")
        print("-" * 30)
        
        if total_expenses > total_revenue * 0.8:
            print("• Consider reducing expenses for future events")
        
        if revenues:
            top_revenue_source = max(revenues, key=lambda x: x[1])
            print(f"• Top revenue source: {top_revenue_source[0]} (£{top_revenue_source[1]:.2f})")
        
        if expenses:
            top_expense = max(expenses, key=lambda x: x[1])
            print(f"• Largest expense: {top_expense[0]} (£{top_expense[1]:.2f})")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def generate_qr_code():
    """Generate a simple QR code string for event attendance"""
    # Generate a random string for QR code
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

def manage_event_attendance():
    """Manage event attendance tracking"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to manage event attendance.")
        return
    
    if not (auth.check_permission('create_club_events') or auth.check_permission('manage_all_events')):
        print("You don't have permission to manage event attendance.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get student ID
        cursor.execute('SELECT student_id FROM users WHERE id = ?', (auth.current_user['id'],))
        result = cursor.fetchone()
        
        if not result:
            print("No student record is associated with your account.")
            conn.close()
            return
        
        student_id = result[0]
        
        # Get events user can manage
        if auth.check_permission('manage_all_events'):
            cursor.execute('''
            SELECT e.event_id, e.event_name, c.club_name, e.event_date, e.status
            FROM union_events e
            JOIN student_clubs c ON e.organizer_id = c.club_id
            WHERE e.event_date >= date('now', '-7 days')
            ORDER BY e.event_date DESC
            ''')
        else:
            cursor.execute('''
            SELECT e.event_id, e.event_name, c.club_name, e.event_date, e.status
            FROM union_events e
            JOIN student_clubs c ON e.organizer_id = c.club_id
            WHERE (c.president_id = ? OR c.treasurer_id = ? OR c.secretary_id = ?)
            AND e.event_date >= date('now', '-7 days')
            ORDER BY e.event_date DESC
            ''', (student_id, student_id, student_id))
        
        events = cursor.fetchall()
        
        if not events:
            print("No recent events available for attendance management.")
            conn.close()
            return
        
        print("\nRecent events:")
        for i, event in enumerate(events):
            print(f"{i+1}. {event[1]} ({event[2]}) - {event[3]} [{event[4]}]")
        
        choice = input("Select an event to manage attendance (enter number): ").strip()
        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(events):
            print("Invalid selection.")
            conn.close()
            return
        
        selected_event = events[int(choice)-1]
        event_id = selected_event[0]
        event_name = selected_event[1]
        
        while True:
            print(f"\nAttendance Management - {event_name}")
            print("1. Generate QR codes for registered attendees")
            print("2. Check in attendee")
            print("3. View attendance report")
            print("4. Mark attendance for multiple students")
            print("5. Award CPD credits")
            print("6. Return to previous menu")
            
            action = input("Choose an action: ").strip()
            
            if action == '1':
                # Generate QR codes for registered attendees
                cursor.execute('''
                SELECT r.user_id, s.first_name, s.last_name
                FROM unified_event_registrations r
                JOIN students s ON r.user_id = s.student_id
                WHERE r.event_id = ? AND r.attendance_status = 'registered'
                ''', (event_id,))
                
                registered = cursor.fetchall()
                
                if not registered:
                    print("No registered attendees found.")
                    continue
                
                print(f"\nGenerating QR codes for {len(registered)} registered attendees...")
                
                for attendee in registered:
                    qr_code = generate_qr_code()
                    
                    # Check if attendance record already exists
                    cursor.execute('''
                    SELECT COUNT(*) FROM unified_event_registrations
                    WHERE event_id = ? AND user_id = ? AND qr_code IS NOT NULL
                    ''', (event_id, attendee[0]))

                    if cursor.fetchone()[0] == 0:
                        cursor.execute('''
                        UPDATE unified_event_registrations
                        SET qr_code = ?
                        WHERE event_id = ? AND user_id = ?
                        ''', (qr_code, event_id, attendee[0]))
                    
                    print(f"{attendee[1]} {attendee[2]} ({attendee[0]}): QR-{qr_code}")
                
                conn.commit()
                print("QR codes generated successfully!")
            
            elif action == '2':
                # Check in attendee
                qr_or_id = input("Enter QR code or Student ID: ").strip()
                
                if qr_or_id.startswith('QR-'):
                    qr_code = qr_or_id[3:]  # Remove 'QR-' prefix
                    cursor.execute('''
                    SELECT a.user_id, s.first_name, s.last_name
                    FROM unified_event_registrations a
                    JOIN students s ON a.user_id = s.student_id
                    WHERE a.event_id = ? AND a.qr_code = ?
                    ''', (event_id, qr_code))
                else:
                    cursor.execute('''
                    SELECT a.user_id, s.first_name, s.last_name
                    FROM unified_event_registrations a
                    JOIN students s ON a.user_id = s.student_id
                    WHERE a.event_id = ? AND a.user_id = ?
                    ''', (event_id, qr_or_id))
                
                attendee = cursor.fetchone()
                
                if not attendee:
                    print("Attendee not found or not registered for this event.")
                    continue
                
                # Check if already checked in
                cursor.execute('''
                SELECT checked_in_at FROM unified_event_registrations
                WHERE event_id = ? AND user_id = ?
                ''', (event_id, attendee[0]))
                
                check_in_data = cursor.fetchone()
                
                if check_in_data and check_in_data[0]:
                    print(f"{attendee[1]} {attendee[2]} is already checked in at {check_in_data[0]}.")
                    continue
                
                # Record check-in
                check_in_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                cursor.execute('''
                UPDATE unified_event_registrations
                SET checked_in_at = ?, attendance_status = 'verified'
                WHERE event_id = ? AND user_id = ?
                ''', (check_in_time, event_id, attendee[0]))
                
                # Update registration status
                cursor.execute('''
                UPDATE unified_event_registrations
                SET attendance_status = 'attended'
                WHERE event_id = ? AND user_id = ?
                ''', (event_id, attendee[0]))

                conn.commit()
                print(f"✓ {attendee[1]} {attendee[2]} checked in successfully at {check_in_time}")
            
            elif action == '3':
                # View attendance report
                cursor.execute('''
                SELECT
                    COUNT(*) as total_registered,
                    COUNT(CASE WHEN r.checked_in_at IS NOT NULL THEN 1 END) as attended,
                    COUNT(CASE WHEN r.checked_in_at IS NULL THEN 1 END) as no_show
                FROM unified_event_registrations r
                WHERE r.event_id = ?
                ''', (event_id,))
                
                stats = cursor.fetchone()
                
                print(f"\nAttendance Report - {event_name}")
                print("=" * 40)
                print(f"Total Registered: {stats[0]}")
                print(f"Attended: {stats[1]}")
                print(f"No Shows: {stats[2]}")
                
                if stats[0] > 0:
                    attendance_rate = (stats[1] / stats[0]) * 100
                    print(f"Attendance Rate: {attendance_rate:.1f}%")
                
                # Show individual attendance
                print(f"\nIndividual Attendance:")
                print(f"{'Student ID':<12} {'Name':<25} {'Status':<15} {'Check-in Time':<20}")
                print("-" * 75)
                
                cursor.execute('''
                SELECT r.user_id, s.first_name, s.last_name,
                       COALESCE(r.checked_in_at, 'Not checked in') as check_in,
                       CASE WHEN r.checked_in_at IS NOT NULL THEN 'Attended' ELSE 'No Show' END as status
                FROM unified_event_registrations r
                JOIN students s ON r.user_id = s.student_id
                WHERE r.event_id = ?
                ORDER BY s.last_name, s.first_name
                ''', (event_id,))
                
                attendees = cursor.fetchall()
                
                for attendee in attendees:
                    print(f"{attendee[0]:<12} {attendee[1]} {attendee[2]:<25} {attendee[4]:<15} {attendee[3]:<20}")
            
            elif action == '4':
                # Mark attendance for multiple students
                print("Enter student IDs (one per line, empty line to finish):")
                student_ids = []
                
                while True:
                    student_id_input = input().strip()
                    if not student_id_input:
                        break
                    student_ids.append(student_id_input)
                
                if not student_ids:
                    print("No student IDs entered.")
                    continue
                
                check_in_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                successful_checkins = 0
                
                for sid in student_ids:
                    try:
                        # Check if student is registered
                        cursor.execute('''
                        SELECT COUNT(*) FROM unified_event_registrations
                        WHERE event_id = ? AND user_id = ?
                        ''', (event_id, sid))
                        
                        if cursor.fetchone()[0] == 0:
                            print(f"Student {sid} is not registered for this event.")
                            continue
                        
                        # Create or update attendance record
                        cursor.execute('''
                        UPDATE unified_event_registrations
                        SET checked_in_at = ?, attendance_status = 'verified'
                        WHERE event_id = ? AND user_id = ?
                        ''', (check_in_time, event_id, sid))

                        # Update registration status
                        cursor.execute('''
                        UPDATE unified_event_registrations
                        SET attendance_status = 'attended'
                        WHERE event_id = ? AND user_id = ?
                        ''', (event_id, sid))
                        
                        successful_checkins += 1
                        
                    except sqlite3.Error as e:
                        print(f"Error checking in student {sid}: {e}")
                
                conn.commit()
                print(f"Successfully checked in {successful_checkins} students.")
            
            elif action == '5':
                # Award CPD credits
                try:
                    cpd_credits = float(input("CPD credits to award per attendee: ").strip())
                    if cpd_credits <= 0:
                        print("CPD credits must be positive.")
                        continue
                except ValueError:
                    print("Invalid CPD credits format.")
                    continue
                
                cursor.execute('''
                UPDATE unified_event_registrations
                SET cpd_credits = ?
                WHERE event_id = ? AND attendance_status = 'verified'
                ''', (cpd_credits, event_id))
                
                affected_rows = cursor.rowcount
                conn.commit()
                
                print(f"Awarded {cpd_credits} CPD credits to {affected_rows} attendees.")
            
            elif action == '6':
                break
            
            else:
                print("Invalid choice.")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

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
        cursor.execute('SELECT student_id FROM users WHERE id = ?', (auth.current_user['id'],))
        result = cursor.fetchone()
        
        if not result:
            print("No student record is associated with your account.")
            conn.close()
            return
        
        student_id = result[0]
        
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
        
        # Create the parent event
        cursor.execute('''
        INSERT INTO union_events (
            event_name, description, event_date, start_time, end_time,
            location, organizer_id, category, max_attendees, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            f"{event_name} (Series)", description, start_date, start_time, end_time,
            location, club_id, category, max_attendees, 'upcoming'
        ))
        
        parent_event_id = cursor.lastrowid
        
        # Create the recurring event record
        cursor.execute('''
        INSERT INTO recurring_events (
            parent_event_id, recurrence_type, recurrence_interval,
            end_date, days_of_week, max_occurrences, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            parent_event_id, recurrence_type, recurrence_interval,
            end_date, days_of_week, max_occurrences, 'active'
        ))
        
        # Generate individual event occurrences
        current_date = datetime.strptime(start_date, '%Y-%m-%d')
        end_datetime = datetime.strptime(end_date, '%Y-%m-%d')
        occurrence_count = 0
        
        while current_date <= end_datetime and (max_occurrences == 0 or occurrence_count < max_occurrences):
            occurrence_count += 1
            
            # Create individual event
            cursor.execute('''
            INSERT INTO union_events (
                event_name, description, event_date, start_time, end_time,
                location, organizer_id, category, max_attendees, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                f"{event_name} #{occurrence_count}", description, 
                current_date.strftime('%Y-%m-%d'), start_time, end_time,
                location, club_id, category, max_attendees, 'upcoming'
            ))
            
            # Calculate next occurrence
            if recurrence_type == 'daily':
                current_date += datetime.timedelta(days=recurrence_interval)
            elif recurrence_type == 'weekly':
                current_date += datetime.timedelta(weeks=recurrence_interval)
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
        print(f"Recurring event series created successfully!")
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
        cursor.execute('SELECT student_id FROM users WHERE id = ?', (auth.current_user['id'],))
        result = cursor.fetchone()
        
        if not result:
            print("No student record is associated with your account.")
            conn.close()
            return
        
        student_id = result[0]
        
        # Get recurring events user can manage
        if auth.check_permission('manage_all_events'):
            cursor.execute('''
            SELECT r.recurring_id, e.event_name, c.club_name, r.recurrence_type,
                   r.current_occurrences, r.max_occurrences, r.status
            FROM recurring_events r
            JOIN union_events e ON r.parent_event_id = e.event_id
            JOIN student_clubs c ON e.organizer_id = c.club_id
            WHERE r.status = 'active'
            ORDER BY e.event_name
            ''')
        else:
            cursor.execute('''
            SELECT r.recurring_id, e.event_name, c.club_name, r.recurrence_type,
                   r.current_occurrences, r.max_occurrences, r.status
            FROM recurring_events r
            JOIN union_events e ON r.parent_event_id = e.event_id
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
                SELECT r.parent_event_id FROM recurring_events WHERE recurring_id = ?
                ''', (recurring_id,))
                parent_id = cursor.fetchone()[0]
                
                cursor.execute('''
                SELECT event_id, event_name, event_date, start_time, status, current_attendees
                FROM union_events
                WHERE organizer_id = (
                    SELECT organizer_id FROM union_events WHERE event_id = ?
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
                WHERE r.recurring_id = ?
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
                FROM union_events
                WHERE event_id = ?
                ''', (parent_id,))
                
                template = cursor.fetchone()
                
                # Find last occurrence date
                cursor.execute('''
                SELECT MAX(event_date) FROM union_events
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
                        last_date += datetime.timedelta(days=recurrence_interval)
                    elif recurrence_type == 'weekly':
                        last_date += datetime.timedelta(weeks=recurrence_interval)
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
                    INSERT INTO union_events (
                        event_name, description, event_date, start_time, end_time,
                        location, organizer_id, category, max_attendees, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        f"{base_name} #{current_count}", template[1],
                        last_date.strftime('%Y-%m-%d'), template[2], template[3],
                        template[4], template[5], template[6], template[7], 'upcoming'
                    ))
                
                # Update occurrence count
                cursor.execute('''
                UPDATE recurring_events 
                SET current_occurrences = ?
                WHERE recurring_id = ?
                ''', (current_count, recurring_id))
                
                conn.commit()
                print(f"Added {additional_count} additional occurrences.")
            
            elif action == '3':
                # Cancel future occurrences
                cursor.execute('''
                SELECT r.parent_event_id FROM recurring_events WHERE recurring_id = ?
                ''', (recurring_id,))
                parent_id = cursor.fetchone()[0]
                
                cursor.execute('''
                SELECT organizer_id, event_name FROM union_events WHERE event_id = ?
                ''', (parent_id,))
                
                org_info = cursor.fetchone()
                base_name = org_info[1].split(' (Series)')[0]
                
                current_date = datetime.now().strftime('%Y-%m-%d')
                
                cursor.execute('''
                UPDATE union_events 
                SET status = 'cancelled'
                WHERE organizer_id = ? AND event_name LIKE ? AND event_date > ? AND status = 'upcoming'
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
                    WHERE recurring_id = ?
                    ''', (new_end_date, recurring_id))
                    
                    print("End date updated.")
                
                elif mod_choice == '2':
                    try:
                        new_max = int(input("New maximum occurrences (0 for unlimited): ").strip())
                        cursor.execute('''
                        UPDATE recurring_events 
                        SET max_occurrences = ?
                        WHERE recurring_id = ?
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
                    WHERE recurring_id = ?
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
                    WHERE recurring_id = ?
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

def manage_sustainable_events(student_id, cursor, conn):
    """Manage sustainable event planning"""
    try:
        print(f"\n🌿 Sustainable Event Planning")
        print("=" * 35)
        
        print("1. Plan sustainable event")
        print("2. Green event checklist")
        print("3. Sustainable vendor directory")
        print("4. View green certified events")
        print("5. Apply for green certification")
        
        choice = input("Choose option: ").strip()
        
        if choice == '1':
            # Plan sustainable event
            print("\nSustainable Event Planning Wizard")
            print("=================================")
            
            event_name = input("Event name: ").strip()
            expected_attendees = input("Expected attendees: ").strip()
            
            if not expected_attendees.isdigit():
                print("Invalid attendee count.")
                return
            
            expected_attendees = int(expected_attendees)
            
            print(f"\nSustainability recommendations for {expected_attendees} attendees:")
            
            # Venue recommendations
            print(f"\n🏢 Venue Selection:")
            print("- Choose venues with public transport access")
            print("- Select venues with renewable energy")
            print("- Consider outdoor venues to reduce energy needs")
            print("- Look for venues with recycling facilities")
            
            # Catering recommendations
            print(f"\n🍽️ Sustainable Catering:")
            print("- Offer 70% plant-based options")
            print("- Source from local suppliers (within 50km)")
            print("- Use reusable or compostable materials")
            print("- Avoid single-use plastics")
            
            # Transport recommendations
            print(f"\n🚌 Green Transportation:")
            print("- Provide public transport information")
            print("- Organize group travel from campus")
            print("- Offer bicycle parking")
            print("- Consider hybrid/virtual attendance")
            
            # Waste reduction
            print(f"\n♻️ Waste Reduction:")
            print("- Set up recycling stations")
            print("- Use digital materials instead of printed")
            print("- Implement food waste reduction strategies")
            print("- Provide water refill stations")
            
            # Calculate estimated carbon footprint
            estimated_carbon = expected_attendees * 2.5  # Conservative estimate
            print(f"\n📊 Estimated Carbon Footprint: {estimated_carbon:.1f} kg CO2")
            print(f"Target: Reduce by 30% through sustainable practices")
            
        elif choice == '2':
            # Green event checklist
            print(f"\n✅ Green Event Checklist")
            print("=" * 25)
            
            checklist_items = [
                "Venue accessible by public transport",
                "Renewable energy powered venue",
                "70%+ plant-based catering options",
                "Local suppliers (within 50km)",
                "Reusable or compostable materials",
                "No single-use plastics",
                "Recycling stations available",
                "Digital materials instead of printed",
                "Water refill stations",
                "Waste sorting system",
                "Carbon offset for unavoidable emissions",
                "Sustainability information for attendees"
            ]
            
            print("Pre-event planning:")
            for i, item in enumerate(checklist_items[:6], 1):
                print(f"{i:2}. ☐ {item}")
            
            print("\nDuring event:")
            for i, item in enumerate(checklist_items[6:9], 7):
                print(f"{i:2}. ☐ {item}")
            
            print("\nPost-event:")
            for i, item in enumerate(checklist_items[9:], 10):
                print(f"{i:2}. ☐ {item}")
        
        elif choice == '3':
            # Sustainable vendor directory
            print(f"\n🌱 Eco-Friendly Supplier Directory")
            print("=" * 40)
            
            suppliers = [
                ("Green Catering Co.", "Catering", "100% organic, local ingredients", "⭐⭐⭐⭐⭐"),
                ("EcoVenue Spaces", "Venues", "Solar-powered event spaces", "⭐⭐⭐⭐⭐"),
                ("Sustainable Supplies", "Equipment", "Biodegradable party supplies", "⭐⭐⭐⭐"),
                ("Carbon Neutral Transport", "Transport", "Electric vehicle fleet", "⭐⭐⭐⭐⭐"),
                ("Zero Waste Solutions", "Waste Management", "Complete recycling service", "⭐⭐⭐⭐"),
            ]
            
            print(f"{'Supplier':<25} {'Category':<15} {'Specialty':<30} {'Rating':<10}")
            print("-" * 85)
            
            for supplier in suppliers:
                print(f"{supplier[0]:<25} {supplier[1]:<15} {supplier[2]:<30} {supplier[3]:<10}")
            
            print(f"\nTo add your eco-friendly supplier:")
            print("- Contact Student Union sustainability team")
            print("- Provide sustainability certifications")
            print("- Complete environmental impact assessment")
        
        elif choice == '4':
            # View green certified events
            cursor.execute('''
            SELECT e.event_name, c.club_name, e.event_date, st.sustainability_score
            FROM union_events e
            JOIN student_clubs c ON e.organizer_id = c.club_id
            JOIN sustainability_tracking st ON e.event_id = st.event_id
            WHERE st.sustainability_score >= 80
            ORDER BY st.sustainability_score DESC, e.event_date DESC
            ''')
            
            green_events = cursor.fetchall()
            
            if not green_events:
                print("No green certified events found.")
                return
            
            print(f"\n🏆 Green Certified Events")
            print("=" * 30)
            print(f"{'Event':<30} {'Organizer':<20} {'Date':<12} {'Score':<8}")
            print("-" * 75)
            
            for event in green_events:
                print(f"{event[0][:30]:<30} {event[1][:20]:<20} {event[2]:<12} {event[3]:.1f}/100")
        
        elif choice == '5':
            # Apply for green certification
            print(f"\n🏅 Green Event Certification")
            print("=" * 30)
            
            # Get events eligible for certification
            cursor.execute('''
            SELECT e.event_id, e.event_name, st.sustainability_score
            FROM union_events e
            JOIN sustainability_tracking st ON e.event_id = st.event_id
            WHERE st.sustainability_score >= 70
            AND e.organizer_id IN (
                SELECT club_id FROM student_clubs
                WHERE president_id = ? OR treasurer_id = ? OR secretary_id = ?
            )
            ORDER BY st.sustainability_score DESC
            ''', (student_id, student_id, student_id))
            
            eligible_events = cursor.fetchall()
            
            if not eligible_events:
                print("No events eligible for green certification.")
                print("Events need a sustainability score of 70+ to qualify.")
                return
            
            print("Events eligible for green certification:")
            for i, event in enumerate(eligible_events):
                print(f"{i+1}. {event[1]} (Score: {event[2]:.1f})")
            
            event_choice = input("Select event to certify (enter number): ").strip()
            if event_choice.isdigit() and 1 <= int(event_choice) <= len(eligible_events):
                selected = eligible_events[int(event_choice)-1]
                
                print(f"\nApplying for certification for: {selected[1]}")
                print("Certification levels:")
                
                if selected[2] >= 90:
                    level = "Platinum"
                    points = 50
                elif selected[2] >= 80:
                    level = "Gold"
                    points = 35
                else:
                    level = "Silver"
                    points = 25
                
                print(f"Your event qualifies for: {level} Green Certification")
                print(f"Sustainability score: {selected[2]:.1f}/100")
                
                confirm = input("Submit certification application? (y/n): ").strip().lower()
                if confirm == 'y':
                    print("Green certification application submitted!")
                    print(f"Certificate level: {level}")
                    
                    # Award points
                    auto_award_points(student_id, "Green Initiatives", points, 
                                    f"{level} green certification for {selected[1]}", cursor, conn)
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def event_popularity_predictions(cursor):
    """Predict event popularity based on historical data"""
    try:
        print(f"\n🔮 Event Popularity Predictions")
        print("=" * 40)
        
        # Analyze factors that contribute to event success
        cursor.execute('''
        SELECT 
            category,
            AVG(current_attendees) as avg_attendance,
            COUNT(*) as event_count,
            AVG(CASE WHEN current_attendees > 
                (SELECT AVG(current_attendees) FROM union_events) 
                THEN 1 ELSE 0 END) as success_rate
        FROM union_events
        WHERE event_date >= date('now', '-12 months')
        GROUP BY category
        HAVING COUNT(*) >= 3
        ORDER BY avg_attendance DESC
        ''')
        
        category_performance = cursor.fetchall()
        
        if category_performance:
            print("Event Category Performance:")
            print(f"{'Category':<20} {'Avg Attendance':<15} {'Events':<8} {'Success Rate':<12}")
            print("-" * 60)
            
            for cat in category_performance:
                success_rate = f"{cat[3]*100:.1f}%"
                print(f"{cat[0]:<20} {cat[1]:<15.1f} {cat[2]:<8} {success_rate:<12}")
        
        # Day of week analysis
        cursor.execute('''
        SELECT 
            CASE CAST(strftime('%w', event_date) AS INTEGER)
                WHEN 0 THEN 'Sunday'
                WHEN 1 THEN 'Monday'
                WHEN 2 THEN 'Tuesday'
                WHEN 3 THEN 'Wednesday'
                WHEN 4 THEN 'Thursday'
                WHEN 5 THEN 'Friday'
                WHEN 6 THEN 'Saturday'
            END as day_of_week,
            AVG(current_attendees) as avg_attendance,
            COUNT(*) as event_count
        FROM union_events
        WHERE event_date >= date('now', '-6 months')
        GROUP BY strftime('%w', event_date)
        ORDER BY avg_attendance DESC
        ''')
        
        day_analysis = cursor.fetchall()
        
        if day_analysis:
            print(f"\nBest Days for Events:")
            print(f"{'Day':<12} {'Avg Attendance':<15} {'Events Held':<12}")
            print("-" * 40)
            
            for day in day_analysis:
                print(f"{day[0]:<12} {day[1]:<15.1f} {day[2]:<12}")
        
        # Time of day analysis
        cursor.execute('''
        SELECT 
            CASE 
                WHEN start_time < '12:00' THEN 'Morning'
                WHEN start_time < '17:00' THEN 'Afternoon'
                ELSE 'Evening'
            END as time_period,
            AVG(current_attendees) as avg_attendance,
            COUNT(*) as event_count
        FROM union_events
        WHERE event_date >= date('now', '-6 months')
        GROUP BY 
            CASE 
                WHEN start_time < '12:00' THEN 'Morning'
                WHEN start_time < '17:00' THEN 'Afternoon'
                ELSE 'Evening'
            END
        ORDER BY avg_attendance DESC
        ''')
        
        time_analysis = cursor.fetchall()
        
        if time_analysis:
            print(f"\nOptimal Event Times:")
            print(f"{'Time Period':<12} {'Avg Attendance':<15} {'Events Held':<12}")
            print("-" * 40)
            
            for time_period in time_analysis:
                print(f"{time_period[0]:<12} {time_period[1]:<15.1f} {time_period[2]:<12}")
        
        # Prediction recommendations
        print(f"\n💡 Recommendations for High Attendance:")
        if category_performance:
            best_category = category_performance[0]
            print(f"- Choose {best_category[0]} category events (avg {best_category[1]:.1f} attendees)")
        
        if day_analysis:
            best_day = day_analysis[0]
            print(f"- Schedule events on {best_day[0]}s (avg {best_day[1]:.1f} attendees)")
        
        if time_analysis:
            best_time = time_analysis[0]
            print(f"- Host events in the {best_time[0].lower()} (avg {best_time[1]:.1f} attendees)")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def manage_virtual_events():
    """Manage virtual and hybrid events"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to manage virtual events.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        while True:
            print(f"\n💻 Virtual Events Management")
            print("1. Create virtual event")
            print("2. Set up hybrid event")
            print("3. Manage live streaming")
            print("4. Interactive features")
            print("5. Recording and replay")
            print("6. Virtual attendance tracking")
            print("7. Technical support")
            print("8. Return to main menu")
            
            choice = input("Choose an option: ").strip()
            
            if choice == '1':
                create_virtual_event(cursor, conn)
            elif choice == '2':
                setup_hybrid_event(cursor, conn)
            elif choice == '3':
                manage_live_streaming(cursor)
            elif choice == '4':
                interactive_virtual_features(cursor)
            elif choice == '5':
                recording_and_replay_management(cursor)
            elif choice == '6':
                virtual_attendance_tracking(cursor)
            elif choice == '7':
                virtual_event_tech_support()
            elif choice == '8':
                break
            else:
                print("Invalid choice.")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def create_virtual_event(cursor, conn):
    """Create a virtual event"""
    try:
        print(f"\n🌐 Create Virtual Event")
        print("=" * 30)
        
        # Basic event information
        event_name = input("Event name: ").strip()
        if not event_name:
            print("Event name cannot be empty.")
            return
        
        description = input("Event description: ").strip()
        event_date = input("Event date (YYYY-MM-DD): ").strip()
        start_time = input("Start time (HH:MM): ").strip()
        end_time = input("End time (HH:MM): ").strip()
        
        # Virtual-specific settings
        print(f"\nVirtual Platform Options:")
        platforms = ["Zoom", "Microsoft Teams", "Google Meet", "Custom Platform", "Other"]
        for i, platform in enumerate(platforms, 1):
            print(f"{i}. {platform}")
        
        platform_choice = input("Select platform: ").strip()
        if platform_choice.isdigit() and 1 <= int(platform_choice) <= len(platforms):
            platform = platforms[int(platform_choice)-1]
        else:
            platform = input("Enter custom platform: ").strip()
        
        max_attendees = input("Maximum attendees (0 for unlimited): ").strip()
        max_attendees = int(max_attendees) if max_attendees.isdigit() else 0
        
        # Access settings
        print(f"\nAccess Settings:")
        print("1. Open to all students")
        print("2. Club members only")
        print("3. Registration required")
        print("4. Private/Invitation only")
        
        access_choice = input("Select access level: ").strip()
        access_levels = {
            '1': 'open',
            '2': 'club_members',
            '3': 'registration_required',
            '4': 'private'
        }
        access_level = access_levels.get(access_choice, 'registration_required')
        
        # Interactive features
        print(f"\nInteractive Features:")
        features = []
        
        if input("Enable chat? (y/n): ").strip().lower() == 'y':
            features.append("chat")
        if input("Enable Q&A? (y/n): ").strip().lower() == 'y':
            features.append("qa")
        if input("Enable polls? (y/n): ").strip().lower() == 'y':
            features.append("polls")
        if input("Enable breakout rooms? (y/n): ").strip().lower() == 'y':
            features.append("breakout_rooms")
        if input("Enable screen sharing? (y/n): ").strip().lower() == 'y':
            features.append("screen_sharing")
        
        # Recording settings
        record_event = input("Record event for later viewing? (y/n): ").strip().lower() == 'y'
        
        print(f"\n📝 Virtual Event Summary:")
        print(f"Name: {event_name}")
        print(f"Platform: {platform}")
        print(f"Date/Time: {event_date} {start_time}-{end_time}")
        print(f"Max Attendees: {max_attendees if max_attendees > 0 else 'Unlimited'}")
        print(f"Access Level: {access_level}")
        print(f"Features: {', '.join(features) if features else 'Basic'}")
        print(f"Recording: {'Yes' if record_event else 'No'}")
        
        confirm = input("\nCreate this virtual event? (y/n): ").strip().lower()
        if confirm == 'y':
            # In a real implementation, this would create the event
            # with virtual-specific settings stored
            print("Virtual event created successfully!")
            print("Virtual meeting link will be generated and shared with registrants.")
            print("Technical setup instructions have been sent to organizers.")
        
    except Exception as e:
        print(f"An error occurred: {e}")

def setup_hybrid_event(cursor, conn):
    """Set up a hybrid (physical + virtual) event"""
    try:
        print(f"\n🔗 Set Up Hybrid Event")
        print("=" * 30)
        
        event_name = input("Event name: ").strip()
        
        # Physical venue information
        print(f"\nPhysical Venue:")
        physical_location = input("Physical location: ").strip()
        physical_capacity = input("Physical venue capacity: ").strip()
        
        try:
            physical_capacity = int(physical_capacity)
        except ValueError:
            physical_capacity = 0
        
        # Virtual settings
        print(f"\nVirtual Component:")
        virtual_platform = input("Virtual platform: ").strip()
        virtual_capacity = input("Virtual attendee limit (0 for unlimited): ").strip()
        
        try:
            virtual_capacity = int(virtual_capacity)
        except ValueError:
            virtual_capacity = 0
        
        # Hybrid-specific features
        print(f"\nHybrid Event Features:")
        
        enable_virtual_qa = input("Allow virtual attendees to ask questions? (y/n): ").strip().lower() == 'y'
        enable_virtual_participation = input("Enable virtual breakout sessions? (y/n): ").strip().lower() == 'y'
        live_stream_to_virtual = input("Live stream physical event to virtual attendees? (y/n): ").strip().lower() == 'y'
        virtual_networking = input("Enable virtual networking sessions? (y/n): ").strip().lower() == 'y'
        
        # Registration preferences
        print(f"\nRegistration Options:")
        print("Attendees can choose:")
        print("1. Physical attendance only")
        print("2. Virtual attendance only")
        print("3. Hybrid (join virtually if physical is full)")
        
        # Technical requirements
        print(f"\nTechnical Setup Required:")
        print("✓ Camera and microphone at physical venue")
        print("✓ Reliable internet connection")
        print("✓ Virtual platform setup")
        print("✓ Technical support staff")
        
        if live_stream_to_virtual:
            print("✓ Live streaming equipment")
            print("✓ Audio mixing for Q&A")
        
        if enable_virtual_participation:
            print("✓ Hybrid facilitation training")
            print("✓ Virtual moderator")
        
        print(f"\n🎯 Hybrid Event Benefits:")
        print("• Increased accessibility")
        print("• Higher attendance capacity")
        print("• Flexibility for attendees")
        print("• Recorded content for later viewing")
        print("• Reduced travel requirements")
        
        setup_support = input("\nRequest technical setup support? (y/n): ").strip().lower() == 'y'
        
        if setup_support:
            print("Technical support request submitted.")
            print("AV team will contact you within 24 hours.")
        
        print("Hybrid event configuration saved!")
        
    except Exception as e:
        print(f"An error occurred: {e}")

def virtual_attendance_tracking(cursor):
    """Track attendance for virtual events"""
    try:
        print(f"\n👥 Virtual Attendance Tracking")
        print("=" * 40)
        
        print("Virtual Attendance Methods:")
        print("1. Login-based tracking")
        print("2. Check-in polls")
        print("3. Engagement monitoring")
        print("4. Time-based verification")
        print("5. Certificate generation")
        
        method_choice = input("Select tracking method: ").strip()
        
        if method_choice == '1':
            print(f"\n🔐 Login-Based Tracking:")
            print("• Automatic attendance when joining")
            print("• Duration tracking")
            print("• Multiple device detection")
            print("• Login/logout timestamps")
            
        elif method_choice == '2':
            print(f"\n📊 Check-in Polls:")
            print("• Periodic attendance polls")
            print("• Random check-in questions")
            print("• Interactive verification")
            print("• Engagement scoring")
            
        elif method_choice == '3':
            print(f"\n📈 Engagement Monitoring:")
            print("• Chat participation")
            print("• Poll responses")
            print("• Q&A submissions")
            print("• Camera/mic usage")
            
        elif method_choice == '4':
            print(f"\n⏰ Time-Based Verification:")
            print("• Minimum attendance duration")
            print("• Active window monitoring")
            print("• Break detection")
            print("• Late arrival handling")
            
        elif method_choice == '5':
            print(f"\n🏆 Certificate Generation:")
            print("• Automatic certificate creation")
            print("• Attendance verification")
            print("• CPD credit recording")
            print("• Digital badge awards")
        
        # Attendance analytics
        print(f"\n📊 Attendance Analytics:")
        print("• Real-time attendance count")
        print("• Peak attendance tracking")
        print("• Drop-off analysis")
        print("• Geographic distribution")
        print("• Device/platform breakdown")
        print("• Engagement heat maps")
        
        # Reporting features
        print(f"\n📋 Attendance Reporting:")
        print("• Individual attendance records")
        print("• Summary statistics")
        print("• Exportable attendance lists")
        print("• Integration with student records")
        print("• Automated follow-up emails")
        
        print("Virtual attendance tracking configured!")
        
    except Exception as e:
        print(f"An error occurred: {e}")

def virtual_event_tech_support():
    """Provide technical support information for virtual events"""
    try:
        print(f"\n🛠️ Virtual Event Technical Support")
        print("=" * 45)
        
        print("Common Technical Issues and Solutions:")
        print()
        
        print("🎥 Video Issues:")
        print("• Camera not working: Check permissions and drivers")
        print("• Poor video quality: Adjust lighting and bandwidth")
        print("• Video lag: Close other applications")
        print("• Can't see others: Check video display settings")
        
        print(f"\n🔊 Audio Issues:")
        print("• No sound: Check audio output device")
        print("• Microphone not working: Verify input permissions")
        print("• Echo/feedback: Use headphones")
        print("• Audio cutting out: Check internet connection")
        
        print(f"\n🌐 Connection Issues:")
        print("• Frequent disconnections: Test internet speed")
        print("• Can't join meeting: Verify meeting link/ID")
        print("• Slow loading: Close bandwidth-heavy applications")
        print("• Login problems: Clear browser cache")
        
        print(f"\n💻 Platform-Specific Help:")
        print("• Zoom: zoom.us/test for system test")
        print("• Teams: aka.ms/TeamsClientLogs for diagnostics")
        print("• Google Meet: Check Chrome extensions")
        print("• Custom platforms: Contact IT support")
        
        print(f"\n📱 Mobile Device Support:")
        print("• Download official mobile apps")
        print("• Ensure sufficient storage space")
        print("• Use stable WiFi connection")
        print("• Close background apps")
        
        print(f"\n🔧 Pre-Event Technical Check:")
        print("• Test camera and microphone")
        print("• Verify internet speed (minimum 5 Mbps)")
        print("• Update browser/app to latest version")
        print("• Test with practice meeting")
        print("• Prepare backup device/connection")
        
        print(f"\n📞 Live Technical Support:")
        print(f"• Support hotline: {get_events_support_phone()}")
        print("• Live chat: Available during events")
        print("• Email: techsupport@studentunion.ac.uk")
        print("• Remote assistance: Available on request")
        
        print(f"\n💡 Optimization Tips:")
        print("• Use wired internet connection when possible")
        print("• Close unnecessary applications")
        print("• Use headphones for better audio")
        print("• Have good lighting for video calls")
        print("• Keep backup communication method ready")
        
        support_request = input("\nSubmit technical support request? (y/n): ").strip().lower() == 'y'
        
        if support_request:
            issue_description = input("Describe your technical issue: ").strip()
            contact_method = input("Preferred contact method (email/phone): ").strip()
            urgency = input("Urgency level (low/medium/high): ").strip()
            
            print("Technical support request submitted!")
            print("Response time:")
            print("• High urgency: Within 1 hour")
            print("• Medium urgency: Within 4 hours") 
            print("• Low urgency: Within 24 hours")
        
    except Exception as e:
        print(f"An error occurred: {e}")

def knowledge_sharing_sessions(student_id, cursor, conn):
    """Organize knowledge sharing and learning sessions"""
    try:
        print(f"\n🧠 Knowledge Sharing Sessions")
        print("=" * 40)
        
        print("1. Organize skill sharing session")
        print("2. Request learning session")
        print("3. Browse available sessions")
        print("4. Peer teaching opportunities")
        print("5. Expert talks series")
        
        choice = input("Choose option: ").strip()
        
        if choice == '1':
            # Organize skill sharing session
            print(f"\n🎯 Organize Skill Sharing Session")
            
            skill_topic = input("What skill will you teach? ").strip()
            skill_level = input("Skill level you'll teach (beginner/intermediate/advanced): ").strip()
            
            session_format = input("Session format (workshop/demo/tutorial/discussion): ").strip()
            duration = input("Session duration (minutes): ").strip()
            
            max_participants = input("Maximum participants: ").strip()
            materials_needed = input("Materials needed (if any): ").strip()
            
            # Your expertise
            your_experience = input("Your experience with this skill: ").strip()
            teaching_experience = input("Previous teaching experience (y/n): ").strip().lower() == 'y'
            
            print(f"\n📋 Session Plan:")
            print(f"Skill: {skill_topic}")
            print(f"Level: {skill_level}")
            print(f"Format: {session_format}")
            print(f"Duration: {duration} minutes")
            print(f"Max participants: {max_participants}")
            
            if materials_needed:
                print(f"Materials: {materials_needed}")
            
            schedule_session = input("\nSchedule this session? (y/n): ").strip().lower() == 'y'
            if schedule_session:
                print("Skill sharing session scheduled!")
                print("Session will be promoted to interested students")
                
                # Award points
                auto_award_points(student_id, "Knowledge Sharing", 25, 
                                f"Organized skill sharing: {skill_topic}", cursor, conn)
        
        elif choice == '2':
            # Request learning session
            print(f"\n📚 Request Learning Session")
            
            desired_skill = input("What skill would you like to learn? ").strip()
            current_level = input("Your current level (complete beginner/some experience): ").strip()
            
            learning_goals = input("What do you hope to achieve? ").strip()
            preferred_format = input("Preferred format (hands-on/lecture/group/one-on-one): ").strip()
            
            urgency = input("How urgent is this request (low/medium/high): ").strip()
            
            print(f"\n📝 Learning Request Summary:")
            print(f"Skill: {desired_skill}")
            print(f"Current level: {current_level}")
            print(f"Goals: {learning_goals}")
            print(f"Format: {preferred_format}")
            print(f"Urgency: {urgency}")
            
            submit_request = input("\nSubmit learning request? (y/n): ").strip().lower() == 'y'
            if submit_request:
                print("Learning request submitted!")
                print("We'll match you with available teachers")
                print("You'll be notified when sessions become available")
        
        elif choice == '3':
            # Browse available sessions
            print(f"\n🔍 Available Knowledge Sharing Sessions")
            
            # Sample sessions
            sessions = [
                ("Python Programming Basics", "2 hours", "Beginner", "Tomorrow 6pm"),
                ("Presentation Skills Workshop", "90 minutes", "All levels", "Friday 4pm"),
                ("Guitar for Beginners", "1 hour", "Beginner", "Saturday 2pm"),
                ("Time Management Techniques", "45 minutes", "All levels", "Monday 7pm"),
                ("Photography Fundamentals", "2 hours", "Beginner", "Wednesday 5pm")
            ]
            
            print(f"{'Session':<30} {'Duration':<12} {'Level':<12} {'Time':<15}")
            print("-" * 75)
            
            for session in sessions:
                print(f"{session[0]:<30} {session[1]:<12} {session[2]:<12} {session[3]:<15}")
            
            session_choice = input("\nJoin a session (enter number, 0 to skip): ").strip()
            if session_choice.isdigit() and 1 <= int(session_choice) <= len(sessions):
                selected = sessions[int(session_choice)-1]
                print(f"Signed up for: {selected[0]}")
                print("Confirmation and details will be emailed to you")
        
        elif choice == '4':
            # Peer teaching opportunities
            print(f"\n👨‍🏫 Peer Teaching Opportunities")
            
            print("Benefits of peer teaching:")
            print("• Strengthen your own knowledge")
            print("• Develop communication skills")
            print("• Build leadership experience")
            print("• Help fellow students succeed")
            print("• Earn community service hours")
            
            print(f"\nTeaching opportunities:")
            print("• Subject-specific tutoring")
            print("• Study skills workshops")
            print("• Technology training")
            print("• Language exchange")
            print("• Creative skills sharing")
            
            subjects_can_teach = input("What subjects/skills can you teach? ").strip()
            availability = input("Your availability (e.g., 'weekday evenings'): ").strip()
            
            if subjects_can_teach:
                print(f"\nTeaching profile:")
                print(f"Skills: {subjects_can_teach}")
                print(f"Availability: {availability}")
                
                register_as_teacher = input("Register as peer teacher? (y/n): ").strip().lower() == 'y'
                if register_as_teacher:
                    print("Registered as peer teacher!")
                    print("Students will be able to request sessions with you")
        
        elif choice == '5':
            # Expert talks series
            print(f"\n🎤 Expert Talks Series")
            
            print("Upcoming expert talks:")
            
            talks = [
                ("The Future of AI", "Prof. Elena Vasquez", "Tech Industry", "Next Tuesday"),
                ("Climate Change Solutions", "Dr. Michael Green", "Environmental Science", "Thursday"),
                ("Entrepreneurship Journey", "Sarah Kim, CEO", "Business", "Next Monday"),
                ("Mental Health Awareness", "Dr. James Liu", "Psychology", "Friday"),
                ("Space Exploration", "Commander Lisa Park", "Aerospace", "Next Wednesday")
            ]
            
            print(f"{'Topic':<25} {'Speaker':<20} {'Field':<18} {'Date':<15}")
            print("-" * 80)
            
            for talk in talks:
                print(f"{talk[0]:<25} {talk[1]:<20} {talk[2]:<18} {talk[3]:<15}")
            
            attend_talk = input("\nRegister for a talk (enter number, 0 to skip): ").strip()
            if attend_talk.isdigit() and 1 <= int(attend_talk) <= len(talks):
                selected = talks[int(attend_talk)-1]
                print(f"Registered for: {selected[0]} by {selected[1]}")
                
            print(f"\nSuggest an expert speaker:")
            suggested_speaker = input("Speaker name/field (optional): ").strip()
            suggested_topic = input("Suggested topic (optional): ").strip()
            
            if suggested_speaker or suggested_topic:
                print("Speaker suggestion recorded!")
                print("Event organizers will consider your suggestion")
        
    except Exception as e:
        print(f"An error occurred: {e}")

def display_event_menu():
    """Display the event management menu"""
    global auth
    
    while True:
        print("\nEvents")
        print("======")
        
        # Options
        print("1. View Upcoming Events")
        print("2. View My Registered Events")
        
        if auth.check_permission('register_for_events'):
            print("3. Register for an Event")
            print("4. Return to Student Union Menu")
            max_option = 4
        else:
            print("3. Return to Student Union Menu")
            max_option = 3
        
        choice = input("\nEnter your choice: ")
        
        if choice == '1':
            # View Events
            view_events()
        elif choice == '2':
            # View My Events
            view_my_events()
        elif choice == '3' and auth.check_permission('register_for_events'):
            # Register for Event
            register_for_event()
        elif choice == str(max_option):
            # Return to Student Union Menu
            return
        else:
            print("Invalid choice. Please try again.")
