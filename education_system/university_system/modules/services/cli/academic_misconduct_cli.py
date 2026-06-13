#!/usr/bin/env python3
"""
Academic Misconduct CLI - Case Management System
A command-line interface for managing academic integrity cases.
"""

from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import json

# Database and utilities imports
from education_system.university_system.core.paths import DEFAULT_DB_PATH

try:
    from education_system.university_system.infrastructure.email.email_service import queue_email
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    queue_email = None

try:
    from education_system.university_system.infrastructure.shared_context import get_auth
    AUTH_AVAILABLE = True
except ImportError:
    AUTH_AVAILABLE = False
    get_auth = None

def init_misconduct_tables():
    """Create the academic misconduct tables if they don't exist."""
    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
    try:
        cursor = conn.cursor()

        # Main cases table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS academic_misconduct_cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id TEXT UNIQUE NOT NULL,
                student_name TEXT NOT NULL,
                student_id TEXT NOT NULL,
                student_email TEXT,
                course TEXT NOT NULL,
                violation_type TEXT NOT NULL,
                status TEXT DEFAULT 'Under Review',
                date_filed TEXT NOT NULL,
                severity TEXT NOT NULL,
                notes TEXT,
                hearing_date TEXT,
                hearing_time TEXT,
                hearing_location TEXT,
                ruling TEXT,
                ruling_rationale TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Case history/timeline table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS academic_misconduct_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id TEXT NOT NULL,
                event_date TEXT NOT NULL,
                event_description TEXT NOT NULL,
                event_type TEXT DEFAULT 'info',
                created_by TEXT,
                FOREIGN KEY (case_id) REFERENCES academic_misconduct_cases(case_id)
            )
        ''')

        # Evidence table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS academic_misconduct_evidence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id TEXT NOT NULL,
                file_name TEXT NOT NULL,
                file_path TEXT,
                file_size TEXT,
                uploaded_date TEXT NOT NULL,
                uploaded_by TEXT,
                FOREIGN KEY (case_id) REFERENCES academic_misconduct_cases(case_id)
            )
        ''')

        conn.commit()
    finally:
        conn.close()

def get_next_case_id():
    """Generate the next case ID in format AM-YYYY-NNNN."""
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()

        year = datetime.now().year
        prefix = f"AM-{year}-"

        cursor.execute('''
            SELECT case_id FROM academic_misconduct_cases
            WHERE case_id LIKE ?
            ORDER BY case_id DESC LIMIT 1
        ''', (f"{prefix}%",))

        result = cursor.fetchone()
        conn.close()

        if result:
            last_num = int(result[0].split('-')[-1])
            next_num = last_num + 1
        else:
            next_num = 1

        return f"{prefix}{next_num:04d}"
    except Exception as e:
        print(f"Error generating case ID: {e}")
        return f"AM-{datetime.now().year}-0001"

def load_all_cases():
    """Load all cases from the database."""
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT case_id, student_name, student_id, student_email, course,
                   violation_type, status, date_filed, severity, notes,
                   hearing_date, hearing_time, hearing_location, ruling, ruling_rationale
            FROM academic_misconduct_cases
            ORDER BY date_filed DESC
        ''')
        rows = cursor.fetchall()
        conn.close()

        cases = []
        for row in rows:
            cases.append({
                'id': row['case_id'],
                'student': row['student_name'],
                'student_id': row['student_id'],
                'student_email': row['student_email'] or '',
                'course': row['course'],
                'type': row['violation_type'],
                'status': row['status'],
                'date_filed': row['date_filed'],
                'severity': row['severity'],
                'notes': row['notes'] or '',
                'hearing_date': row['hearing_date'] or '',
                'hearing_time': row['hearing_time'] or '',
                'hearing_location': row['hearing_location'] or '',
                'ruling': row['ruling'] or '',
                'ruling_rationale': row['ruling_rationale'] or ''
            })
        return cases
    except Exception as e:
        print(f"Error loading cases: {e}")
        return []

def get_case_by_id(case_id):
    """Get a specific case by ID."""
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT case_id, student_name, student_id, student_email, course,
                   violation_type, status, date_filed, severity, notes,
                   hearing_date, hearing_time, hearing_location, ruling, ruling_rationale
            FROM academic_misconduct_cases
            WHERE case_id = ?
        ''', (case_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                'id': row['case_id'],
                'student': row['student_name'],
                'student_id': row['student_id'],
                'student_email': row['student_email'] or '',
                'course': row['course'],
                'type': row['violation_type'],
                'status': row['status'],
                'date_filed': row['date_filed'],
                'severity': row['severity'],
                'notes': row['notes'] or '',
                'hearing_date': row['hearing_date'] or '',
                'hearing_time': row['hearing_time'] or '',
                'hearing_location': row['hearing_location'] or '',
                'ruling': row['ruling'] or '',
                'ruling_rationale': row['ruling_rationale'] or ''
            }
        return None
    except Exception as e:
        print(f"Error loading case: {e}")
        return None

def save_case(case_data):
    """Save a new case to the database."""
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO academic_misconduct_cases
            (case_id, student_name, student_id, student_email, course, violation_type,
             status, date_filed, severity, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            case_data['id'], case_data['student'], case_data['student_id'],
            case_data.get('student_email', ''), case_data['course'], case_data['type'],
            case_data['status'], case_data['date_filed'], case_data['severity'],
            case_data['notes']
        ))

        # Add to history
        cursor.execute('''
            INSERT INTO academic_misconduct_history (case_id, event_date, event_description, event_type)
            VALUES (?, ?, ?, ?)
        ''', (case_data['id'], datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
              'Case filed', 'info'))

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error saving case: {e}")
        return False

def update_case(case_data):
    """Update an existing case in the database."""
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE academic_misconduct_cases
            SET student_name=?, student_id=?, student_email=?, course=?, violation_type=?,
                status=?, severity=?, notes=?, hearing_date=?, hearing_time=?,
                hearing_location=?, ruling=?, ruling_rationale=?, updated_at=CURRENT_TIMESTAMP
            WHERE case_id=?
        ''', (
            case_data['student'], case_data['student_id'], case_data.get('student_email', ''),
            case_data['course'], case_data['type'], case_data['status'], case_data['severity'],
            case_data['notes'], case_data.get('hearing_date', ''), case_data.get('hearing_time', ''),
            case_data.get('hearing_location', ''), case_data.get('ruling', ''),
            case_data.get('ruling_rationale', ''), case_data['id']
        ))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error updating case: {e}")
        return False

def delete_case(case_id):
    """Delete a case from the database."""
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()
        cursor.execute('DELETE FROM academic_misconduct_history WHERE case_id=?', (case_id,))
        cursor.execute('DELETE FROM academic_misconduct_evidence WHERE case_id=?', (case_id,))
        cursor.execute('DELETE FROM academic_misconduct_cases WHERE case_id=?', (case_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error deleting case: {e}")
        return False

def add_case_history(case_id, description, event_type='info'):
    """Add an entry to case history."""
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO academic_misconduct_history (case_id, event_date, event_description, event_type)
            VALUES (?, ?, ?, ?)
        ''', (case_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), description, event_type))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error adding case history: {e}")
        return False

def get_case_history(case_id):
    """Get history for a specific case."""
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT event_date, event_description, event_type
            FROM academic_misconduct_history
            WHERE case_id=?
            ORDER BY event_date DESC
        ''', (case_id,))
        rows = cursor.fetchall()
        conn.close()
        return [(row['event_date'], row['event_description'], row['event_type']) for row in rows]
    except Exception as e:
        print(f"Error getting case history: {e}")
        return []

def get_case_evidence(case_id):
    """Get evidence for a specific case."""
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT file_name, file_path, file_size, uploaded_date, uploaded_by
            FROM academic_misconduct_evidence
            WHERE case_id=?
            ORDER BY uploaded_date DESC
        ''', (case_id,))
        rows = cursor.fetchall()
        conn.close()
        return [(row['file_name'], row['file_path'], row['file_size'],
                 row['uploaded_date'], row['uploaded_by']) for row in rows]
    except Exception as e:
        print(f"Error getting evidence: {e}")
        return []

def add_evidence(case_id, file_name, file_path='', file_size='', uploaded_by=''):
    """Add evidence to a case."""
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO academic_misconduct_evidence
            (case_id, file_name, file_path, file_size, uploaded_date, uploaded_by)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (case_id, file_name, file_path, file_size,
              datetime.now().strftime('%Y-%m-%d %H:%M:%S'), uploaded_by))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error adding evidence: {e}")
        return False

def get_dashboard_stats():
    """Get statistics for dashboard."""
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()

        stats = {}

        # Total cases
        cursor.execute('SELECT COUNT(*) FROM academic_misconduct_cases')
        stats['total_cases'] = cursor.fetchone()[0]

        # Cases by status
        cursor.execute('SELECT status, COUNT(*) FROM academic_misconduct_cases GROUP BY status')
        stats['by_status'] = dict(cursor.fetchall())

        # Cases by severity
        cursor.execute('SELECT severity, COUNT(*) FROM academic_misconduct_cases GROUP BY severity')
        stats['by_severity'] = dict(cursor.fetchall())

        # Cases by violation type
        cursor.execute('SELECT violation_type, COUNT(*) FROM academic_misconduct_cases GROUP BY violation_type')
        stats['by_type'] = dict(cursor.fetchall())

        # Recent cases (last 30 days)
        thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        cursor.execute('SELECT COUNT(*) FROM academic_misconduct_cases WHERE date_filed >= ?', (thirty_days_ago,))
        stats['recent_cases'] = cursor.fetchone()[0]

        conn.close()
        return stats
    except Exception as e:
        print(f"Error getting statistics: {e}")
        return {}

def notify_student(case):
    """Send email notification to student about their case."""
    if not EMAIL_AVAILABLE or not queue_email:
        print("⚠️  Email service not available. Notification cannot be sent.")
        return False

    student_email = case.get('student_email', '')
    if not student_email:
        print("⚠️  Student email not found in case.")
        return False

    subject = f"Academic Misconduct Case {case['id']} - Notification"
    body = f"""
Dear {case['student']},

This is to notify you about an academic misconduct case filed against you.

Case ID: {case['id']}
Course: {case['course']}
Violation Type: {case['type']}
Date Filed: {case['date_filed']}
Status: {case['status']}
Severity: {case['severity']}

{case['notes']}

You will be contacted separately regarding the next steps in this process.

If you have any questions, please contact the Academic Integrity Office.

Sincerely,
Academic Integrity Office
"""

    try:
        queue_email(student_email, subject, body)
        return True
    except Exception as e:
        print(f"Error sending notification: {e}")
        return False

# ==================== CLI Interface Functions ====================

def print_header(title):
    """Print a formatted header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def print_case_summary(case):
    """Print a summary of a case."""
    print(f"\n  Case ID: {case['id']}")
    print(f"  Student: {case['student']} ({case['student_id']})")
    print(f"  Course: {case['course']}")
    print(f"  Type: {case['type']}")
    print(f"  Status: {case['status']}")
    print(f"  Severity: {case['severity']}")
    print(f"  Filed: {case['date_filed']}")

def print_case_details(case):
    """Print detailed information about a case."""
    print_header(f"Case Details: {case['id']}")
    print(f"\n  Student Information:")
    print(f"    Name: {case['student']}")
    print(f"    Student ID: {case['student_id']}")
    print(f"    Email: {case['student_email'] or 'N/A'}")

    print(f"\n  Case Information:")
    print(f"    Course: {case['course']}")
    print(f"    Violation Type: {case['type']}")
    print(f"    Status: {case['status']}")
    print(f"    Severity: {case['severity']}")
    print(f"    Date Filed: {case['date_filed']}")

    if case['notes']:
        print(f"\n  Notes:")
        print(f"    {case['notes']}")

    if case['hearing_date']:
        print(f"\n  Hearing Information:")
        print(f"    Date: {case['hearing_date']}")
        print(f"    Time: {case['hearing_time']}")
        print(f"    Location: {case['hearing_location']}")

    if case['ruling']:
        print(f"\n  Decision:")
        print(f"    Ruling: {case['ruling']}")
        print(f"    Rationale: {case['ruling_rationale']}")

def list_cases_menu():
    """Display all cases."""
    print_header("All Academic Misconduct Cases")

    cases = load_all_cases()

    if not cases:
        print("\n  No cases found.")
        return

    print(f"\n  Total cases: {len(cases)}\n")
    print(f"  {'Case ID':<15} {'Student':<25} {'Course':<15} {'Type':<20} {'Status':<15} {'Severity':<10}")
    print("  " + "-" * 110)

    for case in cases:
        print(f"  {case['id']:<15} {case['student']:<25} {case['course']:<15} {case['type']:<20} {case['status']:<15} {case['severity']:<10}")

    print("\n")

def view_case_menu():
    """View details of a specific case."""
    print_header("View Case Details")

    case_id = input("\n  Enter Case ID: ").strip()

    if not case_id:
        print("  ❌ Case ID cannot be empty.")
        return

    case = get_case_by_id(case_id)

    if not case:
        print(f"  ❌ Case {case_id} not found.")
        return

    print_case_details(case)

    # Show history
    print(f"\n  Case History:")
    history = get_case_history(case_id)
    if history:
        for event_date, description, event_type in history:
            print(f"    [{event_date}] {description}")
    else:
        print("    No history entries.")

    # Show evidence
    print(f"\n  Evidence:")
    evidence = get_case_evidence(case_id)
    if evidence:
        for file_name, file_path, file_size, uploaded_date, uploaded_by in evidence:
            print(f"    • {file_name} ({file_size or 'unknown size'}) - Uploaded: {uploaded_date}")
    else:
        print("    No evidence uploaded.")

    print("\n")

def create_case_menu():
    """Create a new case."""
    print_header("Create New Academic Misconduct Case")

    case_id = get_next_case_id()
    print(f"\n  New Case ID: {case_id}")

    # Collect case information
    student_name = input("  Student Name: ").strip()
    if not student_name:
        print("  ❌ Student name is required.")
        return

    student_id = input("  Student ID: ").strip()
    if not student_id:
        print("  ❌ Student ID is required.")
        return

    student_email = input("  Student Email (optional): ").strip()

    course = input("  Course Code: ").strip()
    if not course:
        print("  ❌ Course code is required.")
        return

    print("\n  Violation Types:")
    print("    1. Plagiarism")
    print("    2. Cheating on Exam")
    print("    3. Unauthorized Collaboration")
    print("    4. Fabrication of Data")
    print("    5. Contract Cheating")
    print("    6. Other")

    violation_choice = input("  Select violation type (1-6): ").strip()
    violation_types = {
        '1': 'Plagiarism',
        '2': 'Cheating on Exam',
        '3': 'Unauthorized Collaboration',
        '4': 'Fabrication of Data',
        '5': 'Contract Cheating',
        '6': 'Other'
    }
    violation_type = violation_types.get(violation_choice, 'Other')

    if violation_choice == '6':
        custom_type = input("  Specify violation type: ").strip()
        if custom_type:
            violation_type = custom_type

    print("\n  Severity Levels:")
    print("    1. Low")
    print("    2. Medium")
    print("    3. High")

    severity_choice = input("  Select severity (1-3): ").strip()
    severity_levels = {'1': 'Low', '2': 'Medium', '3': 'High'}
    severity = severity_levels.get(severity_choice, 'Medium')

    notes = input("  Case notes/description: ").strip()

    # Create case data
    case_data = {
        'id': case_id,
        'student': student_name,
        'student_id': student_id,
        'student_email': student_email,
        'course': course,
        'type': violation_type,
        'status': 'Under Review',
        'date_filed': datetime.now().strftime('%Y-%m-%d'),
        'severity': severity,
        'notes': notes
    }

    # Save case
    if save_case(case_data):
        print(f"\n  ✅ Case {case_id} created successfully!")
    else:
        print(f"\n  ❌ Failed to create case.")

def update_case_menu():
    """Update an existing case."""
    print_header("Update Case")

    case_id = input("\n  Enter Case ID to update: ").strip()

    if not case_id:
        print("  ❌ Case ID cannot be empty.")
        return

    case = get_case_by_id(case_id)

    if not case:
        print(f"  ❌ Case {case_id} not found.")
        return

    print("\n  Current case details:")
    print_case_summary(case)

    print("\n  What would you like to update?")
    print("    1. Status")
    print("    2. Notes")
    print("    3. Schedule Hearing")
    print("    4. Submit Decision")
    print("    0. Cancel")

    choice = input("\n  Enter choice: ").strip()

    if choice == '1':
        # Update status
        print("\n  Status options:")
        print("    1. Under Review")
        print("    2. Investigation")
        print("    3. Pending Hearing")
        print("    4. Resolved")
        print("    5. Dismissed")

        status_choice = input("  Select new status (1-5): ").strip()
        statuses = {
            '1': 'Under Review',
            '2': 'Investigation',
            '3': 'Pending Hearing',
            '4': 'Resolved',
            '5': 'Dismissed'
        }
        new_status = statuses.get(status_choice)

        if new_status:
            case['status'] = new_status
            if update_case(case):
                add_case_history(case_id, f"Status changed to: {new_status}", 'info')
                print(f"\n  ✅ Case status updated to: {new_status}")
            else:
                print("\n  ❌ Failed to update case.")

    elif choice == '2':
        # Update notes
        new_notes = input("  Enter new notes (current will be replaced): ").strip()
        case['notes'] = new_notes
        if update_case(case):
            add_case_history(case_id, "Case notes updated", 'info')
            print("\n  ✅ Case notes updated.")
        else:
            print("\n  ❌ Failed to update case.")

    elif choice == '3':
        # Schedule hearing
        print("\n  Schedule Hearing")
        hearing_date = input("  Hearing Date (YYYY-MM-DD): ").strip()
        hearing_time = input("  Hearing Time (HH:MM): ").strip()
        hearing_location = input("  Hearing Location: ").strip()

        case['hearing_date'] = hearing_date
        case['hearing_time'] = hearing_time
        case['hearing_location'] = hearing_location
        case['status'] = 'Pending Hearing'

        if update_case(case):
            add_case_history(case_id, f"Hearing scheduled for {hearing_date} at {hearing_time}", 'info')
            print("\n  ✅ Hearing scheduled successfully.")
        else:
            print("\n  ❌ Failed to schedule hearing.")

    elif choice == '4':
        # Submit decision
        print("\n  Decision options:")
        print("    1. Not Responsible")
        print("    2. Responsible - Warning")
        print("    3. Responsible - Academic Penalty")
        print("    4. Responsible - Disciplinary Probation")
        print("    5. Responsible - Suspension")
        print("    6. Responsible - Expulsion")

        decision_choice = input("  Select decision (1-6): ").strip()
        decisions = {
            '1': 'Not Responsible',
            '2': 'Responsible - Warning',
            '3': 'Responsible - Academic Penalty',
            '4': 'Responsible - Disciplinary Probation',
            '5': 'Responsible - Suspension',
            '6': 'Responsible - Expulsion'
        }
        ruling = decisions.get(decision_choice)

        if ruling:
            rationale = input("  Decision rationale: ").strip()

            case['ruling'] = ruling
            case['ruling_rationale'] = rationale
            case['status'] = 'Resolved'

            if update_case(case):
                add_case_history(case_id, f"Decision: {ruling}", 'decision')
                print("\n  ✅ Decision submitted successfully.")
            else:
                print("\n  ❌ Failed to submit decision.")

def delete_case_menu():
    """Delete a case."""
    print_header("Delete Case")

    case_id = input("\n  Enter Case ID to delete: ").strip()

    if not case_id:
        print("  ❌ Case ID cannot be empty.")
        return

    case = get_case_by_id(case_id)

    if not case:
        print(f"  ❌ Case {case_id} not found.")
        return

    print_case_summary(case)

    confirm = input("\n  ⚠️  Are you sure you want to delete this case? This cannot be undone. (yes/no): ").strip().lower()

    if confirm == 'yes':
        if delete_case(case_id):
            print(f"\n  ✅ Case {case_id} deleted successfully.")
        else:
            print("\n  ❌ Failed to delete case.")
    else:
        print("\n  ℹ️  Delete cancelled.")

def add_evidence_menu():
    """Add evidence to a case."""
    print_header("Add Evidence to Case")

    case_id = input("\n  Enter Case ID: ").strip()

    if not case_id:
        print("  ❌ Case ID cannot be empty.")
        return

    case = get_case_by_id(case_id)

    if not case:
        print(f"  ❌ Case {case_id} not found.")
        return

    print_case_summary(case)

    file_name = input("\n  Evidence file name: ").strip()
    if not file_name:
        print("  ❌ File name is required.")
        return

    file_path = input("  File path (optional): ").strip()
    file_size = input("  File size (optional): ").strip()

    # Get current user if available
    uploaded_by = ""
    if AUTH_AVAILABLE and get_auth:
        auth = get_auth()
        if hasattr(auth, 'current_user') and auth.current_user:
            uploaded_by = auth.current_user.get('username', '')

    if add_evidence(case_id, file_name, file_path, file_size, uploaded_by):
        add_case_history(case_id, f"Evidence added: {file_name}", 'evidence')
        print(f"\n  ✅ Evidence added successfully.")
    else:
        print("\n  ❌ Failed to add evidence.")

def notify_student_menu():
    """Send notification to student."""
    print_header("Notify Student")

    case_id = input("\n  Enter Case ID: ").strip()

    if not case_id:
        print("  ❌ Case ID cannot be empty.")
        return

    case = get_case_by_id(case_id)

    if not case:
        print(f"  ❌ Case {case_id} not found.")
        return

    print_case_summary(case)

    if not case['student_email']:
        print("\n  ❌ Student email not found in case.")
        return

    print(f"\n  Email will be sent to: {case['student_email']}")
    confirm = input("  Proceed? (yes/no): ").strip().lower()

    if confirm == 'yes':
        if notify_student(case):
            add_case_history(case_id, f"Student notified via email", 'notification')
            print("\n  ✅ Notification sent successfully.")
        else:
            print("\n  ❌ Failed to send notification.")
    else:
        print("\n  ℹ️  Notification cancelled.")

def view_statistics_menu():
    """View dashboard statistics."""
    print_header("Academic Misconduct Statistics")

    stats = get_dashboard_stats()

    print(f"\n  Overall Statistics:")
    print(f"    Total Cases: {stats.get('total_cases', 0)}")
    print(f"    Recent Cases (last 30 days): {stats.get('recent_cases', 0)}")

    print(f"\n  Cases by Status:")
    by_status = stats.get('by_status', {})
    for status, count in sorted(by_status.items()):
        print(f"    {status}: {count}")

    print(f"\n  Cases by Severity:")
    by_severity = stats.get('by_severity', {})
    for severity, count in sorted(by_severity.items()):
        print(f"    {severity}: {count}")

    print(f"\n  Cases by Violation Type:")
    by_type = stats.get('by_type', {})
    for vtype, count in sorted(by_type.items(), key=lambda x: x[1], reverse=True):
        print(f"    {vtype}: {count}")

    print("\n")

def academic_misconduct_menu():
    """Main menu for Academic Misconduct CLI."""
    # Initialize tables
    init_misconduct_tables()

    while True:
        print_header("Academic Misconduct Case Management")
        print("\n  1. List All Cases")
        print("  2. View Case Details")
        print("  3. Create New Case")
        print("  4. Update Case")
        print("  5. Delete Case")
        print("  6. Add Evidence")
        print("  7. Notify Student")
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
            add_evidence_menu()
        elif choice == '7':
            notify_student_menu()
        elif choice == '8':
            view_statistics_menu()
        elif choice == '0':
            print("\n  Returning to main menu...\n")
            break
        else:
            print("\n  ❌ Invalid choice. Please try again.")

        if choice != '0':
            input("\n  Press Enter to continue...")

if __name__ == '__main__':
    academic_misconduct_menu()
