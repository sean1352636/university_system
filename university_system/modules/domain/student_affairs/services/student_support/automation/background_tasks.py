"""
Background task processing.
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
import threading
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


def _start_background_tasks():
    """Start background tasks for escalation and notifications"""
    def background_worker():
        while True:
            try:
                _process_escalations()
                _process_notification_queue()
                _update_metrics()
                time.sleep(300)  # Run every 5 minutes
            except Exception as e:
                logger.error(f"Background task error: {e}")
                time.sleep(60)  # Wait 1 minute before retrying
    
    # Only start background tasks if _auth_mod.auth is available
    if _auth_mod.auth and _auth_mod.auth.current_user:
        background_thread = threading.Thread(target=background_worker, daemon=True)
        background_thread.start()
        logger.info("Background tasks started")
    else:
        logger.info("Background tasks not started - no authentication available")
        

def _process_notification_queue():
    """Process pending notifications"""
    try:
        conn = sqlite3.connect(SUPPORT_DB)
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='notifications'")
        if not cursor.fetchone():
            logger.debug("Notifications table doesn't exist yet, skipping notification processing")
            conn.close()
            return
        
        # Mark expired notifications
        cursor.execute('''
        UPDATE notifications 
        SET is_read = 1 
        WHERE expires_at < datetime('now') AND is_read = 0
        ''')
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        logger.error(f"Error processing notification queue: {e}")
        



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

def _load_staff_assignments():
    """Load staff assignment mappings from database"""
    try:
        conn = sqlite3.connect(SUPPORT_DB)
        cursor = conn.cursor()

        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='staff_assignments'")
        if not cursor.fetchone():
            logger.info("Staff assignments table doesn't exist yet, using empty assignments")
            conn.close()
            return {}

        cursor.execute('SELECT staff_id, category, is_primary FROM staff_assignments WHERE auto_assign_enabled = 1')

        staff_assignments = {}
        for staff_id, category, is_primary in cursor.fetchall():
            if category not in staff_assignments:
                staff_assignments[category] = []
            staff_assignments[category].append({
                'staff_id': staff_id,
                'is_primary': bool(is_primary)
            })

        conn.close()
        logger.info(f"Loaded staff assignments for {len(staff_assignments)} categories")
        return staff_assignments

    except Exception as e:
        logger.error(f"Error loading staff assignments: {e}")
        return {}
    