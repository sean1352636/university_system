#!/usr/bin/env python3
"""
Police Station CLI - Campus Public Safety Management System
Features: Case management, complaints, evidence tracking, patrol logs, emergency alerts
"""

from datetime import datetime
from pathlib import Path

from education_system.post_18.university_system.core.sql_safety import validate_identifier  # nosec B608

from education_system.post_18.university_system.core.paths import DEFAULT_DB_PATH

try:
    from education_system.post_18.university_system.infrastructure.database.db import get_connection
except ImportError:
    from education_system.post_18.university_system.infrastructure.database.db import sqlite3
    def get_connection():
        return sqlite3.connect(str(DEFAULT_DB_PATH))

try:
    from education_system.post_18.university_system.infrastructure.shared_context import get_current_user as get_user
except ImportError:
    get_user = None

try:
    from education_system.post_18.university_system.infrastructure.email.email_service import send_email_as_system
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    send_email_as_system = None

# Campus locations
CAMPUS_LOCATIONS = [
    "Main Library", "Science Building", "Engineering Hall", "Student Center",
    "Administration Building", "Dormitory - North Hall", "Dormitory - South Hall",
    "Dormitory - East Wing", "Dormitory - West Wing", "Dining Hall",
    "Recreation Center", "Athletic Stadium", "Gymnasium", "Parking Lot A",
    "Parking Lot B", "Parking Garage", "Campus Green", "Quad",
    "Computer Lab", "Art Building", "Music Hall", "Theater",
    "Health Center", "Counseling Center", "Career Services Building",
    "Research Lab", "Graduate Housing", "Faculty Offices", "Bookstore",
    "Campus Police Station", "Maintenance Building", "Other"
]

# Incident types
INCIDENT_TYPES = [
    "Theft", "Bike Theft", "Vehicle Break-in", "Alcohol Violation",
    "Drug Violation", "Noise Violation", "Harassment", "Assault",
    "Sexual Misconduct/Title IX", "Hazing", "Vandalism", "Trespassing",
    "Disorderly Conduct", "Mental Health Crisis", "Medical Emergency",
    "Fire Alarm", "Suspicious Activity", "Lost Property", "Found Property",
    "Parking Violation", "Traffic Incident", "Academic Misconduct Referral",
    "Roommate Conflict", "Weapons Violation", "Threat Assessment", "Other"
]

# Complaint types
COMPLAINT_TYPES = [
    "Noise Complaint", "Roommate Dispute", "Harassment", "Theft Report",
    "Vandalism Report", "Parking Issue", "Suspicious Person", "Safety Concern",
    "Lighting Issue", "Building Access Problem", "Lost ID Card", "Stalking",
    "Discrimination", "Retaliation", "Housing Concern", "Other"
]

# Emergency types
EMERGENCY_TYPES = [
    "Active Threat", "Campus Lockdown", "Tornado Warning", "Severe Weather",
    "Building Evacuation", "Fire Emergency", "Hazmat Incident", "Gas Leak",
    "Missing Student", "Medical Emergency", "Power Outage", "Water Main Break",
    "Campus Closure", "Shelter in Place", "All Clear", "Other"
]

# Officer ranks
OFFICER_RANKS = [
    "Chief of Police", "Deputy Chief", "Lieutenant", "Sergeant",
    "Corporal", "Campus Police Officer", "Security Officer",
    "Parking Enforcement Officer", "Dispatcher", "Student Safety Officer"
]

POLICE_STATION_SCHEMA = """
CREATE TABLE IF NOT EXISTS police_cases (
    id TEXT PRIMARY KEY,
    title TEXT,
    type TEXT,
    status TEXT DEFAULT 'Open',
    priority TEXT DEFAULT 'Medium',
    officer TEXT,
    location TEXT,
    description TEXT,
    notes TEXT,
    witnesses TEXT,
    student_id TEXT,
    student_name TEXT,
    is_student_involved INTEGER DEFAULT 0,
    date TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS police_officers (
    badge TEXT PRIMARY KEY,
    name TEXT,
    rank TEXT,
    department TEXT,
    status TEXT DEFAULT 'Active',
    phone TEXT,
    email TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS police_complaints (
    id TEXT PRIMARY KEY,
    complainant TEXT,
    email TEXT,
    phone TEXT,
    student_id TEXT,
    is_student INTEGER DEFAULT 0,
    type TEXT,
    priority TEXT DEFAULT 'Medium',
    status TEXT DEFAULT 'Pending',
    incident_date TEXT,
    incident_time TEXT,
    location TEXT,
    description TEXT,
    suspect_description TEXT,
    date TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS police_criminals (
    id TEXT PRIMARY KEY,
    name TEXT,
    student_id TEXT,
    is_student INTEGER DEFAULT 0,
    affiliation TEXT,
    crime TEXT,
    status TEXT,
    arrest_date TEXT,
    case_number TEXT,
    description TEXT,
    trespass_notice INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS police_evidence (
    id TEXT PRIMARY KEY,
    description TEXT,
    case_number TEXT,
    type TEXT,
    location TEXT,
    custody TEXT,
    date_added TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS police_patrol_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    officer TEXT,
    area TEXT,
    start_time TEXT,
    end_time TEXT,
    status TEXT,
    notes TEXT,
    date TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS police_emergency_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT,
    location TEXT,
    details TEXT,
    reporter TEXT,
    timestamp TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS police_case_counter (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    counter INTEGER DEFAULT 1000
);

INSERT OR IGNORE INTO police_case_counter (id, counter) VALUES (1, 1000);
"""

def init_police_database():
    """Initialize police station database tables."""
    try:
        with get_connection() as conn:
            conn.executescript(POLICE_STATION_SCHEMA)
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

def get_next_case_id():
    """Generate next case ID."""
    try:
        with get_connection() as conn:
            cursor = conn.execute("SELECT counter FROM police_case_counter WHERE id = 1")
            counter = cursor.fetchone()[0]
            new_counter = counter + 1
            conn.execute("UPDATE police_case_counter SET counter = ? WHERE id = 1", (new_counter,))
            conn.commit()
            return f"CASE-{new_counter:05d}"
    except Exception as e:
        print(f"Error generating case ID: {e}")
        return f"CASE-{datetime.now().strftime('%Y%m%d%H%M%S')}"

# ==================== CASE MANAGEMENT ====================

def create_case(case_data):
    """Create a new case."""
    try:
        with get_connection() as conn:
            conn.execute("""
                INSERT INTO police_cases
                (id, title, type, status, priority, officer, location, description,
                 notes, witnesses, student_id, student_name, is_student_involved, date, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                case_data['id'], case_data['title'], case_data['type'],
                case_data['status'], case_data['priority'], case_data['officer'],
                case_data['location'], case_data['description'], case_data.get('notes', ''),
                case_data.get('witnesses', ''), case_data.get('student_id', ''),
                case_data.get('student_name', ''), case_data.get('is_student_involved', 0),
                case_data['date'], case_data['created_at'], case_data['updated_at']
            ))
            conn.commit()
        return True
    except Exception as e:
        print(f"Error creating case: {e}")
        return False

def get_all_cases():
    """Get all cases."""
    try:
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, title, type, status, priority, officer, location,
                       description, student_name, date, created_at
                FROM police_cases
                ORDER BY created_at DESC
            """)
            cases = []
            for row in cursor.fetchall():
                cases.append({
                    'id': row[0], 'title': row[1], 'type': row[2], 'status': row[3],
                    'priority': row[4], 'officer': row[5], 'location': row[6],
                    'description': row[7], 'student_name': row[8], 'date': row[9],
                    'created_at': row[10]
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
                SELECT id, title, type, status, priority, officer, location, description,
                       notes, witnesses, student_id, student_name, is_student_involved, date
                FROM police_cases WHERE id = ?
            """, (case_id,))
            row = cursor.fetchone()
            if row:
                return {
                    'id': row[0], 'title': row[1], 'type': row[2], 'status': row[3],
                    'priority': row[4], 'officer': row[5], 'location': row[6],
                    'description': row[7], 'notes': row[8], 'witnesses': row[9],
                    'student_id': row[10], 'student_name': row[11],
                    'is_student_involved': row[12], 'date': row[13]
                }
    except Exception as e:
        print(f"Error getting case: {e}")
    return None

_CASE_ALLOWED_COLUMNS = frozenset({
    'title', 'type', 'status', 'priority', 'officer', 'location',
    'description', 'notes', 'witnesses', 'student_id', 'student_name',
    'is_student_involved', 'date',
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

        fields.append("updated_at = ?")
        values.append(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        values.append(case_id)

        with get_connection() as conn:
            conn.execute(f"""
                UPDATE police_cases
                SET {', '.join(fields)}
                WHERE id = ?
            """, values)
            conn.commit()
        return True
    except Exception as e:
        print(f"Error updating case: {e}")
        return False

def delete_case(case_id):
    """Delete a case."""
    try:
        with get_connection() as conn:
            conn.execute("DELETE FROM police_cases WHERE id = ?", (case_id,))
            conn.commit()
        return True
    except Exception as e:
        print(f"Error deleting case: {e}")
        return False

# ==================== COMPLAINTS ====================

def create_complaint(complaint_data):
    """Create a new complaint."""
    try:
        with get_connection() as conn:
            conn.execute("""
                INSERT INTO police_complaints
                (id, complainant, email, phone, student_id, is_student, type, priority,
                 status, incident_date, incident_time, location, description,
                 suspect_description, date, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                complaint_data['id'], complaint_data['complainant'], complaint_data.get('email', ''),
                complaint_data.get('phone', ''), complaint_data.get('student_id', ''),
                complaint_data.get('is_student', 0), complaint_data['type'],
                complaint_data['priority'], complaint_data['status'],
                complaint_data['incident_date'], complaint_data.get('incident_time', ''),
                complaint_data['location'], complaint_data['description'],
                complaint_data.get('suspect_description', ''), complaint_data['date'],
                complaint_data['created_at'], complaint_data['updated_at']
            ))
            conn.commit()
        return True
    except Exception as e:
        print(f"Error creating complaint: {e}")
        return False

def get_all_complaints():
    """Get all complaints."""
    try:
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, complainant, type, priority, status, location,
                       incident_date, date
                FROM police_complaints
                ORDER BY created_at DESC
            """)
            complaints = []
            for row in cursor.fetchall():
                complaints.append({
                    'id': row[0], 'complainant': row[1], 'type': row[2],
                    'priority': row[3], 'status': row[4], 'location': row[5],
                    'incident_date': row[6], 'date': row[7]
                })
            return complaints
    except Exception as e:
        print(f"Error getting complaints: {e}")
        return []

def get_complaint_by_id(complaint_id):
    """Get specific complaint by ID."""
    try:
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, complainant, email, phone, student_id, is_student, type,
                       priority, status, incident_date, incident_time, location,
                       description, suspect_description, date
                FROM police_complaints WHERE id = ?
            """, (complaint_id,))
            row = cursor.fetchone()
            if row:
                return {
                    'id': row[0], 'complainant': row[1], 'email': row[2], 'phone': row[3],
                    'student_id': row[4], 'is_student': row[5], 'type': row[6],
                    'priority': row[7], 'status': row[8], 'incident_date': row[9],
                    'incident_time': row[10], 'location': row[11], 'description': row[12],
                    'suspect_description': row[13], 'date': row[14]
                }
    except Exception as e:
        print(f"Error getting complaint: {e}")
    return None

# ==================== EMERGENCY ALERTS ====================

def create_emergency_alert(alert_data):
    """Create an emergency alert."""
    try:
        with get_connection() as conn:
            conn.execute("""
                INSERT INTO police_emergency_alerts (type, location, details, reporter, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (
                alert_data['type'], alert_data['location'], alert_data['details'],
                alert_data['reporter'], alert_data['timestamp']
            ))
            conn.commit()
        return True
    except Exception as e:
        print(f"Error creating alert: {e}")
        return False

def get_all_alerts():
    """Get all emergency alerts."""
    try:
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, type, location, details, reporter, timestamp
                FROM police_emergency_alerts
                ORDER BY id DESC
                LIMIT 50
            """)
            alerts = []
            for row in cursor.fetchall():
                alerts.append({
                    'id': row[0], 'type': row[1], 'location': row[2],
                    'details': row[3], 'reporter': row[4], 'timestamp': row[5]
                })
            return alerts
    except Exception as e:
        print(f"Error getting alerts: {e}")
        return []

# ==================== CLI INTERFACE ====================

def print_header(title):
    """Print formatted header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def print_case_summary(case):
    """Print case summary."""
    print(f"\n  ID: {case['id']}")
    print(f"  Title: {case['title']}")
    print(f"  Type: {case['type']} | Priority: {case['priority']} | Status: {case['status']}")
    print(f"  Officer: {case.get('officer', 'Unassigned')}")
    print(f"  Location: {case.get('location', 'N/A')}")
    print(f"  Date: {case['date']}")

def print_case_details(case):
    """Print full case details."""
    print_header(f"Case Details: {case['id']}")
    print(f"\n  Title: {case['title']}")
    print(f"  Type: {case['type']}")
    print(f"  Status: {case['status']}")
    print(f"  Priority: {case['priority']}")
    print(f"  Officer: {case.get('officer', 'Unassigned')}")
    print(f"  Location: {case.get('location', 'N/A')}")
    print(f"  Date: {case['date']}")
    print(f"\n  Description: {case.get('description', 'N/A')}")

    if case.get('is_student_involved'):
        print(f"\n  Student Involved: {case.get('student_name', 'N/A')} (ID: {case.get('student_id', 'N/A')})")

    if case.get('witnesses'):
        print(f"  Witnesses: {case['witnesses']}")

    if case.get('notes'):
        print(f"  Notes: {case['notes']}")

def list_cases_menu():
    """List all cases."""
    print_header("Police Cases - All Records")

    cases = get_all_cases()

    if not cases:
        print("\n  No cases found.")
        return

    print(f"\n  Total cases: {len(cases)}\n")
    print(f"  {'ID':<15} {'Title':<30} {'Type':<20} {'Status':<12} {'Priority':<10}")
    print("  " + "-" * 90)

    for case in cases:
        title = case['title'][:27] + "..." if len(case['title']) > 30 else case['title']
        case_type = case['type'][:17] + "..." if len(case['type']) > 20 else case['type']
        print(f"  {case['id']:<15} {title:<30} {case_type:<20} {case['status']:<12} {case['priority']:<10}")

    print()

def view_case_menu():
    """View case details."""
    print_header("View Case")

    case_id = input("\n  Enter Case ID: ").strip()
    if not case_id:
        print("  ❌ Case ID required.")
        return

    case = get_case_by_id(case_id)
    if not case:
        print(f"  ❌ Case {case_id} not found.")
        return

    print_case_details(case)

def create_case_menu():
    """Create new case."""
    print_header("Create New Case")

    current_user = get_current_user()

    title = input("\n  Case title: ").strip()
    if not title:
        print("  ❌ Title is required.")
        return

    print("\n  Incident Types:")
    for i, incident_type in enumerate(INCIDENT_TYPES[:10], 1):
        print(f"    {i}. {incident_type}")
    print("    ... (more available)")

    incident_type = input("  Enter incident type (or type manually): ").strip()
    if incident_type.isdigit() and 1 <= int(incident_type) <= len(INCIDENT_TYPES):
        incident_type = INCIDENT_TYPES[int(incident_type) - 1]
    elif not incident_type:
        incident_type = "Other"

    print("\n  Locations:")
    for i, loc in enumerate(CAMPUS_LOCATIONS[:10], 1):
        print(f"    {i}. {loc}")
    print("    ... (more available)")

    location = input("  Enter location (or type manually): ").strip()
    if location.isdigit() and 1 <= int(location) <= len(CAMPUS_LOCATIONS):
        location = CAMPUS_LOCATIONS[int(location) - 1]

    description = input("  Description: ").strip()

    print("\n  Priority:")
    print("    1. Low")
    print("    2. Medium")
    print("    3. High")
    print("    4. Critical")

    priority_choice = input("  Select priority (1-4, default 2): ").strip() or '2'
    priorities = {'1': 'Low', '2': 'Medium', '3': 'High', '4': 'Critical'}
    priority = priorities.get(priority_choice, 'Medium')

    officer = input("  Assigned officer (optional): ").strip() or "Unassigned"

    student_involved = input("  Is student involved? (yes/no): ").strip().lower() == 'yes'
    student_id = ""
    student_name = ""
    if student_involved:
        student_id = input("  Student ID: ").strip()
        student_name = input("  Student name: ").strip()

    case_data = {
        'id': get_next_case_id(),
        'title': title,
        'type': incident_type,
        'status': 'Open',
        'priority': priority,
        'officer': officer,
        'location': location,
        'description': description,
        'notes': '',
        'witnesses': '',
        'student_id': student_id,
        'student_name': student_name,
        'is_student_involved': 1 if student_involved else 0,
        'date': datetime.now().strftime('%Y-%m-%d'),
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

    if create_case(case_data):
        print(f"\n  ✅ Case {case_data['id']} created successfully!")
    else:
        print("\n  ❌ Failed to create case.")

def update_case_menu():
    """Update case status/details."""
    print_header("Update Case")

    case_id = input("\n  Enter Case ID: ").strip()
    if not case_id:
        print("  ❌ Case ID required.")
        return

    case = get_case_by_id(case_id)
    if not case:
        print(f"  ❌ Case {case_id} not found.")
        return

    print_case_summary(case)

    print("\n  Update:")
    print("    1. Status")
    print("    2. Priority")
    print("    3. Assign Officer")
    print("    4. Add Notes")
    print("    0. Cancel")

    choice = input("\n  Enter choice: ").strip()

    if choice == '1':
        print("\n  Status:")
        print("    1. Open")
        print("    2. In Progress")
        print("    3. Under Investigation")
        print("    4. Resolved")
        print("    5. Closed")

        status_choice = input("  Select status (1-5): ").strip()
        statuses = {'1': 'Open', '2': 'In Progress', '3': 'Under Investigation', '4': 'Resolved', '5': 'Closed'}
        new_status = statuses.get(status_choice)

        if new_status and update_case(case_id, {'status': new_status}):
            print(f"\n  ✅ Status updated to: {new_status}")

    elif choice == '2':
        print("\n  Priority:")
        print("    1. Low")
        print("    2. Medium")
        print("    3. High")
        print("    4. Critical")

        priority_choice = input("  Select priority (1-4): ").strip()
        priorities = {'1': 'Low', '2': 'Medium', '3': 'High', '4': 'Critical'}
        new_priority = priorities.get(priority_choice)

        if new_priority and update_case(case_id, {'priority': new_priority}):
            print(f"\n  ✅ Priority updated to: {new_priority}")

    elif choice == '3':
        officer = input("  Officer name: ").strip()
        if officer and update_case(case_id, {'officer': officer}):
            print(f"\n  ✅ Assigned to: {officer}")

    elif choice == '4':
        notes = input("  Enter notes: ").strip()
        if update_case(case_id, {'notes': notes}):
            print("\n  ✅ Notes updated.")

def delete_case_menu():
    """Delete a case."""
    print_header("Delete Case")

    case_id = input("\n  Enter Case ID: ").strip()
    if not case_id:
        print("  ❌ Case ID required.")
        return

    case = get_case_by_id(case_id)
    if not case:
        print(f"  ❌ Case {case_id} not found.")
        return

    print_case_summary(case)

    confirm = input("\n  ⚠️  Delete this case? (yes/no): ").strip().lower()
    if confirm == 'yes':
        if delete_case(case_id):
            print(f"\n  ✅ Case {case_id} deleted.")
        else:
            print("\n  ❌ Failed to delete case.")

def emergency_alert_menu():
    """Create emergency alert."""
    print_header("Create Emergency Alert")

    current_user = get_current_user()

    print("\n  Emergency Types:")
    for i, alert_type in enumerate(EMERGENCY_TYPES, 1):
        print(f"    {i}. {alert_type}")

    type_choice = input("\n  Select type (1-" + str(len(EMERGENCY_TYPES)) + "): ").strip()
    if type_choice.isdigit() and 1 <= int(type_choice) <= len(EMERGENCY_TYPES):
        alert_type = EMERGENCY_TYPES[int(type_choice) - 1]
    else:
        alert_type = "Other"

    location = input("  Location: ").strip()
    details = input("  Details: ").strip()

    alert_data = {
        'type': alert_type,
        'location': location,
        'details': details,
        'reporter': current_user.get('name', 'System'),
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

    if create_emergency_alert(alert_data):
        print("\n  ✅ Emergency alert created successfully!")
        print("  ⚠️  ALERT BROADCAST TO CAMPUS")
    else:
        print("\n  ❌ Failed to create alert.")

def view_alerts_menu():
    """View recent emergency alerts."""
    print_header("Recent Emergency Alerts")

    alerts = get_all_alerts()

    if not alerts:
        print("\n  No alerts found.")
        return

    print(f"\n  Total alerts: {len(alerts)} (showing last 50)\n")

    for alert in alerts:
        print(f"\n  ID: {alert['id']} | Type: {alert['type']}")
        print(f"  Location: {alert['location']}")
        print(f"  Details: {alert['details']}")
        print(f"  Reporter: {alert['reporter']} | Time: {alert['timestamp']}")
        print("  " + "-" * 70)

def statistics_menu():
    """Show case statistics."""
    print_header("Police Station Statistics")

    cases = get_all_cases()
    complaints = get_all_complaints()

    if not cases and not complaints:
        print("\n  No data available.")
        return

    print(f"\n  Total Cases: {len(cases)}")
    print(f"  Total Complaints: {len(complaints)}")

    # By status
    by_status = {}
    for c in cases:
        by_status[c['status']] = by_status.get(c['status'], 0) + 1

    print("\n  Cases by Status:")
    for status, count in sorted(by_status.items()):
        print(f"    {status}: {count}")

    # By priority
    by_priority = {}
    for c in cases:
        by_priority[c['priority']] = by_priority.get(c['priority'], 0) + 1

    print("\n  Cases by Priority:")
    for priority, count in sorted(by_priority.items()):
        print(f"    {priority}: {count}")

    # By type
    by_type = {}
    for c in cases:
        by_type[c['type']] = by_type.get(c['type'], 0) + 1

    print("\n  Top Incident Types:")
    for incident_type, count in sorted(by_type.items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f"    {incident_type}: {count}")

    print()

def police_station_menu():
    """Main police station CLI menu."""
    init_police_database()

    while True:
        print_header("Campus Police Station")
        print("\n  1. List All Cases")
        print("  2. View Case Details")
        print("  3. Create New Case")
        print("  4. Update Case")
        print("  5. Delete Case")
        print("  6. Create Emergency Alert")
        print("  7. View Recent Alerts")
        print("  8. View Statistics")
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
            delete_case_menu()
        elif choice == '6':
            emergency_alert_menu()
        elif choice == '7':
            view_alerts_menu()
        elif choice == '8':
            statistics_menu()
        elif choice == '0':
            print("\n  Returning to main menu...\n")
            break
        else:
            print("\n  ❌ Invalid choice.")

        if choice != '0':
            input("\n  Press Enter to continue...")

if __name__ == '__main__':
    police_station_menu()
