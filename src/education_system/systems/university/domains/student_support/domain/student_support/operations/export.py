"""
Data export functionality.
"""

import datetime
import json
import logging

from education_system.systems.university.infrastructure.database.db import sqlite3

from education_system.systems.university.domains.student_support.domain.student_support.config import (
    SUPPORT_DB, TICKET_STATUSES, TICKET_PRIORITIES, SUPPORT_CATEGORIES
)
from education_system.systems.university.domains.student_support.domain.student_support import auth as _auth_mod

logger = logging.getLogger(__name__)

def export_data(export_type, filters=None, format='csv'):
    """Export support data in various formats"""
    if not _auth_mod.auth or not _auth_mod.auth.current_user or not _auth_mod.is_support_staff():
        raise PermissionError("Only staff can export data")

    try:
        conn = sqlite3.connect(SUPPORT_DB)
        try:
            cursor = conn.cursor()
            # Tickets and replies: only those the exporter may see, and never
            # the sealed text of restricted / safeguarding tickets.
            scope = _auth_mod.ticket_scope_sql(_auth_mod.auth, conn=conn)
            data = _export(export_type, cursor, filters, scope)
        finally:
            conn.close()

        # Format data
        if format == 'csv':
            return _format_as_csv(data)
        elif format == 'json':
            return json.dumps(data, indent=2, default=str)
        else:
            raise ValueError(f"Unknown format: {format}")

    except Exception as e:
        logger.error(f"Error exporting data: {e}")
        raise


def _export(export_type, cursor, filters, scope=("1=1", [])):
    """The rows of one export type."""
    exporters = {
        'tickets': _export_tickets,
        'responses': _export_responses,
        'metrics': _export_metrics,
        'users': _export_users,
        'logs': _export_logs,
    }
    if export_type not in exporters:
        raise ValueError(f"Unknown export type: {export_type}")
    if export_type in ('tickets', 'responses'):
        return exporters[export_type](cursor, filters, scope)
    return exporters[export_type](cursor, filters)


def _masked(columns, rows, tier_column, sealed_columns):
    """Rows with sealed columns replaced by the placeholder on restricted /
    safeguarding tickets, and revealed (plain) on the rest."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        confidentiality, service,
    )
    tier_at = columns.index(tier_column)
    hide = [columns.index(c) for c in sealed_columns if c in columns]
    out = []
    for row in rows:
        row = list(row)
        sealed = str(row[tier_at] or '').lower() in confidentiality.SEALED_TIERS
        for i in hide:
            if row[i]:
                row[i] = service.SEALED_PLACEHOLDER if sealed else confidentiality.reveal(row[i])
        out.append(tuple(row))
    return out


def _export_tickets(cursor, filters, scope=("1=1", [])):
    """Export ticket data"""
    query = f"SELECT * FROM support_tickets WHERE {scope[0]}"  # nosec B608 - scope SQL is built by auth.ticket_scope_sql
    params = list(scope[1])

    if filters:
        if filters.get('date_from'):
            query += " AND created_at >= ?"
            params.append(filters['date_from'])

        if filters.get('date_to'):
            query += " AND created_at <= ?"
            params.append(filters['date_to'])

        if filters.get('status'):
            from education_system.systems.university.domains.student_support.domain.student_support.schema import (
                normalize_status,
            )
            query += " AND status = ?"
            params.append(normalize_status(filters['status']))

    query += " ORDER BY created_at DESC"

    cursor.execute(query, params)
    columns = [description[0] for description in cursor.description]
    rows = _masked(columns, cursor.fetchall(), 'confidentiality', ('description', 'resolution'))

    return {
        'columns': columns,
        'rows': rows
    }

def _export_responses(cursor, filters, scope=("1=1", [])):
    """Export response data"""
    query = f"""
    SELECT tr.*, st.subject, st.category, st.priority, st.confidentiality AS ticket_confidentiality
    FROM ticket_responses tr
    JOIN support_tickets st ON tr.ticket_id = st.ticket_id
    WHERE tr.ticket_id IN (SELECT ticket_id FROM support_tickets WHERE {scope[0]})
    """  # nosec B608 - scope SQL is built by auth.ticket_scope_sql
    params = list(scope[1])

    if filters:
        if filters.get('date_from'):
            query += " AND tr.response_datetime >= ?"
            params.append(filters['date_from'])

        if filters.get('date_to'):
            query += " AND tr.response_datetime <= ?"
            params.append(filters['date_to'])

    query += " ORDER BY tr.response_datetime DESC"

    cursor.execute(query, params)
    columns = [description[0] for description in cursor.description]
    rows = _masked(columns, cursor.fetchall(), 'ticket_confidentiality', ('response_text', 'description'))

    return {
        'columns': columns,
        'rows': rows
    }

def _export_metrics(cursor, filters):
    """Export metrics data"""
    query = "SELECT * FROM system_metrics WHERE 1=1"
    params = []

    if filters:
        if filters.get('date_from'):
            query += " AND recorded_datetime >= ?"
            params.append(filters['date_from'])

        if filters.get('date_to'):
            query += " AND recorded_datetime <= ?"
            params.append(filters['date_to'])

        if filters.get('category'):
            query += " AND category = ?"
            params.append(filters['category'])

    query += " ORDER BY recorded_datetime DESC"

    cursor.execute(query, params)
    columns = [description[0] for description in cursor.description]
    rows = cursor.fetchall()

    return {
        'columns': columns,
        'rows': rows
    }

def _export_users(cursor, filters):
    """Export user data for support-related activities"""
    query = """
    SELECT u.id, u.username, u.role, u.student_id, u.email,
           u.created_at, u.last_login,
           (SELECT COUNT(*) FROM support_tickets WHERE user_id = u.student_id) as ticket_count
    FROM users u
    WHERE 1=1
    """
    params = []

    if filters:
        if filters.get('role'):
            query += " AND u.role = ?"
            params.append(filters['role'])

        if filters.get('date_from'):
            query += " AND u.created_at >= ?"
            params.append(filters['date_from'])

        if filters.get('date_to'):
            query += " AND u.created_at <= ?"
            params.append(filters['date_to'])

    query += " ORDER BY u.username"

    try:
        cursor.execute(query, params)
        columns = [description[0] for description in cursor.description]
        rows = cursor.fetchall()
    except Exception:
        # Fallback if users table has different schema
        columns = ['id', 'username', 'role', 'student_id', 'email', 'created_at', 'last_login', 'ticket_count']
        rows = []

    return {
        'columns': columns,
        'rows': rows
    }

def _export_logs(cursor, filters):
    """Export system logs and activity data"""
    # Try activity_logs table first, then fallback to audit_logs
    try:
        query = """
        SELECT log_id, timestamp, user_id, username, action_type, entity_type,
               entity_id, description, ip_address
        FROM activity_logs
        WHERE 1=1
        """
        params = []

        if filters:
            if filters.get('date_from'):
                query += " AND timestamp >= ?"
                params.append(filters['date_from'])

            if filters.get('date_to'):
                query += " AND timestamp <= ?"
                params.append(filters['date_to'])

            if filters.get('action_type'):
                query += " AND action_type = ?"
                params.append(filters['action_type'])

        query += " ORDER BY timestamp DESC LIMIT 10000"

        cursor.execute(query, params)
        columns = [description[0] for description in cursor.description]
        rows = cursor.fetchall()

        return {
            'columns': columns,
            'rows': rows
        }
    except Exception:
        # Try alternative table names
        try:
            query = "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT 10000"
            cursor.execute(query)
            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()
            return {
                'columns': columns,
                'rows': rows
            }
        except Exception:
            # Return empty result with standard columns if no logs table exists
            return {
                'columns': ['log_id', 'timestamp', 'user_id', 'action', 'entity', 'details'],
                'rows': []
            }

def _format_as_csv(data):
    """Format data as CSV string"""
    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output)

    # Write headers
    writer.writerow(data['columns'])

    # Write rows
    for row in data['rows']:
        writer.writerow(row)

    return output.getvalue()

def export_data_menu(support):
    """Export data menu (staff only)"""
    try:
        print("\n📤 EXPORT DATA")
        print("="*40)

        print("1. Export tickets")
        print("2. Export responses")
        print("3. Export metrics")
        print("4. Export filtered ticket results")
        print("5. Back")

        choice = input("\nSelect export type: ").strip()

        if choice == '1':
            export_tickets_menu(support)
        elif choice == '2':
            export_responses_menu(support)
        elif choice == '3':
            export_metrics_menu(support)
        elif choice == '4':
            export_filtered_tickets_menu(support)
        elif choice == '5':
            return
        else:
            print("❌ Invalid choice.")

    except Exception as e:
        print(f"❌ Error in export menu: {e}")

    input("\nPress Enter to continue...")

def export_tickets_menu(support):
    """Export tickets with filters"""
    print("\n📤 EXPORT TICKETS")
    print("="*40)

    # Date range
    date_from = input("From date (YYYY-MM-DD, optional): ").strip() or None
    date_to = input("To date (YYYY-MM-DD, optional): ").strip() or None

    # Status filter
    status = input(f"Status filter ({', '.join(TICKET_STATUSES)}, optional): ").strip() or None
    if status and status not in TICKET_STATUSES:
        print("❌ Invalid status.")
        return

    # Format
    print("\nExport formats:")
    print("1. CSV")
    print("2. JSON")

    format_choice = input("Select format (1-2): ").strip()
    export_format = 'csv' if format_choice == '1' else 'json'

    # Build filters
    filters = {}
    if date_from:
        filters['date_from'] = date_from
    if date_to:
        filters['date_to'] = date_to
    if status:
        filters['status'] = status

    try:
        # Export data
        print("\n📊 Exporting tickets...")
        exported_data = support.export_data('tickets', filters, export_format)

        # Save to file
        ext = 'csv' if export_format == 'csv' else 'json'
        filename = f"tickets_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"

        with open(filename, 'w') as f:
            f.write(exported_data)

        print(f"✅ Tickets exported to {filename}")

    except Exception as e:
        print(f"❌ Error exporting tickets: {e}")

def export_responses_menu(support):
    """Export responses with filters"""
    print("\n📤 EXPORT RESPONSES")
    print("="*40)

    # Date range
    date_from = input("From date (YYYY-MM-DD, optional): ").strip() or None
    date_to = input("To date (YYYY-MM-DD, optional): ").strip() or None

    # Format
    print("\nExport formats:")
    print("1. CSV")
    print("2. JSON")

    format_choice = input("Select format (1-2): ").strip()
    export_format = 'csv' if format_choice == '1' else 'json'

    # Build filters
    filters = {}
    if date_from:
        filters['date_from'] = date_from
    if date_to:
        filters['date_to'] = date_to

    try:
        # Export data
        print("\n📊 Exporting responses...")
        exported_data = support.export_data('responses', filters, export_format)

        # Save to file
        ext = 'csv' if export_format == 'csv' else 'json'
        filename = f"responses_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"

        with open(filename, 'w') as f:
            f.write(exported_data)

        print(f"✅ Responses exported to {filename}")

    except Exception as e:
        print(f"❌ Error exporting responses: {e}")

def export_metrics_menu(support):
    """Export metrics with filters"""
    print("\n📤 EXPORT METRICS")
    print("="*40)

    # Date range
    date_from = input("From date (YYYY-MM-DD, optional): ").strip() or None
    date_to = input("To date (YYYY-MM-DD, optional): ").strip() or None

    # Category filter
    category = input("Metric category (tickets, performance, satisfaction, optional): ").strip() or None

    # Format
    print("\nExport formats:")
    print("1. CSV")
    print("2. JSON")

    format_choice = input("Select format (1-2): ").strip()
    export_format = 'csv' if format_choice == '1' else 'json'

    # Build filters
    filters = {}
    if date_from:
        filters['date_from'] = date_from
    if date_to:
        filters['date_to'] = date_to
    if category:
        filters['category'] = category

    try:
        # Export data
        print("\n📊 Exporting metrics...")
        exported_data = support.export_data('metrics', filters, export_format)

        # Save to file
        ext = 'csv' if export_format == 'csv' else 'json'
        filename = f"metrics_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"

        with open(filename, 'w') as f:
            f.write(exported_data)

        print(f"✅ Metrics exported to {filename}")

    except Exception as e:
        print(f"❌ Error exporting metrics: {e}")

def export_filtered_tickets_menu(support):
    """Export tickets with advanced filters"""
    print("\n📤 EXPORT FILTERED TICKETS")
    print("="*50)

    # This would typically be called from the main ticket view
    # For now, provide a simplified version
    filters = {}

    # Interactive filter building
    print("Build export filters:")

    status = input(f"Status ({', '.join(TICKET_STATUSES)}, optional): ").strip()
    if status and status in TICKET_STATUSES:
        filters['status'] = status

    category = input(f"Category ({', '.join(SUPPORT_CATEGORIES)}, optional): ").strip()
    if category and category in SUPPORT_CATEGORIES:
        filters['category'] = category

    priority = input(f"Priority ({', '.join(TICKET_PRIORITIES)}, optional): ").strip()
    if priority and priority in TICKET_PRIORITIES:
        filters['priority'] = priority

    date_from = input("From date (YYYY-MM-DD, optional): ").strip()
    if date_from:
        filters['date_from'] = date_from

    date_to = input("To date (YYYY-MM-DD, optional): ").strip()
    if date_to:
        filters['date_to'] = date_to

    # Format selection
    print("\nExport formats:")
    print("1. CSV")
    print("2. JSON")

    format_choice = input("Select format (1-2): ").strip()
    export_format = 'csv' if format_choice == '1' else 'json'

    try:
        # Export data
        print("\n📊 Exporting filtered tickets...")
        exported_data = support.export_data('tickets', filters, export_format)

        # Save to file
        ext = 'csv' if export_format == 'csv' else 'json'
        filename = f"filtered_tickets_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"

        with open(filename, 'w') as f:
            f.write(exported_data)

        print(f"✅ Filtered tickets exported to {filename}")

    except Exception as e:
        print(f"❌ Error exporting filtered tickets: {e}")

