"""
Ticket CRUD operations for Student Support.
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

from education_system.university_system.core.sql_safety import escape_like
from typing import Optional, List, Dict, Any
from functools import wraps

from education_system.university_system.infrastructure.database.db import get_connection, sqlite3, DatabaseManager
from education_system.university_system.infrastructure.email.email_manager import send_email
from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH, TICKET_TEMPLATES_DIR, UPLOAD_DIR
from education_system.university_system.utils.logging.log_config import get_log_file

from education_system.university_system.modules.domain.student_affairs.services.student_support.config import (
    SUPPORT_DB, TICKET_STATUSES, TICKET_PRIORITIES, SUPPORT_CATEGORIES,
    NotificationType, TicketSentiment, FileType, SupportConfig
)
from education_system.university_system.modules.domain.student_affairs.services.student_support import auth as _auth_mod
from education_system.university_system.modules.domain.student_affairs.services.student_support.auth import get_current_user_safe, require_auth, has_staff_permissions
from education_system.university_system.modules.domain.student_affairs.services.student_support.core.attachment_manager import _get_attachment_count, _get_last_response_info, _process_attachments
from education_system.university_system.modules.domain.student_affairs.services.student_support.automation.sentiment_analysis import _analyze_sentiment, _suggest_category, _get_auto_assignment, _estimate_resolution_time
from education_system.university_system.modules.domain.student_affairs.services.student_support.features.templates import _create_auto_response
from education_system.university_system.modules.domain.student_affairs.services.student_support.features.notifications import _create_ticket_notifications

logger = logging.getLogger(__name__)

config = SupportConfig()

def create_support_ticket(student_id, title, description, category, priority='Medium',
                        template_id=None, attachments=None, tags=None):
    """Create a new support ticket with enhanced features."""
    if not _auth_mod.auth or not _auth_mod.auth.current_user:
        raise PermissionError("You must be logged in to create a support ticket")

    try:
        # Validate inputs
        _validate_ticket_inputs(title, description, category, priority)

        # Permission check
        _check_ticket_creation_permission(student_id)

        # Sentiment analysis
        sentiment = _analyze_sentiment(description)

        # Auto-suggest category if not provided correctly
        if category not in SUPPORT_CATEGORIES:
            suggested_category = _suggest_category(title + " " + description)
            if suggested_category:
                category = suggested_category
            else:
                raise ValueError(f"Invalid category. Choose from: {', '.join(SUPPORT_CATEGORIES)}")

        # Create the ticket
        conn = sqlite3.connect(SUPPORT_DB)
        try:
            cursor = conn.cursor()

            created_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Auto-assign staff if enabled
            assigned_to = None
            if config.auto_assign_enabled:
                assigned_to = _get_auto_assignment(category, priority)

            # Estimate resolution time
            estimated_resolution = _estimate_resolution_time(category, priority)

            cursor.execute('''
            INSERT INTO support_tickets (
                student_id, title, description, category, priority, status,
                created_datetime, assigned_to, sentiment, estimated_resolution, tags
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                student_id, title, description, category, priority, 'Open',
                created_time, assigned_to, sentiment, estimated_resolution,
                json.dumps(tags or [])
            ))

            ticket_id = cursor.lastrowid

            # Handle attachments
            if attachments:
                _process_attachments(ticket_id, attachments, cursor)

            # Create auto-acknowledgment response
            _create_auto_response(ticket_id, 'acknowledgment', cursor)

            # Commit and close main transaction BEFORE calling notification helper
            # This prevents database locks from nested connections
            conn.commit()
        finally:
            conn.close()

        # Create notifications (now safe - main transaction is complete)
        _create_ticket_notifications(ticket_id, student_id, assigned_to, 'created')

        logger.info(f"Support ticket #{ticket_id} created for student {student_id} with sentiment {sentiment}")
        return ticket_id

    except Exception as e:
        logger.error(f"Error creating support ticket: {e}")
        raise

def _validate_ticket_inputs(title, description, category, priority):
    """Validate ticket creation inputs"""
    if not title or not description or not category:
        raise ValueError("Title, description and category are required")

    if len(title) > 200:
        raise ValueError("Title must be 200 characters or less")

    if len(description) > 5000:
        raise ValueError("Description must be 5000 characters or less")

    if priority not in TICKET_PRIORITIES:
        raise ValueError(f"Invalid priority. Choose from: {', '.join(TICKET_PRIORITIES)}")

def _check_ticket_creation_permission(student_id):
    """Check if user has permission to create ticket for student_id"""
    if _auth_mod.auth.current_user['role'] == 'student':
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT student_id FROM users WHERE id = ?', (_auth_mod.auth.current_user['id'],))
        result = cursor.fetchone()
        conn.close()

        if not result or result[0] != student_id:
            raise PermissionError("You can only create support tickets for your own account")

def get_student_tickets(student_id=None, filters=None, page=1, per_page=20):
    """Get support tickets with enhanced filtering and pagination."""
    if not _auth_mod.auth or not _auth_mod.auth.current_user:
        raise PermissionError("You must be logged in to view support tickets")

    try:
        conn = sqlite3.connect(SUPPORT_DB)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Build query based on user role and filters
        query, params = _build_ticket_query(student_id, filters, _auth_mod.auth.current_user)

        # Add pagination
        offset = (page - 1) * per_page
        query += f" LIMIT {per_page} OFFSET {offset}"

        cursor.execute(query, params)
        tickets = [dict(row) for row in cursor.fetchall()]

        # Get total count for pagination
        count_query = query.replace('SELECT *', 'SELECT COUNT(*)').split('ORDER BY')[0]
        cursor.execute(count_query, params)
        total_count = cursor.fetchone()[0]

        # Enhance ticket data
        for ticket in tickets:
            ticket['tags'] = json.loads(ticket.get('tags') or '[]')
            ticket['attachment_count'] = _get_attachment_count(ticket['ticket_id'], cursor)
            ticket['last_response_by'] = _get_last_response_info(ticket['ticket_id'], cursor)

        conn.close()

        result = {
            'tickets': tickets,
            'total_count': total_count,
            'page': page,
            'per_page': per_page,
            'total_pages': (total_count + per_page - 1) // per_page
        }

        logger.info(f"Retrieved {len(tickets)} tickets (page {page}) for user {_auth_mod.auth.current_user['username']}")
        return result

    except Exception as e:
        logger.error(f"Error retrieving tickets: {e}")
        raise

def _build_ticket_query(student_id, filters, current_user):
    """Build SQL query for ticket retrieval with filters"""
    base_query = "SELECT * FROM support_tickets WHERE 1=1"
    params = []

    # Role-based filtering
    if current_user['role'] == 'student':
        if not student_id:
            # Get student's own ID
            conn_main = get_connection()
            cursor_main = conn_main.cursor()
            cursor_main.execute('SELECT student_id FROM users WHERE id = ?', (current_user['id'],))
            result = cursor_main.fetchone()
            conn_main.close()

            if result:
                student_id = result[0]
            else:
                raise ValueError("No student ID associated with your account")

        base_query += " AND student_id = ?"
        params.append(student_id)
    elif student_id:
        base_query += " AND student_id = ?"
        params.append(student_id)

    # Apply filters
    if filters:
        if filters.get('status'):
            base_query += " AND status = ?"
            params.append(filters['status'])

        if filters.get('category'):
            base_query += " AND category = ?"
            params.append(filters['category'])

        if filters.get('priority'):
            base_query += " AND priority = ?"
            params.append(filters['priority'])

        if filters.get('assigned_to'):
            base_query += " AND assigned_to = ?"
            params.append(filters['assigned_to'])

        if filters.get('date_from'):
            base_query += " AND created_datetime >= ?"
            params.append(filters['date_from'])

        if filters.get('date_to'):
            base_query += " AND created_datetime <= ?"
            params.append(filters['date_to'])

        if filters.get('search'):
            base_query += " AND (title LIKE ? OR description LIKE ?)"
            search_term = f"%{escape_like(filters['search'])}%"
            params.extend([search_term, search_term])

    base_query += " ORDER BY created_datetime DESC"
    return base_query, params

def get_ticket_details(ticket_id):
    """Get detailed information about a specific ticket"""
    if not _auth_mod.auth or not _auth_mod.auth.current_user:
        raise PermissionError("You must be logged in to view ticket details")

    try:
        conn = sqlite3.connect(SUPPORT_DB)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get ticket
        cursor.execute('SELECT * FROM support_tickets WHERE ticket_id = ?', (ticket_id,))
        ticket = cursor.fetchone()

        if not ticket:
            raise ValueError(f"Ticket #{ticket_id} not found")

        # Check permissions
        if _auth_mod.auth.current_user['role'] == 'student':
            conn_main = get_connection()
            cursor_main = conn_main.cursor()
            cursor_main.execute('SELECT student_id FROM users WHERE id = ?', (_auth_mod.auth.current_user['id'],))
            result = cursor_main.fetchone()
            conn_main.close()

            if not result or result[0] != ticket['student_id']:
                raise PermissionError("You can only view your own support tickets")

        # Get responses
        cursor.execute('''
        SELECT * FROM ticket_responses
        WHERE ticket_id = ?
        ORDER BY response_datetime ASC
        ''', (ticket_id,))
        responses = [dict(row) for row in cursor.fetchall()]

        # Get attachments
        cursor.execute('SELECT * FROM ticket_attachments WHERE ticket_id = ?', (ticket_id,))
        attachments = [dict(row) for row in cursor.fetchall()]

        conn.close()

        ticket_dict = dict(ticket)
        ticket_dict['responses'] = responses
        ticket_dict['attachments'] = attachments

        return ticket_dict

    except Exception as e:
        logger.error(f"Error getting ticket details: {e}")
        raise

def get_ticket_attachments(ticket_id):
    """Get all attachments for a ticket"""
    try:
        conn = sqlite3.connect(SUPPORT_DB)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM ticket_attachments WHERE ticket_id = ? ORDER BY uploaded_datetime DESC', (ticket_id,))
        attachments = [dict(row) for row in cursor.fetchall()]

        conn.close()
        return attachments

    except Exception as e:
        logger.error(f"Error getting ticket attachments: {e}")
        return []

def download_attachment(attachment_id):
    """Download a ticket attachment"""
    if not _auth_mod.auth or not _auth_mod.auth.current_user:
        raise PermissionError("You must be logged in to download attachments")

    try:
        # Open DB connection
        conn = sqlite3.connect(SUPPORT_DB)
        cursor = conn.cursor()

        cursor.execute('SELECT file_path, original_filename FROM ticket_attachments WHERE attachment_id = ?', (attachment_id,))
        result = cursor.fetchone()
        conn.close()

        if not result:
            raise FileNotFoundError(f"Attachment with ID {attachment_id} not found")

        file_path, original_filename = result

        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"File does not exist at path: {file_path}")

        with open(file_path, 'rb') as f:
            file_data = f.read()

        logger.info(f"Attachment {attachment_id} downloaded by {_auth_mod.auth.current_user['username']}")
        return {
            'filename': original_filename,
            'data': file_data
        }

    except sqlite3.Error as e:
        logger.error(f"Database error during attachment download: {e}")
        raise Exception(f"Failed to retrieve attachment: {e}")

    except Exception as e:
        logger.error(f"Unexpected error during attachment download: {e}")
        raise

def get_ticket_history(ticket_id):
    """Get complete history of a ticket including all changes"""
    try:
        conn = sqlite3.connect(SUPPORT_DB)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get ticket details
        cursor.execute('SELECT * FROM support_tickets WHERE ticket_id = ?', (ticket_id,))
        ticket = cursor.fetchone()

        if not ticket:
            raise ValueError(f"Ticket {ticket_id} not found")

        # Check permissions
        if _auth_mod.auth.current_user['role'] == 'student':
            conn_main = get_connection()
            cursor_main = conn_main.cursor()
            cursor_main.execute('SELECT student_id FROM users WHERE id = ?', (_auth_mod.auth.current_user['id'],))
            result = cursor_main.fetchone()
            conn_main.close()

            if not result or result[0] != ticket['student_id']:
                raise PermissionError("You can only view history of your own tickets")

        # Get all responses
        cursor.execute('''
        SELECT * FROM ticket_responses
        WHERE ticket_id = ?
        ORDER BY response_datetime ASC
        ''', (ticket_id,))
        responses = [dict(row) for row in cursor.fetchall()]

        # Get attachments
        cursor.execute('SELECT * FROM ticket_attachments WHERE ticket_id = ?', (ticket_id,))
        attachments = [dict(row) for row in cursor.fetchall()]

        # Get related audit trail
        cursor.execute('''
        SELECT * FROM audit_trail
        WHERE resource_id = ? AND resource_type LIKE '%ticket%'
        ORDER BY timestamp ASC
        ''', (str(ticket_id),))
        audit_entries = [dict(row) for row in cursor.fetchall()]

        conn.close()

        # Combine into timeline
        timeline = []

        # Add ticket creation
        timeline.append({
            'type': 'creation',
            'datetime': ticket['created_datetime'],
            'data': dict(ticket)
        })

        # Add responses
        for response in responses:
            timeline.append({
                'type': 'response',
                'datetime': response['response_datetime'],
                'data': response
            })

        # Add attachments
        for attachment in attachments:
            timeline.append({
                'type': 'attachment',
                'datetime': attachment['uploaded_datetime'],
                'data': attachment
            })

        # Add audit entries
        for audit in audit_entries:
            timeline.append({
                'type': 'audit',
                'datetime': audit['timestamp'],
                'data': audit
            })

        # Sort by datetime
        timeline.sort(key=lambda x: x['datetime'])

        return {
            'ticket': dict(ticket),
            'timeline': timeline
        }

    except Exception as e:
        logger.error(f"Error getting ticket history: {e}")
        raise

def view_my_tickets_enhanced(support):
    """View student's own tickets with enhanced filtering"""
    try:
        print("\n🎫 MY SUPPORT TICKETS")
        print("="*50)

        # Get student ID from auth
        from education_system.university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()

        # Access auth through the global variable or support instance
        import sys
        auth = getattr(sys.modules.get('src.core.services.student_support'), 'auth', None)
        if not _auth_mod.auth or not _auth_mod.auth.current_user:
            print("❌ You must be logged in to view tickets.")
            conn.close()
            return

        cursor.execute('SELECT student_id FROM users WHERE id = ?', (_auth_mod.auth.current_user['id'],))
        result = cursor.fetchone()
        conn.close()

        if not result:
            print("❌ No student ID associated with your account.")
            return

        student_id = result[0]

        # Filter options
        print("📊 Filter Options:")
        print("1. All tickets")
        print("2. Open tickets")
        print("3. In Progress tickets")
        print("4. Resolved tickets")
        print("5. Search tickets")

        choice = input("\nSelect filter: ").strip()

        filters = {}

        if choice == '2':
            filters['status'] = 'Open'
        elif choice == '3':
            filters['status'] = 'In Progress'
        elif choice == '4':
            filters['status'] = 'Resolved'
        elif choice == '5':
            search_query = input("Enter search query: ").strip()
            if search_query:
                filters['search'] = search_query

        # Get tickets
        try:
            result = support.get_student_tickets(student_id, filters, page=1, per_page=20)
            tickets = result['tickets']
        except Exception as e:
            print(f"❌ Error retrieving tickets: {e}")
            return

        if not tickets:
            print("📭 No tickets found with the selected filters.")
            return

        # Display tickets
        print(f"\n🎫 Found {result['total_count']} tickets:")
        print("="*80)

        for ticket in tickets:
            status_emoji = {'Open': '🟢', 'In Progress': '⏳', 'Resolved': '✅', 'Closed': '🔒'}.get(ticket['status'], '❓')
            priority_emoji = {'Critical': '🔴', 'Urgent': '🟠', 'High': '🟡', 'Medium': '🔵', 'Low': '🟢'}.get(ticket['priority'], '⚪')

            print(f"{status_emoji} #{ticket['ticket_id']} - {ticket['title']}")
            print(f"   📂 {ticket['category']} | {priority_emoji} {ticket['priority']} | 📅 {ticket['created_datetime']}")

            if ticket.get('assigned_to'):
                print(f"   👨‍💼 Assigned to: {ticket['assigned_to']}")

            print()

        # View specific ticket
        if tickets:
            ticket_choice = input(f"View ticket details (enter ticket #) or press Enter to go back: ").strip()
            if ticket_choice.isdigit():
                ticket_id = int(ticket_choice)
                if any(t['ticket_id'] == ticket_id for t in tickets):
                    display_ticket_details_enhanced(support, ticket_id)
                else:
                    print("❌ Ticket not found in current list.")

    except Exception as e:
        print(f"❌ Error viewing tickets: {e}")

    input("\nPress Enter to continue...")

def use_ticket_template(support):
    """Create ticket using a template"""
    try:
        print("\n📋 USE TICKET TEMPLATE")
        print("="*50)

        templates = support.get_ticket_templates()

        if not templates:
            print("📭 No ticket templates available.")
            return

        print("📋 Available Templates:")
        for i, template in enumerate(templates, 1):
            print(f"{i}. {template['name']}")
            print(f"   📂 Category: {template['category']} | 🔥 Priority: {template['priority']}")
            print(f"   📈 Used {template.get('usage_count', 0)} times")
            print()

        choice = input(f"Select template (1-{len(templates)}): ").strip()

        if not choice.isdigit() or not 1 <= int(choice) <= len(templates):
            print("❌ Invalid choice.")
            return

        template = templates[int(choice) - 1]

        # Get student ID
        from education_system.university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()

        # Access auth
        import sys
        auth = getattr(sys.modules.get('src.core.services.student_support'), 'auth', None)
        if not _auth_mod.auth or not _auth_mod.auth.current_user:
            print("❌ You must be logged in to create tickets.")
            conn.close()
            return

        cursor.execute('SELECT student_id FROM users WHERE id = ?', (_auth_mod.auth.current_user['id'],))
        result = cursor.fetchone()
        conn.close()

        if not result:
            print("❌ No student ID associated with your account.")
            return

        student_id = result[0]

        print(f"\n📋 Using template: {template['name']}")
        print("="*50)

        # Pre-fill from template
        title = template['title_template']
        description = template['description_template']
        category = template['category']
        priority = template['priority']

        print(f"Title: {title}")
        print(f"Category: {category}")
        print(f"Priority: {priority}")
        print(f"\nDescription:\n{description}")

        # Allow customization
        print("\n🔧 Customize Template:")
        custom_title = input(f"Custom title (or press Enter to keep '{title}'): ").strip()
        if custom_title:
            title = custom_title

        print("Additional description (press Enter twice to finish):")
        additional_lines = []
        while True:
            line = input()
            if not line and (not additional_lines or not additional_lines[-1]):
                break
            additional_lines.append(line)

        if additional_lines:
            description += "\n\n" + '\n'.join(additional_lines)

        # Create ticket
        print("\n🎫 Creating ticket from template...")
        ticket_id = support.create_support_ticket(
            student_id, title, description, category, priority,
            template_id=template['template_id']
        )

        print(f"✅ Support ticket #{ticket_id} created successfully from template!")

        # View ticket details
        view_choice = input("\nView ticket details? (y/n): ").lower()
        if view_choice == 'y':
            display_ticket_details_enhanced(support, ticket_id)

    except Exception as e:
        print(f"❌ Error using template: {e}")

    input("\nPress Enter to continue...")

# Module-level helper functions exposed for GUI/CLI integrations

def view_all_tickets_enhanced(support):
    """View all tickets with advanced filtering (staff only)"""
    try:
        print("\n🎫 ALL SUPPORT TICKETS")
        print("="*50)

        # Advanced filter menu
        print("📊 Filter Options:")
        print("1. All tickets")
        print("2. By status")
        print("3. By category")
        print("4. By priority")
        print("5. By assigned staff")
        print("6. By date range")
        print("7. Unassigned tickets")
        print("8. High priority tickets")
        print("9. Search tickets")

        choice = input("\nSelect filter: ").strip()

        filters = {}

        if choice == '2':
            status_options = ['Open', 'In Progress', 'Resolved', 'Closed', 'Escalated', 'On Hold']
            print("\nStatuses:")
            for i, status in enumerate(status_options, 1):
                print(f"{i}. {status}")
            status_choice = input(f"Select status (1-{len(status_options)}): ").strip()
            if status_choice.isdigit() and 1 <= int(status_choice) <= len(status_options):
                filters['status'] = status_options[int(status_choice) - 1]
        elif choice == '3':
            category_options = ['Academic', 'Technical', 'Financial Aid', 'Library Services', 'Other']
            print("\nCategories:")
            for i, cat in enumerate(category_options, 1):
                print(f"{i}. {cat}")
            cat_choice = input(f"Select category (1-{len(category_options)}): ").strip()
            if cat_choice.isdigit() and 1 <= int(cat_choice) <= len(category_options):
                filters['category'] = category_options[int(cat_choice) - 1]
        elif choice == '5':
            assigned_to = input("Enter staff username: ").strip()
            if assigned_to:
                filters['assigned_to'] = assigned_to
        elif choice == '7':
            filters['assigned_to'] = None
        elif choice == '9':
            search_query = input("Enter search query: ").strip()
            if search_query:
                filters['search'] = search_query

        # Get tickets
        try:
            result = support.get_student_tickets(None, filters, page=1, per_page=20)
            tickets = result['tickets']
        except Exception as e:
            print(f"❌ Error retrieving tickets: {e}")
            return

        if not tickets:
            print("📭 No tickets found with the selected filters.")
            return

        # Display tickets
        print(f"\n🎫 Found {result['total_count']} tickets (showing page {result['page']} of {result['total_pages']}):")
        print("="*100)

        for ticket in tickets:
            status_emoji = {'Open': '🟢', 'In Progress': '⏳', 'Resolved': '✅', 'Closed': '🔒', 'Escalated': '🚨'}.get(ticket['status'], '❓')
            priority_emoji = {'Critical': '🔴', 'Urgent': '🟠', 'High': '🟡', 'Medium': '🔵', 'Low': '🟢'}.get(ticket['priority'], '⚪')

            print(f"{status_emoji} #{ticket['ticket_id']} - {ticket['title']}")
            print(f"   👤 Student: {ticket['student_id']} | 📂 {ticket['category']} | {priority_emoji} {ticket['priority']}")
            print(f"   📅 Created: {ticket['created_datetime']}")

            if ticket.get('assigned_to'):
                print(f"   👨‍💼 Assigned to: {ticket['assigned_to']}")
            else:
                print(f"   ❌ Unassigned")

            print()

        # View specific ticket
        if tickets:
            ticket_choice = input(f"View ticket details (enter ticket #) or press Enter to go back: ").strip()
            if ticket_choice.isdigit():
                ticket_id = int(ticket_choice)
                if any(t['ticket_id'] == ticket_id for t in tickets):
                    try:
                        display_ticket_details_enhanced(support, ticket_id)
                    except Exception as e:
                        print(f"❌ Error displaying ticket: {e}")
                else:
                    print("❌ Ticket not found in current list.")

    except Exception as e:
        print(f"❌ Error viewing tickets: {e}")

    input("\nPress Enter to continue...")

def display_ticket_details_enhanced(support, ticket_id):
    """Display enhanced ticket details"""
    try:
        ticket = support.get_ticket_details(ticket_id)

        print(f"\n🎫 TICKET #{ticket['ticket_id']}")
        print("="*50)
        print(f"📋 Title: {ticket['title']}")
        print(f"👤 Student: {ticket['student_id']}")
        print(f"📊 Status: {ticket['status']}")
        print(f"🔥 Priority: {ticket['priority']}")
        print(f"📂 Category: {ticket['category']}")
        print(f"📅 Created: {ticket['created_datetime']}")

        if ticket.get('assigned_to'):
            print(f"👨‍💼 Assigned to: {ticket['assigned_to']}")

        if ticket.get('estimated_resolution'):
            print(f"⏰ Est. Resolution: {ticket['estimated_resolution']}")

        if ticket.get('sentiment'):
            sentiment_emoji = {'positive': '😊', 'neutral': '😐', 'negative': '😞', 'frustrated': '😤'}
            print(f"😊 Sentiment: {sentiment_emoji.get(ticket['sentiment'], '😐')} {ticket['sentiment']}")

        if ticket.get('tags'):
            try:
                tags = json.loads(ticket['tags']) if isinstance(ticket['tags'], str) else ticket['tags']
                if tags:
                    print(f"🏷️ Tags: {', '.join(tags)}")
            except (json.JSONDecodeError, TypeError):
                pass

        print(f"\n📝 Description:")
        print(ticket['description'])

        # Attachments
        attachments = ticket.get('attachments', [])
        if attachments:
            print(f"\n📎 Attachments ({len(attachments)}):")
            for att in attachments:
                size_mb = att['file_size'] / (1024 * 1024)
                print(f"  📄 {att['original_filename']} ({size_mb:.1f}MB)")

        # Responses
        responses = ticket.get('responses', [])
        if responses:
            print(f"\n💬 Responses ({len(responses)}):")
            for response in responses:
                auto_tag = " 🤖" if response.get('is_auto_generated') else ""
                internal_tag = " 🔒" if response.get('is_internal') else ""
                print(f"\n[{response['response_datetime']}] {response['responder_role']}{auto_tag}{internal_tag}:")
                print(f"  {response['response_text']}")

    except Exception as e:
        print(f"❌ Error displaying ticket: {e}")
