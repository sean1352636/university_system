"""
Ticket merging operations.
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


def merge_tickets(primary_ticket_id, secondary_ticket_ids, merge_reason):
    """Merge multiple tickets into one primary ticket"""
    if not _auth_mod.auth or not _auth_mod.auth.current_user or _auth_mod.auth.current_user['role'] not in ('staff', 'admin'):
        raise PermissionError("Only staff can merge tickets")
    
    try:
        conn = sqlite3.connect(SUPPORT_DB)
        cursor = conn.cursor()
        
        # Validate primary ticket exists
        cursor.execute('SELECT * FROM support_tickets WHERE ticket_id = ?', (primary_ticket_id,))
        primary_ticket = cursor.fetchone()
        
        if not primary_ticket:
            raise ValueError(f"Primary ticket {primary_ticket_id} not found")
        
        merge_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Merge each secondary ticket
        for secondary_id in secondary_ticket_ids:
            # Validate secondary ticket
            cursor.execute('SELECT * FROM support_tickets WHERE ticket_id = ?', (secondary_id,))
            secondary_ticket = cursor.fetchone()
            
            if not secondary_ticket:
                logger.warning(f"Secondary ticket {secondary_id} not found, skipping")
                continue
            
            # Update secondary ticket to reference primary
            cursor.execute('''
            UPDATE support_tickets 
            SET parent_ticket_id = ?, status = 'Closed', closed_at = ?
            WHERE ticket_id = ?
            ''', (primary_ticket_id, merge_time, secondary_id))
            
            # Copy responses from secondary to primary
            cursor.execute('''
            INSERT INTO ticket_responses (
                ticket_id, responder_id, responder_role, response_text, 
                response_datetime, is_internal
            )
            SELECT ?, responder_id, responder_role, 
                   '[MERGED FROM TICKET #' || ? || '] ' || response_text,
                   response_datetime, 1
            FROM ticket_responses 
            WHERE ticket_id = ?
            ''', (primary_ticket_id, secondary_id, secondary_id))
            
            # Copy attachments
            cursor.execute('''
            UPDATE ticket_attachments 
            SET ticket_id = ? 
            WHERE ticket_id = ?
            ''', (primary_ticket_id, secondary_id))
        
        # Add merge note to primary ticket
        cursor.execute('''
        INSERT INTO ticket_responses (
            ticket_id, responder_id, responder_role, response_text,
            response_datetime, is_auto_generated
        ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            primary_ticket_id, _auth_mod.auth.current_user['id'], _auth_mod.auth.current_user['role'],
            f"Tickets merged: {', '.join(map(str, secondary_ticket_ids))}. Reason: {merge_reason}",
            merge_time, 1
        ))
        
        # Update primary ticket timestamp
        cursor.execute('''
        UPDATE support_tickets 
        SET last_updated_datetime = ?
        WHERE ticket_id = ?
        ''', (merge_time, primary_ticket_id))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Tickets {secondary_ticket_ids} merged into {primary_ticket_id} by {_auth_mod.auth.current_user['username']}")
        return True
        
    except Exception as e:
        logger.error(f"Error merging tickets: {e}")
        raise


def merge_tickets_menu(support):
    """Merge multiple tickets into one"""
    print("\n🔗 MERGE TICKETS")
    print("="*40)
    
    primary_id_input = input("Enter primary ticket ID: ").strip()
    if not primary_id_input.isdigit():
        print("❌ Invalid primary ticket ID.")
        return
    
    primary_ticket_id = int(primary_id_input)
    
    secondary_ids_input = input("Enter secondary ticket IDs to merge (comma-separated): ").strip()
    if not secondary_ids_input:
        print("❌ No secondary ticket IDs provided.")
        return
    
    try:
        secondary_ticket_ids = [int(id.strip()) for id in secondary_ids_input.split(',')]
    except ValueError:
        print("❌ Invalid secondary ticket IDs. Please enter numbers only.")
        return
    
    merge_reason = input("Reason for merge: ").strip()
    if not merge_reason:
        print("❌ Merge reason is required.")
        return
    
    # Confirm operation
    print(f"\n📋 Merging tickets {secondary_ticket_ids} into primary ticket #{primary_ticket_id}")
    print(f"Reason: {merge_reason}")
    confirm = input("Confirm ticket merge? (y/n): ").lower()
    
    if confirm == 'y':
        try:
            support.merge_tickets(primary_ticket_id, secondary_ticket_ids, merge_reason)
            print(f"✅ Successfully merged {len(secondary_ticket_ids)} tickets into #{primary_ticket_id}")
        except Exception as e:
            print(f"❌ Error during ticket merge: {e}")
    else:
        print("❌ Ticket merge cancelled.")
