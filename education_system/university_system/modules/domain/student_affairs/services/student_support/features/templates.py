"""
Template management for tickets and responses.
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
from ..utils.audit import audit_action

logger = logging.getLogger(__name__)

def get_ticket_templates():
    """Get all active ticket templates from database and JSON files"""
    templates = []

    # Load from database
    try:
        conn = sqlite3.connect(SUPPORT_DB)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM ticket_templates WHERE is_active = 1 ORDER BY usage_count DESC')
        templates = [dict(row) for row in cursor.fetchall()]

        conn.close()

    except Exception as e:
        logger.error(f"Error getting ticket templates from database: {e}")

    # Load from JSON files in ticket_templates directory
    try:
        if TICKET_TEMPLATES_DIR.exists():
            for json_file in TICKET_TEMPLATES_DIR.glob("*.json"):
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        tmpl_data = json.load(f)

                    # Only include active templates
                    if not tmpl_data.get('is_active', True):
                        continue

                    templates.append({
                        'template_id': f"FILE:{tmpl_data.get('template_id', json_file.stem)}",
                        'name': tmpl_data.get('name', json_file.stem),
                        'title_template': tmpl_data.get('title_template', ''),
                        'description_template': tmpl_data.get('description_template', ''),
                        'category': tmpl_data.get('category', 'General'),
                        'priority': tmpl_data.get('priority', 'Medium'),
                        'created_by': 'System',
                        'is_active': True,
                        'usage_count': 0,
                        'source': 'file'
                    })
                except (json.JSONDecodeError, IOError) as e:
                    logger.warning(f"Failed to load template {json_file}: {e}")
    except Exception as e:
        logger.error(f"Error loading file-based ticket templates: {e}")

    return templates

def get_response_templates(category=None):
    """Get response templates, optionally filtered by category"""
    try:
        conn = sqlite3.connect(SUPPORT_DB)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if category:
            cursor.execute('SELECT * FROM response_templates WHERE is_active = 1 AND (category = ? OR category IS NULL) ORDER BY usage_count DESC', (category,))
        else:
            cursor.execute('SELECT * FROM response_templates WHERE is_active = 1 ORDER BY usage_count DESC')
        
        templates = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return templates
        
    except Exception as e:
        logger.error(f"Error getting response templates: {e}")
        return []

def create_ticket_template(name, title_template, description_template, category, priority):
    """Create a new ticket template"""
    if not _auth_mod.auth or not _auth_mod.auth.current_user or _auth_mod.auth.current_user['role'] not in ('staff', 'admin'):
        raise PermissionError("Only staff can create ticket templates")
    
    try:
        conn = sqlite3.connect(SUPPORT_DB)
        cursor = conn.cursor()
        
        created_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
        INSERT INTO ticket_templates (
            name, title_template, description_template, category, priority,
            created_by, created_datetime
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (name, title_template, description_template, category, priority, _auth_mod.auth.current_user['username'], created_time))
        
        template_id = cursor.lastrowid
        
        conn.commit()
        conn.close()
        
        logger.info(f"Ticket template '{name}' created by {_auth_mod.auth.current_user['username']}")
        return template_id
        
    except Exception as e:
        logger.error(f"Error creating ticket template: {e}")
        raise

@audit_action("create_response_template")

def create_response_template(name, subject, content, category=None, variables=None):
    """Create a new response template"""
    if not _auth_mod.auth or not _auth_mod.auth.current_user or _auth_mod.auth.current_user['role'] not in ('staff', 'admin'):
        raise PermissionError("Only staff can create response templates")
    
    try:
        conn = sqlite3.connect(SUPPORT_DB)
        cursor = conn.cursor()
        
        created_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
        INSERT INTO response_templates (
            name, subject, content, category, created_by, created_datetime, variables
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (name, subject, content, category, _auth_mod.auth.current_user['username'], created_time, json.dumps(variables or [])))
        
        template_id = cursor.lastrowid
        
        conn.commit()
        conn.close()
        
        logger.info(f"Response template '{name}' created by {_auth_mod.auth.current_user['username']}")
        return template_id
        
    except Exception as e:
        logger.error(f"Error creating response template: {e}")
        raise

# File management methods

def _create_auto_response(ticket_id, template_name, cursor):
    """Create an automatic response using a template"""
    try:
        # Get template
        cursor.execute('SELECT content, variables FROM response_templates WHERE name = ? AND is_active = 1', (template_name,))
        template_data = cursor.fetchone()
        
        if not template_data:
            return
            
        content, variables_json = template_data
        variables = json.loads(variables_json or '[]')
        
        # Replace variables
        replacements = {
            'TICKET_ID': str(ticket_id),
            'RESPONSE_TIME': '24 hours',
            'USER_NAME': _auth_mod.auth.current_user.get('username', 'Student')
        }
        
        for var in variables:
            if var in replacements:
                content = content.replace(f'[{var}]', replacements[var])
        
        # Create response
        cursor.execute('''
        INSERT INTO ticket_responses (
            ticket_id, responder_id, responder_role, response_text,
            response_datetime, is_auto_generated, template_used
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            ticket_id, 'system', 'system', content,
            datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            1, template_name
        ))
        
    except Exception as e:
        logger.error(f"Error creating auto response: {e}")

def manage_templates_menu(support):
    """Manage ticket and response templates (staff only)"""
    try:
        print("\n📋 MANAGE TEMPLATES")
        print("="*40)
        
        print("1. View ticket templates")
        print("2. Create ticket template")
        print("3. View response templates")
        print("4. Create response template")
        print("5. Template usage statistics")
        print("6. Back")
        
        choice = input("\nSelect option: ").strip()
        
        if choice == '1':
            view_ticket_templates(support)
        elif choice == '2':
            create_ticket_template_interactive(support)
        elif choice == '3':
            view_response_templates(support)
        elif choice == '4':
            create_response_template_interactive(support)
        elif choice == '5':
            show_template_statistics(support)
        elif choice == '6':
            return
        else:
            print("❌ Invalid choice.")
    
    except Exception as e:
        print(f"❌ Error managing templates: {e}")
    
    input("\nPress Enter to continue...")

def view_ticket_templates(support):
    """View all ticket templates"""
    try:
        templates = support.get_ticket_templates()
        
        if not templates:
            print("📭 No ticket templates found.")
            return
        
        print("\n📋 TICKET TEMPLATES")
        print("="*50)
        
        for template in templates:
            print(f"📄 {template['name']}")
            print(f"   📂 Category: {template['category']} | 🔥 Priority: {template['priority']}")
            print(f"   📈 Used {template.get('usage_count', 0)} times")
            print(f"   ✏️ Created by: {template['created_by']} on {template['created_datetime']}")
            print(f"   📝 Title: {template['title_template'][:60]}...")
            print()
    except Exception as e:
        print(f"❌ Error viewing templates: {e}")

def create_ticket_template_interactive(support):
    """Interactive ticket template creation"""
    try:
        print("\n📋 CREATE TICKET TEMPLATE")
        print("="*40)
        
        name = input("Template name: ").strip()
        if not name:
            print("❌ Template name is required.")
            return
        
        title_template = input("Title template: ").strip()
        if not title_template:
            print("❌ Title template is required.")
            return
        
        print("Description template (press Enter twice to finish):")
        lines = []
        while True:
            line = input()
            if not line and (not lines or not lines[-1]):
                break
            lines.append(line)
        
        description_template = '\n'.join(lines)
        if not description_template:
            print("❌ Description template is required.")
            return
        
        categories = ['Academic', 'Technical', 'Financial Aid', 'Library Services', 'Other']
        print("\nCategories:")
        for i, cat in enumerate(categories, 1):
            print(f"{i}. {cat}")
        
        cat_choice = input(f"Select category (1-{len(categories)}): ").strip()
        if not cat_choice.isdigit() or not 1 <= int(cat_choice) <= len(categories):
            print("❌ Invalid category.")
            return
        
        category = categories[int(cat_choice) - 1]
        
        priorities = ['Low', 'Medium', 'High', 'Urgent', 'Critical']
        print("\nPriorities:")
        for i, pri in enumerate(priorities, 1):
            print(f"{i}. {pri}")
        
        pri_choice = input(f"Select priority (1-{len(priorities)}): ").strip()
        if not pri_choice.isdigit() or not 1 <= int(pri_choice) <= len(priorities):
            print("❌ Invalid priority.")
            return
        
        priority = priorities[int(pri_choice) - 1]
        
        # Create template
        template_id = support.create_ticket_template(name, title_template, description_template, category, priority)
        print(f"✅ Ticket template '{name}' created successfully (ID: {template_id})!")
    
    except Exception as e:
        print(f"❌ Error creating template: {e}")

def view_response_templates(support):
    """View all response templates"""
    try:
        templates = support.get_response_templates()
        
        if not templates:
            print("📭 No response templates found.")
            return
        
        print("\n💬 RESPONSE TEMPLATES")
        print("="*50)
        
        for template in templates:
            print(f"💬 {template['name']}")
            if template.get('category'):
                print(f"   📂 Category: {template['category']}")
            print(f"   📈 Used {template.get('usage_count', 0)} times")
            print(f"   ✏️ Created by: {template['created_by']} on {template['created_datetime']}")
            if template.get('subject'):
                print(f"   📧 Subject: {template['subject']}")
            print(f"   📝 Content: {template['content'][:100]}...")
            print()
    except Exception as e:
        print(f"❌ Error viewing templates: {e}")

def create_response_template_interactive(support):
    """Interactive response template creation"""
    try:
        print("\n💬 CREATE RESPONSE TEMPLATE")
        print("="*40)
        
        name = input("Template name: ").strip()
        if not name:
            print("❌ Template name is required.")
            return
        
        subject = input("Email subject (optional): ").strip()
        
        print("Template content (press Enter twice to finish):")
        lines = []
        while True:
            line = input()
            if not line and (not lines or not lines[-1]):
                break
            lines.append(line)
        
        content = '\n'.join(lines)
        if not content:
            print("❌ Template content is required.")
            return
        
        category = input("Category (optional): ").strip() or None
        
        variables_input = input("Variables (comma-separated, e.g., TICKET_ID,USER_NAME): ").strip()
        variables = [var.strip() for var in variables_input.split(',')] if variables_input else []
        
        # Create template
        template_id = support.create_response_template(name, subject, content, category, variables)
        print(f"✅ Response template '{name}' created successfully (ID: {template_id})!")
    
    except Exception as e:
        print(f"❌ Error creating template: {e}")

def show_template_statistics(support):
    """Show template usage statistics"""
    try:
        print("\n📊 TEMPLATE USAGE STATISTICS")
        print("="*50)
        
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()
        
        # Check if tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ticket_templates'")
        has_ticket_templates = cursor.fetchone() is not None
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='response_templates'")
        has_response_templates = cursor.fetchone() is not None
        
        # Ticket template stats
        print("🎫 TICKET TEMPLATES:")
        if has_ticket_templates:
            cursor.execute('''
            SELECT name, usage_count, created_datetime 
            FROM ticket_templates 
            WHERE is_active = 1 
            ORDER BY usage_count DESC
            ''')
            ticket_templates = cursor.fetchall()
            
            if ticket_templates:
                for name, usage_count, created_date in ticket_templates:
                    print(f"   📋 {name}: {usage_count} uses (created {created_date})")
            else:
                print("   📭 No ticket templates found.")
        else:
            print("   📭 Ticket templates table not found.")
        
        # Response template stats
        print("\n💬 RESPONSE TEMPLATES:")
        if has_response_templates:
            cursor.execute('''
            SELECT name, usage_count, created_datetime 
            FROM response_templates 
            WHERE is_active = 1 
            ORDER BY usage_count DESC
            ''')
            response_templates = cursor.fetchall()
            
            if response_templates:
                for name, usage_count, created_date in response_templates:
                    print(f"   💬 {name}: {usage_count} uses (created {created_date})")
            else:
                print("   📭 No response templates found.")
        else:
            print("   📭 Response templates table not found.")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error getting template statistics: {e}")

# Database schema fix for user_preferences table