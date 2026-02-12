"""
Bulk ticket operations.
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

def bulk_update_tickets(ticket_ids, updates):
    """Bulk update multiple tickets"""
    if not _auth_mod.auth or not _auth_mod.auth.current_user or _auth_mod.auth.current_user['role'] not in ('staff', 'admin'):
        raise PermissionError("Only staff can perform bulk updates")
    
    try:
        conn = sqlite3.connect(SUPPORT_DB)
        cursor = conn.cursor()
        
        update_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        updated_count = 0
        
        for ticket_id in ticket_ids:
            # Validate ticket exists
            cursor.execute('SELECT * FROM support_tickets WHERE ticket_id = ?', (ticket_id,))
            ticket = cursor.fetchone()
            
            if not ticket:
                logger.warning(f"Ticket {ticket_id} not found, skipping")
                continue
            
            # Build update query
            update_fields = []
            params = []
            
            if 'status' in updates:
                update_fields.append('status = ?')
                params.append(updates['status'])
            
            if 'priority' in updates:
                update_fields.append('priority = ?')
                params.append(updates['priority'])
            
            if 'assigned_to' in updates:
                update_fields.append('assigned_to = ?')
                params.append(updates['assigned_to'])
            
            if 'category' in updates:
                update_fields.append('category = ?')
                params.append(updates['category'])
            
            if update_fields:
                update_fields.append('last_updated_datetime = ?')
                params.append(update_time)
                params.append(ticket_id)
                
                query = f"UPDATE support_tickets SET {', '.join(update_fields)} WHERE ticket_id = ?"
                cursor.execute(query, params)
                
                # Add bulk update note
                cursor.execute('''
                INSERT INTO ticket_responses (
                    ticket_id, responder_id, responder_role, response_text,
                    response_datetime, is_auto_generated
                ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    ticket_id, _auth_mod.auth.current_user['id'], _auth_mod.auth.current_user['role'],
                    f"Bulk update applied: {', '.join([f'{k}={v}' for k, v in updates.items()])}",
                    update_time, 1
                ))
                
                updated_count += 1
        
        conn.commit()
        conn.close()
        
        logger.info(f"Bulk update applied to {updated_count} tickets by {_auth_mod.auth.current_user['username']}")
        return updated_count
        
    except Exception as e:
        logger.error(f"Error performing bulk update: {e}")
        raise

def perform_bulk_assign(support, ticket_ids, assigned_to):
    """Perform bulk assignment of tickets to a user"""
    if not ticket_ids:
        print("❌ No ticket IDs provided.")
        return
    
    # Validate ticket IDs exist
    try:
        valid_ids = [str(t.get('id', '')) for t in support.get_all_tickets()]
        ticket_ids = [tid for tid in ticket_ids if tid in valid_ids]
    except ValueError:
        print("❌ Invalid ticket IDs.")
        return
    
    if not ticket_ids:
        print("❌ No valid ticket IDs provided.")
        return
    
    # Confirm operation
    print(f"\n📋 Assigning {len(ticket_ids)} tickets to {assigned_to}")
    confirm = input("Confirm bulk assignment? (y/n): ").lower()
    
    if confirm == 'y':
        try:
            updates = {'assigned_to': assigned_to}
            updated_count = support.bulk_update_tickets(ticket_ids, updates)
            print(f"✅ Successfully assigned {updated_count} tickets to {assigned_to}")
        except Exception as e:
            print(f"❌ Error during bulk assignment: {e}")
    else:
        print("❌ Bulk assignment cancelled.")

def bulk_operations_menu(support):
    """Bulk operations menu (staff only)"""
    try:
        print("\n📦 BULK OPERATIONS")
        print("="*40)
        
        print("1. Bulk assign tickets")
        print("2. Bulk update ticket status")
        print("3. Bulk update ticket priority")
        print("4. Bulk update ticket category")
        print("5. Merge tickets")
        print("6. Back")
        
        choice = input("\nSelect operation: ").strip()
        
        if choice == '1':
            bulk_assign_tickets_menu(support)
        elif choice == '2':
            bulk_update_status_menu(support)
        elif choice == '3':
            bulk_update_priority_menu(support)
        elif choice == '4':
            bulk_update_category_menu(support)
        elif choice == '5':
            merge_tickets_menu(support)
        elif choice == '6':
            return
        else:
            print("❌ Invalid choice.")
    
    except Exception as e:
        print(f"❌ Error in bulk operations: {e}")
    
    input("\nPress Enter to continue...")

def bulk_assign_tickets_menu(support):
    """Bulk assign tickets to staff"""
    print("\n👨‍💼 BULK ASSIGN TICKETS")
    print("="*40)
    
    # Get ticket IDs
    ticket_ids_input = input("Enter ticket IDs (comma-separated): ").strip()
    if not ticket_ids_input:
        print("❌ No ticket IDs provided.")
        return
    
    try:
        ticket_ids = [int(id.strip()) for id in ticket_ids_input.split(',')]
    except ValueError:
        print("❌ Invalid ticket IDs. Please enter numbers only.")
        return
    
    assigned_to = input("Assign to (username): ").strip()
    if not assigned_to:
        print("❌ Staff username is required.")
        return
    
    # Confirm operation
    print(f"\n📋 Assigning {len(ticket_ids)} tickets to {assigned_to}")
    confirm = input("Confirm bulk assignment? (y/n): ").lower()
    
    if confirm == 'y':
        try:
            updates = {'assigned_to': assigned_to}
            updated_count = support.bulk_update_tickets(ticket_ids, updates)
            print(f"✅ Successfully assigned {updated_count} tickets to {assigned_to}")
        except Exception as e:
            print(f"❌ Error during bulk assignment: {e}")
    else:
        print("❌ Bulk assignment cancelled.")

def bulk_update_status_menu(support):
    """Bulk update ticket status"""
    print("\n📊 BULK UPDATE STATUS")
    print("="*40)
    
    # Get ticket IDs
    ticket_ids_input = input("Enter ticket IDs (comma-separated): ").strip()
    if not ticket_ids_input:
        print("❌ No ticket IDs provided.")
        return
    
    try:
        ticket_ids = [int(id.strip()) for id in ticket_ids_input.split(',')]
    except ValueError:
        print("❌ Invalid ticket IDs. Please enter numbers only.")
        return
    
    # Select new status
    print("\nStatuses:")
    for i, status in enumerate(TICKET_STATUSES, 1):
        print(f"{i}. {status}")
    
    status_choice = input(f"Select new status (1-{len(TICKET_STATUSES)}): ").strip()
    if not status_choice.isdigit() or not 1 <= int(status_choice) <= len(TICKET_STATUSES):
        print("❌ Invalid status choice.")
        return
    
    new_status = TICKET_STATUSES[int(status_choice) - 1]
    
    # Confirm operation
    print(f"\n📋 Updating {len(ticket_ids)} tickets to status '{new_status}'")
    confirm = input("Confirm bulk status update? (y/n): ").lower()
    
    if confirm == 'y':
        try:
            updates = {'status': new_status}
            updated_count = support.bulk_update_tickets(ticket_ids, updates)
            print(f"✅ Successfully updated status for {updated_count} tickets")
        except Exception as e:
            print(f"❌ Error during bulk status update: {e}")
    else:
        print("❌ Bulk status update cancelled.")

def bulk_update_priority_menu(support):
    """Bulk update ticket priority"""
    print("\n🔥 BULK UPDATE PRIORITY")
    print("="*40)
    
    # Get ticket IDs
    ticket_ids_input = input("Enter ticket IDs (comma-separated): ").strip()
    if not ticket_ids_input:
        print("❌ No ticket IDs provided.")
        return
    
    try:
        ticket_ids = [int(id.strip()) for id in ticket_ids_input.split(',')]
    except ValueError:
        print("❌ Invalid ticket IDs. Please enter numbers only.")
        return
    
    # Select new priority
    print("\nPriorities:")
    for i, priority in enumerate(TICKET_PRIORITIES, 1):
        print(f"{i}. {priority}")
    
    priority_choice = input(f"Select new priority (1-{len(TICKET_PRIORITIES)}): ").strip()
    if not priority_choice.isdigit() or not 1 <= int(priority_choice) <= len(TICKET_PRIORITIES):
        print("❌ Invalid priority choice.")
        return
    
    new_priority = TICKET_PRIORITIES[int(priority_choice) - 1]
    
    # Confirm operation
    print(f"\n📋 Updating {len(ticket_ids)} tickets to priority '{new_priority}'")
    confirm = input("Confirm bulk priority update? (y/n): ").lower()
    
    if confirm == 'y':
        try:
            updates = {'priority': new_priority}
            updated_count = support.bulk_update_tickets(ticket_ids, updates)
            print(f"✅ Successfully updated priority for {updated_count} tickets")
        except Exception as e:
            print(f"❌ Error during bulk priority update: {e}")
    else:
        print("❌ Bulk priority update cancelled.")

def bulk_update_category_menu(support):
    """Bulk update ticket category"""
    print("\n📂 BULK UPDATE CATEGORY")
    print("="*40)
    
    # Get ticket IDs
    ticket_ids_input = input("Enter ticket IDs (comma-separated): ").strip()
    if not ticket_ids_input:
        print("❌ No ticket IDs provided.")
        return
    
    try:
        ticket_ids = [int(id.strip()) for id in ticket_ids_input.split(',')]
    except ValueError:
        print("❌ Invalid ticket IDs. Please enter numbers only.")
        return
    
    # Select new category
    print("\nCategories:")
    for i, category in enumerate(SUPPORT_CATEGORIES, 1):
        print(f"{i}. {category}")
    
    category_choice = input(f"Select new category (1-{len(SUPPORT_CATEGORIES)}): ").strip()
    if not category_choice.isdigit() or not 1 <= int(category_choice) <= len(SUPPORT_CATEGORIES):
        print("❌ Invalid category choice.")
        return
    
    new_category = SUPPORT_CATEGORIES[int(category_choice) - 1]
    
    # Confirm operation
    print(f"\n📋 Updating {len(ticket_ids)} tickets to category '{new_category}'")
    confirm = input("Confirm bulk category update? (y/n): ").lower()
    
    if confirm == 'y':
        try:
            updates = {'category': new_category}
            updated_count = support.bulk_update_tickets(ticket_ids, updates)
            print(f"✅ Successfully updated category for {updated_count} tickets")
        except Exception as e:
            print(f"❌ Error during bulk category update: {e}")
    else:
        print("❌ Bulk category update cancelled.")

def export_filtered_results(support, filters):
    """Helper function to export filtered results"""
    print("\n📤 EXPORT FILTERED RESULTS")
    print("="*40)
    
    # Format selection
    print("Export formats:")
    print("1. CSV")
    print("2. JSON")
    
    format_choice = input("Select format (1-2): ").strip()
    export_format = 'csv' if format_choice == '1' else 'json'
    
    try:
        # Export data
        print("\n📊 Exporting filtered results...")
        exported_data = support.export_data('tickets', filters, export_format)
        
        # Save to file
        ext = 'csv' if export_format == 'csv' else 'json'
        filename = f"filtered_results_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
        
        with open(filename, 'w') as f:
            f.write(exported_data)
        
        print(f"✅ Filtered results exported to {filename}")
        
    except Exception as e:
        print(f"❌ Error exporting filtered results: {e}")
