"""Workflow extracted from the legacy event-management module."""
from __future__ import annotations
from education_system.systems.university.domain.pastoral.student_life.student_union.events.application.ports import (
    AcademicCalendarManager, DatabaseManager, HAS_AUTH, UserAuth, datetime,
    get_connection, get_events_support_phone, os, random,
    send_confirmation_email, set_auth_instance, sqlite3, string,
)
from education_system.systems.university.interfaces.cli.pastoral.student_union_events.context import auth

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
                    print("\nTicket Sales Summary:")
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
