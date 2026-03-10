#!/usr/bin/env python3
"""
Church Management CLI - Comprehensive church administration system
Features: Members, Donations, Events, Prayer Requests, Sermons, Volunteers, Attendance
"""

from datetime import datetime
from pathlib import Path

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
    from education_system.university_system.infrastructure.email.email_service import send_email_as_system
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False

CHURCH_SCHEMA = """
CREATE TABLE IF NOT EXISTS church_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    address TEXT,
    join_date TEXT,
    membership_status TEXT DEFAULT 'Active'
);

CREATE TABLE IF NOT EXISTS church_donations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    donor_name TEXT,
    amount REAL NOT NULL,
    donation_type TEXT,
    payment_method TEXT,
    reference TEXT,
    date TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS church_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    event_date TEXT,
    event_time TEXT,
    location TEXT,
    organizer TEXT,
    status TEXT DEFAULT 'Scheduled'
);

CREATE TABLE IF NOT EXISTS church_prayer_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    requester_name TEXT,
    request_text TEXT NOT NULL,
    request_type TEXT,
    status TEXT DEFAULT 'Active',
    date_submitted TEXT,
    answered BOOLEAN DEFAULT 0
);

CREATE TABLE IF NOT EXISTS church_sermons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    preacher TEXT,
    sermon_date TEXT,
    scripture TEXT,
    notes TEXT,
    recording_url TEXT
);

CREATE TABLE IF NOT EXISTS church_announcements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    content TEXT,
    announcement_date TEXT,
    expires_date TEXT
);

CREATE TABLE IF NOT EXISTS church_volunteers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    volunteer_name TEXT NOT NULL,
    role TEXT,
    availability TEXT,
    contact TEXT
);

CREATE TABLE IF NOT EXISTS church_attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_date TEXT,
    service_type TEXT,
    count INTEGER
);
"""

def init_church_database():
    """Initialize church database tables."""
    try:
        with get_connection() as conn:
            conn.executescript(CHURCH_SCHEMA)
            conn.commit()
        return True
    except Exception as e:
        print(f"Error initializing database: {e}")
        return False

# ==================== Members ====================

def add_member(name, email='', phone='', address=''):
    """Add a new church member."""
    try:
        with get_connection() as conn:
            conn.execute("""
                INSERT INTO church_members (name, email, phone, address, join_date)
                VALUES (?, ?, ?, ?, ?)
            """, (name, email, phone, address, datetime.now().strftime('%Y-%m-%d')))
            conn.commit()
        return True
    except Exception as e:
        print(f"Error adding member: {e}")
        return False

def list_members():
    """List all church members."""
    try:
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, name, email, phone, membership_status, join_date
                FROM church_members ORDER BY name
            """)
            return cursor.fetchall()
    except Exception as e:
        print(f"Error listing members: {e}")
        return []

def get_member(member_id):
    """Get member details."""
    try:
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, name, email, phone, address, membership_status, join_date
                FROM church_members WHERE id = ?
            """, (member_id,))
            return cursor.fetchone()
    except Exception as e:
        print(f"Error getting member: {e}")
        return None

# ==================== Donations ====================

def record_donation(donor_name, amount, donation_type='Tithe', payment_method='Cash', notes=''):
    """Record a donation."""
    try:
        import random
        reference = f"DON-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"

        with get_connection() as conn:
            conn.execute("""
                INSERT INTO church_donations
                (donor_name, amount, donation_type, payment_method, reference, date, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (donor_name, amount, donation_type, payment_method, reference,
                  datetime.now().strftime('%Y-%m-%d'), notes))
            conn.commit()
        return reference
    except Exception as e:
        print(f"Error recording donation: {e}")
        return None

def list_donations(limit=50):
    """List recent donations."""
    try:
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, donor_name, amount, donation_type, payment_method, reference, date
                FROM church_donations ORDER BY date DESC LIMIT ?
            """, (limit,))
            return cursor.fetchall()
    except Exception as e:
        print(f"Error listing donations: {e}")
        return []

def get_donation_stats():
    """Get donation statistics."""
    try:
        with get_connection() as conn:
            # Total donations
            cursor = conn.execute("SELECT SUM(amount), COUNT(*) FROM church_donations")
            total_amount, total_count = cursor.fetchone()

            # By type
            cursor = conn.execute("""
                SELECT donation_type, SUM(amount), COUNT(*)
                FROM church_donations GROUP BY donation_type
            """)
            by_type = cursor.fetchall()

            return {
                'total_amount': total_amount or 0,
                'total_count': total_count or 0,
                'by_type': by_type
            }
    except Exception as e:
        print(f"Error getting donation stats: {e}")
        return {'total_amount': 0, 'total_count': 0, 'by_type': []}

# ==================== Events ====================

def create_event(title, event_date, event_time='', location='', description=''):
    """Create a church event."""
    try:
        with get_connection() as conn:
            conn.execute("""
                INSERT INTO church_events
                (title, description, event_date, event_time, location, status)
                VALUES (?, ?, ?, ?, ?, 'Scheduled')
            """, (title, description, event_date, event_time, location))
            conn.commit()
        return True
    except Exception as e:
        print(f"Error creating event: {e}")
        return False

def list_events():
    """List upcoming events."""
    try:
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, title, event_date, event_time, location, status
                FROM church_events ORDER BY event_date DESC
            """)
            return cursor.fetchall()
    except Exception as e:
        print(f"Error listing events: {e}")
        return []

# ==================== Prayer Requests ====================

def add_prayer_request(requester_name, request_text, request_type='General'):
    """Add a prayer request."""
    try:
        with get_connection() as conn:
            conn.execute("""
                INSERT INTO church_prayer_requests
                (requester_name, request_text, request_type, date_submitted)
                VALUES (?, ?, ?, ?)
            """, (requester_name, request_text, request_type,
                  datetime.now().strftime('%Y-%m-%d')))
            conn.commit()
        return True
    except Exception as e:
        print(f"Error adding prayer request: {e}")
        return False

def list_prayer_requests(status='Active'):
    """List prayer requests."""
    try:
        with get_connection() as conn:
            if status:
                cursor = conn.execute("""
                    SELECT id, requester_name, request_text, request_type, date_submitted, answered
                    FROM church_prayer_requests WHERE status = ? ORDER BY date_submitted DESC
                """, (status,))
            else:
                cursor = conn.execute("""
                    SELECT id, requester_name, request_text, request_type, date_submitted, answered
                    FROM church_prayer_requests ORDER BY date_submitted DESC
                """)
            return cursor.fetchall()
    except Exception as e:
        print(f"Error listing prayer requests: {e}")
        return []

def mark_prayer_answered(prayer_id):
    """Mark prayer request as answered."""
    try:
        with get_connection() as conn:
            conn.execute("""
                UPDATE church_prayer_requests
                SET answered = 1, status = 'Answered'
                WHERE id = ?
            """, (prayer_id,))
            conn.commit()
        return True
    except Exception as e:
        print(f"Error marking prayer answered: {e}")
        return False

# ==================== Sermons ====================

def add_sermon(title, preacher, sermon_date, scripture='', notes=''):
    """Add a sermon record."""
    try:
        with get_connection() as conn:
            conn.execute("""
                INSERT INTO church_sermons
                (title, preacher, sermon_date, scripture, notes)
                VALUES (?, ?, ?, ?, ?)
            """, (title, preacher, sermon_date, scripture, notes))
            conn.commit()
        return True
    except Exception as e:
        print(f"Error adding sermon: {e}")
        return False

def list_sermons(limit=20):
    """List recent sermons."""
    try:
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, title, preacher, sermon_date, scripture
                FROM church_sermons ORDER BY sermon_date DESC LIMIT ?
            """, (limit,))
            return cursor.fetchall()
    except Exception as e:
        print(f"Error listing sermons: {e}")
        return []

# ==================== CLI Interface ====================

def print_header(title):
    """Print formatted header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

# Members Menu
def members_menu():
    """Church members management."""
    while True:
        print_header("Church Members")
        print("\n  1. List All Members")
        print("  2. View Member Details")
        print("  3. Add New Member")
        print("  0. Back")

        choice = input("\n  Enter choice: ").strip()

        if choice == '1':
            members = list_members()
            if members:
                print(f"\n  Total members: {len(members)}\n")
                print(f"  {'ID':<6} {'Name':<30} {'Email':<30} {'Status':<12}")
                print("  " + "-" * 80)
                for m in members:
                    print(f"  {m[0]:<6} {m[1]:<30} {m[2] or 'N/A':<30} {m[4]:<12}")
            else:
                print("\n  No members found.")

        elif choice == '2':
            member_id = input("\n  Enter Member ID: ").strip()
            member = get_member(member_id)
            if member:
                print(f"\n  ID: {member[0]}")
                print(f"  Name: {member[1]}")
                print(f"  Email: {member[2] or 'N/A'}")
                print(f"  Phone: {member[3] or 'N/A'}")
                print(f"  Address: {member[4] or 'N/A'}")
                print(f"  Status: {member[5]}")
                print(f"  Joined: {member[6]}")
            else:
                print("  ❌ Member not found.")

        elif choice == '3':
            name = input("\n  Member name: ").strip()
            if not name:
                print("  ❌ Name required.")
                continue
            email = input("  Email (optional): ").strip()
            phone = input("  Phone (optional): ").strip()
            address = input("  Address (optional): ").strip()

            if add_member(name, email, phone, address):
                print(f"\n  ✅ Member '{name}' added successfully!")
            else:
                print("\n  ❌ Failed to add member.")

        elif choice == '0':
            break

        if choice != '0':
            input("\n  Press Enter to continue...")

# Donations Menu
def donations_menu():
    """Church donations management."""
    while True:
        print_header("Church Donations")
        print("\n  1. Record Donation")
        print("  2. View Recent Donations")
        print("  3. View Statistics")
        print("  0. Back")

        choice = input("\n  Enter choice: ").strip()

        if choice == '1':
            donor_name = input("\n  Donor name: ").strip()
            try:
                amount = float(input("  Amount: ").strip())
            except ValueError:
                print("  ❌ Invalid amount.")
                continue

            print("\n  Donation type:")
            print("    1. Tithe")
            print("    2. Offering")
            print("    3. Building Fund")
            print("    4. Missions")
            print("    5. Other")

            type_choice = input("  Select (1-5): ").strip()
            types = {'1': 'Tithe', '2': 'Offering', '3': 'Building Fund', '4': 'Missions', '5': 'Other'}
            donation_type = types.get(type_choice, 'Offering')

            print("\n  Payment method:")
            print("    1. Cash")
            print("    2. Check")
            print("    3. Credit Card")
            print("    4. Bank Transfer")

            method_choice = input("  Select (1-4): ").strip()
            methods = {'1': 'Cash', '2': 'Check', '3': 'Credit Card', '4': 'Bank Transfer'}
            payment_method = methods.get(method_choice, 'Cash')

            notes = input("  Notes (optional): ").strip()

            reference = record_donation(donor_name, amount, donation_type, payment_method, notes)
            if reference:
                print(f"\n  ✅ Donation recorded! Reference: {reference}")
            else:
                print("\n  ❌ Failed to record donation.")

        elif choice == '2':
            donations = list_donations(30)
            if donations:
                print(f"\n  Recent donations:\n")
                print(f"  {'ID':<6} {'Donor':<25} {'Amount':<12} {'Type':<15} {'Date':<12}")
                print("  " + "-" * 80)
                for d in donations:
                    print(f"  {d[0]:<6} {d[1]:<25} ${d[2]:<11.2f} {d[3]:<15} {d[6]:<12}")
            else:
                print("\n  No donations found.")

        elif choice == '3':
            stats = get_donation_stats()
            print(f"\n  Total Donations: ${stats['total_amount']:.2f}")
            print(f"  Total Count: {stats['total_count']}")

            if stats['by_type']:
                print("\n  By Type:")
                for dtype, amount, count in stats['by_type']:
                    print(f"    {dtype}: ${amount:.2f} ({count} donations)")

        elif choice == '0':
            break

        if choice != '0':
            input("\n  Press Enter to continue...")

# Events Menu
def events_menu():
    """Church events management."""
    while True:
        print_header("Church Events")
        print("\n  1. List Events")
        print("  2. Create Event")
        print("  0. Back")

        choice = input("\n  Enter choice: ").strip()

        if choice == '1':
            events = list_events()
            if events:
                print(f"\n  Upcoming events:\n")
                print(f"  {'ID':<6} {'Title':<35} {'Date':<12} {'Location':<20}")
                print("  " + "-" * 80)
                for e in events:
                    print(f"  {e[0]:<6} {e[1]:<35} {e[2]:<12} {e[4] or 'TBD':<20}")
            else:
                print("\n  No events found.")

        elif choice == '2':
            title = input("\n  Event title: ").strip()
            if not title:
                print("  ❌ Title required.")
                continue

            event_date = input("  Event date (YYYY-MM-DD): ").strip()
            event_time = input("  Event time (HH:MM, optional): ").strip()
            location = input("  Location: ").strip()
            description = input("  Description: ").strip()

            if create_event(title, event_date, event_time, location, description):
                print(f"\n  ✅ Event '{title}' created!")
            else:
                print("\n  ❌ Failed to create event.")

        elif choice == '0':
            break

        if choice != '0':
            input("\n  Press Enter to continue...")

# Prayer Requests Menu
def prayer_menu():
    """Prayer requests management."""
    while True:
        print_header("Prayer Requests")
        print("\n  1. View Active Requests")
        print("  2. Submit Prayer Request")
        print("  3. Mark as Answered")
        print("  0. Back")

        choice = input("\n  Enter choice: ").strip()

        if choice == '1':
            requests = list_prayer_requests('Active')
            if requests:
                print(f"\n  Active prayer requests:\n")
                for r in requests:
                    print(f"  ID {r[0]}: {r[1]} - {r[2][:60]}...")
                    print(f"  Type: {r[3]} | Submitted: {r[4]}")
                    print()
            else:
                print("\n  No active requests.")

        elif choice == '2':
            requester = input("\n  Requester name: ").strip()
            request_text = input("  Prayer request: ").strip()

            if not request_text:
                print("  ❌ Request text required.")
                continue

            print("\n  Request type:")
            print("    1. Healing")
            print("    2. Guidance")
            print("    3. Thanksgiving")
            print("    4. General")

            type_choice = input("  Select (1-4): ").strip()
            types = {'1': 'Healing', '2': 'Guidance', '3': 'Thanksgiving', '4': 'General'}
            request_type = types.get(type_choice, 'General')

            if add_prayer_request(requester, request_text, request_type):
                print("\n  ✅ Prayer request submitted!")
            else:
                print("\n  ❌ Failed to submit request.")

        elif choice == '3':
            prayer_id = input("\n  Enter Prayer Request ID: ").strip()
            if mark_prayer_answered(prayer_id):
                print("\n  ✅ Marked as answered! Praise God!")
            else:
                print("\n  ❌ Failed to update.")

        elif choice == '0':
            break

        if choice != '0':
            input("\n  Press Enter to continue...")

# Sermons Menu
def sermons_menu():
    """Sermons management."""
    while True:
        print_header("Sermons")
        print("\n  1. List Recent Sermons")
        print("  2. Add Sermon")
        print("  0. Back")

        choice = input("\n  Enter choice: ").strip()

        if choice == '1':
            sermons = list_sermons(20)
            if sermons:
                print(f"\n  Recent sermons:\n")
                for s in sermons:
                    print(f"  {s[1]} by {s[2]}")
                    print(f"  Date: {s[3]} | Scripture: {s[4] or 'N/A'}")
                    print()
            else:
                print("\n  No sermons found.")

        elif choice == '2':
            title = input("\n  Sermon title: ").strip()
            if not title:
                print("  ❌ Title required.")
                continue

            preacher = input("  Preacher: ").strip()
            sermon_date = input("  Date (YYYY-MM-DD): ").strip()
            scripture = input("  Scripture reference: ").strip()
            notes = input("  Notes: ").strip()

            if add_sermon(title, preacher, sermon_date, scripture, notes):
                print(f"\n  ✅ Sermon '{title}' added!")
            else:
                print("\n  ❌ Failed to add sermon.")

        elif choice == '0':
            break

        if choice != '0':
            input("\n  Press Enter to continue...")

def church_menu():
    """Main church management CLI menu."""
    init_church_database()

    while True:
        print_header("Church Management System")
        print("\n  1. Member Management")
        print("  2. Donation Tracking")
        print("  3. Event Planning")
        print("  4. Prayer Requests")
        print("  5. Sermon Records")
        print("  0. Return to Main Menu")

        choice = input("\n  Enter your choice: ").strip()

        if choice == '1':
            members_menu()
        elif choice == '2':
            donations_menu()
        elif choice == '3':
            events_menu()
        elif choice == '4':
            prayer_menu()
        elif choice == '5':
            sermons_menu()
        elif choice == '0':
            print("\n  God bless! Returning to main menu...\n")
            break
        else:
            print("\n  ❌ Invalid choice.")

if __name__ == '__main__':
    church_menu()
