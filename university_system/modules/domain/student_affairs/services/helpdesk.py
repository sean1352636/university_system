from university_system.infrastructure.database.db import sqlite3, DatabaseManager
from datetime import datetime, timedelta
from university_system.infrastructure.email.email_manager import (
    send_ticket_notification,
    send_reply_notification,
    send_sla_alert,
    send_satisfaction_survey,
)
import os
import json
import hashlib
import mimetypes
import base64
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import re
from university_system.infrastructure.database.db import get_connection

# Initialize the enhanced helpdesk database
def init_helpdesk_db():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Create support_tickets table with enhanced fields
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS support_tickets (
            ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            assigned_to INTEGER,
            subject TEXT NOT NULL,
            message TEXT NOT NULL,
            category TEXT NOT NULL,
            subcategory TEXT,
            status TEXT DEFAULT 'open',
            priority TEXT DEFAULT 'medium',
            impact TEXT DEFAULT 'low',
            urgency TEXT DEFAULT 'low',
            source TEXT DEFAULT 'web',
            resolution TEXT,
            satisfaction_rating INTEGER,
            satisfaction_feedback TEXT,
            estimated_hours REAL,
            actual_hours REAL,
            due_date TEXT,
            resolved_at TEXT,
            first_response_at TEXT,
            last_activity_at TEXT,
            escalation_level INTEGER DEFAULT 0,
            tags TEXT,
            department TEXT,
            organization_id INTEGER,
            parent_ticket_id INTEGER,
            knowledge_base_articles TEXT,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (assigned_to) REFERENCES users (id),
            FOREIGN KEY (parent_ticket_id) REFERENCES support_tickets (ticket_id)
        )
        ''')
        
        # Create ticket_replies table with enhanced fields
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ticket_replies (
            reply_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER,
            user_id INTEGER,
            message TEXT NOT NULL,
            is_internal BOOLEAN DEFAULT 0,
            reply_type TEXT DEFAULT 'comment',
            time_spent REAL DEFAULT 0,
            created_at TEXT,
            edited_at TEXT,
            FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        ''')
        
        # Create ticket_attachments table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ticket_attachments (
            attachment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER,
            reply_id INTEGER,
            filename TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            file_size INTEGER,
            mime_type TEXT,
            file_hash TEXT,
            uploaded_by INTEGER,
            upload_path TEXT,
            created_at TEXT,
            FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
            FOREIGN KEY (reply_id) REFERENCES ticket_replies (reply_id),
            FOREIGN KEY (uploaded_by) REFERENCES users (id)
        )
        ''')
        
        # Create ticket_assignments table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ticket_assignments (
            assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER,
            assigned_from INTEGER,
            assigned_to INTEGER,
            assignment_reason TEXT,
            created_at TEXT,
            FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
            FOREIGN KEY (assigned_from) REFERENCES users (id),
            FOREIGN KEY (assigned_to) REFERENCES users (id)
        )
        ''')
        
        # Create ticket_templates table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ticket_templates (
            template_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            category TEXT,
            subject_template TEXT,
            message_template TEXT,
            default_priority TEXT,
            default_impact TEXT,
            default_urgency TEXT,
            form_fields TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_by INTEGER,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (created_by) REFERENCES users (id)
        )
        ''')
        
        # Create sla_policies table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS sla_policies (
            sla_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            priority TEXT,
            impact TEXT,
            urgency TEXT,
            first_response_hours INTEGER,
            resolution_hours INTEGER,
            escalation_hours INTEGER,
            business_hours_only BOOLEAN DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT,
            updated_at TEXT
        )
        ''')
        
        # Create ticket_workflows table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ticket_workflows (
            workflow_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            trigger_type TEXT NOT NULL,
            trigger_conditions TEXT,
            actions TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_by INTEGER,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (created_by) REFERENCES users (id)
        )
        ''')
        
        # Create ticket_time_tracking table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ticket_time_tracking (
            time_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER,
            user_id INTEGER,
            start_time TEXT,
            end_time TEXT,
            duration_minutes INTEGER,
            description TEXT,
            billable BOOLEAN DEFAULT 0,
            created_at TEXT,
            FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        ''')
        
        # Create ticket_escalations table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ticket_escalations (
            escalation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER,
            escalation_level INTEGER,
            escalated_to INTEGER,
            escalated_by INTEGER,
            escalation_reason TEXT,
            resolved BOOLEAN DEFAULT 0,
            created_at TEXT,
            FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
            FOREIGN KEY (escalated_to) REFERENCES users (id),
            FOREIGN KEY (escalated_by) REFERENCES users (id)
        )
        ''')
        
        # Create ticket_links table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ticket_links (
            link_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER,
            linked_ticket_id INTEGER,
            link_type TEXT,
            created_by INTEGER,
            created_at TEXT,
            FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
            FOREIGN KEY (linked_ticket_id) REFERENCES support_tickets (ticket_id),
            FOREIGN KEY (created_by) REFERENCES users (id)
        )
        ''')
        
        # Create ticket_audit_log table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ticket_audit_log (
            audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER,
            user_id INTEGER,
            action TEXT NOT NULL,
            old_values TEXT,
            new_values TEXT,
            ip_address TEXT,
            user_agent TEXT,
            created_at TEXT,
            FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        ''')
        
        # Create knowledge_base table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS knowledge_base (
            article_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT,
            tags TEXT,
            author_id INTEGER,
            status TEXT DEFAULT 'draft',
            views INTEGER DEFAULT 0,
            helpful_votes INTEGER DEFAULT 0,
            unhelpful_votes INTEGER DEFAULT 0,
            search_keywords TEXT,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (author_id) REFERENCES users (id)
        )
        ''')
        
        # Create departments table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS departments (
            dept_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            manager_id INTEGER,
            email TEXT,
            sla_policy_id INTEGER,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (manager_id) REFERENCES users (id),
            FOREIGN KEY (sla_policy_id) REFERENCES sla_policies (sla_id)
        )
        ''')
        
        # Create organizations table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS organizations (
            org_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            domain TEXT,
            contact_email TEXT,
            phone TEXT,
            address TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT,
            updated_at TEXT
        )
        ''')
        
        # Create saved_searches table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS saved_searches (
            search_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT NOT NULL,
            search_criteria TEXT,
            created_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        ''')

        conn.commit()
        conn.close()
        print("Enhanced helpdesk database initialized successfully!")
        
        # Initialize default data
        init_default_data()
        
    except sqlite3.Error as e:
        print(f"An error occurred while initializing the helpdesk database: {e}")

def init_default_data():
    """Initialize default SLA policies, templates, and workflows"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Insert default SLA policies
        cursor.execute("SELECT COUNT(*) FROM sla_policies")
        if cursor.fetchone()[0] == 0:
            default_slas = [
                ('Standard Low Priority', 'Standard SLA for low priority tickets', 'low', 'low', 'low', 24, 72, 48, 1, 1),
                ('Standard Medium Priority', 'Standard SLA for medium priority tickets', 'medium', 'medium', 'medium', 8, 48, 24, 1, 1),
                ('Standard High Priority', 'Standard SLA for high priority tickets', 'high', 'high', 'high', 2, 24, 8, 1, 1),
                ('Critical', 'SLA for critical issues', 'high', 'high', 'high', 1, 8, 4, 0, 1)
            ]
            
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            for sla in default_slas:
                cursor.execute('''
                INSERT INTO sla_policies 
                (name, description, priority, impact, urgency, first_response_hours, 
                 resolution_hours, escalation_hours, business_hours_only, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', sla + (timestamp,))
        
        # Insert default ticket templates
        cursor.execute("SELECT COUNT(*) FROM ticket_templates")
        if cursor.fetchone()[0] == 0:
            default_templates = [
                ('Password Reset Request', 'Template for password reset requests', 'Account Access',
                 'Password Reset Request', 'I need to reset my password for:\n\nAccount: [ACCOUNT_NAME]\nReason: [REASON]\n\nAdditional details:\n[DETAILS]',
                 'medium', 'low', 'medium', '{"fields": [{"name": "account_name", "type": "text", "required": true}, {"name": "reason", "type": "select", "options": ["Forgot password", "Account locked", "Security concern"]}, {"name": "details", "type": "textarea", "required": false}]}'),
                
                ('Technical Issue Report', 'Template for technical problems', 'Technical Support',
                 'Technical Issue: [ISSUE_TYPE]', 'Issue Description:\n[DESCRIPTION]\n\nSteps to reproduce:\n1. [STEP_1]\n2. [STEP_2]\n3. [STEP_3]\n\nExpected behavior:\n[EXPECTED]\n\nActual behavior:\n[ACTUAL]\n\nBrowser/System info:\n[SYSTEM_INFO]',
                 'medium', 'medium', 'medium', '{"fields": [{"name": "issue_type", "type": "select", "options": ["Login problem", "Performance issue", "Feature not working", "Error message"]}, {"name": "description", "type": "textarea", "required": true}, {"name": "steps", "type": "textarea", "required": true}]}'),
                
                ('Financial Services Request', 'Template for financial inquiries', 'Financial Services',
                 'Financial Services: [REQUEST_TYPE]', 'Request Type: [REQUEST_TYPE]\n\nStudent ID: [STUDENT_ID]\n\nDetails:\n[DETAILS]\n\nUrgency: [URGENCY_REASON]',
                 'high', 'medium', 'high', '{"fields": [{"name": "request_type", "type": "select", "options": ["Payment plan", "Refund request", "Financial aid", "Billing inquiry"]}, {"name": "student_id", "type": "text", "required": true}, {"name": "amount", "type": "number", "required": false}]}')
            ]
            
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            for template in default_templates:
                cursor.execute('''
                INSERT INTO ticket_templates 
                (name, description, category, subject_template, message_template, 
                 default_priority, default_impact, default_urgency, form_fields, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', template + (timestamp,))
        
        # Insert default departments
        cursor.execute("SELECT COUNT(*) FROM departments")
        if cursor.fetchone()[0] == 0:
            default_departments = [
                ('IT Support', 'Information Technology Support Department', None, 'itsupport@school.edu', 1),
                ('Academic Affairs', 'Academic Affairs Department', None, 'academic@school.edu', 2),
                ('Financial Services', 'Financial Services Department', None, 'finance@school.edu', 3),
                ('Student Services', 'Student Services Department', None, 'students@school.edu', 2)
            ]
            
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            for dept in default_departments:
                cursor.execute('''
                INSERT INTO departments 
                (name, description, manager_id, email, sla_policy_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', dept + (timestamp,))
        
        # Insert default workflows
        cursor.execute("SELECT COUNT(*) FROM ticket_workflows")
        if cursor.fetchone()[0] == 0:
            default_workflows = [
                ('Auto-assign IT tickets', 'Automatically assign technical support tickets to IT department',
                 'ticket_created', '{"category": "Technical Support"}',
                 '{"assign_to_department": "IT Support", "set_priority": "medium"}'),
                
                ('High priority escalation', 'Escalate high priority tickets after 2 hours',
                 'time_based', '{"priority": "high", "hours_without_response": 2}',
                 '{"escalate_to_manager": true, "send_notification": true}'),
                
                ('Auto-close resolved tickets', 'Auto-close tickets marked as resolved after 48 hours',
                 'time_based', '{"status": "resolved", "hours_inactive": 48}',
                 '{"change_status": "closed", "send_survey": true}')
            ]
            
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            for workflow in default_workflows:
                cursor.execute('''
                INSERT INTO ticket_workflows 
                (name, description, trigger_type, trigger_conditions, actions, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', workflow + (timestamp,))
        
        conn.commit()
        print("Default helpdesk data initialized successfully!")
        
    except sqlite3.Error as e:
        print(f"Error initializing default data: {e}")
    finally:
        conn.close()
        
def display_kb_suggestions(ticket):
    """Display knowledge base article suggestions"""
    if ticket['knowledge_base_articles']:
        conn = get_connection()
        cursor = conn.cursor()
        
        article_ids = ticket['knowledge_base_articles'].split(',')
        placeholders = ','.join(['?' for _ in article_ids])
        
        cursor.execute(f'''
        SELECT article_id, title, category, helpful_votes, unhelpful_votes
        FROM knowledge_base 
        WHERE article_id IN ({placeholders}) AND status = 'published'
        ''', article_ids)
        
        articles = cursor.fetchall()
        
        if articles:
            print("\nSuggested Knowledge Base Articles:")
            print("-" * 80)
            for article in articles:
                helpful_ratio = article[3] / max(1, article[3] + article[4])
                print(f"📚 {article[1]} (Category: {article[2]}) - {helpful_ratio:.0%} helpful")
            print("-" * 80)
        
        conn.close()

def display_ticket_replies(ticket_id, is_admin):
    """Display ticket replies and internal notes"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get all replies
    cursor.execute('''
    SELECT r.*, u.username, u.role
    FROM ticket_replies r
    JOIN users u ON r.user_id = u.id
    WHERE r.ticket_id = ?
    ORDER BY r.created_at ASC
    ''', (ticket_id,))
    
    replies = cursor.fetchall()
    
    if replies:
        print("\nConversation History:")
        print("-" * 80)
        
        for reply in replies:
            reply_type = "Internal Note" if reply[4] else "Reply"  # is_internal
            icon = "🔒" if reply[4] else "💬"
            
            # Only show internal notes to admins
            if reply[4] and not is_admin:
                continue
            
            print(f"{icon} {reply_type} from {reply[-2]} ({reply[-1]}) at {reply[6]}")  # username, role, created_at
            if reply[7]:  # edited_at
                print(f"   (Edited at {reply[7]})")
            
            if reply[6]:  # time_spent
                print(f"   Time spent: {reply[6]} hours")
            
            print(f"   {reply[3]}")  # message
            print("-" * 80)

def display_time_tracking(ticket_id):
    """Display time tracking information"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT tt.*, u.username
    FROM ticket_time_tracking tt
    JOIN users u ON tt.user_id = u.id
    WHERE tt.ticket_id = ?
    ORDER BY tt.created_at
    ''', (ticket_id,))
    
    time_entries = cursor.fetchall()
    
    if time_entries:
        print("\nTime Tracking:")
        print("-" * 80)
        
        total_time = 0
        billable_time = 0
        
        for entry in time_entries:
            duration = entry[5] / 60  # duration_minutes to hours
            total_time += duration
            if entry[7]:  # billable
                billable_time += duration
            
            billable_text = " (Billable)" if entry[7] else ""
            print(f"⏱️  {entry[-1]}: {duration:.2f} hours{billable_text}")
            if entry[6]:  # description
                print(f"   Description: {entry[6]}")
        
        print(f"\nTotal Time: {total_time:.2f} hours")
        print(f"Billable Time: {billable_time:.2f} hours")
        print("-" * 80)
    
    conn.close()

def display_escalation_history(ticket_id):
    """Display escalation history"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT e.*, u1.username as escalated_to_user, u2.username as escalated_by_user
    FROM ticket_escalations e
    LEFT JOIN users u1 ON e.escalated_to = u1.id
    LEFT JOIN users u2 ON e.escalated_by = u2.id
    WHERE e.ticket_id = ?
    ORDER BY e.created_at
    ''', (ticket_id,))
    
    escalations = cursor.fetchall()
    
    if escalations:
        print("\nEscalation History:")
        print("-" * 80)
        
        for esc in escalations:
            status = "Resolved" if esc[6] else "Open"  # resolved
            escalated_by = esc[-1] or "System"
            print(f"🔺 Level {esc[2]} - Escalated to {esc[-2]} by {escalated_by}")
            print(f"   Reason: {esc[4]}")  # escalation_reason
            print(f"   Date: {esc[7]} - Status: {status}")
        print("-" * 80)
    
    conn.close()

def display_audit_trail(ticket_id):
    """Display audit trail for admins"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT al.*, u.username
    FROM ticket_audit_log al
    JOIN users u ON al.user_id = u.id
    WHERE al.ticket_id = ?
    ORDER BY al.created_at DESC
    LIMIT 10
    ''', (ticket_id,))
    
    audit_entries = cursor.fetchall()
    
    if audit_entries:
        print("\nRecent Activity (Audit Trail):")
        print("-" * 80)
        
        for entry in audit_entries:
            print(f"📋 {entry[3]} by {entry[-1]} at {entry[8]}")  # action, username, created_at
            
            if entry[4]:  # old_values
                try:
                    old_vals = json.loads(entry[4])
                    if old_vals:
                        print(f"   Previous values: {old_vals}")
                except json.JSONDecodeError:
                    pass
            
            if entry[5]:  # new_values
                try:
                    new_vals = json.loads(entry[5])
                    if new_vals:
                        print(f"   New values: {new_vals}")
                except json.JSONDecodeError:
                    pass
        
        print("-" * 80)
    
    conn.close()

def display_ticket_actions(auth, ticket_id, ticket):
    """Display available actions for the ticket"""
    print("\nAvailable Actions:")
    print("================")
    
    actions = []
    action_num = 1
    
    # Reply action
    if auth.check_permission('reply_to_any_ticket') or \
       (auth.check_permission('reply_to_own_ticket') and ticket['user_id'] == auth.current_user['id']):
        print(f"{action_num}. Reply to ticket")
        actions.append('reply')
        action_num += 1
    
    # Admin actions
    if auth.check_permission('manage_tickets'):
        print(f"{action_num}. Add internal note")
        actions.append('internal_note')
        action_num += 1
        
        print(f"{action_num}. Change status")
        actions.append('change_status')
        action_num += 1
        
        print(f"{action_num}. Assign ticket")
        actions.append('assign')
        action_num += 1
        
        print(f"{action_num}. Add time entry")
        actions.append('time_entry')
        action_num += 1
        
        print(f"{action_num}. Link to another ticket")
        actions.append('link_ticket')
        action_num += 1
        
        print(f"{action_num}. Escalate ticket")
        actions.append('escalate')
        action_num += 1
        
        if ticket['status'] in ['resolved', 'closed']:
            print(f"{action_num}. Send satisfaction survey")
            actions.append('survey')
            action_num += 1
    
    print(f"{action_num}. Return to previous menu")
    
    # Handle action selection
    while True:
        choice = input("\nChoose an action: ").strip()
        
        try:
            choice_num = int(choice)
            if choice_num == action_num:  # Return option
                return
            elif 1 <= choice_num <= len(actions):
                action = actions[choice_num - 1]
                execute_ticket_action(auth, ticket_id, action, ticket)
                return
            else:
                print("Invalid choice. Please try again.")
        except ValueError:
            print("Please enter a number.")

def execute_ticket_action(auth, ticket_id, action, ticket):
    """Execute the selected ticket action"""
    if action == 'reply':
        reply_to_ticket_enhanced(auth, ticket_id, False)
    elif action == 'internal_note':
        reply_to_ticket_enhanced(auth, ticket_id, True)
    elif action == 'change_status':
        change_ticket_status_enhanced(auth, ticket_id)
    elif action == 'assign':
        assign_ticket_enhanced(auth, ticket_id)
    elif action == 'time_entry':
        add_time_entry(auth, ticket_id)
    elif action == 'link_ticket':
        link_tickets(auth, ticket_id)
    elif action == 'escalate':
        escalate_ticket_manual(auth, ticket_id)
    elif action == 'survey':
        send_satisfaction_survey(ticket_id)

def reply_to_ticket_enhanced(auth, ticket_id, is_internal=False):
    """Enhanced reply functionality with attachments and time tracking"""
    if not auth or not auth.current_user:
        print("You must be logged in to reply to a ticket.")
        return
    
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Check permissions
    is_admin = auth.check_permission('reply_to_any_ticket')
    
    if not is_admin and not auth.check_permission('reply_to_own_ticket'):
        print("You don't have permission to reply to tickets.")
        conn.close()
        return
    
    if not is_admin:
        cursor.execute('''
        SELECT user_id FROM support_tickets WHERE ticket_id = ?
        ''', (ticket_id,))
        
        result = cursor.fetchone()
        if not result or result['user_id'] != auth.current_user['id']:
            print("You don't have permission to reply to this ticket.")
            conn.close()
            return
    
    # Get reply message
    reply_type = "internal note" if is_internal else "reply"
    print(f"\nEnter your {reply_type} (type 'done' on a new line when finished):")
    
    message = ""
    while True:
        line = input()
        if line.lower() == 'done':
            break
        message += line + "\n"
    
    if not message.strip():
        print("Error: Reply cannot be empty.")
        conn.close()
        return
    
    # Time tracking
    time_spent = 0
    if auth.check_permission('manage_tickets'):
        time_input = input("Time spent on this reply (hours, or press Enter to skip): ").strip()
        if time_input:
            try:
                time_spent = float(time_input)
            except ValueError:
                print("Invalid time format, skipping time tracking.")
    
    # Get current time
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Insert reply into database
    try:
        cursor.execute('''
        INSERT INTO ticket_replies 
        (ticket_id, user_id, message, is_internal, time_spent, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (ticket_id, auth.current_user['id'], message, is_internal, time_spent, now))
        
        reply_id = cursor.lastrowid
        
        # Update ticket timestamps and status
        status_update = ""
        if not is_internal:
            if is_admin and auth.current_user['id'] != cursor.execute('SELECT user_id FROM support_tickets WHERE ticket_id = ?', (ticket_id,)).fetchone()[0]:
                # Admin replying to user ticket
                status_update = ", status = CASE WHEN status = 'open' THEN 'in progress' ELSE status END"
                
                # Record first response time if not set
                cursor.execute('''
                UPDATE support_tickets 
                SET first_response_at = CASE WHEN first_response_at IS NULL THEN ? ELSE first_response_at END
                WHERE ticket_id = ?
                ''', (now, ticket_id))
        
        cursor.execute(f'''
        UPDATE support_tickets
        SET updated_at = ?, last_activity_at = ? {status_update}
        WHERE ticket_id = ?
        ''', (now, now, ticket_id))
        
        conn.commit()
        
        # Handle file attachments
        handle_file_attachments(ticket_id, reply_id, auth.current_user['id'])
        
        # Log the action
        log_ticket_action(ticket_id, auth.current_user['id'], 
                         'internal_note_added' if is_internal else 'reply_added',
                         {}, {'message': message[:100] + '...' if len(message) > 100 else message})
        
        print(f"\n{reply_type.title()} added successfully!")
        
        # Send notifications (only for non-internal replies)
        if not is_internal:
            try:
                # Get ticket and user info
                cursor.execute('''
                SELECT t.user_id, t.subject, u1.username as submitter, u2.username as assignee
                FROM support_tickets t
                JOIN users u1 ON t.user_id = u1.id
                LEFT JOIN users u2 ON t.assigned_to = u2.id
                WHERE t.ticket_id = ?
                ''', (ticket_id,))
                
                ticket_info = cursor.fetchone()
                
                if is_admin:
                    # Admin replying to user
                    send_reply_notification(ticket_id, ticket_info['user_id'], 
                                          ticket_info['submitter'], auth.current_user['username'])
                else:
                    # User replying, notify admins and assignee
                    recipients = []
                    if ticket_info['assignee']:
                        recipients.append((ticket_info['assignee'],))
                    
                    # Add other admins
                    cursor.execute('''
                    SELECT username FROM users WHERE role = 'admin' AND username != ?
                    ''', (ticket_info['assignee'] or '',))
                    recipients.extend(cursor.fetchall())
                    
                    if recipients:
                        send_reply_notification(ticket_id, None, None, 
                                              auth.current_user['username'], admin_list=recipients)
            except Exception as e:
                print(f"Note: Could not send email notification: {e}")
        
        # Run workflows
        run_ticket_workflows(ticket_id, 'reply_added', user_role=auth.current_user['role'])

        # Check for SLA breach and send alert if overdue
        try:
            cursor.execute('''
                SELECT due_date, status
                FROM support_tickets
                WHERE ticket_id = ?
            ''', (ticket_id,))

            ticket_data = cursor.fetchone()
            if ticket_data and ticket_data[0]:  # if due_date exists
                due_date_str = ticket_data[0]
                status = ticket_data[1]

                # Parse due date
                try:
                    due_date = datetime.strptime(due_date_str, '%Y-%m-%d %H:%M:%S')
                    current_time = datetime.now()

                    # If ticket is overdue and not resolved/closed
                    if current_time > due_date and status not in ['resolved', 'closed']:
                        send_sla_alert(ticket_id, alert_type='overdue')
                        print("⚠️  SLA alert sent - ticket is overdue")
                except ValueError:
                    # Invalid date format, skip SLA check
                    pass
        except Exception as e:
            print(f"Note: Could not check SLA status: {e}")

    except sqlite3.Error as e:
        print(f"Error adding reply: {e}")
    finally:
        conn.close()

def change_ticket_status_enhanced(auth, ticket_id):
    """Enhanced status change with resolution tracking"""
    if not auth or not auth.current_user:
        print("You must be logged in to update ticket status.")
        return
    
    if not auth.check_permission('manage_tickets'):
        print("You don't have permission to update ticket status.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get current ticket info
    cursor.execute('''
    SELECT status, resolution FROM support_tickets WHERE ticket_id = ?
    ''', (ticket_id,))
    
    result = cursor.fetchone()
    if not result:
        print(f"Ticket #{ticket_id} not found.")
        conn.close()
        return
    
    current_status, current_resolution = result
    
    print(f"\nCurrent status: {current_status.upper()}")
    print("\nAvailable statuses:")
    print("1. Open")
    print("2. In Progress")
    print("3. Waiting for Customer")
    print("4. Resolved")
    print("5. Closed")
    print("6. Cancelled")
    
    status_map = {
        "1": "open",
        "2": "in progress", 
        "3": "waiting for customer",
        "4": "resolved",
        "5": "closed",
        "6": "cancelled"
    }
    
    while True:
        choice = input("Select new status (1-6): ").strip()
        if choice in status_map:
            new_status = status_map[choice]
            break
        print("Error: Invalid status selection.")
    
    if current_status == new_status:
        print(f"Status is already set to {new_status.upper()}.")
        conn.close()
        return
    
    # Get resolution details for resolved/closed tickets
    resolution = current_resolution
    if new_status in ['resolved', 'closed'] and not current_resolution:
        print("\nPlease provide resolution details:")
        resolution = ""
        while True:
            line = input()
            if line.lower() == 'done':
                break
            resolution += line + "\n"
        
        if not resolution.strip():
            print("Resolution details are required for resolved/closed tickets.")
            conn.close()
            return
    
    # Get current time
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    resolved_at = now if new_status in ['resolved', 'closed'] else None
    
    # Update ticket status
    try:
        cursor.execute('''
        UPDATE support_tickets
        SET status = ?, resolution = ?, resolved_at = ?, updated_at = ?, last_activity_at = ?
        WHERE ticket_id = ?
        ''', (new_status, resolution, resolved_at, now, now, ticket_id))
        
        conn.commit()
        
        # Log the action
        log_ticket_action(ticket_id, auth.current_user['id'], 'status_changed',
                         {'status': current_status}, {'status': new_status})
        
        print(f"\nTicket status updated to: {new_status.upper()}")
        
        # Add automatic system message about status change
        cursor.execute('''
        INSERT INTO ticket_replies 
        (ticket_id, user_id, message, is_internal, created_at)
        VALUES (?, ?, ?, ?, ?)
        ''', (ticket_id, auth.current_user['id'], 
              f"*** Status changed from {current_status.upper()} to {new_status.upper()} ***", 
              True, now))
        
        conn.commit()
        
        # Send satisfaction survey for resolved/closed tickets
        if new_status in ['resolved', 'closed']:
            send_survey = input("Send satisfaction survey to customer? (y/n): ").strip().lower()
            if send_survey == 'y':
                send_satisfaction_survey(ticket_id)
        
        # Run workflows
        run_ticket_workflows(ticket_id, 'status_changed', new_status=new_status, old_status=current_status)
        
        # Send notifications
        try:
            cursor.execute('''
            SELECT t.user_id, u.username, t.subject
            FROM support_tickets t
            JOIN users u ON t.user_id = u.id
            WHERE t.ticket_id = ?
            ''', (ticket_id,))
            
            ticket_info = cursor.fetchone()
            
            send_reply_notification(
                ticket_id, 
                ticket_info[0], 
                ticket_info[1],
                auth.current_user['username'],
                status_update=new_status
            )
        except Exception as e:
            print(f"Note: Could not send email notification: {e}")
        
    except sqlite3.Error as e:
        print(f"Error updating ticket status: {e}")
    finally:
        conn.close()

def assign_ticket_enhanced(auth, ticket_id):
    """Enhanced ticket assignment with load balancing"""
    if not auth or not auth.current_user:
        print("You must be logged in to assign tickets.")
        return
    
    if not auth.check_permission('manage_tickets'):
        print("You don't have permission to assign tickets.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get current assignment
    cursor.execute('''
    SELECT assigned_to, department FROM support_tickets WHERE ticket_id = ?
    ''', (ticket_id,))
    
    result = cursor.fetchone()
    if not result:
        print(f"Ticket #{ticket_id} not found.")
        conn.close()
        return
    
    current_assigned, current_department = result
    
    print("\nAssignment Options:")
    print("1. Assign to specific user")
    print("2. Assign to department (auto-balance)")
    print("3. Unassign ticket")
    
    choice = input("Select option (1-3): ").strip()
    
    new_assigned = None
    new_department = current_department
    
    if choice == '1':
        # Show available staff
        cursor.execute('''
        SELECT id, username, role, department 
        FROM users 
        WHERE role IN ('staff', 'admin') AND is_active = 1
        ORDER BY department, username
        ''')
        
        staff = cursor.fetchall()
        
        if not staff:
            print("No available staff members found.")
            conn.close()
            return
        
        print("\nAvailable staff:")
        for i, member in enumerate(staff, 1):
            dept = member[3] or 'No Department'
            print(f"{i}. {member[1]} ({member[2]}) - {dept}")
        
        while True:
            try:
                staff_choice = int(input("Select staff member: ").strip())
                if 1 <= staff_choice <= len(staff):
                    new_assigned = staff[staff_choice - 1][0]
                    new_department = staff[staff_choice - 1][3] or current_department
                    break
                else:
                    print("Invalid selection.")
            except ValueError:
                print("Please enter a number.")
    
    elif choice == '2':
        # Show departments
        cursor.execute('''
        SELECT name FROM departments WHERE is_active = 1 ORDER BY name
        ''')
        
        departments = cursor.fetchall()
        
        if not departments:
            print("No active departments found.")
            conn.close()
            return
        
        print("\nAvailable departments:")
        for i, dept in enumerate(departments, 1):
            print(f"{i}. {dept[0]}")
        
        while True:
            try:
                dept_choice = int(input("Select department: ").strip())
                if 1 <= dept_choice <= len(departments):
                    new_department = departments[dept_choice - 1][0]
                    
                    # Auto-assign to least loaded staff member in department
                    cursor.execute('''
                    SELECT u.id, COUNT(t.ticket_id) as ticket_count
                    FROM users u
                    LEFT JOIN support_tickets t ON u.id = t.assigned_to AND t.status NOT IN ('closed', 'resolved')
                    WHERE u.department = ? AND u.role IN ('staff', 'admin') AND u.is_active = 1
                    GROUP BY u.id
                    ORDER BY ticket_count ASC, u.last_login_at DESC
                    LIMIT 1
                    ''', (new_department,))
                    
                    staff_result = cursor.fetchone()
                    if staff_result:
                        new_assigned = staff_result[0]
                    
                    break
                else:
                    print("Invalid selection.")
            except ValueError:
                print("Please enter a number.")
    
    elif choice == '3':
        new_assigned = None
        new_department = None
    
    else:
        print("Invalid choice.")
        conn.close()
        return
    
    # Update assignment
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    try:
        cursor.execute('''
        UPDATE support_tickets
        SET assigned_to = ?, department = ?, updated_at = ?, last_activity_at = ?
        WHERE ticket_id = ?
        ''', (new_assigned, new_department, now, now, ticket_id))
        
        # Record assignment history
        cursor.execute('''
        INSERT INTO ticket_assignments
        (ticket_id, assigned_from, assigned_to, assignment_reason, created_at)
        VALUES (?, ?, ?, ?, ?)
        ''', (ticket_id, current_assigned, new_assigned, 'Manual assignment', now))
        
        conn.commit()
        
        # Log the action
        old_values = {'assigned_to': current_assigned, 'department': current_department}
        new_values = {'assigned_to': new_assigned, 'department': new_department}
        log_ticket_action(ticket_id, auth.current_user['id'], 'assignment_changed', old_values, new_values)
        
        # Display result
        if new_assigned:
            cursor.execute("SELECT username FROM users WHERE id = ?", (new_assigned,))
            assignee_name = cursor.fetchone()[0]
            print(f"\nTicket assigned to: {assignee_name}")
            if new_department:
                print(f"Department: {new_department}")
        else:
            print("\nTicket unassigned.")
        
        # Send notification to new assignee
        if new_assigned:
            try:
                cursor.execute('''
                SELECT t.subject, u1.username as submitter, u2.username as assignee
                FROM support_tickets t
                JOIN users u1 ON t.user_id = u1.id
                JOIN users u2 ON t.assigned_to = u2.id
                WHERE t.ticket_id = ?
                ''', (ticket_id,))
                
                ticket_info = cursor.fetchone()
                send_ticket_notification(ticket_id, ticket_info[0], ticket_info[1], [(ticket_info[2],)])
            except Exception as e:
                print(f"Note: Could not send assignment notification: {e}")
        
    except sqlite3.Error as e:
        print(f"Error updating ticket assignment: {e}")
    finally:
        conn.close()

def add_time_entry(auth, ticket_id):
    """Add time tracking entry"""
    if not auth or not auth.current_user:
        print("You must be logged in to add time entries.")
        return
    
    if not auth.check_permission('manage_tickets'):
        print("You don't have permission to add time entries.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\nAdd Time Entry")
    print("==============")
    
    # Get time details
    while True:
        try:
            duration = float(input("Duration (hours): ").strip())
            if duration > 0:
                break
            else:
                print("Duration must be greater than 0.")
        except ValueError:
            print("Please enter a valid number.")
    
    description = input("Description (optional): ").strip()
    
    billable = input("Is this time billable? (y/n): ").strip().lower() == 'y'
    
    # Calculate duration in minutes
    duration_minutes = int(duration * 60)
    
    # Get current time
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    start_time = (datetime.now() - timedelta(hours=duration)).strftime('%Y-%m-%d %H:%M:%S')
    
    try:
        cursor.execute('''
        INSERT INTO ticket_time_tracking
        (ticket_id, user_id, start_time, end_time, duration_minutes, description, billable, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (ticket_id, auth.current_user['id'], start_time, now, duration_minutes, 
              description, billable, now))
        
        conn.commit()
        
        # Log the action
        log_ticket_action(ticket_id, auth.current_user['id'], 'time_entry_added',
                         {}, {'duration': duration, 'billable': billable})
        
        print(f"\nTime entry added: {duration} hours")
        if billable:
            print("Marked as billable")
        
    except sqlite3.Error as e:
        print(f"Error adding time entry: {e}")
    finally:
        conn.close()

def link_tickets(auth, ticket_id):
    """Link tickets together"""
    if not auth or not auth.current_user:
        print("You must be logged in to link tickets.")
        return
    
    if not auth.check_permission('manage_tickets'):
        print("You don't have permission to link tickets.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\nLink Tickets")
    print("============")
    
    # Get ticket to link to
    linked_ticket_id = input("Enter ticket ID to link to: ").strip()
    
    try:
        linked_ticket_id = int(linked_ticket_id)
        
        # Check if target ticket exists
        cursor.execute('SELECT ticket_id, subject FROM support_tickets WHERE ticket_id = ?', 
                      (linked_ticket_id,))
        target_ticket = cursor.fetchone()
        
        if not target_ticket:
            print("Target ticket not found.")
            conn.close()
            return
        
        if target_ticket[0] == ticket_id:
            print("Cannot link ticket to itself.")
            conn.close()
            return
        
        print(f"\nTarget ticket: #{target_ticket[0]} - {target_ticket[1]}")
        
        # Select link type
        print("\nLink types:")
        print("1. Related to")
        print("2. Duplicate of")
        print("3. Blocks")
        print("4. Blocked by")
        print("5. Parent of")
        print("6. Child of")
        
        link_types = {
            '1': 'related_to',
            '2': 'duplicate_of',
            '3': 'blocks',
            '4': 'blocked_by',
            '5': 'parent_of',
            '6': 'child_of'
        }
        
        while True:
            choice = input("Select link type (1-6): ").strip()
            if choice in link_types:
                link_type = link_types[choice]
                break
            print("Invalid choice.")
        
        # Check if link already exists
        cursor.execute('''
        SELECT link_id FROM ticket_links 
        WHERE ticket_id = ? AND linked_ticket_id = ? AND link_type = ?
        ''', (ticket_id, linked_ticket_id, link_type))
        
        if cursor.fetchone():
            print("This link already exists.")
            conn.close()
            return
        
        # Create the link
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
        INSERT INTO ticket_links
        (ticket_id, linked_ticket_id, link_type, created_by, created_at)
        VALUES (?, ?, ?, ?, ?)
        ''', (ticket_id, linked_ticket_id, link_type, auth.current_user['id'], now))
        
        # Create reciprocal link for certain types
        reciprocal_map = {
            'blocks': 'blocked_by',
            'blocked_by': 'blocks',
            'parent_of': 'child_of',
            'child_of': 'parent_of',
            'related_to': 'related_to'
        }
        
        if link_type in reciprocal_map:
            reciprocal_type = reciprocal_map[link_type]
            cursor.execute('''
            INSERT INTO ticket_links
            (ticket_id, linked_ticket_id, link_type, created_by, created_at)
            VALUES (?, ?, ?, ?, ?)
            ''', (linked_ticket_id, ticket_id, reciprocal_type, auth.current_user['id'], now))
        
        conn.commit()
        
        # Log the action
        log_ticket_action(ticket_id, auth.current_user['id'], 'ticket_linked',
                         {}, {'linked_to': linked_ticket_id, 'link_type': link_type})
        
        print(f"\nTickets linked successfully: {link_type}")
        
    except ValueError:
        print("Invalid ticket ID.")
    except sqlite3.Error as e:
        print(f"Error linking tickets: {e}")
    finally:
        conn.close()
        
# Enhanced ticket creation with templates and attachments
def create_ticket_enhanced(auth):
    if not auth or not auth.current_user:
        print("You must be logged in to create a support ticket.")
        return
    
    if not auth.check_permission('create_ticket'):
        print("You don't have permission to create support tickets.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\nCreate New Support Ticket")
    print("=========================")
    
    # Show available templates
    cursor.execute('''
    SELECT template_id, name, description, category 
    FROM ticket_templates 
    WHERE is_active = 1 
    ORDER BY category, name
    ''')
    templates = cursor.fetchall()
    
    if templates:
        print("\nAvailable templates:")
        print("0. Create custom ticket")
        for i, template in enumerate(templates, 1):
            print(f"{i}. {template[1]} ({template[3]})")
        
        template_choice = input("\nSelect template (0 for custom): ").strip()
        
        try:
            if template_choice != '0':
                template_idx = int(template_choice) - 1
                if 0 <= template_idx < len(templates):
                    return create_ticket_from_template(auth, templates[template_idx][0])
        except ValueError:
            pass
    
    # Custom ticket creation
    return create_custom_ticket(auth)

def create_ticket_from_template(auth, template_id):
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get template details
    cursor.execute('''
    SELECT * FROM ticket_templates WHERE template_id = ?
    ''', (template_id,))
    template = cursor.fetchone()
    
    if not template:
        print("Template not found.")
        conn.close()
        return
    
    print(f"\nUsing template: {template[1]}")
    print(f"Description: {template[2]}")
    
    # Parse form fields if available
    form_fields = {}
    if template[9]:  # form_fields column
        try:
            form_data = json.loads(template[9])
            if 'fields' in form_data:
                print("\nPlease fill in the following information:")
                for field in form_data['fields']:
                    value = get_form_field_value(field)
                    form_fields[field['name']] = value
        except json.JSONDecodeError:
            pass
    
    # Generate subject and message from template
    subject = template[4] or ''  # subject_template
    message = template[5] or ''  # message_template
    
    # Replace placeholders with form field values
    for field_name, field_value in form_fields.items():
        placeholder = f'[{field_name.upper()}]'
        subject = subject.replace(placeholder, str(field_value))
        message = message.replace(placeholder, str(field_value))
    
    # Allow user to edit subject and message
    print(f"\nSubject: {subject}")
    new_subject = input("Edit subject (or press Enter to keep): ").strip()
    if new_subject:
        subject = new_subject
    
    print(f"\nMessage:\n{message}")
    print("\nEdit message (type 'done' on a new line when finished, or 'keep' to use template):")
    
    edit_choice = input().strip().lower()
    if edit_choice != 'keep':
        if edit_choice != 'done':
            message = edit_choice + "\n"
        
        while True:
            line = input()
            if line.lower() == 'done':
                break
            message += line + "\n"
    
    # Use template defaults
    category = template[3]  # category
    priority = template[6] or 'medium'  # default_priority
    impact = template[7] or 'low'  # default_impact
    urgency = template[8] or 'low'  # default_urgency
    
    # Create the ticket
    return create_ticket_with_details(auth, subject, message, category, priority, impact, urgency)

def get_form_field_value(field):
    field_name = field.get('name', '')
    field_type = field.get('type', 'text')
    required = field.get('required', False)
    options = field.get('options', [])
    
    while True:
        if field_type == 'select' and options:
            print(f"\n{field_name.replace('_', ' ').title()}:")
            for i, option in enumerate(options, 1):
                print(f"{i}. {option}")
            
            choice = input("Select option: ").strip()
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(options):
                    return options[idx]
                else:
                    print("Invalid selection.")
            except ValueError:
                print("Please enter a number.")
        else:
            prompt = f"{field_name.replace('_', ' ').title()}: "
            if field_type == 'textarea':
                print(f"\n{field_name.replace('_', ' ').title()} (type 'done' when finished):")
                value = ""
                while True:
                    line = input()
                    if line.lower() == 'done':
                        break
                    value += line + "\n"
                return value.strip()
            else:
                value = input(prompt).strip()
                
            if value or not required:
                return value
            else:
                print("This field is required.")

def create_custom_ticket(auth):
    # Get ticket information from user
    subject = ""
    while not subject:
        subject = input("Subject: ").strip()
        if not subject:
            print("Error: Subject cannot be empty.")
    
    # Enhanced categories with subcategories
    print("\nCategories:")
    categories = {
        "1": {"name": "Technical Support", "subcategories": ["Login Issues", "Performance Problems", "Software Bugs", "Hardware Problems"]},
        "2": {"name": "Academic Inquiry", "subcategories": ["Course Information", "Grading Questions", "Academic Records", "Transcript Requests"]},
        "3": {"name": "Financial Services", "subcategories": ["Payment Plans", "Refunds", "Financial Aid", "Billing Inquiries"]},
        "4": {"name": "Account Access", "subcategories": ["Password Reset", "Account Locked", "Permission Issues", "Profile Updates"]},
        "5": {"name": "Other", "subcategories": ["General Inquiry", "Feedback", "Complaint", "Suggestion"]}
    }
    
    for key, cat in categories.items():
        print(f"{key}. {cat['name']}")
    
    category_choice = ""
    while category_choice not in categories:
        category_choice = input("Select category (1-5): ").strip()
        if category_choice not in categories:
            print("Error: Invalid category selection.")
    
    category = categories[category_choice]["name"]
    
    # Select subcategory
    subcategories = categories[category_choice]["subcategories"]
    print(f"\nSubcategories for {category}:")
    for i, subcat in enumerate(subcategories, 1):
        print(f"{i}. {subcat}")
    
    subcat_choice = ""
    while True:
        try:
            subcat_choice = int(input("Select subcategory: ").strip())
            if 1 <= subcat_choice <= len(subcategories):
                subcategory = subcategories[subcat_choice - 1]
                break
            else:
                print("Error: Invalid subcategory selection.")
        except ValueError:
            print("Error: Please enter a number.")
    
    # Get ticket message
    message = ""
    print("\nPlease describe your issue (type 'done' on a new line when finished):")
    while True:
        line = input()
        if line.lower() == 'done':
            break
        message += line + "\n"
    
    if not message.strip():
        print("Error: Message cannot be empty.")
        return
    
    # Set priority, impact, and urgency
    priority = get_priority_selection()
    impact = get_impact_selection()
    urgency = get_urgency_selection()
    
    return create_ticket_with_details(auth, subject, message, category, priority, impact, urgency, subcategory)

def get_priority_selection():
    print("\nPriority:")
    print("1. Low - General inquiries, minor issues")
    print("2. Medium - Standard requests, moderate impact")
    print("3. High - Urgent issues, significant impact")
    
    priority_map = {"1": "low", "2": "medium", "3": "high"}
    
    while True:
        choice = input("Select priority (1-3): ").strip()
        if choice in priority_map:
            return priority_map[choice]
        print("Error: Invalid priority selection.")

def get_impact_selection():
    print("\nImpact (how many people are affected):")
    print("1. Low - Individual user")
    print("2. Medium - Department or group")
    print("3. High - Institution-wide")
    
    impact_map = {"1": "low", "2": "medium", "3": "high"}
    
    while True:
        choice = input("Select impact (1-3): ").strip()
        if choice in impact_map:
            return impact_map[choice]
        print("Error: Invalid impact selection.")

def get_urgency_selection():
    print("\nUrgency (how quickly this needs to be resolved):")
    print("1. Low - Can wait days/weeks")
    print("2. Medium - Should be resolved within 1-2 days")
    print("3. High - Needs immediate attention")
    
    urgency_map = {"1": "low", "2": "medium", "3": "high"}
    
    while True:
        choice = input("Select urgency (1-3): ").strip()
        if choice in urgency_map:
            return urgency_map[choice]
        print("Error: Invalid urgency selection.")

def create_ticket_with_details(auth, subject, message, category, priority, impact, urgency, subcategory=None):
    conn = get_connection()
    cursor = conn.cursor()
    
    # Determine SLA and department assignment
    cursor.execute('''
    SELECT sla_id, first_response_hours, resolution_hours 
    FROM sla_policies 
    WHERE priority = ? AND impact = ? AND urgency = ? AND is_active = 1
    ORDER BY sla_id LIMIT 1
    ''', (priority, impact, urgency))
    
    sla_result = cursor.fetchone()
    due_date = None
    if sla_result:
        resolution_hours = sla_result[2]
        due_date = (datetime.now() + timedelta(hours=resolution_hours)).strftime('%Y-%m-%d %H:%M:%S')
    
    # Auto-assign to department based on category
    assigned_to = None
    department = None
    
    category_dept_map = {
        "Technical Support": "IT Support",
        "Academic Inquiry": "Academic Affairs",
        "Financial Services": "Financial Services",
        "Account Access": "IT Support"
    }
    
    if category in category_dept_map:
        department = category_dept_map[category]
        
        # Find available staff in the department
        cursor.execute('''
        SELECT u.id FROM users u 
        JOIN departments d ON u.department = d.name 
        WHERE d.name = ? AND u.role IN ('staff', 'admin') AND u.is_active = 1
        ORDER BY u.last_login_at DESC LIMIT 1
        ''', (department,))
        
        dept_staff = cursor.fetchone()
        if dept_staff:
            assigned_to = dept_staff[0]
    
    # Get current time
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Insert ticket into database
    try:
        cursor.execute('''
        INSERT INTO support_tickets 
        (user_id, assigned_to, subject, message, category, subcategory, status, priority, 
         impact, urgency, source, due_date, department, created_at, updated_at, last_activity_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (auth.current_user['id'], assigned_to, subject, message, category, subcategory, 
              'open', priority, impact, urgency, 'web', due_date, department, now, now, now))
        
        conn.commit()
        ticket_id = cursor.lastrowid
        
        # Log ticket creation
        log_ticket_action(ticket_id, auth.current_user['id'], 'created', {}, {
            'subject': subject, 'category': category, 'priority': priority,
            'impact': impact, 'urgency': urgency
        })
        
        # Handle file attachments
        handle_file_attachments(ticket_id, None, auth.current_user['id'])
        
        print(f"\nTicket #{ticket_id} created successfully!")
        print(f"Priority: {priority.upper()}, Impact: {impact.upper()}, Urgency: {urgency.upper()}")
        if due_date:
            print(f"Due date: {due_date}")
        if assigned_to:
            cursor.execute("SELECT username FROM users WHERE id = ?", (assigned_to,))
            assignee = cursor.fetchone()
            if assignee:
                print(f"Assigned to: {assignee[0]}")
        
        # Run automated workflows
        run_ticket_workflows(ticket_id, 'ticket_created')
        
        # Send notifications
        try:
            # Notify assigned staff member
            if assigned_to:
                send_ticket_notification(ticket_id, subject, auth.current_user['username'], [(assignee[0],)])
            
            # Notify department managers
            if department:
                cursor.execute('''
                SELECT u.username FROM users u 
                JOIN departments d ON u.id = d.manager_id 
                WHERE d.name = ?
                ''', (department,))
                managers = cursor.fetchall()
                if managers:
                    send_ticket_notification(ticket_id, subject, auth.current_user['username'], managers)
        except Exception as e:
            print(f"Note: Could not send email notification: {e}")
        
        # Suggest knowledge base articles
        suggest_knowledge_base_articles(ticket_id, subject + " " + message)

        # Check for immediate SLA breach (rare but possible)
        if due_date:
            try:
                due_datetime = datetime.strptime(due_date, '%Y-%m-%d %H:%M:%S')
                if datetime.now() > due_datetime:
                    send_sla_alert(ticket_id, alert_type='overdue')
                    print("⚠️  SLA alert sent - ticket is already overdue")
            except (ValueError, Exception) as e:
                # Skip SLA check if date parsing fails
                pass

    except sqlite3.Error as e:
        print(f"Error creating support ticket: {e}")
    finally:
        conn.close()

def handle_file_attachments(ticket_id, reply_id, user_id):
    """Handle file attachments for tickets or replies"""
    while True:
        attach_file = input("\nWould you like to attach a file? (y/n): ").strip().lower()
        if attach_file == 'n':
            break
        elif attach_file == 'y':
            file_path = input("Enter file path: ").strip()
            if os.path.exists(file_path):
                if add_attachment(ticket_id, reply_id, file_path, user_id):
                    print("File attached successfully!")
                else:
                    print("Failed to attach file.")
            else:
                print("File not found.")
        else:
            print("Please enter 'y' or 'n'.")

def add_attachment(ticket_id, reply_id, file_path, user_id):
    """Add a file attachment to a ticket or reply"""
    try:
        # Create attachments directory if it doesn't exist
        upload_dir = "attachments"
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)
        
        # Get file information
        original_filename = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        mime_type, _ = mimetypes.guess_type(file_path)
        
        # Check file size (limit to 10MB)
        if file_size > 10 * 1024 * 1024:
            print("Error: File size exceeds 10MB limit.")
            return False
        
        # Check file type
        allowed_types = [
            'image/', 'text/', 'application/pdf', 'application/msword',
            'application/vnd.openxmlformats-officedocument',
            'application/zip', 'application/x-zip-compressed'
        ]
        
        if mime_type and not any(mime_type.startswith(t) for t in allowed_types):
            print(f"Error: File type {mime_type} not allowed.")
            return False
        
        # Generate unique filename
        file_hash = hashlib.md5()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                file_hash.update(chunk)
        
        file_extension = os.path.splitext(original_filename)[1]
        unique_filename = f"{file_hash.hexdigest()}{file_extension}"
        upload_path = os.path.join(upload_dir, unique_filename)
        
        # Copy file to upload directory
        import shutil
        shutil.copy2(file_path, upload_path)
        
        # Save attachment record
        conn = get_connection()
        cursor = conn.cursor()
        
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
        INSERT INTO ticket_attachments 
        (ticket_id, reply_id, filename, original_filename, file_size, mime_type, 
         file_hash, uploaded_by, upload_path, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (ticket_id, reply_id, unique_filename, original_filename, file_size,
              mime_type, file_hash.hexdigest(), user_id, upload_path, now))
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error uploading file: {e}")
        return False

def suggest_knowledge_base_articles(ticket_id, content):
    """Suggest relevant knowledge base articles based on ticket content"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Simple keyword matching for suggestions
    keywords = extract_keywords(content.lower())
    
    if keywords:
        # Search for articles with matching keywords
        keyword_conditions = []
        params = []
        
        for keyword in keywords[:5]:  # Limit to top 5 keywords
            keyword_conditions.append("(title LIKE ? OR content LIKE ? OR search_keywords LIKE ?)")
            params.extend([f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"])
        
        if keyword_conditions:
            query = f'''
            SELECT article_id, title, category 
            FROM knowledge_base 
            WHERE status = 'published' AND ({" OR ".join(keyword_conditions)})
            ORDER BY helpful_votes DESC, views DESC
            LIMIT 3
            '''
            
            cursor.execute(query, params)
            articles = cursor.fetchall()
            
            if articles:
                print("\nSuggested knowledge base articles that might help:")
                for article in articles:
                    print(f"- {article[1]} (Category: {article[2]})")
                
                # Store suggestions in ticket
                article_ids = [str(a[0]) for a in articles]
                cursor.execute('''
                UPDATE support_tickets 
                SET knowledge_base_articles = ? 
                WHERE ticket_id = ?
                ''', (','.join(article_ids), ticket_id))
                
                conn.commit()
    
    conn.close()

def extract_keywords(text):
    """Extract relevant keywords from text"""
    # Remove common words and extract meaningful terms
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'can', 'cant', 'cannot', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them', 'my', 'your', 'his', 'her', 'its', 'our', 'their'}
    
    # Simple word extraction
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text)
    keywords = [word for word in words if word.lower() not in stop_words]
    
    # Return most frequent keywords
    from collections import Counter
    word_counts = Counter(keywords)
    return [word for word, count in word_counts.most_common(10)]

def run_ticket_workflows(ticket_id, trigger_type, **kwargs):
    """Run automated workflows based on triggers"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get active workflows for this trigger
    cursor.execute('''
    SELECT workflow_id, name, trigger_conditions, actions 
    FROM ticket_workflows 
    WHERE trigger_type = ? AND is_active = 1
    ''', (trigger_type,))
    
    workflows = cursor.fetchall()
    
    for workflow in workflows:
        workflow_id, name, conditions_json, actions_json = workflow
        
        try:
            conditions = json.loads(conditions_json) if conditions_json else {}
            actions = json.loads(actions_json) if actions_json else {}
            
            # Check if conditions are met
            if check_workflow_conditions(ticket_id, conditions, **kwargs):
                execute_workflow_actions(ticket_id, actions)
                print(f"Executed workflow: {name}")
                
        except json.JSONDecodeError:
            print(f"Error parsing workflow {name}")
    
    conn.close()

def check_workflow_conditions(ticket_id, conditions, **kwargs):
    """Check if workflow conditions are met"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get ticket details
    cursor.execute('SELECT * FROM support_tickets WHERE ticket_id = ?', (ticket_id,))
    ticket = cursor.fetchone()
    
    if not ticket:
        conn.close()
        return False
    
    # Convert to dict for easier access
    columns = [desc[0] for desc in cursor.description]
    ticket_dict = dict(zip(columns, ticket))
    
    # Check each condition
    for field, expected_value in conditions.items():
        if field in ticket_dict:
            if ticket_dict[field] != expected_value:
                conn.close()
                return False
        elif field in kwargs:
            if kwargs[field] != expected_value:
                conn.close()
                return False
    
    conn.close()
    return True

def execute_workflow_actions(ticket_id, actions):
    """Execute workflow actions"""
    conn = get_connection()
    cursor = conn.cursor()
    
    for action, value in actions.items():
        if action == 'assign_to_department':
            # Find available staff in department
            cursor.execute('''
            SELECT u.id FROM users u 
            JOIN departments d ON u.department = d.name 
            WHERE d.name = ? AND u.role IN ('staff', 'admin') AND u.is_active = 1
            ORDER BY u.last_login_at DESC LIMIT 1
            ''', (value,))
            
            staff = cursor.fetchone()
            if staff:
                cursor.execute('''
                UPDATE support_tickets 
                SET assigned_to = ?, department = ?, updated_at = ?
                WHERE ticket_id = ?
                ''', (staff[0], value, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), ticket_id))
        
        elif action == 'set_priority':
            cursor.execute('''
            UPDATE support_tickets 
            SET priority = ?, updated_at = ?
            WHERE ticket_id = ?
            ''', (value, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), ticket_id))
        
        elif action == 'change_status':
            cursor.execute('''
            UPDATE support_tickets 
            SET status = ?, updated_at = ?
            WHERE ticket_id = ?
            ''', (value, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), ticket_id))
        
        elif action == 'escalate_to_manager':
            if value:
                escalate_ticket(ticket_id, 'workflow_auto_escalation')
        
        elif action == 'send_survey':
            if value:
                send_satisfaction_survey(ticket_id)
    
    conn.commit()
    conn.close()

def escalate_ticket(ticket_id, reason='manual'):
    """Escalate a ticket to higher level"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get current ticket info
    cursor.execute('''
    SELECT assigned_to, department, escalation_level 
    FROM support_tickets 
    WHERE ticket_id = ?
    ''', (ticket_id,))
    
    ticket_info = cursor.fetchone()
    if not ticket_info:
        conn.close()
        return
    
    current_assigned, department, current_level = ticket_info
    new_level = current_level + 1
    
    # Find manager to escalate to
    escalate_to = None
    
    if department:
        cursor.execute('''
        SELECT manager_id FROM departments WHERE name = ?
        ''', (department,))
        dept_manager = cursor.fetchone()
        if dept_manager and dept_manager[0]:
            escalate_to = dept_manager[0]
    
    if not escalate_to:
        # Escalate to any admin
        cursor.execute('''
        SELECT id FROM users WHERE role = 'admin' AND is_active = 1 LIMIT 1
        ''', )
        admin = cursor.fetchone()
        if admin:
            escalate_to = admin[0]
    
    if escalate_to:
        # Update ticket
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
        UPDATE support_tickets 
        SET assigned_to = ?, escalation_level = ?, updated_at = ?
        WHERE ticket_id = ?
        ''', (escalate_to, new_level, now, ticket_id))
        
        # Record escalation
        cursor.execute('''
        INSERT INTO ticket_escalations 
        (ticket_id, escalation_level, escalated_to, escalation_reason, created_at)
        VALUES (?, ?, ?, ?, ?)
        ''', (ticket_id, new_level, escalate_to, reason, now))
        
        conn.commit()
        print(f"Ticket #{ticket_id} escalated to level {new_level}")
    
    conn.close()

def log_ticket_action(ticket_id, user_id, action, old_values, new_values, ip_address=None, user_agent=None):
    """Log ticket actions for audit trail"""
    conn = get_connection()
    cursor = conn.cursor()
    
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute('''
    INSERT INTO ticket_audit_log 
    (ticket_id, user_id, action, old_values, new_values, ip_address, user_agent, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (ticket_id, user_id, action, json.dumps(old_values), json.dumps(new_values), 
          ip_address, user_agent, now))
    
    conn.commit()
    conn.close()

# Enhanced search functionality
def advanced_search_tickets(auth):
    if not auth or not auth.current_user:
        print("You must be logged in to search tickets.")
        return
    
    print("\nAdvanced Ticket Search")
    print("=====================")
    
    # Build search criteria
    criteria = {}
    
    # Text search
    search_text = input("Search text (subject/message): ").strip()
    if search_text:
        criteria['text'] = search_text
    
    # Status filter
    print("\nStatus filter:")
    print("1. All statuses")
    print("2. Open only")
    print("3. In progress only")
    print("4. Resolved only")
    print("5. Closed only")
    
    status_choice = input("Select status filter (1-5): ").strip()
    status_map = {'2': 'open', '3': 'in progress', '4': 'resolved', '5': 'closed'}
    if status_choice in status_map:
        criteria['status'] = status_map[status_choice]
    
    # Priority filter
    print("\nPriority filter:")
    print("1. All priorities")
    print("2. Low only")
    print("3. Medium only")
    print("4. High only")
    
    priority_choice = input("Select priority filter (1-4): ").strip()
    priority_map = {'2': 'low', '3': 'medium', '4': 'high'}
    if priority_choice in priority_map:
        criteria['priority'] = priority_map[priority_choice]
    
    # Category filter
    categories = ["Technical Support", "Academic Inquiry", "Financial Services", "Account Access", "Other"]
    print(f"\nCategory filter:")
    print("0. All categories")
    for i, cat in enumerate(categories, 1):
        print(f"{i}. {cat}")
    
    cat_choice = input("Select category (0-5): ").strip()
    try:
        cat_idx = int(cat_choice)
        if 1 <= cat_idx <= len(categories):
            criteria['category'] = categories[cat_idx - 1]
    except ValueError:
        pass
    
    # Date range
    start_date = input("Start date (YYYY-MM-DD, or press Enter to skip): ").strip()
    if start_date:
        try:
            datetime.strptime(start_date, '%Y-%m-%d')
            criteria['start_date'] = start_date
        except ValueError:
            print("Invalid date format, skipping date filter.")
    
    end_date = input("End date (YYYY-MM-DD, or press Enter to skip): ").strip()
    if end_date:
        try:
            datetime.strptime(end_date, '%Y-%m-%d')
            criteria['end_date'] = end_date
        except ValueError:
            print("Invalid date format, skipping date filter.")
    
    # Assigned user filter (admin only)
    if auth.check_permission('view_all_tickets'):
        assigned_user = input("Assigned to username (or press Enter to skip): ").strip()
        if assigned_user:
            criteria['assigned_user'] = assigned_user
    
    # Save search option
    save_search = input("Save this search? (y/n): ").strip().lower()
    if save_search == 'y':
        search_name = input("Enter search name: ").strip()
        if search_name:
            save_search_criteria(auth.current_user['id'], search_name, criteria)
    
    # Execute search
    results = execute_search(auth, criteria)
    display_search_results(auth, results)

def save_search_criteria(user_id, name, criteria):
    """Save search criteria for later use"""
    conn = get_connection()
    cursor = conn.cursor()
    
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute('''
    INSERT INTO saved_searches (user_id, name, search_criteria, created_at)
    VALUES (?, ?, ?, ?)
    ''', (user_id, name, json.dumps(criteria), now))
    
    conn.commit()
    conn.close()
    print(f"Search '{name}' saved successfully!")

def load_saved_searches(auth):
    """Load and execute saved searches"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT search_id, name, search_criteria 
    FROM saved_searches 
    WHERE user_id = ? 
    ORDER BY created_at DESC
    ''', (auth.current_user['id'],))
    
    searches = cursor.fetchall()
    
    if not searches:
        print("No saved searches found.")
        conn.close()
        return
    
    print("\nSaved Searches:")
    for i, search in enumerate(searches, 1):
        print(f"{i}. {search[1]}")
    
    choice = input("Select search to execute (or press Enter to cancel): ").strip()
    
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(searches):
            search_id, name, criteria_json = searches[idx]
            criteria = json.loads(criteria_json)
            
            print(f"\nExecuting search: {name}")
            results = execute_search(auth, criteria)
            display_search_results(auth, results)
    except (ValueError, json.JSONDecodeError):
        print("Invalid selection or corrupted search data.")
    
    conn.close()

def execute_search(auth, criteria):
    """Execute search with given criteria"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Build query
    where_conditions = []
    params = []
    
    # Check permissions
    if not auth.check_permission('view_all_tickets'):
        where_conditions.append("t.user_id = ?")
        params.append(auth.current_user['id'])
    
    # Text search
    if 'text' in criteria:
        where_conditions.append("(t.subject LIKE ? OR t.message LIKE ?)")
        text_param = f"%{criteria['text']}%"
        params.extend([text_param, text_param])
    
    # Status filter
    if 'status' in criteria:
        where_conditions.append("t.status = ?")
        params.append(criteria['status'])
    
    # Priority filter
    if 'priority' in criteria:
        where_conditions.append("t.priority = ?")
        params.append(criteria['priority'])
    
    # Category filter
    if 'category' in criteria:
        where_conditions.append("t.category = ?")
        params.append(criteria['category'])
    
    # Date range
    if 'start_date' in criteria:
        where_conditions.append("DATE(t.created_at) >= ?")
        params.append(criteria['start_date'])
    
    if 'end_date' in criteria:
        where_conditions.append("DATE(t.created_at) <= ?")
        params.append(criteria['end_date'])
    
    # Assigned user
    if 'assigned_user' in criteria:
        where_conditions.append("u2.username = ?")
        params.append(criteria['assigned_user'])
    
    # Build final query
    where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
    
    query = f'''
    SELECT t.*, u1.username as submitter, u2.username as assignee
    FROM support_tickets t
    JOIN users u1 ON t.user_id = u1.id
    LEFT JOIN users u2 ON t.assigned_to = u2.id
    WHERE {where_clause}
    ORDER BY t.updated_at DESC
    '''
    
    cursor.execute(query, params)
    results = cursor.fetchall()
    
    conn.close()
    return results

def display_search_results(auth, results):
    """Display search results"""
    if not results:
        print("\nNo tickets found matching your search criteria.")
        return
    
    print(f"\nSearch Results ({len(results)} tickets found):")
    print("=" * 120)
    print(f"{'ID':<5} {'Subject':<30} {'From':<15} {'Assigned':<15} {'Status':<12} {'Priority':<8} {'Updated':<20}")
    print("=" * 120)
    
    for ticket in results:
        assignee = ticket['assignee'] or 'Unassigned'
        print(f"{ticket['ticket_id']:<5} {ticket['subject'][:28]:<30} {ticket['submitter'][:13]:<15} "
              f"{assignee[:13]:<15} {ticket['status'].upper():<12} {ticket['priority'].upper():<8} "
              f"{ticket['updated_at']:<20}")
    
    print("=" * 100)
    
    # Ask if user wants to view a specific ticket
    ticket_choice = input("\nEnter ticket number to view details (or press Enter to return): ")
    
    if ticket_choice:
        try:
            ticket_id = int(ticket_choice)
            view_ticket_detail_enhanced(auth, ticket_id)
        except ValueError:
            print("Invalid ticket number.")
    
    conn.close()

def view_all_tickets_enhanced(auth):
    """Enhanced view of all tickets for admins"""
    if not auth or not auth.current_user:
        print("You must be logged in to view all tickets.")
        return
    
    if not auth.check_permission('view_all_tickets'):
        print("You don't have permission to view all tickets.")
        return
    
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Enhanced filter options
    print("\nAdvanced Filter Options:")
    print("1. All tickets")
    print("2. Unassigned tickets")
    print("3. My assigned tickets")
    print("4. Overdue tickets")
    print("5. High priority tickets")
    print("6. Escalated tickets")
    print("7. Custom filter")
    
    filter_choice = input("Select filter (1-7): ").strip()
    
    where_conditions = []
    params = []
    
    if filter_choice == '2':
        where_conditions.append("t.assigned_to IS NULL")
    elif filter_choice == '3':
        where_conditions.append("t.assigned_to = ?")
        params.append(auth.current_user['id'])
    elif filter_choice == '4':
        where_conditions.append("t.due_date IS NOT NULL AND t.due_date < ? AND t.status NOT IN ('resolved', 'closed')")
        params.append(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    elif filter_choice == '5':
        where_conditions.append("t.priority = 'high'")
    elif filter_choice == '6':
        where_conditions.append("t.escalation_level > 0")
    elif filter_choice == '7':
        # Custom filter
        status_filter = input("Status (open/in progress/resolved/closed, or press Enter for all): ").strip()
        if status_filter:
            where_conditions.append("t.status = ?")
            params.append(status_filter)
        
        priority_filter = input("Priority (low/medium/high, or press Enter for all): ").strip()
        if priority_filter:
            where_conditions.append("t.priority = ?")
            params.append(priority_filter)
        
        dept_filter = input("Department (or press Enter for all): ").strip()
        if dept_filter:
            where_conditions.append("t.department = ?")
            params.append(dept_filter)
    
    where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
    
    # Get tickets with enhanced information
    cursor.execute(f'''
    SELECT t.ticket_id, t.subject, t.category, t.status, t.priority, t.impact, t.urgency,
           t.created_at, t.updated_at, t.due_date, t.escalation_level,
           u1.username as submitter, u2.username as assignee, t.department
    FROM support_tickets t
    JOIN users u1 ON t.user_id = u1.id
    LEFT JOIN users u2 ON t.assigned_to = u2.id
    WHERE {where_clause}
    ORDER BY 
        CASE WHEN t.due_date IS NOT NULL AND t.due_date < datetime('now') AND t.status NOT IN ('resolved', 'closed') THEN 1 ELSE 2 END,
        t.escalation_level DESC,
        CASE 
            WHEN t.status = 'open' THEN 1
            WHEN t.status = 'in progress' THEN 2
            WHEN t.status = 'waiting for customer' THEN 3
            WHEN t.status = 'resolved' THEN 4
            WHEN t.status = 'closed' THEN 5
        END,
        CASE 
            WHEN t.priority = 'high' THEN 1
            WHEN t.priority = 'medium' THEN 2
            WHEN t.priority = 'low' THEN 3
        END,
        t.updated_at DESC
    ''', params)
    
    tickets = cursor.fetchall()
    
    if not tickets:
        print("\nNo tickets found with the selected filter.")
        conn.close()
        return
    
    print(f"\nSupport Tickets ({len(tickets)} found):")
    print("=" * 140)
    print(f"{'ID':<5} {'Subject':<25} {'From':<12} {'Assigned':<12} {'Dept':<10} {'Status':<12} {'P/I/U':<7} {'Updated':<20}")
    print("=" * 140)
    
    for ticket in tickets:
        # Status indicators
        status_icon = {
            'open': '🆕',
            'in progress': '🔄',
            'waiting for customer': '⏳',
            'resolved': '✅',
            'closed': '🔒'
        }.get(ticket['status'], '📋')
        
        # Priority/Impact/Urgency indicators
        priority_indicators = f"{ticket['priority'][0].upper()}/{ticket['impact'][0].upper()}/{ticket['urgency'][0].upper()}"
        
        assignee = ticket['assignee'] or 'Unassigned'
        department = ticket['department'] or 'None'
        
        print(f"{ticket['ticket_id']:<5} {ticket['subject'][:23]:<25} {ticket['submitter'][:10]:<12} "
              f"{assignee[:10]:<12} {department[:8]:<10} {status_icon} {ticket['status'][:10]:<10} "
              f"{priority_indicators:<7} {ticket['updated_at']:<20}")
        
        # Show special indicators
        indicators = []
        if ticket['escalation_level'] > 0:
            indicators.append(f"🔺 L{ticket['escalation_level']}")
        
        if ticket['due_date']:
            due_dt = datetime.strptime(ticket['due_date'], '%Y-%m-%d %H:%M:%S')
            if due_dt < datetime.now() and ticket['status'] not in ['resolved', 'closed']:
                indicators.append("⚠️  OVERDUE")
        
        if indicators:
            print(f"      {' '.join(indicators)}")
    
    print("=" * 140)
    
    # Bulk actions menu
    print("\nBulk Actions:")
    print("1. View ticket details")
    print("2. Bulk assign tickets")
    print("3. Bulk status change")
    print("4. Export ticket list")
    print("5. Return to menu")
    
    action_choice = input("Select action (1-5): ").strip()
    
    if action_choice == '1':
        ticket_choice = input("Enter ticket number to view details: ")
        try:
            ticket_id = int(ticket_choice)
            view_ticket_detail_enhanced(auth, ticket_id)
        except ValueError:
            print("Invalid ticket number.")
    elif action_choice == '2':
        bulk_assign_tickets(auth, [t['ticket_id'] for t in tickets])
    elif action_choice == '3':
        bulk_status_change(auth, [t['ticket_id'] for t in tickets])
    elif action_choice == '4':
        export_ticket_list(auth, tickets)
    
    conn.close()

def bulk_assign_tickets(auth, ticket_ids):
    """Bulk assign multiple tickets"""
    if not auth.check_permission('manage_tickets'):
        print("You don't have permission to assign tickets.")
        return
    
    # Get ticket IDs to assign
    ticket_input = input("Enter ticket IDs to assign (comma-separated, or 'all' for all): ").strip()
    
    if ticket_input.lower() == 'all':
        selected_tickets = ticket_ids
    else:
        try:
            selected_tickets = [int(x.strip()) for x in ticket_input.split(',')]
            selected_tickets = [tid for tid in selected_tickets if tid in ticket_ids]
        except ValueError:
            print("Invalid ticket IDs.")
            return
    
    if not selected_tickets:
        print("No valid tickets selected.")
        return
    
    # Show staff for assignment
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT id, username, role, department 
    FROM users 
    WHERE role IN ('staff', 'admin') AND is_active = 1
    ORDER BY department, username
    ''')
    
    staff = cursor.fetchall()
    
    print("\nAvailable staff:")
    for i, member in enumerate(staff, 1):
        dept = member[3] or 'No Department'
        print(f"{i}. {member[1]} ({member[2]}) - {dept}")
    
    try:
        staff_choice = int(input("Select staff member: ").strip())
        if 1 <= staff_choice <= len(staff):
            assignee_id = staff[staff_choice - 1][0]
            assignee_name = staff[staff_choice - 1][1]
            
            # Perform bulk assignment
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            for ticket_id in selected_tickets:
                cursor.execute('''
                UPDATE support_tickets
                SET assigned_to = ?, updated_at = ?, last_activity_at = ?
                WHERE ticket_id = ?
                ''', (assignee_id, now, now, ticket_id))
                
                # Log the action
                log_ticket_action(ticket_id, auth.current_user['id'], 'bulk_assigned',
                                 {}, {'assigned_to': assignee_id})
            
            conn.commit()
            print(f"\n{len(selected_tickets)} tickets assigned to {assignee_name}")
        else:
            print("Invalid selection.")
    except ValueError:
        print("Please enter a number.")
    finally:
        conn.close()

def bulk_status_change(auth, ticket_ids):
    """Bulk change status of multiple tickets"""
    if not auth.check_permission('manage_tickets'):
        print("You don't have permission to change ticket status.")
        return
    
    # Get ticket IDs
    ticket_input = input("Enter ticket IDs to update (comma-separated, or 'all' for all): ").strip()
    
    if ticket_input.lower() == 'all':
        selected_tickets = ticket_ids
    else:
        try:
            selected_tickets = [int(x.strip()) for x in ticket_input.split(',')]
            selected_tickets = [tid for tid in selected_tickets if tid in ticket_ids]
        except ValueError:
            print("Invalid ticket IDs.")
            return
    
    if not selected_tickets:
        print("No valid tickets selected.")
        return
    
    # Status selection
    print("\nSelect new status:")
    print("1. Open")
    print("2. In Progress")
    print("3. Waiting for Customer")
    print("4. Resolved")
    print("5. Closed")
    
    status_map = {
        "1": "open",
        "2": "in progress",
        "3": "waiting for customer",
        "4": "resolved",
        "5": "closed"
    }
    
    status_choice = input("Select status (1-5): ").strip()
    
    if status_choice not in status_map:
        print("Invalid status selection.")
        return
    
    new_status = status_map[status_choice]
    
    # Perform bulk status change
    conn = get_connection()
    cursor = conn.cursor()
    
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    resolved_at = now if new_status in ['resolved', 'closed'] else None
    
    for ticket_id in selected_tickets:
        cursor.execute('''
        UPDATE support_tickets
        SET status = ?, resolved_at = ?, updated_at = ?, last_activity_at = ?
        WHERE ticket_id = ?
        ''', (new_status, resolved_at, now, now, ticket_id))
        
        # Log the action
        log_ticket_action(ticket_id, auth.current_user['id'], 'bulk_status_change',
                         {}, {'status': new_status})
    
    conn.commit()
    conn.close()
    
    print(f"\n{len(selected_tickets)} tickets updated to {new_status.upper()}")

def export_ticket_list(auth, tickets):
    """Export ticket list to file"""
    try:
        if not os.path.exists('exports'):
            os.makedirs('exports')
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"exports/ticket_list_{timestamp}.csv"
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            import csv
            
            fieldnames = ['ticket_id', 'subject', 'submitter', 'assignee', 'department', 
                         'category', 'status', 'priority', 'impact', 'urgency', 
                         'created_at', 'updated_at', 'due_date']
            
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for ticket in tickets:
                writer.writerow({
                    'ticket_id': ticket['ticket_id'],
                    'subject': ticket['subject'],
                    'submitter': ticket['submitter'],
                    'assignee': ticket['assignee'] or '',
                    'department': ticket['department'] or '',
                    'category': ticket['category'],
                    'status': ticket['status'],
                    'priority': ticket['priority'],
                    'impact': ticket['impact'],
                    'urgency': ticket['urgency'],
                    'created_at': ticket['created_at'],
                    'updated_at': ticket['updated_at'],
                    'due_date': ticket['due_date'] or ''
                })
        
        print(f"\nTicket list exported to {filename}")
        
    except Exception as e:
        print(f"Error exporting ticket list: {e}")

def generate_enhanced_ticket_report(auth):
    """Generate comprehensive ticket reports"""
    if not auth or not auth.current_user:
        print("You must be logged in to generate reports.")
        return
    
    if not auth.check_permission('view_all_tickets'):
        print("You don't have permission to generate reports.")
        return
    
    print("\nEnhanced Ticket Report Generator")
    print("================================")
    print("1. Executive Summary Report")
    print("2. Staff Performance Report")
    print("3. SLA Compliance Report")
    print("4. Customer Satisfaction Report")
    print("5. Trend Analysis Report")
    print("6. Department Performance Report")
    print("7. Custom Date Range Report")
    
    report_choice = input("Select report type (1-7): ").strip()
    
    if report_choice == '1':
        generate_executive_summary(auth)
    elif report_choice == '2':
        generate_staff_performance_report(auth)
    elif report_choice == '3':
        generate_sla_compliance_report(auth)
    elif report_choice == '4':
        generate_satisfaction_report(auth)
    elif report_choice == '5':
        generate_trend_analysis_report(auth)
    elif report_choice == '6':
        generate_department_report(auth)
    elif report_choice == '7':
        generate_custom_date_report(auth)
    else:
        print("Invalid report selection.")

def generate_executive_summary(auth):
    """Generate executive summary report"""
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\nExecutive Summary Report")
    print("=" * 50)
    
    # Time period selection
    period = input("Select period (7d/30d/90d/1y): ").strip().lower()
    
    days_map = {'7d': 7, '30d': 30, '90d': 90, '1y': 365}
    days = days_map.get(period, 30)
    
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    
    # Key metrics
    cursor.execute('''
    SELECT 
        COUNT(*) as total_tickets,
        COUNT(CASE WHEN status IN ('resolved', 'closed') THEN 1 END) as resolved_tickets,
        COUNT(CASE WHEN status = 'open' THEN 1 END) as open_tickets,
        COUNT(CASE WHEN priority = 'high' THEN 1 END) as high_priority,
        AVG(CASE WHEN resolved_at IS NOT NULL 
            THEN (julianday(resolved_at) - julianday(created_at)) * 24 
            ELSE NULL END) as avg_resolution_hours,
        AVG(satisfaction_rating) as avg_satisfaction
    FROM support_tickets
    WHERE created_at >= ?
    ''', (start_date,))
    
    metrics = cursor.fetchone()
    
    if metrics[0] > 0:  # total_tickets
        resolution_rate = (metrics[1] / metrics[0] * 100)  # resolved/total
        
        print(f"\n📊 KEY METRICS ({period.upper()})")
        print("-" * 30)
        print(f"Total Tickets: {metrics[0]}")
        print(f"Resolution Rate: {resolution_rate:.1f}%")
        print(f"Open Tickets: {metrics[2]}")
        print(f"High Priority: {metrics[3]}")
        
        if metrics[4]:
            print(f"Avg Resolution Time: {metrics[4]:.1f} hours")
        
        if metrics[5]:
            print(f"Customer Satisfaction: {metrics[5]:.1f}/5.0")
        
        # Top categories
        print(f"\n📋 TOP CATEGORIES")
        print("-" * 30)
        
        cursor.execute('''
        SELECT category, COUNT(*) as count
        FROM support_tickets
        WHERE created_at >= ?
        GROUP BY category
        ORDER BY count DESC
        LIMIT 5
        ''', (start_date,))
        
        categories = cursor.fetchall()
        for cat, count in categories:
            percentage = (count / metrics[0] * 100)
            print(f"{cat}: {count} ({percentage:.1f}%)")
        
        # Staff workload
        print(f"\n👥 STAFF WORKLOAD")
        print("-" * 30)
        
        cursor.execute('''
        SELECT u.username, 
               COUNT(t.ticket_id) as assigned,
               COUNT(CASE WHEN t.status IN ('resolved', 'closed') THEN 1 END) as resolved
        FROM users u
        LEFT JOIN support_tickets t ON u.id = t.assigned_to AND t.created_at >= ?
        WHERE u.role IN ('staff', 'admin') AND u.is_active = 1
        GROUP BY u.id, u.username
        HAVING assigned > 0
        ORDER BY assigned DESC
        LIMIT 5
        ''', (start_date,))
        
        staff_stats = cursor.fetchall()
        for username, assigned, resolved in staff_stats:
            resolution_rate = (resolved / assigned * 100) if assigned > 0 else 0
            print(f"{username}: {assigned} assigned, {resolved} resolved ({resolution_rate:.1f}%)")
    
    # Save report option
    save_choice = input("\nSave report to file? (y/n): ").strip().lower()
    if save_choice == 'y':
        save_report_to_file("executive_summary", period, auth)
    
    conn.close()

def system_management_menu(auth):
    """System management menu for admins"""
    if not auth.check_permission('manage_tickets'):
        print("You don't have permission to access system management.")
        return
    
    while True:
        print("\nSystem Management")
        print("================")
        print("1. Manage SLA Policies")
        print("2. Manage Ticket Templates")
        print("3. Manage Workflows")
        print("4. Manage Departments")
        print("5. Manage Organizations")
        print("6. System Maintenance")
        print("7. Data Import/Export")
        print("8. Return to main menu")
        
        choice = input("\nEnter your choice: ").strip()
        
        if choice == '1':
            manage_sla_policies(auth)
        elif choice == '2':
            manage_ticket_templates(auth)
        elif choice == '3':
            manage_workflows(auth)
        elif choice == '4':
            manage_departments(auth)
        elif choice == '5':
            manage_organizations(auth)
        elif choice == '6':
            system_maintenance(auth)
        elif choice == '7':
            data_import_export(auth)
        elif choice == '8':
            return
        else:
            print("Invalid choice. Please try again.")

def manage_sla_policies(auth):
    """Manage SLA policies"""
    print("\nSLA Policy Management")
    print("====================")
    print("1. View SLA policies")
    print("2. Create new SLA policy")
    print("3. Edit SLA policy")
    print("4. Activate/Deactivate SLA policy")
    print("5. Return to system management")
    
    choice = input("\nEnter your choice: ").strip()
    
    if choice == '1':
        view_sla_policies()
    elif choice == '2':
        create_sla_policy(auth)
    elif choice == '3':
        edit_sla_policy(auth)
    elif choice == '4':
        toggle_sla_policy(auth)

def view_sla_policies():
    """View existing SLA policies"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT sla_id, name, priority, impact, urgency, first_response_hours, 
           resolution_hours, escalation_hours, business_hours_only, is_active
    FROM sla_policies
    ORDER BY priority, impact, urgency
    ''')
    
    policies = cursor.fetchall()
    
    if policies:
        print("\nSLA Policies:")
        print("=" * 120)
        print(f"{'ID':<5} {'Name':<25} {'P/I/U':<10} {'Response':<8} {'Resolution':<10} {'Escalation':<10} {'Business':<8} {'Active':<6}")
        print("=" * 120)
        
        for policy in policies:
            p_i_u = f"{policy[2]}/{policy[3]}/{policy[4]}"
            business = "Yes" if policy[8] else "No"
            active = "Yes" if policy[9] else "No"
            
            print(f"{policy[0]:<5} {policy[1][:23]:<25} {p_i_u:<10} {policy[5]:<8}h "
                  f"{policy[6]:<10}h {policy[7]:<10}h {business:<8} {active:<6}")
        
        print("=" * 120)
    else:
        print("No SLA policies found.")
    
    conn.close()

def create_sla_policy(auth):
    """Create new SLA policy"""
    print("\nCreate New SLA Policy")
    print("====================")
    
    name = input("Policy name: ").strip()
    if not name:
        print("Name is required.")
        return
    
    description = input("Description: ").strip()
    
    # Priority, impact, urgency
    priority = get_priority_selection()
    impact = get_impact_selection()
    urgency = get_urgency_selection()
    
    # Time targets
    try:
        first_response = int(input("First response time (hours): ").strip())
        resolution = int(input("Resolution time (hours): ").strip())
        escalation = int(input("Escalation time (hours): ").strip())
    except ValueError:
        print("Invalid time values.")
        return
    
    business_hours = input("Business hours only? (y/n): ").strip().lower() == 'y'
    
    # Save policy
    conn = get_connection()
    cursor = conn.cursor()
    
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    try:
        cursor.execute('''
        INSERT INTO sla_policies
        (name, description, priority, impact, urgency, first_response_hours,
         resolution_hours, escalation_hours, business_hours_only, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (name, description, priority, impact, urgency, first_response,
              resolution, escalation, business_hours, now))
        
        conn.commit()
        sla_id = cursor.lastrowid
        
        print(f"\nSLA Policy #{sla_id} created successfully!")
        
    except sqlite3.Error as e:
        print(f"Error creating SLA policy: {e}")
    finally:
        conn.close()

def setup_enhanced_helpdesk_permissions():
    """Setup enhanced helpdesk permissions"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Check if the permissions table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='permissions'")
    if not cursor.fetchone():
        print("Permissions table not found. Please initialize the user authentication system first.")
        conn.close()
        return
    
    # Add enhanced helpdesk permissions
    try:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        permissions = [
            ('create_ticket', 'Can create support tickets'),
            ('view_own_tickets', 'Can view own support tickets'),
            ('reply_to_own_ticket', 'Can reply to own support tickets'),
            ('view_all_tickets', 'Can view all support tickets'),
            ('reply_to_any_ticket', 'Can reply to any support tickets'),
            ('manage_tickets', 'Can manage ticket status and priority'),
            ('manage_sla', 'Can manage SLA policies'),
            ('manage_workflows', 'Can manage automated workflows'),
            ('manage_kb', 'Can manage knowledge base articles'),
            ('view_analytics', 'Can view analytics and reports'),
            ('manage_departments', 'Can manage departments'),
            ('manage_organizations', 'Can manage organizations'),
            ('bulk_operations', 'Can perform bulk ticket operations'),
            ('system_admin', 'Full system administration access')
        ]
        
        # Add permissions if they don't already exist
        for perm_name, perm_desc in permissions:
            cursor.execute(
                "SELECT COUNT(*) FROM permissions WHERE permission_name = ?",
                (perm_name,)
            )
            if cursor.fetchone()[0] == 0:
                cursor.execute(
                    "INSERT INTO permissions (permission_name, description, created_at) VALUES (?, ?, ?)",
                    (perm_name, perm_desc, timestamp)
                )
        
        # Associate permissions with roles
        # Student role permissions
        cursor.execute("SELECT id FROM roles WHERE role_name = 'student'")
        student_role_id = cursor.fetchone()
        
        if student_role_id:
            student_perms = ['create_ticket', 'view_own_tickets', 'reply_to_own_ticket']
            for perm in student_perms:
                cursor.execute("SELECT id FROM permissions WHERE permission_name = ?", (perm,))
                perm_id = cursor.fetchone()
                if perm_id:
                    cursor.execute(
                        "INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)",
                        (student_role_id[0], perm_id[0])
                    )
        
        # Staff role permissions
        cursor.execute("SELECT id FROM roles WHERE role_name = 'staff'")
        staff_role_id = cursor.fetchone()
        
        if staff_role_id:
            staff_perms = ['create_ticket', 'view_own_tickets', 'reply_to_own_ticket',
                          'view_all_tickets', 'reply_to_any_ticket', 'manage_tickets']
            for perm in staff_perms:
                cursor.execute("SELECT id FROM permissions WHERE permission_name = ?", (perm,))
                perm_id = cursor.fetchone()
                if perm_id:
                    cursor.execute(
                        "INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)",
                        (staff_role_id[0], perm_id[0])
                    )
        
        # Admin role permissions (all permissions)
        cursor.execute("SELECT id FROM roles WHERE role_name = 'admin'")
        admin_role_id = cursor.fetchone()
        
        if admin_role_id:
            cursor.execute("SELECT id FROM permissions")
            all_permissions = cursor.fetchall()
            
            for perm_id in all_permissions:
                cursor.execute(
                    "INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)",
                    (admin_role_id[0], perm_id[0])
                )
        
        conn.commit()
        print("Enhanced helpdesk permissions setup successfully!")
        
    except sqlite3.Error as e:
        print(f"Error setting up enhanced helpdesk permissions: {e}")
    finally:
        conn.close()

def save_report_to_file(report_type, period, auth):
    """Save report data to file"""
    try:
        from university_system.modules.shared.constants import paths
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = str(paths.REPORTS_DIR / f"{report_type}_{period}_{timestamp}.txt")
        
        # This would contain the actual report generation logic
        with open(filename, 'w') as f:
            f.write(f"Helpdesk Report: {report_type}\n")
            f.write(f"Period: {period}\n")
            f.write(f"Generated by: {auth.current_user['username']}\n")
            f.write(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("\n" + "="*50 + "\n\n")
            f.write("Report data would go here...\n")
        
        print(f"Report saved to {filename}")
        
    except Exception as e:
        print(f"Error saving report: {e}")

        while True:
            choice = input("Select link type (1-6): ").strip()
            if choice in link_types:
                link_type = link_types[choice]
                break
            print("Invalid choice.")
        
        # Check if link already exists
        cursor.execute('''
        SELECT link_id FROM ticket_links 
        WHERE ticket_id = ? AND linked_ticket_id = ? AND link_type = ?
        ''', (ticket_id, linked_ticket_id, link_type))
        
        if cursor.fetchone():
            print("This link already exists.")
            conn.close()
            return
        
        # Create the link
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
        INSERT INTO ticket_links
        (ticket_id, linked_ticket_id, link_type, created_by, created_at)
        VALUES (?, ?, ?, ?, ?)
        ''', (ticket_id, linked_ticket_id, link_type, auth.current_user['id'], now))
        
        # Create reciprocal link for certain types
        reciprocal_map = {
            'blocks': 'blocked_by',
            'blocked_by': 'blocks',
            'parent_of': 'child_of',
            'child_of': 'parent_of',
            'related_to': 'related_to'
        }
        
        if link_type in reciprocal_map:
            reciprocal_type = reciprocal_map[link_type]
            cursor.execute('''
            INSERT INTO ticket_links
            (ticket_id, linked_ticket_id, link_type, created_by, created_at)
            VALUES (?, ?, ?, ?, ?)
            ''', (linked_ticket_id, ticket_id, reciprocal_type, auth.current_user['id'], now))
        
        conn.commit()
        
        # Log the action
        log_ticket_action(ticket_id, auth.current_user['id'], 'ticket_linked',
                         {}, {'linked_to': linked_ticket_id, 'link_type': link_type})
        
        print(f"\nTickets linked successfully: {link_type}")
        
    except ValueError:
        print("Invalid ticket ID.")
    except sqlite3.Error as e:
        print(f"Error linking tickets: {e}")
    finally:
        conn.close()

def escalate_ticket_manual(auth, ticket_id):
    """Manually escalate a ticket"""
    if not auth or not auth.current_user:
        print("You must be logged in to escalate tickets.")
        return
    
    if not auth.check_permission('manage_tickets'):
        print("You don't have permission to escalate tickets.")
        return
    
    reason = input("Escalation reason: ").strip()
    if not reason:
        reason = "Manual escalation"
    
    escalate_ticket(ticket_id, reason)
    print(f"Ticket #{ticket_id} escalated successfully.")

def send_satisfaction_survey(ticket_id):
    """Send customer satisfaction survey"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get ticket and customer info
    cursor.execute('''
    SELECT t.subject, u.username, u.email
    FROM support_tickets t
    JOIN users u ON t.user_id = u.id
    WHERE t.ticket_id = ?
    ''', (ticket_id,))
    
    ticket_info = cursor.fetchone()
    
    if ticket_info:
        try:
            # This would integrate with your email system
            print(f"Satisfaction survey sent to {ticket_info[1]} ({ticket_info[2]})")
            # send_satisfaction_survey_email(ticket_id, ticket_info[2], ticket_info[0])
        except Exception as e:
            print(f"Error sending satisfaction survey: {e}")
    
    conn.close()

# Analytics and Reporting Functions
def generate_analytics_dashboard(auth):
    """Generate comprehensive analytics dashboard"""
    if not auth or not auth.current_user:
        print("You must be logged in to view analytics.")
        return
    
    if not auth.check_permission('view_all_tickets'):
        print("You don't have permission to view analytics.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\nHelpdesk Analytics Dashboard")
    print("=" * 50)
    
    # Overall statistics
    print("\n📊 OVERALL STATISTICS")
    print("-" * 30)
    
    # Total tickets
    cursor.execute("SELECT COUNT(*) FROM support_tickets")
    total_tickets = cursor.fetchone()[0]
    print(f"Total Tickets: {total_tickets}")
    
    # Tickets by status
    cursor.execute('''
    SELECT status, COUNT(*) as count
    FROM support_tickets
    GROUP BY status
    ORDER BY count DESC
    ''')
    
    status_stats = cursor.fetchall()
    for status, count in status_stats:
        percentage = (count / total_tickets * 100) if total_tickets > 0 else 0
        print(f"  {status.title()}: {count} ({percentage:.1f}%)")
    
    # Response time statistics
    print("\n⏱️ RESPONSE TIME ANALYSIS")
    print("-" * 30)
    
    cursor.execute('''
    SELECT 
        AVG(CASE WHEN first_response_at IS NOT NULL 
            THEN (julianday(first_response_at) - julianday(created_at)) * 24 
            ELSE NULL END) as avg_first_response_hours,
        AVG(CASE WHEN resolved_at IS NOT NULL 
            THEN (julianday(resolved_at) - julianday(created_at)) * 24 
            ELSE NULL END) as avg_resolution_hours
    FROM support_tickets
    WHERE created_at >= date('now', '-30 days')
    ''')
    
    response_stats = cursor.fetchone()
    if response_stats[0]:
        print(f"Average First Response Time: {response_stats[0]:.1f} hours")
    if response_stats[1]:
        print(f"Average Resolution Time: {response_stats[1]:.1f} hours")
    
    # SLA compliance
    print("\n🎯 SLA COMPLIANCE")
    print("-" * 30)
    
    cursor.execute('''
    SELECT 
        COUNT(CASE WHEN due_date IS NULL OR resolved_at IS NULL OR resolved_at <= due_date THEN 1 END) as met_sla,
        COUNT(CASE WHEN due_date IS NOT NULL AND resolved_at IS NOT NULL AND resolved_at > due_date THEN 1 END) as missed_sla,
        COUNT(*) as total_with_sla
    FROM support_tickets
    WHERE due_date IS NOT NULL AND created_at >= date('now', '-30 days')
    ''')
    
    sla_stats = cursor.fetchone()
    if sla_stats[2] > 0:
        sla_compliance = (sla_stats[0] / sla_stats[2] * 100)
        print(f"SLA Compliance Rate: {sla_compliance:.1f}%")
        print(f"  Met SLA: {sla_stats[0]}")
        print(f"  Missed SLA: {sla_stats[1]}")
    
    # Category analysis
    print("\n📋 TICKET CATEGORIES")
    print("-" * 30)
    
    cursor.execute('''
    SELECT category, COUNT(*) as count
    FROM support_tickets
    WHERE created_at >= date('now', '-30 days')
    GROUP BY category
    ORDER BY count DESC
    ''')
    
    category_stats = cursor.fetchall()
    for category, count in category_stats:
        print(f"  {category}: {count}")
    
    # Staff performance
    print("\n👥 STAFF PERFORMANCE (Last 30 Days)")
    print("-" * 30)
    
    cursor.execute('''
    SELECT 
        u.username,
        COUNT(t.ticket_id) as assigned_tickets,
        COUNT(CASE WHEN t.status IN ('resolved', 'closed') THEN 1 END) as resolved_tickets,
        AVG(CASE WHEN t.resolved_at IS NOT NULL 
            THEN (julianday(t.resolved_at) - julianday(t.created_at)) * 24 
            ELSE NULL END) as avg_resolution_hours,
        COALESCE(SUM(tt.duration_minutes), 0) / 60.0 as total_hours
    FROM users u
    LEFT JOIN support_tickets t ON u.id = t.assigned_to AND t.created_at >= date('now', '-30 days')
    LEFT JOIN ticket_time_tracking tt ON t.ticket_id = tt.ticket_id AND tt.user_id = u.id
    WHERE u.role IN ('staff', 'admin') AND u.is_active = 1
    GROUP BY u.id, u.username
    HAVING assigned_tickets > 0
    ORDER BY resolved_tickets DESC
    ''')
    
    staff_stats = cursor.fetchall()
    for staff in staff_stats:
        username, assigned, resolved, avg_resolution, total_hours = staff
        resolution_rate = (resolved / assigned * 100) if assigned > 0 else 0
        print(f"  {username}:")
        print(f"    Assigned: {assigned}, Resolved: {resolved} ({resolution_rate:.1f}%)")
        if avg_resolution:
            print(f"    Avg Resolution Time: {avg_resolution:.1f} hours")
        print(f"    Total Time Logged: {total_hours:.1f} hours")
    
    # Customer satisfaction
    print("\n⭐ CUSTOMER SATISFACTION")
    print("-" * 30)
    
    cursor.execute('''
    SELECT 
        AVG(satisfaction_rating) as avg_rating,
        COUNT(satisfaction_rating) as total_ratings
    FROM support_tickets
    WHERE satisfaction_rating IS NOT NULL 
    AND created_at >= date('now', '-30 days')
    ''')
    
    satisfaction_stats = cursor.fetchone()
    if satisfaction_stats[1] > 0:
        print(f"Average Rating: {satisfaction_stats[0]:.1f}/5.0")
        print(f"Total Responses: {satisfaction_stats[1]}")
        
        # Rating distribution
        cursor.execute('''
        SELECT satisfaction_rating, COUNT(*) as count
        FROM support_tickets
        WHERE satisfaction_rating IS NOT NULL 
        AND created_at >= date('now', '-30 days')
        GROUP BY satisfaction_rating
        ORDER BY satisfaction_rating DESC
        ''')
        
        rating_dist = cursor.fetchall()
        for rating, count in rating_dist:
            percentage = (count / satisfaction_stats[1] * 100)
            print(f"  {rating} stars: {count} ({percentage:.1f}%)")
    
    # Trend analysis
    print("\n📈 TRENDS (Last 7 Days vs Previous 7 Days)")
    print("-" * 30)
    
    cursor.execute('''
    SELECT 
        COUNT(CASE WHEN created_at >= date('now', '-7 days') THEN 1 END) as recent_tickets,
        COUNT(CASE WHEN created_at >= date('now', '-14 days') AND created_at < date('now', '-7 days') THEN 1 END) as previous_tickets
    FROM support_tickets
    ''')
    
    trend_stats = cursor.fetchone()
    recent, previous = trend_stats
    
    if previous > 0:
        trend_percentage = ((recent - previous) / previous * 100)
        trend_direction = "📈" if trend_percentage > 0 else "📉" if trend_percentage < 0 else "➡️"
        print(f"Ticket Volume: {recent} vs {previous} {trend_direction} {abs(trend_percentage):.1f}%")
    
    conn.close()
    
    # Export option
    export_choice = input("\nExport analytics to file? (y/n): ").strip().lower()
    if export_choice == 'y':
        export_analytics_report(auth)

def export_analytics_report(auth):
    """Export analytics to a file"""
    try:
        from university_system.modules.shared.constants import paths
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = str(paths.REPORTS_DIR / f"analytics_report_{timestamp}.json")
        
        # Generate detailed analytics data
        conn = get_connection()
        cursor = conn.cursor()
        
        analytics_data = {
            'generated_at': datetime.now().isoformat(),
            'generated_by': auth.current_user['username'],
            'summary': {},
            'detailed_stats': {}
        }
        
        # Add comprehensive data collection here
        # This would include all the analytics from the dashboard function
        
        with open(filename, 'w') as f:
            json.dump(analytics_data, f, indent=2)
        
        print(f"Analytics report exported to {filename}")
        
        conn.close()
        
    except Exception as e:
        print(f"Error exporting analytics: {e}")

# Knowledge Base Management
def manage_knowledge_base(auth):
    """Manage knowledge base articles"""
    if not auth or not auth.current_user:
        print("You must be logged in to manage knowledge base.")
        return
    
    while True:
        print("\nKnowledge Base Management")
        print("=========================")
        print("1. View articles")
        print("2. Create new article")
        print("3. Edit article")
        print("4. Search articles")
        print("5. Article statistics")
        print("6. Return to main menu")
        
        choice = input("\nEnter your choice: ").strip()
        
        if choice == '1':
            view_kb_articles(auth)
        elif choice == '2':
            if auth.check_permission('manage_tickets'):
                create_kb_article(auth)
            else:
                print("You don't have permission to create articles.")
        elif choice == '3':
            if auth.check_permission('manage_tickets'):
                edit_kb_article(auth)
            else:
                print("You don't have permission to edit articles.")
        elif choice == '4':
            search_kb_articles(auth)
        elif choice == '5':
            if auth.check_permission('view_all_tickets'):
                kb_statistics(auth)
            else:
                print("You don't have permission to view statistics.")
        elif choice == '6':
            return
        else:
            print("Invalid choice. Please try again.")

def view_kb_articles(auth):
    """View knowledge base articles"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Show categories
    cursor.execute('''
    SELECT DISTINCT category FROM knowledge_base 
    WHERE status = 'published' AND category IS NOT NULL
    ORDER BY category
    ''')
    categories = [row[0] for row in cursor.fetchall()]
    
    if categories:
        print("\nCategories:")
        print("0. All categories")
        for i, cat in enumerate(categories, 1):
            print(f"{i}. {cat}")
        
        cat_choice = input("Select category (0 for all): ").strip()
        
        where_clause = "WHERE status = 'published'"
        params = []
        
        try:
            if cat_choice != '0':
                cat_idx = int(cat_choice) - 1
                if 0 <= cat_idx < len(categories):
                    where_clause += " AND category = ?"
                    params.append(categories[cat_idx])
        except ValueError:
            pass
        
        cursor.execute(f'''
        SELECT article_id, title, category, views, helpful_votes, unhelpful_votes, updated_at
        FROM knowledge_base 
        {where_clause}
        ORDER BY helpful_votes DESC, views DESC
        ''', params)
        
        articles = cursor.fetchall()
        
        if articles:
            print(f"\nKnowledge Base Articles:")
            print("=" * 80)
            print(f"{'ID':<5} {'Title':<40} {'Category':<15} {'Views':<8} {'Rating':<10}")
            print("=" * 80)
            
            for article in articles:
                total_votes = article[4] + article[5]  # helpful + unhelpful
                rating = f"{article[4]}/{total_votes}" if total_votes > 0 else "No votes"
                print(f"{article[0]:<5} {article[1][:38]:<40} {article[2][:13]:<15} "
                      f"{article[3]:<8} {rating:<10}")
            
            print("=" * 80)
            
            # View specific article
            article_choice = input("\nEnter article ID to view (or press Enter to return): ")
            if article_choice:
                try:
                    article_id = int(article_choice)
                    view_kb_article_detail(article_id)
                except ValueError:
                    print("Invalid article ID.")
        else:
            print("No articles found.")
    
    conn.close()

def view_kb_article_detail(article_id):
    """View detailed knowledge base article"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT kb.*, u.username as author
    FROM knowledge_base kb
    LEFT JOIN users u ON kb.author_id = u.id
    WHERE kb.article_id = ?
    ''', (article_id,))
    
    article = cursor.fetchone()
    
    if article:
        print(f"\n{'='*60}")
        print(f"ARTICLE #{article[0]}: {article[1]}")
        print(f"{'='*60}")
        print(f"Category: {article[3] or 'Uncategorized'}")
        print(f"Author: {article[-1] or 'Unknown'}")
        print(f"Status: {article[6]}")
        print(f"Views: {article[7]}")
        print(f"Helpful votes: {article[8]}")
        print(f"Unhelpful votes: {article[9]}")
        print(f"Created: {article[11]}")
        print(f"Updated: {article[12]}")
        if article[4]:  # tags
            print(f"Tags: {article[4]}")
        print(f"\n{'-'*60}")
        print("CONTENT:")
        print(f"{'-'*60}")
        print(article[2])  # content
        print(f"{'='*60}")
        
        # Update view count
        cursor.execute('''
        UPDATE knowledge_base SET views = views + 1 WHERE article_id = ?
        ''', (article_id,))
        conn.commit()
        
        # Rating option
        rating_choice = input("\nWas this article helpful? (y/n/skip): ").strip().lower()
        if rating_choice == 'y':
            cursor.execute('''
            UPDATE knowledge_base SET helpful_votes = helpful_votes + 1 WHERE article_id = ?
            ''', (article_id,))
            conn.commit()
            print("Thank you for your feedback!")
        elif rating_choice == 'n':
            cursor.execute('''
            UPDATE knowledge_base SET unhelpful_votes = unhelpful_votes + 1 WHERE article_id = ?
            ''', (article_id,))
            conn.commit()
            print("Thank you for your feedback!")
    else:
        print("Article not found.")
    
    conn.close()

def create_kb_article(auth):
    """Create new knowledge base article"""
    print("\nCreate Knowledge Base Article")
    print("=============================")
    
    title = input("Article title: ").strip()
    if not title:
        print("Title is required.")
        return
    
    category = input("Category: ").strip()
    tags = input("Tags (comma-separated): ").strip()
    
    print("\nEnter article content (type 'done' on a new line when finished):")
    content = ""
    while True:
        line = input()
        if line.lower() == 'done':
            break
        content += line + "\n"
    
    if not content.strip():
        print("Content is required.")
        return
    
    keywords = input("Search keywords (comma-separated): ").strip()
    
    status = 'draft'
    if auth.check_permission('manage_tickets'):
        publish = input("Publish immediately? (y/n): ").strip().lower()
        if publish == 'y':
            status = 'published'
    
    # Save article
    conn = get_connection()
    cursor = conn.cursor()
    
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    try:
        cursor.execute('''
        INSERT INTO knowledge_base
        (title, content, category, tags, author_id, status, search_keywords, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (title, content, category, tags, auth.current_user['id'], status, keywords, now, now))
        
        conn.commit()
        article_id = cursor.lastrowid
        
        print(f"\nArticle #{article_id} created successfully!")
        print(f"Status: {status}")
        
    except sqlite3.Error as e:
        print(f"Error creating article: {e}")
    finally:
        conn.close()

def search_kb_articles(auth):
    """Search knowledge base articles"""
    search_term = input("Enter search term: ").strip()
    if not search_term:
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Search in title, content, and keywords
    cursor.execute('''
    SELECT article_id, title, category, views, helpful_votes, unhelpful_votes
    FROM knowledge_base
    WHERE status = 'published' 
    AND (title LIKE ? OR content LIKE ? OR search_keywords LIKE ?)
    ORDER BY helpful_votes DESC, views DESC
    ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
    
    results = cursor.fetchall()
    
    if results:
        print(f"\nSearch Results for '{search_term}':")
        print("=" * 80)
        print(f"{'ID':<5} {'Title':<40} {'Category':<15} {'Views':<8} {'Rating':<10}")
        print("=" * 80)
        
        for article in results:
            total_votes = article[4] + article[5]
            rating = f"{article[4]}/{total_votes}" if total_votes > 0 else "No votes"
            print(f"{article[0]:<5} {article[1][:38]:<40} {article[2][:13]:<15} "
                  f"{article[3]:<8} {rating:<10}")
        
        print("=" * 80)
        
        # View specific article
        article_choice = input("\nEnter article ID to view (or press Enter to return): ")
        if article_choice:
            try:
                article_id = int(article_choice)
                view_kb_article_detail(article_id)
            except ValueError:
                print("Invalid article ID.")
    else:
        print(f"No articles found for '{search_term}'.")
    
    conn.close()

# Main enhanced menu function
def display_helpdesk_menu(auth):
    """Main menu for enhanced helpdesk system"""
    # Initialize enhanced helpdesk database
    init_helpdesk_db()
    
    # Setup permissions
    setup_enhanced_helpdesk_permissions()
    
    while True:
        print("\n" + "="*50)
        print("🎫 ENHANCED HELPDESK SYSTEM")
        print("="*50)
        
        # Check for overdue tickets (admin only)
        if auth.check_permission('view_all_tickets'):
            check_overdue_tickets(auth)
        
        options = []
        option_num = 1
        
        # User options
        if auth.check_permission('create_ticket'):
            print(f"{option_num}. 🆕 Create New Support Ticket")
            options.append('create_ticket')
            option_num += 1
        
        if auth.check_permission('view_own_tickets'):
            print(f"{option_num}. 📋 View My Support Tickets")
            options.append('view_own_tickets')
            option_num += 1
        
        # Search functionality
        print(f"{option_num}. 🔍 Advanced Search")
        options.append('advanced_search')
        option_num += 1
        
        if auth.current_user:
            print(f"{option_num}. 💾 Saved Searches")
            options.append('saved_searches')
            option_num += 1
        
        # Knowledge base
        print(f"{option_num}. 📚 Knowledge Base")
        options.append('knowledge_base')
        option_num += 1
        
        # Admin options
        if auth.check_permission('view_all_tickets'):
            print(f"{option_num}. 👥 View All Support Tickets")
            options.append('view_all_tickets')
            option_num += 1
            
            print(f"{option_num}. 📊 Analytics Dashboard")
            options.append('analytics')
            option_num += 1
            
            print(f"{option_num}. 📈 Generate Reports")
            options.append('generate_report')
            option_num += 1
            
            print(f"{option_num}. ⚙️ System Management")
            options.append('system_management')
            option_num += 1
        
        print(f"{option_num}. 🚪 Return to Main Menu")
        
        choice = input("\nEnter your choice: ").strip()
        
        try:
            choice_idx = int(choice) - 1
            
            if choice_idx == len(options):  # Return option
                print("Returning to main menu...")
                return
            elif 0 <= choice_idx < len(options):
                action = options[choice_idx]
                
                if action == 'create_ticket':
                    create_ticket_enhanced(auth)
                elif action == 'view_own_tickets':
                    view_user_tickets_enhanced(auth)
                elif action == 'advanced_search':
                    advanced_search_tickets(auth)
                elif action == 'saved_searches':
                    load_saved_searches(auth)
                elif action == 'knowledge_base':
                    manage_knowledge_base(auth)
                elif action == 'view_all_tickets':
                    view_all_tickets_enhanced(auth)
                elif action == 'analytics':
                    generate_analytics_dashboard(auth)
                elif action == 'generate_report':
                    generate_enhanced_ticket_report(auth)
                elif action == 'system_management':
                    system_management_menu(auth)
            else:
                print("Invalid choice. Please try again.")
        except ValueError:
            print("Invalid choice. Please try again.")

def check_overdue_tickets(auth):
    """Check for overdue tickets and display alert"""
    conn = get_connection()
    cursor = conn.cursor()
    
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute('''
    SELECT COUNT(*) FROM support_tickets
    WHERE due_date IS NOT NULL
    AND due_date < ?
    AND status NOT IN ('resolved', 'closed')
    ''', (now,))
    
    overdue_count = cursor.fetchone()[0]
    
    if overdue_count > 0:
        print(f"\n⚠️  ALERT: {overdue_count} tickets are overdue!")
    
    conn.close()

def view_user_tickets_enhanced(auth):
    """Enhanced view of user's own tickets"""
    if not auth or not auth.current_user:
        print("You must be logged in to view your support tickets.")
        return
    
    if not auth.check_permission('view_own_tickets'):
        print("You don't have permission to view support tickets.")
        return
    
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Filter options
    print("\nFilter Options:")
    print("1. All my tickets")
    print("2. Open tickets only")
    print("3. In progress tickets only")  
    print("4. Resolved/Closed tickets")
    
    filter_choice = input("Select filter (1-4): ").strip()
    
    where_clause = "WHERE user_id = ?"
    params = [auth.current_user['id']]
    
    if filter_choice == '2':
        where_clause += " AND status = 'open'"
    elif filter_choice == '3':
        where_clause += " AND status = 'in progress'"
    elif filter_choice == '4':
        where_clause += " AND status IN ('resolved', 'closed')"
    
    cursor.execute(f'''
    SELECT ticket_id, subject, category, subcategory, status, priority, impact, urgency,
           created_at, updated_at, due_date, assigned_to
    FROM support_tickets
    {where_clause}
    ORDER BY 
        CASE 
            WHEN status = 'open' THEN 1
            WHEN status = 'in progress' THEN 2
            WHEN status = 'waiting for customer' THEN 3
            WHEN status = 'resolved' THEN 4
            WHEN status = 'closed' THEN 5
        END,
        CASE 
            WHEN priority = 'high' THEN 1
            WHEN priority = 'medium' THEN 2
            WHEN priority = 'low' THEN 3
        END,
        updated_at DESC
    ''', params)
    
    tickets = cursor.fetchall()
    
    if not tickets:
        print("\nYou have no support tickets matching the selected filter.")
        conn.close()
        return
    
    print(f"\nYour Support Tickets ({len(tickets)} found):")
    print("=" * 100)
    print(f"{'ID':<5} {'Subject':<25} {'Category':<15} {'Status':<12} {'Priority':<8} {'Updated':<20}")
    print("=" * 100)
    
    for ticket in tickets:
        status_icon = {
            'open': '🆕',
            'in progress': '🔄', 
            'waiting for customer': '⏳',
            'resolved': '✅',
            'closed': '🔒'
        }.get(ticket['status'], '📋')
        
        print(f"{ticket['ticket_id']:<5} {ticket['subject'][:23]:<25} {ticket['category'][:13]:<15} "
              f"{status_icon} {ticket['status']:<10} {ticket['priority'].upper():<8} {ticket['updated_at']:<20}")
        
        # Show overdue indicator
        if ticket['due_date']:
            due_dt = datetime.strptime(ticket['due_date'], '%Y-%m-%d %H:%M:%S')
            if due_dt < datetime.now() and ticket['status'] not in ['resolved', 'closed']:
                print(f"      ⚠️  OVERDUE (Due: {ticket['due_date']})")
    
    print("=" * 100)

# Enhanced ticket creation with templates and attachments
def create_ticket_enhanced(auth):
    if not auth or not auth.current_user:
        print("You must be logged in to create a support ticket.")
        return
    
    if not auth.check_permission('create_ticket'):
        print("You don't have permission to create support tickets.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\nCreate New Support Ticket")
    print("=========================")
    
    # Show available templates
    cursor.execute('''
    SELECT template_id, name, description, category 
    FROM ticket_templates 
    WHERE is_active = 1 
    ORDER BY category, name
    ''')
    templates = cursor.fetchall()
    
    if templates:
        print("\nAvailable templates:")
        print("0. Create custom ticket")
        for i, template in enumerate(templates, 1):
            print(f"{i}. {template[1]} ({template[3]})")
        
        template_choice = input("\nSelect template (0 for custom): ").strip()
        
        try:
            if template_choice != '0':
                template_idx = int(template_choice) - 1
                if 0 <= template_idx < len(templates):
                    return create_ticket_from_template(auth, templates[template_idx][0])
        except ValueError:
            pass
    
    # Custom ticket creation
    return create_custom_ticket(auth)

def create_ticket_from_template(auth, template_id):
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get template details
    cursor.execute('''
    SELECT * FROM ticket_templates WHERE template_id = ?
    ''', (template_id,))
    template = cursor.fetchone()
    
    if not template:
        print("Template not found.")
        conn.close()
        return
    
    print(f"\nUsing template: {template[1]}")
    print(f"Description: {template[2]}")
    
    # Parse form fields if available
    form_fields = {}
    if template[9]:  # form_fields column
        try:
            form_data = json.loads(template[9])
            if 'fields' in form_data:
                print("\nPlease fill in the following information:")
                for field in form_data['fields']:
                    value = get_form_field_value(field)
                    form_fields[field['name']] = value
        except json.JSONDecodeError:
            pass
    
    # Generate subject and message from template
    subject = template[4] or ''  # subject_template
    message = template[5] or ''  # message_template
    
    # Replace placeholders with form field values
    for field_name, field_value in form_fields.items():
        placeholder = f'[{field_name.upper()}]'
        subject = subject.replace(placeholder, str(field_value))
        message = message.replace(placeholder, str(field_value))
    
    # Allow user to edit subject and message
    print(f"\nSubject: {subject}")
    new_subject = input("Edit subject (or press Enter to keep): ").strip()
    if new_subject:
        subject = new_subject
    
    print(f"\nMessage:\n{message}")
    print("\nEdit message (type 'done' on a new line when finished, or 'keep' to use template):")
    
    edit_choice = input().strip().lower()
    if edit_choice != 'keep':
        if edit_choice != 'done':
            message = edit_choice + "\n"
        
        while True:
            line = input()
            if line.lower() == 'done':
                break
            message += line + "\n"
    
    # Use template defaults
    category = template[3]  # category
    priority = template[6] or 'medium'  # default_priority
    impact = template[7] or 'low'  # default_impact
    urgency = template[8] or 'low'  # default_urgency
    
    # Create the ticket
    return create_ticket_with_details(auth, subject, message, category, priority, impact, urgency)

def get_form_field_value(field):
    field_name = field.get('name', '')
    field_type = field.get('type', 'text')
    required = field.get('required', False)
    options = field.get('options', [])
    
    while True:
        if field_type == 'select' and options:
            print(f"\n{field_name.replace('_', ' ').title()}:")
            for i, option in enumerate(options, 1):
                print(f"{i}. {option}")
            
            choice = input("Select option: ").strip()
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(options):
                    return options[idx]
                else:
                    print("Invalid selection.")
            except ValueError:
                print("Please enter a number.")
        else:
            prompt = f"{field_name.replace('_', ' ').title()}: "
            if field_type == 'textarea':
                print(f"\n{field_name.replace('_', ' ').title()} (type 'done' when finished):")
                value = ""
                while True:
                    line = input()
                    if line.lower() == 'done':
                        break
                    value += line + "\n"
                return value.strip()
            else:
                value = input(prompt).strip()
                
            if value or not required:
                return value
            else:
                print("This field is required.")

# Enhanced ticket detail view
def view_ticket_detail_enhanced(auth, ticket_id):
    if not auth or not auth.current_user:
        print("You must be logged in to view ticket details.")
        return
    
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Check permissions
    is_admin = auth.check_permission('view_all_tickets')
    
    if not is_admin:
        cursor.execute('''
        SELECT user_id FROM support_tickets WHERE ticket_id = ?
        ''', (ticket_id,))
        
        result = cursor.fetchone()
        if not result or result['user_id'] != auth.current_user['id']:
            print("You don't have permission to view this ticket.")
            conn.close()
            return
    
    # Get comprehensive ticket details
    cursor.execute('''
    SELECT t.*, u1.username as submitter, u1.email as submitter_email,
           u2.username as assignee, u2.email as assignee_email,
           d.name as dept_name, d.email as dept_email
    FROM support_tickets t
    JOIN users u1 ON t.user_id = u1.id
    LEFT JOIN users u2 ON t.assigned_to = u2.id
    LEFT JOIN departments d ON t.department = d.name
    WHERE t.ticket_id = ?
    ''', (ticket_id,))
    
    ticket = cursor.fetchone()
    
    if not ticket:
        print(f"Ticket #{ticket_id} not found.")
        conn.close()
        return
    
    # Display comprehensive ticket information
    print("\n" + "=" * 80)
    print(f"TICKET #{ticket['ticket_id']}: {ticket['subject']}")
    print("=" * 80)
    
    # Basic information
    print(f"Submitted by: {ticket['submitter']} ({ticket['submitter_email']})")
    print(f"Category: {ticket['category']}")
    if ticket['subcategory']:
        print(f"Subcategory: {ticket['subcategory']}")
    
    print(f"Status: {ticket['status'].upper()}")
    print(f"Priority: {ticket['priority'].upper()}")
    print(f"Impact: {ticket['impact'].upper()}")
    print(f"Urgency: {ticket['urgency'].upper()}")
    
    if ticket['assignee']:
        print(f"Assigned to: {ticket['assignee']} ({ticket['assignee_email']})")
    else:
        print("Assigned to: Unassigned")
    
    if ticket['department']:
        print(f"Department: {ticket['department']}")
    
    print(f"Source: {ticket['source'].upper()}")
    print(f"Created: {ticket['created_at']}")
    print(f"Last Updated: {ticket['updated_at']}")
    
    if ticket['due_date']:
        print(f"Due Date: {ticket['due_date']}")
        # Check if overdue
        due_dt = datetime.strptime(ticket['due_date'], '%Y-%m-%d %H:%M:%S')
        if due_dt < datetime.now():
            print("⚠️  OVERDUE")
    
    if ticket['first_response_at']:
        print(f"First Response: {ticket['first_response_at']}")
    
    if ticket['resolved_at']:
        print(f"Resolved: {ticket['resolved_at']}")
    
    if ticket['escalation_level'] > 0:
        print(f"Escalation Level: {ticket['escalation_level']}")
    
    if ticket['tags']:
        print(f"Tags: {ticket['tags']}")
    
    print("-" * 80)
    print("Original Message:")
    print(ticket['message'])
    print("-" * 80)
    
    # Display resolution if available
    if ticket['resolution']:
        print("Resolution:")
        print(ticket['resolution'])
        print("-" * 80)
    
    # Display attachments
    display_ticket_attachments(ticket_id)
    
    # Display linked tickets
    display_linked_tickets(ticket_id)
    
    # Display knowledge base suggestions
    display_kb_suggestions(ticket)
    
    # Display replies and internal notes
    display_ticket_replies(ticket_id, is_admin)
    
    # Display time tracking
    if is_admin:
        display_time_tracking(ticket_id)
    
    # Display escalation history
    if ticket['escalation_level'] > 0:
        display_escalation_history(ticket_id)
    
    # Display satisfaction rating
    if ticket['satisfaction_rating']:
        print(f"\nCustomer Satisfaction: {ticket['satisfaction_rating']}/5 stars")
        if ticket['satisfaction_feedback']:
            print(f"Feedback: {ticket['satisfaction_feedback']}")
    
    # Display audit trail for admins
    if is_admin:
        display_audit_trail(ticket_id)
    
    # Action menu
    display_ticket_actions(auth, ticket_id, ticket)
    
    conn.close()

def display_ticket_attachments(ticket_id):
    """Display ticket attachments"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT a.*, u.username 
    FROM ticket_attachments a
    JOIN users u ON a.uploaded_by = u.id
    WHERE a.ticket_id = ?
    ORDER BY a.created_at
    ''', (ticket_id,))
    
    attachments = cursor.fetchall()
    
    if attachments:
        print("\nAttachments:")
        print("-" * 80)
        for att in attachments:
            size_mb = att[4] / (1024 * 1024)  # file_size
            print(f"📎 {att[3]} ({size_mb:.2f} MB) - uploaded by {att[-1]} at {att[-2]}")
        print("-" * 80)
    
    conn.close()

def display_linked_tickets(ticket_id):
    """Display linked/related tickets"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get tickets linked to this one
    cursor.execute('''
    SELECT tl.link_type, t.ticket_id, t.subject, t.status, u.username
    FROM ticket_links tl
    JOIN support_tickets t ON tl.linked_ticket_id = t.ticket_id
    JOIN users u ON tl.created_by = u.id
    WHERE tl.ticket_id = ?
    ''', (ticket_id,))
    
    linked = cursor.fetchall()
    
    # Get tickets that link to this one
    cursor.execute('''
    SELECT tl.link_type, t.ticket_id, t.subject, t.status, u.username
    FROM ticket_links tl
    JOIN support_tickets t ON tl.ticket_id = t.ticket_id
    JOIN users u ON tl.created_by = u.id
    WHERE tl.linked_ticket_id = ?
    ''', (ticket_id,))
    
    linking = cursor.fetchall()
    
    if linked or linking:
        print("\nLinked Tickets:")
        print("-" * 80)
        
        # Display tickets this one links to
        for link in linked:
            link_type, linked_ticket_id, subject, status, created_by = link
            status_icon = {
                'open': '🆕',
                'in progress': '🔄',
                'waiting for customer': '⏳',
                'resolved': '✅',
                'closed': '🔒'
            }.get(status, '📋')
            
            print(f"🔗 {link_type.replace('_', ' ').title()}: Ticket #{linked_ticket_id} - {subject[:40]} ({status_icon} {status.upper()})")
        
        # Display tickets that link to this one
        for link in linking:
            link_type, linking_ticket_id, subject, status, created_by = link
            status_icon = {
                'open': '🆕',
                'in progress': '🔄',
                'waiting for customer': '⏳',
                'resolved': '✅',
                'closed': '🔒'
            }.get(status, '📋')
            
            # Convert link type to reverse perspective
            reverse_link_map = {
                'related_to': 'Related to',
                'duplicate_of': 'Duplicated by',
                'blocks': 'Blocked by',
                'blocked_by': 'Blocks',
                'parent_of': 'Child of',
                'child_of': 'Parent of'
            }
            
            reverse_type = reverse_link_map.get(link_type, link_type.replace('_', ' ').title())
            print(f"🔗 {reverse_type}: Ticket #{linking_ticket_id} - {subject[:40]} ({status_icon} {status.upper()})")
        
        print("-" * 80)
    
    conn.close()

def edit_sla_policy(auth):
    """Edit an existing SLA policy"""
    view_sla_policies()
    
    policy_id = input("\nEnter SLA policy ID to edit: ").strip()
    
    try:
        policy_id = int(policy_id)
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get current policy
        cursor.execute('''
        SELECT * FROM sla_policies WHERE sla_id = ?
        ''', (policy_id,))
        
        policy = cursor.fetchone()
        if not policy:
            print("SLA policy not found.")
            conn.close()
            return
        
        print(f"\nEditing SLA Policy: {policy[1]}")
        print(f"Current Response Time: {policy[5]} hours")
        print(f"Current Resolution Time: {policy[6]} hours")
        print(f"Current Escalation Time: {policy[7]} hours")
        
        # Get new values
        new_response = input(f"New response time (current: {policy[5]}): ").strip()
        new_resolution = input(f"New resolution time (current: {policy[6]}): ").strip()
        new_escalation = input(f"New escalation time (current: {policy[7]}): ").strip()
        
        # Update policy
        updates = []
        params = []
        
        if new_response:
            updates.append("first_response_hours = ?")
            params.append(int(new_response))
        
        if new_resolution:
            updates.append("resolution_hours = ?")
            params.append(int(new_resolution))
        
        if new_escalation:
            updates.append("escalation_hours = ?")
            params.append(int(new_escalation))
        
        if updates:
            params.append(policy_id)
            cursor.execute(f'''
            UPDATE sla_policies SET {", ".join(updates)} WHERE sla_id = ?
            ''', params)
            
            conn.commit()
            print("SLA policy updated successfully!")
        else:
            print("No changes made.")
        
        conn.close()
        
    except (ValueError, sqlite3.Error) as e:
        print(f"Error editing SLA policy: {e}")

def toggle_sla_policy(auth):
    """Activate or deactivate an SLA policy"""
    view_sla_policies()
    
    policy_id = input("\nEnter SLA policy ID to toggle: ").strip()
    
    try:
        policy_id = int(policy_id)
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get current status
        cursor.execute('''
        SELECT name, is_active FROM sla_policies WHERE sla_id = ?
        ''', (policy_id,))
        
        result = cursor.fetchone()
        if not result:
            print("SLA policy not found.")
            conn.close()
            return
        
        name, is_active = result
        new_status = not is_active
        
        cursor.execute('''
        UPDATE sla_policies SET is_active = ? WHERE sla_id = ?
        ''', (new_status, policy_id))
        
        conn.commit()
        conn.close()
        
        status_text = "activated" if new_status else "deactivated"
        print(f"SLA policy '{name}' has been {status_text}.")
        
    except (ValueError, sqlite3.Error) as e:
        print(f"Error toggling SLA policy: {e}")

def manage_ticket_templates(auth):
    """Manage ticket templates"""
    print("\nTicket Template Management")
    print("=========================")
    print("1. View templates")
    print("2. Create new template")
    print("3. Edit template")
    print("4. Activate/Deactivate template")
    print("5. Return to system management")
    
    choice = input("\nEnter your choice: ").strip()
    
    if choice == '1':
        view_ticket_templates()
    elif choice == '2':
        create_ticket_template(auth)
    elif choice == '3':
        edit_ticket_template(auth)
    elif choice == '4':
        toggle_ticket_template(auth)

def view_ticket_templates():
    """View existing ticket templates"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT template_id, name, category, default_priority, is_active
    FROM ticket_templates
    ORDER BY category, name
    ''')
    
    templates = cursor.fetchall()
    
    if templates:
        print("\nTicket Templates:")
        print("=" * 80)
        print(f"{'ID':<5} {'Name':<25} {'Category':<20} {'Priority':<10} {'Active':<6}")
        print("=" * 80)
        
        for template in templates:
            active = "Yes" if template[4] else "No"
            print(f"{template[0]:<5} {template[1][:23]:<25} {template[2][:18]:<20} "
                  f"{template[3]:<10} {active:<6}")
        
        print("=" * 80)
    else:
        print("No templates found.")
    
    conn.close()

def create_ticket_template(auth):
    """Create a new ticket template"""
    print("\nCreate New Ticket Template")
    print("==========================")
    
    name = input("Template name: ").strip()
    if not name:
        print("Name is required.")
        return
    
    description = input("Description: ").strip()
    category = input("Category: ").strip()
    
    subject_template = input("Subject template (use [FIELD_NAME] for placeholders): ").strip()
    
    print("\nEnter message template (type 'done' on a new line when finished):")
    message_template = ""
    while True:
        line = input()
        if line.lower() == 'done':
            break
        message_template += line + "\n"
    
    priority = get_priority_selection()
    impact = get_impact_selection()
    urgency = get_urgency_selection()
    
    # Save template
    conn = get_connection()
    cursor = conn.cursor()
    
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    try:
        cursor.execute('''
        INSERT INTO ticket_templates
        (name, description, category, subject_template, message_template,
         default_priority, default_impact, default_urgency, created_by, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (name, description, category, subject_template, message_template,
              priority, impact, urgency, auth.current_user['id'], now))
        
        conn.commit()
        template_id = cursor.lastrowid
        
        print(f"\nTemplate #{template_id} created successfully!")
        
    except sqlite3.Error as e:
        print(f"Error creating template: {e}")
    finally:
        conn.close()

def edit_ticket_template(auth):
    """Edit an existing ticket template"""
    view_ticket_templates()
    
    template_id = input("\nEnter template ID to edit: ").strip()
    
    try:
        template_id = int(template_id)
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get current template
        cursor.execute('''
        SELECT * FROM ticket_templates WHERE template_id = ?
        ''', (template_id,))
        
        template = cursor.fetchone()
        if not template:
            print("Template not found.")
            conn.close()
            return
        
        print(f"\nEditing Template: {template[1]}")
        
        # Get new values
        new_name = input(f"New name (current: {template[1]}): ").strip()
        new_description = input(f"New description (current: {template[2]}): ").strip()
        
        # Update template
        updates = []
        params = []
        
        if new_name:
            updates.append("name = ?")
            params.append(new_name)
        
        if new_description:
            updates.append("description = ?")
            params.append(new_description)
        
        if updates:
            params.append(template_id)
            cursor.execute(f'''
            UPDATE ticket_templates SET {", ".join(updates)} WHERE template_id = ?
            ''', params)
            
            conn.commit()
            print("Template updated successfully!")
        else:
            print("No changes made.")
        
        conn.close()
        
    except (ValueError, sqlite3.Error) as e:
        print(f"Error editing template: {e}")

def toggle_ticket_template(auth):
    """Activate or deactivate a ticket template"""
    view_ticket_templates()
    
    template_id = input("\nEnter template ID to toggle: ").strip()
    
    try:
        template_id = int(template_id)
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get current status
        cursor.execute('''
        SELECT name, is_active FROM ticket_templates WHERE template_id = ?
        ''', (template_id,))
        
        result = cursor.fetchone()
        if not result:
            print("Template not found.")
            conn.close()
            return
        
        name, is_active = result
        new_status = not is_active
        
        cursor.execute('''
        UPDATE ticket_templates SET is_active = ? WHERE template_id = ?
        ''', (new_status, template_id))
        
        conn.commit()
        conn.close()
        
        status_text = "activated" if new_status else "deactivated"
        print(f"Template '{name}' has been {status_text}.")
        
    except (ValueError, sqlite3.Error) as e:
        print(f"Error toggling template: {e}")

def manage_workflows(auth):
    """Manage automated workflows"""
    print("\nWorkflow Management")
    print("==================")
    print("1. View workflows")
    print("2. Create new workflow")
    print("3. Edit workflow")
    print("4. Activate/Deactivate workflow")
    print("5. Return to system management")
    
    choice = input("\nEnter your choice: ").strip()
    
    if choice == '1':
        view_workflows()
    elif choice == '2':
        create_workflow(auth)
    elif choice == '3':
        edit_workflow(auth)
    elif choice == '4':
        toggle_workflow(auth)

def view_workflows():
    """View existing workflows"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT workflow_id, name, trigger_type, is_active, created_at
    FROM ticket_workflows
    ORDER BY is_active DESC, name
    ''')
    
    workflows = cursor.fetchall()
    
    if workflows:
        print("\nWorkflows:")
        print("=" * 80)
        print(f"{'ID':<5} {'Name':<30} {'Trigger':<15} {'Active':<8} {'Created':<20}")
        print("=" * 80)
        
        for workflow in workflows:
            active = "Yes" if workflow[3] else "No"
            print(f"{workflow[0]:<5} {workflow[1][:28]:<30} {workflow[2]:<15} "
                  f"{active:<8} {workflow[4]:<20}")
        
        print("=" * 80)
    else:
        print("No workflows found.")
    
    conn.close()

def create_workflow(auth):
    """Create a new workflow"""
    print("\nCreate New Workflow")
    print("==================")
    
    name = input("Workflow name: ").strip()
    if not name:
        print("Name is required.")
        return
    
    description = input("Description: ").strip()
    
    print("\nTrigger types:")
    print("1. ticket_created")
    print("2. status_changed")
    print("3. reply_added")
    print("4. time_based")
    
    trigger_map = {
        '1': 'ticket_created',
        '2': 'status_changed',
        '3': 'reply_added',
        '4': 'time_based'
    }
    
    trigger_choice = input("Select trigger type (1-4): ").strip()
    if trigger_choice not in trigger_map:
        print("Invalid trigger type.")
        return
    
    trigger_type = trigger_map[trigger_choice]
    
    # Simple conditions and actions for demo
    conditions = {}
    actions = {}
    
    if trigger_type == 'ticket_created':
        category = input("Category condition (or press Enter to skip): ").strip()
        if category:
            conditions['category'] = category
    
    print("\nActions:")
    assign_dept = input("Auto-assign to department (or press Enter to skip): ").strip()
    if assign_dept:
        actions['assign_to_department'] = assign_dept
    
    set_priority = input("Set priority (low/medium/high, or press Enter to skip): ").strip()
    if set_priority in ['low', 'medium', 'high']:
        actions['set_priority'] = set_priority
    
    # Save workflow
    conn = get_connection()
    cursor = conn.cursor()
    
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    try:
        cursor.execute('''
        INSERT INTO ticket_workflows
        (name, description, trigger_type, trigger_conditions, actions, created_by, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (name, description, trigger_type, json.dumps(conditions), 
              json.dumps(actions), auth.current_user['id'], now))
        
        conn.commit()
        workflow_id = cursor.lastrowid
        
        print(f"\nWorkflow #{workflow_id} created successfully!")
        
    except sqlite3.Error as e:
        print(f"Error creating workflow: {e}")
    finally:
        conn.close()

def edit_workflow(auth):
    """Edit an existing workflow"""
    view_workflows()
    
    workflow_id = input("\nEnter workflow ID to edit: ").strip()
    
    try:
        workflow_id = int(workflow_id)
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get current workflow
        cursor.execute('''
        SELECT * FROM ticket_workflows WHERE workflow_id = ?
        ''', (workflow_id,))
        
        workflow = cursor.fetchone()
        if not workflow:
            print("Workflow not found.")
            conn.close()
            return
        
        print(f"\nEditing Workflow: {workflow[1]}")
        
        # Simple edit - just name and description
        new_name = input(f"New name (current: {workflow[1]}): ").strip()
        new_description = input(f"New description (current: {workflow[2]}): ").strip()
        
        # Update workflow
        updates = []
        params = []
        
        if new_name:
            updates.append("name = ?")
            params.append(new_name)
        
        if new_description:
            updates.append("description = ?")
            params.append(new_description)
        
        if updates:
            params.append(workflow_id)
            cursor.execute(f'''
            UPDATE ticket_workflows SET {", ".join(updates)} WHERE workflow_id = ?
            ''', params)
            
            conn.commit()
            print("Workflow updated successfully!")
        else:
            print("No changes made.")
        
        conn.close()
        
    except (ValueError, sqlite3.Error) as e:
        print(f"Error editing workflow: {e}")

def toggle_workflow(auth):
    """Activate or deactivate a workflow"""
    view_workflows()
    
    workflow_id = input("\nEnter workflow ID to toggle: ").strip()
    
    try:
        workflow_id = int(workflow_id)
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get current status
        cursor.execute('''
        SELECT name, is_active FROM ticket_workflows WHERE workflow_id = ?
        ''', (workflow_id,))
        
        result = cursor.fetchone()
        if not result:
            print("Workflow not found.")
            conn.close()
            return
        
        name, is_active = result
        new_status = not is_active
        
        cursor.execute('''
        UPDATE ticket_workflows SET is_active = ? WHERE workflow_id = ?
        ''', (new_status, workflow_id))
        
        conn.commit()
        conn.close()
        
        status_text = "activated" if new_status else "deactivated"
        print(f"Workflow '{name}' has been {status_text}.")
        
    except (ValueError, sqlite3.Error) as e:
        print(f"Error toggling workflow: {e}")

def manage_departments(auth):
    """Manage departments"""
    print("\nDepartment Management")
    print("====================")
    print("1. View departments")
    print("2. Create new department")
    print("3. Edit department")
    print("4. Activate/Deactivate department")
    print("5. Return to system management")
    
    choice = input("\nEnter your choice: ").strip()
    
    if choice == '1':
        view_departments()
    elif choice == '2':
        create_department(auth)
    elif choice == '3':
        edit_department(auth)
    elif choice == '4':
        toggle_department(auth)

def view_departments():
    """View existing departments"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT d.dept_id, d.name, d.email, u.username as manager, d.is_active
    FROM departments d
    LEFT JOIN users u ON d.manager_id = u.id
    ORDER BY d.name
    ''')
    
    departments = cursor.fetchall()
    
    if departments:
        print("\nDepartments:")
        print("=" * 80)
        print(f"{'ID':<5} {'Name':<20} {'Email':<25} {'Manager':<15} {'Active':<6}")
        print("=" * 80)
        
        for dept in departments:
            manager = dept[3] or 'None'
            active = "Yes" if dept[4] else "No"
            print(f"{dept[0]:<5} {dept[1][:18]:<20} {dept[2][:23]:<25} "
                  f"{manager[:13]:<15} {active:<6}")
        
        print("=" * 80)
    else:
        print("No departments found.")
    
    conn.close()

def create_department(auth):
    """Create a new department"""
    print("\nCreate New Department")
    print("====================")
    
    name = input("Department name: ").strip()
    if not name:
        print("Name is required.")
        return
    
    description = input("Description: ").strip()
    email = input("Department email: ").strip()
    
    # Save department
    conn = get_connection()
    cursor = conn.cursor()
    
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    try:
        cursor.execute('''
        INSERT INTO departments (name, description, email, created_at)
        VALUES (?, ?, ?, ?)
        ''', (name, description, email, now))
        
        conn.commit()
        dept_id = cursor.lastrowid
        
        print(f"\nDepartment #{dept_id} created successfully!")
        
    except sqlite3.Error as e:
        print(f"Error creating department: {e}")
    finally:
        conn.close()

def edit_department(auth):
    """Edit an existing department"""
    view_departments()
    
    dept_id = input("\nEnter department ID to edit: ").strip()
    
    try:
        dept_id = int(dept_id)
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get current department
        cursor.execute('''
        SELECT * FROM departments WHERE dept_id = ?
        ''', (dept_id,))
        
        dept = cursor.fetchone()
        if not dept:
            print("Department not found.")
            conn.close()
            return
        
        print(f"\nEditing Department: {dept[1]}")
        
        # Get new values
        new_name = input(f"New name (current: {dept[1]}): ").strip()
        new_email = input(f"New email (current: {dept[3]}): ").strip()
        
        # Update department
        updates = []
        params = []
        
        if new_name:
            updates.append("name = ?")
            params.append(new_name)
        
        if new_email:
            updates.append("email = ?")
            params.append(new_email)
        
        if updates:
            params.append(dept_id)
            cursor.execute(f'''
            UPDATE departments SET {", ".join(updates)} WHERE dept_id = ?
            ''', params)
            
            conn.commit()
            print("Department updated successfully!")
        else:
            print("No changes made.")
        
        conn.close()
        
    except (ValueError, sqlite3.Error) as e:
        print(f"Error editing department: {e}")

def toggle_department(auth):
    """Activate or deactivate a department"""
    view_departments()
    
    dept_id = input("\nEnter department ID to toggle: ").strip()
    
    try:
        dept_id = int(dept_id)
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get current status
        cursor.execute('''
        SELECT name, is_active FROM departments WHERE dept_id = ?
        ''', (dept_id,))
        
        result = cursor.fetchone()
        if not result:
            print("Department not found.")
            conn.close()
            return
        
        name, is_active = result
        new_status = not is_active
        
        cursor.execute('''
        UPDATE departments SET is_active = ? WHERE dept_id = ?
        ''', (new_status, dept_id))
        
        conn.commit()
        conn.close()
        
        status_text = "activated" if new_status else "deactivated"
        print(f"Department '{name}' has been {status_text}.")
        
    except (ValueError, sqlite3.Error) as e:
        print(f"Error toggling department: {e}")

def manage_organizations(auth):
    """Manage organizations"""
    print("\nOrganization Management")
    print("======================")
    print("1. View organizations")
    print("2. Create new organization")
    print("3. Edit organization")
    print("4. Return to system management")
    
    choice = input("\nEnter your choice: ").strip()
    
    if choice == '1':
        view_organizations()
    elif choice == '2':
        create_organization(auth)
    elif choice == '3':
        edit_organization(auth)

def view_organizations():
    """View existing organizations"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT org_id, name, domain, contact_email, is_active
    FROM organizations
    ORDER BY name
    ''')
    
    organizations = cursor.fetchall()
    
    if organizations:
        print("\nOrganizations:")
        print("=" * 80)
        print(f"{'ID':<5} {'Name':<25} {'Domain':<20} {'Contact Email':<25} {'Active':<6}")
        print("=" * 80)
        
        for org in organizations:
            active = "Yes" if org[4] else "No"
            domain = org[2] or ''
            email = org[3] or ''
            print(f"{org[0]:<5} {org[1][:23]:<25} {domain[:18]:<20} "
                  f"{email[:23]:<25} {active:<6}")
        
        print("=" * 80)
    else:
        print("No organizations found.")
    
    conn.close()

def create_organization(auth):
    """Create a new organization"""
    print("\nCreate New Organization")
    print("======================")
    
    name = input("Organization name: ").strip()
    if not name:
        print("Name is required.")
        return
    
    domain = input("Domain (optional): ").strip()
    contact_email = input("Contact email: ").strip()
    phone = input("Phone (optional): ").strip()
    address = input("Address (optional): ").strip()
    
    # Save organization
    conn = get_connection()
    cursor = conn.cursor()
    
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    try:
        cursor.execute('''
        INSERT INTO organizations (name, domain, contact_email, phone, address, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, domain, contact_email, phone, address, now))
        
        conn.commit()
        org_id = cursor.lastrowid
        
        print(f"\nOrganization #{org_id} created successfully!")
        
    except sqlite3.Error as e:
        print(f"Error creating organization: {e}")
    finally:
        conn.close()

def edit_organization(auth):
    """Edit an existing organization"""
    view_organizations()
    
    org_id = input("\nEnter organization ID to edit: ").strip()
    
    try:
        org_id = int(org_id)
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get current organization
        cursor.execute('''
        SELECT * FROM organizations WHERE org_id = ?
        ''', (org_id,))
        
        org = cursor.fetchone()
        if not org:
            print("Organization not found.")
            conn.close()
            return
        
        print(f"\nEditing Organization: {org[1]}")
        
        # Get new values
        new_name = input(f"New name (current: {org[1]}): ").strip()
        new_email = input(f"New contact email (current: {org[3]}): ").strip()
        
        # Update organization
        updates = []
        params = []
        
        if new_name:
            updates.append("name = ?")
            params.append(new_name)
        
        if new_email:
            updates.append("contact_email = ?")
            params.append(new_email)
        
        if updates:
            params.append(org_id)
            cursor.execute(f'''
            UPDATE organizations SET {", ".join(updates)} WHERE org_id = ?
            ''', params)
            
            conn.commit()
            print("Organization updated successfully!")
        else:
            print("No changes made.")
        
        conn.close()
        
    except (ValueError, sqlite3.Error) as e:
        print(f"Error editing organization: {e}")

def system_maintenance(auth):
    """System maintenance functions"""
    print("\nSystem Maintenance")
    print("==================")
    print("1. Database cleanup")
    print("2. Rebuild search indexes")
    print("3. Check data integrity")
    print("4. Backup database")
    print("5. Return to system management")
    
    choice = input("\nEnter your choice: ").strip()
    
    if choice == '1':
        database_cleanup(auth)
    elif choice == '2':
        rebuild_search_indexes(auth)
    elif choice == '3':
        check_data_integrity(auth)
    elif choice == '4':
        backup_database(auth)

def database_cleanup(auth):
    """Clean up old data"""
    print("\nDatabase Cleanup")
    print("================")
    
    days = input("Delete tickets older than how many days? (default: 365): ").strip()
    try:
        days = int(days) if days else 365
    except ValueError:
        days = 365
    
    confirm = input(f"This will delete tickets older than {days} days. Continue? (y/n): ").strip().lower()
    
    if confirm == 'y':
        conn = get_connection()
        cursor = conn.cursor()
        
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        # Delete old closed tickets
        cursor.execute('''
        DELETE FROM support_tickets 
        WHERE status = 'closed' AND created_at < ?
        ''', (cutoff_date,))
        
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        print(f"Deleted {deleted_count} old tickets.")
    else:
        print("Cleanup cancelled.")

def rebuild_search_indexes(auth):
    """Rebuild search indexes"""
    print("\nRebuilding search indexes...")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Update search keywords for knowledge base articles
        cursor.execute('''
        UPDATE knowledge_base 
        SET search_keywords = LOWER(title || ' ' || content || ' ' || COALESCE(tags, ''))
        ''')
        
        conn.commit()
        print("Search indexes rebuilt successfully!")
        
    except sqlite3.Error as e:
        print(f"Error rebuilding indexes: {e}")
    finally:
        conn.close()

def check_data_integrity(auth):
    """Check database integrity"""
    print("\nChecking Data Integrity")
    print("======================")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    issues = []
    
    # Check for orphaned tickets
    cursor.execute('''
    SELECT COUNT(*) FROM support_tickets t
    LEFT JOIN users u ON t.user_id = u.id
    WHERE u.id IS NULL
    ''')
    
    orphaned_tickets = cursor.fetchone()[0]
    if orphaned_tickets > 0:
        issues.append(f"{orphaned_tickets} tickets with invalid user_id")
    
    # Check for orphaned replies
    cursor.execute('''
    SELECT COUNT(*) FROM ticket_replies r
    LEFT JOIN support_tickets t ON r.ticket_id = t.ticket_id
    WHERE t.ticket_id IS NULL
    ''')
    
    orphaned_replies = cursor.fetchone()[0]
    if orphaned_replies > 0:
        issues.append(f"{orphaned_replies} replies with invalid ticket_id")
    
    conn.close()
    
    if issues:
        print("Data integrity issues found:")
        for issue in issues:
            print(f"- {issue}")
    else:
        print("No data integrity issues found.")

def backup_database(auth):
    """Backup database"""
    print("\nBacking up database...")
    
    try:
        import shutil
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"student_records_backup_{timestamp}.db"
        
        db_path = '/home/seancatchpole989/university_system/data/db_files/student_records.db'
        shutil.copy2(db_path, backup_filename)
        print(f"Database backed up to {backup_filename}")
        
    except Exception as e:
        print(f"Error backing up database: {e}")

def data_import_export(auth):
    """Data import/export functions"""
    print("\nData Import/Export")
    print("==================")
    print("1. Export tickets to CSV")
    print("2. Export users to CSV")
    print("3. Import tickets from CSV")
    print("4. Export analytics data")
    print("5. Return to system management")
    
    choice = input("\nEnter your choice: ").strip()
    
    if choice == '1':
        export_tickets_csv(auth)
    elif choice == '2':
        export_users_csv(auth)
    elif choice == '3':
        import_tickets_csv(auth)
    elif choice == '4':
        export_analytics_data(auth)

def export_tickets_csv(auth):
    """Export tickets to CSV"""
    try:
        import csv
        
        if not os.path.exists('exports'):
            os.makedirs('exports')
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"exports/tickets_export_{timestamp}.csv"
        
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT t.ticket_id, t.subject, t.category, t.status, t.priority,
               t.created_at, t.resolved_at, u1.username as submitter,
               u2.username as assignee, t.department
        FROM support_tickets t
        JOIN users u1 ON t.user_id = u1.id
        LEFT JOIN users u2 ON t.assigned_to = u2.id
        ORDER BY t.ticket_id
        ''')
        
        tickets = cursor.fetchall()
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['ticket_id', 'subject', 'category', 'status', 'priority',
                         'created_at', 'resolved_at', 'submitter', 'assignee', 'department']
            
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for ticket in tickets:
                writer.writerow({
                    'ticket_id': ticket[0],
                    'subject': ticket[1],
                    'category': ticket[2],
                    'status': ticket[3],
                    'priority': ticket[4],
                    'created_at': ticket[5],
                    'resolved_at': ticket[6] or '',
                    'submitter': ticket[7],
                    'assignee': ticket[8] or '',
                    'department': ticket[9] or ''
                })
        
        conn.close()
        print(f"Tickets exported to {filename}")
        
    except Exception as e:
        print(f"Error exporting tickets: {e}")

def export_users_csv(auth):
    """Export users to CSV"""
    try:
        import csv
        
        if not os.path.exists('exports'):
            os.makedirs('exports')
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"exports/users_export_{timestamp}.csv"
        
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT id, username, email, role, department, is_active, created_at
        FROM users
        ORDER BY id
        ''')
        
        users = cursor.fetchall()
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['id', 'username', 'email', 'role', 'department', 'is_active', 'created_at']
            
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for user in users:
                writer.writerow({
                    'id': user[0],
                    'username': user[1],
                    'email': user[2],
                    'role': user[3],
                    'department': user[4] or '',
                    'is_active': user[5],
                    'created_at': user[6]
                })
        
        conn.close()
        print(f"Users exported to {filename}")
        
    except Exception as e:
        print(f"Error exporting users: {e}")

def import_tickets_csv(auth):
    """Import tickets from CSV"""
    filename = input("Enter CSV filename to import: ").strip()
    
    if not os.path.exists(filename):
        print("File not found.")
        return
    
    try:
        import csv
        
        conn = get_connection()
        cursor = conn.cursor()
        
        imported_count = 0
        
        with open(filename, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            
            for row in reader:
                # Validate required fields
                if not all(k in row for k in ['subject', 'message', 'category', 'submitter']):
                    print(f"Skipping row due to missing required fields: {row}")
                    continue
                
                # Get user ID for submitter
                cursor.execute('SELECT id FROM users WHERE username = ?', (row['submitter'],))
                user_result = cursor.fetchone()
                
                if not user_result:
                    print(f"User not found: {row['submitter']}")
                    continue
                
                user_id = user_result[0]
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # Insert ticket
                cursor.execute('''
                INSERT INTO support_tickets
                (user_id, subject, message, category, status, priority, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (user_id, row['subject'], row.get('message', ''), row['category'],
                      row.get('status', 'open'), row.get('priority', 'medium'), now, now))
                
                imported_count += 1
        
        conn.commit()
        conn.close()
        
        print(f"Successfully imported {imported_count} tickets from {filename}")
        
    except Exception as e:
        print(f"Error importing tickets: {e}")

def export_analytics_data(auth):
    """Export analytics data"""
    try:
        if not os.path.exists('exports'):
            os.makedirs('exports')
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"exports/analytics_export_{timestamp}.json"
        
        conn = get_connection()
        cursor = conn.cursor()
        
        analytics_data = {
            'generated_at': datetime.now().isoformat(),
            'generated_by': auth.current_user['username'],
            'summary': {},
            'detailed_stats': {}
        }
        
        # Total ticket counts
        cursor.execute('SELECT COUNT(*) FROM support_tickets')
        analytics_data['summary']['total_tickets'] = cursor.fetchone()[0]
        
        # Tickets by status
        cursor.execute('''
        SELECT status, COUNT(*) FROM support_tickets GROUP BY status
        ''')
        analytics_data['summary']['tickets_by_status'] = dict(cursor.fetchall())
        
        # Tickets by category
        cursor.execute('''
        SELECT category, COUNT(*) FROM support_tickets GROUP BY category
        ''')
        analytics_data['summary']['tickets_by_category'] = dict(cursor.fetchall())
        
        # Monthly ticket trends (last 12 months)
        cursor.execute('''
        SELECT strftime('%Y-%m', created_at) as month, COUNT(*) as count
        FROM support_tickets
        WHERE created_at >= date('now', '-12 months')
        GROUP BY month
        ORDER BY month
        ''')
        analytics_data['detailed_stats']['monthly_trends'] = dict(cursor.fetchall())
        
        conn.close()
        
        with open(filename, 'w') as f:
            json.dump(analytics_data, f, indent=2)
        
        print(f"Analytics data exported to {filename}")
        
    except Exception as e:
        print(f"Error exporting analytics: {e}")

def generate_staff_performance_report(auth):
    """Generate staff performance report"""
    print("\nStaff Performance Report")
    print("=" * 50)
    
    # Time period selection
    period = input("Select period (7d/30d/90d): ").strip().lower()
    days_map = {'7d': 7, '30d': 30, '90d': 90}
    days = days_map.get(period, 30)
    
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT 
        u.username,
        u.department,
        COUNT(t.ticket_id) as assigned_tickets,
        COUNT(CASE WHEN t.status IN ('resolved', 'closed') THEN 1 END) as resolved_tickets,
        AVG(CASE WHEN t.resolved_at IS NOT NULL 
            THEN (julianday(t.resolved_at) - julianday(t.created_at)) * 24 
            ELSE NULL END) as avg_resolution_hours,
        COALESCE(SUM(tt.duration_minutes), 0) / 60.0 as total_hours,
        AVG(t.satisfaction_rating) as avg_satisfaction
    FROM users u
    LEFT JOIN support_tickets t ON u.id = t.assigned_to AND t.created_at >= ?
    LEFT JOIN ticket_time_tracking tt ON t.ticket_id = tt.ticket_id AND tt.user_id = u.id
    WHERE u.role IN ('staff', 'admin') AND u.is_active = 1
    GROUP BY u.id, u.username, u.department
    HAVING assigned_tickets > 0
    ORDER BY resolved_tickets DESC
    ''', (start_date,))
    
    staff_stats = cursor.fetchall()
    
    if staff_stats:
        print(f"\nStaff Performance ({period.upper()}):")
        print("=" * 100)
        print(f"{'Staff':<15} {'Dept':<12} {'Assigned':<8} {'Resolved':<8} {'Rate%':<6} {'Avg Hours':<10} {'Total Hrs':<10} {'Satisfaction':<12}")
        print("=" * 100)
        
        for staff in staff_stats:
            username, dept, assigned, resolved, avg_resolution, total_hours, avg_satisfaction = staff
            resolution_rate = (resolved / assigned * 100) if assigned > 0 else 0
            dept_display = (dept or 'None')[:10]
            
            print(f"{username[:13]:<15} {dept_display:<12} {assigned:<8} {resolved:<8} "
                  f"{resolution_rate:.1f}%{'':<2} {avg_resolution or 0:.1f}h{'':<5} "
                  f"{total_hours:.1f}h{'':<5} {avg_satisfaction or 0:.1f}/5.0{'':<7}")
        
        print("=" * 100)
    else:
        print("No staff performance data found.")
    
    conn.close()

def generate_sla_compliance_report(auth):
    """Generate SLA compliance report"""
    print("\nSLA Compliance Report")
    print("=" * 50)
    
    period = input("Select period (7d/30d/90d): ").strip().lower()
    days_map = {'7d': 7, '30d': 30, '90d': 90}
    days = days_map.get(period, 30)
    
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Overall SLA compliance
    cursor.execute('''
    SELECT 
        COUNT(*) as total_tickets,
        COUNT(CASE WHEN due_date IS NOT NULL AND resolved_at IS NOT NULL 
                   AND resolved_at <= due_date THEN 1 END) as met_sla,
        COUNT(CASE WHEN due_date IS NOT NULL AND resolved_at IS NOT NULL 
                   AND resolved_at > due_date THEN 1 END) as missed_sla,
        COUNT(CASE WHEN due_date IS NOT NULL AND resolved_at IS NULL 
                   AND due_date < datetime('now') THEN 1 END) as overdue
    FROM support_tickets
    WHERE created_at >= ? AND due_date IS NOT NULL
    ''', (start_date,))
    
    sla_stats = cursor.fetchone()
    
    if sla_stats[0] > 0:
        total, met, missed, overdue = sla_stats
        compliance_rate = (met / total * 100) if total > 0 else 0
        
        print(f"\nOverall SLA Compliance ({period.upper()}):")
        print("-" * 40)
        print(f"Total tickets with SLA: {total}")
        print(f"Met SLA: {met} ({compliance_rate:.1f}%)")
        print(f"Missed SLA: {missed}")
        print(f"Currently overdue: {overdue}")
        
        # SLA compliance by priority
        print(f"\nSLA Compliance by Priority:")
        print("-" * 40)
        
        cursor.execute('''
        SELECT 
            priority,
            COUNT(*) as total,
            COUNT(CASE WHEN resolved_at <= due_date THEN 1 END) as met
        FROM support_tickets
        WHERE created_at >= ? AND due_date IS NOT NULL AND resolved_at IS NOT NULL
        GROUP BY priority
        ORDER BY priority
        ''', (start_date,))
        
        priority_stats = cursor.fetchall()
        
        for priority, total, met in priority_stats:
            rate = (met / total * 100) if total > 0 else 0
            print(f"{priority.capitalize()}: {met}/{total} ({rate:.1f}%)")
    else:
        print("No SLA data found for the selected period.")
    
    conn.close()

def generate_satisfaction_report(auth):
    """Generate customer satisfaction report"""
    print("\nCustomer Satisfaction Report")
    print("=" * 50)
    
    period = input("Select period (7d/30d/90d): ").strip().lower()
    days_map = {'7d': 7, '30d': 30, '90d': 90}
    days = days_map.get(period, 30)
    
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Overall satisfaction
    cursor.execute('''
    SELECT 
        AVG(satisfaction_rating) as avg_rating,
        COUNT(satisfaction_rating) as total_responses,
        COUNT(CASE WHEN satisfaction_rating >= 4 THEN 1 END) as positive_responses
    FROM support_tickets
    WHERE created_at >= ? AND satisfaction_rating IS NOT NULL
    ''', (start_date,))
    
    satisfaction_stats = cursor.fetchone()
    
    if satisfaction_stats[1] > 0:  # total_responses
        avg_rating, total_responses, positive_responses = satisfaction_stats
        satisfaction_rate = (positive_responses / total_responses * 100)
        
        print(f"\nOverall Satisfaction ({period.upper()}):")
        print("-" * 40)
        print(f"Average Rating: {avg_rating:.1f}/5.0")
        print(f"Total Responses: {total_responses}")
        print(f"Positive Ratings (4-5 stars): {positive_responses} ({satisfaction_rate:.1f}%)")
        
        # Rating distribution
        cursor.execute('''
        SELECT satisfaction_rating, COUNT(*) as count
        FROM support_tickets
        WHERE created_at >= ? AND satisfaction_rating IS NOT NULL
        GROUP BY satisfaction_rating
        ORDER BY satisfaction_rating DESC
        ''', (start_date,))
        
        rating_dist = cursor.fetchall()
        
        print(f"\nRating Distribution:")
        print("-" * 40)
        for rating, count in rating_dist:
            percentage = (count / total_responses * 100)
            stars = "⭐" * int(rating)
            print(f"{stars} ({rating}): {count} ({percentage:.1f}%)")
        
        # Satisfaction by category
        print(f"\nSatisfaction by Category:")
        print("-" * 40)
        
        cursor.execute('''
        SELECT category, AVG(satisfaction_rating) as avg_rating, COUNT(*) as count
        FROM support_tickets
        WHERE created_at >= ? AND satisfaction_rating IS NOT NULL
        GROUP BY category
        ORDER BY avg_rating DESC
        ''', (start_date,))
        
        category_stats = cursor.fetchall()
        
        for category, avg_rating, count in category_stats:
            print(f"{category}: {avg_rating:.1f}/5.0 ({count} responses)")
    else:
        print("No satisfaction data found for the selected period.")
    
    conn.close()

def generate_trend_analysis_report(auth):
    """Generate trend analysis report"""
    print("\nTrend Analysis Report")
    print("=" * 50)
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Monthly ticket trends (last 12 months)
    print(f"\nMonthly Ticket Trends (Last 12 Months):")
    print("-" * 50)
    
    cursor.execute('''
    SELECT 
        strftime('%Y-%m', created_at) as month,
        COUNT(*) as total_tickets,
        COUNT(CASE WHEN status IN ('resolved', 'closed') THEN 1 END) as resolved_tickets
    FROM support_tickets
    WHERE created_at >= date('now', '-12 months')
    GROUP BY month
    ORDER BY month
    ''')
    
    monthly_trends = cursor.fetchall()
    
    if monthly_trends:
        print(f"{'Month':<10} {'Total':<8} {'Resolved':<10} {'Resolution %':<12}")
        print("-" * 50)
        
        for month, total, resolved in monthly_trends:
            resolution_rate = (resolved / total * 100) if total > 0 else 0
            print(f"{month:<10} {total:<8} {resolved:<10} {resolution_rate:.1f}%")
    
    # Weekly trends (last 8 weeks)
    print(f"\nWeekly Ticket Trends (Last 8 Weeks):")
    print("-" * 50)
    
    cursor.execute('''
    SELECT 
        strftime('%Y-W%W', created_at) as week,
        COUNT(*) as total_tickets
    FROM support_tickets
    WHERE created_at >= date('now', '-8 weeks')
    GROUP BY week
    ORDER BY week
    ''')
    
    weekly_trends = cursor.fetchall()
    
    if weekly_trends:
        print(f"{'Week':<10} {'Tickets':<8}")
        print("-" * 20)
        
        for week, total in weekly_trends:
            print(f"{week:<10} {total:<8}")
    
    conn.close()

def generate_department_report(auth):
    """Generate department performance report"""
    print("\nDepartment Performance Report")
    print("=" * 50)
    
    period = input("Select period (7d/30d/90d): ").strip().lower()
    days_map = {'7d': 7, '30d': 30, '90d': 90}
    days = days_map.get(period, 30)
    
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT 
        COALESCE(t.department, 'Unassigned') as department,
        COUNT(t.ticket_id) as total_tickets,
        COUNT(CASE WHEN t.status IN ('resolved', 'closed') THEN 1 END) as resolved_tickets,
        AVG(CASE WHEN t.resolved_at IS NOT NULL 
            THEN (julianday(t.resolved_at) - julianday(t.created_at)) * 24 
            ELSE NULL END) as avg_resolution_hours,
        AVG(t.satisfaction_rating) as avg_satisfaction
    FROM support_tickets t
    WHERE t.created_at >= ?
    GROUP BY t.department
    HAVING total_tickets > 0
    ORDER BY total_tickets DESC
    ''', (start_date,))
    
    dept_stats = cursor.fetchall()
    
    if dept_stats:
        print(f"\nDepartment Performance ({period.upper()}):")
        print("=" * 80)
        print(f"{'Department':<15} {'Total':<8} {'Resolved':<10} {'Rate%':<8} {'Avg Hours':<12} {'Satisfaction':<12}")
        print("=" * 80)
        
        for dept, total, resolved, avg_hours, avg_satisfaction in dept_stats:
            resolution_rate = (resolved / total * 100) if total > 0 else 0
            dept_display = dept[:13]
            
            print(f"{dept_display:<15} {total:<8} {resolved:<10} {resolution_rate:.1f}%{'':<4} "
                  f"{avg_hours or 0:.1f}h{'':<7} {avg_satisfaction or 0:.1f}/5.0{'':<7}")
        
        print("=" * 80)
    else:
        print("No department data found.")
    
    conn.close()

def generate_custom_date_report(auth):
    """Generate custom date range report"""
    print("\nCustom Date Range Report")
    print("=" * 50)
    
    start_date = input("Start date (YYYY-MM-DD): ").strip()
    end_date = input("End date (YYYY-MM-DD): ").strip()
    
    try:
        # Validate dates
        datetime.strptime(start_date, '%Y-%m-%d')
        datetime.strptime(end_date, '%Y-%m-%d')
    except ValueError:
        print("Invalid date format. Please use YYYY-MM-DD.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Basic statistics for the date range
    cursor.execute('''
    SELECT 
        COUNT(*) as total_tickets,
        COUNT(CASE WHEN status IN ('resolved', 'closed') THEN 1 END) as resolved_tickets,
        AVG(CASE WHEN resolved_at IS NOT NULL 
            THEN (julianday(resolved_at) - julianday(created_at)) * 24 
            ELSE NULL END) as avg_resolution_hours,
        AVG(satisfaction_rating) as avg_satisfaction
    FROM support_tickets
    WHERE DATE(created_at) BETWEEN ? AND ?
    ''', (start_date, end_date))
    
    stats = cursor.fetchone()
    
    if stats[0] > 0:  # total_tickets
        total, resolved, avg_hours, avg_satisfaction = stats
        resolution_rate = (resolved / total * 100) if total > 0 else 0
        
        print(f"\nCustom Report ({start_date} to {end_date}):")
        print("-" * 50)
        print(f"Total Tickets: {total}")
        print(f"Resolved Tickets: {resolved} ({resolution_rate:.1f}%)")
        
        if avg_hours:
            print(f"Average Resolution Time: {avg_hours:.1f} hours")
        
        if avg_satisfaction:
            print(f"Average Satisfaction: {avg_satisfaction:.1f}/5.0")
        
        # Category breakdown
        print(f"\nTickets by Category:")
        print("-" * 30)
        
        cursor.execute('''
        SELECT category, COUNT(*) as count
        FROM support_tickets
        WHERE DATE(created_at) BETWEEN ? AND ?
        GROUP BY category
        ORDER BY count DESC
        ''', (start_date, end_date))
        
        categories = cursor.fetchall()
        
        for category, count in categories:
            percentage = (count / total * 100)
            print(f"{category}: {count} ({percentage:.1f}%)")
    else:
        print(f"No tickets found for the date range {start_date} to {end_date}.")
    
    conn.close()

def edit_kb_article(auth):
    """Edit an existing knowledge base article"""
    print("\nEdit Knowledge Base Article")
    print("===========================")
    
    article_id = input("Enter article ID to edit: ").strip()
    
    try:
        article_id = int(article_id)
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get current article
        cursor.execute('''
        SELECT * FROM knowledge_base WHERE article_id = ?
        ''', (article_id,))
        
        article = cursor.fetchone()
        if not article:
            print("Article not found.")
            conn.close()
            return
        
        # Check if user can edit (author or admin)
        if article[5] != auth.current_user['id'] and not auth.check_permission('manage_tickets'):
            print("You don't have permission to edit this article.")
            conn.close()
            return
        
        print(f"\nEditing Article: {article[1]}")
        
        # Get new values
        new_title = input(f"New title (current: {article[1]}): ").strip()
        new_category = input(f"New category (current: {article[3]}): ").strip()
        
        edit_content = input("Edit content? (y/n): ").strip().lower()
        new_content = None
        
        if edit_content == 'y':
            print("Enter new content (type 'done' on a new line when finished):")
            new_content = ""
            while True:
                line = input()
                if line.lower() == 'done':
                    break
                new_content += line + "\n"
        
        # Update article
        updates = []
        params = []
        
        if new_title:
            updates.append("title = ?")
            params.append(new_title)
        
        if new_category:
            updates.append("category = ?")
            params.append(new_category)
        
        if new_content:
            updates.append("content = ?")
            params.append(new_content)
        
        if updates:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            updates.append("updated_at = ?")
            params.append(now)
            params.append(article_id)
            
            cursor.execute(f'''
            UPDATE knowledge_base SET {", ".join(updates)} WHERE article_id = ?
            ''', params)
            
            conn.commit()
            print("Article updated successfully!")
        else:
            print("No changes made.")
        
        conn.close()
        
    except (ValueError, sqlite3.Error) as e:
        print(f"Error editing article: {e}")

def kb_statistics(auth):
    """Display knowledge base statistics"""
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\nKnowledge Base Statistics")
    print("=" * 50)
    
    # Total articles
    cursor.execute('SELECT COUNT(*) FROM knowledge_base WHERE status = "published"')
    total_articles = cursor.fetchone()[0]
    print(f"Total Published Articles: {total_articles}")
    
    # Most viewed articles
    print(f"\nMost Viewed Articles:")
    print("-" * 40)
    
    cursor.execute('''
    SELECT title, views FROM knowledge_base 
    WHERE status = 'published' 
    ORDER BY views DESC 
    LIMIT 5
    ''')
    
    top_viewed = cursor.fetchall()
    
    for title, views in top_viewed:
        print(f"{title[:35]}: {views} views")
    
    # Most helpful articles
    print(f"\nMost Helpful Articles:")
    print("-" * 40)
    
    cursor.execute('''
    SELECT title, helpful_votes, unhelpful_votes 
    FROM knowledge_base 
    WHERE status = 'published' AND (helpful_votes + unhelpful_votes) > 0
    ORDER BY (helpful_votes * 1.0 / (helpful_votes + unhelpful_votes)) DESC 
    LIMIT 5
    ''')
    
    top_helpful = cursor.fetchall()
    
    for title, helpful, unhelpful in top_helpful:
        total_votes = helpful + unhelpful
        helpfulness = (helpful / total_votes * 100) if total_votes > 0 else 0
        print(f"{title[:35]}: {helpfulness:.1f}% helpful ({total_votes} votes)")
    
    # Articles by category
    print(f"\nArticles by Category:")
    print("-" * 40)
    
    cursor.execute('''
    SELECT category, COUNT(*) as count
    FROM knowledge_base 
    WHERE status = 'published'
    GROUP BY category
    ORDER BY count DESC
    ''')
    
    categories = cursor.fetchall()
    
    for category, count in categories:
        print(f"{category or 'Uncategorized'}: {count}")
    
    conn.close()