"""
Data export functionality.
"""

import datetime
import json
import logging
import time
import re
import os
import hashlib
import mimetypes
import base64
import secrets
import traceback
from typing import Optional, List, Dict, Any
from functools import wraps

from education_system.university_system.infrastructure.database.db import get_connection, sqlite3, DatabaseManager
from education_system.university_system.infrastructure.email.email_manager import send_email
from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH, TICKET_TEMPLATES_DIR, UPLOAD_DIR
from education_system.university_system.infrastructure.logging.log_config import get_log_file

from education_system.university_system.modules.domain.student_affairs.services.student_support.config import (
    SUPPORT_DB, TICKET_STATUSES, TICKET_PRIORITIES, SUPPORT_CATEGORIES,
    NotificationType, TicketSentiment, FileType, SupportConfig
)
from education_system.university_system.modules.domain.student_affairs.services.student_support import auth as _auth_mod
from education_system.university_system.modules.domain.student_affairs.services.student_support.auth import get_current_user_safe, require_auth, has_staff_permissions

logger = logging.getLogger(__name__)

def export_data(export_type, filters=None, format='csv'):
    """Export support data in various formats"""
    if not _auth_mod.auth or not _auth_mod.auth.current_user or _auth_mod.auth.current_user['role'] not in ('staff', 'admin'):
        raise PermissionError("Only staff can export data")

    try:
        conn = sqlite3.connect(SUPPORT_DB)
        cursor = conn.cursor()

        if export_type == 'tickets':
            data = _export_tickets(cursor, filters)
        elif export_type == 'responses':
            data = _export_responses(cursor, filters)
        elif export_type == 'metrics':
            data = _export_metrics(cursor, filters)
        elif export_type == 'users':
            data = _export_users(cursor, filters)
        elif export_type == 'logs':
            data = _export_logs(cursor, filters)
        else:
            raise ValueError(f"Unknown export type: {export_type}")

        conn.close()

        # Format data
        if format == 'csv':
            return _format_as_csv(data)
        elif format == 'json':
            return json.dumps(data, indent=2)
        else:
            raise ValueError(f"Unknown format: {format}")

    except Exception as e:
        logger.error(f"Error exporting data: {e}")
        raise

def _export_tickets(cursor, filters):
    """Export ticket data"""
    query = "SELECT * FROM support_tickets WHERE 1=1"
    params = []

    if filters:
        if filters.get('date_from'):
            query += " AND created_datetime >= ?"
            params.append(filters['date_from'])

        if filters.get('date_to'):
            query += " AND created_datetime <= ?"
            params.append(filters['date_to'])

        if filters.get('status'):
            query += " AND status = ?"
            params.append(filters['status'])

    query += " ORDER BY created_datetime DESC"

    cursor.execute(query, params)
    columns = [description[0] for description in cursor.description]
    rows = cursor.fetchall()

    return {
        'columns': columns,
        'rows': rows
    }

def _export_responses(cursor, filters):
    """Export response data"""
    query = """
    SELECT tr.*, st.title, st.category, st.priority
    FROM ticket_responses tr
    JOIN support_tickets st ON tr.ticket_id = st.ticket_id
    WHERE 1=1
    """
    params = []

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
    rows = cursor.fetchall()

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
           (SELECT COUNT(*) FROM support_tickets WHERE student_id = u.student_id) as ticket_count
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

