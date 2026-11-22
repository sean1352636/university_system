from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection
from education_system import paths
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
    """Export the tickets the signed-in support staff member may see to CSV
    (through the ticket service: list fields only, no ticket text)."""
    from education_system.systems.university.domains.student_support.domain.helpdesk.tickets.service import (
        iter_tickets,
    )
    try:
        import csv

        tickets = sorted(iter_tickets(auth), key=lambda t: t['ticket_id'])

        os.makedirs(paths.UNIVERSITY_EXPORTS_TICKETS_DIR, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = paths.UNIVERSITY_EXPORTS_TICKETS_DIR / f"tickets_export_{timestamp}.csv"

        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['ticket_id', 'subject', 'category', 'status', 'priority',
                         'created_at', 'resolved_at', 'submitter', 'assignee', 'department',
                         'team', 'confidentiality']

            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for ticket in tickets:
                writer.writerow({
                    'ticket_id': ticket['ticket_id'],
                    'subject': ticket.get('subject'),
                    'category': ticket.get('category'),
                    'status': ticket.get('status'),
                    'priority': ticket.get('priority'),
                    'created_at': ticket.get('created_at'),
                    'resolved_at': ticket.get('resolved_at') or '',
                    'submitter': ticket.get('requester_username') or ticket.get('student_id') or '',
                    'assignee': ticket.get('assigned_to') or '',
                    'department': ticket.get('department') or '',
                    'team': ticket.get('team') or '',
                    'confidentiality': ticket.get('confidentiality') or 'standard',
                })

        print(f"Tickets exported to {filename}")

    except (PermissionError, ValueError, OSError) as e:
        print(f"Error exporting tickets: {e}")

def export_users_csv(auth):
    """Export the university's user accounts to CSV with the support teams
    each belongs to (administrators only)."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        auth as support_auth, routing,
    )
    if not support_auth.is_admin(auth):
        print("Only an administrator can export users.")
        return
    try:
        import csv

        os.makedirs(paths.UNIVERSITY_EXPORTS_TICKETS_DIR, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = paths.UNIVERSITY_EXPORTS_TICKETS_DIR / f"users_export_{timestamp}.csv"

        with get_connection() as conn:
            users = conn.execute('''
            SELECT id, username, email, role, created_at
            FROM users
            ORDER BY id
            ''').fetchall()

        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['id', 'username', 'email', 'role', 'department', 'created_at']

            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for user in users:
                teams = sorted(routing.user_teams(user[1]))
                writer.writerow({
                    'id': user[0],
                    'username': user[1],
                    'email': user[2],
                    'role': user[3],
                    'department': "; ".join(routing.team_label(t) for t in teams),
                    'created_at': user[4]
                })

        print(f"Users exported to {filename}")

    except (sqlite3.Error, OSError) as e:
        print(f"Error exporting users: {e}")

def import_tickets_csv(auth):
    """Import tickets from CSV (columns subject, message, category, submitter;
    optional priority, status). Each row is raised through the ticket service
    for its submitter, so routing, tier, crisis detection and SLA apply."""
    from education_system.systems.university.domains.student_support.domain.helpdesk.tickets.service import (
        submit_helpdesk_ticket,
    )
    from education_system.systems.university.domains.student_support.domain.student_support import (
        auth as support_auth, schema, service,
    )
    if not support_auth.is_case_worker(auth):
        print("Only support staff can import tickets.")
        return

    filename = input("Enter CSV filename to import: ").strip()

    if not os.path.exists(filename):
        print("File not found.")
        return

    import csv
    try:
        with open(filename, 'r', encoding='utf-8') as csvfile:
            rows = list(csv.DictReader(csvfile))
    except (OSError, csv.Error, UnicodeDecodeError) as e:
        print(f"Error importing tickets: {e}")
        return

    imported_count = 0
    for line, row in enumerate(rows, 2):
        if not all(row.get(k) for k in ['subject', 'message', 'category', 'submitter']):
            print(f"Line {line}: skipped - subject, message, category and submitter are required")
            continue
        try:
            result = submit_helpdesk_ticket(
                auth, subject=row['subject'], description=row['message'],
                category=row['category'], priority=row.get('priority') or 'medium',
                requester=row['submitter'].strip(), channel='import')
        except (PermissionError, ValueError) as e:
            print(f"Line {line}: {e}")
            continue
        imported_count += 1
        if result.get('crisis'):
            print(f"Line {line}: ticket #{result['ticket_id']} used crisis language - it is now a "
                  "safeguarding ticket and the safeguarding team has been told.")
        status = schema.normalize_status(row.get('status'), default='open')
        if status != 'open':
            try:
                service.set_status(auth, result['ticket_id'], status, note="Imported")
            except (PermissionError, ValueError) as e:
                print(f"Line {line}: ticket #{result['ticket_id']} left open: {e}")

    print(f"Successfully imported {imported_count} tickets from {filename}")

def export_analytics_data(auth):
    """Export ticket figures (counts only) over the tickets the signed-in
    support staff member may see, as JSON."""
    from education_system.systems.university.domains.student_support.domain.helpdesk.tickets.service import (
        ticket_counts,
    )
    try:
        year_ago = datetime.now().replace(day=1).strftime('%Y-%m-%d')
        year_ago = f"{int(year_ago[:4]) - 1}{year_ago[4:]}"
        analytics_data = {
            'generated_at': datetime.now().isoformat(),
            'generated_by': auth.current_user['username'],
            'summary': {
                'total_tickets': ticket_counts(auth),
                'tickets_by_status': ticket_counts(auth, by='status'),
                'tickets_by_category': ticket_counts(auth, by='category'),
                'tickets_by_team': ticket_counts(auth, by='team'),
            },
            'detailed_stats': {
                'monthly_trends': dict(sorted(ticket_counts(
                    auth, by='month', filters={'date_from': year_ago}).items())),
            },
        }

        os.makedirs(paths.UNIVERSITY_EXPORTS_TICKETS_DIR, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = paths.UNIVERSITY_EXPORTS_TICKETS_DIR / f"analytics_export_{timestamp}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(analytics_data, f, indent=2)

        print(f"Analytics data exported to {filename}")

    except (PermissionError, ValueError, OSError) as e:
        print(f"Error exporting analytics: {e}")
