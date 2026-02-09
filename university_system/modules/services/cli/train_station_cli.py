#!/usr/bin/env python3
"""
Train Station CLI - Train Ticket Booking System
Features: Train services, ticket booking, payment processing, refunds
"""

from datetime import datetime
from pathlib import Path
import random
import string

try:
    from university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
except ImportError:
    DEFAULT_DB_PATH = Path(__file__).resolve().parents[3] / "data" / "db_files" / "student_records.db"

try:
    from university_system.infrastructure.database.db import get_connection
except ImportError:
    import sqlite3
    def get_connection():
        return sqlite3.connect(str(DEFAULT_DB_PATH))

try:
    from university_system.infrastructure.shared_context import get_current_user as get_user
except ImportError:
    get_user = None

try:
    from university_system.infrastructure.email.email_service import send_email_as_system
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    send_email_as_system = None


TRAIN_STATION_SCHEMA = """
CREATE TABLE IF NOT EXISTS train_station_services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_number TEXT UNIQUE NOT NULL,
    departure_station TEXT NOT NULL,
    arrival_station TEXT NOT NULL,
    departure_time TEXT NOT NULL,
    arrival_time TEXT NOT NULL,
    price REAL NOT NULL,
    available_seats INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS train_station_tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_number TEXT UNIQUE NOT NULL,
    service_id INTEGER NOT NULL,
    passenger_name TEXT NOT NULL,
    payment_method TEXT NOT NULL,
    price_paid REAL NOT NULL,
    purchase_date TEXT NOT NULL,
    FOREIGN KEY (service_id) REFERENCES train_station_services (id)
);

CREATE TABLE IF NOT EXISTS train_station_receipts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_number TEXT UNIQUE NOT NULL,
    ticket_id INTEGER NOT NULL,
    total_amount REAL NOT NULL,
    payment_method TEXT NOT NULL,
    transaction_date TEXT NOT NULL,
    FOREIGN KEY (ticket_id) REFERENCES train_station_tickets (id)
);

CREATE TABLE IF NOT EXISTS train_refunds (
    refund_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_number TEXT NOT NULL,
    student_id TEXT,
    amount DECIMAL(10,2) NOT NULL,
    refund_method TEXT NOT NULL,
    refund_reference TEXT,
    refunded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_by TEXT
);
"""


def init_train_database():
    """Initialize train station database tables."""
    try:
        with get_connection() as conn:
            conn.executescript(TRAIN_STATION_SCHEMA)

            # Insert default services if none exist
            cursor = conn.execute("SELECT COUNT(*) FROM train_station_services")
            if cursor.fetchone()[0] == 0:
                default_services = [
                    ("EXP001", "London Kings Cross", "Edinburgh", "06:00", "10:30", 89.50, 150),
                    ("EXP002", "London Euston", "Manchester", "07:15", "09:30", 65.00, 200),
                    ("EXP003", "London Paddington", "Bristol", "08:00", "09:45", 45.00, 180),
                    ("EXP004", "London Victoria", "Brighton", "09:30", "10:30", 25.00, 250),
                    ("EXP005", "London St Pancras", "Paris", "10:00", "13:00", 120.00, 300),
                    ("REG001", "Birmingham", "Liverpool", "11:00", "13:15", 35.00, 120),
                    ("REG002", "Leeds", "Sheffield", "12:30", "13:15", 18.50, 100),
                    ("REG003", "Glasgow", "Edinburgh", "14:00", "15:00", 22.00, 90),
                    ("EXP006", "Newcastle", "London Kings Cross", "15:30", "18:45", 95.00, 175),
                    ("REG004", "Cardiff", "Swansea", "16:00", "17:00", 15.00, 80),
                ]
                conn.executemany("""
                    INSERT INTO train_station_services
                    (service_number, departure_station, arrival_station, departure_time, arrival_time, price, available_seats)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, default_services)

            conn.commit()
        return True
    except Exception as e:
        print(f"Error initializing database: {e}")
        return False


def get_current_user():
    """Get the current authenticated user."""
    if get_user:
        user = get_user()
        if user:
            return user
    return {"username": "guest", "role": "guest", "email": "", "id": None, "name": "Guest User"}


def generate_ticket_number():
    """Generate unique ticket number."""
    return "TKT-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))


def generate_receipt_number():
    """Generate unique receipt number."""
    return "RCP-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))


# ==================== SERVICE MANAGEMENT ====================

def get_all_services():
    """Get all train services."""
    try:
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, service_number, departure_station, arrival_station,
                       departure_time, arrival_time, price, available_seats
                FROM train_station_services
            """)
            services = []
            for row in cursor.fetchall():
                services.append({
                    'id': row[0], 'service_number': row[1], 'departure_station': row[2],
                    'arrival_station': row[3], 'departure_time': row[4], 'arrival_time': row[5],
                    'price': row[6], 'available_seats': row[7]
                })
            return services
    except Exception as e:
        print(f"Error getting services: {e}")
        return []


def get_service_by_id(service_id):
    """Get a specific service by ID."""
    try:
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, service_number, departure_station, arrival_station,
                       departure_time, arrival_time, price, available_seats
                FROM train_station_services WHERE id = ?
            """, (service_id,))
            row = cursor.fetchone()
            if row:
                return {
                    'id': row[0], 'service_number': row[1], 'departure_station': row[2],
                    'arrival_station': row[3], 'departure_time': row[4], 'arrival_time': row[5],
                    'price': row[6], 'available_seats': row[7]
                }
    except Exception as e:
        print(f"Error getting service: {e}")
    return None


def update_service_seats(service_id, seats_change):
    """Update available seats for a service."""
    try:
        with get_connection() as conn:
            conn.execute("""
                UPDATE train_station_services
                SET available_seats = available_seats + ?
                WHERE id = ?
            """, (seats_change, service_id))
            conn.commit()
        return True
    except Exception as e:
        print(f"Error updating seats: {e}")
        return False


# ==================== TICKET BOOKING ====================

def purchase_ticket(service_id, passenger_name, payment_method, price_paid):
    """Create a new ticket purchase."""
    try:
        ticket_number = generate_ticket_number()
        purchase_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with get_connection() as conn:
            # Create ticket
            conn.execute("""
                INSERT INTO train_station_tickets (ticket_number, service_id, passenger_name, payment_method, price_paid, purchase_date)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (ticket_number, service_id, passenger_name, payment_method, price_paid, purchase_date))

            cursor = conn.execute("SELECT last_insert_rowid()")
            ticket_id = cursor.fetchone()[0]

            # Create receipt
            receipt_number = generate_receipt_number()
            conn.execute("""
                INSERT INTO train_station_receipts (receipt_number, ticket_id, total_amount, payment_method, transaction_date)
                VALUES (?, ?, ?, ?, ?)
            """, (receipt_number, ticket_id, price_paid, payment_method, purchase_date))

            # Update available seats
            conn.execute("""
                UPDATE train_station_services
                SET available_seats = available_seats - 1
                WHERE id = ?
            """, (service_id,))

            conn.commit()
        return ticket_id, ticket_number, receipt_number
    except Exception as e:
        print(f"Error purchasing ticket: {e}")
        return None, None, None


def get_all_tickets():
    """Get all tickets with service details."""
    try:
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT t.id, t.ticket_number, t.passenger_name, t.payment_method,
                       t.price_paid, t.purchase_date, s.service_number, s.departure_station,
                       s.arrival_station, s.departure_time, s.arrival_time
                FROM train_station_tickets t
                JOIN train_station_services s ON t.service_id = s.id
                ORDER BY t.id DESC
            """)
            tickets = []
            for row in cursor.fetchall():
                tickets.append({
                    'id': row[0], 'ticket_number': row[1], 'passenger_name': row[2],
                    'payment_method': row[3], 'price_paid': row[4], 'purchase_date': row[5],
                    'service_number': row[6], 'departure_station': row[7],
                    'arrival_station': row[8], 'departure_time': row[9], 'arrival_time': row[10]
                })
            return tickets
    except Exception as e:
        print(f"Error getting tickets: {e}")
        return []


def get_ticket_by_number(ticket_number):
    """Get a specific ticket by ticket number."""
    try:
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT t.id, t.ticket_number, t.passenger_name, t.payment_method,
                       t.price_paid, t.purchase_date, s.service_number, s.departure_station,
                       s.arrival_station, s.departure_time, s.arrival_time, s.id as service_id
                FROM train_station_tickets t
                JOIN train_station_services s ON t.service_id = s.id
                WHERE t.ticket_number = ?
            """, (ticket_number,))
            row = cursor.fetchone()
            if row:
                return {
                    'id': row[0], 'ticket_number': row[1], 'passenger_name': row[2],
                    'payment_method': row[3], 'price_paid': row[4], 'purchase_date': row[5],
                    'service_number': row[6], 'departure_station': row[7],
                    'arrival_station': row[8], 'departure_time': row[9], 'arrival_time': row[10],
                    'service_id': row[11]
                }
    except Exception as e:
        print(f"Error getting ticket: {e}")
    return None


# ==================== REFUNDS ====================

def process_refund(ticket_number, amount, refund_method, student_id=None):
    """Process a ticket refund."""
    try:
        current_user = get_current_user()
        refund_reference = "REF-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

        with get_connection() as conn:
            conn.execute("""
                INSERT INTO train_refunds (ticket_number, student_id, amount, refund_method, refund_reference, processed_by)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (ticket_number, student_id, amount, refund_method, refund_reference, current_user.get('name', 'System')))
            conn.commit()
        return refund_reference
    except Exception as e:
        print(f"Error processing refund: {e}")
        return None


# ==================== CLI INTERFACE ====================

def print_header(title):
    """Print formatted header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_service_details(service):
    """Print service details."""
    print(f"\n  Service Number: {service['service_number']}")
    print(f"  Route: {service['departure_station']} → {service['arrival_station']}")
    print(f"  Departure: {service['departure_time']}")
    print(f"  Arrival: {service['arrival_time']}")
    print(f"  Price: £{service['price']:.2f}")
    print(f"  Available Seats: {service['available_seats']}")


def print_ticket_details(ticket):
    """Print ticket details."""
    print(f"\n  Ticket Number: {ticket['ticket_number']}")
    print(f"  Passenger: {ticket['passenger_name']}")
    print(f"  Service: {ticket['service_number']}")
    print(f"  Route: {ticket['departure_station']} → {ticket['arrival_station']}")
    print(f"  Departure: {ticket['departure_time']}")
    print(f"  Arrival: {ticket['arrival_time']}")
    print(f"  Price Paid: £{ticket['price_paid']:.2f}")
    print(f"  Payment Method: {ticket['payment_method']}")
    print(f"  Purchase Date: {ticket['purchase_date']}")


def list_services_menu():
    """List all train services."""
    print_header("Available Train Services")

    services = get_all_services()

    if not services:
        print("\n  No services available.")
        return

    print(f"\n  Total services: {len(services)}\n")
    print(f"  {'ID':<5} {'Service':<10} {'Route':<40} {'Departs':<8} {'Arrives':<8} {'Price':<10} {'Seats':<6}")
    print("  " + "-" * 95)

    for service in services:
        route = f"{service['departure_station']} → {service['arrival_station']}"
        route = route[:37] + "..." if len(route) > 40 else route
        print(f"  {service['id']:<5} {service['service_number']:<10} {route:<40} {service['departure_time']:<8} {service['arrival_time']:<8} £{service['price']:<9.2f} {service['available_seats']:<6}")

    print()


def book_ticket_menu():
    """Book a train ticket."""
    print_header("Book Train Ticket")

    current_user = get_current_user()
    default_name = current_user.get('name', '')

    services = get_all_services()
    if not services:
        print("\n  No services available.")
        return

    print("\n  Available Services:")
    for service in services:
        if service['available_seats'] > 0:
            print(f"    {service['id']}. {service['service_number']} - {service['departure_station']} → {service['arrival_station']} at {service['departure_time']} (£{service['price']:.2f}, {service['available_seats']} seats)")

    service_choice = input("\n  Select service ID: ").strip()
    if not service_choice.isdigit():
        print("  ❌ Invalid service ID.")
        return

    service_id = int(service_choice)
    service = get_service_by_id(service_id)
    if not service:
        print("  ❌ Service not found.")
        return

    if service['available_seats'] <= 0:
        print("  ❌ No seats available for this service.")
        return

    print_service_details(service)

    passenger_name = input(f"\n  Passenger name [{default_name}]: ").strip() or default_name
    if not passenger_name:
        print("  ❌ Passenger name is required.")
        return

    print("\n  Payment Methods:")
    print("    1. Cash")
    print("    2. Card")
    print("    3. Student Account")

    payment_choice = input("  Select payment method (1-3): ").strip()
    payment_methods = {'1': 'Cash', '2': 'Card', '3': 'Student Account'}
    payment_method = payment_methods.get(payment_choice, 'Card')

    confirm = input(f"\n  Confirm purchase for £{service['price']:.2f}? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("  Purchase cancelled.")
        return

    ticket_id, ticket_number, receipt_number = purchase_ticket(
        service_id, passenger_name, payment_method, service['price']
    )

    if ticket_id:
        print(f"\n  ✅ Ticket purchased successfully!")
        print(f"  Ticket Number: {ticket_number}")
        print(f"  Receipt Number: {receipt_number}")
        print(f"  Total Paid: £{service['price']:.2f}")
    else:
        print("\n  ❌ Failed to purchase ticket.")


def view_tickets_menu():
    """View all tickets."""
    print_header("All Train Tickets")

    tickets = get_all_tickets()

    if not tickets:
        print("\n  No tickets found.")
        return

    print(f"\n  Total tickets: {len(tickets)}\n")
    print(f"  {'Ticket':<15} {'Passenger':<20} {'Service':<10} {'Route':<30} {'Price':<10}")
    print("  " + "-" * 90)

    for ticket in tickets:
        passenger = ticket['passenger_name'][:17] + "..." if len(ticket['passenger_name']) > 20 else ticket['passenger_name']
        route = f"{ticket['departure_station']} → {ticket['arrival_station']}"
        route = route[:27] + "..." if len(route) > 30 else route
        print(f"  {ticket['ticket_number']:<15} {passenger:<20} {ticket['service_number']:<10} {route:<30} £{ticket['price_paid']:<9.2f}")

    print()


def view_ticket_menu():
    """View ticket details."""
    print_header("View Ticket")

    ticket_number = input("\n  Enter Ticket Number: ").strip()
    if not ticket_number:
        print("  ❌ Ticket number required.")
        return

    ticket = get_ticket_by_number(ticket_number)
    if not ticket:
        print(f"  ❌ Ticket not found.")
        return

    print_header("Ticket Details")
    print_ticket_details(ticket)


def refund_ticket_menu():
    """Process a ticket refund."""
    print_header("Process Refund")

    ticket_number = input("\n  Enter Ticket Number: ").strip()
    if not ticket_number:
        print("  ❌ Ticket number required.")
        return

    ticket = get_ticket_by_number(ticket_number)
    if not ticket:
        print(f"  ❌ Ticket not found.")
        return

    print_ticket_details(ticket)

    confirm = input(f"\n  Process refund of £{ticket['price_paid']:.2f}? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("  Refund cancelled.")
        return

    print("\n  Refund Methods:")
    print("    1. Cash")
    print("    2. Card")
    print("    3. Student Account")

    refund_choice = input("  Select refund method (1-3): ").strip()
    refund_methods = {'1': 'Cash', '2': 'Card', '3': 'Student Account'}
    refund_method = refund_methods.get(refund_choice, 'Card')

    student_id = None
    if refund_method == 'Student Account':
        student_id = input("  Student ID: ").strip()

    refund_reference = process_refund(ticket_number, ticket['price_paid'], refund_method, student_id)

    if refund_reference:
        # Restore the seat
        update_service_seats(ticket['service_id'], 1)
        print(f"\n  ✅ Refund processed successfully!")
        print(f"  Refund Reference: {refund_reference}")
        print(f"  Amount: £{ticket['price_paid']:.2f}")
        print(f"  Method: {refund_method}")
    else:
        print("\n  ❌ Failed to process refund.")


def statistics_menu():
    """Show train station statistics."""
    print_header("Train Station Statistics")

    tickets = get_all_tickets()
    services = get_all_services()

    if not tickets and not services:
        print("\n  No data available.")
        return

    total_revenue = sum(t['price_paid'] for t in tickets)
    total_seats_available = sum(s['available_seats'] for s in services)

    print(f"\n  Total Services: {len(services)}")
    print(f"  Total Tickets Sold: {len(tickets)}")
    print(f"  Total Revenue: £{total_revenue:.2f}")
    print(f"  Available Seats: {total_seats_available}")

    # By route
    by_route = {}
    for t in tickets:
        route = f"{t['departure_station']} → {t['arrival_station']}"
        if route not in by_route:
            by_route[route] = {'count': 0, 'revenue': 0}
        by_route[route]['count'] += 1
        by_route[route]['revenue'] += t['price_paid']

    if by_route:
        print("\n  Top Routes:")
        for route, stats in sorted(by_route.items(), key=lambda x: x[1]['revenue'], reverse=True)[:5]:
            print(f"    {route}: {stats['count']} tickets, £{stats['revenue']:.2f}")

    # By payment method
    by_payment = {}
    for t in tickets:
        method = t['payment_method']
        by_payment[method] = by_payment.get(method, 0) + 1

    if by_payment:
        print("\n  By Payment Method:")
        for method, count in sorted(by_payment.items()):
            print(f"    {method}: {count}")

    print()


def train_station_menu():
    """Main train station CLI menu."""
    init_train_database()

    while True:
        print_header("Train Station - Ticket Booking")
        print("\n  1. View Train Services")
        print("  2. Book Ticket")
        print("  3. View All Tickets")
        print("  4. View Ticket Details")
        print("  5. Process Refund")
        print("  6. View Statistics")
        print("  0. Return to Main Menu")

        choice = input("\n  Enter your choice: ").strip()

        if choice == '1':
            list_services_menu()
        elif choice == '2':
            book_ticket_menu()
        elif choice == '3':
            view_tickets_menu()
        elif choice == '4':
            view_ticket_menu()
        elif choice == '5':
            refund_ticket_menu()
        elif choice == '6':
            statistics_menu()
        elif choice == '0':
            print("\n  Returning to main menu...\n")
            break
        else:
            print("\n  ❌ Invalid choice.")

        if choice != '0':
            input("\n  Press Enter to continue...")


if __name__ == '__main__':
    train_station_menu()
