#!/usr/bin/env python3
"""
Legal Services CLI - University Legal Aid Center Management
Features: Case management, consultations, document tracking, billing
"""

from datetime import datetime
from pathlib import Path

from education_system.university_system.core.sql_safety import validate_identifier

try:
    from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
except ImportError:
    DEFAULT_DB_PATH = Path(__file__).resolve().parents[3] / "data" / "db_files" / "student_records.db"

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

# Case types
CASE_TYPES = [
    "Contract Dispute", "Landlord/Tenant", "Employment Issue", "Academic Matter",
    "Criminal Defense", "Family Law", "Immigration", "Consumer Protection",
    "Debt Collection", "Small Claims", "Civil Rights", "Other"
]

# Case statuses
CASE_STATUSES = ["Pending", "In Progress", "Awaiting Documents", "Resolved", "Closed"]

# Consultation statuses
CONSULTATION_STATUSES = ["Scheduled", "Completed", "Cancelled", "No-Show"]

# Payment statuses
PAYMENT_STATUSES = ["Pending", "Paid", "Partial", "Waived"]

LEGAL_SERVICES_SCHEMA = """
CREATE TABLE IF NOT EXISTS legal_cases (
    case_id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_number TEXT UNIQUE NOT NULL,
    client_name TEXT NOT NULL,
    client_email TEXT,
    client_phone TEXT,
    student_id TEXT,
    case_type TEXT NOT NULL,
    status TEXT DEFAULT 'Pending',
    description TEXT,
    assigned_attorney TEXT,
    created_date TEXT NOT NULL,
    updated_date TEXT NOT NULL,
    closed_date TEXT
);

CREATE TABLE IF NOT EXISTS legal_consultations (
    consultation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER,
    client_name TEXT NOT NULL,
    client_email TEXT,
    consultation_date TEXT NOT NULL,
    consultation_time TEXT NOT NULL,
    status TEXT DEFAULT 'Scheduled',
    notes TEXT,
    attorney TEXT,
    created_date TEXT NOT NULL,
    FOREIGN KEY (case_id) REFERENCES legal_cases (case_id)
);

CREATE TABLE IF NOT EXISTS legal_documents (
    document_id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER NOT NULL,
    document_name TEXT NOT NULL,
    document_type TEXT,
    file_path TEXT,
    uploaded_by TEXT,
    upload_date TEXT NOT NULL,
    FOREIGN KEY (case_id) REFERENCES legal_cases (case_id)
);

CREATE TABLE IF NOT EXISTS legal_payments (
    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    payment_method TEXT,
    payment_status TEXT DEFAULT 'Pending',
    payment_date TEXT,
    created_date TEXT NOT NULL,
    FOREIGN KEY (case_id) REFERENCES legal_cases (case_id)
);
"""

def init_legal_database():
    """Initialize legal services database tables."""
    try:
        with get_connection() as conn:
            conn.executescript(LEGAL_SERVICES_SCHEMA)
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

def generate_case_number():
    """Generate unique case number."""
    return f"LEGAL-{datetime.now().strftime('%Y%m%d%H%M%S')}"

# ==================== CASE MANAGEMENT ====================

def create_case(case_data):
    """Create a new legal case."""
    try:
        with get_connection() as conn:
            conn.execute("""
                INSERT INTO legal_cases
                (case_number, client_name, client_email, client_phone, student_id,
                 case_type, status, description, assigned_attorney, created_date, updated_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                case_data['case_number'], case_data['client_name'], case_data.get('client_email', ''),
                case_data.get('client_phone', ''), case_data.get('student_id', ''),
                case_data['case_type'], case_data['status'], case_data.get('description', ''),
                case_data.get('assigned_attorney', 'Unassigned'), case_data['created_date'],
                case_data['updated_date']
            ))
            conn.commit()
        return True
    except Exception as e:
        print(f"Error creating case: {e}")
        return False

def get_all_cases():
    """Get all legal cases."""
    try:
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT case_id, case_number, client_name, case_type, status,
                       assigned_attorney, created_date
                FROM legal_cases
                ORDER BY created_date DESC
            """)
            cases = []
            for row in cursor.fetchall():
                cases.append({
                    'case_id': row[0], 'case_number': row[1], 'client_name': row[2],
                    'case_type': row[3], 'status': row[4], 'assigned_attorney': row[5],
                    'created_date': row[6]
                })
            return cases
    except Exception as e:
        print(f"Error getting cases: {e}")
        return []

def get_case_by_id(case_id):
    """Get specific case by ID."""
    try:
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT case_id, case_number, client_name, client_email, client_phone,
                       student_id, case_type, status, description, assigned_attorney,
                       created_date, closed_date
                FROM legal_cases WHERE case_id = ?
            """, (case_id,))
            row = cursor.fetchone()
            if row:
                return {
                    'case_id': row[0], 'case_number': row[1], 'client_name': row[2],
                    'client_email': row[3], 'client_phone': row[4], 'student_id': row[5],
                    'case_type': row[6], 'status': row[7], 'description': row[8],
                    'assigned_attorney': row[9], 'created_date': row[10], 'closed_date': row[11]
                }
    except Exception as e:
        print(f"Error getting case: {e}")
    return None

_CASE_ALLOWED_COLUMNS = frozenset({
    'case_number', 'client_name', 'client_email', 'client_phone', 'student_id',
    'case_type', 'status', 'description', 'assigned_attorney', 'closed_date',
})

def update_case(case_id, updates):
    """Update case fields."""
    try:
        fields = []
        values = []
        for key, value in updates.items():
            if key not in _CASE_ALLOWED_COLUMNS:
                raise ValueError(f"Invalid column name: {key}")
            validate_identifier(key, "column")
            fields.append(f"{key} = ?")
            values.append(value)

        fields.append("updated_date = ?")
        values.append(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        values.append(case_id)

        with get_connection() as conn:
            conn.execute(f"""
                UPDATE legal_cases
                SET {', '.join(fields)}
                WHERE case_id = ?
            """, values)
            conn.commit()
        return True
    except Exception as e:
        print(f"Error updating case: {e}")
        return False

# ==================== CONSULTATIONS ====================

def schedule_consultation(consult_data):
    """Schedule a new consultation."""
    try:
        with get_connection() as conn:
            conn.execute("""
                INSERT INTO legal_consultations
                (case_id, client_name, client_email, consultation_date, consultation_time,
                 status, notes, attorney, created_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                consult_data.get('case_id'), consult_data['client_name'],
                consult_data.get('client_email', ''), consult_data['consultation_date'],
                consult_data['consultation_time'], consult_data['status'],
                consult_data.get('notes', ''), consult_data.get('attorney', 'TBD'),
                consult_data['created_date']
            ))
            conn.commit()
        return True
    except Exception as e:
        print(f"Error scheduling consultation: {e}")
        return False

def get_all_consultations():
    """Get all consultations."""
    try:
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT consultation_id, case_id, client_name, consultation_date,
                       consultation_time, status, attorney
                FROM legal_consultations
                ORDER BY consultation_date DESC, consultation_time DESC
            """)
            consultations = []
            for row in cursor.fetchall():
                consultations.append({
                    'consultation_id': row[0], 'case_id': row[1], 'client_name': row[2],
                    'consultation_date': row[3], 'consultation_time': row[4],
                    'status': row[5], 'attorney': row[6]
                })
            return consultations
    except Exception as e:
        print(f"Error getting consultations: {e}")
        return []

# ==================== CLI INTERFACE ====================

def print_header(title):
    """Print formatted header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def print_case_summary(case):
    """Print case summary."""
    print(f"\n  Case #: {case['case_number']}")
    print(f"  Client: {case['client_name']}")
    print(f"  Type: {case['case_type']} | Status: {case['status']}")
    print(f"  Attorney: {case['assigned_attorney']}")
    print(f"  Date: {case['created_date']}")

def print_case_details(case):
    """Print full case details."""
    print_header(f"Case Details: {case['case_number']}")
    print(f"\n  Client Name: {case['client_name']}")
    print(f"  Email: {case.get('client_email', 'N/A')}")
    print(f"  Phone: {case.get('client_phone', 'N/A')}")
    print(f"  Student ID: {case.get('student_id', 'N/A')}")
    print(f"\n  Case Type: {case['case_type']}")
    print(f"  Status: {case['status']}")
    print(f"  Assigned Attorney: {case['assigned_attorney']}")
    print(f"\n  Description: {case.get('description', 'N/A')}")
    print(f"\n  Created: {case['created_date']}")
    if case.get('closed_date'):
        print(f"  Closed: {case['closed_date']}")

def list_cases_menu():
    """List all cases."""
    print_header("Legal Services - All Cases")

    cases = get_all_cases()

    if not cases:
        print("\n  No cases found.")
        return

    print(f"\n  Total cases: {len(cases)}\n")
    print(f"  {'Case #':<20} {'Client':<25} {'Type':<20} {'Status':<15}")
    print("  " + "-" * 85)

    for case in cases:
        client = case['client_name'][:22] + "..." if len(case['client_name']) > 25 else case['client_name']
        case_type = case['case_type'][:17] + "..." if len(case['case_type']) > 20 else case['case_type']
        print(f"  {case['case_number']:<20} {client:<25} {case_type:<20} {case['status']:<15}")

    print()

def view_case_menu():
    """View case details."""
    print_header("View Case")

    case_id = input("\n  Enter Case ID: ").strip()
    if not case_id.isdigit():
        print("  ❌ Invalid Case ID.")
        return

    case = get_case_by_id(int(case_id))
    if not case:
        print(f"  ❌ Case not found.")
        return

    print_case_details(case)

def create_case_menu():
    """Create new case."""
    print_header("Create New Legal Case")

    client_name = input("\n  Client name: ").strip()
    if not client_name:
        print("  ❌ Client name is required.")
        return

    client_email = input("  Client email (optional): ").strip()
    client_phone = input("  Client phone (optional): ").strip()
    student_id = input("  Student ID (if applicable): ").strip()

    print("\n  Case Types:")
    for i, case_type in enumerate(CASE_TYPES, 1):
        print(f"    {i}. {case_type}")

    type_choice = input(f"\n  Select case type (1-{len(CASE_TYPES)}): ").strip()
    if type_choice.isdigit() and 1 <= int(type_choice) <= len(CASE_TYPES):
        case_type = CASE_TYPES[int(type_choice) - 1]
    else:
        case_type = "Other"

    description = input("  Case description: ").strip()
    attorney = input("  Assign to attorney (optional): ").strip()

    case_data = {
        'case_number': generate_case_number(),
        'client_name': client_name,
        'client_email': client_email,
        'client_phone': client_phone,
        'student_id': student_id,
        'case_type': case_type,
        'status': 'Pending',
        'description': description,
        'assigned_attorney': attorney or 'Unassigned',
        'created_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'updated_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

    if create_case(case_data):
        print(f"\n  ✅ Case {case_data['case_number']} created successfully!")
    else:
        print("\n  ❌ Failed to create case.")

def update_case_menu():
    """Update case status."""
    print_header("Update Case")

    case_id = input("\n  Enter Case ID: ").strip()
    if not case_id.isdigit():
        print("  ❌ Invalid Case ID.")
        return

    case = get_case_by_id(int(case_id))
    if not case:
        print(f"  ❌ Case not found.")
        return

    print_case_summary(case)

    print("\n  Update:")
    print("    1. Status")
    print("    2. Assign Attorney")
    print("    3. Close Case")
    print("    0. Cancel")

    choice = input("\n  Enter choice: ").strip()

    if choice == '1':
        print("\n  Status:")
        for i, status in enumerate(CASE_STATUSES, 1):
            print(f"    {i}. {status}")

        status_choice = input(f"  Select status (1-{len(CASE_STATUSES)}): ").strip()
        if status_choice.isdigit() and 1 <= int(status_choice) <= len(CASE_STATUSES):
            new_status = CASE_STATUSES[int(status_choice) - 1]
            if update_case(int(case_id), {'status': new_status}):
                print(f"\n  ✅ Status updated to: {new_status}")

    elif choice == '2':
        attorney = input("  Attorney name: ").strip()
        if attorney and update_case(int(case_id), {'assigned_attorney': attorney}):
            print(f"\n  ✅ Assigned to: {attorney}")

    elif choice == '3':
        confirm = input("  Close this case? (yes/no): ").strip().lower()
        if confirm == 'yes':
            updates = {
                'status': 'Closed',
                'closed_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            if update_case(int(case_id), updates):
                print("\n  ✅ Case closed.")

def schedule_consultation_menu():
    """Schedule a consultation."""
    print_header("Schedule Consultation")

    client_name = input("\n  Client name: ").strip()
    if not client_name:
        print("  ❌ Client name is required.")
        return

    client_email = input("  Client email (optional): ").strip()
    case_id = input("  Link to Case ID (optional): ").strip()

    date = input("  Consultation date (YYYY-MM-DD): ").strip()
    time = input("  Consultation time (HH:MM): ").strip()

    attorney = input("  Attorney (optional): ").strip()
    notes = input("  Notes (optional): ").strip()

    consult_data = {
        'case_id': int(case_id) if case_id.isdigit() else None,
        'client_name': client_name,
        'client_email': client_email,
        'consultation_date': date,
        'consultation_time': time,
        'status': 'Scheduled',
        'attorney': attorney or 'TBD',
        'notes': notes,
        'created_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

    if schedule_consultation(consult_data):
        print("\n  ✅ Consultation scheduled successfully!")
    else:
        print("\n  ❌ Failed to schedule consultation.")

def view_consultations_menu():
    """View all consultations."""
    print_header("Scheduled Consultations")

    consultations = get_all_consultations()

    if not consultations:
        print("\n  No consultations found.")
        return

    print(f"\n  Total consultations: {len(consultations)}\n")
    print(f"  {'ID':<5} {'Client':<25} {'Date':<12} {'Time':<8} {'Status':<12} {'Attorney':<15}")
    print("  " + "-" * 85)

    for consult in consultations:
        client = consult['client_name'][:22] + "..." if len(consult['client_name']) > 25 else consult['client_name']
        attorney = consult['attorney'][:12] + "..." if len(consult['attorney']) > 15 else consult['attorney']
        print(f"  {consult['consultation_id']:<5} {client:<25} {consult['consultation_date']:<12} {consult['consultation_time']:<8} {consult['status']:<12} {attorney:<15}")

    print()

def statistics_menu():
    """Show legal services statistics."""
    print_header("Legal Services Statistics")

    cases = get_all_cases()
    consultations = get_all_consultations()

    if not cases and not consultations:
        print("\n  No data available.")
        return

    print(f"\n  Total Cases: {len(cases)}")
    print(f"  Total Consultations: {len(consultations)}")

    # By status
    by_status = {}
    for case in cases:
        by_status[case['status']] = by_status.get(case['status'], 0) + 1

    print("\n  Cases by Status:")
    for status, count in sorted(by_status.items()):
        print(f"    {status}: {count}")

    # By type
    by_type = {}
    for case in cases:
        by_type[case['case_type']] = by_type.get(case['case_type'], 0) + 1

    print("\n  Cases by Type:")
    for case_type, count in sorted(by_type.items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f"    {case_type}: {count}")

    print()

def legal_services_menu():
    """Main legal services CLI menu."""
    init_legal_database()

    while True:
        print_header("Legal Services Center")
        print("\n  1. List All Cases")
        print("  2. View Case Details")
        print("  3. Create New Case")
        print("  4. Update Case")
        print("  5. Schedule Consultation")
        print("  6. View Consultations")
        print("  7. View Statistics")
        print("  0. Return to Main Menu")

        choice = input("\n  Enter your choice: ").strip()

        if choice == '1':
            list_cases_menu()
        elif choice == '2':
            view_case_menu()
        elif choice == '3':
            create_case_menu()
        elif choice == '4':
            update_case_menu()
        elif choice == '5':
            schedule_consultation_menu()
        elif choice == '6':
            view_consultations_menu()
        elif choice == '7':
            statistics_menu()
        elif choice == '0':
            print("\n  Returning to main menu...\n")
            break
        else:
            print("\n  ❌ Invalid choice.")

        if choice != '0':
            input("\n  Press Enter to continue...")

if __name__ == '__main__':
    legal_services_menu()
