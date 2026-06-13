#!/usr/bin/env python3
"""
Car Rental CLI - Vehicle Rental Management System
Features: Vehicle management, rental bookings, returns, payment processing
"""

from datetime import datetime, timedelta
from pathlib import Path

from education_system.university_system.core.paths import DEFAULT_DB_PATH

try:
    from education_system.university_system.infrastructure.database.db import get_connection
except ImportError:
    from education_system.university_system.infrastructure.database.db import sqlite3
    def get_connection():
        return sqlite3.connect(str(DEFAULT_DB_PATH))

try:
    from education_system.university_system.infrastructure.shared_context import get_current_user as get_user
except ImportError:
    get_user = None

try:
    from education_system.university_system.infrastructure.email.email_service import send_email_as_system
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    send_email_as_system = None

# Vehicle categories
VEHICLE_CATEGORIES = ["Economy", "Compact", "Mid-Size", "Full-Size", "SUV", "Luxury", "Van"]

# Rental statuses
RENTAL_STATUSES = ["Active", "Returned", "Overdue", "Cancelled"]

# Vehicle statuses
VEHICLE_STATUSES = ["Available", "Rented", "Maintenance", "Unavailable"]

CARRENTAL_SCHEMA = """
CREATE TABLE IF NOT EXISTS carrental_vehicles (
    vehicle_id INTEGER PRIMARY KEY AUTOINCREMENT,
    registration TEXT UNIQUE NOT NULL,
    make TEXT NOT NULL,
    model TEXT NOT NULL,
    year INTEGER,
    category TEXT NOT NULL,
    daily_rate REAL NOT NULL,
    status TEXT DEFAULT 'Available',
    mileage INTEGER DEFAULT 0,
    fuel_type TEXT,
    created_date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS carrental_rentals (
    rental_id INTEGER PRIMARY KEY AUTOINCREMENT,
    vehicle_id INTEGER NOT NULL,
    customer_name TEXT NOT NULL,
    customer_email TEXT,
    customer_phone TEXT,
    student_id TEXT,
    rental_date TEXT NOT NULL,
    return_date TEXT,
    expected_return_date TEXT NOT NULL,
    daily_rate REAL NOT NULL,
    total_cost REAL,
    payment_status TEXT DEFAULT 'Pending',
    rental_status TEXT DEFAULT 'Active',
    created_date TEXT NOT NULL,
    FOREIGN KEY (vehicle_id) REFERENCES carrental_vehicles (vehicle_id)
);

-- Car rental transactions now use unified 'transactions' table with source_type='car_rental'
"""

def init_carrental_database():
    """Initialize car rental database tables."""
    try:
        with get_connection() as conn:
            conn.executescript(CARRENTAL_SCHEMA)

            # Insert sample vehicles if none exist
            cursor = conn.execute("SELECT COUNT(*) FROM carrental_vehicles")
            if cursor.fetchone()[0] == 0:
                sample_vehicles = [
                    ("ABC123", "Toyota", "Corolla", 2022, "Economy", 35.00, "Available", 15000, "Petrol"),
                    ("XYZ789", "Honda", "Civic", 2023, "Compact", 40.00, "Available", 8000, "Hybrid"),
                    ("DEF456", "Ford", "Focus", 2021, "Compact", 38.00, "Available", 22000, "Petrol"),
                    ("GHI789", "Toyota", "Camry", 2022, "Mid-Size", 50.00, "Available", 12000, "Petrol"),
                    ("JKL012", "Nissan", "Altima", 2023, "Mid-Size", 48.00, "Available", 5000, "Hybrid"),
                    ("MNO345", "Honda", "Accord", 2022, "Full-Size", 55.00, "Available", 18000, "Petrol"),
                    ("PQR678", "Toyota", "RAV4", 2023, "SUV", 70.00, "Available", 10000, "Hybrid"),
                    ("STU901", "Ford", "Explorer", 2022, "SUV", 75.00, "Available", 14000, "Petrol"),
                    ("VWX234", "BMW", "3 Series", 2023, "Luxury", 120.00, "Available", 6000, "Petrol"),
                    ("YZA567", "Mercedes", "C-Class", 2023, "Luxury", 130.00, "Available", 7000, "Diesel"),
                    ("BCD890", "Ford", "Transit", 2021, "Van", 65.00, "Available", 30000, "Diesel"),
                ]
                for vehicle in sample_vehicles:
                    conn.execute("""
                        INSERT INTO carrental_vehicles
                        (registration, make, model, year, category, daily_rate, status, mileage, fuel_type, created_date)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (*vehicle, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

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

# ==================== VEHICLE MANAGEMENT ====================

def get_all_vehicles(category=None):
    """Get all vehicles, optionally filtered by category."""
    try:
        with get_connection() as conn:
            if category and category != 'All':
                cursor = conn.execute("""
                    SELECT vehicle_id, registration, make, model, year, category,
                           daily_rate, status, mileage
                    FROM carrental_vehicles WHERE category = ?
                    ORDER BY category, make, model
                """, (category,))
            else:
                cursor = conn.execute("""
                    SELECT vehicle_id, registration, make, model, year, category,
                           daily_rate, status, mileage
                    FROM carrental_vehicles
                    ORDER BY category, make, model
                """)

            vehicles = []
            for row in cursor.fetchall():
                vehicles.append({
                    'vehicle_id': row[0], 'registration': row[1], 'make': row[2],
                    'model': row[3], 'year': row[4], 'category': row[5],
                    'daily_rate': row[6], 'status': row[7], 'mileage': row[8]
                })
            return vehicles
    except Exception as e:
        print(f"Error getting vehicles: {e}")
        return []

def get_vehicle_by_id(vehicle_id):
    """Get specific vehicle by ID."""
    try:
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT vehicle_id, registration, make, model, year, category,
                       daily_rate, status, mileage, fuel_type
                FROM carrental_vehicles WHERE vehicle_id = ?
            """, (vehicle_id,))
            row = cursor.fetchone()
            if row:
                return {
                    'vehicle_id': row[0], 'registration': row[1], 'make': row[2],
                    'model': row[3], 'year': row[4], 'category': row[5],
                    'daily_rate': row[6], 'status': row[7], 'mileage': row[8],
                    'fuel_type': row[9]
                }
    except Exception as e:
        print(f"Error getting vehicle: {e}")
    return None

# ==================== RENTAL MANAGEMENT ====================

def create_rental(rental_data):
    """Create a new rental."""
    try:
        with get_connection() as conn:
            # Create rental
            conn.execute("""
                INSERT INTO carrental_rentals
                (vehicle_id, customer_name, customer_email, customer_phone, student_id,
                 rental_date, expected_return_date, daily_rate, total_cost,
                 payment_status, rental_status, created_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                rental_data['vehicle_id'], rental_data['customer_name'],
                rental_data.get('customer_email', ''), rental_data.get('customer_phone', ''),
                rental_data.get('student_id', ''), rental_data['rental_date'],
                rental_data['expected_return_date'], rental_data['daily_rate'],
                rental_data['total_cost'], rental_data['payment_status'],
                rental_data['rental_status'], rental_data['created_date']
            ))

            # Update vehicle status
            conn.execute("""
                UPDATE carrental_vehicles SET status = 'Rented'
                WHERE vehicle_id = ?
            """, (rental_data['vehicle_id'],))

            conn.commit()
        return True
    except Exception as e:
        print(f"Error creating rental: {e}")
        return False

def get_all_rentals(status=None):
    """Get all rentals, optionally filtered by status."""
    try:
        with get_connection() as conn:
            if status and status != 'All':
                cursor = conn.execute("""
                    SELECT r.rental_id, r.customer_name, v.make, v.model, v.registration,
                           r.rental_date, r.expected_return_date, r.total_cost, r.rental_status
                    FROM carrental_rentals r
                    JOIN carrental_vehicles v ON r.vehicle_id = v.vehicle_id
                    WHERE r.rental_status = ?
                    ORDER BY r.rental_date DESC
                """, (status,))
            else:
                cursor = conn.execute("""
                    SELECT r.rental_id, r.customer_name, v.make, v.model, v.registration,
                           r.rental_date, r.expected_return_date, r.total_cost, r.rental_status
                    FROM carrental_rentals r
                    JOIN carrental_vehicles v ON r.vehicle_id = v.vehicle_id
                    ORDER BY r.rental_date DESC
                """)

            rentals = []
            for row in cursor.fetchall():
                rentals.append({
                    'rental_id': row[0], 'customer_name': row[1], 'make': row[2],
                    'model': row[3], 'registration': row[4], 'rental_date': row[5],
                    'expected_return_date': row[6], 'total_cost': row[7], 'rental_status': row[8]
                })
            return rentals
    except Exception as e:
        print(f"Error getting rentals: {e}")
        return []

def return_vehicle(rental_id):
    """Process vehicle return."""
    try:
        with get_connection() as conn:
            # Get rental details
            cursor = conn.execute("""
                SELECT vehicle_id, expected_return_date, daily_rate
                FROM carrental_rentals WHERE rental_id = ?
            """, (rental_id,))
            row = cursor.fetchone()
            if not row:
                return False

            vehicle_id = row[0]

            # Update rental
            conn.execute("""
                UPDATE carrental_rentals
                SET rental_status = 'Returned',
                    return_date = ?
                WHERE rental_id = ?
            """, (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), rental_id))

            # Update vehicle status
            conn.execute("""
                UPDATE carrental_vehicles
                SET status = 'Available'
                WHERE vehicle_id = ?
            """, (vehicle_id,))

            conn.commit()
        return True
    except Exception as e:
        print(f"Error returning vehicle: {e}")
        return False

# ==================== CLI INTERFACE ====================

def print_header(title):
    """Print formatted header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def list_vehicles_menu():
    """List all vehicles."""
    print_header("Car Rental - Vehicle Fleet")

    print("\n  Filter by category:")
    print("    0. All")
    for i, cat in enumerate(VEHICLE_CATEGORIES, 1):
        print(f"    {i}. {cat}")

    choice = input("\n  Select category (0-7): ").strip()
    if choice == '0':
        category = None
    elif choice.isdigit() and 1 <= int(choice) <= len(VEHICLE_CATEGORIES):
        category = VEHICLE_CATEGORIES[int(choice) - 1]
    else:
        category = None

    vehicles = get_all_vehicles(category)

    if not vehicles:
        print("\n  No vehicles found.")
        return

    print(f"\n  Total vehicles: {len(vehicles)}\n")
    print(f"  {'ID':<5} {'Registration':<12} {'Make':<12} {'Model':<15} {'Category':<12} {'Rate/Day':<10} {'Status':<12}")
    print("  " + "-" * 90)

    for vehicle in vehicles:
        print(f"  {vehicle['vehicle_id']:<5} {vehicle['registration']:<12} {vehicle['make']:<12} {vehicle['model']:<15} {vehicle['category']:<12} £{vehicle['daily_rate']:<9.2f} {vehicle['status']:<12}")

    print()

def book_rental_menu():
    """Create a new rental booking."""
    print_header("Book Vehicle Rental")

    current_user = get_current_user()
    default_name = current_user.get('name', '')

    # Show available vehicles
    available_vehicles = [v for v in get_all_vehicles() if v['status'] == 'Available']

    if not available_vehicles:
        print("\n  ❌ No vehicles currently available.")
        return

    print("\n  Available Vehicles:")
    for vehicle in available_vehicles[:10]:
        print(f"    {vehicle['vehicle_id']}. {vehicle['make']} {vehicle['model']} ({vehicle['category']}) - £{vehicle['daily_rate']:.2f}/day")

    vehicle_id = input("\n  Select vehicle ID: ").strip()
    if not vehicle_id.isdigit():
        print("  ❌ Invalid vehicle ID.")
        return

    vehicle = get_vehicle_by_id(int(vehicle_id))
    if not vehicle or vehicle['status'] != 'Available':
        print("  ❌ Vehicle not available.")
        return

    customer_name = input(f"  Customer name [{default_name}]: ").strip() or default_name
    if not customer_name:
        print("  ❌ Customer name is required.")
        return

    customer_email = input("  Customer email (optional): ").strip()
    customer_phone = input("  Customer phone (optional): ").strip()
    student_id = input("  Student ID (if applicable): ").strip()

    rental_days = input("  Number of rental days: ").strip()
    if not rental_days.isdigit() or int(rental_days) < 1:
        print("  ❌ Invalid number of days.")
        return

    rental_days = int(rental_days)
    total_cost = vehicle['daily_rate'] * rental_days

    print(f"\n  Rental Summary:")
    print(f"    Vehicle: {vehicle['make']} {vehicle['model']}")
    print(f"    Daily Rate: £{vehicle['daily_rate']:.2f}")
    print(f"    Duration: {rental_days} days")
    print(f"    Total Cost: £{total_cost:.2f}")

    confirm = input("\n  Confirm booking? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("  Booking cancelled.")
        return

    rental_data = {
        'vehicle_id': int(vehicle_id),
        'customer_name': customer_name,
        'customer_email': customer_email,
        'customer_phone': customer_phone,
        'student_id': student_id,
        'rental_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'expected_return_date': (datetime.now() + timedelta(days=rental_days)).strftime('%Y-%m-%d'),
        'daily_rate': vehicle['daily_rate'],
        'total_cost': total_cost,
        'payment_status': 'Pending',
        'rental_status': 'Active',
        'created_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

    if create_rental(rental_data):
        print(f"\n  ✅ Rental booked successfully!")
        print(f"  Total: £{total_cost:.2f}")
    else:
        print("\n  ❌ Failed to create rental.")

def view_rentals_menu():
    """View all rentals."""
    print_header("Car Rental - All Rentals")

    print("\n  Filter by status:")
    print("    0. All")
    for i, status in enumerate(RENTAL_STATUSES, 1):
        print(f"    {i}. {status}")

    choice = input("\n  Select status (0-4): ").strip()
    if choice == '0':
        status = None
    elif choice.isdigit() and 1 <= int(choice) <= len(RENTAL_STATUSES):
        status = RENTAL_STATUSES[int(choice) - 1]
    else:
        status = None

    rentals = get_all_rentals(status)

    if not rentals:
        print("\n  No rentals found.")
        return

    print(f"\n  Total rentals: {len(rentals)}\n")
    print(f"  {'ID':<5} {'Customer':<20} {'Vehicle':<25} {'Rental Date':<12} {'Return':<12} {'Cost':<10} {'Status':<10}")
    print("  " + "-" * 100)

    for rental in rentals:
        customer = rental['customer_name'][:17] + "..." if len(rental['customer_name']) > 20 else rental['customer_name']
        vehicle = f"{rental['make']} {rental['model']} ({rental['registration']})"
        vehicle = vehicle[:22] + "..." if len(vehicle) > 25 else vehicle
        print(f"  {rental['rental_id']:<5} {customer:<20} {vehicle:<25} {rental['rental_date'][:10]:<12} {rental['expected_return_date'][:10]:<12} £{rental['total_cost']:<9.2f} {rental['rental_status']:<10}")

    print()

def return_vehicle_menu():
    """Process vehicle return."""
    print_header("Return Vehicle")

    rental_id = input("\n  Enter Rental ID: ").strip()
    if not rental_id.isdigit():
        print("  ❌ Invalid Rental ID.")
        return

    confirm = input(f"  Confirm return of rental #{rental_id}? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("  Return cancelled.")
        return

    if return_vehicle(int(rental_id)):
        print("\n  ✅ Vehicle returned successfully!")
    else:
        print("\n  ❌ Failed to process return.")

def statistics_menu():
    """Show rental statistics."""
    print_header("Car Rental Statistics")

    vehicles = get_all_vehicles()
    rentals = get_all_rentals()

    if not vehicles and not rentals:
        print("\n  No data available.")
        return

    print(f"\n  Total Vehicles: {len(vehicles)}")
    print(f"  Total Rentals: {len(rentals)}")

    # Vehicle status
    by_status = {}
    for vehicle in vehicles:
        by_status[vehicle['status']] = by_status.get(vehicle['status'], 0) + 1

    print("\n  Vehicles by Status:")
    for status, count in sorted(by_status.items()):
        print(f"    {status}: {count}")

    # Rental revenue
    total_revenue = sum(r['total_cost'] for r in rentals)
    print(f"\n  Total Revenue: £{total_revenue:.2f}")

    # Popular categories
    by_category = {}
    for vehicle in vehicles:
        by_category[vehicle['category']] = by_category.get(vehicle['category'], 0) + 1

    print("\n  Vehicles by Category:")
    for category, count in sorted(by_category.items()):
        print(f"    {category}: {count}")

    print()

def carrental_menu():
    """Main car rental CLI menu."""
    init_carrental_database()

    while True:
        print_header("Car Rental System")
        print("\n  1. View Vehicle Fleet")
        print("  2. Book Rental")
        print("  3. View All Rentals")
        print("  4. Return Vehicle")
        print("  5. View Statistics")
        print("  0. Return to Main Menu")

        choice = input("\n  Enter your choice: ").strip()

        if choice == '1':
            list_vehicles_menu()
        elif choice == '2':
            book_rental_menu()
        elif choice == '3':
            view_rentals_menu()
        elif choice == '4':
            return_vehicle_menu()
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
    carrental_menu()
