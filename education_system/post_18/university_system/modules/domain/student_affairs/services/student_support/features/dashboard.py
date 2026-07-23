"""
Dashboard data and display for support system.
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

from education_system.post_18.university_system.infrastructure.database.db import get_connection, sqlite3, DatabaseManager
from education_system.post_18.university_system.infrastructure.email.email_manager import send_email
from education_system.post_18.university_system.core.paths import DEFAULT_DB_PATH, TICKET_TEMPLATES_DIR, UPLOAD_DIR
from education_system.post_18.university_system.infrastructure.logging.log_config import get_log_file

from education_system.post_18.university_system.modules.domain.student_affairs.services.student_support.config import (
    SUPPORT_DB, TICKET_STATUSES, TICKET_PRIORITIES, SUPPORT_CATEGORIES,
    NotificationType, TicketSentiment, FileType, SupportConfig
)
from education_system.post_18.university_system.modules.domain.student_affairs.services.student_support import auth as _auth_mod
from education_system.post_18.university_system.modules.domain.student_affairs.services.student_support.auth import get_current_user_safe, require_auth, has_staff_permissions
from education_system.post_18.university_system.modules.domain.student_affairs.services.student_support.features.notifications import _get_recent_notifications

logger = logging.getLogger(__name__)

def get_dashboard_data(user_role, user_id):
    """Get dashboard data based on user role"""
    # Check if we have user information
    if not user_role or not user_id:
        raise PermissionError("You must be logged in to view dashboard")

    try:
        conn = sqlite3.connect(SUPPORT_DB)
        cursor = conn.cursor()

        dashboard_data = {}

        if user_role == 'student':
            dashboard_data = _get_student_dashboard(user_id, cursor)
        elif user_role in ('staff', 'admin'):
            dashboard_data = _get_staff_dashboard(user_id, cursor)

        # Add common data
        dashboard_data['notifications'] = _get_recent_notifications(user_id, cursor)
        dashboard_data['system_status'] = _get_system_status()

        conn.close()

        logger.info(f"Dashboard data retrieved for {user_role} {user_id}")
        return dashboard_data

    except Exception as e:
        logger.error(f"Error getting dashboard data: {e}")
        raise

def _get_student_dashboard(user_id, cursor):
    """Get dashboard data for students"""
    # Get student ID
    conn_main = get_connection()
    cursor_main = conn_main.cursor()
    cursor_main.execute('SELECT student_id FROM users WHERE id = ?', (user_id,))
    result = cursor_main.fetchone()
    conn_main.close()

    if not result:
        return {}

    student_id = result[0]

    # Get ticket statistics
    cursor.execute('SELECT status, COUNT(*) FROM support_tickets WHERE user_id = ? GROUP BY status', (student_id,))
    ticket_stats = dict(cursor.fetchall())

    # Get recent tickets
    cursor.execute('''
    SELECT ticket_id, subject, status, created_at
    FROM support_tickets
    WHERE user_id = ?
    ORDER BY created_at DESC
    LIMIT 5
    ''', (student_id,))
    recent_tickets = [dict(zip(['ticket_id', 'title', 'status', 'created_datetime'], row)) for row in cursor.fetchall()]

    # Get featured resources
    cursor.execute('SELECT * FROM support_resources WHERE is_featured = 1 LIMIT 5')
    featured_resources = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]

    return {
        'ticket_stats': ticket_stats,
        'recent_tickets': recent_tickets,
        'featured_resources': featured_resources,
        'quick_actions': [
            {'name': 'Create Ticket', 'action': 'create_ticket'},
            {'name': 'View FAQs', 'action': 'view_faqs'},
            {'name': 'Search Resources', 'action': 'search_resources'}
        ]
    }

def _get_staff_dashboard(user_id, cursor):
    """Get dashboard data for staff"""
    # Get username from user_id
    conn_main = get_connection()
    cursor_main = conn_main.cursor()
    cursor_main.execute('SELECT username FROM users WHERE id = ?', (user_id,))
    result = cursor_main.fetchone()
    conn_main.close()

    if not result:
        return {}

    username = result[0]

    # Get assigned tickets
    cursor.execute('''
    SELECT status, COUNT(*)
    FROM support_tickets
    WHERE assigned_to = ?
    GROUP BY status
    ''', (username,))
    assigned_stats = dict(cursor.fetchall())

    # Get high priority tickets
    cursor.execute('''
    SELECT ticket_id, subject, priority, created_at, user_id
    FROM support_tickets
    WHERE priority IN ('High', 'Critical', 'Urgent')
    AND status NOT IN ('Resolved', 'Closed')
    ORDER BY
        CASE priority
            WHEN 'Critical' THEN 1
            WHEN 'Urgent' THEN 2
            WHEN 'High' THEN 3
        END,
        created_at ASC
    LIMIT 10
    ''')
    priority_tickets = [dict(zip(['ticket_id', 'title', 'priority', 'created_datetime', 'student_id'], row)) for row in cursor.fetchall()]

    # Get team performance metrics
    cursor.execute('''
    SELECT
        COUNT(*) as total_tickets,
        AVG(CASE WHEN resolved_at IS NOT NULL
            THEN julianday(resolved_at) - julianday(created_at)
            END) as avg_resolution_days,
        COUNT(CASE WHEN status = 'Resolved' THEN 1 END) as resolved_count
    FROM support_tickets
    WHERE created_at >= date('now', '-30 days')
    ''')

    performance_data = cursor.fetchone()
    performance_metrics = {
        'total_tickets_month': performance_data[0] or 0,
        'avg_resolution_time': round(performance_data[1] or 0, 2),
        'resolution_rate': round((performance_data[2] or 0) / max(performance_data[0] or 1, 1) * 100, 1)
    }

    # Get recent activity
    cursor.execute('''
    SELECT tr.ticket_id, st.subject, tr.response_datetime, tr.responder_role
    FROM ticket_responses tr
    JOIN support_tickets st ON tr.ticket_id = st.ticket_id
    WHERE tr.response_datetime >= datetime('now', '-24 hours')
    ORDER BY tr.response_datetime DESC
    LIMIT 10
    ''')
    recent_activity = [dict(zip(['ticket_id', 'title', 'datetime', 'responder_role'], row)) for row in cursor.fetchall()]

    return {
        'assigned_stats': assigned_stats,
        'priority_tickets': priority_tickets,
        'performance_metrics': performance_metrics,
        'recent_activity': recent_activity,
        'quick_actions': [
            {'name': 'View Assigned Tickets', 'action': 'view_assigned'},
            {'name': 'Manage Templates', 'action': 'manage_templates'},
            {'name': 'View Reports', 'action': 'view_reports'}
        ]
    }

def _get_system_status():
    """Get current system status"""
    return {
        'status': 'operational',
        'last_maintenance': '2024-01-15 02:00:00',
        'next_maintenance': '2024-02-15 02:00:00',
        'active_incidents': 0
    }

def display_dashboard(support):
    """Display user dashboard"""
    try:
        dashboard_data = support.get_dashboard_data(_auth_mod.auth.current_user['role'], _auth_mod.auth.current_user['id'])

        print("\n📊 DASHBOARD")
        print("="*50)

        if _auth_mod.auth.current_user['role'] == 'student':
            # Student dashboard
            stats = dashboard_data.get('ticket_stats', {})
            print(f"🎫 Your Tickets: Open: {stats.get('Open', 0)}, In Progress: {stats.get('In Progress', 0)}, Resolved: {stats.get('Resolved', 0)}")

            print("\n📋 Recent Tickets:")
            for ticket in dashboard_data.get('recent_tickets', [])[:5]:
                print(f"  #{ticket['ticket_id']} - {ticket['title']} ({ticket['status']})")

            print("\n⭐ Featured Resources:")
            for resource in dashboard_data.get('featured_resources', [])[:3]:
                print(f"  📄 {resource['title']} - {resource['description'][:50]}...")

        else:
            # Staff dashboard
            stats = dashboard_data.get('assigned_stats', {})
            print(f"🎫 Assigned Tickets: Open: {stats.get('Open', 0)}, In Progress: {stats.get('In Progress', 0)}")

            metrics = dashboard_data.get('performance_metrics', {})
            print(f"📈 Performance (30 days): {metrics.get('total_tickets_month', 0)} tickets, {metrics.get('avg_resolution_time', 0)} days avg resolution")

            print("\n🚨 High Priority Tickets:")
            for ticket in dashboard_data.get('priority_tickets', [])[:5]:
                print(f"  #{ticket['ticket_id']} - {ticket['title']} ({ticket['priority']})")

        # Notifications
        notifications = dashboard_data.get('notifications', [])
        if notifications:
            print(f"\n🔔 Recent Notifications ({len(notifications)}):")
            for notif in notifications[:3]:
                status = "📫" if notif['is_read'] else "📬"
                print(f"  {status} {notif['title']}")

    except Exception as e:
        print(f"Error loading dashboard: {e}")

    input("\nPress Enter to continue...")

def display_support_menu():
    """Enhanced version of the support menu with new features"""
    from education_system.post_18.university_system.modules.domain.student_affairs.services.student_support import EnhancedStudentSupport
    from education_system.post_18.university_system.modules.domain.student_affairs.services.student_support.features.search import perform_advanced_search
    from education_system.post_18.university_system.modules.domain.student_affairs.services.student_support.utils.helpers import (
        display_enhanced_faqs,
        display_enhanced_resources,
        create_enhanced_ticket,
        manage_preferences,
    )
    from education_system.post_18.university_system.modules.domain.student_affairs.services.student_support.features.knowledge_base import browse_knowledge_base, manage_knowledge_base_menu
    from education_system.post_18.university_system.modules.domain.student_affairs.services.student_support.core.ticket_manager import view_my_tickets_enhanced, use_ticket_template, view_all_tickets_enhanced
    from education_system.post_18.university_system.modules.domain.student_affairs.services.student_support.features.reports import generate_reports_menu
    from education_system.post_18.university_system.modules.domain.student_affairs.services.student_support.features.templates import manage_templates_menu
    from education_system.post_18.university_system.modules.domain.student_affairs.services.student_support.operations.bulk_operations import bulk_operations_menu
    from education_system.post_18.university_system.modules.domain.student_affairs.services.student_support.operations.export import export_data_menu
    from education_system.post_18.university_system.modules.domain.student_affairs.services.student_support.features.notifications import view_notifications
    if _auth_mod.auth is None:
        from education_system.post_18.university_system.infrastructure.auth import UserAuth
        from education_system.post_18.university_system.infrastructure.shared_context import get_auth
        try:
            auth_instance = get_auth()
            if auth_instance is None:
                auth_instance = UserAuth()
            _auth_mod.set_auth(auth_instance)
        except Exception as e:
            print(f"Error initializing authentication system: {e}")
            return

    # Initialize enhanced support system
    try:
        config = SupportConfig()
        support = EnhancedStudentSupport(config)
    except Exception as e:
        print(f"Error initializing enhanced student support system: {e}")
        return

    while True:
        print("\n" + "="*60)
        print("🎓 ENHANCED STUDENT SUPPORT PORTAL")
        print("="*60)

        if not _auth_mod.auth or not _auth_mod.auth.current_user:
            print("❌ You must be logged in to access the support portal.")
            break

        user_role = _auth_mod.auth.current_user['role']
        print(f"👤 Logged in as: {_auth_mod.auth.current_user['username']} ({user_role})")

        options = []
        option_num = 1

        # Dashboard
        print(f"{option_num}. 📊 View Dashboard")
        options.append('dashboard')
        option_num += 1

        # Common features
        print(f"{option_num}. 🔍 Advanced Search")
        options.append('advanced_search')
        option_num += 1

        print(f"{option_num}. ❓ Browse FAQs")
        options.append('view_faqs')
        option_num += 1

        print(f"{option_num}. 📚 Knowledge Base")
        options.append('knowledge_base')
        option_num += 1

        print(f"{option_num}. 📋 Support Resources")
        options.append('view_resources')
        option_num += 1

        # Student features
        if user_role == 'student':
            print(f"{option_num}. 🎫 Create Support Ticket")
            options.append('create_ticket')
            option_num += 1

            print(f"{option_num}. 📋 My Support Tickets")
            options.append('my_tickets')
            option_num += 1

            print(f"{option_num}. 📋 Use Ticket Template")
            options.append('use_template')
            option_num += 1

        # Staff features
        if user_role in ('staff', 'admin'):
            print(f"{option_num}. 🎫 All Support Tickets")
            options.append('all_tickets')
            option_num += 1

            print(f"{option_num}. 📊 Generate Reports")
            options.append('reports')
            option_num += 1

            print(f"{option_num}. 🔧 Manage Templates")
            options.append('manage_templates')
            option_num += 1

            print(f"{option_num}. 📝 Manage Knowledge Base")
            options.append('manage_kb')
            option_num += 1

            print(f"{option_num}. 🔄 Bulk Operations")
            options.append('bulk_operations')
            option_num += 1

            print(f"{option_num}. 📤 Export Data")
            options.append('export_data')
            option_num += 1

        # Settings and preferences
        print(f"{option_num}. ⚙️ Preferences")
        options.append('preferences')
        option_num += 1

        print(f"{option_num}. 🔔 Notifications")
        options.append('notifications')
        option_num += 1

        print(f"{option_num}. ↩️ Return to Main Menu")

        print("\n" + "-"*60)
        choice = input("Enter your choice: ").strip()

        if choice.isdigit() and 1 <= int(choice) <= len(options) + 1:
            idx = int(choice) - 1
            if idx == len(options):
                break

            action = options[idx]

            try:
                if action == 'dashboard':
                    display_dashboard(support)
                elif action == 'advanced_search':
                    perform_advanced_search(support)
                elif action == 'view_faqs':
                    display_enhanced_faqs(support)
                elif action == 'knowledge_base':
                    browse_knowledge_base(support)
                elif action == 'view_resources':
                    display_enhanced_resources(support)
                elif action == 'create_ticket':
                    create_enhanced_ticket(support)
                elif action == 'my_tickets':
                    view_my_tickets_enhanced(support)
                elif action == 'use_template':
                    use_ticket_template(support)
                elif action == 'all_tickets':
                    view_all_tickets_enhanced(support)
                elif action == 'reports':
                    generate_reports_menu(support)
                elif action == 'manage_templates':
                    manage_templates_menu(support)
                elif action == 'manage_kb':
                    manage_knowledge_base_menu(support)
                elif action == 'bulk_operations':
                    bulk_operations_menu(support)
                elif action == 'export_data':
                    export_data_menu(support)
                elif action == 'preferences':
                    manage_preferences(support)
                elif action == 'notifications':
                    view_notifications(support)

            except Exception as e:
                print(f"\n❌ Error: {e}")
                input("Press Enter to continue...")

        else:
            print("❌ Invalid choice. Please try again.")

# Enhanced CLI functions (simplified for brevity)