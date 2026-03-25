from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.university_system.modules.shared.constants import paths
from datetime import datetime
import os
import json


def data_import_export(auth):
    """Data import/export functions"""
    print("\nData Import/Export")
    print("==================")
    print("1. Export tickets to CSV")
    print("2. Export users to CSV")
    print("3. Import tickets from CSV")
    print("4. Export analytics data")
    print("5. Return to system management")

    choice = input("\nEnter your choice: ").strip()

    if choice == '1':
        export_tickets_csv(auth)
    elif choice == '2':
        export_users_csv(auth)
    elif choice == '3':
        import_tickets_csv(auth)
    elif choice == '4':
        export_analytics_data(auth)

def export_tickets_csv(auth):
    """Export tickets to CSV"""
    try:
        import csv

        if not os.path.exists(paths.EXPORTS_TICKETS_DIR):
            os.makedirs(paths.EXPORTS_TICKETS_DIR)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = paths.EXPORTS_TICKETS_DIR / f"tickets_export_{timestamp}.csv"

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        SELECT t.ticket_id, t.subject, t.category, t.status, t.priority,
               t.created_at, t.resolved_at, u1.username as submitter,
               u2.username as assignee, t.department
        FROM support_tickets t
        JOIN users u1 ON t.user_id = u1.id
        LEFT JOIN users u2 ON t.assigned_to = u2.id
        ORDER BY t.ticket_id
        ''')

        tickets = cursor.fetchall()

        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['ticket_id', 'subject', 'category', 'status', 'priority',
                         'created_at', 'resolved_at', 'submitter', 'assignee', 'department']

            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for ticket in tickets:
                writer.writerow({
                    'ticket_id': ticket[0],
                    'subject': ticket[1],
                    'category': ticket[2],
                    'status': ticket[3],
                    'priority': ticket[4],
                    'created_at': ticket[5],
                    'resolved_at': ticket[6] or '',
                    'submitter': ticket[7],
                    'assignee': ticket[8] or '',
                    'department': ticket[9] or ''
                })

        conn.close()
        print(f"Tickets exported to {filename}")

    except Exception as e:
        print(f"Error exporting tickets: {e}")

def export_users_csv(auth):
    """Export users to CSV"""
    try:
        import csv

        if not os.path.exists(paths.EXPORTS_TICKETS_DIR):
            os.makedirs(paths.EXPORTS_TICKETS_DIR)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = paths.EXPORTS_TICKETS_DIR / f"users_export_{timestamp}.csv"

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        SELECT id, username, email, role, department, is_active, created_at
        FROM users
        ORDER BY id
        ''')

        users = cursor.fetchall()

        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['id', 'username', 'email', 'role', 'department', 'is_active', 'created_at']

            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for user in users:
                writer.writerow({
                    'id': user[0],
                    'username': user[1],
                    'email': user[2],
                    'role': user[3],
                    'department': user[4] or '',
                    'is_active': user[5],
                    'created_at': user[6]
                })

        conn.close()
        print(f"Users exported to {filename}")

    except Exception as e:
        print(f"Error exporting users: {e}")

def import_tickets_csv(auth):
    """Import tickets from CSV"""
    filename = input("Enter CSV filename to import: ").strip()

    if not os.path.exists(filename):
        print("File not found.")
        return

    try:
        import csv

        conn = get_connection()
        cursor = conn.cursor()

        imported_count = 0

        with open(filename, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)

            for row in reader:
                if not all(k in row for k in ['subject', 'message', 'category', 'submitter']):
                    print(f"Skipping row due to missing required fields: {row}")
                    continue

                cursor.execute('SELECT id FROM users WHERE username = ?', (row['submitter'],))
                user_result = cursor.fetchone()

                if not user_result:
                    print(f"User not found: {row['submitter']}")
                    continue

                user_id = user_result[0]
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                INSERT INTO support_tickets
                (user_id, subject, message, category, status, priority, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (user_id, row['subject'], row.get('message', ''), row['category'],
                      row.get('status', 'open'), row.get('priority', 'medium'), now, now))

                imported_count += 1

        conn.commit()
        conn.close()

        print(f"Successfully imported {imported_count} tickets from {filename}")

    except Exception as e:
        print(f"Error importing tickets: {e}")

def export_analytics_data(auth):
    """Export analytics data"""
    try:
        if not os.path.exists(paths.EXPORTS_TICKETS_DIR):
            os.makedirs(paths.EXPORTS_TICKETS_DIR)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = paths.EXPORTS_TICKETS_DIR / f"analytics_export_{timestamp}.json"

        conn = get_connection()
        cursor = conn.cursor()

        analytics_data = {
            'generated_at': datetime.now().isoformat(),
            'generated_by': auth.current_user['username'],
            'summary': {},
            'detailed_stats': {}
        }

        cursor.execute('SELECT COUNT(*) FROM support_tickets')
        analytics_data['summary']['total_tickets'] = cursor.fetchone()[0]

        cursor.execute('''
        SELECT status, COUNT(*) FROM support_tickets GROUP BY status
        ''')
        analytics_data['summary']['tickets_by_status'] = dict(cursor.fetchall())

        cursor.execute('''
        SELECT category, COUNT(*) FROM support_tickets GROUP BY category
        ''')
        analytics_data['summary']['tickets_by_category'] = dict(cursor.fetchall())

        cursor.execute('''
        SELECT strftime('%Y-%m', created_at) as month, COUNT(*) as count
        FROM support_tickets
        WHERE created_at >= date('now', '-12 months')
        GROUP BY month
        ORDER BY month
        ''')
        analytics_data['detailed_stats']['monthly_trends'] = dict(cursor.fetchall())

        conn.close()

        with open(filename, 'w') as f:
            json.dump(analytics_data, f, indent=2)

        print(f"Analytics data exported to {filename}")

    except Exception as e:
        print(f"Error exporting analytics: {e}")
