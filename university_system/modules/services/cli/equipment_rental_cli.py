#!/usr/bin/env python3
"""
Equipment Rental CLI - Equipment Rental Management System
Features: Equipment inventory, rental bookings, returns, payment processing
"""

from datetime import datetime, timedelta
from pathlib import Path

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


# Equipment categories
EQUIPMENT_CATEGORIES = ["Camera", "Laptop", "Projector", "Audio", "Lab Equipment", "Sports", "Tools", "Other"]

# Rental statuses
RENTAL_STATUSES = ["Active", "Returned", "Overdue", "Cancelled"]

# Equipment conditions
EQUIPMENT_CONDITIONS = ["Excellent", "Good", "Fair", "Needs Repair"]


EQUIPMENT_RENTAL_SCHEMA = """
CREATE TABLE IF NOT EXISTS equipment_inventory (
    equipment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment_code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT,
    daily_rate REAL NOT NULL,
    quantity_available INTEGER DEFAULT 1,
    quantity_total INTEGER DEFAULT 1,
    condition TEXT DEFAULT 'Good',
    created_date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS equipment_rentals (
    rental_id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment_id INTEGER NOT NULL,
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
    FOREIGN KEY (equipment_id) REFERENCES equipment_inventory (equipment_id)
);

CREATE TABLE IF NOT EXISTS equipment_transactions (
    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    rental_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    payment_method TEXT,
    transaction_date TEXT NOT NULL,
    reference_number TEXT,
    FOREIGN KEY (rental_id) REFERENCES equipment_rentals (rental_id)
);
"""


def init_equipment_database():
    """Initialize equipment rental database tables."""
    try:
        with get_connection() as conn:
            conn.executescript(EQUIPMENT_RENTAL_SCHEMA)

            # Insert sample equipment if none exist
            cursor = conn.execute("SELECT COUNT(*) FROM equipment_inventory")
            if cursor.fetchone()[0] == 0:
                sample_equipment = [
                    ("CAM001", "Canon EOS R5", "Camera", "Professional mirrorless camera", 50.00, 3, 3, "Excellent"),
                    ("CAM002", "Sony A7 III", "Camera", "Full-frame mirrorless camera", 45.00, 2, 2, "Good"),
                    ("LAP001", "MacBook Pro 16\"", "Laptop", "M2 Max processor, 32GB RAM", 35.00, 5, 5, "Excellent"),
                    ("LAP002", "Dell XPS 15", "Laptop", "Intel i7, 16GB RAM", 30.00, 4, 4, "Good"),
                    ("PRJ001", "Epson PowerLite", "Projector", "4K projector 3000 lumens", 25.00, 6, 6, "Good"),
                    ("PRJ002", "BenQ TH685", "Projector", "1080p projector 3500 lumens", 20.00, 4, 4, "Excellent"),
                    ("AUD001", "Shure SM7B Microphone", "Audio", "Professional broadcast microphone", 15.00, 8, 8, "Excellent"),
                    ("AUD002", "Zoom H6 Recorder", "Audio", "6-track portable recorder", 18.00, 4, 4, "Good"),
                    ("LAB001", "Oscilloscope", "Lab Equipment", "Digital storage oscilloscope", 40.00, 2, 2, "Good"),
                    ("LAB002", "Microscope", "Lab Equipment", "Digital microscope 1000x", 30.00, 3, 3, "Excellent"),
                    ("SPT001", "Tennis Racket Set", "Sports", "Professional tennis rackets", 5.00, 10, 10, "Good"),
                    ("SPT002", "Basketball", "Sports", "Official size basketball", 3.00, 15, 15, "Good"),
                ]
                for equipment in sample_equipment:
                    conn.execute("""
                        INSERT INTO equipment_inventory
                        (equipment_code, name, category, description, daily_rate, quantity_available, quantity_total, condition, created_date)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (*equipment, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

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


# ==================== EQUIPMENT MANAGEMENT ====================

def get_all_equipment(category=None):
    """Get all equipment, optionally filtered by category."""
    try:
        with get_connection() as conn:
            if category and category != 'All':
                cursor = conn.execute("""
                    SELECT equipment_id, equipment_code, name, category, daily_rate,
                           quantity_available, quantity_total, condition
                    FROM equipment_inventory WHERE category = ?
                    ORDER BY category, name
                """, (category,))
            else:
                cursor = conn.execute("""
                    SELECT equipment_id, equipment_code, name, category, daily_rate,
                           quantity_available, quantity_total, condition
                    FROM equipment_inventory
                    ORDER BY category, name
                """)

            equipment = []
            for row in cursor.fetchall():
                equipment.append({
                    'equipment_id': row[0], 'equipment_code': row[1], 'name': row[2],
                    'category': row[3], 'daily_rate': row[4], 'quantity_available': row[5],
                    'quantity_total': row[6], 'condition': row[7]
                })
            return equipment
    except Exception as e:
        print(f"Error getting equipment: {e}")
        return []


def get_equipment_by_id(equipment_id):
    """Get specific equipment by ID."""
    try:
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT equipment_id, equipment_code, name, category, description,
                       daily_rate, quantity_available, quantity_total, condition
                FROM equipment_inventory WHERE equipment_id = ?
            """, (equipment_id,))
            row = cursor.fetchone()
            if row:
                return {
                    'equipment_id': row[0], 'equipment_code': row[1], 'name': row[2],
                    'category': row[3], 'description': row[4], 'daily_rate': row[5],
                    'quantity_available': row[6], 'quantity_total': row[7], 'condition': row[8]
                }
    except Exception as e:
        print(f"Error getting equipment: {e}")
    return None


# ==================== RENTAL MANAGEMENT ====================

def create_rental(rental_data):
    """Create a new rental."""
    try:
        with get_connection() as conn:
            # Create rental
            conn.execute("""
                INSERT INTO equipment_rentals
                (equipment_id, customer_name, customer_email, customer_phone, student_id,
                 rental_date, expected_return_date, daily_rate, total_cost,
                 payment_status, rental_status, created_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                rental_data['equipment_id'], rental_data['customer_name'],
                rental_data.get('customer_email', ''), rental_data.get('customer_phone', ''),
                rental_data.get('student_id', ''), rental_data['rental_date'],
                rental_data['expected_return_date'], rental_data['daily_rate'],
                rental_data['total_cost'], rental_data['payment_status'],
                rental_data['rental_status'], rental_data['created_date']
            ))

            # Decrease available quantity
            conn.execute("""
                UPDATE equipment_inventory
                SET quantity_available = quantity_available - 1
                WHERE equipment_id = ?
            """, (rental_data['equipment_id'],))

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
                    SELECT r.rental_id, r.customer_name, e.name, e.equipment_code,
                           r.rental_date, r.expected_return_date, r.total_cost, r.rental_status
                    FROM equipment_rentals r
                    JOIN equipment_inventory e ON r.equipment_id = e.equipment_id
                    WHERE r.rental_status = ?
                    ORDER BY r.rental_date DESC
                """, (status,))
            else:
                cursor = conn.execute("""
                    SELECT r.rental_id, r.customer_name, e.name, e.equipment_code,
                           r.rental_date, r.expected_return_date, r.total_cost, r.rental_status
                    FROM equipment_rentals r
                    JOIN equipment_inventory e ON r.equipment_id = e.equipment_id
                    ORDER BY r.rental_date DESC
                """)

            rentals = []
            for row in cursor.fetchall():
                rentals.append({
                    'rental_id': row[0], 'customer_name': row[1], 'equipment_name': row[2],
                    'equipment_code': row[3], 'rental_date': row[4],
                    'expected_return_date': row[5], 'total_cost': row[6], 'rental_status': row[7]
                })
            return rentals
    except Exception as e:
        print(f"Error getting rentals: {e}")
        return []


def return_equipment(rental_id):
    """Process equipment return."""
    try:
        with get_connection() as conn:
            # Get rental details
            cursor = conn.execute("""
                SELECT equipment_id
                FROM equipment_rentals WHERE rental_id = ?
            """, (rental_id,))
            row = cursor.fetchone()
            if not row:
                return False

            equipment_id = row[0]

            # Update rental
            conn.execute("""
                UPDATE equipment_rentals
                SET rental_status = 'Returned',
                    return_date = ?
                WHERE rental_id = ?
            """, (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), rental_id))

            # Increase available quantity
            conn.execute("""
                UPDATE equipment_inventory
                SET quantity_available = quantity_available + 1
                WHERE equipment_id = ?
            """, (equipment_id,))

            conn.commit()
        return True
    except Exception as e:
        print(f"Error returning equipment: {e}")
        return False


# ==================== CLI INTERFACE ====================

def print_header(title):
    """Print formatted header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def list_equipment_menu():
    """List all equipment."""
    print_header("Equipment Rental - Inventory")

    print("\n  Filter by category:")
    print("    0. All")
    for i, cat in enumerate(EQUIPMENT_CATEGORIES, 1):
        print(f"    {i}. {cat}")

    choice = input(f"\n  Select category (0-{len(EQUIPMENT_CATEGORIES)}): ").strip()
    if choice == '0':
        category = None
    elif choice.isdigit() and 1 <= int(choice) <= len(EQUIPMENT_CATEGORIES):
        category = EQUIPMENT_CATEGORIES[int(choice) - 1]
    else:
        category = None

    equipment = get_all_equipment(category)

    if not equipment:
        print("\n  No equipment found.")
        return

    print(f"\n  Total items: {len(equipment)}\n")
    print(f"  {'ID':<5} {'Code':<10} {'Name':<30} {'Category':<15} {'Rate/Day':<10} {'Available':<10}")
    print("  " + "-" * 90)

    for item in equipment:
        name = item['name'][:27] + "..." if len(item['name']) > 30 else item['name']
        availability = f"{item['quantity_available']}/{item['quantity_total']}"
        print(f"  {item['equipment_id']:<5} {item['equipment_code']:<10} {name:<30} {item['category']:<15} £{item['daily_rate']:<9.2f} {availability:<10}")

    print()


def book_rental_menu():
    """Create a new rental booking."""
    print_header("Book Equipment Rental")

    current_user = get_current_user()
    default_name = current_user.get('name', '')

    # Show available equipment
    available_equipment = [e for e in get_all_equipment() if e['quantity_available'] > 0]

    if not available_equipment:
        print("\n  ❌ No equipment currently available.")
        return

    print("\n  Available Equipment:")
    for item in available_equipment[:15]:
        print(f"    {item['equipment_id']}. {item['name']} ({item['category']}) - £{item['daily_rate']:.2f}/day [{item['quantity_available']} available]")

    equipment_id = input("\n  Select equipment ID: ").strip()
    if not equipment_id.isdigit():
        print("  ❌ Invalid equipment ID.")
        return

    equipment = get_equipment_by_id(int(equipment_id))
    if not equipment or equipment['quantity_available'] <= 0:
        print("  ❌ Equipment not available.")
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
    total_cost = equipment['daily_rate'] * rental_days

    print(f"\n  Rental Summary:")
    print(f"    Equipment: {equipment['name']}")
    print(f"    Daily Rate: £{equipment['daily_rate']:.2f}")
    print(f"    Duration: {rental_days} days")
    print(f"    Total Cost: £{total_cost:.2f}")

    confirm = input("\n  Confirm booking? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("  Booking cancelled.")
        return

    rental_data = {
        'equipment_id': int(equipment_id),
        'customer_name': customer_name,
        'customer_email': customer_email,
        'customer_phone': customer_phone,
        'student_id': student_id,
        'rental_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'expected_return_date': (datetime.now() + timedelta(days=rental_days)).strftime('%Y-%m-%d'),
        'daily_rate': equipment['daily_rate'],
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
    print_header("Equipment Rental - All Rentals")

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
    print(f"  {'ID':<5} {'Customer':<20} {'Equipment':<30} {'Rental Date':<12} {'Return':<12} {'Cost':<10} {'Status':<10}")
    print("  " + "-" * 105)

    for rental in rentals:
        customer = rental['customer_name'][:17] + "..." if len(rental['customer_name']) > 20 else rental['customer_name']
        equipment = rental['equipment_name'][:27] + "..." if len(rental['equipment_name']) > 30 else rental['equipment_name']
        print(f"  {rental['rental_id']:<5} {customer:<20} {equipment:<30} {rental['rental_date'][:10]:<12} {rental['expected_return_date'][:10]:<12} £{rental['total_cost']:<9.2f} {rental['rental_status']:<10}")

    print()


def return_equipment_menu():
    """Process equipment return."""
    print_header("Return Equipment")

    rental_id = input("\n  Enter Rental ID: ").strip()
    if not rental_id.isdigit():
        print("  ❌ Invalid Rental ID.")
        return

    confirm = input(f"  Confirm return of rental #{rental_id}? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("  Return cancelled.")
        return

    if return_equipment(int(rental_id)):
        print("\n  ✅ Equipment returned successfully!")
    else:
        print("\n  ❌ Failed to process return.")


def statistics_menu():
    """Show rental statistics."""
    print_header("Equipment Rental Statistics")

    equipment = get_all_equipment()
    rentals = get_all_rentals()

    if not equipment and not rentals:
        print("\n  No data available.")
        return

    total_items = sum(e['quantity_total'] for e in equipment)
    total_available = sum(e['quantity_available'] for e in equipment)

    print(f"\n  Total Equipment Items: {total_items}")
    print(f"  Currently Available: {total_available}")
    print(f"  Total Rentals: {len(rentals)}")

    # Equipment by category
    by_category = {}
    for item in equipment:
        by_category[item['category']] = by_category.get(item['category'], 0) + item['quantity_total']

    print("\n  Equipment by Category:")
    for category, count in sorted(by_category.items()):
        print(f"    {category}: {count}")

    # Rental revenue
    total_revenue = sum(r['total_cost'] for r in rentals)
    print(f"\n  Total Revenue: £{total_revenue:.2f}")

    print()


def equipment_rental_menu():
    """Main equipment rental CLI menu."""
    init_equipment_database()

    while True:
        print_header("Equipment Rental System")
        print("\n  1. View Equipment Inventory")
        print("  2. Book Rental")
        print("  3. View All Rentals")
        print("  4. Return Equipment")
        print("  5. View Statistics")
        print("  0. Return to Main Menu")

        choice = input("\n  Enter your choice: ").strip()

        if choice == '1':
            list_equipment_menu()
        elif choice == '2':
            book_rental_menu()
        elif choice == '3':
            view_rentals_menu()
        elif choice == '4':
            return_equipment_menu()
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
    equipment_rental_menu()
