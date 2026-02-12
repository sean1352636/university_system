#!/usr/bin/env python3
"""
Security Desk CLI - Security assistance ticket management system
Features: Help requests, issue reporting, ticket tracking, status monitoring
"""

from datetime import datetime
from pathlib import Path

from university_system.core.sql_safety import validate_identifier

try:
    from university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
except ImportError:
    DEFAULT_DB_PATH = Path(__file__).resolve().parents[3] / "data" / "db_files" / "student_records.db"

try:
    from university_system.infrastructure.database.db import get_connection
except ImportError:
    from university_system.infrastructure.database.db import sqlite3
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

SECURITY_DESK_SCHEMA = """
CREATE TABLE IF NOT EXISTS security_desk_tickets (
    id TEXT PRIMARY KEY,
    type TEXT,
    category TEXT,
    priority TEXT DEFAULT 'Normal',
    status TEXT DEFAULT 'Open',
    subject TEXT,
    description TEXT,
    location TEXT,
    user_id TEXT,
    user_name TEXT,
    user_email TEXT,
    admin_notes TEXT,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS security_desk_counter (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    counter INTEGER DEFAULT 1000
);

INSERT OR IGNORE INTO security_desk_counter (id, counter) VALUES (1, 1000);
"""

def init_security_desk_database():
    """Initialize security desk database tables."""
    try:
        with get_connection() as conn:
            conn.executescript(SECURITY_DESK_SCHEMA)
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

def get_next_ticket_id():
    """Generate next ticket ID."""
    try:
        with get_connection() as conn:
            cursor = conn.execute("SELECT counter FROM security_desk_counter WHERE id = 1")
            counter = cursor.fetchone()[0]
            new_counter = counter + 1
            conn.execute("UPDATE security_desk_counter SET counter = ? WHERE id = 1", (new_counter,))
            conn.commit()
            return f"SD-{new_counter:05d}"
    except Exception as e:
        print(f"Error generating ticket ID: {e}")
        return f"SD-{datetime.now().strftime('%Y%m%d%H%M%S')}"

def create_ticket(ticket_data):
    """Create a new ticket."""
    try:
        with get_connection() as conn:
            conn.execute("""
                INSERT INTO security_desk_tickets
                (id, type, category, priority, status, subject, description, location,
                 user_id, user_name, user_email, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ticket_data['id'], ticket_data['type'], ticket_data['category'],
                ticket_data['priority'], ticket_data['status'], ticket_data['subject'],
                ticket_data['description'], ticket_data['location'], ticket_data['user_id'],
                ticket_data['user_name'], ticket_data['user_email'],
                ticket_data['created_at'], ticket_data['updated_at']
            ))
            conn.commit()
        return True
    except Exception as e:
        print(f"Error creating ticket: {e}")
        return False

def get_all_tickets():
    """Get all tickets."""
    try:
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, type, category, priority, status, subject, description, location,
                       user_name, user_email, admin_notes, created_at, updated_at
                FROM security_desk_tickets
                ORDER BY created_at DESC
            """)
            tickets = []
            for row in cursor.fetchall():
                tickets.append({
                    'id': row[0], 'type': row[1], 'category': row[2], 'priority': row[3],
                    'status': row[4], 'subject': row[5], 'description': row[6],
                    'location': row[7], 'user_name': row[8], 'user_email': row[9],
                    'admin_notes': row[10], 'created_at': row[11], 'updated_at': row[12]
                })
            return tickets
    except Exception as e:
        print(f"Error getting tickets: {e}")
        return []

def get_ticket_by_id(ticket_id):
    """Get specific ticket by ID."""
    try:
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, type, category, priority, status, subject, description, location,
                       user_name, user_email, admin_notes, created_at, updated_at
                FROM security_desk_tickets WHERE id = ?
            """, (ticket_id,))
            row = cursor.fetchone()
            if row:
                return {
                    'id': row[0], 'type': row[1], 'category': row[2], 'priority': row[3],
                    'status': row[4], 'subject': row[5], 'description': row[6],
                    'location': row[7], 'user_name': row[8], 'user_email': row[9],
                    'admin_notes': row[10], 'created_at': row[11], 'updated_at': row[12]
                }
    except Exception as e:
        print(f"Error getting ticket: {e}")
    return None

_TICKET_ALLOWED_COLUMNS = frozenset({
    'type', 'category', 'priority', 'status', 'subject', 'description',
    'location', 'user_id', 'user_name', 'user_email', 'admin_notes',
})

def update_ticket(ticket_id, updates):
    """Update ticket fields."""
    try:
        fields = []
        values = []
        for key, value in updates.items():
            if key not in _TICKET_ALLOWED_COLUMNS:
                raise ValueError(f"Invalid column name: {key}")
            validate_identifier(key, "column")
            fields.append(f"{key} = ?")
            values.append(value)

        fields.append("updated_at = ?")
        values.append(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        values.append(ticket_id)

        with get_connection() as conn:
            conn.execute(f"""
                UPDATE security_desk_tickets
                SET {', '.join(fields)}
                WHERE id = ?
            """, values)
            conn.commit()
        return True
    except Exception as e:
        print(f"Error updating ticket: {e}")
        return False

def delete_ticket(ticket_id):
    """Delete a ticket."""
    try:
        with get_connection() as conn:
            conn.execute("DELETE FROM security_desk_tickets WHERE id = ?", (ticket_id,))
            conn.commit()
        return True
    except Exception as e:
        print(f"Error deleting ticket: {e}")
        return False

# ==================== CLI Interface ====================

def print_header(title):
    """Print formatted header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def print_ticket_summary(ticket):
    """Print ticket summary."""
    print(f"\n  ID: {ticket['id']}")
    print(f"  Type: {ticket['type']} | Category: {ticket['category']}")
    print(f"  Priority: {ticket['priority']} | Status: {ticket['status']}")
    print(f"  Subject: {ticket['subject']}")
    print(f"  Created: {ticket['created_at']}")

def print_ticket_details(ticket):
    """Print full ticket details."""
    print_header(f"Ticket Details: {ticket['id']}")
    print(f"\n  Type: {ticket['type']}")
    print(f"  Category: {ticket['category']}")
    print(f"  Priority: {ticket['priority']}")
    print(f"  Status: {ticket['status']}")
    print(f"\n  Subject: {ticket['subject']}")
    print(f"  Description: {ticket['description']}")
    print(f"  Location: {ticket['location']}")
    print(f"\n  Submitted by: {ticket['user_name']}")
    print(f"  Email: {ticket['user_email']}")
    print(f"  Created: {ticket['created_at']}")
    print(f"  Updated: {ticket['updated_at']}")

    if ticket['admin_notes']:
        print(f"\n  Admin Notes: {ticket['admin_notes']}")

def list_tickets_menu():
    """List all tickets."""
    print_header("Security Desk - All Tickets")

    tickets = get_all_tickets()

    if not tickets:
        print("\n  No tickets found.")
        return

    print(f"\n  Total tickets: {len(tickets)}\n")
    print(f"  {'ID':<12} {'Type':<15} {'Priority':<10} {'Status':<12} {'Subject':<30}")
    print("  " + "-" * 80)

    for ticket in tickets:
        subject = ticket['subject'][:27] + "..." if len(ticket['subject']) > 30 else ticket['subject']
        print(f"  {ticket['id']:<12} {ticket['type']:<15} {ticket['priority']:<10} {ticket['status']:<12} {subject:<30}")

    print()

def view_ticket_menu():
    """View ticket details."""
    print_header("View Ticket")

    ticket_id = input("\n  Enter Ticket ID: ").strip()
    if not ticket_id:
        print("  ❌ Ticket ID required.")
        return

    ticket = get_ticket_by_id(ticket_id)
    if not ticket:
        print(f"  ❌ Ticket {ticket_id} not found.")
        return

    print_ticket_details(ticket)

def create_ticket_menu():
    """Create new ticket."""
    print_header("Create New Security Ticket")

    current_user = get_current_user()

    print("\n  Ticket Types:")
    print("    1. Help Request")
    print("    2. Security Issue")
    print("    3. Emergency")

    type_choice = input("  Select type (1-3): ").strip()
    types = {'1': 'Help Request', '2': 'Security Issue', '3': 'Emergency'}
    ticket_type = types.get(type_choice, 'Help Request')

    print("\n  Categories:")
    if ticket_type == 'Help Request':
        print("    1. Lost & Found")
        print("    2. Lockout")
        print("    3. Access Issue")
        print("    4. General Assistance")
    elif ticket_type == 'Security Issue':
        print("    1. Suspicious Activity")
        print("    2. Theft")
        print("    3. Vandalism")
        print("    4. Safety Concern")
    else:
        print("    1. Medical Emergency")
        print("    2. Fire")
        print("    3. Security Threat")
        print("    4. Other Emergency")

    category = input("  Enter category: ").strip() or "General"

    subject = input("  Subject: ").strip()
    if not subject:
        print("  ❌ Subject is required.")
        return

    description = input("  Description: ").strip()
    location = input("  Location: ").strip()

    print("\n  Priority:")
    print("    1. Low")
    print("    2. Normal")
    print("    3. High")
    print("    4. Critical")

    priority_choice = input("  Select priority (1-4): ").strip()
    priorities = {'1': 'Low', '2': 'Normal', '3': 'High', '4': 'Critical'}
    priority = priorities.get(priority_choice, 'Normal')

    ticket_data = {
        'id': get_next_ticket_id(),
        'type': ticket_type,
        'category': category,
        'priority': priority,
        'status': 'Open',
        'subject': subject,
        'description': description,
        'location': location,
        'user_id': str(current_user.get('id', '')),
        'user_name': current_user.get('name', current_user.get('username', 'Unknown')),
        'user_email': current_user.get('email', ''),
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

    if create_ticket(ticket_data):
        print(f"\n  ✅ Ticket {ticket_data['id']} created successfully!")
    else:
        print("\n  ❌ Failed to create ticket.")

def update_ticket_menu():
    """Update ticket status/notes."""
    print_header("Update Ticket")

    ticket_id = input("\n  Enter Ticket ID: ").strip()
    if not ticket_id:
        print("  ❌ Ticket ID required.")
        return

    ticket = get_ticket_by_id(ticket_id)
    if not ticket:
        print(f"  ❌ Ticket {ticket_id} not found.")
        return

    print_ticket_summary(ticket)

    print("\n  Update:")
    print("    1. Status")
    print("    2. Priority")
    print("    3. Add Admin Notes")
    print("    0. Cancel")

    choice = input("\n  Enter choice: ").strip()

    if choice == '1':
        print("\n  Status:")
        print("    1. Open")
        print("    2. In Progress")
        print("    3. Resolved")
        print("    4. Closed")

        status_choice = input("  Select status (1-4): ").strip()
        statuses = {'1': 'Open', '2': 'In Progress', '3': 'Resolved', '4': 'Closed'}
        new_status = statuses.get(status_choice)

        if new_status and update_ticket(ticket_id, {'status': new_status}):
            print(f"\n  ✅ Status updated to: {new_status}")

    elif choice == '2':
        print("\n  Priority:")
        print("    1. Low")
        print("    2. Normal")
        print("    3. High")
        print("    4. Critical")

        priority_choice = input("  Select priority (1-4): ").strip()
        priorities = {'1': 'Low', '2': 'Normal', '3': 'High', '4': 'Critical'}
        new_priority = priorities.get(priority_choice)

        if new_priority and update_ticket(ticket_id, {'priority': new_priority}):
            print(f"\n  ✅ Priority updated to: {new_priority}")

    elif choice == '3':
        notes = input("  Enter admin notes: ").strip()
        if update_ticket(ticket_id, {'admin_notes': notes}):
            print("\n  ✅ Notes updated.")

def delete_ticket_menu():
    """Delete a ticket."""
    print_header("Delete Ticket")

    ticket_id = input("\n  Enter Ticket ID: ").strip()
    if not ticket_id:
        print("  ❌ Ticket ID required.")
        return

    ticket = get_ticket_by_id(ticket_id)
    if not ticket:
        print(f"  ❌ Ticket {ticket_id} not found.")
        return

    print_ticket_summary(ticket)

    confirm = input("\n  ⚠️  Delete this ticket? (yes/no): ").strip().lower()
    if confirm == 'yes':
        if delete_ticket(ticket_id):
            print(f"\n  ✅ Ticket {ticket_id} deleted.")
        else:
            print("\n  ❌ Failed to delete ticket.")

def statistics_menu():
    """Show ticket statistics."""
    print_header("Security Desk Statistics")

    tickets = get_all_tickets()

    if not tickets:
        print("\n  No tickets found.")
        return

    print(f"\n  Total Tickets: {len(tickets)}")

    # By status
    by_status = {}
    for t in tickets:
        by_status[t['status']] = by_status.get(t['status'], 0) + 1

    print("\n  By Status:")
    for status, count in sorted(by_status.items()):
        print(f"    {status}: {count}")

    # By priority
    by_priority = {}
    for t in tickets:
        by_priority[t['priority']] = by_priority.get(t['priority'], 0) + 1

    print("\n  By Priority:")
    for priority, count in sorted(by_priority.items()):
        print(f"    {priority}: {count}")

    # By type
    by_type = {}
    for t in tickets:
        by_type[t['type']] = by_type.get(t['type'], 0) + 1

    print("\n  By Type:")
    for ttype, count in sorted(by_type.items()):
        print(f"    {ttype}: {count}")

    print()

def security_desk_menu():
    """Main security desk CLI menu."""
    init_security_desk_database()

    while True:
        print_header("Security Desk - Ticket Management")
        print("\n  1. List All Tickets")
        print("  2. View Ticket Details")
        print("  3. Create New Ticket")
        print("  4. Update Ticket")
        print("  5. Delete Ticket")
        print("  6. View Statistics")
        print("  0. Return to Main Menu")

        choice = input("\n  Enter your choice: ").strip()

        if choice == '1':
            list_tickets_menu()
        elif choice == '2':
            view_ticket_menu()
        elif choice == '3':
            create_ticket_menu()
        elif choice == '4':
            update_ticket_menu()
        elif choice == '5':
            delete_ticket_menu()
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
    security_desk_menu()
