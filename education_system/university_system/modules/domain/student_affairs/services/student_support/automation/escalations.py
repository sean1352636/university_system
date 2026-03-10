"""
Automatic ticket escalation.
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
from education_system.university_system.utils.logging.log_config import get_log_file

from ..config import (
    SUPPORT_DB, TICKET_STATUSES, TICKET_PRIORITIES, SUPPORT_CATEGORIES,
    NotificationType, TicketSentiment, FileType, SupportConfig
)
from .. import auth as _auth_mod
from ..auth import get_current_user_safe, require_auth, has_staff_permissions

logger = logging.getLogger(__name__)

def _process_escalations():
    """Process automatic escalations based on rules"""
    try:
        conn = sqlite3.connect(SUPPORT_DB)
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='escalation_rules'")
        if not cursor.fetchone():
            logger.debug("Escalation rules table doesn't exist yet, skipping escalation processing")
            conn.close()
            return
        
        # Get active escalation rules
        cursor.execute('SELECT * FROM escalation_rules WHERE is_active = 1')
        rules = cursor.fetchall()
        
        for rule in rules:
            _apply_escalation_rule(rule, cursor)
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        logger.error(f"Error processing escalations: {e}")
    

def _apply_escalation_rule(rule, cursor):
    """Apply a specific escalation rule with improved error handling"""
    rule_id, name, category, priority, condition_type, condition_value, action_type, action_target, is_active, created_by, created_datetime = rule
    
    try:
        # Check if required columns exist in support_tickets table
        cursor.execute("PRAGMA table_info(support_tickets)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'created_datetime' not in columns:
            # Fall back to registration_datetime or skip time-based rules
            if condition_type == 'time_based':
                logger.warning(f"Skipping time-based escalation rule {rule_id}: created_datetime column missing")
                return
        
        # Build query based on rule conditions
        query = "SELECT * FROM support_tickets WHERE status NOT IN ('Resolved', 'Closed', 'Escalated')"
        params = []
        
        if category:
            query += " AND category = ?"
            params.append(category)
        
        if priority:
            query += " AND priority = ?"
            params.append(priority)
        
        if condition_type == 'time_based':
            hours_threshold = float(condition_value)
            threshold_time = datetime.datetime.now() - datetime.timedelta(hours=hours_threshold)
            
            # Use created_datetime if available, otherwise fall back to registration_datetime
            if 'created_datetime' in columns:
                query += " AND created_datetime < ?"
            else:
                # Check if there's a registration_datetime column as fallback
                if 'registration_datetime' in columns:
                    query += " AND registration_datetime < ?"
                    logger.info(f"Using registration_datetime as fallback for escalation rule {rule_id}")
                else:
                    logger.warning(f"No suitable datetime column found for escalation rule {rule_id}")
                    return
            
            params.append(threshold_time.strftime('%Y-%m-%d %H:%M:%S'))
        
        cursor.execute(query, params)
        tickets = cursor.fetchall()
        
        # Apply actions to matching tickets
        for ticket in tickets:
            if action_type == 'escalate':
                _escalate_ticket(ticket[0], rule_id, cursor)  # ticket[0] is ticket_id
            elif action_type == 'notify':
                _create_escalation_notification(ticket[0], action_target, cursor)
            elif action_type == 'reassign':
                _reassign_ticket(ticket[0], action_target, cursor)
        
    except Exception as e:
        logger.error(f"Error applying escalation rule {rule_id}: {e}")

def _escalate_ticket(ticket_id, rule_id, cursor):
    """Escalate a ticket"""
    escalation_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Update ticket status
    cursor.execute('''
    UPDATE support_tickets 
    SET status = 'Escalated', escalated_at = ?, last_updated_datetime = ?
    WHERE ticket_id = ?
    ''', (escalation_time, escalation_time, ticket_id))
    
    # Add escalation response
    cursor.execute('''
    INSERT INTO ticket_responses (
        ticket_id, responder_id, responder_role, response_text,
        response_datetime, is_auto_generated
    ) VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        ticket_id, 'system', 'system',
        f'Ticket automatically escalated due to escalation rule #{rule_id}',
        escalation_time, 1
    ))

def _create_escalation_notification(ticket_id, target, cursor):
    """Create notification for escalation"""
    if not target:
        logger.warning(f"Cannot create escalation notification for ticket #{ticket_id}: target is NULL")
        return

    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute('''
    INSERT INTO notifications (
        user_id, title, message, notification_type,
        related_ticket_id, created_datetime
    ) VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        target, 'Ticket Escalation Alert',
        f'Ticket #{ticket_id} requires attention due to escalation rules.',
        NotificationType.EMAIL.value, ticket_id, timestamp
    ))

def _reassign_ticket(ticket_id, new_assignee, cursor):
    """Reassign a ticket"""
    update_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute('''
    UPDATE support_tickets 
    SET assigned_to = ?, last_updated_datetime = ?
    WHERE ticket_id = ?
    ''', (new_assignee, update_time, ticket_id))
