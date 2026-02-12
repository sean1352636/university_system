"""
Metrics tracking and recording.
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

__all__ = [
    'submit_satisfaction_rating',
    '_record_status_change_metrics',
    '_update_metrics',
]

def submit_satisfaction_rating(ticket_id, rating, feedback=None):
    """Submit satisfaction rating for a resolved ticket"""
    if not _auth_mod.auth or not _auth_mod.auth.current_user:
        raise PermissionError("You must be logged in to submit ratings")
    
    if not 1 <= rating <= 5:
        raise ValueError("Rating must be between 1 and 5")
    
    try:
        conn = sqlite3.connect(SUPPORT_DB)
        cursor = conn.cursor()
        
        # Verify ticket exists and is resolved
        cursor.execute('SELECT * FROM support_tickets WHERE ticket_id = ? AND status = "Resolved"', (ticket_id,))
        ticket = cursor.fetchone()
        
        if not ticket:
            raise ValueError("Ticket not found or not resolved")
        
        # Check if user owns the ticket (for students)
        if _auth_mod.auth.current_user['role'] == 'student':
            conn_main = get_connection()
            cursor_main = conn_main.cursor()
            cursor_main.execute('SELECT student_id FROM users WHERE id = ?', (_auth_mod.auth.current_user['id'],))
            result = cursor_main.fetchone()
            conn_main.close()
            
            if not result or result[0] != ticket[1]:  # ticket[1] is student_id
                raise PermissionError("You can only rate your own tickets")
        
        # Update satisfaction rating
        cursor.execute('''
        UPDATE support_tickets 
        SET satisfaction_rating = ?, satisfaction_feedback = ?
        WHERE ticket_id = ?
        ''', (rating, feedback, ticket_id))
        
        # Log the rating
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
        INSERT INTO system_metrics (
            metric_name, metric_value, category, recorded_datetime, metadata
        ) VALUES (?, ?, ?, ?, ?)
        ''', (
            'satisfaction_rating', rating, 'satisfaction', timestamp,
            json.dumps({'ticket_id': ticket_id, 'user_id': _auth_mod.auth.current_user['id'], 'feedback': feedback})
        ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Satisfaction rating {rating} submitted for ticket #{ticket_id} by {_auth_mod.auth.current_user['username']}")
        return True
        
    except Exception as e:
        logger.error(f"Error submitting satisfaction rating: {e}")
        raise

# Add this method to the EnhancedStudentSupport class

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

def _update_metrics():
    """Update system performance metrics with improved error handling"""
    try:
        conn = sqlite3.connect(SUPPORT_DB)
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='system_metrics'")
        if not cursor.fetchone():
            logger.debug("System metrics table doesn't exist yet, skipping metrics update")
            conn.close()
            return
        
        # Check if support_tickets table has required columns
        cursor.execute("PRAGMA table_info(support_tickets)")
        columns = [column[1] for column in cursor.fetchall()]
        
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Calculate current metrics with fallback handling
        metrics = []
        
        # Active tickets metric
        try:
            cursor.execute('SELECT COUNT(*) FROM support_tickets WHERE status NOT IN ("Resolved", "Closed")')
            active_count = cursor.fetchone()[0] or 0
            metrics.append(('active_tickets', active_count, 'tickets'))
        except Exception as e:
            logger.warning(f"Could not calculate active tickets metric: {e}")
        
        # Average response time metric
        try:
            if 'last_updated_datetime' in columns and 'created_datetime' in columns:
                cursor.execute('''
                SELECT AVG(julianday(last_updated_datetime) - julianday(created_datetime)) * 24 
                FROM support_tickets 
                WHERE last_updated_datetime IS NOT NULL AND created_datetime IS NOT NULL
                ''')
            else:
                # Skip this metric if required columns don't exist
                logger.debug("Skipping response time metric: required datetime columns missing")
                cursor.execute('SELECT 0')  # Placeholder query
            
            avg_response_time = cursor.fetchone()[0] or 0
            metrics.append(('avg_response_time', avg_response_time, 'performance'))
        except Exception as e:
            logger.warning(f"Could not calculate response time metric: {e}")
        
        # User satisfaction metric
        try:
            cursor.execute('SELECT AVG(satisfaction_rating) FROM support_tickets WHERE satisfaction_rating IS NOT NULL')
            avg_satisfaction = cursor.fetchone()[0] or 0
            metrics.append(('user_satisfaction', avg_satisfaction, 'satisfaction'))
        except Exception as e:
            logger.warning(f"Could not calculate satisfaction metric: {e}")
        
        # Insert calculated metrics
        for metric_name, value, category in metrics:
            try:
                cursor.execute('''
                INSERT INTO system_metrics (
                    metric_name, metric_value, category, recorded_datetime
                ) VALUES (?, ?, ?, ?)
                ''', (metric_name, value, category, timestamp))
            except Exception as e:
                logger.warning(f"Could not insert metric {metric_name}: {e}")
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        logger.error(f"Error updating metrics: {e}")
    
# Template management methods