"""
File attachment handling for Student Support.
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

from education_system.university_system.modules.domain.student_affairs.services.student_support.config import (
    SUPPORT_DB, TICKET_STATUSES, TICKET_PRIORITIES, SUPPORT_CATEGORIES,
    NotificationType, TicketSentiment, FileType, SupportConfig
)
from education_system.university_system.modules.domain.student_affairs.services.student_support import auth as _auth_mod
from education_system.university_system.modules.domain.student_affairs.services.student_support.auth import get_current_user_safe, require_auth, has_staff_permissions
from education_system.university_system.modules.domain.student_affairs.services.student_support.utils.audit import audit_action

logger = logging.getLogger(__name__)

def _process_attachments(ticket_id, attachments, cursor):
    """Process and store ticket attachments"""
    for attachment in attachments:
        if not _validate_file(attachment):
            continue
            
        # Generate secure filename
        secure_filename = _generate_secure_filename(attachment['filename'])
        file_path = os.path.join(str(UPLOAD_DIR), 'tickets', str(ticket_id), secure_filename)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Save file
        with open(file_path, 'wb') as f:
            f.write(attachment['data'])
        
        # Store in database
        cursor.execute('''
        INSERT INTO ticket_attachments (
            ticket_id, filename, original_filename, file_path, file_size,
            file_type, mime_type, uploaded_by, uploaded_datetime
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            ticket_id, secure_filename, attachment['filename'], file_path,
            len(attachment['data']), _get_file_type(attachment['filename']),
            attachment.get('mime_type'), _auth_mod.auth.current_user['id'],
            datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))

def _validate_file(attachment):
    """Validate uploaded file"""
    if len(attachment['data']) > config.max_file_size:
        logger.warning(f"File too large: {len(attachment['data'])} bytes")
        return False
        
    ext = os.path.splitext(attachment['filename'])[1].lower()
    if ext not in config.allowed_file_types:
        logger.warning(f"File type not allowed: {ext}")
        return False
        
    return True

def _generate_secure_filename(filename):
    """Generate a secure filename"""
    name, ext = os.path.splitext(filename)
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    random_suffix = secrets.token_hex(4)
    return f"{timestamp}_{random_suffix}{ext}"

def _get_file_type(filename):
    """Determine file type from filename"""
    ext = os.path.splitext(filename)[1].lower()
    
    if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
        return FileType.IMAGE.value
    elif ext in ['.pdf', '.doc', '.docx', '.txt', '.rtf']:
        return FileType.DOCUMENT.value
    elif ext in ['.mp4', '.avi', '.mov', '.wmv']:
        return FileType.VIDEO.value
    else:
        return FileType.OTHER.value

def _get_attachment_count(ticket_id, cursor):
    """Get number of attachments for a ticket"""
    cursor.execute('SELECT COUNT(*) FROM ticket_attachments WHERE ticket_id = ?', (ticket_id,))
    return cursor.fetchone()[0]

def _get_last_response_info(ticket_id, cursor):
    """Get information about the last response to a ticket"""
    cursor.execute('''
    SELECT responder_role, response_datetime FROM ticket_responses 
    WHERE ticket_id = ? ORDER BY response_datetime DESC LIMIT 1
    ''', (ticket_id,))
    
    result = cursor.fetchone()
    if result:
        return {'role': result[0], 'datetime': result[1]}
    return None

@audit_action("add_response")

def download_attachment_menu(support, attachments):
    """Download attachment menu"""
    try:
        print(f"\n📎 DOWNLOAD ATTACHMENTS")
        print("="*40)
        
        print("Available attachments:")
        for i, att in enumerate(attachments, 1):
            size_mb = att['file_size'] / (1024 * 1024)
            print(f"{i}. 📄 {att['original_filename']} ({size_mb:.1f}MB)")
            print(f"   📅 Uploaded: {att['uploaded_datetime']}")
            print(f"   👤 By: {att['uploaded_by']}")
        
        choice = input(f"\nSelect attachment to download (1-{len(attachments)}): ").strip()
        
        if not choice.isdigit() or not 1 <= int(choice) <= len(attachments):
            print("❌ Invalid choice.")
            return
        
        attachment = attachments[int(choice) - 1]
        attachment_id = attachment['attachment_id']
        
        # Download attachment
        print(f"📥 Downloading {attachment['original_filename']}...")
        
        file_info = support.download_attachment(attachment_id)
        
        # Save to current directory
        filename = file_info['filename']
        with open(filename, 'wb') as f:
            f.write(file_info['data'])
        
        print(f"✅ File downloaded as {filename}")
        
    except Exception as e:
        print(f"❌ Error downloading attachment: {e}")
    
    input("\nPress Enter to continue...")

# Ticket management enhancements