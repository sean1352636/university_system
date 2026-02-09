"""
Ticket status management for Student Support.
"""

import sqlite3
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

from university_system.infrastructure.database.db import get_connection, sqlite3, DatabaseManager
from university_system.infrastructure.email.email_manager import send_email
from university_system.modules.shared.constants.paths import DEFAULT_DB_PATH, TICKET_TEMPLATES_DIR, UPLOAD_DIR
from university_system.utils.logging.log_config import get_log_file

from ..config import (
    SUPPORT_DB, TICKET_STATUSES, TICKET_PRIORITIES, SUPPORT_CATEGORIES,
    NotificationType, TicketSentiment, FileType, SupportConfig
)
from .. import auth as _auth_mod
from ..auth import get_current_user_safe, require_auth, has_staff_permissions



logger = logging.getLogger(__name__)


def update_ticket_status(ticket_id, new_status, resolution_notes=None):
    """Update the status of a support ticket with enhanced tracking."""
    if not _auth_mod.auth or not _auth_mod.auth.current_user:
        raise PermissionError("You must be logged in to update a ticket status")
    
    if _auth_mod.auth.current_user['role'] not in ('staff', 'admin'):
        raise PermissionError("Only staff members can update ticket status")
    
    try:
        if new_status not in TICKET_STATUSES:
            raise ValueError(f"Invalid status. Choose from: {', '.join(TICKET_STATUSES)}")
        
        conn = sqlite3.connect(SUPPORT_DB)
        cursor = conn.cursor()
        
        # Get current ticket
        cursor.execute('SELECT * FROM support_tickets WHERE ticket_id = ?', (ticket_id,))
        ticket = cursor.fetchone()
        
        if not ticket:
            raise ValueError(f"Ticket #{ticket_id} not found")
        
        old_status = ticket[6]
        update_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Build update query based on status
        update_fields = {
            'status': new_status,
            'last_updated_datetime': update_time,
            'assigned_to': _auth_mod.auth.current_user['username']
        }
        
        if new_status == 'Resolved':
            update_fields['resolved_at'] = update_time
        elif new_status == 'Closed':
            update_fields['closed_at'] = update_time
        
        # Build SQL
        set_clause = ', '.join([f"{k} = ?" for k in update_fields.keys()])
        values = list(update_fields.values()) + [ticket_id]
        
        cursor.execute(f'UPDATE support_tickets SET {set_clause} WHERE ticket_id = ?', values)
        
        # Add system response about status change
        response_text = f"Ticket status updated from '{old_status}' to '{new_status}'"
        if resolution_notes:
            response_text += f"\n\nResolution Notes: {resolution_notes}"
        
        cursor.execute('''
        INSERT INTO ticket_responses (
            ticket_id, responder_id, responder_role, response_text, 
            response_datetime, is_auto_generated
        ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            ticket_id, _auth_mod.auth.current_user['id'], _auth_mod.auth.current_user['role'], 
            response_text, update_time, 1
        ))
        
        # Commit and close main transaction BEFORE calling helper methods
        # This prevents database locks from nested connections
        conn.commit()
        conn.close()

        # Store values needed for helper methods (ticket data no longer accessible after close)
        student_id = ticket[1]

        # Create notifications (now safe - main transaction is complete)
        _create_status_update_notifications(ticket_id, student_id, old_status, new_status)

        # Record metrics
        _record_status_change_metrics(ticket_id, old_status, new_status, update_time)

        # Trigger satisfaction survey for resolved tickets
        if new_status == 'Resolved' and config.satisfaction_survey_enabled:
            _trigger_satisfaction_survey(ticket_id, student_id)

        logger.info(f"Updated status of ticket #{ticket_id} from '{old_status}' to '{new_status}' by {_auth_mod.auth.current_user['username']}")
        return True
        
    except Exception as e:
        logger.error(f"Error updating ticket status: {e}")
        raise


def _create_status_update_notifications(ticket_id, student_id, old_status, new_status):
    """Create notifications for status updates"""
    # Skip if student_id is None or invalid
    if not student_id:
        logger.warning(f"Cannot create notification for ticket #{ticket_id}: student_id is None")
        return

    conn = None
    try:
        conn = sqlite3.connect(SUPPORT_DB, timeout=10)
        cursor = conn.cursor()

        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Notify student
        cursor.execute('''
        INSERT INTO notifications (
            user_id, title, message, notification_type,
            related_ticket_id, created_datetime
        ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            student_id, 'Ticket Status Updated',
            f'Your support ticket #{ticket_id} status has been updated to {new_status}.',
            NotificationType.EMAIL.value, ticket_id, timestamp
        ))

        conn.commit()

    except Exception as e:
        logger.error(f"Error creating status update notifications: {e}")
    finally:
        if conn:
            conn.close()


def _record_status_change_metrics(ticket_id, old_status, new_status, timestamp):
    """Record metrics for status changes"""
    conn = None
    try:
        conn = sqlite3.connect(SUPPORT_DB, timeout=10)
        cursor = conn.cursor()

        # Get username safely
        username = 'unknown'
        if _auth_mod.auth and _auth_mod.auth.current_user:
            username = _auth_mod.auth.current_user.get('username', 'unknown')

        # Record the status change
        cursor.execute('''
        INSERT INTO system_metrics (
            metric_name, metric_value, category, recorded_datetime, metadata
        ) VALUES (?, ?, ?, ?, ?)
        ''', (
            'status_change', 1, 'tickets', timestamp,
            json.dumps({
                'ticket_id': ticket_id,
                'old_status': old_status,
                'new_status': new_status,
                'changed_by': username
            })
        ))

        conn.commit()

    except Exception as e:
        logger.error(f"Error recording status change metrics: {e}")
    finally:
        if conn:
            conn.close()


def _trigger_satisfaction_survey(ticket_id, student_id):
    """Trigger satisfaction survey for resolved ticket"""
    # Skip if student_id is None or invalid
    if not student_id:
        logger.warning(f"Cannot trigger satisfaction survey for ticket #{ticket_id}: student_id is None")
        return

    conn = None
    try:
        conn = sqlite3.connect(SUPPORT_DB, timeout=10)
        cursor = conn.cursor()

        # Create survey notification
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        expires_at = (datetime.datetime.now() + datetime.timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        INSERT INTO notifications (
            user_id, title, message, notification_type,
            related_ticket_id, created_datetime, expires_at, data
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            student_id, 'Rate Your Support Experience',
            f'Please rate your support experience for ticket #{ticket_id}.',
            NotificationType.IN_APP.value, ticket_id, timestamp, expires_at,
            json.dumps({'survey_type': 'satisfaction', 'ticket_id': ticket_id})
        ))

        conn.commit()

    except Exception as e:
        logger.error(f"Error triggering satisfaction survey: {e}")
    finally:
        if conn:
            conn.close()


def update_status_enhanced(support, ticket_id):
    """Enhanced status update with resolution notes"""
    try:
        print(f"\n📊 UPDATE TICKET #{ticket_id} STATUS")
        print("="*50)
        
        # Show current status
        ticket = support.get_ticket_details(ticket_id)
        print(f"Current Status: {ticket['status']}")
        
        # Status selection
        print("\nNew Status:")
        for i, status in enumerate(TICKET_STATUSES, 1):
            print(f"{i}. {status}")
        
        choice = input(f"Select new status (1-{len(TICKET_STATUSES)}): ").strip()
        
        if not choice.isdigit() or not 1 <= int(choice) <= len(TICKET_STATUSES):
            print("❌ Invalid status choice.")
            return
        
        new_status = TICKET_STATUSES[int(choice) - 1]
        
        # Resolution notes for resolved/closed tickets
        resolution_notes = None
        if new_status in ['Resolved', 'Closed']:
            print(f"\nResolution notes for {new_status} status:")
            lines = []
            while True:
                line = input()
                if not line and (not lines or not lines[-1]):
                    break
                lines.append(line)
            
            if lines:
                resolution_notes = '\n'.join(lines)
        
        # Update status
        support.update_ticket_status(ticket_id, new_status, resolution_notes)
        print(f"✅ Ticket #{ticket_id} status updated to '{new_status}'")
        
    except Exception as e:
        print(f"❌ Error updating status: {e}")


def add_internal_note(support, ticket_id):
    """Add internal note to ticket"""
    try:
        print(f"\n🔒 ADD INTERNAL NOTE TO TICKET #{ticket_id}")
        print("="*50)
        
        print("Internal note (visible only to staff, press Enter twice to finish):")
        lines = []
        while True:
            line = input()
            if not line and (not lines or not lines[-1]):
                break
            lines.append(line)
        
        note_text = '\n'.join(lines)
        
        if not note_text:
            print("❌ Note cannot be empty.")
            return
        
        # Add as internal response
        support.add_ticket_response(ticket_id, note_text, is_internal=True)
        print("✅ Internal note added successfully!")
        
    except Exception as e:
        print(f"❌ Error adding internal note: {e}")


def view_ticket_history(support, ticket_id):
    """View complete ticket history"""
    try:
        print(f"\n📚 TICKET #{ticket_id} HISTORY")
        print("="*60)
        
        history = support.get_ticket_history(ticket_id)
        ticket = history['ticket']
        timeline = history['timeline']
        
        print(f"🎫 {ticket['title']}")
        print(f"👤 Student: {ticket['student_id']}")
        print(f"📊 Current Status: {ticket['status']}")
        print(f"🔥 Priority: {ticket['priority']}")
        print(f"📂 Category: {ticket['category']}")
        
        print(f"\n📅 TIMELINE ({len(timeline)} events):")
        print("="*60)
        
        for event in timeline:
            event_type = event['type']
            data = event['data']
            datetime_str = event['datetime']
            
            if event_type == 'creation':
                print(f"🎫 [{datetime_str}] Ticket Created")
                print(f"   📝 {data['description'][:100]}...")
                
            elif event_type == 'response':
                responder = data['responder_role']
                is_internal = data.get('is_internal', False)
                is_auto = data.get('is_auto_generated', False)
                
                internal_tag = " 🔒" if is_internal else ""
                auto_tag = " 🤖" if is_auto else ""
                
                print(f"💬 [{datetime_str}] Response by {responder}{internal_tag}{auto_tag}")
                print(f"   📝 {data['response_text'][:100]}...")
                
            elif event_type == 'attachment':
                print(f"📎 [{datetime_str}] Attachment Added")
                print(f"   📄 {data['original_filename']} ({data['file_size']} bytes)")
                
            elif event_type == 'audit':
                print(f"🔍 [{datetime_str}] System Event")
                print(f"   ⚙️ {data['action']} by {data.get('user_id', 'system')}")
            
            print()
        
        # Pagination for large histories
        if len(timeline) > 20:
            print(f"... showing first 20 of {len(timeline)} events")
            show_all = input("Show all events? (y/n): ").lower()
            if show_all == 'y':
                for event in timeline[20:]:
                    # Display remaining events (same format as above)
                    pass
        
    except Exception as e:
        print(f"❌ Error viewing ticket history: {e}")
    
    input("\nPress Enter to continue...")
