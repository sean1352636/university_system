#!/usr/bin/env python3
"""
Taxi Booking CLI - Taxi Service Booking System
Features: Service management, ticket booking, payment processing, receipt generation
"""

from datetime import datetime
from pathlib import Path
import random
import string

from education_system.systems.university.infrastructure.paths import DEFAULT_DB_PATH

try:
    from education_system.systems.university.infrastructure.database.db import get_connection
except ImportError:
    from education_system.systems.university.infrastructure.database.db import sqlite3
    def get_connection():
        return sqlite3.connect(str(DEFAULT_DB_PATH))

try:
    from education_system.systems.university.infrastructure.shared_context import get_current_user as get_user
except ImportError:
    get_user = None

try:
    from education_system.systems.university.infrastructure.email.email_service import send_email_as_system
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    send_email_as_system = None

TAXI_BOOKING_SCHEMA = """
CREATE TABLE IF NOT EXISTS taxi_booking_services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_name TEXT NOT NULL,
    vehicle_type TEXT NOT NULL,
    capacity INTEGER NOT NULL,
    price_per_km REAL NOT NULL,
    base_fare REAL NOT NULL,
    description TEXT,
    available INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS taxi_booking_tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_number TEXT UNIQUE NOT NULL,
    service_id INTEGER NOT NULL,
    customer_name TEXT NOT NULL,
    pickup_location TEXT NOT NULL,
    dropoff_location TEXT NOT NULL,
    distance_km REAL NOT NULL,
    total_fare REAL NOT NULL,
    payment_method TEXT NOT NULL,
    payment_status TEXT DEFAULT 'Completed',
    booking_date TEXT NOT NULL,
    booking_time TEXT NOT NULL,
    FOREIGN KEY (service_id) REFERENCES taxi_booking_services (id)
);
"""

def init_taxi_database():
    """Initialize taxi booking database tables."""
    try:
        with get_connection() as conn:
            conn.executescript(TAXI_BOOKING_SCHEMA)

            # Insert default services if none exist
            cursor = conn.execute("SELECT COUNT(*) FROM taxi_booking_services")
            if cursor.fetchone()[0] == 0:
                default_services = [
                    ("City Express", "Sedan", 4, 2.50, 5.00, "Comfortable city rides with AC"),
                    ("Premium Luxury", "SUV", 6, 4.00, 10.00, "Luxury SUV for premium travel"),
                    ("Budget Saver", "Hatchback", 4, 1.75, 3.00, "Affordable rides for short trips"),
                    ("Family Van", "Minivan", 8, 3.50, 8.00, "Spacious van for family outings"),
                    ("Eco Green", "Electric", 4, 2.00, 4.00, "Eco-friendly electric vehicle"),
                    ("Executive Class", "Luxury Sedan", 4, 5.00, 15.00, "Top-tier business class service"),
                    ("Airport Shuttle", "Van", 10, 3.00, 20.00, "Dedicated airport transfers"),
                    ("Night Owl", "Sedan", 4, 3.00, 7.00, "24/7 night service with safety features"),
                ]
                conn.executemany("""
                    INSERT INTO taxi_booking_services (service_name, vehicle_type, capacity, price_per_km, base_fare, description)
                    VALUES (?, ?, ?, ?, ?, ?)
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
    return "TXI-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

# ==================== SERVICE MANAGEMENT ====================

def get_all_services():
    """Get all available taxi services."""
    try:
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, service_name, vehicle_type, capacity, price_per_km, base_fare, description
                FROM taxi_booking_services
                WHERE available = 1
            """)
            services = []
            for row in cursor.fetchall():
                services.append({
                    'id': row[0], 'service_name': row[1], 'vehicle_type': row[2],
                    'capacity': row[3], 'price_per_km': row[4], 'base_fare': row[5],
                    'description': row[6]
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
                SELECT id, service_name, vehicle_type, capacity, price_per_km, base_fare, description
                FROM taxi_booking_services WHERE id = ?
            """, (service_id,))
            row = cursor.fetchone()
            if row:
                return {
                    'id': row[0], 'service_name': row[1], 'vehicle_type': row[2],
                    'capacity': row[3], 'price_per_km': row[4], 'base_fare': row[5],
                    'description': row[6]
                }
    except Exception as e:
        print(f"Error getting service: {e}")
    return None

# ==================== TICKET BOOKING ====================

def create_ticket(service_id, customer_name, pickup, dropoff, distance, total_fare, payment_method):
    """Create a new ticket."""
    try:
        ticket_number = generate_ticket_number()
        now = datetime.now()

        with get_connection() as conn:
            conn.execute("""
                INSERT INTO taxi_booking_tickets
                (ticket_number, service_id, customer_name, pickup_location, dropoff_location,
                 distance_km, total_fare, payment_method, booking_date, booking_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ticket_number, service_id, customer_name, pickup, dropoff, distance,
                total_fare, payment_method, now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")
            ))
            conn.commit()
            cursor = conn.execute("SELECT last_insert_rowid()")
            ticket_id = cursor.fetchone()[0]
        return ticket_id, ticket_number
    except Exception as e:
        print(f"Error creating ticket: {e}")
        return None, None

def get_all_tickets():
    """Get all tickets with service details."""
    try:
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT t.id, t.ticket_number, t.customer_name, t.pickup_location,
                       t.dropoff_location, t.distance_km, t.total_fare, t.payment_method,
                       t.booking_date, t.booking_time, s.service_name, s.vehicle_type
                FROM taxi_booking_tickets t
                JOIN taxi_booking_services s ON t.service_id = s.id
                ORDER BY t.id DESC
            """)
            tickets = []
            for row in cursor.fetchall():
                tickets.append({
                    'id': row[0], 'ticket_number': row[1], 'customer_name': row[2],
                    'pickup_location': row[3], 'dropoff_location': row[4], 'distance_km': row[5],
                    'total_fare': row[6], 'payment_method': row[7], 'booking_date': row[8],
                    'booking_time': row[9], 'service_name': row[10], 'vehicle_type': row[11]
                })
            return tickets
    except Exception as e:
        print(f"Error getting tickets: {e}")
        return []

def get_ticket_by_id(ticket_id):
    """Get a specific ticket with full details."""
    try:
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT t.id, t.ticket_number, t.customer_name, t.pickup_location,
                       t.dropoff_location, t.distance_km, t.total_fare, t.payment_method,
                       t.booking_date, t.booking_time, s.service_name, s.vehicle_type, s.description
                FROM taxi_booking_tickets t
                JOIN taxi_booking_services s ON t.service_id = s.id
                WHERE t.id = ?
            """, (ticket_id,))
            row = cursor.fetchone()
            if row:
                return {
                    'id': row[0], 'ticket_number': row[1], 'customer_name': row[2],
                    'pickup_location': row[3], 'dropoff_location': row[4], 'distance_km': row[5],
                    'total_fare': row[6], 'payment_method': row[7], 'booking_date': row[8],
                    'booking_time': row[9], 'service_name': row[10], 'vehicle_type': row[11],
                    'description': row[12]
                }
    except Exception as e:
        print(f"Error getting ticket: {e}")
    return None

# ==================== CLI INTERFACE ====================

def print_header(title):
    """Print formatted header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def print_service_details(service):
    """Print service details."""
    print(f"\n  ID: {service['id']}")
    print(f"  Service: {service['service_name']}")
    print(f"  Vehicle Type: {service['vehicle_type']}")
    print(f"  Capacity: {service['capacity']} passengers")
    print(f"  Base Fare: £{service['base_fare']:.2f}")
    print(f"  Price per km: £{service['price_per_km']:.2f}")
    print(f"  Description: {service['description']}")

def print_ticket_details(ticket):
    """Print ticket details."""
    print(f"\n  Ticket Number: {ticket['ticket_number']}")
    print(f"  Customer: {ticket['customer_name']}")
    print(f"  Service: {ticket['service_name']} ({ticket['vehicle_type']})")
    print(f"  Pickup: {ticket['pickup_location']}")
    print(f"  Drop-off: {ticket['dropoff_location']}")
    print(f"  Distance: {ticket['distance_km']} km")
    print(f"  Total Fare: £{ticket['total_fare']:.2f}")
    print(f"  Payment Method: {ticket['payment_method']}")
    print(f"  Booking Date: {ticket['booking_date']} at {ticket['booking_time']}")

def list_services_menu():
    """List all available taxi services."""
    print_header("Available Taxi Services")

    services = get_all_services()

    if not services:
        print("\n  No services available.")
        return

    print(f"\n  Total services: {len(services)}\n")

    for service in services:
        print_service_details(service)
        print("  " + "-" * 70)

def book_taxi_menu():
    """Book a taxi."""
    print_header("Book a Taxi")

    current_user = get_current_user()
    default_name = current_user.get('name', '')

    services = get_all_services()
    if not services:
        print("\n  No services available.")
        return

    print("\n  Available Services:")
    for service in services:
        print(f"    {service['id']}. {service['service_name']} - {service['vehicle_type']} (£{service['base_fare']:.2f} + £{service['price_per_km']:.2f}/km)")

    service_choice = input("\n  Select service ID: ").strip()
    if not service_choice.isdigit():
        print("  ❌ Invalid service ID.")
        return

    service_id = int(service_choice)
    service = get_service_by_id(service_id)
    if not service:
        print("  ❌ Service not found.")
        return

    print_service_details(service)

    customer_name = input(f"\n  Customer name [{default_name}]: ").strip() or default_name
    if not customer_name:
        print("  ❌ Customer name is required.")
        return

    pickup = input("  Pickup location: ").strip()
    if not pickup:
        print("  ❌ Pickup location is required.")
        return

    dropoff = input("  Drop-off location: ").strip()
    if not dropoff:
        print("  ❌ Drop-off location is required.")
        return

    distance_input = input("  Distance (km): ").strip()
    try:
        distance = float(distance_input)
        if distance <= 0:
            print("  ❌ Distance must be positive.")
            return
    except ValueError:
        print("  ❌ Invalid distance.")
        return

    # Calculate fare
    total_fare = service['base_fare'] + (distance * service['price_per_km'])

    print("\n  Fare Calculation:")
    print(f"    Base Fare: £{service['base_fare']:.2f}")
    print(f"    Distance: {distance} km × £{service['price_per_km']:.2f}/km = £{distance * service['price_per_km']:.2f}")
    print(f"    Total Fare: £{total_fare:.2f}")

    print("\n  Payment Methods:")
    print("    1. Cash")
    print("    2. Card")
    print("    3. Student Account")

    payment_choice = input("  Select payment method (1-3): ").strip()
    payment_methods = {'1': 'Cash', '2': 'Card', '3': 'Student Account'}
    payment_method = payment_methods.get(payment_choice, 'Cash')

    confirm = input(f"\n  Confirm booking for £{total_fare:.2f}? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("  Booking cancelled.")
        return

    ticket_id, ticket_number = create_ticket(
        service_id, customer_name, pickup, dropoff, distance, total_fare, payment_method
    )

    if ticket_id:
        print("\n  ✅ Booking successful!")
        print(f"  Ticket Number: {ticket_number}")
        print(f"  Total Paid: £{total_fare:.2f}")
    else:
        print("\n  ❌ Failed to create booking.")

def view_bookings_menu():
    """View all bookings."""
    print_header("All Taxi Bookings")

    tickets = get_all_tickets()

    if not tickets:
        print("\n  No bookings found.")
        return

    print(f"\n  Total bookings: {len(tickets)}\n")
    print(f"  {'Ticket':<15} {'Customer':<20} {'Service':<20} {'Fare':<10} {'Date':<12}")
    print("  " + "-" * 80)

    for ticket in tickets:
        customer = ticket['customer_name'][:17] + "..." if len(ticket['customer_name']) > 20 else ticket['customer_name']
        service = ticket['service_name'][:17] + "..." if len(ticket['service_name']) > 20 else ticket['service_name']
        print(f"  {ticket['ticket_number']:<15} {customer:<20} {service:<20} £{ticket['total_fare']:<9.2f} {ticket['booking_date']:<12}")

    print()

def view_ticket_menu():
    """View ticket details."""
    print_header("View Ticket")

    ticket_number = input("\n  Enter Ticket Number (or ID): ").strip()
    if not ticket_number:
        print("  ❌ Ticket number required.")
        return

    # Try to find by ticket number or ID
    ticket = None
    if ticket_number.isdigit():
        ticket = get_ticket_by_id(int(ticket_number))

    if not ticket:
        # Search by ticket number
        tickets = get_all_tickets()
        for t in tickets:
            if t['ticket_number'] == ticket_number:
                ticket = t
                break

    if not ticket:
        print("  ❌ Ticket not found.")
        return

    print_header("Ticket Details")
    print_ticket_details(ticket)

def statistics_menu():
    """Show booking statistics."""
    print_header("Taxi Booking Statistics")

    tickets = get_all_tickets()

    if not tickets:
        print("\n  No bookings available.")
        return

    total_revenue = sum(t['total_fare'] for t in tickets)
    total_distance = sum(t['distance_km'] for t in tickets)

    print(f"\n  Total Bookings: {len(tickets)}")
    print(f"  Total Revenue: £{total_revenue:.2f}")
    print(f"  Total Distance: {total_distance:.2f} km")

    # By service
    by_service = {}
    for t in tickets:
        service_name = t['service_name']
        if service_name not in by_service:
            by_service[service_name] = {'count': 0, 'revenue': 0}
        by_service[service_name]['count'] += 1
        by_service[service_name]['revenue'] += t['total_fare']

    print("\n  By Service:")
    for service, stats in sorted(by_service.items(), key=lambda x: x[1]['revenue'], reverse=True):
        print(f"    {service}: {stats['count']} bookings, £{stats['revenue']:.2f}")

    # By payment method
    by_payment = {}
    for t in tickets:
        method = t['payment_method']
        by_payment[method] = by_payment.get(method, 0) + 1

    print("\n  By Payment Method:")
    for method, count in sorted(by_payment.items()):
        print(f"    {method}: {count}")

    print()

def taxi_booking_menu():
    """Main taxi booking CLI menu."""
    init_taxi_database()

    while True:
        print_header("Taxi Booking System")
        print("\n  1. View Available Services")
        print("  2. Book a Taxi")
        print("  3. View All Bookings")
        print("  4. View Ticket Details")
        print("  5. View Statistics")
        print("  0. Return to Main Menu")

        choice = input("\n  Enter your choice: ").strip()

        if choice == '1':
            list_services_menu()
        elif choice == '2':
            book_taxi_menu()
        elif choice == '3':
            view_bookings_menu()
        elif choice == '4':
            view_ticket_menu()
        elif choice == '5':
            statistics_menu()
        elif choice == '0':
            print("\n  Returning to main menu...\n")
            break
        else:
            print("\n  ❌ Invalid choice.")

        if choice != '0':
            input("\n  Press Enter to continue...")

if __name__ == '__main__':
    taxi_booking_menu()
